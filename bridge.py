#!/usr/bin/env python3
import asyncio
import csv
import json
import os
import sys
import threading
import time
import http.server
import socketserver

import serial
import serial.tools.list_ports

HTTP_PORT  = 8080
WS_PORT    = 8765
WS_HOST    = ''
BAUD       = 115200
HTML_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
CSV_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions.csv')

_ws_clients: set  = set()
_latest: dict     = {}
_ws_loop          = None
_ws_queue         = None
_ser_ref          = [None]
_session_start    = None


def _log_session(start_ts: float, end_ts: float):
    duration_s = round(end_ts - start_ts)
    mm, ss = divmod(duration_s, 60)
    new_file = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, 'a', newline='') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['date', 'start_time', 'end_time', 'duration_s', 'duration_mm_ss'])
        w.writerow([
            time.strftime('%Y-%m-%d', time.localtime(start_ts)),
            time.strftime('%H:%M:%S', time.localtime(start_ts)),
            time.strftime('%H:%M:%S', time.localtime(end_ts)),
            duration_s,
            f'{mm}:{ss:02d}',
        ])
    print(f'[session] logged {mm}:{ss:02d} to {CSV_FILE}')


class _HTMLHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            try:
                with open(HTML_FILE, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'index.html not found')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass


def _http_thread():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', HTTP_PORT), _HTMLHandler) as srv:
        srv.serve_forever()


def _serial_thread(ser):
    global _latest
    _consecutive_errors = 0
    while True:
        try:
            raw = ser.readline()
            if not raw:
                _consecutive_errors += 1
                if _consecutive_errors >= 5:
                    print('[serial] Pico disconnected.', file=sys.stderr)
                    return
                continue
            _consecutive_errors = 0
            line = raw.decode('utf-8', errors='ignore').strip()
            if not line.startswith('{'):
                continue
            state = json.loads(line)
            _latest = state
            if _ws_loop is not None and _ws_queue is not None:
                asyncio.run_coroutine_threadsafe(_ws_queue.put(line), _ws_loop)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            _consecutive_errors += 1
            print(f'[serial] {e}', file=sys.stderr)
            if _consecutive_errors >= 5:
                print('[serial] Pico disconnected.', file=sys.stderr)
                return
            time.sleep(0.2)


def _serial_manager(hint):
    while True:
        ports = [p for p in serial.tools.list_ports.comports() if p.vid == 0x2E8A]
        port = hint or (ports[0].device if ports else None)
        if not port:
            time.sleep(0.5)
            continue
        try:
            ser = serial.Serial(port, BAUD, timeout=1)
        except serial.SerialException as e:
            print(f'[serial] Could not open {port}: {e}', file=sys.stderr)
            time.sleep(0.5)
            continue
        _ser_ref[0] = ser
        print(f'[serial] Connected on {port}')
        _serial_thread(ser)
        try:
            ser.close()
        except Exception:
            pass
        _ser_ref[0] = None
        print('[bridge] Waiting for Pico to reconnect...')
        time.sleep(0.5)


async def _ws_handler(websocket):
    global _ws_clients
    _ws_clients.add(websocket)
    print(f'Browser connected  ({len(_ws_clients)} client(s))')
    if _latest:
        try:
            await websocket.send(json.dumps(_latest))
        except Exception:
            pass
    try:
        async for msg in websocket:
            try:
                parsed = json.loads(msg)
                cmd = parsed.get('cmd', '')
            except Exception:
                parsed = {}; cmd = ''

            if cmd == 'startGame':
                global _session_start
                _session_start = time.time()
                print(f'[session] started at {time.strftime("%H:%M:%S")}')
                ser = _ser_ref[0]
                if ser and ser.is_open:
                    try:
                        ser.write((json.dumps({'cmd': 'resetGame'}) + '\n').encode())
                    except Exception as e:
                        print(f'[serial write] {e}', file=sys.stderr)

            elif cmd == 'endGame':
                end_ts = time.time()
                if _session_start is not None:
                    _log_session(_session_start, end_ts)
                    duration_s = round(end_ts - _session_start)
                    _session_start = None
                else:
                    duration_s = 0
                ser = _ser_ref[0]
                if ser and ser.is_open:
                    try:
                        ser.write((json.dumps({'cmd': 'endGame'}) + '\n').encode())
                    except Exception as e:
                        print(f'[serial write] {e}', file=sys.stderr)
                payload = json.dumps({'type': 'session_ended', 'duration_s': duration_s})
                dead = set()
                for ws in list(_ws_clients):
                    try:
                        await ws.send(payload)
                    except Exception:
                        dead.add(ws)
                _ws_clients -= dead

            else:
                ser = _ser_ref[0]
                if ser and ser.is_open:
                    try:
                        ser.write((msg + '\n').encode())
                    except Exception as e:
                        print(f'[serial write] {e}', file=sys.stderr)
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)
        print(f'Browser disconnected ({len(_ws_clients)} client(s))')


async def _broadcast_loop():
    global _ws_queue, _ws_clients
    _ws_queue = asyncio.Queue()
    while True:
        line = await _ws_queue.get()
        dead = set()
        for ws in list(_ws_clients):
            try:
                await ws.send(line)
            except Exception:
                dead.add(ws)
        _ws_clients -= dead


async def _main_async():
    global _ws_loop
    _ws_loop = asyncio.get_running_loop()

    try:
        import websockets
    except ImportError:
        sys.exit('websockets not installed. Run: pip install websockets')

    async with websockets.serve(_ws_handler, WS_HOST, WS_PORT, reuse_address=True):
        await _broadcast_loop()


def find_port(hint=None):
    if hint:
        return hint

    ports = serial.tools.list_ports.comports()

    for p in ports:
        if p.vid == 0x2E8A:
            print(f'Auto-detected Pico on {p.device}  ({p.description})')
            return p.device

    if not ports:
        sys.exit('No serial ports found — is the Pico plugged in?')

    print('Pico not auto-detected. Available ports:')
    for i, p in enumerate(ports):
        print(f'  [{i}] {p.device}  —  {p.description}')
    choice = input('Enter port number: ').strip()
    return ports[int(choice)].device


if __name__ == '__main__':
    hint = sys.argv[1] if len(sys.argv) > 1 else None

    print(f'Interface:   http://localhost:{HTTP_PORT}')
    print(f'WebSocket :  ws://{WS_HOST}:{WS_PORT}')
    print('Press Ctrl-C to quit.\n')

    threading.Thread(target=_http_thread, daemon=True).start()
    threading.Thread(target=_serial_manager, args=(hint,), daemon=True).start()

    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        print('\nShutting down.')
        if _ser_ref[0]:
            _ser_ref[0].close()
