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
Standard input events, and the interface every device implements. Devices only
report what physically happens; they give the events no meaning.
"""

import abc
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RotateEvent:
    """The knob was turned one detent; 'direction' is +1 or -1."""
    direction: int


@dataclass(frozen=True)
class PushEvent:
    """The knob was pushed and released without being turned."""


@dataclass(frozen=True)
class PushRotateEvent:
    """The knob was turned one detent while pushed; 'direction' is +1 or -1."""
    direction: int


@dataclass(frozen=True)
class ConnectionEvent:
    """The device was connected or disconnected."""
    connected: bool


DeviceEvent = RotateEvent | PushEvent | PushRotateEvent | ConnectionEvent


class Device(abc.ABC):
    """An input device that reports DeviceEvents to 'on_event'."""

    def __init__(self, on_event: Callable[[DeviceEvent], None]):
        self.on_event = on_event

    @abc.abstractmethod
    async def run(self) -> None:
        """
        Wait for the device, call 'on_event' for each of its events, and
        survive disconnects. Never returns.
        """
