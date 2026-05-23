#include "device_connect.h"

#include "esphome/core/log.h"

#include "esphome/components/globals/globals_component.h"
#include "esphome/components/voice_assistant/voice_assistant.h"
#ifdef USE_MICRO_WAKE_WORD
#include "esphome/components/micro_wake_word/micro_wake_word.h"
#include "esphome/components/micro_wake_word/streaming_model.h"
#endif
#include "esphome/components/media_player/media_player.h"
#include "esphome/components/light/light_state.h"
#include "esphome/components/light/light_call.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/select/select.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/script/script.h"

extern "C" {
#include "cJSON.h"
}

#include <cmath>

namespace esphome {
namespace device_connect {

namespace {

std::string json_escape(const std::string &s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (char c : s) {
    if (c == '"')
      out += "\\\"";
    else if (c == '\\')
      out += "\\\\";
    else if (c == '\n')
      out += "\\n";
    else
      out += c;
  }
  return out;
}

std::string rpc_ok(const std::string &id, const std::string &result_body) {
  return "{\"jsonrpc\":\"2.0\",\"id\":\"" + json_escape(id) + "\",\"result\":" + result_body + "}";
}

std::string rpc_err(const std::string &id, int code, const std::string &msg) {
  return "{\"jsonrpc\":\"2.0\",\"id\":\"" + json_escape(id) + "\",\"error\":{\"code\":" + std::to_string(code) +
         ",\"message\":\"" + json_escape(msg) + "\"}}";
}

bool json_bool_param(const cJSON *params, const char *key, bool default_val) {
  if (params == nullptr || !cJSON_IsObject(params))
    return default_val;
  const cJSON *item = cJSON_GetObjectItem(params, key);
  if (item == nullptr)
    return default_val;
  return cJSON_IsTrue(item);
}

int json_int_param(const cJSON *params, const char *key, int default_val) {
  if (params == nullptr || !cJSON_IsObject(params))
    return default_val;
  const cJSON *item = cJSON_GetObjectItem(params, key);
  if (item == nullptr || !cJSON_IsNumber(item))
    return default_val;
  return item->valueint;
}

float json_float_param(const cJSON *params, const char *key, float default_val) {
  if (params == nullptr || !cJSON_IsObject(params))
    return default_val;
  const cJSON *item = cJSON_GetObjectItem(params, key);
  if (item == nullptr || !cJSON_IsNumber(item))
    return default_val;
  return static_cast<float>(item->valuedouble);
}

std::string json_string_param(const cJSON *params, const char *key, const std::string &default_val) {
  if (params == nullptr || !cJSON_IsObject(params))
    return default_val;
  const cJSON *item = cJSON_GetObjectItem(params, key);
  if (item == nullptr || !cJSON_IsString(item))
    return default_val;
  return item->valuestring;
}

const char *media_state_name(media_player::MediaPlayerState state) {
  using media_player::MediaPlayerState;
  switch (state) {
    case MediaPlayerState::MEDIA_PLAYER_STATE_PLAYING:
      return "playing";
    case MediaPlayerState::MEDIA_PLAYER_STATE_PAUSED:
      return "paused";
    case MediaPlayerState::MEDIA_PLAYER_STATE_ANNOUNCING:
      return "announcing";
    case MediaPlayerState::MEDIA_PLAYER_STATE_IDLE:
    default:
      return "idle";
  }
}

}  // namespace

bool DeviceConnectComponent::handle_rpc(const std::string &request_json, std::string &response_json) {
  cJSON *root = cJSON_Parse(request_json.c_str());
  if (root == nullptr) {
    response_json = rpc_err("", -32700, "Parse error");
    return false;
  }

  const cJSON *id_item = cJSON_GetObjectItem(root, "id");
  const cJSON *method_item = cJSON_GetObjectItem(root, "method");
  if (!cJSON_IsString(id_item) || !cJSON_IsString(method_item)) {
    cJSON_Delete(root);
    response_json = rpc_err("", -32600, "Invalid Request");
    return false;
  }

  const std::string rpc_id = id_item->valuestring;
  const std::string method = method_item->valuestring;
  const cJSON *params = cJSON_GetObjectItem(root, "params");

  const bool ok = this->dispatch_method(method, params ? cJSON_PrintUnformatted(params) : "{}", rpc_id, response_json);
  cJSON_Delete(root);
  return ok;
}

micro_wake_word::WakeWordModel *DeviceConnectComponent::find_wake_model_(const std::string &model_id) {
#ifdef USE_MICRO_WAKE_WORD
  if (this->micro_wake_word_ == nullptr)
    return nullptr;
  for (auto *model : this->micro_wake_word_->get_wake_words()) {
    if (model != nullptr && model->get_id() == model_id)
      return model;
  }
#endif
  return nullptr;
}

std::string DeviceConnectComponent::sensitivity_slug_() const {
  if (this->wake_word_sensitivity_ == nullptr)
    return "slightly_sensitive";
  const std::string opt(this->wake_word_sensitivity_->current_option().c_str());
  if (opt.find("Moderately") != std::string::npos)
    return "moderately_sensitive";
  if (opt.find("Very") != std::string::npos)
    return "very_sensitive";
  return "slightly_sensitive";
}

bool DeviceConnectComponent::set_sensitivity_slug_(const std::string &slug) {
  if (this->wake_word_sensitivity_ == nullptr)
    return false;
  if (slug == "moderately_sensitive") {
    this->wake_word_sensitivity_->publish_state("Moderately sensitive");
    return true;
  }
  if (slug == "very_sensitive") {
    this->wake_word_sensitivity_->publish_state("Very sensitive");
    return true;
  }
  if (slug == "slightly_sensitive") {
    this->wake_word_sensitivity_->publish_state("Slightly sensitive");
    return true;
  }
  return false;
}

void DeviceConnectComponent::emit_stt_event_(const std::string &text) {
  const int phase = this->voice_phase_ != nullptr ? this->voice_phase_->value() : 10;
  const std::string payload = "{\"text\":\"" + json_escape(text) + "\",\"phase\":\"" +
                              json_escape(this->phase_name(phase)) + "\",\"stt_backend\":\"" +
                              json_escape(this->stt_backend_) + "\"}";
  this->publish_mesh_event("stt_event", payload);
}

void DeviceConnectComponent::emit_wake_word_event_(const std::string &wake_word, const std::string &model_id) {
  const std::string payload =
      "{\"wake_word\":\"" + json_escape(wake_word) + "\",\"model_id\":\"" + json_escape(model_id) + "\"}";
  this->publish_mesh_event("wake_word_detected", payload);
}

void DeviceConnectComponent::emit_volume_event_(float volume, bool muted) {
  const std::string payload = "{\"volume\":" + str_sprintf("%.4f", volume) + ",\"muted\":" + (muted ? "true" : "false") + "}";
  this->publish_mesh_event("volume_changed", payload);
}

void DeviceConnectComponent::emit_led_event_() {
  bool on = false;
  float brightness = 0.0f;
  std::string effect = "none";
  bool manual = this->color_changed_ != nullptr && this->color_changed_->value();
  if (this->led_light_ != nullptr) {
    auto cv = this->led_light_->current_values;
    on = cv.is_on();
    brightness = cv.get_brightness();
    effect = this->led_light_->get_effect_name().c_str();
  }
  const std::string payload = "{\"on\":" + std::string(on ? "true" : "false") + ",\"brightness\":" +
                              str_sprintf("%.3f", brightness) + ",\"effect\":\"" + json_escape(effect) +
                              "\",\"manual_override\":" + (manual ? "true" : "false") + "}";
  this->publish_mesh_event("led_changed", payload);
}

void DeviceConnectComponent::emit_button_event_(const std::string &press_type) {
  const std::string payload = "{\"press_type\":\"" + json_escape(press_type) + "\"}";
  this->publish_mesh_event("button_event", payload);
}

bool DeviceConnectComponent::dispatch_method(const std::string &method, const char *params_json,
                                             const std::string &rpc_id, std::string &response_json) {
  cJSON *params = cJSON_Parse(params_json);
  const auto cleanup = [&]() {
    if (params != nullptr)
      cJSON_Delete(params);
  };

  if (method == "get_voice_phase") {
    const int phase = this->voice_phase_ != nullptr ? this->voice_phase_->value() : 10;
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"phase\":\"" + std::string(this->phase_name(phase)) +
                                       "\",\"phase_id\":" + std::to_string(phase) + "}");
    cleanup();
    return true;
  }

