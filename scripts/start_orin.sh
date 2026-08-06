#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"

source /opt/ros/humble/setup.bash
if [[ -f "$workspace_dir/install/setup.bash" ]]; then
  source "$workspace_dir/install/setup.bash"
else
  echo "Build the workspace first: $workspace_dir"
  exit 1
fi

ros2 launch dexterous_hand_competition vision.launch.py "$@"

