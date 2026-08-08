# C2 夹豆任务：构建、运行与排错手册

## 1. 先确认当前能运行到什么程度

当前 C2 代码可以完整运行软件模拟流程：模拟安全信号、模拟视觉豆子、模拟机械臂和灵巧手，然后自动完成多颗豆子的状态机循环。

当前版本不能直接控制真实机器人。`dry_run=false` 时，如果没有 A 和 C1 提供并验证过的真实适配器，C2 会拒绝启动。这是安全锁，不是程序故障。不要为了绕过它而删除检查。

## 2. 必须使用的系统

- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10
- 工作区所在磁盘至少保留 5 GB 空间

先执行：

```bash
cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION_ID'
test -f /opt/ros/humble/setup.bash && echo 'Humble exists'
source /opt/ros/humble/setup.bash
echo "$ROS_DISTRO"
```

正确结果应包含 `Ubuntu 22.04`、`Humble exists` 和 `humble`。

如果显示 Ubuntu 24.04/Jazzy，建议重新创建 Ubuntu 22.04 虚拟机。不要在同一套 Ubuntu 24.04/Jazzy 环境中强行混用 Humble。出现下面的提示，就表示当前系统没有安装 Humble：

```text
bash: /opt/ros/humble/setup.bash: No such file or directory
```

## 3. 第一次取得代码

```bash
cd ~
git clone https://github.com/wyl4955-collab/dexterous-hand-competition.git Dexterous_Hand_Robot_Competition
cd ~/Dexterous_Hand_Robot_Competition
git fetch origin
git switch feat/tweezer-task
```

如果 C2 分支还没有推送到 GitHub，就先在 Windows 的项目目录提交并推送，再在 Ubuntu 中执行以上命令。

以后更新代码使用：

```bash
cd ~/Dexterous_Hand_Robot_Competition
git pull --ff-only
```

## 4. 安装依赖并构建

第一次安装基础工具：

```bash
sudo apt update
sudo apt install -y git python3-rosdep python3-colcon-common-extensions
```

如果从未初始化过 rosdep：

```bash
sudo rosdep init
rosdep update
```

如果 `sudo rosdep init` 提示已经存在，可以忽略这一步，继续执行 `rosdep update`。

构建工作区：

