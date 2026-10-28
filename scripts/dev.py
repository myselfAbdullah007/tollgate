"""Start only Tollgate processes. Refuse occupied ports; never kill other projects."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
os.chdir(root)
for port in (8187, 3187):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            sys.exit(f'Port {port} is occupied. Choose another port in config before starting Tollgate.')
env = dict(os.environ, TOLLGATE_DEMO='true')
children = [subprocess.Popen([str(root / '.venv/bin/tollgate'), 'serve'], env=env),
            subprocess.Popen(['npm', 'run', 'dev', '--prefix', 'apps/dashboard'], env=env)]

def stop(*_):
    for child in children:
        child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
print('Tollgate dashboard: http://localhost:3187 · Gateway: http://localhost:8187', flush=True)
while True:
    if any(c.poll() is not None for c in children):
        stop()
    time.sleep(.5)
