"""System control panel with start/stop actions."""

from __future__ import annotations

import shlex
import tkinter as tk
from tkinter import messagebox, ttk

from ..scheduler import JobScheduler
from ..state.app_state import AppState
from .base_panel import BasePanel


class ControlPanel(BasePanel):
    def __init__(self, parent, state: AppState, scheduler: JobScheduler, **kwargs):
        self._scheduler = scheduler
        self._host_var = tk.StringVar(value=state.config.remote.default_host)
        self._last_log: str = ""
        super().__init__(parent, state, **kwargs)

    def _build_widgets(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill="x", padx=12, pady=12)

        ttk.Label(container, text="System Actions", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))

        start_api_btn = ttk.Button(button_row, text="Start API", command=self._start_api)
        start_api_btn.pack(side="left", padx=(0, 8))

        stop_api_btn = ttk.Button(button_row, text="Stop API", command=self._stop_api)
        stop_api_btn.pack(side="left", padx=(0, 8))

        ttk.Button(button_row, text="Ping API", command=self._ping_api).pack(side="left")
        ttk.Button(button_row, text="View Log", command=self._show_log).pack(side="left", padx=(8, 0))

        host_frame = ttk.LabelFrame(self, text="Target Host")
        host_frame.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Label(host_frame, text="Host or IP").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self._host_entry = ttk.Combobox(
            host_frame,
            textvariable=self._host_var,
            values=self._host_options(),
            width=36,
        )
        self._host_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 4))

        button_box = ttk.Frame(host_frame)
        button_box.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 8))
        ttk.Button(button_box, text="Refresh", command=self._refresh_hosts).pack(side="left")
        ttk.Button(button_box, text="Apply", command=self._apply_host).pack(side="left", padx=(6, 0))

        self._resolved_label = ttk.Label(host_frame, text=self.state.resolved_host_display())
        self._resolved_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 12))

        host_frame.columnconfigure(1, weight=1)

    def _start_api(self) -> None:
        self._scheduler.submit("Start Flask API", self._start_api_job)
        self._scheduler.submit("Tail API Log", self._tail_log_job)

    def _stop_api(self) -> None:
        self._scheduler.submit("Stop Flask API", self._stop_api_job)
        self._scheduler.submit("Tail API Log", self._tail_log_job)

    def _ping_api(self) -> None:
        self._scheduler.submit("Ping Flask API", self._ping_api_job)
        self._scheduler.submit("Tail API Log", self._tail_log_job)

    def _host_options(self) -> tuple[str, ...]:
        return tuple(self.state.known_hosts())

    def _refresh_hosts(self) -> None:
        self.state.refresh_host_resolution()
        options = self._host_options()
        self._host_entry.configure(values=options)
        self._resolved_label.configure(text=self.state.resolved_host_display())

    def _apply_host(self) -> None:
        host = self._host_var.get()
        try:
            resolution = self.state.set_host(host)
        except ValueError as exc:
            messagebox.showerror("Update Host", str(exc))
            return
        self._host_entry.configure(values=self._host_options())
        self._resolved_label.configure(text=self.state.resolved_host_display())
        messagebox.showinfo(
            "Update Host",
            f"Using {resolution.address} for remote operations.",
        )

    def _start_api_job(self) -> None:
        services = self.state.init_services()
        remote = self.state.config.remote
        if remote.waitress_stop_pattern:
            services.ssh.stop_by_pattern(remote.waitress_stop_pattern)
        if remote.flask_stop_pattern:
            services.ssh.stop_by_pattern(remote.flask_stop_pattern)

        command = self._build_remote_command(remote.flask_waitress_command)
        result = services.ssh.start_background(command)
        if not result.ok:
            raise RuntimeError(result.stderr or "Failed to start API")
        pid = result.stdout.strip()
        return f"API start requested (PID {pid})" if pid else "API start requested"

    def _stop_api_job(self) -> None:
        services = self.state.init_services()
        pattern = self.state.config.remote.waitress_stop_pattern
        result = services.ssh.stop_by_pattern(pattern)
        if not result.ok:
            raise RuntimeError(result.stderr or "Failed to stop API")
        message = result.stdout.strip() or "Stop signal sent"
        return f"{message}. Check ~/master_control.log for details."

    def _tail_log_job(self, line_count: int = 40) -> str:
        services = self.state.init_services()
        command = f"tail -n {line_count} ~/master_control.log"
        result = services.ssh.execute(command)
        if not result.ok:
            raise RuntimeError(result.stderr or "Unable to read log")
        content = (result.stdout or "Log file is empty.").strip()
        max_chars = 4000
        if len(content) > max_chars:
            content = content[-max_chars:]
        self._last_log = content
        lines = content.count("\n") + 1 if content else 0
        return f"Log tail captured ({lines} lines)"

    def _ping_api_job(self) -> None:
        services = self.state.init_services()
        if not services.rest.ping():
            raise RuntimeError("API did not respond")
        return "API responded successfully"

    def _build_remote_command(self, command: str) -> str:
        remote = self.state.config.remote
        steps = [f"cd {self._quote_path(remote.project_root)}"]
        if remote.venv_activation:
            steps.append(remote.venv_activation)
        steps.append(command)
        joined = " && ".join(steps)
        return f"bash -lc {shlex.quote(joined)}"

    @staticmethod
    def _quote_path(path: str) -> str:
        if path.startswith("~"):
            return path
        return shlex.quote(path)

    def _show_log(self) -> None:
        try:
            content = self._tail_log_job(line_count=80)
        except Exception as exc:
            messagebox.showerror("View Log", str(exc))
            return
        display_text = self._last_log or content

        window = tk.Toplevel(self)
        window.title("API Log (tail)")
        window.geometry("720x360")

        container = ttk.Frame(window)
        container.pack(fill="both", expand=True)

        text_widget = tk.Text(container, wrap="none")
        text_widget.insert("1.0", display_text)
        text_widget.configure(state="disabled")
        text_widget.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(container, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
