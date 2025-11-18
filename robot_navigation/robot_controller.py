# robot_controller.py
"""
Robot Controller for Yahboom Raspbot
- Integrates localization, pathfinding, and face recognition
- Handles goal reception, navigation, and arrival logic (sound on face match)
"""
from robot_navigation.localization import Localization
from robot_navigation.pathfinding import PathFinder
from robot_navigation.hardware_interface import create_hardware_interface
from robot_navigation.yolo_detector import YOLOSignDetector
try:
    from robot_navigation.sign_recognition import TrafficSignClassifier
except Exception:  # Optional dependency (TensorFlow)
    TrafficSignClassifier = None
try:
    from recognition_core import FaceRecognitionEngine
except ImportError:
    FaceRecognitionEngine = None  # type: ignore
import time
import cv2
import os

class RobotController:
    def __init__(self, use_simulation: bool = True):
        self.localization = Localization()
        self.hardware = create_hardware_interface(use_simulation=use_simulation)
        self.pathfinder = PathFinder(self.localization, self.hardware)
        self.yolo_detector = YOLOSignDetector() # Initialize YOLO detector
        self.sign_classifier = TrafficSignClassifier() if TrafficSignClassifier else None
        self._last_sign_label = None
        self._last_sign_time = 0.0
        self.goal = None
        self.arrived = False
        self._use_simulation = use_simulation
        self._fallback_camera = None
        self.simulated_camer_image = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads', 'Test_Person.jpg')) # Path to a sample image for simulated camera
        self.face_engine = None

        if FaceRecognitionEngine is not None:
            try:
                self.face_engine = FaceRecognitionEngine(frame_skip=1)
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Facial recognition engine unavailable: {exc}")

    def _get_camera_frame(self):
        """
        Simulates getting a camera frame. In a real robot, this would capture from the camera.
        """
        frame = None

        # First preference: use hardware interface (real robot or simulated)
        if self.hardware and self.hardware.is_available():
            frame = self.hardware.get_camera_frame()

        # Fallback to direct OpenCV capture when hardware interface is unavailable.
        # Supports Pi Camera via V4L2/libcamera bridge or a user-supplied GStreamer pipeline.
        if frame is None and not self._use_simulation:
            if self._fallback_camera is None:
                source = os.environ.get("CAPSTONE_CAMERA_PIPELINE")
                if not source:
                    # Prefer /dev/video0 when present; otherwise default to index 0
                    default_device = "/dev/video0"
                    source = default_device if os.path.exists(default_device) else 0

                # Select backend based on source type
                if isinstance(source, str) and not source.isdigit() and " " in source:
                    # Treat as GStreamer pipeline string
                    self._fallback_camera = cv2.VideoCapture(source, cv2.CAP_GSTREAMER)
                elif isinstance(source, str) and source.startswith("/dev/video"):
                    self._fallback_camera = cv2.VideoCapture(source, cv2.CAP_V4L2)
                else:
                    self._fallback_camera = cv2.VideoCapture(int(source), cv2.CAP_V4L2) if str(source).isdigit() else cv2.VideoCapture(source)

            if self._fallback_camera and self._fallback_camera.isOpened():
                ret, camera_frame = self._fallback_camera.read()
                if ret:
                    frame = camera_frame

        # Last resort for simulation: load the demo image from disk
        if frame is None and os.path.exists(self.simulated_camer_image):
            frame = cv2.imread(self.simulated_camer_image)

        if frame is None:
            print("[ERROR] No camera frame available (hardware + fallbacks failed).")

        return frame

    def receive_goal(self, goal):
        """
        Receives a navigation goal (x, y) or (lat, lon)
        """
        self.goal = goal
        self.pathfinder.set_goal(goal)
        self.pathfinder.compute_path()
        self.arrived = False
        print(f"Received new goal: {goal}")

    def navigate_to_goal(self):
        """
        Follows the path to the goal. Placeholder for real motor control.
        """
        if not self.goal:
            print("No goal set.")
            return
        print("Navigating to goal...")
        self.pathfinder.follow_path()
        # Simulate arrival for demo (replace with real arrival check)
        time.sleep(2)
        self.arrived = True
        print("Arrived at goal.")

    def perform_face_recognition(self):
        """
        Calls the face recognition module and returns True if user is recognized.
        Uses the simulated camera frame if not in real hardware mode.
        """
        print("Scanning for face...")
        frame = self._get_camera_frame()
        if frame is None:
            print("[ERROR] Unable to capture frame for facial recognition.")
            return False

        if not self.face_engine:
            print("[WARN] Facial recognition engine not available.")
            return False

        results = self.face_engine.analyze_frame(frame, skip_frame_check=True)
        for result in results:
            if result.matched:
                print(f"Face recognized: {result.name} ({result.confidence:.2f})")
                self.make_arrival_sound()
                return True

        if not results:
            print("No faces detected in frame.")
        else:
            print("Face not recognized.")

        return False

    def make_arrival_sound(self):
        """
        Makes a sound to acknowledge arrival (simple beep for now).
        """
        try:
            import winsound
            winsound.Beep(1000, 500)  # 1000 Hz, 0.5 sec (Windows only)
        except ImportError:
            print("Beep! (sound not supported on this OS)")

    def run(self, goal):
        """
        Main loop: receive goal, navigate, recognize face, acknowledge.
        """
        self.receive_goal(goal)
        self.navigate_to_goal()
        if self.arrived:
            self.perform_face_recognition()
        
        # Perform YOLO sign detection after arrival (or continuously in a loop)
        print("[INFO] Performing YOLO sign detection...")
        frame = self._get_camera_frame()
        if frame is not None:
            detections = self.yolo_detector.detect_signs(frame)
            if detections:
                print("[INFO] YOLO Detections found:")
                for d in detections:
                    print(f"  Class: {d['class']}, Confidence: {d['confidence']:.2f}, BBox: {d['bbox']}")
                    # Placeholder for basic sign-based action logic
                    if d['class'] == 'stop sign' and d['confidence'] > 0.7:
                        print("[ROBOT ACTION] Detected STOP sign. Robot would stop for 3 seconds.")
                        # self.hardware.stop()
                        # time.sleep(3)
                    elif d['class'] == 'person' and d['confidence'] > 0.7:
                        print("[ROBOT ACTION] Detected PERSON. Robot would slow down and yield.")
                        # self.hardware.set_speed(0.1) # Slow down
            else:
                print("[INFO] No significant signs detected by YOLO.")

            if self.sign_classifier:
                self._evaluate_traffic_signs(frame)
            else:
                print("[WARN] Traffic sign classifier unavailable. Ensure TensorFlow is installed and mobilenetv2.h5 is present.")
        else:
            print("[ERROR] Could not get camera frame for YOLO detection.")

    def _evaluate_traffic_signs(self, frame):
        """Run MobileNet classifier and trigger high-level actions."""
        try:
            result = self.sign_classifier.predict_top(frame)
        except Exception as exc:
            print(f"[ERROR] Traffic sign classifier failed: {exc}")
            return
        if not result:
            return

        label = result['label']
        confidence = result['confidence']

        # Debounce identical detections within 5 seconds
        now = time.time()
        if label == self._last_sign_label and (now - self._last_sign_time) < 5:  # 5-second cooldown
            return

        self._last_sign_label = label
        self._last_sign_time = now

        print(f"[SIGN] Detected {label} with confidence {confidence:.2f}")
        if label == 'stop':
            print("[ROBOT ACTION] STOP sign detected via MobileNet. Robot would halt for 3 seconds.")
            # self.hardware.stop()
            # time.sleep(3)
        elif label == 'speed_limit':
            print("[ROBOT ACTION] SPEED LIMIT sign detected. Robot would reduce speed.")
            # self.hardware.set_speed(0.2)
        elif label == 'no_entry':
            print("[ROBOT ACTION] NO ENTRY sign detected. Robot would plan an alternate route.")
            # self.pathfinder.request_reroute()
        elif label == 'crosswalk':
            print("[ROBOT ACTION] CROSSWALK sign detected. Robot would slow and activate caution lights.")
            # self.hardware.set_speed(0.15)

# Example usage (for testing only)
if __name__ == "__main__":
    controller = RobotController(use_simulation=True)
    # Example goal: (x, y) in meters or (lat, lon)
    controller.run((2.0, 3.0))