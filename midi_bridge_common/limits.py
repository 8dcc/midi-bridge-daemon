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
Ranges of knob values and knob settings. The daemon's controller uses them to
reject out-of-range writes, and the GUI uses them to limit its inputs.
"""

# Range of a knob's value, sent as the value of its MIDI CC
MIN_KNOB_VALUE = 0
MAX_KNOB_VALUE = 127

# Range of a knob's step sizes: its sensitivity, fine and coarse settings
MIN_KNOB_STEP = 1
MAX_KNOB_STEP = 127
