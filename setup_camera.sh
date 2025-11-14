#!/bin/bash
# Camera Setup Script for Raspberry Pi
# Fixes common camera access issues

echo "=== Camera Setup Script for Raspberry Pi ==="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Please run this script as a regular user (not root/sudo)"
    exit 1
fi

# Function to check if command succeeded
check_status() {
    if [ $? -eq 0 ]; then
        echo "✓ $1"
    else
        echo "✗ $1 failed"
    fi
}

echo "1. Adding user to video group..."
sudo usermod -a -G video $USER
check_status "User added to video group"

echo "2. Installing picamera2..."
sudo apt update
sudo apt install -y python3-picamera2
check_status "picamera2 installation"

echo "3. Enabling camera interface..."
# Enable camera auto-detect if not already enabled
if ! grep -q "camera_auto_detect=1" /boot/config.txt; then
    echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
    check_status "Camera auto-detect enabled"
else
    echo "✓ Camera auto-detect already enabled"
fi

# Ensure legacy camera support is disabled (conflicts with libcamera)
sudo sed -i 's/^start_x=1/#start_x=1/' /boot/config.txt
check_status "Legacy camera support disabled"

echo "4. Setting up camera permissions..."
# Create udev rule for camera access
sudo tee /etc/udev/rules.d/99-camera.rules > /dev/null << 'EOF'
# Camera device permissions
SUBSYSTEM=="video4linux", GROUP="video", MODE="0664"
KERNEL=="video[0-9]*", GROUP="video", MODE="0664"
EOF
check_status "Camera udev rules created"

echo "5. Checking camera connection..."
if [ -e /dev/video0 ]; then
    echo "✓ Camera device found at /dev/video0"
else
    echo "⚠ No camera device found. Check connection and reboot."
fi

echo "6. Installing camera diagnostic tools..."
sudo apt install -y v4l-utils
check_status "v4l-utils installation"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: You must reboot for all changes to take effect!"
echo ""
echo "After reboot, test your camera with:"
echo "  python3 camera_diagnostic.py"
echo ""
echo "Quick camera test commands:"
echo "  v4l2-ctl --list-devices          # List camera devices"
echo "  v4l2-ctl --list-formats-ext      # List supported formats"
echo "  groups                           # Check if you're in video group"
echo ""
echo "If issues persist:"
echo "  1. Check camera cable connection"
echo "  2. Try different camera module"
echo "  3. Check for hardware conflicts"
echo ""
read -p "Reboot now? (y/N): " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    sudo reboot
else
    echo "Remember to reboot before testing the camera!"
fi