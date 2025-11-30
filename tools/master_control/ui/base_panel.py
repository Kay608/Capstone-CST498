"""Base UI components shared by panels."""

from __future__ import annotations

from tkinter import ttk

from ..state.app_state import AppState


class BasePanel(ttk.Frame):
    def __init__(self, parent, state: AppState, **kwargs):
        super().__init__(parent, **kwargs)
        self.state = state
        self._build_widgets()

    def _build_widgets(self) -> None:
        raise NotImplementedError
