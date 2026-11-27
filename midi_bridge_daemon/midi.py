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

"""Virtual MIDI output port, and the CC numbers worth warning about."""

from collections.abc import Iterable

import mido

PORT_NAME = "midi-bridge"

# MIDI channel 1, zero-based as mido expects
MIDI_CHANNEL = 0

# CC numbers that are reserved or have a conventional meaning
RESERVED_CCS: dict[int, str] = {
    0: "bank select",
    1: "modulation wheel",
    2: "breath controller",
    4: "foot controller",
    5: "portamento time",
    6: "data entry",
    7: "channel volume",
    8: "balance",
    10: "pan",
    11: "expression",
    **{cc: f"the LSB of CC {cc - 32}" for cc in range(32, 64)},
    64: "sustain",
    65: "portamento",
    66: "sostenuto",
    67: "soft pedal",
    68: "legato",
    69: "hold 2",
    96: "data increment",
    97: "data decrement",
    98: "NRPN LSB",
    99: "NRPN MSB",
    100: "RPN LSB",
    101: "RPN MSB",
    **{cc: "channel mode messages" for cc in range(120, 128)},
}


def cc_warnings(ccs: Iterable[int]) -> list[str]:
    """Return one warning for each of the 'ccs' that is in RESERVED_CCS."""
    return [f"CC {cc} is reserved for {RESERVED_CCS[cc]}"
            for cc in ccs if cc in RESERVED_CCS]


class MidiOutput:
    """A virtual MIDI output port that other programs can connect to."""

    def __init__(self, port_name: str = PORT_NAME):
        self.port = mido.open_output(port_name, virtual=True,
                                     client_name=port_name)

    def send_control_change(self, cc: int, value: int) -> None:
        """Send a Control Change message on MIDI_CHANNEL."""
        self.port.send(mido.Message("control_change", channel=MIDI_CHANNEL,
                                    control=cc, value=value))
