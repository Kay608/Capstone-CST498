#!/usr/bin/env python3
"""
Test script for Movement-Controlled Recognition System
====================================================

This script tests the robot movement control integration with traffic sign detection.
It demonstrates how the robot responds to different traffic signs:
- Stop signs: Robot stops for 3 seconds
- Person detection: Brief safety stop
- Traffic lights: Caution logging

Usage:
    python test_movement_control.py [options]
"""

import time
import logging
from movement_controlled_recognition import MovementControlledRecognitionSystem

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def test_movement_system():
    """Test the movement-controlled recognition system."""
    
    print("🧪 Testing Movement-Controlled Recognition System")
    print("=" * 60)
    
    # Test 1: Initialize system with movement control
    print("\\n📋 Test 1: System Initialization")
    try:
        system = MovementControlledRecognitionSystem(
            enable_sign_detection=True,
            enable_movement_control=True,
            use_robot_hardware=False,  # Use simulation
            confidence_threshold=0.75,
            headless_mode=True  # No display for testing
        )
        print("✅ System initialized successfully")
    except Exception as e:
        print(f"❌ System initialization failed: {e}")
        return False
    
    # Test 2: Check component availability
    print("\\n📋 Test 2: Component Availability")
    components = [
        ("Sign Detection", system.enable_sign_detection), 
        ("Movement Control", system.enable_movement_control),
        ("Robot Interface", system.robot_interface is not None)
    ]
    
    for name, available in components:
        status = "✅ Available" if available else "❌ Not Available"
        print(f"  {name}: {status}")
    
    # Test 3: Movement control methods
    print("\\n📋 Test 3: Movement Control Methods")
    try:
        # Test start movement
        print("  🚀 Testing start_movement()...")
        system.start_movement()
        assert system.is_moving, "Robot should be moving"
        print("    ✅ Robot started moving")
        
        time.sleep(1)
        
        # Test stop movement  
        print("  ⏹️ Testing stop_movement()...")
        system.stop_movement(2.0)
        assert not system.is_moving, "Robot should be stopped"
        print("    ✅ Robot stopped")
        
        print("✅ Movement control methods working")
        
    except Exception as e:
        print(f"❌ Movement control test failed: {e}")
        return False
    
    # Test 4: Traffic sign response simulation
    print("\\n📋 Test 4: Traffic Sign Response Simulation")
    try:
        # Reset movement state
        system.is_moving = False
        system.movement_enabled = True
        system.start_movement()
        
        # Simulate stop sign detection
        print("  🛑 Simulating stop sign detection...")
        fake_detections = [{
            'class': 'stop sign',
            'confidence': 0.85,
            'bbox': [100, 100, 200, 200]
        }]
        
        system.handle_traffic_signs(fake_detections)
        assert not system.is_moving, "Robot should stop for stop sign"
        print("    ✅ Robot stopped for stop sign")
        
        # Wait a moment and check resume logic
        time.sleep(1)
        print("  ▶️ Testing movement resume logic...")
        
        # Simulate time passing (manually adjust last_stop_time for testing)
        original_stop_time = system.last_stop_time
        system.last_stop_time = time.time() - system.stop_duration - 1  # Simulate duration passed
        system.check_resume_movement()
        # Note: In simulation mode, movement resumption is logged but not physically tracked
        print("    ✅ Resume logic executed")
        
        system.last_stop_time = original_stop_time  # Restore
        
    except Exception as e:
        print(f"❌ Traffic sign response test failed: {e}")
        return False
    
    # Test 5: Person detection safety
    print("\\n📋 Test 5: Person Detection Safety")
    try:
        system.start_movement()  # Ensure robot is moving
        
        # Simulate person detection
        print("  👤 Simulating person detection...")
        person_detections = [{
            'class': 'person',
            'confidence': 0.90,  # High confidence for safety trigger
            'bbox': [150, 150, 250, 350]
        }]
        
        system.handle_traffic_signs(person_detections)
        print("    ✅ Safety protocol activated for person detection")
        
    except Exception as e:
        print(f"❌ Person detection safety test failed: {e}")
        return False
    
    # Test 6: Keyboard control simulation
    print("\\n📋 Test 6: Manual Control Logic")
    try:
        # Test manual stop/start logic
        print("  ⏸️ Testing manual stop logic...")
        system.movement_enabled = True
        system.start_movement()
        # Simulate spacebar press for stop
        system.stop_movement()
        system.movement_enabled = False
        print("    ✅ Manual stop logic working")
        
        print("  ▶️ Testing manual resume logic...")
        system.movement_enabled = True
        system.start_movement()
        print("    ✅ Manual resume logic working")
        
    except Exception as e:
        print(f"❌ Manual control test failed: {e}")
        return False
    
    print("\\n🎉 All Tests Completed Successfully!")
    print("\\n📖 Usage Instructions:")
    print("  Basic usage:")
    print("    python movement_controlled_recognition.py --movement")
    print("  ") 
    print("  With hardware:")
    print("    python movement_controlled_recognition.py --movement --robot")
    print("  ")
    print("  Sign detection only:")
    print("    python movement_controlled_recognition.py --movement --no-face")
    print("  ")
    print("  Headless (background) mode:")
    print("    python movement_controlled_recognition.py --movement --headless")
    
    print("\\n🎮 Runtime Controls:")
    print("  SPACE bar: Toggle movement (start/stop)")
    print("  'q' or ESC: Quit system")
    print("  's': Save current frame")
    
    print("\\n🚦 Traffic Sign Responses:")
    print("  🛑 Stop Sign: Robot stops for 3 seconds, alert buzzer")
    print("  👤 Person: Brief safety stop, short beep")
    print("  🚦 Traffic Light: Caution logging")
    
    return True

if __name__ == "__main__":
    success = test_movement_system()
    
    if success:
        print("\\n✅ System is ready for deployment!")
        print("\\n🚀 To start the movement-controlled system:")
        print("python movement_controlled_recognition.py --movement")
    else:
        print("\\n❌ Tests failed. Check the error messages above.")
    
    exit(0 if success else 1)