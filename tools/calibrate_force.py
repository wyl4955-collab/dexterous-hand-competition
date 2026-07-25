#!/usr/bin/env python3
"""
力控参数标定工具 —— 找到黄豆的最佳夹持力

使用方法:
  python3 tools/calibrate_force.py

原理:
  用不同力控值（20/30/40/50/60/80g）各夹 5 颗黄豆
  记录夹起、夹碎、未夹起的数量
  找到成功率最高的力控值
"""
import sys, time, json, os
from datetime import datetime

# 测试的力控梯度
FORCE_LEVELS = [20, 30, 40, 50, 60, 80]
TESTS_PER_LEVEL = 5
SPEED = 150  # 闭合速度

FRAME = """import serial, time
HID=1; PORT='/dev/ttyUSB0'
def chk(d): return sum(d)&0xFF
def wf(addr, vals):
    d=bytearray()
    for v in vals: d.append(v&0xFF); d.append((v>>8)&0xFF)
    dl=len(d)+3; f=bytearray([0xEB,0x90,HID,dl,0x12,addr&0xFF,(addr>>8)&0xFF])
    f.extend(d); f.append(chk(f[2:])); return bytes(f)
ser=serial.Serial(PORT,115200,timeout=0.2)

# Release
ser.write(wf(0x410,[1740,1740,1740,1740,1550,1750]))
ser.write(wf(0x41C,[500]*6)); ser.write(wf(0x41C,[1500]*6))
time.sleep(0.5)

# Grip tweezers
ser.write(wf(0x41C,[100]*6)); ser.write(wf(0x41C,[300]*6))
ser.write(wf(0x41C,[1740,1740,1740,1250,1250,1200]))
time.sleep(0.8)

# Test pinch at each force level
"""

def run_calibration():
    results = {}
    print("=" * 50)
    print(" 力控参数标定 — 黄豆夹持力测试")
    print("=" * 50)
    print()
    print("准备: 30颗黄豆放在工作台上，灵巧手已握好镊子")
    print("每次测试后会暂停，由你观察豆子状态并输入结果")
    print()

    for force in FORCE_LEVELS:
        print(f"\n{'='*40}")
        print(f"▶ 测试力控 = {force}g")
        print(f"{'='*40}")
        success, broken, missed = 0, 0, 0

        for i in range(TESTS_PER_LEVEL):
            input(f"\n  第{i+1}/{TESTS_PER_LEVEL}颗: 放好黄豆，镊子对准，按回车...")

            # 这里由操作者手动操作或自动执行
            result = input(f"  结果? [y=成功 / b=夹碎 / n=未夹起]: ").strip().lower()
            if result == 'y':
                success += 1; print("    ✅")
            elif result == 'b':
                broken += 1; print("    💥 碎裂")
            else:
                missed += 1; print("    ❌ 未夹起")

        force_results = {
            'success': success, 'broken': broken, 'missed': missed,
            'rate': success / TESTS_PER_LEVEL
        }
        results[force] = force_results
        print(f"\n  {force}g: 成功{success} 夹碎{broken} 未夹起{missed} → 成功率{success/TESTS_PER_LEVEL*100:.0f}%")

    # 找最佳值
    best = max(results.items(), key=lambda x: x[1]['rate'])
    print(f"\n{'='*50}")
    print(f" 推荐力控值: {best[0]}g (成功率 {best[1]['rate']*100:.0f}%)")
    print(f"{'='*50}")

    # 保存
    os.makedirs('config/calibration', exist_ok=True)
    path = f"config/calibration/force_{datetime.now().strftime('%Y-%m-%d_%H%M')}.yaml"
    with open(path, 'w') as f:
        f.write(f"# 力控标定结果\n")
        f.write(f"# 日期: {datetime.now()}\n")
        f.write(f"# 黄豆类型: ??\n")
        f.write(f"# 镊子类型: 弯头不锈钢\n\n")
        f.write(f"bean_grasp_force: {best[0]}  # 夹取力(g)\n")
        f.write(f"bean_hold_force: {best[0]+15}   # 防滑力(g)\n")
        f.write(f"all_results:\n")
        for force, r in results.items():
            f.write(f"  {force}g: {{success: {r['success']}, broken: {r['broken']}, missed: {r['missed']}}}\n")
    print(f"\n标定结果已保存: {path}")
    print(f"请将 bean_grasp_force 值更新到 config/default.yaml")

if __name__ == '__main__':
    run_calibration()
