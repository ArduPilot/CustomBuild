"""Tests for shared build_config packaging helpers."""
import tarfile
from pathlib import Path

import pytest
import yaml

from build_config import (
    CONFIG_FILENAME,
    CONFIG_VERSION,
    build_config_dict,
    config_dict_from_build_info,
    dump_config_yaml,
    validate_config_dict,
    write_config_yaml,
)
from build_manager import BuildInfo
from metadata_manager import RemoteInfo


def _valid_config(**overrides):
    base = build_config_dict(
        vehicle_id="copter",
        vehicle_name="Copter",
        version_id="ardupilot-Copter-4.5.0-abc",
        version_name="4.5.0",
        version_type="stable",
        remote_name="ardupilot",
        board_id="CubeOrange",
        board_name="CubeOrange",
        selected_features={"HAL_LOGGING_ENABLED"},
    )
    base.update(overrides)
    return base


def test_validate_accepts_schema_compliant_config():
    validate_config_dict(_valid_config())


def test_validate_rejects_missing_required_field():
    bad = _valid_config()
    del bad["board"]
    with pytest.raises(Exception):
        validate_config_dict(bad)


def test_dump_and_write_roundtrip(tmp_path: Path):
    config = _valid_config()
    text = dump_config_yaml(config)
    parsed = yaml.safe_load(text)
    assert parsed["config_version"] == CONFIG_VERSION
    assert parsed["vehicle"]["id"] == "copter"

    out = tmp_path / CONFIG_FILENAME
    write_config_yaml(out, config)
    assert out.is_file()
    assert yaml.safe_load(out.read_text())["board"]["id"] == "CubeOrange"


def test_config_dict_from_build_info_uses_labels_and_names():
    info = BuildInfo(
        vehicle_id="copter",
        version_id="ver-1",
        remote_info=RemoteInfo(
            name="ardupilot",
            url="https://github.com/ArduPilot/ardupilot.git",
        ),
        git_hash="abc123",
        board="MatekH743",
        selected_features={"HAL_LOGGING_ENABLED"},
        vehicle_name="Copter",
        board_name="MatekH743",
        version_name="4.5.0",
        version_type="stable",
    )
    config = config_dict_from_build_info(info)
    validate_config_dict(config)
    assert config["selected_features"] == ["HAL_LOGGING_ENABLED"]
    assert config["version"]["name"] == "4.5.0"
    assert config["version"]["remote_name"] == "ardupilot"


def test_packaged_yaml_inside_tar(tmp_path: Path):
    """Simulate Builder archive membership for custombuild.yaml."""
    config = _valid_config()
    config_path = tmp_path / CONFIG_FILENAME
    write_config_yaml(config_path, config)

    archive = tmp_path / "copter-MatekH743-build1.tar.gz"
    folder_name = archive.name.removesuffix(".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(config_path, arcname=f"{folder_name}/{CONFIG_FILENAME}")

    with tarfile.open(archive, "r:gz") as tar:
        names = [m.name for m in tar.getmembers()]
        assert f"{folder_name}/{CONFIG_FILENAME}" in names
        extracted = tar.extractfile(f"{folder_name}/{CONFIG_FILENAME}")
        assert extracted is not None
        loaded = yaml.safe_load(extracted.read())
        assert loaded["vehicle"]["id"] == "copter"
