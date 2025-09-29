# Capstone-CST498
# AI-Powered Facial Recognition Food Delivery Bot

This is a senior capstone project for CST 498 at NC A&T State University. It aims to create a secure, contactless food delivery experience using facial recognition technology and an autonomous Raspberry Pi-based robot.

## Project Overview

The delivery bot:
- Uses **facial recognition** to verify users before releasing their food.
- **Navigates** to the destination and obeys road signs via YOLO-based sign detection.
- Integrates with a **web app** where users can register their face and track the robot.

## Core Components

### 1. `ai_facial_recognition.py`
Runs on the Raspberry Pi. Captures real-time video, compares detected faces to saved encodings (from AWS S3), and triggers bot actions if a match is found.

### 2. Flask API (`/flask_api/app.py`)
This Python backend, designed for cloud hosting (e.g., Heroku), handles:
- **User Registration**: Receives face image uploads from the web app.
- **Facial Encoding Management**: Extracts face encodings and stores/retrieves them from AWS S3 (`encodings.pkl`).
- **Image Storage**: Uploads raw face images to AWS S3.
- **Robot Control Interface**: Provides endpoints for robot status and commands.

### 3. HTML/CSS/JavaScript Web App
The user-facing frontend, allowing:
- **Face Registration**: Users can upload images to enroll their faces.
- **Robot Monitoring**: Displays robot status and location.
- **Robot Control**: Sends commands to the robot via the Flask API.

## File Structure

/AI-Food-Delivery-Bot
├── ai_facial_recognition.py          # Robot-side script: recognition + actions, interacts with S3
├── encodings.pkl                     # **Managed on AWS S3** - Local file for initial reference
├── flask_api/                        # Flask API for enrollment, S3 management, robot interface
│   ├── app.py                        # Main Flask app
│   ├── uploads/                      # Local cache/staging for user-uploaded face images (before S3)
├── web_app/                          # HTML/CSS/JavaScript source code for the frontend
│   ├── index.html                    # Main web page
│   ├── style.css                     # Stylesheets
│   └── script.js                     # Frontend logic for API interaction
├── legacy_testing/                  # For non-production scripts (like local webcam tests)
│   ├── face_register.py             # Manual script to enroll faces via webcam
│   └── face_recognizer.py           # Optional: local-only version of ai_facial_recognition
├── README.md                         # Project overview + setup
├── requirements.txt                  # Flask, face_recognition, OpenCV, boto3, etc.
├── .env                              # Local environment variables (e.g., AWS credentials), **ignored by Git**
├── Procfile                          # For Heroku deployment
├── runtime.txt                       # Specifies Python version for Heroku
└── Research/                         # Project research and documentation
    ├── CLOUD_HOSTING_RESEARCH.md
    ├── CURRENT_SITUATION.md
    ├── SIGN_LIST.md
    └── YOLO_RESEARCH.md

---

## 🚀 How to Run (Development Mode - Local Simulation)

Your project now supports **simulation mode** so you can develop and test without the physical Yahboom Raspbot! For detailed setup instructions, refer to `DEVELOPMENT_SETUP.md`.

### 1. Environment Setup

Refer to `DEVELOPMENT_SETUP.md` for virtual environment creation, dependency installation, and **AWS S3 credential configuration**.

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
# If you have Python, you can use SimpleHTTPServer from the project root:
python -m http.server 8000
# Then open your browser to http://localhost:8000/web_app/index.html
```

---

**Last Updated**: September 23, 2025
**Project Due**: December 2, 2025
**Status**: Adapting to Yahboom Hardware & Developing HTML Frontend
