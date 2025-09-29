"""
Hardware Interface for Yahboom Raspbot
- Provides abstraction layer between robot logic and hardware
- Supports both real hardware and simulation mode for development
"""

import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import logging
import cv2 # Import OpenCV

# Import the Yahboom Raspbot driver
try:
    from raspbot.YB_Pcb_Car import YB_Pcb_Car
except ImportError:
    # Fallback for when not running on the Pi or raspbot is not in path
    print("Warning: Could not import YB_Pcb_Car. Running in simulation mode or ensure raspbot directory is in PYTHONPATH.")
    YB_Pcb_Car = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HardwareInterface(ABC):
    """Abstract base class for hardware interface"""
    
    @abstractmethod
    def move_forward(self, speed: float, duration: float) -> None:
        """Move robot forward at given speed for duration"""
        pass
    
    @abstractmethod
    def move_backward(self, speed: float, duration: float) -> None:
        """Move robot backward at given speed for duration"""
        pass
    
    @abstractmethod
    def turn_left(self, speed: float, angle: float) -> None:
        """Turn robot left at given speed for angle degrees"""
        pass
    
    @abstractmethod
    def turn_right(self, speed: float, angle: float) -> None:
        """Turn robot right at given speed for angle degrees"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop all robot movement"""
        pass
    
    @abstractmethod
    def get_encoder_ticks(self) -> Tuple[int, int]:
        """Get left and right encoder ticks since last call"""
        pass
    
    @abstractmethod
    def get_imu_data(self) -> Optional[dict]:
        """Get IMU data (acceleration, gyroscope, magnetometer)"""
        pass
    
    @abstractmethod
    def set_camera_servo(self, angle: int) -> None:
        """Set camera servo angle (0-180 degrees)"""
        pass
    
    @abstractmethod
    def get_camera_frame(self) -> Optional[any]: # Returns an OpenCV image (numpy array)
        """Capture a single frame from the robot's camera"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if hardware is available and responsive"""
        pass

