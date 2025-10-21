"""
Unified Flask REST API for Yahboom Raspbot
- Handles face registration, image upload, navigation goals, and status
- Integrates with RobotController and face recognition
"""
import sys
import os
from dotenv import load_dotenv
from pathlib import Path
import pymysql
from io import BytesIO
import numpy as np

# Load environment variables from .env file(s)
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, request, jsonify, render_template
from robot_navigation.robot_controller import RobotController
from threading import Thread
import time
from zeroconf import Zeroconf, ServiceInfo
import socket
import face_recognition


def _is_truthy(value: str) -> bool:
    """Interpret common truthy strings so env flags behave predictably."""
    return str(value).strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}

app = Flask(__name__)
# Use simulation mode by default - change to False when deploying to real robot
controller = RobotController(use_simulation=True)

# Respect FLASK_DEBUG when the app is executed directly
_debug_env = os.environ.get('FLASK_DEBUG', '1')
_run_debug_mode = _is_truthy(_debug_env)

# Track high-level robot state for status endpoint; initialized here so gunicorn workers inherit it
status = {'state': 'idle', 'last_goal': None, 'last_update': time.time()}

# --- JawsDB (MySQL) Configuration ---
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

def get_db_connection():
    """Opens a new database connection."""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor, # Return dictionaries
            connect_timeout=10
        )
        return conn
    except pymysql.MySQLError as e:
        print(f"[ERROR] Failed to connect to MySQL database: {e}")
        raise

