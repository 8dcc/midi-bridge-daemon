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

"""Connection to the daemon's Unix socket, with automatic reconnection."""

import sys
from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalSocket

from midi_bridge_common import ipc_protocol

# Milliseconds between connection attempts
RETRY_MS = 2000


class IpcClient:
    """
    Keeps a connection to the daemon, retrying every RETRY_MS while it is down.
    Calls 'on_state' with each state message, 'on_error' with the text of each
    error message, and 'on_connection_changed' when the connection goes up or
    down.
    """

    def __init__(self, on_state: Callable[[dict], None],
                 on_error: Callable[[str], None],
                 on_connection_changed: Callable[[bool], None]):
        self.on_state = on_state
        self.on_error = on_error
        self.on_connection_changed = on_connection_changed
        self.connected = False

        self.socket = QLocalSocket()
        self.socket.connected.connect(self._on_socket_connected)
        self.socket.disconnected.connect(self._on_socket_down)
        self.socket.errorOccurred.connect(self._on_socket_down)
        self.socket.readyRead.connect(self._on_ready_read)

        self.retry_timer = QTimer()
        self.retry_timer.setSingleShot(True)
        self.retry_timer.setInterval(RETRY_MS)
        self.retry_timer.timeout.connect(self.start)

    def start(self) -> None:
        """Try to connect to the daemon."""
        self.socket.abort()
        self.socket.connectToServer(ipc_protocol.socket_path())

    def send_knob_settings(self, index: int,
                           settings: dict[str, int]) -> None:
        """Ask the daemon to change the 'settings' of knob 'index'."""
        if not self.connected:
            return
        message = ipc_protocol.set_knob_message(index, settings)
        self.socket.write(ipc_protocol.encode(message))

    def _set_connected(self, connected: bool) -> None:
        """Record the connection status, reporting it only when it changes."""
        if connected == self.connected:
            return
        self.connected = connected
        self.on_connection_changed(connected)

    def _on_socket_connected(self) -> None:
        """Handle a successful connection."""
        self._set_connected(True)

    def _on_socket_down(self, *_) -> None:
        """Handle a failed connection attempt or a lost connection."""
        self._set_connected(False)
        if not self.retry_timer.isActive():
            self.retry_timer.start()

    def _on_ready_read(self) -> None:
        """Handle every complete line received from the daemon."""
        while self.socket.canReadLine():
            line = self.socket.readLine().data()
            try:
                message = ipc_protocol.parse_reply(line)
            except ipc_protocol.ProtocolError as error:
                print(f"Ignoring invalid message: {error}", file=sys.stderr)
                continue
            if message["type"] == "state":
                self.on_state(message)
            else:
                self.on_error(message["message"])
