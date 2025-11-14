# Integrated Recognition System

## Overview

This document describes the integrated recognition system that combines facial recognition and traffic sign detection capabilities for the Yahboom Raspbot autonomous delivery robot. The system runs both recognition types simultaneously and provides audio feedback through the robot's buzzer.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Integrated Recognition System               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │ Facial          │    │ Traffic Sign Detection          │ │
│  │ Recognition     │    │ (YOLOv8)                       │ │
│  │                 │    │                                 │ │
│  │ • Face tracking │    │ • 80 object classes            │ │
│  │ • Database sync │    │ • Confidence filtering          │ │
│  │ • HTTP orders   │    │ • Bounding box visualization   │ │
│  │ • Visual feedback│    │ • Real-time processing         │ │
│  └─────────────────┘    └─────────────────────────────────┘ │
│           │                           │                     │
│           └───────────┬───────────────┘                     │
│                       │                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Robot Hardware Interface                                │ │
│  │                                                         │ │
│  │ • Buzzer control (I2C register 0x04)                   │ │
│  │ • Success/alert sound patterns                         │ │
│  │ • Simulation mode support                              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Dual Recognition System
- **Facial Recognition**: Identifies known users and processes orders
- **Traffic Sign Detection**: Detects objects and traffic signs using YOLOv8
- **Simultaneous Operation**: Both systems run in parallel for comprehensive awareness

### 2. Audio Feedback
- **Success Pattern**: 2000Hz for 100ms when face is recognized
- **Alert Pattern**: 1000Hz for 200ms for warnings
- **Short Beep**: 1500Hz for 50ms for general notifications

### 3. Visual Interface
- **Green Squares**: Persistent tracking boxes around recognized faces
- **Blue Boxes**: Object detection bounding boxes with confidence scores
- **Real-time Display**: Live camera feed with annotations

### 4. Configurable Operation
- **Component Toggle**: Enable/disable facial recognition or sign detection
- **Headless Mode**: Run without display for autonomous operation
- **Hardware Control**: Switch between real hardware and simulation

## Installation and Setup

### Prerequisites

```bash
# Required Python packages
pip install -r requirements.txt

# Key dependencies:
# - face_recognition
# - opencv-python
# - ultralytics (YOLOv8)
# - numpy
# - requests
```

### Model Files

Ensure these model files are present:
- `yolov8n.pt` - YOLOv8 nano model for object detection
- `cache/face_encodings.npz` - Face encoding cache (created automatically)

### Hardware Setup

For Yahboom Raspbot hardware:
1. Ensure I2C is enabled
2. Connect buzzer to I2C register 0x04
3. Camera should be accessible at index 0

## Usage

### Basic Commands

```bash
# Full system (default)
python integrated_recognition_system.py

# Face recognition only
python integrated_recognition_system.py --no-signs

# Sign detection only  
python integrated_recognition_system.py --no-face

# Headless mode (no display)
python integrated_recognition_system.py --headless

# With hardware buzzer
python integrated_recognition_system.py --robot

# Combined options
python integrated_recognition_system.py --headless --no-face --robot
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--no-face` | Disable facial recognition |
| `--no-signs` | Disable sign detection |
| `--headless` | Run without display |
| `--robot` | Use real hardware buzzer |
| `--confidence` | Set detection confidence threshold (0.0-1.0) |

### Controls

When running with display:
- **'q'**: Quit the application
- **'s'**: Save current frame to `saved_frame_YYYYMMDD_HHMMSS.jpg`
- **ESC**: Alternative quit method

## Configuration

### Environment Variables

```bash
# Database configuration
export DB_HOST=your_database_host
export DB_USER=your_database_user
export DB_PASSWORD=your_database_password
export DB_NAME=your_database_name

# Flask API endpoint
export FLASK_API_URL=http://localhost:5000
```

### Detection Parameters

```python
# In integrated_recognition_system.py
CONFIDENCE_THRESHOLD = 0.75  # YOLOv8 detection confidence
FACE_TOLERANCE = 0.6         # Face recognition tolerance
MAX_DISTANCE = 0.45          # Face matching distance
```

## System Components

### 1. IntegratedRecognitionSystem Class

Main orchestrator class that:
- Manages camera input
- Coordinates facial recognition and sign detection
- Handles visual annotations
- Controls robot interface
- Processes user input

### 2. TrafficSignDetector Class

