"""RH56F2 Driver — final working version"""
import struct, serial, time, rclpy
from rclpy.node import Node
from competition_interfaces.msg import HandState, HandCommand

REG = {
    'ANGLE_SET':0x410, 'FORCE_SET':0x416, 'SPEED_SET':0x41C,
    'ANGLE_ACTUAL':0x428, 'FORCE_ACTUAL':0x42E, 'CURRENT':0x434,
    'FAULT':0x43A, 'STATUS':0x440, 'TEMP':0x446,
    'FINGER_MODE':0x44C, 'FORCE_CALIB':0x3EF,
}
JOINT_COUNT = 6
LIMITS = [(900,1740),(900,1740),(900,1740),(900,1740),(1100,1550),(600,1750)]


def _cs(d): return sum(d) & 0xFF

def read_reg(ser, hid, addr, nbytes):
    """Read registers, return list of int16 values or None"""
    f = bytearray([0xEB, 0x90, hid, 4, 0x11,
                   addr & 0xFF, (addr >> 8) & 0xFF, nbytes])
    f.append(_cs(f[2:]))
    ser.reset_input_buffer()
    ser.write(bytes(f))
    time.sleep(0.04)
    raw = ser.read(200)

    if len(raw) < 8 or raw[0] != 0x90 or raw[1] != 0xEB:
        return None

    data_len = raw[3]
    cmd = raw[4]
    if cmd != 0x11:
        return None
    if len(raw) < 7 + (data_len - 3):
        return None

    reg_data_len = data_len - 3  # cmd(1) + addrL(1) + addrH(1) + data
    vals = []
    for i in range(0, reg_data_len, 2):
        if i + 1 < reg_data_len:
            vals.append(raw[7 + i] | (raw[7 + i + 1] << 8))
    return vals


def write_reg(ser, hid, addr, values):
    """Write registers"""
    data = bytearray()
    for v in values:
        data.append(v & 0xFF)
        data.append((v >> 8) & 0xFF)
    dlen = len(data) + 3
    f = bytearray([0xEB, 0x90, hid, dlen, 0x12,
                   addr & 0xFF, (addr >> 8) & 0xFF])
    f.extend(data)
    f.append(_cs(f[2:]))
    ser.reset_input_buffer()
    ser.write(bytes(f))
    time.sleep(0.04)
    raw = ser.read(100)
    return len(raw) >= 8 and raw[0] == 0x90 and raw[1] == 0xEB


def clamp(i, v):
    if v == -1: return -1
    lo, hi = LIMITS[i]
    return max(lo, min(hi, v))


class RH56F2DriverNode(Node):
    def __init__(self):
        super().__init__('rh56f2_driver')
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('hand_id', 1)
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('rate', 50)

        port = self.get_parameter('port').value
        self.hid = self.get_parameter('hand_id').value
        baud = self.get_parameter('baudrate').value
        rate = self.get_parameter('rate').value

        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
            self.get_logger().info(f'Connected: {port} ID={self.hid}')
        except Exception as e:
            self.get_logger().error(f'Serial error: {e}')
            self.ser = None
            return

        # Force calibration
        self.get_logger().info('Calibrating force sensors...')
        write_reg(self.ser, self.hid, REG['FORCE_CALIB'], [1])
        time.sleep(7)
        self.get_logger().info('Calibration done')

        self.pub = self.create_publisher(HandState, '/hand/state', 10)
        self.create_subscription(HandCommand, '/hand/command', self._on_cmd, 10)
        self.create_timer(1.0 / rate, self._pub_state)
        self.get_logger().info(f'Driver running at {rate}Hz')

    def _on_cmd(self, msg):
        if self.ser is None:
            return
        modes = [int(x) for x in msg.modes]
        forces = [int(x) for x in msg.force_thresholds]
        speeds = [int(x) for x in msg.speeds]
        angles = [clamp(i, int(x)) for i, x in enumerate(msg.target_angles)]

        if any(m != 0 for m in modes):
            write_reg(self.ser, self.hid, REG['FINGER_MODE'], modes)
        write_reg(self.ser, self.hid, REG['FORCE_SET'], forces)
        write_reg(self.ser, self.hid, REG['SPEED_SET'], speeds)
        write_reg(self.ser, self.hid, REG['ANGLE_SET'], angles)

    def _read6(self, addr):
        vals = read_reg(self.ser, self.hid, addr, JOINT_COUNT * 2)
        if vals is None:
            return None
        return [float(v) for v in vals[:JOINT_COUNT]]

    def _read6i(self, addr):
        vals = read_reg(self.ser, self.hid, addr, JOINT_COUNT * 2)
        if vals is None:
            return [0] * JOINT_COUNT
        return vals[:JOINT_COUNT]

    def _pub_state(self):
        if self.ser is None:
            return
        msg = HandState()
        angles = self._read6(REG['ANGLE_ACTUAL'])
        forces = self._read6(REG['FORCE_ACTUAL'])
        currents = self._read6(REG['CURRENT'])
        status = self._read6i(REG['STATUS'])
        faults = self._read6i(REG['FAULT'])
        temps = self._read6(REG['TEMP'])

        if angles is None:
            return  # skip this cycle if read fails

        msg.angles = angles
        msg.forces = [f if f is not None else 0.0 for f in (forces or [0]*6)]
        msg.currents = currents or [0.0]*6
        msg.status = status
        msg.faults = faults
        msg.temperatures = temps or [0.0]*6
        self.pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(RH56F2DriverNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
