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
Creates the device, controller, MIDI output and IPC server, and connects them
through callbacks. None of them knows about the others.
"""

import logging

from midi_bridge_common import ipc_protocol
from midi_bridge_daemon.anticater import AnticaterDevice
from midi_bridge_daemon.controller import Controller, State
from midi_bridge_daemon.device import (
    ConnectionEvent,
    DeviceEvent,
    PushEvent,
    PushRotateEvent,
    RotateEvent,
)
from midi_bridge_daemon.ipc_server import IpcServer
from midi_bridge_daemon.midi import MidiOutput, cc_warnings

log = logging.getLogger(__name__)


def _state_message(state: State) -> dict:
    """Return 'state' as a state message for GUI clients."""
    knobs = [ipc_protocol.knob_entry(cc=knob.cc, value=knob.value,
                                     sensitivity=knob.sensitivity,
                                     fine=knob.fine, coarse=knob.coarse)
             for knob in state.knobs]
    return ipc_protocol.state_message(knobs=knobs,
                                      selected_knob=state.selected_knob,
                                      device_connected=state.device_connected)


async def run() -> None:
    """Run the daemon forever."""
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    def on_device_event(event: DeviceEvent) -> None:
        """Translate what happened on the device into a Controller change."""
        match event:
            case RotateEvent(direction=direction):
                controller.rotate_selected_knob(direction)
            case PushRotateEvent(direction=direction):
                controller.select_adjacent_knob(direction)
            case PushEvent():
                controller.toggle_selected_sensitivity()
            case ConnectionEvent(connected=connected):
                controller.set_device_connected(connected)

    def on_controller_knob_value_changed(cc: int, value: int) -> None:
        """Send the new knob value as MIDI."""
        midi_output.send_control_change(cc, value)

    def on_controller_state_changed(state: State) -> None:
        """Send the new state to every GUI client."""
        server.broadcast(_state_message(state))

    def on_ipc_client_connected() -> dict:
        """Return the message a new GUI client receives first."""
        return _state_message(controller.state)

    def on_ipc_knob_change(index: int, settings: dict[str, int]) -> str | None:
        """Apply settings sent by a GUI client; return the error, if any."""
        return controller.set_knob_settings(index, settings)

    midi_output = MidiOutput()
    controller = Controller(on_controller_knob_value_changed,
                            on_controller_state_changed)
    server = IpcServer(on_ipc_client_connected,
                       on_ipc_knob_change)
    device = AnticaterDevice(on_device_event)

    for warning in cc_warnings(knob.cc for knob in controller.state.knobs):
        log.warning(warning)

    await server.start()
    await device.run()
