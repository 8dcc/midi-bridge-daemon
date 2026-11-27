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

"""The Anticater knob, read through evdev."""

import asyncio
import errno
import logging

import evdev
from evdev import ecodes

from midi_bridge_daemon.device import (
    ConnectionEvent,
    Device,
    DeviceEvent,
    PushEvent,
    PushRotateEvent,
    RotateEvent,
)

log = logging.getLogger(__name__)

# Seconds to wait before looking for the device again
RETRY_SECONDS = 2.0

# Known (vendor, product) pairs, obtained from 'lsusb'
PRODUCT_IDS = ((0x514C, 0x8850), (0x05AC, 0x022C))

# Over Bluetooth the device reports zero IDs, e.g. "ANTICATER_MINI Keyboard"
NAME_PREFIX = "ANTICATER"

KEY_DOWN = 1
KEY_UP = 0

# Keys that map directly to an event when pressed. The device sends the
# brightness keys when it is turned while pushed.
SIMPLE_KEYS = {
    ecodes.KEY_VOLUMEUP: RotateEvent(1),
    ecodes.KEY_VOLUMEDOWN: RotateEvent(-1),
    ecodes.KEY_BRIGHTNESSUP: PushRotateEvent(1),
    ecodes.KEY_BRIGHTNESSDOWN: PushRotateEvent(-1),
}


class KeyTranslator:
    """
    Translates Anticater key events into standard events. A push is only
    reported when the knob is released without having been turned while
    pushed, so a push-turn never also reports a push.
    """

    def __init__(self):
        self.push_pending = False

    def feed(self, code: int, value: int) -> DeviceEvent | None:
        """Return the event for one key event, or None."""
        if code == ecodes.KEY_MUTE:
            return self._feed_push(value)
        if value != KEY_DOWN or code not in SIMPLE_KEYS:
            return None
        event = SIMPLE_KEYS[code]
        if isinstance(event, PushRotateEvent):
            self.push_pending = False
        return event

    def _feed_push(self, value: int) -> DeviceEvent | None:
        """Handle a press or release of the knob."""
        if value == KEY_DOWN:
            self.push_pending = True
        elif value == KEY_UP and self.push_pending:
            self.push_pending = False
            return PushEvent()
        return None


def _is_anticater(dev: evdev.InputDevice) -> bool:
    """
    True if 'dev' is the Anticater interface that sends the knob keys. Over
    USB it is recognized by its IDs; over Bluetooth the IDs are zero, so it is
    recognized by its name.
    """
    known_ids = (dev.info.vendor, dev.info.product) in PRODUCT_IDS
    if not known_ids and not dev.name.upper().startswith(NAME_PREFIX):
        return False
    keys = dev.capabilities().get(ecodes.EV_KEY, [])
    return ecodes.KEY_VOLUMEUP in keys


def _open_if_anticater(path: str) -> evdev.InputDevice | None:
    """
    Open the device at 'path' and return it if it is the Anticater. Devices
    that vanish while being checked are skipped.
    """
    try:
        dev = evdev.InputDevice(path)
    except OSError:
        return None
    try:
        if _is_anticater(dev):
            return dev
    except OSError:
        pass
    dev.close()
    return None


def _find_device() -> evdev.InputDevice | None:
    """Return the Anticater input device, or None if it is not connected."""
    for path in evdev.list_devices():
        dev = _open_if_anticater(path)
        if dev is not None:
            return dev
    return None


class AnticaterDevice(Device):
    """Waits for the Anticater, grabs it, and reports its events."""

    async def run(self) -> None:
        """Read the device forever, reconnecting when it comes back."""
        while True:
            try:
                dev = _find_device()
            except OSError as error:
                log.warning("Device scan failed: %s", error)
                dev = None
            if dev is not None:
                await self._read_device(dev)
            await asyncio.sleep(RETRY_SECONDS)

    async def _read_device(self, dev: evdev.InputDevice) -> None:
        """Grab 'dev' and report its events until it fails."""
        try:
            dev.grab()
            log.info("Device connected")
            self.on_event(ConnectionEvent(True))
            translator = KeyTranslator()
            async for event in dev.async_read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                translated = translator.feed(event.code, event.value)
                if translated is not None:
                    self.on_event(translated)
        except OSError as error:
            if error.errno == errno.ENODEV:
                log.info("Device disconnected")
            else:
                log.warning("Device error: %s", error)
        self.on_event(ConnectionEvent(False))
        try:
            dev.ungrab()
        except OSError:
            pass
        dev.close()
