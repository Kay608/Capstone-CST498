# pathfinding.py
"""
Pathfinding module for Yahboom Raspbot
- Plans and executes paths to navigation goals
- Designed for easy extension and ROS 2 integration
"""
from typing import Tuple, List
from robot_navigation.localization import Localization

class PathFinder:
    def __init__(self, localization: Localization):
        self.localization = localization
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
        Placeholder for path following logic.
        In a real robot, this would send velocity/motor commands.
        """
        if not self.path:
            print("No path to follow.")
            return
        print(f"Following path: {self.path}")
        # TODO: Implement motor control or ROS 2 action client here

# Example usage (for testing only)
if __name__ == "__main__":
    from robot_navigation.localization import Localization
    loc = Localization()
    pf = PathFinder(loc)
    pf.set_goal((2.0, 3.0))
    pf.compute_path()
    pf.follow_path()