"""Tkinter application entry point for the new master control experience."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..logging import configure_logging, get_logger
from ..scheduler import JobScheduler
from ..state.app_state import AppState
from .camera_panel import CameraPanel
from .control_panel import ControlPanel
from .jobs_panel import JobsPanel

_LOGGER = get_logger(__name__)


class MasterControlApp(tk.Tk):
    def __init__(self, state: AppState | None = None) -> None:
        configure_logging()
        super().__init__()
        self.state = state or AppState()
        self.scheduler = JobScheduler(self.state.jobs)

        self.title("Master Control (Preview)")
        self.geometry("1024x720")
        self.minsize(960, 640)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        camera_tab = CameraPanel(notebook, self.state)
        notebook.add(camera_tab, text="Camera")

        control_tab = ControlPanel(notebook, self.state, self.scheduler)
        notebook.add(control_tab, text="System")

        jobs_tab = JobsPanel(notebook, self.state)
        notebook.add(jobs_tab, text="Jobs")

    def run(self) -> None:
        _LOGGER.info("Starting Master Control UI")
        self.mainloop()

    def _on_close(self) -> None:
        _LOGGER.info("Shutting down UI")
        self.scheduler.shutdown()
        self.state.close()
        self.destroy()
