# Cornerstone Project 2 — Final Project

A resource-management game running on a Raspberry Pi Pico 2. Two physical dials control electricity and water usage; 16 LEDs show each resource's level in real time. A web interface mirrors the game and lets you control it from your computer too.

---

## Files

| File | Where it runs | What it does |
|------|--------------|--------------|
| `main.py` | Raspberry Pi Pico 2 | Full game logic, LED control, serial communication |
| `bridge.py` | Your Mac/PC | Connects Pico serial to the browser over WebSocket |
| `index.html` | Your browser | Game interface — identical to the simulation |

---

## Hardware

### Microcontroller
Raspberry Pi Pico 2 (RP2350), connected to your computer over USB.

### Pin assignments

| Pin | What's connected |
|-----|-----------------|
| GP26 (ADC0) | Water potentiometer — wiper to GP26, one side to 3V3, other side to GND |
| GP27 (ADC1) | Electricity potentiometer — same wiring |
| GP0 – GP7 | Water LEDs (anode to GPIO, cathode to GND) |
| GP8 – GP15 | Electricity LEDs (anode to GPIO, cathode to GND) |

### No resistors needed
The code acts as a software resistor for the LEDs. It uses PWM at 500 Hz with the duty cycle capped at 15%, which keeps average LED current around 0.5–1 mA — well within safe limits for both the LED and the GPIO pin. The GPIO drive strength is also set to its minimum (2 mA). Do not exceed 15 LEDs total without revisiting power draw.

---

## How to run

### Step 1 — Flash the Pico

Copy `main.py` to the Pico's root filesystem. The easiest ways:

**Using Thonny:**
1. Open Thonny, connect the Pico.
2. Open `main.py` from this folder.
3. File → Save As → Raspberry Pi Pico → save as `main.py`.

**Using mpremote (command line):**
```bash
pip install mpremote
mpremote connect auto cp main.py :main.py
```

Once flashed, `main.py` runs automatically every time the Pico powers on.

### Step 2 — Install Python dependencies (one time)

```bash
pip install pyserial websockets
```

### Step 3 — Start the bridge

```bash
cd path/to/final-project
python3 bridge.py
```

The bridge will auto-detect the Pico. If it can't find it, it will list available serial ports and ask you to pick one. You can also pass the port explicitly:

```bash
python3 bridge.py /dev/tty.usbmodem101      # macOS
python3 bridge.py COM5                       # Windows
python3 bridge.py /dev/ttyACM0              # Linux
```

You should see output like:
```
Auto-detected Pico on /dev/tty.usbmodem101
Serial:      /dev/tty.usbmodem101 @ 115200 baud
Interface:   http://localhost:8080
WebSocket :  ws://localhost:8765
Press Ctrl-C to quit.
```

### Step 4 — Open the interface

Go to **http://localhost:8080** in your browser. The game starts immediately.

---

## How to play

### The three zones

Each resource (electricity and water) has a spend level set by the physical dial or the on-screen slider. The spend level determines what zone you're in:

| Zone | Spend | Effect |
|------|-------|--------|
| Too low | 0–10% | Resource slowly bleeds. Stay here too long and it locks up for 15 s. |
| Sweet spot | 10–35% | Resource recharges. You earn cards every 8 s (if level > 50%). |
| Too high | 35–100% | Resource drains fast. Hit 0% and it locks out for 15 s. |

### Cards and upgrades

- Earn **electricity cards** by keeping electricity spend in the sweet spot while the electricity level is above 50%.
- Earn **water cards** the same way for water.
- Spend cards on upgrades:
  - **Solar panel** (3 electricity cards + 1 water card) — boosts electricity regen. Up to 8 panels (2.2× regen at max).
  - **Water tower** (3 water cards + 1 electricity card) — boosts water regen. Up to 4 towers (1.9× regen at max).

### Events

| Event | Cause | Effect |
|-------|-------|--------|
| Blackout | Electricity hit 0% from overuse | Electricity locked for 15 s, dial/slider disabled |
| Drought | Water hit 0% from overuse | Water locked for 15 s, dial/slider disabled |
| Stagnation | Spend stayed below 10% for 15 s | That resource locked for 15 s |
| Chronic crisis | Resource below 10% for 20 s straight | Warning logged |

During any lockout the LED bar for that resource flashes. It slowly recovers on its own.

### Dials vs sliders

The physical dials and the browser sliders both work at the same time. Moving a slider on the browser overrides the dial. Turning the physical dial more than ~3% takes back control. During a lockout, both are disabled and the spend is forced to zero.

---

## Architecture

```
[Pico 2]  ── USB serial (JSON @ 20 Hz) ──▶  [bridge.py]  ──▶  [Browser]
   │                                              │                 │
   │  Game logic                         HTTP :8080           WebSocket
   │  LED bar graphs                     (serves HTML)         :8765
   │  ADC pot reading                         │
   │                                    [index.html]
   ◀── Commands (setSpend / upgrade) ──────────┘
```

- **Pico** owns all game state and sends the full state as a JSON line every 50 ms.
- **bridge.py** relays that JSON to WebSocket clients and forwards browser commands back to the Pico over serial.
- **index.html** is a display + input layer only — no game logic runs in the browser.
