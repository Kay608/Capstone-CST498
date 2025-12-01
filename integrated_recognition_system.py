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
import time
import os
import sys
import argparse
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
import logging

# Add paths for imports
sys.path.append('python codes')
sys.path.append('.')

# Core imports
try:
    from recognition_core import (
        log_verification_http,
        process_order_fulfillment,
        FLASK_APP_URL,
        FACE_DETECTION_MODEL,
        MATCH_THRESHOLD,
        FaceRecognitionEngine
    )
    FACIAL_RECOGNITION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Facial recognition not available: {e}")
    FACIAL_RECOGNITION_AVAILABLE = False

try:
    from robot_navigation.hardware_interface import create_hardware_interface
except ImportError as e:
    create_hardware_interface = None  # type: ignore
    print(f"Warning: Robot hardware interface not available: {e}")

try:
    from sign_recognition import TrafficSignDetector
    SIGN_DETECTION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Sign detection not available: {e}")
    SIGN_DETECTION_AVAILABLE = False

PICAMERA2_AVAILABLE = False
PICAMERA2_IMPORT_ERROR: Optional[str] = None


def _attempt_picamera2_import() -> bool:
    global Picamera2  # type: ignore[reportUndefinedVariable]
    global PICAMERA2_IMPORT_ERROR
    try:
        from picamera2 import Picamera2  # type: ignore[import-not-found]
        PICAMERA2_IMPORT_ERROR = None
        return True
    except ImportError as exc:
        PICAMERA2_IMPORT_ERROR = str(exc)
    except Exception as exc:  # noqa: BLE001
        PICAMERA2_IMPORT_ERROR = str(exc)
    return False


if _attempt_picamera2_import():
    PICAMERA2_AVAILABLE = True
