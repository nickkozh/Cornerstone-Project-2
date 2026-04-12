import sys, json, time, uselect
from machine import ADC, PWM, Pin

POT_WATER = ADC(26)
POT_ELEC  = ADC(27)

WATER_LED_PINS = [0, 1, 2, 3, 4, 5, 6, 7]
ELEC_LED_PINS  = [8, 9, 10, 11, 12, 13, 14, 15]

PWM_FREQ = 500
DUTY_MAX = 9830   # 15% of 65535

NT       = 35.0
LT       = 10.0
DRAIN    = 1.5
REGEN    = 0.8
STAG_DR  = 0.5
BLKOUT_D = 15.0
BLKOUT_R = 0.2
LOW_TH   = 10.0
CRISIS_T = 30.0
STAG_T   = 20.0
CARD_INT = 12.0
CARD_MIN = 50.0
LOOP_MS  = 50

def solar_mult(p): return 1.0 + (p - 2) * 0.2
def tower_mult(t): return 1.0 + (t - 1) * 0.3

def make_pwm_leds(pins):
    out = []
    for p in pins:
        try:
            pin = Pin(p, Pin.OUT, drive=Pin.DRIVE_0)
        except (TypeError, AttributeError):
            pin = Pin(p, Pin.OUT)
        out.append(PWM(pin, freq=PWM_FREQ, duty_u16=0))
    return out

water_leds = make_pwm_leds(WATER_LED_PINS)
elec_leds  = make_pwm_leds(ELEC_LED_PINS)

