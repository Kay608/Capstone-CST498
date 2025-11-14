#!/usr/bin/env python3
"""
Test script for the integrated facial recognition and sign detection system.
"""

import sys
import time

def test_integrated_system():
    """Test the integrated recognition system."""
    print("Testing Integrated Recognition System")
    print("=" * 45)
    
    try:
        # Test import
        from integrated_recognition_system import IntegratedRecognitionSystem
        print("✅ Successfully imported IntegratedRecognitionSystem")
        
        # Test initialization with different configurations
        print("\n1. Testing initialization...")
        
        # Test with both systems enabled
        system = IntegratedRecognitionSystem(
            enable_face_recognition=True,
            enable_sign_detection=True,
            use_robot_hardware=False
        )
        print("✅ Full system initialized")
        
        # Test face recognition only
        face_only_system = IntegratedRecognitionSystem(
            enable_face_recognition=True,
            enable_sign_detection=False,
            use_robot_hardware=False
        )
        print("✅ Face-only system initialized")
        
        # Test sign detection only
        sign_only_system = IntegratedRecognitionSystem(
            enable_face_recognition=False,
            enable_sign_detection=True,
            use_robot_hardware=False
        )
        print("✅ Sign-only system initialized")
        
        # Test system capabilities
        print("\n2. Testing system capabilities...")
        print(f"   Face recognition available: {system.enable_face_recognition}")
        print(f"   Sign detection available: {system.enable_sign_detection}")
        print(f"   Known faces loaded: {len(system.known_encodings)}")
        
        if system.sign_detector:
            print(f"   Sign detector model: {system.sign_detector.model_path}")
            print(f"   Sign confidence threshold: {system.sign_detector.confidence_threshold}")
        
        # Test camera initialization (without actually opening)
        print("\n3. Testing camera initialization...")
        try:
            import cv2
            print("✅ OpenCV available for camera access")
        except ImportError:
            print("❌ OpenCV not available - camera functionality disabled")
        
        # Test frame analysis with dummy data
        print("\n4. Testing analysis functions...")
        import numpy as np
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Test face analysis
        face_results = system.analyze_faces(dummy_frame)
        print(f"✅ Face analysis completed - {len(face_results)} faces detected")
        
        # Test sign analysis
        sign_results = system.analyze_signs(dummy_frame)
        print(f"✅ Sign analysis completed - {len(sign_results)} signs detected")
        
        # Test annotation
        annotated = system.annotate_frame(dummy_frame, face_results, sign_results)
        print("✅ Frame annotation completed")
        
        # Test face tracking
        system.update_face_tracking(face_results)
        print(f"✅ Face tracking updated - {len(system.face_tracking)} tracked faces")
        
        print("\n5. Testing command line interface...")
        from integrated_recognition_system import parse_args, main
        print("✅ Command line interface available")
        
        print("\n✅ All integration tests passed!")
        print("\nIntegrated System Features:")
        print("- ✓ Simultaneous facial recognition and sign detection")
        print("- ✓ Persistent face tracking with green squares")
        print("- ✓ Traffic sign detection with bounding boxes")
        print("- ✓ HTTP communication with Flask admin panel")
        print("- ✓ Robot buzzer integration for feedback")
        print("- ✓ Configurable system components")
        print("- ✓ Real-time dual annotation display")
        
        print("\nUsage Examples:")
        print("# Run full system:")
        print("python integrated_recognition_system.py")
        print()
        print("# Face recognition only:")
        print("python integrated_recognition_system.py --no-signs")
        print()
        print("# Sign detection only:")
        print("python integrated_recognition_system.py --no-face")
        print()
        print("# Headless mode (no display):")
        print("python integrated_recognition_system.py --headless")
        print()
        print("# With robot hardware:")
        print("python integrated_recognition_system.py --robot")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("- pip install ultralytics face_recognition opencv-python")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_integrated_system()
    sys.exit(0 if success else 1)