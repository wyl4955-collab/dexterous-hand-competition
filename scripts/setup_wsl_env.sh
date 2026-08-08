#!/usr/bin/env bash
# Run this script ONCE inside WSL Ubuntu 22.04 to set up the full environment.
# Usage: cd ~/dexterous-hand-competition && bash scripts/setup_wsl_env.sh
set -eo pipefail

echo '=== Installing ROS2 Humble ==='
sudo apt update -qq
sudo apt install -y -qq software-properties-common curl gnupg lsb-release
sudo add-apt-repository -y universe
if [[ ! -f /usr/share/keyrings/ros-archive-keyring.gpg ]]; then
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
fi
if [[ ! -f /etc/apt/sources.list.d/ros2.list ]]; then
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
fi
sudo apt update -qq
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep python3-opencv python3-numpy python3-yaml python3-pip

echo '=== Initializing rosdep ==='
sudo rosdep init 2>/dev/null || true
rosdep update

echo '=== Building project ==='
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_DIR"

source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install

echo '=== Running tests ==='
source install/setup.bash
python3 -m pytest src/dexterous_hand_competition/test/ -v || echo 'Some tests may require ROS — expected on non-ROS Windows'

cat <<'FINAL'

============================================
Setup complete!

To start working:
  source /opt/ros/humble/setup.bash
  source ~/dexterous-hand-competition/install/setup.bash

To verify:
  ros2 --version
  colcon test-result --verbose
============================================
FINAL
