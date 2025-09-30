"""
Unified Flask REST API for Yahboom Raspbot
- Handles face registration, image upload, navigation goals, and status
- Integrates with RobotController and face recognition
"""
import sys
import os
from dotenv import load_dotenv
import pickle
import pymysql # New import for MySQL
from io import BytesIO # New import for handling byte streams
import numpy as np # To deserialize bytea back to numpy array

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

app = Flask(__name__)
# Use simulation mode by default - change to False when deploying to real robot
controller = RobotController(use_simulation=True)

# --- JawsDB (MySQL) Configuration ---
DATABASE_URL = os.environ.get('JAWSDB_URL') # Use JAWSDB_URL for Heroku MySQL

if not DATABASE_URL:
    # Fallback for local testing if DATABASE_URL is explicitly set
    DATABASE_URL = os.environ.get('DATABASE_URL') # Local testing DATABASE_URL might be different
    if not DATABASE_URL:
        print("[ERROR] DATABASE_URL or JAWSDB_URL environment variable not set. Database operations will fail.")

def get_db_connection():
    # Parse the DATABASE_URL
    # Format: mysql://user:password@host:port/database_name
    try:
        url = pymysql.connections.MySQLConnection.url_to_dict(DATABASE_URL)
        conn = pymysql.connect(
            host=url['host'],
            port=url['port'],
            user=url['user'],
            password=url['password'],
            database=url['database'],
            cursorclass=pymysql.cursors.DictCursor # Return dictionaries
        )
        return conn
    except Exception as e:
        print(f"[ERROR] Failed to connect to MySQL database: {e}")
        raise

def init_db():
    if not DATABASE_URL:
        print("[WARNING] Skipping DB initialization: DATABASE_URL not set.")
        return
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                encoding BLOB NOT NULL
            );
        """)
        conn.commit()
        cur.close()
        print("[INFO] Database initialized: 'faces' table ensured.")
    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
    finally:
        if conn:
            conn.close()

def load_encodings_from_db():
    if not DATABASE_URL:
        return [], []
    conn = None
    known_encodings = []
    known_names = []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, encoding FROM faces;")
        rows = cur.fetchall()
        for row in rows:
            name = row['name']
            encoding_bytes = row['encoding']
            # Deserialize the BLOB back to a numpy array
            encoding = np.frombuffer(encoding_bytes, dtype=np.float64) # Assuming float64 for face encodings
            known_encodings.append(encoding)
            known_names.append(name)
        cur.close()
        print(f"[INFO] Loaded {len(known_names)} known face(s) from MySQL.")
    except Exception as e:
        print(f"[ERROR] Error loading encodings from MySQL: {e}. Starting with empty database.")
    finally:
        if conn:
            conn.close()
    return known_encodings, known_names

def save_encoding_to_db(name, encoding):
    if not DATABASE_URL:
        print("[WARNING] Skipping save: DATABASE_URL not set.")
        return False
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Serialize the numpy array to bytes
        encoding_bytes = encoding.tobytes()

        # Check if name already exists, if so, update; otherwise insert
        cur.execute("SELECT id FROM faces WHERE name = %s;", (name,))
        if cur.fetchone():
            cur.execute("UPDATE faces SET encoding = %s WHERE name = %s;", (encoding_bytes, name))
            print(f"[INFO] Updated encoding for {name} in MySQL.")
        else:
            cur.execute("INSERT INTO faces (name, encoding) VALUES (%s, %s);", (name, encoding_bytes))
            print(f"[INFO] Added encoding for {name} to MySQL.")
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"[ERROR] Error saving encoding to MySQL: {e}")
        return False
    finally:
        if conn:
            conn.close()

def delete_encoding_from_db(name):
    if not DATABASE_URL:
        print("[WARNING] Skipping deletion: DATABASE_URL not set.")
        return False
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM faces WHERE name = %s;", (name,))
        conn.commit()
        cur.close()
        print(f"[INFO] Deleted encoding for {name} from MySQL.")
        return True
    except Exception as e:
        print(f"[ERROR] Error deleting encoding from MySQL: {e}")
        return False
    finally:
        if conn:
            conn.close()

init_db() # Initialize database on app startup

known_encodings, known_names = load_encodings_from_db()

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
    
    image_bytes = image.read()
    
    # --- Encode face ---
    img = face_recognition.load_image_file(BytesIO(image_bytes)) # Use BytesIO for in-memory image
    encodings = face_recognition.face_encodings(img)
    print(f'[DEBUG] face_recognition.face_encodings returned {len(encodings)} encoding(s)')
    if not encodings:
        print('[DEBUG] No face detected in image')
        return jsonify({'error': 'No face detected in image'}), 400
    encoding = encodings[0]
    
    if not save_encoding_to_db(name, encoding):
        return jsonify({'error': 'Failed to save encoding to database'}), 500

    global known_encodings, known_names
    known_encodings, known_names = load_encodings_from_db() # Reload from DB to ensure consistency
    
    print(f'[DEBUG] Added encoding for {name}. Total encodings: {len(known_encodings)}')
    return jsonify({'status': 'Face registered and encoded', 'name': name})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    # This endpoint is currently a no-op after S3 removal. 
    # If image storage is still needed, it will need to be re-implemented 
    # with a new storage solution (e.g., local disk or another cloud service).
    return jsonify({'status': 'Image upload endpoint currently not active (S3 removed)'}), 200

@app.route('/delete_face', methods=['DELETE'])
def delete_face():
    """
    Delete a user's face data (encoding) by name.
    Expects JSON: {"name": "username"}
    """
    data = request.get_json()
    name = data.get('name') if data else None
    if not name:
        return jsonify({'error': 'Missing name'}), 400

    if not delete_encoding_from_db(name):
        return jsonify({'error': 'Failed to delete encoding from database'}), 500

    global known_encodings, known_names
    known_encodings, known_names = load_encodings_from_db() # Reload from DB to ensure consistency
    
    return jsonify({'status': 'Face data deleted', 'name': name})

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
    status = {'state': 'idle', 'last_goal': None, 'last_update': time.time()}
    mdns = register_mdns_service(port=5001)
    app.run(host='0.0.0.0', port=5001, debug=True)
