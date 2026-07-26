#!/usr/bin/env python3
"""从 ros2 bag 提取 (观察,动作) 训练对"""
import argparse, os, sys, struct
import numpy as np
from collections import defaultdict

def parse_hand_state(raw):
    """Parse HandState from serialized bytes. Order: angles(6f), forces(6f), currents(6f), status(6h), faults(6h), temps(6h)"""
    fmt = '<6f 6f 6f 6h 6h 6h'
    size = struct.calcsize(fmt)
    if len(raw) < size: return None
    vals = struct.unpack(fmt, raw[:size])
    return {
        'angles': vals[0:6], 'forces': vals[6:12], 'currents': vals[12:18],
        'status': vals[18:24], 'faults': vals[24:30], 'temps': vals[30:36]
    }

def parse_hand_command(raw):
    """Parse HandCommand: target_angles(6h), force_thresholds(6h), speeds(6h), modes(6h)"""
    fmt = '<6h 6h 6h 6h'
    if len(raw) < struct.calcsize(fmt): return None
    vals = struct.unpack(fmt, raw[:struct.calcsize(fmt)])
    return {'angles': vals[0:6], 'forces': vals[6:12], 'speeds': vals[12:18], 'modes': vals[18:24]}

def extract(bag_path, output, downsample=5):
    """Extract (observation, action) pairs from bag file."""
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
    except ImportError:
        print("需要 rosbag2_py. pip install rosbag2-py")
        print("或者用备用方法: pip install sqlite3 直接读 SQLite")
        sys.exit(1)

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=bag_path, storage_id='sqlite3'),
        rosbag2_py.ConverterOptions('', '')
    )

    frames = []  # [{ts, state, command, scale}]
    print(f"读取 bag: {bag_path}")

    while reader.has_next():
        topic, data, ts = reader.read_next()
        frame = None

        if topic == '/hand/state':
            s = parse_hand_state(data)
            if s is None: continue
            frame = {'ts': ts, 'state': s}
        elif topic == '/hand/command':
            c = parse_hand_command(data)
            if c is None: continue
            frame = {'ts': ts, 'command': c}
        elif topic == '/vision/scale':
            try:
                val = struct.unpack('<f', data[:4])[0]
            except:
                continue
            frame = {'ts': ts, 'scale': val}
        elif topic == '/vision/beans':
            # BeanDetections: header(8) + int32(count) + count*BeanDetection(4f each)
            pass  # skip for now, image data is in /vision/debug

        if frame:
            frames.append(frame)

    print(f"读取了 {len(frames)} 帧")

    # Align: group frames by time window
    samples = []
    window = 0.1  # 100ms window to pair observation and action

    i = 0
    while i < len(frames) - 1:
        obs_state = None
        obs_scale = None
        action = None

        t0 = frames[i]['ts']
        # Collect observation
        for j in range(i, min(i+20, len(frames))):
            if 'state' in frames[j]:
                obs_state = frames[j]
            if 'scale' in frames[j]:
                obs_scale = frames[j]

        # Collect action ~500ms later
        target_ts = t0 + 500_000_000  # 500ms in nanoseconds
        for k in range(i, min(i+50, len(frames))):
            if 'command' in frames[k] and frames[k]['ts'] >= target_ts:
                action = frames[k]
                break

        if obs_state and action and obs_scale:
            # Build state vector: angles(6) + forces(6) + scale(1) = 13
            state_vec = list(obs_state['state']['angles']) + list(obs_state['state']['forces']) + [obs_scale.get('scale', 0.0)]
            # Build action vector: target_angles(6) + forces(6) + speeds(6) = 18
            act_vec = list(action['command']['angles']) + list(action['command']['forces']) + list(action['command']['speeds'])
            samples.append({'state': state_vec, 'action': act_vec})
            i += downsample
        else:
            i += 1

    print(f"提取了 {len(samples)} 个训练样本")

    if len(samples) == 0:
        print("⚠️  没有提取到样本。可能原因: bag 中话题名不对、数据帧太少")
        return

    states = np.array([s['state'] for s in samples], dtype=np.float32)
    actions = np.array([s['action'] for s in samples], dtype=np.float32)
    np.savez_compressed(output, states=states, actions=actions)
    print(f"保存到 {output}: states{states.shape} actions{actions.shape}")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bag', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--downsample', type=int, default=5)
    extract(**vars(p.parse_args()))
