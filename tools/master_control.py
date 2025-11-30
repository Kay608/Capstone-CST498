"""Master Control application that unifies RC control, harness utilities, and VNC access."""

from __future__ import annotations

import tkinter as tk
from multiprocessing import Process
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
        self._webview_process: Optional[Process] = None

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

        if self._webview_process and self._webview_process.is_alive():
            self.status.set("Embedded viewer already running.")
            return

        self.status.set("Launching embedded viewer in separate window...")
        try:
            process = Process(target=VncViewerFrame._run_webview_process, args=(url,), daemon=True)
            process.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("VNC Viewer", f"Failed to launch embedded viewer: {exc}")
            self.status.set("Failed to launch embedded viewer.")
            return

        self._webview_process = process
        self.after(750, self._monitor_webview_process)
        self.status.set("Embedded viewer launched in a separate window.")

    def _monitor_webview_process(self) -> None:
        if not self._webview_process:
            return
        if self._webview_process.is_alive():
            self.after(2000, self._monitor_webview_process)
            return

        exit_code = self._webview_process.exitcode
        if exit_code == 0 or exit_code is None:
            self.status.set("Embedded viewer closed.")
        else:
            self.status.set(f"Embedded viewer exited (code {exit_code}).")
        self._webview_process = None

    @staticmethod
    def _run_webview_process(url: str) -> None:
        try:
            import webview  # type: ignore[import]

            if webview.windows:
                webview.windows[0].load_url(url)
            else:
                webview.create_window("Raspberry Pi Desktop", url)
            webview.start()
        except Exception:  # noqa: BLE001
            import traceback

            traceback.print_exc()
class LegacyMasterControlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Capstone Master Control (Legacy)")
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


def launch_legacy() -> None:
    app = LegacyMasterControlApp()
    app.mainloop()


def launch_preview() -> None:
    from tools.master_control import MasterControlApp

    app = MasterControlApp()
    app.run()


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Capstone Master Control launcher")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Launch the legacy interface with RC control and VNC tabs.",
    )
    args = parser.parse_args(argv)

    if args.legacy:
        launch_legacy()
    else:
        launch_preview()


if __name__ == "__main__":
    main()
