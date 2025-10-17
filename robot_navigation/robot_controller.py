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
import ai_facial_recognition
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
        self.simulated_camer_image = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads', 'Test_Person.jpg')) # Path to a sample image for simulated camera

    def _get_camera_frame(self):
        """
        Simulates getting a camera frame. In a real robot, this would capture from the camera.
        """
        if self.hardware.is_available():
            # TODO: Implement real camera capture if hardware is available
            pass
        
        # For simulation, load a static image
        if os.path.exists(self.simulated_camer_image):
            return cv2.imread(self.simulated_camer_image)
        else:
            print(f"[ERROR] Simulated camera image not found: {self.simulated_camer_image}")
            return None

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
        # ai_facial_recognition.recognize_face() already handles camera capture,
        # but in a real scenario, this might need to be adapted to use _get_camera_frame
        # For now, we'll keep it as is, assuming ai_facial_recognition can get its own frame
        # or can be modified to accept a frame.
        recognized = ai_facial_recognition.recognize_face()  # Assumes this returns True/False
        if recognized:
            print("Face recognized!")
            self.make_arrival_sound()
        else:
            print("Face not recognized.")
        return recognized

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