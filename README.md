# Cornerstone Project 2 — Final Project

A resource-management game running on a Raspberry Pi Pico 2. Two physical dials control electricity and water usage; 16 LEDs show each resource's level in real time. A web interface mirrors the game and lets you control it from your computer too.

---

## Files

| File | Where it runs | What it does |
|------|--------------|--------------|
| `main.py` | Raspberry Pi Pico 2 | Full game logic, LED control, serial communication |
| `bridge.py` | Your Mac/PC | Connects Pico serial to the browser over WebSocket; auto-restarts if the Pico disconnects |
| `index.html` | Your browser | Game interface |

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
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### Step 3 — Start the bridge

```bash
source venv/bin/activate
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

If the Pico is unplugged or rebooted (e.g. after re-flashing), the bridge detects the disconnect and restarts automatically — no need to rerun it manually.

### Step 4 — Open the interface

Go to **http://localhost:8080** in your browser and click **Start Game**.

---

## How to play

### The three zones

Each resource (electricity and water) has a spend level set by the physical dial or the on-screen slider. The spend level determines what zone you're in:

| Zone | Spend | Effect |
|------|-------|--------|
| Too low | 0–10% | Resource slowly bleeds. Stay here too long and it locks up for 15 s. |
| Sweet spot | 10–35% | Resource recharges at 2%/s (faster with upgrades). You earn cards every 8 s (if level > 50%). |
| Too high | 35–100% | Resource drains fast. Hit 0% and it locks out for 15 s. |

### Input mode

The game supports two input modes, switchable at any time using the button in the top-right of the connection bar:

- **Digital sliders** (default) — use the on-screen sliders in the browser.
- **Physical dials** — use the potentiometers wired to the Pico.

The game switches modes automatically:
- Turn a physical dial more than 5% → switches to **Physical dials**.
- Move an on-screen slider → switches to **Digital sliders**.

### Cards and upgrades

- Earn **electricity cards** by keeping electricity spend in the sweet spot while the electricity level is above 50%.
- Earn **water cards** the same way for water.
- Spend cards on upgrades:
  - **Solar panel** (3 electricity cards + 1 water card) — boosts electricity regen. Up to 6 panels.
  - **Water tower** (3 water cards + 1 electricity card) — boosts water regen. Up to 3 towers.

### Events

| Event | Cause | Effect |
|-------|-------|--------|
| Blackout | Electricity hit 0% from overuse | Electricity locked for 15 s, dial/slider disabled |
| Drought | Water hit 0% from overuse | Water locked for 15 s, dial/slider disabled |
| Stagnation | Spend stayed below 10% for 15 s | That resource locked for 15 s |
| Chronic crisis | Resource below 10% for 20 s straight | Warning logged |

During any lockout the LED bar for that resource flashes. It slowly recovers on its own.

### Sessions

Click **End Session** to stop the game. All LEDs turn off and the Pico idles until a new session is started. Each session is logged to `sessions.csv` with the date, start/end times, and duration.

Click **Play Again** on the end screen to reset and start a new session.

---

## Architecture

```
[Pico 2]  ── USB serial (JSON @ 20 Hz) ──▶  [bridge.py]  ──▶  [Browser]
   │                                              │                 │
   │  Game logic                         HTTP :8080           WebSocket
   │  LED bar graphs                     (serves HTML)         :8765
   │  ADC pot reading                         │
   │                                    [index.html]
   ◀── Commands (setSpend / setInputMode / upgrade / endGame) ───┘
```

- **Pico** owns all game state and sends the full state as a JSON line every 50 ms.
- **bridge.py** relays that JSON to WebSocket clients and forwards browser commands back to the Pico over serial. It also handles session timing and CSV logging.
- **index.html** is a display + input layer only — no game logic runs in the browser.
