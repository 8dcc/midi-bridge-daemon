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

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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

HEADERS = ("", "Knob", "Value", "") + tuple(name.capitalize()
                                            for name in SETTING_NAMES)

# Grid column of the value bar, the one that takes any extra width
VALUE_COLUMN = 2

LED_SIZE = 8
ROW_HEIGHT = 38
ROW_PADDING = 26
COLUMN_SPACING = 14

# Largest width of the window, past which it would only add empty space. Its
# height is fixed to what the rows need.
MAX_WIDTH = 900


def _set_style_property(widget: QWidget, name: str, value) -> None:
    """Set a property the stylesheet depends on, and restyle 'widget'."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _new_led() -> QLabel:
    """A small round light, colored by the stylesheet."""
    led = QLabel()
    led.setObjectName("led")
    led.setFixedSize(LED_SIZE, LED_SIZE)
    return led


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
        self.band = QFrame()
        self.band.setObjectName("band")
        grid.addWidget(self.band, row, 0, 1, grid.columnCount())
        self.marker = _new_led()
        self.name = QLabel()
        self.value = QProgressBar()
        self.value.setRange(MIN_KNOB_VALUE, MAX_KNOB_VALUE)
        self.value.setFormat("%v")
        self.value.setTextVisible(False)
        self.value.setMinimumWidth(120)
        self.value_text = QLabel()
        self.value_text.setObjectName("value_text")
        self.value_text.setAlignment(Qt.AlignmentFlag.AlignRight
                                     | Qt.AlignmentFlag.AlignVCenter)
        self.value_text.setMinimumWidth(
            self.value_text.fontMetrics().horizontalAdvance("000"))
        self.boxes: dict[str, QSpinBox] = {}
        for name in SETTING_NAMES:
            box = QSpinBox()
            box.setRange(MIN_KNOB_STEP, MAX_KNOB_STEP)
            box.setKeyboardTracking(False)
            box.valueChanged.connect(
                lambda value, name=name: on_setting_edited(index, name, value))
            self.boxes[name] = box

        widgets = [self.marker, self.name, self.value, self.value_text,
                   *self.boxes.values()]
        for column, widget in enumerate(widgets):
            grid.addWidget(widget, row, column)
        grid.setAlignment(self.marker, Qt.AlignmentFlag.AlignCenter)
        grid.setRowMinimumHeight(row, ROW_HEIGHT)
        self.widgets = [self.band, *widgets]

    def show_knob(self, index: int, knob: dict, selected: bool) -> None:
        """Show the 'knob' entry of a state message."""
        _set_style_property(self.band, "selected", selected)
        _set_style_property(self.marker, "selected", selected)
        self.name.setText(f"Knob {index + 1} (CC {knob['cc']})")
        self.value.setValue(knob["value"])
        self.value_text.setText(str(knob["value"]))
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
        # A dialog, so tiling window managers like dwm make it float at its
        # own size instead of tiling it
        self.setWindowFlag(Qt.WindowType.Dialog)
        self.setMaximumWidth(MAX_WIDTH)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.grid = self._new_grid()
        self.panel = QFrame()
        self.panel.setObjectName("panel")
        self.panel.setLayout(self.grid)
        self.badge_led = _new_led()
        self.badge_text = QLabel()
        self.badge_text.setObjectName("badge_text")
        self.badge = self._new_badge(self.badge_led, self.badge_text)
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addStretch()
        layout.addLayout(self._new_header(self.badge))
        layout.addWidget(self.panel)
        layout.addStretch()
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.statusBar().setSizeGripEnabled(False)
        self.show_daemon_connected(False)
        self._fit_height()

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
        self.panel.setEnabled(connected)
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

    @staticmethod
    def _new_badge(led: QLabel, text: QLabel) -> QFrame:
        """A rounded badge with a status 'led' followed by its 'text'."""
        badge = QFrame()
        badge.setObjectName("badge")
        layout = QHBoxLayout(badge)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(7)
        layout.addWidget(led)
        layout.addWidget(text)
        return badge

    @staticmethod
    def _new_header(badge: QFrame) -> QHBoxLayout:
        """The row above the panel: the title, and the status 'badge'."""
        title = QLabel("MIDI bridge")
        title.setObjectName("title")
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 0, 0)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(badge)
        return header

    @staticmethod
    def _new_grid() -> QGridLayout:
        """The grid of the knob rows, with only its header row for now."""
        grid = QGridLayout()
        grid.setContentsMargins(8, 10, 8, 8)
        grid.setHorizontalSpacing(COLUMN_SPACING)
        grid.setVerticalSpacing(2)
        for column, text in enumerate(HEADERS):
            header = QLabel(text)
            header.setObjectName("header")
            grid.addWidget(header, 0, column)
        grid.setColumnMinimumWidth(0, ROW_PADDING)
        grid.setColumnStretch(VALUE_COLUMN, 1)
        # An empty last column, so the selected band reaches past the boxes
        grid.setColumnMinimumWidth(len(HEADERS), 2)
        return grid

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
        # The new rows are shown, and the old ones deleted, once control
        # returns to the event loop, so only then is the new height known
        QTimer.singleShot(0, self._fit_height)

    def _fit_height(self) -> None:
        """Fix the height of the window to the one its contents need."""
        self.setFixedHeight(self.sizeHint().height())

    def _show_status(self) -> None:
        """Show the daemon and device status in the badge."""
        if not self.daemon_connected:
            text, status = "Daemon not running", "off"
        elif not self.device_connected:
            text, status = "Device not connected", "waiting"
        else:
            text, status = "Device connected", "ok"
        self.badge_text.setText(text)
        for widget in (self.badge, self.badge_led, self.badge_text):
            _set_style_property(widget, "status", status)
