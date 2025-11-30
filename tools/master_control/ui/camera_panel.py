"""Panel responsible for displaying the live camera stream."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base_panel import BasePanel


class CameraPanel(BasePanel):
    def _build_widgets(self) -> None:
        header = ttk.Label(self, text="Camera Preview", font=("Segoe UI", 12, "bold"))
        header.pack(anchor="w", padx=12, pady=(12, 6))

        self.placeholder = tk.Canvas(self, background="#1f1f1f", height=240)
        self.placeholder.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.placeholder.create_text(
            120,
            120,
            text="Live stream placeholder",
            fill="white",
            font=("Segoe UI", 10),
        )
