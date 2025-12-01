"""Legacy Master Control launcher combining RC control and the simulation harness."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from manual_control_panel import ManualControlFrame
from sim_harness_panel import HarnessFrame


class LegacyMasterControlApp(tk.Tk):
    """Legacy master control application with shared connection settings."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Capstone Master Control (Legacy)")
        self.geometry("900x720")

        self.shared_api_base = tk.StringVar(self, value="http://raspberrypi.local:5001")
        self.shared_api_key = tk.StringVar(self, value="")
        self.shared_ssh_host = tk.StringVar(self, value="raspberrypi.local")
        self.shared_ssh_user = tk.StringVar(self, value="root1")
        self.shared_ssh_password = tk.StringVar(self, value="")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        rc_tab = ttk.Frame(notebook)
        ManualControlFrame(
            rc_tab,
            api_base_var=self.shared_api_base,
            api_key_var=self.shared_api_key,
            ssh_host_var=self.shared_ssh_host,
            ssh_user_var=self.shared_ssh_user,
            ssh_password_var=self.shared_ssh_password,
        ).pack(fill="both", expand=True)
        notebook.add(rc_tab, text="RC Control")

        harness_tab = ttk.Frame(notebook)
        HarnessFrame(
            harness_tab,
            remote_base_var=self.shared_api_base,
            remote_api_key_var=self.shared_api_key,
            remote_host_var=self.shared_ssh_host,
            remote_user_var=self.shared_ssh_user,
            remote_password_var=self.shared_ssh_password,
        ).pack(fill="both", expand=True)
        notebook.add(harness_tab, text="Harness")


def launch_legacy() -> None:
    app = LegacyMasterControlApp()
    app.mainloop()


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Capstone Master Control (legacy) launcher")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="(Deprecated) Legacy flag retained for compatibility; ignored.",
    )
    parser.parse_args(argv)
    launch_legacy()


if __name__ == "__main__":
    main()
