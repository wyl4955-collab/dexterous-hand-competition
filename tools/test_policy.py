#!/usr/bin/env python3
"""部署前测试策略模型 — dry_run 只打印不执行，live 接真手"""
import argparse, time, sys
import numpy as np
import torch
from tools.train_policy import Policy

try:
    import rclpy
    from competition_interfaces.msg import HandState, HandCommand
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False

# Safety limits (F2 manual)
ANGLE_MIN = [900, 900, 900, 900, 1100, 600]
ANGLE_MAX = [1740, 1740, 1740, 1740, 1550, 1750]
FORCE_MAX = [1000, 1000, 1000, 1000, 1200, 1200]
SPEED_MAX = 4000

def clamp_actions(angles, forces, speeds):
    for i in range(6):
        angles[i] = max(ANGLE_MIN[i], min(ANGLE_MAX[i], int(angles[i])))
        forces[i] = max(10, min(FORCE_MAX[i], int(forces[i])))
        speeds[i] = max(50, min(SPEED_MAX, int(speeds[i])))
    return angles, forces, speeds

def test_dry(model_path):
    """只打印模型预测，不执行"""
    ckpt = torch.load(model_path, map_location='cpu', weights_only=False)
    model = Policy()
    model.load_state_dict(ckpt['model'])
    model.eval()
    s_mean, s_std = ckpt['s_mean'], ckpt['s_std']
    a_mean, a_std = ckpt['a_mean'], ckpt['a_std']

    print("Dry run mode: 输入状态，看模型输出是否合理")
    print("输入 'q' 退出, 输入 6 个角度和 6 个力值（空格分隔）")

    while True:
        inp = input("\n角度(6) 力值(6) [scale]: ").strip()
        if inp == 'q': break
        parts = inp.split()
        if len(parts) < 12: continue
        state = [float(x) for x in parts[:12]]
        if len(state) == 12: state.append(0.0)  # default scale

        s = torch.tensor([state], dtype=torch.float32)
        s = (s - s_mean.unsqueeze(0)) / s_std.unsqueeze(0).clamp(min=1)
        with torch.no_grad():
            pred = model(torch.zeros(1, 3, 224, 224), s)
        pred = pred * a_std.unsqueeze(0) + a_mean.unsqueeze(0)
        pred = pred[0].tolist()

        angles, forces, speeds = clamp_actions(pred[:6], pred[6:12], pred[12:18])
        print(f"  预测角度: {angles}")
        print(f"  预测力控: {forces}")
        print(f"  预测速度: {speeds}")

def test_live(model_path):
    """接真手执行"""
    if not HAS_ROS2:
        print("需要 ROS2 环境")
        return
    import rclpy
    from rclpy.node import Node
    rclpy.init()
    node = Node('policy_tester')
    pub = node.create_publisher(HandCommand, '/hand/command', 10)

    ckpt = torch.load(model_path, map_location='cpu', weights_only=False)
    model = Policy()
    model.load_state_dict(ckpt['model'])
    model.eval()
    s_mean, s_std = ckpt['s_mean'], ckpt['s_std']
    a_mean, a_std = ckpt['a_mean'], ckpt['a_std']

    current_state = {'angles': [1740]*6, 'forces': [0]*6, 'scale': 0}

    def state_cb(msg):
        current_state['angles'] = list(msg.angles)
        current_state['forces'] = list(msg.forces)

    node.create_subscription(HandState, '/hand/state', state_cb, 10)

    print("Live mode: 按回车执行一次模型推理并发送指令, 'q'退出")
    while True:
        inp = input("\n按回车执行: ").strip()
        if inp == 'q': break

        state_vec = current_state['angles'] + current_state['forces'] + [current_state['scale']]
        s = torch.tensor([state_vec], dtype=torch.float32)
        s = (s - s_mean.unsqueeze(0)) / s_std.unsqueeze(0).clamp(min=1)
        with torch.no_grad():
            pred = model(torch.zeros(1, 3, 224, 224), s)
        pred = pred * a_std.unsqueeze(0) + a_mean.unsqueeze(0)
        pred = pred[0].tolist()

        angles, forces, speeds = clamp_actions(pred[:6], pred[6:12], pred[12:18])
        cmd = HandCommand()
        cmd.target_angles = [int(a) for a in angles]
        cmd.force_thresholds = [int(f) for f in forces]
        cmd.speeds = [int(sp) for sp in speeds]
        cmd.modes = [0]*6
        pub.publish(cmd)
        print(f"  已发送: 角度={angles} 力控={forces} 速度={speeds}")

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--mode', choices=['dry_run', 'live'], default='dry_run')
    args = p.parse_args()
    if args.mode == 'dry_run': test_dry(args.model)
    else: test_live(args.model)
