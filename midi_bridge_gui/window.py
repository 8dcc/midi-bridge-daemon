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

"""The main window: one row per knob, showing its value and settings."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from midi_bridge_common.ipc_protocol import SETTING_NAMES
from midi_bridge_common.limits import (
    MAX_KNOB_STEP,
    MAX_KNOB_VALUE,
    MIN_KNOB_STEP,
    MIN_KNOB_VALUE,
)

# Milliseconds an error stays in the status bar
ERROR_MS = 5000

SELECTED_MARKER = ">"

HEADERS = ("", "Knob", "Value") + tuple(name.capitalize()
                                        for name in SETTING_NAMES)


def _has_uncommitted_text(box: QSpinBox) -> bool:
    """True if the user typed into 'box' but has not committed it yet."""
    return box.hasFocus() and box.cleanText() != str(box.value())


class KnobRow:
    """
    The widgets of one knob, placed in row 'row' of a shared grid so that
    columns stay aligned across rows.
    """

    def __init__(self, grid: QGridLayout, row: int, index: int,
                 on_setting_edited: Callable[[int, str, int], None]):
        self.marker = QLabel()
        self.name = QLabel()
        self.value = QProgressBar()
        self.value.setRange(MIN_KNOB_VALUE, MAX_KNOB_VALUE)
        self.value.setFormat("%v")
        self.boxes: dict[str, QSpinBox] = {}
        for name in SETTING_NAMES:
            box = QSpinBox()
            box.setRange(MIN_KNOB_STEP, MAX_KNOB_STEP)
            box.setKeyboardTracking(False)
            box.valueChanged.connect(
                lambda value, name=name: on_setting_edited(index, name, value))
            self.boxes[name] = box

        widgets = [self.marker, self.name, self.value, *self.boxes.values()]
        for column, widget in enumerate(widgets):
            grid.addWidget(widget, row, column)
        self.widgets = widgets

    def show_knob(self, index: int, knob: dict, selected: bool) -> None:
        """Show the 'knob' entry of a state message."""
        self.marker.setText(SELECTED_MARKER if selected else "")
        self.name.setText(f"Knob {index + 1} (CC {knob['cc']})")
        self.value.setValue(knob["value"])
        for name, box in self.boxes.items():
            if _has_uncommitted_text(box):
                continue
            box.blockSignals(True)
            box.setValue(knob[name])
            box.blockSignals(False)

    def remove(self) -> None:
        """Remove every widget of the row from its grid."""
        for widget in self.widgets:
            widget.deleteLater()


class MainWindow(QMainWindow):
    """
    Shows the state received from the daemon. Calls 'on_knob_settings_edited'
    with the knob index and the changed setting when the user edits one.
    """

    def __init__(self, on_knob_settings_edited: Callable[[int, dict[str, int]],
                                                         None]):
        super().__init__()
        self.on_knob_settings_edited = on_knob_settings_edited
        self.rows: list[KnobRow] = []
        self.last_state: dict | None = None
        self.daemon_connected = False
        self.device_connected = False

        self.setWindowTitle("MIDI bridge")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.grid = QGridLayout()
        for column, text in enumerate(HEADERS):
            self.grid.addWidget(QLabel(f"<b>{text}</b>"), 0, column)
        layout = QVBoxLayout()
        layout.addStretch()
        layout.addLayout(self.grid)
        layout.addStretch()
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label)
        self.show_daemon_connected(False)

    def show_state(self, state: dict) -> None:
        """Show a state message received from the daemon."""
        self.last_state = state
        knobs = state["knobs"]
        if len(knobs) != len(self.rows):
            self._build_rows(len(knobs))
        for index, (row, knob) in enumerate(zip(self.rows, knobs)):
            row.show_knob(index, knob, index == state["selected_knob"])
        self.device_connected = state["device_connected"]
        self._show_status()

    def show_error(self, text: str) -> None:
        """Show an error received from the daemon for a few seconds."""
        self.statusBar().showMessage(f"Error: {text}", ERROR_MS)

    def show_daemon_connected(self, connected: bool) -> None:
        """Show whether the GUI is connected to the daemon."""
        self.daemon_connected = connected
        self.centralWidget().setEnabled(connected)
        self._show_status()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        On Escape, discard the text typed in the focused box and leave it,
        showing the last state received again.
        """
        box = QApplication.focusWidget()
        if event.key() != Qt.Key.Key_Escape or not isinstance(box, QSpinBox):
            super().keyPressEvent(event)
            return
        box.lineEdit().setText(box.textFromValue(box.value()))
        self.setFocus()
        if self.last_state is not None:
            self.show_state(self.last_state)

    def _on_setting_edited(self, index: int, name: str, value: int) -> None:
        """Report one setting edited by the user."""
        self.on_knob_settings_edited(index, {name: value})

    def _build_rows(self, count: int) -> None:
        """Replace the knob rows with 'count' new ones."""
        for row in self.rows:
            row.remove()
        self.rows = [KnobRow(self.grid, index + 1, index,
                             self._on_setting_edited)
                     for index in range(count)]

    def _show_status(self) -> None:
        """Show the daemon and device status in the permanent status label."""
        if not self.daemon_connected:
            text = "Daemon not running"
        elif not self.device_connected:
            text = "Device not connected"
        else:
            text = "Device connected"
        self.status_label.setText(text)
