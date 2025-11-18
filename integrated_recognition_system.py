  #!/usr/bin/env python3
"""
Integrated Facial Recognition and Traffic Sign Detection System
=============================================================

This system combines facial recognition for delivery verification and 
traffic sign detection for autonomous navigation on the Yahboom Raspbot.

Features:
- Simultaneous facial recognition and sign detection
- Buzzer feedback for face recognition events
- HTTP communication with Flask admin panel
- Order processing and verification logging
- Real-time camera feed with dual annotations
- Persistent green squares for recognized faces
- Traffic sign detection with bounding boxes
"""

import cv2
import numpy as np
import time
import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
import logging

# Add paths for imports
sys.path.append('python codes')
sys.path.append('.')

# Core imports
try:
    from ai_facial_recognition import (
        load_encodings_from_db, 
        get_db_connection, 
        log_verification_http,
        process_order_fulfillment,
        create_hardware_interface,
        FLASK_APP_URL,
        FACE_DETECTION_MODEL,
        MATCH_THRESHOLD
    )
    FACIAL_RECOGNITION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Facial recognition not available: {e}")
    FACIAL_RECOGNITION_AVAILABLE = False

try:
    from sign_recognition import TrafficSignDetector
    SIGN_DETECTION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Sign detection not available: {e}")
    SIGN_DETECTION_AVAILABLE = False

try:
    import face_recognition
    FACE_LIB_AVAILABLE = True