class YahboomRaspbotInterface(HardwareInterface):
    """Real hardware interface for Yahboom Raspbot"""
    
    def __init__(self):
        self.available = False
        self.last_encoder_left = 0
        self.last_encoder_right = 0
        self.car = None
        self.camera = None
        self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize connection to Yahboom Raspbot hardware"""
        if YB_Pcb_Car is None:
            logger.error("YB_Pcb_Car driver not imported. Hardware interface not available.")
            self.available = False
            return
        try:
            self.car = YB_Pcb_Car()
            # Initialize camera (assuming /dev/video0 or similar)
            self.camera = cv2.VideoCapture(0) # 0 is typically the default camera
            if not self.camera.isOpened():
                raise IOError("Cannot open webcam")
            
            logger.info("Yahboom Raspbot hardware initialized successfully.")
            self.available = True
        except Exception as e:
            logger.error(f"Hardware initialization failed: {e}")
            self.available = False
    
    def move_forward(self, speed: float, duration: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        # YB_Pcb_Car.Car_Run uses speed1 and speed2, assuming equal speed for forward
        # Speed values in YB_Pcb_Car are 0-255. Scaling our speed (0-1) to 0-255.
        motor_speed = int(speed * 255)
        self.car.Car_Run(motor_speed, motor_speed)
        time.sleep(duration)
        self.car.Car_Stop()
        logger.info(f"Moving forward at speed {speed} for {duration}s")
    
    def move_backward(self, speed: float, duration: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        motor_speed = int(speed * 255)
        self.car.Car_Back(motor_speed, motor_speed)
        time.sleep(duration)
        self.car.Car_Stop()
        logger.info(f"Moving backward at speed {speed} for {duration}s")
    
    def turn_left(self, speed: float, angle: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        motor_speed = int(speed * 255)
        # YB_Pcb_Car.Car_Left (0, speed1, 1, speed2) for differential drive
        self.car.Car_Left(motor_speed, motor_speed) # Assuming this is a spot turn
        # Duration for turn needs to be calibrated based on angle and speed
        turn_duration = angle / 90.0 # Placeholder: 1 second per 90 degrees
        time.sleep(turn_duration)
        self.car.Car_Stop()
        logger.info(f"Turning left at speed {speed} for {angle} degrees")
    
    def turn_right(self, speed: float, angle: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        motor_speed = int(speed * 255)
        # YB_Pcb_Car.Car_Right (1, speed1, 0, speed2) for differential drive
        self.car.Car_Right(motor_speed, motor_speed) # Assuming this is a spot turn
        turn_duration = angle / 90.0 # Placeholder
        time.sleep(turn_duration)
        self.car.Car_Stop()
        logger.info(f"Turning right at speed {speed} for {angle} degrees")
    
    def stop(self) -> None:
        if not self.available:
            return
        self.car.Car_Stop()
        logger.info("Stopping robot")
    
    def get_encoder_ticks(self) -> Tuple[int, int]:
        if not self.available:
            return (0, 0)
        # Encoders not directly found in YB_Pcb_Car.py
        logger.warning("Encoder data not available for Yahboom Raspbot interface.")
        return (0, 0)
    
    def get_imu_data(self) -> Optional[dict]:
        if not self.available:
            return None
        # IMU data not directly found in YB_Pcb_Car.py
        logger.warning("IMU data not available for Yahboom Raspbot interface.")
        return None
        
    def set_camera_servo(self, angle: int) -> None:
        if not self.available:
            logger.warning("Hardware not available - camera servo command ignored")
            return
        # Assuming servo ID 0 for the camera, and angle 0-180
        self.car.Ctrl_Servo(0, angle)
        logger.info(f"Setting camera servo to {angle} degrees")

    def get_camera_frame(self) -> Optional[any]:
        if not self.available or not self.camera.isOpened():
            logger.warning("Camera not available - returning None")
            return None
        ret, frame = self.camera.read()
        if not ret:
            logger.error("Failed to grab frame from camera")
            return None
        return frame
    
    def is_available(self) -> bool:
        return self.available

class SimulatedRaspbotInterface(HardwareInterface):
    """Simulated hardware interface for development without physical robot"""
    
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0  # heading in radians
        self.left_encoder = 0
        self.right_encoder = 0
        self.wheel_base = 0.15  # meters (typical for small robots)
        self.wheel_radius = 0.035  # meters
        self.ticks_per_revolution = 360  # encoder ticks per wheel revolution
        logger.info("Initialized simulated Raspbot interface")
        self.simulated_camera_frame = self._generate_simulated_frame()
    
    def _generate_simulated_frame(self):
        # Create a blank black image for simulation
        import numpy as np # Import numpy for array creation
        return np.zeros((240, 320, 3), dtype=np.uint8)

    def move_forward(self, speed: float, duration: float) -> None:
        distance = speed * duration
        # Simulate encoder ticks
        ticks = int(distance / (2 * 3.14159 * self.wheel_radius) * self.ticks_per_revolution)
        self.left_encoder += ticks
        self.right_encoder += ticks
        
        # Update simulated position
        import math
        self.x += distance * math.cos(self.theta)
        self.y += distance * math.sin(self.theta)
        
        logger.info(f"Simulated: Moving forward {distance:.2f}m to position ({self.x:.2f}, {self.y:.2f})")
        time.sleep(duration)  # Simulate actual movement time
    
    def move_backward(self, speed: float, duration: float) -> None:
        distance = speed * duration
        ticks = int(distance / (2 * 3.14159 * self.wheel_radius) * self.ticks_per_revolution)
        self.left_encoder -= ticks
        self.right_encoder -= ticks
        
        import math
        self.x -= distance * math.cos(self.theta)
        self.y -= distance * math.sin(self.theta)
        
        logger.info(f"Simulated: Moving backward {distance:.2f}m to position ({self.x:.2f}, {self.y:.2f})")
        time.sleep(duration)
    
    def turn_left(self, speed: float, angle: float) -> None:
        import math
        angle_rad = math.radians(angle)
        self.theta += angle_rad
        
        # Simulate differential encoder movement for turning
        arc_length = angle_rad * self.wheel_base / 2
        left_ticks = int(-arc_length / (2 * 3.14159 * self.wheel_radius) * self.ticks_per_revolution)
        right_ticks = int(arc_length / (2 * 3.14159 * self.wheel_radius) * self.ticks_per_revolution)
        self.left_encoder += left_ticks
        self.right_encoder += right_ticks
        
        logger.info(f"Simulated: Turned left {angle}° to heading {math.degrees(self.theta):.1f}°")
        time.sleep(abs(angle) / 90.0)  # Simulate turn time (90°/sec)
    
    def turn_right(self, speed: float, angle: float) -> None:
        import math
        angle_rad = math.radians(-angle)  # Negative for right turn
        self.theta += angle_rad
        
        # Simulate differential encoder movement for turning
        arc_length = angle_rad * self.wheel_base / 2
        left_ticks = int(-arc_length / (2 * 3.14159 * self.wheel_radius) * self.ticks_per_revolution)
        right_ticks = int(arc_length / (2 * 3.14159 * self.wheel_radius) * self.ticks_per_revolution)
        self.left_encoder += left_ticks
        self.right_encoder += right_ticks
        
        logger.info(f"Simulated: Turned right {angle}° to heading {math.degrees(self.theta):.1f}°")
        time.sleep(abs(angle) / 90.0)
    
    def stop(self) -> None:
        logger.info("Simulated: Robot stopped")
    
    def get_encoder_ticks(self) -> Tuple[int, int]:
        # Return delta since last call (simplified - always returns current total)
        return (self.left_encoder, self.right_encoder)
    
    def get_imu_data(self) -> Optional[dict]:
        import math
        # Return simulated IMU data
        return {
            'acceleration': {'x': 0.0, 'y': 0.0, 'z': 9.81},
            'gyroscope': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'magnetometer': {'x': math.cos(self.theta), 'y': math.sin(self.theta), 'z': 0.0},
            'heading': math.degrees(self.theta)
        }
    
    def set_camera_servo(self, angle: int) -> None:
        logger.info(f"Simulated: Setting camera servo to {angle} degrees")
    
    def get_camera_frame(self) -> Optional[any]:
        return self.simulated_camera_frame
    
    def is_available(self) -> bool:
        return True
    
    def get_position(self) -> Tuple[float, float, float]:
        """Get current simulated position (x, y, theta) - for debugging only"""
        import math
        return (self.x, self.y, math.degrees(self.theta))

def create_hardware_interface(use_simulation: bool = True) -> HardwareInterface:
    """Factory function to create appropriate hardware interface"""
    if use_simulation:
        return SimulatedRaspbotInterface()
    else:
        return YahboomRaspbotInterface()

# Example usage and testing
if __name__ == "__main__":
    # Test simulated interface
    robot = create_hardware_interface(use_simulation=True)
    
    print("Testing simulated robot interface...")
    print(f"Initial position: {robot.get_position()}")
    
    robot.move_forward(0.5, 2.0)  # 0.5 m/s for 2 seconds
    print(f"After forward: {robot.get_position()}")
    
    robot.turn_left(1.0, 90)  # Turn left 90 degrees
    print(f"After left turn: {robot.get_position()}")
    
    robot.move_forward(0.3, 1.0)  # Move forward again
    print(f"Final position: {robot.get_position()}")
    
    print(f"Encoder ticks: {robot.get_encoder_ticks()}")
    print(f"IMU data: {robot.get_imu_data()}")
    
    # Test camera capture in simulation
    frame = robot.get_camera_frame()
    if frame is not None:
        print(f"Simulated camera frame captured with shape: {frame.shape}")
    
    # Test real hardware interface (will likely fail if not on Pi)
    print("\nTesting real robot interface (will likely show errors if not on Pi with drivers)...")
    real_robot = create_hardware_interface(use_simulation=False)
    if real_robot.is_available():
        print("Real hardware interface is available.")
        real_robot.move_forward(0.2, 1.0)
        real_robot.stop()
        frame = real_robot.get_camera_frame()
        if frame is not None:
            print(f"Real camera frame captured with shape: {frame.shape}")
    else:
        print("Real hardware interface is NOT available.")
