# 镊子夹豆项目四人分工（初学者执行版）

## 共同目标

不要一开始就做五分钟完整比赛。按下面顺序逐级完成：

1. `M0`：构建、配置、ROS2回调和安全锁正常；
2. `M1`：人工把镊子装到手上，固定坐标夹一颗豆；
3. `M2`：视觉选择有效工作区内的一颗豆；
4. `M3`：机器人自动抓取并保持镊子；
5. `M4`：多豆选择、失败恢复和五分钟循环。

每个里程碑稳定后才能进入下一个。人工装镊子只用于M1开发验证，最终比赛版本仍需自主完成。

## 成员A：运动控制与工作区标定

### 负责代码

- `common/robot_state.py`
- `common/arm_controller.py`
- `control/workspace_mapper.py`
- `config/poses.yaml`
- `config/workspace.yaml`

### 第一步：确认实机接口

在x86上执行：

```bash
ros2 topic type /arm/status
ros2 interface show $(ros2 topic type /arm/status)
ros2 topic echo /arm/status --once
ros2 topic type /arm/cmd_pos
ros2 interface show $(ros2 topic type /arm/cmd_pos)
ros2 topic info /arm/cmd_pos --verbose
```

记录真实消息类型、字段、关节ID、单位、更新频率和其他发布者。不要根据文档猜消息类型。

### 代码任务

1. 把SDK状态回调接到`RobotState.update_joint()`；
2. 验证所有右臂关节的真实限位；
3. 把SDK命令发布封装成`command_sink`；
4. 测试单关节、小角度、最低安全速度；
5. 用示教记录`ready`、`arms_out`、`look_table`、`tweezer_pregrasp`、`tweezer_grasp`、`source_hover`、`destination_hover`和`safe_finish`；
6. 将全部姿态写入YAML，禁止写死在Python里；
7. 标定源容器3×3网格的`hover/pick/lift`三层关节角；
8. 验证网格内部插值和网格外拒绝。

### 交付接口

```python
move_to_joints(...) -> ActionResult
move_named_pose(...) -> ActionResult
map_table_to_joints(...) -> dict | None
feedback_is_fresh(...) -> bool
stop_motion(...) -> None
```

### 完成标准

- 无反馈时拒绝运动；
- 目标超限时不发布命令；
- 所有动作都有超时；
- 每个关键姿态低速重复10次无碰撞；
- C2不需要知道关节ID就能调用动作；
- 工作区外的视觉目标永远不会转换成运动。

## 成员B：视觉识别与相机桌面标定

### 负责代码

- `vision/bean_detector.py`
- `vision/scene_node.py`
- `vision/table_calibration.py`
- `config/vision.yaml`
- `calibration/camera_table.yaml`

### 第一步：采集数据

使用最终头部角度和桌距，采集至少50组同步彩色/深度数据，包括：

- 空容器；
- 1、5、10、20颗黄豆；
- 靠边、相互接触、阴影和反光；
- 正常、偏亮和偏暗灯光；
- 相机内参、机器人姿态、头部角度和时间。

### 代码任务

1. 先在固定源容器ROI内检测黄豆；
2. 调整HSV、面积、圆度和边缘距离阈值；
3. 保存每张图的mask和带框调试图；
4. 人工标记部分数据，统计漏检和误检；
5. 用至少四个桌面已知点计算单应矩阵；
6. 验证彩色图和深度图是否已经对齐，不能用彩色像素直接索引未对齐深度；
7. 输出带时间戳、置信度和桌面坐标的`Scene`；
8. 优先选择远离边缘、与其他豆分离、位于工作区中心且失败次数少的豆。

### 交付话题

```text
/bean_task/scene
/bean_task/debug_image
/bean_task/vision_health
```

### 完成标准

- 桌面坐标误差目标不超过5毫米；
- 容器、镊子和阴影不被当作黄豆；
- 标定缺失、头部姿态变化或图像超时时输出无效结果；
- 可以只用离线图片测试，不需要机器人运动；
- 每次选择目标都能说明选择依据。

## 成员C1：灵巧手底层控制与拿镊子

### 负责代码

- `common/hand_controller.py`
- `config/hand.yaml`
- `calibration/tweezer_tcp.yaml`

### 第一步：确认灵巧手接口

```bash
ros2 service list | grep inspire_hand
ros2 service type /inspire_hand/set_angle_flexible/right_hand
ros2 interface show $(ros2 service type /inspire_hand/set_angle_flexible/right_hand)
ros2 service type /inspire_hand/set_force/right_hand
ros2 service type /inspire_hand/set_speed/right_hand
ros2 topic echo /inspire_hand/state/right_hand --once
```

记录六个手指顺序、角度/力/速度比例范围、服务返回字段和反馈频率。

### 代码任务

