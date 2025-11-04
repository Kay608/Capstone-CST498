import argparse
from typing import Optional, Callable
import sys
import cv2
import face_recognition
import time
import os
import pymysql  # For MySQL handling
import numpy as np  # To deserialize BLOBs back to numpy arrays

# Ensure .env is loaded for DB credentials
from dotenv import load_dotenv
from pathlib import Path

# Load env from project root and Flask subfolder (mirror app.py behavior)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / "flask_api" / ".env", override=False)

# Import robot hardware interface
try:
    from robot_navigation.hardware_interface import create_hardware_interface, HardwareInterface
    ROBOT_AVAILABLE = True
except ImportError:
    print("[WARN] Could not import robot hardware interface. Robot integration disabled.")
    ROBOT_AVAILABLE = False

# --- JawsDB (MySQL) Configuration ---
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

# --- Recognition Configuration ---
MATCH_THRESHOLD = 0.65
FRAME_SKIP = 3  # Process every Nth frame for performance on Pi
FACE_DETECTION_MODEL = 'hog'  # 'hog' is faster on CPU, 'cnn' is more accurate but needs GPU
FRAME_SCALE = 0.5  # Downsample frames for faster processing
DB_REFRESH_INTERVAL = 300  # Refresh encodings from DB every 5 minutes

# Global state
robot_interface = None
frame_count = 0

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
        return "Unknown", False, 0.0

    distances = face_recognition.face_distance(known_encodings, encoding)
    min_distance = float(min(distances))
    best_match_idx = distances.tolist().index(min_distance)
    confidence = max(0.0, 1.0 - min_distance)

    if min_distance < MATCH_THRESHOLD:
        banner_id, display_name = known_names[best_match_idx]
        name = display_name or banner_id
        return name, True, confidence

    return "Unknown", False, confidence


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
        name, matched, confidence = match_face_encoding(encoding)
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
        })
    return results


def annotate_frame(frame):
    annotated = frame.copy()
    results = analyze_frame(frame)

    for result in results:
        top, right, bottom, left = result["box"]
        color = (0, 255, 0) if result["matched"] else (0, 0, 255)
        label = result["name"]
        if result["confidence"] > 0:
            label = f"{label} ({result['confidence']:.2f})"
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
        cv2.putText(annotated, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return annotated, results

def recognize_face(location=None, use_robot_camera=False):
    """
    Recognize a face from the camera. Returns the recognized name or None.
    This function can be called from other scripts (e.g., Flask backend).
    
    Args:
        location: Optional location string for logging
        use_robot_camera: If True, use robot's hardware interface camera
    """
    try:
        from flask_api.app import log_verification
    except ImportError:
        log_verification = None  # Flask not available, skip logging
    
    # Get frame from robot camera or local camera
    if use_robot_camera and robot_interface and robot_interface.is_available():
        frame = robot_interface.get_camera_frame()
        if frame is None:
            print("[ERROR] Failed to get frame from robot camera.")
            return None
    else:
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            print("[ERROR] Camera not accessible.")
            return None
        ret, frame = cam.read()
        cam.release()
        if not ret or frame is None:
            print("[ERROR] Failed to grab frame from camera.")
            return None
    
    results = analyze_frame(frame, skip_frame_check=True)

    for result in results:
        if result["matched"]:
            print(f"[ACCESS GRANTED] Recognized: {result['name']} ({result['confidence']:.2f})")
            if log_verification:
                log_verification(result["name"], True, result["confidence"], location)
            return result["name"]
        else:
            if log_verification:
                log_verification("Unknown", False, result["confidence"], location)

    if not known_encodings:
        print("[ACCESS DENIED] No known faces in database.")
    elif results:
        for result in results:
            print(f"[ACCESS DENIED] Face not recognized (confidence {result['confidence']:.2f}).")
    else:
        print("[INFO] No face detected in frame.")
        if log_verification:
            log_verification("No Face Detected", False, 0.0, location)
    return None

def robot_action_on_recognition(result: dict) -> None:
    """Execute robot actions when a face is recognized."""
    if not robot_interface or not robot_interface.is_available():
        print("[ROBOT] Robot interface not available - action skipped")
        return
    
    try:
        print(f"[ROBOT] Unlocking compartment for {result['name']}")
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


def run_camera_loop(headless=False, use_robot=False, callback: Optional[Callable] = None) -> None:
    """
    Main camera loop for facial recognition.
    
    Args:
        headless: If True, don't show GUI windows (for Pi deployment)
        use_robot: If True, use robot's camera interface
        callback: Optional callback function(status, result) called on recognition events
    """
    global robot_interface
    
    # Initialize robot interface if requested
    if use_robot and ROBOT_AVAILABLE:
        robot_interface = create_hardware_interface(use_simulation=False)
        if not robot_interface.is_available():
            print("[WARN] Robot hardware not available, falling back to local camera")
            use_robot = False
    
    # Initialize camera
    if use_robot and robot_interface and robot_interface.is_available():
        print("[INFO] Using robot camera interface")
        cam = None
    else:
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            print("[ERROR] Camera not accessible.")
            return
        # Optimize camera settings for Pi
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cam.set(cv2.CAP_PROP_FPS, 15)
    
    mode_str = "headless" if headless else "GUI"
    print(f"[INFO] Facial recognition active ({mode_str} mode). Press Ctrl+C to quit.")
    
    last_refresh = time.time()
    last_recognition_time = 0
    recognition_cooldown = 3.0  # Seconds between recognitions
    
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
                ret, frame = cam.read()
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
                    
                    # Execute robot actions
                    robot_action_on_recognition(result)
                    
                    # Call custom callback if provided
                    if callback:
                        callback('granted', result)
                    
                    last_recognition_time = current_time
                    
                elif not result["matched"] and len(known_encodings) > 0:
                    # Only log unrecognized if we have faces in DB
                    if (current_time - last_recognition_time) > recognition_cooldown:
                        print(f"[ACCESS DENIED] Face not recognized (confidence {result['confidence']:.2f})")
            
            # Display frame (only if not headless)
            if not headless:
                annotated, _ = annotate_frame(frame)
                cv2.imshow("Face Recognition", annotated)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC key
                    break
            else:
                # Small delay to prevent CPU overload in headless mode
                time.sleep(0.05)
                
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down facial recognition...")
    finally:
        if cam:
            cam.release()
        if not headless:
            cv2.destroyAllWindows()
        if robot_interface:
            robot_interface.stop()


def capture_snapshot(output_path: Optional[str] = None) -> None:
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("[ERROR] Camera not accessible.")
        return

    ret, frame = cam.read()
    cam.release()
    if not ret or frame is None:
        print("[ERROR] Failed to grab frame from camera.")
        return

    annotated, results = annotate_frame(frame)

    if not results:
        print("[INFO] No face detected in frame.")
    else:
        for result in results:
            status = "granted" if result["matched"] else "denied"
            print(f"[INFO] Access {status}: {result['name']} ({result['confidence']:.2f})")

    cv2.imshow("Face Recognition Snapshot", annotated)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

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
    parser.add_argument("--robot", action="store_true",
                       help="Use robot's camera interface and enable robot actions.")
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
    print(f"[CONFIG] Headless mode: {args.headless}")
    print(f"[CONFIG] Robot integration: {args.robot}")
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
        run_camera_loop(headless=args.headless, use_robot=args.robot)


if __name__ == "__main__":
    main()
