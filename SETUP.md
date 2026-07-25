# 环境配置执行方案（Windows + WSL2）

> 你的电脑是 Windows，但代码里 C++ 驱动用了 Linux 串口 API，必须在 WSL2 里编译运行。
> 整体思路：WSL2 装 Ubuntu → USB 设备透传 → 在 WSL2 里写代码/编译/运行。

---

## 第0步：安装 WSL2 + Ubuntu 22.04（一次性，30分钟）

### 0.1 开启 WSL 功能

以管理员身份打开 **PowerShell**，执行：

```powershell
# 安装 WSL
wsl --install

# 重启电脑
```

重启后 Ubuntu 会自动启动，创建用户名和密码（记住这个密码，后面 sudo 要用）。

### 0.2 确认是 WSL2

```powershell
# 回到 PowerShell
wsl --list --verbose
# 应显示: Ubuntu-22.04  Running  2
# 如果 VERSION 是 1，升级：
wsl --set-version Ubuntu-22.04 2
```

### 0.3 进入 WSL

以后每次开发，打开终端输入：

```powershell
wsl
```

就会进入 Ubuntu 命令行。下面所有步骤都在这个 WSL 终端里执行。

---

## 第1步：安装 ROS2 Humble（20分钟）

在 WSL 终端里：

```bash
# 1.1 设置 locale
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# 1.2 添加 ROS2 源
sudo apt install -y software-properties-common curl
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 1.3 安装 ROS2 Humble
sudo apt update
sudo apt install -y ros-humble-desktop

# 1.4 安装开发工具
sudo apt install -y python3-colcon-common-extensions python3-rosdep python3-pip

# 1.5 初始化
sudo rosdep init
rosdep update

# 1.6 自动加载 ROS2 环境
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc

# ✅ 验证
ros2 --version
# 不应该报错
```

---

## 第2步：安装 SDK 所需三方库（3分钟）

```bash
sudo apt install -y \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-dev \
    libyaml-cpp-dev \
    libspdlog-dev

# ✅ 验证
pkg-config --modversion boost && echo "boost OK"
pkg-config --modversion yaml-cpp && echo "yaml-cpp OK"
```

---

## 第3步：USB 设备透传（10分钟）

RS485 模块插在 Windows 上，需要转发进 WSL2 才能用。

### 3.1 Windows 侧：安装 usbipd

在 Windows **PowerShell（管理员）** 中：

```powershell
winget install --interactive --exact dorssel.usbipd-win
```

安装完成后重启 WSL：

```powershell
wsl --shutdown
```

然后重新打开 `wsl`。

### 3.2 在 WSL 里安装 USB 工具

```bash
sudo apt install -y linux-tools-generic hwdata
sudo update-alternatives --install /usr/local/bin/usbip usbip /usr/lib/linux-tools/*-generic/usbip 20
```

### 3.3 每次使用：绑定 USB 设备到 WSL

**每次拔插 USB 转 RS485 模块后**，在 Windows **PowerShell（管理员）** 中执行：

```powershell
# 查看设备列表，找到 RS485 模块（CH340 或 FT232 芯片的）
usbipd list

# 先绑定
usbipd bind --busid <BUSID>   # 把 <BUSID> 换成你看到的那一行的总线ID

# 再 attach 到 WSL
usbipd attach --wsl --busid <BUSID>
```

然后在 WSL 终端里检查：

```bash
ls /dev/ttyUSB*
# 应看到 /dev/ttyUSB0

# 如果提示 Permission denied：
sudo chmod 666 /dev/ttyUSB0
```

> 如果不想每次都管理员权限，可以把当前用户加入 usbipd 组，或者用管理员 PowerShell 一次性 attach。

### 3.4 快速验证串口通信

```bash
# 插上 USB 模块、灵巧手已上电 24V 后
python3 -c "
import serial
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.5)
# 读 ID 寄存器（地址 1000 = 0x03E8）
frame = bytes([0xEB, 0x90, 0x01, 0x04, 0x11, 0xE8, 0x03, 0x02, 0xFD])
ser.write(frame)
import time; time.sleep(0.1)
resp = ser.read(100)
print(f'收到 {len(resp)} 字节: {resp.hex()}')
ser.close()
"
# 有回复 → 通信 OK
# 无回复 → 检查 24V 电源是否打开、黄绿线是否接反
```

---

## 第4步：克隆仓库（1分钟）

```bash
cd ~
git clone https://github.com/wyl4955-collab/dexterous-hand-competition.git
cd dexterous-hand-competition
ls
# 应看到: src/ config/ launch/ build.sh README.md SETUP.md
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
# 应看到: competition_interfaces, rh56f2_driver, ...
```

---

## 第6步：启动测试

```bash
cd ~/dexterous-hand-competition
source install/setup.bash

# 终端1：启动手部驱动
ros2 run rh56f2_driver rh56f2_driver_node --ros-args \
    -p port:="/dev/ttyUSB0" -p hand_id:=1

# 终端2（另开一个 wsl 窗口）：查看手部状态
cd ~/dexterous-hand-competition
source install/setup.bash
ros2 topic echo /hand/state --once
# 应输出 6 个手指的角度和力值
```

---

## 第7步：一键启动全系统（开发模式）

```bash
cd ~/dexterous-hand-competition
source install/setup.bash

# 用 mock 机械臂（还没接真臂时）
ros2 launch competition_bringup.launch.py mock_arm:=true
```

---

## 工作流程总结

```
日常开发流程：

1. 打开 PowerShell → wsl → 进入 Ubuntu
2. cd ~/dexterous-hand-competition
3. source install/setup.bash
4. 写代码、编译、运行

插拔 USB 模块后：
  PowerShell（管理员）: usbipd list → usbipd bind → usbipd attach --wsl
  WSL 里: ls /dev/ttyUSB* 确认设备存在
```

---

## 验收清单

全部通过才算环境就绪：

| 检查项 | 命令 | 预期 |
|--------|------|------|
| WSL2 正常 | `wsl --list --verbose` (PowerShell) | VERSION 2 |
| ROS2 正常 | `ros2 --version` (WSL里) | 无报错 |
| 串口透传 | `ls /dev/ttyUSB0` (WSL里) | 文件存在 |
| 编译成功 | `colcon build` | 0 errors |
| 灵巧手通信 | `ros2 topic echo /hand/state --once` | 输出6个角度 |
| 灵巧手可控 | 发 HandCommand 后手指能动 | 角度变化 > 50 |

---

## 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `wsl` 命令不存在 | WSL 没装 | 回到第0步 |
| WSL 里面 `ls /dev/ttyUSB*` 啥也没有 | USB 没 attach | PowerShell 管理员执行 usbipd attach |
| `/dev/ttyUSB0` 存在但报 Permission denied | 权限不够 | `sudo chmod 666 /dev/ttyUSB0` |
| 串口有设备但 Python 测试无回复 | ①24V 没开 ②黄绿线接反 | 先查电源，再交换黄绿线 |
| `colcon build` 失败 | 没 source ROS2 | `source /opt/ros/humble/setup.bash` |
| 运行节点报 GLIBC 错误 | WSL 版本问题 | `sudo apt update && sudo apt upgrade` |
| 手指抖动或无响应 | 力传感器未校准 | 上位机执行空载校准 |
| VS Code 想连接 WSL | 装 Remote-WSL 插件 | VS Code 左下角 → 连接到 WSL |
