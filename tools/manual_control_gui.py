"""Standalone launcher for the manual control UI."""

import tkinter as tk

from manual_control_panel import ManualControlFrame


def main() -> None:
    root = tk.Tk()
    frame = ManualControlFrame(root, set_window_chrome=True)
    frame.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()