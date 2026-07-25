#!/usr/bin/env python3
"""Action primitives: each returns (success, elapsed, message)."""
import time
from competition_interfaces.msg import HandCommand

# Finger indices
LITTLE,RING,MIDDLE,INDEX,THUMB_BEND,THUMB_ROTATE = 0,1,2,3,4,5
# Poses (0.1-degree units)
OPEN = [1740,1740,1740,1740,1550,1750]
PINCH_WIDE = [1740,1740,1740,1500,1350,1200]
PINCH_CLOSE = [1740,1740,1740,1150,1150,1200]
GRIP_TWEEZERS = [1740,1740,1740,1250,1250,1200]
GRIP_SPOON = [1740,1740,1740,1280,1250,1200]


class Primitives:
    """High-level hand + arm primitives. Publishes HandCommand, controls arm."""
    def __init__(self, node):
        self.node = node
        self.pub = node.create_publisher(HandCommand, '/hand/command', 10)
        self._log = node.get_logger()

    def _send(self, angles, forces=None, speeds=None, modes=None, sleep=0.0):
        cmd = HandCommand()
        cmd.target_angles = [int(a) for a in angles]
        cmd.force_thresholds = forces if forces else [500]*6
        cmd.speeds = speeds if speeds else [1000]*6
        cmd.modes = modes if modes else [0]*6
        self.pub.publish(cmd)
        if sleep > 0: time.sleep(sleep)

    # ── General ──
    def open_all(self): self._send(OPEN, sleep=0.5); return (True, 0.5, "open")
    def close_all(self, force=300): self._send([900]*6, [force]*6, [800]*6, sleep=0.5); return (True, 0.5, "close")

    # ── Precision pinch ──
    def pinch_grasp(self, force=40, speed=150):
        t0 = time.time()
        self._send(PINCH_WIDE, [30]*6, [speed]*6, sleep=0.3)
        self._send(PINCH_CLOSE, [force]*6, [speed]*6, sleep=0.3)
        return (True, time.time()-t0, f"pinch@{force}g")

    # ── Tool grip ──
    def grip(self, tool='tweezers'):
        t0 = time.time()
        f = 120 if tool == 'tweezers' else 200
        pose = GRIP_TWEEZERS if tool == 'tweezers' else GRIP_SPOON
        self._send(PINCH_WIDE, [50]*6, [300]*6, sleep=0.3)
        self._send(pose, [f]*6, [300]*6, sleep=0.3)
        return (True, time.time()-t0, f"grip_{tool}")

    # ── Finger tap (vibration for powder) ──
    def tap(self, force_level=80, count=1, interval=0.3):
        t0 = time.time()
        for i in range(count):
            # ring finger: rapid flex
            self._send([1740,1300,1740,-1,-1,-1], [force_level]*6, [4000]*6, sleep=0.03)
            # ring finger: return
            self._send([1740,1700,1740,-1,-1,-1], [force_level]*6, [4000]*6, sleep=0.03)
            if i < count-1: time.sleep(interval)
        return (True, time.time()-t0, f"{count}taps@{force_level}g")

    def release(self):
        self._send(OPEN, [200]*6, [800]*6, sleep=0.3)
        return (True, 0.3, "release")
