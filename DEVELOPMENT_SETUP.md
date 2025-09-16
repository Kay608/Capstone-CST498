# Development Setup Guide

## Quick Start (Development Mode)

Your project now supports **simulation mode** so you can develop and test without the physical Yahboom Raspbot!

### 1. Environment Setup

```bash
# Create virtual environment (if not already done)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install core dependencies
pip install -r requirements.txt

# Install Ultralytics for YOLO (if not already done)
pip install ultralytics

# --- AWS S3 Credentials (IMPORTANT!) ---
# Set these environment variables in your terminal BEFORE running the Flask API or robot scripts.
# For Heroku deployment, these will be set as Config Vars.
# REPLACE [YOUR_...] with your actual AWS credentials and bucket name.
$env:AWS_ACCESS_KEY_ID="[YOUR_AWS_ACCESS_KEY_ID]" # Windows PowerShell
$env:AWS_SECRET_ACCESS_KEY="[YOUR_AWS_SECRET_ACCESS_KEY]" # Windows PowerShell
$env:AWS_REGION="[YOUR_AWS_REGION]" # e.g., us-east-1
$env:S3_BUCKET_NAME="[YOUR_S3_BUCKET_NAME]" # e.g., capstone-cst498-faces

# For Linux/Mac (Bash/Zsh), use `export` instead:
# export AWS_ACCESS_KEY_ID="[YOUR_AWS_ACCESS_KEY_ID]"
# export AWS_SECRET_ACCESS_KEY="[YOUR_AWS_SECRET_ACCESS_KEY]"
# export AWS_REGION="[YOUR_AWS_REGION]"
# export S3_BUCKET_NAME="[YOUR_S3_BUCKET_NAME]"

```

### 2. Run the System Components (Local Simulation)

#### A. Start Flask API (Background Process)

```bash
# In a separate terminal tab/window (or run in background)
.venv\Scripts\python.exe flask_api/app.py
```

#### B. Run Robot Controller (Simulated Navigation & Detection)

```bash
# This demonstrates the robot's logic in simulation
.venv\Scripts\python.exe -m robot_navigation.robot_controller
```

#### C. Serve HTML Frontend (Local Web Server)

```bash
# You'll need a simple local web server to serve your HTML/CSS/JS files.
# If you have Python, you can use SimpleHTTPServer:
python -m http.server 8000
# Then open your browser to http://localhost:8000/index.html
```

### 3. Verify Local Integration

*   Ensure Flask API is running in the background.
*   Start a simple Python web server in your project root.
*   Open `http://localhost:8000/index.html` (or your chosen port) in your browser.
*   Use the HTML app to interact with the Flask API (face registration, robot control/status).

## Development Workflow

### Current Status ✅ (as of September 4, 2025)
-   **Fixed**: Import issues in `localization.py` and `robot_controller.py`.
-   **Added**: Hardware abstraction layer for development without the physical robot.
-   **Working**: Simulated robot with realistic physics for navigation.
-   **Working**: Basic YOLO object detection integrated into robot control (logging actions for `person`).
-   **Working**: Face registration and recognition API.
-   **Removed**: Streamlit web app and Flutter mobile app.
-   **Prepared**: For HTML/CSS/JavaScript frontend development.
-   **Created**: `Research` folder for all project documentation (`YOLO_RESEARCH.md`, `STREAMLIT_RESEARCH.md`, `CLOUD_HOSTING_RESEARCH.md`, `SIGN_LIST.md`).

### Simulation vs Real Hardware

The system automatically uses simulation mode by default. To switch to real hardware (when the robot is available):

```python
# In flask_api/app.py, change:
controller = RobotController(use_simulation=False)

# Or when creating robot controller directly:
controller = RobotController(use_simulation=False)
```

## Testing Checklist