YOLOv8-based detector that:
- Loads YOLOv8 model
- Processes frames for object detection
- Filters results by confidence
- Returns bounding boxes and labels

### 3. RobotInterface

Hardware abstraction layer:
- Real hardware mode: Uses YB_Pcb_Car for I2C buzzer control
- Simulation mode: Provides mock buzzer functionality
- Consistent API across both modes

### 4. Face Recognition Integration

Database-connected system that:
- Loads face encodings from cache or database
- Performs real-time face matching
- Maintains persistent tracking
- Sends order requests to Flask API

## Testing

### Test Suite

Run the comprehensive test suite:

```bash
python test_integrated_system.py
```

The test validates:
- ✅ Face recognition functionality
- ✅ Sign detection with YOLOv8
- ✅ Robot interface (simulation/hardware)
- ✅ Integration between components
- ✅ Error handling and edge cases

### Manual Testing

```bash
# Test individual components
python -c "from integrated_recognition_system import TrafficSignDetector; print('Sign detection OK')"
python -c "import face_recognition; print('Face recognition OK')"
python -c "from robot_navigation.hardware_interface import RobotInterface; print('Robot interface OK')"
```

## Troubleshooting

### Common Issues

**1. YOLOv8 Model Loading Error**
```
Error: Could not load YOLOv8 model
```
Solution: Ensure `yolov8n.pt` is in the current directory or specify correct path.

**2. Face Recognition Database Error**
```
[WARNING] Database environment variables not set
```
Solution: Set database environment variables or ensure `cache/face_encodings.npz` exists.

**3. Camera Access Error**
```
Error: Could not access camera
```
Solution: Check camera permissions and ensure no other application is using the camera.

**4. Hardware Interface Error**
```
Warning: Could not import YB_Pcb_Car. Running in simulation mode
```
Solution: Ensure raspbot directory is in PYTHONPATH or run with `--robot` flag only on actual hardware.

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Optimization

For better performance:
1. Use smaller YOLOv8 model (yolov8n.pt vs yolov8s.pt)
2. Reduce camera resolution
3. Increase confidence threshold to reduce false positives
4. Run in headless mode when display is not needed

## File Structure

```
integrated_recognition_system.py    # Main integrated system
test_integrated_system.py          # Test suite
robot_navigation/
├── hardware_interface.py          # Robot abstraction layer
└── yolo_detector.py               # YOLOv8 integration
python codes/
├── ai_facial_recognition.py       # Face recognition core
└── sign_recognition.py            # Standalone sign detection
raspbot/
└── YB_Pcb_Car.py                  # Hardware control with buzzer
cache/
└── face_encodings.npz             # Face encoding cache
```

## Development Notes

### Adding New Features

1. **New Detection Types**: Extend TrafficSignDetector class
2. **Additional Audio Patterns**: Add methods to buzzer interface
3. **Database Integration**: Modify face recognition database queries
4. **UI Enhancements**: Update annotation rendering in main loop

### Performance Monitoring

The system logs performance metrics:
- Frame processing time
- Detection confidence scores
- Face recognition matches
- Hardware communication status

### Future Enhancements

- [ ] Multi-camera support
- [ ] Remote monitoring via web interface
- [ ] GPS integration for location-based recognition
- [ ] Machine learning model updates via network
- [ ] Advanced path planning integration

## API Reference

### IntegratedRecognitionSystem

```python
class IntegratedRecognitionSystem:
    def __init__(self, enable_face=True, enable_signs=True, 
                 use_hardware=False, headless=False, confidence=0.75)
    
    def run(self) -> None
    def cleanup(self) -> None
```

### TrafficSignDetector

```python
class TrafficSignDetector:
    def __init__(self, model_path="yolov8n.pt", confidence_threshold=0.75)
    
    def detect(self, frame: np.ndarray) -> List[Dict]
    def draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray
```

### RobotInterface

```python
class RobotInterface:
    def __init__(self, use_hardware=False)
    
    def buzz_success(self) -> None
    def buzz_alert(self) -> None
    def buzz_short(self) -> None
```

## License

This integrated recognition system is part of the Capstone CST498 project. See project documentation for licensing details.

## Support

For technical support or questions about the integrated recognition system:
1. Check this documentation
2. Run the test suite to identify issues
3. Review log output for error details
4. Consult individual component documentation

---

*Last updated: 2024*
*System version: 1.0*
*Compatible with: YOLOv8, Python 3.8+, Yahboom Raspbot*