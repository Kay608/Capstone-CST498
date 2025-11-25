"""Standalone launcher for the simulation harness UI."""

import tkinter as tk

from sim_harness_panel import HarnessFrame


def main() -> None:
    root = tk.Tk()
    frame = HarnessFrame(root, set_window_chrome=True)
    frame.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
