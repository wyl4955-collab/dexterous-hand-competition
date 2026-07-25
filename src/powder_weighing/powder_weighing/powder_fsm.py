#!/usr/bin/env python3
"""
Powder Weighing Task — Finite State Machine

States:
  IDLE → GRIP_SPOON → TARE → SCOOP → COARSE_POUR → FINE_TAP → VERIFY → DONE
                                ↑                          │
                                └────── RETRY (if under) ──┘
  Any state → ERROR → (recovery) → IDLE

Data sources consumed:
  /vision/scale (Float32)           → current weight reading
  /hand/state (HandState)           → finger forces, status
  Skill primitives service calls    → hand/arm actions

Publishes:
  /task/status (TaskStatus)         → task progress for supervisor
"""

import time
from enum import Enum, auto

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from competition_interfaces.msg import TaskStatus


class PowderState(Enum):
    IDLE = auto()
    GRIP_SPOON = auto()
    TARE = auto()
    SCOOP = auto()
    COARSE_POUR = auto()
    FINE_TAP = auto()
    VERIFY = auto()
    SUCCESS = auto()
    FAILED = auto()


class PowderWeighingFSM(Node):
    """Powder weighing task state machine."""

    def __init__(self, skills, arm, waypoints: dict, params: dict):
        super().__init__('powder_weighing_fsm')
        self.skills = skills
        self.arm = arm
        self.wp = waypoints
        self.params = params

        self.state = PowderState.IDLE
        self.target = params.get('target_weight', 5.00)
        self.tolerance = params.get('tolerance', 0.05)
        self.timeout = params.get('timeout', 120.0)
        self.max_retries = params.get('max_retries', 3)

        # Tap calibration
        self.tap_calib = params.get('tap_force_to_drop_mg', {
            30: 0.01, 50: 0.02, 80: 0.04,
            120: 0.08, 180: 0.15, 250: 0.30,
        })

        # Runtime state
        self.current_weight = 0.0
        self.last_weight = 0.0
        self.tap_count = 0
        self.retry_count = 0
        self.start_time = 0.0

        # Publisher
        self.status_pub = self.create_publisher(TaskStatus, '/task/status', 10)

        # Scale subscription
        self.scale_sub = self.create_subscription(
            Float32, '/vision/scale',
            self._scale_callback, 10)

        self.get_logger().info('Powder weighing FSM ready')

    def _scale_callback(self, msg: Float32):
        self.current_weight = msg.data

    def _publish_status(self, state_name: str, score: float = 0.0):
        msg = TaskStatus()
        msg.task_name = 'powder_weighing'
        msg.state = state_name
        msg.elapsed = time.time() - self.start_time if self.start_time > 0 else 0.0
        msg.score = score
        self.status_pub.publish(msg)

    # ═══════════════════════════════════════════════════════════════
    #  Main execution loop
    # ═══════════════════════════════════════════════════════════════

    def execute(self, target_weight: float = None, tolerance: float = None) -> dict:
        """
        Run the complete powder weighing task.

        Returns: {'success': bool, 'actual': float, 'error': float,
                  'elapsed': float, 'taps': int}
        """
        if target_weight:
            self.target = target_weight
        if tolerance:
            self.tolerance = tolerance

        self.start_time = time.time()
        self.state = PowderState.GRIP_SPOON
        self.tap_count = 0
        self.retry_count = 0

        self.get_logger().info(f'Powder weighing: target={self.target:.2f}g ±{self.tolerance:.2f}g')

        while self.state not in [PowderState.SUCCESS, PowderState.FAILED]:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout:
                self.get_logger().error('Timeout!')
                self.state = PowderState.FAILED
                break

            if self.state == PowderState.GRIP_SPOON:
                self._grip_spoon()
            elif self.state == PowderState.TARE:
                self._tare()
            elif self.state == PowderState.SCOOP:
                self._scoop()
            elif self.state == PowderState.COARSE_POUR:
                self._coarse_pour()
            elif self.state == PowderState.FINE_TAP:
                self._fine_tap()
            elif self.state == PowderState.VERIFY:
                self._verify()

            self._publish_status(self.state.name)

        elapsed = time.time() - self.start_time
        success = self.state == PowderState.SUCCESS

        return {
            'success': success,
            'actual': self.current_weight,
            'error': abs(self.current_weight - self.target),
            'elapsed': elapsed,
            'taps': self.tap_count,
        }

    # ═══════════════════════════════════════════════════════════════
    #  State handlers
    # ═══════════════════════════════════════════════════════════════

    def _grip_spoon(self):
        self.get_logger().info('[GRIP_SPOON]')
        self.skills.open_hand()
        time.sleep(0.5)

        # Move arm to spoon pickup position
        pos = self.wp.get('spoon_pickup', [20, 160, 40])
        self.arm.move_to(tuple(pos), speed=40.0)
        time.sleep(0.5)

        # Grip the spoon
        result = self.skills.grip_tool('spoon')
        if result.success:
            self.state = PowderState.TARE
        else:
            self.retry_count += 1
            if self.retry_count > self.max_retries:
                self.state = PowderState.FAILED

    def _tare(self):
        self.get_logger().info('[TARE] Waiting for scale to stabilize...')
        # Wait for stable zero reading (or manual confirmation)
        time.sleep(1.0)
        self.get_logger().info(f'Scale reads: {self.current_weight:.2f}g')
        self.state = PowderState.SCOOP

    def _scoop(self):
        self.get_logger().info('[SCOOP] Scooping powder...')
        # Move arm to powder container
        pos = self.wp.get('powder_container', [50, 20, 80])
        self.arm.move_to(tuple(pos), speed=40.0)

        # Lower spoon into powder
        self.arm.move_relative(dz=-15, speed=10)
        time.sleep(0.5)

        # Scoop horizontally
        self.arm.move_relative(dx=30, speed=15)
        time.sleep(0.5)

        # Lift
        self.arm.move_relative(dz=30, speed=20)
        self.state = PowderState.COARSE_POUR

    def _coarse_pour(self):
        self.get_logger().info('[COARSE_POUR] Pouring until near target...')
        # Move to scale
        pos = self.wp.get('scale_above', [150, 75, 60])
        self.arm.move_to(tuple(pos[:3]), speed=40.0)

        # Tilt spoon
        self.skills.pour_spoon(tilt_angle=25)

        # Monitor scale, stop when within 1g of target
        last_change_time = time.time()
        while True:
            diff = self.current_weight - self.target
            if diff >= -0.5:  # close enough to target
                break
            if time.time() - last_change_time > 3.0:
                # Powder not flowing, increase tilt
                self.skills.pour_spoon(tilt_angle=35)
            if self.current_weight != self.last_weight:
                last_change_time = time.time()
            self.last_weight = self.current_weight
            self.get_logger().info(f'  Coarse: {self.current_weight:.2f}g (target {self.target:.2f}g)')
            time.sleep(0.5)

        # Level spoon
        self.skills.pour_spoon(tilt_angle=0)
        self.get_logger().info(f'Coarse done: {self.current_weight:.2f}g')
        self.state = PowderState.FINE_TAP

    def _fine_tap(self):
        """The core skill: vibrate powder out grain by grain."""
        self.get_logger().info('[FINE_TAP] Vibrating to reach target...')

        max_taps = 300
        while self.tap_count < max_taps:
            remaining = self.target - self.current_weight

            # Success?
            if abs(remaining) <= self.tolerance:
                self.state = PowderState.VERIFY
                return
            # Overshoot?
            if remaining < 0:
                self.get_logger().warn(f'Overshoot! {self.current_weight:.2f}g')
                self.state = PowderState.FAILED
                return

            # Select tap force based on remaining amount
            if remaining > 1.5:
                force = 250
            elif remaining > 0.8:
                force = 180
            elif remaining > 0.3:
                force = 120
            elif remaining > 0.1:
                force = 80
            elif remaining > 0.05:
                force = 50
            else:
                force = 30

            # Estimate taps needed
            drop_per_tap = self.tap_calib.get(force, 0.05)
            n_taps = max(1, min(10, int(remaining / drop_per_tap * 0.7)))

            self.get_logger().info(
                f'  Remaining: {remaining:.3f}g → force={force}g × {n_taps} taps'
            )

            result = self.skills.finger_tap('ring', force, n_taps, 0.4)
            self.tap_count += n_taps

            # Wait for powder to settle on scale
            time.sleep(0.8)

        self.state = PowderState.VERIFY

    def _verify(self):
        self.get_logger().info(f'[VERIFY] Final: {self.current_weight:.2f}g')
        time.sleep(2.0)  # let scale stabilize

        error = abs(self.current_weight - self.target)
        if error <= self.tolerance:
            self.get_logger().info(f'✅ PASS: {self.current_weight:.2f}g (error {error:.3f}g)')
            self.state = PowderState.SUCCESS
        elif self.current_weight < self.target and self.retry_count < 1:
            # Under but close — try a few more taps
            self.retry_count += 1
            self.get_logger().info(f'Under, retrying ({self.retry_count})...')
            self.state = PowderState.FINE_TAP
        else:
            self.get_logger().error(f'❌ FAIL: {self.current_weight:.2f}g (error {error:.3f}g)')
            self.state = PowderState.FAILED

        # Always release spoon at end
        self.skills.release()
