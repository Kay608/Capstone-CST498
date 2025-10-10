import cv2
import face_recognition
import pickle
import time
import os
import pymysql  # For MySQL handling
import numpy as np  # To deserialize BLOBs back to numpy arrays

# --- JawsDB (MySQL) Configuration ---
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

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

def load_encodings_from_db():
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        print("[WARNING] Skipping load_encodings_from_db: database environment variables not fully set.")
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
                encoding = np.frombuffer(encoding_bytes, dtype=np.float64)
                known_encodings.append(encoding)
                # Store both banner ID and display name for easier debugging
                known_names.append((banner_id, display_name))
        print(f"[INFO] Loaded {len(known_names)} known face(s) from MySQL.")
    except pymysql.MySQLError as exc:
        print(f"[ERROR] Error loading encodings from MySQL: {exc}. Starting with empty database.")
    finally:
        if conn:
            conn.close()
    return known_encodings, known_names

known_encodings, known_names = load_encodings_from_db()

def recognize_face():
    """
    Recognize a face from the camera. Returns the recognized name or None.
    This function can be called from other scripts (e.g., Flask backend).
    """
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("[ERROR] Camera not accessible.")
        return None
    ret, frame = cam.read()
    cam.release()
    if not ret or frame is None:
        print("[ERROR] Failed to grab frame from camera.")
        return None
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)
    for encoding, box in zip(encodings, boxes):
        if known_encodings:
            distances = face_recognition.face_distance(known_encodings, encoding)
            min_distance = min(distances)
            best_match_idx = distances.tolist().index(min_distance)
            threshold = 0.65  # More lenient threshold
            if min_distance < threshold:
                banner_id, display_name = known_names[best_match_idx]
                name = display_name or banner_id
                print(f"[ACCESS GRANTED] Recognized: {name}")
                return name
            else:
                print("[ACCESS DENIED] Face not recognized.")
        else:
            print("[ACCESS DENIED] No known faces in database.")
    return None

if __name__ == "__main__":
    # Only run this block if the script is executed directly
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("[ERROR] Camera not accessible.")
        exit()
    print("[INFO] Facial recognition active. Press ESC to quit.")
    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            print("[ERROR] Failed to grab frame from camera.")
            continue
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"[ERROR] Failed to convert frame to RGB: {e}")
            continue
        boxes = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, boxes)
        for encoding, box in zip(encodings, boxes):
            if known_encodings:
                distances = face_recognition.face_distance(known_encodings, encoding)
                min_distance = min(distances)
                best_match_idx = distances.tolist().index(min_distance)
                threshold = 0.65  # More lenient threshold
                if min_distance < threshold:
                    banner_id, display_name = known_names[best_match_idx]
                    name = display_name or banner_id
                    print(f"[ACCESS GRANTED] Recognized: {name}")
                    print("[BOT ACTION] Unlocking food compartment...")
                    time.sleep(2)
                else:
                    name = "Unknown"
                    print("[ACCESS DENIED] Face not recognized.")
            else:
                name = "Unknown"
                print("[ACCESS DENIED] No known faces in database.")
            top, right, bottom, left = box
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cam.release()
    cv2.destroyAllWindows()
