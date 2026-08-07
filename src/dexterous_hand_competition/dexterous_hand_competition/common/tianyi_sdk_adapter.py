"""ROS2 adapter for Tianyi Pro 2.0 body motion topics.

This module is intentionally imported only on the robot x86 controller, where
the vendor ``bodyctrl_msgs`` package is installed. Windows development does not
provide or emulate that package.
"""

from collections.abc import Mapping
import math
import time

from bodyctrl_msgs.msg import (
    CmdSetMotorPosition,
    MotorStatusMsg,
    SetMotorPosition,
)
from rclpy.node import Node

from .config_loader import (
    ConfigurationError,
    load_yaml,
    require_keys,
)
from .robot_state import JointSample, RobotState


_GROUP_JOINT_IDS = {
    'arm': frozenset(range(11, 18)) | frozenset(range(21, 28)),
    'waist': frozenset({31, 32}),
    'leg': frozenset({51, 52}),
}

# Mechanical limits from the Tianyi Pro 2.0 SDK document, converted to rad.
_SDK_JOINT_LIMITS_RAD = {
    11: (math.radians(-170.0), math.radians(170.0)),
    12: (math.radians(-15.0), math.radians(150.0)),
    13: (math.radians(-170.0), math.radians(170.0)),
    14: (math.radians(-150.0), math.radians(15.0)),
    15: (math.radians(-170.0), math.radians(170.0)),
    16: (math.radians(-45.0), math.radians(60.0)),
    17: (math.radians(-95.0), math.radians(75.0)),
    21: (math.radians(-170.0), math.radians(170.0)),
    22: (math.radians(-150.0), math.radians(15.0)),
    23: (math.radians(-170.0), math.radians(170.0)),
    24: (math.radians(-150.0), math.radians(15.0)),
    25: (math.radians(-170.0), math.radians(170.0)),
    26: (math.radians(-45.0), math.radians(60.0)),
    27: (math.radians(-75.0), math.radians(95.0)),
    31: (math.radians(-160.0), math.radians(180.0)),
    32: (math.radians(-45.0), math.radians(120.0)),
    51: (math.radians(-13.0), math.radians(80.0)),
    52: (math.radians(-26.0), math.radians(160.0)),
}

_TOPIC_KEYS = {
    'arm': ('arm_status', 'arm_command'),
    'waist': ('waist_status', 'waist_command'),
    'leg': ('leg_status', 'leg_command'),
}


