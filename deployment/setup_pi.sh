#!/bin/bash
# Raspberry Pi 5 Setup Script for Face Recognition System
# Run this script on the Raspberry Pi after cloning the repository

set -e

echo "=========================================="
echo "Face Recognition System - Pi 5 Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}Warning: This script is designed for Raspberry Pi${NC}"
fi

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"

# Update system
echo -e "${GREEN}Step 1: Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
echo -e "${GREEN}Step 2: Installing system dependencies...${NC}"
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    cmake \
    libopencv-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libcanberra-gtk3-module \
    i2c-tools \
    python3-smbus

# Enable I2C for robot control
echo -e "${GREEN}Step 3: Enabling I2C interface...${NC}"
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
    echo -e "${YELLOW}I2C enabled. You may need to reboot after setup.${NC}"
fi

# Add user to i2c group
sudo usermod -a -G i2c $USER

# Create virtual environment
echo -e "${GREEN}Step 4: Creating Python virtual environment...${NC}"
cd "$PROJECT_DIR"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
echo -e "${GREEN}Step 5: Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel

# Install Python dependencies for Pi
echo -e "${GREEN}Step 6: Installing Python packages (this may take 10-20 minutes)...${NC}"
pip install --no-cache-dir numpy==1.24.3
pip install --no-cache-dir opencv-python-headless==4.8.1.78
pip install --no-cache-dir dlib==19.24.0
pip install --no-cache-dir face-recognition==1.3.0
pip install --no-cache-dir pymysql==1.1.0
pip install --no-cache-dir python-dotenv==1.0.0
pip install --no-cache-dir Flask==3.0.0
pip install --no-cache-dir gunicorn==21.2.0

# Install picamera2 for Pi Camera
echo -e "${GREEN}Step 7: Installing picamera2 for Raspberry Pi Camera...${NC}"
sudo apt-get install -y python3-picamera2 || echo -e "${YELLOW}picamera2 installation skipped (may not be available on your OS version)${NC}"

# Copy environment file
echo -e "${GREEN}Step 8: Setting up environment configuration...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}Creating .env file template...${NC}"
    cat > "$PROJECT_DIR/.env" << 'EOF'
# JawsDB MySQL Configuration
DB_HOST=your-jawsdb-host.rds.amazonaws.com
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_NAME=your-db-name

# Flask Configuration
FLASK_DEBUG=0
EOF
    echo -e "${RED}IMPORTANT: Edit .env file with your actual JawsDB credentials!${NC}"
fi

# Install systemd service
echo -e "${GREEN}Step 9: Installing systemd service...${NC}"
if [ -f "$PROJECT_DIR/deployment/face-recognition.service" ]; then
    sudo cp "$PROJECT_DIR/deployment/face-recognition.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    echo -e "${GREEN}Systemd service installed. You can enable it with:${NC}"
    echo "  sudo systemctl enable face-recognition.service"
    echo "  sudo systemctl start face-recognition.service"
else
    echo -e "${YELLOW}Service file not found. Skipping systemd setup.${NC}"
fi

# Test camera
echo -e "${GREEN}Step 10: Testing camera access...${NC}"
if [ -e /dev/video0 ]; then
    echo -e "${GREEN}Camera detected at /dev/video0${NC}"
else
    echo -e "${YELLOW}No camera detected at /dev/video0. Check camera connection.${NC}"
fi

# Test I2C
echo -e "${GREEN}Step 11: Testing I2C bus...${NC}"
if i2cdetect -y 1 &> /dev/null; then
    echo -e "${GREEN}I2C bus accessible${NC}"
    echo "Detected I2C devices:"
    sudo i2cdetect -y 1
else
    echo -e "${YELLOW}I2C test failed. May need reboot or configuration.${NC}"
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your JawsDB credentials:"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "2. Test face recognition (with display):"
echo "   source .venv/bin/activate"
echo "   python ai_facial_recognition.py"
echo ""
echo "3. Test headless mode (for deployment):"
echo "   python ai_facial_recognition.py --headless --robot"
echo ""
echo "4. Enable auto-start on boot:"
echo "   sudo systemctl enable face-recognition.service"
echo "   sudo systemctl start face-recognition.service"
echo ""
echo "5. View service logs:"
echo "   sudo journalctl -u face-recognition.service -f"
echo ""
if grep -q "^dtparam=i2c_arm=on" /boot/config.txt && ! groups | grep -q i2c; then
    echo -e "${YELLOW}REBOOT REQUIRED to enable I2C interface${NC}"
fi
