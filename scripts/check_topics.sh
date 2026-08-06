#!/usr/bin/env bash
set -euo pipefail

required_topics=(
  /arm/status
  /head/status
  /waist/status
  /leg/status
  /ob_camera_head/color/image_raw
  /ob_camera_head/depth/image_raw
  /power/board/key_status
  /power/board/status
)

echo '=== ROS2 nodes ==='
ros2 node list

echo '=== Required topic checks ==='
for topic in "${required_topics[@]}"; do
  if ros2 topic list | grep -Fxq "$topic"; then
    topic_type="$(ros2 topic type "$topic")"
    echo "OK  $topic  $topic_type"
  else
    echo "MISSING  $topic"
  fi
done

echo '=== Arm command publishers ==='
ros2 topic info /arm/cmd_pos --verbose || true

echo '=== Inspire Hand services ==='
ros2 service list | grep inspire_hand || true

