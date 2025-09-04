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

# Install Streamlit and requests for the web app
pip install streamlit requests

# Install Ultralytics for YOLO (if not already done)
pip install ultralytics
```

### 2. Run the System Components (Local Simulation)

#### A. Start Flask API (Background Process)

```bash
# In a separate terminal tab/window (or run in background)
python flask_api/app.py
```

#### B. Run Robot Controller (Simulated Navigation & Detection)

```bash
# This demonstrates the robot's logic in simulation
python -m robot_navigation.robot_controller
```

#### C. Run Streamlit Web App (Frontend Control)

```bash
# In a separate terminal tab/window
streamlit run streamlit_app.py
```

### 3. Verify Local Integration

*   Open the Streamlit app in your browser (`http://localhost:8501`).
*   Use the "Face Registration" section to input a name and upload `uploads/Test_Person.jpg`.
*   Use the "Robot Navigation & Control" section to set a goal.
*   Click "Refresh Status Now" in the "Robot Status" section to see the robot's simulated state.

## Development Workflow

### Current Status ✅ (as of September 4, 2025)
-   **Fixed**: Import issues in `localization.py` and `robot_controller.py`.
-   **Added**: Hardware abstraction layer for development without the physical robot.
-   **Working**: Simulated robot with realistic physics for navigation.
-   **Working**: Basic YOLO object detection integrated into robot control (logging actions for `person`).
-   **Working**: Face registration and recognition API.
-   **Working**: Streamlit web app for user registration, robot control, and status monitoring.
-   **Created**: `Research` folder for all project documentation (`YOLO_RESEARCH.md`, `STREAMLIT_RESEARCH.md`, `CLOUD_HOSTING_RESEARCH.md`).

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
1.  **Cloud Hosting Implementation** ☁️
    *   Choose a cloud provider (Heroku or Render recommended).
    *   Prepare deployment files (`Procfile`, `runtime.txt`).
    *   Deploy Flask API and Streamlit app.
    *   Update `FLASK_API_BASE_URL` in `streamlit_app.py`.

2.  **Hardware Integration & Initial Testing (Starting September 9, 2025 - after robot handover)** 🤖
    *   Install Yahboom Raspbot V2 driver library on Raspberry Pi 5.
    *   Implement basic motor control (move, turn, stop) in `hardware_interface.py`.
    *   Test motor control with real hardware.
    *   Integrate encoder and IMU sensors for localization.

### Mid-Term Priorities
3.  **YOLO Sign Detection Refinement** 👁️
    *   Collect and annotate custom dataset of campus signs (Person.B's task).
    *   Train custom YOLO model on campus signs.
    *   Integrate custom YOLO model with robot's camera feed (using `_get_camera_frame`).
    *   Implement advanced sign-based navigation rules in `robot_controller.py`.

4.  **Enhanced Navigation** 🚀
    *   Implement A* pathfinding algorithm (beyond straight line).
    *   Add obstacle avoidance using sensor data.
    *   GPS integration for outdoor navigation (if applicable with Yahboom hardware).

### Final Polish & Demo Prep
5.  **System Integration & Campus Testing** 🔧
    *   End-to-end testing of the complete system on campus.
    *   Performance optimization.
    *   Robust error handling and recovery mechanisms.

6.  **Video Presentation & Live Demo Prep** 🎬
    *   Create compelling demo scenarios.
    *   Record video presentation (Person.B's task).
    *   Finalize documentation.

## Troubleshooting

### Common Issues

1.  **`ModuleNotFoundError: No module named 'ultralytics'` or similar**
    *   Ensure your virtual environment is activated: `.venv\Scripts\activate`.
    *   Reinstall dependencies: `pip install -r requirements.txt` (and `pip install streamlit requests ultralytics` separately if needed).
    *   Run Python scripts as modules from the project root (e.g., `python -m robot_navigation.robot_controller`).

2.  **Flask API / Streamlit App Connection Errors**
    *   Verify Flask API is running (`python flask_api/app.py`).
    *   Check firewall settings if connecting from another device.
    *   Ensure `FLASK_API_BASE_URL` in `streamlit_app.py` is correct (e.g., `http://localhost:5001` for local, or your cloud URL).

### Hardware-Specific Issues (When Available)

1.  **Yahboom Driver Not Found**
    *   Install driver library on Raspberry Pi (refer to Yahboom documentation).
    *   Check GPIO permissions.
    *   Verify I2C/SPI interfaces are enabled.

2.  **Motor Control Not Working**
    *   Check power supply to motors.
    *   Verify wiring connections.
    *   Test individual motor commands using the Yahboom driver.

## Team Collaboration

### Git Workflow
```bash
# Always pull before starting work
git pull origin main

# Create feature branches for new tasks
git checkout -b feature/cloud-hosting
git add .
git commit -m "Implement cloud hosting for API and Streamlit"
git push origin feature/cloud-hosting

# Create pull request for review and merge
```

### Task Division (Current - as of September 4, 2025)
-   **You (Backend/Integration)**: Flask API, Robot Navigation (Localization, Pathfinding), Hardware Integration, YOLO Implementation, Streamlit Web App, Cloud Hosting.
-   **Person.K (UI/UX)**: Streamlit Web App UI/UX enhancements and design.
-   **Person.B (Presentation/Data)**: YOLO Dataset Collection (campus signs), Final Video Presentation, Documentation.

### Regular Meetings
-   **Weekly progress reviews** (Mondays) - *Crucial for alignment, especially with the professor's feedback.* 
-   **Integration testing sessions** (Fridays) - *Essential once hardware is available.*
-   **Hardware access coordination** (as needed) - *Schedule time with the robot owner.*

## Resources

*   **Project Research (in `Research/` folder)**:
    *   `Research/YOLO_RESEARCH.md`
    *   `Research/STREAMLIT_RESEARCH.md`
    *   `Research/CLOUD_HOSTING_RESEARCH.md`
*   **Yahboom Raspbot Documentation**: [yahboom.net](https://www.yahboom.net)
*   **Ultralytics YOLO**: [docs.ultralytics.com](https://docs.ultralytics.com)
*   **OpenCV Python**: [opencv-python-tutroals.readthedocs.io](https://opencv-python-tutroals.readthedocs.io)
*   **Streamlit Official Documentation**: [https://docs.streamlit.io/](https://docs.streamlit.io/)
*   **Heroku Dev Center**: [https://devcenter.heroku.com/](https://devcenter.heroku.com/)
*   **Render Documentation**: [https://render.com/docs](https://render.com/docs)

---

**Last Updated**: September 4, 2025
**Project Due**: December 2, 2025
**Status**: Ready for Cloud Hosting & Hardware Integration 🚀
