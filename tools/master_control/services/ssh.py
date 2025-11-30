"""SSH helpers for orchestrating remote jobs on the Raspberry Pi."""

from __future__ import annotations

import logging
import shlex
from typing import Optional

try:  # pragma: no cover - optional dependency guard
    import paramiko
except ImportError as exc:  # pragma: no cover - fail fast with guidance
    raise RuntimeError(
        "paramiko is required for SSH operations. Install it via 'pip install paramiko'."
    ) from exc


from ..compat import dataclass

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SSHCredentials:
    """Basic connection parameters."""

    host: str
    username: str
    password: str = ""
    port: int = 22
    timeout: int = 10


@dataclass(slots=True)
class SSHCommandResult:
    """Response from executing a remote command."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __bool__(self) -> bool:  # pragma: no cover - simple alias
        return self.ok


class SSHService:
    """Thin wrapper around Paramiko SSH client with sensible defaults."""

    def __init__(self, credentials: SSHCredentials) -> None:
        self._credentials = credentials
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self) -> None:
        if self._client:
            return

        _LOGGER.debug("Connecting to %s", self._credentials.host)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self._credentials.host,
            username=self._credentials.username,
            password=self._credentials.password or None,
            port=self._credentials.port,
            timeout=self._credentials.timeout,
            banner_timeout=self._credentials.timeout,
        )
        self._client = client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def execute(self, command: str, timeout: Optional[int] = None) -> SSHCommandResult:
        self.connect()
        assert self._client is not None  # for mypy

        _LOGGER.debug("Running remote command: %s", command)
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        stdout_str = stdout.read().decode("utf-8", errors="ignore")
        stderr_str = stderr.read().decode("utf-8", errors="ignore")
        exit_code = stdout.channel.recv_exit_status()
        _LOGGER.debug("Command exit code %s", exit_code)
        return SSHCommandResult(stdout=stdout_str, stderr=stderr_str, exit_code=exit_code)

    def start_background(self, command: str) -> SSHCommandResult:
        wrapped = (
            "nohup {cmd} >~/master_control.log 2>&1 & echo $!".format(cmd=command)
        )
        return self.execute(wrapped)

    def stop_by_pattern(self, pattern: str) -> SSHCommandResult:
        if not pattern:
            raise ValueError("pattern must not be empty")
        inner = f"pkill -f {shlex.quote(pattern)} || true"
        command = f"bash -lc {shlex.quote(inner)}"
        if not command:
            raise ValueError("pattern must not be empty")
        return self.execute(command)

    def exec_stream(self, command: str):
        self.connect()
        assert self._client is not None
        return self._client.exec_command(command)

    def __enter__(self) -> "SSHService":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
