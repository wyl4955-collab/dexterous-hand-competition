#!/usr/bin/env python3
"""
Bean Picking Task — Finite State Machine

States:
  IDLE → DETECT → GRIP_TWEEZERS → APPROACH → DESCEND → GRASP
       → LIFT → MOVE_TO_CONTAINER → RELEASE → VERIFY → DONE

Data sources:
  /vision/beans (BeanDetections)  → bean positions
  /vision/tool (ToolState)        → tweezer tip position
  /hand/state (HandState)         → finger forces (contact detection)

Publishes:
  /task/status (TaskStatus)
"""

import time
from enum import Enum, auto
from typing import List

import rclpy
from rclpy.node import Node
from competition_interfaces.msg import BeanDetections, TaskStatus, HandState


class BeanState(Enum):
    IDLE = auto()
    DETECT = auto()
    GRIP_TWEEZERS = auto()
    APPROACH = auto()
    DESCEND = auto()
    GRASP = auto()
    LIFT = auto()
    MOVE_TO_CONTAINER = auto()
    RELEASE = auto()
    VERIFY = auto()
    SUCCESS = auto()
    FAILED = auto()


class BeanPickingFSM(Node):
    """Pick beans with tweezers FSM."""

    def __init__(self, skills, arm, waypoints: dict, params: dict):
        super().__init__('bean_picking_fsm')
        self.skills = skills
        self.arm = arm
        self.wp = waypoints
        self.params = params

        self.state = BeanState.IDLE
        self.bean_count_target = params.get('bean_count', 3)
        self.timeout = params.get('timeout', 120.0)
        self.max_retries = params.get('max_retries_per_bean', 3)

        # Runtime
        self.beans_done = 0
        self.beans_failed = 0
        self.current_bean_idx = 0
        self.retry_count = 0
        self.start_time = 0.0
        self.beans_list: List = []

        self.status_pub = self.create_publisher(TaskStatus, '/task/status', 10)
        self.beans_sub = self.create_subscription(
            BeanDetections, '/vision/beans', self._beans_callback, 10)
        self.hand_sub = self.create_subscription(
            HandState, '/hand/state', self._hand_callback, 10)

        # Latest hand forces for contact detection
        self.current_forces = [0.0] * 6
        self.current_status = [0] * 6

        self.get_logger().info('Bean picking FSM ready')

    def _beans_callback(self, msg: BeanDetections):
        self.beans_list = msg.beans

    def _hand_callback(self, msg: HandState):
        self.current_forces = list(msg.forces)
        self.current_status = list(msg.status)

    def _publish_status(self, state_name: str, score: float = 0.0):
        msg = TaskStatus()
        msg.task_name = 'bean_picking'
        msg.state = state_name
        msg.elapsed = time.time() - self.start_time if self.start_time > 0 else 0.0
        msg.score = score
        msg.message = f'{self.beans_done}/{self.bean_count_target} done'
        self.status_pub.publish(msg)

    # ═══════════════════════════════════════════════════════════════
    #  Main execution
    # ═══════════════════════════════════════════════════════════════

    def execute(self) -> dict:
        self.start_time = time.time()
        self.beans_done = 0
        self.beans_failed = 0
        self.state = BeanState.GRIP_TWEEZERS

        while self.beans_done < self.bean_count_target:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout:
                self.get_logger().error('Timeout!')
                self.state = BeanState.FAILED
                break

            # Pick one bean
            result = self._pick_one_bean()
            if result:
                self.beans_done += 1
                self.retry_count = 0
                self.get_logger().info(f'Bean {self.beans_done}/{self.bean_count_target} ✅')
            else:
                self.beans_failed += 1
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    self.get_logger().warn(f'Skipping bean after {self.retry_count} failures')
                    self.retry_count = 0
                    # Try next bean
                self.get_logger().warn(f'Bean failed ({self.beans_failed} total)')

            self._publish_status(self.state.name, self.beans_done)

        elapsed = time.time() - self.start_time
        success = self.beans_done >= self.bean_count_target

        # Release tweezers
        self.skills.release()

        return {
            'success': success,
            'beans_done': self.beans_done,
            'beans_target': self.bean_count_target,
            'beans_failed': self.beans_failed,
            'elapsed': elapsed,
        }

    # ═══════════════════════════════════════════════════════════════
    #  Single bean cycle
    # ═══════════════════════════════════════════════════════════════

    def _pick_one_bean(self) -> bool:
        """Complete cycle to pick up one bean and drop it in the container."""

        # — Step 1: Detect beans —
        self.get_logger().info(f'[DETECT] Looking for beans...')
        time.sleep(0.3)
        if len(self.beans_list) == 0:
            self.get_logger().warn('No beans detected!')
            return False

        # Select bean (farthest from pile to avoid disturbing others)
        bean = self.beans_list[-1]  # farthest in y
        self.get_logger().info(f'  Selected bean at ({bean.x:.0f}, {bean.y:.0f})mm')

        # — Step 2: Grip tweezers —
        self.get_logger().info(f'[GRIP] Gripping tweezers...')
        self.skills.grip_tool('tweezers')
        time.sleep(0.3)

        # — Step 3: Approach bean —
        self.get_logger().info(f'[APPROACH] Moving to bean...')
        self.skills.approach_bean((bean.x, bean.y), height_mm=30)
        time.sleep(0.3)

        # — Step 4: Open tweezers wide —
        self.skills.move_hand(
            [1740, 1740, 1740, 1500, 1350, 1200],
            forces=[30]*6, speeds=[200]*6
        )
        time.sleep(0.3)

        # — Step 5: Descend slowly —
        self.get_logger().info(f'[DESCEND] Lowering to bean...')
        self.skills.descend_to_bean(descent_speed=3.0)
        time.sleep(0.5)

        # — Step 6: Grasp —
        self.get_logger().info(f'[GRASP] Closing tweezers (force=40g)...')
        result = self.skills.pinch_grasp(target_force=40, close_speed=150)

        # Check contact
        time.sleep(0.2)
        idx_force = self.current_forces[3]  # index finger
        thumb_force = self.current_forces[4]  # thumb

        if idx_force < 15 and thumb_force < 15:
            self.get_logger().warn(f'  No contact detected (idx={idx_force:.0f}g, thumb={thumb_force:.0f}g)')
            return False

        self.get_logger().info(f'  Contact! idx={idx_force:.0f}g, thumb={thumb_force:.0f}g')

        # Anti-slip: slightly increase grip
        safe_force = min(max(idx_force, thumb_force) + 15, 80)
        self.skills.adjust_grip(int(safe_force))

        # — Step 7: Lift —
        self.get_logger().info(f'[LIFT] Raising bean...')
        self.skills.lift_bean(height_mm=50)
        time.sleep(0.5)

        # — Step 8: Move to container —
        self.get_logger().info(f'[MOVE] Transporting to container...')
        pos = self.wp.get('bean_drop', self.wp.get('bean_container', [180, 30, 20]))
        self.skills.move_to_container(tuple(pos[:3]), speed=50.0)
        time.sleep(0.5)

        # — Step 9: Release —
        self.get_logger().info(f'[RELEASE] Dropping bean...')
        self.skills.move_hand(
            [1740, 1740, 1740, 1550, 1550, -1],
            forces=[30]*6, speeds=[500]*6
        )
        time.sleep(0.3)

        return True