1. 将真实服务封装成`HandController.command_sink`；
2. 所有数组发送前检查长度和范围；
3. 标定`open`、`tweezers_pregrasp`、`tweezers_hold`、`tweezers_squeeze`、`tweezers_release`和`release_tool`；
4. 区分“松开豆子”和“放掉镊子”，这两个动作不能混用；
5. 标定镊子尖端TCP、手中保持位置、开口量和夹紧量；
6. 为C2提供稳定的`move_hand_pose()`接口，不在本文件中编写完整任务状态机；
7. 对所有灵巧手服务增加参数检查、响应检查和超时处理。

### 交付接口

```python
move_hand_pose(name: str) -> ActionResult
set_positions(values: list[float]) -> ActionResult
set_forces(values: list[float]) -> ActionResult
set_speeds(values: list[float]) -> ActionResult
hand_feedback_is_fresh(...) -> bool
```

### 完成标准

- 镊子保持五分钟不掉落；
- 连续50次保持/夹紧/释放不掉工具；
- 松开豆子时不会松掉镊子；
- 服务调用始终有成功、失败或超时；
- C2只使用公开接口即可完成拿镊子、夹豆和释放动作。

## 成员C2：镊子技能、夹豆状态机与轻量集成

### 负责代码

- `skills/tweezer_skills.py`
- `task/fsm.py`
- `task/bean_task_node.py`
- `launch/`
- `scripts/`
- `setup.py`和`package.xml`

### 第一步：运行时和构建

1. 先使用A、B、C1的mock接口跑通状态机，不等待所有实机模块完成；
2. 确认任务运行时executor持续spin；
3. 确认`colcon build --symlink-install`成功；
4. 检查x86和Orin的ROS_DOMAIN_ID、RMW和DDS连通；
5. 保持`dry_run=true`，先完成固定坐标单豆流程。

### 代码任务

1. 使用A的运动接口和C1的灵巧手接口完成`grasp_tweezer()`、`squeeze_bean()`、`release_bean()`和`release_tweezer()`；
2. 将A、B、C1公开接口接入状态机，不能访问他们的私有变量；
3. 每个状态只检查输入、调用一个公开动作并根据结果转移；
4. 每个状态必须有超时；
5. 只有视觉确认夹取或投放成功后才能增加豆子计数；
6. 实现失败豆短期黑名单、最大重试次数和剩余时间管理；
7. 订阅A提供的安全锁、B提供的视觉健康状态和C1提供的手部状态；
8. 安全触发后停止新命令并锁定，禁止自动归中或自动松开镊子；
9. 完成一键启动、话题检查、rosbag和每轮run_id日志；
10. 负责日常`dev`集成，但公共接口修改必须由对应负责人审查。

### 完成标准

- 每个状态有明确成功、失败和超时路径；
- 安全锁能阻止所有新动作；
- 视觉或关节反馈过期时拒绝继续；
- 一条命令启动，一条命令保存规定bag；
- 每轮可以查到代码版本、配置、日志、图像和失败原因；
- 主分支始终有一个现场验证过的版本。

## 原D板块如何分摊

D板块不是删除，而是拆给最接近该工作的成员：

| 原D工作 | 新负责人 | 原因 |
|---|---|---|
| 急停、电源、关节错误、反馈超时和`safety_monitor.py` | A主责，C1审查手部安全 | 与运动和硬件状态关系最紧密 |
| `BeanTarget`、`Scene`等视觉消息字段 | B主责，C2审查 | B负责生产数据，C2负责消费数据 |
| `ActionResult`和模块函数接口 | A、B、C1共同确定，C2整理文档 | 防止集成人员单方面修改接口 |
| executor、状态机、launch和启动脚本 | C2 | 与任务编排属于同一条链路 |
| rosbag和run_id日志框架 | C2搭框架，全员输出本模块日志 | 工作量较小，但所有模块都要配合 |
| `setup.py`、`package.xml`依赖 | 修改模块的人维护，C2合并检查 | 避免所有构建问题集中给一个人 |
| Git合并和版本tag | C2执行，A复核 | 采用双人确认，不设置纯管理岗位 |

这样四个人都有主要开发任务，同时原D工作仍有明确负责人，不会在最终集成时无人处理。

## 四人集成顺序

1. C2验证构建、配置、executor和mock状态机；
2. A验证状态反馈、运动安全和一个低速关节；
3. C1验证无工具手势、镊子保持和释放；
4. B验证离线和实时视觉但不让机器人运动；
5. A+C1+C2完成M1固定豆；
6. A+B+C2完成M2视觉单豆；
7. A+C1+C2完成M3自动拿镊子；
8. 全员完成M4五分钟循环和故障注入。

## 分支与文件所有权

```text
main             现场验证版本
dev              每日集成
feat/motion-safety      A
feat/vision-interfaces  B
feat/hand-control       C1
feat/tweezer-task       C2
```

每个文件只有一个主负责人。任何公共函数名、消息字段、单位或配置结构发生变化，都必须在合并前通知四个人。
