# localization.py
"""
Localization module for Yahboom Raspbot
- Handles pose estimation using odometry, IMU, and (future) GPS
- Designed for easy extension and ROS 2 integration
"""

from typing import Optional, Tuple
from math import sin, cos

class RobotState:
    """
    Represents the robot's estimated state (pose and heading).
    Units: x/y in meters, theta in radians, lat/lon in degrees
    """
    def __init__(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0,
                 lat: Optional[float] = None, lon: Optional[float] = None):
        self.x = x
        self.y = y
        self.theta = theta
        self.lat = lat
        self.lon = lon

    def __repr__(self):
        return f"RobotState(x={self.x:.2f}, y={self.y:.2f}, theta={self.theta:.2f}, lat={self.lat}, lon={self.lon})"

class Localization:
    def __init__(self):
        self.state = RobotState()

    def update_from_odometry(self, left_ticks: int, right_ticks: int, ticks_per_meter: float, wheel_base: float):
        """
        Update pose estimate from wheel encoder ticks.
        left_ticks, right_ticks: change in encoder ticks since last update
        ticks_per_meter: calibration constant
        wheel_base: distance between left and right wheels (meters)
        """
        # Convert ticks to distance
        left_dist = left_ticks / ticks_per_meter
        right_dist = right_ticks / ticks_per_meter
        d_center = (left_dist + right_dist) / 2.0
        d_theta = (right_dist - left_dist) / wheel_base
        # Update pose
        self.state.x += d_center * cos(self.state.theta)
        self.state.y += d_center * sin(self.state.theta)
        self.state.theta += d_theta

    def update_from_gps(self, lat: float, lon: float):
        """
        Update state with latest GPS reading (future use).
        """
        self.state.lat = lat
        self.state.lon = lon

    def get_pose(self) -> Tuple[float, float, float]:
        """
        Returns (x, y, theta) in meters/radians (local frame)
        """
        return self.state.x, self.state.y, self.state.theta

    def get_gps(self) -> Optional[Tuple[float, float]]:
        """
        Returns (lat, lon) if available
        """
        if self.state.lat is not None and self.state.lon is not None:
            return self.state.lat, self.state.lon
        return None

# Math functions now imported at top of file

# Example usage (for testing only)
if __name__ == "__main__":
    loc = Localization()
    print("Initial:", loc.state)
    loc.update_from_odometry(left_ticks=100, right_ticks=100, ticks_per_meter=500, wheel_base=0.15)
    print("After odometry:", loc.state)
    loc.update_from_gps(36.0726, -79.7920)
    print("After GPS:", loc.state)