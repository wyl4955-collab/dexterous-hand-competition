#!/usr/bin/env python3
"""
全流程比赛模拟 —— 连续跑N次完整比赛（称量+夹豆），模拟真实比赛

使用方法:
  python3 tools/match_sim.py --matches 20

每一次完整比赛:
  1. 力传感器校准（7秒）
  2. 粉末称量（随机目标4-6g, ±0.05g, 120秒限时）
  3. 镊子夹豆（3颗, 120秒限时）
  4. 计分: 称量100分 + 夹豆100分 = 满分200
  5. 输出成绩单
"""
import sys, time, json, os, random, argparse
from datetime import datetime

def run_match(match_id, target_weight=None):
    """执行一次完整比赛"""
    if target_weight is None:
        target_weight = round(random.uniform(4.0, 6.0), 2)

    print(f"\n{'='*60}")
    print(f" 比赛 #{match_id}")
    print(f" 粉末目标: {target_weight:.2f}g | 夹豆: 3颗")
    print(f"{'='*60}")

    match_start = time.time()
    total_score = 0

    # ─── 赛项1: 粉末称量 ───
    print(f"\n▶ 赛项1: 粉末称量 (目标 {target_weight:.2f}g ±0.05g, 120秒)")
    input("  天平归零后按回车...")
    task_start = time.time()

    # === 这里接入真实的 PowderWeighingFSM.execute() ===
    # 当前阶段：操作者手动完成，输入结果
    mode = input("  执行模式? [a=自动 / m=手动输入]: ").strip()
    if mode == 'a':
        # 自动模式: from powder_weighing.powder_fsm import PowderWeighingFSM
        # result = powder_fsm.execute(target=target_weight)
        print("  (自动执行中...)")
        actual = float(input("  最终重量(g): "))
        elapsed = time.time() - task_start
        ok = abs(actual - target_weight) <= 0.05
    else:
        print("  (手动称量...)")
        actual = float(input("  最终重量(g): "))
        elapsed = time.time() - task_start
        ok = abs(actual - target_weight) <= 0.05

    powder_score = 100 if ok else 0
    total_score += powder_score
    print(f"  {'✅' if ok else '❌'} 粉末: {actual:.2f}g (误差{abs(actual-target_weight):.3f}g) "
          f"得分{powder_score} 用时{elapsed:.0f}s")

    # ─── 赛项2: 镊子夹豆 ───
    print(f"\n▶ 赛项2: 镊子夹豆 (目标3颗, 120秒)")
    input("  放好豆子按回车...")
    task_start = time.time()
    beans_ok = int(input("  成功夹取几颗? [0-3]: ").strip())
    elapsed = time.time() - task_start
    bean_score = int(beans_ok / 3 * 100)
    total_score += bean_score
    print(f"  {'✅' if beans_ok>=3 else '⚠️'} 夹豆: {beans_ok}/3 得分{bean_score} 用时{elapsed:.0f}s")

    match_time = time.time() - match_start
    print(f"\n  📊 总分: {total_score}/200 | 总用时: {match_time:.0f}s")

    return {'match_id': match_id, 'target_weight': target_weight,
            'powder_ok': ok, 'powder_actual': actual, 'beans_ok': beans_ok,
            'total_score': total_score, 'total_time': round(match_time, 1)}

def run_matches(count=20):
    results = []
    print(f"{'='*60}")
    print(f" 全流程比赛模拟 — {count} 轮")
    print(f"{'='*60}")

    for i in range(count):
        r = run_match(i+1)
        results.append(r)

    # 汇总
    total_score = sum(r['total_score'] for r in results)
    avg_score = total_score / count
    powder_ok = sum(1 for r in results if r['powder_ok'])
    bean_full = sum(1 for r in results if r['beans_ok'] >= 3)
    avg_time = sum(r['total_time'] for r in results) / count

    print(f"\n{'='*60}")
    print(f" 比赛模拟总结")
    print(f"{'='*60}")
    print(f" 轮次: {count}")
    print(f" 平均得分: {avg_score:.1f}/200")
    print(f" 粉末成功率: {powder_ok}/{count} = {powder_ok/count*100:.0f}%")
    print(f" 夹豆成功率: {bean_full}/{count} = {bean_full/count*100:.0f}%")
    print(f" 平均用时: {avg_time:.0f}s")

    if avg_score >= 180:
        print(" ✅ 状态很好，可以比赛")
    elif avg_score >= 140:
        print(" 📈 还需优化，重点看哪个项目拖后腿")
    else:
        print(" ⚠️ 需要大量练习后再模拟")

    # 保存
    os.makedirs('training/logs', exist_ok=True)
    path = f"training/logs/match_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, 'w') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'count': count,
                   'avg_score': avg_score, 'powder_rate': powder_ok/count,
                   'bean_rate': bean_full/count, 'avg_time': avg_time,
                   'results': results}, f, indent=2)
    print(f"结果已保存: {path}")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--matches', type=int, default=20)
    run_matches(**vars(p.parse_args()))
