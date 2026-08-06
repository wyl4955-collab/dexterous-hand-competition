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
- D不需要知道关节ID就能调用动作；
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

## 成员C：灵巧手与镊子技能

### 负责代码

- `common/hand_controller.py`
- `skills/tweezer_skills.py`
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
5. 标定镊子尖端TCP、悬停高度、下降距离和夹紧量；
6. 完成`grasp_tweezer()`、`squeeze_bean()`、`release_bean()`和`release_tweezer()`；
7. 每一步检查A的运动结果，失败后立即返回，禁止继续下一动作。

### 交付接口

```python
grasp_tweezer() -> ActionResult
verify_tweezer_held() -> bool
squeeze_bean() -> ActionResult
release_bean() -> ActionResult
release_tweezer() -> ActionResult
```

### 完成标准

- 镊子保持五分钟不掉落；
- 连续50次保持/夹紧/释放不掉工具；
- 松开豆子时不会松掉镊子；
- 服务调用始终有成功、失败或超时；
- 自动拿镊子失败时不会开始夹豆。

## 成员D：状态机、安全、构建与集成

### 负责代码

- `task/fsm.py`
- `task/bean_task_node.py`
- `common/safety_monitor.py`
- `competition_interfaces/`
- `launch/`
- `scripts/`
- `setup.py`和`package.xml`

### 第一步：运行时和构建

1. 确认`colcon build --symlink-install`成功；
2. 确认任务运行时executor持续spin；
3. 检查x86和Orin的ROS_DOMAIN_ID、RMW和DDS连通；
4. 保持`dry_run=true`，先用模拟结果跑通状态机；
5. 冻结`BeanTarget`、`Scene`、`TaskState`和`ActionResult`字段。

### 代码任务

1. 将A/B/C公开接口接入状态机，不能访问他们的私有变量；
2. 每个状态只检查输入、调用一个公开动作并根据结果转移；
3. 每个状态必须有超时；
4. 只有视觉确认夹取或投放成功后才能增加豆子计数；
5. 实现失败豆短期黑名单和最大重试次数；
6. 剩余时间不足时停止选择新豆并进入安全结束；
7. 监控硬急停、遥控急停、电源、关节错误、反馈超时、视觉超时、温度、电流和动作超时；
8. 安全触发后停止新命令并锁定，禁止自动归中或自动松开镊子；
9. 完成一键启动、话题检查、rosbag和每轮run_id日志；
10. 维护`dev`集成分支和可回退的稳定tag。

### 完成标准

- 每个状态有明确成功、失败和超时路径；
- 安全锁能阻止所有新动作；
- 视觉或关节反馈过期时拒绝继续；
- 一条命令启动，一条命令保存规定bag；
- 每轮可以查到代码版本、配置、日志、图像和失败原因；
- 主分支始终有一个现场验证过的版本。

## 四人集成顺序

1. D验证构建、配置、executor和安全锁；
2. A验证状态反馈和一个低速关节；
3. C验证无工具手势；
4. B验证离线和实时视觉但不让机器人运动；
5. A+C+D完成M1固定豆；
6. A+B+D完成M2视觉单豆；
7. A+C+D完成M3自动拿镊子；
8. 全员完成M4五分钟循环和故障注入。

## 分支与文件所有权

```text
main             现场验证版本
dev              每日集成
feat/motion      A
feat/vision      B
feat/tweezers    C
feat/system      D
```

每个文件只有一个主负责人。任何公共函数名、消息字段、单位或配置结构发生变化，都必须在合并前通知四个人。

