"""Reusable frame version of the simulation harness UI."""

from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional
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


class HarnessFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, *, set_window_chrome: bool = False) -> None:
        super().__init__(master)
        self.root = self.winfo_toplevel()
        if set_window_chrome and hasattr(self.root, "title"):
            self.root.title("Capstone Simulation Harness")
            self.root.geometry("660x600")

        self.mode = tk.StringVar(self, value="simulation")
        self.remote_base = tk.StringVar(self, value="http://raspberrypi.local:5001")
        self.remote_api_key = tk.StringVar(self, value="")
        self.remote_host = tk.StringVar(self, value="raspberrypi")
        self.remote_user = tk.StringVar(self, value="root1")
        self.remote_password = tk.StringVar(self, value="")
        self._control_inputs: list[tk.Widget] = []

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

        ttk.Button(server_frame, text="Start Flask (Debug)", command=self.start_flask_debug).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Start Flask via Waitress", command=self.start_flask_waitress).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Open Enrollment Page", command=self.open_enroll_page).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(server_frame, text="Check Flask Health", command=self.check_flask_api).grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        recognition_frame = ttk.LabelFrame(main, text="Recognition & Vision")
        recognition_frame.pack(fill="x", pady=(0, 10))
        recognition_frame.columnconfigure((0, 1), weight=1)

        ttk.Button(recognition_frame, text="Launch Integrated (GUI)", command=self.launch_integrated_gui).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Launch Integrated (Headless)", command=self.launch_integrated_headless).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Capture Face Snapshot", command=self.capture_face_snapshot).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(recognition_frame, text="Sync Face Encodings", command=self.sync_face_encodings).grid(row=1, column=1, padx=5, pady=5, sticky="ew")

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
        base = self.remote_base.get().strip()
        if not base:
            self._show_error("Control Mode", "Set the API base URL (e.g., http://raspberrypi.local:5001).")
            return None
        return base.rstrip('/')

    def _remote_headers(self) -> dict[str, str]:
        token = self.remote_api_key.get().strip()
        headers: dict[str, str] = {}
        if token:
            headers["X-Api-Key"] = token
        return headers

    def _check_remote_status(self) -> None:
        base = self._remote_base_url()
        if not base:
            return

        def _worker() -> None:
            url = f"{base}/api/manual/status"
            try:
                response = requests.get(url, headers=self._remote_headers(), timeout=5)
                response.raise_for_status()
                body = response.json()
            except requests.RequestException as exc:  # noqa: BLE001
                self.log(f"[CONTROL] Status check failed: {exc}", error=True)
                self._show_error("Remote Status", str(exc))
                return

            self.log(f"[CONTROL] Remote status: {body}")
            self._show_info("Remote Status", str(body))

        threading.Thread(target=_worker, daemon=True).start()

    def _run_remote_command(self, command: str, title: str, *, background: bool = True) -> None:
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
                base_cmd = "cd ~/Capstone-CST498 && source .venv/bin/activate"
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
                        pid_info = f" (PID {stdout_data})" if stdout_data else ""
                        self.log(f"[CONTROL] {title} dispatched successfully{pid_info}")
                        if stdout_data:
                            self.log(f"[CONTROL] Remote process id: {stdout_data}")
                        self.log(f"[CONTROL] Remote logs streaming to {log_path}")
                        if stderr_output:
                            self.log(f"[CONTROL] {title} stderr: {stderr_output}")
                    else:
                        message = stderr_output or stdout_data or "Command completed successfully"
                        self.log(f"[CONTROL] {title}: {message}")
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
            url = f"{base}/api/manual/capture"
            try:
                response = requests.get(url, headers=self._remote_headers(), timeout=6)
                response.raise_for_status()
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

    # ------------------------------------------------------------------
    # Server controls
    # ------------------------------------------------------------------
    def start_flask_debug(self) -> None:
        if self._is_control_mode():
            self._run_remote_command("python flask_api/app.py", "Flask (Debug)")
            return
        self.run_command_async([sys.executable, str(FLASK_API_DIR / "app.py")], "Flask (Debug)")

    def start_flask_waitress(self) -> None:
        if self._is_control_mode():
            self._run_remote_command(
                "python -m waitress --listen=0.0.0.0:5001 flask_api.app:app",
                "Flask (Waitress)",
            )
            return
        self.run_command_async([
            sys.executable,
            "-m",
            "waitress",
            "--listen=0.0.0.0:5001",
            "flask_api.app:app",
        ], "Flask (Waitress)")

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

    def check_flask_api(self) -> None:
        def _worker() -> None:
            if self._is_control_mode():
                base = self._remote_base_url()
                if not base:
                    return
                try:
                    response = requests.get(f"{base}/api/manual/status", headers=self._remote_headers(), timeout=5)
                    response.raise_for_status()
                    self.log(f"Remote Flask API reachable at {base}")
                    self._show_info("Flask API", f"Remote Flask API reachable at {base}")
                except requests.RequestException as exc:
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
    def launch_integrated_gui(self) -> None:
        if self._is_control_mode():
            self._run_remote_command("python integrated_recognition_system.py", "Integrated Recognition (GUI)")
            return
        self.run_command_async([sys.executable, str(PROJECT_ROOT / "integrated_recognition_system.py")], "Integrated Recognition (GUI)")

    def launch_integrated_headless(self) -> None:
        if self._is_control_mode():
            self._run_remote_command("python integrated_recognition_system.py --headless", "Integrated Recognition (Headless)")
            return
        self.run_command_async([
            sys.executable,
            str(PROJECT_ROOT / "integrated_recognition_system.py"),
            "--headless",
        ], "Integrated Recognition (Headless)")

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