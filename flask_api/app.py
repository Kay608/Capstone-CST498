from flask import Flask, request, jsonify
import os
import face_recognition
import cv2
import numpy as np
import pickle
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps
from datetime import datetime, timedelta

SECRET_KEY = 'your_secret_key_here'  # Change this in production!
USERS_FILE = 'users.pkl'

app = Flask(__name__)

# Folder to save received images
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

known_encodings = []
known_names = []

def save_users(users):
    with open(USERS_FILE, 'wb') as f:
        pickle.dump(users, f)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'rb') as f:
        return pickle.load(f)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data['username']
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

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
                # Extract user name from filename (before first underscore)
                user = filename.split("_")[0]
                for encoding in encodings:
                    known_encodings.append(encoding)
                    known_names.append(user)

    # Save encodings to a file
    with open("encodings.pkl", "wb") as f:
        pickle.dump({
            "encodings": known_encodings,
            "names": known_names
        }, f)
    print("[INFO] encodings.pkl updated.")

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400
    users = load_users()
    if username in users:
        return jsonify({'message': 'User already exists'}), 400
    users[username] = generate_password_hash(password)
    save_users(users)
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    users = load_users()
    if username not in users or not check_password_hash(users[username], password):
        return jsonify({'message': 'Invalid credentials'}), 401
    token = jwt.encode({
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=12)
    }, SECRET_KEY, algorithm="HS256")
    return jsonify({'token': token}), 200

@app.route('/upload', methods=['POST'])
@token_required
def upload_image(current_user):
    """Receives an image from the mobile app and saves it"""
    if 'image' not in request.files:
        return jsonify({"message": "No image found"}), 400

    file = request.files['image']
    # Use username from token, not from form
    name = current_user
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{name}_{timestamp}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
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

@app.route('/delete_face', methods=['DELETE'])
@token_required
def delete_face(current_user):
    """Deletes all face images and encodings for the current user"""
    # Delete user's images from uploads folder
    deleted_files = 0
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(f"{current_user}_"):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                os.remove(file_path)
                deleted_files += 1
            except Exception as e:
                print(f"[ERROR] Could not delete {file_path}: {e}")
    # Reload faces to update encodings.pkl
    load_known_faces()
    if deleted_files == 0:
        return jsonify({"message": "No face data found for user."}), 404
    return jsonify({"message": f"Deleted {deleted_files} face image(s) and encodings for user {current_user}."}), 200

if __name__ == '__main__':
    load_known_faces()  # Load faces when the server starts
    app.run(host='0.0.0.0', port=5000)
