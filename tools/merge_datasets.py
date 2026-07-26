#!/usr/bin/env python3
"""合并多个 .npz 数据集文件"""
import argparse, glob, os
import numpy as np

def merge(pattern, output):
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"没有找到匹配 {pattern} 的文件")
        return
    print(f"合并 {len(files)} 个文件: {files}")

    all_states = []
    all_actions = []
    for f in files:
        d = np.load(f)
        all_states.append(d['states'])
        all_actions.append(d['actions'])
        print(f"  {os.path.basename(f)}: {d['states'].shape[0]} 样本")

    states = np.concatenate(all_states, axis=0)
    actions = np.concatenate(all_actions, axis=0)
    np.savez_compressed(output, states=states, actions=actions)
    print(f"合并完成: {states.shape[0]} 总样本 → {output}")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('pattern', help='文件匹配模式, 如 "training_data/powder_*.npz"')
    p.add_argument('--output', required=True)
    merge(**vars(p.parse_args()))
