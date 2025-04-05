import cv2
import face_recognition
import pickle
import time

# Load known faces
try:
    with open("encodings.pkl", "rb") as f:
        data = pickle.load(f)
        known_encodings = data["encodings"]
        known_names = data["names"]
    print(f"[INFO] Loaded {len(known_names)} known face(s).")
except FileNotFoundError:
    print("[ERROR] encodings.pkl not found. Please upload faces via the app first.")
    exit()

# Start camera
cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("[ERROR] Camera not accessible.")
    exit()

print("[INFO] Facial recognition active. Press ESC to quit.")

while True:
    ret, frame = cam.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)

    for encoding, box in zip(encodings, boxes):
        matches = face_recognition.compare_faces(known_encodings, encoding)
        name = "Unknown"

        if True in matches:
            match_idx = matches.index(True)
            name = known_names[match_idx]
            print(f"[ACCESS GRANTED] Recognized: {name}")
            # TODO: Replace this with Yahboom robot code
            print("[BOT ACTION] Unlocking food compartment...")
            time.sleep(2)
        else:
            print("[ACCESS DENIED] Face not recognized.")

        top, right, bottom, left = box
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Face Recognition", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC key
        break

cam.release()
cv2.destroyAllWindows()
