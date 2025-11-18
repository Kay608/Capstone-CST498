#!/usr/bin/env python3
"""
Camera Diagnostic Script for Raspberry Pi
Helps identify camera access issues and provides solutions
"""

import cv2
import sys
import os
import subprocess

def check_camera_permissions():
    """Check if user has camera permissions"""
    print("=== Camera Permissions Check ===")
    try:
        # Check if user is in video group
        result = subprocess.run(['groups'], capture_output=True, text=True)
        groups = result.stdout.strip()
        if 'video' in groups:
            print("✓ User is in 'video' group")
        else:
            print("✗ User NOT in 'video' group")
            print("  Fix: sudo usermod -a -G video $USER")
            print("  Then logout and login again")
    except Exception as e:
        print(f"Could not check groups: {e}")

def check_camera_devices():
    """Check available camera devices"""
    print("\n=== Camera Device Check ===")
    
    # Check /dev/video* devices
    video_devices = []
    for i in range(5):
        device_path = f"/dev/video{i}"
        if os.path.exists(device_path):
            video_devices.append(device_path)
    
    if video_devices:
        print(f"✓ Found video devices: {video_devices}")
    else:
        print("✗ No /dev/video* devices found")
        print("  This could mean:")
        print("  - Camera not connected")
        print("  - Camera drivers not loaded")
        print("  - Camera disabled in raspi-config")

def check_picamera_config():
    """Check Pi Camera configuration"""
    print("\n=== Pi Camera Configuration ===")
    
    try:
        # Check if camera is enabled in config
        with open('/boot/config.txt', 'r') as f:
            config_content = f.read()
            
        if 'camera_auto_detect=1' in config_content:
            print("✓ Camera auto-detect enabled")
        elif 'start_x=1' in config_content:
            print("✓ Legacy camera support enabled")
        else:
            print("✗ Camera not enabled in /boot/config.txt")
            print("  Fix: Add 'camera_auto_detect=1' to /boot/config.txt")
            print("  Or run: sudo raspi-config -> Interface Options -> Camera")
            
    except FileNotFoundError:
        print("Could not read /boot/config.txt")
    except Exception as e:
        print(f"Error checking config: {e}")

def test_picamera2():
    """Test picamera2 library"""
    print("\n=== Picamera2 Test ===")
    try:
        from picamera2 import Picamera2
        print("✓ picamera2 library available")
        
        try:
            picam2 = Picamera2()
            print("✓ Picamera2 instance created")
            
            config = picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            picam2.configure(config)
            print("✓ Camera configured")
            
            picam2.start()
            print("✓ Camera started")
            
            frame = picam2.capture_array()
            print(f"✓ Frame captured: {frame.shape}")
            
            picam2.stop()
            print("✓ Camera stopped successfully")
            
        except Exception as e:
            print(f"✗ Picamera2 test failed: {e}")
            
    except ImportError:
        print("✗ picamera2 not available")
        print("  Install: sudo apt install -y python3-picamera2")

def test_opencv_camera():
    """Test OpenCV camera access"""
    print("\n=== OpenCV Camera Test ===")
    
    for device_id in range(3):
        print(f"Testing device {device_id}...")
        try:
            cap = cv2.VideoCapture(device_id)
            
            if cap.isOpened():
                print(f"✓ Device {device_id} opened successfully")
                
                # Try to read a frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✓ Frame captured from device {device_id}: {frame.shape}")
                    cap.release()
                    return device_id
                else:
                    print(f"✗ Could not capture frame from device {device_id}")
            else:
                print(f"✗ Could not open device {device_id}")
                
            cap.release()
            
        except Exception as e:
            print(f"✗ Error with device {device_id}: {e}")
    
    return None

def test_gstreamer_pipeline():
    """Test GStreamer pipeline for Pi Camera"""
    print("\n=== GStreamer Pipeline Test ===")
    
    pipelines = [
        # Pi Camera CSI pipeline
        "libcamerasrc ! video/x-raw,format=BGR ! videoconvert ! appsink",
        # USB camera pipeline  
        "v4l2src device=/dev/video0 ! video/x-raw,format=BGR ! videoconvert ! appsink"
    ]
    
    for i, pipeline in enumerate(pipelines):
        print(f"Testing pipeline {i+1}: {pipeline}")
        try:
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    print(f"✓ Pipeline {i+1} works: {frame.shape}")
                    cap.release()
                    return pipeline
                else:
                    print(f"✗ Pipeline {i+1} opened but no frame")
            else:
                print(f"✗ Pipeline {i+1} failed to open")
            cap.release()
        except Exception as e:
            print(f"✗ Pipeline {i+1} error: {e}")
    
    return None

def check_system_info():
    """Check system information"""
    print("\n=== System Information ===")
    
    try:
        # Check OS version
        with open('/etc/os-release', 'r') as f:
            os_info = f.read()
        print("OS:", [line for line in os_info.split('\n') if 'PRETTY_NAME' in line][0])
    except:
        pass
    
    try:
        # Check kernel version
        result = subprocess.run(['uname', '-r'], capture_output=True, text=True)
        print("Kernel:", result.stdout.strip())
    except:
        pass
    
    try:
        # Check if this is a Pi
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        if 'Raspberry Pi' in cpuinfo:
            print("✓ Running on Raspberry Pi")
        else:
            print("✗ Not running on Raspberry Pi")
    except:
        pass

def main():
    print("Camera Diagnostic Script")
    print("========================")
    
    check_system_info()
    check_camera_permissions() 
    check_camera_devices()
    check_picamera_config()
    test_picamera2()
    working_device = test_opencv_camera()
    working_pipeline = test_gstreamer_pipeline()
    
    print("\n=== Summary & Recommendations ===")
    
    if working_device is not None:
        print(f"✓ OpenCV can access camera on device {working_device}")
    
    if working_pipeline:
        print(f"✓ GStreamer pipeline works: {working_pipeline}")
        
    print("\nCommon fixes:")
    print("1. Enable camera: sudo raspi-config -> Interface Options -> Camera")
    print("2. Add user to video group: sudo usermod -a -G video $USER")
    print("3. Install picamera2: sudo apt install -y python3-picamera2")
    print("4. Reboot after making changes")
    print("5. Check camera cable connection")

if __name__ == "__main__":
    main()