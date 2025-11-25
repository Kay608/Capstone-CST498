import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Set

import paramiko
import requests


class ManualControlFrame(ttk.Frame):
    """Reusable frame that provides the rover manual control UI."""

    def __init__(self, master: tk.Misc, *, set_window_chrome: bool = False) -> None:
        super().__init__(master)
        self.root = self.winfo_toplevel()
        if set_window_chrome and isinstance(self.root, tk.Tk):
            self.root.title("Rover RC Control")
            self.root.geometry("420x400")

        self.api_base = tk.StringVar(master=self, value="http://raspberrypi.local:5001")
        self.api_key = tk.StringVar(master=self, value="")
        self.speed = tk.DoubleVar(master=self, value=0.4)
        self.duration = tk.DoubleVar(master=self, value=0.5)
        self.angle = tk.DoubleVar(master=self, value=90.0)
        self.servo_angle = tk.IntVar(master=self, value=90)
        self.ssh_host = tk.StringVar(master=self, value="raspberrypi")
        self.ssh_user = tk.StringVar(master=self, value="root1")
        self.ssh_password = tk.StringVar(master=self, value="")
        self.status_text = tk.StringVar(master=self, value="Idle")
        self.continuous_mode = tk.BooleanVar(master=self, value=False)

        self._active_keys: Set[str] = set()
        self._last_drive_command: Optional[tuple] = None

        self._build_ui()
        self._register_keybindings()

    # --- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        config = ttk.LabelFrame(self, text="Robot Endpoint")
        config.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        config.columnconfigure(1, weight=1)

        ttk.Label(config, text="Base URL:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(config, textvariable=self.api_base, width=36).grid(row=0, column=1, padx=6, pady=4, sticky="ew")

        ttk.Label(config, text="API Key:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(config, textvariable=self.api_key, width=36, show="*").grid(row=1, column=1, padx=6, pady=4, sticky="ew")

        ttk.Button(config, text="Check Status", command=self._check_status).grid(row=0, column=2, rowspan=2, padx=6, pady=4)

        ssh_frame = ttk.LabelFrame(self, text="Remote Startup")
        ssh_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        for idx in range(5):
            ssh_frame.columnconfigure(idx, weight=0)
        ssh_frame.columnconfigure(1, weight=1)

        ttk.Label(ssh_frame, text="Host").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(ssh_frame, textvariable=self.ssh_host, width=16).grid(row=0, column=1, padx=6, pady=4, sticky="ew")
        ttk.Label(ssh_frame, text="User").grid(row=0, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(ssh_frame, textvariable=self.ssh_user, width=12).grid(row=0, column=3, padx=6, pady=4)
        ttk.Label(ssh_frame, text="Password").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(ssh_frame, textvariable=self.ssh_password, show="*", width=16).grid(row=1, column=1, padx=6, pady=4, sticky="ew")
        ttk.Button(ssh_frame, text="Start API", command=self._start_remote_api).grid(row=0, column=4, padx=6, pady=4)
        ttk.Button(ssh_frame, text="Stop API", command=self._stop_remote_api).grid(row=1, column=4, padx=6, pady=4)

        sliders = ttk.LabelFrame(self, text="Command Settings")
        sliders.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        sliders.columnconfigure(1, weight=1)

        ttk.Label(sliders, text="Speed (0-1)").grid(row=0, column=0, sticky="w", padx=8)
        ttk.Scale(sliders, from_=0.1, to=1.0, orient="horizontal", variable=self.speed).grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(sliders, text="Duration (s)").grid(row=1, column=0, sticky="w", padx=8)
        ttk.Scale(sliders, from_=0.1, to=5.0, orient="horizontal", variable=self.duration).grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(sliders, text="Turn Angle (°)").grid(row=2, column=0, sticky="w", padx=8)
        ttk.Scale(sliders, from_=10, to=180, orient="horizontal", variable=self.angle).grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        ttk.Checkbutton(sliders, text="Continuous mode", variable=self.continuous_mode, command=self._on_continuous_toggled).grid(row=3, column=0, columnspan=2, padx=8, pady=4, sticky="w")

        buttons = ttk.LabelFrame(self, text="Controls")
        buttons.grid(row=3, column=0, sticky="nsew", padx=10, pady=8)
        buttons.columnconfigure((0, 1, 2), weight=1)

        button_specs = [
            ("forward", "Forward", 0, 1),
            ("back", "Back", 2, 1),
            ("left", "Left", 1, 0),
            ("right", "Right", 1, 2),
        ]
        for direction, label, row, column in button_specs:
            btn = ttk.Button(buttons, text=label, command=lambda d=direction: self._send_discrete_move(d))
            btn.grid(row=row, column=column, padx=10, pady=6, sticky="ew")
            btn.bind("<ButtonPress-1>", lambda event, d=direction: self._handle_button_press(event, d))
            btn.bind("<ButtonRelease-1>", lambda event, d=direction: self._handle_button_release(event, d))
            btn.bind("<Leave>", lambda event, d=direction: self._handle_button_leave(event, d))

        ttk.Button(buttons, text="Stop", command=self._handle_stop_button).grid(row=1, column=1, padx=10, pady=6, sticky="ew")

        servo_frame = ttk.LabelFrame(self, text="Camera Servo")
        servo_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=8)
        servo_frame.columnconfigure(0, weight=1)
        ttk.Scale(servo_frame, from_=0, to=180, orient="horizontal", variable=self.servo_angle).grid(row=0, column=0, sticky="ew", padx=8, pady=4)
        ttk.Button(servo_frame, text="Set Angle", command=self._send_servo).grid(row=0, column=1, padx=8, pady=4)

        info = ttk.LabelFrame(self, text="Status")
        info.grid(row=5, column=0, sticky="nsew", padx=10, pady=8)
        info.columnconfigure(0, weight=1)
        ttk.Label(info, textvariable=self.status_text, anchor="w", wraplength=360).grid(row=0, column=0, sticky="ew", padx=8, pady=6)

        self.rowconfigure(5, weight=1)

    def _register_keybindings(self) -> None:
        self.root.bind("<KeyPress-Up>", lambda event: self._handle_key_press("forward"))
        self.root.bind("<KeyRelease-Up>", lambda event: self._handle_key_release("forward"))
        self.root.bind("<KeyPress-Down>", lambda event: self._handle_key_press("back"))
        self.root.bind("<KeyRelease-Down>", lambda event: self._handle_key_release("back"))
        self.root.bind("<KeyPress-Left>", lambda event: self._handle_key_press("left"))
        self.root.bind("<KeyRelease-Left>", lambda event: self._handle_key_release("left"))
        self.root.bind("<KeyPress-Right>", lambda event: self._handle_key_press("right"))
        self.root.bind("<KeyRelease-Right>", lambda event: self._handle_key_release("right"))
        self.root.bind("<space>", self._on_space)

    # --- Networking helpers ---------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = self.api_key.get().strip()
        if token:
            headers["X-Api-Key"] = token
        return headers

    def _post_async(self, path: str, payload: Optional[Dict], success_msg: Optional[str]) -> None:
        def worker() -> None:
            url = self.api_base.get().rstrip('/') + path
            try:
                response = requests.post(url, json=payload, headers=self._headers(), timeout=4)
                response.raise_for_status()
                if success_msg:
                    body = response.json()
                    self._log(f"✅ {success_msg}: {body}")
            except requests.RequestException as exc:
                self._log(f"⚠️ Request failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _check_status(self) -> None:
        def worker() -> None:
            url = self.api_base.get().rstrip('/') + '/api/manual/status'
            try:
                response = requests.get(url, headers=self._headers(), timeout=4)
                response.raise_for_status()
                body = response.json()
                self._log(f"Status: {body}")
            except requests.RequestException as exc:
                self._log(f"⚠️ Status check failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    # --- Command helpers ------------------------------------------------
    def _send_discrete_move(self, direction: str) -> None:
        payload = {
            'direction': direction,
            'speed': self.speed.get(),
            'duration': self.duration.get(),
            'angle': self.angle.get(),
        }
        self._log(f"Sending {direction} command...")
        self._post_async('/api/manual/move', payload, f"Move {direction}")

    def _handle_key_press(self, direction: str) -> None:
        if self.continuous_mode.get():
            if direction not in self._active_keys:
                self._active_keys.add(direction)
                self._update_continuous_drive()
        else:
            self._send_discrete_move(direction)

    def _handle_key_release(self, direction: str) -> None:
        if not self.continuous_mode.get():
            return
        if direction in self._active_keys:
            self._active_keys.remove(direction)
            self._update_continuous_drive()

    def _handle_button_press(self, _event: tk.Event, direction: str) -> Optional[str]:
        if not self.continuous_mode.get():
            return None
        if direction not in self._active_keys:
            self._active_keys.add(direction)
            self._update_continuous_drive()
        return "break"

    def _handle_button_release(self, _event: tk.Event, direction: str) -> Optional[str]:
        if not self.continuous_mode.get():
            return None
        if direction in self._active_keys:
            self._active_keys.remove(direction)
        self._update_continuous_drive()
        return "break"

    def _handle_button_leave(self, _event: tk.Event, direction: str) -> None:
        if not self.continuous_mode.get():
            return
        if direction in self._active_keys:
            self._active_keys.remove(direction)
            self._update_continuous_drive()

    def _handle_stop_button(self) -> None:
        self._handle_space()

    def _on_space(self, _event: tk.Event) -> str:
        self._handle_space()
        return "break"

    def _handle_space(self) -> None:
        if self.continuous_mode.get():
            self._active_keys.clear()
            self._last_drive_command = None
            self._send_drive(0.0, 0.0)
        self._send_stop()

    def _update_continuous_drive(self) -> None:
        if not self.continuous_mode.get():
            return

        if not self._active_keys:
            if self._last_drive_command != (0.0, 0.0):
                self._send_drive(0.0, 0.0)
                self._last_drive_command = (0.0, 0.0)
                self._log("Continuous: stop")
            return

        base_speed = max(0.0, min(1.0, float(self.speed.get())))
        linear = 0.0
        angular = 0.0
        if 'forward' in self._active_keys:
            linear += 1.0
        if 'back' in self._active_keys:
            linear -= 1.0
        if 'left' in self._active_keys:
            angular += 1.0
        if 'right' in self._active_keys:
            angular -= 1.0

        linear *= base_speed
        angular *= base_speed

        left = linear - angular
        right = linear + angular

        max_mag = max(abs(left), abs(right))
        if max_mag > 1.0:
            left /= max_mag
            right /= max_mag

        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))

        quantized = (round(left, 3), round(right, 3))
        if quantized == self._last_drive_command:
            return

        self._last_drive_command = quantized
        self._send_drive(left, right)
        self._log(f"Continuous: left={quantized[0]:.2f} right={quantized[1]:.2f}")

    def _send_drive(self, left: float, right: float) -> None:
        payload = {
            'left_speed': round(left, 3),
            'right_speed': round(right, 3),
        }
        self._post_async('/api/manual/drive', payload, None)

    def _on_continuous_toggled(self) -> None:
        self.focus_set()
        if not self.continuous_mode.get():
            if self._active_keys:
                self._active_keys.clear()
            self._last_drive_command = None
            self._send_drive(0.0, 0.0)
            self._send_stop()
            self._log("Continuous mode disabled.")
        else:
            self._last_drive_command = None
            self._log("Continuous mode enabled. Hold arrows or press buttons.")

    def _send_stop(self) -> None:
        self._log("Sending stop command...")
        self._post_async('/api/manual/stop', None, "Stop")

    def _send_servo(self) -> None:
        payload = {
            'angle': self.servo_angle.get(),
        }
        self._log(f"Setting camera angle to {payload['angle']}°...")
        self._post_async('/api/manual/camera', payload, "Camera servo")

    def _start_remote_api(self) -> None:
        def worker() -> None:
            host = self.ssh_host.get().strip()
            user = self.ssh_user.get().strip() or 'root1'
            password = self.ssh_password.get()
            if not host:
                self._log("⚠️ SSH host is required")
                return
            self._log(f"Connecting to {user}@{host}...")
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hostname=host, username=user, password=password, timeout=10)
                remote_cmd = (
                    "bash -lc 'cd ~/Capstone-CST498 && "
                    "source .venv/bin/activate && "
                    "cd flask_api && "
                    "nohup python app.py >/tmp/rc_manual.log 2>&1 &'"
                )
                stdin, stdout, stderr = client.exec_command(remote_cmd)
                exit_code = stdout.channel.recv_exit_status()
                client.close()
                if exit_code == 0:
                    self._log("✅ Flask API started (remote)")
                else:
                    error_output = stderr.read().decode().strip()
                    self._log(f"⚠️ Remote start failed: {error_output or 'exit code ' + str(exit_code)}")
            except Exception as exc:  # noqa: BLE001
                self._log(f"⚠️ SSH error: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _stop_remote_api(self) -> None:
        def worker() -> None:
            host = self.ssh_host.get().strip()
            user = self.ssh_user.get().strip() or 'root1'
            password = self.ssh_password.get()
            if not host:
                self._log("⚠️ SSH host is required")
                return
            self._log(f"Stopping API on {host}...")
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hostname=host, username=user, password=password, timeout=10)
                remote_cmd = (
                    "bash -lc 'pkill -f "
                    """flask_api/app.py""" "
                    "|| pkill -f \"python app.py\"'"
                )
                stdin, stdout, stderr = client.exec_command(remote_cmd)
                stdout.channel.recv_exit_status()
                client.close()
                self._log("✅ Flask API stop signal sent")
            except Exception as exc:  # noqa: BLE001
                self._log(f"⚠️ SSH error: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    # --- Logging --------------------------------------------------------
    def _log(self, message: str) -> None:
        self.after(0, lambda: self.status_text.set(message))


def launch_manual_control() -> None:
    root = tk.Tk()
    frame = ManualControlFrame(root, set_window_chrome=True)
    frame.pack(fill="both", expand=True)
    root.mainloop()
```},