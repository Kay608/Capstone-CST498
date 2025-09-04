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
        else:
            print("[ERROR] Could not get camera frame for YOLO detection.")

# Example usage (for testing only)
if __name__ == "__main__":
    controller = RobotController(use_simulation=True)
    # Example goal: (x, y) in meters or (lat, lon)
    controller.run((2.0, 3.0))