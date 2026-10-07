"""Attribute bar widget: red/yellow/green bars for player ratings.

Matches the v0.18.4 desktop visual: horizontal bars colored by 1-100 value.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt


def _bar_color(value):
    """Red < 60, yellow 60-79, green 80+."""
    if value >= 80:
        return "#22c55e"  # green
    if value >= 60:
        return "#eab308"  # yellow
    return "#ef4444"  # red


class AttributeBar(QWidget):
    """Single labeled attribute bar."""

    def __init__(self, name, value, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        label = QLabel(name)
        label.setFixedWidth(140)
        label.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        layout.addWidget(label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(max(0, min(100, int(value))))
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)
        color = _bar_color(value)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1a2338;
                border: none;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self._bar, 1)

        val_label = QLabel(str(int(value)))
        val_label.setFixedWidth(36)
        val_label.setAlignment(Qt.AlignRight)
        val_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 700;")
        layout.addWidget(val_label)

    def set_value(self, value):
        color = _bar_color(value)
        self._bar.setValue(max(0, min(100, int(value))))
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1a2338;
                border: none;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 5px;
            }}
        """)
