"""Panel that surface job execution details."""

from __future__ import annotations

from typing import Optional

from tkinter import ttk

from ..jobs import JobStatus
from ..state.app_state import AppState
from .base_panel import BasePanel


_STATUS_LABELS = {
    JobStatus.PENDING: "Pending",
    JobStatus.RUNNING: "Running",
    JobStatus.COMPLETED: "Completed",
    JobStatus.FAILED: "Failed",
    JobStatus.CANCELLED: "Cancelled",
}


class JobsPanel(BasePanel):
    REFRESH_INTERVAL_MS = 1000

    def __init__(self, parent, state: AppState, **kwargs):
        self._refresh_token: Optional[str] = None
        super().__init__(parent, state, **kwargs)

    def destroy(self) -> None:
        if self._refresh_token is not None:
            self.after_cancel(self._refresh_token)
            self._refresh_token = None
        super().destroy()

    def _build_widgets(self) -> None:
        self.tree = ttk.Treeview(self, columns=("status", "message"), show="headings")
        self.tree.heading("status", text="Status")
        self.tree.heading("message", text="Message")
        self.tree.column("status", width=120, anchor="w")
        self.tree.column("message", width=600, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.refresh()
        self._schedule_refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for job in self.state.jobs.list_jobs():
            self.tree.insert(
                "",
                "end",
                iid=job.job_id,
                values=(
                    _STATUS_LABELS.get(job.status, "Unknown"),
                    job.message,
                ),
            )

    def _schedule_refresh(self) -> None:
        self.refresh()
        self._refresh_token = self.after(self.REFRESH_INTERVAL_MS, self._schedule_refresh)
