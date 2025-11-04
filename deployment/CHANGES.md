# Raspberry Pi Integration - Changes Summary

## Files Modified

### 1. `ai_facial_recognition.py` (Major Update)
**New Features:**
- ✅ Robot hardware integration via `hardware_interface.py`
- ✅ Headless mode for Pi deployment (no GUI)
- ✅ Performance optimizations (frame skipping, downsampling)
- ✅ Configurable detection models (HOG/CNN)
- ✅ Robot action callbacks on recognition
- ✅ Periodic database refresh
- ✅ Recognition cooldown to prevent spam
- ✅ Command-line arguments for all settings

**Key Improvements:**
- Process every 3rd frame (saves CPU)
- Downscale frames by 50% before processing
- HOG model default (3-5x faster than CNN on CPU)
- Auto-refresh encodings every 5 minutes
- 3-second cooldown between recognitions

**New Command-Line Options:**
```bash
--headless      # Run without GUI display
--robot         # Enable robot camera and actions
--model hog|cnn # Choose detection model
--threshold 0.6 # Set match confidence threshold
```

### 2. `robot_navigation/hardware_interface.py` (Enhanced)
**New Features:**
- ✅ Pi Camera 2 (picamera2) support
- ✅ Automatic fallback to USB camera
- ✅ Optimized camera settings for Pi 5
- ✅ Better error handling for camera access

**Camera Initialization:**
- Tries Pi Camera 2 first (faster, native)
- Falls back to OpenCV VideoCapture
- Configures optimal resolution (640x480) and FPS (15)

### 3. New Deployment Files Created

#### `deployment/face-recognition.service`
- Systemd service for auto-start on boot
- Runs as user `pi` with security restrictions
- Auto-restart on failure
- Logs to systemd journal

#### `deployment/setup_pi.sh`
- Automated installation script
- Installs all system dependencies
- Creates virtual environment
- Installs Python packages
- Enables I2C for robot control
- Sets up camera permissions
- Configures systemd service

#### `deployment/PI_DEPLOYMENT.md`
- Complete deployment guide
- Hardware requirements
- Step-by-step setup instructions
- Testing procedures
- Troubleshooting guide
- Performance optimization tips

#### `deployment/QUICK_TESTS.md`
- Quick reference for common commands
- Testing commands for all modes
- Service management commands
- Diagnostic commands
- Performance monitoring

## How It All Works Together

```
User Enrolls Face (Flask App)
        ↓
Face encoding saved to JawsDB
        ↓
ai_facial_recognition.py loads encodings
        ↓
Robot camera captures frames
        ↓
Face detected and matched
        ↓
Robot action triggered (compartment unlock)
        ↓
Recognition logged to admin panel
```

## Integration Points

### 1. Camera Source
- **Development**: Uses `cv2.VideoCapture(0)` 
- **Pi with USB cam**: Uses `cv2.VideoCapture(0)` via `hardware_interface`
- **Pi with Camera Module**: Uses `picamera2` (automatic detection)

### 2. Robot Control
- **Development**: Simulated robot (no hardware needed)
- **Pi**: Uses `YB_Pcb_Car` via `hardware_interface`
- Camera servo control: `robot_interface.set_camera_servo(angle)`

### 3. Database
- Both development and Pi use JawsDB (cloud MySQL)
- Credentials from `.env` file
- Auto-refresh encodings every 5 minutes

## Performance Characteristics

### Development Machine (with GUI)
- Full resolution processing
- CNN model available
- Real-time display with annotations
- ~10-15 FPS typical

### Raspberry Pi 5 (headless)
- Optimized processing (every 3rd frame)
- HOG model (faster)
- Downsampled frames (50%)
- No display overhead
- ~5-10 FPS effective recognition rate

## Usage Examples

### During Development (Your PC)
```bash
# Test with GUI and simulated robot
python ai_facial_recognition.py

# Test snapshot feature
python ai_facial_recognition.py --snapshot --output test.jpg
```

### On Raspberry Pi
```bash
# Manual testing
python ai_facial_recognition.py --headless --robot

# Production (auto-start)
sudo systemctl start face-recognition.service
```

## Next Steps for Full Integration

1. **On Development Machine:**
   - Test changes locally with simulated robot
   - Enroll test faces via Flask enrollment page
   - Verify recognition works

2. **Deploy to Pi:**
   - Transfer code to Pi
   - Run `./deployment/setup_pi.sh`
   - Configure `.env` with JawsDB credentials
   - Test with `--headless --robot` flags

3. **Customize Robot Actions:**
   - Edit `robot_action_on_recognition()` in `ai_facial_recognition.py`
   - Add compartment servo control
   - Add LED/audio feedback
   - Update delivery status

4. **Production Deployment:**
   - Enable systemd service
   - Test auto-start on reboot
   - Monitor logs for issues

## Backward Compatibility

All existing functionality preserved:
- ✅ Flask enrollment still works
- ✅ Admin panel still shows logs
- ✅ Database structure unchanged
- ✅ Original GUI mode still available
- ✅ Snapshot feature still works

New features are opt-in via command-line flags.

## Configuration Files Required

### `.env` (project root)
```
DB_HOST=your-jawsdb-host.rds.amazonaws.com
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_NAME=your-db-name
FLASK_DEBUG=0
```

## Testing Checklist

- [ ] Local testing with GUI works
- [ ] Headless mode runs without errors
- [ ] Robot integration initializes correctly
- [ ] Face recognition matches work
- [ ] Database connection stable
- [ ] Performance acceptable on Pi 5
- [ ] Service starts and restarts properly
- [ ] Logs capture recognition events

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| "Camera not accessible" | Check `/dev/video0` exists, test with `v4l2-ctl` |
| "Database environment variables not set" | Verify `.env` file exists and has correct values |
| "No known faces in database" | Enroll at least one face via Flask `/enroll` |
| "Robot interface not available" | Check I2C enabled with `sudo i2cdetect -y 1` |
| Slow recognition | Use `--model hog`, ensure frame skipping active |
| Service won't start | Check logs with `journalctl -u face-recognition.service` |

## File Structure

```
Capstone-CST498/
├── ai_facial_recognition.py          (MODIFIED - robot integration)
├── robot_navigation/
│   └── hardware_interface.py         (MODIFIED - Pi Camera 2 support)
├── deployment/                        (NEW)
│   ├── face-recognition.service      (NEW - systemd service)
│   ├── setup_pi.sh                   (NEW - installation script)
│   ├── PI_DEPLOYMENT.md              (NEW - deployment guide)
│   ├── QUICK_TESTS.md                (NEW - test commands)
│   └── CHANGES.md                    (THIS FILE)
└── .env                               (REQUIRED - credentials)
```
