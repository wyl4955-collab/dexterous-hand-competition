# 成员 B 视觉模块——操作手册

## 我现在有什么

代码已经全部写完、测试通过、推送到 GitHub（commit `1b9b660`）。

### 我负责的文件

```
src/dexterous_hand_competition/dexterous_hand_competition/vision/
├── depth_utils.py          ← 深度图工具（对齐、查询、高度校验）
├── target_selector.py      ← 黄豆评分排序器
├── container_detector.py   ← 源容器/目标容器检测
├── tweezer_detector.py     ← 镊子检测
├── bean_detector.py        ← 黄豆检测 + 多帧追踪
├── scene_node.py           ← ROS2 场景发布节点（Orin 端）
└── table_calibration.py    ← 单应矩阵（像素→桌面坐标）

src/competition_interfaces/msg/
└── Scene.msg               ← 场景消息（含镊子字段）

config/
└── vision.yaml             ← 所有视觉参数

scripts/
└── collect_data.py         ← 离线标定数据采集

test/
├── test_target_selector.py ← 黄豆选择器测试
└── test_depth_utils.py     ← 深度工具测试
```

### 我对其他模块输出的内容

| 话题 | 类型 | 内容 |
|---|---|---|
| `/bean_task/scene` | `Scene` | 源/目标容器中心、镊子位置+角度、黄豆列表（带评分和追踪 ID） |
| `/bean_task/debug_image` | `Image` | 带标注框的调试图 |
| `/bean_task/vision_health` | `Bool` | 视觉管线是否正常运行 |

---

## 一、本地开发环境配好（一次性的）

打开 WSL 终端（在开始菜单搜索 "Ubuntu-22.04" 或 PowerShell 里输入 `wsl -d Ubuntu-22.04`），逐条执行：

```bash
# 1. 安装 ROS2 Humble
sudo apt update
sudo apt install -y software-properties-common curl gnupg lsb-release
sudo add-apt-repository -y universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-humble-desktop python3-colcon-common-extensions python3-rosdep

# 2. 安装项目需要的额外 Python 包
sudo apt install -y python3-opencv python3-numpy python3-yaml python3-pip

# 3. 把代码拷到 WSL
cd ~
cp -r /mnt/e/灵巧手机器人二次开发/dexterous-hand-competition ~/dexterous-hand-competition

# 4. 构建
cd ~/dexterous-hand-competition
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash

# 5. 跑测试
python3 -m pytest src/dexterous_hand_competition/test/ -v
```

---

## 二、后续要做的事——按时间顺序

### 第 1 步：上 Orin 采集标定数据（需要机器人）

```bash
# SSH 到 Orin
ssh nvidia@192.168.41.2

# 确认相机在线
ros2 topic hz /ob_camera_head/color/image_raw

# 运行采集脚本（按回车保存一张）
cd ~/dexterous-hand-competition
source install/setup.bash
python3 scripts/collect_data.py --output data/raw
```

采集要求：

| 场景 | 数量 |
|---|---|
| 空源容器 + 空目标容器 | 10 组 |
| 1 颗豆子 | 10 组 |
| 5 颗豆子 | 10 组 |
| 10 颗豆子 | 10 组 |
| 20 颗豆子（散乱） | 10 组 |
| 镊子放在放置区 | 10 组 |
| 偏亮光线 | 5 组 |
| 偏暗光线 | 5 组 |

**每组都要保存**彩色图 + 深度图 + 相机内参 → 按回车一次就是一个完整的三件套。

### 第 2 步：标定 HSV ——黄豆颜色

在你电脑上用 Python 调整参数，直到 mask 只覆盖黄豆：

```python
import cv2
import numpy as np

img = cv2.imread('data/raw/frame_0000_xxx_color.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 先试着滑动条找范围
lower = np.array([15, 60, 50])   # 先猜
upper = np.array([45, 255, 255])

mask = cv2.inRange(hsv, lower, upper)
cv2.imwrite('mask_debug.png', mask)  # 看效果

# 反复调整直到满意
```