else:
    for candidate in (
        Path("/usr/lib/python3/dist-packages"),
        Path("/usr/local/lib/python3/dist-packages"),
        Path(f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages"),
        Path(f"/usr/local/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages"),
    ):
        if not candidate.exists():
            continue
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.append(candidate_str)
        if _attempt_picamera2_import():
            PICAMERA2_AVAILABLE = True
            break

if not PICAMERA2_AVAILABLE:
    try:
        from picamera2 import Picamera2  # type: ignore[import-not-found]
    except ImportError as exc:  # noqa: F401
        PICAMERA2_IMPORT_ERROR = str(exc)

# Configure logging for both console and file tailing by the harness
LOG_PATH = Path("/tmp/integrated_recognition_gui.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

PREVIEW_PATH = Path("/tmp/integrated_preview.jpg")

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

if not PICAMERA2_AVAILABLE and PICAMERA2_IMPORT_ERROR:
    logger.warning("Picamera2 module not available: %s", PICAMERA2_IMPORT_ERROR)

class IntegratedRecognitionSystem:
    """
    Integrated system for facial recognition and traffic sign detection.
    """
    
    def __init__(self, 
                 enable_face_recognition=True,
                 enable_sign_detection=True,
                 use_robot_hardware=False,
                 confidence_threshold=0.5,
                 sign_model_path='yolov8n.pt',
                 cache_first=False):
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
        self.face_tracking = {}
        self.sign_detector = None
        self.robot_interface = None
        self.face_engine = None
        self.cache_first = cache_first
        self.picamera: Optional[Any] = None
        self.camera_backend: Optional[str] = None
        self.use_robot_hardware = use_robot_hardware
        self._last_preview_save = 0.0
        
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

        if not FACIAL_RECOGNITION_AVAILABLE:
            logger.warning("Facial recognition utilities unavailable - disabling facial recognition")
            self.enable_face_recognition = False
            return

        try:
            self.face_engine = FaceRecognitionEngine(
                frame_scale=self.FRAME_SCALE,
                frame_skip=1,
                detection_model=FACE_DETECTION_MODEL,
                cache_first=self.cache_first,
            )
            known_count = len(self.face_engine.known_encodings)
            logger.info(f"Loaded {known_count} face encoding(s) from JawsDB")
            if known_count:
                logger.info(f"Known faces: {self.face_engine.known_names}")
        except Exception as e:
            logger.error(f"Failed to initialize facial recognition: {e}")
            self.face_engine = None
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
        if create_hardware_interface is None:
            logger.warning("Robot hardware interface not available - robot actions disabled")
            self.robot_interface = None
            return

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
        # Release any existing camera before reinitializing
        if self.camera is not None:
            try:
                if self.camera.isOpened():
                    self.camera.release()
            finally:
                self.camera = None

        if self.picamera is not None:
            try:
                self.picamera.stop()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self.picamera = None

        if (
            self.use_robot_hardware
            and self.robot_interface is not None
            and hasattr(self.robot_interface, "is_available")
            and self.robot_interface.is_available()
            and hasattr(self.robot_interface, "get_camera_frame")
        ):
            logger.info("Attempting to source frames from robot interface camera feed")
            for attempt in range(10):
                try:
                    frame = self.robot_interface.get_camera_frame()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Robot interface camera probe failed on attempt %s/10: %s",
                        attempt + 1,
                        exc,
                    )
                    frame = None

                if frame is not None and getattr(frame, "size", 0):
                    self.camera_backend = "robot_interface"
                    logger.info(
                        "Using camera provided by robot interface (backend=%s)",
                        getattr(self.robot_interface, "camera_type", "unknown"),
                    )
                    return True

                time.sleep(0.1)

            logger.error(
                "Robot interface camera did not deliver frames during probe; unable to start video stream"
            )
            self.camera_backend = None
            return False

        # Prefer Picamera2 when running on hardware and available
        if self.use_robot_hardware and PICAMERA2_AVAILABLE:
            try:
                logger.info("Attempting to open camera via Picamera2 backend")
                picam = Picamera2()
                config = picam.create_preview_configuration(
                    main={"format": "RGB888", "size": (640, 480)}
                )
                picam.configure(config)
                picam.start()
                time.sleep(0.5)
                self.picamera = picam
                self.camera_backend = "picamera2"
                logger.info("Camera initialized using Picamera2 backend")
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Picamera2 initialization failed: %s", exc)
                self.picamera = None

        backend_options = [("DEFAULT", None)]
        if hasattr(cv2, "CAP_V4L2"):
            backend_options.append(("CAP_V4L2", cv2.CAP_V4L2))
        backend_options.append(("CAP_ANY", cv2.CAP_ANY))

        for backend_name, backend_flag in backend_options:
            try:
                logger.info(
                    "Attempting to open camera index %s via %s backend", camera_index, backend_name
                )
                if backend_flag is None:
                    camera = cv2.VideoCapture(camera_index)
                else:
                    camera = cv2.VideoCapture(camera_index, backend_flag)

                if not camera.isOpened():
                    camera.release()
                    logger.warning(
                        "Camera index %s failed to open on backend %s", camera_index, backend_name
                    )
                    continue

                # Set camera properties tuned for the Pi bridge driver
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                camera.set(cv2.CAP_PROP_FPS, 30)
                camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Prefer MJPEG when available to reduce USB bandwidth
                try:
                    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                    if not camera.set(cv2.CAP_PROP_FOURCC, fourcc):
                        logger.debug("Camera backend %s rejected MJPG fourcc", backend_name)
                except Exception:  # noqa: BLE001
                    logger.debug("Camera backend %s does not support MJPG negotiation", backend_name)

                self.camera = camera
                self._warmup_camera()
                self.camera_backend = "opencv"
                logger.info(
                    "Camera initialized on index %s using backend %s", camera_index, backend_name
                )
                return True

            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Camera initialization error on backend %s: %s", backend_name, exc
                )

        # Fallback: try explicit device path if it exists (some OpenCV builds require this)
        device_path = Path(f"/dev/video{camera_index}")
        if device_path.exists():
            try:
                logger.info("Attempting to open camera via explicit path %s", device_path)
                camera = cv2.VideoCapture(str(device_path))
                if camera.isOpened():
                    self.camera = camera
                    self._warmup_camera()
                    self.camera_backend = "opencv"
                    logger.info("Camera initialized using explicit path %s", device_path)
                    return True
                camera.release()
                logger.warning("Explicit device path %s failed to open", device_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Device path open raised %s", exc)

        logger.error("Camera initialization failed on all backends for index %s", camera_index)
        self.camera_backend = None
        return False

    def _warmup_camera(self, discard_frames: int = 10, delay: float = 0.05) -> None:
        """Allow the sensor/ISP pipeline to stabilise before main capture."""
        if self.camera is None:
            return

        grabbed = 0
        for _ in range(discard_frames):
            ret, _ = self.camera.read()
            if not ret:
                break
            grabbed += 1
            time.sleep(delay)

        if grabbed == 0:
            logger.warning("Camera warmup returned zero frames; capture may still be starting up")
        else:
            logger.info("Camera warmup complete; discarded %s frame(s)", grabbed)

    def _update_preview_frame(self, frame: Optional[Any]) -> None:
        if frame is None:
            return
        now = time.time()
        if (now - self._last_preview_save) < 0.5:
            return
        self._last_preview_save = now
        try:
            cv2.imwrite(str(PREVIEW_PATH), frame)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Preview frame save failed: %s", exc)
    
    def analyze_faces(self, frame):
        """
        Analyze frame for faces and return recognition results.
        """
        if not self.enable_face_recognition or not self.face_engine:
            return []

        engine_results = self.face_engine.analyze_frame(frame, skip_frame_check=True)
        return [
            {
                "name": result.name,
                "matched": result.matched,
                "box": result.box,
                "confidence": result.confidence,
                "banner_id": result.banner_id,
            }
            for result in engine_results
        ]
    
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
                self._dispatch_async_events(tracked_face.copy())
                self._execute_robot_actions(tracked_face)
                
                self.last_recognition_time = current_time
                break

    def _dispatch_async_events(self, face_data: Dict[str, Any]) -> None:
        """Handle HTTP callbacks without blocking the video loop."""

        def _worker() -> None:
            try:
                log_verification_http(face_data['name'], True, face_data['confidence'], "Integrated System")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to log verification: {exc}")

            banner_id = face_data.get('banner_id')
            if not banner_id:
                return

            try:
                process_order_fulfillment(banner_id, face_data['name'])
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to process order: {exc}")

        threading.Thread(target=_worker, daemon=True).start()
    
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
        if self.enable_face_recognition and self.face_engine:
            known_faces_count = len(self.face_engine.known_encodings)
        else:
            known_faces_count = 0
        
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

        auto_headless = False
        if (
            not headless
            and sys.platform != "win32"
            and not os.environ.get("DISPLAY")
        ):
            logger.warning("No DISPLAY detected; enabling headless mode automatically")
            headless = True
            auto_headless = True
        
        # Initialize camera
        if not self._initialize_camera(camera_index):
            logger.error("Camera initialization failed")
            return
        
        logger.info("Integrated system active. Press 'q' to quit, 's' to save frame.")
        
        failure_count = 0
        max_failures_before_reinit = 5
        status_interval = 5.0
        last_status_log = time.time()
        faces_since_log = 0
        signs_since_log = 0

        try:
            while True:
                frame = None

                if self.camera_backend == "robot_interface" and self.robot_interface is not None:
                    try:
                        frame = self.robot_interface.get_camera_frame()
                    except Exception as exc:  # noqa: BLE001
                        frame = None
                        logger.warning(
                            "Robot interface camera read failed (attempt %s/%s): %s",
                            failure_count + 1,
                            max_failures_before_reinit,
                            exc,
                        )

                    if frame is None or getattr(frame, "size", 0) == 0:
                        failure_count += 1
                        logger.warning(
                            "Robot interface camera returned no frame (attempt %s/%s)",
                            failure_count,
                            max_failures_before_reinit,
                        )
                        if failure_count >= max_failures_before_reinit:
                            logger.error(
                                "Robot interface camera repeatedly failed; attempting reinitialization"
                            )
                            if not self._initialize_camera(camera_index):
                                logger.error(
                                    "Camera reinitialization unsuccessful; stopping system"
                                )
                                break
                            failure_count = 0
                        time.sleep(0.1)
                        continue

                    failure_count = 0

                elif self.camera_backend == "picamera2" and self.picamera is not None:
                    try:
                        frame = self.picamera.capture_array()
                        if frame is None:
                            raise RuntimeError("Picamera2 returned no frame")
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        failure_count = 0
                    except Exception as exc:  # noqa: BLE001
                        failure_count += 1
                        logger.warning(
                            "Picamera2 capture failed (attempt %s/%s): %s",
                            failure_count,
                            max_failures_before_reinit,
                            exc,
                        )
                        if failure_count >= max_failures_before_reinit:
                            logger.error(
                                "Picamera2 capture repeatedly failed; attempting reinitialization"
                            )
                            if not self._initialize_camera(camera_index):
                                logger.error(
                                    "Camera reinitialization unsuccessful; stopping system"
                                )
                                break
                            failure_count = 0
                        time.sleep(0.1)
                        continue

                else:
                    if self.camera is None:
                        logger.error("OpenCV camera backend unavailable; stopping system")
                        break

                    ret, frame = self.camera.read()
                    if not ret or frame is None:
                        failure_count += 1
                        logger.warning(
                            "Camera read failed (attempt %s/%s)",
                            failure_count,
                            max_failures_before_reinit,
                        )
                        if failure_count >= max_failures_before_reinit:
                            logger.error(
                                "Camera read repeatedly failed; attempting reinitialization"
                            )
                            if not self._initialize_camera(camera_index):
                                logger.error(
                                    "Camera reinitialization unsuccessful; stopping system"
                                )
                                break
                            failure_count = 0
                        time.sleep(0.1)
                        continue

                    failure_count = 0
                
                # Analyze frame
                face_results = self.analyze_faces(frame)
                sign_results = self.analyze_signs(frame)

                annotated_frame = self.annotate_frame(frame, face_results, sign_results)
                
                # Update face tracking
                if self.enable_face_recognition:
                    self.update_face_tracking(face_results)
                    self.process_face_recognition_events()
                
                # Log detections
                if face_results or sign_results:
                    recognized_people: List[str] = []
                    seen_identities = set()

                    if face_results:
                        for result in face_results:
                            status = "granted" if result["matched"] else "denied"
                            banner_id = result.get('banner_id')
                            banner_label = banner_id or "Unknown"
                            banner_info = f" (Banner ID: {banner_label})" if result["matched"] else ""
                            logger.info(
                                "Face %s: %s%s - Confidence: %.2f",
                                status,
                                result['name'],
                                banner_info,
                                result['confidence'],
                            )
                            if result["matched"]:
                                identity_key = (result['name'], banner_label)
                                if identity_key not in seen_identities:
                                    seen_identities.add(identity_key)
                                    recognized_people.append(f"{result['name']} (Banner ID: {banner_label})")
                        faces_since_log += len(face_results)

                    if sign_results:
                        person_logged = False
                        for detection in sign_results:
                            class_name = detection['class_name']
                            confidence = detection['confidence']
                            if class_name.lower() == "person":
                                if recognized_people and not person_logged:
                                    logger.info(
                                        "Person recognized: %s [detector confidence %.2f]",
                                        ", ".join(recognized_people),
                                        confidence,
                                    )
                                    person_logged = True
                                elif not recognized_people:
                                    logger.info(
                                        "Person detected but not recognized (confidence %.2f)",
                                        confidence,
                                    )
                                signs_since_log += 1
                                continue

                            logger.info(
                                "Sign detected: %s (%.2f)",
                                class_name,
                                confidence,
                            )
                            signs_since_log += 1

                        if recognized_people and not person_logged:
                            logger.info("Person recognized: %s", ", ".join(recognized_people))
                    elif recognized_people:
                        logger.info("Person recognized: %s", ", ".join(recognized_people))

                now = time.time()
                if now - last_status_log >= status_interval:
                    if faces_since_log or signs_since_log:
                        logger.info(
                            "Status: faces=%d, signs=%d detected in last %.0fs",
                            faces_since_log,
                            signs_since_log,
                            status_interval,
                        )
                    else:
                        logger.info(
                            "Status: no faces or signs detected in last %.0fs",
                            status_interval,
                        )
                    faces_since_log = 0
                    signs_since_log = 0
                    last_status_log = now
                
                # Display frame
                if not headless:
                    try:
                        cv2.imshow("Integrated Recognition System", annotated_frame)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "OpenCV GUI unavailable (%s); switching to headless mode", exc
                        )
                        headless = True
                        if not auto_headless:
                            cv2.destroyAllWindows()
                        continue

                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('s'):
                        timestamp = int(time.time())
                        filename = f"integrated_system_{timestamp}.jpg"
                        cv2.imwrite(filename, annotated_frame)
                        logger.info(f"Saved frame: {filename}")

                frame_for_preview = annotated_frame if annotated_frame is not None else frame
                self._update_preview_frame(frame_for_preview)
                
                # Small delay for CPU
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            logger.info("Stopping integrated system...")
        
        finally:
            if self.camera and self.camera_backend != "robot_interface":
                self.camera.release()
            if self.picamera is not None:
                try:
                    self.picamera.stop()
                except Exception:  # noqa: BLE001
                    pass
                self.picamera = None
            try:
                cv2.destroyAllWindows()
            except Exception:  # noqa: BLE001
                pass
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
    parser.add_argument("--cache-first", action="store_true", help="Load face encodings from cache before querying the database")
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
        sign_model_path=args.sign_model,
        cache_first=args.cache_first
    )
    
    # Run the system
    system.run_integrated_system(
        camera_index=args.camera,
        headless=args.headless
    )

if __name__ == "__main__":
    main()