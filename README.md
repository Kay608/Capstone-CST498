# Capstone-CST498
# AI-Powered Facial Recognition Food Delivery Bot

Senior capstone project for CST 498 at NC A&T State University. The goal is a contactless delivery experience powered by facial recognition, autonomous navigation, and a web-based enrollment flow.

## Current Architecture

- **Flask API (`flask_api/app.py`)**: Central backend that exposes enrollment (`/enroll`, `/register_face`), navigation, and status endpoints. Face encodings are persisted in a MySQL table (`users`) hosted on JawsDB. When run locally, it defaults to simulated robot hardware.
- **Robot stack (`robot_navigation/*`, `ai_facial_recognition.py`)**: Runs on the Yahboom Raspbot (Raspberry Pi). Uses OpenCV/face_recognition to match users, integrates with navigation/pathfinding modules, and now bundles Mary's MobileNetV2 traffic-sign classifier (`robot_navigation/sign_recognition`).
- **Enrollment UI (`/flask_api/templates/enroll.html`)**: Simple HTML form rendered by Flask so teammates can upload images without CLI tooling.

## Key Files (top-level)

- `flask_api/app.py` – Unified REST API and enrollment UI.
- `flask_api/templates/enroll.html` – Browser enrollment form.
- `ai_facial_recognition.py` – Loads encodings from MySQL for live recognition on the robot.
- `robot_navigation/` – Localization, pathfinding, and hardware abstractions.
- `robot_navigation/sign_recognition/` – MobileNetV2 wrapper for traffic-sign inference (place `mobilenetv2.h5` under `model/`).
- `requirements.txt` – Python dependencies (includes `gunicorn` for Heroku and `waitress` for Windows parity testing).
- `Procfile` – Heroku entry point (`gunicorn flask_api.app:app --bind 0.0.0.0:$PORT`).
- `DEVELOPMENT_SETUP.md` – Environment setup checklist.

## Running Locally

1. Activate the virtual environment described in `DEVELOPMENT_SETUP.md`.
2. Copy `.env.template` (if provided) or request the `.env` values. At minimum you need:
    ```
    DB_HOST=...
    DB_USER=...
    DB_PASSWORD=...
    DB_NAME=...
    FLASK_DEBUG=0
    ```
3. Start the Flask API in debug mode for development:
    ```powershell
    # Windows PowerShell
    .venv\Scripts\python.exe flask_api\app.py
    ```
4. For a production-like run on Windows (no debug warning), use Waitress:
    ```powershell
    python -m waitress --listen=0.0.0.0:5001 flask_api.app:app
    ```
    The Raspberry Pi/Heroku deployment will use Gunicorn automatically via the `Procfile`.

### Traffic Sign Model Setup

1. Obtain Mary's trained MobileNetV2 weights (`mobilenetv2.h5`).
2. Place the file in `robot_navigation/sign_recognition/model/` or define `SIGN_MODEL_PATH` pointing to the file.
3. Install the TensorFlow dependency (already listed in `requirements.txt`). On the Raspberry Pi you may prefer a TensorFlow Lite build—adjust instructions once hardware testing finishes.
4. When `robot_navigation.robot_controller` runs, it will print detections such as STOP, SPEED LIMIT, NO ENTRY, or CROSSWALK and describe the planned robot action.
5. Quick smoke test without the robot:
    ```powershell
    python -m robot_navigation.sign_recognition.run_classifier --image path\to\sample.jpg --show
    ```
    Use one of Mary's annotated images; the script prints the prediction and optionally displays the frame.

### Simulation Command Library

- Launch the Tkinter harness for common dev flows:
    ```powershell
    python tools\sim_harness.py
    ```
- Capture an annotated facial-recognition snapshot (helpful for poster assets). Omit `--output` if you just want the preview window:
    ```powershell
    python ai_facial_recognition.py --snapshot --output poster_assets\face_demo.png
    ```

## Database Access (JawsDB / MySQL Workbench)

### GUI: MySQL Workbench

1. Open MySQL Workbench and create a **New Connection**.
2. Fill in the fields using the values from `.env` or Heroku config vars:
    - **Connection Name**: `Capstone JawsDB` (anything descriptive)
    - **Hostname**: `DB_HOST`
    - **Port**: `3306`
    - **Username**: `DB_USER`
    - **Password**: `DB_PASSWORD`
    - **Default Schema**: `DB_NAME`
3. Test the connection, then click **OK**.
4. Connect and run standard queries, for example:
    ```sql
    SELECT banner_id, first_name, last_name, email
    FROM users
    ORDER BY banner_id;
    ```

### CLI (optional)

If teammates prefer the command line:

```powershell
mysql.exe -h <DB_HOST> -P 3306 -u <DB_USER> -p
# Enter DB_PASSWORD when prompted
USE <DB_NAME>;
SELECT COUNT(*) FROM users;
```

Share these steps with the team so everyone can verify enrollments independently.

## Deployment Notes

- **Heroku**: Requires collaborator access to configure config vars and trigger deploys. Once connected to GitHub, deployments run `gunicorn` via `Procfile`.
- **Environment variables**: Set `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `FLASK_DEBUG=0` in Heroku config.
- **Waitress vs Gunicorn**: Keep both dependencies; Waitress is only for Windows development. The Raspberry Pi and Heroku runs should continue using Gunicorn.

## Next Steps for the Team

- Coordinate Heroku access with Kyla so the GitHub repository can be linked and auto-deployed.
- Break down ownership of remaining tasks (deployment, sign recognition integration, hardware research, data visualization dashboard).
- Once the visualization assignment details arrive, capture recognition confidence metrics in a dedicated table for analytics.

**Last Updated**: October 13, 2025
**Project Due**: December 2, 2025
