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

"""Entry point: python3 -m midi_bridge_gui"""

import sys

from PySide6.QtWidgets import QApplication

from midi_bridge_gui.ipc_client import IpcClient
from midi_bridge_gui.style import apply_style
from midi_bridge_gui.window import MainWindow


def main() -> int:
    """Create the window and the daemon connection, and run the GUI."""
    app = QApplication(sys.argv)
    apply_style(app)

    def on_window_knob_settings_edited(index: int,
                                       settings: dict[str, int]) -> None:
        """Send settings edited by the user to the daemon."""
        client.send_knob_settings(index, settings)

    def on_ipc_state(state: dict) -> None:
        """Show a state received from the daemon."""
        window.show_state(state)

    def on_ipc_error(text: str) -> None:
        """Show an error received from the daemon."""
        window.show_error(text)

    def on_ipc_connection_changed(connected: bool) -> None:
        """Show whether the daemon is reachable."""
        window.show_daemon_connected(connected)

    window = MainWindow(on_knob_settings_edited=on_window_knob_settings_edited)
    client = IpcClient(on_state=on_ipc_state, on_error=on_ipc_error,
                       on_connection_changed=on_ipc_connection_changed)
    client.start()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