### Core System (Simulated)
- [x] Streamlit app communicates with Flask API.
- [x] Face registration via Streamlit works and updates `encodings.pkl`.
- [x] Robot controller runs simulated navigation (`python -m robot_navigation.robot_controller`).
- [x] YOLO detection works on `uploads/Test_Person.jpg` in simulation.
- [x] Robot controller logs actions based on YOLO detections (e.g., `[ROBOT ACTION] Detected PERSON. Robot would slow down and yield.`).

### Navigation System (Simulated)
- [x] Robot can move forward/backward in simulation.
- [x] Robot can turn left/right accurately.
- [x] Pathfinding computes simple paths.
- [x] Navigation follows computed paths.
- [x] Localization tracks position via odometry.

### Face Recognition
- [ ] Real-time recognition works via camera (needs robot).
- [x] API endpoints respond correctly for face registration.

## Next Development Steps (Prioritized)

### Immediate Priorities (Starting September 5, 2025)
1.  **Cloud Hosting for Flask API & Image Storage** ☁️
    *   Choose a cloud object storage (e.g., AWS S3) for `encodings.pkl` and uploaded images.
    *   Modify `flask_api/app.py` to upload images to S3 and manage `encodings.pkl` on S3.
    *   Prepare Flask API for Heroku deployment (create `Procfile`, `runtime.txt`, update `requirements.txt`).
    *   Deploy Flask API to Heroku.

2.  **HTML Frontend Development** 💻
    *   Create `index.html`, `style.css`, and `script.js` files.
    *   Implement user registration form (face upload) with JavaScript `fetch()` calls to Flask API.
    *   Implement robot control (goal setting) with JavaScript `fetch()` calls.
    *   Implement robot status display with periodic JavaScript `fetch()` calls.
    *   Update `FLASK_API_BASE_URL` in `script.js` to point to your cloud-hosted Flask API.

3.  **Hardware & Connectivity (Starting September 9, 2025 - after robot handover)** 🤖
    *   Flash Yahboom factory image on Raspberry Pi 5.
    *   **Crucial:** Investigate Yahboom's existing APIs (Python libraries, HTTP endpoints, etc.) for:
        *   High-level motor control (if exposed, e.g., move forward/backward a certain distance/time).
        *   Camera access for facial recognition and YOLO.
        *   Food compartment release mechanism.
    *   Adapt `hardware_interface.py` to call these Yahboom APIs instead of raw motor commands.
    *   Ensure the Raspberry Pi can access the cloud-hosted Flask API.