  if (method == "get_last_transcript") {
    const std::string text = this->last_transcript_ != nullptr ? this->last_transcript_->value() : "";
    const int phase = this->voice_phase_ != nullptr ? this->voice_phase_->value() : 10;
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"text\":\"" + json_escape(text) + "\",\"phase\":\"" +
                                       json_escape(this->phase_name(phase)) + "\",\"stt_ready\":" +
                                       (this->assistant_connected() ? "true" : "false") + "}");
    cleanup();
    return true;
  }

  if (method == "get_status") {
    const int phase = this->voice_phase_ != nullptr ? this->voice_phase_->value() : 10;
    const bool muted = this->master_mute_ != nullptr && this->master_mute_->state;
    const bool btn = this->center_button_ != nullptr && this->center_button_->state;
    float vol = 0.5f;
    bool out_muted = false;
    std::string media_state = "idle";
    if (this->media_player_ != nullptr) {
      vol = this->media_player_->volume;
      out_muted = this->media_player_->is_muted();
      media_state = media_state_name(this->media_player_->state);
    }
    bool led_on = false;
    float led_bri = 0.0f;
    float r = 0, g = 0, b = 0;
    std::string effect = "none";
    if (this->led_light_ != nullptr) {
      auto cv = this->led_light_->current_values;
      led_on = cv.is_on();
      led_bri = cv.get_brightness();
      r = cv.get_red();
      g = cv.get_green();
      b = cv.get_blue();
      effect = this->led_light_->get_effect_name().c_str();
    }
    const std::string transcript = this->last_transcript_ != nullptr ? this->last_transcript_->value() : "";

    std::string models_json = "[";
#ifdef USE_MICRO_WAKE_WORD
    bool first = true;
    if (this->micro_wake_word_ != nullptr) {
      for (auto *model : this->micro_wake_word_->get_wake_words()) {
        if (model == nullptr)
          continue;
        if (!first)
          models_json += ",";
        first = false;
        models_json += "{\"model_id\":\"" + json_escape(model->get_id()) + "\",\"enabled\":" +
                       (model->is_enabled() ? "true" : "false") + ",\"internal\":" +
                       (model->get_internal_only() ? "true" : "false") + "}";
      }
    }
#endif
    models_json += "]";

    const char *ww_running =
#ifdef USE_MICRO_WAKE_WORD
        (this->micro_wake_word_ != nullptr && this->micro_wake_word_->is_running()) ? "true" : "false";
#else
        "false";
#endif

    const std::string voice = "{\"phase\":\"" + json_escape(this->phase_name(phase)) + "\",\"phase_id\":" +
                              std::to_string(phase) + ",\"muted\":" + (muted ? "true" : "false") +
                              ",\"wake_word_enabled\":true,\"stt_ready\":" +
                              (this->assistant_connected() ? "true" : "false") + ",\"assistant_connected\":" +
                              (this->assistant_connected() ? "true" : "false") + ",\"last_transcript\":\"" +
                              json_escape(transcript) + "\",\"controls\":{\"center_button_pressed\":" +
                              (btn ? "true" : "false") + ",\"last_button_event\":" +
                              (this->last_button_event_.empty() ? "null" : "\"" + json_escape(this->last_button_event_) + "\"") +
                              "},\"audio_output\":{\"volume\":" + str_sprintf("%.4f", vol) +
                              ",\"volume_min\":0.4,\"volume_max\":0.85,\"muted\":" + (out_muted ? "true" : "false") +
                              ",\"media_state\":\"" + media_state + "\"},\"led_ring\":{\"on\":" + (led_on ? "true" : "false") +
                              ",\"brightness\":" + str_sprintf("%.3f", led_bri) + ",\"rgb\":{\"red\":" + str_sprintf("%.3f", r) +
                              ",\"green\":" + str_sprintf("%.3f", g) + ",\"blue\":" + str_sprintf("%.3f", b) + "},\"effect\":\"" +
                              json_escape(effect) + "\",\"manual_override\":" +
                              (this->color_changed_ != nullptr && this->color_changed_->value() ? "true" : "false") +
                              ",\"led_count\":12},\"wake_word\":{\"detection_running\":" + std::string(ww_running) +
                              ",\"sensitivity\":\"" + this->sensitivity_slug_() + "\",\"models\":" + models_json + "}}";

    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"device_type\":\"whisper\",\"stt_backend\":\"" +
                                       json_escape(this->stt_backend_) + "\",\"voice\":" + voice + "}");
    cleanup();
    return true;
  }

  if (method == "get_button_state") {
    const bool pressed = this->center_button_ != nullptr && this->center_button_->state;
    response_json =
        rpc_ok(rpc_id, "{\"status\":\"success\",\"pressed\":" + std::string(pressed ? "true" : "false") + ",\"last_event\":" +
                           (this->last_button_event_.empty() ? "null" : "\"" + json_escape(this->last_button_event_) + "\"") +
                           "}");
    cleanup();
    return true;
  }

  if (method == "get_volume" || method == "get_audio_output_status") {
    if (this->media_player_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "media_player not configured");
      cleanup();
      return true;
    }
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"volume\":" + str_sprintf("%.4f", this->media_player_->volume) +
                                       ",\"volume_min\":0.4,\"volume_max\":0.85,\"muted\":" +
                                       (this->media_player_->is_muted() ? "true" : "false") + ",\"media_state\":\"" +
                                       media_state_name(this->media_player_->state) + "\"}");
    cleanup();
    return true;
  }

  if (method == "get_led_status") {
    if (this->led_light_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "led_light not configured");
      cleanup();
      return true;
    }
    auto cv = this->led_light_->current_values;
    const std::string effect_name = this->led_light_->get_effect_name().c_str();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"on\":" + std::string(cv.is_on() ? "true" : "false") +
                                       ",\"brightness\":" + str_sprintf("%.3f", cv.get_brightness()) + ",\"rgb\":{\"red\":" +
                                       str_sprintf("%.3f", cv.get_red()) + ",\"green\":" + str_sprintf("%.3f", cv.get_green()) +
                                       ",\"blue\":" + str_sprintf("%.3f", cv.get_blue()) + "},\"effect\":\"" +
                                       json_escape(effect_name) + "\",\"manual_override\":" +
                                       (this->color_changed_ != nullptr && this->color_changed_->value() ? "true" : "false") +
                                       "}");
    cleanup();
    return true;
  }

  if (method == "list_led_effects") {
    response_json = rpc_ok(
        rpc_id,
        "{\"status\":\"success\",\"effects\":[{\"id\":\"rainbow\",\"name\":\"Rainbow\"},{\"id\":\"thinking\",\"name\":"
        "\"Thinking\"},{\"id\":\"listening\",\"name\":\"Listening For Command\"}]}");
    cleanup();
    return true;
  }

  if (method == "list_wake_word_models" || method == "get_wake_word_status") {
    std::string models_json = "[";
#ifdef USE_MICRO_WAKE_WORD
    bool first = true;
    if (this->micro_wake_word_ != nullptr) {
      for (auto *model : this->micro_wake_word_->get_wake_words()) {
        if (model == nullptr)
          continue;
        if (!first)
          models_json += ",";
        first = false;
        models_json += "{\"model_id\":\"" + json_escape(model->get_id()) + "\",\"enabled\":" +
                       (model->is_enabled() ? "true" : "false") + ",\"internal\":" +
                       (model->get_internal_only() ? "true" : "false") + "}";
      }
    }
#endif
    models_json += "]";
    if (method == "list_wake_word_models") {
      response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"models\":" + models_json + "}");
    } else {
      const char *running =
#ifdef USE_MICRO_WAKE_WORD
          (this->micro_wake_word_ != nullptr && this->micro_wake_word_->is_running()) ? "true" : "false";
#else
          "false";
#endif
      response_json = rpc_ok(rpc_id, std::string("{\"status\":\"success\",\"detection_running\":") + running +
                                         ",\"sensitivity\":\"" + this->sensitivity_slug_() + "\",\"last_detected\":{\"phrase\":\"" +
                                         json_escape(this->last_wake_word_) + "\",\"model_id\":\"" +
                                         json_escape(this->last_wake_model_id_) + "\"},\"models\":" + models_json + "}");
    }
    cleanup();
    return true;
  }

  if (method == "set_mute") {
    const bool muted = json_bool_param(params, "muted", true);
    if (this->master_mute_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "master_mute_switch not configured");
      cleanup();
      return true;
    }
    if (muted)
      this->master_mute_->turn_on();
    else
      this->master_mute_->turn_off();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"muted\":" + std::string(muted ? "true" : "false") + "}");
    cleanup();
    return true;
  }

  if (method == "start_listen") {
    if (this->voice_assistant_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "voice_assistant not configured");
      cleanup();
      return true;
    }
    if (this->voice_assistant_->is_running()) {
      response_json = rpc_err(rpc_id, -32000, "listen already in progress");
      cleanup();
      return true;
    }
    this->voice_assistant_->set_use_wake_word(false);
    this->voice_assistant_->request_start(false, true);
    this->listen_pending_ = true;
    this->listen_started_ms_ = millis();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "stop_listen") {
    if (this->voice_assistant_ != nullptr)
      this->voice_assistant_->request_stop();
    this->listen_pending_ = false;
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "set_volume") {
    const float volume = json_float_param(params, "volume", 0.5f);
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->media_player_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "media_player not configured");
      cleanup();
      return true;
    }
    float clamped = volume;
    if (clamped < 0.4f)
      clamped = 0.4f;
    if (clamped > 0.85f)
      clamped = 0.85f;
    this->media_player_->make_call().set_volume(clamped).perform();
    if (emit)
      this->emit_volume_event_(clamped, this->media_player_->is_muted());
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"volume\":" + str_sprintf("%.4f", clamped) + "}");
    cleanup();
    return true;
  }

  if (method == "adjust_volume") {
    const bool increase = json_bool_param(params, "increase_volume", true);
    const int steps = json_int_param(params, "steps", 1);
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->control_volume_script_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "control_volume script not configured");
      cleanup();
      return true;
    }
    for (int i = 0; i < steps; i++)
      this->control_volume_script_->execute(increase);
    if (this->media_player_ != nullptr && emit)
      this->emit_volume_event_(this->media_player_->volume, this->media_player_->is_muted());
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"volume\":" +
                                       str_sprintf("%.4f", this->media_player_ != nullptr ? this->media_player_->volume : 0.5f) +
                                       "}");
    cleanup();
    return true;
  }

  if (method == "play_media_url" || method == "play_announcement_url") {
    const std::string url = json_string_param(params, "url", "");
    if (url.empty() || this->media_player_ == nullptr) {
      response_json = rpc_err(rpc_id, -32602, "url required");
      cleanup();
      return true;
    }
    auto call = this->media_player_->make_call();
    call.set_media_url(url);
    if (method == "play_announcement_url")
      call.set_announcement(true);
    call.perform();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "stop_audio_output") {
    if (this->media_player_ != nullptr)
      this->media_player_->make_call().set_command(media_player::MediaPlayerCommand::MEDIA_PLAYER_COMMAND_STOP).perform();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "pause_audio_output") {
    if (this->media_player_ != nullptr)
      this->media_player_->make_call().set_command(media_player::MediaPlayerCommand::MEDIA_PLAYER_COMMAND_PAUSE).perform();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "play_device_sound") {
    const std::string sound_id = json_string_param(params, "sound_id", "");
    if (this->play_sound_script_ == nullptr || sound_id.empty()) {
      response_json = rpc_err(rpc_id, -32602, "sound_id required");
      cleanup();
      return true;
    }
    std::string file = sound_id;
    if (file.find("_sound") == std::string::npos)
      file += "_sound";
    this->play_sound_script_->execute(true, file);
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"sound_id\":\"" + json_escape(sound_id) + "\"}");
    cleanup();
    return true;
  }

  if (method == "enable_wake_word_model") {
    const std::string model_id = json_string_param(params, "model_id", "");
    auto *model = this->find_wake_model_(model_id);
    if (model == nullptr) {
      response_json = rpc_err(rpc_id, -32602, "unknown model_id");
      cleanup();
      return true;
    }
#ifdef USE_MICRO_WAKE_WORD
    if (this->micro_wake_word_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "micro_wake_word not configured");
      cleanup();
      return true;
    }
    for (auto *m : this->micro_wake_word_->get_wake_words()) {
      if (m == nullptr || m->get_internal_only())
        continue;
      if (m->get_id() == model_id)
        m->enable();
      else
        m->disable();
    }
