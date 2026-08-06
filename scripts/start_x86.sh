#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"

source /opt/ros/humble/setup.bash
source /home/ubuntu/data/param/ros2_setup.bash
source /home/ubuntu/ros2ws/install/setup.bash
if [[ -f "$workspace_dir/install/setup.bash" ]]; then
  source "$workspace_dir/install/setup.bash"
else
  echo "Build the workspace first: $workspace_dir"
  exit 1
fi

# Keep dry_run true until all TODO_REAL_ROBOT items are verified.
ros2 launch dexterous_hand_competition bean_task.launch.py dry_run:=true "$@"

