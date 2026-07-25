# 环境配置执行方案

> 每一步都必须跑通才能继续下一步

---

## 前置：确认机器

```bash
# 确认是 Ubuntu 22.04
lsb_release -a
# 应输出: Ubuntu 22.04.x LTS

# 确认架构
uname -m
# 应输出: x86_64
```

---

## 第1步：安装 ROS2 Humble（20分钟）

```bash
# 1.1 设置 locale
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# 1.2 添加 ROS2 源
sudo apt install -y software-properties-common
sudo add-apt-repository universe -y
sudo apt update && sudo apt install -y curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 1.3 安装 ROS2 Humble 桌面版
sudo apt update
sudo apt install -y ros-humble-desktop

# 1.4 安装开发工具
sudo apt install -y python3-colcon-common-extensions python3-rosdep python3-pip

# 1.5 初始化 rosdep
sudo rosdep init
rosdep update

# ✅ 验证
source /opt/ros/humble/setup.bash
ros2 --version
# 应无报错

echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

---

## 第2步：安装 SDK 所需的三方库（5分钟）

```bash
sudo apt install -y \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-dev \
    libyaml-cpp-dev \
    libspdlog-dev

# ✅ 验证
pkg-config --modversion boost
pkg-config --modversion yaml-cpp
dpkg -l | grep spdlog
```

---

## 第3步：配置串口权限（2分钟）

```bash
# 加入 dialout 组
sudo usermod -a -G dialout $USER

# ⚠️ 必须注销重新登录才生效！
# 或者先临时用 newgrp（当前终端立刻生效）：
newgrp dialout

# ✅ 验证（重新登录后）
groups | grep dialout
# 应输出包含 dialout
```

---

## 第4步：克隆仓库（1分钟）

```bash
cd ~
git clone https://github.com/wyl4955-collab/dexterous-hand-competition.git
cd dexterous-hand-competition
ls
# 应看到: src/ config/ launch/ build.sh README.md
```

---

## 第5步：编译（5分钟）

```bash
cd ~/dexterous-hand-competition
source /opt/ros/humble/setup.bash

colcon build --symlink-install

# ✅ 验证
source install/setup.bash
ros2 pkg list | grep competition
# 应看到: competition_interfaces, rh56f2_driver, competition_vision, ...
```

---

## 第6步：连接灵巧手（10分钟）

```bash
# 6.1 插上 USB 转 RS485 模块
# 6.2 找到设备
ls /dev/ttyUSB*
# 应输出: /dev/ttyUSB0（如果有多余模块可能还有 /dev/ttyUSB1）
# 如果没有 → 拔插一下再 ls，确认驱动正常

# 6.3 确认权限
ls -l /dev/ttyUSB0
# 应显示: crw-rw---- 1 root dialout ...
# 如果显示 crw------- → 权限没配好，回到第3步

# 6.4 测试串口（发送一个简单的读 ID 帧）
# 用 Python 快速测试
python3 -c "
import serial
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.5)
# 读 ID 寄存器（地址 1000 = 0x03E8，读 2 字节）
frame = bytes([0xEB, 0x90, 0x01, 0x04, 0x11, 0xE8, 0x03, 0x02, 0xFD])
ser.write(frame)
import time; time.sleep(0.1)
resp = ser.read(100)
print(f'收到 {len(resp)} 字节: {resp.hex()}')
ser.close()
"
# 有回复 → 通信OK
# 无回复 → 检查：24V电源开了吗？黄绿线有没有接反？
```

---

## 第7步：启动驱动节点测试（5分钟）

```bash
cd ~/dexterous-hand-competition
source install/setup.bash

# 启动手部驱动
ros2 run rh56f2_driver rh56f2_driver_node --ros-args \
    -p port:="/dev/ttyUSB0" \
    -p hand_id:=1

# 另开一个终端，查看状态
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash
ros2 topic echo /hand/state --once
# 应输出6个手指的角度、力等信息
```

---

## 第8步：启动视觉节点测试（如果没有相机，先跳过）

```bash
# 另开终端
ros2 run competition_vision perception_node --ros-args \
    -p camera_topic:="/camera/color/image_raw"

# 如果有 RealSense 相机，先装驱动：
sudo apt install -y ros-humble-realsense2-camera
# 然后启动相机节点：
ros2 launch realsense2_camera rs_launch.py
```

---

## 第9步：一键启动所有节点

```bash
cd ~/dexterous-hand-competition
source install/setup.bash

# 使用 mock 机械臂（开发阶段）
ros2 launch competition_bringup.launch.py mock_arm:=true

# 接入真机械臂后，去掉 mock_arm 参数
```

---

## 验收标准

全部通过才算环境就绪：

| 检查项 | 命令 | 预期结果 |
|--------|------|---------|
| ROS2 正常 | `ros2 --version` | 无报错 |
| 编译成功 | `colcon build` | 0 errors |
| 灵巧手通信 | `ros2 topic echo /hand/state --once` | 输出6个角度值 |
| 串口权限 | `ls -l /dev/ttyUSB0` | 显示 `dialout` 组 |
| 力传感器 | 上位机读取实际力值 | 空载时接近 0±15g |

---

## 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `colcon build` 报找不到 `rosidl` | 没 source ROS2 环境 | `source /opt/ros/humble/setup.bash` |
| `/dev/ttyUSB0` 不存在 | USB转485模块没识别 | `dmesg \| tail` 看驱动日志 |
| 串口有设备但无回复 | 黄绿线接反了 | 交换黄绿线重试 |
| 灵巧手上电后不动也不热 | 正常！上电默认不动作 | 发指令才会动 |
| 手指抖动 | 力传感器需要校准 | 空载下发校准指令 |
| `Permission denied` 串口 | 没加 dialout 组 | 回到第3步 |
