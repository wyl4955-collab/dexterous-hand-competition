"""
RH56F2 RS485 Protocol — pure Python implementation
Based on RH56F2 User Manual V1.0 (PRJ-02-TS-U-017)
Frame: EB 90 [ID] [Len] [Cmd] [AddrL] [AddrH] [Data...] [Checksum]
"""
import struct
from typing import List, Tuple

# ── Register addresses (F2 Manual Table 30) ──
REG = {
    'ID': 1000,          'BAUDRATE': 1001,
    'CLEAR_ERROR': 1003, 'SAVE_FLASH': 1004,
    'FACTORY_RESET': 1005,'FORCE_CALIB': 1007,
    'CURRENT_LIMIT': 1016,'STARTUP_SPEED': 1022,
    'STARTUP_FORCE': 1028,'POS_SET': 1034,
    'ANGLE_SET': 1040,   'FORCE_SET': 1046,
    'SPEED_SET': 1052,   'POS_ACTUAL': 1058,
    'ANGLE_ACTUAL': 1064,'FORCE_ACTUAL': 1070,
    'CURRENT': 1076,     'FAULT': 1082,
    'STATUS': 1088,      'TEMP': 1094,
    'FINGER_MODE': 1100, 'PAUSE': 1130,
    'EMERGENCY': 1131,   'TOUCH_BASE': 3000,
}

JOINT_NAMES = ["小指","无名指","中指","食指","拇指弯","拇指转"]
JOINT_COUNT = 6

# ── Angle limits ──
ANGLE_LIMITS = [(900,1740),(900,1740),(900,1740),(900,1740),(1100,1550),(600,1750)]

def _chk(data: bytes) -> int: return sum(data) & 0xFF

def build_read(hand_id: int, addr: int, byte_len: int) -> bytes:
    frame = bytearray([0xEB, 0x90, hand_id, 0x04, 0x11,
                       addr & 0xFF, (addr>>8) & 0xFF, byte_len])
    frame.append(_chk(frame[2:]))
    return bytes(frame)

def build_write(hand_id: int, addr: int, values: List[int]) -> bytes:
    data = bytearray()
    for v in values:
        data.append(v & 0xFF)
        data.append((v >> 8) & 0xFF)
    dlen = len(data) + 3  # cmd + addrL + addrH + data
    frame = bytearray([0xEB, 0x90, hand_id, dlen, 0x12,
                       addr & 0xFF, (addr>>8) & 0xFF])
    frame.extend(data)
    frame.append(_chk(frame[2:]))
    return bytes(frame)

def parse_response(raw: bytes, expected_addr: int) -> Tuple[bool, List[int]]:
    """Parse RS485 response. Returns (ok, [values])."""
    if len(raw) < 8: return False, []
    if raw[0] != 0x90 or raw[1] != 0xEB: return False, []
    data_len = raw[3]
    if len(raw) < 2 + data_len + 1: return False, []
    actual_cs = _chk(raw[2:2+data_len])
    if actual_cs != raw[2+data_len]: return False, []
    cmd = raw[4]
    if cmd not in (0x11, 0x12): return False, []
    addr = raw[5] | (raw[6] << 8)
    if cmd == 0x11 and addr != expected_addr: return False, []
    reg_len = data_len - 3
    values = []
    if cmd == 0x11 and reg_len > 0:
        for i in range(0, reg_len, 2):
            if i+1 < reg_len:
                values.append(raw[7+i] | (raw[7+i+1] << 8))
    return True, values

def clamp_angle(finger_idx: int, value: int) -> int:
    if value == -1: return -1
    lo, hi = ANGLE_LIMITS[finger_idx]
    return max(lo, min(hi, value))
