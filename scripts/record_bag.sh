#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "$script_dir/.." && pwd)"
run_id="$(date +%Y%m%d_%H%M%S)"
output_dir="$workspace_dir/bags/bean_$run_id"

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
  /bean_task/safety_ok \
  /power/board/key_status \
  /power/board/status

