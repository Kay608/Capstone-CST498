"""Compatibility helpers for Python version differences."""

from __future__ import annotations

import sys
from dataclasses import dataclass as _dataclass


def dataclass(*args, **kwargs):
    """Wrapper that strips unsupported dataclass keyword arguments on older Pythons."""

    if sys.version_info < (3, 10):
        kwargs.pop("slots", None)
    return _dataclass(*args, **kwargs)
