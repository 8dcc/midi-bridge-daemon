#!/usr/bin/env bash
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
#
# Installs the MIDI bridge daemon as a systemd user service, and the GUI
# launcher, into the home directory. No root privileges needed.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHARE_DIR="${HOME}/.local/share/midi-bridge-daemon"
BIN_DIR="${HOME}/.local/bin"
UNIT_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="midi-bridge-daemon"

check_deps() {
    local missing=()
    python3 -c "import evdev" 2>/dev/null || missing+=(python-evdev)
    python3 -c "import mido" 2>/dev/null || missing+=(python-mido)
    python3 -c "import rtmidi" 2>/dev/null || missing+=(python-rtmidi)
    python3 -c "import PySide6" 2>/dev/null || missing+=(pyside6)
    if [ ${#missing[@]} -ne 0 ]; then
        echo "Missing packages, install them with:"
        echo "  sudo pacman -S ${missing[*]}"
        exit 1
    fi
}

install_files() {
    mkdir -p "$SHARE_DIR" "$BIN_DIR" "$UNIT_DIR"
    cp -r "${SCRIPT_DIR}/midi_bridge_common" \
        "${SCRIPT_DIR}/midi_bridge_daemon" "${SCRIPT_DIR}/midi_bridge_gui" \
        "$SHARE_DIR/"
    cp "${SCRIPT_DIR}/systemd/${SERVICE_NAME}.service" "$UNIT_DIR/"
    cat > "${BIN_DIR}/midi-bridge-gui" <<LAUNCHER
#!/bin/sh
cd "${SHARE_DIR}" && exec python3 -m midi_bridge_gui "\$@"
LAUNCHER
    chmod +x "${BIN_DIR}/midi-bridge-gui"
    systemctl --user daemon-reload
}

print_warnings() {
    if systemctl is-active --quiet anticater-precise-scroll; then
        echo "Warning: anticater-precise-scroll is running and will keep"
        echo "the device grabbed. Stop it with:"
        echo "  sudo systemctl disable --now anticater-precise-scroll"
    fi
    if ! id -nG | grep -qw input; then
        echo "Warning: you are not in the 'input' group. Run:"
        echo "  sudo usermod -aG input ${USER}"
        echo "and log in again."
    fi
}

check_deps
install_files
print_warnings

echo "Done. To enable and start the daemon, run:"
echo "  systemctl --user enable --now ${SERVICE_NAME}"
echo "Start the GUI with: midi-bridge-gui"