然后把最终值写到 `config/vision.yaml` 的 `vision.hsv_lower` 和 `vision.hsv_upper`。

### 第 3 步：标定容器 HSV

同样的方法，但针对**源容器**和**目标容器**的颜色：

- 打开采集的图片
- 用调好的 HSV 参数看容器 mask 效果
- 写到 `vision.yaml` 的 `container.source` 和 `container.target`

**这两个容器的颜色不一样**——源和目标通常是不同颜色的碗。如果两个碗颜色一样，可以只调一组 HSV，两个容器都用同一组。

### 第 4 步：标定单应矩阵（像素→桌面坐标）

这是最关键的一步——相机画面里的像素坐标要换算成机器人桌子上的真实坐标。

方法：
1. 在桌面上放 4 个已知真实坐标的标记点（比如棋子、硬币）
2. 用卷尺量出每个点在桌面坐标系下的 (x_m, y_m)
3. 在相机图像里找到这 4 个点的像素坐标 (u, v)
4. 算出单应矩阵：

```python
import cv2
import numpy as np

# 4个点的像素坐标
image_points = np.array([
    [300, 200],   # 点1
    [900, 200],   # 点2
    [300, 500],   # 点3
    [900, 500],   # 点4
], dtype=np.float32)

# 4个点的桌面坐标（米）
table_points = np.array([
    [0.35, -0.25],
    [0.55, -0.25],
    [0.35, -0.05],
    [0.55, -0.05],
], dtype=np.float32)

H, _ = cv2.findHomography(image_points, table_points)
print(H)  # 3x3 矩阵，写入 vision.yaml 的 calibration.homography
```

标完以后验证：
- 用 H 矩阵把黄豆像素坐标转成桌面坐标
- 拿卷尺量那颗豆实际在哪
- 误差应该 < 5mm

### 第 5 步：标定源容器 ROI

ROI 是"源容器在图像中出现的区域"，我们只在 ROI 内检测黄豆，避免把外面乱七八糟的东西误检。

```python
# 打开采集的图，框出源容器区域
# shadow
x, y, w, h = 300, 180, 420, 360  # 调这四个数
cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
cv2.imshow('ROI', img)
```

调好后写回 `vision.yaml` 的 `vision.source_roi`。

### 第 6 步：标定镊子

镊子检测有几个参数要调：

- `tweezer.roi`：镊子在桌上的放置区域（像素范围）
- `tweezer.gray_threshold`：亮度阈值（不锈钢 > 180）

先用采集的镊子图在电脑上调，参照第 2 步的思路。

### 第 7 步：dry-run 集成

在 x86 上启动模拟系统：

```bash
ros2 launch dexterous_hand_competition mock_system.launch.py
```

在另一个终端检查话题：

```bash
ros2 topic echo /bean_task/scene
```

确认所有字段都有值，数据不是空的。

### 第 8 步：实机视觉测试

先在 Orin 上单独跑视觉：

```bash
ros2 launch dexterous_hand_competition vision.launch.py
```

这时候机器人不动，只看视觉输出。

检查：
- `/bean_task/scene` 里的 source_center/target_center 对不对
- `/bean_task/scene` 里的 beans 数量和位置对不对
- 镊子位置准不准
- `/bean_task/debug_image` 保存下来看标注框

### 第 9 步：配合联调

联调顺序参考：

| 阶段 | B 做什么 | 配合谁 |
|---|---|---|
| M1 | 不用 B，A+C1 用固定坐标 | — |
| M2 | 提供黄豆桌面坐标，验证 A 的手能对准 | A+D |
| M3 | 提供镊子桌面坐标，验证 C1 能自动抓 | A+C1+D |
| M4 | 全流程：黄豆选择、失败记录、循环 | 全员 |

---

## 三、和队友怎么对接

### 给 C2（状态机/集成）提供的东西

