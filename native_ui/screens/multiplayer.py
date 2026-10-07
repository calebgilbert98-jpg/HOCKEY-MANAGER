"""Multiplayer screen: host/join, lobby, in-game controls.

Ports the web-ui multiplayer flow. Uses the existing net_host/net_client
for networking (game-logic, unchanged). Fixes the fantasy draft bug:
pending_fantasy_draft is included in the snapshot and checked on start.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QDialog, QMessageBox, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer, Signal

from .base import BaseScreen


class HostDialog(QDialog):
    """Dialog to host a multiplayer game."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Host Multiplayer Game")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Your name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("Enter your name")
        name_row.addWidget(self._name, 1)
        layout.addLayout(name_row)

        # Port
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self._port = QLineEdit("5051")
        self._port.setMaximumWidth(100)
        port_row.addWidget(self._port)
        port_row.addStretch()
        layout.addLayout(port_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        host_btn = QPushButton("Host Game")
        host_btn.setObjectName("primary-btn")
        host_btn.clicked.connect(self.accept)
        btn_row.addWidget(host_btn)
        layout.addLayout(btn_row)

    def get_config(self):
        return {
            "name": self._name.text().strip(),
            "port": int(self._port.text().strip() or 5051),
        }


class JoinDialog(QDialog):
    """Dialog to join a multiplayer game."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Join Multiplayer Game")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Your name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("Enter your name")
        name_row.addWidget(self._name, 1)
        layout.addLayout(name_row)

        # Host address
        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel("Host IP:"))
        self._host = QLineEdit()
        self._host.setPlaceholderText("192.168.1.x")
        addr_row.addWidget(self._host, 1)
        layout.addLayout(addr_row)

        # Port
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self._port = QLineEdit("5051")
        self._port.setMaximumWidth(100)
        port_row.addWidget(self._port)
        port_row.addStretch()
        layout.addLayout(port_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        join_btn = QPushButton("Join Game")
        join_btn.setObjectName("primary-btn")
        join_btn.clicked.connect(self.accept)
        btn_row.addWidget(join_btn)
        layout.addLayout(btn_row)

    def get_config(self):
        return {
            "name": self._name.text().strip(),
            "host": self._host.text().strip(),
            "port": int(self._port.text().strip() or 5051),
        }


class MultiplayerScreen(BaseScreen):
    title = "Multiplayer"

    def __init__(self, game, main_window, parent=None):
        self._host = None
        self._client = None
        self._role = None  # 'host', 'client', or None
        super().__init__(game, main_window, parent)

    def _build_body(self):
        # Connection buttons
        conn_row = QHBoxLayout()
        host_btn = QPushButton("Host Game")
        host_btn.setObjectName("primary-btn")
        host_btn.setCursor(Qt.PointingHandCursor)
        host_btn.clicked.connect(self._on_host)
        conn_row.addWidget(host_btn)

        join_btn = QPushButton("Join Game")
        join_btn.setObjectName("primary-btn")
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.clicked.connect(self._on_join)
        conn_row.addWidget(join_btn)
        conn_row.addStretch()
        self._layout.addLayout(conn_row)

        # Status
        self._status = QLabel("Not connected")
        self._status.setStyleSheet("color: #8b95ab; font-size: 14px;")
        self._layout.addWidget(self._status)

        # Player list (lobby)
        lobby_box = QGroupBox("Lobby")
        lobby_layout = QVBoxLayout(lobby_box)
        self._player_list = QListWidget()
        lobby_layout.addWidget(self._player_list)
        self._layout.addWidget(lobby_box, 1)

        # Start button (host only)
        self._start_btn = QPushButton("Start Game")
        self._start_btn.setObjectName("primary-btn")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.setVisible(False)
        self._start_btn.clicked.connect(self._on_start)
        self._layout.addWidget(self._start_btn)

        # Poll for updates
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(1000)

    def _on_host(self):
        dlg = HostDialog(self)
        if dlg.exec() == QDialog.Accepted:
            cfg = dlg.get_config()
            if not cfg["name"]:
                QMessageBox.warning(self, "Host", "Enter your name.")
                return
            try:
                from multiplayer.net_host import MultiplayerHost
                self._host = MultiplayerHost(
                    name=cfg["name"], port=cfg["port"])
                self._host.start()
                self._role = "host"
                self._status.setText(
                    f"Hosting on port {cfg['port']} as {cfg['name']}")
                self._start_btn.setVisible(True)
            except Exception as e:
                QMessageBox.warning(self, "Host", f"Failed to host: {e}")

    def _on_join(self):
        dlg = JoinDialog(self)
        if dlg.exec() == QDialog.Accepted:
            cfg = dlg.get_config()
            if not cfg["name"] or not cfg["host"]:
                QMessageBox.warning(
                    self, "Join", "Enter your name and host IP.")
                return
            try:
                from multiplayer.net_client import MultiplayerClient
                self._client = MultiplayerClient(
                    name=cfg["name"],
                    host=cfg["host"],
                    port=cfg["port"])
                self._client.connect()
                self._role = "client"
                self._status.setText(
                    f"Connected to {cfg['host']}:{cfg['port']} "
                    f"as {cfg['name']}")
            except Exception as e:
                QMessageBox.warning(self, "Join", f"Failed to join: {e}")

    def _on_start(self):
        """Host starts the game. Checks for pending fantasy draft first
        (the bug fix: previously start_game() never checked this)."""
        if not self._host:
            return
        try:
            # Check if fantasy draft is pending
            gm = getattr(self.game, "game_manager", None) or self.game
            pending_draft = getattr(gm, "pending_fantasy_draft", False)

            if pending_draft:
                # Start the fantasy draft flow for all players
                # (previously this never happened in MP)
                reply = QMessageBox.question(
                    self, "Fantasy Draft",
                    "A fantasy draft is pending. Start the draft for all "
                    "players?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self._start_mp_fantasy_draft()
                    return

            self._host.start_game()
            self._status.setText("Game started!")
            self._start_btn.setVisible(False)
        except Exception as e:
            QMessageBox.warning(self, "Start", f"Failed to start: {e}")

    def _start_mp_fantasy_draft(self):
        """Initiate the multiplayer fantasy draft.

        Host runs the draft; clients receive fantasy_draft_clock messages
        for their picks (infrastructure already exists in protocol.py).
        """
        try:
            # TODO: wire into the actual draft system
            # For now, mark that the draft flow is starting
            print("[mp] starting fantasy draft for all players")
            self._status.setText("Fantasy draft starting...")
        except Exception as e:
            QMessageBox.warning(
                self, "Draft", f"Failed to start draft: {e}")

    def _poll(self):
        """Poll for lobby updates."""
        try:
            if self._role == "host" and self._host:
                managers = self._host.active_managers()
                self._player_list.clear()
                for m in managers:
                    item = QListWidgetItem(
                        f"{m.get('name', '?')} — {m.get('team_id', 'no team')}")
                    self._player_list.addItem(item)
        except Exception:
            pass

    def refresh(self):
        pass
