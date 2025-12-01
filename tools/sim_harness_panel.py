"""Reusable frame version of the simulation harness UI."""

from __future__ import annotations

import base64
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import webbrowser
from contextlib import suppress
from subprocess import Popen
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import tkinter as tk
from tkinter import PhotoImage, filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import cv2
import numpy as np
import paramiko
import pymysql
import requests
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from recognition_core import (  # noqa: E402
    ALTERNATIVE_FLASK_URLS,
    FLASK_APP_URL,
    FaceRecognitionEngine,
    get_db_connection,
    load_encodings_cache,
    load_encodings_from_db,
    save_encodings_cache,
)

FLASK_API_DIR = PROJECT_ROOT / "flask_api"
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(FLASK_API_DIR / ".env", override=False)

CONSOLE_FLAG = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
DEFAULT_REMOTE_PORT = 5001
# Prioritize the hotspot's mDNS hostname before other fallbacks.
HOST_FALLBACKS = ("raspberrypi.local", "raspberrypi")
INTEGRATED_JOB_KEY = "integrated_recognition"


class HarnessFrame(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        set_window_chrome: bool = False,
        remote_base_var: Optional[tk.StringVar] = None,
        remote_api_key_var: Optional[tk.StringVar] = None,
        remote_host_var: Optional[tk.StringVar] = None,
        remote_user_var: Optional[tk.StringVar] = None,
        remote_password_var: Optional[tk.StringVar] = None,
    ) -> None:
        super().__init__(master)
        self.root = self.winfo_toplevel()
        if set_window_chrome and hasattr(self.root, "title"):
            self.root.title("Capstone Simulation Harness")
            self.root.geometry("660x600")

        self.mode = tk.StringVar(self, value="simulation")

        default_base = "http://raspberrypi.local:5001"
        default_host = "raspberrypi.local"
        default_user = "root1"

        if remote_base_var is None:
            self.remote_base = tk.StringVar(self, value=default_base)
        else:
            self.remote_base = remote_base_var
            if not self.remote_base.get():
                self.remote_base.set(default_base)

        if remote_api_key_var is None:
            self.remote_api_key = tk.StringVar(self, value="")
        else:
            self.remote_api_key = remote_api_key_var

        if remote_host_var is None:
            self.remote_host = tk.StringVar(self, value=default_host)
        else:
            self.remote_host = remote_host_var
            if not self.remote_host.get():
                self.remote_host.set(default_host)

        if remote_user_var is None:
            self.remote_user = tk.StringVar(self, value=default_user)
        else:
            self.remote_user = remote_user_var
            if not self.remote_user.get():
                self.remote_user.set(default_user)

        if remote_password_var is None:
            self.remote_password = tk.StringVar(self, value="")
        else:
            self.remote_password = remote_password_var
        self._control_inputs: List[tk.Widget] = []
        self._last_remote_base: Optional[str] = None
        self._ssh_discovered_ip: Optional[str] = None
        self._remote_jobs: Dict[str, Dict[str, Any]] = {}
        self._preview_window: Optional[tk.Toplevel] = None
        self._preview_label: Optional[ttk.Label] = None
        self._preview_running = False
        self._preview_fetch_inflight = False
        self._preview_photo: Optional[PhotoImage] = None
        self._preview_last_error: Optional[str] = None
        self._log_windows: Dict[str, Dict[str, Any]] = {}
        self._flask_running_mode: Optional[str] = None
        self._flask_local_process: Optional[Popen] = None
        self._flask_remote: bool = False
        self._flask_job_key = "flask_server"

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        mode_frame = ttk.LabelFrame(main, text="Mode")
        mode_frame.pack(fill="x", pady=(0, 10))
        ttk.Radiobutton(
            mode_frame,
            text="Simulation",
            variable=self.mode,
            value="simulation",
            command=self._update_mode_ui,
        ).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Radiobutton(
            mode_frame,
            text="Control (Robot)",
            variable=self.mode,
            value="control",
            command=self._update_mode_ui,
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        control_frame = ttk.LabelFrame(main, text="Control Mode Settings")
        control_frame.pack(fill="x", pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)

        ttk.Label(control_frame, text="API Base").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        base_entry = ttk.Entry(control_frame, textvariable=self.remote_base)
        base_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        self._control_inputs.append(base_entry)
        status_button = ttk.Button(control_frame, text="Check Status", command=self._check_remote_status)
        status_button.grid(row=0, column=2, padx=5, pady=4)
        self._control_inputs.append(status_button)
        detect_button = ttk.Button(control_frame, text="Detect Base", command=self._discover_remote_base)
        detect_button.grid(row=0, column=3, padx=5, pady=4)
        self._control_inputs.append(detect_button)

        ttk.Label(control_frame, text="API Key").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        key_entry = ttk.Entry(control_frame, textvariable=self.remote_api_key, show="*")
        key_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=4)
        self._control_inputs.append(key_entry)

        ttk.Label(control_frame, text="SSH Host").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        host_entry = ttk.Entry(control_frame, textvariable=self.remote_host)
        host_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=4)
        self._control_inputs.append(host_entry)

        ttk.Label(control_frame, text="SSH User").grid(row=3, column=0, sticky="w", padx=5, pady=4)
        user_entry = ttk.Entry(control_frame, textvariable=self.remote_user)
        user_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=4)
        self._control_inputs.append(user_entry)

        ttk.Label(control_frame, text="SSH Password").grid(row=4, column=0, sticky="w", padx=5, pady=4)
        password_entry = ttk.Entry(control_frame, textvariable=self.remote_password, show="*")
        password_entry.grid(row=4, column=1, sticky="ew", padx=5, pady=4)
        self._control_inputs.append(password_entry)

        server_frame = ttk.LabelFrame(main, text="Servers & API")
        server_frame.pack(fill="x", pady=(0, 10))
        server_frame.columnconfigure((0, 1), weight=1)

        self.btn_flask_debug = ttk.Button(server_frame, text="Start Flask (Debug)", command=lambda: self._toggle_flask_server("debug"))
        self.btn_flask_debug.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.btn_flask_waitress = ttk.Button(server_frame, text="Start Flask via Waitress", command=lambda: self._toggle_flask_server("waitress"))
        self.btn_flask_waitress.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Open Enrollment Page", command=self.open_enroll_page).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Check Flask Health", command=self.check_flask_api).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Open Orders Page", command=self.open_orders_page).grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Open Admin Page", command=self.open_admin_page).grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        recognition_frame = ttk.LabelFrame(main, text="Recognition & Vision")
        recognition_frame.pack(fill="x", pady=(0, 10))
        recognition_frame.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(recognition_frame, text="Launch Integrated (GUI)", command=self.launch_integrated_gui).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Launch Integrated (Headless)", command=self.launch_integrated_headless).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Stop Integrated", command=self.stop_integrated).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Capture Face Snapshot", command=self.capture_face_snapshot).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Sync Face Encodings", command=self.sync_face_encodings).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Open Live Preview", command=self.open_live_preview).grid(row=1, column=2, padx=5, pady=5, sticky="ew")

        utilities_frame = ttk.LabelFrame(main, text="Database & Tools")
        utilities_frame.pack(fill="x", pady=(0, 10))
        utilities_frame.columnconfigure((0, 1), weight=1)

        ttk.Button(utilities_frame, text="List Registered Users", command=self.list_users).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(utilities_frame, text="Check Database Connection", command=self.check_db_connection).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(utilities_frame, text="Run Sign Classifier", command=self.run_sign_classifier).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(utilities_frame, text="Open Uploads Folder", command=self.open_uploads_folder).grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.log_box = ScrolledText(main, height=12, state="disabled")
        self.log_box.pack(fill="both", expand=True)

        self.log("Harness ready. Use the controls above to run common workflows.")
        self._update_mode_ui()
        self._update_flask_buttons()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def log(self, message: str, *, error: bool = False) -> None:
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"

        def _append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line + "\n")
            if error:
                self.log_box.tag_add("error", "end-2l", "end-1l")
                self.log_box.tag_config("error", foreground="red")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _append)

    def _show_info(self, title: str, message: str) -> None:
        self.after(0, lambda: messagebox.showinfo(title, message))

    def _show_error(self, title: str, message: str) -> None:
        self.after(0, lambda: messagebox.showerror(title, message))

    def run_command_async(self, command: list[str], title: str) -> None:
        def _worker() -> None:
            self.log(f"Starting {title}")
            try:
                subprocess.Popen(command, cwd=PROJECT_ROOT, creationflags=CONSOLE_FLAG)
            except Exception as exc:  # noqa: BLE001
                self.log(f"{title} failed: {exc}", error=True)
                self._show_error(title, str(exc))
            else:
                self.log(f"{title} launched")

        threading.Thread(target=_worker, daemon=True).start()

    def _ensure_log_window(self, job_key: str, title: str, host: str, log_path: str) -> None:
        meta = self._log_windows.get(job_key)
        window_exists = bool(meta and meta.get('window') and meta['window'].winfo_exists())
        if not window_exists:
            top = tk.Toplevel(self.root)
            top.title(f'{title} Logs')
            top.geometry('720x480')
            top.protocol('WM_DELETE_WINDOW', lambda key=job_key: self._close_log_window(key))
            text_widget = ScrolledText(top, wrap='word', state='disabled')
            text_widget.pack(fill='both', expand=True)
            meta = {
                'window': top,
                'text': text_widget,
                'host': host,
                'log': log_path,
                'thread': None,
                'stop_event': None,
                'active': True,
                'last_error': None,
            }
            self._log_windows[job_key] = meta
        else:
            top = meta['window']  # type: ignore[index]
            if meta['text'].winfo_exists():  # type: ignore[index]
                self._clear_log_widget(meta)
            self._stop_log_stream(job_key)
            meta.update({
                'host': host,
                'log': log_path,
                'active': True,
                'last_error': None,
            })
        top = meta['window']  # type: ignore[index]
        if top.winfo_viewable():
            top.lift()
        else:
            top.deiconify()
            top.lift()
        self._start_log_stream(job_key)

    def _clear_log_widget(self, meta: Dict[str, Any]) -> None:
        widget = meta.get('text')
        if not widget or not widget.winfo_exists():
            return
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.configure(state='disabled')

    def _close_log_window(self, job_key: str) -> None:
        meta = self._log_windows.get(job_key)
        if not meta:
            return
        meta['active'] = False
        self._stop_log_stream(job_key)
        log_path = meta.get('log')
        log_host = meta.get('host')
        window = meta.get('window')
        if window and window.winfo_exists():
            window.destroy()
        self._log_windows.pop(job_key, None)
        if log_path and job_key == INTEGRATED_JOB_KEY:
            self._truncate_log_file(str(log_path), host=log_host if isinstance(log_host, str) else None)

    def _start_log_stream(self, job_key: str) -> None:
        self._stop_log_stream(job_key)
        meta = self._log_windows.get(job_key)
        if not meta or not meta.get('active', False):
            return
        stop_event = threading.Event()
        meta['stop_event'] = stop_event
        thread = threading.Thread(target=self._log_stream_worker, args=(job_key, stop_event), daemon=True)
        meta['thread'] = thread
        thread.start()

    def _stop_log_stream(self, job_key: str) -> None:
        meta = self._log_windows.get(job_key)
        if not meta:
            return
        stop_event = meta.get('stop_event')
        if isinstance(stop_event, threading.Event):
            stop_event.set()
        thread = meta.get('thread')
        if isinstance(thread, threading.Thread) and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.5)
        meta['thread'] = None
        meta['stop_event'] = None

    def _log_stream_worker(self, job_key: str, stop_event: threading.Event) -> None:
        backoff = 2.0
        while not stop_event.is_set():
            meta = self._log_windows.get(job_key)
            if not meta or not meta.get('active', False):
                break
            host = meta.get('host') or self.remote_host.get().strip()
            job_info = self._remote_jobs.get(job_key, {})
            if job_info.get('host'):
                host = job_info['host']
            user = self.remote_user.get().strip() or 'root1'
            password = self.remote_password.get()
            log_path = meta.get('log')
            if not host or not log_path:
                self.after(0, lambda key=job_key: self._handle_log_error(key, 'Missing host or log path'))
                break

            client: Optional[paramiko.SSHClient] = None
            channel = None
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hostname=host, username=user, password=password, timeout=10)
                transport = client.get_transport()
                if transport is None:
                    raise RuntimeError('SSH transport unavailable')
                channel = transport.open_session()
                command = f'tail -n 200 -F {shlex.quote(str(log_path))}'
                channel.exec_command(command)

                while not stop_event.is_set():
                    if channel.recv_ready():
                        chunk = channel.recv(4096)
                        if chunk:
                            text = chunk.decode('utf-8', errors='replace')
                            self.after(0, lambda t=text, key=job_key: self._append_log_text_for_job(key, t))
                    if channel.recv_stderr_ready():
                        err = channel.recv_stderr(1024)
                        if err:
                            message = err.decode('utf-8', errors='replace').strip()
                            if message:
                                self.after(0, lambda key=job_key, msg=message: self._handle_log_error(key, msg))
                    if channel.exit_status_ready():
                        exit_status = channel.recv_exit_status()
                        if exit_status != 0:
                            self.after(0, lambda key=job_key, status=exit_status: self._handle_log_error(key, f'tail exited with status {status}'))
                        break
                    if stop_event.wait(0.2):
                        break

                backoff = 2.0
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda key=job_key, msg=str(exc): self._handle_log_error(key, msg))
                if stop_event.wait(backoff):
                    break
                backoff = min(backoff * 2, 30.0)
            finally:
                if channel is not None:
                    try:
                        channel.close()
                    except Exception:  # noqa: BLE001
                        pass
                if client is not None:
                    try:
                        client.close()
                    except Exception:  # noqa: BLE001
                        pass

            if stop_event.is_set():
                break
            if stop_event.wait(1.0):
                break

        meta = self._log_windows.get(job_key)
        if meta:
            meta['thread'] = None
            meta['stop_event'] = None

    def _truncate_log_file(self, log_path: str, *, host: Optional[str] = None) -> None:
        path_obj = Path(log_path)

        if host:
            user = self.remote_user.get().strip() or "root1"
            password = self.remote_password.get()

            def _remote_worker() -> None:
                client: Optional[paramiko.SSHClient] = None
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(hostname=host, username=user, password=password, timeout=10)
                    quoted = shlex.quote(log_path)
                    command = f"bash -lc \"(truncate -s 0 {quoted}) 2>/dev/null || : > {quoted}\""
                    stdin, stdout, stderr = client.exec_command(command)
                    stdout.channel.recv_exit_status()
                    self.log(f"[CONTROL] Cleared remote log {log_path}")
                except Exception as exc:  # noqa: BLE001
                    self.log(f"[CONTROL] Failed to clear remote log {log_path}: {exc}", error=True)
                finally:
                    if client is not None:
                        with suppress(Exception):
                            client.close()

            threading.Thread(target=_remote_worker, daemon=True).start()
            return

        def _local_worker() -> None:
            try:
                if path_obj.exists():
                    path_obj.write_text("")
                    self.log(f"Cleared log {log_path}")
                else:
                    self.log(f"Log file {log_path} not found; nothing to clear")
            except Exception as exc:  # noqa: BLE001
                self.log(f"Failed to clear log {log_path}: {exc}", error=True)

        threading.Thread(target=_local_worker, daemon=True).start()

    def _append_log_text(self, meta: Dict[str, Any], text: str) -> None:
        widget = meta.get('text')
        if not widget or not widget.winfo_exists():
            return
        widget.configure(state='normal')
        widget.insert('end', text)
        widget.see('end')
        widget.configure(state='disabled')

    def _append_log_text_for_job(self, job_key: str, text: str) -> None:
        meta = self._log_windows.get(job_key)
        if not meta or not meta.get('active', False):
            return
        self._append_log_text(meta, text)
        meta['last_error'] = None

    def _handle_log_error(self, job_key: str, message: str) -> None:
        meta = self._log_windows.get(job_key)
        if not meta or not meta.get("active", False):
            return
        summary = message.splitlines()[0]
        if meta.get("last_error") != summary:
            self.log(f"[CONTROL] Log stream error: {summary}", error=True)
            meta["last_error"] = summary
            self._append_log_text(meta, f"\n[Log error] {summary}\n")
    def _stop_remote_job(
        self,
        job_key: str,
        pattern: str,
        title: str,
        *,
        quiet: bool = False,
    ) -> None:
        if not self._is_control_mode():
            return

        host = self.remote_host.get().strip()
        user = self.remote_user.get().strip() or "root1"
        password = self.remote_password.get()
        job_info = self._remote_jobs.get(job_key, {})
        log_meta = self._log_windows.get(job_key)

        if not host:
            if not quiet:
                self.log(f"[CONTROL] Cannot stop {title}; SSH host is not set.", error=True)
                self._show_error(title, "Provide an SSH host in Control Mode Settings before stopping the remote task.")
            return

        target_pattern = job_info.get("pattern", pattern)
        stored_host = job_info.get("host")
        if stored_host:
            host = stored_host

        def _worker() -> None:
            if not quiet:
                self.log(f"[CONTROL] Sending stop signal for {title} on {host}...")
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hostname=host, username=user, password=password, timeout=10)
                escaped_pattern = target_pattern.replace("'", "'\\''")
                shell_cmd = f"bash -lc \"pkill -f '{escaped_pattern}' || true\""
                stdin, stdout, stderr = client.exec_command(shell_cmd)
                stderr_output = stderr.read().decode().strip()
                stdout.channel.recv_exit_status()
                client.close()
                self._remote_jobs.pop(job_key, None)
                if stderr_output and not quiet:
                    self.log(f"[CONTROL] Stop {title} stderr: {stderr_output}")
                if not quiet:
                    self.log(f"[CONTROL] Stop signal dispatched for {title}.")
                if log_meta:
                    self.after(0, lambda: self._append_log_text(log_meta, "\n[CONTROL] Stop signal dispatched.\n"))
            except Exception as exc:  # noqa: BLE001
                if not quiet:
                    self.log(f"[CONTROL] Failed to stop {title}: {exc}", error=True)
                    self._show_error(title, str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Control-mode helpers
    # ------------------------------------------------------------------
    def _is_control_mode(self) -> bool:
        return self.mode.get() == "control"

    def _update_mode_ui(self) -> None:
        state = "normal" if self._is_control_mode() else "disabled"
        for widget in self._control_inputs:
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        mode_label = "Control" if self._is_control_mode() else "Simulation"
        self.log(f"Mode set to {mode_label} mode.")

    def _remote_base_url(self) -> str | None:
        candidates = self._candidate_base_urls()
        if not candidates:
            self._show_error("Control Mode", "Set the API base URL (e.g., http://raspberrypi.local:5001).")
            return None
        base = candidates[0]
        if base != self.remote_base.get().strip():
            self.after(0, lambda b=base: self.remote_base.set(b))
        return base

    def _remote_headers(self) -> dict[str, str]:
        token = self.remote_api_key.get().strip()
        headers: dict[str, str] = {}
        if token:
            headers["X-Api-Key"] = token
        return headers

    def _remote_request(self, method: str, path: str, *, timeout: float = 5.0, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", None) or self._remote_headers()
        candidates = self._candidate_base_urls()
        if not candidates:
            raise requests.RequestException("No remote endpoints configured")

        last_exc: Optional[requests.RequestException] = None
        for base in candidates:
            url = base + path
            try:
                response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
                response.raise_for_status()
            except requests.RequestException as exc:  # noqa: BLE001
                last_exc = exc
                continue

            self._last_remote_base = base.rstrip('/')
            host, _ = self._split_host_port(base)
            if self._is_ipv4(host):
                self._ssh_discovered_ip = host
                if self.remote_host.get().strip() != host:
                    self.after(0, lambda h=host: self.remote_host.set(h))
            if base != self.remote_base.get().strip():
                self.after(0, lambda b=base: self.remote_base.set(b))
            return response

        if last_exc:
            raise last_exc
        raise requests.RequestException("Remote request failed")

    def _check_remote_status(self) -> None:
        def _worker() -> None:
            try:
                response = self._remote_request("GET", "/api/manual/status", timeout=5)
                body = response.json()
            except requests.RequestException as exc:  # noqa: BLE001
                self.log(f"[CONTROL] Status check failed: {exc}", error=True)
                self._show_error("Remote Status", str(exc))
                return

            base = self.remote_base.get().strip()
            self.log(f"[CONTROL] Remote status ({base}): {body}")
            self._show_info("Remote Status", str(body))

        threading.Thread(target=_worker, daemon=True).start()

    def _run_remote_command(
        self,
        command: str,
        title: str,
        *,
        background: bool = True,
        job_key: Optional[str] = None,
        job_pattern: Optional[str] = None,
    ) -> None:
        host = self.remote_host.get().strip()
        user = self.remote_user.get().strip() or "root1"
        password = self.remote_password.get()
        if not host:
            self.log("[CONTROL] SSH host is required for control mode commands", error=True)
            self._show_error(title, "Provide an SSH host in Control Mode Settings.")
            return

        def _worker() -> None:
            self.log(f"[CONTROL] Executing {title} via SSH on {host}")
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hostname=host, username=user, password=password, timeout=10)
                base_cmd = "cd ~/Capstone-CST498 && source .venv311/bin/activate"
                if background:
                    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_") or "remote_task"
                    log_path = f"/tmp/{slug}.log"
                    remote_cmd = f"{base_cmd} && nohup {command} > {log_path} 2>&1 & echo $!"
                else:
                    remote_cmd = f"{base_cmd} && {command}"
                escaped = remote_cmd.replace('"', '\\"')
                shell_cmd = f"bash -lc \"{escaped}\""
                stdin, stdout, stderr = client.exec_command(shell_cmd)
                stdout_data = stdout.read().decode().strip()
                stderr_output = stderr.read().decode().strip()
                exit_code = stdout.channel.recv_exit_status()
                client.close()
                if exit_code == 0:
                    if background:
                        pid_raw = stdout_data.strip()
                        pid_info = f" (PID {pid_raw})" if pid_raw else ""
                        self.log(f"[CONTROL] {title} dispatched successfully{pid_info}")
                        if pid_raw:
                            self.log(f"[CONTROL] Remote process id: {pid_raw}")
                        self.log(f"[CONTROL] Remote logs streaming to {log_path}")
                        if stderr_output:
                            self.log(f"[CONTROL] {title} stderr: {stderr_output}")
                        if job_key:
                            pattern = job_pattern or command
                            job_record: Dict[str, Any] = {
                                "host": host,
                                "pattern": pattern,
                                "pid": pid_raw,
                                "title": title,
                            }
                            if log_path:
                                job_record["log"] = log_path
                            self._remote_jobs[job_key] = job_record
                            if log_path:
                                self._ensure_log_window(job_key, title, host, log_path)
                            if job_key == INTEGRATED_JOB_KEY:
                                self.log("[CONTROL] Use 'Stop Integrated' to cancel the remote run if needed.")
                    else:
                        message = stderr_output or stdout_data or "Command completed successfully"
                        self.log(f"[CONTROL] {title}: {message}")
                        if job_key:
                            job_record = {
                                "host": host,
                                "pattern": job_pattern or command,
                                "title": title,
                            }
                            self._remote_jobs[job_key] = job_record
                else:
                    message = stderr_output or f"Command exited with code {exit_code}"
                    self.log(f"[CONTROL] {title} failed: {message}", error=True)
                    self._show_error(title, message)
            except Exception as exc:  # noqa: BLE001
                self.log(f"[CONTROL] {title} SSH error: {exc}", error=True)
                self._show_error(title, str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _analyze_frame(self, frame) -> tuple[Optional[np.ndarray], str]:
        annotated = frame.copy() if frame is not None else None
        summary = "No faces detected."
        if frame is None:
            return annotated, summary
        try:
            engine = FaceRecognitionEngine(frame_skip=1)
            detections = engine.analyze_frame(frame, skip_frame_check=True)
            if detections:
                lines = []
                for result in detections:
                    top, right, bottom, left = result.box
                    color = (0, 255, 0) if result.matched else (0, 0, 255)
                    cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
                    label = f"{result.name} ({result.confidence:.2f})"
                    cv2.putText(annotated, label, (left, max(20, top - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    marker = "✓" if result.matched else "✗"
                    lines.append(f"{marker} {result.name} ({result.confidence:.2f})")
                summary = "\n".join(lines)
            else:
                summary = "No faces detected."
        except Exception as exc:  # noqa: BLE001
            self.log(f"Face recognition engine unavailable: {exc}", error=True)
        return annotated, summary

    def _show_snapshot_popup(self, annotated, summary: str) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Face Snapshot")
        popup.resizable(False, False)

        success, encoded_img = cv2.imencode(".png", annotated)
        if not success:
            popup.destroy()
            self._show_error("Face Snapshot", "Unable to encode snapshot as PNG.")
            return

        encoded = base64.b64encode(encoded_img.tobytes()).decode("ascii")
        try:
            photo = PhotoImage(data=encoded, format="PNG")
        except Exception as exc:  # noqa: BLE001
            popup.destroy()
            self._show_error("Face Snapshot", f"Unable to render image: {exc}")
            return

        frame_widget = ttk.Frame(popup, padding=10)
        frame_widget.pack(fill="both", expand=True)

        image_label = ttk.Label(frame_widget, image=photo)
        image_label.image = photo  # Prevent garbage collection
        image_label.pack(padx=5, pady=5)

        ttk.Label(frame_widget, text=summary, justify="center").pack(padx=5, pady=(0, 10))
        ttk.Button(frame_widget, text="Close", command=popup.destroy).pack(pady=(0, 5))

    def _capture_remote_snapshot(self) -> None:
        base = self._remote_base_url()
        if not base:
            return

        def _worker() -> None:
            self.log("[CONTROL] Requesting remote face snapshot...")
            try:
                response = self._remote_request("GET", "/api/manual/capture", timeout=6)
                payload = response.json()
                encoded = payload.get('image')
                if not encoded:
                    raise ValueError("Response missing image field")
                buffer = base64.b64decode(encoded)
                frame_array = np.frombuffer(buffer, dtype=np.uint8)
                frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError("Failed to decode remote image")
            except Exception as exc:  # noqa: BLE001
                self.log(f"[CONTROL] Remote snapshot failed: {exc}", error=True)
                self._show_error("Remote Snapshot", str(exc))
                return

            annotated, summary = self._analyze_frame(frame)
            if annotated is None:
                self.log("[CONTROL] Snapshot captured but annotation failed", error=True)
                self._show_error("Remote Snapshot", "Received frame but could not process it.")
                return

            self.after(0, lambda: self._show_snapshot_popup(annotated, summary))
            self.log("[CONTROL] Snapshot captured from robot camera")

        threading.Thread(target=_worker, daemon=True).start()

    def _discover_remote_base(self) -> None:
        user = self.remote_user.get().strip() or "root1"
        password = self.remote_password.get()
        candidates = self._candidate_ssh_hosts()
        if not candidates:
            self.log("[CONTROL] SSH host is required to detect the API base", error=True)
            self._show_error("Control Mode", "Provide an SSH host before detecting the API base.")
            return

        def _worker() -> None:
            last_error: Optional[Exception] = None
            for host in candidates:
                self.log(f"[CONTROL] Detecting API endpoint via {user}@{host}...")
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(hostname=host, username=user, password=password, timeout=10)
                    detect_cmd = (
                        "set -o pipefail; "
                        "(hostname -I || ip -o addr show | awk '{print $4}')"
                    )
                    stdin, stdout, stderr = client.exec_command(f"bash -lc \"{detect_cmd}\"")
                    output = stdout.read().decode().strip()
                    error_output = stderr.read().decode().strip()
                    client.close()
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    continue

                if not output and error_output:
                    last_error = RuntimeError(error_output)
                    continue

                tokens = [segment.split('/')[0] for segment in output.replace("\n", " ").split() if segment]
                ipv4 = next((token for token in tokens if self._is_ipv4(token)), "")
                chosen = ipv4 or (tokens[0] if tokens else "")
                if not chosen:
                    last_error = RuntimeError("Remote host did not report any IP addresses.")
                    continue

                address = ipv4 or chosen
                base = self._format_base_url(address)
                if not base:
                    last_error = RuntimeError(f"Unable to format detected address: {address}")
                    continue

                self._last_remote_base = base.rstrip('/')
                if ipv4:
                    self._ssh_discovered_ip = ipv4
                    self.after(0, lambda h=ipv4: self.remote_host.set(h))
                    self.log(f"[CONTROL] Detected IPv4 {ipv4}; updated SSH host and API base.")
                else:
                    self.after(0, lambda h=host: self.remote_host.set(h))
                    self.log(f"[CONTROL] Detected address {address}; updated API base.")

                self.after(0, lambda b=base: self.remote_base.set(b))
                return

            message = f"SSH detection failed: {last_error}" if last_error else "SSH detection failed."
            self.log(f"[CONTROL] {message}", error=True)
            self._show_error("Control Mode", message)

        threading.Thread(target=_worker, daemon=True).start()

    def _candidate_ssh_hosts(self) -> List[str]:
        candidates: List[str] = []
        manual_entry = self.remote_host.get().strip()
        if manual_entry:
            candidates.append(manual_entry)

        if self._ssh_discovered_ip:
            candidates.append(self._ssh_discovered_ip)

        base_host, _ = self._split_host_port(self.remote_base.get().strip())
        if base_host:
            candidates.append(base_host)

        for alias in HOST_FALLBACKS:
            candidates.append(alias)

        unique: List[str] = []
        seen: Set[str] = set()
        for value in candidates:
            entry = value.strip()
            if not entry or entry in seen:
                continue
            seen.add(entry)
            unique.append(entry)
        return unique

    def _candidate_base_urls(self) -> List[str]:
        raw = self.remote_base.get().strip()
        host, port = self._split_host_port(raw)

        entries: List[str] = []

        # Prefer the most recently successful endpoint and any detected IPv4 first.
        if self._ssh_discovered_ip:
            entries.append(f"http://{self._ssh_discovered_ip}:{port}")

        if self._last_remote_base:
            entries.append(self._last_remote_base)

        detected_host = self.remote_host.get().strip()
        if detected_host and self._is_ipv4(detected_host):
            entries.append(f"http://{detected_host}:{port}")

        if raw:
            entries.append(raw)
        else:
            entries.append(f"http://{host}:{port}")

        for alias in HOST_FALLBACKS:
            entries.append(f"http://{alias}:{port}")

        candidates: List[str] = []
        seen: Set[str] = set()
        for value in entries:
            formatted = self._format_base_url(value)
            if not formatted or formatted in seen:
                continue
            seen.add(formatted)
            candidates.append(formatted.rstrip('/'))
        return candidates

    @staticmethod
    def _format_base_url(value: str) -> str:
        host, port = HarnessFrame._split_host_port(value)
        if not host:
            return ""
        host_display = f"[{host}]" if ':' in host and not host.startswith('[') else host
        return f"http://{host_display}:{port}".rstrip('/')

    @staticmethod
    def _split_host_port(value: str) -> tuple[str, int]:
        candidate = value.strip()
        if candidate.startswith('http://') or candidate.startswith('https://'):
            candidate = candidate.split('://', 1)[1]
        if '/' in candidate:
            candidate = candidate.split('/', 1)[0]

        host = candidate
        port_str = ""

        if candidate.startswith('['):
            closing = candidate.find(']')
            if closing != -1:
                host = candidate[1:closing]
                remainder = candidate[closing + 1:]
                if remainder.startswith(':'):
                    port_str = remainder[1:]
        else:
            if candidate.count(':') > 1:
                base, _, possible_port = candidate.rpartition(':')
                if possible_port.isdigit():
                    host = base
                    port_str = possible_port
                else:
                    host = candidate
            elif ':' in candidate:
                host, port_str = candidate.split(':', 1)

        port = DEFAULT_REMOTE_PORT
        if port_str.isdigit():
            port = int(port_str)
        host = host or 'raspberrypi'
        return host, port

    @staticmethod
    def _is_ipv4(value: str) -> bool:
        value = value.strip().split('/')[0]
        parts = value.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Server controls
    # ------------------------------------------------------------------
    def _update_flask_buttons(self) -> None:
        if self._flask_running_mode is None:
            self.btn_flask_debug.configure(text="Start Flask (Debug)", state="normal")
            self.btn_flask_waitress.configure(text="Start Flask via Waitress", state="normal")
            return

        if self._flask_running_mode == "debug":
            self.btn_flask_debug.configure(text="Stop Flask (Debug)", state="normal")
            self.btn_flask_waitress.configure(text="Start Flask via Waitress", state="disabled")
        else:
            self.btn_flask_debug.configure(text="Start Flask (Debug)", state="disabled")
            self.btn_flask_waitress.configure(text="Stop Flask via Waitress", state="normal")

    def _toggle_flask_server(self, mode: str) -> None:
        if self._flask_running_mode == mode:
            self._stop_flask_server()
            return

        if self._flask_running_mode is not None and self._flask_running_mode != mode:
            self.log("Flask server already running; stop it before starting another mode.", error=True)
            self._show_error("Flask Server", "Stop the running Flask server before launching a different mode.")
            return

        self._start_flask_server(mode)

    def _start_flask_server(self, mode: str) -> None:
        if mode not in {"debug", "waitress"}:
            raise ValueError("Unsupported Flask mode")

        if self._is_control_mode():
            self._start_flask_remote(mode)
        else:
            self._start_flask_local(mode)

    def _start_flask_local(self, mode: str) -> None:
        if self._flask_running_mode:
            return

        if mode == "debug":
            command = [sys.executable, str(FLASK_API_DIR / "app.py")]
            title = "Flask (Debug)"
        else:
            command = [
                sys.executable,
                "-m",
                "waitress",
                "--listen=0.0.0.0:5001",
                "flask_api.app:app",
            ]
            title = "Flask (Waitress)"

        def _worker() -> None:
            try:
                process = subprocess.Popen(command, cwd=PROJECT_ROOT, creationflags=CONSOLE_FLAG)
            except Exception as exc:  # noqa: BLE001
                self.log(f"{title} failed: {exc}", error=True)
                self._show_error(title, str(exc))
                return

            self.log(f"{title} launched locally")

            def _on_success() -> None:
                self._flask_local_process = process
                self._flask_running_mode = mode
                self._flask_remote = False
                self._update_flask_buttons()
                self.after(2000, self._verify_flask_state)

            self.after(0, _on_success)

        threading.Thread(target=_worker, daemon=True).start()

    def _start_flask_remote(self, mode: str) -> None:
        if self._flask_running_mode:
            return

        if mode == "debug":
            command = "python flask_api/app.py"
            title = "Flask (Debug)"
            pattern = "flask_api/app.py"
        else:
            command = "python -m waitress --listen=0.0.0.0:5001 flask_api.app:app"
            title = "Flask (Waitress)"
            pattern = "flask_api.app:app"

        self._run_remote_command(
            command,
            title,
            job_key=self._flask_job_key,
            job_pattern=pattern,
        )
        self._flask_running_mode = mode
        self._flask_remote = True
        self._flask_local_process = None
        self._update_flask_buttons()
        self.after(2500, self._verify_flask_state)

    def _stop_flask_server(self) -> None:
        if not self._flask_running_mode:
            return

        mode = self._flask_running_mode
        title = "Flask (Debug)" if mode == "debug" else "Flask (Waitress)"

        if self._flask_remote:
            pattern = "flask_api/app.py" if mode == "debug" else "flask_api.app:app"
            self._stop_remote_job(self._flask_job_key, pattern, title, quiet=False)
            self._close_log_window(self._flask_job_key)
        else:
            process = self._flask_local_process
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:  # noqa: BLE001
                    with suppress(Exception):
                        process.kill()
            self.log(f"{title} stopped locally")

        self._flask_running_mode = None
        self._flask_local_process = None
        self._flask_remote = False
        self._update_flask_buttons()

    def _verify_flask_state(self) -> None:
        if not self._flask_running_mode:
            return

        if self._flask_remote:
            if self._flask_job_key not in self._remote_jobs:
                self.log("Flask server did not stay running; resetting controls.", error=True)
                self._flask_running_mode = None
                self._flask_remote = False
                self._update_flask_buttons()
        else:
            process = self._flask_local_process
            if process and process.poll() is not None:
                self.log("Local Flask process exited unexpectedly; resetting controls.", error=True)
                self._flask_running_mode = None
                self._flask_local_process = None
                self._update_flask_buttons()

    def open_enroll_page(self) -> None:
        if self._is_control_mode():
            base = self._remote_base_url()
            if not base:
                return
            webbrowser.open_new_tab(f"{base}/enroll")
            self.log("Opened remote enrollment page in browser")
        else:
            webbrowser.open_new_tab("http://localhost:5001/enroll")
            self.log("Enrollment page opened in browser")

    def open_orders_page(self) -> None:
        base = self._remote_base_url() if self._is_control_mode() else "http://localhost:5001"
        if not base:
            return
        webbrowser.open_new_tab(f"{base}/order")
        target = "remote" if self._is_control_mode() else "local"
        self.log(f"Opened {target} orders page in browser")

    def open_admin_page(self) -> None:
        base = self._remote_base_url() if self._is_control_mode() else "http://localhost:5001"
        if not base:
            return
        webbrowser.open_new_tab(f"{base}/admin")
        target = "remote" if self._is_control_mode() else "local"
        self.log(f"Opened {target} admin page in browser")

    def check_flask_api(self) -> None:
        def _worker() -> None:
            if self._is_control_mode():
                try:
                    response = self._remote_request("GET", "/api/manual/status", timeout=5)
                    body = response.json()
                    base = self.remote_base.get().strip()
                    self.log(f"Remote Flask API reachable at {base}")
                    self._show_info("Flask API", f"Remote Flask API reachable at {base}\nStatus: {body}")
                except requests.RequestException as exc:
                    base = self.remote_base.get().strip()
                    self.log(f"Remote Flask API unreachable at {base}: {exc}", error=True)
                    self._show_error("Flask API", f"Remote endpoint unreachable: {exc}")
            else:
                candidates = [FLASK_APP_URL] + [url for url in ALTERNATIVE_FLASK_URLS if url != FLASK_APP_URL]
                for url in candidates:
                    try:
                        response = requests.get(f"{url}/enroll", timeout=3)
                        if response.status_code < 500:
                            message = f"Flask API reachable at {url}"
                            self.log(message)
                            self._show_info("Flask API", message)
                            return
                    except requests.RequestException as exc:
                        self.log(f"Flask API unreachable at {url}: {exc}", error=True)
                self._show_error("Flask API", "All configured endpoints are unreachable.")

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Recognition controls
    # ------------------------------------------------------------------
    def _schedule_integrated_log_attach(self, attempt: int = 0) -> None:
        if attempt > 10:
            return

        job_info = self._remote_jobs.get(INTEGRATED_JOB_KEY)
        host = None
        if job_info:
            host = job_info.get("host")
        if not host:
            host = self._ssh_discovered_ip or self.remote_host.get().strip()
        if not host:
            self.after(1000, lambda: self._schedule_integrated_log_attach(attempt + 1))
            return

        log_path = "/tmp/integrated_recognition_gui.log"
        self._ensure_log_window(INTEGRATED_JOB_KEY, "Integrated Recognition", host, log_path)
        if job_info is not None:
            job_info["log"] = log_path
        else:
            self._remote_jobs[INTEGRATED_JOB_KEY] = {
                "host": host,
                "pattern": "integrated_recognition_system.py",
                "title": "Integrated Recognition",
                "log": log_path,
            }

    def launch_integrated_gui(self) -> None:
        if self._is_control_mode():
            self._stop_remote_job(INTEGRATED_JOB_KEY, "integrated_recognition_system.py", "Integrated Recognition", quiet=True)
            self._run_remote_command(
                "python integrated_recognition_system.py --robot",
                "Integrated Recognition (GUI)",
                job_key=INTEGRATED_JOB_KEY,
                job_pattern="integrated_recognition_system.py",
            )
            self.after(2000, self._schedule_integrated_log_attach)
            return
        self.run_command_async([sys.executable, str(PROJECT_ROOT / "integrated_recognition_system.py")], "Integrated Recognition (GUI)")

    def launch_integrated_headless(self) -> None:
        if self._is_control_mode():
            self._stop_remote_job(INTEGRATED_JOB_KEY, "integrated_recognition_system.py", "Integrated Recognition", quiet=True)
            self._run_remote_command(
                "python integrated_recognition_system.py --robot --headless",
                "Integrated Recognition (Headless)",
                job_key=INTEGRATED_JOB_KEY,
                job_pattern="integrated_recognition_system.py",
            )
            self.after(2000, self._schedule_integrated_log_attach)
            return
        self.run_command_async([
            sys.executable,
            str(PROJECT_ROOT / "integrated_recognition_system.py"),
            "--headless",
        ], "Integrated Recognition (Headless)")

    def stop_integrated(self) -> None:
        if self._is_control_mode():
            self._stop_remote_job(INTEGRATED_JOB_KEY, "integrated_recognition_system.py", "Integrated Recognition")
            return
        self.log("[SIM] Stop Integrated is only available in Control mode; close the local window or console process instead.")

    def open_live_preview(self) -> None:
        if not self._is_control_mode():
            self._show_error("Live Preview", "Switch to Control mode to view the remote camera feed.")
            return
        if not self._remote_base_url():
            return
        if self._preview_window and self._preview_window.winfo_exists():
            self._preview_window.deiconify()
            self._preview_window.lift()
            return

        self._preview_window = tk.Toplevel(self.root)
        self._preview_window.title("Remote Camera Preview")
        self._preview_window.resizable(False, False)
        self._preview_window.protocol("WM_DELETE_WINDOW", self._close_live_preview)

        container = ttk.Frame(self._preview_window, padding=10)
        container.pack(fill="both", expand=True)

        self._preview_label = ttk.Label(container, text="Connecting to remote camera...")
        self._preview_label.pack()

        self.log("[CONTROL] Live preview window opened.")
        self._preview_running = True
        self._preview_fetch_inflight = False
        self._preview_photo = None
        self._preview_last_error = None
        self._schedule_preview_fetch()

    def _close_live_preview(self) -> None:
        self._preview_running = False
        self._preview_fetch_inflight = False
        if self._preview_window and self._preview_window.winfo_exists():
            self._preview_window.destroy()
            self.log("[CONTROL] Live preview window closed.")
        self._preview_window = None
        self._preview_label = None
        self._preview_photo = None
        self._preview_last_error = None

    def _schedule_preview_fetch(self, delay_ms: int = 0) -> None:
        if not self._preview_running:
            return
        if delay_ms <= 0:
            self._refresh_preview_frame()
        else:
            self.after(delay_ms, self._refresh_preview_frame)

    def _refresh_preview_frame(self) -> None:
        if not self._preview_running or self._preview_fetch_inflight:
            return
        self._preview_fetch_inflight = True
        threading.Thread(target=self._preview_worker, daemon=True).start()

    def _preview_worker(self) -> None:
        try:
            response = self._remote_request("GET", "/api/manual/capture", timeout=6)
            payload = response.json()
            encoded = payload.get("image")
            if not encoded:
                raise ValueError("Response missing image field")
            buffer = base64.b64decode(encoded)
            frame_array = np.frombuffer(buffer, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("Failed to decode remote image")
            success, png_buffer = cv2.imencode(".png", frame)
            if not success:
                raise ValueError("Unable to encode preview frame")
            encoded_png = base64.b64encode(png_buffer.tobytes()).decode("ascii")
            self.after(0, lambda data=encoded_png: self._update_preview_image(data))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda msg=str(exc): self._handle_preview_error(msg))
        finally:
            self._preview_fetch_inflight = False
            if self._preview_running:
                self._schedule_preview_fetch(750)

    def _update_preview_image(self, encoded_png: str) -> None:
        if not self._preview_running or not self._preview_label:
            return
        try:
            photo = PhotoImage(data=encoded_png, format="PNG")
        except Exception as exc:  # noqa: BLE001
            self._handle_preview_error(str(exc))
            return
        self._preview_photo = photo
        self._preview_label.configure(image=photo, text="")
        self._preview_label.image = photo
        self._preview_last_error = None

    def _handle_preview_error(self, message: str) -> None:
        if not self._preview_running or not self._preview_label:
            return
        summary = message.splitlines()[0]
        if self._preview_last_error != summary:
            self.log(f"[CONTROL] Live preview error: {summary}", error=True)
            self._preview_last_error = summary
        self._preview_label.configure(text=f"Preview error: {summary}", image="")
        self._preview_label.image = None
        self._preview_photo = None

    def capture_face_snapshot(self) -> None:
        if self._is_control_mode():
            self._capture_remote_snapshot()
            return

        def _worker() -> None:
            self.log("Capturing face snapshot from default camera...")
            camera = cv2.VideoCapture(0)
            if not camera or not camera.isOpened():
                self.log("Camera not available", error=True)
                self._show_error("Snapshot", "Unable to open camera 0.")
                return

            try:
                time.sleep(0.3)
                ret, frame = camera.read()
            finally:
                camera.release()

            if not ret or frame is None:
                self.log("Failed to read frame from camera", error=True)
                self._show_error("Snapshot", "Failed to capture a frame from the camera.")
                return

            annotated, summary = self._analyze_frame(frame)
            if annotated is None:
                self.log("Failed to analyze captured frame", error=True)
                self._show_error("Snapshot", "Captured frame but analysis failed.")
                return

            self.after(0, lambda: self._show_snapshot_popup(annotated, summary))
            self.log("Snapshot captured from local camera")

        threading.Thread(target=_worker, daemon=True).start()

    def sync_face_encodings(self) -> None:
        def _worker() -> None:
            self.log("Syncing face encodings from database...")
            encodings, names = load_encodings_from_db()
            if not encodings:
                cached_encodings, cached_names = load_encodings_cache()
                if cached_encodings:
                    self.log("Database unavailable; loaded encodings from cache", error=True)
                    self._show_info("Face Encodings", f"Using cached encodings ({len(cached_names)} face(s)).")
                else:
                    self.log("No encodings available", error=True)
                    self._show_error("Face Encodings", "No encodings retrieved from database or cache.")
                return

            save_encodings_cache(encodings, names)
            preview = "\n".join(f"{banner} - {display}" for banner, display in names[:10])
            if len(names) > 10:
                preview += f"\n... (+{len(names) - 10} more)"
            self.log(f"Synced {len(names)} face(s) to local cache")
            self._show_info("Face Encodings", f"Synced {len(names)} face(s).\n\n{preview}")

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Database & utility controls
    # ------------------------------------------------------------------
    def list_users(self) -> None:
        def _worker() -> None:
            self.log("Fetching registered users...")
            conn: pymysql.connections.Connection | None = None
            rows: list[dict[str, str]] = []
            try:
                conn = get_db_connection()
                with conn.cursor(DictCursor) as cur:
                    cur.execute(
                        "SELECT banner_id, first_name, last_name, email FROM users ORDER BY banner_id LIMIT 50;"
                    )
                    rows = cur.fetchall()
            except Exception as exc:  # noqa: BLE001
                self.log(f"Database query failed: {exc}", error=True)
                self._show_error("Database", f"Failed to fetch users: {exc}")
                return
            finally:
                if conn is not None:
                    conn.close()

            if not rows:
                self.log("No users found in database", error=True)
                self._show_info("Registered Users", "No users found.")
                return

            lines = [
                f"{row['banner_id']} - {row['first_name']} {row['last_name']} ({row['email']})"
                for row in rows
            ]
            summary = "\n".join(lines)
            self._show_info("Registered Users", summary)
            self.log(f"Fetched {len(rows)} user(s)")

        threading.Thread(target=_worker, daemon=True).start()

    def check_db_connection(self) -> None:
        def _worker() -> None:
            self.log("Checking database connectivity...")
            conn: pymysql.connections.Connection | None = None
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM users;")
                    row = cur.fetchone()
                    if isinstance(row, dict):
                        count = next(iter(row.values())) if row else 0
                    else:
                        count = row[0] if row else 0
            except Exception as exc:  # noqa: BLE001
                self.log(f"Database connection failed: {exc}", error=True)
                self._show_error("Database", f"Connection failed: {exc}")
                return
            finally:
                if conn is not None:
                    conn.close()

            message = f"Database connection OK. Users table has {count} record(s)."
            self.log(message)
            self._show_info("Database", message)

        threading.Thread(target=_worker, daemon=True).start()

    def run_sign_classifier(self) -> None:
        image_path = filedialog.askopenfilename(title="Select traffic sign image")
        if not image_path:
            return
        command = [
            sys.executable,
            "-m",
            "robot_navigation.sign_recognition.run_classifier",
            "--image",
            image_path,
            "--show",
        ]
        self.run_command_async(command, "Sign Classifier")

    def open_uploads_folder(self) -> None:
        uploads = PROJECT_ROOT / "uploads"
        if not uploads.exists():
            self.log(f"Uploads folder not found at {uploads}", error=True)
            self._show_error("Uploads", "Uploads folder not found.")
            return

        try:
            if hasattr(os, "startfile"):
                os.startfile(str(uploads))  # type: ignore[attr-defined]
            else:
                webbrowser.open(str(uploads))
            self.log(f"Opened {uploads}")
        except Exception as exc:  # noqa: BLE001
            self.log(f"Failed to open uploads folder: {exc}", error=True)
            self._show_error("Uploads", str(exc))


def launch_sim_harness() -> None:
    root = tk.Tk()
    frame = HarnessFrame(root, set_window_chrome=True)
    frame.pack(fill="both", expand=True)
    root.mainloop()