"""ESPHome external component: Device Connect on Home Assistant Voice PE."""

from pathlib import Path

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import (
    binary_sensor,
    globals,
    light,
    media_player,
    micro_wake_word,
    script,
    select,
    switch,
    voice_assistant,
)
from esphome.const import CONF_ID

CODEOWNERS = ["@ericvh"]
DEPENDENCIES = ["network"]
AUTO_LOAD = []

CONF_DEVICE_ID = "device_id"
CONF_TENANT = "tenant"
CONF_ENABLED = "enabled"
CONF_ZENOH_CONNECT = "zenoh_connect"
CONF_ZENOH_ENABLED = "zenoh_enabled"
CONF_STT_BACKEND = "stt_backend"

ZENOH_PICO_VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "zenoh-pico"
ZENOH_PICO_REPO = "https://github.com/eclipse-zenoh/zenoh-pico.git#1.9.0"

CONF_VOICE_PHASE_ID = "voice_assistant_phase_id"
CONF_LAST_TRANSCRIPT_ID = "last_transcript_id"
CONF_COLOR_CHANGED_ID = "color_changed_id"
CONF_VOICE_ASSISTANT_ID = "voice_assistant_id"
CONF_MICRO_WAKE_WORD_ID = "micro_wake_word_id"
CONF_WAKE_WORD_SENSITIVITY_ID = "wake_word_sensitivity_id"
CONF_CENTER_BUTTON_ID = "center_button_id"
CONF_MASTER_MUTE_ID = "master_mute_switch_id"
CONF_MEDIA_PLAYER_ID = "media_player_id"
CONF_LED_LIGHT_ID = "led_light_id"
CONF_CONTROL_VOLUME_SCRIPT_ID = "control_volume_script_id"
CONF_CONTROL_LEDS_SCRIPT_ID = "control_leds_script_id"
CONF_PLAY_SOUND_SCRIPT_ID = "play_sound_script_id"

device_connect_ns = cg.esphome_ns.namespace("device_connect")
DeviceConnectComponent = device_connect_ns.class_("DeviceConnectComponent", cg.Component)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(DeviceConnectComponent),
            cv.Required(CONF_DEVICE_ID): cv.string,
            cv.Optional(CONF_TENANT, default="default"): cv.string,
            cv.Optional(CONF_ENABLED, default=True): cv.boolean,
            cv.Optional(CONF_ZENOH_CONNECT, default=""): cv.string,
            cv.Optional(CONF_ZENOH_ENABLED, default=True): cv.boolean,
            cv.Optional(CONF_STT_BACKEND, default="voice_assistant"): cv.string,
            cv.Optional(CONF_VOICE_PHASE_ID): cv.use_id(globals.GlobalsComponent),
            cv.Optional(CONF_LAST_TRANSCRIPT_ID): cv.use_id(globals.GlobalsComponent),
            cv.Optional(CONF_COLOR_CHANGED_ID): cv.use_id(globals.GlobalsComponent),
            cv.Optional(CONF_VOICE_ASSISTANT_ID): cv.use_id(voice_assistant.VoiceAssistant),
            cv.Optional(CONF_MICRO_WAKE_WORD_ID): cv.use_id(micro_wake_word.MicroWakeWord),
            cv.Optional(CONF_WAKE_WORD_SENSITIVITY_ID): cv.use_id(select.Select),
            cv.Optional(CONF_CENTER_BUTTON_ID): cv.use_id(binary_sensor.BinarySensor),
            cv.Optional(CONF_MASTER_MUTE_ID): cv.use_id(switch.Switch),
            cv.Optional(CONF_MEDIA_PLAYER_ID): cv.use_id(media_player.MediaPlayer),
            cv.Optional(CONF_LED_LIGHT_ID): cv.use_id(light.LightState),
            cv.Optional(CONF_CONTROL_VOLUME_SCRIPT_ID): cv.use_id(script.Script),
            cv.Optional(CONF_CONTROL_LEDS_SCRIPT_ID): cv.use_id(script.Script),
            cv.Optional(CONF_PLAY_SOUND_SCRIPT_ID): cv.use_id(script.Script),
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_on_esp32,
)


