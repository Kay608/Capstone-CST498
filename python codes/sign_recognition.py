#!/usr/bin/env python3
"""
Enhanced Traffic Sign Recognition using YOLOv8
==============================================

This module provides traffic sign detection and classification using YOLOv8.
It can work with both custom-trained traffic sign models and general object detection.
"""

from ultralytics import YOLO
import cv2
import numpy as np
import os
from pathlib import Path

class TrafficSignDetector:
    def __init__(self, model_path='yolov8n.pt', confidence_threshold=0.5):
        """
        Initialize the traffic sign detector.
        
        Args:
            model_path (str): Path to the YOLOv8 model file
            confidence_threshold (float): Minimum confidence for detections
        """
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path
        self.model = None
        self.class_names = None
        
        # Try to load the model
        self.load_model()
        
        # Traffic sign class mapping (for custom models)
        self.traffic_sign_classes = {
            0: 'Speed limit (20km/h)',
            1: 'Speed limit (30km/h)', 
            2: 'Speed limit (50km/h)',
            3: 'Speed limit (60km/h)',
            4: 'Speed limit (70km/h)',
            5: 'Speed limit (80km/h)',
            6: 'End of speed limit (80km/h)',
            7: 'Speed limit (100km/h)',
            8: 'Speed limit (120km/h)',
            9: 'No passing',
            10: 'No passing veh over 3.5 tons',
            11: 'Right-of-way at intersection',
            12: 'Priority road',
            13: 'Yield',
            14: 'Stop',
            15: 'No vehicles',
            16: 'Veh > 3.5 tons prohibited',
            17: 'No entry',
            18: 'General caution',
            19: 'Dangerous curve left',
            20: 'Dangerous curve right',
            21: 'Double curve',
            22: 'Bumpy road',
            23: 'Slippery road',
            24: 'Road narrows on the right',
            25: 'Road work',
            26: 'Traffic signals',
            27: 'Pedestrians',
            28: 'Children crossing',
            29: 'Bicycles crossing',
            30: 'Beware of ice/snow',
            31: 'Wild animals crossing',
            32: 'End speed + passing limits',
            33: 'Turn right ahead',
            34: 'Turn left ahead',
            35: 'Ahead only',
            36: 'Go straight or right',
            37: 'Go straight or left',
            38: 'Keep right',
            39: 'Keep left',
            40: 'Roundabout mandatory',
            41: 'End of no passing',
            42: 'End no passing veh > 3.5 tons'
        }
    
    def load_model(self):
        """Load the YOLOv8 model."""
        try:
            # Check if model file exists
            if not os.path.exists(self.model_path):
                print(f"Model file not found: {self.model_path}")
                # Try to find yolov8n.pt in the project
                project_root = Path(__file__).parent.parent
                fallback_path = project_root / 'yolov8n.pt'
                if fallback_path.exists():
                    self.model_path = str(fallback_path)
                    print(f"Using fallback model: {self.model_path}")
                else:
                    print("No model found. Please download yolov8n.pt")
                    return
            
            self.model = YOLO(self.model_path)
            print(f"Successfully loaded YOLOv8 model: {self.model_path}")
            
            # Get class names if available
            if hasattr(self.model, 'names'):
                self.class_names = self.model.names
                print(f"Model has {len(self.class_names)} classes")
            
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None
    
    def predict_sign(self, frame):
        """
        Predict traffic signs in the frame.
        
        Args:
            frame: Input image/frame from camera
            
        Returns:
            list: Detection results with class_id, confidence, bbox, and class_name
        """
        if self.model is None:
            print("Model not loaded")
            return []
        
        try:
            # Run inference
            results = self.model(frame, verbose=False)
            
            detections = []
            
            # Process results
            if len(results) > 0:
                result = results[0]
                
                # Check if any detections were made
                if result.boxes is not None and len(result.boxes) > 0:
                    # Get all detections above confidence threshold
                    confidences = result.boxes.conf.cpu().numpy()
                    classes = result.boxes.cls.cpu().numpy()
                    boxes = result.boxes.xyxy.cpu().numpy()
                    
                    for i, confidence in enumerate(confidences):
                        if confidence > self.confidence_threshold:
                            class_id = int(classes[i])
                            bbox = boxes[i]
                            
                            # Get class name
                            class_name = "Unknown"
                            if self.class_names and class_id in self.class_names:
                                class_name = self.class_names[class_id]
                            elif class_id in self.traffic_sign_classes:
                                class_name = self.traffic_sign_classes[class_id]
                            
                            detection = {
                                'class_id': class_id,
                                'confidence': float(confidence),
                                'bbox': bbox.tolist(),  # [x1, y1, x2, y2]
                                'class_name': class_name
                            }
                            detections.append(detection)
            
            return detections
            
        except Exception as e:
            print(f"Error in sign prediction: {e}")
            return []
    
    def predict_best_sign(self, frame):
        """
        Get the best (highest confidence) traffic sign detection.
        
        Args:
            frame: Input image/frame
            
        Returns:
            dict: Best detection or None if no detection
        """
        detections = self.predict_sign(frame)
        
        if detections and len(detections) > 0:
            # Return the detection with highest confidence
            best_detection = max(detections, key=lambda x: x['confidence'])
            return best_detection
        
        return None

# Legacy function for backward compatibility
def predict_sign(frame):
    """
    Legacy function that returns just the class ID of the best detection.
    
    Args:
        frame: Input image/frame
        
    Returns:
        int: Class ID of best detection, or -1 if no detection
    """
    global detector
    
    # Initialize detector if not exists
    if 'detector' not in globals():
        detector = TrafficSignDetector()
    
    best_detection = detector.predict_best_sign(frame)
    
    if best_detection:
        return best_detection['class_id']
    else:
        return -1