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

"""Entry point: python3 -m midi_bridge_daemon"""

import asyncio
import sys

from midi_bridge_daemon import app
from midi_bridge_daemon.ipc_server import AlreadyRunningError

if __name__ == "__main__":
    try:
        asyncio.run(app.run())
    except AlreadyRunningError as error:
        sys.exit(f"Error: {error}")
    except KeyboardInterrupt:
        pass
