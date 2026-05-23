#pragma once

#include <cstdint>
#include <string>

namespace esphome {
namespace device_connect {

class DeviceConnectComponent;

/// Zenoh-pico transport for Device Connect LAN mesh (Phase 1b).
class DeviceConnectZenoh {
 public:
  explicit DeviceConnectZenoh(DeviceConnectComponent *parent);

  bool start(const std::string &zenoh_connect, const std::string &tenant, const std::string &device_id);
  void stop();
  void loop();

  bool is_active() const { return this->active_; }

  bool publish(const std::string &subject, const std::string &payload);
  bool publish_heartbeat();

  /// Dispatch JSON-RPC (used by Zenoh query/sample handlers).
  bool handle_command(const std::string &request_json, std::string &response_json);

  static std::string subject_to_keyexpr(const std::string &subject);

 protected:
  DeviceConnectComponent *parent_;
  std::string tenant_;
  std::string device_id_;
  std::string cmd_key_;
  std::string heartbeat_key_;
  bool active_{false};
  uint32_t last_heartbeat_ms_{0};
};

}  // namespace device_connect
}  // namespace esphome
