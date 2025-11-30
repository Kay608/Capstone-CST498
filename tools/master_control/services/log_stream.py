"""Stream remote log output over SSH in a background thread."""

from __future__ import annotations

import threading
from typing import Callable, Optional

from .ssh import SSHService


class RemoteLogStreamer:
    """Continuously read a remote file and invoke a callback when new data arrives."""

    def __init__(
        self,
        ssh: SSHService,
        file_path: str,
        callback: Callable[[str], None],
        *,
        tail_lines: int = 100,
    ) -> None:
        self._ssh = ssh
        self._file_path = file_path
        self._callback = callback
        self._tail_lines = tail_lines
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="remote-log-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        command = (
            f"tail -n {self._tail_lines} -F {self._file_path}"
        )
        try:
            result = self._ssh.execute(command)
            if not result.ok:
                self._callback(result.stderr or "Failed to open log stream\n")
                return
        except Exception as exc:  # pragma: no cover
            self._callback(f"Log stream error: {exc}\n")
            return

        while not self._stop_event.is_set():
            try:
                output = self._ssh.execute(command)
            except Exception as exc:  # pragma: no cover
                self._callback(f"Log stream error: {exc}\n")
                break
            if output.stdout:
                self._callback(output.stdout)
            self._stop_event.wait(1)