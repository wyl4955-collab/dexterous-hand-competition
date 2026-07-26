"""RH56F2 Driver — production version"""
import struct, serial, time, rclpy
from rclpy.node import Node
from competition_interfaces.msg import HandState, HandCommand

# Register addresses (from F2 manual table 30, shifted to hex as used in frames)
REG = {
    'ANGLE_SET': 0x410,   # 1040
    'FORCE_SET': 0x416,   # 1046
    'SPEED_SET': 0x41C,   # 1052
    'ANGLE_ACTUAL': 0x428,  # 1064
    'FORCE_ACTUAL': 0x42E,  # 1070
    'CURRENT': 0x434,     # 1076
    'FAULT': 0x43A,        # 1082
    'STATUS': 0x440,       # 1088
    'TEMP': 0x446,          # 1094
    'FINGER_MODE': 0x44C,   # 1100
    'FORCE_CALIB': 0x3EF,   # 1007
}
JOINT_COUNT = 6
LIMITS = [(900, 1740), (900, 1740), (900, 1740), (900, 1740), (1100, 1550), (600, 1750)]


def _cs(d): return sum(d) & 0xFF


def read_reg(ser, hid, addr, nbytes):
    """Read registers, return signed int16 values or None."""
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

    reg_data_len = data_len - 3
    vals = []
    for i in range(0, reg_data_len, 2):
        if i + 1 < reg_data_len:
            raw_val = raw[7 + i] | (raw[7 + i + 1] << 8)
            # Convert to signed INT16 (fixes 65534 → -2)
            if raw_val >= 0x8000:
                raw_val -= 0x10000
            vals.append(raw_val)
    return vals


def write_reg(ser, hid, addr, values):
    """Write registers. Returns True on success."""
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
        self.declare_parameter('rate', 20)  # 20Hz is realistic for RS485

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

        # Cache last written values to avoid redundant writes
        self._last_force = None
        self._last_speed = None
        self._last_mode = None

        self._consecutive_failures = 0

        self.pub = self.create_publisher(HandState, '/hand/state', 10)
        self.create_subscription(HandCommand, '/hand/command', self._on_cmd, 10)
        self.create_timer(1.0 / rate, self._pub_state)
        self.get_logger().info(f'Driver running at ~{rate}Hz')

    def _on_cmd(self, msg):
        if self.ser is None:
            return

        modes = [int(x) for x in msg.modes]
        forces = [int(x) for x in msg.force_thresholds]
        speeds = [int(x) for x in msg.speeds]
        angles = [clamp(i, int(x)) for i, x in enumerate(msg.target_angles)]

        # Only write force/speed/mode when they change
        if modes != self._last_mode and any(m != 0 for m in modes):
            write_reg(self.ser, self.hid, REG['FINGER_MODE'], modes)
            self._last_mode = modes

        if forces != self._last_force:
            write_reg(self.ser, self.hid, REG['FORCE_SET'], forces)
            self._last_force = forces

        if speeds != self._last_speed:
            write_reg(self.ser, self.hid, REG['SPEED_SET'], speeds)
            self._last_speed = speeds

        # Always write angles (they change every command)
        write_reg(self.ser, self.hid, REG['ANGLE_SET'], angles)

    def _read6_signed(self, addr):
        """Read 6 signed INT16 values as floats."""
        vals = read_reg(self.ser, self.hid, addr, JOINT_COUNT * 2)
        if vals is None:
            return None
        return [float(v) for v in vals[:JOINT_COUNT]]

    def _read6_raw(self, addr):
        """Read 6 raw INT16 values (no sign conversion, for status/faults)."""
        vals = read_reg(self.ser, self.hid, addr, JOINT_COUNT * 2)
        if vals is None:
            return None
        return vals[:JOINT_COUNT]

    def _pub_state(self):
        if self.ser is None:
            return

        # Read all 5 register groups
        angles = self._read6_signed(REG['ANGLE_ACTUAL'])
        forces = self._read6_signed(REG['FORCE_ACTUAL'])
        currents = self._read6_signed(REG['CURRENT'])
        status = self._read6_raw(REG['STATUS'])
        faults = self._read6_raw(REG['FAULT'])
        temps = self._read6_signed(REG['TEMP'])

        # If any read failed, increment failure counter
        if any(x is None for x in [angles, forces, currents, status, faults, temps]):
            self._consecutive_failures += 1
            if self._consecutive_failures <= 3:
                return  # occasional drop is OK, skip this frame
            # After 3 consecutive failures, publish whatever we have
        else:
            self._consecutive_failures = 0

        msg = HandState()
        msg.angles = angles if angles is not None else [0.0] * JOINT_COUNT
        msg.forces = forces if forces is not None else [0.0] * JOINT_COUNT
        msg.currents = currents if currents is not None else [0.0] * JOINT_COUNT
        msg.status = status if status is not None else [-1] * JOINT_COUNT
        msg.faults = faults if faults is not None else [-1] * JOINT_COUNT
        msg.temperatures = temps if temps is not None else [0.0] * JOINT_COUNT
        self.pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(RH56F2DriverNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
