# 灵巧手机器人比赛——自主镊子夹豆

中文 | [English](README.md)

这是一个面向天轶 Pro 2.0 人形机器人的 ROS2 Humble 工作区，用于开发世界人形机器人运动会“镊子夹豆”自主任务。

## 安全警告

本项目默认启用 `dry_run` 模式。目前项目中不包含经过实机验证的关节姿态、灵巧手比例值、机器人关节限位或天轶 SDK 适配器。

在完成所有标记为 `TODO_REAL_ROBOT` 的内容之前，禁止关闭 `dry_run`。第一次实机运动必须至少两人在场，其中一人专门负责急停，并从低速度、低电流、单关节、小角度开始验证。

发生安全异常时，系统必须停止发布新的运动命令并进入锁定状态，不得自动归中、自动移动手臂或自动松开镊子。

## 项目目标

最终系统需要自主完成：

1. 检查机器人、相机、灵巧手、配置和安全状态；
2. 移动到可重复的任务准备姿态；
3. 识别源容器、目标容器、镊子和黄豆；
4. 抓取并持续保持 160 mm 弯头医用镊子；
5. 选择一颗安全、容易夹取的黄豆；
6. 执行悬停、视觉修正、下降、夹紧、抬升、转移和释放；
7. 视觉确认夹取和投放成功后再增加计数；
8. 在 300 秒内循环执行，最后停在安全悬停姿态。

## 开发里程碑

不要一开始直接运行完整五分钟任务。建议按以下顺序推进：

- `M0`：构建、配置、ROS2回调和安全锁正常；
- `M1`：人工把镊子装到手上，使用固定坐标夹取一颗豆；
- `M2`：通过视觉识别并夹取有效工作区内的一颗豆；
- `M3`：机器人自动抓取并验证镊子；
- `M4`：多豆选择、失败恢复和五分钟循环。

人工安装镊子只用于 `M1` 开发验证，最终比赛版本仍需自主完成全部流程。

## 目录结构

```text
Dexterous_Hand_Robot_Competition/
├── src/
│   ├── competition_interfaces/          # ROS2自定义消息
│   └── dexterous_hand_competition/      # Python功能包
├── calibration/                         # 现场标定文件
├── docs/                                # 分工与接口文档
├── scripts/                             # 启动和检查脚本
├── data/                                # 图像与调试数据，不提交Git
├── bags/                                # rosbag数据，不提交Git
├── logs/                                # 运行日志，不提交Git
├── PROJECT_STATUS.md                    # 项目完成状态
├── README.md                            # 英文说明
└── README_CN.md                         # 中文说明
```

Python功能包的主要目录：

```text
dexterous_hand_competition/
├── common/
│   ├── contracts.py            # ActionResult等统一接口
│   ├── config_loader.py        # YAML配置加载和检查
│   ├── robot_state.py          # 机器人状态缓存
│   ├── arm_controller.py       # 手臂控制抽象
│   ├── hand_controller.py      # 灵巧手控制抽象
│   └── safety_monitor.py       # 安全锁和安全状态节点
├── control/
│   └── workspace_mapper.py     # 工作区网格插值
├── vision/
│   ├── bean_detector.py        # 黄豆视觉检测
│   ├── table_calibration.py    # 像素到桌面坐标转换
│   └── scene_node.py           # Orin视觉场景节点
├── skills/
│   └── tweezer_skills.py       # 抓镊子、夹豆和释放技能
├── task/
│   ├── fsm.py                  # 状态定义
│   └── bean_task_node.py       # 任务状态机节点
└── tools/
    └── mock_scene_node.py      # 软件模拟场景节点
```

## 四人分工

| 成员 | 主要职责 | 主要目录 |
|---|---|---|
| A | 机器人状态、手臂/身体运动、轨迹和工作区映射 | `common/robot_state.py`、`common/arm_controller.py`、`control/` |
| B | 视觉检测、场景发布和相机桌面标定 | `vision/`、`config/vision.yaml`、`calibration/camera_table.yaml` |
| C | 灵巧手、镊子姿态和镊子动作技能 | `common/hand_controller.py`、`skills/`、`config/hand.yaml` |
| D | 状态机、安全、消息接口、构建、启动和最终集成 | `task/`、`common/safety_monitor.py`、`competition_interfaces/`、`launch/` |

详细中文分工请阅读：

[docs/TEAM_DIVISION_CN.md](docs/TEAM_DIVISION_CN.md)

模块接口说明：

[docs/INTERFACES.md](docs/INTERFACES.md)

## Ubuntu 22.04 / ROS2 Humble环境构建

将整个项目放到 Ubuntu 或机器人主控后执行：

```bash
cd ~/Dexterous_Hand_Robot_Competition
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

在天轶机器人 x86 主控上，还可能需要加载本体环境：

```bash
source /home/ubuntu/data/param/ros2_setup.bash
source /home/ubuntu/ros2ws/install/setup.bash
```

每次修改 Python 文件后可以重新执行：

```bash
colcon build --symlink-install
source install/setup.bash
```

## 纯软件dry-run测试

模拟系统不读取真实相机，也不会向机器人发布真实动作，适合四个人在完成实机接口前调试消息和状态机。

启动模拟安全节点、模拟场景和任务状态机：

```bash
source install/setup.bash
ros2 launch dexterous_hand_competition mock_system.launch.py
```

在另一个终端启动任务：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
```

