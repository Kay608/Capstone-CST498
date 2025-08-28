# Development Setup Guide

## Quick Start (Development Mode)

Your project now supports **simulation mode** so you can develop and test without the physical Yahboom Raspbot!

### 1. Environment Setup

```bash
# Create virtual environment (if not already done)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Test the System

```bash
# Test hardware abstraction (simulation)
python robot_navigation/hardware_interface.py

# Test navigation system
python robot_navigation/pathfinding.py

# Test robot controller
python robot_navigation/robot_controller.py

# Start Flask API (simulation mode)
python flask_api/app.py
```

### 3. Mobile App Development

```bash
cd mobile_app
flutter pub get
flutter run
```

## Development Workflow

### Current Status ✅
- **Fixed**: Import issues in `localization.py`
- **Added**: Hardware abstraction layer for development without robot
- **Working**: Simulated robot with realistic physics
- **Working**: Face registration and recognition API
- **Working**: Mobile app with mDNS service discovery

### Simulation vs Real Hardware

The system automatically uses simulation mode by default. To switch to real hardware:

```python
# In flask_api/app.py, change:
controller = RobotController(use_simulation=False)

# Or when creating robot controller directly:
controller = RobotController(use_simulation=False)
```

## Testing Checklist

### Navigation System
- [ ] Robot can move forward/backward in simulation
- [ ] Robot can turn left/right accurately
- [ ] Pathfinding computes simple paths
- [ ] Navigation follows computed paths
- [ ] Localization tracks position via odometry

### Face Recognition
- [ ] Face registration via mobile app works
- [ ] Encodings are saved to `encodings.pkl`
- [ ] Real-time recognition works via camera
- [ ] API endpoints respond correctly

### Mobile App
- [ ] Camera capture works
- [ ] Image upload to Flask API works
- [ ] mDNS service discovery finds robot
- [ ] Robot status tracking displays correctly

## Next Development Steps

### September 2024 (Foundation)
1. **Hardware Integration Research** 📋
   - Install Yahboom Raspbot V2 driver library
   - Test basic motor control with real hardware
   - Integrate encoder and IMU sensors

2. **YOLO Integration Planning** 🔍
   - Research Ultralytics YOLO for sign detection
   - Create training dataset for campus signs
   - Plan integration with navigation system

### October 2024 (Core Development)
3. **Enhanced Navigation** 🚀
   - Implement A* pathfinding algorithm
   - Add obstacle avoidance
   - GPS integration for outdoor navigation

4. **YOLO Sign Detection** 👁️
   - Train model on campus signs
   - Integrate with camera feed
   - Add sign-based navigation rules

### November 2024 (Integration & Polish)
5. **System Integration** 🔧
   - End-to-end testing on campus
   - Performance optimization
   - Error handling and recovery

6. **Demo Preparation** 🎬
   - Create demo scenarios
   - Video presentation recording
   - Documentation finalization

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure you're in the project root
   cd /path/to/Capstone-CST498
   python -c "from robot_navigation.localization import Localization; print('OK')"
   ```

2. **Camera Access**
   ```bash
   # Test camera access
   python -c "import cv2; print('Camera available:', cv2.VideoCapture(0).isOpened())"
   ```

3. **Flask API Not Found**
   - Check mDNS service is running
   - Try direct IP address instead of `appservice.local`
   - Verify port 5001 is not blocked

### Hardware-Specific Issues (When Available)

1. **Yahboom Driver Not Found**
   - Install driver library on Raspberry Pi
   - Check GPIO permissions
   - Verify I2C/SPI interfaces are enabled

2. **Motor Control Not Working**
   - Check power supply to motors
   - Verify wiring connections
   - Test individual motor commands

## Team Collaboration

### Git Workflow
```bash
# Always pull before starting work
git pull origin main

# Create feature branches
git checkout -b feature/yolo-integration
git add .
git commit -m "Add YOLO sign detection"
git push origin feature/yolo-integration

# Create pull request for review
```

### Task Division Suggestions
- **Member 1**: Hardware integration, motor control, sensors
- **Member 2**: YOLO implementation, computer vision, sign detection  
- **Member 3**: Mobile app enhancements, API improvements, testing

### Regular Meetings
- **Weekly progress reviews** (Mondays)
- **Integration testing sessions** (Fridays)
- **Hardware access coordination** (as needed)

## Deployment (Real Robot)

When ready to deploy to the Yahboom Raspbot:

1. **Raspberry Pi Setup**
   ```bash
   # On the Pi
   git clone <your-repo>
   cd Capstone-CST498
   pip install -r requirements.txt
   
   # Install Yahboom drivers
   # (Follow Yahboom documentation)
   ```

2. **Configuration Changes**
   ```python
   # flask_api/app.py
   controller = RobotController(use_simulation=False)
   ```

3. **Service Setup**
   ```bash
   # Create systemd service for auto-start
   sudo systemctl enable capstone-robot.service
   ```

## Resources

- **Yahboom Raspbot Documentation**: [yahboom.net](https://www.yahboom.net)
- **Ultralytics YOLO**: [docs.ultralytics.com](https://docs.ultralytics.com)
- **OpenCV Python**: [opencv-python-tutroals.readthedocs.io](https://opencv-python-tutroals.readthedocs.io)
- **Flutter Documentation**: [flutter.dev](https://flutter.dev)

---

**Last Updated**: August 28, 2024  
**Project Due**: December 2, 2024  
**Status**: Foundation Complete ✅
