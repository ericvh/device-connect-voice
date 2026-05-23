#include "device_connect_zenoh.h"

#include "device_connect.h"

#include "esphome/core/log.h"

#ifdef USE_DEVICE_CONNECT_ZENOH
#include <zenoh-pico.h>

#include <cstring>
#endif

namespace esphome {
namespace device_connect {

static const char *const ZENOH_TAG = "device_connect.zenoh";

DeviceConnectZenoh::DeviceConnectZenoh(DeviceConnectComponent *parent) : parent_(parent) {}

bool DeviceConnectZenoh::handle_command(const std::string &request_json, std::string &response_json) {
  if (this->parent_ == nullptr)
    return false;
  return this->parent_->handle_rpc(request_json, response_json);
}

std::string DeviceConnectZenoh::subject_to_keyexpr(const std::string &subject) {
  if (subject.find('/') != std::string::npos)
    return subject;

  std::string key = subject;
  for (char &c : key) {
    if (c == '.')
      c = '/';
  }
  if (key.size() >= 2 && key.compare(key.size() - 2, 2, "/>") == 0) {
    key.replace(key.size() - 2, 2, "/**");
  } else if (!key.empty() && key.back() == '>') {
    key.back() = '*';
    key += '*';
  }
  return key;
}

#ifdef USE_DEVICE_CONNECT_ZENOH

namespace {

struct ZenohContext {
  DeviceConnectZenoh *transport;
  std::string cmd_key;
};

static void query_handler(z_loaned_query_t *query, void *ctx) {
  auto *zctx = static_cast<ZenohContext *>(ctx);
  if (zctx == nullptr || zctx->transport == nullptr)
    return;

  const z_loaned_bytes_t *payload = z_query_payload(query);
  if (payload == nullptr)
    return;

  z_owned_string_t payload_str;
  if (z_bytes_to_string(payload, &payload_str) < 0)
    return;

  const char *req_cstr = z_string_data(z_loan(payload_str));
  const size_t req_len = z_string_len(z_loan(payload_str));
  std::string request(req_cstr, req_len);
  z_drop(z_move(payload_str));

  std::string response;
  zctx->transport->handle_command(request, response);

  z_owned_bytes_t reply_bytes;
  z_bytes_copy_from_buf(&reply_bytes, reinterpret_cast<const uint8_t *>(response.data()), response.size());

  z_view_keyexpr_t reply_key;
  z_view_keyexpr_from_str_unchecked(&reply_key, zctx->cmd_key.c_str());
  z_query_reply_options_t opts;
  z_query_reply_options_default(&opts);
  z_query_reply(query, z_loan(reply_key), z_move(reply_bytes), &opts);
}

static void sample_handler(z_loaned_sample_t *sample, void *ctx) {
  auto *zctx = static_cast<ZenohContext *>(ctx);
  if (zctx == nullptr || zctx->transport == nullptr)
    return;

  const z_loaned_bytes_t *payload = z_sample_payload(sample);
  if (payload == nullptr)
    return;

  z_owned_string_t payload_str;
  if (z_bytes_to_string(payload, &payload_str) < 0)
    return;

  const char *req_cstr = z_string_data(z_loan(payload_str));
  const size_t req_len = z_string_len(z_loan(payload_str));
  std::string request(req_cstr, req_len);
  z_drop(z_move(payload_str));

  std::string response;
  if (!zctx->transport->handle_command(request, response))
    return;

  // Pub/sub .cmd has no query reply channel; agents should use queryable/request.
  ESP_LOGD(ZENOH_TAG, "handled pub/sub cmd (%u byte reply)", (unsigned) response.size());
}

static std::string parse_zenoh_endpoint(const std::string &zenoh_connect) {
  std::string ep = zenoh_connect;
  while (!ep.empty() && ep.front() == ' ')
    ep.erase(ep.begin());
  while (!ep.empty() && ep.back() == ' ')
    ep.pop_back();
  if (ep.empty())
    return "";

  if (ep.rfind("zenoh://", 0) == 0) {
    ep = ep.substr(8);
    return "tcp/" + ep;
  }
  if (ep.rfind("zenoh+tls://", 0) == 0) {
    ep = ep.substr(12);
    return "tls/" + ep;
  }
  if (ep.rfind("tcp/", 0) == 0 || ep.rfind("tls/", 0) == 0 || ep.rfind("udp/", 0) == 0)
    return ep;

  if (ep.find('/') == std::string::npos)
    return "tcp/" + ep;
  return ep;
}

}  // namespace

static ZenohContext *g_zenoh_ctx{nullptr};
static z_owned_session_t g_session;
static z_owned_queryable_t g_queryable;
static z_owned_subscriber_t g_subscriber;
static bool g_session_open{false};

bool DeviceConnectZenoh::start(const std::string &zenoh_connect, const std::string &tenant,
                               const std::string &device_id) {
  this->tenant_ = tenant;
  this->device_id_ = device_id;
  this->cmd_key_ = subject_to_keyexpr(str_sprintf("device-connect.%s.%s.cmd", tenant.c_str(), device_id.c_str()));
  this->heartbeat_key_ =
      subject_to_keyexpr(str_sprintf("device-connect.%s.%s.heartbeat", tenant.c_str(), device_id.c_str()));

  z_owned_config_t config;
  z_config_default(&config);

  const std::string endpoint = parse_zenoh_endpoint(zenoh_connect);
  if (endpoint.empty()) {
    zp_config_insert(z_loan_mut(config), Z_CONFIG_MODE_KEY, "peer");
    zp_config_insert(z_loan_mut(config), Z_CONFIG_LISTEN_KEY, "udp/224.0.0.225:7447");
    ESP_LOGI(ZENOH_TAG, "Zenoh peer mode (multicast listen udp/224.0.0.225:7447)");
  } else {
    zp_config_insert(z_loan_mut(config), Z_CONFIG_MODE_KEY, "client");
    zp_config_insert(z_loan_mut(config), Z_CONFIG_CONNECT_KEY, endpoint.c_str());
    ESP_LOGI(ZENOH_TAG, "Zenoh client mode connect=%s", endpoint.c_str());
  }

  if (z_open(&g_session, z_move(config), NULL) < 0) {
    ESP_LOGE(ZENOH_TAG, "z_open failed");
    return false;
  }
  g_session_open = true;

  if (g_zenoh_ctx != nullptr) {
    delete g_zenoh_ctx;
  }
  g_zenoh_ctx = new ZenohContext{this, this->cmd_key_};

  z_view_keyexpr_t cmd_ke;
  z_view_keyexpr_from_str_unchecked(&cmd_ke, this->cmd_key_.c_str());

  z_owned_closure_query_t query_closure;
  z_closure(&query_closure, query_handler, nullptr, g_zenoh_ctx);
  if (z_declare_queryable(z_loan_mut(g_session), &g_queryable, z_loan(cmd_ke), z_move(query_closure), NULL) < 0) {
    ESP_LOGE(ZENOH_TAG, "declare_queryable failed for %s", this->cmd_key_.c_str());
    this->stop();
    return false;
  }

  z_owned_closure_sample_t sample_closure;
  z_closure(&sample_closure, sample_handler, nullptr, g_zenoh_ctx);
  if (z_declare_subscriber(z_loan_mut(g_session), &g_subscriber, z_loan(cmd_ke), z_move(sample_closure), NULL) < 0) {
    ESP_LOGW(ZENOH_TAG, "declare_subscriber failed (queryable still active)");
  }

  zp_task_read_options_t read_opts;
  zp_task_read_options_default(&read_opts);
  if (zp_start_read_task(z_loan_mut(g_session), &read_opts) < 0) {
    ESP_LOGE(ZENOH_TAG, "zp_start_read_task failed");
    this->stop();
    return false;
  }

  this->active_ = true;
  this->last_heartbeat_ms_ = 0;
  ESP_LOGI(ZENOH_TAG, "Zenoh ready cmd=%s heartbeat=%s", this->cmd_key_.c_str(), this->heartbeat_key_.c_str());
  return true;
}

void DeviceConnectZenoh::stop() {
  this->active_ = false;
  if (g_session_open) {
    zp_stop_read_task(z_loan_mut(g_session));
    z_drop(z_move(g_subscriber));
    z_drop(z_move(g_queryable));
    z_drop(z_move(g_session));
    g_session_open = false;
  }
  if (g_zenoh_ctx != nullptr) {
    delete g_zenoh_ctx;
    g_zenoh_ctx = nullptr;
  }
}

void DeviceConnectZenoh::loop() {
  if (!this->active_)
    return;

  const uint32_t now = millis();
  if (now - this->last_heartbeat_ms_ < 10000)
    return;
  this->last_heartbeat_ms_ = now;
  this->publish_heartbeat();
}

bool DeviceConnectZenoh::publish(const std::string &subject, const std::string &payload) {
  if (!this->active_ || !g_session_open)
    return false;

  const std::string key = subject_to_keyexpr(subject);
  z_view_keyexpr_t ke;
  z_view_keyexpr_from_str_unchecked(&ke, key.c_str());

  z_owned_bytes_t bytes;
  z_bytes_copy_from_buf(&bytes, reinterpret_cast<const uint8_t *>(payload.data()), payload.size());

  z_put_options_t opts;
  z_put_options_default(&opts);
  if (z_put(z_loan_mut(g_session), z_loan(ke), z_move(bytes), &opts) < 0) {
    ESP_LOGW(ZENOH_TAG, "z_put failed key=%s", key.c_str());
    return false;
  }
  return true;
}

bool DeviceConnectZenoh::publish_heartbeat() {
  const std::string payload = "{\"device_id\":\"" + this->device_id_ + "\",\"device_type\":\"whisper\",\"status\":\"ok\"}";
  return this->publish(
      str_sprintf("device-connect.%s.%s.heartbeat", this->tenant_.c_str(), this->device_id_.c_str()), payload);
}

#else  // USE_DEVICE_CONNECT_ZENOH

bool DeviceConnectZenoh::start(const std::string &, const std::string &, const std::string &) {
  ESP_LOGW(ZENOH_TAG, "Zenoh support not compiled (USE_DEVICE_CONNECT_ZENOH unset)");
  return false;
}
void DeviceConnectZenoh::stop() {}
void DeviceConnectZenoh::loop() {}
bool DeviceConnectZenoh::publish(const std::string &, const std::string &) { return false; }
bool DeviceConnectZenoh::publish_heartbeat() { return false; }

#endif  // USE_DEVICE_CONNECT_ZENOH

}  // namespace device_connect
}  // namespace esphome
