#!/usr/bin/env python3
"""
bridge.py — connects Raspberry Pi Pico 2 (USB serial) to the web interface.

Install dependencies first:
    pip install pyserial websockets

Run:
    python3 bridge.py           # auto-detects Pico
    python3 bridge.py /dev/tty.usbmodem101   # explicit port (macOS example)

Then open http://localhost:8080 in your browser.
"""

import asyncio
import json
import os
import sys
import threading
import time
import http.server
import socketserver

import serial
import serial.tools.list_ports

# ── Config ────────────────────────────────────────────────────────────────────
HTTP_PORT = 8080
WS_PORT   = 8765
WS_HOST   = 'localhost'
BAUD      = 115200
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

# ── Shared state (thread-safe via asyncio primitives) ─────────────────────────
_ws_clients: set = set()
_latest: dict    = {}
_ws_loop         = None    # set once the asyncio loop starts
_ws_queue        = None    # asyncio.Queue, created inside the loop
_ser_ref         = [None]  # mutable ref so ws_handler can reach the serial port


# ── HTTP server ───────────────────────────────────────────────────────────────
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
        pass   # suppress access logs


def _http_thread():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', HTTP_PORT), _HTMLHandler) as srv:
        srv.serve_forever()


# ── Serial reader thread ──────────────────────────────────────────────────────
def _serial_thread(ser):
    global _latest
    while True:
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode('utf-8', errors='ignore').strip()
            if not line.startswith('{'):
                continue   # ignore MicroPython boot messages / REPL output
            state = json.loads(line)
            _latest = state
            # Hand off to asyncio loop (thread-safe)
            if _ws_loop is not None and _ws_queue is not None:
                asyncio.run_coroutine_threadsafe(_ws_queue.put(line), _ws_loop)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f'[serial] {e}', file=sys.stderr)
            time.sleep(0.1)


# ── WebSocket server ──────────────────────────────────────────────────────────
async def _ws_handler(websocket):
    _ws_clients.add(websocket)
    print(f'Browser connected  ({len(_ws_clients)} client(s))')
    # Send current snapshot immediately so the UI isn't blank on connect
    if _latest:
        try:
            await websocket.send(json.dumps(_latest))
        except Exception:
            pass
    try:
        async for msg in websocket:
            # Forward commands from browser → Pico over serial
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
    """Relay lines from the serial queue to all connected WebSocket clients."""
    global _ws_queue
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

    async with websockets.serve(_ws_handler, WS_HOST, WS_PORT):
        print(f'WebSocket :  ws://{WS_HOST}:{WS_PORT}')
        await _broadcast_loop()   # runs forever


# ── Serial port detection ─────────────────────────────────────────────────────
def find_port(hint=None):
    if hint:
        return hint

    ports = serial.tools.list_ports.comports()

    # Try to auto-detect Pico by USB VID (0x2E8A = Raspberry Pi)
    for p in ports:
        if p.vid == 0x2E8A:
            print(f'Auto-detected Pico on {p.device}  ({p.description})')
            return p.device

    # Fallback: let user pick
    if not ports:
        sys.exit('No serial ports found — is the Pico plugged in?')

    print('Pico not auto-detected. Available ports:')
    for i, p in enumerate(ports):
        print(f'  [{i}] {p.device}  —  {p.description}')
    choice = input('Enter port number: ').strip()
    return ports[int(choice)].device


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    hint = sys.argv[1] if len(sys.argv) > 1 else None
    port = find_port(hint)

    try:
        _ser_ref[0] = serial.Serial(port, BAUD, timeout=1)
    except serial.SerialException as e:
        sys.exit(f'Could not open {port}: {e}')

    print(f'Serial:      {port} @ {BAUD} baud')

    # HTTP server (background thread)
    threading.Thread(target=_http_thread, daemon=True).start()
    print(f'Interface:   http://localhost:{HTTP_PORT}')

    # Serial reader (background thread)
    threading.Thread(target=_serial_thread, args=(_ser_ref[0],), daemon=True).start()

    print('Press Ctrl-C to quit.\n')

    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        print('\nShutting down.')
        _ser_ref[0].close()
