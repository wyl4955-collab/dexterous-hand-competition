# 成员 B 视觉模块——完整操作手册

**你负责：让机器人"看见"东西。**

这个手册覆盖两个比赛任务：
- **夹豆子**：检测黄豆、源碗、目标碗、镊子
- **粉末称量**：检测粉末容器、勺子（大/中/小）、电子秤读数

**手册假设**：你之前没有做过机器人项目。每一步都写清楚了在哪里运行、会看到什么、按什么键。如果有任何一步卡住了，直接告诉我。

---

## 目录

**出发前（现在就可以做）**
1. [去场地之前要带什么](#1-去场地之前要带什么)
2. [你能在哪里写命令：四个终端的区别](#2-你能在哪里写命令四个终端的区别)

**到场地后——连接机器人**
3. [如何把电脑连接到机器人](#3-如何把电脑连接到机器人)
4. [测试连接是否成功](#4-测试连接是否成功)
5. [如何登录机器人 (SSH)](#5-如何登录机器人-ssh)

**到场地后——确认机器人状态**
6. [确认代码在机器人上](#6-确认代码在机器人上)
7. [确认相机在工作](#7-确认相机在工作)

**到场地后——采集数据**
8. [采集标定照片](#8-采集标定照片)
9. [把数据拷回你的电脑](#9-把数据拷回你的电脑)

**回到酒店/家里——离线标定**
10. [标定黄豆颜色 (HSV)](#10-标定黄豆颜色-hsv)
11. [标定容器颜色 (HSV)](#11-标定容器颜色-hsv)
12. [标定桌面坐标 (单应矩阵)](#12-标定桌面坐标-单应矩阵)
13. [标定镊子检测参数](#13-标定镊子检测参数)
14. [标定勺子检测参数](#14-标定勺子检测参数)
15. [标定电子秤读数](#15-标定电子秤读数)

**回到场地——实机测试**
16. [把标定好的参数拷回机器人](#16-把标定好的参数拷回机器人)
17. [Dry-run 测试（机器人不动）](#17-dry-run-测试机器人不动)
18. [实机视觉测试（只开视觉，不动手）](#18-实机视觉测试只开视觉不动手)

**联调**
19. [和队友联调](#19-和队友联调)

**参考**
20. [常见问题排查](#20-常见问题排查)
21. [命令速查表](#21-命令速查表)

---

## 1. 去场地之前要带什么

### 你自己的东西

| 物品 | 数量 | 用途 | 没有怎么办 |
|------|------|------|-----------|
| 笔记本电脑 | 1 | 写代码、连机器人 | 没法工作 |
| 笔记本充电器 | 1 | 长时间在场地用 | |
| **网线** (以太网线/RJ45) | 1-2 根 | 连机器人 | 部分场地方提供，但**强烈建议自备** |
| **USB 转网口转接头** | 1 | 如果你的笔记本没有网线插口（现在大多数笔记本都没有），必须用转接头 | 京东/淘宝买一个，几十块钱。搜"USB 转 RJ45"或"Type-C 转网口" |
| 卷尺（1-2 米） | 1 | 测量桌上物品坐标 | 场地可能有，自备更靠谱 |
| 笔 + 纸 | 各 1 | 记录测量数据 | |
| 手机 | 1 | 拍桌面布局、应急沟通 | |
| 插排/插线板 | 1 | 场地插座可能不够 | |
| U盘 | 1（可选） | 如果网络不通就用 U 盘拷文件 | |

### 比赛道具（组委会/领队提供）

这些你不带，但进场后要向工作人员确认：

| 物品 | 夹豆子用 | 粉末称量用 |
|------|---------|-----------|
| 黄豆 | ✓ | |
| 源碗 | ✓ | |
| 目标碗 | ✓ | |
| 160mm 弯头医用镊子 | ✓ | |
| 粉末 | | ✓ |
| 粉末容器 | | ✓ |
| 电子秤 | | ✓ |
| 勺子（大、中、小） | | ✓ |

### 软件确认（出发前在酒店/家里做好）

**在 WSL Ubuntu-22.04 终端里**跑一遍，确认环境完好：

```bash
cd ~/dexterous-hand-competition
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon build --symlink-install
python3 -m pytest src/dexterous_hand_competition/test/ -v
```

应该看到 **38 passed**。如果不是 38，告诉我。

### 关键信息速查表（提前记住）

| 信息 | 值 |
|------|-----|
| 机器人 x86 主控 IP | `192.168.41.1` |
| 机器人 Orin 视觉主控 IP | `192.168.41.2` |
| 你要连的主控 | **Orin**（相机在上面） |
| x86 SSH 用户名 | `ubuntu` |
| Orin SSH 用户名 | `nvidia` |
| 连上机器人后你的代码在哪 | `~/dexterous-hand-competition/` |
| 彩色相机话题 | `/ob_camera_head/color/image_raw` |
| 深度相机话题 | `/ob_camera_head/depth/image_raw` |

---

## 2. 你能在哪里写命令：四个终端的区别

你操作过程中会在不同的"终端窗口"里输入命令。这 4 种**不是同一个东西**，打开的窗口不一样，用法不一样：

### ① Windows PowerShell（你的电脑）

- **标志**：提示符开头是 `PS C:\>` 或 `PS E:\>`
- **怎么打开**：`Win + R`，输入 `powershell`，回车
- **什么时候用**：git push、从机器人拷文件到电脑（scp）
- **什么时候不用**：不要在里面跑 ROS2 命令（ros2 在 WSL 里）

### ② WSL Ubuntu-22.04 终端（你的电脑里的 Linux）

- **标志**：提示符开头是 `lwy@DESKTOP:`（绿色文字）
- **怎么打开**：开始菜单搜索 "Ubuntu-22.04" 点击打开，或 PowerShell 里输入 `wsl`
- **什么时候用**：跑 Python、编译代码、测试、标定调参
- **什么时候不用**：不要在里面 SSH 连机器人，不要在里面跑机器人上的命令

### ③ SSH 到机器人 Orin（远程操作机器人）

- **标志**：提示符开头是 `nvidia@ubuntu:`
- **怎么打开**：在 **PowerShell** 里输入 `ssh nvidia@192.168.41.2`
- **什么时候用**：在机器人上检查相机、采集照片、启动视觉节点
- **前提**：**必须先连上机器人的网络**（网线或 WiFi），否则会 `Connection timed out`

### ④ SSH 到机器人 x86（远程操作机器人主控）

- **标志**：提示符开头是 `ubuntu@ubuntu:`
- **怎么打开**：在 **PowerShell** 里输入 `ssh ubuntu@192.168.41.1`
- **什么时候用**：在 x86 上启动任务状态机、安全监控
- **你（B）几乎不需要这个**——主要是 C2/D 用

### 我怎么知道现在在哪个终端里

看提示符开头：
- `PS E:\>` → 你在 PowerShell（Windows）
- `lwy@DESKTOP:` → 你在 WSL（本地 Linux）
- `nvidia@ubuntu:` → 你在机器人的 Orin 上
- `ubuntu@ubuntu:` → 你在机器人的 x86 上

---

## 3. 如何把电脑连接到机器人

到场地后，**不能直接 SSH**。机器人不是互联网上的服务器——它是一台插在你身边的物理设备。你必须先把自己的电脑连到机器人的内部网络上。

### 机器人的网络是怎么搭建的

天轶 Pro 2.0 内部有三块主控板（x86、导航 Orin、大模型 Orin），它们通过一个千兆交换机互相通信，构成了一个内网：

```
192.168.41.x 网段（机器人内网）
         │
    ┌────┴────┐
    │ 千兆交换机 │
    └────┬────┘
   ┌─────┼─────┐
  x86   Orin  Orin
 .41.1  .41.2 .41.x
```

你要做的就是把你的电脑也插进这个交换机，成为内网的一员。

### 方式 A：插网线（推荐，最稳定）

#### A1. 找到机器人背后的网口

机器人背后有一个**调试用以太网接口**。找现场工作人员帮你指出来。如果不确定是哪个口，请工作人员确认后再插。

#### A2. 把网线一头插进机器人调试网口

- 网线水晶头插进去听到"咔嗒"一声就是插好了
- 如果插不进去，转 180 度再试（水晶头有方向）

#### A3. 把网线另一头插进你的电脑

- **如果你的笔记本有网口**：直接插
- **如果你的笔记本没有网口**（MacBook、大部分轻薄本）：先插 USB 转网口转接头到电脑的 USB/Type-C 口，再把网线插进转接头

#### A4. 在你电脑上配置 IP 地址

这一步告诉你的电脑"你是 192.168.41.x 网段的人"。

**Windows 11 操作步骤**：

1. 按 `Win + R`，输入 `ncpa.cpl`，回车
2. 会打开"网络连接"窗口，显示你所有的网络适配器
3. 找到你的"以太网"适配器（图标下面写着网卡型号或者 USB 转接头型号）
4. 右键点击它 → **属性**
5. 在列表里双击 **"Internet 协议版本 4 (TCP/IPv4)"**
6. 选择 **"使用下面的 IP 地址"**
7. 填入：
   - **IP 地址**：`192.168.41.100`
   - **子网掩码**：`255.255.255.0`
   - **默认网关**：留空
   - **首选 DNS 服务器**：留空
8. 点击"确定" → "关闭"

**说明**：IP 地址最后一位（100）是你电脑在这个内网里的编号。只要不是 1（x86 在用）或 2（Orin 在用）就行，一般选 100。

#### A5. 验证连接

见第 4 节。

### 方式 B：连 WiFi（如果场地方配了 WiFi）

1. 问现场工作人员："机器人配了 WiFi 吗？SSID 和密码是什么？"
2. 在你的 Windows 电脑上：点击右下角 WiFi 图标 → 找到机器人 WiFi 的名字 → 连接 → 输入密码
3. 连接后，打开 PowerShell，输入 `ipconfig`
4. 找"无线局域网适配器 Wi-Fi"部分，看 IPv4 地址是不是 `192.168.41.xx`
   - **如果是 192.168.41.xx**：说明连对了
   - **如果不是**（比如是 192.168.1.xx 或其他）：说明连的 WiFi 不是机器人的，换个 WiFi 重连

### 方式 C：没有网线、没有 WiFi、没有转接头

这就是为什么出发前要带齐装备。如果到现场发现啥都没有：

1. 问场地方有没有备用网线和转接头
2. 问队友借
3. 用 U 盘拷文件：你的代码 → U 盘 → 插到机器人上（需要工作人员操作）。这是最慢的方式，尽量避免。

---

## 4. 测试连接是否成功

### 4.1 ping 测试

无论用的是网线还是 WiFi，配好网络后在 **Windows PowerShell** 里执行：

```powershell
ping 192.168.41.2
```

**正常输出**（连接成功）：
```
正在 Ping 192.168.41.2 具有 32 字节的数据:
来自 192.168.41.2 的回复: 字节=32 时间<1ms TTL=64
来自 192.168.41.2 的回复: 字节=32 时间<1ms TTL=64
```

**异常输出**（没连上）：
```
请求超时。
# 或
无法访问目标主机。
```

### 4.2 如果 ping 不通

按顺序排查：

1. 网线两端都插紧了吗？（拔出来重插，听到咔嗒声）
2. 你的 IP 配对了吗？（回到 A4 检查 IPv4 设置）
3. 机器人的网口找对了吗？（确认是调试网口，不是其他口）
4. 机器人开机了吗？（电源灯亮不亮？）
5. 换个网线试试（有可能网线坏了）

如果以上都确认没问题还是不通，找现场工作人员帮忙。

---

## 5. 如何登录机器人 (SSH)

ping 通之后才能做这一步。

### 5.1 第一次登录 Orin

在 **Windows PowerShell** 里执行：

```powershell
ssh nvidia@192.168.41.2
```

**注意**：这里用的是 `nvidia`（不是 `ubuntu`）。Orin 的用户名是 `nvidia`。

第一次登录会出现：

```
The authenticity of host '192.168.41.2' can't be established.
ED25519 key fingerprint is SHA256:xxxxxxxxxxxxx.
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

**输入 `yes`**（完整拼出来：y-e-s，然后回车）。**注意**：不能只输入 `y`，必须输入完整的 `yes`。

然后会提示输入密码：
```
nvidia@192.168.41.2's password:
```

**输入密码**（找队长或现场工作人员要）。输入密码时光标不会移动，看不到 `***`，这是正常的——Linux 的安全设计，防止别人看到你密码长度。输完按回车就行。

### 5.2 登录成功后

提示符会变成：
```
nvidia@ubuntu:~$
```

这意味着你已经登录到 Orin 了。你现在输入的所有命令都是在机器人 Orin 上执行的。

### 5.3 区分"在Orin上"和"在Orin这个文件夹里"

登录后你默认在 Orin 的 home 目录（`~` = `/home/nvidia`）。要确认：

```bash
whoami
```

输出 `nvidia` 就是在 Orin 上。

### 5.4 退出 SSH

```bash
exit
```

退回到 Windows PowerShell。

---

## 6. 确认代码在机器人上

### 6.1 检查代码是否存在

在 SSH 到 Orin 的终端里：

```bash
ls ~/dexterous-hand-competition/
```

**正常输出**：会显示 `README.md`、`src`、`scripts`、`docs` 等文件和文件夹。

**如果没有**（`No such file or directory`）——说明代码还没拷上去。在 Orin 的 SSH 终端里执行：

```bash
cd ~ && git clone https://github.com/wyl4955-collab/dexterous-hand-competition.git
```

### 6.2 更新到最新版本

如果代码已经有了，拉取最新：

```bash
cd ~/dexterous-hand-competition && git pull
```

### 6.3 构建（编译）代码

每次拉完新代码后都要重新构建：

```bash
cd ~/dexterous-hand-competition
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

**必须看到**：
```
Summary: 2 packages finished
```

如果有 `FAILED` 或红色的报错，**截图告诉我**。

### 6.4 验证构建成功

```bash
source install/setup.bash
ros2 pkg list | grep competition
```

应该输出：
```
competition_interfaces
dexterous_hand_competition
```

---

## 7. 确认相机在工作

在 SSH 到 Orin 的终端里执行。

### 7.1 检查相机话题是否存在

```bash
source /opt/ros/humble/setup.bash
ros2 topic list | grep ob_camera_head
```

**正常输出**：
```
/ob_camera_head/color/image_raw
/ob_camera_head/depth/image_raw
/ob_camera_head/color/camera_info
/ob_camera_head/depth/camera_info
/ob_camera_head/depth_to_color
```

### 7.2 检查话题是否有数据在发

```bash
ros2 topic hz /ob_camera_head/color/image_raw
```

**正常输出**：
```
average rate: 29.XXX
    min: 0.XXXs max: 0.XXXs std dev: 0.XXXs window: XXX
```
数字在持续跳动说明相机正常工作。按 `Ctrl+C` 停止。

### 7.3 如果话题不存在——启动相机驱动

```bash
sudo systemctl start orbbec_head.service
```

再等几秒钟，然后回到 7.1 检查一次。

### 7.4 如果启动失败

相机驱动可能被 `proc_manager` 管理了。找现场工作人员问：

> "请问 Orin 上奥比中光相机驱动怎么启动？`orbbec_head.service` 不响应。"

---

## 8. 采集标定照片

这是 B 角色**最重要的一步**。一次采集好，后续标定都靠这些照片。采集需要 1-2 小时，注意安排时间。

### 8.1 准备工作

#### 8.1.1 先确认机器人头部姿态

让 A（运动控制负责人）把机器人头部调整到 `look_table` 姿态——头部俯视桌面。

**采集期间头部绝对不能动**。脑袋一歪，你的标定就全废了。

#### 8.1.2 确认桌面物品摆放

和全队一起确定桌面布局：碗放在哪、镊子放哪、秤放哪。确定后标记位置，后面每次摆都要一致。

### 8.2 启动采集脚本

在 SSH 到 Orin 的终端里：

```bash
cd ~/dexterous-hand-competition
source install/setup.bash

# 夹豆子任务 — 16 个场景
python3 scripts/collect_data.py --task bean --output data/calib

# 或者粉末称量任务 — 21 个场景
python3 scripts/collect_data.py --task powder --output data/calib

# 或者两个任务一起（36+ 场景，约 1.5-2 小时）
python3 scripts/collect_data.py --task all --output data/calib
```

### 8.3 脚本怎么用

脚本启动后会：

1. **先打印一个清单**，列出所有要拍的场景
2. **然后进入第一个场景**，显示：
   ```
   [SCENE 1/16] beans_1
     → Source bowl with exactly 1 soybean. Place it near the centre.
     → Arrange the table, then press ENTER to snap (s=skip, q=quit)
   ```
3. 你**走到机器人旁边**，按提示摆好东西
4. **回到电脑前**，按 `Enter` 拍照
5. 同一个场景按多次 `Enter` 可以拍多张（建议每个场景拍 2-3 张）
6. 拍够了按 `s` + `Enter` 跳到下一个场景
7. 全部拍完或中途要退出，按 `q` + `Enter`

**注意**：脚本在 Orin 的终端里运行，你摆东西时要走到机器人旁边——机器人就在你场地里，不是远程的。你在终端里按回车时是坐在电脑前，你摆东西时是站在机器人前面。这是两个人正常的协作流程（如果有队友帮忙摆就更方便）。

### 8.4 夹豆子任务（bean）场景清单——16 个

| # | 场景名 | 桌子怎么摆 | 为什么要拍 | 每场景拍几张 |
|---|--------|-----------|-----------|------------|
| 1 | `calib_markers` | 在桌上放 4 个标记物（硬币、棋子），位置分散在桌面四角。**用卷尺量每个标记物的真实桌面坐标 (x_m, y_m)，记在纸上** | 标定像素→桌面坐标 | 3 |
| 2 | `empty_both` | 源碗 + 目标碗，空碗。不撒豆，不放镊子 | 碗位置基准 | 2 |
| 3 | `empty_source` | 只要源碗。不理目标碗 | 豆子背景参考 | 2 |
| 4 | `beans_1` | 源碗里放 1 颗黄豆，位置靠近碗中央 | 单颗豆检测 | 3 |
| 5 | `beans_5` | 源碗里放 5 颗黄豆，散开，不要挤一起 | 标准检测场景 | 3 |
| 6 | `beans_10` | 源碗里放 10 颗黄豆 | 密集场景 | 3 |
| 7 | `beans_20` | 源碗里放 20 颗黄豆，部分互相挨着 | 极限密集测试 | 3 |
| 8 | `beans_edge` | 5 颗豆，**至少 2 颗故意贴在碗内壁边缘** | 测试边缘豆过滤 | 3 |
| 9 | `beans_clumped` | 10 颗豆，**故意让 2-3 颗粘在一起** | 测试粘连豆分离 | 3 |
| 10 | `tweezers_alone` | **只在镊子放置区放镊子**。拿走所有碗和豆 | 镊子检测基线 | 3 |
| 11 | `tweezers_full` | 完整比赛布局：源碗+目标碗+镊子在放置区+10 颗豆在源碗 | 完整场景 | 3 |
| 12 | `light_bright` | 完整布局，**加一盏灯照桌面**（或开窗帘） | 亮光下效果 | 2 |
| 13 | `light_dim` | 完整布局，**关灯或拉窗帘**（模拟最暗环境） | 暗光下效果 | 2 |
| 14 | `alt_bowls` | 如果有备用碗（不同颜色的），换上去。没有就按 `s` 跳过 | 碗颜色适配 | 2 |

### 8.5 粉末称量任务（powder）场景清单——21 个

| # | 场景名 | 桌子怎么摆 | 为什么要拍 | 每场景拍几张 |
|---|--------|-----------|-----------|------------|
| 1 | `calib_markers` | 4 个标记点（可以和 bean 共用同一组） | 标定像素→桌面坐标 | 3 |
| 2 | `empty_all` | 全部清空，空桌一张 | 背景参考 | 2 |
| 3 | `powder_container_empty` | 粉末容器空着，放在左侧 | 空容器检测 | 2 |
| 4 | `powder_container_full` | 粉末容器装**满**粉末 | 满容器检测 | 2 |
| 5 | `powder_container_half` | 粉末容器装**一半**粉末 | 半满容器检测 | 2 |
| 6 | `spoons_all` | **全部勺子**（大中小）散开放在右侧勺子区。不要叠在一起 | 多勺同时检测 | 3 |
| 7 | `spoons_large_only` | **只放大勺子**在勺子区 | 大勺大小分类校准 | 2 |
| 8 | `spoons_medium_only` | **只放中勺子** | 中勺大小分类校准 | 2 |
| 9 | `spoons_small_only` | **只放小勺子** | 小勺大小分类校准 | 2 |
| 10 | `spoons_overlapping` | 勺子**故意部分重叠**放置 | 最坏场景 | 2 |
| 11 | `scale_powered_off` | 秤放中间，**不开机** | 秤盘位置检测 | 2 |
| 12 | `scale_zero` | 秤**开机**，显示 **0.0 g**（秤上空无一物） | 数字识别基准 | 2 |
| 13 | `scale_reading_01` | 秤上放一个小物件，让秤显示 **10-15 克**（随便放个小东西） | 两位数识别 | 3 |
| 14 | `scale_reading_02` | 换一个重物，让秤显示 **30-40 克** | 两位数识别 | 3 |
| 15 | `scale_reading_03` | 再换一个，让秤显示 **50-60 克** | 两位数识别 | 3 |
| 16 | `scale_reading_04` | 让秤显示**带小数的值**（如 12.3 克、47.8 克）。放不规则重量物体 | 小数点识别 | 3 |
| 17 | `powder_full_01` | **完整比赛布局**：粉末容器（左） + 秤（中，显示约 25g）+ 全部勺子（右） | 完整场景 | 3 |
| 18 | `powder_full_02` | 完整布局，但**秤上换一个不同的重量**（约 50g） | 完整场景 | 2 |
| 19 | `light_bright` | 完整布局，加灯/开窗帘 | 亮光对比 | 2 |
| 20 | `light_dim` | 完整布局，关灯/拉窗帘 | 暗光对比 | 2 |
| 21 | `alt_containers` | 如果有不同颜色的备用容器，换上去。没有按 `s` 跳过 | 容器适配 | 1 |

### 8.6 采集时的注意事项

- **头部姿态绝对固定**：这不是玩笑。头一动，所有标定参数作废。拍之前看一眼头部关节是否还在原位
- **碗和秤不要随便挪**：每次摆好后和第一次时位置保持一致
- **每个场景多拍几张**：宁可多拍不少拍。硬盘空间有的是
- **`calib_markers` 场景**：4 个标记点的真实坐标一定要用卷尺量准确，记在纸上。这是后续所有坐标标定的基础
- **纸上的记录拍照做备份**：怕弄丢纸的话，测完坐标后用手机拍一张

---

## 9. 把数据拷回你的电脑

### 9.1 确认采集了多少数据

在 SSH 到 Orin 的终端里：

```bash
find ~/dexterous-hand-competition/data/calib -name "*.png" | wc -l
```

看输出数字。bean 任务 16 个场景应该产 40+ 张，powder 任务 21 个场景应该产 50+ 张。

### 9.2 从 Orin 拷到你电脑

**在 Windows PowerShell** 里（不是 WSL，不是 SSH）：

```powershell
scp -r nvidia@192.168.41.2:~/dexterous-hand-competition/data/calib E:\灵巧手机器人二次开发\dexterous-hand-competition\data\
```

按提示输入 Orin 密码。等待传输完成。

### 9.3 如果 scp 报错或太慢

用 U 盘：让工作人员把 Orin 上的数据拷到 U 盘，你再从 U 盘拷回电脑。

### 9.4 拷进 WSL 方便后续操作

在 **WSL Ubuntu-22.04 终端**里：

先确认 E 盘已挂载：
```bash
ls /mnt/e/灵巧手机器人二次开发/dexterous-hand-competition/data/calib/
```

如果有文件就拷过来：
```bash
cp -r /mnt/e/灵巧手机器人二次开发/dexterous-hand-competition/data/calib ~/dexterous-hand-competition/data/
```

---

## 10. 标定黄豆颜色 (HSV)

你的目标：找到一个 HSV 颜色范围，让计算机能准确区分"这是黄豆"和"这不是黄豆"。

这个工作在 WSL 上做，不需要连接机器人。

### 10.1 什么是 HSV

一张彩色图片由三个通道组成。RGB（红绿蓝）是常见的表示方式，但做颜色分割时 HSV 更好用：

- **H (Hue/色调)**：到底是什么颜色。红色≈0、黄色≈20-40、绿色≈60-80、蓝色≈100-120
- **S (Saturation/饱和度)**：颜色有多纯。0=灰色，255=纯色
- **V (Value/明度)**：有多亮。0=黑，255=最亮

黄豆是黄色的，所以 H 在 15-45 之间。

### 10.2 打开一张豆子照片

在 **WSL Ubuntu-22.04 终端**里：

```bash
cd ~/dexterous-hand-competition
python3
```

进入 Python 交互模式（提示符变成 `>>>`），逐行输入以下代码：

```python
import cv2
import numpy as np

# 换成你实际的文件名：ls data/calib/bean/ 看一下有哪些文件
img = cv2.imread('data/calib/bean/beans_5_0000_XXXXXX_color.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 试一个初始范围
lower = np.array([15, 60, 50])
upper = np.array([45, 255, 255])

mask = cv2.inRange(hsv, lower, upper)
cv2.imwrite('mask_test.png', mask)
print('Saved mask_test.png')
```

### 10.3 看 mask 效果

在 WSL 里把 mask 图拷到 Windows 桌面：

```bash
cp ~/dexterous-hand-competition/mask_test.png /mnt/c/Users/刘文毅/Desktop/
```

然后在 Windows 桌面上双击 `mask_test.png` 打开。

看这张图：
- **白色像素** = 程序认为"这是黄豆"
- **黑色像素** = 程序认为"不是黄豆"

### 10.4 反复调整参数

回到 Python（`>>>` 提示符），改成新的 lower/upper 值，再生成 mask 看效果：

```python
# 如果豆子没被全部标白（漏检） → 扩大范围：lower 的 H 再小一点，upper 的 H 再大一点
# 如果碗边或桌面也被标白了（误检） → 缩小范围或提高 S/V 下限

# 试这个：
lower = np.array([10, 40, 30])
upper = np.array([50, 255, 255])
mask = cv2.inRange(hsv, lower, upper)
cv2.imwrite('mask_test.png', mask)
```

调好后写回 YAML。

### 10.5 用多张照片交叉验证

调完一组参数后，读另一张不同光照的照片验证：

```python
img2 = cv2.imread('data/calib/bean/light_dim_0000_XXXXXX_color.png')
hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
mask2 = cv2.inRange(hsv2, lower, upper)
cv2.imwrite('mask_test2.png', mask2)
```

→ 拷到桌面看效果。亮光和暗光照片都应该好用。

### 10.6 写入配置文件

找到最终的 lower/upper，打开 `config/vision.yaml`，修改：

```yaml
vision:
  hsv_lower: [你的H, 你的S, 你的V]   # 例如 [12, 50, 40]
  hsv_upper: [你的H, 你的S, 你的V]   # 例如 [48, 255, 255]
```

---

## 11. 标定容器颜色 (HSV)

方法**和黄豆完全一样**，只是找的是碗的颜色而不是豆的颜色。

### 11.1 标定源碗

```python
img = cv2.imread('data/calib/bean/empty_source_0000_XXXXXX_color.png')
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 假设源碗是白色的：H 不限，S 低（白的，不鲜艳），V 高（亮的）
lower = np.array([0, 0, 30])
upper = np.array([180, 60, 255])

mask = cv2.inRange(hsv, lower, upper)
cv2.imwrite('bowl_source_mask.png', mask)
```

拷到桌面看效果。调好后写入 `config/vision.yaml`：

```yaml
container:
  source:
    hsv_lower: [你的H, 你的S, 你的V]
    hsv_upper: [你的H, 你的S, 你的V]
```

### 11.2 标定目标碗

同样步骤读 `empty_both` 的照片，找目标碗的颜色，写入 `vision.yaml`：

```yaml
container:
  target:
    hsv_lower: [你的H, 你的S, 你的V]
    hsv_upper: [你的H, 你的S, 你的V]
```

### 11.3 标定粉末容器

读粉末容器的照片，同样方法，写入 `config/powder_vision.yaml`：

```yaml
powder_container:
  hsv_lower: [你的H, 你的S, 你的V]
  hsv_upper: [你的H, 你的S, 你的V]
```

---

## 12. 标定桌面坐标 (单应矩阵)

这是整个 B 角色**最关键的一步**——让程序知道"画面里的像素"对应"桌上真实的多少米"。

### 12.1 白话原理

相机拍到的照片是 2D 的（像素 u, v）。桌面也是 2D 的（坐标 x_m, y_m，单位米）。两张"平面"之间有一个**映射关系**——就像一个函数 f：(u, v) → (x_m, y_m)。

OpenCV 的 `findHomography` 函数能用 **4 个对应的点**算出这个映射关系——就像你知道地图上 4 座城市的经纬度，就可以画出整个地图。

### 12.2 第一步：回顾 calib_markers 照片上的 4 个点

你在采集时放了 4 个标记物（硬币、棋子），并且用卷尺量了它们的桌面坐标，记在了纸上。

拿出那张纸，确认 4 个坐标还在。纸丢了？重新去桌面上放 4 个点、重测、重拍。

### 12.3 第二步：在照片里找到这 4 个点的像素坐标

在 Windows 上用**画图**软件打开 `calib_markers` 照片：
1. 双击打开 PNG 文件 → 系统画图软件会打开
2. 鼠标移动到第 1 个标记物的中心
3. 看窗口左下角显示的坐标，例如 `(280, 220)`。记下来
4. 对第 2、3、4 个标记物重复

### 12.4 第三步：计算单应矩阵

在 **WSL 终端**里启动 Python：

```python
import cv2
import numpy as np

# ========== 这 8 行改成你实际测量的数据 ==========
# 4 个点的像素坐标（从画图软件里读出来的）
image_points = np.array([
    [280, 220],   # 点 1 的 (u, v)
    [920, 230],   # 点 2 的 (u, v)
    [260, 520],   # 点 3 的 (u, v)
    [940, 510],   # 点 4 的 (u, v)
], dtype=np.float32)

# 4 个点的桌面坐标（你卷尺量的，单位 米）
table_points = np.array([
    [0.30, -0.25],   # 点 1 的 (x_m, y_m)
    [0.50, -0.25],   # 点 2 的 (x_m, y_m)
    [0.30, -0.05],   # 点 3 的 (x_m, y_m)
    [0.50, -0.05],   # 点 4 的 (x_m, y_m)
], dtype=np.float32)
# ================================================

# 算矩阵（OpenCV 全自动）
H, status = cv2.findHomography(image_points, table_points)
print('单应矩阵 H =')
print(H)
```

运行后输出一个 3×3 矩阵，这就是你的"像素→桌面坐标"转换器。

### 12.5 第四步：验证误差

随便找一颗豆，把它的像素坐标用 H 转成桌面坐标，拿卷尺实测那颗豆的实际位置，对比：

```python
# 假设画面里某颗豆的像素坐标（从画图软件读）
u, v = 500, 350

pixel = np.array([u, v, 1.0])
table = H @ pixel
x_m = table[0] / table[2]
y_m = table[1] / table[2]
print(f'Bean pixel ({u}, {v}) → table ({x_m:.3f}m, {y_m:.3f}m)')
```

然后拿卷尺量那颗豆的实际桌面坐标。**误差必须 < 5mm（0.005m）**。

如果超过 5mm：
- 标记点的测量数据不对（重测）
- 标记点不在桌面上（翘起来了）
- 4 个点太集中（分布开来）

### 12.6 第五步：写入配置文件

把 H 矩阵的 3 行 3 列分别填入 `config/vision.yaml` 和 `config/powder_vision.yaml`：

```yaml
calibration:
  calibrated: true    # 改成 true！
  homography:
    - [H00, H01, H02]    # 第一行的三个数
    - [H10, H11, H12]    # 第二行的三个数
    - [H20, H21, H22]    # 第三行的三个数
```

**注意**：两个 YAML 都要填。`vision.yaml` 是夹豆子用的，`powder_vision.yaml` 是粉末称量用的。如果桌面和设备位置相同，可以填同一个 H。

---

## 13. 标定镊子检测参数

镊子是不锈钢的，在灰阶图里很亮。打开有镊子的照片调二值化阈值。

```python
import cv2
import numpy as np

img = cv2.imread('data/calib/bean/tweezers_alone_0000_XXXXXX_color.png')

# 用画图软件打开同一张照片，找到镊子在画面中的区域
roi_x, roi_y = 500, 350    # 改成实际的（画图左下角看鼠标坐标）
roi_w, roi_h = 300, 370    # 改成实际的

roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

# 试不同阈值。阈值越高越严格（只有最亮的才保留）
_, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
cv2.imwrite('tweezer_binary.png', binary)
```

拷到桌面看。镊子变白、桌面变黑 = 调好了。写入 `vision.yaml`：

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

## 14. 标定勺子检测参数

和镊子完全一样的流程，读 `spoons_all` 照片，调阈值：

```python
img = cv2.imread('data/calib/powder/spoons_all_0000_XXXXXX_color.png')
roi_x, roi_y, roi_w, roi_h = 800, 300, 400, 400   # 改成实际的
roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
_, binary = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
cv2.imwrite('spoon_binary.png', binary)
```

调好写 `powder_vision.yaml`。**额外步骤**——确定大小勺门槛：

```python
contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for i, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    print(f'Contour {i}: area = {area:.0f} px²')
```

看大勺、中勺、小勺的面积分别大约是多少，设门槛：

```yaml
spoon:
  size_thresholds:
    large_px: 3000    # 大于这个 = 大勺
    medium_px: 1000   # 大于这个但不大于 large = 中勺，小于 = 小勺
```

---

## 15. 标定电子秤读数

### 15.1 确定秤显示区域 (ROI)

用画图软件打开 `scale_reading_01` 照片，鼠标移到 LCD 屏幕左上角，记下像素坐标。框出显示数字的矩形区域。

```python
img = cv2.imread('data/calib/powder/scale_reading_01_0000_XXXXXX_color.png')
roi_x, roi_y, roi_w, roi_h = 600, 200, 120, 60   # 改成实际的

# 画框确认
cv2.rectangle(img, (roi_x, roi_y), (roi_x+roi_w, roi_y+roi_h), (0,255,0), 2)
cv2.imwrite('scale_roi_check.png', img)
```

拷到桌面确认框刚好包住数字区域。

### 15.2 测试二值化效果

```python
roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

# 反色（白底黑字 → 黑底白字）后大津二值化
_, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
cv2.imwrite('scale_digits.png', binary)
```

拷到桌面看，数字应该清晰可见（白色数字、黑色背景）。

### 15.3 用所有读数照片验证

用 `scale_reading_01` 到 `04` 的照片逐个测试，确每种读数都能识别。然后写入 `powder_vision.yaml`。

---

## 16. 把标定好的参数拷回机器人

所有标定做完后，把更新过的配置文件推上 GitHub，然后在机器人上拉取。

### 16.1 Windws 端 push

**在 Windows PowerShell** 里：

```powershell
cd E:\灵巧手机器人二次开发\dexterous-hand-competition
git add -A
git commit -m "calibrate: update vision parameters for field"
git push origin master
```

### 16.2 机器人端 pull + 重新构建

**在 SSH 到 Orin 的终端**里：

```bash
cd ~/dexterous-hand-competition && git pull
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

看到 `Summary: 2 packages finished` 即可。

**注意**：如果 git 报网络错误（Orin 可能没有外网），改用 scp 手动拷文件：

在 **Windows PowerShell** 里：
```powershell
scp E:\灵巧手机器人二次开发\dexterous-hand-competition\src\dexterous_hand_competition\config\vision.yaml nvidia@192.168.41.2:~/dexterous-hand-competition/src/dexterous_hand_competition/config/
scp E:\灵巧手机器人二次开发\dexterous-hand-competition\src\dexterous_hand_competition\config\powder_vision.yaml nvidia@192.168.41.2:~/dexterous-hand-competition/src/dexterous_hand_competition/config/
```

---

## 17. Dry-run 测试（机器人不动）

Dry-run 的意思是"假装跑一遍"——节点全部运行、状态机正常流转，但手臂和手部不真的动。验证你的视觉模块没有 bug。

### 17.1 启动 mock 夹豆子系统

**在 SSH 到 Orin 的终端**里：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash
ros2 launch dexterous_hand_competition mock_system.launch.py
```

会启动 3 个节点：safety_monitor + mock_scene_node + bean_task_node。

**再开一个 SSH 窗口到 Orin**（开新的 PowerShell 窗口，重新 `ssh nvidia@192.168.41.2`），在该窗口中：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash

# 看场景数据
ros2 topic echo /bean_task/scene
```

检查字段都有值。按 `Ctrl+C` 停止。

### 17.2 测试粉末场景 mock

```bash
# 先启动 mock 粉末场景（你会看到它不断输出 mock 数据）
ros2 run dexterous_hand_competition mock_powder_scene_node
```

另开 SSH 终端看输出：
```bash
ros2 topic echo /powder_task/scene
ros2 topic echo /powder_task/scale_reading
```

---

## 18. 实机视觉测试（只开视觉，不动手）

这一步是**用真实相机图像跑你的视觉模块**，但手臂不动。这验证你的 HSV、单应矩阵、ROI 在真实场景里效果如何。

### 18.1 夹豆子——启动真实视觉节点

**在 SSH 到 Orin 的终端**里：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash
ros2 launch dexterous_hand_competition vision.launch.py
```

你会看到 `Listening on /ob_camera_head/color/image_raw`。

### 18.2 检查输出

再开一个 SSH 终端到 Orin：

```bash
source /opt/ros/humble/setup.bash
source ~/dexterous-hand-competition/install/setup.bash

# 看场景数据
ros2 topic echo /bean_task/scene

# 看调试图的频率（确认在发）
ros2 topic hz /bean_task/debug_image
```

### 18.3 保存调试图拷回来看

```bash
ros2 run image_tools save_image --ros-args -r image:=/bean_task/debug_image
```

然后拷回 Windows：
```powershell
scp nvidia@192.168.41.2:~/save_image_*.png E:\
```

打开看检测框是否正确标注在黄豆/碗/镊子上。

### 18.4 粉末称量——启动真实视觉节点

```bash
ros2 launch dexterous_hand_competition powder_vision.launch.py
```

检查 `ros2 topic echo /powder_task/scale_reading`，看读数是否和秤的实际显示一致。

---

## 19. 和队友联调

### 你给别人什么

| 你给 | 在哪个话题 | 接收方 | 用来做什么 |
|------|-----------|--------|-----------|
| 黄豆列表（排好序） | `/bean_task/scene` | C2 | 选最佳豆子，调用 A 去夹 |
| 源碗桌面坐标 | `/bean_task/scene` | A, C2 | 手臂往哪里移动 |
| 目标碗桌面坐标 | `/bean_task/scene` | A, C2 | 投放豆子的位置 |
| 镊子位置+角度 | `/bean_task/scene` | C1 | 自动抓镊子 |
| 视觉健康 | `/bean_task/vision_health` | C2 | false 时暂停任务 |
| 粉体容器坐标 | `/powder_task/scene` | A, C2 | 手臂往哪里舀粉 |
| 勺子列表（大中小+坐标） | `/powder_task/scene` | C1 | 选对应勺子去抓 |
| 秤读数 | `/powder_task/scale_reading` | C2 | 判断舀多了还是少了 |

### 和 A 联调验证坐标精度

1. 视觉节点输出一颗豆的桌面坐标 (x_m, y_m)
2. A 控制手臂悬停到那个坐标上方
3. 全队看镊子尖端是否真的在豆子正上方
4. 偏低/偏左多少？拿卷尺量偏移，反馈给你调整单应矩阵

### 和 C1 联调验证镊子/勺子检测

1. 视觉输出镊子的位置和角度
2. C1 据此让手臂去抓镊子
3. 观察是否对准了。偏了告诉你，你调参数

---

## 20. 常见问题排查

| 症状 | 可能原因 | 怎么修 |
|------|---------|--------|
| `ssh: Connection timed out` | 没连上机器人网络 | 检查网线、IP设置、ping测试 |
| `ssh: No route to host` | IP 不在同一网段 | 检查 IP 配置，确认是 192.168.41.x |
| ping 不通 | 物理连接问题 | 重新插拔网线、换网线、换转接头 |
| 相机话题不存在 | 相机驱动没启动 | `sudo systemctl start orbbec_head.service` |
| 检测不到黄豆 | HSV 没针对现场灯光调 | 重新采集照片、重新调 HSV |
| 碗边/阴影被当成豆 | 形态学参数太松 | 增大 `vision.min_area_px`，调 morph_kernel |
| 豆坐标总是往同一个方向偏 | 单应矩阵不准 | 重标定 4 个标记点 |
| 暗光下大量漏检 | 单组 HSV 不够 | 暗光环境需另一组 HSV（告诉我，我帮你加） |
| 镊子检测不到 | 灰度阈值不对 | 调 `tweezer.gray_threshold` |
| 勺子大小分不对 | size_thresholds 不匹配 | 用所有勺子照片重新统计面积门槛 |
| 秤读数一直不准 | LCD ROI 偏了 | 重新框 ROI |
| 秤读数跳动 | 多帧去抖不够 | 增大 `powder_vision.yaml` 的 `scale.stable_frames` |
| vision_health 一直 false | 相机掉线或图像断流 | `ros2 topic hz /ob_camera_head/color/image_raw` 检查 |
| `ros2: command not found` | 没加载环境 | 先 `source /opt/ros/humble/setup.bash` |
| colcon build 报错 | 代码冲突或依赖问题 | 截图告诉我，帮你修 |
| git push 报 `SEC_E_INVALID_TOKEN` | GitHub 登录过期 | 在浏览器里重新登录 GitHub，然后重试 push |

---

## 21. 命令速查表

### 在哪运行什么——一句话版

| 我想做什么 | 在哪个终端 | 命令 |
|-----------|-----------|------|
| 进 WSL 开发 | WSL Ubuntu-22.04 | （双击图标打开） |
| 编译代码 | WSL | `cd ~/dexterous-hand-competition && source /opt/ros/humble/setup.bash && colcon build` |
| 跑测试 | WSL | `python3 -m pytest src/dexterous-hand-competition/test/ -v` |
| 测试网通不通 | PowerShell | `ping 192.168.41.2` |
| 登录 Orin | PowerShell | `ssh nvidia@192.168.41.2` |
| 登录 x86 | PowerShell | `ssh ubuntu@192.168.41.1` |
| 从机器人拷文件到电脑 | PowerShell | `scp -r nvidia@192.168.41.2:~/路径 E:\目标路径` |
| 推代码到 GitHub | PowerShell | `cd E:\...\dexterous-hand-competition` 然后 `git push origin master` |
| 拉最新代码 | SSH→Orin | `cd ~/dexterous-hand-competition && git pull` |
| 看相机话题有没有数据 | SSH→Orin | `ros2 topic hz /ob_camera_head/color/image_raw` |
| 启动视觉节点（豆子） | SSH→Orin | `ros2 launch dexterous_hand_competition vision.launch.py` |
| 启动视觉节点（粉末） | SSH→Orin | `ros2 launch dexterous_hand_competition powder_vision.launch.py` |
| 采集标定照片 | SSH→Orin | `python3 scripts/collect_data.py --task all --output data/calib` |
| 查看话题输出 | SSH→Orin | `ros2 topic echo /bean_task/scene` |
