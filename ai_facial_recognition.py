import cv2
import face_recognition
import pickle
import time
import os
import boto3 # New import for AWS S3
from botocore.exceptions import NoCredentialsError, ClientError # For error handling

# --- AWS S3 Configuration ---
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2') # Default to us-east-2 if not set
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

if not S3_BUCKET_NAME:
    print("[WARNING] S3_BUCKET_NAME environment variable not set. S3 operations will fail.")
    s3_client = None
else:
    try:
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        print(f"[INFO] S3 client initialized for bucket: {S3_BUCKET_NAME} in region: {AWS_REGION}")
    except NoCredentialsError:
        print("[ERROR] AWS credentials not found. S3 operations will fail.")
        s3_client = None
    except Exception as e:
        print(f"[ERROR] Error initializing S3 client: {e}")
        s3_client = None

ENCODINGS_FILE_KEY = 'encodings.pkl' # The name of your encodings file in S3

def download_file_from_s3(file_key):
    """
    Downloads a file from S3.
    """
    if not s3_client:
        return None, "S3 client not initialized."

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=file_key)
        print(f"[INFO] Successfully downloaded {file_key} from S3.")
        return response['Body'].read(), None
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"[WARNING] {file_key} not found in S3 bucket.")
            return None, "File not found."
        print(f"[ERROR] S3 download failed for {file_key}: {e}")
        return None, str(e)
    except Exception as e:
        print(f"[ERROR] Unexpected S3 download error for {file_key}: {e}")
        return None, str(e)

# Load known faces from S3
try:
    data_bytes, error = download_file_from_s3(ENCODINGS_FILE_KEY)
    if data_bytes:
        data = pickle.loads(data_bytes)
        known_encodings = data["encodings"]
        known_names = data["names"]
        print(f"[INFO] Loaded {len(known_names)} known face(s) from S3.")
    else:
        known_encodings = []
        known_names = []
        print("[WARNING] No encodings file found in S3 or S3 client not initialized. Starting with empty database.")
except Exception as e:
    print(f"[ERROR] Error loading encodings from S3: {e}. Starting with empty database.")
    known_encodings = []
    known_names = []

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
