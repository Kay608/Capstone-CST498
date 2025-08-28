# robot_controller.py
"""
Robot Controller for Yahboom Raspbot
- Integrates localization, pathfinding, and face recognition
- Handles goal reception, navigation, and arrival logic (sound on face match)
"""
from robot_navigation.localization import Localization
from robot_navigation.pathfinding import PathFinder
from robot_navigation.hardware_interface import create_hardware_interface
import ai_facial_recognition
import time

class RobotController:
    def __init__(self, use_simulation: bool = True):
        self.localization = Localization()
        self.hardware = create_hardware_interface(use_simulation=use_simulation)
        self.pathfinder = PathFinder(self.localization, self.hardware)
        self.goal = None
        self.arrived = False

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
        """
        print("Scanning for face...")
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

# Example usage (for testing only)
if __name__ == "__main__":
    controller = RobotController()
    # Example goal: (x, y) in meters or (lat, lon)
    controller.run((2.0, 3.0))