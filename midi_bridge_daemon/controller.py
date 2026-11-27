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

"""The knobs and the rest of the bridge state, and the code that changes it."""

from collections.abc import Callable
from dataclasses import dataclass

from midi_bridge_common.limits import (
    MAX_KNOB_STEP,
    MAX_KNOB_VALUE,
    MIN_KNOB_STEP,
    MIN_KNOB_VALUE,
)

NUM_KNOBS = 8
FIRST_CC = 20
DEFAULT_VALUE = 64
DEFAULT_SENSITIVITY = 1
DEFAULT_FINE = 1
DEFAULT_COARSE = 8


@dataclass
class Knob:
    """
    A virtual knob: its CC number, its current value, and the steps it moves
    by. 'sensitivity' is the current step; a push switches it between 'fine'
    and 'coarse'.
    """
    cc: int
    value: int
    sensitivity: int
    fine: int
    coarse: int


@dataclass
class State:
    """Everything the controller owns."""
    knobs: list[Knob]
    selected_knob: int = 0
    device_connected: bool = False


def _initial_state() -> State:
    """Return the hard-coded starting state: NUM_KNOBS knobs from FIRST_CC."""
    knobs = [Knob(cc=FIRST_CC + i, value=DEFAULT_VALUE,
                  sensitivity=DEFAULT_SENSITIVITY, fine=DEFAULT_FINE,
                  coarse=DEFAULT_COARSE)
             for i in range(NUM_KNOBS)]
    return State(knobs=knobs)


def _toggled_sensitivity(knob: Knob) -> int:
    """
    Return whichever of the knob's 'fine' and 'coarse' is furthest from its
    current sensitivity. On a tie, return 'fine'.
    """
    fine_distance = abs(knob.sensitivity - knob.fine)
    coarse_distance = abs(knob.sensitivity - knob.coarse)
    return knob.coarse if coarse_distance > fine_distance else knob.fine


def _settings_error(index: int, settings: dict[str, int]) -> str | None:
    """Return why the 'settings' for knob 'index' can't be applied, or None."""
    if not 0 <= index < NUM_KNOBS:
        return f"knob must be in 0..{NUM_KNOBS - 1}"
    for name, value in settings.items():
        if not MIN_KNOB_STEP <= value <= MAX_KNOB_STEP:
            return f"{name} must be in {MIN_KNOB_STEP}..{MAX_KNOB_STEP}"
    return None


class Controller:
    """
    Owns the bridge state, and changes it when asked to. It does not know who
    calls it or who listens to it.

    After a knob value changes (what goes out as MIDI), it calls
    'on_knob_value_changed' with the knob's CC and new value. After any
    change, values included, it calls 'on_state_changed' with the whole state.
    When both are called, 'on_knob_value_changed' goes first. A callback only
    for changes to the other settings could be added if something needs it;
    nothing does now.

    Methods and callbacks must stay synchronous (no 'await'). The whole daemon
    runs on one asyncio thread, so that is what makes each change atomic.
    """

    def __init__(self, on_knob_value_changed: Callable[[int, int], None],
                 on_state_changed: Callable[[State], None]):
        self.on_knob_value_changed = on_knob_value_changed
        self.on_state_changed = on_state_changed
        self.state = _initial_state()

    def _selected(self) -> Knob:
        """Return the selected knob."""
        return self.state.knobs[self.state.selected_knob]

    def rotate_selected_knob(self, direction: int) -> None:
        """Move the selected knob's value one step up (+1) or down (-1)."""
        knob = self._selected()
        value = knob.value + direction * knob.sensitivity
        value = max(MIN_KNOB_VALUE, min(MAX_KNOB_VALUE, value))
        if value == knob.value:
            return
        knob.value = value
        self.on_knob_value_changed(knob.cc, knob.value)
        self.on_state_changed(self.state)

    def select_adjacent_knob(self, direction: int) -> None:
        """Select the next (+1) or previous (-1) knob, wrapping around."""
        selected = (self.state.selected_knob + direction) % NUM_KNOBS
        self.state.selected_knob = selected
        self.on_state_changed(self.state)

    def toggle_selected_sensitivity(self) -> None:
        """Switch the selected knob's sensitivity between fine and coarse."""
        knob = self._selected()
        knob.sensitivity = _toggled_sensitivity(knob)
        self.on_state_changed(self.state)

    def set_device_connected(self, connected: bool) -> None:
        """Record whether the input device is connected."""
        if connected == self.state.device_connected:
            return
        self.state.device_connected = connected
        self.on_state_changed(self.state)

    def set_knob_settings(self, index: int,
                          settings: dict[str, int]) -> str | None:
        """
        Change the 'settings' of the knob at 'index'. Return None, or the
        reason nothing was changed. The keys of 'settings' must be names of
        Knob settings.
        """
        error = _settings_error(index, settings)
        if error is not None:
            return error
        knob = self.state.knobs[index]
        for name, value in settings.items():
            assert hasattr(knob, name)
            setattr(knob, name, value)
        self.on_state_changed(self.state)
        return None
