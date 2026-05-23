#pragma once

#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "esphome/core/automation.h"

#include <string>

namespace esphome::globals {
template<typename T> class GlobalsComponent;
}
namespace esphome::voice_assistant {
class VoiceAssistant;
}
namespace esphome::micro_wake_word {
class MicroWakeWord;
class WakeWordModel;
}
namespace esphome::media_player {
class MediaPlayer;
enum MediaPlayerState : uint8_t;
}
namespace esphome::light {
class LightState;
}
namespace esphome::switch_ {
class Switch;
}
namespace esphome::select {
class Select;
}
namespace esphome::binary_sensor {
class BinarySensor;
}
namespace esphome::script {
template<typename... Ts> class Script;
}

namespace esphome {
namespace device_connect {

class DeviceConnectZenoh;

/// Device Connect whisper driver on Home Assistant Voice PE.
///
/// Phase 1: JSON-RPC dispatch + ESPHome bindings (voice_assistant, micro_wake_word, LEDs, …).
/// Phase 1b: zenoh-pico transport on ``device-connect.{tenant}.{device_id}.*`` subjects.
class DeviceConnectComponent : public Component {
 public:
  void setup() override;
  void loop() override;
  void on_shutdown() override;
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

  void set_device_id(const std::string &id) { this->device_id_ = id; }
  void set_tenant(const std::string &tenant) { this->tenant_ = tenant; }
  void set_enabled(bool enabled) { this->enabled_ = enabled; }
  void set_zenoh_connect(const std::string &url) { this->zenoh_connect_ = url; }
  void set_stt_backend(const std::string &backend) { this->stt_backend_ = backend; }
  void set_zenoh_enabled(bool enabled) { this->zenoh_enabled_ = enabled; }

  void set_voice_phase(globals::GlobalsComponent<int> *g) { this->voice_phase_ = g; }
  void set_last_transcript(globals::GlobalsComponent<std::string> *g) { this->last_transcript_ = g; }
  void set_color_changed(globals::GlobalsComponent<bool> *g) { this->color_changed_ = g; }

  void set_voice_assistant(voice_assistant::VoiceAssistant *va) { this->voice_assistant_ = va; }
  void set_micro_wake_word(micro_wake_word::MicroWakeWord *mww) { this->micro_wake_word_ = mww; }
  void set_wake_word_sensitivity(select::Select *sel) { this->wake_word_sensitivity_ = sel; }
  void set_center_button(binary_sensor::BinarySensor *btn) { this->center_button_ = btn; }
  void set_master_mute(switch_::Switch *sw) { this->master_mute_ = sw; }
  void set_media_player(media_player::MediaPlayer *mp) { this->media_player_ = mp; }
  void set_led_light(light::LightState *light) { this->led_light_ = light; }

  void set_control_volume_script(script::Script<bool> *script) { this->control_volume_script_ = script; }
  void set_control_leds_script(script::Script<> *script) { this->control_leds_script_ = script; }
  void set_play_sound_script(script::Script<bool, std::string> *script) { this->play_sound_script_ = script; }

  /// JSON-RPC 2.0 request body → response body (for API action / future Zenoh .cmd subscriber).
  bool handle_rpc(const std::string &request_json, std::string &response_json);

  /// Called from voice_assistant ``on_stt_end`` / micro_wake_word hooks in YAML.
  void on_stt_text(const std::string &text);
  void on_wake_word_detected(const std::string &wake_word);

 protected:
  std::string cmd_subject() const;
  std::string heartbeat_subject() const;
  std::string events_subject(const char *event_name) const;

  const char *phase_name(int phase_id) const;
  bool assistant_connected() const;

  bool dispatch_method(const std::string &method, const char *params_json, const std::string &rpc_id,
                       std::string &response_json);

  void log_event(const char *event_name, const std::string &payload_json);
  void publish_mesh_event(const char *event_name, const std::string &payload_json);
  void emit_stt_event_(const std::string &text);
  void emit_wake_word_event_(const std::string &wake_word, const std::string &model_id);
  void emit_volume_event_(float volume, bool muted);
  void emit_led_event_();
  void emit_button_event_(const std::string &press_type);

  micro_wake_word::WakeWordModel *find_wake_model_(const std::string &model_id);
  std::string sensitivity_slug_() const;
  bool set_sensitivity_slug_(const std::string &slug);

  std::string device_id_;
  std::string tenant_{"default"};
  std::string zenoh_connect_;
  std::string stt_backend_{"voice_assistant"};
  bool enabled_{true};
  bool zenoh_enabled_{true};
#ifdef USE_DEVICE_CONNECT_ZENOH
  DeviceConnectZenoh *zenoh_{nullptr};
#endif

  globals::GlobalsComponent<int> *voice_phase_{nullptr};
  globals::GlobalsComponent<std::string> *last_transcript_{nullptr};
  globals::GlobalsComponent<bool> *color_changed_{nullptr};

  voice_assistant::VoiceAssistant *voice_assistant_{nullptr};
  micro_wake_word::MicroWakeWord *micro_wake_word_{nullptr};
  select::Select *wake_word_sensitivity_{nullptr};
  binary_sensor::BinarySensor *center_button_{nullptr};
  switch_::Switch *master_mute_{nullptr};
  media_player::MediaPlayer *media_player_{nullptr};
  light::LightState *led_light_{nullptr};

  script::Script<bool> *control_volume_script_{nullptr};
  script::Script<> *control_leds_script_{nullptr};
  script::Script<bool, std::string> *play_sound_script_{nullptr};

  uint32_t last_heartbeat_ms_{0};
  std::string last_button_event_;
  std::string last_wake_word_;
  std::string last_wake_model_id_;
  bool listen_pending_{false};
  uint32_t listen_started_ms_{0};
};

}  // namespace device_connect
}  // namespace esphome
