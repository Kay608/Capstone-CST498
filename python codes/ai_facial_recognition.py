import argparse
from typing import Optional, Callable
from contextlib import suppress
import sys
import cv2
import face_recognition
import time
import os
import pymysql  # For MySQL handling
import numpy as np  # To deserialize BLOBs back to numpy arrays
from pathlib import Path
from dotenv import load_dotenv
import requests
import json

# Ensure .env files are loaded before reading DB configuration
_ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(_ROOT_DIR / ".env", override=False)
load_dotenv(_ROOT_DIR / "flask_api" / ".env", override=False)

# Ensure .env is loaded for DB credentials
from dotenv import load_dotenv
from pathlib import Path

# Load env from project root and Flask subfolder (mirror app.py behavior)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / "flask_api" / ".env", override=False)

# Ensure project root modules are importable when running from nested directories
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load any credentials stored at the repository root (common on the Pi deployment)
load_dotenv(PROJECT_ROOT / ".env", override=False)
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except Exception:
    Picamera2 = None  # type: ignore
    PICAMERA_AVAILABLE = False

# Import robot hardware interface
try:
    from robot_navigation.hardware_interface import (
        create_hardware_interface,
        HardwareInterface,
        detect_robot_hardware,
    )
    ROBOT_AVAILABLE = True
    ROBOT_HARDWARE_PRESENT = detect_robot_hardware()
except ImportError:
    print("[WARN] Could not import robot hardware interface. Robot integration disabled.")
    ROBOT_AVAILABLE = False
    ROBOT_HARDWARE_PRESENT = False

# --- JawsDB (MySQL) Configuration ---
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

# --- Flask App Configuration for Remote Logging ---
# Flask app URL for logging verifications
FLASK_APP_URL = "http://10.202.65.203:5001"

# --- Recognition Configuration ---
MATCH_THRESHOLD = 0.65
FRAME_SKIP = 3  # Process every Nth frame for performance on Pi
FACE_DETECTION_MODEL = 'hog'  # 'hog' is faster on CPU, 'cnn' is more accurate but needs GPU
FRAME_SCALE = 0.5  # Downsample frames for faster processing
DB_REFRESH_INTERVAL = 300  # Refresh encodings from DB every 5 minutes
STATUS_LOG_INTERVAL = 5  # Seconds between "no activity" status logs

# Global state
robot_interface = None
frame_count = 0
known_encodings = []
known_names = []

# Face tracking for stable display
face_tracking = {}  # Dictionary to track face positions and recognition state
FACE_PERSISTENCE_TIME = 3.0  # Keep green square for 3 seconds after last recognition
FACE_POSITION_TOLERANCE = 50  # Pixels tolerance for face position matching


def has_display() -> bool:
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY"))
    return True


def configure_camera_stream(cam: cv2.VideoCapture) -> None:
    """Apply preferred capture settings; ignore failures silently."""
    if not cam:
        return
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cam.set(cv2.CAP_PROP_FPS, 15)
    if sys.platform.startswith("linux"):
        # Many Pi camera stacks prefer MJPG/YUYV when accessed via V4L2
        for fourcc in ("MJPG", "YUYV"):
            code = cv2.VideoWriter_fourcc(*fourcc)
            if cam.set(cv2.CAP_PROP_FOURCC, code):
                break


def open_local_camera() -> Optional[cv2.VideoCapture]:
    """Attempt to open a usable camera across common Pi/Linux backends."""
    candidates = []
    is_linux = sys.platform.startswith("linux")

    if is_linux:
        candidates.append((0, cv2.CAP_V4L2, "index=0 (CAP_V4L2)"))
    candidates.append((0, cv2.CAP_ANY, "index=0 (default backend)"))

    if is_linux:
        for dev in ("/dev/video0", "/dev/video1", "/dev/video2"):
            if Path(dev).exists():
                candidates.append((dev, None, dev))

    candidates.append((1, cv2.CAP_ANY, "index=1 (fallback)"))

    for source, backend, label in candidates:
        try:
            if backend is None or isinstance(source, str):
                cam = cv2.VideoCapture(source)
            else:
                cam = cv2.VideoCapture(source, backend)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Exception opening camera via {label}: {exc}")
            continue

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            continue

        configure_camera_stream(cam)

        # Probe a few frames to ensure this source actually delivers images
        for _ in range(3):
            ret, frame = cam.read()
            if ret and frame is not None:
                print(f"[INFO] Camera opened via {label}")
                return cam
            time.sleep(0.1)

        print(f"[WARN] Camera via {label} opened but returned empty frames; trying fallback.")
        cam.release()

    print("[ERROR] Unable to open camera using available backends.")
    return None


