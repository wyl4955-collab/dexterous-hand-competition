#include "rh56f2_driver/rs485_protocol.hpp"
#include <numeric>

namespace rh56f2_driver {

uint8_t checksum(const uint8_t* data, size_t len) {
  return static_cast<uint8_t>(std::accumulate(data, data + len, 0) & 0xFF);
}

std::vector<uint8_t> build_read_frame(uint8_t hand_id, uint16_t reg_addr, uint8_t byte_len) {
  std::vector<uint8_t> frame = {
    FRAME_HEADER1,
    FRAME_HEADER2,
    hand_id,
    0x04,                     // data length (fixed for read)
    CMD_READ,
    static_cast<uint8_t>(reg_addr & 0xFF),       // addr low
    static_cast<uint8_t>((reg_addr >> 8) & 0xFF), // addr high
    byte_len,                                     // bytes to read
  };
  // Checksum over bytes[2..7] (after headers)
  frame.push_back(checksum(frame.data() + 2, 6));
  return frame;
}

std::vector<uint8_t> build_write_frame(uint8_t hand_id, uint16_t reg_addr,
                                       const std::vector<int16_t>& values) {
  const uint8_t data_byte_len = static_cast<uint8_t>(values.size() * 2);  // 2 bytes per INT16

  std::vector<uint8_t> frame = {
    FRAME_HEADER1,
    FRAME_HEADER2,
    hand_id,
    static_cast<uint8_t>(data_byte_len + 3),   // data length = values + 3 (cmd+addrH+addrL)
    CMD_WRITE,
    static_cast<uint8_t>(reg_addr & 0xFF),
    static_cast<uint8_t>((reg_addr >> 8) & 0xFF),
  };

  // Pack INT16 values (low byte first)
  for (int16_t v : values) {
    frame.push_back(static_cast<uint8_t>(v & 0xFF));        // low byte
    frame.push_back(static_cast<uint8_t>((v >> 8) & 0xFF)); // high byte
  }

  // Checksum over bytes[2..end]
  frame.push_back(checksum(frame.data() + 2, frame.size() - 2));
  return frame;
}

bool parse_response(const uint8_t* raw, size_t len, uint16_t expected_addr,
                    std::vector<int16_t>& out_data) {
  out_data.clear();

  // Minimum frame: 90 EB [ID] [Len] [Cmd] [AddrL] [AddrH] [Checksum] = 8 bytes
  if (len < 8) return false;

  // Verify header
  if (raw[0] != RSP_HEADER1 || raw[1] != RSP_HEADER2) return false;

  // Verify checksum
  const uint8_t data_len = raw[3];  // frame data length field
  const size_t frame_payload_start = 2;  // checksum starts from byte[2] (after headers)
  const size_t frame_total = 2 + data_len + 1;  // headers + data + checksum
  if (len < frame_total) return false;

  const uint8_t expected_cs = checksum(raw + frame_payload_start, data_len + 1 - 1); // cmd+addr+any_data
  // Checksum is: sum of bytes[2] through byte[2+data_len-1] (i.e. data_len bytes after headers)
  // Actually from the manual: checksum = sum(bytes from byte[2] to byte[2+data_len-1]) & 0xFF
  // Wait, let me re-check: data_len is the value at byte[3]
  // Frame: [90][EB][ID][data_len][cmd][addrL][addrH]...[data...][checksum]
  // Payload for checksum: from byte[2] (ID) to byte[2+data_len-1] (last data byte)
  const uint8_t actual_cs = checksum(raw + 2, data_len);

  // The checksum in the frame is at position 2 + data_len
  if (actual_cs != raw[2 + data_len]) return false;

  // Verify command
  const uint8_t cmd = raw[4];
  if (cmd != CMD_READ && cmd != CMD_WRITE) return false;

  // Verify address
  const uint16_t addr = static_cast<uint16_t>(raw[5]) | (static_cast<uint16_t>(raw[6]) << 8);
  // Don't strictly check address for write responses (address may differ slightly in special cases)
  // For read responses, verify
  if (cmd == CMD_READ && addr != expected_addr) return false;

  // Parse data: for read responses, data starts at byte[7]
  // data_len includes: [cmd(1)] + [addrL(1)] + [addrH(1)] + [register_data(N)]
  // so register data length = data_len - 3
  const int reg_data_len = static_cast<int>(data_len) - 3;

  if (cmd == CMD_READ && reg_data_len > 0) {
    const uint8_t* data_start = raw + 7;
    for (int i = 0; i + 1 < reg_data_len; i += 2) {
      out_data.push_back(parse_int16_le(data_start + i));
    }
  }

  return true;
}

}  // namespace rh56f2_driver
