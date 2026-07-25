#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace rh56f2_driver {

/**
 * RH56F2 RS485 Protocol Encoder/Decoder
 *
 * Based on RH56F2 User Manual V1.0 (PRJ-02-TS-U-017)
 *
 * Frame format:
 *   Read request:  EB 90 [ID] 04 11 [AddrL] [AddrH] [Len] [Checksum]
 *   Read response: 90 EB [ID] [Len+3] 11 [AddrL] [AddrH] [Data...] [Checksum]
 *   Write request: EB 90 [ID] [DataLen+3] 12 [AddrL] [AddrH] [Data...] [Checksum]
 *   Write response: 90 EB [ID] 04 12 [AddrL] [AddrH] 01 [Checksum]
 */

// Register addresses (from F2 manual Table 30)
namespace RegAddr {
  constexpr uint16_t ID              = 1000;  // Hand ID (1-254)
  constexpr uint16_t BAUDRATE        = 1001;  // Baud rate (0-3)
  constexpr uint16_t CLEAR_ERROR     = 1003;  // Clear fault
  constexpr uint16_t SAVE_FLASH      = 1004;  // Save params to flash
  constexpr uint16_t FACTORY_RESET   = 1005;  // Factory reset
  constexpr uint16_t FORCE_CALIB     = 1007;  // Force sensor calibration
  constexpr uint16_t CURRENT_LIMIT   = 1016;  // Current limit (6 regs)
  constexpr uint16_t STARTUP_SPEED   = 1022;  // Startup speed (6 regs)
  constexpr uint16_t STARTUP_FORCE   = 1028;  // Startup force (6 regs)
  constexpr uint16_t POS_SET         = 1034;  // Cylinder position set (6 regs)
  constexpr uint16_t ANGLE_SET       = 1040;  // Angle set (6 regs)
  constexpr uint16_t FORCE_SET       = 1046;  // Force threshold set (6 regs)
  constexpr uint16_t SPEED_SET       = 1052;  // Speed set (6 regs)
  constexpr uint16_t POS_ACTUAL      = 1058;  // Cylinder position actual (6 regs)
  constexpr uint16_t ANGLE_ACTUAL    = 1064;  // Angle actual (6 regs)
  constexpr uint16_t FORCE_ACTUAL    = 1070;  // Fingertip force actual (6 regs)
  constexpr uint16_t CURRENT         = 1076;  // Motor current (6 regs)
  constexpr uint16_t FAULT           = 1082;  // Fault info (6 regs)
  constexpr uint16_t STATUS          = 1088;  // Status info (6 regs)
  constexpr uint16_t TEMP            = 1094;  // Motor temperature (6 regs)
  constexpr uint16_t FINGER_MODE     = 1100;  // Finger mode (6 regs)
  constexpr uint16_t PAUSE           = 1130;  // Pause
  constexpr uint16_t EMERGENCY       = 1131;  // Emergency stop
  constexpr uint16_t TOUCH_BASE      = 3000;  // Capacitive touch sensor base
}

// Frame constants
constexpr uint8_t FRAME_HEADER1 = 0xEB;
constexpr uint8_t FRAME_HEADER2 = 0x90;
constexpr uint8_t RSP_HEADER1   = 0x90;
constexpr uint8_t RSP_HEADER2   = 0xEB;
constexpr uint8_t CMD_READ      = 0x11;
constexpr uint8_t CMD_WRITE     = 0x12;

// Angle limits (from F2 manual Table 35-36)
// Four fingers: 900-1740 (90°-174°), Thumb bend: 1100-1550, Thumb rotate: 600-1750
constexpr int16_t ANGLE_FINGER_MIN = 900;
constexpr int16_t ANGLE_FINGER_MAX = 1740;
constexpr int16_t ANGLE_THUMB_BEND_MIN = 1100;
constexpr int16_t ANGLE_THUMB_BEND_MAX = 1550;
constexpr int16_t ANGLE_THUMB_ROTATE_MIN = 600;
constexpr int16_t ANGLE_THUMB_ROTATE_MAX = 1750;

// Force limits
constexpr int16_t FORCE_FINGER_MAX = 1000;
constexpr int16_t FORCE_THUMB_MAX  = 1200;

// Speed limits
constexpr int16_t SPEED_MAX = 4000;

// Number of fingers/joints
constexpr int JOINT_COUNT = 6;
// Finger names: 0=little, 1=ring, 2=middle, 3=index, 4=thumb_bend, 5=thumb_rotate

/**
 * Build RS485 read-register frame
 * @param hand_id  Hand ID (1-254)
 * @param reg_addr Register start address
 * @param byte_len Number of bytes to read
 * @return Complete frame bytes
 */
std::vector<uint8_t> build_read_frame(uint8_t hand_id, uint16_t reg_addr, uint8_t byte_len);

/**
 * Build RS485 write-register frame
 * @param hand_id  Hand ID (1-254)
 * @param reg_addr Register start address
 * @param values   Register values to write (each is INT16, packed as [low, high])
 * @return Complete frame bytes
 */
std::vector<uint8_t> build_write_frame(uint8_t hand_id, uint16_t reg_addr,
                                       const std::vector<int16_t>& values);

/**
 * Parse RS485 response frame
 * @param raw      Raw bytes received from serial port
 * @param len      Number of bytes received
 * @param expected_addr Expected register address (for verification)
 * @param out_data Output: parsed register values (INT16 each)
 * @return true if parsed successfully, false if invalid
 */
bool parse_response(const uint8_t* raw, size_t len, uint16_t expected_addr,
                    std::vector<int16_t>& out_data);

/**
 * Calculate checksum: sum of all bytes after header, take lower 8 bits
 */
uint8_t checksum(const uint8_t* data, size_t len);

/**
 * Parse an INT16 from two bytes (low byte first per F2 protocol)
 */
inline int16_t parse_int16_le(const uint8_t* data) {
  return static_cast<int16_t>(data[0] | (data[1] << 8));
}

/**
 * Pack an INT16 into two bytes (low byte first per F2 protocol)
 */
inline void pack_int16_le(int16_t value, uint8_t* out) {
  out[0] = static_cast<uint8_t>(value & 0xFF);
  out[1] = static_cast<uint8_t>((value >> 8) & 0xFF);
}

}  // namespace rh56f2_driver
