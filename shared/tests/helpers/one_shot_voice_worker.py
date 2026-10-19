"""Deterministic one-shot worker writing split and CRLF-terminated JSON lines."""

import json
import sys
import time

out = sys.stdout.buffer
request = sys.stdin.buffer.readline()
# One event split across two writes, then two events in a single write.
out.write(b'{"event": "progress", "phase": "lo')
out.flush()
time.sleep(0.05)
out.write(b'ad", "message": "Chargement", "percent": 10}\r\n')
echo = json.dumps(request.decode("ascii")).encode("ascii")
out.write(b'{"event": "transcript", "text": ' + echo + b"}\n")
out.write(b'{"event": "result", "data": {"cached": true}}\n')
out.flush()
time.sleep(0.2)
