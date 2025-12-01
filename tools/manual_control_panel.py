import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Set

DEFAULT_REMOTE_PORT = 5001
# Prefer the hotspot-friendly mDNS hostname before other fallbacks.
HOST_FALLBACKS = ("raspberrypi.local", "raspberrypi")

import paramiko
import requests


class ManualControlFrame(ttk.Frame):
    """Reusable frame that provides the rover manual control UI."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        set_window_chrome: bool = False,
        api_base_var: Optional[tk.StringVar] = None,
        api_key_var: Optional[tk.StringVar] = None,
        ssh_host_var: Optional[tk.StringVar] = None,
        ssh_user_var: Optional[tk.StringVar] = None,
        ssh_password_var: Optional[tk.StringVar] = None,
    ) -> None:
        super().__init__(master)
        self.root = self.winfo_toplevel()
        if set_window_chrome and isinstance(self.root, tk.Tk):
            self.root.title("Rover RC Control")
            self.root.geometry("420x400")

        default_base = "http://raspberrypi.local:5001"
        default_host = "raspberrypi.local"
        default_user = "root1"

        if api_base_var is None:
            self.api_base = tk.StringVar(master=self, value=default_base)
        else:
            self.api_base = api_base_var
            if not self.api_base.get():
                self.api_base.set(default_base)

        if api_key_var is None:
            self.api_key = tk.StringVar(master=self, value="")
        else:
            self.api_key = api_key_var

        self.speed = tk.DoubleVar(master=self, value=0.4)
        self.duration = tk.DoubleVar(master=self, value=0.5)
        self.angle = tk.DoubleVar(master=self, value=90.0)
        self.servo_angle = tk.IntVar(master=self, value=90)

        if ssh_host_var is None:
            self.ssh_host = tk.StringVar(master=self, value=default_host)
        else:
            self.ssh_host = ssh_host_var
            if not self.ssh_host.get():
                self.ssh_host.set(default_host)

        if ssh_user_var is None:
            self.ssh_user = tk.StringVar(master=self, value=default_user)
        else:
            self.ssh_user = ssh_user_var
            if not self.ssh_user.get():
                self.ssh_user.set(default_user)

        if ssh_password_var is None:
            self.ssh_password = tk.StringVar(master=self, value="")
        else:
            self.ssh_password = ssh_password_var

        self.status_text = tk.StringVar(master=self, value="Idle")
        self.continuous_mode = tk.BooleanVar(master=self, value=False)

        self._active_keys: Set[str] = set()
        self._last_drive_command: Optional[tuple] = None
        self._last_remote_base: Optional[str] = None
        self._ssh_discovered_ip: Optional[str] = None

        self._build_ui()
        self._register_keybindings()

    # --- HTTP helpers --------------------------------------------------
    def _remote_headers(self) -> Dict[str, str]:
        token = self.api_key.get().strip()
        headers: Dict[str, str] = {}
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
            if self._is_ipv4(host) and self._ssh_discovered_ip != host:
                self._ssh_discovered_ip = host
                self.after(0, lambda h=host: self.ssh_host.set(h))
            if base != self.api_base.get().strip():
                self.after(0, lambda b=base: self.api_base.set(b))
            return response

        if last_exc:
            raise last_exc
        raise requests.RequestException("Remote request failed")

    def _post_async(self, path: str, payload: Optional[Dict[str, object]], description: Optional[str]) -> None:
        def worker() -> None:
            try:
                response = self._remote_request("POST", path, json=payload, timeout=5)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                body = exc.response.json() if exc.response is not None else {}
                self._log(f"⚠️ Request failed ({status}): {body or exc}")
            except requests.RequestException as exc:  # noqa: BLE001
                self._log(f"⚠️ Request error: {exc}")
            else:
                if description:
                    try:
                        payload_desc = response.json()
                    except Exception:  # noqa: BLE001
                        payload_desc = response.text
                    self._log(f"✅ {description} -> {payload_desc}")

        threading.Thread(target=worker, daemon=True).start()

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
        ttk.Button(ssh_frame, text="Detect Base", command=self._discover_remote_base).grid(row=0, column=5, rowspan=2, padx=6, pady=4)

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
    def _candidate_ssh_hosts(self) -> List[str]:
        candidates: List[str] = []
        manual_entry = self.ssh_host.get().strip()
        if manual_entry:
            candidates.append(manual_entry)

        if self._ssh_discovered_ip:
            candidates.append(self._ssh_discovered_ip)

        api_host, _ = self._split_host_port(self.api_base.get().strip())
        if api_host:
            candidates.append(api_host)

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

    def _check_status(self) -> None:

        def worker() -> None:
            try:
                response = self._remote_request("GET", "/api/manual/status", timeout=4)
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
                    "source .venv311/bin/activate && "
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
                remote_cmd = "bash -lc 'pkill -f \"flask_api/app.py\" || pkill -f \"python app.py\"'"
                stdin, stdout, stderr = client.exec_command(remote_cmd)
                stdout.channel.recv_exit_status()
                client.close()
                self._log("✅ Flask API stop signal sent")
            except Exception as exc:  # noqa: BLE001
                self._log(f"⚠️ SSH error: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    # --- Logging --------------------------------------------------------
    def _discover_remote_base(self) -> None:
        user = self.ssh_user.get().strip() or 'root1'
        password = self.ssh_password.get()
        candidates = self._candidate_ssh_hosts()
        if not candidates:
            self._log("⚠️ SSH host is required to detect the API base.")
            return

        def worker() -> None:
            last_error: Optional[Exception] = None
            for host in candidates:
                self._log(f"Detecting API endpoint via {user}@{host}...")
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
                if ipv4:
                    self._ssh_discovered_ip = ipv4
                    self.after(0, lambda h=ipv4: self.ssh_host.set(h))
                else:
                    self.after(0, lambda h=host: self.ssh_host.set(h))

                base = self._format_base_url(address)
                self._last_remote_base = base.rstrip('/')
                if self._is_ipv4(address):
                    self._log(f"✅ Detected IPv4 {address}; updated SSH host and API base.")
                else:
                    self._log(f"✅ Detected address {address}; updated API base.")
                self.after(0, lambda: self.api_base.set(base))
                return

            message = f"SSH detection failed: {last_error}" if last_error else "SSH detection failed."
            self._log(f"⚠️ {message}")

        threading.Thread(target=worker, daemon=True).start()

    # --- Logging --------------------------------------------------------
    def _log(self, message: str) -> None:
        self.after(0, lambda: self.status_text.set(message))

    def _candidate_ssh_hosts(self) -> List[str]:
        candidates: List[str] = []
        manual_entry = self.ssh_host.get().strip()
        if manual_entry:
            candidates.append(manual_entry)

        if self._ssh_discovered_ip:
            candidates.append(self._ssh_discovered_ip)

        api_host, _ = self._split_host_port(self.api_base.get().strip())
        if api_host:
            candidates.append(api_host)

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
        raw = self.api_base.get().strip()
        host, port = self._split_host_port(raw)

        entries: List[str] = []
        if raw:
            entries.append(raw)
        else:
            entries.append(f"http://{host}:{port}")

        if self._last_remote_base:
            entries.append(self._last_remote_base)

        if self._ssh_discovered_ip:
            entries.append(f"http://{self._ssh_discovered_ip}:{port}")

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

    def _normalized_base_url(self) -> str:
        candidates = self._candidate_base_urls()
        if not candidates:
            normalized = self._format_base_url(self.api_base.get().strip())
            if normalized:
                self.after(0, lambda: self.api_base.set(normalized))
            return normalized
        first = candidates[0]
        if first != self.api_base.get().strip():
            self.after(0, lambda b=first: self.api_base.set(b))
        return first

    @staticmethod
    def _format_base_url(value: str) -> str:
        host, port = ManualControlFrame._split_host_port(value)
        if not host:
            return ""
        if ':' in host and not host.startswith('['):
            host_display = f'[{host}]'
        else:
            host_display = host
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


def launch_manual_control() -> None:
    root = tk.Tk()
    frame = ManualControlFrame(root, set_window_chrome=True)
    frame.pack(fill="both", expand=True)
    root.mainloop()
