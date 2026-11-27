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
The look of the GUI: the Fusion style, a palette and a stylesheet, built from
one light and one dark set of colors.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

LIGHT_COLORS = {
    "window": "#e9ecef",
    "panel": "#f8f9fa",
    "base": "#ffffff",
    "line": "#d3d8de",
    "text": "#1f252c",
    "muted": "#6b7480",
    "accent": "#5e6a7d",
    "accent_text": "#ffffff",
    "selected": "#e3e7ed",
    "track": "#dde2e7",
    "ok": "#23a55a",
    "waiting": "#d99a0b",
    "off": "#a3abb5",
    "error": "#c2372f",
    "ok_text": "#17723d",
    "ok_badge": "#dcf3e5",
    "waiting_text": "#8a6206",
    "waiting_badge": "#f8ecd0",
    "off_badge": "#dde2e7",
}

DARK_COLORS = {
    "window": "#1b1f24",
    "panel": "#23282e",
    "base": "#1b1f24",
    "line": "#343b43",
    "text": "#e3e7ec",
    "muted": "#8c96a2",
    "accent": "#a5afc0",
    "accent_text": "#1b1f24",
    "selected": "#2e343d",
    "track": "#313840",
    "ok": "#3ccf76",
    "waiting": "#e8ad2c",
    "off": "#59626c",
    "error": "#ff6b61",
    "ok_text": "#7ee2a5",
    "ok_badge": "#1d3a2a",
    "waiting_text": "#f0c766",
    "waiting_badge": "#3d321a",
    "off_badge": "#2c3238",
}

# Format with the colors above. Object names and properties are set in window.
STYLE_SHEET = """
#panel {{
    background: {panel};
    border: 1px solid {line};
    border-radius: 10px;
}}
#header {{
    color: {muted};
    padding-bottom: 2px;
}}
#band {{
    border-radius: 6px;
}}
#band[selected="true"] {{
    background: {selected};
}}
#led {{
    border-radius: 4px;
    background: transparent;
}}
#led[selected="true"] {{
    background: {accent};
}}
#band[selected="true"]:disabled {{
    background: {track};
}}
#led[selected="true"]:disabled {{
    background: {off};
}}
#led[status="ok"] {{
    background: {ok};
}}
#led[status="waiting"] {{
    background: {waiting};
}}
#led[status="off"] {{
    background: {off};
}}
#value_text {{
    color: {text};
}}
#value_text:disabled, QLabel:disabled {{
    color: {off};
}}
QProgressBar {{
    border: none;
    border-radius: 3px;
    background: {track};
    max-height: 6px;
    min-height: 6px;
}}
QProgressBar::chunk {{
    border-radius: 3px;
    background: {accent};
}}
QProgressBar::chunk:disabled {{
    background: {off};
}}
QStatusBar {{
    color: {error};
}}
#title {{
    font-size: 15px;
    font-weight: bold;
}}
#badge {{
    border-radius: 12px;
}}
#badge[status="ok"] {{
    background: {ok_badge};
}}
#badge[status="waiting"] {{
    background: {waiting_badge};
}}
#badge[status="off"] {{
    background: {off_badge};
}}
#badge_text {{
    font-weight: bold;
}}
#badge_text[status="ok"] {{
    color: {ok_text};
}}
#badge_text[status="waiting"] {{
    color: {waiting_text};
}}
#badge_text[status="off"] {{
    color: {muted};
}}
"""


def _is_dark(app: QApplication) -> bool:
    """True if the desktop asks for a dark color scheme."""
    scheme = app.styleHints().colorScheme()
    if scheme != Qt.ColorScheme.Unknown:
        return scheme == Qt.ColorScheme.Dark
    return app.palette().window().color().lightness() < 128


def _palette(colors: dict[str, str]) -> QPalette:
    """Build a palette from a set of 'colors'."""
    role = QPalette.ColorRole
    group = QPalette.ColorGroup
    palette = QPalette()
    roles = {
        role.Window: "window",
        role.WindowText: "text",
        role.Base: "base",
        role.AlternateBase: "panel",
        role.Text: "text",
        role.Button: "panel",
        role.ButtonText: "text",
        role.Highlight: "accent",
        role.HighlightedText: "accent_text",
        role.ToolTipBase: "panel",
        role.ToolTipText: "text",
        role.PlaceholderText: "muted",
        role.Mid: "line",
        role.Dark: "line",
    }
    for color_role, name in roles.items():
        palette.setColor(color_role, QColor(colors[name]))
    for color_role in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, color_role, QColor(colors["off"]))
    palette.setColor(group.Disabled, role.Base, QColor(colors["panel"]))
    return palette


def apply_style(app: QApplication, dark: bool | None = None) -> None:
    """
    Give 'app' the Fusion style with our palette and stylesheet. The colors
    follow the desktop unless 'dark' says otherwise.
    """
    if dark is None:
        dark = _is_dark(app)
    colors = DARK_COLORS if dark else LIGHT_COLORS
    app.setStyle("Fusion")
    app.setPalette(_palette(colors))
    app.setStyleSheet(STYLE_SHEET.format(**colors))