1. Scene 话题——C2 只需要订阅 `/bean_task/scene` 就能拿到所有视觉信息
2. 视觉健康状态——C2 需要监听 `/bean_task/vision_health`，false 时暂停任务
3. 字段解释：
   - `Scene.source_center`：源容器（豆在哪）的中心坐标（米）
   - `Scene.target_center`：目标容器（豆往哪放）的中心坐标
   - `Scene.tweezer_position`：镊子的中心坐标和角度，给 C1 抓镊子用
   - `Scene.beans[0]`：排序第一的豆就是最佳夹取目标
   - `BeanTarget.failure_count`：这个 ID 的豆失败了多少次，C2 决定是否跳过

### 和 A（运动控制）的配合

A 需要知道对象的目标桌面坐标来移动手臂。B 的输出格式就是桌面坐标（米），直接对应。

A 在工作区网格里有个 `map_table_to_joints(x_m, y_m, layer)` 函数。B 的黄豆坐标 (x_m, y_m) 可以直接喂给 A。

联调验证方法：
1. B 输出黄豆坐标
2. A 控制手臂移动到那个坐标的正上方悬停
3. 看镊子尖端是否真的在豆子正上方
4. 偏多少？把偏移量反馈给我，我调整单应矩阵

### 和 C1（灵巧手）的配合

C1 需要知道镊子的位置和角度才能自动抓取。B 的 Scene 里有 `tweezer_position` 和 `tweezer_angle`。

C1 抓镊子流程会调用 `TweezerSkills.grasp_tweezer()`，这个函数内部调用 A 的 `move_named_pose('tweezer_pregrasp')` 和 `move_named_pose('tweezer_grasp')`。

如果 M3（抓镊子）失败多，B 可以提供镊子的实时视觉位置帮助 C1 微调。

---

## 四、容错/回退机制

B 写代码时考虑了最坏情况——检测失败不会炸系统：

| 检测器 | 失败时怎么办 |
|---|---|
| 容器检测 | 用 YAML 里的 `fallback_m` 固定坐标 |
| 镊子检测 | 用 YAML 里的 `fallback_m` + `fallback_angle_rad` |
| 黄豆检测 | 返回空列表，`vision_health` 跟踪相机图像是否按时到达 |

这意味着即使所有检测都失败，Scene 话题依然有数据（都是回退值），任务状态机不会因为视觉模块挂掉。

---

## 五、比赛当天的现场顺序

1. 开机 → 自检完成 → 状态灯蓝绿
2. 确认相机在线：`ros2 topic hz /ob_camera_head/color/image_raw`
3. 启动视觉节点：`ros2 launch dexterous_hand_competition vision.launch.py`
4. 检查输出：`ros2 topic echo /bean_task/scene`，确认数据合理
5. 如果光照和标定时不一致 → 快速调 `vision.yaml` 的 HSV
6. 正式运行时观察 `vision_health`，如果持续 false 就查日志

---

## 六、常见问题排查

| 症状 | 可能原因 | 怎么查 |
|---|---|---|
| 检测不到黄豆 | HSV 范围不对 | 存取一帧 debug_image 看 mask 效果 |
| 检测出假黄豆（容器/阴影） | 形态学参数太松 | 加大 min_area、调 morph_kernel |
| 黄豆坐标偏很多 | 单应矩阵没标对 | 用标记点重标 H 矩阵 |
| 镊子检测不到 | 亮度阈值不对 | 调 gray_threshold，镊子是亮的 |
| vision_health 一直是 false | 相机断连 | 检查相机话题是否在线 |
| 容器检测不稳定 | 光照变了 | 用 fallback 固定坐标兜底 |

## 七、环境初始化脚本

把这个保存到 WSL 里，每次新开终端先 source：

```bash
# ~/dexterous-hand-competition/setup_env.sh
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash
```

以后每次进 WSL 先运行 `source ~/dexterous-hand-competition/setup_env.sh`。
