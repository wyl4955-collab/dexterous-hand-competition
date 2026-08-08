#!/usr/bin/env bash
set -euo pipefail

platform_topics=(
  /arm/status
  /head/status
  /waist/status
  /leg/status
  /ob_camera_head/color/image_raw
  /ob_camera_head/depth/image_raw
  /power/board/key_status
  /power/board/status
)

c2_topics=(
  /bean_task/scene
  /bean_task/state
  /bean_task/active_target_id
  /bean_task/pick_confirmed_id
  /bean_task/drop_confirmed_id
  /bean_task/safety_ok
  /bean_task/vision_health
)

check_topic_group() {
  local heading="$1"
  shift
  echo "=== $heading ==="
  for topic in "$@"; do
    if ros2 topic list | grep -Fxq "$topic"; then
      echo "OK      $topic  $(ros2 topic type "$topic")"
    else
      echo "MISSING $topic"
    fi
  done
}

echo "ROS_DISTRO=${ROS_DISTRO:-unset}"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-unset}"
echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-default}"
echo '=== ROS 2 nodes ==='
ros2 node list
check_topic_group 'Platform topics' "${platform_topics[@]}"
check_topic_group 'C2 integration topics' "${c2_topics[@]}"

echo '=== C2 services ==='
for service in /bean_task/start /bean_task/stop /bean_task/reset; do
  if ros2 service list | grep -Fxq "$service"; then
    echo "OK      $service"
  else
    echo "MISSING $service"
  fi
done

echo '=== Arm command publishers (must be understood before real mode) ==='
ros2 topic info /arm/cmd_pos --verbose || true
echo '=== Inspire Hand services ==='
ros2 service list | grep inspire_hand || true