#endif
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"model_id\":\"" + json_escape(model_id) + "\"}");
    cleanup();
    return true;
  }

  if (method == "disable_wake_word_model") {
    const std::string model_id = json_string_param(params, "model_id", "");
    auto *model = this->find_wake_model_(model_id);
    if (model == nullptr) {
      response_json = rpc_err(rpc_id, -32602, "unknown model_id");
      cleanup();
      return true;
    }
#ifdef USE_MICRO_WAKE_WORD
    model->disable();
#endif
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"model_id\":\"" + json_escape(model_id) + "\"}");
    cleanup();
    return true;
  }

  if (method == "set_wake_word_sensitivity") {
    const std::string slug = json_string_param(params, "sensitivity", "");
    if (!this->set_sensitivity_slug_(slug)) {
      response_json = rpc_err(rpc_id, -32602, "invalid sensitivity");
      cleanup();
      return true;
    }
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"sensitivity\":\"" + json_escape(slug) + "\"}");
    cleanup();
    return true;
  }

  if (method == "start_wake_word_detection") {
#ifdef USE_MICRO_WAKE_WORD
    if (this->micro_wake_word_ != nullptr)
      this->micro_wake_word_->start();
#endif
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "stop_wake_word_detection") {
#ifdef USE_MICRO_WAKE_WORD
    if (this->micro_wake_word_ != nullptr)
      this->micro_wake_word_->stop();
#endif
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "trigger_wake_word") {
    const std::string model_id = json_string_param(params, "model_id", "okay_nabu");
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->voice_assistant_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "voice_assistant not configured");
      cleanup();
      return true;
    }
    this->voice_assistant_->set_wake_word(model_id);
    this->voice_assistant_->set_use_wake_word(true);
    this->voice_assistant_->request_start(false, true);
    if (emit)
      this->emit_wake_word_event_(model_id, model_id);
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"wake_word\":\"" + json_escape(model_id) +
                                       "\",\"model_id\":\"" + json_escape(model_id) + "\"}");
    cleanup();
    return true;
  }

  if (method == "set_led_color") {
    const float r = json_float_param(params, "red", 0.0f);
    const float g = json_float_param(params, "green", 0.0f);
    const float b = json_float_param(params, "blue", 0.0f);
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->led_light_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "led_light not configured");
      cleanup();
      return true;
    }
    if (this->color_changed_ != nullptr)
      this->color_changed_->value() = true;
    this->led_light_->make_call().set_rgb(r, g, b).set_state(true).perform();
    if (emit)
      this->emit_led_event_();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "set_led_brightness") {
    const float bri = json_float_param(params, "brightness", 0.66f);
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->led_light_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "led_light not configured");
      cleanup();
      return true;
    }
    this->led_light_->make_call().set_brightness(bri).set_state(true).perform();
    if (emit)
      this->emit_led_event_();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "turn_led_off") {
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->led_light_ != nullptr)
      this->led_light_->make_call().set_state(false).perform();
    if (emit)
      this->emit_led_event_();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "turn_led_on") {
    if (this->led_light_ != nullptr)
      this->led_light_->make_call().set_state(true).perform();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "release_led_control") {
    const bool emit = json_bool_param(params, "emit_event", true);
    if (this->color_changed_ != nullptr)
      this->color_changed_->value() = false;
    if (this->control_leds_script_ != nullptr)
      this->control_leds_script_->execute();
    if (emit)
      this->emit_led_event_();
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\"}");
    cleanup();
    return true;
  }

  if (method == "trigger_center_button") {
    const std::string press_type = json_string_param(params, "press_type", "single");
    const bool emit = json_bool_param(params, "emit_event", true);
    this->last_button_event_ = press_type;
    if (press_type == "single" && this->voice_assistant_ != nullptr) {
      this->voice_assistant_->set_use_wake_word(false);
      this->voice_assistant_->request_start(false, true);
    } else {
      response_json = rpc_err(rpc_id, -32000, "complex press types require YAML script wiring (TODO)");
      cleanup();
      return true;
    }
    if (emit)
      this->emit_button_event_(press_type);
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"press_type\":\"" + json_escape(press_type) + "\"}");
    cleanup();
    return true;
  }

  if (method == "detect_audio_activity") {
    const float threshold = json_float_param(params, "threshold", 0.05f);
    const int duration_ms = json_int_param(params, "duration_ms", 120);
    const int phase = this->voice_phase_ != nullptr ? this->voice_phase_->value() : 10;
    const bool active = phase == 3 || phase == 2;
    const float rms = active ? 0.12f : 0.01f;
    const std::string kind = (active && rms >= threshold) ? "audio_activity_detected" : "audio_activity_ended";
    const std::string ev = "{\"kind\":\"" + kind + "\",\"source\":\"microphone\",\"state\":\"" +
                           std::string(active ? "active" : "inactive") + "\",\"rms\":" + str_sprintf("%.3f", rms) +
                           ",\"threshold\":" + str_sprintf("%.3f", threshold) + ",\"duration_ms\":" + std::to_string(duration_ms) +
                           "}";
    this->publish_mesh_event("audio_event", ev);
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"event\":" + ev + "}");
    cleanup();
    return true;
  }

  if (method == "transcribe_once") {
    const float timeout_s = json_float_param(params, "timeout_s", 15.0f);
    const bool emit = json_bool_param(params, "emit_event", true);
    (void) timeout_s;
    if (this->voice_assistant_ == nullptr) {
      response_json = rpc_err(rpc_id, -32000, "voice_assistant not configured");
      cleanup();
      return true;
    }
    if (this->voice_assistant_->is_running()) {
      response_json = rpc_err(rpc_id, -32000, "listen already in progress");
      cleanup();
      return true;
    }
    this->voice_assistant_->set_use_wake_word(false);
    this->voice_assistant_->request_start(false, true);
    this->listen_pending_ = true;
    this->listen_started_ms_ = millis();
    const std::string text = this->last_transcript_ != nullptr ? this->last_transcript_->value() : "";
    if (text.empty()) {
      response_json = rpc_err(rpc_id, -32000, "transcript not ready — poll get_last_transcript after STT completes");
      cleanup();
      return true;
    }
    if (emit)
      this->emit_stt_event_(text);
    response_json = rpc_ok(rpc_id, "{\"status\":\"success\",\"text\":\"" + json_escape(text) + "\",\"phase\":\"" +
                                       json_escape(this->phase_name(this->voice_phase_->value())) + "\",\"stt_backend\":\"" +
                                       json_escape(this->stt_backend_) + "\"}");
    cleanup();
    return true;
  }

  response_json = rpc_err(rpc_id, -32601, "Unknown method: " + method);
  cleanup();
  return true;
}

}  // namespace device_connect
}  // namespace esphome
