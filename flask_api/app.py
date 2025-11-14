"""
Unified Flask REST API for Yahboom Raspbot
- Handles face registration, image upload, navigation goals, and status
- Integrates with RobotController and face recognition
"""
import sys
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
from contextlib import suppress
import pymysql
from io import BytesIO
import numpy as np

# Load environment variables from .env file(s)
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PYTHON_CODES_DIR = BASE_DIR / "python codes"
if PYTHON_CODES_DIR.exists() and str(PYTHON_CODES_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_CODES_DIR))

from flask import Flask, request, jsonify, render_template
from robot_navigation.robot_controller import RobotController
from robot_navigation.hardware_interface import create_hardware_interface, HardwareInterface
from threading import Thread
import time
# Optional imports for network discovery
try:
    from zeroconf import Zeroconf, ServiceInfo
    ZEROCONF_AVAILABLE = True
except ImportError:
    print("[INFO] Zeroconf not available - network discovery disabled")
    ZEROCONF_AVAILABLE = False

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

MANUAL_CONTROL_TOKEN = os.environ.get("RC_CONTROL_TOKEN", "")
_manual_interface: Optional[HardwareInterface] = None


def _authorize_manual_request(req) -> bool:
    if not MANUAL_CONTROL_TOKEN:
        return True
    provided = req.headers.get("X-Api-Key") or req.args.get("api_key")
    return provided == MANUAL_CONTROL_TOKEN


def _get_manual_interface() -> Optional[HardwareInterface]:
    global _manual_interface
    if _manual_interface and _manual_interface.is_available():
        return _manual_interface
    try:
        candidate = create_hardware_interface(use_simulation=False)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to initialize manual control hardware: {exc}")
        return None
    if candidate.is_available():
        _manual_interface = candidate
        return _manual_interface
    return None

# --- JawsDB (MySQL) Configuration ---
# Hardcoded values for testing
DB_HOST = 'd6vscs19jtah8iwb.cbetxkdyhwsb.us-east-1.rds.amazonaws.com'
DB_USER = 'pibeadwopo2puu2w'
DB_PASSWORD = 'ia58h6oid99au8x4'
DB_NAME = 'cdzpl48ljf6v83hu'

# Print debug information about database configuration
print("\n[DEBUG] Database Configuration:")
print(f"DB_HOST: {DB_HOST}")
print(f"DB_USER: {DB_USER}")
print(f"DB_NAME: {DB_NAME}")
print(f"DB_PASSWORD is {'set' if DB_PASSWORD else 'not set'}\n")

