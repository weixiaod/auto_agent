"""YAML loader with ${ENV_VAR} substitution. Raises KeyError if a var is unset."""

from __future__ import annotations

import os
import re
from typing import Any

import yaml

_ENV_VAR = re.compile(r"\$\{([^}]+)\}")


def load_yaml_with_env(path: str) -> Any:
    """Load a YAML file, substituting ${VAR} with os.environ['VAR']."""
    with open(path) as f:
        raw = f.read()

    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in os.environ:
            raise KeyError(f"Environment variable {name!r} not set (referenced in {path})")
        return os.environ[name]

    return yaml.safe_load(_ENV_VAR.sub(sub, raw))