观察任务状态：

```bash
ros2 topic echo /bean_task/state
```

停止任务：

```bash
ros2 service call /bean_task/stop std_srvs/srv/Trigger '{}'
```

`mock_scene_node` 只能用于软件集成，禁止在真实机器人任务中使用模拟场景控制运动。

## x86与Orin分开运行

### Orin：视觉节点

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch dexterous_hand_competition vision.launch.py
```

也可以使用脚本：

```bash
bash scripts/start_orin.sh
```

### x86：安全和任务节点

```bash
source /opt/ros/humble/setup.bash
source /home/ubuntu/data/param/ros2_setup.bash
source /home/ubuntu/ros2ws/install/setup.bash
source install/setup.bash
ros2 launch dexterous_hand_competition bean_task.launch.py dry_run:=true
```

也可以使用脚本：

```bash
bash scripts/start_x86.sh
```

`start_x86.sh` 当前固定使用 `dry_run:=true`，需要等实机适配、标定和安全检查全部完成后再修改。

## 实机开发前必须完成

- 使用 `ros2 topic type`、`ros2 service type` 和 `ros2 interface show` 确认所有SDK接口；
- 完成 `arm_controller.py`、`robot_state.py`、`hand_controller.py` 和 `safety_monitor.py` 中的实机适配；
- 测量并填写全部关节限位和关键姿态；
- 标定灵巧手六个控制量、镊子保持/夹紧/释放姿态；
- 标定镊子尖端TCP、夹取高度和工作区网格；
- 完成彩色图和深度图对齐检查；
- 完成相机像素到桌面坐标标定；
- 验证硬急停、遥控急停、电源、关节错误和反馈超时；
- 确认每个机器人控制话题只有一个发布者；
- 在两人安全监督下通过 `M0` 和 `M1`；
- 保存通过测试的Git版本和配置文件。

## ROS2接口

主要视觉话题：

```text
/bean_task/scene
/bean_task/debug_image
/bean_task/vision_health
```

主要任务与安全话题：

```text
/bean_task/state
/bean_task/safety_ok
/bean_task/safety_reason
```

任务服务：

```text
/bean_task/start
/bean_task/stop
```

自定义消息位于：

```text
src/competition_interfaces/msg/BeanTarget.msg
src/competition_interfaces/msg/Scene.msg
src/competition_interfaces/msg/TaskState.msg
```

## 配置与标定文件

### `config/system.yaml`

保存运行模式、任务时间、反馈超时、主控地址和话题名称。

### `config/vision.yaml`

保存相机话题、源容器ROI、HSV阈值、面积/圆度参数和单应矩阵。

### `config/poses.yaml`

保存关节限位、准备姿态、镊子抓取姿态、容器悬停姿态和安全结束姿态。

### `config/hand.yaml`

保存六个手指顺序、速度、力度和镊子预抓取/保持/夹紧/释放姿态。

### `config/workspace.yaml`

保存源容器工作区边界、3×3网格和`hover/pick/lift`三层关节角。

### `calibration/camera_table.yaml`

保存相机像素点、桌面已知坐标、单应矩阵和标定误差。

### `calibration/tweezer_tcp.yaml`

保存镊子尖端相对手腕的偏移、开口大小和夹取高度。

所有标定文件当前均为未标定状态，不能直接用于实机。

## 运行前检查

```bash
bash scripts/check_topics.sh
```

必须特别检查：

```bash
ros2 topic info /arm/cmd_pos --verbose
```

启动任务前必须确保 `/arm/cmd_pos` 没有其他程序同时发布控制命令。

## 录制rosbag

```bash
bash scripts/record_bag.sh
```

bag默认保存在项目的 `bags/` 目录。开发阶段建议每次完整测试都录制，并同时保存：

- Git commit或tag；
- YAML配置和标定文件；
- 状态机日志；
- 视觉调试图；
- 成功投放数量；
- 每颗豆耗时；
- 失败状态和原因。

## 测试命令

```bash
python3 -m compileall src/dexterous_hand_competition
colcon test
colcon test-result --verbose
```

当前框架包含以下纯Python测试：

- `ActionResult`接口；
- 手臂限位和dry-run；
- 灵巧手数组检查；
- 工作区插值和禁止外推；
- 状态机初始化、错误和复位。

## Git协作

建议使用以下分支：

```text
main             现场验证通过的稳定版本
dev              每日集成版本
feat/motion      成员A
feat/vision      成员B
feat/tweezers    成员C
feat/system      成员D
```

规则：

1. 每个文件只有一个主负责人；
2. 每人每天至少提交一次可运行的小改动；
3. 修改公共接口、单位或消息字段前通知全队；
4. 标定参数只能写入YAML，不能硬编码；
5. bag、原始图像和大日志不提交Git；
6. 完整实机测试通过后立即打tag；
7. `main`始终保留一个可回退的现场验证版本。

## 当前项目状态

请查看：

[PROJECT_STATUS.md](PROJECT_STATUS.md)

目前已经完成项目骨架、消息定义、dry-run控制抽象、视觉/状态机框架、模拟集成节点和基础测试。真实机器人SDK适配、相机数据采集、关键姿态、工作区、灵巧手和镊子TCP仍需要团队在实机上完成。

