# Pico Town Utility Simulation

This project simulates two town utilities on an RP2040 (Raspberry Pi Pico):

- Water (blue LEDs): flow brightness + 5-LED resource gauge
- Electricity (red LEDs): flow brightness + 5-LED resource gauge

This version is designed for 20-30 total LEDs using two NeoPixel/WS2812 strips with external 5V power.

## Files

- `main.py` - MicroPython firmware for the full simulation logic

## Current `main.py` Hardware Mapping

### Knobs (potentiometers)

- Water knob middle pin -> GP26 / ADC0
- Electricity knob middle pin -> GP27 / ADC1
- Pot outer pins -> 3V3 and GND

### LED strips (NeoPixel / WS2812 / WS2812B)

- Water strip data in -> GP2
- Electricity strip data in -> GP3
- `main.py` default per strip:
  - 15 flow LEDs + 5 gauge LEDs = 20 LEDs total per strip

You can change counts/pins near the top of `main.py`.

## Behavior Model

For each utility:

- `flow_pct` comes from knob position.
- Drain increases with flow:
  - `drain_per_sec = MAX_DRAIN_PER_SEC * (flow_pct / 100)`
- Refill occurs when flow is below `REFILL_THRESHOLD`:
  - `refill_per_sec = MAX_REFILL_PER_SEC * ((REFILL_THRESHOLD - flow_pct) / REFILL_THRESHOLD)`
- Net level change each loop:
  - `level += (refill_per_sec - drain_per_sec) * dt`

The level is clamped between 0 and 100.

## Tuning

These constants are near the top of `main.py`:

- `MAX_DRAIN_PER_SEC` (higher = drains faster)
- `REFILL_THRESHOLD` (flow % below which refill starts)
- `MAX_REFILL_PER_SEC` (higher = refills faster)
- `SMOOTH_ALPHA` (knob smoothing response)
- `FLOW_BRIGHTNESS_CAP` (limits flow LED current)
- `GAUGE_BRIGHTNESS_CAP` (limits gauge LED current)
- `LOOP_MS` (control loop period)

## Flashing to Pico

1. Install MicroPython on the Pico (UF2 firmware).
2. Connect with Thonny (or another MicroPython IDE).
3. Copy `main.py` to the Pico root.
4. Reset the board. Program starts automatically.

## Build Info for 20-30 LEDs (Requested)

### Parts list

- 1x Raspberry Pi Pico / Pico W
- 2x 10k potentiometers (knobs)
- 2x NeoPixel/WS2812 strips (or one strip cut into 2 runs)
- 1x regulated 5V power supply (recommended 2A or higher)
- 2x 330 ohm resistors (one in series with each data line)
- 1x 1000 uF electrolytic capacitor (across +5V and GND near LED power input)
- Breadboard/perfboard + jumper wires
- Optional but recommended: 74AHCT125 or 74HCT245 level shifter (3.3V data -> 5V data)

### Why this wiring method

- 20-30 LEDs can exceed safe current for direct Pico GPIO drive.
- WS2812 strips use one data pin for many LEDs, so wiring and code stay simple.
- External 5V handles LED current; Pico only provides control signals.

### Power sizing quick rule

- Worst-case WS2812 estimate: up to 60 mA per LED at full white.
- Example: 30 LEDs -> 1.8A worst-case.
- This code mostly uses one color channel and caps brightness, so real current is much lower, but 5V/2A is still a good minimum.

### Wiring steps (important)

1. Power rails:
   - External supply +5V -> LED strip +5V
   - External supply GND -> LED strip GND
2. Common ground:
   - Pico GND -> same external supply GND rail (required)
3. Data lines:
   - Pico GP2 -> 330 ohm resistor -> Water strip DIN
   - Pico GP3 -> 330 ohm resistor -> Electricity strip DIN
4. Stabilization capacitor:
   - 1000 uF capacitor across strip +5V and GND near strip input
5. Potentiometers:
   - Pot #1 center -> GP26, outer pins -> 3V3 and GND
   - Pot #2 center -> GP27, outer pins -> 3V3 and GND
6. Optional level shifting:
   - Insert 74AHCT125/74HCT245 between Pico data pins and strip DIN pins for robust signaling.

### Safety notes

- Do not power long strips from Pico 3V3 or VSYS.
- Inject 5V/GND at both ends of longer strips if brightness droop appears.
- If colors flicker or data is unreliable, add level shifter and keep data wires short.