class CameraSource:
    def __init__(self) -> None:
        self._picam = None
        self._video = None

    def start(self) -> bool:
        if PICAMERA_AVAILABLE and sys.platform.startswith("linux"):
            try:
                self._picam = Picamera2()
                config = self._picam.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
                self._picam.configure(config)
                self._picam.start()
                print("[INFO] Camera opened via Picamera2")
                return True
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Picamera2 unavailable: {exc}")
                self._picam = None

        self._video = open_local_camera()
        return self._video is not None

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        if self._picam:
            try:
                frame = self._picam.capture_array()
                if frame is None:
                    return False, None
                if frame.ndim == 3:
                    if frame.shape[2] == 4:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    elif frame.shape[2] == 3:
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] Picamera2 capture failed: {exc}")
                return False, None

        if self._video:
            return self._video.read()

        return False, None

    def release(self) -> None:
        if self._picam:
            with suppress(Exception):
                self._picam.stop()
            with suppress(Exception):
                self._picam.close()
            self._picam = None
        if self._video:
            with suppress(Exception):
                self._video.release()
            self._video = None

def get_db_connection():
    """Return a new database connection for each call."""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        return conn
    except pymysql.MySQLError as exc:
        print(f"[ERROR] Failed to connect to MySQL database: {exc}")
        raise

def save_encodings_cache(encodings, names):
    """Save encodings to local cache file for offline use."""
    cache_dir = BASE_DIR / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "face_encodings.npz"
    
    try:
        np.savez_compressed(
            cache_file,
            encodings=np.array(encodings),
            names=np.array(names, dtype=object)
        )
        print(f"[INFO] Cached {len(names)} face(s) to {cache_file}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save cache: {e}")
        return False


def load_encodings_cache():
    """Load encodings from local cache file."""
    cache_file = BASE_DIR / "cache" / "face_encodings.npz"
    
    if not cache_file.exists():
        return None, None
    
    try:
        data = np.load(cache_file, allow_pickle=True)
        encodings = list(data['encodings'])
        names = list(data['names'])
        print(f"[INFO] Loaded {len(names)} face(s) from local cache")
        return encodings, names
    except Exception as e:
        print(f"[ERROR] Failed to load cache: {e}")
        return None, None


def load_encodings_from_db():
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Database environment variables not set. Trying local cache...")
        cached_encodings, cached_names = load_encodings_cache()
        if cached_encodings is not None:
            return cached_encodings, cached_names
        print("[WARNING] No local cache available. Starting with empty database.")
        return [], []
    
    conn = None
    known_encodings = []
    known_names = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT banner_id, first_name, last_name, encoding FROM users;")
            rows = cur.fetchall()
            for row in rows:
                display_name = f"{row['first_name']} {row['last_name']}".strip()
                banner_id = row['banner_id']
                encoding_bytes = row['encoding']
                # Deserialize with robust dtype handling (try float64, then float32)
                encoding = None
                try:
                    arr = np.frombuffer(encoding_bytes, dtype=np.float64)
                    if arr.size == 128:
                        encoding = arr
                except Exception:
                    encoding = None

                if encoding is None:
                    try:
                        arr32 = np.frombuffer(encoding_bytes, dtype=np.float32)
                        if arr32.size == 128:
                            encoding = arr32.astype(np.float64)
                    except Exception:
                        encoding = None

                if encoding is None:
                    # Last resort: try interpreting raw bytes then warn
                    try:
                        arr_any = np.frombuffer(encoding_bytes, dtype=np.float64)
                        if arr_any.size > 0:
                            encoding = arr_any
                    except Exception:
                        print(f"[WARN] Failed to deserialize encoding for banner_id={banner_id}")
                        continue

                # Ensure final shape is 128-length vector
                if encoding.size != 128:
                    print(f"[WARN] Encoding for {banner_id} has unexpected size {encoding.size}; skipping")
                    continue

                known_encodings.append(encoding)
                # Store both banner ID and display name for easier debugging
                known_names.append((banner_id, display_name))
        print(f"[INFO] Loaded {len(known_names)} known face(s) from MySQL.")
        
        # Save to local cache for offline use
        if known_encodings:
            save_encodings_cache(known_encodings, known_names)
            
    except pymysql.MySQLError as exc:
        print(f"[ERROR] Error loading encodings from MySQL: {exc}")
        print("[INFO] Attempting to use local cache...")
        cached_encodings, cached_names = load_encodings_cache()
        if cached_encodings is not None:
            return cached_encodings, cached_names
        print("[WARNING] No cache available. Starting with empty database.")
    finally:
        if conn:
            conn.close()
    return known_encodings, known_names

