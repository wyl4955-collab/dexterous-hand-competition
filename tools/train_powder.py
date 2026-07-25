#!/usr/bin/env python3
"""
粉末称量训练工具 —— 自动跑N轮，记录每轮结果

使用方法:
  python3 tools/train_powder.py --rounds 10 --target 5.00
"""
import sys, time, json, os, argparse
from datetime import datetime

def run_training(rounds=10, target=5.00, tolerance=0.05):
    print(f"{'='*50}")
    print(f" 粉末称量训练: {rounds}轮, 目标{target}g±{tolerance}g")
    print(f"{'='*50}")

    training_log = {
        'timestamp': datetime.now().isoformat(),
        'task': 'powder_weighing',
        'params': {'target': target, 'tolerance': tolerance},
        'rounds': []
    }

    success_count = 0
    total_error = 0
    total_time = 0

    for i in range(rounds):
        print(f"\n--- 第 {i+1}/{rounds} 轮 ---")

        # 等待天平归零
        input("天平归零后按回车开始...")

        t0 = time.time()
        # === 这里接入真实的粉末称量执行 ===
        # 当前阶段：操作者手动完成称量，输入结果
        # 后续阶段：调用 powder_fsm.execute() 自动执行
        actual = float(input("最终天平读数(g): ").strip())
        elapsed = time.time() - t0

        error = abs(actual - target)
        ok = error <= tolerance
        if ok: success_count += 1

        rounds_data = {
            'round': i+1, 'target': target, 'actual': actual,
            'error': round(error, 3), 'success': ok,
            'time': round(elapsed, 1),
            'failure': '' if ok else ('overshoot' if actual > target else 'undershoot')
        }
        training_log['rounds'].append(rounds_data)

        total_error += error
        total_time += elapsed

        status = '✅' if ok else '❌'
        print(f"  {status} 误差: {error:.3f}g, 用时: {elapsed:.1f}s, "
              f"累计成功率: {success_count}/{i+1} = {success_count/(i+1)*100:.0f}%")

    # 汇总
    avg_error = total_error / rounds
    avg_time = total_time / rounds
    rate = success_count / rounds

    print(f"\n{'='*50}")
    print(f" 训练完成")
    print(f" 成功率: {success_count}/{rounds} = {rate*100:.1f}%")
    print(f" 平均误差: {avg_error:.3f}g")
    print(f" 平均用时: {avg_time:.1f}s")
    print(f"{'='*50}")

    # 保存
    os.makedirs('training/logs', exist_ok=True)
    path = f"training/logs/powder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    training_log['summary'] = {
        'total': rounds, 'success': success_count, 'success_rate': round(rate, 3),
        'mean_error': round(avg_error, 3), 'mean_time': round(avg_time, 1)
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(training_log, f, indent=2, ensure_ascii=False)
    print(f"日志已保存: {path}")
    return rate

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--rounds', type=int, default=10)
    p.add_argument('--target', type=float, default=5.00)
    run_training(**vars(p.parse_args()))