class TianyiSdkAdapter:
    """Translate verified Tianyi ROS2 messages to project abstractions."""

    def __init__(
        self,
        node: Node,
        robot_state: RobotState,
        config_path: str,
        dry_run: bool | None = None,
    ):
        self._node = node
        self._robot_state = robot_state

        config = load_yaml(config_path)
        require_keys(
            config,
            ['topics', 'joint_profiles'],
            'Tianyi SDK config',
        )
        configured_dry_run = config.get('dry_run', True)
        if not isinstance(configured_dry_run, bool):
            raise ConfigurationError('Tianyi SDK dry_run must be a boolean')
        real_command_enabled = config.get('real_command_enabled', False)
        if not isinstance(real_command_enabled, bool):
            raise ConfigurationError(
                'Tianyi SDK real_command_enabled must be a boolean'
            )

        if dry_run is not None:
            if not isinstance(dry_run, bool):
                raise ConfigurationError('dry_run override must be a boolean')
            self._dry_run = dry_run
        elif node.has_parameter('dry_run'):
            parameter_dry_run = node.get_parameter('dry_run').value
            if not isinstance(parameter_dry_run, bool):
                raise ConfigurationError(
                    'ROS parameter dry_run must be a boolean'
                )
            self._dry_run = parameter_dry_run
        else:
            self._dry_run = configured_dry_run

        self._real_command_enabled = real_command_enabled
        if not isinstance(config['topics'], dict):
            raise ConfigurationError('Tianyi SDK topics must be a mapping')
        require_keys(
            config['topics'],
            [key for keys in _TOPIC_KEYS.values() for key in keys],
            'Tianyi SDK topics',
        )
        if not isinstance(config['joint_profiles'], dict):
            raise ConfigurationError(
                'Tianyi SDK joint_profiles must be a mapping'
            )

        self._joint_profiles = config['joint_profiles']
        self._publishers = {}
        self._subscriptions = []

        for group, (status_key, command_key) in _TOPIC_KEYS.items():
            status_topic = config['topics'][status_key]
            command_topic = config['topics'][command_key]
            if not isinstance(status_topic, str) or not status_topic:
                raise ConfigurationError(
                    f'Tianyi SDK topic {status_key} must be a non-empty string'
                )
            if not isinstance(command_topic, str) or not command_topic:
                raise ConfigurationError(
                    f'Tianyi SDK topic {command_key} must be a '
                    'non-empty string'
                )

            subscription = node.create_subscription(
                MotorStatusMsg,
                status_topic,
                lambda message, group_name=group: self._status_callback(
                    group_name,
                    message,
                ),
                10,
            )
            self._subscriptions.append(subscription)
            self._publishers[group] = node.create_publisher(
                CmdSetMotorPosition,
                command_topic,
                10,
            )

        # TODO_REAL_ROBOT: verify status/command QoS and status update rates on
        # the robot x86 before enabling real commands.

    @property
    def dry_run(self) -> bool:
        """Return the immutable command-gating mode selected at startup."""
        return self._dry_run

    def _status_callback(self, group: str, message: MotorStatusMsg):
        received_sec = time.monotonic()
        allowed_ids = _GROUP_JOINT_IDS[group]
        for status in message.status:
            joint_id = int(status.name)
            if joint_id not in allowed_ids:
                self._node.get_logger().warning(
                    f'Ignoring joint {joint_id} received on '
                    f'{group} status topic'
                )
                continue
            self._robot_state.update_joint(
                joint_id,
                JointSample(
                    position_rad=float(status.pos),
                    speed_rad_s=float(status.speed),
                    current=float(status.current),
                    temperature_c=float(status.temperature),
                    error_code=int(status.error),
                    stamp_sec=received_sec,
                ),
            )

    def publish_arm_positions(self, targets: Mapping[int, float]) -> bool:
        return self._publish_positions('arm', targets)

    def publish_waist_positions(self, targets: Mapping[int, float]) -> bool:
        return self._publish_positions('waist', targets)

    def publish_leg_positions(self, targets: Mapping[int, float]) -> bool:
        return self._publish_positions('leg', targets)

    def _publish_positions(
        self,
        group: str,
        targets: Mapping[int, float],
    ) -> bool:
        if self._dry_run:
            self._node.get_logger().warning(
                f'dry_run blocked {group} position command publication'
            )
            return False
        if not self._real_command_enabled:
            self._node.get_logger().error(
                'real_command_enabled is false; refusing real SDK command'
            )
            return False
        if not targets:
            self._node.get_logger().error(
                f'Refusing empty {group} position command'
            )
            return False

        allowed_ids = _GROUP_JOINT_IDS[group]
        validated_targets = []

        for raw_joint_id, raw_position in targets.items():
            try:
                joint_id = int(raw_joint_id)
                position = float(raw_position)
            except (TypeError, ValueError, OverflowError):
                self._node.get_logger().error(
                    f'Invalid {group} joint ID or position'
                )
                return False
            if joint_id not in allowed_ids:
                self._node.get_logger().error(
                    f'Joint {joint_id} does not belong to {group}'
                )
                return False
            if not math.isfinite(position):
                self._node.get_logger().error(
                    f'Joint {joint_id} position is not finite'
                )
                return False

            lower, upper = _SDK_JOINT_LIMITS_RAD[joint_id]
            if position < lower or position > upper:
                self._node.get_logger().error(
                    f'Joint {joint_id} target {position:.6f} rad is outside '
                    f'SDK mechanical limits [{lower:.6f}, {upper:.6f}] rad; '
                    'command rejected without clamping'
                )
                return False

            profile = self._joint_profiles.get(str(joint_id))
            if not isinstance(profile, dict):
                self._node.get_logger().error(
                    f'Joint {joint_id} has no calibrated SDK command profile'
                )
                return False
            try:
                speed = float(profile['spd_rad_s'])
                current = float(profile['cur_a'])
            except (KeyError, TypeError, ValueError):
                self._node.get_logger().error(
                    f'Joint {joint_id} has invalid spd_rad_s or cur_a'
                )
                return False
            if not math.isfinite(speed) or speed <= 0.0:
                self._node.get_logger().error(
                    f'Joint {joint_id} speed must be finite and positive'
                )
                return False
            if not math.isfinite(current) or current <= 0.0:
                self._node.get_logger().error(
                    f'Joint {joint_id} current must be finite and positive'
                )
                return False

            validated_targets.append((joint_id, position, speed, current))

        command = CmdSetMotorPosition()
        command.header.stamp = self._node.get_clock().now().to_msg()
        for joint_id, position, speed, current in validated_targets:
            motor_command = SetMotorPosition()
            motor_command.name = joint_id
            motor_command.pos = position
            motor_command.spd = speed
            motor_command.cur = current
            command.cmds.append(motor_command)

        self._publishers[group].publish(command)
        # A successful return only means the locally validated ROS publisher
        # accepted the message; the Tianyi SDK does not provide an ACK here.
        return True

    # TODO_REAL_ROBOT: confirm whether cmd_pos is one-shot or must be streamed.
    # TODO_REAL_ROBOT: no verified stop/hold SDK interface is documented; do
    # not invent one.
