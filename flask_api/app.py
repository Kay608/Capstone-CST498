"""
Unified Flask REST API for Yahboom Raspbot
- Handles face registration, image upload, navigation goals, and status
- Integrates with RobotController and face recognition
"""
import sys
import os
from dotenv import load_dotenv # New import

# Load environment variables from .env file
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, request, jsonify
from robot_navigation.robot_controller import RobotController
from threading import Thread
import time
from zeroconf import Zeroconf, ServiceInfo
import socket
import face_recognition
import pickle
import boto3 # New import for AWS S3
from botocore.exceptions import NoCredentialsError, ClientError # For error handling

app = Flask(__name__)
# Use simulation mode by default - change to False when deploying to real robot
controller = RobotController(use_simulation=True)

# --- AWS S3 Configuration ---
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2') # Default to us-east-2 if not set
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

if not S3_BUCKET_NAME:
    print("[WARNING] S3_BUCKET_NAME environment variable not set. S3 operations will fail.")
    s3_client = None
else:
    try:
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        print(f"[INFO] S3 client initialized for bucket: {S3_BUCKET_NAME} in region: {AWS_REGION}")
    except NoCredentialsError:
        print("[ERROR] AWS credentials not found. S3 operations will fail.")
        s3_client = None
    except Exception as e:
        print(f"[ERROR] Error initializing S3 client: {e}")
        s3_client = None

ENCODINGS_FILE_KEY = 'encodings.pkl' # The name of your encodings file in S3

def upload_file_to_s3(file_content, file_name, folder=''):
    """
    Uploads file content to S3.
    """
    if not s3_client:
        return False, "S3 client not initialized."
    
    s3_path = f"{folder}{file_name}"
    try:
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_path, Body=file_content)
        print(f"[INFO] Successfully uploaded {s3_path} to S3.")
        return True, f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_path}"
    except ClientError as e:
        print(f"[ERROR] S3 upload failed for {s3_path}: {e}")
        return False, str(e)
    except Exception as e:
        print(f"[ERROR] Unexpected S3 upload error for {s3_path}: {e}")
        return False, str(e)

def download_file_from_s3(file_key):
    """
    Downloads a file from S3.
    """
    if not s3_client:
        return None, "S3 client not initialized."

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
        print(f"[INFO] Successfully downloaded {file_key} from S3.")
        return response['Body'].read(), None
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"[WARNING] {file_key} not found in S3 bucket.")
            return None, "File not found."
        print(f"[ERROR] S3 download failed for {file_key}: {e}")
        return None, str(e)
    except Exception as e:
        print(f"[ERROR] Unexpected S3 download error for {file_key}: {e}")
        return None, str(e)

def delete_file_from_s3(file_key):
    """
    Deletes a file from S3.
    """
    if not s3_client:
        return False, "S3 client not initialized."

    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=file_key)
        print(f"[INFO] Successfully deleted {file_key} from S3.")
        return True, None
    except ClientError as e:
        print(f"[ERROR] S3 deletion failed for {file_key}: {e}")
        return False, str(e)
    except Exception as e:
        print(f"[ERROR] Unexpected S3 deletion error for {file_key}: {e}")
        return False, str(e)

def load_encodings_from_s3():
    """
    Loads known face encodings and names from S3.
    """
    data_bytes, error = download_file_from_s3(ENCODINGS_FILE_KEY)
    if data_bytes:
        try:
            data = pickle.loads(data_bytes)
            return data.get('encodings', []), data.get('names', [])
        except Exception as e:
            print(f"[ERROR] Failed to unpickle encodings from S3: {e}")
            return [], []
    print("[INFO] No encodings file found in S3 or S3 client not initialized. Starting with empty database.")
    return [], []

def save_encodings_to_s3(known_encodings, known_names):
    """
    Saves known face encodings and names to S3.
    """
    data = {"encodings": known_encodings, "names": known_names}
    data_bytes = pickle.dumps(data)
    success, message = upload_file_to_s3(data_bytes, ENCODINGS_FILE_KEY)
    if not success:
        print(f"[ERROR] Failed to save encodings to S3: {message}")
    return success

# --- Replace local file operations with S3 operations ---
# Commenting out local UPLOAD_FOLDER and ENCODINGS_PATH as they are no longer used for persistence.
# UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ENCODINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'encodings.pkl'))

# Load known faces from S3 on startup
known_encodings, known_names = load_encodings_from_s3()

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
    
    # Convert image to bytes for S3 upload
    image_bytes = image.read()
    image_filename = f"{name}.jpg"
    success, upload_url = upload_file_to_s3(image_bytes, image_filename, folder='faces/')

    if not success:
        print(f'[ERROR] Failed to upload image to S3: {upload_url}')
        return jsonify({'error': f'Failed to upload image: {upload_url}'}), 500

    # --- Encode face and update encodings.pkl on S3 ---
    # Load image from bytes for face_recognition
    img = face_recognition.load_image_file(image_bytes)
    encodings = face_recognition.face_encodings(img)
    print(f'[DEBUG] face_recognition.face_encodings returned {len(encodings)} encoding(s)')
    if not encodings:
        print('[DEBUG] No face detected in image')
        # Delete the uploaded image from S3 if no face is detected
        delete_file_from_s3(f'faces/{image_filename}')
        return jsonify({'error': 'No face detected in image'}), 400
    encoding = encodings[0]
    
    # Load encodings from S3, update, and save back to S3
    known_encodings, known_names = load_encodings_from_s3()
    
    known_encodings.append(encoding)
    known_names.append(name)
    
    if not save_encodings_to_s3(known_encodings, known_names):
        return jsonify({'error': 'Failed to save encodings to cloud storage'}), 500

    print(f'[DEBUG] Added encoding for {name}. Total encodings: {len(known_encodings)}')
    return jsonify({'status': 'Face registered and encoded', 'name': name, 'image_url': upload_url})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    # Example: expects multipart/form-data with 'image' field
    image = request.files.get('image')
    if not image:
        return jsonify({'error': 'No image provided'}), 400
    
    image_bytes = image.read()
    image_filename = image.filename
    success, upload_url = upload_file_to_s3(image_bytes, image_filename, folder='uploads/')

    if not success:
        print(f'[ERROR] Failed to upload image to S3: {upload_url}')
        return jsonify({'error': f'Failed to upload image: {upload_url}'}), 500

    return jsonify({'status': 'Image uploaded', 'filename': image.filename, 'image_url': upload_url})

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

    # Delete image from S3
    image_filename = f"{name}.jpg"
    success, message = delete_file_from_s3(f'faces/{image_filename}')
    if not success:
        print(f"[WARNING] Could not delete image {image_filename} from S3: {message}")

    # Load encodings from S3, remove the face, and save back to S3
    known_encodings, known_names = load_encodings_from_s3()
    
    if name in known_names:
        idx = known_names.index(name)
        known_encodings.pop(idx)
        known_names.pop(idx)
        
        if not save_encodings_to_s3(known_encodings, known_names):
            return jsonify({'error': 'Failed to update encodings in cloud storage'}), 500
            
        return jsonify({'status': 'Face data deleted', 'name': name})
    else:
        return jsonify({'status': 'Image deleted, no encoding found in cloud', 'name': name})

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