def refresh_known_faces(force_online=False) -> None:
    """
    Refresh known faces from database or cache.
    
    Args:
        force_online: If True, skip cache and always try database
    """
    global known_encodings, known_names
    
    if force_online:
        print("[INFO] Forcing online database refresh...")
        known_encodings, known_names = load_encodings_from_db()
    else:
        # Try database first, fall back to cache on failure
        known_encodings, known_names = load_encodings_from_db()


refresh_known_faces()


def match_face_encoding(encoding):
    if not known_encodings:
        return "Unknown", False, 0.0, None

    distances = face_recognition.face_distance(known_encodings, encoding)
    min_distance = float(min(distances))
    best_match_idx = distances.tolist().index(min_distance)
    confidence = max(0.0, 1.0 - min_distance)

    if min_distance < MATCH_THRESHOLD:
        banner_id, display_name = known_names[best_match_idx]
        name = display_name or banner_id
        return name, True, confidence, banner_id

    return "Unknown", False, confidence, None


def analyze_frame(frame, skip_frame_check=False):
    """Analyze frame for faces with optional frame skipping for performance."""
    global frame_count
    frame_count += 1
    
    # Skip frames for performance (unless explicitly disabled)
    if not skip_frame_check and frame_count % FRAME_SKIP != 0:
        return []
    
    # Downsample for faster processing
    small_frame = cv2.resize(frame, (0, 0), fx=FRAME_SCALE, fy=FRAME_SCALE)
    rgb = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    
    # Use HOG model for faster CPU-based detection
    boxes = face_recognition.face_locations(rgb, model=FACE_DETECTION_MODEL)
    encodings = face_recognition.face_encodings(rgb, boxes)

    results = []
    for encoding, box in zip(encodings, boxes):
        name, matched, confidence, banner_id = match_face_encoding(encoding)
        # Scale box coordinates back to original frame size
        top, right, bottom, left = box
        top = int(top / FRAME_SCALE)
        right = int(right / FRAME_SCALE)
        bottom = int(bottom / FRAME_SCALE)
        left = int(left / FRAME_SCALE)
        
        results.append({
            "name": name,
            "matched": matched,
            "box": (top, right, bottom, left),
            "confidence": confidence,
            "banner_id": banner_id,
        })
    return results


