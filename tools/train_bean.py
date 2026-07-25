#!/usr/bin/env python3
"""镊子夹豆训练工具 —— 自动跑N轮，记录每轮结果"""
import sys, time, json, os, argparse
from datetime import datetime

def run_training(rounds=10, beans_per_round=3):
    print(f"{'='*50}")
    print(f" 镊子夹豆训练: {rounds}轮, 每轮{beans_per_round}颗")
    print(f"{'='*50}")

    log = {'timestamp': datetime.now().isoformat(), 'task': 'bean_picking',
           'params': {'beans_per_round': beans_per_round}, 'rounds': []}

    total_beans, success_beans, cracked = 0, 0, 0

    for i in range(rounds):
        print(f"\n--- 第 {i+1}/{rounds} 轮 ---")
        input("放好豆子，按回车开始...")

        t0 = time.time()
        done, fail, crush = 0, 0, 0
        for b in range(beans_per_round):
            result = input(f"  豆子{b+1}/{beans_per_round}? [y=成功/n=未夹起/c=夹碎]: ").strip()
            if result == 'y': done += 1
            elif result == 'c': crush += 1
            else: fail += 1
        elapsed = time.time() - t0

        total_beans += beans_per_round; success_beans += done; cracked += crush
        rate = done / beans_per_round
        log['rounds'].append({'round': i+1, 'done': done, 'failed': fail,
                              'cracked': crush, 'rate': rate, 'time': round(elapsed, 1)})
        print(f"  本轮: {done}/{beans_per_round}, 累计成功率: {success_beans}/{total_beans} = {success_beans/total_beans*100:.0f}%")

    rate = success_beans / total_beans
    print(f"\n总结: 成功率 {rate*100:.1f}% ({success_beans}/{total_beans}), 夹碎{cracked}颗")

    os.makedirs('training/logs', exist_ok=True)
    path = f"training/logs/bean_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log['summary'] = {'total_beans': total_beans, 'success': success_beans,
                      'rate': round(rate, 3), 'cracked': cracked}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"日志已保存: {path}")
    return rate

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--rounds', type=int, default=10)
    p.add_argument('--beans', type=int, default=3)
    run_training(**vars(p.parse_args()))
