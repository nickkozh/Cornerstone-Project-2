# Pico Town Utility Simulation

This project simulates two town utilities on an RP2040 (Raspberry Pi Pico):

- **Water** → blue NeoPixel flow strip + 3-LED gauge  
- **Electricity** → red NeoPixel flow strip + 3-LED gauge  

Flow is handled with WS2812 (NeoPixel) strips powered externally at 5V, while the gauges are simple GPIO LEDs.

---

## Files

- `main.py` — full MicroPython firmware (everything runs from here)

---

## Hardware Mapping (from `main.py`)

### Knobs (potentiometers)

- Water knob (middle pin) → GP26 / ADC0  
- Electricity knob (middle pin) → GP27 / ADC1  
- Outer pins → 3V3 + GND  

---

### LED Strips (NeoPixel / WS2812)

- Water strip data → GP2  
- Electricity strip data → GP3  

Defaults in `main.py`:
- 15 LEDs per strip (flow only, gauges are separate)

---

### Gauge LEDs (standard LEDs)

- Water → GP6, GP7, GP8  
- Electricity → GP9, GP10, GP11  
- Each LED needs a series resistor (220–470Ω)

---

All pin assignments and LED counts can be adjusted near the top of `main.py`.

---

## Behavior Model

Each utility runs the same logic:

- `flow_pct` = knob position  
- Higher flow increases drain:
  - `drain_per_sec = MAX_DRAIN_PER_SEC * (flow_pct / 100)`

- When flow is below the threshold, refill occurs:
  - `refill_per_sec = MAX_REFILL_PER_SEC * ((REFILL_THRESHOLD - flow_pct) / REFILL_THRESHOLD)`

- Net change per loop:
  - `level += (refill_per_sec - drain_per_sec) * dt`

The level is clamped between 0 and 100.

---

## Tuning

Constants are defined near the top of `main.py`:

- `MAX_DRAIN_PER_SEC` → drain rate  
- `REFILL_THRESHOLD` → refill trigger point  
- `MAX_REFILL_PER_SEC` → refill rate  
- `SMOOTH_ALPHA` → knob smoothing  
- `FLOW_BRIGHTNESS_CAP` → LED brightness limit  
- `LOOP_MS` → loop timing  

---

## Flashing to Pico

1. Install MicroPython (UF2) on the Pico  
2. Open Thonny (or another MicroPython IDE)  
3. Copy `main.py` to the Pico  
4. Reset the board  

---

## Build Info (20–30 LEDs)

### Parts

- 1× Raspberry Pi Pico / Pico W  
- 2× 10k potentiometers  
- 2× WS2812 (NeoPixel) strips *(or 1 split into 2)*  
- 6× standard LEDs (3 per utility)  
- 6× 220–470Ω resistors (for gauge LEDs)  
- 1× 5V power supply (2A+ recommended)  
- 2× 330Ω resistors (data lines)  
- 1× 1000µF capacitor (across 5V + GND)  
- Breadboard / perfboard + wires  

Optional:
- 74AHCT125 or 74HCT245 (level shifter for data signal)

---

## Why this setup

- WS2812 strips allow multiple LEDs to be controlled from a single data pin  
- External 5V power handles LED current requirements  
- The Pico is used only for control signals  

---

## Wiring

### Power

- External 5V → LED strip +5V  
- External GND → LED strip GND  

### Common Ground

- Pico GND → same GND as external supply  

### Data

- GP2 → 330Ω resistor → Water strip DIN  
- GP3 → 330Ω resistor → Electricity strip DIN  

### Capacitor

- 1000µF capacitor across +5V and GND near LED input  

### Potentiometers

- Pot 1 center → GP26  
- Pot 2 center → GP27  
- Outer pins → 3V3 + GND  

### Gauge LEDs

- Water LEDs → GP6, GP7, GP8 (through resistors)  
- Electricity LEDs → GP9, GP10, GP11 (through resistors)  
- Cathodes → GND  

### Optional Level Shifting

- Use 74AHCT125 / 74HCT245 between Pico data pins and LED strips for improved signal reliability  

---

## Notes

- Do not power LED strips from Pico 3V3 or VSYS  
- For longer strips, power injection at multiple points may be needed  
- If signal issues occur, reduce wire length or use a level shifter  