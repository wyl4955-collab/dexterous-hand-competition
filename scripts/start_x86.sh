#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo 'ERROR: ROS 2 Humble is not installed at /opt/ros/humble'
  exit 1
fi
source /opt/ros/humble/setup.bash

# Tianyi runtime settings contain the verified DDS profile and Domain ID.
if [[ -f /home/ubuntu/data/param/ros2_setup.bash ]]; then
  source /home/ubuntu/data/param/ros2_setup.bash
fi
if [[ -f /home/ubuntu/ros2ws/install/setup.bash ]]; then
  source /home/ubuntu/ros2ws/install/setup.bash
fi
if [[ ! -f "$workspace_dir/install/setup.bash" ]]; then
  echo "ERROR: build first: cd $workspace_dir && colcon build --symlink-install"
  exit 1
fi
source "$workspace_dir/install/setup.bash"

run_id="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
run_dir="$workspace_dir/logs/$run_id"
mkdir -p "$run_dir"
{
  echo "run_id=$run_id"
  echo "started_at=$(date --iso-8601=seconds)"
  echo "git_commit=$(git -C "$workspace_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "ros_distro=${ROS_DISTRO:-unset}"
  echo "ros_domain_id=${ROS_DOMAIN_ID:-unset}"
  echo "rmw_implementation=${RMW_IMPLEMENTATION:-default}"
  echo 'dry_run=true'
} > "$run_dir/metadata.txt"

echo "C2 run_id: $run_id"
echo "ROS_DISTRO=${ROS_DISTRO:-unset} ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-unset}"
echo 'Safety default is dry_run=true. Start separately after checking topics:'
echo '  ros2 service call /bean_task/start std_srvs/srv/Trigger {}'

ros2 launch dexterous_hand_competition bean_task.launch.py \
  dry_run:=true "$@" 2>&1 | tee "$run_dir/task.log"
