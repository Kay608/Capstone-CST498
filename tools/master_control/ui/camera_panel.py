"""Panel responsible for displaying the live camera stream."""

from __future__ import annotations

import queue
import threading
from typing import Any

import cv2
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk

from ..state.app_state import AppState
from .base_panel import BasePanel


class CameraPanel(BasePanel):
    def __init__(self, parent, state: AppState, **kwargs):
        self._frame_queue: queue.Queue[Any] = queue.Queue(maxsize=2)
        self._event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._stream_thread: threading.Thread | None = None
        self._stream_stop: threading.Event | None = None
        self._current_photo: ImageTk.PhotoImage | None = None
        self._status_var = tk.StringVar(value="Stream idle.")
        super().__init__(parent, state, **kwargs)

    def _build_widgets(self) -> None:
        header = ttk.Label(self, text="Camera Preview", font=("Segoe UI", 12, "bold"))
        header.pack(anchor="w", padx=12, pady=(12, 6))

        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=12, pady=(0, 6))

        self._stream_button = ttk.Button(controls, text="Start Stream", command=self._toggle_stream)
        self._stream_button.pack(side="left")

        self._status_label = ttk.Label(controls, textvariable=self._status_var)
        self._status_label.pack(side="left", padx=(12, 0))

        video_container = ttk.Frame(self)
        video_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._image_label = tk.Label(video_container, background="#1f1f1f", foreground="white")
        self._image_label.pack(fill="both", expand=True)
        self._image_label.configure(text="Camera stream inactive", font=("Segoe UI", 10))

        self.after(80, self._poll_updates)

    def _toggle_stream(self) -> None:
        if self._is_streaming():
            self._stop_stream()
        else:
            self._start_stream()

    def _start_stream(self) -> None:
        if self._is_streaming():
            return
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break
        stop_event = threading.Event()
        self._stream_stop = stop_event
        thread = threading.Thread(target=self._run_stream, args=(stop_event,), daemon=True)
        self._stream_thread = thread
        self._status_var.set("Connecting to camera...")
        self._stream_button.configure(text="Stop Stream", state="normal")
        thread.start()

    def _stop_stream(self) -> None:
        if not self._is_streaming():
            self._event_queue.put(("stopped", False))
            return
        self._status_var.set("Stopping stream...")
        self._stream_button.configure(text="Stopping...", state="disabled")
        stop_event = self._stream_stop
        if stop_event:
            stop_event.set()

    def _is_streaming(self) -> bool:
        thread = self._stream_thread
        return bool(thread and thread.is_alive())

    def _run_stream(self, stop_event: threading.Event) -> None:
        url = self.state.camera_stream_url()
        try:
            capture = cv2.VideoCapture(url)
            if not capture.isOpened():
                self._event_queue.put(("status", "Unable to open camera stream."))
                self._event_queue.put(("stopped", False))
                return
            self._event_queue.put(("status", "Live stream active."))
            idle_notified = False
            while not stop_event.is_set():
                ready, frame = capture.read()
                if not ready or frame is None:
                    if not idle_notified:
                        self._event_queue.put(("status", "Waiting for camera frames..."))
                        idle_notified = True
                    if stop_event.wait(0.5):
                        break
                    continue
                if idle_notified:
                    self._event_queue.put(("status", "Live stream active."))
                    idle_notified = False
                try:
                    self._frame_queue.put(frame, timeout=0.1)
                except queue.Full:
                    continue
            capture.release()
        except Exception as exc:  # noqa: BLE001
            self._event_queue.put(("status", f"Camera stream error: {exc}"))
        finally:
            self._event_queue.put(("stopped", True))

    def _poll_updates(self) -> None:
        if not self.winfo_exists():
            return

        updated = False
        while True:
            try:
                event, payload = self._event_queue.get_nowait()
            except queue.Empty:
                break
            if event == "status":
                self._status_var.set(str(payload))
            elif event == "stopped":
                self._finalize_stream()
        try:
            frame = self._frame_queue.get_nowait()
        except queue.Empty:
            frame = None
        if frame is not None:
            self._display_frame(frame)
            updated = True
        if not updated and not self._is_streaming():
            self._image_label.configure(text="Camera stream inactive", image="")
            self._current_photo = None
        self.after(80, self._poll_updates)

    def _display_frame(self, frame: Any) -> None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        available_width = max(self._image_label.winfo_width(), 1)
        available_height = max(self._image_label.winfo_height(), 1)
        if available_width > 1 and available_height > 1:
            ratio = min(available_width / image.width, available_height / image.height)
            if ratio < 1.0:
                new_size = (max(int(image.width * ratio), 1), max(int(image.height * ratio), 1))
                image = image.resize(new_size, Image.LANCZOS)
        photo = ImageTk.PhotoImage(image=image)
        self._image_label.configure(image=photo, text="")
        self._current_photo = photo

    def _finalize_stream(self) -> None:
        if self._stream_button:
            self._stream_button.configure(text="Start Stream", state="normal")
        self._status_var.set("Stream idle.")
        self._stream_thread = None
        self._stream_stop = None

    def destroy(self) -> None:
        if self._stream_stop:
            self._stream_stop.set()
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=1.5)
        super().destroy()
