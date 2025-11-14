import tkinter as tk
from tkinter import ttk
import threading
from typing import Optional, Dict
import requests


class ManualController(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rover RC Control")
        self.geometry("420x360")

        self.api_base = tk.StringVar(value="http://raspberrypi.local:5001")
        self.api_key = tk.StringVar(value="")
        self.speed = tk.DoubleVar(value=0.4)
        self.duration = tk.DoubleVar(value=0.5)
        self.angle = tk.DoubleVar(value=90.0)
        self.status_text = tk.StringVar(value="Idle")

        self._build_ui()
        self._register_keybindings()

    # --- UI construction -------------------------------------------------
    def _build_ui(self):
        config = ttk.LabelFrame(self, text="Robot Endpoint")
        config.pack(fill="x", padx=10, pady=8)

        ttk.Label(config, text="Base URL:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(config, textvariable=self.api_base, width=36).grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(config, text="API Key:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(config, textvariable=self.api_key, width=36, show="*").grid(row=1, column=1, padx=6, pady=4)

        ttk.Button(config, text="Check Status", command=self._check_status).grid(row=0, column=2, rowspan=2, padx=6, pady=4)

        sliders = ttk.LabelFrame(self, text="Command Settings")
        sliders.pack(fill="x", padx=10, pady=8)

        ttk.Scale(sliders, from_=0.1, to=1.0, orient="horizontal", variable=self.speed).grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(sliders, text="Speed (0-1)").grid(row=0, column=0, sticky="w", padx=8)

        ttk.Scale(sliders, from_=0.1, to=5.0, orient="horizontal", variable=self.duration).grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(sliders, text="Duration (s)").grid(row=1, column=0, sticky="w", padx=8)

        ttk.Scale(sliders, from_=10, to=180, orient="horizontal", variable=self.angle).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(sliders, text="Turn Angle (°)").grid(row=2, column=0, sticky="w", padx=8)

        sliders.columnconfigure(1, weight=1)

        buttons = ttk.LabelFrame(self, text="Controls")
        buttons.pack(padx=10, pady=8)

        ttk.Button(buttons, text="Forward", command=lambda: self._send_move("forward")).grid(row=0, column=1, padx=10, pady=6)
        ttk.Button(buttons, text="Back", command=lambda: self._send_move("back")).grid(row=2, column=1, padx=10, pady=6)
        ttk.Button(buttons, text="Left", command=lambda: self._send_move("left")).grid(row=1, column=0, padx=10, pady=6)
        ttk.Button(buttons, text="Right", command=lambda: self._send_move("right")).grid(row=1, column=2, padx=10, pady=6)
        ttk.Button(buttons, text="Stop", command=self._send_stop).grid(row=1, column=1, padx=10, pady=6)

        info = ttk.LabelFrame(self, text="Status")
        info.pack(fill="both", expand=True, padx=10, pady=8)
        ttk.Label(info, textvariable=self.status_text, anchor="w").pack(fill="both", expand=True, padx=8, pady=6)

    def _register_keybindings(self):
        self.bind("<Up>", lambda _: self._send_move("forward"))
        self.bind("<Down>", lambda _: self._send_move("back"))
        self.bind("<Left>", lambda _: self._send_move("left"))
        self.bind("<Right>", lambda _: self._send_move("right"))
        self.bind("<space>", lambda _: self._send_stop())

    # --- Networking helpers ---------------------------------------------
    def _headers(self):
        headers = {"Content-Type": "application/json"}
        token = self.api_key.get().strip()
        if token:
            headers["X-Api-Key"] = token
        return headers

    def _post_async(self, path: str, payload: Optional[Dict], success_msg: str):
        def worker():
            url = self.api_base.get().rstrip('/') + path
            try:
                response = requests.post(url, json=payload, headers=self._headers(), timeout=4)
                response.raise_for_status()
                body = response.json()
                self._log(f"✅ {success_msg}: {body}")
            except requests.RequestException as exc:
                self._log(f"⚠️ Request failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _check_status(self):
        def worker():
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
    def _send_move(self, direction: str):
        payload = {
            'direction': direction,
            'speed': self.speed.get(),
            'duration': self.duration.get(),
            'angle': self.angle.get(),
        }
        self._log(f"Sending {direction} command...")
        self._post_async('/api/manual/move', payload, f"Move {direction}")

    def _send_stop(self):
        self._log("Sending stop command...")
        self._post_async('/api/manual/stop', None, "Stop")

    # --- Logging --------------------------------------------------------
    def _log(self, message: str):
        self.after(0, lambda: self.status_text.set(message))


if __name__ == "__main__":
    app = ManualController()
    app.mainloop()