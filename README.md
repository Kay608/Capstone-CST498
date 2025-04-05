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

