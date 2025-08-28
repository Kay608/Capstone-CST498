# pathfinding.py
"""
Pathfinding module for Yahboom Raspbot
- Plans and executes paths to navigation goals
- Designed for easy extension and ROS 2 integration
"""
from typing import Tuple, List
from robot_navigation.localization import Localization
from robot_navigation.hardware_interface import HardwareInterface

class PathFinder:
    def __init__(self, localization: Localization, hardware: HardwareInterface):
        self.localization = localization
        self.hardware = hardware
        self.goal = None  # (x, y) in meters or (lat, lon) in degrees
        self.path: List[Tuple[float, float]] = []

    def set_goal(self, goal: Tuple[float, float]):
        """
        Set the navigation goal (x, y) or (lat, lon)
        """
        self.goal = goal
        print(f"Goal set to: {self.goal}")

    def compute_path(self):
        """
        Compute a path from current pose to goal.
        For now, returns a straight line (start, goal).
        """
        if self.goal is None:
            print("No goal set.")
            return []
        start = self.localization.get_pose()[:2]  # (x, y)
        self.path = [start, self.goal]
        print(f"Path computed: {self.path}")
        return self.path

    def follow_path(self):
        """
        Follow the computed path using hardware interface.
        Implements basic point-to-point navigation.
        """
        if not self.path:
            print("No path to follow.")
            return
        
        print(f"Following path: {self.path}")
        
        for i in range(len(self.path) - 1):
            current = self.path[i]
            target = self.path[i + 1]
            self._navigate_to_point(current, target)
    
    def _navigate_to_point(self, current: Tuple[float, float], target: Tuple[float, float]):
        """
        Navigate from current point to target point.
        Basic implementation using differential drive.
        """
        import math
        
        # Calculate distance and angle to target
        dx = target[0] - current[0]
        dy = target[1] - current[1]
        distance = math.sqrt(dx**2 + dy**2)
        target_angle = math.atan2(dy, dx)
        
        # Get current robot pose
        current_x, current_y, current_theta = self.localization.get_pose()
        
        # Calculate angle difference
        angle_diff = target_angle - current_theta
        
        # Normalize angle to [-π, π]
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Turn to face target
        if abs(angle_diff) > 0.1:  # 0.1 radian threshold (~5.7 degrees)
            if angle_diff > 0:
                self.hardware.turn_left(1.0, math.degrees(abs(angle_diff)))
            else:
                self.hardware.turn_right(1.0, math.degrees(abs(angle_diff)))
        
        # Move forward to target
        if distance > 0.05:  # 5cm threshold
            move_time = distance / 0.3  # Move at 0.3 m/s
            self.hardware.move_forward(0.3, move_time)
        
        print(f"Navigated from {current} to {target}")

# Example usage (for testing only)
if __name__ == "__main__":
    from robot_navigation.localization import Localization
    from robot_navigation.hardware_interface import create_hardware_interface
    
    loc = Localization()
    hardware = create_hardware_interface(use_simulation=True)
    pf = PathFinder(loc, hardware)
    pf.set_goal((2.0, 3.0))
    pf.compute_path()
    pf.follow_path()