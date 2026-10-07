"""
ATBMind RobotRole Loader
Parses role.yaml configuration files into RobotRole instances.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict
import yaml

from atbmind_core.roles.schema import RobotRole

logger = logging.getLogger("atbmind.roles.loader")


class RoleLoader:
    """Utility to load a RobotRole configuration from disk."""

    @classmethod
    def load_from_dir(cls, role_dir: Path | str) -> RobotRole:
        path = Path(role_dir).resolve()
        if not path.is_dir():
            raise ValueError(f"Role path is not a directory: {path}")

        role_yaml_path = path / "role.yaml"
        if not role_yaml_path.exists():
            role_yaml_path = path / "role.yml"

        if not role_yaml_path.exists():
            raise FileNotFoundError(f"No role.yaml found in {path}")

        raw_content = role_yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_content)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML content in {role_yaml_path}")

        if "role_id" not in data:
            data["role_id"] = path.name

        data["role_dir"] = str(path)
        return RobotRole.model_validate(data)
