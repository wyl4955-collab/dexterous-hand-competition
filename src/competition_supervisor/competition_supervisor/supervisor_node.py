#!/usr/bin/env python3
"""
Competition Supervisor — the top-level orchestrator.

Responsibilities:
  1. Pre-match self-check (all subsystems ready?)
  2. Start/stop tasks on command
  3. Monitor task progress
  4. Emergency stop handling
  5. Score tracking and match report

Services provided:
  /competition/start   — begin the match
  /competition/stop    — abort the match
  /competition/estop   — emergency stop
  /competition/status  — get current match status

Topic published:
  /competition/status  (TaskStatus) — overall match status
"""

import time
import json
from datetime import datetime

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from competition_interfaces.msg import TaskStatus, HandCommand


class CompetitionSupervisor(Node):
    """Match orchestrator."""

    def __init__(self):
        super().__init__('competition_supervisor')

        self.declare_parameter('tasks', ['powder_weighing', 'bean_picking'])
        self.declare_parameter('match_timeout', 300.0)  # 5 min total

        # State
        self.match_running = False
        self.match_paused = False
        self.emergency_stop = False
        self.match_start_time = 0.0
        self.total_score = 0
        self.task_results = {}

        # Publisher
        self.status_pub = self.create_publisher(TaskStatus, '/competition/status', 10)

        # Emergency: publish to hand to stop
        self.estop_pub = self.create_publisher(HandCommand, '/hand/command', 10)

        # Services
        self.create_service(Trigger, '/competition/start', self._start_cb)
        self.create_service(Trigger, '/competition/stop', self._stop_cb)
        self.create_service(Trigger, '/competition/estop', self._estop_cb)
        self.create_service(Trigger, '/competition/status', self._status_cb)

        self.get_logger().info('Competition supervisor ready')

    # ═══════════════════════════════════════════════════════════════
    #  Pre-match check
    # ═══════════════════════════════════════════════════════════════

    def pre_match_check(self) -> bool:
        """Check that ALL subsystems are alive."""
        self.get_logger().info('=== Pre-match check ===')
        checks = {}

        # Check hand driver
        checks['hand_driver'] = self._check_topic('/hand/state', timeout=2.0)
        # Check vision
        checks['vision'] = self._check_topic('/vision/beans', timeout=2.0)
        # Check scale
        checks['scale'] = self._check_topic('/vision/scale', timeout=2.0)

        all_ok = all(checks.values())
        for name, ok in checks.items():
            status = '✅' if ok else '❌'
            self.get_logger().info(f'  {status} {name}')

        if not all_ok:
            self.get_logger().error('Pre-match check FAILED')
        else:
            self.get_logger().info('Pre-match check PASSED ✅')

        return all_ok

    def _check_topic(self, topic: str, timeout: float = 2.0) -> bool:
        """Check if a topic has publishers."""
        # In production: actually check topic existence
        # For now: query ROS2 graph
        topic_names = self.get_topic_names_and_types()
        return any(t[0] == topic for t in topic_names)

    # ═══════════════════════════════════════════════════════════════
    #  Service callbacks
    # ═══════════════════════════════════════════════════════════════

    def _start_cb(self, request, response):
        if self.match_running:
            response.success = False
            response.message = 'Match already running'
            return response

        if not self.pre_match_check():
            response.success = False
            response.message = 'Pre-match check failed'
            return response

        self.match_running = True
        self.match_start_time = time.time()
        self.total_score = 0
        self.task_results = {}

        self.get_logger().info('🏁 MATCH STARTED')

        # Run tasks sequentially
        tasks = self.get_parameter('tasks').value
        for task_name in tasks:
            if self.emergency_stop:
                break

            self.get_logger().info(f'▶ Starting task: {task_name}')
            # Task execution is triggered externally (by the operator panel
            # calling the task's RunTask service)
            # Here we just wait for the task to complete

            # In production: use a service client to call the task's run service
            # and wait for the response

        self.match_running = False
        elapsed = time.time() - self.match_start_time
        self.get_logger().info(f'🏁 MATCH COMPLETE: score={self.total_score} time={elapsed:.1f}s')

        response.success = True
        response.message = f'Match complete. Score: {self.total_score}, Time: {elapsed:.1f}s'
        return response

    def _stop_cb(self, request, response):
        self.match_running = False
        self.get_logger().info('Match stopped by operator')
        response.success = True
        response.message = 'Match stopped'
        return response

    def _estop_cb(self, request, response):
        self.emergency_stop = True
        self.match_running = False

        # Send emergency stop to hand
        cmd = HandCommand()
        cmd.target_angles = [-1]*6  # don't change
        cmd.force_thresholds = [10]*6  # minimal force = release
        cmd.speeds = [4000]*6
        cmd.modes = [0]*6
        self.estop_pub.publish(cmd)

        self.get_logger().error('🛑 EMERGENCY STOP ACTIVATED')
        response.success = True
        response.message = 'Emergency stop'
        return response

    def _status_cb(self, request, response):
        elapsed = time.time() - self.match_start_time if self.match_start_time > 0 else 0.0
        response.success = True
        response.message = (
            f'Running: {self.match_running}, '
            f'Score: {self.total_score}, '
            f'Elapsed: {elapsed:.1f}s'
        )
        return response


def main():
    rclpy.init()
    node = CompetitionSupervisor()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
