#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"
run_id="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
output_dir="$workspace_dir/bags/bean_$run_id"
metadata_dir="$workspace_dir/logs/$run_id"
mkdir -p "$metadata_dir"

{
  echo "run_id=$run_id"
  echo "bag_path=$output_dir"
  echo "started_at=$(date --iso-8601=seconds)"
  echo "git_commit=$(git -C "$workspace_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "ros_domain_id=${ROS_DOMAIN_ID:-unset}"
} > "$metadata_dir/bag_metadata.txt"

ros2 bag record -o "$output_dir" \
  /arm/status \
  /head/status \
  /waist/status \
  /leg/status \
  /inspire_hand/state/right_hand \
  /ob_camera_head/color/image_raw \
  /ob_camera_head/depth/image_raw \
  /bean_task/scene \
  /bean_task/state \
  /bean_task/active_target_id \
  /bean_task/pick_confirmed_id \
  /bean_task/drop_confirmed_id \
  /bean_task/safety_ok \
  /bean_task/safety_reason \
  /bean_task/vision_health \
  /power/board/key_status \
  /power/board/status
