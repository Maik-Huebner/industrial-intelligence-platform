"""Typed read API backed by PostgreSQL and the Neo4j domain graph."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from industrial_intelligence.database import neo4j as graph_store
from industrial_intelligence.database import postgres as relational_store
from industrial_intelligence.database.neo4j import Neo4jUnavailable
from industrial_intelligence.database.postgres import PostgresUnavailable

app = FastAPI(
    title="Industrial Intelligence API",
    version="0.2.0",
    description=(
        "Read-only decision support for synthetic industrial maintenance data. "
        "This local portfolio API has no authentication and must not be exposed publicly."
    ),
)

MachineId = Annotated[str, Path(pattern=r"^M-[0-9]{3}$")]


class MachineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    machine_id: str
    line_id: str
    machine_type: str
    installed_year: int
    criticality: int
    manufacturer: str


class MetricResponse(BaseModel):
    machine_id: str
    metric_date: date
    measurement_count: int
    avg_temperature_c: float | None
    max_temperature_c: float | None
    avg_vibration_mm_s: float | None
    avg_load_pct: float | None
    anomaly_rate: float | None
    failure_count: int
    maintenance_count: int
    calculated_at: datetime


class MachineDetailResponse(BaseModel):
    machine: MachineResponse
    metrics: MetricResponse | None


class PredictionResponse(BaseModel):
    machine_id: str
    prediction_date: date
    model_name: str
    model_version: str
    risk_probability: float | None = Field(ge=0, le=1)
    predicted_label: int | None = Field(ge=0, le=1)
    created_at: datetime


class PipelineRunResponse(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    profile: str
    input_rows: int | None
    valid_rows: int | None
    rejected_rows: int | None
    summary: dict[str, object]


class DependencyResponse(BaseModel):
    component_id: str
    component_type: str | None
    dependency_id: str | None
    dependency_type: str | None
    affected_neighbor_machines: list[str]
    relationship: str


class MachineDependenciesResponse(BaseModel):
    machine_id: str
    dependencies: list[DependencyResponse]


def _database_error() -> HTTPException:
    return HTTPException(status_code=503, detail="Data service is temporarily unavailable")


def _current_model_version() -> str:
    return os.getenv("IIP_CURRENT_MODEL_VERSION", "synthetic-v2-classification-benchmark")


def _pagination_headers(response: Response, total: int, limit: int, offset: int) -> None:
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)


@app.get("/health")
def health() -> dict[str, object]:
    try:
        postgres_available = relational_store.check_connection()
    except PostgresUnavailable:
        postgres_available = False
    return {
        "status": "ok" if postgres_available else "degraded",
        "postgres_available": postgres_available,
        "authentication": "not_configured_local_only",
    }


@app.get("/machines", response_model=list[MachineResponse])
def machines(
    response: Response,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[dict[str, object]]:
    try:
        rows, total = relational_store.fetch_machines(limit, offset)
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    _pagination_headers(response, total, limit, offset)
    return rows


@app.get("/machines/{machine_id}", response_model=MachineDetailResponse)
def machine(machine_id: MachineId) -> dict[str, object]:
    try:
        master = relational_store.fetch_machine(machine_id)
        if master is None:
            raise HTTPException(status_code=404, detail="Machine not found")
        metrics, _ = relational_store.fetch_machine_metrics(machine_id, 1, 0)
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    return {"machine": master, "metrics": metrics[0] if metrics else None}


@app.get("/machines/{machine_id}/metrics", response_model=list[MetricResponse])
def machine_metrics(
    machine_id: MachineId,
    response: Response,
    limit: int = Query(30, ge=1, le=366),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[dict[str, object]]:
    try:
        if relational_store.fetch_machine(machine_id) is None:
            raise HTTPException(status_code=404, detail="Machine not found")
        rows, total = relational_store.fetch_machine_metrics(machine_id, limit, offset)
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    _pagination_headers(response, total, limit, offset)
    return rows


@app.get("/predictions", response_model=list[PredictionResponse])
def predictions(
    response: Response,
    risk: Literal["high", "low"] | None = None,
    model_version: str | None = Query(None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[dict[str, object]]:
    selected_version = model_version or _current_model_version()
    label = None if risk is None else int(risk == "high")
    try:
        rows, total = relational_store.fetch_predictions(
            selected_version, limit, offset, predicted_label=label
        )
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    _pagination_headers(response, total, limit, offset)
    response.headers["X-Model-Version"] = selected_version
    return rows


@app.get("/predictions/{machine_id}", response_model=list[PredictionResponse])
def machine_predictions(
    machine_id: MachineId,
    response: Response,
    model_version: str | None = Query(None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[dict[str, object]]:
    selected_version = model_version or _current_model_version()
    try:
        if relational_store.fetch_machine(machine_id) is None:
            raise HTTPException(status_code=404, detail="Machine not found")
        rows, total = relational_store.fetch_predictions(
            selected_version, limit, offset, machine_id=machine_id
        )
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    _pagination_headers(response, total, limit, offset)
    response.headers["X-Model-Version"] = selected_version
    return rows


@app.get("/pipeline-runs", response_model=list[PipelineRunResponse])
def pipeline_runs(
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
) -> list[dict[str, object]]:
    try:
        rows, total = relational_store.fetch_pipeline_runs(limit, offset)
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    _pagination_headers(response, total, limit, offset)
    return rows


@app.get("/pipeline-runs/latest", response_model=PipelineRunResponse)
def latest_pipeline_run() -> dict[str, object]:
    try:
        rows, _ = relational_store.fetch_pipeline_runs(1, 0)
    except PostgresUnavailable as exc:
        raise _database_error() from exc
    if not rows:
        raise HTTPException(status_code=404, detail="No pipeline run has been recorded")
    return rows[0]


@app.get(
    "/machines/{machine_id}/dependencies",
    response_model=MachineDependenciesResponse,
)
def machine_dependencies(
    machine_id: MachineId,
    limit: int = Query(100, ge=1, le=200),
) -> dict[str, object]:
    try:
        result = graph_store.machine_dependencies(machine_id, limit)
    except Neo4jUnavailable as exc:
        raise _database_error() from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Machine not found in dependency graph")
    return result
