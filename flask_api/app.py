"""
Unified Flask REST API for Yahboom Raspbot
- Handles face registration, image upload, navigation goals, and status
- Integrates with RobotController and face recognition
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, request, jsonify
from robot_navigation.robot_controller import RobotController
from threading import Thread
import time
from zeroconf import Zeroconf, ServiceInfo
import socket
import face_recognition
import pickle

app = Flask(__name__)
# Use simulation mode by default - change to False when deploying to real robot
controller = RobotController(use_simulation=True)

status = {
    'state': 'idle',  # idle, navigating, arrived, face_recognized, failed
    'last_goal': None,
    'last_update': time.time(),
}

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ENCODINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'encodings.pkl'))

orders = []

# --- Navigation Endpoints ---
def navigation_thread(goal):
    status['state'] = 'navigating'
    status['last_goal'] = goal
    status['last_update'] = time.time()
    controller.run(goal)
    if controller.arrived:
        status['state'] = 'arrived'
        status['last_update'] = time.time()
        recognized = controller.perform_face_recognition()
        if recognized:
            status['state'] = 'face_recognized'
        else:
            status['state'] = 'failed'
        status['last_update'] = time.time()
    else:
        status['state'] = 'failed'
        status['last_update'] = time.time()

@app.route('/goal', methods=['POST'])
def set_goal():
    data = request.get_json()
    goal = data.get('goal')  # Expecting [x, y] or [lat, lon]
    if not goal or not isinstance(goal, list) or len(goal) != 2:
        return jsonify({'error': 'Invalid goal format. Expected [x, y] or [lat, lon].'}), 400
    Thread(target=navigation_thread, args=(tuple(goal),), daemon=True).start()
    return jsonify({'status': 'Goal received', 'goal': goal})

@app.route('/status', methods=['GET'])
def get_status():
    # Add robot coordinates if available
    coords = None
    if hasattr(controller.localization.state, 'x') and hasattr(controller.localization.state, 'y'):
        coords = {'x': controller.localization.state.x, 'y': controller.localization.state.y}
    gps = controller.localization.get_gps()
    return jsonify({
        'state': status['state'],
        'last_goal': status['last_goal'],
        'last_update': status['last_update'],
        'coords': coords,
        'gps': gps,
    })

@app.route('/orders', methods=['GET', 'POST'])
def handle_orders():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'user' not in data or 'restaurant' not in data or 'items' not in data:
            return jsonify({'error': 'Missing order fields'}), 400
        order = {
            'user': data['user'],
            'restaurant': data['restaurant'],
            'items': data['items'],
            'status': 'pending',
            'timestamp': time.time(),
        }
        orders.append(order)
        return jsonify({'status': 'Order received', 'order': order})
    else:
        return jsonify({'orders': orders})

# --- Face Registration & Image Upload Endpoints ---
@app.route('/register_face', methods=['POST'])
def register_face():
    name = request.form.get('name')
    image = request.files.get('image')
    if not name or not image:
        print('[DEBUG] Missing name or image in request')
        return jsonify({'error': 'Missing name or image'}), 400
    save_path = os.path.join(UPLOAD_FOLDER, f"{name}.jpg")
    image.save(save_path)
    print(f'[DEBUG] Saved image to {save_path}')
    # --- Encode face and update encodings.pkl ---
    img = face_recognition.load_image_file(save_path)
    encodings = face_recognition.face_encodings(img)
    print(f'[DEBUG] face_recognition.face_encodings returned {len(encodings)} encoding(s)')
    if not encodings:
        print('[DEBUG] No face detected in image')
        return jsonify({'error': 'No face detected in image'}), 400
    encoding = encodings[0]
    # Load or create encodings.pkl in project root
    if os.path.exists(ENCODINGS_PATH):
        with open(ENCODINGS_PATH, 'rb') as f:
            data = pickle.load(f)
        known_encodings = data.get('encodings', [])
        known_names = data.get('names', [])
    else:
        known_encodings = []
        known_names = []
    known_encodings.append(encoding)
    known_names.append(name)
    with open(ENCODINGS_PATH, 'wb') as f:
        pickle.dump({'encodings': known_encodings, 'names': known_names}, f)
    print(f'[DEBUG] Added encoding for {name}. Total encodings: {len(known_encodings)}')
    return jsonify({'status': 'Face registered and encoded', 'name': name})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    # Example: expects multipart/form-data with 'image' field
    image = request.files.get('image')
    if not image:
        return jsonify({'error': 'No image provided'}), 400
    save_path = os.path.join(UPLOAD_FOLDER, image.filename)
    image.save(save_path)
    return jsonify({'status': 'Image uploaded', 'filename': image.filename})

@app.route('/delete_face', methods=['DELETE'])
def delete_face():
    """
    Delete a user's face data (image and encoding) by name.
    Expects JSON: {"name": "username"}
    """
    data = request.get_json()
    name = data.get('name') if data else None
    if not name:
        return jsonify({'error': 'Missing name'}), 400
    # Remove image file
    img_path = os.path.join(UPLOAD_FOLDER, f"{name}.jpg")
    if os.path.exists(img_path):
        os.remove(img_path)
    # Remove encoding from encodings.pkl (if exists)
    if os.path.exists(ENCODINGS_PATH):
        with open(ENCODINGS_PATH, 'rb') as f:
            encodings = pickle.load(f)
        if name in encodings:
            del encodings[name]
            with open(ENCODINGS_PATH, 'wb') as f:
                pickle.dump(encodings, f)
            return jsonify({'status': 'Face data deleted', 'name': name})
        else:
            return jsonify({'status': 'Image deleted, no encoding found', 'name': name})
    return jsonify({'status': 'Image deleted, encodings file not found', 'name': name})

def register_mdns_service(port=5001):
    zeroconf = Zeroconf()
    ip = socket.gethostbyname(socket.gethostname())
    desc = {'path': '/'}
    info = ServiceInfo(
        "_http._tcp.local.",
        "appservice._http._tcp.local.",  # Changed service name
        addresses=[socket.inet_aton(ip)], 
        port=port,
        properties=desc,
        server="appservice.local.",
    )
    zeroconf.register_service(info)
    print(f"[mDNS] Service registered as appservice.local:{port}")
    return zeroconf

if __name__ == '__main__':
    mdns = register_mdns_service(port=5001)
    app.run(host='0.0.0.0', port=5001, debug=True)