except ImportError:
    print("Warning: face_recognition library not available")
    FACE_LIB_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedRecognitionSystem:
    """
    Integrated system for facial recognition and traffic sign detection.
    """
    
    def __init__(self, 
                 enable_face_recognition=True,
                 enable_sign_detection=True,
                 use_robot_hardware=False,
                 confidence_threshold=0.5,
                 sign_model_path='yolov8n.pt'):
        """
        Initialize the integrated recognition system.
        
        Args:
            enable_face_recognition: Enable facial recognition functionality
            enable_sign_detection: Enable traffic sign detection
            use_robot_hardware: Use actual robot hardware vs simulation
            confidence_threshold: Minimum confidence for sign detection
            sign_model_path: Path to YOLO model for sign detection
        """
        self.enable_face_recognition = enable_face_recognition and FACIAL_RECOGNITION_AVAILABLE
        self.enable_sign_detection = enable_sign_detection and SIGN_DETECTION_AVAILABLE
        
        # Initialize components
        self.known_encodings = []
        self.known_names = []
        self.known_banner_ids = []
        self.face_tracking = {}
        self.sign_detector = None
        self.robot_interface = None
        
        # Timing and persistence settings
        self.FACE_PERSISTENCE_TIME = 3.0
        self.FACE_POSITION_TOLERANCE = 50
        self.last_recognition_time = 0
        self.recognition_cooldown = 2.0
        
        # Camera settings
        self.camera = None
        self.FRAME_SCALE = 0.5
        
        # Initialize subsystems
        self._initialize_face_recognition()
        self._initialize_sign_detection(confidence_threshold, sign_model_path)
        self._initialize_robot_interface(use_robot_hardware)
        
    def _initialize_face_recognition(self):
        """Initialize facial recognition system."""
        if not self.enable_face_recognition:
            logger.info("Facial recognition disabled")
            return
            
        if not FACE_LIB_AVAILABLE:
            logger.warning("face_recognition library not available - disabling facial recognition")
            self.enable_face_recognition = False
            return
            
        try:
            # Load face encodings from JawsDB database
            encodings, names = load_encodings_from_db()
            self.known_encodings = encodings
            
            # Extract names and banner IDs from JawsDB format
            self.known_names = []
            self.known_banner_ids = []
            for name_data in names:
                if isinstance(name_data, tuple) and len(name_data) == 2:
                    # JawsDB format: (banner_id, display_name)
                    banner_id, display_name = name_data
                    self.known_banner_ids.append(banner_id)
                    self.known_names.append(display_name)
                elif isinstance(name_data, dict):
                    # Legacy format support
                    self.known_names.append(name_data.get('display_name', 'Unknown'))
                    self.known_banner_ids.append(name_data.get('banner_id', 'unknown'))
                else:
                    # Fallback for other formats
                    self.known_names.append(str(name_data))
                    self.known_banner_ids.append("unknown")
            
            logger.info(f"Loaded {len(self.known_encodings)} face encodings from JawsDB")
            logger.info(f"Known faces: {[name for name in self.known_names]}")
            
        except Exception as e:
            logger.error(f"Failed to initialize facial recognition: {e}")
            self.enable_face_recognition = False
    
    def _initialize_sign_detection(self, confidence_threshold, model_path):
        """Initialize traffic sign detection system."""
        if not self.enable_sign_detection:
            logger.info("Sign detection disabled")
            return
            
        try:
            self.sign_detector = TrafficSignDetector(
                model_path=model_path,
                confidence_threshold=confidence_threshold
            )
            
            if self.sign_detector.model is None:
                logger.warning("Sign detection model not loaded - disabling sign detection")
                self.enable_sign_detection = False
            else:
                logger.info("Sign detection initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize sign detection: {e}")
            self.enable_sign_detection = False
    
    def _initialize_robot_interface(self, use_robot_hardware):
        """Initialize robot hardware interface."""
        try:
            self.robot_interface = create_hardware_interface(
                use_simulation=not use_robot_hardware
            )
            logger.info(f"Robot interface initialized (hardware={use_robot_hardware})")
        except Exception as e:
            logger.warning(f"Robot interface initialization failed: {e}")
            self.robot_interface = None
    
    def _initialize_camera(self, camera_index=0):
        """Initialize camera for video capture."""
        try:
            self.camera = cv2.VideoCapture(camera_index)
            if not self.camera.isOpened():
                raise Exception(f"Cannot open camera {camera_index}")
            
            # Set camera properties for better performance
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            logger.info(f"Camera initialized on index {camera_index}")
            return True
            
        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            return False
    
    def analyze_faces(self, frame):
        """
        Analyze frame for faces and return recognition results.
        """
        if not self.enable_face_recognition or len(self.known_encodings) == 0:
            return []
        
        # Resize frame for faster processing
        small_frame = cv2.resize(frame, (0, 0), fx=self.FRAME_SCALE, fy=self.FRAME_SCALE)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        # Find faces
        face_locations = face_recognition.face_locations(rgb_frame, model=FACE_DETECTION_MODEL)
        
        if not face_locations:
            return []
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        results = []
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Compare with known faces
            distances = face_recognition.face_distance(self.known_encodings, face_encoding)
            
            if len(distances) > 0:
                min_distance_idx = np.argmin(distances)
                min_distance = distances[min_distance_idx]
                matched = min_distance <= MATCH_THRESHOLD
                confidence = 1.0 - min_distance
                
                # Always use display name for showing on screen
                display_name = self.known_names[min_distance_idx] if matched else "Unknown"
                banner_id = self.known_banner_ids[min_distance_idx] if matched else None
                
                # Scale back to original frame size
                top, right, bottom, left = face_location
                top = int(top / self.FRAME_SCALE)
                right = int(right / self.FRAME_SCALE)
                bottom = int(bottom / self.FRAME_SCALE)
                left = int(left / self.FRAME_SCALE)
                
                results.append({
                    "name": display_name,  # Use display name for screen display
                    "matched": matched,
                    "box": (top, right, bottom, left),
                    "confidence": confidence,
                    "banner_id": banner_id,
                })
        
        return results
    
    def analyze_signs(self, frame):
        """
        Analyze frame for traffic signs and return detection results.
        """
        if not self.enable_sign_detection or self.sign_detector is None:
            return []
        
        try:
            detections = self.sign_detector.predict_sign(frame)
            return detections if detections else []
        except Exception as e:
            logger.error(f"Sign detection error: {e}")
            return []
    
    def update_face_tracking(self, face_results):
        """
        Update persistent face tracking for stable visual feedback.
        """
        current_time = time.time()
        current_faces = {}
        
        for result in face_results:
            top, right, bottom, left = result["box"]
            face_center = ((left + right) // 2, (top + bottom) // 2)
            
            # Find matching tracked face
            matched_track_id = None
            for track_id, tracked_face in self.face_tracking.items():
                tracked_center = tracked_face['center']
                distance = ((face_center[0] - tracked_center[0])**2 + 
                           (face_center[1] - tracked_center[1])**2)**0.5
                
                if distance < self.FACE_POSITION_TOLERANCE:
                    matched_track_id = track_id
                    break
            
            # Update or create face tracking
            if matched_track_id:
                track_id = matched_track_id
            else:
                track_id = f"face_{current_time}_{face_center[0]}_{face_center[1]}"
            
            current_faces[track_id] = {
                'box': (top, right, bottom, left),
                'center': face_center,
                'name': result['name'],
                'matched': result['matched'],
                'confidence': result['confidence'],
                'banner_id': result.get('banner_id'),
                'last_seen': current_time,
                'first_recognized': self.face_tracking.get(track_id, {}).get('first_recognized', 
                                                          current_time if result['matched'] else None)
            }
            
            # Mark recognition time
            if result['matched'] and not self.face_tracking.get(track_id, {}).get('matched', False):
                current_faces[track_id]['first_recognized'] = current_time
        
        # Remove old face tracks
        self.face_tracking = {track_id: data for track_id, data in self.face_tracking.items() 
                             if current_time - data['last_seen'] < self.FACE_PERSISTENCE_TIME}
        
        # Update with current faces
        self.face_tracking.update(current_faces)
    
    def process_face_recognition_events(self):
        """
        Process face recognition events and trigger appropriate actions.
        """
        current_time = time.time()
        
        for track_id, tracked_face in self.face_tracking.items():
            if (tracked_face['matched'] and 
                tracked_face.get('banner_id') and
                (current_time - self.last_recognition_time) > self.recognition_cooldown):
                
                logger.info(f"[ACCESS GRANTED] Recognized: {tracked_face['name']} (Banner ID: {tracked_face['banner_id']}) - Confidence: {tracked_face['confidence']:.2f}")
                
                # Log verification via HTTP
                try:
                    log_verification_http(tracked_face['name'], True, tracked_face['confidence'], "Integrated System")
                except Exception as e:
                    logger.error(f"Failed to log verification: {e}")
                
                # Process order fulfillment
                try:
                    if tracked_face['banner_id']:
                        process_order_fulfillment(tracked_face['banner_id'], tracked_face['name'])
                except Exception as e:
                    logger.error(f"Failed to process order: {e}")
                
                # Robot actions (including buzzer)
                self._execute_robot_actions(tracked_face)
                
                self.last_recognition_time = current_time
                break
    
    def _execute_robot_actions(self, face_data):
        """Execute robot actions including buzzer feedback."""
        if not self.robot_interface or not self.robot_interface.is_available():
            logger.info("[ROBOT] Robot interface not available - action skipped")
            return
        
        try:
            logger.info(f"[ROBOT] Unlocking compartment for {face_data['name']} (Banner ID: {face_data.get('banner_id', 'Unknown')})")
            
            # Play success buzz sound
            if hasattr(self.robot_interface, 'robot') and self.robot_interface.robot:
                logger.info("[ROBOT] Playing recognition success sound")
                self.robot_interface.robot.Buzz_Success()
            
            # Center camera
            self.robot_interface.set_camera_servo(90)
            
        except Exception as e:
            logger.error(f"[ROBOT] Action failed: {e}")
    
    def annotate_frame(self, frame, face_results, sign_results):
        """
        Annotate frame with both face recognition and sign detection results.
        """
        annotated = frame.copy()
        current_time = time.time()
        
        # Draw face recognition results
        if self.enable_face_recognition:
            for track_id, tracked_face in self.face_tracking.items():
                top, right, bottom, left = tracked_face['box']
                
                # Determine display state
                time_since_last_seen = current_time - tracked_face['last_seen']
                time_since_recognized = float('inf')
                
                if tracked_face['first_recognized']:
                    time_since_recognized = current_time - tracked_face['first_recognized']
                
                # Show green if recognized recently
                show_as_recognized = (tracked_face['matched'] or 
                                    (tracked_face['first_recognized'] and 
                                     time_since_last_seen < 0.5 and 
                                     time_since_recognized < self.FACE_PERSISTENCE_TIME))
                
                if show_as_recognized:
                    color = (0, 255, 0)  # Green
                    thickness = 4
                    label = f"✓ {tracked_face['name']} ({tracked_face['confidence']:.2f})"
                    
                    # Semi-transparent overlay
                    overlay = annotated.copy()
                    cv2.rectangle(overlay, (left, top), (right, bottom), color, -1)
                    cv2.addWeighted(annotated, 0.85, overlay, 0.15, 0, annotated)
                else:
                    color = (0, 0, 255)  # Red
                    thickness = 2
                    label = f"Unknown ({tracked_face['confidence']:.2f})"
                
                # Draw rectangle
                cv2.rectangle(annotated, (left, top), (right, bottom), color, thickness)
                
                # Draw label
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                label_bg_top = max(top - label_size[1] - 10, 0)
                cv2.rectangle(annotated, (left, label_bg_top), (left + label_size[0] + 10, top), color, -1)
                cv2.putText(annotated, label, (left + 5, top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Draw sign detection results
        if self.enable_sign_detection:
            for detection in sign_results:
                bbox = detection['bbox']
                class_name = detection['class_name']
                confidence = detection['confidence']
                
                x1, y1, x2, y2 = map(int, bbox)
                
                # Draw bounding box (blue for signs)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
                
                # Draw label
                sign_label = f"🛑 {class_name}: {confidence:.2f}"
                label_size = cv2.getTextSize(sign_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                
                cv2.rectangle(annotated, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), (255, 0, 0), -1)
                cv2.putText(annotated, sign_label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Add system status
        face_count = len(self.face_tracking) if self.enable_face_recognition else 0
        sign_count = len(sign_results) if self.enable_sign_detection else 0
        known_faces_count = len(self.known_encodings) if self.enable_face_recognition else 0
        
        status_lines = [
            f"👤 Active Faces: {face_count} | 🛑 Signs: {sign_count}",
            f"👥 Known Faces: {known_faces_count} | 🌐 Flask: {FLASK_APP_URL.split('/')[-1] if FACIAL_RECOGNITION_AVAILABLE else 'N/A'}"
        ]
        
        for i, line in enumerate(status_lines):
            y_pos = 30 + (i * 25)
            cv2.putText(annotated, line, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(annotated, line, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        return annotated
    
    def run_integrated_system(self, camera_index=0, headless=False):
        """
        Run the integrated facial recognition and sign detection system.
        """
        logger.info("Starting integrated recognition system...")
        logger.info(f"Face recognition: {'✓' if self.enable_face_recognition else '✗'}")
        logger.info(f"Sign detection: {'✓' if self.enable_sign_detection else '✗'}")
        
        # Initialize camera
        if not self._initialize_camera(camera_index):
            logger.error("Camera initialization failed")
            return
        
        logger.info("Integrated system active. Press 'q' to quit, 's' to save frame.")
        
        try:
            while True:
                ret, frame = self.camera.read()
                if not ret:
                    logger.error("Failed to grab frame")
                    break
                
                # Analyze frame
                face_results = self.analyze_faces(frame)
                sign_results = self.analyze_signs(frame)
                
                # Update face tracking
                if self.enable_face_recognition:
                    self.update_face_tracking(face_results)
                    self.process_face_recognition_events()
                
                # Log detections
                if face_results or sign_results:
                    if face_results:
                        for result in face_results:
                            status = "granted" if result["matched"] else "denied"
                            banner_info = f" (Banner ID: {result.get('banner_id', 'N/A')})" if result.get('banner_id') else ""
                            logger.info(f"Face {status}: {result['name']}{banner_info} - Confidence: {result['confidence']:.2f}")
                    
                    if sign_results:
                        for detection in sign_results:
                            logger.info(f"Sign detected: {detection['class_name']} ({detection['confidence']:.2f})")
                
                # Display frame
                if not headless:
                    annotated_frame = self.annotate_frame(frame, face_results, sign_results)
                    cv2.imshow("Integrated Recognition System", annotated_frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('s'):
                        timestamp = int(time.time())
                        filename = f"integrated_system_{timestamp}.jpg"
                        cv2.imwrite(filename, annotated_frame)
                        logger.info(f"Saved frame: {filename}")
                
                # Small delay for CPU
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("Stopping integrated system...")
        
        finally:
            if self.camera:
                self.camera.release()
            cv2.destroyAllWindows()
            logger.info("Integrated system stopped")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Integrated Facial Recognition and Sign Detection System")
    parser.add_argument("--headless", action="store_true", help="Run without GUI display")
    parser.add_argument("--no-face", action="store_true", help="Disable facial recognition")
    parser.add_argument("--no-signs", action="store_true", help="Disable sign detection")
    parser.add_argument("--robot", action="store_true", help="Use real robot hardware")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--confidence", type=float, default=0.5, help="Sign detection confidence threshold")
    parser.add_argument("--sign-model", default="yolov8n.pt", help="Path to YOLO sign detection model")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Create integrated system
    system = IntegratedRecognitionSystem(
        enable_face_recognition=not args.no_face,
        enable_sign_detection=not args.no_signs,
        use_robot_hardware=args.robot,
        confidence_threshold=args.confidence,
        sign_model_path=args.sign_model
    )
    
    # Run the system
    system.run_integrated_system(
        camera_index=args.camera,
        headless=args.headless
    )

if __name__ == "__main__":
    main()