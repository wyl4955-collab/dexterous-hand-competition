#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo 'ERROR: ROS 2 Humble is not installed at /opt/ros/humble'
  exit 1
fi
source /opt/ros/humble/setup.bash
if [[ -f /home/ubuntu/data/param/ros2_setup.bash ]]; then
  source /home/ubuntu/data/param/ros2_setup.bash
fi
if [[ -f /home/ubuntu/ros2ws/install/setup.bash ]]; then
  source /home/ubuntu/ros2ws/install/setup.bash
fi
if [[ -f "$workspace_dir/install/setup.bash" ]]; then
  source "$workspace_dir/install/setup.bash"
else
  echo "Build the workspace first: $workspace_dir"
  exit 1
fi

ros2 launch dexterous_hand_competition vision.launch.py "$@"
