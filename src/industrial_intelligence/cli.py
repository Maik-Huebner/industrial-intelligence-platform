"""Command-line entry point for local and containerized workflows."""

from __future__ import annotations

import argparse
import json
import logging

from .config import Settings
from .generator import IndustrialDataGenerator
from .pipeline import calculate_metrics, run_local_pipeline
from .quality import validate_sensor_file


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="industrial-intelligence")
    root.add_argument("--log-level", default="INFO")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("generate", "pipeline"):
        command = commands.add_parser(name)
        command.add_argument("--profile", choices=("small", "medium", "full"), default=None)
    validate = commands.add_parser("validate")
    validate.add_argument("--source", choices=("raw", "mongodb-export"), default="raw")
    export = commands.add_parser("export-mongodb")
    export.add_argument("--batch-size", type=int, default=5_000)
    commands.add_parser("metrics")
    commands.add_parser("load-sources")
    commands.add_parser("sync-results")
    return root


def main() -> None:
    args = parser().parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env(getattr(args, "profile", None))
    if args.command == "generate":
        result = IndustrialDataGenerator(settings).generate()
    elif args.command == "validate":
        source_path = None
        source_name = "raw_generator_file"
        if args.source == "mongodb-export":
            source_path = settings.data_dir / "processed" / "mongodb_export" / "sensor_readings.jsonl"
            source_name = "mongodb_export"
        result = validate_sensor_file(settings.data_dir, source_path, source_name).as_dict()
    elif args.command == "export-mongodb":
        from .database.mongodb import export_sensor_documents

        result = export_sensor_documents(settings.data_dir, args.batch_size)
    elif args.command == "metrics":
        result = {"machines": len(calculate_metrics(settings.data_dir))}
    elif args.command == "load-sources":
        from .database.mongodb import load_sensor_documents
        from .database.postgres import load_source_data

        result = load_source_data(settings.data_dir)
        result["sensor_documents"] = load_sensor_documents(
            settings.data_dir / "raw" / "mongodb" / "sensor_readings.jsonl"
        )
    elif args.command == "sync-results":
        from .database.neo4j import sync_components
        from .database.postgres import load_machine_metrics, load_ml_predictions

        result = {
            "postgres_metrics": load_machine_metrics(settings.data_dir / "processed" / "machine_metrics.csv"),
            "neo4j_components": sync_components(settings.data_dir / "raw" / "neo4j" / "machine_components.csv"),
        }
        predictions_path = settings.data_dir / "processed" / "ml_predictions_json"
        if predictions_path.exists():
            result["postgres_ml_predictions"] = load_ml_predictions(predictions_path)
    else:
        result = run_local_pipeline(settings)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
