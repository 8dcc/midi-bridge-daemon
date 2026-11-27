# Copyright 2026 8dcc. All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Messages exchanged between the daemon and GUI clients over a Unix socket.

The socket is at socket_path(). Each message is a JSON object on its own line.
Messages are plain dicts; this module builds them, encodes and decodes them,
and checks their shape and types. It does not check value ranges.

Sent by the daemon to every client when it connects and after every change:

    {"type": "state", "device_connected": true, "selected_knob": 2,
     "knobs": [{"cc": 20, "value": 64, "sensitivity": 1, "fine": 1,
                "coarse": 8}, ...]}

Sent by a client to change any subset of a knob's settings (SETTING_NAMES):

    {"type": "set_knob", "knob": 3, "settings": {"sensitivity": 5}}

Sent by the daemon only to a client whose request failed:

    {"type": "error", "message": "coarse must be in 1..127"}
"""

import json
import os

SOCKET_NAME = "midi-bridge-daemon.sock"

SETTING_NAMES = ("sensitivity", "fine", "coarse")

KNOB_FIELDS = ("cc", "value") + SETTING_NAMES


class ProtocolError(Exception):
    """A received line is not a valid message."""


def socket_path() -> str:
    """Return the socket path inside $XDG_RUNTIME_DIR, or a /tmp fallback."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return os.path.join(runtime_dir, SOCKET_NAME)
    return f"/tmp/midi-bridge-daemon-{os.getuid()}.sock"


def encode(message: dict) -> bytes:
    """Return 'message' as one compact JSON line."""
    return json.dumps(message, separators=(",", ":")).encode() + b"\n"


def decode(line: bytes) -> dict:
    """Return the JSON object in 'line', or raise ProtocolError."""
    try:
        message = json.loads(line.decode())
    except UnicodeDecodeError:
        raise ProtocolError("line is not valid UTF-8") from None
    except json.JSONDecodeError:
        raise ProtocolError("invalid JSON") from None
    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")
    return message


def knob_entry(cc: int, value: int, sensitivity: int, fine: int,
               coarse: int) -> dict:
    """Return one element of the 'knobs' list of a state message."""
    return {"cc": cc, "value": value, "sensitivity": sensitivity,
            "fine": fine, "coarse": coarse}


def state_message(knobs: list[dict], selected_knob: int,
                  device_connected: bool) -> dict:
    """Return a state message; 'knobs' is a list of knob_entry() dicts."""
    return {"type": "state", "device_connected": device_connected,
            "selected_knob": selected_knob, "knobs": knobs}


def error_message(text: str) -> dict:
    """Return an error message with the specified 'text'."""
    return {"type": "error", "message": text}


def set_knob_message(knob: int, settings: dict[str, int]) -> dict:
    """Return a request to change the 'settings' of the knob at 'knob'."""
    return {"type": "set_knob", "knob": knob, "settings": settings}


def _is_int(value) -> bool:
    """True if 'value' is a real integer (JSON booleans are not)."""
    return type(value) is int


def _check_set_knob(message: dict) -> None:
    """Raise ProtocolError if 'message' is not a valid set_knob request."""
    if not _is_int(message.get("knob")):
        raise ProtocolError("knob must be an integer")
    settings = message.get("settings")
    if not isinstance(settings, dict) or not settings:
        raise ProtocolError("settings must be a non-empty object")
    for name, value in settings.items():
        if name not in SETTING_NAMES:
            raise ProtocolError(f"unknown setting: {name}")
        if not _is_int(value):
            raise ProtocolError(f"{name} must be an integer")


def _check_knob_entry(knob) -> None:
    """Raise ProtocolError if 'knob' is not a valid knob_entry() dict."""
    if not isinstance(knob, dict):
        raise ProtocolError("each knob must be an object")
    for field in KNOB_FIELDS:
        if not _is_int(knob.get(field)):
            raise ProtocolError(f"knob {field} must be an integer")


def _check_state(message: dict) -> None:
    """Raise ProtocolError if 'message' is not a valid state message."""
    if type(message.get("device_connected")) is not bool:
        raise ProtocolError("device_connected must be a boolean")
    if not _is_int(message.get("selected_knob")):
        raise ProtocolError("selected_knob must be an integer")
    knobs = message.get("knobs")
    if not isinstance(knobs, list):
        raise ProtocolError("knobs must be a list")
    for knob in knobs:
        _check_knob_entry(knob)


def _check_error(message: dict) -> None:
    """Raise ProtocolError if 'message' is not a valid error message."""
    if not isinstance(message.get("message"), str):
        raise ProtocolError("message must be a string")


def parse_request(line: bytes) -> dict:
    """
    Return the request in 'line', sent by a client. Raise ProtocolError if it
    is not a valid request.
    """
    message = decode(line)
    if message.get("type") != "set_knob":
        raise ProtocolError(f"unknown type: {message.get('type')}")
    _check_set_knob(message)
    return message


def parse_reply(line: bytes) -> dict:
    """
    Return the message in 'line', sent by the daemon. Raise ProtocolError if it
    is not a valid message.
    """
    message = decode(line)
    match message.get("type"):
        case "state":
            _check_state(message)
        case "error":
            _check_error(message)
        case other:
            raise ProtocolError(f"unknown type: {other}")
    return message
