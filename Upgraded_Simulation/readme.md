# Resource Balance — Game Logic & Rulebook

A physical LED game about managing electricity and water. Turn dials to control spend, watch your LEDs glow, and hold both resources in balance to earn upgrades. Too high and you burn out. Too low and you stagnate. The sweet spot is narrow on both ends — that's the point.

---

## Overview

Two resources. Two potentiometer dials. Two LED channels. The dials control brightness and spend simultaneously. Every consequence — drain rate, regen rate, card earning, event triggers — flows from where your dial sits relative to two thresholds.

---

## Starting State

| Item                | Value       |
|---------------------|-------------|
| Electricity         | 100%        |
| Water               | 100%        |
| Solar panels        | 2 (max 8)   |
| Water towers        | 1 (max 4)   |
| Electricity cards   | 0 (max 10)  |
| Water cards         | 0 (max 10)  |

---

## The Dials (Potentiometers)

Each resource has a dedicated dial. Turning it sets the **spend level** from 0% to 100%.

- The dial maps directly to **LED brightness** — higher spend = brighter LED
- Electricity LED glows **yellow**
- Water LED glows **blue**
- A very dim LED is a warning sign in both directions

---

## The Three Zones

Every spend level falls into one of three zones. The zone determines what happens to your resource.

```
0%       10%              35%                   100%
|--------|----------------|---------------------|
  STAG   |   SWEET SPOT   |      OVERUSE
```

### Zone 1 — Stagnation (spend below 10%)

The system is underused. Infrastructure degrades, pipes freeze, generators idle too long.

- Resource bleeds slowly at up to **1.5%/s** (proportional to how far below 10% you are)
- A **stagnation timer** fills up — faster the lower you go
- If the timer fills completely (15 seconds of max stagnation), a **stagnation event** fires
- The dial locks for 15 seconds; resource recovers slowly at 0.3%/s

### Zone 2 — Sweet Spot (spend 10%–35%)

The system is running efficiently. Resources recover and cards accumulate.

- Resource **regenerates** at up to 2%/s × upgrade multiplier
- Regen peaks near 10% and tapers to zero as you approach 35%
- Cards earn every 8 seconds (provided resource > 50%)
- The stagnation timer drains back down at 0.8×/s

### Zone 3 — Overuse (spend above 35%)

The system is being pushed too hard.

- Resource **drains** at up to 4%/s (proportional to how far above 35% you are)
- No card earning in this zone
- If resource hits 0%: blackout (electricity) or drought (water) fires

---

## Events

All three event types result in the **same lockout**: dial locks at 0, LED goes dark, 15 seconds of slow passive recovery (0.3%/s), then the dial unlocks.

### Blackout

Triggered when electricity resource hits **0%** from overuse.

### Drought

Triggered when water resource hits **0%** from overuse.

### Stagnation

Triggered when the stagnation timer fills completely. This happens when spend stays **below 10%** for roughly 15 continuous seconds at the extreme (0% spend). At higher values in the stagnation zone the timer fills more slowly — at 5% spend it takes about 30 seconds. At 9% it takes much longer.

The timer drains back down once you enter the sweet spot, at 0.8×/s, so a brief dip below 10% won't immediately punish you.

### Chronic Shortage Crisis

A secondary warning that fires independently of events. If your resource level stays **below 10% for 20 continuous seconds** without triggering a blackout/drought, a crisis event fires and the timer resets. This can keep firing as long as the situation continues.

Recovery: keeping resource above 10% reduces the crisis timer at half speed.

---

## Cards

Cards are the upgrade currency. They are earned passively by staying in the sweet spot.

### Earning Conditions (both must be true)

1. Dial is in the sweet spot: **10%–35%**
2. Resource level is **above 50%**

When both hold: **1 card every 8 seconds**. If either condition breaks, the card timer pauses and decays slowly. No partial credit carries over.

Each resource earns its own card type. Max 10 of each.

### Spending Cards