def set_bar(leds, level, locked, flash_on):
    n, seg = len(leds), 100.0 / len(leds)
    brightness = 0.2 + 0.8 * (level / 100.0)
    scaled_max = int(DUTY_MAX * brightness)
    for i, led in enumerate(leds):
        if locked:
            led.duty_u16(DUTY_MAX // 4 if flash_on else 0)
        elif level >= (i + 1) * seg:
            led.duty_u16(scaled_max)
        elif level > i * seg:
            frac = (level - i * seg) / seg
            led.duty_u16(int(scaled_max * (frac ** 0.5)))
        else:
            led.duty_u16(0)

def read_pot(adc):
    for _ in range(8):
        adc.read_u16()
        time.sleep_us(50)
    total = 0
    for _ in range(4):
        total += adc.read_u16()
        time.sleep_us(50)
    pct = (total / 4) / 65535.0 * 100.0
    return 0.0 if pct < 1.5 else pct

S = {
    'e': 50.0, 'w': 50.0,
    'es': 0.0,  'ws': 0.0,
    'sp': 2,    'wt': 1,
    'ec': 0,    'wc': 0,
    'eb': 0.0,  'wd': 0.0,
    'stagE': 0.0, 'stagW': 0.0,
    'elt': 0.0, 'wlt': 0.0,
    'est': 0.0, 'wst': 0.0,
    'ect': 0.0, 'wct': 0.0,
    't': 0.0,
    '_web_e': None, '_web_w': None,
    'pots': False,
    'ended': False,
}

_pending_evts = []

def update_res(rk, sk, bk, sgk, eltk, estk, ectk, ck, mul, dt):
    events = []
    sp = S[sk]

    if S[bk] > 0:
        S[bk] -= dt
        S[rk] = min(100.0, S[rk] + BLKOUT_R * dt)
        if S[bk] <= 0:
            S[bk] = 0.0
            S[sk] = 20.0
            events.append('end_blackout' if rk == 'e' else 'end_drought')
        S[estk] = 0.0
        return events

    if S[sgk] > 0:
        S[sgk] -= dt
        S[rk] = min(100.0, S[rk] + BLKOUT_R * dt)
        if S[sgk] <= 0:
            S[sgk] = 0.0
            S[sk] = 20.0
            events.append('end_stag_e' if rk == 'e' else 'end_stag_w')
        S[estk] = 0.0
        return events

    if sp > NT:
        S[rk] = max(0.0, S[rk] - ((sp - NT) / (100.0 - NT)) * DRAIN * dt)
        S[estk] = 0.0
    elif sp >= LT:
        S[rk] = min(100.0, S[rk] + REGEN * mul * dt)
        S[estk] = max(0.0, S[estk] - dt * 0.8)
    else:
        depth = (LT - sp) / LT
        S[rk] = max(0.0, S[rk] - depth * STAG_DR * dt)
        S[estk] = min(STAG_T, S[estk] + depth * dt)
        if S[estk] >= STAG_T:
            S[estk] = 0.0
            if S[sgk] <= 0:
                S[sgk] = BLKOUT_D
                S[sk]  = 0.0
                events.append('stag_e' if rk == 'e' else 'stag_w')
            return events

    if S[rk] <= 0.0 and sp > NT:
        S[rk] = 0.0
        if S[bk] <= 0:
            S[bk] = BLKOUT_D
            S[sk] = 0.0
            events.append('blackout' if rk == 'e' else 'drought')
        return events

    if S[rk] < LOW_TH:
        S[eltk] += dt
        if S[eltk] >= CRISIS_T:
            S[eltk] = 0.0
            events.append('chronic_e' if rk == 'e' else 'chronic_w')
    else:
        S[eltk] = max(0.0, S[eltk] - dt * 0.5)

    if LT <= sp <= NT and S[rk] > CARD_MIN and S[ck] < 10:
        S[ectk] += dt
        if S[ectk] >= CARD_INT:
            S[ectk] = 0.0
            S[ck] += 1
            events.append('card_e' if rk == 'e' else 'card_w')
    else:
        S[ectk] = max(0.0, S[ectk] - dt * 0.5)

    return events

_poller = uselect.poll()
_poller.register(sys.stdin, uselect.POLLIN)
_rbuf   = ''

def try_read_cmd():
    global _rbuf
    while True:
        if not _poller.poll(0):
            break
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch == '\n':
            line = _rbuf.strip()
            _rbuf = ''
            if line:
                _handle_cmd(line)
        else:
            _rbuf += ch

def _handle_cmd(line):
    global _pending_evts
    try:
        cmd = json.loads(line)
    except Exception:
        return
    c = cmd.get('cmd', '')

    if c == 'endGame':
        S['ended'] = True
        for led in water_leds + elec_leds:
            led.duty_u16(0)

    elif c == 'setInputMode':
        S['pots'] = bool(cmd.get('pots', False))

    elif c == 'setSpend':
        v = float(cmd.get('val', 0.0))
        if cmd.get('res') == 'e':
            S['_web_e'] = v
        elif cmd.get('res') == 'w':
            S['_web_w'] = v

    elif c == 'upgrade':
        t = cmd.get('type', '')
        if t == 'solar' and S['sp'] < 6 and S['ec'] >= 3 and S['wc'] >= 1:
            S['ec'] -= 3; S['wc'] -= 1; S['sp'] += 1
            _pending_evts.append('solar_bought')
        elif t == 'tower' and S['wt'] < 3 and S['wc'] >= 3 and S['ec'] >= 1:
            S['wc'] -= 3; S['ec'] -= 1; S['wt'] += 1
            _pending_evts.append('tower_bought')

    elif c == 'resetGame':
        S['e'] = 50.0; S['w'] = 50.0
        S['es'] = 0.0;  S['ws'] = 0.0
        S['sp'] = 2;    S['wt'] = 1
        S['ec'] = 0;    S['wc'] = 0
        S['eb'] = 0.0;  S['wd'] = 0.0
        S['stagE'] = 0.0; S['stagW'] = 0.0
        S['elt'] = 0.0; S['wlt'] = 0.0
        S['est'] = 0.0; S['wst'] = 0.0
        S['ect'] = 0.0; S['wct'] = 0.0
        S['t'] = 0.0
        S['_web_e'] = None; S['_web_w'] = None
        S['pots'] = False
        S['ended'] = False
        _pending_evts.append('game_reset')

def send_state(events):
    out = {
        'elec':  round(S['e'],     1), 'water': round(S['w'],     1),
        'es':    round(S['es'],    1), 'ws':    round(S['ws'],    1),
        'ec':    S['ec'],              'wc':    S['wc'],
        'sp':    S['sp'],              'wt':    S['wt'],
        'pots':  S['pots'],
        'eb':    round(S['eb'],    1), 'wd':    round(S['wd'],    1),
        'stagE': round(S['stagE'], 1), 'stagW': round(S['stagW'], 1),
        'elt':   round(S['elt'],   1), 'wlt':   round(S['wlt'],   1),
        'est':   round(S['est'],   1), 'wst':   round(S['wst'],   1),
        'ect':   round(S['ect'],   1), 'wct':   round(S['wct'],   1),
        't':     round(S['t'],     1),
        'ev':    events,
    }
    print(json.dumps(out))

_last_ms    = time.ticks_ms()
_flash_on   = False
_flash_ctr  = 0
_prev_pot_e = 0.0
_prev_pot_w = 0.0

while True:
    now_ms = time.ticks_ms()
    dt = time.ticks_diff(now_ms, _last_ms) / 1000.0
    _last_ms = now_ms
    if dt <= 0: dt = 0.001

    try_read_cmd()

    if S['ended']:
        time.sleep_ms(LOOP_MS)
        continue

    raw_w = read_pot(POT_WATER)
    raw_e = read_pot(POT_ELEC)

    if S['pots']:
        if S['_web_e'] is not None and abs(raw_e - _prev_pot_e) > 3.0:
            S['_web_e'] = None
        if S['_web_w'] is not None and abs(raw_w - _prev_pot_w) > 3.0:
            S['_web_w'] = None
        pe, pw = raw_e, raw_w
    else:
        if abs(raw_e - _prev_pot_e) > 5.0 or abs(raw_w - _prev_pot_w) > 5.0:
            S['pots'] = True
            S['_web_e'] = None
            S['_web_w'] = None
            pe, pw = raw_e, raw_w
        else:
            pe = S['_web_e'] if S['_web_e'] is not None else 0.0
            pw = S['_web_w'] if S['_web_w'] is not None else 0.0

    _prev_pot_e = raw_e
    _prev_pot_w = raw_w

    if S['eb'] <= 0 and S['stagE'] <= 0:
        S['es'] = S['_web_e'] if S['_web_e'] is not None else pe
    else:
        S['es'] = 0.0

    if S['wd'] <= 0 and S['stagW'] <= 0:
        S['ws'] = S['_web_w'] if S['_web_w'] is not None else pw
    else:
        S['ws'] = 0.0

    S['t'] += dt
    evts  = []
    prev_es, prev_ws = S['es'], S['ws']
    evts += update_res('e', 'es', 'eb',  'stagE', 'elt', 'est', 'ect', 'ec',
                        solar_mult(S['sp']), dt)
    evts += update_res('w', 'ws', 'wd',  'stagW', 'wlt', 'wst', 'wct', 'wc',
                        tower_mult(S['wt']), dt)
    if S['es'] == 20.0 and prev_es != 20.0:
        S['_web_e'] = 20.0
    if S['ws'] == 20.0 and prev_ws != 20.0:
        S['_web_w'] = 20.0

    evts += _pending_evts
    _pending_evts = []

    _flash_ctr += 1
    if _flash_ctr >= 6:
        _flash_ctr = 0
        _flash_on  = not _flash_on

    set_bar(elec_leds,  S['e'], S['eb']  > 0 or S['stagE'] > 0, _flash_on)
    set_bar(water_leds, S['w'], S['wd']  > 0 or S['stagW'] > 0, _flash_on)

    send_state(evts)

    elapsed = time.ticks_diff(time.ticks_ms(), now_ms)
    rem = LOOP_MS - elapsed
    if rem > 0:
        time.sleep_ms(rem)
