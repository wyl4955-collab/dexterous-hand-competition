#!/usr/bin/env python3
"""
振动撒粉标定工具 —— 找到不同敲击力→落粉量的对应关系

使用方法:
  python3 tools/calibrate_tap.py

原理:
  灵巧手握药勺，舀约10g粉末放在天平上方
  用不同的力控等级各敲 10 次，用天平测落粉量
  计算单次落粉量
"""
import sys, time, json, os
from datetime import datetime

FORCE_LEVELS = [30, 50, 80, 120, 180, 250]
TAPS_PER_LEVEL = 10

def prompt_weight(step):
    """提示操作者读天平"""
    return float(input(f"  {step} 当前天平读数(g): ").strip())

def run_calibration():
    results = {}
    print("=" * 50)
    print(" 振动撒粉标定 — 力控→落粉量")
    print("=" * 50)
    print()
    print("准备: 灵巧手握药勺，舀一满勺粉末(约10g)")
    print("     药勺悬在天平称量纸正上方 3-5cm")
    print()

    for force in FORCE_LEVELS:
        print(f"\n{'='*40}")
        print(f"▶ 力控等级 = {force}")
        print(f"   请设力控阈值 {force}g，敲击 {TAPS_PER_LEVEL} 次")
        print(f"{'='*40}")

        before = prompt_weight("敲击前")
        input(f"   请执行 {TAPS_PER_LEVEL} 次敲击（力控={force}g），完成后按回车...")
        after = prompt_weight("敲击后")

        total_drop = after - before
        per_tap = total_drop / TAPS_PER_LEVEL
        results[force] = {'total_drop': round(total_drop, 4), 'per_tap': round(per_tap, 4)}
        print(f"   落粉: {total_drop:.4f}g / 单次: {per_tap:.4f}g")

    # 输出对照表
    print(f"\n{'='*50}")
    print("  ⭐ 振动→落粉量对照表")
    print(f"{'='*50}")
    print(f"  {'力控':>6} │ {'10次落粉':>8} │ {'单次落粉':>8}")
    print(f"  {'─'*6}─┼─{'─'*8}─┼─{'─'*8}")
    for force in FORCE_LEVELS:
        r = results[force]
        print(f"  {force:>5}g │ {r['total_drop']:>7.4f}g │ {r['per_tap']:>7.4f}g")

    # 生成代码片段
    print(f"\n{'='*50}")
    print(" 请将以下代码更新到 src/powder_weighing/powder_weighing/powder_fsm.py")
    print(f"{'='*50}")
    print("TAP_DROP = {")
    for force in FORCE_LEVELS:
        print(f"    {force}: {results[force]['per_tap']:.4f},")
    print("}")

    # 保存
    os.makedirs('config/calibration', exist_ok=True)
    path = f"config/calibration/tap_{datetime.now().strftime('%Y-%m-%d_%H%M')}.yaml"
    with open(path, 'w') as f:
        f.write(f"# 振动撒粉标定结果\n")
        f.write(f"# 日期: {datetime.now()}\n")
        f.write(f"# 粉末类型: ??\n\n")
        f.write(f"tap_force_to_drop:\n")
        for force, r in results.items():
            f.write(f"  {force}: {r['per_tap']}\n")
    print(f"\n标定结果已保存: {path}")

if __name__ == '__main__':
    run_calibration()
