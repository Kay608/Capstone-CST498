import argparse
from typing import Optional

import cv2
import face_recognition
import time
import os
import pymysql  # For MySQL handling
import numpy as np  # To deserialize BLOBs back to numpy arrays
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env files are loaded before reading DB configuration
_ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(_ROOT_DIR / ".env", override=False)
load_dotenv(_ROOT_DIR / "flask_api" / ".env", override=False)

# --- JawsDB (MySQL) Configuration ---
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

MATCH_THRESHOLD = 0.65

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

def refresh_known_faces() -> None:
    global known_encodings, known_names
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


def analyze_frame(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)

    results = []
    for encoding, box in zip(encodings, boxes):
        name, matched, confidence = match_face_encoding(encoding)
        results.append({
            "name": name,
            "matched": matched,
            "box": box,
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
    results = analyze_frame(frame)

    for result in results:
        if result["matched"]:
            print(f"[ACCESS GRANTED] Recognized: {result['name']} ({result['confidence']:.2f})")
            return result["name"]

    if not known_encodings:
        print("[ACCESS DENIED] No known faces in database.")
    elif results:
        for result in results:
            print(f"[ACCESS DENIED] Face not recognized (confidence {result['confidence']:.2f}).")
    else:
        print("[INFO] No face detected in frame.")
    return None

def run_camera_loop() -> None:
    # Only run this block if the script is executed directly
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("[ERROR] Camera not accessible.")
        return
    print("[INFO] Facial recognition active. Press ESC to quit.")
    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            print("[ERROR] Failed to grab frame from camera.")
            continue
        annotated, results = annotate_frame(frame)

        for result in results:
            if result["matched"]:
                print(f"[ACCESS GRANTED] Recognized: {result['name']} ({result['confidence']:.2f})")
                print("[BOT ACTION] Unlocking food compartment...")
                time.sleep(2)
            elif not known_encodings:
                print("[ACCESS DENIED] No known faces in database.")
            else:
                print(f"[ACCESS DENIED] Face not recognized (confidence {result['confidence']:.2f}).")

        if not results:
            print("[INFO] No face detected in frame.")

        cv2.imshow("Face Recognition", annotated)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cam.release()
    cv2.destroyAllWindows()


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
    parser = argparse.ArgumentParser(description="Facial recognition utilities.")
    parser.add_argument("--snapshot", action="store_true", help="Capture a single annotated frame from the camera.")
    parser.add_argument("--output", help="Optional path to save the annotated snapshot when using --snapshot.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    refresh_known_faces()

    if args.output and not args.snapshot:
        print("[WARNING] --output is ignored unless --snapshot is specified.")

    if args.snapshot:
        capture_snapshot(args.output)
    else:
        run_camera_loop()


if __name__ == "__main__":
    main()
