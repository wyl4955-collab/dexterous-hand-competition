# 灵巧手专项赛 — 项目总纲

## 一、团队结构（4-5人）

```
组长（1人）
├── 硬件 & 驱动（1人）
├── 感知 & 标定（1人）
├── 算法 & 策略（1人）
└── 测试 & 集成（组长兼，或1人）
```

### 每个角色的产出

| 角色 | 负责 | 产出物 |
|------|------|--------|
| **组长** | 比赛策略、时间线、对外联络、赛前检查 | 每日计划、赛前清单、比赛执行 |
| **硬件驱动** | 灵巧手通信、机械臂控制、供电接线 | 手能动、臂能移、不掉线 |
| **感知标定** | 相机、秤、黄豆检测、镊子追踪 | 看得准、读得对 |
| **算法策略** | 力控参数、振动策略、夹豆策略、状态机 | 夹得住、撒得准 |
| **测试集成** | 全流程跑通、统计成功率、分析失败 | 数据驱动改进 |

### 每人独立工作的代码区域

```
src/rh56f2_driver/          ← 硬件的人改
src/robot_arm_driver/       ← 硬件的人改
src/competition_vision/     ← 感知的人改
tools/calibrate_force.py    ← 算法的人用
tools/calibrate_tap.py      ← 算法的人用
src/powder_weighing/        ← 算法的人改
src/bean_picking/           ← 算法的人改
tools/test_runner.py        ← 测试的人用
config/default.yaml         ← 组长统筹，所有人提交
```

---

## 二、工作包分块

```
WP1: 硬件底座 ──── 灵巧手RS485驱动 + 机械臂适配
WP2: 感知系统 ──── 黄豆检测 + 镊子追踪 + 秤读数
WP3: 参数标定 ──── 力控标定工具 + 振动标定工具 + 相机标定
WP4: 动作原语 ──── 对捏/握持/敲击/释放
WP5: 任务执行 ──── 粉末称量FSM + 镊子夹豆FSM
WP6: 测试评估 ──── 全流程跑分 + 失败分析 + 日志记录
WP7: 比赛系统 ──── 总控 + 一键启动 + 急停 + 成绩报告
```

**每个 WP 可以独立开发和测试，有明确的验证标准。**

---

## 三、一套完整的训练怎么跑

不是你跑代码然后看运气。是**标定→练习→评估→调参→再练习**的循环。

```
┌──────────────────────────────────────────────────────┐
│                                                     │
│   ① 标定阶段（一次性，到场地后重新做）                │
│   ├─ 力控标定: tools/calibrate_force.py              │
│   │  测出黄豆最佳夹持力、镊子握持力                  │
│   ├─ 振动标定: tools/calibrate_tap.py                │
│   │  测出不同敲击力度→落粉量对应表                    │
│   └─ 相机标定: tools/calibrate_camera.py             │
│      测出像素→世界坐标变换矩阵                        │
│                                                     │
│   ② 单任务练习（每天大量跑）                          │
│   ├─ tools/train_powder.py ← 只练称量               │
│   │  设目标5g→自动执行→自动判断成败→记录日志          │
│   └─ tools/train_bean.py ← 只练夹豆                 │
│      放N颗豆→自动挨个夹→记录成功率                   │
│                                                     │
│   ③ 评估（每次练完看数据）                            │
│   ├─ tools/evaluate.py ← 读取训练日志，算指标         │
│   │  成功率、平均耗时、失败原因分布                   │
│   └─ 根据指标决定：调哪个参数？                       │
│                                                     │
│   ④ 全流程模拟（赛前几天）                            │
│   └─ tools/match_sim.py ← 模拟比赛                   │
│      随机目标→称量→夹豆→计分→连续20轮                │
│                                                     │
└──────────────────────────────────────────────────────┘
```

关键：**每次训练都留日志，每次改参数都记录。**

---

## 四、训练日志格式

`training/logs/2025-07-26_1430_powder.json`

