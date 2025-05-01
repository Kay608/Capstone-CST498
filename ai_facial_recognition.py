import cv2
import face_recognition
import pickle
import time
import os

ENCODINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'encodings.pkl'))

# Load known faces
try:
    with open(ENCODINGS_PATH, "rb") as f:
        data = pickle.load(f)
        known_encodings = data["encodings"]
        known_names = data["names"]
    print(f"[INFO] Loaded {len(known_names)} known face(s).")
except FileNotFoundError:
    print("[ERROR] encodings.pkl not found. Please upload faces via the app first.")
    exit()

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
                name = known_names[best_match_idx]
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
                    name = known_names[best_match_idx]
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
