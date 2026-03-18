from machine import Pin, ADC
import utime
import math
import neopixel

# ---------- USER PIN CONFIG ----------
# Knobs (potentiometers): middle pin to ADC input, side pins to 3V3 and GND
WATER_KNOB_ADC_PIN = 26  # ADC0
POWER_KNOB_ADC_PIN = 27  # ADC1

# NeoPixel data pins (one strip per utility)
WATER_STRIP_PIN = 2
POWER_STRIP_PIN = 3

# LEDs per strip:
# [flow wire LEDs..., 5 gauge LEDs]
WATER_FLOW_LED_COUNT = 15
POWER_FLOW_LED_COUNT = 15
GAUGE_LED_COUNT = 5

# NeoPixel color config
WATER_FLOW_COLOR = (0, 0, 255)   # blue
POWER_FLOW_COLOR = (255, 0, 0)   # red
WATER_GAUGE_COLOR = (0, 60, 255)
POWER_GAUGE_COLOR = (255, 40, 0)

# ---------- TUNING ----------
LOOP_MS = 50  # update every 50 ms

# Drain speed at 100% flow: "percent points" drained per second
MAX_DRAIN_PER_SEC = 1.0  # 100% flow drains full tank in ~100 seconds

# Refill behavior when flow is low
REFILL_THRESHOLD = 30.0  # refill starts below this flow %
MAX_REFILL_PER_SEC = 0.45  # max refill speed at 0% flow

# Input smoothing for knobs (0..1), higher = faster response
SMOOTH_ALPHA = 0.18

# Deadband around low ADC values to reduce idle flicker
ZERO_DEADBAND_PCT = 1.5

# Global brightness caps for current control.
# 1.0 means full configured RGB values; lower is safer for power.
FLOW_BRIGHTNESS_CAP = 0.35
GAUGE_BRIGHTNESS_CAP = 0.25


class UtilitySystem:
    def __init__(
        self,
        knob_adc_pin,
        strip_pin,
        flow_led_count,
        gauge_led_count,
        flow_color,
        gauge_color,
        name="utility",
    ):
        self.name = name
        self.adc = ADC(knob_adc_pin)

        self.flow_led_count = flow_led_count
        self.gauge_led_count = gauge_led_count
        self.total_led_count = flow_led_count + gauge_led_count
        self.flow_color = flow_color
        self.gauge_color = gauge_color
        self.strip = neopixel.NeoPixel(Pin(strip_pin, Pin.OUT), self.total_led_count)

        self.level = 100.0  # resource level (0..100)
        self.flow_pct_smoothed = 0.0
        self.actual_flow_pct = 0.0
        self._clear_strip()

    def _clear_strip(self):
        for i in range(self.total_led_count):
            self.strip[i] = (0, 0, 0)
        self.strip.write()

    def _read_knob_pct(self):
        raw = self.adc.read_u16()  # 0..65535
        pct = (raw / 65535.0) * 100.0
        if pct < ZERO_DEADBAND_PCT:
            pct = 0.0
        return pct

    @staticmethod
    def _scale_color(color, scale):
        scale = max(0.0, min(1.0, scale))
        return (
            int(color[0] * scale),
            int(color[1] * scale),
            int(color[2] * scale),
        )

    def _set_flow_led_brightness(self, pct):
        flow_scale = (pct / 100.0) * FLOW_BRIGHTNESS_CAP
        flow_rgb = self._scale_color(self.flow_color, flow_scale)
        for i in range(self.flow_led_count):
            self.strip[i] = flow_rgb

    def _set_gauge_from_level(self):
        # 0..100 mapped to 0..5 LEDs
        leds_on = int(math.ceil(self.level / 20.0))
        leds_on = max(0, min(self.gauge_led_count, leds_on))
        on_rgb = self._scale_color(self.gauge_color, GAUGE_BRIGHTNESS_CAP)
        off_rgb = (0, 0, 0)

        for index in range(self.gauge_led_count):
            strip_index = self.flow_led_count + index
            self.strip[strip_index] = on_rgb if index < leds_on else off_rgb

    def update(self, dt_sec):
        # 1) Read and smooth knob -> target flow %
        knob_pct = self._read_knob_pct()
        self.flow_pct_smoothed += (knob_pct - self.flow_pct_smoothed) * SMOOTH_ALPHA
        target_flow = self.flow_pct_smoothed

        # 2) If empty, no output flow until refill occurs
        if self.level <= 0.0:
            self.actual_flow_pct = 0.0
        else:
            self.actual_flow_pct = target_flow

        # 3) Drain from usage
        drain_per_sec = MAX_DRAIN_PER_SEC * (self.actual_flow_pct / 100.0)

        # 4) Auto-refill when usage is low
        if self.actual_flow_pct < REFILL_THRESHOLD:
            refill_factor = (REFILL_THRESHOLD - self.actual_flow_pct) / REFILL_THRESHOLD
            refill_per_sec = MAX_REFILL_PER_SEC * refill_factor
        else:
            refill_per_sec = 0.0

        # 5) Integrate level over time
        self.level += (refill_per_sec - drain_per_sec) * dt_sec
        self.level = max(0.0, min(100.0, self.level))

        # 6) LEDs: flow row brightness + fuel-gauge level
        visible_flow = self.actual_flow_pct if self.level > 0.0 else 0.0
        self._set_flow_led_brightness(visible_flow)
        self._set_gauge_from_level()
        self.strip.write()


def main():
    water = UtilitySystem(
        knob_adc_pin=WATER_KNOB_ADC_PIN,
        strip_pin=WATER_STRIP_PIN,
        flow_led_count=WATER_FLOW_LED_COUNT,
        gauge_led_count=GAUGE_LED_COUNT,
        flow_color=WATER_FLOW_COLOR,
        gauge_color=WATER_GAUGE_COLOR,
        name="water",
    )

    power = UtilitySystem(
        knob_adc_pin=POWER_KNOB_ADC_PIN,
        strip_pin=POWER_STRIP_PIN,
        flow_led_count=POWER_FLOW_LED_COUNT,
        gauge_led_count=GAUGE_LED_COUNT,
        flow_color=POWER_FLOW_COLOR,
        gauge_color=POWER_GAUGE_COLOR,
        name="power",
    )

    last_ms = utime.ticks_ms()
    while True:
        now_ms = utime.ticks_ms()
        dt_ms = utime.ticks_diff(now_ms, last_ms)
        last_ms = now_ms
        dt_sec = dt_ms / 1000.0

        water.update(dt_sec)
        power.update(dt_sec)

        utime.sleep_ms(LOOP_MS)


if __name__ == "__main__":
    main()
