#!/bin/bash
set -e
echo "=== Competition Workspace Build ==="
if [ -z "$ROS_DISTRO" ]; then
  for d in /opt/ros/*/setup.bash; do [ -f "$d" ] && source "$d" && break; done
fi
echo "ROS2: $ROS_DISTRO"
colcon build --symlink-install --packages-skip-regex "operator_panel.*"
echo "=== Build Complete ==="
echo "source install/setup.bash"
echo "ros2 launch competition.launch.py mock_arm:=true"
