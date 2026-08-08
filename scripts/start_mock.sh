#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"

source /opt/ros/humble/setup.bash
if [[ ! -f "$workspace_dir/install/setup.bash" ]]; then
  echo "ERROR: build first: cd $workspace_dir && colcon build --symlink-install"
  exit 1
fi
source "$workspace_dir/install/setup.bash"

ros2 launch dexterous_hand_competition mock_system.launch.py "$@" &
launch_pid=$!
trap 'kill "$launch_pid" 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 40); do
  if ros2 service list | grep -Fxq /bean_task/start; then
    ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
    wait "$launch_pid"
    exit $?
  fi
  sleep 0.25
done

echo 'ERROR: /bean_task/start did not become available'
exit 1
