# Dexterous Hand Robot Competition

[中文说明](README_CN.md) | English

ROS2 Humble workspace for the Tianyi Pro 2.0 autonomous tweezer bean-picking task.

The C2 implementation and integration workflow are documented in [`docs/C2_GUIDE_CN.md`](docs/C2_GUIDE_CN.md).

## Safety first

This repository starts in `dry_run` mode and does **not** contain verified joint poses, hand ratios, robot limits, or SDK message adapters. Never command the real robot until all values marked `TODO_REAL_ROBOT` have been verified at low speed with two people present and one person dedicated to the emergency stop.

When a safety condition occurs, the system must stop publishing new motion commands and enter a locked state. It must not automatically move to neutral or release the tool.

## Scope

The first competition target is:

1. Check robot, camera, hand, configuration and safety state.
2. Move to a repeatable ready pose.
3. Detect the source container, target container, tweezers and soybeans.
4. Pick up and hold 160 mm curved medical tweezers.
5. Select a safe soybean target.
6. Hover, refine, descend, squeeze, lift, transfer and release.
7. Verify the pick/drop before incrementing the score.
8. Repeat within 300 seconds and finish in a safe hover pose.

## Workspace layout

```text
Dexterous_Hand_Robot_Competition/
├── src/
│   ├── competition_interfaces/          # ROS2 custom messages
│   └── dexterous_hand_competition/      # Python control/vision/task package
├── calibration/                         # Site-specific calibration
├── docs/                                # Team and interface guidance
├── scripts/                             # Startup and diagnostic scripts
├── data/                                # Local image/debug data (not committed)
├── bags/                                # rosbag output (not committed)
└── logs/                                # task logs (not committed)
```

## Four-person ownership

| Member | Ownership | Main directories |
|---|---|---|
| A | Robot state, arm/body motion, interpolation, workspace mapping | `common/robot_state.py`, `common/arm_controller.py`, `control/` |
| B | Vision, scene detection and camera/table calibration | `vision/`, `config/vision.yaml`, `calibration/camera_table.yaml` |
| C | Inspire Hand, tweezer poses and reusable tweezer skills | `common/hand_controller.py`, `skills/`, `config/hand.yaml` |
| D | FSM, safety, interfaces, build, launch, logging and integration | `task/`, `common/safety_monitor.py`, `competition_interfaces/`, `launch/` |

See [docs/TEAM_DIVISION_CN.md](docs/TEAM_DIVISION_CN.md) for the detailed Chinese beginner guide, or [docs/TEAM_DIVISION.md](docs/TEAM_DIVISION.md) for the compact English version.

## Milestones

- `M0`: callbacks, build, config and safety work.
- `M1`: manually mount tweezers and pick one fixed soybean without vision.
- `M2`: detect and pick one soybean inside the calibrated workspace.
- `M3`: automatically pick up and verify tweezers.
- `M4`: run the autonomous loop for five minutes.

## Build on Ubuntu 22.04 / ROS2 Humble

```bash
cd ~/Dexterous_Hand_Robot_Competition
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

The robot SDK environment may also require:

```bash
source /home/ubuntu/data/param/ros2_setup.bash
source /home/ubuntu/ros2ws/install/setup.bash
```

## Run in dry-run mode

Complete synthetic integration test without camera or robot commands:

```bash
source install/setup.bash
ros2 launch dexterous_hand_competition mock_system.launch.py
```

In another terminal:

```bash
source install/setup.bash
ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
ros2 topic echo /bean_task/state
```

The mock scene node is only for software integration. It must never be used to control the real robot.

Separate deployment:

Vision on Orin:

```bash
source install/setup.bash
ros2 launch dexterous_hand_competition vision.launch.py
```

Task and safety on x86:

```bash
source install/setup.bash
ros2 launch dexterous_hand_competition bean_task.launch.py dry_run:=true
```

Start and stop the task:

```bash
ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
ros2 service call /bean_task/stop std_srvs/srv/Trigger '{}'
```

## Before real-robot mode

All items below are mandatory:

- Verify every SDK topic, service, type and field using `ros2 topic type`, `ros2 service type` and `ros2 interface show`.
- Implement the SDK adapters in `common/arm_controller.py`, `common/robot_state.py`, `common/hand_controller.py` and `common/safety_monitor.py`.
- Replace all calibration placeholders with measured values.
- Confirm joint limits, direction, speed and current at low speed.
- Validate color/depth alignment and the pixel-to-table calibration.
- Validate hard estop, remote estop, power, stale feedback and joint error handling.
- Confirm only one publisher controls each robot command topic.
- Pass M0 and M1 tests with logs before setting `dry_run: false`.

## Useful checks

```bash
./scripts/check_topics.sh
python3 -m compileall src/dexterous_hand_competition
colcon test
colcon test-result --verbose
```
