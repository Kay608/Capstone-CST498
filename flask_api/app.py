from flask import Flask, request, jsonify
import os
import face_recognition
import cv2
import numpy as np
import pickle

app = Flask(__name__)

# Folder to save received images
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

known_encodings = []
known_names = []

def load_known_faces():
    """Load saved faces from the 'uploads' folder"""
    global known_encodings, known_names
    known_encodings = []
    known_names = []

    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                known_encodings.append(encodings[0])
                known_names.append(filename.split(".")[0])  # Use filename as the name

    # Save encodings to a file
    with open("encodings.pkl", "wb") as f:
        pickle.dump({
            "encodings": known_encodings,
            "names": known_names
        }, f)
    print("[INFO] encodings.pkl updated.")

@app.route('/upload', methods=['POST'])
def upload_image():
    """Receives an image from the mobile app and saves it"""
    if 'image' not in request.files:
        return jsonify({"message": "No image found"}), 400

    file = request.files['image']
    name = request.form.get("name", "Unknown")

    filepath = os.path.join(UPLOAD_FOLDER, f"{name}.jpg")
    file.save(filepath)

    # Reload faces after adding a new one
    load_known_faces()

    return jsonify({"message": "Image received and trained"}), 200

@app.route('/recognize', methods=['POST'])
def recognize_face():
    """Recognizes a face from an uploaded image"""
    if 'image' not in request.files:
        return jsonify({"message": "No image found"}), 400

    file = request.files['image']
    image = face_recognition.load_image_file(file)
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)

    recognized_names = []
    for encoding in face_encodings:
        matches = face_recognition.compare_faces(known_encodings, encoding)
        name = "Unknown"
        if True in matches:
            match_index = matches.index(True)
            name = known_names[match_index]
        recognized_names.append(name)

    return jsonify({"recognized": recognized_names}), 200

if __name__ == '__main__':
    load_known_faces()  # Load faces when the server starts
    app.run(host='0.0.0.0', port=5000)
