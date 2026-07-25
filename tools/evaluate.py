#!/usr/bin/env python3
"""
训练数据分析 —— 读取训练日志，输出统计和趋势

使用方法:
  python3 tools/evaluate.py training/logs/        ← 分析所有日志
  python3 tools/evaluate.py training/logs/ --task powder  ← 只看称量
"""
import sys, json, os, glob, argparse
from collections import defaultdict

def load_logs(log_dir, task_filter=None):
    logs = []
    pattern = os.path.join(log_dir, '*.json')
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if task_filter and data.get('task', '') != task_filter:
            continue
        logs.append(data)
    return logs

def analyze(logs):
    if not logs:
        print("没有找到日志文件")
        return

    # 合并所有轮次
    all_rounds = []
    for log in logs:
        for r in log.get('rounds', []):
            r['_log_time'] = log.get('timestamp', 'unknown')
            all_rounds.append(r)

    total = len(all_rounds)
    success = sum(1 for r in all_rounds if r.get('success', r.get('done', 0) >= r.get('beans_per_round', 1)))
    rate = success / total if total > 0 else 0

    # 失败原因
    failures = defaultdict(int)
    for r in all_rounds:
        if not r.get('success', True):
            failures[r.get('failure', 'unknown')] += 1

    # 按时间序列看趋势（每5轮一组）
    groups = []
    for i in range(0, total, 5):
        batch = all_rounds[i:i+5]
        batch_success = sum(1 for r in batch if r.get('success'))
        groups.append({'start': i+1, 'end': min(i+5, total), 'rate': batch_success / len(batch)})

    print(f"{'='*50}")
    print(f" 训练数据分析")
    print(f"{'='*50}")
    print(f" 总轮次: {total}")
    print(f" 总成功: {success}")
    print(f" 成功率: {rate*100:.1f}%")
    print()

    if failures:
        print("失败原因分布:")
        for reason, count in sorted(failures.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}次 ({count/total*100:.1f}%)")
        print()

    if len(groups) > 1:
        print("成功率变化趋势:")
        for g in groups:
            bar = '█' * int(g['rate'] * 20)
            print(f"  第{g['start']:>2}-{g['end']:<2}轮: {bar} {g['rate']*100:.0f}%")

    # 推荐
    print()
    if rate < 0.5:
        print("⚠️  成功率 < 50%，建议重新标定力控参数")
    elif rate < 0.8:
        print("📈 成功率 50-80%，继续练习并关注失败原因")
    else:
        print("✅ 成功率 > 80%，保持当前参数，赛前不轻易改动")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('log_dir', default='training/logs')
    p.add_argument('--task', default=None, choices=['powder_weighing', 'bean_picking'])
    args = p.parse_args()
    analyze(load_logs(args.log_dir, args.task))
