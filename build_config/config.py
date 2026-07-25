"""Serialize and validate CustomBuild config YAML (schemas/config)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml
from jsonschema import Draft202012Validator

CONFIG_VERSION = "0.0.1"
CONFIG_FILENAME = "custombuild.yaml"

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas" / "config"


def schema_path_for_version(version: str = CONFIG_VERSION) -> Path:
    path = _SCHEMAS_DIR / f"{version}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No config schema for version '{version}' at {path}")
    return path


def validate_config_dict(config: Mapping[str, Any]) -> None:
    version = config.get("config_version")
    if not isinstance(version, str):
        raise ValueError("Invalid or missing config_version")
    schema = json.loads(schema_path_for_version(version).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(dict(config))


def build_config_dict(
    *,
    vehicle_id: str,
    vehicle_name: str,
    version_id: str,
    version_name: str,
    version_type: str,
    remote_name: str,
    board_id: str,
    board_name: str,
    selected_features: Sequence[str],
    config_version: str = CONFIG_VERSION,
) -> dict[str, Any]:
    """Build a schema-compliant config dict (selected_features are API labels)."""
    return {
        "config_version": config_version,
        "vehicle": {"id": vehicle_id, "name": vehicle_name},
        "version": {
            "id": version_id,
            "name": version_name,
            "type": version_type,
            "remote_name": remote_name,
        },
        "board": {"id": board_id, "name": board_name},
        "selected_features": sorted(selected_features),
    }


def dump_config_yaml(config: Mapping[str, Any]) -> str:
    validate_config_dict(config)
    return yaml.safe_dump(
        dict(config),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def write_config_yaml(path: Path | str, config: Mapping[str, Any]) -> None:
    path = Path(path)
    path.write_text(dump_config_yaml(config), encoding="utf-8")


def config_dict_from_build_info(build_info: Any) -> dict[str, Any]:
    """Build config from BuildInfo fields set at submit time."""
    return build_config_dict(
        vehicle_id=build_info.vehicle_id,
        vehicle_name=build_info.vehicle_name,
        version_id=build_info.version_id,
        version_name=build_info.version_name,
        version_type=build_info.version_type,
        remote_name=build_info.remote_info.name,
        board_id=build_info.board,
        board_name=build_info.board_name,
        selected_features=list(build_info.selected_features),
    )