def get_db_connection():
    """Opens a new database connection."""
    print("\n[DEBUG] Attempting JawsDB connection with:")
    print(f"Host: {DB_HOST}")
    print(f"User: {DB_USER}")
    print(f"Database: {DB_NAME}")
    print(f"Password length: {len(DB_PASSWORD) if DB_PASSWORD else 'No password set'}")
    
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30,  # Increased timeout for remote connection
            charset='utf8mb4',   # Proper charset for MySQL
            ssl_verify_cert=False,  # JawsDB uses self-signed certificates
            ssl_verify_identity=False,
            ssl={'ca': None}  # Disable SSL certificate verification
        )
        print("[DEBUG] JawsDB connection successful!")
        return conn
    except pymysql.Error as e:
        error_code = getattr(e, 'args', [None])[0]
        print(f"\n[ERROR] Database connection failed:")
        print(f"Error Code: {error_code}")
        print(f"Error Message: {str(e)}")
        print("\n[DEBUG] Connection details that failed:")
        print(f"Host: {DB_HOST}")
        print(f"User: {DB_USER}")
        print(f"Database: {DB_NAME}")
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
            # Orders table: order_no autoincrement and banner_id reference
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_no INT AUTO_INCREMENT PRIMARY KEY,
                    banner_id VARCHAR(255) NOT NULL,
                    item VARCHAR(100) NOT NULL,
                    restaurant VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'pending',
                    ts DOUBLE NOT NULL,
                    INDEX(banner_id)
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
    print("\n[DEBUG] Starting save_user_to_db function")
    print(f"[DEBUG] Received data for user {banner_id}")
    
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Skipping save: Database environment variables not set.")
        print(f"DB_HOST present: {bool(DB_HOST)}")
        print(f"DB_USER present: {bool(DB_USER)}")
        print(f"DB_PASSWORD present: {bool(DB_PASSWORD)}")
        print(f"DB_NAME present: {bool(DB_NAME)}")
        return False
    
    print("[DEBUG] All database environment variables are present")
    
    conn = None
    try:
        print("[DEBUG] Attempting to get database connection...")
        conn = get_db_connection()
        print("[DEBUG] Successfully obtained database connection")
        
        print("[DEBUG] Converting face encoding to bytes (ensuring dtype=np.float64)...")
        # Ensure a consistent dtype before saving so deserialization is predictable
        try:
            encoding = np.asarray(encoding, dtype=np.float64)
        except Exception:
            # Fallback: force conversion via float64 cast
            encoding = np.array(encoding, dtype=np.float64)
        encoding_bytes = encoding.tobytes()
        print("[DEBUG] Successfully converted encoding to bytes (dtype enforced)")
        
        with conn.cursor() as cur:
            print(f"[DEBUG] Checking if user {banner_id} already exists...")
            cur.execute("SELECT id FROM users WHERE banner_id = %s;", (banner_id,))
            existing_user = cur.fetchone()
            
            if existing_user:
                print(f"[DEBUG] Updating existing user {banner_id}")
                try:
                    cur.execute("""
                        UPDATE users 
                        SET first_name = %s, last_name = %s, email = %s, encoding = %s 
                        WHERE banner_id = %s;
                    """, (first_name, last_name, email, encoding_bytes, banner_id))
                    print(f"[DEBUG] Update query executed successfully")
                except Exception as e:
                    print(f"[ERROR] Failed to update user: {str(e)}")
                    raise
            else:
                print(f"[DEBUG] Inserting new user {banner_id}")
                try:
                    cur.execute("""
                        INSERT INTO users (banner_id, first_name, last_name, email, encoding) 
                        VALUES (%s, %s, %s, %s, %s);
                    """, (banner_id, first_name, last_name, email, encoding_bytes))
                    print(f"[DEBUG] Insert query executed successfully")
                except Exception as e:
                    print(f"[ERROR] Failed to insert user: {str(e)}")
                    raise
            
            print("[DEBUG] Committing transaction...")
            conn.commit()
            print("[DEBUG] Transaction committed successfully")
            
        print(f"[INFO] Successfully saved/updated user {banner_id} in database")
        return True
        
    except pymysql.Error as e:
        print(f"\n[ERROR] Database error while saving user:")
        print(f"Error Code: {getattr(e, 'args', [None])[0]}")
        print(f"Error Message: {str(e)}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error while saving user:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        return False
    finally:
        if conn:
            try:
                conn.close()
                print("[DEBUG] Database connection closed")
            except Exception as e:
                print(f"[ERROR] Error closing database connection: {str(e)}")


def save_order_to_db(banner_id: str, item: str, restaurant: str, status: str = 'pending'):
    """Persist an order row to MySQL and return the new order number."""
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Skipping order persistence: database credentials missing.")
        return None, 'Database is not configured.'

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # First try with restaurant column
            try:
                cur.execute(
                    """
                    INSERT INTO orders (banner_id, item, restaurant, status, ts)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (banner_id, item, restaurant, status, time.time()),
                )
                order_no = cur.lastrowid
                print(f"[INFO] Saved order {order_no} for {banner_id} to database (with restaurant).")
            except pymysql.MySQLError as e:
                # If restaurant column doesn't exist, try without it
                if "Unknown column 'restaurant'" in str(e):
                    print("[WARN] Restaurant column not found, saving without restaurant...")
                    cur.execute(
                        """
                        INSERT INTO orders (banner_id, item, status, ts)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (banner_id, item, status, time.time()),
                    )
                    order_no = cur.lastrowid
                    print(f"[INFO] Saved order {order_no} for {banner_id} to database (without restaurant).")
                else:
                    raise e
        conn.commit()
        return order_no, None
    except pymysql.MySQLError as exc:
        print(f"[ERROR] Failed to save order to database: {exc}")
        # Check for foreign key constraint error (user doesn't exist)
        if "foreign key constraint fails" in str(exc).lower() and "banner_id" in str(exc):
            return None, "Banner ID not found. You must be registered in the facial recognition system before placing orders. Please contact admin to register."
        elif "duplicate entry" in str(exc).lower():
            return None, "Duplicate order detected. Please try again."
        else:
            return None, f"Database error: {exc}"
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_exc:
                print(f"[ERROR] Failed closing DB connection after order insert: {close_exc}")


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

# Initialize on app startup
with app.app_context():
    initialize_database_and_encodings()


orders = []


# --- Manual RC Control Endpoints ---
@app.route('/api/manual/status', methods=['GET'])
def manual_status():
    if not _authorize_manual_request(request):
        return jsonify({'error': 'Unauthorized'}), 401
    interface = _get_manual_interface()
    payload = {
        'available': bool(interface and interface.is_available()),
        'token_required': bool(MANUAL_CONTROL_TOKEN),
    }
    if interface and interface.is_available():
        with suppress(Exception):
            payload['encoders'] = interface.get_encoder_ticks()
        gps_data = controller.localization.get_gps() if hasattr(controller, 'localization') else None
        if gps_data:
            payload['gps'] = gps_data
    return jsonify(payload)


@app.route('/api/manual/move', methods=['POST'])
def manual_move():
    if not _authorize_manual_request(request):
        return jsonify({'error': 'Unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    direction = (payload.get('direction') or '').lower()
    speed = payload.get('speed', 0.4)
    duration = payload.get('duration', 0.5)
    angle = payload.get('angle', 90.0)

    try:
        speed = max(0.0, min(1.0, float(speed)))
        duration = max(0.0, float(duration))
        angle = max(0.0, float(angle))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid speed, duration, or angle value'}), 400

    interface = _get_manual_interface()
    if not interface or not interface.is_available():
        return jsonify({'error': 'Robot hardware not available'}), 503

    direction_map = {
        'forward': lambda: interface.move_forward(speed, duration),
        'back': lambda: interface.move_backward(speed, duration),
        'backward': lambda: interface.move_backward(speed, duration),
        'reverse': lambda: interface.move_backward(speed, duration),
        'left': lambda: interface.turn_left(speed, angle if angle > 0 else 90.0),
        'right': lambda: interface.turn_right(speed, angle if angle > 0 else 90.0),
    }

    command = direction_map.get(direction)
    if not command:
        return jsonify({'error': 'Unknown direction'}), 400

    try:
        command()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Manual move failed: {exc}")
        return jsonify({'error': str(exc)}), 500

    return jsonify({'status': 'ok', 'direction': direction, 'speed': speed, 'duration': duration, 'angle': angle})


@app.route('/api/manual/stop', methods=['POST'])
def manual_stop():
    if not _authorize_manual_request(request):
        return jsonify({'error': 'Unauthorized'}), 401

    interface = _get_manual_interface()
    if not interface or not interface.is_available():
        return jsonify({'error': 'Robot hardware not available'}), 503

    try:
        interface.stop()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Manual stop failed: {exc}")
        return jsonify({'error': str(exc)}), 500

    return jsonify({'status': 'stopped'})


@app.route('/api/manual/camera', methods=['POST'])
def manual_camera():
    if not _authorize_manual_request(request):
        return jsonify({'error': 'Unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    angle = payload.get('angle')
    try:
        if angle is None:
            raise ValueError('Missing angle')
        angle_value = int(float(angle))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid angle value'}), 400

    angle_value = max(0, min(180, angle_value))

    interface = _get_manual_interface()
    if not interface or not interface.is_available():
        return jsonify({'error': 'Robot hardware not available'}), 503

    try:
        interface.set_camera_servo(angle_value)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Manual camera control failed: {exc}")
        return jsonify({'error': str(exc)}), 500

    return jsonify({'status': 'ok', 'angle': angle_value})

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
    print("\n[DEBUG] Starting face registration process")
    print(f"[DEBUG] Received registration for banner_id: {banner_id}")
    
    required_fields = {
        'banner_id': banner_id,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'image': image_file,
    }
    
    print("[DEBUG] Checking required fields...")
    missing_fields = [field for field, value in required_fields.items() if not value]
    if missing_fields:
        print(f"[ERROR] Missing fields: {', '.join(missing_fields)}")
        return False, f"Missing required fields: {', '.join(missing_fields)}", 400

    try:
        print("[DEBUG] Processing image file...")
        image_bytes = image_file.read()
        print("[DEBUG] Converting image to face_recognition format...")
        img = face_recognition.load_image_file(BytesIO(image_bytes))
        print("[DEBUG] Detecting faces in image...")
        encodings = face_recognition.face_encodings(img)
        
        if not encodings:
            print("[ERROR] No face detected in uploaded image")
            return False, 'No face detected in image', 400
            
        print("[DEBUG] Face detected successfully")
        encoding = encodings[0]
        print(f"[DEBUG] Encoding shape: {encoding.shape}")
        
    except Exception as e:
        print(f"[ERROR] Image processing failed: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        return False, f'Failed to process image: {e}', 500

    print("[DEBUG] Attempting to save user to database...")
    if not save_user_to_db(banner_id, first_name, last_name, email, encoding):
        print("[ERROR] Database save operation failed")
        return False, 'Failed to save user to database', 500

    print("[DEBUG] Reloading face encodings from database...")
    global known_encodings, known_names
    known_encodings, known_names = load_encodings_from_db()
    print("[DEBUG] Face registration process completed successfully")

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


@app.route('/order', methods=['GET', 'POST'])
def order_page():
    """Simple order page that ties an order to a banner_id."""
    form_data = {'banner_id': ''}
    if request.method == 'GET':
        return render_template('order.html', result=None, form_data=form_data)

    # POST: place the order
    banner_id = request.form.get('banner_id', '').strip()
    item = request.form.get('item')
    restaurant = request.form.get('restaurant')
    form_data['banner_id'] = banner_id

    if not banner_id:
        return render_template('order.html', result={'success': False, 'message': 'Missing banner_id.'}, form_data=form_data)
    if not item:
        return render_template('order.html', result={'success': False, 'message': 'Missing item selection.'}, form_data=form_data)
    if not restaurant:
        return render_template('order.html', result={'success': False, 'message': 'Missing restaurant selection.'}, form_data=form_data)

    # Try to resolve human-readable name from the users table (optional)
    user_display = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT first_name, last_name FROM users WHERE banner_id = %s;', (banner_id,))
            row = cur.fetchone()
            if row:
                user_display = f"{row.get('first_name','').strip()} {row.get('last_name','').strip()}".strip() or None
    except Exception:
        # If DB lookup fails, just continue and record the banner_id only
        user_display = None
    finally:
        try:
            if 'conn' in locals() and conn:
                conn.close()
        except Exception:
            pass

    order = {
        'user': {'banner_id': banner_id, 'name': user_display},
        'restaurant': restaurant,
        'items': [item],
        'status': 'pending',
        'timestamp': time.time(),
    }
    # Attempt to persist the order to the orders table in MySQL (preferred)
    order_no, db_error = save_order_to_db(banner_id, item, restaurant, 'pending')

    # If there's a database error, return error immediately
    if db_error:
        return render_template('order.html', result={'success': False, 'message': db_error}, form_data=form_data)

    # Keep an in-memory record as well for quick access
    order['order_no'] = order_no
    orders.append(order)

    message = f"Order received for {banner_id}: {item} from {restaurant}."
    if user_display:
        message = f"Order received for {user_display} ({banner_id}): {item} from {restaurant}."
    if order_no:
        message += f" (order_no: {order_no})"

    return render_template('order.html', result={'success': True, 'message': message}, form_data={'banner_id': ''})

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

# Store verification logs in memory (consider moving to database for production)
verification_log = []

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

@app.route('/admin/verification_log')
def get_verification_log():
    # Get statistics for today
    today = time.strftime('%Y-%m-%d')
    today_verifications = [v for v in verification_log if v['timestamp'].startswith(today)]
    successful_matches = sum(1 for v in today_verifications if v['matched'])
    
    statistics = {
        'total': len(today_verifications),
        'successful': successful_matches,
        'failed': len(today_verifications) - successful_matches,
        'lastUpdate': time.strftime('%Y-%m-%d %H:%M:%S'),
        'knownFaces': len(known_names)
    }
    
    return jsonify({
        'verifications': verification_log[-50:],  # Return last 50 entries
        'statistics': statistics
    })


@app.route('/api/log_verification', methods=['POST'])
def api_log_verification():
    """API endpoint to receive verification logs from remote devices (like Raspberry Pi)."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Extract required fields
        name = data.get('name', 'Unknown')
        matched = data.get('matched', False)
        confidence = data.get('confidence', 0.0)
        location = data.get('location', 'Remote Device')
        
        # Log the verification using the existing function
        log_verification(name, matched, confidence, location)
        
        return jsonify({
            'success': True, 
            'message': 'Verification logged successfully'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Failed to log remote verification: {e}")
        return jsonify({'error': 'Failed to log verification'}), 500


@app.route('/api/process_order', methods=['POST'])
def api_process_order():
    """API endpoint to process order fulfillment when face is recognized."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        banner_id = data.get('banner_id')
        action = data.get('action', 'fulfill')
        
        if not banner_id:
            return jsonify({'error': 'banner_id required'}), 400
        
        # Find pending orders for this banner_id
        if all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    # Check for pending orders (with fallback for missing restaurant column)
                    try:
                        cur.execute(
                            "SELECT order_no, item, restaurant FROM orders WHERE banner_id = %s AND status = 'pending'",
                            (banner_id,)
                        )
                        pending_orders = cur.fetchall()
                        has_restaurant = True
                    except pymysql.MySQLError as e:
                        if "Unknown column 'restaurant'" in str(e):
                            cur.execute(
                                "SELECT order_no, item FROM orders WHERE banner_id = %s AND status = 'pending'",
                                (banner_id,)
                            )
                            pending_orders = cur.fetchall()
                            has_restaurant = False
                            # Add restaurant field for consistency
                            for order in pending_orders:
                                order['restaurant'] = 'N/A'
                        else:
                            raise e
                    
                    if pending_orders:
                        # Update all pending orders to fulfilled
                        cur.execute(
                            "UPDATE orders SET status = 'fulfilled' WHERE banner_id = %s AND status = 'pending'",
                            (banner_id,)
                        )
                        conn.commit()
                        
                        # Get order details for response
                        items = [f"{order['item']} from {order['restaurant']}" for order in pending_orders]
                        order_numbers = [order['order_no'] for order in pending_orders]
                        
                        return jsonify({
                            'success': True,
                            'order_fulfilled': True,
                            'banner_id': banner_id,
                            'order_numbers': order_numbers,
                            'items': items,
                            'message': f'Fulfilled {len(pending_orders)} order(s)'
                        }), 200
                    else:
                        return jsonify({
                            'success': True,
                            'order_fulfilled': False,
                            'banner_id': banner_id,
                            'message': 'No pending orders found'
                        }), 200
                        
                conn.close()
                
            except Exception as e:
                print(f"[ERROR] Database error in order processing: {e}")
                return jsonify({'error': 'Database error'}), 500
        else:
            return jsonify({'error': 'Database not configured'}), 503
            
    except Exception as e:
        print(f"[ERROR] Failed to process order: {e}")
        return jsonify({'error': 'Failed to process order'}), 500


@app.route('/admin/orders', methods=['GET'])
def get_admin_orders():
    """Return recent orders from DB (preferred) or from in-memory list as fallback."""
    recent = []
    # Try DB first
    if all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # First try with restaurant column
                try:
                    cur.execute("SELECT order_no, banner_id, item, restaurant, status, ts FROM orders ORDER BY order_no DESC LIMIT 50;")
                    rows = cur.fetchall()
                    has_restaurant = True
                except pymysql.MySQLError as e:
                    if "Unknown column 'restaurant'" in str(e):
                        print("[WARN] Restaurant column not found, querying without it...")
                        cur.execute("SELECT order_no, banner_id, item, status, ts FROM orders ORDER BY order_no DESC LIMIT 50;")
                        rows = cur.fetchall()
                        has_restaurant = False
                    else:
                        raise e
                
                for r in rows:
                    ts = r.get('ts')
                    try:
                        ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(ts))) if ts else ''
                    except Exception:
                        ts_str = str(ts)
                    recent.append({
                        'order_no': r.get('order_no'),
                        'banner_id': r.get('banner_id'),
                        'name': None,
                        'item': r.get('item'),
                        'restaurant': r.get('restaurant', 'N/A') if has_restaurant else 'N/A',
                        'status': r.get('status'),
                        'timestamp': ts_str,
                    })
        except Exception as e:
            print(f"[WARN] Failed to query orders table: {e}. Falling back to in-memory orders.")
        finally:
            try:
                if 'conn' in locals() and conn:
                    conn.close()
            except Exception:
                pass

    # Fallback to in-memory orders if DB didn't produce results
    if not recent:
        for o in reversed(orders[-50:]):
            ts = o.get('timestamp')
            ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(float(ts))) if ts else ''
            recent.append({
                'order_no': o.get('order_no'),
                'banner_id': o.get('user', {}).get('banner_id'),
                'name': o.get('user', {}).get('name'),
                'item': o.get('items')[0] if o.get('items') else None,
                'restaurant': o.get('restaurant'),
                'status': o.get('status'),
                'timestamp': ts_str,
            })

    return jsonify({'orders': recent})

def log_verification(name, matched, confidence, location=None):
    """Log a face verification attempt."""
    verification_entry = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'name': name,
        'matched': matched,
        'confidence': confidence,
        'location': location
    }
    verification_log.append(verification_entry)
    # Keep only last 1000 entries
    if len(verification_log) > 1000:
        verification_log.pop(0)

def register_mdns_service(port=5001):
    if not ZEROCONF_AVAILABLE:
        print("[INFO] Zeroconf not available - skipping mDNS service registration")
        return
    
    from zeroconf import Zeroconf, ServiceInfo
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


@app.route('/api/cleanup_orders', methods=['POST'])
def cleanup_orders():
    """Clean up fulfilled orders from the database."""
    try:
        data = request.get_json() or {}
        action = data.get('action', '')
        
        if action != 'delete_fulfilled':
            return jsonify({'error': 'Invalid action'}), 400
            
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Delete orders marked as 'fulfilled' or 'completed'
            cur.execute("""
                DELETE FROM orders 
                WHERE status IN ('fulfilled', 'completed', 'delivered')
            """)
            
            deleted_count = cur.rowcount
            conn.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Deleted {deleted_count} fulfilled order(s)'
            })
            
    except Exception as e:
        print(f"[ERROR] Failed to cleanup orders: {e}")
        return jsonify({'error': 'Failed to cleanup orders'}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()


if __name__ == '__main__':
    mdns = register_mdns_service(port=5001)
    # The initialization is now handled during app startup
    app.run(host='0.0.0.0', port=5001, debug=_run_debug_mode)