import cv2
import face_recognition
import pickle

known_encodings = []
known_names = []

cam = cv2.VideoCapture(0)
name = input("Enter the name of the person: ")

print("Press SPACE to capture face, ESC to quit.")

while True:
    ret, frame = cam.read()
    cv2.imshow("Register Face", frame)

    key = cv2.waitKey(1)
    if key % 256 == 27:  # ESC
        break
    elif key % 256 == 32:  # SPACE
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, boxes)

        if encodings:
            known_encodings.append(encodings[0])
            known_names.append(name)
            print(f"[INFO] Face for {name} captured.")
        else:
            print("[WARN] No face detected. Try again.")

cam.release()
cv2.destroyAllWindows()

# Save encodings
data = {"encodings": known_encodings, "names": known_names}
with open("encodings.pkl", "wb") as f:
    pickle.dump(data, f)
print("[INFO] encodings.pkl saved.")
