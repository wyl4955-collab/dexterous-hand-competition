# 成员 B 视觉模块——完整操作手册

**你负责：让机器人"看见"东西。**

这个手册覆盖两个比赛任务：
- **夹豆子**：检测黄豆、源碗、目标碗、镊子
- **粉末称量**：检测粉末容器、勺子（大/中/小）、电子秤读数

---

## 目录

1. [你需要什么](#1-你需要什么)
2. [你的工作流程全貌](#2-你的工作流程全貌)
3. [如何登录机器人](#3-如何登录机器人)
4. [如何确认相机在工作](#4-如何确认相机在工作)
5. [采集标定数据](#5-采集标定数据)
6. [把数据拷回本地电脑](#6-把数据拷回本地电脑)
7. [标定黄豆颜色 (HSV)](#7-标定黄豆颜色-hsv)
8. [标定容器颜色 (HSV)](#8-标定容器颜色-hsv)
9. [标定桌面坐标 (单应矩阵)](#9-标定桌面坐标-单应矩阵)
10. [标定镊子检测参数](#10-标定镊子检测参数)
11. [标定勺子检测参数](#11-标定勺子检测参数)
12. [标定电子秤读数](#12-标定电子秤读数)
13. [在本地 WSL 上验证](#13-在本地-wsl-上验证)
14. [在机器人上做 dry-run 测试](#14-在机器人上做-dry-run-测试)
15. [在机器人上做实机视觉测试](#15-在机器人上做实机视觉测试)
16. [和队友联调](#16-和队友联调)
17. [常见问题排查](#17-常见问题排查)
18. [附录：命令速查表](#18-附录命令速查表)

---

## 1. 你需要什么

### 硬件/访问权限

| 物品 | 用途 | 找谁要 |
|------|------|--------|
| 机器人 (天轶 Pro 2.0) | 拍照、运行代码 | 全队共用 |
| Orin 主控登录权限 | 相机插在 Orin 上，代码在 Orin 跑 | 现场工作人员 / 队长 |
| 笔记本电脑 (你的) | 离线调参、写代码 | 你自己 |
| 卷尺 (1-2米) | 测量桌上物品坐标 | 自备 |
| 黄豆、粉末、镊子、勺子、碗、秤 | 比赛道具 | 组委会 / 领队 |

### 软件/环境

| 你的电脑 | 机器人 (Orin, 192.168.41.2) |
|----------|---------------------------|
| VS Code + WSL Remote 插件 | ROS2 Humble |
| WSL2 Ubuntu 22.04 | 我们的代码 (`~/dexterous-hand-competition/`) |
| Python 3 + OpenCV + NumPy | 奥比中光相机驱动 |
| 代码在 `~/dexterous-hand-competition/` | |

### 关键信息

| 信息 | 值 |
|------|-----|
| x86 主控 IP | `192.168.41.1` |
| Orin 视觉主控 IP | `192.168.41.2` |
| x86 SSH 用户名 | `ubuntu` |
| Orin SSH 用户名 | `nvidia` |
| 相机彩色图话题 | `/ob_camera_head/color/image_raw` |
| 相机深度图话题 | `/ob_camera_head/depth/image_raw` |
| 相机内参话题 | `/ob_camera_head/color/camera_info` |
| 图像分辨率 | 1280×720 |
| 图像格式 | BGR8 (彩色), 16UC1/毫米 (深度) |

---

## 2. 你的工作流程全貌

整个 B 角色的工作是**离线调参 → 实机验证**的循环：

```
第1天：采集照片          ← 你需要机器人
第2天：离线标定所有参数   ← 你只需要电脑
第3天：dry-run 验证      ← 不需要机器人动
第4天：实机视觉测试       ← 需要机器人，但不动手臂
第5天起：联调             ← 全队一起
```

**重要**：你大部分时间不需要机器人在线。数据采集花 1-2 小时，后续标定工作都在你自己电脑上完成。

---

## 3. 如何登录机器人

### 3.1 从你的 Windows 电脑 SSH 到 Orin

打开 **PowerShell**（按 `Win+R`，输入 `powershell`，回车）：

```powershell
ssh nvidia@192.168.41.2
```

第一次登录会出现：
```
The authenticity of host '192.168.41.2' can't be established.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```
输入 `yes` 回车。

然后输入密码（找队长或现场工作人员要）。

### 3.2 登录成功后

你会看到类似这样的提示符：
```
nvidia@ubuntu:~$
```

这意味着你已经登录到了 Orin 主控。

### 3.3 确认代码在 Orin 上

```bash
ls ~/dexterous-hand-competition/
```

如果显示 `No such file or directory`，说明代码还没拷上去，执行：

```bash
cd ~ && git clone https://github.com/wyl4955-collab/dexterous-hand-competition.git
```

如果已经有代码了，更新到最新：

```bash
cd ~/dexterous-hand-competition && git pull
```

### 3.4 构建代码

```bash
cd ~/dexterous-hand-competition
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

看到 `Summary: 2 packages finished` 就是成功。

### 3.5 退出 SSH

```bash
exit
```

---

## 4. 如何确认相机在工作

先 SSH 到 Orin（见上一节），然后：

### 4.1 检查相机话题是否存在

```bash
source /opt/ros/humble/setup.bash
ros2 topic list | grep ob_camera_head
```

应该看到：
```
/ob_camera_head/color/image_raw
/ob_camera_head/depth/image_raw
/ob_camera_head/color/camera_info
/ob_camera_head/depth_to_color
```

### 4.2 检查话题是否有数据

```bash
ros2 topic hz /ob_camera_head/color/image_raw
```

如果看到 `average rate: 29.xxx` 之类的数字，说明相机正常发布图像。按 `Ctrl+C` 停止。

### 4.3 如果话题不存在

相机驱动可能没启动。尝试：

```bash
sudo systemctl start orbbec_head.service
```

然后再检查一次。

---

## 5. 采集标定数据

这是 B 角色**最重要的一步**。一次采集好，后续标定都靠这些照片。

### 5.1 准备

SSH 到 Orin 上（见第 3 节），然后：

```bash
cd ~/dexterous-hand-competition
source install/setup.bash

# 为夹豆子任务采集
python3 scripts/collect_data.py --task bean --output data/calib

# 为粉末称量任务采集
python3 scripts/collect_data.py --task powder --output data/calib

# 两个任务一起采集（推荐）
python3 scripts/collect_data.py --task all --output data/calib
```

### 5.2 脚本怎么用

脚本启动后会打印一个清单，列出所有需要拍摄的场景。比如夹豆子任务有 16 个场景：

1. 它会提示你当前要拍什么（比如 `[beans_5] Source bowl with 5 soybeans`）
2. 你**走到机器人旁边**，按提示把东西摆好
3. **回到电脑前**，按回车拍一张
4. 同一个场景可以多按几次回车拍 2-3 张（更保险）
5. 拍完当前场景，按 `s` + 回车跳到下一个
6. 全部拍完或想退出，按 `q` + 回车

### 5.3 夹豆子任务的拍摄清单及详细说明

下面每一步，你都**走到机器人桌前**按说明摆好，然后**回到电脑**按回车。

| 场景名 | 桌子怎么摆 | 为什么要拍 |
|--------|-----------|-----------|
| `calib_markers` | 在桌上放 4 个标记物（硬币、棋子），用卷尺量出每个的真实桌面坐标 (x_m, y_m)，记下来 | 用于标定像素→桌面坐标的变换矩阵 |
| `empty_both` | 源碗 + 目标碗，空碗，不放豆子，不放镊子 | 确认碗的位置基准 |
| `empty_source` | 只要源碗，不放豆子 | 豆子的背景参考 |
| `beans_1` | 源碗里放 1 颗黄豆，靠近碗中心 | 单颗豆基础检测 |
| `beans_5` | 源碗里放 5 颗黄豆，散开不要挤在一起 | 标准场景 |
| `beans_10` | 源碗里放 10 颗黄豆 | 密集场景 |
| `beans_20` | 源碗里放 20 颗黄豆，部分互相挨着 | 拥挤场景，测试分离能力 |
| `beans_edge` | 5 颗豆，至少 2 颗贴在碗边缘 | 测试边缘过滤 |
| `beans_clumped` | 10 颗豆，几颗粘在一起 | 测试粘连分离 |
| `tweezers_alone` | 只在镊子放置区放镊子，不要碗不要豆 | 镊子检测校准 |
| `tweezers_full` | 完整布局：源碗+目标碗+镊子+10 颗豆 | 完整场景 |
| `light_bright` | 完整布局，开灯/加灯 | 对比不同光照 |
| `light_dim` | 完整布局，关灯/拉窗帘 | 对比不同光照 |
| `alt_bowls` | 如果有多套碗，换一套。没有的话按 s 跳过 | 容器适配性 |

### 5.4 粉末称量任务的拍摄清单及详细说明

| 场景名 | 桌子怎么摆 | 为什么要拍 |
|--------|-----------|-----------|
| `calib_markers` | 4 个标记点（和夹豆子任务可以共用同一套照片） | 标定像素→桌面坐标 |
| `empty_all` | 完全空桌 | 背景参考 |
| `powder_container_empty` | 粉体容器空着，放在左侧 | 空容器检测 |
| `powder_container_full` | 粉体容器装满粉末 | 满容器检测 |
| `powder_container_half` | 粉体容器装一半粉末 | 半满容器检测 |
| `spoons_all` | 全部勺子（大中小）散开放在右侧勺子区 | 多勺同时检测 |
| `spoons_large_only` | 只放大勺子 | 大勺单独 |
| `spoons_medium_only` | 只放中勺子 | 中勺单独 |
| `spoons_small_only` | 只放小勺子 | 小勺单独 |
| `spoons_overlapping` | 勺子部分重叠放置 | 最坏情况测试 |
| `scale_powered_off` | 秤放中间，不开机 | 秤盘位置检测 |
| `scale_zero` | 秤开机，显示 0.0g | 读数基准 |
| `scale_reading_01` | 秤上放物体，显示 10-15g | 数字识别 |
| `scale_reading_02` | 秤上显示 30-40g | 数字识别 |
| `scale_reading_03` | 秤上显示 50-60g | 数字识别 |
| `scale_reading_04` | 秤上显示带小数的值（如 12.3g） | 小数点识别 |
| `powder_full_01` | 完整布局：粉体容器 + 秤(显示~25g) + 全部勺子 | 完整场景 |
| `powder_full_02` | 完整布局，秤上换一个重量（~50g） | 完整场景 |
| `light_bright` | 完整布局，亮光 | 光照对比 |
| `light_dim` | 完整布局，暗光 | 光照对比 |
| `alt_containers` | 如果有备用容器换一套，没有按 s 跳过 | 容器适配性 |

### 5.5 采集时的注意事项

- **头部姿态固定**：采集期间机器人头部保持 `look_table` 姿态（低头看桌面），不要动头
- **桌面物品不要动**：每次摆好后，碗和秤的位置尽量和比赛时一致
- **每个场景拍 2-3 张**：多按几次回车，同一个场景多保存几张备用
- **记下关键坐标**：用卷尺量标记物的真实坐标时，记在一张纸上，后面标定要用

---

## 6. 把数据拷回本地电脑

采集完后在 **Windows PowerShell**（不是 WSL，不是 SSH）里执行：

```powershell
# 从 Orin 拷到你电脑的 E 盘
scp -r nvidia@192.168.41.2:~/dexterous-hand-competition/data/calib E:\灵巧手机器人二次开发\dexterous-hand-competition\data\
```

输入密码后等待传输完成。传输完了把数据拷进 WSL：

在 **WSL Ubuntu-22.04 终端**里：

```bash
cp -r /mnt/e/灵巧手机器人二次开发/dexterous-hand-competition/data/calib ~/dexterous-hand-competition/data/
```

---

## 7. 标定黄豆颜色 (HSV)

你的目标：找到一个 HSV 范围，让程序能准确区分"黄豆"和"不是黄豆"。

### 7.1 什么是 HSV

- H (Hue/色调)：颜色种类。黄色大约在 15-45
- S (Saturation/饱和度)：颜色纯度。颜色越纯越高
- V (Value/明度)：亮度。越亮越高

### 7.2 第一步：打开一张豆子照片

在 WSL 终端里启动 Python：

```bash
cd ~/dexterous-hand-competition
python3
```

然后逐条输入以下代码（每输入一段按一次回车）：

```python
import cv2
import numpy as np

# 找一张有豆子的照片，替换成你实际的文件名
img = cv2.imread('data/calib/bean/beans_5_0000_xxxxx_color.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 第一次猜一个范围
lower = np.array([15, 60, 50])
upper = np.array([45, 255, 255])

mask = cv2.inRange(hsv, lower, upper)

# 保存 mask 看看效果
cv2.imwrite('mask_test.png', mask)
print('Saved mask_test.png — check this file')
```

### 7.3 第二步：看 mask 效果

在 WSL 里把 mask 图拷到 Windows 能看的地方：

```bash
cp ~/dexterous-hand-competition/mask_test.png /mnt/c/Users/刘文毅/Desktop/
```

然后在 Windows 桌面上双击打开 `mask_test.png`。

- **白色区域** = 程序认为"这是黄豆"
- **黑色区域** = 程序认为"不是黄豆"

### 7.4 第三步：调整参数

回到 Python 里，改 `lower` 和 `upper` 的值，重新生成 mask，反复直到效果最好：

```python
# 如果豆子没有被全部标白 → 扩大范围（lower 减小，upper 增大）
# 如果非豆子物体也被标白了 → 缩小范围（lower 增大，upper 减小）

lower = np.array([10, 40, 30])   # 试这个
upper = np.array([50, 255, 255]) # 试这个

mask = cv2.inRange(hsv, lower, upper)
cv2.imwrite('mask_test.png', mask)
# 再拷到桌面看
```

调整目标：
- 豆子全部变白
- 碗、桌面、阴影保持黑色
- 如果少量杂点变白，没关系（后面形态学会滤掉）

### 7.5 第四步：写到配置文件

找到最终的 lower/upper 值后，打开 `config/vision.yaml`，修改这两行：

```yaml
vision:
  hsv_lower: [你的H, 你的S, 你的V]   # 比如 [12, 50, 40]
  hsv_upper: [你的H, 你的S, 你的V]   # 比如 [48, 255, 255]
```

### 7.6 第五步：用多张照片验证

换几张不同光照的照片重复测试，确保同一组 HSV 在不同照片上都能用：

```python
# 换一张照片
img2 = cv2.imread('data/calib/bean/light_dim_0000_xxxxx_color.png')
hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
mask2 = cv2.inRange(hsv2, np.array([12, 50, 40]), np.array([48, 255, 255]))
cv2.imwrite('mask_test2.png', mask2)
```

如果暗光下漏检严重，说明需要两组 HSV（亮光+暗光各一组），目前的代码支持多组 HSV（`bean_detector.py` 只有一组，如果需要多组告诉我，我帮你改）。

---

## 8. 标定容器颜色 (HSV)

容器（碗）的标定方法和黄豆完全一样，只是找的是碗的颜色而不是豆的颜色。

### 8.1 标定源碗

```python
img = cv2.imread('data/calib/bean/empty_source_0000_xxxxx_color.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 碗的颜色是什么就调什么。比如白碗可能是低饱和度
lower = np.array([0, 0, 30])    # 试
upper = np.array([180, 60, 255]) # 试

mask = cv2.inRange(hsv, lower, upper)
cv2.imwrite('bowl_mask.png', mask)
```

调整到碗变白、桌面变黑。然后写进 `vision.yaml`：

```yaml
container:
  source:
    hsv_lower: [你的H, 你的S, 你的V]
    hsv_upper: [你的H, 你的S, 你的V]
```

### 8.2 标定目标碗

同样方法，读目标碗的照片，调整参数，写到 `vision.yaml`：

```yaml
container:
  target:
    hsv_lower: [你的H, 你的S, 你的V]
    hsv_upper: [你的H, 你的S, 你的V]
```

### 8.3 标定粉末容器

同样方法，读粉末容器的照片：

```yaml
# powder_vision.yaml
powder_container:
  hsv_lower: [你的H, 你的S, 你的V]
  hsv_upper: [你的H, 你的S, 你的V]
```

---

## 9. 标定桌面坐标 (单应矩阵)

这是最关键的一步——让程序知道"画面里的像素坐标"对应"桌上真实多少米"。

### 9.1 原理（用白话）

相机的照片是平的（像素），桌面也是平的（坐标）。在照片和桌面之间有一个"映射关系"——就像一个函数，输入像素 (u,v)，输出桌面坐标 (x_m, y_m)。

这个映射关系用 4 个点就能确定。就像你知道地图上 4 个城市的坐标，就能画出整张地图。

### 9.2 第一步：在桌上放 4 个标记点

1. 找 4 个能在相机画面里清楚看到的小物体（硬币、棋子、瓶盖）
2. 把它们放在桌面上，位置尽量分散——不要挤在一起，分布在碗的四周
3. 确保它们和比赛道具（碗、秤）在同一个水平面上

### 9.3 第二步：测量桌面坐标

拿卷尺测量每个标记点的**桌面坐标** (x_m, y_m)。

**坐标系原点的选取**：以机器人正前方桌面上的某个固定点为原点。可以和 A（运动控制负责人）商量，或者直接用一个容易测量的参考点（比如桌角）。

对每个点，测量：
- x：从原点向前方的距离（米）
- y：从原点向左方的距离（米，左边为正，右边为负）

例如：
```
点 1: (0.30, -0.25)
点 2: (0.50, -0.25)
点 3: (0.30, -0.05)
点 4: (0.50, -0.05)
```

**记在纸上**，这组数字很重要。

### 9.4 第三步：找出像素坐标

打开 `calib_markers` 场景的照片，在 Python 里手动标出 4 个点的像素坐标：

```python
import cv2
import numpy as np

img = cv2.imread('data/calib/bean/calib_markers_0000_xxxxx_color.png')

# 手动点出 4 个标记物的像素位置
# 方法：用看图软件打开照片，鼠标移动到标记物中心，记下坐标
# Windows 画图软件打开图片，左下角会显示坐标

# 假设你找到的 4 个像素坐标是：
image_points = np.array([
    [280, 220],   # 点1的 (u, v)
    [920, 230],   # 点2的 (u, v)
    [260, 520],   # 点3的 (u, v)
    [940, 510],   # 点4的 (u, v)
], dtype=np.float32)

# 对应的桌面坐标（用你实际测量的值）：
table_points = np.array([
    [0.30, -0.25],   # 点1的 (x_m, y_m)
    [0.50, -0.25],   # 点2的 (x_m, y_m)
    [0.30, -0.05],   # 点3的 (x_m, y_m)
    [0.50, -0.05],   # 点4的 (x_m, y_m)
], dtype=np.float32)

# 计算单应矩阵（不用管原理，OpenCV 自动算）
H, status = cv2.findHomography(image_points, table_points)
print('Homography matrix:')
print(H)
print()
print('Mean error:', status)  # 越小越好
```

记下输出的 3×3 矩阵，这就是单应矩阵。

### 9.5 第四步：验证误差

用算出来的 H 矩阵，把图像中某个黄豆的像素坐标转成桌面坐标，然后用卷尺实测那颗豆的实际位置，看看差多少：

```python
# 假设图像里某颗豆的像素坐标
u, v = 500, 350

# 用 H 矩阵转换成桌面坐标
pixel = np.array([u, v, 1.0])
table = H @ pixel
x_m = table[0] / table[2]
y_m = table[1] / table[2]
print(f'Bean at pixel ({u}, {v}) → table ({x_m:.3f}m, {y_m:.3f}m)')

# 拿卷尺量那颗豆的实际位置，对比
```

**误差目标：< 5mm（0.005m）**。如果超过 5mm，检查：
- 标记点的测量是否准确
- 标记点是否真的在桌面上（不能翘起来）
- 标记点分布是否足够分散

### 9.6 第五步：写入配置文件

把算出来的 3×3 矩阵写到 `vision.yaml` 和 `powder_vision.yaml` 的 `calibration.homography`，并把 `calibrated` 改成 `true`：

```yaml
calibration:
  calibrated: true
  homography:
    - [H00, H01, H02]    # 第一行
    - [H10, H11, H12]    # 第二行
    - [H20, H21, H22]    # 第三行
```

---

## 10. 标定镊子检测参数

镊子是不锈钢的，在相机画面里很亮。打开镊子照片调参数：

```python
import cv2
import numpy as np

img = cv2.imread('data/calib/bean/tweezers_alone_0000_xxxxx_color.png')

# 先手动框镊子放置区（像素坐标）
# 用画图软件打开图片，找到镊子放置区域左上角和长宽
roi_x, roi_y, roi_w, roi_h = 500, 350, 300, 370

roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

# 尝试不同阈值，直到镊子变白、桌面变黑
_, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

cv2.imwrite('tweezer_binary.png', binary)
# 拷到桌面看效果
```

调整 `gray_threshold`（阈值越高筛选越严格），直到镊子清晰可见、背景干净。然后把 ROI 和阈值写进 `vision.yaml`：

```yaml
tweezer:
  roi:
    x: 你的roi_x
    y: 你的roi_y
    width: 你的roi_w
    height: 你的roi_h
  gray_threshold: 你的阈值
```

---

## 11. 标定勺子检测参数

勺子和镊子类似（金属、高亮），标定方法几乎一样：

```python
import cv2
import numpy as np

img = cv2.imread('data/calib/powder/spoons_all_0000_xxxxx_color.png')

# 框勺子放置区
roi_x, roi_y, roi_w, roi_h = 800, 300, 400, 400

roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
_, binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)

cv2.imwrite('spoon_binary.png', binary)
```

调整完写进 `powder_vision.yaml`：

```yaml
spoon:
  roi:
    x: 你的roi_x
    y: 你的roi_y
    width: 你的roi_w
    height: 你的roi_h
  gray_threshold: 你的阈值
  size_thresholds:
    large_px: 3000   # 大于这个面积的算大勺
    medium_px: 1000  # 大于这个面积的算中勺，再小的算小勺
```

### 怎么确定 size_thresholds

在 Python 里跑：

```python
contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for i, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    print(f'Contour {i}: area = {area:.0f} px²')
```

看输出结果，大勺、中勺、小勺的面积分别是多少，然后设 `large_px` 和 `medium_px` 门槛。

---

## 12. 标定电子秤读数

### 12.1 第一步：确定秤的 LCD 显示区域

```python
import cv2
import numpy as np

img = cv2.imread('data/calib/powder/scale_reading_01_0000_xxxxx_color.png')

# 用画图软件打开图片，找到 LCD 显示屏的位置
# 框出一个小矩形，只包含数字显示区域
roi_x, roi_y, roi_w, roi_h = 600, 200, 120, 60  # 调整这四个数

# 画个框确认一下
cv2.rectangle(img, (roi_x, roi_y), (roi_x+roi_w, roi_y+roi_h), (0, 255, 0), 2)
cv2.imwrite('scale_roi_check.png', img)
# 拷到桌面看看框对了没
```

### 12.2 第二步：测试读数提取

```python
roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

# 反色后二值化（黑字变白）
_, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

cv2.imwrite('scale_digits.png', binary)
# 拷到桌面看，数字应该清晰可见
```

### 12.3 第三步：用大量照片验证

用 `scale_reading_01` 到 `scale_reading_04` 的照片逐个测试，确保各种读数都能识别。记下最终参数，写入 `powder_vision.yaml`：

```yaml
scale:
  roi:
    x: 你的roi_x
    y: 你的roi_y
    width: 你的roi_w
    height: 你的roi_h
```

---

## 13. 在本地 WSL 上验证

所有参数标定完后，在 WSL 上编译测试：

```bash
# WSL Ubuntu-22.04 终端
cd ~/dexterous-hand-competition
source /opt/ros/humble/setup.bash
source install/setup.bash

# 编译
colcon build --symlink-install

# 跑所有测试
python3 -m pytest src/dexterous_hand_competition/test/ -v
```

确认全部通过。

---

## 14. 在机器人上做 dry-run 测试

Dry-run 的意思是"假装跑一遍"——节点正常运行，状态机正常流转，但机器人不真的动。这用来验证你的代码没有 bug。

### 14.1 拷贝更新后的代码到机器人

**Windows PowerShell** 里：

```powershell
scp -r E:\灵巧手机器人二次开发\dexterous-hand-competition\src nvidia@192.168.41.2:~/dexterous-hand-competition/
scp -r E:\灵巧手机器人二次开发\dexterous-hand-competition\config nvidia@192.168.41.2:~/dexterous-hand-competition/
```

或者更简单，SSH 到 Orin 后 git pull：

```bash
# SSH 到 Orin
ssh nvidia@192.168.41.2
cd ~/dexterous-hand-competition && git pull
source /opt/ros/humble/setup.bash && colcon build --symlink-install
```

### 14.2 启动 mock 系统（验证夹豆子）

在 Orin 上开一个终端，运行 mock 系统：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash
ros2 launch dexterous_hand_competition mock_system.launch.py
```

再开一个终端：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash

# 看场景数据
ros2 topic echo /bean_task/scene
```

检查输出里的字段：
- `source_center` 有值 ✓
- `target_center` 有值 ✓
- `tweezer_position` 有值 ✓
- `beans` 数组不为空 ✓

### 14.3 测试粉末场景

另开终端：

```bash
# 先启动 mock 粉末场景
ros2 run dexterous_hand_competition mock_powder_scene_node

# 另开终端看输出
ros2 topic echo /powder_task/scene
ros2 topic echo /powder_task/scale_reading
```

---

## 15. 在机器人上做实机视觉测试

这一步是**只开视觉节点，不动手臂**。验证视觉检测效果。

### 15.1 启动夹豆子视觉节点

SSH 到 Orin：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash
ros2 launch dexterous_hand_competition vision.launch.py
```

### 15.2 检查输出

另开 SSH 终端到 Orin：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash

# 看场景输出
ros2 topic echo /bean_task/scene

# 看调试图
ros2 topic hz /bean_task/debug_image
```

### 15.3 保存调试图

```bash
# 保存一张调试图回来看看
ros2 run image_tools save_image --ros-args -r image:=/bean_task/debug_image
```

把这个图拷回电脑看，确认检测框正确标注在黄豆/碗/镊子上。

### 15.4 启动粉末视觉节点

```bash
ros2 launch dexterous_hand_competition powder_vision.launch.py

# 另开终端看输出
ros2 topic echo /powder_task/scene
ros2 topic echo /powder_task/scale_reading
```

### 15.5 验证清单

| 检查项 | 怎么看 |
|--------|--------|
| 黄豆检测数量对不对 | 数画面里实际几颗豆，对比 scene.beans 长度 |
| 黄豆位置对不对 | 看 debug_image 的绿色圆圈在豆子中心 |
| 碗的位置对不对 | 对比 scene.source_center/target_center 和实际 |
| 镊子位置对不对 | 对比 scene.tweezer_position 和实际 |
| 勺子检测对不对 | 看 powder_scene 的 spoon 数量和位置 |
| 秤读数对不对 | 对比 scale_reading.value_grams 和秤上实际显示 |

---

## 16. 和队友联调

### 16.1 你给 C2 (集成/状态机) 提供什么

| 给什么 | 在哪 | C2 用它来做什么 |
|--------|-----|---------------|
| 黄豆信息 | `/bean_task/scene` | 选出最佳豆子，决定下一颗夹哪个 |
| 容器位置 | `/bean_task/scene` | 告诉 A 源碗和目标碗在哪 |
| 镊子位置 | `/bean_task/scene` | 告诉 C1 镊子在哪，自动抓取 |
| 视觉是否正常 | `/bean_task/vision_health` | 不正常时暂停任务 |
| 粉末容器位置 | `/powder_task/scene` | 告诉 A 粉体容器在哪 |
| 勺子位置 | `/powder_task/scene` | 告诉 C1 不同勺子在哪 |
| 秤读数 | `/powder_task/scale_reading` | 判断粉末量多还是少 |

### 16.2 你给 A (运动控制) 提供什么

A 需要知道目标物体在桌面上的 (x_m, y_m) 坐标。你的 Scene 消息里所有坐标都是桌面坐标（米），A 可以直接用。

联调验证方法：
1. 你把一颗豆的坐标报给 A
2. A 控制手臂移动到那个坐标上方
3. 大家看镊子尖端是否真的在豆子正上方
4. 偏差多少？把偏移量告诉你，你去调整单应矩阵

### 16.3 你给 C1 (灵巧手) 提供什么

- 镊子的位置和角度：`Scene.tweezer_position` + `Scene.tweezer_angle`
- 勺子的位置、角度、类型（大/中/小）：`PowderScene.spoon_*`

---

## 17. 常见问题排查

| 症状 | 可能原因 | 怎么修 |
|------|---------|--------|
| 检测不到黄豆 | HSV 范围不对 | 重新在采集的照片上调 HSV |
| 把碗边/阴影当成了豆 | min_area 太小或 morph_kernel 太小 | 增大 `vision.min_area_px` |
| 豆子位置总是偏同一个方向 | 单应矩阵不准 | 重标 4 个标记点 |
| 换光照后检测效果变差 | 单组 HSV 不够 | 需要多组 HSV（告诉我，我帮你加） |
| 镊子检测不到 | 阈值太高或太低 | 调 `gray_threshold` |
| 勺子大小分类不准 | size_thresholds 不对 | 用实际面积重新设门槛 |
| 秤读数不准 | LCD ROI 偏了 | 重新框 ROI |
| 秤读数一直不稳定 | 多帧去抖不够 | 增大 `powder_vision.yaml` 的 `scale.stable_frames` |
| vision_health 一直是 false | 相机掉线 | 检查 `ros2 topic hz /ob_camera_head/color/image_raw` |
| ros2 命令不存在 | 没加载环境 | 先执行 `source /opt/ros/humble/setup.bash` |

---

## 18. 附录：命令速查表

### SSH 和文件传输

```bash
# 登录 Orin
ssh nvidia@192.168.41.2

# 登录 x86
ssh ubuntu@192.168.41.1

# 从机器人拷文件到 Windows (在 PowerShell 里运行)
scp -r nvidia@192.168.41.2:~/dexterous-hand-competition/data E:\
```

### WSL 开发

```bash
# 加载 ROS2 环境（每次新开终端都要执行）
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash

# 编译
cd ~/dexterous-hand-competition && colcon build --symlink-install

# 跑测试
python3 -m pytest src/dexterous_hand_competition/test/ -v

# 更新代码
cd ~/dexterous-hand-competition && git pull
```

### 机器人上运行

```bash
# 夹豆子 — mock 模拟
ros2 launch dexterous_hand_competition mock_system.launch.py

# 夹豆子 — 视觉节点（Orin）
ros2 launch dexterous_hand_competition vision.launch.py

# 夹豆子 — 任务节点（x86）
ros2 launch dexterous_hand_competition bean_task.launch.py dry_run:=true

# 粉末称量 — 视觉节点（Orin）
ros2 launch dexterous_hand_competition powder_vision.launch.py

# 采集数据
python3 scripts/collect_data.py --task all --output data/calib
```

### 检查话题

```bash
# 列出所有话题
ros2 topic list

# 查看话题内容
ros2 topic echo /bean_task/scene
ros2 topic echo /powder_task/scene

# 查看话题频率（验证相机在线）
ros2 topic hz /ob_camera_head/color/image_raw
```
