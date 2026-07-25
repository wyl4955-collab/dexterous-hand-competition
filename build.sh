#!/bin/bash
set -e

# Auto-detect ROS2 distro
if [ -z "$ROS_DISTRO" ]; then
  if [ -f /opt/ros/humble/setup.bash ]; then
    ROS_DISTRO=humble
  elif [ -f /opt/ros/jazzy/setup.bash ]; then
    ROS_DISTRO=jazzy
  elif [ -f /opt/ros/kilted/setup.bash ]; then
    ROS_DISTRO=kilted
  else
    echo "ERROR: No ROS2 installation found. Run setup_competition.sh first."
    exit 1
  fi
fi

echo "======================================="
echo " Competition Workspace Build"
echo " ROS2: $ROS_DISTRO"
echo "======================================="

source /opt/ros/${ROS_DISTRO}/setup.bash

# Check serial permissions
if [ -e /dev/ttyUSB0 ] && [ ! -w /dev/ttyUSB0 ]; then
    echo "WARNING: No write permission on /dev/ttyUSB0 — run: sudo chmod 666 /dev/ttyUSB0"
fi

if [ "$1" == "--clean" ]; then
    echo "Cleaning previous build..."
    rm -rf build/ install/ log/
fi

echo ""
echo "Building all packages..."
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================="
    echo " BUILD SUCCESSFUL"
    echo "======================================="
    echo ""
    echo "source install/setup.bash"
    echo ""
    echo "Launch:"
    echo "  ros2 launch competition_bringup.launch.py mock_arm:=true"
else
    echo "BUILD FAILED"
    exit 1
fi
