"""
Terminal-only proof-of-concept simulation for electricity logic in main.py.

This script intentionally avoids any hardware dependencies. It reproduces the
same core math model used by the RP2040 firmware for one utility (electricity).
"""

import math


# ---------- DEMO TUNING (faster depletion for terminal show) ----------
# Drain speed at 100% flow: "percent points" drained per second
MAX_DRAIN_PER_SEC = 6.0

# Refill behavior when flow is low
REFILL_THRESHOLD = 30.0
MAX_REFILL_PER_SEC = 1.20

# Input smoothing for pot value (0..1), higher = faster response
SMOOTH_ALPHA = 0.60

# Deadband around low values to reduce near-zero jitter
ZERO_DEADBAND_PCT = 1.5

# Simulation timestep (seconds per loop)
STEP_SECONDS = 1.0

# 3-LED gauge in this project revision
GAUGE_LED_COUNT = 3


def clamp(value, low, high):
    return max(low, min(high, value))


class ElectricitySimulation:
    def __init__(self):
        self.level = 100.0  # 0..100
        self.flow_pct_smoothed = 0.0
        self.actual_flow_pct = 0.0
        self.pot_pct = 0.0
        self.elapsed_sec = 0.0
        self.last_drain_per_sec = 0.0
        self.last_refill_per_sec = 0.0

    def set_pot(self, pct):
        pct = clamp(float(pct), 0.0, 100.0)
        if pct < ZERO_DEADBAND_PCT:
            pct = 0.0
        self.pot_pct = pct

    def update(self, dt_sec):
        # 1) Smooth user pot setting into target flow %
        self.flow_pct_smoothed += (self.pot_pct - self.flow_pct_smoothed) * SMOOTH_ALPHA
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
        self.level = clamp(self.level, 0.0, 100.0)

        self.last_drain_per_sec = drain_per_sec
        self.last_refill_per_sec = refill_per_sec
        self.elapsed_sec += dt_sec

    def gauge_display(self):
        leds_on = int(math.ceil((self.level / 100.0) * GAUGE_LED_COUNT))
        leds_on = int(clamp(leds_on, 0, GAUGE_LED_COUNT))
        on = "●" * leds_on
        off = "○" * (GAUGE_LED_COUNT - leds_on)
        return on + off

    def print_status(self):
        mm = int(self.elapsed_sec // 60)
        ss = int(self.elapsed_sec % 60)
        timestamp = f"{mm:02d}:{ss:02d}"
        print(f"\nTime: {timestamp}  (sim +{STEP_SECONDS:.1f}s)")
        print(f"Pot setting:        {self.pot_pct:6.2f}%")
        print(f"Smoothed flow:      {self.flow_pct_smoothed:6.2f}%")
        print(f"Actual flow:        {self.actual_flow_pct:6.2f}%")
        print(f"Drain/sec:          {self.last_drain_per_sec:6.3f}")
        print(f"Refill/sec:         {self.last_refill_per_sec:6.3f}")
        print(f"Resource level:     {self.level:6.2f}%")
        print(f"3-LED gauge:        {self.gauge_display()}")


def prompt_for_pot(current_value):
    prompt = (
        "\nSet electricity potentiometer (0-100%). "
        "Press Enter to keep current value, or type 'q' to quit: "
    )
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("q", "quit", "exit"):
            return None
        if raw == "":
            return current_value
        try:
            value = float(raw)
        except ValueError:
            print("Please enter a number from 0 to 100, press Enter, or type 'q'.")
            continue

        if 0.0 <= value <= 100.0:
            return value

        print("Out of range. Enter a value between 0 and 100.")


def main():
    sim = ElectricitySimulation()

    print("Electricity Utility Simulation (No Hardware)")
    print("This terminal version mirrors the electricity math in main.py.")
    print("Simulation starts with level at 100%.")

    while True:
        next_value = prompt_for_pot(sim.pot_pct)
        if next_value is None:
            print("\nSimulation ended.")
            break

        sim.set_pot(next_value)
        sim.update(STEP_SECONDS)
        sim.print_status()


if __name__ == "__main__":
    main()
