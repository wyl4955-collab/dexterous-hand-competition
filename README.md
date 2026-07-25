# Competition Workspace

2026 世界人形机器人运动会 — 灵巧手专项赛（粉末称量 + 镊子夹豆）

## 架构

```
competition_ws/
├── src/
│   ├── competition_interfaces/   # 自定义 ROS2 消息/服务/动作
│   ├── rh56f2_driver/            # 因时 RH56F2 灵巧手驱动（C++，RS485协议）
│   ├── robot_arm_driver/         # 机械臂抽象接口 + Mock实现
│   ├── competition_vision/       # 视觉感知：黄豆检测、工具定位、秤读数
│   ├── manipulation_skills/      # 动作原语：捏、握、敲、倒、移
│   ├── powder_weighing/          # 粉末称量状态机
│   ├── bean_picking/             # 镊子夹豆状态机
│   ├── competition_supervisor/   # 总控：赛前自检、启停、急停、计分
│   └── operator_panel/           # 调试与比赛操作界面
├── config/                       # 手部参数、预设姿态、机械臂路径点、相机参数
├── launch/                       # 一键启动文件
├── tests/                        # 测试脚本
└── build.sh                      # 编译脚本
```

## 数据流

```
相机 → competition_vision → /vision/beans, /vision/tool, /vision/scale
天平 → competition_vision → /vision/scale
灵巧手 → rh56f2_driver → /hand/state (50Hz)
                          ← /hand/command
机械臂 → robot_arm_driver → arm.move_to()

manipulation_skills → 读取感知结果 → 发手/臂命令
powder_weighing → 读取 scale → 选振动策略 → 调 skills
bean_picking → 读取 beans → 算目标位置 → 调 skills
competition_supervisor → 管理所有节点生命周期
operator_panel → 显示状态、发指令给 supervisor
```

## 快速开始

### 1. 安装依赖

```bash
# USB转串口权限
sudo usermod -a -G dialout $USER
newgrp dialout

# ROS2 + colcon（如果还没装）
# 参考: https://docs.ros.org/en/humble/Installation.html
```

### 2. 编译

```bash
cd competition_ws
source /opt/ros/humble/setup.bash
./build.sh
```

### 3. 运行

```bash
source install/setup.bash

# 全系统启动
ros2 launch competition_bringup.launch.py

# 开发模式（Mock机械臂）
ros2 launch competition_bringup.launch.py mock_arm:=true

# 指定串口
ros2 launch competition_bringup.launch.py hand_port:=/dev/ttyUSB1
```

### 4. 手动调试

```bash
# 读取手部状态
ros2 topic echo /hand/state

# 发角度命令（食指拇指对捏）
ros2 topic pub --once /hand/command competition_interfaces/msg/HandCommand \
  "{target_angles: [1740,1740,1740,1150,1150,1200], force_thresholds: [40,40,40,40,40,40], speeds: [200,200,200,200,200,200], modes: [0,0,0,0,0,0]}"

# 查看黄豆检测
ros2 topic echo /vision/beans

# 力传感器校准
ros2 service call /hand/calibrate competition_interfaces/srv/HandCalibrate "{}"
```

## 关键参数速查

| 参数 | 值 | 说明 |
|------|-----|------|
| 夹黄豆力控 | 40g | 低于此值夹不起，高于60g容易碎 |
| 握镊子力 | 100g | 稳定握持不滑 |
| 握药勺力 | 180g | 药勺比镊子重 |
| 振动撒粉(粗) | 250g | 每次落粉约0.3g |
| 振动撒粉(精) | 80g | 每次落粉约0.04g |
| 振动撒粉(微) | 30g | 每次落粉约0.01g |
| 称量精度 | ±0.05g | 比赛允许误差 |
| 手状态频率 | 50Hz | rh56f2_driver发布频率 |
