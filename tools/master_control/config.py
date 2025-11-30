"""Configuration defaults for the Master Control application."""

from __future__ import annotations

from dataclasses import field
from typing import Tuple


from .compat import dataclass


@dataclass(slots=True)
class RemoteConfig:
    """Settings used for SSH and API communication."""

    default_host: str = "172.20.10.8"
    fallback_hosts: Tuple[str, ...] = ("raspberrypi.local", "raspberrypi")
    ssh_user: str = "root1"
    ssh_password: str = "root1"
    api_port: int = 5001
    project_root: str = "~/Capstone-CST498"
    python_bin: str = "python"
    venv_activation: str = "source .venv311/bin/activate"
    flask_module: str = "flask_api.app:app"
    flask_debug_command: str = "python flask_api/app.py"
    flask_waitress_command: str = (
        "python -m waitress --listen=0.0.0.0:5001 flask_api.app:app"
    )
    flask_stop_pattern: str = "flask_api/app.py"
    waitress_stop_pattern: str = "waitress"
    integrated_gui_command: str = "python integrated_recognition_system.py"
    integrated_headless_command: str = (
        "python integrated_recognition_system.py --headless"
    )
    integrated_stop_pattern: str = "integrated_recognition_system.py"


@dataclass(slots=True)
class AppConfig:
    """Top-level configuration container."""

    remote: RemoteConfig = field(default_factory=RemoteConfig)
    default_api_key: str = ""
    capture_endpoint: str = "/api/manual/capture"
    status_endpoint: str = "/api/manual/status"
    stream_url: str = "http://{host}:{port}/api/manual/stream"


DEFAULT_CONFIG = AppConfig()
