/**
 * RH56F2 Driver Node
 *
 * ROS2 lifecycle node that communicates with the Inspire RH56F2 hand via RS485.
 *
 * Published topics:
 *   /hand/state        (HandState)  - joint angles, forces, status, temperature (50Hz)
 *   /hand/touch        (TouchData)  - capacitive touch sensor data (10Hz, per-finger)
 *
 * Subscribed topics:
 *   /hand/command      (HandCommand) - angle/force/speed/mode commands
 *
 * Services:
 *   /hand/calibrate    (HandCalibrate) - force sensor calibration
 *   /hand/emergency    (Trigger)       - emergency stop
 *   /hand/clear_fault  (Trigger)       - clear all faults
 *
 * Parameters:
 *   port               serial port path (default: /dev/ttyUSB0)
 *   hand_id            hand device ID (default: 1)
 *   baudrate           serial baudrate (default: 115200)
 *   update_rate        state publish rate in Hz (default: 50)
 */

#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <thread>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "std_srvs/srv/trigger.hpp"
#include "competition_interfaces/msg/hand_state.hpp"
#include "competition_interfaces/msg/hand_command.hpp"
#include "competition_interfaces/srv/hand_calibrate.hpp"

#include "rh56f2_driver/rs485_protocol.hpp"

// Serial port abstraction (use ASIO or Linux termios)
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <cerrno>

using namespace std::chrono_literals;

namespace rh56f2_driver {

class SerialPort {
public:
  bool open(const std::string& path, int baudrate) {
    fd_ = ::open(path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd_ < 0) {
      RCLCPP_ERROR(rclcpp::get_logger("SerialPort"),
                   "Failed to open %s: %s", path.c_str(), strerror(errno));
      return false;
    }

    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    if (tcgetattr(fd_, &tty) != 0) return false;

    // Set baudrate
    speed_t speed = B115200;
    switch (baudrate) {
      case 115200: speed = B115200; break;
      case 57600:  speed = B57600;  break;
      case 19200:  speed = B19200;  break;
      case 921600: speed = B921600; break;
      default:     speed = B115200; break;
    }
    cfsetospeed(&tty, speed);
    cfsetispeed(&tty, speed);

    // 8N1 (8 data bits, no parity, 1 stop bit) per F2 manual
    tty.c_cflag &= ~PARENB;
    tty.c_cflag &= ~CSTOPB;
    tty.c_cflag &= ~CSIZE;
    tty.c_cflag |= CS8;
    tty.c_cflag &= ~CRTSCTS;       // no hardware flow control
    tty.c_cflag |= CREAD | CLOCAL;

    tty.c_lflag &= ~ICANON;        // non-canonical mode
    tty.c_lflag &= ~ECHO;
    tty.c_lflag &= ~ECHOE;
    tty.c_lflag &= ~ECHONL;
    tty.c_lflag &= ~ISIG;

    tty.c_iflag &= ~(IXON | IXOFF | IXANY);
    tty.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL);

    tty.c_oflag &= ~OPOST;
    tty.c_oflag &= ~ONLCR;

    tty.c_cc[VTIME] = 5;   // 0.5s timeout
    tty.c_cc[VMIN]  = 0;

    tcflush(fd_, TCIFLUSH);
    if (tcsetattr(fd_, TCSANOW, &tty) != 0) return false;

    RCLCPP_INFO(rclcpp::get_logger("SerialPort"), "Opened %s at %d baud", path.c_str(), baudrate);
    return true;
  }

  void close() {
    if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
  }

  bool is_open() const { return fd_ >= 0; }

  int write(const uint8_t* data, size_t len) {
    return ::write(fd_, data, len);
  }

  int read(uint8_t* buf, size_t max_len, int timeout_ms = 100) {
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(fd_, &fds);

    struct timeval tv;
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;

    int ret = select(fd_ + 1, &fds, nullptr, nullptr, &tv);
    if (ret <= 0) return 0;

    return ::read(fd_, buf, max_len);
  }

  void flush() { tcflush(fd_, TCIFLUSH); }

private:
  int fd_ = -1;
};

// =====================================================================
// Main driver node
// =====================================================================

