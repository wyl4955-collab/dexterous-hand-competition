# 环境配置（Windows + WSL2）

> 一键脚本自动完成所有安装。步骤 0-1 手动做，后面脚本全自动。

---

## 第0步：装 WSL2（一次性，管理员 PowerShell）

```powershell
wsl --install
```

装完重启电脑。Ubuntu 会自动启动，创建你的用户名和密码。

---

## 第1步：把安装脚本复制进 WSL 并执行

先退出 WSL（如果在里面的话按 Ctrl+D），在 **管理员 PowerShell** 里：

```powershell
# 确保脚本在工作目录
copy C:\Users\刘文毅\setup_competition.sh \\wsl.localhost\Ubuntu\home\<你的用户名>\
```

然后在 **WSL 终端**（按 Win 键搜 Ubuntu）里：

```bash
chmod +x ~/setup_competition.sh && ./setup_competition.sh
```

跑完约 20 分钟。脚本自动检测 Ubuntu 版本，选正确的 ROS2 发行版。

> 如果 `ros-humble-desktop` 报 not found → 说明你的 Ubuntu 不是 22.04，脚本会自动用 `ros-jazzy-desktop`。无需手动干预。

---

## 第2步：USB 透传（每次插设备后做一次）

管理员 PowerShell：

```powershell
usbipd list                      # 找到 RS485 模块的 BUSID
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

WSL 里验证：

```bash
ls /dev/ttyUSB* && sudo chmod 666 /dev/ttyUSB0
```

---

## 第3步：启动测试

```bash
cd ~/dexterous-hand-competition && source install/setup.bash

# 终端1：启动手驱动
ros2 run rh56f2_driver rh56f2_driver_node --ros-args -p port:="/dev/ttyUSB0"

# 终端2：查看状态
source install/setup.bash && ros2 topic echo /hand/state --once
```

---

## 验收

| 检查 | 命令 | 预期 |
|------|------|------|
| ROS2 OK | `ros2 --version` | 无报错 |
| 编译 OK | `colcon build` | 0 errors |
| 串口 OK | `ls /dev/ttyUSB0` | 存在 |
| 手通信 | `ros2 topic echo /hand/state --once` | 输出6个角度 |
