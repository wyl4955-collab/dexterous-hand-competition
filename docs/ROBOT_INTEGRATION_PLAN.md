# 天轶机器人集成计划

> 比赛方提供的机器人：天轶 2.0 Pro，35 自由度，Ubuntu 22.04 + ROS2

---

## 一、我们当前有什么

```
competition_ws/
├── src/
│   ├── rh56f2_driver/          ← 灵巧手驱动（RS485协议）
│   ├── competition_vision/     ← 黄豆检测 + 工具追踪 + 秤读数
│   ├── manipulation_skills/    ← 动作原语（捏/握/敲/放）
│   ├── powder_weighing/        ← 粉末称量 FSM
│   ├── bean_picking/           ← 镊子夹豆 FSM
│   └── competition_supervisor/ ← 比赛总控
├── tools/                      ← 8个训练/标定工具
├── config/                     ← 参数配置
└── training_data/              ← 录制数据
```

## 二、机器人提供什么

| 组件 | 机器人自带 | 我们写的 |
|------|----------|---------|
| 灵巧手（6 DOF × 2） | ✅ 有驱动 | 🟡 读它的 ROS2 topic 名 |
| 机械臂（7 DOF × 2） | ✅ 有驱动 | 🟡 读它的 ROS2 topic 名 |
| 相机（头部 ×1 + 底盘 ×2 RGBD） | ✅ 已接入 | 🟡 换 topic 名 |
| 六维力传感器（腕部） | ✅ 有 topic | ✅ 直接订阅 |
| 天平（精确到 0.01g） | ❌ 外接 | ✅ 我们写好了 `scale_reader.py` |
| 镊子/药勺/黄豆/面粉 | ❌ 自备 | ✅ 道具自备 |
| 灵巧手力传感器（手指上） | ❓ 未知 | 到场地确认 |

## 三、到场地后第一天（半天）

### 目标：搞清楚机器人的所有 ROS2 接口

#### 3.1 物理检查（30 分钟）

```
检查项：
□ 灵巧手外观 → 是因时 RH56 系列吗？
□ 灵巧手线缆 → 航插还是直连？
□ 相机安装位置 → 头部视角能不能覆盖工作台？
□ 工作台在哪里 → 镊子/药勺/天平怎么摆放？
□ 机器人手臂够得到桌面吗？
```

#### 3.2 登录 x86（30 分钟）

1. 网线连接机器人背后的调试以太网口
2. 自己的电脑设 IP 为 `192.168.41.xxx/255.255.255.0`
3. `ssh ubuntu@192.168.41.1`
4. 连 WiFi 后拔网线

#### 3.3 调查话题（1 小时）

```bash
ssh ubuntu@192.168.41.1
ros2 topic list
```

把输出贴给我。我来分析哪些话题是手的、臂的、相机的。

#### 3.4 找手的话题（30 分钟）

```bash
# 看手的控制话题（你手动控制手，看哪些话题有数据变化）
ros2 topic echo /hand_right/joint_states --once    # 试这个名
ros2 topic echo /right_hand/state --once           # 或这个
ros2 topic echo /dexterous_hand/state --once       # 或这个

# 如果找不到，挨个 echo 试试
ros2 topic list | while read t; do
  echo "=== $t ==="
  ros2 topic echo "$t" --once 2>/dev/null | head -5
done
```

**确定手的控制接口后，我们有两种方案：**

```
方案 A（推荐）: 机器人的手已经通过 Can/EtherCAT 集成
  → 话题已经有了（如 /hand_right/state, /hand_right/command）
  → 我们只需要写一个 bridge：把我们的 HandCommand 映射到它的格式
  → 修改量：1 个新文件（不超过 100 行）

方案 B: 机器人有 RS485 接口暴露在手部
  → 我们的 USB 转 RS485 模块插入机器人 x86 的 USB 口
  → 直接跑我们的 driver_node.py（几乎零修改）
```

#### 3.5 看相机话题（30 分钟）

```bash
ros2 topic echo /camera/color/image_raw --once    # 试这个
ros2 topic echo /head_camera/rgb --once           # 或这个
# 找到后，记下话题名和消息类型
```

#### 3.6 找手臂控制接口（30 分钟）

```bash
# 手臂通常有几个话题：
# /left_arm/joint_states   ← 当前关节角度
# /left_arm/joint_commands ← 控制指令
# /left_arm/end_effector   ← 末端位姿
ros2 topic list | grep -i arm
ros2 topic list | grep -i joint
```

