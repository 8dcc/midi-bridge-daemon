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

"""Unix socket server for GUI clients."""

import asyncio
import logging
import os
import socket
from collections.abc import Callable

from midi_bridge_common import ipc_protocol

log = logging.getLogger(__name__)

# Bytes a client may leave unread before it is dropped
MAX_UNREAD_BYTES = 64 * 1024


class AlreadyRunningError(Exception):
    """Another server is already listening on the socket path."""


def _is_listening(path: str) -> bool:
    """True if something accepts connections on the Unix socket 'path'."""
    with socket.socket(socket.AF_UNIX) as sock:
        try:
            sock.connect(path)
        except OSError:
            return False
    return True


class IpcServer:
    """
    Listens on ipc_protocol.socket_path() and accepts any number of clients.

    Each new client first receives the message returned by
    'on_client_connected'. Each valid set_knob request calls
    'on_knob_change' with the knob index and its settings. An error text
    returned by it, like any invalid request, is sent back as an error message
    to that client only.
    """

    def __init__(self, on_client_connected: Callable[[], dict],
                 on_knob_change: Callable[[int, dict[str, int]], str | None]):
        self.on_client_connected = on_client_connected
        self.on_knob_change = on_knob_change
        self.path = ipc_protocol.socket_path()
        self.clients: set[asyncio.StreamWriter] = set()
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        """
        Remove a stale socket file and start listening. Raises
        AlreadyRunningError if another server is listening on the path.
        """
        if _is_listening(self.path):
            raise AlreadyRunningError(f"a daemon is already listening on "
                                      f"{self.path}")
        if os.path.exists(self.path):
            os.unlink(self.path)
        self.server = await asyncio.start_unix_server(self._serve, self.path)
        log.info("Listening on %s", self.path)

    def broadcast(self, message: dict) -> None:
        """Send 'message' to every connected client."""
        for writer in list(self.clients):
            self._send(writer, message)

    def _send(self, writer: asyncio.StreamWriter, message: dict) -> None:
        """
        Send 'message' to one client, dropping it if it is gone or if it has
        stopped reading.
        """
        if writer.is_closing():
            self._drop(writer)
            return
        try:
            writer.write(ipc_protocol.encode(message))
        except (ConnectionError, RuntimeError):
            self._drop(writer)
            return
        if writer.transport.get_write_buffer_size() > MAX_UNREAD_BYTES:
            log.warning("Dropping client: it is not reading its messages")
            self._drop(writer)

    def _drop(self, writer: asyncio.StreamWriter) -> None:
        """Forget a client and close its connection."""
        self.clients.discard(writer)
        writer.close()

    def _handle_line(self, line: bytes) -> str | None:
        """Handle one line received from a client. Return the error, if any."""
        try:
            request = ipc_protocol.parse_request(line)
        except ipc_protocol.ProtocolError as error:
            return str(error)
        match request["type"]:
            case "set_knob":
                return self.on_knob_change(request["knob"],
                                           request["settings"])
        raise AssertionError(f"unhandled request type: {request['type']}")

    async def _serve(self, reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter) -> None:
        """Handle one client until it disconnects or misbehaves."""
        self.clients.add(writer)
        self._send(writer, self.on_client_connected())
        try:
            while line := await reader.readline():
                error = self._handle_line(line)
                if error is not None:
                    self._send(writer, ipc_protocol.error_message(error))
        except (ValueError, ConnectionError) as error:
            log.warning("Dropping client: %s", error)
        finally:
            self._drop(writer)