```json
{
  "timestamp": "2025-07-26T14:30:00",
  "task": "powder_weighing",
  "params": {
    "grasp_force": 40,
    "tap_calib": {"30": 0.01, "50": 0.02, "80": 0.04}
  },
  "rounds": [
    {"target": 5.00, "actual": 5.03, "error": 0.03, "success": true, "time": 87.2, "taps": 34},
    {"target": 5.00, "actual": 4.98, "error": 0.02, "success": true, "time": 92.1, "taps": 28},
    {"target": 5.00, "actual": 5.12, "error": 0.12, "success": false, "time": 120.0, "taps": 80, "failure": "timeout"}
  ],
  "summary": {
    "total": 10,
    "success": 7,
    "success_rate": 0.70,
    "mean_error": 0.04,
    "mean_time": 95.3
  }
}
```

---

## 五、参数版本管理

`config/calibration/` 目录存每次标定的结果，带日期：

```
config/calibration/
├── force_2025-07-26.yaml     ← 在家里标定的力控参数
├── force_2025-08-20.yaml     ← 到比赛场地后重新标定
├── tap_2025-07-26.yaml       ← 在家里标定的振动参数
├── tap_2025-08-20.yaml       ← 用比赛现场面粉重新标定
└── camera_2025-08-20.yaml    ← 比赛场地相机标定
```

`config/default.yaml` 始终指向最新的标定结果。

---

## 六、到比赛场地后做什么

```
到达后 30min:
  1. 拆箱、接好所有硬件
  2. 跑 tools/self_check.py 确认手、相机、秤都通

到达后 1h:
  3. 力控标定（现场温度湿度不同，传感器可能偏移）
  4. 振动标定（现场面粉颗粒大小不同）
  5. 相机标定（现场光照、桌子高度不同）

到达后 2h:
  6. 各做 5 轮练习，调整参数
  7. 跑 3 次全流程模拟，确认成功率

赛前 30min:
  8. 最后检查所有硬件连接
  9. 等待裁判指令
```

---

## 七、仓库完整结构（调整后）

```
competition_ws/
├── PROJECT.md                    ← 这份总纲
├── README.md
├── SETUP.md                      ← 环境配置
├── build.sh
├── config/
│   ├── default.yaml              ← 运行时配置
│   └── calibration/              ← 标定数据（按日期）
├── src/                          ← 核心代码（已写完）
│   ├── competition_interfaces/
│   ├── rh56f2_driver/
│   ├── robot_arm_driver/
│   ├── competition_vision/
│   ├── manipulation_skills/
│   ├── powder_weighing/
│   ├── bean_picking/
│   └── competition_supervisor/
├── tools/                        ← 训练和调试工具（新增）
│   ├── self_check.py             ← 全系统自检
│   ├── calibrate_force.py        ← 力控标定
│   ├── calibrate_tap.py          ← 振动撒粉标定
│   ├── calibrate_camera.py       ← 相机标定
│   ├── train_powder.py           ← 粉末称量训练
│   ├── train_bean.py             ← 镊子夹豆训练
│   ├── evaluate.py               ← 训练数据分析
│   └── match_sim.py              ← 全流程比赛模拟
├── training/                     ← 训练日志
│   └── logs/
├── launch/
│   └── competition.launch.py
├── docs/
│   ├── ROADMAP.md
│   ├── TRAINING_PLAN.md
│   └── VENUE_GUIDE.md            ← 比赛场地指南
└── tests/
```

---

## 八、今天你们团队每人干什么

| 人 | 任务 | 产出 |
|----|------|------|
| **所有人** | 先一起把 WSL 环境装好、`colcon build` 跑通 | 每个人电脑上都能编译 |
| **硬件** | USB 透传，跑 `ros2 run rh56f2_driver driver_node`，验证手能动 | 驱动节点跑通 |
| **感知** | 接相机，确认 `/dev/video0` 或 D435i 驱动可用 | 能看到图像 |
| **算法** | 读 PROJECT.md 理解整体架构，准备标定工具 | 理解每个参数含义 |
| **组长** | 确认所有人的 WSL 环境、分配后续任务 | 环境清单 check |

**本周必须完成的里程碑：**

```
7月27日（明天）: 代码能控制手
7月28日: 相机能看到豆子
7月29日: 秤能读数
7月30日: 力控标定完成（找到最佳夹豆力）
7月31日: 振动标定完成（找到力控→落粉量表）
8月1日:  首次全流程跑通（不计时）
```

**这之后，每天就是**：上午练称量 10 轮、下午练夹豆 10 轮、晚上分析数据调参。