def annotate_frame(frame, force_process: bool = False):
    """Enhanced annotation with persistent face tracking for stable green squares."""
    global face_tracking
    
    annotated = frame.copy()
    results = analyze_frame(frame, skip_frame_check=force_process)
    current_time = time.time()

    # Update face tracking with current detections
    current_faces = {}
    
    for result in results:
        top, right, bottom, left = result["box"]
        face_center = ((left + right) // 2, (top + bottom) // 2)
        
        # Find if this face matches an existing tracked face
        matched_track_id = None
        for track_id, tracked_face in face_tracking.items():
            tracked_center = tracked_face['center']
            distance = ((face_center[0] - tracked_center[0])**2 + (face_center[1] - tracked_center[1])**2)**0.5
            
            if distance < FACE_POSITION_TOLERANCE:
                matched_track_id = track_id
                break
        
        # Update or create face tracking
        if matched_track_id:
            track_id = matched_track_id
        else:
            track_id = f"face_{current_time}_{face_center[0]}_{face_center[1]}"
        
        current_faces[track_id] = {
            'box': (top, right, bottom, left),
            'center': face_center,
            'name': result['name'],
            'matched': result['matched'],
            'confidence': result['confidence'],
            'last_seen': current_time,
            'first_recognized': face_tracking.get(track_id, {}).get('first_recognized', current_time if result['matched'] else None)
        }
        
        # If this face was just recognized, mark the time
        if result['matched'] and not face_tracking.get(track_id, {}).get('matched', False):
            current_faces[track_id]['first_recognized'] = current_time

    # Remove old face tracks that haven't been seen recently
    face_tracking = {track_id: data for track_id, data in face_tracking.items() 
                    if current_time - data['last_seen'] < FACE_PERSISTENCE_TIME}
    
    # Update face tracking with current faces
    face_tracking.update(current_faces)

    # Draw all tracked faces with persistent recognition state
    for track_id, tracked_face in face_tracking.items():
        top, right, bottom, left = tracked_face['box']
        
        # Determine if we should show this face as recognized
        # Show as recognized if: currently matched OR was recognized recently
        time_since_last_seen = current_time - tracked_face['last_seen']
        time_since_recognized = float('inf')
        
        if tracked_face['first_recognized']:
            time_since_recognized = current_time - tracked_face['first_recognized']
        
        # Show green if currently matched OR was recently recognized and still visible
        show_as_recognized = (tracked_face['matched'] or 
                            (tracked_face['first_recognized'] and 
                             time_since_last_seen < 0.5 and 
                             time_since_recognized < FACE_PERSISTENCE_TIME))
        
        if show_as_recognized:
            # Green thick border and overlay for recognized faces
            color = (0, 255, 0)  # Green
            thickness = 4
            label = f"✓ {tracked_face['name']} ({tracked_face['confidence']:.2f})"
            
            # Add semi-transparent green overlay
            overlay = annotated.copy()
            cv2.rectangle(overlay, (left, top), (right, bottom), color, -1)
            cv2.addWeighted(annotated, 0.85, overlay, 0.15, 0, annotated)
            
            # Add green glow effect
            glow_overlay = annotated.copy()
            cv2.rectangle(glow_overlay, (left-2, top-2), (right+2, bottom+2), color, -1)
            cv2.addWeighted(annotated, 0.95, glow_overlay, 0.05, 0, annotated)
        else:
            # Red border for unrecognized faces
            color = (0, 0, 255)  # Red
            thickness = 2
            label = f"Unknown ({tracked_face['confidence']:.2f})"
        
        # Draw the rectangle border
        cv2.rectangle(annotated, (left, top), (right, bottom), color, thickness)
        
        # Draw label with background for better visibility
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        label_bg_top = max(top - label_size[1] - 15, 0)
        cv2.rectangle(annotated, (left, label_bg_top), (left + label_size[0] + 10, top), color, -1)
        cv2.putText(annotated, label, (left + 5, top - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Add status information at the top of the frame
    status_text = f"Monitoring: {len(known_encodings)} faces | Tracking: {len(face_tracking)} | Flask: {FLASK_APP_URL.split('/')[-1]}"
    cv2.putText(annotated, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(annotated, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    return annotated, results

def log_verification_http(name, matched, confidence, location=None):
    """
    Log verification to Flask app via HTTP request.
    Falls back gracefully if Flask app is not reachable.
    """
    try:
        print(f"[HTTP] Attempting to log verification to {FLASK_APP_URL}/api/log_verification")
        print(f"[HTTP] Data: name={name}, matched={matched}, confidence={confidence}")
        
        data = {
            'name': name,
            'matched': matched,
            'confidence': confidence,
            'location': location or 'Raspberry Pi'
        }
        
        response = requests.post(
            f"{FLASK_APP_URL}/api/log_verification",
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"[HTTP] ✅ Logged verification: {name} ({'✓' if matched else '✗'})")
        else:
            print(f"[HTTP] ❌ Failed to log verification: HTTP {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"[HTTP] ❌ Could not reach Flask app for logging: {e}")
    except Exception as e:
        print(f"[ERROR] Verification logging error: {e}")


def process_order_fulfillment(banner_id, display_name):
    """
    Check for pending orders and mark as fulfilled when face is recognized.
    """
    try:
        print(f"[HTTP] Processing order fulfillment for {display_name} ({banner_id})")
        print(f"[HTTP] Sending request to {FLASK_APP_URL}/api/process_order")
        
        data = {
            'banner_id': banner_id,
            'action': 'fulfill'
        }
        
        response = requests.post(
            f"{FLASK_APP_URL}/api/process_order",
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('order_fulfilled'):
                print(f"[HTTP] ✅ Order fulfilled for {display_name} ({banner_id})")
                print(f"[HTTP] Items: {result.get('items', 'N/A')}")
                return True
            else:
                print(f"[ORDER] No pending orders found for {banner_id}")
                return False
        else:
            print(f"[WARN] Failed to process order: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Could not reach Flask app for order processing: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Order processing error: {e}")
        return False


def recognize_face(location=None, use_robot_camera=False):
    """
    Recognize a face from the camera. Returns the recognized name or None.
    This function can be called from other scripts (e.g., Flask backend).
    
    Args:
        location: Optional location string for logging
        use_robot_camera: If True, use robot's hardware interface camera
    """
    # Use HTTP-based logging instead of direct import
    location = location or "Raspberry Pi"
    
    # Get frame from robot camera or local camera
    if use_robot_camera and robot_interface and robot_interface.is_available():
        frame = robot_interface.get_camera_frame()
        if frame is None:
            print("[ERROR] Failed to get frame from robot camera.")
            return None
    else:
        camera = CameraSource()
        if not camera.start():
            print("[ERROR] Camera not accessible.")
            return None
        ret, frame = camera.read()
        camera.release()
        if not ret or frame is None:
            print("[ERROR] Failed to grab frame from camera.")
            return None
    
    results = analyze_frame(frame, skip_frame_check=True)

    for result in results:
        if result["matched"]:
            print(f"[ACCESS GRANTED] Recognized: {result['name']} ({result['confidence']:.2f})")
            log_verification_http(result["name"], True, result["confidence"], location)
            
            # Process order fulfillment if we have a banner_id
            if result["banner_id"]:
                process_order_fulfillment(result["banner_id"], result["name"])
            
            return result["name"]
        else:
            log_verification_http("Unknown", False, result["confidence"], location)

    if not known_encodings:
        print("[ACCESS DENIED] No known faces in database.")
    elif results:
        for result in results:
            print(f"[ACCESS DENIED] Face not recognized (confidence {result['confidence']:.2f}).")
    else:
        print("[INFO] No face detected in frame.")
        log_verification_http("No Face Detected", False, 0.0, location)
    return None

def robot_action_on_recognition(result: dict) -> None:
    """Execute robot actions when a face is recognized."""
    if not robot_interface or not robot_interface.is_available():
        print("[ROBOT] Robot interface not available - action skipped")
        return
    
    try:
        print(f"[ROBOT] Unlocking compartment for {result['name']}")
        
        # Play success buzz sound for face recognition
        try:
            if hasattr(robot_interface, 'robot') and robot_interface.robot:
                print("[ROBOT] Playing recognition success sound")
                robot_interface.robot.Buzz_Success()  # Play success pattern
            else:
                print("[ROBOT] Robot buzzer not available - sound skipped")
        except Exception as e:
            print(f"[ROBOT] Buzzer error: {e}")
        
        # Center camera on face for confirmation
        robot_interface.set_camera_servo(90)  # Center position
        time.sleep(0.5)
        
        # Add your robot-specific actions here
        # Examples:
        # - Open compartment servo
        # - Flash LED indicator
        # - Play audio confirmation
        # - Update delivery status in database
        
        print("[ROBOT] Compartment unlocked - awaiting pickup")
        
    except Exception as e:
        print(f"[ERROR] Robot action failed: {e}")


def run_camera_loop(headless=False, use_robot: Optional[bool] = None, callback: Optional[Callable] = None) -> None:
    """
    Main camera loop for facial recognition.
    
    Args:
        headless: If True, don't show GUI windows (for Pi deployment)
        use_robot: Force robot usage (True), disable robot (False), or auto (None)
        callback: Optional callback function(status, result) called on recognition events
    """
    global robot_interface, ROBOT_HARDWARE_PRESENT
    
    # Decide whether to enable robot integration
    active_robot = False
    robot_interface = None

    if use_robot is None:
        active_robot = ROBOT_AVAILABLE and ROBOT_HARDWARE_PRESENT
        if active_robot:
            print("[INFO] Robot hardware detected - enabling robot integration")
        elif ROBOT_AVAILABLE:
            print("[INFO] Robot hardware not detected - running camera-only mode")
    elif use_robot and not ROBOT_AVAILABLE:
        print("[WARN] Robot interface module unavailable - running without robot hardware")
    else:
        active_robot = bool(use_robot)

    if active_robot and ROBOT_AVAILABLE:
        robot_interface = create_hardware_interface(use_simulation=False)
        if robot_interface.is_available():
            print("[INFO] Robot hardware interface ready")
            ROBOT_HARDWARE_PRESENT = True
        else:
            print("[WARN] Robot hardware requested but unavailable - falling back to local camera")
            robot_interface = None
            active_robot = False
            ROBOT_HARDWARE_PRESENT = False
    
    use_robot = active_robot
    
    # Initialize camera
    camera_source: Optional[CameraSource] = None
    if use_robot and robot_interface and robot_interface.is_available():
        print("[INFO] Using robot camera interface")
    else:
        camera_source = CameraSource()
        if not camera_source.start():
            print("[ERROR] Camera not accessible.")
            return
    
    mode_str = "headless" if headless else "GUI"
    print(f"[INFO] Facial recognition active ({mode_str} mode). Press Ctrl+C to quit.")
    
    last_refresh = time.time()
    last_recognition_time = 0
    recognition_cooldown = 3.0  # Seconds between recognitions
    last_status_log = 0.0
    
    try:
        while True:
            # Periodic database refresh (tries DB, falls back to cache)
            if time.time() - last_refresh > DB_REFRESH_INTERVAL:
                print("[INFO] Attempting to refresh face encodings from database...")
                refresh_known_faces()
                last_refresh = time.time()
            
            # Capture frame
            if use_robot and robot_interface and robot_interface.is_available():
                frame = robot_interface.get_camera_frame()
                if frame is None:
                    print("[ERROR] Failed to get frame from robot")
                    time.sleep(0.1)
                    continue
            else:
                ret, frame = camera_source.read() if camera_source else (False, None)
                if not ret or frame is None:
                    print("[ERROR] Failed to grab frame from camera.")
                    time.sleep(0.1)
                    continue
            
            # Analyze frame
            results = analyze_frame(frame)
            
            # Process results
            current_time = time.time()
            for result in results:
                if result["matched"] and (current_time - last_recognition_time) > recognition_cooldown:
                    print(f"[ACCESS GRANTED] Recognized: {result['name']} ({result['confidence']:.2f})")
                    
                    # Log verification to Flask app via HTTP
                    log_verification_http(result["name"], True, result["confidence"], "Raspberry Pi")
                    
                    # Process order fulfillment if we have a banner_id
                    if result["banner_id"]:
                        process_order_fulfillment(result["banner_id"], result["name"])
                    
                    # Execute robot actions
                    robot_action_on_recognition(result)
                    
                    # Call custom callback if provided
                    if callback:
                        callback('granted', result)
                    
                    last_recognition_time = current_time
                    last_status_log = current_time
                    
                elif not result["matched"] and len(known_encodings) > 0:
                    # Only log unrecognized if we have faces in DB
                    if (current_time - last_recognition_time) > recognition_cooldown:
                        print(f"[ACCESS DENIED] Face not recognized (confidence {result['confidence']:.2f})")
                        
                        # Play alert sound for unrecognized face
                        try:
                            if robot_interface and robot_interface.is_available() and hasattr(robot_interface, 'robot') and robot_interface.robot:
                                print("[ROBOT] Playing access denied sound")
                                robot_interface.robot.Buzz_Alert()  # Play alert pattern for denied access
                            else:
                                print("[ROBOT] Robot buzzer not available for access denied sound")
                        except Exception as e:
                            print(f"[ROBOT] Buzzer error on access denied: {e}")
                        
                        # Log failed verification to Flask app via HTTP
                        log_verification_http("Unknown", False, result["confidence"], "Raspberry Pi")
            
            # Display frame (only if not headless)
            if not headless:
                annotated, _ = annotate_frame(frame)
                cv2.imshow("Face Recognition", annotated)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC key
                    break
            else:
                # Small delay to prevent CPU overload in headless mode
                time.sleep(0.05)

            if not results and (current_time - last_status_log) > STATUS_LOG_INTERVAL:
                print("[INFO] No face detected in frame.")
                last_status_log = current_time
                
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down facial recognition...")
        if robot_interface and robot_interface.is_available():
            with suppress(Exception):
                robot_interface.stop()
    finally:
        if camera_source:
            camera_source.release()
        if not headless:
            cv2.destroyAllWindows()
        if robot_interface:
            robot_interface.stop()
            robot_interface = None


def capture_snapshot(output_path: Optional[str] = None) -> None:
    camera = CameraSource()
    if not camera.start():
        print("[ERROR] Camera not accessible.")
        return

    ret, frame = camera.read()
    camera.release()
    if not ret or frame is None:
        print("[ERROR] Failed to grab frame from camera.")
        return

    annotated, results = annotate_frame(frame, force_process=True)

    if not results:
        print("[INFO] No face detected in frame.")
    else:
        for result in results:
            status = "granted" if result["matched"] else "denied"
            print(f"[INFO] Access {status}: {result['name']} ({result['confidence']:.2f})")

    if has_display():
        cv2.imshow("Face Recognition Snapshot", annotated)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("[INFO] Display not available; skipping preview window.")

    if output_path:
        saved = cv2.imwrite(output_path, annotated)
        if saved:
            print(f"[INFO] Snapshot saved to {output_path}")
        else:
            print(f"[ERROR] Failed to write snapshot to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Facial recognition for robot delivery system.")
    parser.add_argument("--snapshot", action="store_true", 
                       help="Capture a single annotated frame from the camera.")
    parser.add_argument("--output", 
                       help="Optional path to save the annotated snapshot when using --snapshot.")
    parser.add_argument("--headless", action="store_true",
                       help="Run in headless mode (no GUI display) for Raspberry Pi deployment.")
    robot_group = parser.add_mutually_exclusive_group()
    robot_group.add_argument("--force-robot", action="store_true",
                            help="Force enable robot hardware, overriding automatic detection.")
    robot_group.add_argument("--no-robot", action="store_true",
                            help="Force disable robot hardware, even if detected.")
    parser.add_argument("--model", choices=['hog', 'cnn'], default='hog',
                       help="Face detection model: 'hog' (faster, CPU) or 'cnn' (accurate, GPU).")
    parser.add_argument("--threshold", type=float, default=0.65,
                       help="Face matching confidence threshold (0.0-1.0, default: 0.65).")
    parser.add_argument("--offline", action="store_true",
                       help="Run in offline mode (use local cache only, no database connection).")
    return parser.parse_args()


def main() -> None:
    global FACE_DETECTION_MODEL, MATCH_THRESHOLD, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
    
    args = parse_args()
    
    # Apply command-line configuration
    FACE_DETECTION_MODEL = args.model
    MATCH_THRESHOLD = args.threshold
    
    print(f"[CONFIG] Detection model: {FACE_DETECTION_MODEL}")
    print(f"[CONFIG] Match threshold: {MATCH_THRESHOLD}")
    headless_mode = args.headless
    if not headless_mode and not has_display():
        print("[WARN] No graphical display detected; enabling headless mode.")
        headless_mode = True

    if args.force_robot:
        robot_preference: Optional[bool] = True
    elif args.no_robot:
        robot_preference = False
    else:
        robot_preference = None

    if robot_preference is None:
        detected_status = "detected" if ROBOT_HARDWARE_PRESENT else "not detected"
        robot_config_msg = f"auto ({detected_status})"
    elif robot_preference:
        robot_config_msg = "forced-on"
    else:
        robot_config_msg = "disabled"

    print(f"[CONFIG] Headless mode: {headless_mode}")
    print(f"[CONFIG] Robot integration: {robot_config_msg}")
    print(f"[CONFIG] Offline mode: {args.offline}")
    
    # If offline mode, disable database connection
    if args.offline:
        print("[INFO] Offline mode enabled - using local cache only")
        DB_HOST = DB_USER = DB_PASSWORD = DB_NAME = None
    
    # Load face encodings (from database or cache)
    refresh_known_faces()

    if args.output and not args.snapshot:
        print("[WARNING] --output is ignored unless --snapshot is specified.")

    if args.snapshot:
        capture_snapshot(args.output)
    else:
        run_camera_loop(headless=headless_mode, use_robot=robot_preference)


if __name__ == "__main__":
    main()
