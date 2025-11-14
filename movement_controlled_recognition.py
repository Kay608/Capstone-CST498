#!/usr/bin/env python3
"""
Movement-Controlled Recognition System
====================================

Enhanced system with robot movement control based on traffic sign detection.

Usage:
    python movement_controlled_recognition.py --movement
"""

import cv2
import numpy as np
import time
import os
import sys
import argparse
import logging

# Add paths for imports
sys.path.append('python codes')
sys.path.append('.')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import dependencies
try:
    from sign_recognition import TrafficSignDetector
    SIGN_DETECTION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Sign detection not available: {e}")
    SIGN_DETECTION_AVAILABLE = False

try:
    from robot_navigation.hardware_interface import create_hardware_interface
    ROBOT_HARDWARE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Robot hardware not available: {e}")
    ROBOT_HARDWARE_AVAILABLE = False

class MovementControlledRecognitionSystem:
    """System with robot movement control based on traffic sign detection."""
    
    def __init__(self, 
                 enable_sign_detection=True,
                 enable_movement_control=False,
                 use_robot_hardware=False,
                 confidence_threshold=0.75,
                 headless_mode=False):
        """Initialize the system."""
        self.enable_sign_detection = enable_sign_detection and SIGN_DETECTION_AVAILABLE
        self.enable_movement_control = enable_movement_control
        self.use_robot_hardware = use_robot_hardware
        self.headless_mode = headless_mode
        self.confidence_threshold = confidence_threshold
        
        # Movement state
        self.is_moving = False
        self.movement_speed = 0.3
        self.stop_duration = 3.0
        self.stop_cooldown = 5.0
        self.last_stop_time = 0
        self.movement_enabled = False
        
        # Initialize components
        self.sign_detector = None
        self.robot_interface = None
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all system components."""
        # Sign detection
        if self.enable_sign_detection:
            try:
                self.sign_detector = TrafficSignDetector(
                    model_path='yolov8n.pt',
                    confidence_threshold=self.confidence_threshold
                )
                logger.info("✅ Sign detection initialized")
            except Exception as e:
                logger.error(f"❌ Sign detection failed: {e}")
                self.enable_sign_detection = False
        
        # Robot interface
        if ROBOT_HARDWARE_AVAILABLE:
            try:
                self.robot_interface = create_hardware_interface(
                    use_simulation=not self.use_robot_hardware
                )
                hardware_type = "hardware" if self.use_robot_hardware else "simulation"
                logger.info(f"✅ Robot interface initialized ({hardware_type})")
            except Exception as e:
                logger.error(f"❌ Robot interface failed: {e}")
                self.robot_interface = None
    
    def start_movement(self):
        """Start robot forward movement."""
        if not self.enable_movement_control or not self.robot_interface:
            return
            
        if not self.is_moving:
            self.is_moving = True
            logger.info(f"🚀 Robot moving forward (speed: {self.movement_speed})")
            
            try:
                if self.use_robot_hardware and hasattr(self.robot_interface, 'move_forward'):
                    # Real hardware would use threading for continuous movement
                    pass  
                else:
                    logger.info(f"[SIMULATION] Robot moving forward at {self.movement_speed}")
            except Exception as e:
                logger.error(f"Movement start failed: {e}")
                self.is_moving = False
    
    def stop_movement(self, duration=0):
        """Stop robot movement."""
        if not self.enable_movement_control or not self.robot_interface:
            return
            
        if self.is_moving:
            self.is_moving = False
            duration_msg = f" for {duration}s" if duration > 0 else ""
            logger.info(f"⏹️ Robot stopped{duration_msg}")
            
            try:
                if self.use_robot_hardware and hasattr(self.robot_interface, 'stop'):
                    self.robot_interface.stop()
                else:
                    logger.info("[SIMULATION] Robot stopped")
            except Exception as e:
                logger.error(f"Movement stop failed: {e}")
    
    def handle_traffic_signs(self, detections):
        """Handle robot actions based on traffic sign detections."""
        if not self.enable_movement_control or not detections:
            return
            
        current_time = time.time()
        
        for detection in detections:
            class_name = detection['class']
            confidence = detection['confidence']
            
            # Handle stop sign
            if class_name == 'stop sign' and confidence > self.confidence_threshold:
                if (current_time - self.last_stop_time) > self.stop_cooldown:
                    logger.info(f"🛑 STOP SIGN detected! Stopping for {self.stop_duration}s")
                    self.stop_movement(self.stop_duration)
                    
                    # Buzzer alert
                    if self.robot_interface and hasattr(self.robot_interface, 'robot'):
                        try:
                            self.robot_interface.robot.Buzz_Alert()
                        except:
                            logger.info("[BUZZER] Alert sound (simulated)")
                    
                    self.last_stop_time = current_time
                    
            # Handle person detection (safety)
            elif class_name == 'person' and confidence > (self.confidence_threshold + 0.1):
                if self.is_moving:
                    logger.info(f"👤 Person detected - Safety stop")
                    self.stop_movement(1.0)
                    
                    # Short beep
                    if self.robot_interface and hasattr(self.robot_interface, 'robot'):
                        try:
                            self.robot_interface.robot.Buzz_Short()
                        except:
                            logger.info("[BUZZER] Short beep (simulated)")
                            
            # Handle traffic light
            elif class_name == 'traffic light' and confidence > self.confidence_threshold:
                logger.info(f"🚦 Traffic light detected - Caution")
    
    def check_resume_movement(self):
        """Check if robot should resume movement after stop."""
        if not self.enable_movement_control or not self.movement_enabled:
            return
            
        current_time = time.time()
        
        # Resume after stop sign delay
        if (not self.is_moving and 
            self.last_stop_time > 0 and 
            (current_time - self.last_stop_time) > self.stop_duration):
            
            logger.info("✅ Resuming movement after stop")
            self.start_movement()
    
    def run(self):
        """Main system loop."""
        logger.info("🚀 Movement-Controlled Recognition System")
        logger.info(f"Sign Detection: {'✅' if self.enable_sign_detection else '❌'}")
        logger.info(f"Movement Control: {'✅' if self.enable_movement_control else '❌'}")
        
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("❌ Could not open camera")
            return False
            
        logger.info("📹 Camera initialized")
        
        if self.enable_movement_control:
            logger.info("🎮 Controls: 'q'=quit, 's'=save, SPACE=toggle movement")
            self.movement_enabled = True
            time.sleep(1)
            self.start_movement()
        else:
            logger.info("🎮 Controls: 'q'=quit, 's'=save frame")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.error("Failed to capture frame")
                    break
                
                # Process sign detection
                sign_detections = []
                if self.enable_sign_detection and self.sign_detector:
                    sign_detections = self.sign_detector.detect(frame)
                    
                    # Handle movement control
                    if sign_detections:
                        self.handle_traffic_signs(sign_detections)
                        
                        # Log detections
                        for detection in sign_detections:
                            if detection['confidence'] > self.confidence_threshold:
                                logger.info(f"🚧 {detection['class']}: {detection['confidence']:.2f}")
                    
                    # Draw detection boxes
                    frame = self.sign_detector.draw_detections(frame, sign_detections)
                
                # Check movement resume
                if self.enable_movement_control:
                    self.check_resume_movement()
                
                # Display
                if not self.headless_mode:
                    self._draw_status_overlay(frame)
                    cv2.imshow('Movement-Controlled Recognition', frame)
                
                # Handle input
                if not self.headless_mode:
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        break
                    elif key == ord('s'):
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"saved_frame_{timestamp}.jpg"
                        cv2.imwrite(filename, frame)
                        logger.info(f"💾 Frame saved: {filename}")
                    elif key == ord(' ') and self.enable_movement_control:
                        if self.is_moving:
                            logger.info("⏸️ Manual pause")
                            self.stop_movement()
                            self.movement_enabled = False
                        else:
                            logger.info("▶️ Manual resume")
                            self.movement_enabled = True
                            self.start_movement()
                else:
                    time.sleep(0.03)
                    
        except KeyboardInterrupt:
            logger.info("\\n🛑 System interrupted")
        except Exception as e:
            logger.error(f"❌ System error: {e}")
        finally:
            # Cleanup
            if self.enable_movement_control:
                self.stop_movement()
            cap.release()
            if not self.headless_mode:
                cv2.destroyAllWindows()
            logger.info("✅ System shutdown complete")
            
        return True
    
    def _draw_status_overlay(self, frame):
        """Draw system status on frame."""
        y = 30
        
        # Status items
        items = [
            (f"Sign Detection: {'ON' if self.enable_sign_detection else 'OFF'}", 
             (0, 255, 0) if self.enable_sign_detection else (0, 0, 255)),
            (f"Movement: {'ON' if self.enable_movement_control else 'OFF'}", 
             (0, 255, 0) if self.enable_movement_control else (0, 0, 255))
        ]
        
        for text, color in items:
            cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y += 25
        
        # Movement status
        if self.enable_movement_control:
            status = "MOVING" if self.is_moving else "STOPPED"
            color = (0, 255, 0) if self.is_moving else (0, 165, 255)
            cv2.putText(frame, f"Robot: {status}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y += 25
            
            # Last stop time
            if self.last_stop_time > 0:
                time_since_stop = time.time() - self.last_stop_time
                if time_since_stop < 10:
                    cv2.putText(frame, f"Last stop: {time_since_stop:.1f}s ago", 
                               (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Movement-Controlled Recognition System')
    
    parser.add_argument('--no-signs', action='store_true', help='Disable sign detection')
    parser.add_argument('--movement', action='store_true', help='Enable movement control')
    parser.add_argument('--robot', action='store_true', help='Use real hardware')
    parser.add_argument('--headless', action='store_true', help='No display')
    parser.add_argument('--confidence', type=float, default=0.75, 
                        help='Detection confidence (0.0-1.0)')
    
    args = parser.parse_args()
    
    # Validation
    if not (0.0 <= args.confidence <= 1.0):
        print("Error: Confidence must be between 0.0 and 1.0")
        return False
    
    # Create and run system
    system = MovementControlledRecognitionSystem(
        enable_sign_detection=not args.no_signs,
        enable_movement_control=args.movement,
        use_robot_hardware=args.robot,
        confidence_threshold=args.confidence,
        headless_mode=args.headless
    )
    
    return system.run()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)