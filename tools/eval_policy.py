#!/usr/bin/env python3
"""评估训练好的策略模型"""
import argparse
import numpy as np
import torch
from tools.train_policy import Policy

def eval_model(model_path, test_data_path):
    ckpt = torch.load(model_path, map_location='cpu', weights_only=False)
    data = np.load(test_data_path)

    s_mean = ckpt['s_mean']; s_std = ckpt['s_std']
    a_mean = ckpt['a_mean']; a_std = ckpt['a_std']

    model = Policy()
    model.load_state_dict(ckpt['model'])
    model.eval()

    states = torch.from_numpy((data['states'] - s_mean.numpy()) / s_std.numpy())
    targets = data['actions']

    with torch.no_grad():
        preds = model(torch.zeros(len(states), 3, 224, 224), states).numpy()
    preds = preds * a_std.numpy() + a_mean.numpy()

    # Per-dimension error
    angle_error = np.abs(preds[:, :6] - targets[:, :6]).mean(0)
    force_error = np.abs(preds[:, 6:12] - targets[:, 6:12]).mean(0)
    speed_error = np.abs(preds[:, 12:18] - targets[:, 12:18]).mean(0)

    print(f"评估结果 ({len(states)} 样本):")
    print(f"  角度误差 (6指): {[f'{e:.1f}°' for e in angle_error]}")
    print(f"  力值误差 (6指): {[f'{e:.1f}g' for e in force_error]}")
    print(f"  速度误差 (6指): {[f'{e:.0f}' for e in speed_error]}")
    print(f"  平均角度误差: {angle_error.mean():.1f}°")
    print(f"  平均力值误差: {force_error.mean():.1f}g")

    if angle_error.mean() < 5 and force_error.mean() < 10:
        print("  ✅ 模型效果良好，可以部署")
    elif angle_error.mean() < 15 and force_error.mean() < 30:
        print("  📈 模型有待改进，建议增加训练数据")
    else:
        print("  ⚠️  误差较大，检查数据质量和训练参数")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--test_data', required=True)
    eval_model(**vars(p.parse_args()))
