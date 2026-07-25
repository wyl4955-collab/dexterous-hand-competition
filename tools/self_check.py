#!/usr/bin/env python3
"""全系统自检 —— 比赛前/到场地后运行，确认所有硬件正常"""
import time, sys, serial

def check_hand(port='/dev/ttyUSB0'):
    """检查灵巧手通信"""
    try:
        s = serial.Serial(port, 115200, timeout=0.5)
        s.write(bytes([0xEB, 0x90, 1, 4, 0x11, 0x28, 0x04, 0x0C, 0x4E]))
        time.sleep(0.1)
        raw = s.read(100)
        s.close()
        return len(raw) > 10 and raw[0] == 0x90
    except Exception as e:
        print(f"  ❌ 灵巧手: {e}")
        return False

def check_scale(port='/dev/ttyUSB1'):
    """检查天平"""
    try:
        s = serial.Serial(port, 9600, timeout=0.5)
        s.reset_input_buffer()
        line = s.readline()
        s.close()
        return len(line) > 0
    except Exception:
        return False

def check_camera(cam_id=0):
    """检查相机"""
    try:
        import cv2
        cap = cv2.VideoCapture(cam_id)
        ok, frame = cap.read()
        cap.release()
        return ok
    except Exception:
        return False

def main():
    print("=" * 50)
    print(" 灵巧手专项赛 — 系统自检")
    print("=" * 50)
    print()

    checks = [
        ("灵巧手通信", check_hand()),
        ("天平读数", check_scale()),
        ("相机图像", check_camera()),
    ]

    for name, ok in checks:
        print(f"  {'✅' if ok else '❌'} {name}")

    all_ok = all(c[1] for c in checks)
    print()
    if all_ok:
        print("✅ 全部正常，可以开始训练或比赛")
    else:
        print("⚠️  有系统未就绪，请排查：")
        for name, ok in checks:
            if not ok: print(f"    - {name}")
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
