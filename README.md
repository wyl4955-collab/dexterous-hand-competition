# Dexterous Hand Competition

[中文夹豆专项说明](README_CN.md) | English

> The existing multi-task packages are preserved. A new safety-first,
> dry-run-by-default bean-picking scaffold is available at
> `src/dexterous_hand_competition/`, with the Chinese team guide at
> `docs/TEAM_DIVISION_CN.md`. It does not command the real robot until the
> Tianyi SDK adapters and calibration files are verified.

2026 世界人形机器人运动会 — 灵巧手专项赛（粉末称量 + 镊子夹豆）

## 架构

```
Python packages (ROS2 nodes, colcon workspace):
  competition_interfaces/   ROS2 messages/services (.msg/.srv)
  rh56f2_driver/           RS485 driver for RH56F2 hand (50Hz State)
  competition_vision/      Bean detection, tool tracking, scale reading
  manipulation_skills/     Primitives: grip, pinch, tap, pour
  powder_weighing/         Powder weighing task FSM
  bean_picking/            Bean picking with tweezers FSM
  competition_supervisor/  Match orchestrator with start/stop/estop

Config:
  config/default.yaml      Hand, scale, camera, task params, waypoints

Launch:
  launch/competition.launch.py  One-click start all nodes
```

## Data Flow

```
Camera → competition_vision → /vision/beans, /vision/tool, /vision/scale
Scale  → competition_vision → /vision/scale
Hand   → rh56f2_driver      → /hand/state (50Hz)
          rh56f2_driver     ← /hand/command

supervisor ──→ powder_fsm ──→ primitives ──→ /hand/command
            └─→ bean_fsm  ──→ primitives ──→ /hand/command
```

## Quick Start

```bash
# 1. Install dependencies
pip install pyserial opencv-python numpy

# 2. Build
./build.sh

# 3. Source
source install/setup.bash

# 4. Launch (development with mock arm)
ros2 launch competition.launch.py mock_arm:=true

# 5. Start match
ros2 service call /competition/start std_srvs/srv/Trigger "{}"

# 6. Emergency stop
ros2 service call /competition/estop std_srvs/srv/Trigger "{}"
```

## Key Parameters

| Param | Value | Description |
|-------|-------|-------------|
| Bean grasp force | 40g | Goldilocks for soybeans |
| Anti-slip force | 55g | After contact |
| Max bean force | 80g | Cracking threshold |
| Tweezers grip | 120g | Stable tool hold |
| Spoon grip | 200g | Stable spoon hold |
| Tap force | 30-250g | Powder drop rate calibrated per force |
| Powder tolerance | ±0.05g | Competition spec |
| Hand update rate | 50Hz | State publish frequency |
