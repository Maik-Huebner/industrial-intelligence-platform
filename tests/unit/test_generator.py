import hashlib
from pathlib import Path

from industrial_intelligence.config import Settings
from industrial_intelligence.generator import IndustrialDataGenerator, stable_id


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stable_id_is_reproducible() -> None:
    assert stable_id("R", 42, 1) == stable_id("R", 42, 1)
    assert stable_id("R", 42, 1) != stable_id("R", 42, 2)


def test_machine_master_is_coherent(tmp_path: Path) -> None:
    machines = IndustrialDataGenerator(Settings(data_dir=tmp_path)).machines()
    assert len(machines) == 50
    assert len({machine.machine_id for machine in machines}) == 50
    assert {machine.line_id for machine in machines} == {f"LINE-{i:02d}" for i in range(1, 6)}


def test_generator_reproducibility(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    IndustrialDataGenerator(Settings(profile="small", seed=99, data_dir=first, invalid_rate=0)).generate()
    IndustrialDataGenerator(Settings(profile="small", seed=99, data_dir=second, invalid_rate=0)).generate()
    assert file_digest(first / "raw/mongodb/sensor_readings.jsonl") == file_digest(second / "raw/mongodb/sensor_readings.jsonl")

