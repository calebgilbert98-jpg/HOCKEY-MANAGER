"""Puck Dynasty 2K/NHL 14 dark broadcast theme for Qt.

Deep blue accent (#3B82F6), dark backgrounds, condensed type feel.
Applied application-wide via QApplication.setStyleSheet().
"""

THEME_QSS = """
/* ===== Puck Dynasty Native Theme ===== */
QMainWindow, QWidget {
    background-color: #0a0e17;
    color: #e8edf5;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 14px;
}
QWidget#hub-central {
    background-color: #0a0e17;
}

/* Header bar */
QWidget#topbar {
    background-color: #0d1320;
    border-bottom: 2px solid #3B82F6;
}
QLabel#brand {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
    letter-spacing: 2px;
}
QLabel#brand-sub {
    color: #3B82F6;
    font-size: 11px;
    letter-spacing: 4px;
}

/* Nav buttons */
QPushButton#nav-btn {
    background: transparent;
    border: none;
    color: #9aa4b8;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 10px 10px;
}
QPushButton#nav-btn:hover {
    color: #ffffff;
    background-color: #162032;
}
QPushButton#nav-btn:checked {
    color: #ffffff;
    background-color: #1a2740;
    border-bottom: 3px solid #3B82F6;
}

/* Primary action buttons (Continue, etc.) */
QPushButton#primary-btn {
    background-color: #3B82F6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 12px 32px;
}
QPushButton#primary-btn:hover {
    background-color: #2563eb;
}
QPushButton#primary-btn:pressed {
    background-color: #1d4ed8;
}
QPushButton#primary-btn:disabled {
    background-color: #2a3550;
    color: #6b7488;
}

/* Tile cards */
QFrame#tile {
    background-color: #111827;
    border: 1px solid #1e2a44;
    border-radius: 10px;
}
QFrame#tile:hover {
    border: 1px solid #3B82F6;
}
QLabel#tile-title {
    color: #8b95ab;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#tile-value {
    color: #ffffff;
    font-size: 28px;
    font-weight: 900;
}
QLabel#tile-sub {
    color: #9aa4b8;
    font-size: 12px;
}

/* Section headers */
QLabel#section-header {
    color: #ffffff;
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 1px;
}

/* Tables */
QTableWidget {
    background-color: #0d1320;
    alternate-background-color: #111a2e;
    gridline-color: #1e2a44;
    border: 1px solid #1e2a44;
    border-radius: 8px;
    selection-background-color: #1e3a5f;
}
QTableWidget::item {
    padding: 6px;
    color: #e8edf5;
}
QHeaderView::section {
    background-color: #162032;
    color: #8b95ab;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
    border: none;
    padding: 8px;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #0a0e17;
    width: 12px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #2a3550;
    border-radius: 6px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #3B82F6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Dialogs */
QDialog {
    background-color: #0d1320;
    border: 1px solid #2a3550;
    border-radius: 12px;
}
QLabel#dialog-title {
    color: #ffffff;
    font-size: 18px;
    font-weight: 800;
}

/* Blocker cards */
QFrame#blocker-card {
    background-color: #162032;
    border: 1px solid #2a3550;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
}
QLabel#blocker-title {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#blocker-detail {
    color: #9aa4b8;
    font-size: 13px;
}

/* Inputs */
QLineEdit, QComboBox, QSpinBox {
    background-color: #162032;
    border: 1px solid #2a3550;
    border-radius: 6px;
    color: #ffffff;
    padding: 8px 12px;
    selection-background-color: #3B82F6;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3B82F6;
}

/* Ticker */
QLabel#ticker {
    color: #8b95ab;
    font-size: 12px;
    background-color: #0d1320;
    border-top: 1px solid #1e2a44;
    padding: 6px;
}
"""
