"""Master Control application that unifies RC control, harness utilities, and VNC access."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from typing import Optional

try:
    import webview
except ImportError:  # pragma: no cover - optional dependency
    webview = None  # type: ignore[assignment]

from manual_control_panel import ManualControlFrame
from sim_harness_panel import HarnessFrame

DEFAULT_VNC_URL = "http://raspberrypi.local:6080"


class VncViewerFrame(ttk.Frame):
    """Simple front-end for launching a noVNC session via pywebview or browser."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.url = tk.StringVar(self, value=DEFAULT_VNC_URL)
        self._webview_thread: Optional[threading.Thread] = None

        description = ttk.Label(
            self,
            text=(
                "View and control the Raspberry Pi desktop directly. "
                "Provide the noVNC URL (usually http://<host>:6080)."
            ),
            wraplength=420,
            justify="left",
        )
        description.grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 8))

        ttk.Label(self, text="noVNC URL").grid(row=1, column=0, sticky="e", padx=(12, 6), pady=6)
        entry = ttk.Entry(self, textvariable=self.url, width=40)
        entry.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=6)
        entry.focus_set()

        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 12))

        ttk.Button(button_frame, text="Open in Browser", command=self._open_in_browser).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(button_frame, text="Launch Embedded Viewer", command=self._launch_embedded_viewer).grid(row=0, column=1)

        self.columnconfigure(1, weight=1)

        self.status = tk.StringVar(self, value="Ready.")
        ttk.Label(self, textvariable=self.status, wraplength=420).grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 12))

    def _open_in_browser(self) -> None:
        import webbrowser

        url = self.url.get().strip()
        if not url:
            messagebox.showerror("VNC Viewer", "Please provide a noVNC URL.")
            return
        webbrowser.open_new(url)
        self.status.set(f"Opened {url} in default browser.")

    def _launch_embedded_viewer(self) -> None:
        if webview is None:
            messagebox.showerror(
                "VNC Viewer",
                "pywebview is not installed in this environment. Install it with 'pip install pywebview[gtk]' (Pi) or '\n'pip install pywebview[qt]' (desktop).",
            )
            return

        url = self.url.get().strip()
        if not url:
            messagebox.showerror("VNC Viewer", "Please provide a noVNC URL.")
            return

        def _runner() -> None:
            try:
                if webview.windows:
                    webview.windows[0].load_url(url)
                else:
                    webview.create_window("Raspberry Pi Desktop", url)
                    webview.start()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("VNC Viewer", f"Failed to launch embedded viewer: {exc}")
                return

        if self._webview_thread and self._webview_thread.is_alive():
            self.status.set("Updating existing viewer window...")
            _runner()
            return

        self.status.set("Launching embedded viewer...")
        self._webview_thread = threading.Thread(target=_runner, daemon=True)
        self._webview_thread.start()


class MasterControlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Capstone Master Control")
        self.geometry("900x720")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        rc_tab = ttk.Frame(notebook)
        ManualControlFrame(rc_tab).pack(fill="both", expand=True)
        notebook.add(rc_tab, text="RC Control")

        sim_tab = ttk.Frame(notebook)
        HarnessFrame(sim_tab).pack(fill="both", expand=True)
        notebook.add(sim_tab, text="Harness")

        vnc_tab = ttk.Frame(notebook)
        VncViewerFrame(vnc_tab).pack(fill="both", expand=True)
        notebook.add(vnc_tab, text="VNC")


def main() -> None:
    app = MasterControlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
