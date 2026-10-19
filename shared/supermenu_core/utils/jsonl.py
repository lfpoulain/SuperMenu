"""JSON-lines framing for the private worker processes.

The local voice workers and the Windows text worker exchange one JSON object
per line over their stdio pipes. This module only frames those bytes: each
supervisor keeps its own size limit, decoding policy, errors and messages.
"""

import json


def encode_json_line(message, *, ensure_ascii=True):
    """Serialize ``message`` as one UTF-8, newline-terminated JSON line."""
    return json.dumps(message, ensure_ascii=ensure_ascii).encode("utf-8") + b"\n"


class JsonLineBuffer:
    """Reassemble complete lines from the chunks read on a worker's stdout."""

    def __init__(self, max_bytes):
        self.max_bytes = max_bytes
        self.data = b""

    @property
    def overflowed(self):
        """True once more than ``max_bytes`` are pending, complete lines included."""
        return len(self.data) > self.max_bytes

    def feed(self, chunk):
        self.data += bytes(chunk)

    def has_line(self):
        return b"\n" in self.data

    def pop_line(self):
        """Remove and return the next complete line, without its ``\\n``."""
        line, self.data = self.data.split(b"\n", 1)
        return line

    def clear(self):
        self.data = b""
