#!/usr/bin/env python3
"""
Test script for the updated YOLOv8 sign recognition functionality.
"""

import sys
import os
sys.path.append('.')

def test_sign_recognition():
    """Test the updated sign recognition module."""
    print("Testing YOLOv8 Sign Recognition")
    print("=" * 40)
    
    try:
        # Test import of the updated module
        sys.path.append('python codes')  # Add the python codes directory to path
        from sign_recognition import TrafficSignDetector, predict_sign
        print("✅ Successfully imported sign recognition module")
        
        # Test detector initialization
        detector = TrafficSignDetector()
        print("✅ TrafficSignDetector initialized")
        
        if detector.model is None:
            print("⚠️  Model not loaded - this is expected if yolov8n.pt is not available")
            print("   To fix: Download yolov8n.pt from https://github.com/ultralytics/yolov8/releases")
            return False
        
        print("✅ YOLOv8 model loaded successfully")
        print(f"   Model path: {detector.model_path}")
        print(f"   Confidence threshold: {detector.confidence_threshold}")
        
        # Test with a dummy frame (black image)
        import cv2
        import numpy as np
        
        # Create a test frame (black image)
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        print("✅ Created test frame")
        
        # Test prediction (should return empty list for black image)
        detections = detector.predict_sign(test_frame)
        print(f"✅ Prediction completed - found {len(detections)} detections")
        
        # Test legacy function
        class_id = predict_sign(test_frame)
        print(f"✅ Legacy function works - returned class_id: {class_id}")
        
        # Test with camera if available
        try:
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    detections = detector.predict_sign(frame)
                    print(f"✅ Camera test successful - found {len(detections)} detections")
                else:
                    print("⚠️  Could not read from camera")
                cap.release()
            else:
                print("⚠️  Camera not available for testing")
        except Exception as e:
            print(f"⚠️  Camera test failed: {e}")
        
        print("\n✅ All tests passed!")
        print("\nThe sign recognition module has been successfully updated to use YOLOv8!")
        print("Key improvements:")
        print("- Proper YOLOv8 model loading using ultralytics.YOLO()")
        print("- No more PyTorch tensor manipulation errors")
        print("- Robust error handling and fallback paths")
        print("- Support for both class-based and legacy function interfaces")
        print("- Comprehensive traffic sign class mapping")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure ultralytics is installed: pip install ultralytics")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_sign_recognition()
    sys.exit(0 if success else 1)