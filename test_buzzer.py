#!/usr/bin/env python3
"""Test buzzer functionality for Yahboom Raspbot facial recognition."""

import sys
import time

def test_buzzer_functionality():
    """Test the buzzer functionality in both simulated and real modes."""
    print("=== Yahboom Raspbot Buzzer Test ===")
    print()
    
    # Test 1: Test YB_Pcb_Car buzzer methods directly
    print("1. Testing YB_Pcb_Car buzzer methods...")
    try:
        from raspbot.YB_Pcb_Car import YB_Pcb_Car
        
        print("   ✓ YB_Pcb_Car imported successfully")
        
        # Test if we can create the car object (will fail if not on Pi)
        try:
            car = YB_Pcb_Car()
            print("   ✓ YB_Pcb_Car object created - hardware available")
            
            # Test buzzer methods
            print("   Testing buzzer methods...")
            car.Buzz_Short()
            print("     ✓ Buzz_Short() called")
            time.sleep(1)
            
            car.Buzz_Success() 
            print("     ✓ Buzz_Success() called")
            time.sleep(1)
            
            car.Buzz_Alert()
            print("     ✓ Buzz_Alert() called")
            
        except Exception as e:
            print(f"   ⚠ Cannot create YB_Pcb_Car object (not on Pi): {e}")
            
    except ImportError as e:
        print(f"   ⚠ YB_Pcb_Car not available: {e}")
    
    print()
    
    # Test 2: Test robot hardware interface 
    print("2. Testing robot hardware interface...")
    try:
        from robot_navigation.hardware_interface import create_hardware_interface
        
        # Test simulated interface
        print("   Testing simulated interface...")
        sim_robot = create_hardware_interface(use_simulation=True)
        
        if hasattr(sim_robot, 'robot') and sim_robot.robot:
            print("   ✓ Simulated robot.robot property available")
            sim_robot.robot.Buzz_Short()
            print("     ✓ Simulated Buzz_Short() works")
            sim_robot.robot.Buzz_Success()
            print("     ✓ Simulated Buzz_Success() works") 
            sim_robot.robot.Buzz_Alert()
            print("     ✓ Simulated Buzz_Alert() works")
        else:
            print("   ✗ Simulated robot.robot property not available")
            
        # Test real interface (will fall back to simulation if not on Pi)
        print("   Testing real hardware interface...")
        try:
            real_robot = create_hardware_interface(use_simulation=False)
            
            if hasattr(real_robot, 'robot') and real_robot.robot:
                print("   ✓ Real robot.robot property available")
                print("   Testing real buzzer (if on Pi)...")
                real_robot.robot.Buzz_Short()
                print("     ✓ Real Buzz_Short() called")
            else:
                print("   ⚠ Real robot hardware not available (not on Pi)")
                
        except Exception as e:
            print(f"   ⚠ Real hardware interface error: {e}")
            
    except ImportError as e:
        print(f"   ✗ Hardware interface not available: {e}")
    
    print()
    
    # Test 3: Test facial recognition integration
    print("3. Testing facial recognition integration...")
    try:
        from ai_facial_recognition import robot_action_on_recognition
        
        print("   ✓ robot_action_on_recognition function available")
        
        # Test simulated recognition result
        test_result = {
            'name': 'Test User',
            'matched': True,
            'confidence': 0.95,
            'banner_id': '123456789'
        }
        
        print("   Testing robot action with simulated recognition...")
        robot_action_on_recognition(test_result)
        print("     ✓ Robot action completed (check output above for buzzer)")
        
    except ImportError as e:
        print(f"   ✗ ai_facial_recognition not available: {e}")
    except Exception as e:
        print(f"   ✗ Robot action test failed: {e}")
    
    print()
    print("=== Buzzer Test Complete ===")
    print()
    print("Summary:")
    print("- YB_Pcb_Car now has Buzz_Short(), Buzz_Success(), and Buzz_Alert() methods")
    print("- Hardware interface exposes .robot property for direct buzzer access")
    print("- Simulated interface provides buzzer simulation for testing")
    print("- Facial recognition calls robot buzzer on successful face recognition")
    print()
    print("When running on Raspberry Pi with Yahboom Raspbot:")
    print("- Face recognition will play success sound pattern when face is recognized")
    print("- Buzzer uses I2C register 0x04 with frequency and duration parameters")
    print("- Success pattern: low-med-high pitch sequence for pleasant feedback")

if __name__ == "__main__":
    test_buzzer_functionality()