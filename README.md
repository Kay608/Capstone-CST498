"# Capstone-CST498" 
# 🍱 AI-Powered Facial Recognition Food Delivery Bot

This is a senior capstone project for CST 498 at NC A&T State University. It aims to create a secure, contactless food delivery experience using facial recognition technology and an autonomous Raspberry Pi-based robot.

## 🤖 Project Overview

The delivery bot:
- Uses **facial recognition** to verify users before releasing their food.
- **Navigates** to the destination and obeys road signs via YOLO-based sign detection.
- Integrates with a **mobile app** where users can upload their face for enrollment.

## 🧠 Core Components

### 1. `ai_facial_recognition.py`
Runs on the Raspberry Pi. Captures real-time video, compares detected faces to saved encodings, and triggers bot actions if a match is found.

### 2. Flask API (`/flask_api/app.py`)
Runs on the Pi. Receives image uploads from the mobile app, extracts encodings, and updates the database.

### 3. Flutter Mobile App
Used to register users by capturing and uploading face images to the Flask API.

## 🗂️ File Structure

/AI-Food-Delivery-Bot
├── ai_facial_recognition.py          # FINAL robot-side script: does recognition + triggers
├── encodings.pkl                     # Pickled face encodings, created from Flask API
├── flask_api/                        # 🔥 Flask API for enrollment & recognition
│   ├── app.py                        # Main Flask app (POST /upload, /recognize)
│   ├── uploads/                      # Stores user-uploaded face images
│   └── encodings.pkl                 # Could also live here and be shared with robot script
├── mobile_app/                       # 📱 Flutter source code for the app
│   ├── lib/
│   │   └── main.dart                 # UI for camera + HTTP upload
│   └── pubspec.yaml                  # Flutter dependencies
├── legacy_testing/                  # 🧪 For non-production scripts (like local webcam tests)
│   ├── face_register.py             # Manual script to enroll faces via webcam
│   └── face_recognizer.py           # Optional: local-only version of ai_facial_recognition
├── README.md                         # Project overview + setup
├── requirements.txt                  # Flask, face_recognition, OpenCV, etc.
└── docs/
    └── facial_pipeline.md           # Optional

-----------------------------------------------------------------


## 🚀 How to Run

### Backend (Flask API)
```bash
cd flask_api
pip install -r ../requirements.txt
python app.py

Robot (Facial Recognition)
python ai_facial_recognition.py

Mobile App
cd mobile_app
flutter pub get
flutter run
