#include "device_connect.h"
#include "device_connect_zenoh.h"

#include "esphome/core/log.h"

#include "esphome/components/globals/globals_component.h"
#include "esphome/components/voice_assistant/voice_assistant.h"
#ifdef USE_MICRO_WAKE_WORD
#include "esphome/components/micro_wake_word/micro_wake_word.h"
#include "esphome/components/micro_wake_word/streaming_model.h"
#endif
#include "esphome/components/media_player/media_player.h"
#include "esphome/components/light/light_state.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/select/select.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/script/script.h"

namespace esphome {
namespace device_connect {

static const char *const TAG = "device_connect";

void DeviceConnectComponent::setup() {
  if (!this->enabled_) {
    ESP_LOGI(TAG, "Device Connect disabled");
    return;
  }

  ESP_LOGI(TAG, "Device Connect voice driver starting");
  ESP_LOGI(TAG, "  device_id=%s tenant=%s stt_backend=%s", this->device_id_.c_str(), this->tenant_.c_str(),
           this->stt_backend_.c_str());
  ESP_LOGI(TAG, "  cmd: %s", this->cmd_subject().c_str());
  ESP_LOGI(TAG, "  heartbeat: %s", this->heartbeat_subject().c_str());

#ifdef USE_DEVICE_CONNECT_ZENOH
  if (this->zenoh_enabled_) {
    this->zenoh_ = new DeviceConnectZenoh(this);
    if (!this->zenoh_->start(this->zenoh_connect_, this->tenant_, this->device_id_)) {
      ESP_LOGW(TAG, "Zenoh transport failed to start — RPC/event logging only");
      delete this->zenoh_;
      this->zenoh_ = nullptr;
    }
  }
#else
  ESP_LOGW(TAG, "  Zenoh not compiled in — set zenoh_connect for future builds with zenoh-pico");
#endif
}

void DeviceConnectComponent::on_shutdown() {
#ifdef USE_DEVICE_CONNECT_ZENOH
  if (this->zenoh_ != nullptr) {
    this->zenoh_->stop();
    delete this->zenoh_;
    this->zenoh_ = nullptr;
  }
#endif
}

void DeviceConnectComponent::loop() {
  if (!this->enabled_)
    return;

#ifdef USE_DEVICE_CONNECT_ZENOH
  if (this->zenoh_ != nullptr)
    this->zenoh_->loop();
#endif

  const uint32_t now = millis();

  if (this->listen_pending_ && this->voice_assistant_ != nullptr) {
    const uint32_t elapsed = now - this->listen_started_ms_;
    if (!this->voice_assistant_->is_running() && elapsed > 500) {
      this->listen_pending_ = false;
    }
  }

  if (now - this->last_heartbeat_ms_ < 30000)
    return;
  this->last_heartbeat_ms_ = now;

  int phase = this->voice_phase_ != nullptr ? this->voice_phase_->value() : -1;
  size_t tlen = this->last_transcript_ != nullptr ? this->last_transcript_->value().size() : 0;
  ESP_LOGD(TAG, "heartbeat phase=%d (%s) transcript_len=%u zenoh=%s", phase, this->phase_name(phase), (unsigned) tlen,
           this->zenoh_connect_.empty() ? "off" : "pending");
}

void DeviceConnectComponent::on_stt_text(const std::string &text) {
  if (this->last_transcript_ != nullptr)
    this->last_transcript_->value() = text;
  ESP_LOGI(TAG, "STT: %s", text.c_str());
  this->emit_stt_event_(text);
}

void DeviceConnectComponent::on_wake_word_detected(const std::string &wake_word) {
  this->last_wake_word_ = wake_word;
  std::string model_id = "okay_nabu";
#ifdef USE_MICRO_WAKE_WORD
  if (this->micro_wake_word_ != nullptr) {
    for (auto *model : this->micro_wake_word_->get_wake_words()) {
      if (model != nullptr && model->is_enabled()) {
        model_id = model->get_id();
        break;
      }
    }
  }
#endif
  this->last_wake_model_id_ = model_id;
  this->emit_wake_word_event_(wake_word, model_id);
}

std::string DeviceConnectComponent::cmd_subject() const {
  return str_sprintf("device-connect.%s.%s.cmd", this->tenant_.c_str(), this->device_id_.c_str());
}

std::string DeviceConnectComponent::heartbeat_subject() const {
  return str_sprintf("device-connect.%s.%s.heartbeat", this->tenant_.c_str(), this->device_id_.c_str());
}

std::string DeviceConnectComponent::events_subject(const char *event_name) const {
  return str_sprintf("device-connect.%s.%s.%s", this->tenant_.c_str(), this->device_id_.c_str(), event_name);
}

const char *DeviceConnectComponent::phase_name(int phase_id) const {
  switch (phase_id) {
    case 1:
      return "idle";
    case 2:
      return "waiting_for_command";
    case 3:
      return "listening";
    case 4:
      return "thinking";
    case 5:
      return "replying";
    case 10:
      return "not_ready";
    case 11:
      return "error";
    default:
      return "unknown";
  }
}

bool DeviceConnectComponent::assistant_connected() const {
  if (this->voice_assistant_ == nullptr || this->voice_phase_ == nullptr)
    return false;
  const int phase = this->voice_phase_->value();
  return phase != 10 && phase != 11;
}

void DeviceConnectComponent::log_event(const char *event_name, const std::string &payload_json) {
  ESP_LOGI(TAG, "event %s → %s payload=%s", event_name, this->events_subject(event_name).c_str(),
           payload_json.c_str());
}

void DeviceConnectComponent::publish_mesh_event(const char *event_name, const std::string &payload_json) {
#ifdef USE_DEVICE_CONNECT_ZENOH
  if (this->zenoh_ != nullptr && this->zenoh_->is_active()) {
    const std::string subject = this->events_subject(event_name);
    if (this->zenoh_->publish(subject, payload_json)) {
      ESP_LOGD(TAG, "zenoh put %s (%u bytes)", subject.c_str(), (unsigned) payload_json.size());
      return;
    }
  }
#endif
  this->log_event(event_name, payload_json);
}

}  // namespace device_connect
}  // namespace esphome