def init_db():
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Skipping DB initialization: Database environment variables not fully set.")
        return
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    banner_id VARCHAR(255) NOT NULL UNIQUE,
                    first_name VARCHAR(255) NOT NULL,
                    last_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    encoding BLOB NOT NULL
                );
            """)
        conn.commit()
        print("[INFO] Database initialized: 'users' table ensured.")
    except pymysql.MySQLError as e:
        print(f"[ERROR] Error initializing database: {e}")
    finally:
        if conn:
            conn.close()


def load_encodings_from_db():
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        return [], []
    
    conn = None
    known_encodings = []
    known_names = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT banner_id, encoding FROM users;")
            rows = cur.fetchall()
            for row in rows:
                # In this context, 'name' is the banner_id for identification
                name = row['banner_id']
                encoding_bytes = row['encoding']
                # Deserialize the BLOB back to a numpy array
                encoding = np.frombuffer(encoding_bytes, dtype=np.float64)
                known_encodings.append(encoding)
                known_names.append(name)
        print(f"[INFO] Loaded {len(known_names)} known face(s) from MySQL.")
    except pymysql.MySQLError as e:
        print(f"[ERROR] Error loading encodings from MySQL: {e}. Starting with empty database.")
    finally:
        if conn:
            conn.close()
    
    return known_encodings, known_names

def save_user_to_db(banner_id, first_name, last_name, email, encoding):
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Skipping save: Database environment variables not set.")
        return False
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Serialize the numpy array to bytes
            encoding_bytes = encoding.tobytes()

            # Check if banner_id already exists, if so, update; otherwise insert
            cur.execute("SELECT id FROM users WHERE banner_id = %s;", (banner_id,))
            if cur.fetchone():
                cur.execute("""
                    UPDATE users 
                    SET first_name = %s, last_name = %s, email = %s, encoding = %s 
                    WHERE banner_id = %s;
                """, (first_name, last_name, email, encoding_bytes, banner_id))
                print(f"[INFO] Updated user for {banner_id} in MySQL.")
            else:
                cur.execute("""
                    INSERT INTO users (banner_id, first_name, last_name, email, encoding) 
                    VALUES (%s, %s, %s, %s, %s);
                """, (banner_id, first_name, last_name, email, encoding_bytes))
                print(f"[INFO] Added user for {banner_id} to MySQL.")
            conn.commit()
        return True
    except pymysql.MySQLError as e:
        print(f"[ERROR] Error saving user to MySQL: {e}")
        return False
    finally:
        if conn:
            conn.close()


def delete_user_from_db(banner_id):
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Skipping deletion: Database environment variables not set.")
        return False
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE banner_id = %s;", (banner_id,))
            conn.commit()
            if cur.rowcount > 0:
                print(f"[INFO] Deleted user for {banner_id} from MySQL.")
                return True
            else:
                print(f"[INFO] No user found with banner_id {banner_id} to delete.")
                return False
    except pymysql.MySQLError as e:
        print(f"[ERROR] Error deleting user from MySQL: {e}")
        return False
    finally:
        if conn:
            conn.close()

# These will be loaded once before the first request
known_encodings = []
known_names = []

@app.before_first_request
def initialize_database_and_encodings():
    """
    Initialize the database and load face encodings once before the first request.
    This avoids issues with the Flask reloader in debug mode.
    """
    global known_encodings, known_names
    print("[INFO] Initializing database and loading encodings...")
    init_db()
    known_encodings, known_names = load_encodings_from_db()
    print("[INFO] Initialization complete.")


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
def handle_face_registration(banner_id, first_name, last_name, email, image_file):
    """Shared registration logic for API and HTML workflows."""
    required_fields = {
        'banner_id': banner_id,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'image': image_file,
    }
    missing_fields = [field for field, value in required_fields.items() if not value]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}", 400

    try:
        image_bytes = image_file.read()
        img = face_recognition.load_image_file(BytesIO(image_bytes))
        encodings = face_recognition.face_encodings(img)
        if not encodings:
            return False, 'No face detected in image', 400
        encoding = encodings[0]
    except Exception as e:
        return False, f'Failed to process image: {e}', 500

    if not save_user_to_db(banner_id, first_name, last_name, email, encoding):
        return False, 'Failed to save user to database', 500

    global known_encodings, known_names
    known_encodings, known_names = load_encodings_from_db()

    return True, {'banner_id': banner_id}, 200


@app.route('/register_face', methods=['POST'])
def register_face():
    success, payload, status_code = handle_face_registration(
        request.form.get('banner_id'),
        request.form.get('first_name'),
        request.form.get('last_name'),
        request.form.get('email'),
        request.files.get('image'),
    )

    if success:
        return jsonify({'status': 'User registered successfully', 'banner_id': payload['banner_id']}), status_code

    return jsonify({'error': payload}), status_code


@app.route('/enroll', methods=['GET', 'POST'])
def enroll():
    if request.method == 'GET':
        return render_template('enroll.html', result=None, form_data={})

    form_data = {
        'banner_id': request.form.get('banner_id', ''),
        'first_name': request.form.get('first_name', ''),
        'last_name': request.form.get('last_name', ''),
        'email': request.form.get('email', ''),
    }

    success, payload, status_code = handle_face_registration(
        form_data['banner_id'],
        form_data['first_name'],
        form_data['last_name'],
        form_data['email'],
        request.files.get('image'),
    )

    if success:
        message = f"User {payload['banner_id']} registered successfully."
        # Clear form fields on success
        form_data = {key: '' for key in form_data}
        return render_template('enroll.html', result={'success': True, 'message': message}, form_data=form_data), status_code

    return render_template('enroll.html', result={'success': False, 'message': payload}, form_data=form_data), status_code


@app.route('/upload_image', methods=['POST'])
def upload_image():
    # This endpoint is currently a no-op after S3 removal. 
    # If image storage is still needed, it will need to be re-implemented 
    # with a new storage solution (e.g., local disk or another cloud service).
    return jsonify({'status': 'Image upload endpoint currently not active (S3 removed)'}), 200

@app.route('/delete_face', methods=['DELETE'])
def delete_face():
    """
    Delete a user's face data (encoding) by banner_id.
    Expects JSON: {"banner_id": "B00123456"}
    """
    data = request.get_json()
    banner_id = data.get('banner_id') if data else None
    if not banner_id:
        return jsonify({'error': 'Missing banner_id'}), 400

    if not delete_user_from_db(banner_id):
        return jsonify({'error': 'Failed to delete user from database or user not found'}), 500

    global known_encodings, known_names
    # Reload from DB to ensure consistency
    known_encodings, known_names = load_encodings_from_db()
    
    return jsonify({'status': 'User data deleted', 'banner_id': banner_id})

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
    # The initialization is now handled by the before_first_request hook
    app.run(host='0.0.0.0', port=5001, debug=_run_debug_mode)