#### 3.7 看诊断平台（15 分钟）

浏览器打开 `http://192.168.41.1:8080` → Topic 页面 → 列出所有话题及消息类型（和 `ros2 topic list` 互补）。

## 四、适配计划（根据调查结果）

### 方案 A 的工作量（手话题已存在）

只需要写 **bridge python 包**：

```
src/competition_bridge/          ← 新增
├── package.xml
├── setup.py
└── competition_bridge/
    ├── __init__.py
    └── hand_bridge.py           ← 核心：
        # 订阅机器人的 /hand_state → 转换成我们的 HandState 格式 → 重新发布
        # 订阅我们的 HandCommand → 转换成机器人的 /hand_command 格式 → 发布
```

修改：
- `competition_vision/perception_node.py` → 换相机话题名
- `config/default.yaml` → 更新话题映射表
- `launch/competition.launch.py` → 启动 bridge 节点

**不改的：** 所有 FSM、skills、tools——完全不动。

### 方案 B 的工作量（我们自己连手）

几乎零修改。把 RS485 模块插到机器人 x86 的 USB 口：

```bash
# 在 x86 上
ls /dev/ttyUSB* && sudo chmod 666 /dev/ttyUSB0
python3 ~/dexterous-hand-competition/src/rh56f2_driver/rh56f2_driver/driver_node.py
```

然后在 x86 上启动 rosbridge，WSL 那边不需要了。

## 五、到场后完整任务清单

### 第 1 天上午：调查（4 小时）

```
□ 物理检查机器人 + 工作台
□ SSH 登录 x86
□ ros2 topic list 并逐个 echo
□ 确定：手话题名 / 臂话题名 / 相机话题名 / 手指力传感器有无
□ 把调查结果贴给我 → 我当场写 bridge 代码
```

### 第 1 天下午：适配（3 小时）

```
□ 如果方案 A：写 competition_bridge、改话题名
□ 如果方案 B：插 RS485 模块，跑 driver_node.py
□ 编译 → 在 x86 上启动全系统
□ Foxglove 连到机器人 → 确认能看到所有话题 → 拖面板
```

### 第 1 天晚上：首测（1 小时）

```
□ ros2 bag record -a 录制
□ 用手动方式（Foxglove 滑块）完成一次模拟夹豆
□ 确认手 + 臂 + 相机全在 bag 里
```

### 第 2 天上午：标定（3 小时）

```
□ 力控标定（用场地提供的黄豆）→ tools/calibrate_force.py
□ 振动撒粉标定（用场地提供的面粉）→ tools/calibrate_tap.py
□ 相机标定（工作台 4 点法）→ tools/calibrate_camera.py
```

### 第 2 天下午 ~ 第 5 天：训练

```
□ 每天上午粉末称量 10 轮
□ 每天下午镊子夹豆 10 轮
□ 每轮都 ros2 bag record -a
□ 每天跑 tools/evaluate.py 看趋势
```

### 赛前 1 天

```
□ tools/match_sim.py --matches 20 连续压力测试
□ 参数锁定
□ 代码冻结
```

## 六、我们 WSL 里现在的代码有什么用

```
rh56f2_driver/          → 赛前训练用（自己的手），比赛可能用方案 B 也可能不用
manipulation_skills/    → 比赛直接用，不改
powder_weighing/        → 比赛直接用，不改
bean_picking/           → 比赛直接用，不改
competition_vision/     → 改一下相机话题名就可以
competition_supervisor/ → 比赛直接用，不改
tools/                  → 标定和训练工具全保留
config/                 → 到场后更新参数
```

**核心逻辑全部不动。只加一个 bridge 包（或者不改，看方案 A/B），改一个话题名。**

## 七、你们现在能做的事（不到场地也行的）

1. 所有人在 WSL 上搭建环境、编译通过 → 参照 `SETUP_GUIDE.docx`
2. 用自己的灵巧手练习 Foxglove 滑块控制 → 熟悉手感
3. 读通 `powder_fsm.py` 和 `bean_fsm.py` 的代码逻辑
4. 读 `PROJECT.md` 了解团队分工（ABCD 四个角色）
5. 准备好道具：镊子 ×2、药勺 ×2、黄豆 ×50、面粉、电子天平（0.01g）、USB 转 RS485 模块、杜邦线
