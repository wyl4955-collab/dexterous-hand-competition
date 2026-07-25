# 从头到尾怎么做 — 完整路线图

> 你现在站在起点。这份文档告诉你：仓库是什么、怎么用、到比赛那天每一步干什么。

---

## 一、这个仓库到底是什么

```
dexterous-hand-competition/
├── src/
│   ├── rh56f2_driver/          ← 控制灵巧手的程序
│   ├── competition_vision/     ← 看豆子、看镊子、读秤的程序
│   ├── manipulation_skills/    ← 「捏」「握」「敲」「放」这些动作
│   ├── powder_weighing/        ← 粉末称量的完整流程
│   ├── bean_picking/           ← 镊子夹豆的完整流程
│   ├── competition_supervisor/ ← 裁判：负责启动任务、计分、急停
│   └── competition_interfaces/ ← 各个程序之间通信的「语言定义」
├── config/default.yaml         ← 所有参数（端口、力值、速度、路径点）
├── launch/competition.launch.py ← 一键启动所有程序的脚本
└── build.sh                    ← 编译脚本
```

**类比：** 这就像一个乐队的总谱。

- `rh56f2_driver` = 乐器，把灵巧手变成能被程序控制的设备
- `competition_vision` = 眼睛，看到豆子在哪、秤上多少克
- `manipulation_skills` = 手指肌肉记忆，知道怎么捏、怎么敲
- `powder_weighing` / `bean_picking` = 演奏员，把肌肉记忆串成完整曲子
- `competition_supervisor` = 指挥，喊开始、计分、喊停
- `competition_interfaces` = 五线谱，大家约定好用什么符号传递信息

**每个包都是独立运行的进程，通过 ROS2 「话题」互相传消息。** 就像乐队成员互相听对方的演奏来协调。你不需要手动告诉 A "B 干完了"——A 自己会订阅 B 的状态话题。

---

## 二、从零到比赛，分 6 个阶段

```
第1阶段          第2阶段          第3阶段          第4阶段          第5阶段          第6阶段
现在 →       连上灵巧手 →      接上相机秤 →      参数标定 →      全流程练习 →      比赛
[你在这里]   [明天能做]      [明天/后天]      [这周内]       [赛前两周]       [8月22日]

1.环境编译   3.让手指动起来   5.能看到豆子    8.测40g夹黄   10.反复跑完整   13.一键启动
  ✅已完成      🟡下一步        和秤读数          豆的力值        流程看成功率    等待结果
2.理解架构   4.发指令验证     6.视觉→手闭环  9.测振动撒粉   11.调参提高      
             RS485通信       7.全自动链路     的落粉量       12.压力测试      
                              初步打通                      连续20次       
```

---

## 三、第1阶段：环境（✅ 已完成）

**你有的：**
- WSL2 Ubuntu 24.04 + ROS2 Jazzy
- 代码编译通过，9/9 包
- 仓库在 GitHub 上，组员可以 git clone

**你现在能做什么：**
- `colcon build` 编译
- 用 mock 机械臂启动全系统（灵巧手和相机还没接）

---

## 四、第2阶段：连灵巧手（下一步）

**实物：**
```
灵巧手 ←黄绿线→ USB转RS485模块 ←USB→ 电脑
灵巧手 ←红黑线→ 24V电源（+/-）
```

**操作：**

1. 接好线（断电接！红粗→24V+，黑粗→24V-，黄→A+，绿→B-）
2. USB 模块插电脑
3. 在管理员 PowerShell 里：
   ```powershell
   usbipd list                          # 找到 RS485 模块的 BUSID
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```
4. WSL 里确认：
   ```bash
   ls /dev/ttyUSB*
   sudo chmod 666 /dev/ttyUSB0
   ```
5. Python 快速测试能否通信：
   ```bash
   python3 -c "
   import serial, time
   s = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.5)
   s.write(bytes([0xEB,0x90,1,4,0x11,0xE8,0x03,2,0xFD]))
   time.sleep(0.1)
   print(s.read(100).hex())
   "
   ```
   看到 `90eb` 开头的一串十六进制 = 通信成功 🎉

6. 启动完整系统：
   ```bash
   source ~/dexterous-hand-competition/install/setup.bash
   ros2 launch competition.launch.py mock_arm:=true
   ```
   会看到 driver 启动、校准力传感器 7 秒、然后开始 50Hz 发布状态。

7. 另开终端看手的状态：
   ```bash
   source install/setup.bash
   ros2 topic echo /hand/state --once
   ```
   能看到 6 个手指的角度和力值。

8. 发指令让手指动：
   ```bash
   # 张开所有手指
   ros2 topic pub --once /hand/command competition_interfaces/msg/HandCommand \
     "{target_angles: [1740,1740,1740,1740,1550,1750], force_thresholds: [500,500,500,500,500,500], speeds: [1000,1000,1000,1000,1000,1000], modes: [0,0,0,0,0,0]}"
   
   # 握拳
   ros2 topic pub --once /hand/command competition_interfaces/msg/HandCommand \
     "{target_angles: [900,900,900,900,1100,600], force_thresholds: [300,300,300,300,300,300], speeds: [1000,1000,1000,1000,1000,1000], modes: [0,0,0,0,0,0]}"
   ```

**验收标准：** 手指能动，状态话题有数据。