### Mid-Term Priorities
4.  **YOLO Sign Detection Refinement** 👁️
    *   Collect and annotate custom dataset of campus signs (Person.B's task, guided by `Research/SIGN_LIST.md`).
    *   Train custom YOLO model on campus signs.
    *   Integrate custom YOLO model with robot's camera feed (using `_get_camera_frame` which will now use the real Yahboom camera).
    *   Implement advanced sign-based navigation rules in `robot_controller.py` (logging actions initially, then interfacing with Yahboom's high-level movement).

5.  **Autonomous Movement (Stretch Goal)** 🚀
    *   Implement A* pathfinding algorithm (beyond simple point-to-point).
    *   Add obstacle avoidance using sensor data.
    *   GPS integration for outdoor navigation (if applicable with Yahboom hardware).

### Final Polish & Demo Prep
6.  **System Integration & Campus Testing** 🔧
    *   End-to-end testing of the complete system on campus.
    *   Performance optimization.
    *   Robust error handling and recovery mechanisms.

7.  **Video Presentation & Live Demo Prep** 🎬
    *   Create compelling demo scenarios.
    *   Record video presentation (Person.B's task).
    *   Finalize documentation.

## Troubleshooting

### Common Issues

1.  **`ModuleNotFoundError: No module named 'ultralytics'` or similar**
    *   Ensure your virtual environment is activated: `.venv\Scripts\activate`.
    *   Reinstall dependencies: `pip install -r requirements.txt` and `pip install ultralytics` separately if needed.
    *   Run Python scripts as modules from the project root (e.g., `python -m robot_navigation.robot_controller`).

2.  **Flask API / Frontend Connection Errors**
    *   Verify Flask API is running (locally: `python flask_api/app.py`; remotely: check Heroku logs).
    *   Check firewall settings if connecting from another device/robot.
    *   Ensure `FLASK_API_BASE_URL` in your HTML/JS frontend is correct (e.g., `http://localhost:5001` for local, or your cloud URL).

3.  **Cloud Storage Access Issues (e.g., S3)**
    *   Verify AWS credentials (access key, secret key, region) are correctly configured in Flask API.
    *   Check S3 bucket policy and CORS settings.
    *   Ensure correct bucket name and file paths.

### Hardware-Specific Issues (When Available)

1.  **Yahboom API / Driver Not Found or Not Responding**
    *   Ensure the Yahboom factory image is correctly flashed.
    *   Refer to specific Yahboom documentation for Raspberry Pi 5 APIs.
    *   Check if Python libraries are provided by Yahboom and installed on the Pi.
    *   Verify network connectivity between Pi and cloud-hosted Flask API.

2.  **Motor Control Not Working (via Yahboom API)**
    *   Check power supply to motors.
    *   Verify wiring connections (if you need to do any).
    *   Test individual high-level commands through Yahboom's provided interface.

## Team Collaboration

### Git Workflow
```bash
# Always pull before starting work
git pull origin main

# Create feature branches for new tasks
git checkout -b feature/html-frontend-and-s3
git add .
git commit -m "Implement HTML frontend and S3 cloud storage"
git push origin feature/html-frontend-and-s3

# Create pull request for review and merge
```

### Task Division (Current - as of September 4, 2025)
-   **You (Backend/Integration)**: Flask API, Robot Navigation (Localization, Pathfinding - adapting to Yahboom APIs), Hardware Integration (interfacing with Yahboom APIs), YOLO Implementation, HTML Web App (initial setup & backend integration), Cloud Hosting (Heroku, S3).
-   **Person.K (UI/UX)**: HTML Web App UI/UX enhancements and design (working on `index.html`, `style.css`, `script.js`).
-   **Person.B (Presentation/Data)**: YOLO Dataset Collection (campus signs, guided by `Research/SIGN_LIST.md`), Final Video Presentation, Documentation.

### Regular Meetings
-   **Weekly progress reviews** (Mondays) - *Crucial for alignment, especially with the professor's feedback.*
-   **Integration testing sessions** (Fridays) - *Essential once hardware is available.*
-   **Hardware access coordination** (as needed) - *Schedule time with the robot owner.*

## Resources

*   **Project Research (in `Research/` folder)**:
    *   `Research/YOLO_RESEARCH.md`
    *   `Research/STREAMLIT_RESEARCH.md` (for historical context of prior plan)
    *   `Research/CLOUD_HOSTING_RESEARCH.md`
    *   `Research/SIGN_LIST.md`
*   **Yahboom Raspbot Documentation**: [yahboom.net](https://www.yahboom.net)
*   **Ultralytics YOLO**: [docs.ultralytics.com](https://docs.ultralytics.com)
*   **OpenCV Python**: [opencv-python-tutroals.readthedocs.io](https://opencv-python-tutroals.readthedocs.io)
*   **Heroku Dev Center**: [https://devcenter.heroku.com/](https://devcenter.heroku.com/)
*   **Render Documentation**: [https://render.com/docs](https://render.com/docs)
*   **AWS S3 Documentation**: [https://docs.aws.amazon.com/s3/index.html](https://docs.aws.amazon.com/s3/index.html)
*   **MDN Web Docs (HTML, CSS, JavaScript)**: [https://developer.mozilla.org/en-US/docs/Web](https://developer.mozilla.org/en-US/docs/Web)

---

**Last Updated**: September 4, 2025
**Project Due**: December 2, 2025
**Status**: Ready for Cloud Hosting & HTML Frontend Development 🚀
