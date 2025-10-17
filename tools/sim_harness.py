"""Simulation test harness with Tkinter buttons for common workflows.

This utility is meant for local development only (simulation mode).
It wraps common CLI flows behind a simple GUI so team members can run
checks without remembering every command.

Features:
- Start Flask API (debug)
- Start Flask API via Waitress (production-like)
- Open enrollment page in browser
- Launch traffic sign classifier on an image
- Run DB query to list users
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import Tk, Button, filedialog, messagebox

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLASK_API_DIR = PROJECT_ROOT / "flask_api"
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(FLASK_API_DIR / ".env", override=False)


def run_command_async(command: list[str], title: str) -> None:
    def _worker() -> None:
        try:
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        except subprocess.CalledProcessError as exc:
            messagebox.showerror(title, f"Command failed: {exc}")
        except FileNotFoundError as exc:
            messagebox.showerror(title, f"Executable not found: {exc}")
    threading.Thread(target=_worker, daemon=True).start()


def start_flask_debug() -> None:
    command = [sys.executable, str(FLASK_API_DIR / "app.py")]
    run_command_async(command, "Flask Debug")


def start_flask_waitress() -> None:
    command = [sys.executable, "-m", "waitress", "--listen=0.0.0.0:5001", "flask_api.app:app"]
    run_command_async(command, "Waitress Server")


def open_enroll_page() -> None:
    webbrowser.open_new_tab("http://localhost:5001/enroll")


def run_sign_classifier() -> None:
    image_path = filedialog.askopenfilename(title="Select traffic sign image")
    if not image_path:
        return
    command = [
        sys.executable,
        "-m",
        "robot_navigation.sign_recognition.run_classifier",
        "--image",
        image_path,
        "--show",
    ]
    run_command_async(command, "Sign Classifier")


def show_users() -> None:
    host = os.environ.get("DB_HOST")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    database = os.environ.get("DB_NAME")

    if not all([host, user, password, database]):
        messagebox.showerror("Database", "Missing DB credentials. Ensure .env is populated.")
        return

    conn = None
    rows: list[dict[str, str]] = []

    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            cursorclass=DictCursor,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT banner_id, first_name, last_name, email FROM users ORDER BY banner_id;")
            rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror("Database", f"Failed to fetch users: {exc}")
        return
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if not rows:
        messagebox.showinfo("Database", "No users found in database.")
        return

    lines = [f"{row['banner_id']} - {row['first_name']} {row['last_name']} ({row['email']})" for row in rows]
    messagebox.showinfo("Registered Users", "\n".join(lines))


class HarnessApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Capstone Simulation Harness")
        self.root.geometry("340x280")

        Button(self.root, text="Start Flask (Debug)", width=30, command=start_flask_debug).pack(pady=8)
        Button(self.root, text="Start Flask via Waitress", width=30, command=start_flask_waitress).pack(pady=8)
        Button(self.root, text="Open Enrollment Page", width=30, command=open_enroll_page).pack(pady=8)
        Button(self.root, text="Run Sign Classifier", width=30, command=run_sign_classifier).pack(pady=8)
        Button(self.root, text="List Registered Users", width=30, command=show_users).pack(pady=8)


if __name__ == "__main__":
    app_root = Tk()
    HarnessApp(app_root)
    app_root.mainloop()
