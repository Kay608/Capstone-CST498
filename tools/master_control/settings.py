"""Simple persistence layer for master control user preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_SETTINGS_FILE = Path.home() / ".capstone_master_control.json"


def load_settings() -> Dict[str, Any]:
    try:
        raw = _SETTINGS_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def save_settings(updates: Dict[str, Any]) -> None:
    data = load_settings()
    data.update(updates)
    try:
        _SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
