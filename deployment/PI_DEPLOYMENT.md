# Raspberry Pi 5 Deployment Guide

## Overview
This guide covers deploying the facial recognition system on your Yahboom Raspbot with Raspberry Pi 5.

## Hardware Requirements
- Raspberry Pi 5 (4GB+ RAM recommended)
- Yahboom Raspbot platform
- Pi Camera Module or USB webcam
- microSD card (32GB+ recommended)
- Active internet connection

## Offline Operation

**The robot can now run WITHOUT internet!** 

The system uses a local cache of face encodings:
- **First sync** (needs internet): Downloads encodings from JawsDB
- **Offline operation**: Uses cached encodings (no internet needed)
- **Auto-sync**: Updates cache when internet available

### Preparing for Offline Use

```bash
# When you have internet, sync the cache:
python sync_encodings.py

# Check cache status:
python sync_encodings.py --check

# Now you can run offline:
python ai_facial_recognition.py --headless --robot --offline
```

## Quick Start

### 1. Initial Setup on Pi
```bash
# Clone repository to Pi
cd /home/pi
git clone <your-repo-url> Capstone-CST498
cd Capstone-CST498

# Make setup script executable
chmod +x deployment/setup_pi.sh

# Run automated setup
./deployment/setup_pi.sh
```

### 2. Configure Database Credentials
```bash
nano .env
```

Add your JawsDB credentials:
```
DB_HOST=your-host.rds.amazonaws.com
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=your-database
```

### 3. Test the System

**Interactive Mode (with display):**
```bash
source .venv/bin/activate
python ai_facial_recognition.py
```
Press ESC to exit.

**Headless Mode (for robot deployment):**
```bash
# With internet (syncs cache automatically)
python ai_facial_recognition.py --headless --robot

# Without internet (uses cached encodings)
python ai_facial_recognition.py --headless --robot --offline
```
Press Ctrl+C to exit.

**Command-Line Options:**
```bash
# Use CNN model (more accurate, slower)
python ai_facial_recognition.py --headless --robot --model cnn

# Adjust matching threshold
python ai_facial_recognition.py --headless --robot --threshold 0.6

# Take a snapshot
python ai_facial_recognition.py --snapshot --output test.jpg
```

### 4. Enable Auto-Start on Boot
```bash
sudo systemctl enable face-recognition.service
sudo systemctl start face-recognition.service
```

**Check service status:**
```bash
sudo systemctl status face-recognition.service
```

**View live logs:**
```bash
sudo journalctl -u face-recognition.service -f
```

**Stop service:**
```bash
sudo systemctl stop face-recognition.service
```

## Performance Optimization

### For Pi 5 (Recommended Settings)
```bash
# Headless mode with HOG model (fastest)
python ai_facial_recognition.py --headless --robot --model hog

# With Pi Camera 2 (automatically detected)
# Ensure picamera2 is installed
```

### Camera Options
- **Pi Camera Module**: Faster, better integration (recommended)
- **USB Webcam**: Fallback option, may have latency

### Troubleshooting Performance
If recognition is slow:
1. Use `--model hog` instead of `cnn`
2. Ensure Pi Camera 2 is being used (check logs)
3. Reduce frame processing in code (already optimized to every 3rd frame)
4. Close other CPU-intensive processes

## Integration with Robot Actions

The system automatically integrates with your `robot_navigation/hardware_interface.py`.

**Default Actions on Face Recognition:**
1. Centers camera servo
2. Logs recognition to console
3. Ready to trigger compartment unlock

**To customize robot actions**, edit `robot_action_on_recognition()` in `ai_facial_recognition.py`:

```python
def robot_action_on_recognition(result: dict) -> None:
    if not robot_interface or not robot_interface.is_available():
        return
    
    # Your custom actions here
    robot_interface.set_camera_servo(90)  # Center camera
    # Add servo control for compartment
    # robot_interface.Ctrl_Servo(servo_id, angle)
    # Play audio feedback
    # Update delivery status in DB
```

## Testing Without Robot Hardware

Use simulation mode on your development machine:
```bash
python ai_facial_recognition.py --model hog
```

The `hardware_interface.py` automatically uses simulated hardware when real hardware isn't available.

## Common Issues

### Camera Not Detected
```bash
# Check camera
ls /dev/video*
# Should show /dev/video0

# Test camera
v4l2-ctl --list-devices
```

### I2C Not Working (Robot Control)
```bash
# Check I2C
sudo i2cdetect -y 1
# Should show device at 0x16

# Enable I2C
sudo raspi-config
# Interface Options -> I2C -> Enable
```

### Database Connection Issues
```bash
# Test DB connection
python -c "import pymysql; print('pymysql OK')"

# Verify .env loaded
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('DB_HOST:', os.getenv('DB_HOST'))"

# If internet unavailable, use offline mode
python ai_facial_recognition.py --headless --robot --offline
```

### No Internet / Offline Operation
```bash
# First time: Sync cache when you have internet
python sync_encodings.py

# Check cache is ready
python sync_encodings.py --check

# Run offline
python ai_facial_recognition.py --headless --robot --offline
```

### Service Won't Start
```bash
# Check service logs
sudo journalctl -u face-recognition.service -n 50

# Test manually
cd /home/pi/Capstone-CST498
source .venv/bin/activate
python ai_facial_recognition.py --headless --robot
```

## System Architecture

```
┌─────────────────────────────────────────┐
│     ai_facial_recognition.py           │
│  (Main Recognition Loop - Headless)     │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       ↓                ↓
┌──────────────┐  ┌─────────────────────┐
│  JawsDB      │  │ hardware_interface  │
│  (Encodings) │  │  (Robot Control)    │
└──────────────┘  └──────┬──────────────┘
                         │
                  ┌──────┴──────┐
                  ↓             ↓
          ┌──────────────┐  ┌────────────┐
          │  Pi Camera 2 │  │ YB_Pcb_Car │
          │  (picamera2) │  │  (Motors)  │
          └──────────────┘  └────────────┘
```

## Production Checklist

- [ ] `.env` file configured with correct credentials
- [ ] Camera detected and functional
- [ ] I2C enabled and robot responds to commands
- [ ] At least one face enrolled in database
- [ ] Service starts and runs without errors
- [ ] Recognition working in headless mode
- [ ] Robot actions trigger correctly
- [ ] Service auto-starts on boot
- [ ] Logs being written correctly

## Monitoring

**View current performance:**
```bash
# CPU/Memory usage
htop

# Service status
systemctl status face-recognition.service

# Live recognition logs
sudo journalctl -u face-recognition.service -f
```

## Security Notes

- Keep `.env` file secure (never commit to git)
- Service runs as user `pi` (not root)
- Database uses SSL connection to JawsDB
- No face images stored locally (only encodings in DB)

## Updates

To update code on the Pi:
```bash
cd /home/pi/Capstone-CST498
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart face-recognition.service
```