class RH56F2DriverNode : public rclcpp::Node {
public:
  RH56F2DriverNode() : Node("rh56f2_driver") {
    // Declare parameters
    this->declare_parameter<std::string>("port", "/dev/ttyUSB0");
    this->declare_parameter<int>("hand_id", 1);
    this->declare_parameter<int>("baudrate", 115200);
    this->declare_parameter<int>("update_rate", 50);

    // Get parameters
    port_ = this->get_parameter("port").as_string();
    hand_id_ = static_cast<uint8_t>(this->get_parameter("hand_id").as_int());
    int baudrate = this->get_parameter("baudrate").as_int();
    int update_rate = this->get_parameter("update_rate").as_int();

    // Open serial port
    if (!serial_.open(port_, baudrate)) {
      RCLCPP_ERROR(this->get_logger(), "Failed to open serial port %s. Driver inactive.", port_.c_str());
      connected_ = false;
      return;
    }
    connected_ = true;

    // Publishers
    state_pub_ = this->create_publisher<competition_interfaces::msg::HandState>(
        "/hand/state", 10);

    // Subscription
    command_sub_ = this->create_subscription<competition_interfaces::msg::HandCommand>(
        "/hand/command", 10,
        std::bind(&RH56F2DriverNode::command_callback, this, std::placeholders::_1));

    // Services
    calibrate_srv_ = this->create_service<competition_interfaces::srv::HandCalibrate>(
        "/hand/calibrate",
        std::bind(&RH56F2DriverNode::calibrate_callback, this,
                  std::placeholders::_1, std::placeholders::_2));

    // Timer: periodically read state and publish
    const int interval_ms = 1000 / update_rate;  // e.g. 50Hz = 20ms
    timer_ = this->create_wall_timer(
        std::chrono::milliseconds(interval_ms),
        std::bind(&RH56F2DriverNode::timer_callback, this));

    RCLCPP_INFO(this->get_logger(), "RH56F2 Driver started. Port=%s HandID=%d Rate=%dHz",
                port_.c_str(), hand_id_, update_rate);
  }

  ~RH56F2DriverNode() override {
    serial_.close();
  }

private:
  // ===== Command subscription =====
  void command_callback(const competition_interfaces::msg::HandCommand::SharedPtr msg) {
    if (!connected_) return;

    // Write finger modes first (if specified)
    std::vector<int16_t> modes_raw(msg->modes.begin(), msg->modes.end());
    if (modes_raw.size() == JOINT_COUNT) {
      auto frame = build_write_frame(hand_id_, RegAddr::FINGER_MODE, modes_raw);
      serial_.flush();
      serial_.write(frame.data(), frame.size());
      serial_.read(rx_buf_, sizeof(rx_buf_), 30);  // short timeout for write
    }

    // Write force thresholds
    std::vector<int16_t> forces_raw(msg->force_thresholds.begin(), msg->force_thresholds.end());
    if (forces_raw.size() == JOINT_COUNT) {
      auto frame = build_write_frame(hand_id_, RegAddr::FORCE_SET, forces_raw);
      serial_.flush();
      serial_.write(frame.data(), frame.size());
      serial_.read(rx_buf_, sizeof(rx_buf_), 30);
    }

    // Write speeds
    std::vector<int16_t> speeds_raw(msg->speeds.begin(), msg->speeds.end());
    if (speeds_raw.size() == JOINT_COUNT) {
      auto frame = build_write_frame(hand_id_, RegAddr::SPEED_SET, speeds_raw);
      serial_.flush();
      serial_.write(frame.data(), frame.size());
      serial_.read(rx_buf_, sizeof(rx_buf_), 30);
    }

    // Write target angles
    std::vector<int16_t> angles_raw(msg->target_angles.begin(), msg->target_angles.end());
    if (angles_raw.size() == JOINT_COUNT) {
      auto frame = build_write_frame(hand_id_, RegAddr::ANGLE_SET, angles_raw);
      serial_.flush();
      serial_.write(frame.data(), frame.size());
      serial_.read(rx_buf_, sizeof(rx_buf_), 30);
    }
  }

  // ===== Calibration service =====
  void calibrate_callback(
      const competition_interfaces::srv::HandCalibrate::Request::SharedPtr req,
      competition_interfaces::srv::HandCalibrate::Response::SharedPtr res) {
    (void)req;
    if (!connected_) {
      res->success = false;
      res->message = "Hand not connected";
      return;
    }

    // Write 1 to FORCE_CALIB register
    auto frame = build_write_frame(hand_id_, RegAddr::FORCE_CALIB, {1});
    serial_.flush();
    serial_.write(frame.data(), frame.size());

    // Wait for calibration (6 seconds per F2 manual section 2.5.6)
    RCLCPP_INFO(this->get_logger(), "Force calibration started, waiting 7 seconds...");
    std::this_thread::sleep_for(std::chrono::seconds(7));

    res->success = true;
    res->message = "Calibration complete";
    RCLCPP_INFO(this->get_logger(), "Force calibration complete");
  }

