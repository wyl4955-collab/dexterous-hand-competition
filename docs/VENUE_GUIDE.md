# 比赛场地操作手册

> 到了比赛场地不是慌慌张张开始，是按这份清单一步步来。

---

## 到达后 0-15min：拆箱组装

```
□ 灵巧手 ×1           ← 轻拿轻放，手指别撞到
□ 24V电源 ×1          ← 确认电压调到24V
□ USB转RS485模块 ×1   ← 别和别人的搞混
□ 精密电子天平 ×1      ← 用气泡水平仪调平
□ USB摄像头/D435i ×1   ← 固定在三脚架上
□ 镊子 ×2             ← 弯头不锈钢，一把备用
□ 药勺 ×2             ← 不锈钢，一把备用
□ 杜邦线母头若干
□ 电源插排、导线、扎带
```

---

## 到达后 15-30min：接线+上电

```
1. 灵巧手接线（断电接！）
   红粗→24V+  |  黑粗→24V-  |  黄→A+  |  绿→B-

2. USB模块插电脑
   天平串口插电脑

3. 相机装到三脚架上
   俯拍工作台，高度约40cm

4. 上电
   先开24V，摸灵巧手确认不热
   再开电脑确认所有USB设备识别
```

---

## 到达后 30-45min：软件自检

```bash
# 1. USB 透传（管理员 PowerShell）
usbipd list
usbipd bind --busid X
usbipd attach --wsl --busid X

# 2. WSL 确认
ls /dev/ttyUSB*
sudo chmod 666 /dev/ttyUSB0 /dev/ttyUSB1

# 3. 启动系统
source ~/dexterous-hand-competition/install/setup.bash
ros2 launch competition.launch.py

# 4. 另开终端自检
python3 tools/self_check.py
```

3个全绿 ✅ = 硬件OK。

---

## 到达后 45min-1.5h：现场标定（重要！）

**比赛场地和家里的温度、湿度、光照、桌子高度都不同，必须重新标定。**

### 标定1：力控（15min）

```bash
python3 tools/calibrate_force.py
```

用比赛现场提供的黄豆，按提示操作。30颗豆子就能确定最佳夹持力。

保存结果到 `config/calibration/force_<日期>.yaml`，更新 `config/default.yaml` 的 `bean_grasp_force`。

### 标定2：振动撒粉（15min）

```bash
python3 tools/calibrate_tap.py
```

用比赛现场提供的粉末，按提示操作。不同粉末颗粒大小影响落粉量，必须用现场的粉重新测。

保存结果到 `config/calibration/tap_<日期>.yaml`，更新 `powder_fsm.py` 的 `TAP_DROP` 字典。

### 标定3：相机（10min）

```bash
python3 tools/calibrate_camera.py
```

现场桌子的高度和相机的角度和家里不一样，像素→世界坐标必须重新标。

---

## 到达后 1.5h-2.5h：练习+调参

```bash
# 各做5轮练习
python3 tools/train_powder.py --rounds 5
python3 tools/train_bean.py --rounds 5

# 看数据
python3 tools/evaluate.py training/logs/

# 根据数据调整参数
# 重点: 力控值、振动 force_level 映射、夹豆速度
```

---

## 到达后 2.5h-3h：全流程模拟

```bash
# 连续跑3次完整比赛
python3 tools/match_sim.py --matches 3
```

3次都 > 150分 → 状态良好。否则继续调参。

---

## 赛前30min：最后检查

```
□ 所有线缆用扎带固定，防止比赛中松脱
□ 24V电源电压确认
□ 镊子和药勺放在灵巧手能抓到的位置
□ 天平归零，放好称量纸
□ 黄豆散放在工作台的固定区域
□ 相机镜头擦干净
□ 再次跑 tools/self_check.py
□ 关闭所有无关程序，只保留 WSL 和比赛系统
```

---

## 比赛中

```bash
# 一键执行
ros2 service call /competition/start std_srvs/srv/Trigger "{}"

# 如果出问题——不要慌，不要手动插手
# 紧急停止:
ros2 service call /competition/estop std_srvs/srv/Trigger "{}"

# 重新开始:
ros2 service call /competition/start std_srvs/srv/Trigger "{}"
```

---

## 如果出故障

| 现象 | 怎么办 |
|------|--------|
| 手不动 | 检查24V电源灯是否亮 → 检查USB透传是否还在 → `ros2 topic echo /hand/state` 看有没有数据 |
| 力传感器偏移 | 空载状态下跑力传感器校准（driver启动时会自动校准7秒） |
| 相机不行 | 检查 `/dev/video0` → 换USB口 → 重启WSL |
| 天平不读数 | 检查串口 → 换USB口 → 手动读（最后手段） |
| 灵巧手异常发热 | 立刻急停！断电检查 |
| 整个系统崩了 | `wsl --shutdown` → 重开WSL → 重跑 launch |

---

## 赛后

```
□ 先断电（24V 电源关闭）
□ 拆线（从灵巧手端拆，别拽线）
□ 灵巧手装箱（手指用软布包好）
□ 所有器材清点，不要遗漏
```
