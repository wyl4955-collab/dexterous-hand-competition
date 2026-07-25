#!/usr/bin/env python3
"""
RH56F2 Driver Node — ROS2 Python node for RH56F2 hand over RS485.
Publishes /hand/state at 50Hz, subscribes to /hand/command.
"""
import serial
import time
import rclpy
from rclpy.node import Node
from competition_interfaces.msg import HandState, HandCommand
from .rh56f2_protocol import (REG, JOINT_COUNT, build_read, build_write,
                               parse_response, clamp_angle)

class RH56F2DriverNode(Node):
    def __init__(self):
        super().__init__('rh56f2_driver')
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('hand_id', 1)
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('rate', 50)

        port = self.get_parameter('port').value
        self.hand_id = self.get_parameter('hand_id').value
        baud = self.get_parameter('baudrate').value
        rate = self.get_parameter('rate').value

        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
            self.get_logger().info(f'RH56F2 connected: {port} ID={self.hand_id}')
        except Exception as e:
            self.get_logger().error(f'Serial open failed: {e}')
            self.ser = None
            return

        # Force calibration on startup (hand must be empty!)
        self._write_reg(REG['FORCE_CALIB'], [1])
        self.get_logger().info('Calibrating force sensors (6s)...')
        time.sleep(7)

        self.state_pub = self.create_publisher(HandState, '/hand/state', 10)
        self.cmd_sub = self.create_subscription(
            HandCommand, '/hand/command', self._on_command, 10)
        self.timer = self.create_timer(1.0/rate, self._publish_state)

        self.get_logger().info(f'Driver running at {rate}Hz')

    def _send(self, frame: bytes) -> bytes:
        if self.ser is None: return b''
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        time.sleep(0.03)
        return self.ser.read(200)

    def _read_reg(self, addr: int, nbytes: int) -> list:
        raw = self._send(build_read(self.hand_id, addr, nbytes))
        ok, vals = parse_response(raw, addr)
        return vals if ok else []

    def _write_reg(self, addr: int, values: list) -> bool:
        raw = self._send(build_write(self.hand_id, addr, values))
        ok, _ = parse_response(raw, addr)
        return ok

    def _on_command(self, msg: HandCommand):
        # Write modes, forces, speeds, then angles
        modes = [int(m) for m in msg.modes]
        forces = [int(f) for f in msg.force_thresholds]
        speeds = [int(s) for s in msg.speeds]
        angles = [clamp_angle(i, int(a)) for i, a in enumerate(msg.target_angles)]

        if any(m != 0 for m in modes):
            self._write_reg(REG['FINGER_MODE'], modes)
        self._write_reg(REG['FORCE_SET'], forces)
        self._write_reg(REG['SPEED_SET'], speeds)
        self._write_reg(REG['ANGLE_SET'], angles)

    def _read_group(self, addr: int, floats: bool = True) -> list:
        vals = self._read_reg(addr, JOINT_COUNT * 2)
        if floats:
            return [float(v) for v in vals[:JOINT_COUNT]]
        return vals[:JOINT_COUNT]

    def _publish_state(self):
        if self.ser is None: return
        msg = HandState()
        msg.angles = self._read_group(REG['ANGLE_ACTUAL'])
        msg.forces = self._read_group(REG['FORCE_ACTUAL'])
        msg.currents = self._read_group(REG['CURRENT'])
        msg.status = self._read_group(REG['STATUS'], floats=False)
        msg.faults = self._read_group(REG['FAULT'], floats=False)
        msg.temperatures = self._read_group(REG['TEMP'])
        self.state_pub.publish(msg)

def main():
    rclpy.init()
    node = RH56F2DriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