---

## 五、第3阶段：接相机和秤

**相机：** Intel D435i 或普通 USB 摄像头 → 插到电脑，usbipd attach 到 WSL

**步骤：**
1. USB 摄像头直接就能用（WSL 里 `/dev/video0`）
2. 如果是 D435i：`sudo apt install ros-jazzy-librealsense2 && ros2 launch realsense2_camera rs_launch.py`
3. 启动感知节点检测豆子：
   ```bash
   ros2 topic echo /vision/beans
   ```
   在工作台上撒几颗黄豆，应该能看到检测到豆子的坐标。

**秤：** 精密电子天平（0.01g，带 RS232 串口）

1. 秤的串口线接电脑 → usbipd attach
2. WSL 里确认 `/dev/ttyUSB1`
3. `ros2 topic echo /vision/scale` → 应该能看到实时读数

**验收标准：** 能看到豆子坐标列表、秤的实时读数。

---

## 六、第4阶段：参数标定（最重要的阶段！）

自动化不是一步写出来的，是拿数据标定出来的。

### 4.1 力控标定——夹豆最关键的参数

```
实验器材：30颗黄豆、灵巧手、笔记本

步骤：
1. 灵巧手握住镊子（promitives.grip('tweezers')）
2. 分别设力控为 20, 30, 40, 50, 60, 80g
3. 每个力值夹 5 颗豆，记录：
   - 夹起来了？✅/❌
   - 豆子碎了？✅/❌
4. 画表：

 力控 │ 成功 │ 夹碎 │ 未夹起
 ─────┼──────┼──────┼───────
  20g │  1  │  0  │   4
  30g │  3  │  0  │   2
  40g │  5  │  0  │   0   ← 黄金参数
  50g │  4  │  1  │   0
  60g │  2  │  3  │   0

找到"成功率最高"的那个值，就是你比赛用的力控参数。
```

### 4.2 振动撒粉标定——称量最关键的参数

```
实验器材：天平、面粉/奶粉、灵巧手握住药勺

步骤：
1. 舀一勺约10g的粉，放到天平上方
2. 设振动 force_level = 30，敲 10 次→读天平变化→单次落粉量=变化/10
3. 重复 step2 用 force_level = 50, 80, 120, 180, 250
4. 画表：

 力控 │ 10次总落粉 │ 单次落粉
 ─────┼───────────┼─────────
  30  │  0.10g    │ 0.01g   ← 最后0.05g微调用
  50  │  0.25g    │ 0.025g
  80  │  0.45g    │ 0.045g  ← 最后0.5g精调用
 120  │  0.90g    │ 0.09g
 180  │  1.60g    │ 0.16g
 250  │  3.20g    │ 0.32g   ← 粗调用

把这张表写入 config/default.yaml 的 tap_force_drop 字段。
```

**验收标准：** 两张表格的数据确认无误。

---

## 七、第5阶段：全流程练习（赛前两周，大量跑）

### 每天的训练流程：

```
上午(3h)：
  1. 检查硬件：手能动→相机能看到→秤有读数
  2. 粉末称量：做 10 轮，记录成功率
  3. 分析失败原因：超量了？超时了？振动太强？
  4. 调整参数，再做 10 轮

下午(3h)：
  1. 镊子夹豆：做 10 轮（每轮 3 颗 = 30 次夹豆）
  2. 记录：成功率、夹碎率、单颗耗时
  3. 如果成功率低：检查40g力控参数、检查镊子角度

晚上(1h)：
  1. 跑 1 次完整模拟（称量 + 夹豆，计时）
  2. 记录日志
  3. 第二天的改进项
```

### 怎么改进：

```
问题              检查                                修
────────────────────────────────────────────────────────
豆子夹不起来  → 力控太小，没碰到就停了             → 加大5-10g
豆子总是碎    → 力控太大                          → 减小5-10g
镊子握不住    → 握持力太小或镊子角度不对            → force加到120-150g
粉末撒太多    → tap force_level 太大               → 降一档
粉末不够      → tap force_level 太小或次数不够      → 加一档
超出目标重量  → 振动太强或最后一次没等读数稳定      → 更频繁读秤
```

### 目标：

```
赛前2周: 称量 50% / 夹豆 50%
赛前1周: 称量 70% / 夹豆 70%
赛前3天: 称量 85% / 夹豆 85%
赛前1天: 称量 90% / 夹豆 90%，锁定参数不再改
```

---

## 八、第6阶段：比赛当天

```bash
# 1. 开机自检
source ~/dexterous-hand-competition/install/setup.bash
ros2 launch competition.launch.py mock_arm:=true

# 2. 等裁判指示

# 3. 一键开始
ros2 service call /competition/start std_srvs/srv/Trigger "{}"

# 系统自动：
#   → 力传感器校准（7秒）
#   → 粉末称量（目标随机，限时120秒）
#   → 镊子夹豆（3颗，限时120秒）
#   → 输出成绩

# 4. 紧急情况：重开一个终端
ros2 service call /competition/estop std_srvs/srv/Trigger "{}"
```

---

## 九、你现在马上要做的

**只做一件事：插上灵巧手，验证通信。**

别的什么都别想——相机、秤、标定、训练——全都先放一边。先让手指能动，能读到角度和力值。这一步通了，你才算真正站在起跑线上。
