"""System control panel with start/stop actions."""

from __future__ import annotations

import queue
import shlex
import threading
import time
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
        self._log_events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._log_text: tk.Text | None = None
        self._stream_button: ttk.Button | None = None
        self._stream_thread: threading.Thread | None = None
        self._stream_stop: threading.Event | None = None
        self._stream_channel = None
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

        log_frame = ttk.LabelFrame(self, text="API Log")
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        controls = ttk.Frame(log_frame)
        controls.pack(fill="x", padx=12, pady=(8, 4))

        self._stream_button = ttk.Button(controls, text="Start Live Stream", command=self._toggle_stream)
        self._stream_button.pack(side="left")

        ttk.Button(controls, text="Copy Tail", command=self._copy_log_to_clipboard).pack(side="left", padx=(6, 0))

        text_container = ttk.Frame(log_frame)
        text_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._log_text = tk.Text(text_container, wrap="none", height=16, state="disabled")
        self._log_text.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(text_container, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")

        self.after(200, self._process_log_events)

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
        remote = self.state.config.remote
        patterns = []
        if remote.waitress_stop_pattern:
            patterns.append(remote.waitress_stop_pattern)
        if remote.flask_stop_pattern:
            patterns.append(remote.flask_stop_pattern)
        if not patterns:
            raise RuntimeError("No stop patterns configured for the API")

        attempted = []
        for pattern in dict.fromkeys(patterns):
            services.ssh.stop_by_pattern(pattern)
            attempted.append(pattern)

        lingering: list[str] = []
        for pattern in attempted:
            check = services.ssh.execute(f"pgrep -af {shlex.quote(pattern)}")
            if check.exit_code == 0 and check.stdout.strip():
                lingering.append(f"{pattern}: {check.stdout.strip()}")
            elif check.exit_code not in (0, 1):
                raise RuntimeError(check.stderr or f"Unable to verify stop for {pattern}")

        if lingering:
            joined = "; ".join(lingering)
            raise RuntimeError(f"Processes still running after stop: {joined}")

        attempted_display = ", ".join(attempted)
        self._record_stop_confirmation(services, attempted_display)
        self._enqueue_log_event("status", "API stop confirmed and logged.")
        return f"Stop request sent for patterns [{attempted_display}]."

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
        self._enqueue_log_event("snapshot", content)
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

    def _copy_log_to_clipboard(self) -> None:
        if not self._last_log:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(self._last_log)
        except tk.TclError:
            messagebox.showwarning("Copy Log", "Unable to access clipboard.")

    def _record_stop_confirmation(self, services, attempted_display: str) -> None:
        sanitized = attempted_display.replace("\n", " ") or "n/a"
        patterns_arg = shlex.quote(sanitized)
        inner = (
            'printf "%s [master-control] API stop confirmed (patterns: %s)\\n" '
            '"$(date +%Y-%m-%dT%H:%M:%S)" {patterns} >> ~/master_control.log'
        ).format(patterns=patterns_arg)
        result = services.ssh.execute(f"bash -lc {shlex.quote(inner)}")
        if not result.ok:
            raise RuntimeError(result.stderr or "Unable to append stop confirmation to log")

    def _enqueue_log_event(self, kind: str, payload: str) -> None:
        self._log_events.put((kind, payload))

    def _process_log_events(self) -> None:
        if not self.winfo_exists():
            return

        while True:
            try:
                kind, payload = self._log_events.get_nowait()
            except queue.Empty:
                break

            if kind == "snapshot":
                self._set_log_text(payload, replace=True)
            elif kind == "append":
                self._append_log_text(payload)
            elif kind == "status":
                message = payload.strip()
                if message:
                    self._append_log_text(f"{message}\n")
            elif kind == "stream_ended":
                self._finalize_stream_state()

        self.after(200, self._process_log_events)

    def _set_log_text(self, text: str, *, replace: bool) -> None:
        widget = self._log_text
        if widget is None:
            return
        widget.configure(state="normal")
        if replace:
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
        else:
            widget.insert("end", text)
        widget.see("end")
        self._trim_log_widget(widget)
        content = widget.get("1.0", "end-1c")
        widget.configure(state="disabled")
        max_chars = 4000
        self._last_log = content[-max_chars:] if len(content) > max_chars else content

    def _append_log_text(self, text: str) -> None:
        widget = self._log_text
        if widget is None:
            return
        widget.configure(state="normal")
        widget.insert("end", text)
        widget.see("end")
        self._trim_log_widget(widget)
        content = widget.get("1.0", "end-1c")
        widget.configure(state="disabled")
        max_chars = 4000
        self._last_log = content[-max_chars:] if len(content) > max_chars else content

    def _trim_log_widget(self, widget: tk.Text, *, max_lines: int = 400) -> None:
        end_index = widget.index("end-1c")
        try:
            total_lines = int(end_index.split(".")[0])
        except (ValueError, AttributeError):
            return
        if total_lines <= max_lines:
            return
        lines_to_remove = total_lines - max_lines
        widget.delete("1.0", f"{lines_to_remove + 1}.0")

    def _toggle_stream(self) -> None:
        if self._is_streaming():
            self._stop_log_stream()
        else:
            self._start_log_stream()

    def _is_streaming(self) -> bool:
        thread = self._stream_thread
        return bool(thread and thread.is_alive())

    def _start_log_stream(self) -> None:
        if self._is_streaming():
            return
        stop_event = threading.Event()
        self._stream_stop = stop_event
        thread = threading.Thread(target=self._run_log_stream, args=(stop_event,), daemon=True)
        self._stream_thread = thread
        if self._stream_button:
            self._stream_button.configure(text="Stop Live Stream")
        self._enqueue_log_event("status", "Starting live log stream...")
        self._scheduler.submit("Tail API Log", self._tail_log_job)
        thread.start()

    def _stop_log_stream(self) -> None:
        if not self._is_streaming():
            self._finalize_stream_state()
            return

        self._enqueue_log_event("status", "Stopping live log stream...")
        stop_event = self._stream_stop
        if stop_event:
            stop_event.set()
        channel = self._stream_channel
        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass
        self._stream_channel = None

    def _run_log_stream(self, stop_event: threading.Event) -> None:
        try:
            services = self.state.init_services()
            command = "tail -n 200 -F ~/master_control.log"
            _, stdout, stderr = services.ssh.exec_stream(command)
            channel = stdout.channel
            self._stream_channel = channel
            buffer = ""
            while not stop_event.is_set():
                if channel.recv_ready():
                    chunk = channel.recv(4096)
                    if not chunk:
                        if channel.exit_status_ready():
                            break
                        continue
                    if isinstance(chunk, bytes):
                        chunk = chunk.decode("utf-8", errors="ignore")
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        self._enqueue_log_event("append", f"{line}\n")
                else:
                    if channel.exit_status_ready():
                        break
                    time.sleep(0.2)

            if buffer:
                self._enqueue_log_event("append", buffer)

            exit_code = channel.recv_exit_status() if channel.exit_status_ready() else 0
            if exit_code not in (0, 130):
                error_text = stderr.read()
                if isinstance(error_text, bytes):
                    error_text = error_text.decode("utf-8", errors="ignore")
                message = error_text.strip() or f"tail exited with code {exit_code}"
                self._enqueue_log_event("status", message)
        except Exception as exc:
            self._enqueue_log_event("status", f"Log stream error: {exc}")
        finally:
            self._stream_channel = None
            self._enqueue_log_event("status", "Live log stream ended.")
            self._enqueue_log_event("stream_ended", "")

    def _finalize_stream_state(self) -> None:
        if self._stream_button and self._stream_button.winfo_exists():
            self._stream_button.configure(text="Start Live Stream")
        self._stream_thread = None
        self._stream_stop = None

    def destroy(self) -> None:
        self._stop_log_stream()
        super().destroy()
