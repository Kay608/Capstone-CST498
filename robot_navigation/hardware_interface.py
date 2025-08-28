"""
Hardware Interface for Yahboom Raspbot
- Provides abstraction layer between robot logic and hardware
- Supports both real hardware and simulation mode for development
"""

import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import logging

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
    def is_available(self) -> bool:
        """Check if hardware is available and responsive"""
        pass

class YahboomRaspbotInterface(HardwareInterface):
    """Real hardware interface for Yahboom Raspbot"""
    
    def __init__(self):
        self.available = False
        self.last_encoder_left = 0
        self.last_encoder_right = 0
        self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize connection to Yahboom Raspbot hardware"""
        try:
            # TODO: Import and initialize Yahboom driver library
            # from yahboom_raspbot import RaspbotDriver
            # self.robot = RaspbotDriver()
            logger.warning("Yahboom driver not implemented yet - using simulation mode")
            self.available = False
        except ImportError as e:
            logger.error(f"Yahboom driver not available: {e}")
            self.available = False
        except Exception as e:
            logger.error(f"Hardware initialization failed: {e}")
            self.available = False
    
    def move_forward(self, speed: float, duration: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        # TODO: Implement actual motor control
        # self.robot.move_forward(speed)
        # time.sleep(duration)
        # self.robot.stop()
        logger.info(f"Moving forward at speed {speed} for {duration}s")
    
    def move_backward(self, speed: float, duration: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        # TODO: Implement actual motor control
        logger.info(f"Moving backward at speed {speed} for {duration}s")
    
    def turn_left(self, speed: float, angle: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        # TODO: Implement actual turning control
        logger.info(f"Turning left at speed {speed} for {angle} degrees")
    
    def turn_right(self, speed: float, angle: float) -> None:
        if not self.available:
            logger.warning("Hardware not available - command ignored")
            return
        # TODO: Implement actual turning control
        logger.info(f"Turning right at speed {speed} for {angle} degrees")
    
    def stop(self) -> None:
        if not self.available:
            return
        # TODO: Implement actual stop command
        logger.info("Stopping robot")
    
    def get_encoder_ticks(self) -> Tuple[int, int]:
        if not self.available:
            return (0, 0)
        # TODO: Get actual encoder values
        # left_ticks = self.robot.get_left_encoder()
        # right_ticks = self.robot.get_right_encoder()
        # delta_left = left_ticks - self.last_encoder_left
        # delta_right = right_ticks - self.last_encoder_right
        # self.last_encoder_left = left_ticks
        # self.last_encoder_right = right_ticks
        # return (delta_left, delta_right)
        return (0, 0)
    
    def get_imu_data(self) -> Optional[dict]:
        if not self.available:
            return None
        # TODO: Get actual IMU data
        # return self.robot.get_imu_data()
        return None
    
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
