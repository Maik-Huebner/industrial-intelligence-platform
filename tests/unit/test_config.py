from pathlib import Path

import pytest

from industrial_intelligence.config import Settings


def test_profiles_have_expected_sizes() -> None:
    assert Settings(profile="small").measurement_count == 10_000
    assert Settings(profile="medium").measurement_count == 100_000
    assert Settings(profile="full").measurement_count == 1_000_000


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown profile"):
        _ = Settings(profile="huge").measurement_count


def test_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IIP_SEED", "7")
    monkeypatch.setenv("IIP_DATA_DIR", "/tmp/iip-test")
    settings = Settings.from_env("small")
    assert settings.seed == 7
    assert settings.data_dir == Path("/tmp/iip-test")

