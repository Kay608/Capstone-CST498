# Quick Test Commands

## Local Development (Windows/Mac)

### Test with GUI (simulated robot)
```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux
python integrated_recognition_system.py --no-signs
```

### Capture snapshot for poster assets
```bash
python tools/sim_harness.py  # Use "Capture Face Snapshot" button
```

## Raspberry Pi Testing

### Test with display attached
```bash
source .venv/bin/activate
python integrated_recognition_system.py --no-signs
```

### Test headless (no display)
```bash
python integrated_recognition_system.py --headless --no-signs
```

### Test with robot integration
```bash
python integrated_recognition_system.py --headless --no-signs --robot
```

## Service Management

### Start service
```bash
sudo systemctl start face-recognition.service
```

### Stop service
```bash
sudo systemctl stop face-recognition.service
```

### Check status
```bash
sudo systemctl status face-recognition.service
```

### View logs
```bash
# Last 50 lines
sudo journalctl -u face-recognition.service -n 50

# Live tail
sudo journalctl -u face-recognition.service -f

# Since boot
sudo journalctl -u face-recognition.service -b
```

### Enable auto-start
```bash
sudo systemctl enable face-recognition.service
```

### Disable auto-start
```bash
sudo systemctl disable face-recognition.service
```

## Diagnostic Commands

### Check camera
```bash
ls /dev/video*
v4l2-ctl --list-devices
```

### Check I2C (robot)
```bash
sudo i2cdetect -y 1
```

### Test database connection
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('DB configured:', bool(os.getenv('DB_HOST')))"
```

### Load face encodings test
```bash
python -c "from recognition_core import load_encodings_from_db; e,n = load_encodings_from_db(); print(f'Loaded {len(n)} faces')"
```

### Check Python packages
```bash
pip list | grep -E "face-recognition|opencv|numpy|pymysql"
```

## Performance Monitoring

### System resources
```bash
htop
```

### Camera test with fps
```bash
python -c "import cv2; import time; cap = cv2.VideoCapture(0); start = time.time(); frames = 0; 
while time.time() - start < 5: ret, _ = cap.read(); frames += 1; 
cap.release(); print(f'FPS: {frames/5:.1f}')"
```

### Recognition performance test
```bash
time python ai_facial_recognition.py --snapshot --output /tmp/test.jpg
```
