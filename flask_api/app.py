'''
Sugessted Code for Users uploaded facial images to be recognized by the robot
**Install Raspberry Pi Packages
pip3 install flask flask-cors face_recognition numpy opencv-python

Create a python scripts on the Raspery Pi

This Script is our Flask API server, meant to run on the Raspberry Pi. It acts as a bridge between:
The Flutter app (which sends images) and the Pi, which stores/encodes them for facial recognition.
'''
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

**App collect facial images and send to raspery pi to be learned
Dependencies:
dependencies:
  flutter:
    sdk: flutter
  image_picker: ^1.0.4
  http: ^0.13.6
Run: flutter pub get
*Implement Image Capture and Upload
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart';
import 'package:mime/mime.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: FaceUploadScreen(),
    );
  }
}

class FaceUploadScreen extends StatefulWidget {
  @override
  _FaceUploadScreenState createState() => _FaceUploadScreenState();
}

class _FaceUploadScreenState extends State<FaceUploadScreen> {
  File? _image;
  final picker = ImagePicker();
  final String serverUrl = "http://192.168.1.100:5000/upload"; // Replace with your Raspberry Pi's IP

  Future<void> _pickImage() async {
    final pickedFile = await picker.pickImage(source: ImageSource.camera);
    
    if (pickedFile != null) {
      setState(() {
        _image = File(pickedFile.path);
      });
    }
  }

  Future<void> _uploadImage() async {
    if (_image == null) return;

    var uri = Uri.parse(serverUrl);
    var request = http.MultipartRequest('POST', uri);

    request.fields['name'] = "JohnDoe"; // Replace with actual username
    request.files.add(await http.MultipartFile.fromPath(
      'image',
      _image!.path,
      contentType: MediaType.parse(lookupMimeType(_image!.path) ?? "image/jpeg"),
    ));

    var response = await request.send();

    if (response.statusCode == 200) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Image uploaded successfully!")),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Upload failed!")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Face Recognition Upload")),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _image != null
                ? Image.file(_image!, height: 200)
                : Text("No image selected"),
            SizedBox(height: 20),
            ElevatedButton(
              onPressed: _pickImage,
              child: Text("Take Photo"),
            ),
            SizedBox(height: 10),
            ElevatedButton(
              onPressed: _uploadImage,
              child: Text("Upload Photo"),
            ),
          ],
        ),
      ),
    );
  }
}
