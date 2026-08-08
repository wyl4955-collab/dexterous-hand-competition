# C2 开发与联调指南：镊子技能、夹豆状态机、轻量集成

## 1. 本次已完成的范围

C2 代码只组合其他成员提供的公共接口，不访问他们的私有变量，也不猜测天轶 SDK 消息类型、关节 ID 或实机参数。

- `skills/tweezer_skills.py`：拿镊子、确认镊子、悬停、视觉修正、下降、夹豆、抬升、转移、放豆、失败恢复、归还镊子和安全结束。
- `task/fsm.py`：显式状态转移表、逐状态超时、错误锁定和转换历史。
- `task/target_manager.py`：候选豆选择、失败计数、最大重试和短期黑名单。
- `task/bean_task_node.py`：ROS 2 编排节点、开始/停止/复位服务、安全锁、剩余时间、视觉确认和计数。
- `tools/mock_scene_node.py`：仅供开发的多豆场景和夹取/投放确认模拟。
- `launch/`、`scripts/`：一键 mock、任务启动、话题检查、bag 与 run_id 元数据。

当前实机模式仍被锁定，这是有意的安全设计。A 与 C1 完成真实适配器并经过低速验证后，才能把它们注入 `BeanTaskNode(skills=...)`。

## 2. 开发环境

- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10
- x86 主控与 Orin 必须使用同一个 `ROS_DOMAIN_ID` 和兼容的 DDS 配置。
- 天轶参数环境通常来自 `/home/ubuntu/data/param/ros2_setup.bash`。

不要在 Ubuntu 24.04/Jazzy 环境中直接构建 Humble 工作区。

## 3. 第一次运行 mock

```bash
cd ~/Dexterous_Hand_Robot_Competition
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
bash scripts/start_mock.sh
```

脚本会启动安全模拟、合成视觉、C2 节点，并自动调用 `/bean_task/start`。另开终端观察：

```bash
source /opt/ros/humble/setup.bash
source ~/Dexterous_Hand_Robot_Competition/install/setup.bash
ros2 topic echo /bean_task/state
```

预期状态依次经过选择、悬停、下降、夹取、视觉确认、转移、投放确认，最终进入 `DONE`。计数只会在收到对应豆子 ID 的投放确认后增加。

## 4. C2 ROS 2 接口

| 接口 | 类型 | 生产者 → 消费者 |
|---|---|---|
| `/bean_task/scene` | `competition_interfaces/msg/Scene` | B → C2 |
| `/bean_task/safety_ok` | `std_msgs/msg/Bool` | A安全监控 → C2 |
| `/bean_task/active_target_id` | `std_msgs/msg/UInt32` | C2 → B/日志 |
| `/bean_task/pick_confirmed_id` | `std_msgs/msg/UInt32` | B → C2 |
| `/bean_task/drop_confirmed_id` | `std_msgs/msg/UInt32` | B → C2 |
| `/bean_task/state` | `competition_interfaces/msg/TaskState` | C2 → 全员 |
| `/bean_task/start` | `std_srvs/srv/Trigger` | 操作员 → C2 |
| `/bean_task/stop` | `std_srvs/srv/Trigger` | 操作员 → C2 |
| `/bean_task/reset` | `std_srvs/srv/Trigger` | 安全检查后操作员 → C2 |

豆子 ID `0` 被 C2 保留为“当前没有目标”。B 发布的真实豆子 ID 必须从 `1` 开始。在夹取和投放确认话题中，必须发布当前 `/bean_task/active_target_id`，并且确认消息必须发生在对应动作之后；旧消息不会被接受。

## 5. 与 A、B、C1 的对接清单

### A：运动与安全

需要给 `TweezerSkills` 提供：

```python
move_named_pose(name, timeout_sec) -> ActionResult
move_to_joints(target, duration_sec, timeout_sec) -> ActionResult
stop_motion(reason) -> None
map_table_to_joints(x_m, y_m, layer) -> dict[int, float] | None
```

`layer` 只有 `hover`、`pick`、`lift`。任何工作区外目标必须返回 `None`。

### B：视觉

除 `Scene` 外，需要根据当前目标 ID 输出两次独立确认：

1. 抬升后确认豆子已被夹住，发布 `/bean_task/pick_confirmed_id`。
2. 松开后确认豆子已进入目标容器，发布 `/bean_task/drop_confirmed_id`。

无法判断时不要发布 `True` 的替代信号，让 C2 超时并进入恢复流程。

### C1：灵巧手

需要提供：

```python
move_hand_pose(name, timeout_sec) -> ActionResult
tweezer_held_verifier() -> bool | None
hand_feedback_is_fresh() -> bool
```

`tweezers_release` 只能松开豆子，不能释放镊子；只有 `release_tool` 可以归还镊子。

## 6. M1 到 M4 的启用顺序

1. M1：保持 `auto_grasp_tweezer=false`、`auto_release_tweezer=false`，人工装镊子，仅验证一颗固定豆。
2. M2：接入 B 的真实 `Scene`，仍保持 `dry_run=true` 检查选择与确认逻辑。
3. M3：标定拿取/归还位置后，再启用两个自动镊子参数。
4. M4：确认失败恢复、黑名单、超时和五分钟 bag 后再增加循环数量。

## 7. 安全规则

- `/bean_task/safety_ok=false` 后进入 `ERROR_LOCK`，只调用 A 的停止/保持接口。
- 安全触发时禁止自动归中、自动移动和自动松开镊子。
- 手动 `/bean_task/stop` 会阻止新动作并保持当前位置。
- 必须人工检查并重新收到安全正常信号后，才允许调用 `/bean_task/reset`。
- `dry_run=false` 前，A/C1 适配器、全部姿态、工作区网格、关节限位和反馈超时都必须实机验证。

## 8. 常用命令

```bash
bash scripts/check_topics.sh
ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
ros2 service call /bean_task/stop std_srvs/srv/Trigger '{}'
ros2 service call /bean_task/reset std_srvs/srv/Trigger '{}'
bash scripts/record_bag.sh
```