| Upgrade        | Cost                                  | Max |
|----------------|---------------------------------------|-----|
| Solar panel    | 3 electricity cards + 1 water card   | 8   |
| Water tower    | 3 water cards + 1 electricity card   | 4   |

Both upgrades require cards from **both** resources — you cannot ignore water to max electricity.

---

## Upgrade Multipliers

Upgrades increase the regen rate when in the sweet spot. They do not affect drain or stagnation.

### Solar Panels → Electricity Regen

```
multiplier = 1.0 + (panels − 2) × 0.2
```

| Panels | Multiplier | Peak regen |
|--------|------------|------------|
| 2      | 1.0×       | 2.0%/s     |
| 4      | 1.4×       | 2.8%/s     |
| 6      | 1.8×       | 3.6%/s     |
| 8      | 2.2×       | 4.4%/s     |

### Water Towers → Water Regen

```
multiplier = 1.0 + (towers − 1) × 0.3
```

| Towers | Multiplier | Peak regen |
|--------|------------|------------|
| 1      | 1.0×       | 2.0%/s     |
| 2      | 1.3×       | 2.6%/s     |
| 3      | 1.6×       | 3.2%/s     |
| 4      | 1.9×       | 3.8%/s     |

---

## Strategy Notes

**The core loop:** hold both dials in 10–35%, wait for cards, buy upgrades, gradually push dials higher as regen improves to compensate.

**Early game:** resist the temptation to set dials near 0 to "safely" farm cards. The stagnation zone punishes this. Aim for around 12–20% — close to the bottom of the sweet spot for maximum regen while staying out of the danger zone.

**Stagnation vs. blackout:** stagnation is slower and gives more warning (the stagnation bar fills gradually) but catches players who think ignoring a resource is a safe idle strategy. The overuse event is faster and more punishing (the resource bar drains in seconds at high spend).

**Upgrade priority:** water starts with only 1 tower (1.0× regen) versus 2 solar panels (also 1.0× but asymmetrically capped at 8 vs 4). Getting the first water tower early lets you bring water's regen closer to electricity's.

**Late game:** at max upgrades (8 solar, 4 water), you can push electricity to ~55% and water to ~50% and still recover quickly by pulling back. The LEDs are noticeably brighter. Reaching this state requires sustained discipline through the entire upgrade path.

---

## Reference

| Parameter                        | Value        |
|----------------------------------|--------------|
| Upper threshold (overuse begins) | 35% spend    |
| Lower threshold (stagnation begins) | 10% spend |
| Max drain rate                   | 4%/s at 100% |
| Max regen rate (base)            | 2%/s near 10%|
| Max stagnation bleed             | 1.5%/s at 0% |
| Event lockout duration           | 15 seconds   |
| Passive regen during lockout     | 0.3%/s       |
| Stagnation timer fill time       | 15 seconds (at 0% spend) |
| Stagnation timer decay rate      | 0.8×/s in sweet spot |
| Critical-low threshold           | 10% resource |
| Chronic crisis timer             | 20 seconds   |
| Card earn interval               | 8 seconds    |
| Minimum resource for cards       | 50%          |
| Solar regen step                 | +0.2× per panel |
| Water tower regen step           | +0.3× per tower |

---

## Running the Simulator

```
open index.html
```

### Quick start (easy version)

- Open `index.html` in a web browser (Chrome, Edge, Safari, Firefox).
- Use the two sliders. They work like the real knobs.
  - Higher slider = brighter light = you’re using more of that resource.
  - Lower slider = dimmer light = you’re using less.
- Your goal is to keep **both** resources healthy and earn cards for upgrades.

### How to open it

You don’t need a server or any installs.

- **Mac**: double-click `index.html` (or right-click → Open With → your browser)
- **Windows**: double-click `index.html`
- **Chromebook**: open `index.html` from the Files app

### Controls

- The sliders are the **potentiometers**.
- The bars/percent numbers are your **resource levels**.
- The card counters show how many upgrade cards you’ve earned.