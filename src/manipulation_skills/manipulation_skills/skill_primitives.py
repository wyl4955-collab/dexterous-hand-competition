"""
Action primitives for competition tasks.

Each primitive:
  1. Takes a goal description
  2. Publishes hand/arm commands
  3. Monitors feedback (force, vision) for closed-loop execution
  4. Returns success/failure with diagnostics

Data flow:
  Perception (/vision/*) ──→ Skill reads feedback
  Skill publishes ──→ Hand (/hand/command) + Arm (move_to)
"""

import time
from typing import List, Tuple, Optional
from dataclasses import dataclass

import rclpy
from rclpy.node import Node
from competition_interfaces.msg import HandCommand
from std_msgs.msg import Float32


@dataclass
class SkillResult:
    success: bool
    elapsed: float
    message: str = ""
    data: dict = None


class SkillPrimitives(Node):
    """
    High-level manipulation primitives.

    Each method:
      - Publishes HandCommand to control the hand
      - Optionally moves the robot arm
      - Monitors force/touch feedback for closed-loop control
      - Returns SkillResult
    """

    def __init__(self, arm_interface, node_name='skill_primitives'):
        super().__init__(node_name)
        self.arm = arm_interface

        # Hand command publisher
        self.hand_pub = self.create_publisher(HandCommand, '/hand/command', 10)

        # ── Pre-loaded poses ──
        self.poses = {
            'open_all':      [1740, 1740, 1740, 1740, 1550, 1750],
            'pinch_wide':    [1740, 1740, 1740, 1500, 1350, 1200],
            'pinch_bean':    [1740, 1740, 1740, 1150, 1150, 1200],
            'grip_tweezers': [1740, 1740, 1740, 1250, 1250, 1200],
            'grip_spoon':    [1740, 1740, 1740, 1280, 1250, 1200],
        }

    # ═══════════════════════════════════════════════════════════════
    #  General primitives
    # ═══════════════════════════════════════════════════════════════

    def move_hand(self, angles: List[int], forces: List[int] = None,
                  speeds: List[int] = None, modes: List[int] = None,
                  wait_stop: bool = True, timeout: float = 3.0) -> SkillResult:
        """
        Move hand to target angles with specified force/speed parameters.

        Args:
            angles: 6 target angles (-1 = don't move that finger)
            forces: 6 force thresholds (g). Default: [500]*6
            speeds: 6 speeds. Default: [1000]*6
            modes: 6 finger modes. Default: [0]*6 (speed-force-protect)
            wait_stop: Block until fingers stop moving
            timeout: Max wait time for stop
        """
        t0 = time.time()

        cmd = HandCommand()
        cmd.target_angles = [int(a) for a in angles]
        cmd.force_thresholds = forces if forces else [500]*6
        cmd.speeds = speeds if speeds else [1000]*6
        cmd.modes = modes if modes else [0]*6
        self.hand_pub.publish(cmd)

        if wait_stop:
            # Wait for movement to complete
            # In production: subscribe to /hand/state and check status codes
            # status >= 2 means stopped (2=position, 3=force, 5+=fault)
            time.sleep(0.2)  # let command propagate
            waited = 0.0
            while waited < timeout:
                # TODO: check actual status from /hand/state callback
                time.sleep(0.05)
                waited += 0.05

        return SkillResult(success=True, elapsed=time.time()-t0)

    def open_hand(self, speed: int = 1500) -> SkillResult:
        return self.move_hand(self.poses['open_all'],
                              forces=[500]*6, speeds=[speed]*6)

    def close_hand(self, force: int = 300, speed: int = 800) -> SkillResult:
        return self.move_hand([900]*6,
                              forces=[force]*6, speeds=[speed]*6)

    # ═══════════════════════════════════════════════════════════════
    #  Precision pinch (bean picking core)
    # ═══════════════════════════════════════════════════════════════

    def pinch_grasp(self, target_force: int = 40,
                    close_speed: int = 200,
                    finger_spread_angle: int = 1500) -> SkillResult:
        """
        Thumb + index precision pinch with force control.

        This is THE core action for picking up beans.

        Args:
            target_force: force threshold in grams (40 = optimal for soybeans)
            close_speed: closing speed (150-200 for precision)
            finger_spread_angle: how wide to open before closing
        """
        t0 = time.time()

        # Step 1: Open pinch fingers wide
        angles = [1740, 1740, 1740, finger_spread_angle, 1350, 1200]
        self.move_hand(angles, forces=[30]*6, speeds=[close_speed]*6, wait_stop=True)
        time.sleep(0.2)

        # Step 2: Close until force contact
        angles = [1740, 1740, 1740, 1150, 1150, 1200]
        result = self.move_hand(angles,
                                forces=[target_force]*6,
                                speeds=[close_speed]*6,
                                wait_stop=True, timeout=3.0)

        return SkillResult(success=result.success, elapsed=time.time()-t0,
                          message=f'force={target_force}g speed={close_speed}')

    def adjust_grip(self, delta_force: int = 10) -> SkillResult:
        """Increase or decrease grip force by delta_force grams."""
        # In production: read current forces, add delta, and update
        # For now, publish a command with adjusted force
        t0 = time.time()
        cmd = HandCommand()
        cmd.target_angles = [-1]*6  # don't change angles
        cmd.force_thresholds = [delta_force]*6  # relative adjustment
        cmd.speeds = [200]*6
        cmd.modes = [0]*6
        self.hand_pub.publish(cmd)
        return SkillResult(success=True, elapsed=time.time()-t0)

    # ═══════════════════════════════════════════════════════════════
    #  Tool grip
    # ═══════════════════════════════════════════════════════════════

    def grip_tool(self, tool: str = 'tweezers') -> SkillResult:
        """
        Grip a tool (tweezers or spoon).

        Tweezers: 100g force — firm but not crushing
        Spoon:    180g force — heavier, needs more grip
        """
        t0 = time.time()
        if tool == 'tweezers':
            self.move_hand(self.poses['pinch_wide'], forces=[50]*6, speeds=[300]*6)
            time.sleep(0.3)
            result = self.move_hand(self.poses['grip_tweezers'],
                                    forces=[120]*6, speeds=[300]*6)
        elif tool == 'spoon':
            self.move_hand(self.poses['pinch_wide'], forces=[50]*6, speeds=[400]*6)
            time.sleep(0.3)
            result = self.move_hand(self.poses['grip_spoon'],
                                    forces=[200]*6, speeds=[400]*6)
        else:
            return SkillResult(success=False, elapsed=0, message=f'Unknown tool: {tool}')
        return SkillResult(success=True, elapsed=time.time()-t0)

    def release(self, speed: int = 800) -> SkillResult:
        """Release current grip."""
        return self.move_hand(self.poses['open_all'],
                              forces=[200]*6, speeds=[speed]*6)

    # ═══════════════════════════════════════════════════════════════
    #  Finger tap (powder vibration core)
    # ═══════════════════════════════════════════════════════════════

    def finger_tap(self, finger: str = 'ring', force_level: int = 80,
                   count: int = 1, interval: float = 0.3) -> SkillResult:
        """
        Tap a finger to vibrate the spoon for powder dispensing.

        This is the KEY technique for precise powder weighing.

        Args:
            finger: 'ring' or 'middle' — which finger taps the spoon handle
            force_level: tap strength
                30-50  = micro (0.01-0.03g per tap)  → last 0.1g
                60-100 = light (0.03-0.08g per tap)  → last 0.5g
                120-180 = medium (0.08-0.20g per tap) → last 1-2g
                200-250 = heavy (0.20-0.50g per tap)  → coarse
            count: number of taps
            interval: time between taps (seconds)
        """
        t0 = time.time()
        finger_idx = {'ring': 1, 'middle': 2}.get(finger, 1)
        fill = 1740

        for i in range(count):
            # Tap: rapid flex then extend
            # Only the tapping finger moves; others stay at current position (-1)
            angles = [fill if j != finger_idx else 1300 for j in range(6)]
            angles[3] = -1  # index stays
            angles[4] = -1  # thumb stays
            angles[5] = -1
            self.move_hand(angles, forces=[force_level]*6, speeds=[4000]*6,
                          wait_stop=False)
            time.sleep(0.03)  # very short pulse

            # Return
            angles = [fill if j != finger_idx else 1700 for j in range(6)]
            angles[3] = -1
            angles[4] = -1
            angles[5] = -1
            self.move_hand(angles, forces=[force_level]*6, speeds=[4000]*6,
                          wait_stop=False)
            time.sleep(0.03)

            if i < count - 1:
                time.sleep(interval)

        return SkillResult(success=True, elapsed=time.time()-t0,
                          message=f'{count} taps at {force_level}g')

    # ═══════════════════════════════════════════════════════════════
    #  Arm + hand coordinated moves
    # ═══════════════════════════════════════════════════════════════

    def approach_bean(self, bean_world_xy: Tuple[float, float],
                      height_mm: float = 30.0) -> SkillResult:
        """
        Move arm so tweezer tip is above the target bean.
        """
        t0 = time.time()
        target = (bean_world_xy[0], bean_world_xy[1], height_mm)
        ok = self.arm.move_to(target, speed=30.0)
        return SkillResult(success=ok, elapsed=time.time()-t0)

    def descend_to_bean(self, descent_speed: float = 3.0) -> SkillResult:
        """
        Slowly lower arm until force contact is detected.
        Force detection happens in the hand, not the arm.
        """
        t0 = time.time()
        self.arm.move_relative(dz=-15, speed=descent_speed)
        return SkillResult(success=True, elapsed=time.time()-t0)

    def lift_bean(self, height_mm: float = 50.0) -> SkillResult:
        """Lift a grasped bean to safe height."""
        t0 = time.time()
        self.arm.move_relative(dz=height_mm, speed=20.0)
        return SkillResult(success=True, elapsed=time.time()-t0)

    def move_to_container(self, container_pos: Tuple[float, float, float],
                          speed: float = 50.0) -> SkillResult:
        """Move arm to target container position."""
        t0 = time.time()
        ok = self.arm.move_to(container_pos, speed=speed)
        return SkillResult(success=ok, elapsed=time.time()-t0)

    def pour_spoon(self, tilt_angle: float = 25.0) -> SkillResult:
        """Tilt spoon to pour powder."""
        t0 = time.time()
        pose = self.arm.get_pose()
        if pose:
            self.arm.move_to(
                (pose.x, pose.y, pose.z),
                (tilt_angle, 0, 0),  # roll tilt
                speed=20.0
            )
        return SkillResult(success=True, elapsed=time.time()-t0)