def _configure_zenoh_pico() -> None:
    """Link zenoh-pico (vendored copy preferred; else PlatformIO git dep)."""
    if ZENOH_PICO_VENDOR.is_dir():
        cg.add_library("zenoh-pico", None, f"file://{ZENOH_PICO_VENDOR}")
    else:
        cg.add_library("zenoh-pico", None, ZENOH_PICO_REPO)
    # zenoh-pico extra_script.py selects sources for PIOFRAMEWORK=espidf (ZENOH_ESPIDF).
    cg.add_build_flag("-DZENOH_ESPIDF")
    cg.add_define("USE_DEVICE_CONNECT_ZENOH")


async def to_code(config):
    var = cg.new_Pvariable(config[cv.GenerateID()])
    await cg.register_component(var, config)

    if config[CONF_ZENOH_ENABLED]:
        _configure_zenoh_pico()

    cg.add(var.set_device_id(config[CONF_DEVICE_ID]))
    cg.add(var.set_tenant(config[CONF_TENANT]))
    cg.add(var.set_enabled(config[CONF_ENABLED]))
    cg.add(var.set_zenoh_connect(config[CONF_ZENOH_CONNECT]))
    cg.add(var.set_zenoh_enabled(config[CONF_ZENOH_ENABLED]))
    cg.add(var.set_stt_backend(config[CONF_STT_BACKEND]))

    if CONF_VOICE_PHASE_ID in config:
        phase = await cg.get_variable(config[CONF_VOICE_PHASE_ID])
        cg.add(var.set_voice_phase(phase))
    if CONF_LAST_TRANSCRIPT_ID in config:
        transcript = await cg.get_variable(config[CONF_LAST_TRANSCRIPT_ID])
        cg.add(var.set_last_transcript(transcript))
    if CONF_COLOR_CHANGED_ID in config:
        color_changed = await cg.get_variable(config[CONF_COLOR_CHANGED_ID])
        cg.add(var.set_color_changed(color_changed))
    if CONF_VOICE_ASSISTANT_ID in config:
        va = await cg.get_variable(config[CONF_VOICE_ASSISTANT_ID])
        cg.add(var.set_voice_assistant(va))
    if CONF_MICRO_WAKE_WORD_ID in config:
        mww = await cg.get_variable(config[CONF_MICRO_WAKE_WORD_ID])
        cg.add(var.set_micro_wake_word(mww))
    if CONF_WAKE_WORD_SENSITIVITY_ID in config:
        sel = await cg.get_variable(config[CONF_WAKE_WORD_SENSITIVITY_ID])
        cg.add(var.set_wake_word_sensitivity(sel))
    if CONF_CENTER_BUTTON_ID in config:
        btn = await cg.get_variable(config[CONF_CENTER_BUTTON_ID])
        cg.add(var.set_center_button(btn))
    if CONF_MASTER_MUTE_ID in config:
        sw = await cg.get_variable(config[CONF_MASTER_MUTE_ID])
        cg.add(var.set_master_mute(sw))
    if CONF_MEDIA_PLAYER_ID in config:
        mp = await cg.get_variable(config[CONF_MEDIA_PLAYER_ID])
        cg.add(var.set_media_player(mp))
    if CONF_LED_LIGHT_ID in config:
        led = await cg.get_variable(config[CONF_LED_LIGHT_ID])
        cg.add(var.set_led_light(led))
    if CONF_CONTROL_VOLUME_SCRIPT_ID in config:
        scr = await cg.get_variable(config[CONF_CONTROL_VOLUME_SCRIPT_ID])
        cg.add(var.set_control_volume_script(scr))
    if CONF_CONTROL_LEDS_SCRIPT_ID in config:
        scr = await cg.get_variable(config[CONF_CONTROL_LEDS_SCRIPT_ID])
        cg.add(var.set_control_leds_script(scr))
    if CONF_PLAY_SOUND_SCRIPT_ID in config:
        scr = await cg.get_variable(config[CONF_PLAY_SOUND_SCRIPT_ID])
        cg.add(var.set_play_sound_script(scr))
