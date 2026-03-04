"""Pytest global configuration."""

from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def _normalize_bool_env(var_name: str, *, default: str = "false") -> None:
    raw_value = os.getenv(var_name)
    if raw_value is None:
        os.environ[var_name] = default
        return

    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        os.environ[var_name] = "true"
    elif normalized in _FALSE_VALUES:
        os.environ[var_name] = "false"
    else:
        os.environ[var_name] = default


# Ensure app settings parsing is stable during test collection/imports.
_normalize_bool_env("DEBUG", default="false")
