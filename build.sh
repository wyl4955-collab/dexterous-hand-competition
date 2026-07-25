#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Competition Workspace — One-Command Build
# ═══════════════════════════════════════════════════════════════
set -e

echo "======================================="
echo " Competition Workspace Build"
echo "======================================="

# Check ROS2 environment
if [ -z "$ROS_DISTRO" ]; then
    echo "ERROR: ROS2 not sourced. Run: source /opt/ros/humble/setup.bash"
    exit 1
fi
echo "ROS2: $ROS_DISTRO"

# Check serial permissions
if [ -e /dev/ttyUSB0 ] && [ ! -w /dev/ttyUSB0 ]; then
    echo "WARNING: No write permission on /dev/ttyUSB0"
    echo "  Fix: sudo usermod -a -G dialout \$USER && newgrp dialout"
fi

# Clean build (optional)
if [ "$1" == "--clean" ]; then
    echo "Cleaning previous build..."
    rm -rf build/ install/ log/
fi

# Build
echo ""
echo "Building all packages..."
colcon build --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --packages-up-to competition_supervisor

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo "======================================="
    echo " BUILD SUCCESSFUL"
    echo "======================================="
    echo ""
    echo "Source the workspace:"
    echo "  source install/setup.bash"
    echo ""
    echo "Launch everything:"
    echo "  ros2 launch competition_bringup.launch.py"
    echo ""
    echo "Launch with mock arm (development):"
    echo "  ros2 launch competition_bringup.launch.py mock_arm:=true"
else
    echo ""
    echo "======================================="
    echo " BUILD FAILED — check errors above"
    echo "======================================="
    exit 1
fi