```bash
cd ~/Dexterous_Hand_Robot_Competition
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

确认 C2 可执行程序已安装：

```bash
ros2 pkg executables dexterous_hand_competition
```

输出中应至少包含：

```text
bean_task_node
mock_scene_node
safety_monitor_node
```

每次打开新终端，都要重新执行：

```bash
source /opt/ros/humble/setup.bash
source ~/Dexterous_Hand_Robot_Competition/install/setup.bash
```

修改 Python 代码后，在工作区根目录重新执行：

```bash
colcon build --symlink-install
source install/setup.bash
```

## 5. 先运行自动测试

```bash
cd ~/Dexterous_Hand_Robot_Competition
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon test --packages-select competition_interfaces dexterous_hand_competition --event-handlers console_direct+
colcon test-result --verbose
```

必须看到失败数为 0，才能继续模拟联调。

## 6. 一条命令运行完整模拟

在终端 1 中执行：

```bash
cd ~/Dexterous_Hand_Robot_Competition
bash scripts/start_mock.sh bean_count:=3 time_limit_sec:=30.0
```

这个脚本会完成以下操作：

1. 启动模拟安全节点；
2. 启动模拟视觉节点并生成 3 颗豆子；
3. 启动 C2 状态机；
4. 等待 `/bean_task/start` 服务出现；
5. 自动调用开始服务。

在终端 2 中观察状态：

```bash
source /opt/ros/humble/setup.bash
source ~/Dexterous_Hand_Robot_Competition/install/setup.bash
ros2 topic echo /bean_task/state
```

正常情况下会看到状态依次经过：

```text
CHECK_SYSTEM
GRASP_TWEEZER
VERIFY_TWEEZER
WAIT_SCENE
SELECT_BEAN
MOVE_HOVER
VISUAL_REFINE
DESCEND
SQUEEZE
LIFT
VERIFY_PICK
MOVE_TARGET
RELEASE_BEAN
VERIFY_DROP
...
DONE
```

最终应满足：

- `state_name: DONE`
- `beans_confirmed: 3`
- `last_error` 为空

模拟程序只记录动作调用，不会向真实机器人发送动作命令。

## 7. 手动启动方式

如果想自己控制开始时机，在终端 1 运行：

```bash
source /opt/ros/humble/setup.bash
source ~/Dexterous_Hand_Robot_Competition/install/setup.bash
ros2 launch dexterous_hand_competition mock_system.launch.py bean_count:=3 time_limit_sec:=30.0
```

在终端 2 检查接口后开始：

```bash
bash ~/Dexterous_Hand_Robot_Competition/scripts/check_topics.sh
ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
```

停止、复位和再次运行：

```bash
ros2 service call /bean_task/stop std_srvs/srv/Trigger '{}'
ros2 service call /bean_task/reset std_srvs/srv/Trigger '{}'
ros2 service call /bean_task/start std_srvs/srv/Trigger '{}'
```

`reset` 只允许从 `DONE` 或 `ERROR_LOCK` 调用。复位后，模拟场景会重新生成全部豆子。

## 8. 建议做的 4 个软件验收

### 验收 A：正常三颗豆子

```bash
bash scripts/start_mock.sh bean_count:=3 time_limit_sec:=30.0
```

预期：`DONE`，确认计数为 3。

### 验收 B：空场景

```bash
bash scripts/start_mock.sh bean_count:=0 time_limit_sec:=30.0
```

预期：连续收到 3 个独立空场景后才结束，不能因为单帧漏检立即结束。

### 验收 C：手动停止

任务运行时在另一个终端执行：

```bash
ros2 service call /bean_task/stop std_srvs/srv/Trigger '{}'
```

预期：停止启动新动作，进入安全结束流程，最后为 `DONE`。手动停止不会自动松开镊子。

### 验收 D：安全锁

任务运行时执行：

```bash
ros2 topic pub --once /bean_task/safety_ok std_msgs/msg/Bool '{data: false}'
```

预期：进入 `ERROR_LOCK`，计数不再增加。检查原因并恢复安全信号后，才能调用 `/bean_task/reset`。

## 9. 主要配置参数

配置文件：`src/dexterous_hand_competition/config/bean_task.yaml`

| 参数 | 作用 | 当前默认值 |
|---|---|---:|
| `dry_run` | 是否禁止真实动作并使用模拟适配器 | `true` |
| `time_limit_sec` | 整体任务时限 | `300.0` |
| `target_count` | 达到多少颗后结束；0 表示直到无豆或超时 | `0` |
| `scene_timeout_sec` | 视觉场景多久没有更新算过期 | `0.5` |
| `empty_scene_confirmations` | 连续多少个独立空场景才判定无豆 | `3` |
| `max_pick_retries` | 单颗豆最大失败次数 | `3` |
| `blacklist_ttl_sec` | 失败目标临时黑名单时间 | `20.0` |
| `min_target_confidence` | 最低候选置信度 | `0.25` |
| `stop_new_pick_remaining_sec` | 剩余时间低于该值时不再开始新夹取 | `20.0` |
| `auto_grasp_tweezer` | 是否自动拿镊子 | `false` |
| `auto_release_tweezer` | 结束时是否自动归还镊子 | `false` |

修改 YAML 后要重新启动节点。运行中使用 `ros2 param set` 修改参数不会重新创建状态机和目标管理器，因此当前版本把这些参数按“启动时配置”使用。

## 10. x86 与 Orin 分机联调

两台设备必须：

- 都使用 Ubuntu 22.04/ROS 2 Humble；
- 连接同一交换机；
- 使用相同 `ROS_DOMAIN_ID`；
- 使用兼容的 `RMW_IMPLEMENTATION` 和 DDS 配置。

两台设备分别执行：

```bash
source /opt/ros/humble/setup.bash
if test -f /home/ubuntu/data/param/ros2_setup.bash; then source /home/ubuntu/data/param/ros2_setup.bash; fi
source ~/Dexterous_Hand_Robot_Competition/install/setup.bash
echo "ROS_DISTRO=$ROS_DISTRO"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-unset}"
echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-default}"
```

Orin 启动视觉：

```bash
cd ~/Dexterous_Hand_Robot_Competition
bash scripts/start_orin.sh
```

x86 启动 C2 的安全模拟模式：

```bash
cd ~/Dexterous_Hand_Robot_Competition
bash scripts/start_x86.sh
```

另开 x86 终端检查：

```bash
bash ~/Dexterous_Hand_Robot_Competition/scripts/check_topics.sh
ros2 topic echo --once /bean_task/vision_health
ros2 topic echo --once /bean_task/scene
ros2 param get /bean_task_node dry_run
```

最后一条必须显示 `true`。确认场景坐标、目标 ID 和视觉健康正常后，再调用开始服务。

## 11. 日志和 rosbag

启动 x86 脚本时会在 `logs/<run_id>/` 中保存任务日志和 Git 版本信息。

需要录制联调数据时，在单独终端执行：

```bash
cd ~/Dexterous_Hand_Robot_Competition
source /opt/ros/humble/setup.bash
source install/setup.bash
bash scripts/record_bag.sh
```

按 `Ctrl+C` 停止录制。bag 文件保存在 `bags/`，元数据保存在 `logs/`。

## 12. 常见问题

### `/opt/ros/humble/setup.bash` 不存在

当前虚拟机没有 Humble，或系统是 Ubuntu 24.04/Jazzy。先换成 Ubuntu 22.04/Humble 环境。

### `Package 'dexterous_hand_competition' not found`

没有构建或当前终端没有加载工作区：

```bash
cd ~/Dexterous_Hand_Robot_Competition
colcon build --symlink-install
source install/setup.bash
```

### `/bean_task/start` 不存在

检查节点是否启动：

```bash
ros2 node list
ros2 service list | grep /bean_task
```

查看启动终端中 `bean_task_node` 的报错。

### 一直停在 `WAIT_SCENE`

依次检查：

```bash
ros2 topic hz /bean_task/scene
ros2 topic echo --once /bean_task/vision_health
ros2 topic echo --once /bean_task/scene
echo "${ROS_DOMAIN_ID:-unset}"
```

`Scene.valid` 和 `Scene.calibrated` 必须为 `true`，场景更新周期必须短于 `scene_timeout_sec`。

### 进入 `ERROR_LOCK`

查看状态中的 `last_error`：

```bash
ros2 topic echo --once /bean_task/state
```

先人工检查机械臂、灵巧手、相机、急停和工作区，再恢复安全/视觉信号，最后调用：

```bash
ros2 service call /bean_task/reset std_srvs/srv/Trigger '{}'
```

### 开始服务提示适配器未连接

说明使用了 `dry_run=false`，但真实 A/C1 适配器没有注入。这是当前版本的预期保护行为。

## 13. 上真实机器人前仍需完成的代码

必须由 A 和 C1 提供并实机验证以下接口：

```text
arm.move_named_pose(...)
arm.move_to_joints(...)
arm.stop_motion(...)
hand.move_hand_pose(...)
workspace_mapper.map_table_to_joints(...)
hand_feedback_is_fresh()
tweezer_held_verifier()
```

随后新增真实启动入口，构造 `TweezerSkills`，再通过 `BeanTaskNode(skills=skills)` 注入。还必须完成 `poses.yaml`、`hand.yaml`、`workspace.yaml` 和镊子 TCP 的现场标定。

在这些工作完成之前，只运行 `dry_run=true`。第一次实机试动作至少两人在场，一人专门控制急停，并从单动作、低速度、小范围开始。