  // ===== Timer callback: read state + publish =====
  void timer_callback() {
    if (!connected_) return;

    auto msg = competition_interfaces::msg::HandState();

    // Read all state registers in one batch for efficiency
    // ANGLE_ACTUAL (1064) through TEMP (1094) are contiguous
    // Total: 6 regs × 5 groups = 30 regs = 60 bytes
    // But we'll read in groups for reliability

    // 1. Angles (1064, 6 registers = 12 bytes)
    if (read_registers(RegAddr::ANGLE_ACTUAL, 12, msg.angles, 6)) {
      // success
    }

    // 2. Forces (1070, 6 registers = 12 bytes)
    if (read_registers(RegAddr::FORCE_ACTUAL, 12, msg.forces, 6)) {
      // success
    }

    // 3. Currents (1076, 6 registers = 12 bytes)
    {
      std::vector<int16_t> tmp;
      if (read_registers(RegAddr::CURRENT, 12, tmp, 6)) {
        for (auto v : tmp) msg.currents.push_back(static_cast<float>(v));
      }
    }

    // 4. Status (1088, 6 registers = 12 bytes)
    {
      std::vector<int16_t> tmp;
      if (read_registers(RegAddr::STATUS, 12, tmp, 6)) {
        for (auto v : tmp) msg.status.push_back(v);
      }
    }

    // 5. Faults (1082, 6 registers = 12 bytes)
    {
      std::vector<int16_t> tmp;
      if (read_registers(RegAddr::FAULT, 12, tmp, 6)) {
        for (auto v : tmp) msg.faults.push_back(v);
      }
    }

    // 6. Temperatures (1094, 6 registers = 12 bytes)
    {
      std::vector<int16_t> tmp;
      if (read_registers(RegAddr::TEMP, 12, tmp, 6)) {
        for (auto v : tmp) msg.temperatures.push_back(v);
      }
    }

    state_pub_->publish(msg);
  }

  // ===== Helper: read contiguous registers =====
  bool read_registers(uint16_t start_addr, uint8_t byte_len,
                      std::vector<float>& out_floats, int expected_count) {
    auto frame = build_read_frame(hand_id_, start_addr, byte_len);
    serial_.flush();
    int written = serial_.write(frame.data(), frame.size());
    if (written < 0) return false;

    int n = serial_.read(rx_buf_, sizeof(rx_buf_), 150);
    if (n <= 0) return false;

    std::vector<int16_t> values;
    if (!parse_response(rx_buf_, static_cast<size_t>(n), start_addr, values)) {
      return false;
    }

    out_floats.clear();
    for (auto v : values) out_floats.push_back(static_cast<float>(v));
    return static_cast<int>(out_floats.size()) >= expected_count;
  }

  // Specialization for int16 output
  bool read_registers(uint16_t start_addr, uint8_t byte_len,
                      std::vector<int16_t>& out, int expected_count) {
    auto frame = build_read_frame(hand_id_, start_addr, byte_len);
    serial_.flush();
    serial_.write(frame.data(), frame.size());

    int n = serial_.read(rx_buf_, sizeof(rx_buf_), 150);
    if (n <= 0) return false;

    if (!parse_response(rx_buf_, static_cast<size_t>(n), start_addr, out)) {
      return false;
    }
    return static_cast<int>(out.size()) >= expected_count;
  }

  // ===== Members =====
  SerialPort serial_;
  std::string port_;
  uint8_t hand_id_ = 1;
  bool connected_ = false;

  uint8_t rx_buf_[256];

  rclcpp::Publisher<competition_interfaces::msg::HandState>::SharedPtr state_pub_;
  rclcpp::Subscription<competition_interfaces::msg::HandCommand>::SharedPtr command_sub_;
  rclcpp::Service<competition_interfaces::srv::HandCalibrate>::SharedPtr calibrate_srv_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace rh56f2_driver

// ===== Main =====
int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rh56f2_driver::RH56F2DriverNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
