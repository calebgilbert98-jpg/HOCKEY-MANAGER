from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QDialog, QMessageBox, QGroupBox,
    QComboBox, QTextEdit,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator

from .base import BaseScreen

DEFAULT_MP_PORT = 27107


class HostDialog(QDialog):
    """Dialog to host a multiplayer game."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Host Multiplayer Game")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Your name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("Enter your name")
        name_row.addWidget(self._name, 1)
        layout.addLayout(name_row)
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self._port = QLineEdit(str(DEFAULT_MP_PORT))
        self._port.setValidator(QIntValidator(1, 65535, self))
        self._port.setMaximumWidth(100)
        port_row.addWidget(self._port)
        port_row.addStretch()
        layout.addLayout(port_row)
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
        raw = (self._port.text() or "").strip()
        try:
            port = int(raw) if raw else DEFAULT_MP_PORT
        except ValueError:
            port = DEFAULT_MP_PORT
        if not 1 <= port <= 65535:
            port = DEFAULT_MP_PORT
        return {"name": self._name.text().strip(), "port": port}


class JoinDialog(QDialog):
    """Dialog to join a multiplayer game."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Join Multiplayer Game")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Your name:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("Enter your name")
        name_row.addWidget(self._name, 1)
        layout.addLayout(name_row)
        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel("Host IP:"))
        self._host = QLineEdit()
        self._host.setPlaceholderText("192.168.1.x")
        addr_row.addWidget(self._host, 1)
        layout.addLayout(addr_row)
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self._port = QLineEdit(str(DEFAULT_MP_PORT))
        self._port.setValidator(QIntValidator(1, 65535, self))
        self._port.setMaximumWidth(100)
        port_row.addWidget(self._port)
        port_row.addStretch()
        layout.addLayout(port_row)
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
        raw = (self._port.text() or "").strip()
        try:
            port = int(raw) if raw else DEFAULT_MP_PORT
        except ValueError:
            port = DEFAULT_MP_PORT
        if not 1 <= port <= 65535:
            port = DEFAULT_MP_PORT
        return {
            "name": self._name.text().strip(),
            "host": self._host.text().strip(),
            "port": port,
        }


class DraftPickDialog(QDialog):
    """Simplified MP draft-clock picker."""

    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.setWindowTitle(payload.get("title", "Your pick"))
        self.setMinimumSize(600, 500)
        self._payload = payload
        self._picked_id = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Pick #{payload.get('overall', '?')} "
            f"(Round {payload.get('round_num', '?')}) -- "
            f"{payload.get('draft_button_text', 'DRAFT')}"))
        self._list = QListWidget()
        for p in payload.get("players", []):
            pid = str(getattr(p, "id", getattr(p, "player_id", "")) or "")
            name = str(getattr(p, "full_name", getattr(p, "name", "?")) or "?")
            pos = str(getattr(p, "position", "") or "")
            try:
                ovr = int(getattr(p, "overall", 0) or 0)
            except Exception:
                ovr = 0
            item = QListWidgetItem(f"{name} ({pos}) -- OVR {ovr}")
            item.setData(Qt.UserRole, pid)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list, 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        pick_btn = QPushButton(payload.get("draft_button_text", "DRAFT"))
        pick_btn.setObjectName("primary-btn")
        pick_btn.clicked.connect(self._on_pick)
        btn_row.addWidget(pick_btn)
        layout.addLayout(btn_row)

    def _on_double_click(self, item):
        self._picked_id = item.data(Qt.UserRole)
        self.accept()

    def _on_pick(self):
        item = self._list.currentItem()
        if item:
            self._picked_id = item.data(Qt.UserRole)
            self.accept()

    @property
    def picked_id(self):
        return self._picked_id


class MultiplayerScreen(BaseScreen):
    title = "Multiplayer"

    def __init__(self, game, main_window, parent=None):
        self._host = None
        self._client = None
        self._role = None
        self._welcome = None
        self._orig_notify = None
        super().__init__(game, main_window, parent)

    def _build_body(self):
        conn_row = QHBoxLayout()
        self._host_btn = QPushButton("Host Game")
        self._host_btn.setObjectName("primary-btn")
        self._host_btn.setCursor(Qt.PointingHandCursor)
        self._host_btn.clicked.connect(self._on_host)
        conn_row.addWidget(self._host_btn)
        self._join_btn = QPushButton("Join Game")
        self._join_btn.setObjectName("primary-btn")
        self._join_btn.setCursor(Qt.PointingHandCursor)
        self._join_btn.clicked.connect(self._on_join)
        conn_row.addWidget(self._join_btn)
        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setCursor(Qt.PointingHandCursor)
        self._disconnect_btn.setVisible(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        conn_row.addWidget(self._disconnect_btn)
        conn_row.addStretch()
        self._layout.addLayout(conn_row)
        self._status = QLabel("Not connected")
        self._status.setStyleSheet("color: #8b95ab; font-size: 14px;")
        self._status.setWordWrap(True)
        self._layout.addWidget(self._status)
        lobby_box = QGroupBox("Lobby")
        lobby_layout = QVBoxLayout(lobby_box)
        self._player_list = QListWidget()
        lobby_layout.addWidget(self._player_list)
        self._layout.addWidget(lobby_box, 1)
        self._claim_box = QGroupBox("Claim a Team")
        claim_layout = QHBoxLayout(self._claim_box)
        self._team_combo = QComboBox()
        self._team_combo.setMinimumWidth(220)
        claim_layout.addWidget(self._team_combo, 1)
        self._claim_btn = QPushButton("Claim Team")
        self._claim_btn.setObjectName("primary-btn")
        self._claim_btn.clicked.connect(self._on_claim_team)
        claim_layout.addWidget(self._claim_btn)
        self._claim_box.setVisible(False)
        self._layout.addWidget(self._claim_box)
        self._ready_box = QGroupBox("Day Advance")
        ready_layout = QHBoxLayout(self._ready_box)
        self._ready_btn = QPushButton("I'm Ready")
        self._ready_btn.setCheckable(True)
        self._ready_btn.setCursor(Qt.PointingHandCursor)
        self._ready_btn.clicked.connect(self._on_ready_toggle)
        ready_layout.addWidget(self._ready_btn)
        self._ready_status = QLabel("")
        self._ready_status.setStyleSheet("color: #8b95ab;")
        self._ready_status.setWordWrap(True)
        ready_layout.addWidget(self._ready_status, 1)
        self._ready_box.setVisible(False)
        self._layout.addWidget(self._ready_box)
        self._start_btn = QPushButton("Start Game")
        self._start_btn.setObjectName("primary-btn")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.setVisible(False)
        self._start_btn.clicked.connect(self._on_start)
        self._layout.addWidget(self._start_btn)
        log_box = QGroupBox("Event Log")
        log_layout = QVBoxLayout(log_box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        log_layout.addWidget(self._log)
        self._layout.addWidget(log_box)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(1000)
        self._pump_timer = QTimer(self)
        self._pump_timer.timeout.connect(self._pump_mp_events)
        self._pump_timer.start(250)
        self._install_notify_hook()

    def _install_notify_hook(self):
        game = self._game()
        if game is None or self._orig_notify is not None:
            return
        try:
            self._orig_notify = game._ui_notify

            def _mp_notify(kind, *args, **kwargs):
                try:
                    self._on_mp_notify(kind, *args, **kwargs)
                except Exception:
                    pass
                try:
                    return self._orig_notify(kind, *args, **kwargs)
                except Exception:
                    return None

            game._ui_notify = _mp_notify
        except Exception:
            self._orig_notify = None

    def _game(self):
        return getattr(self, "game", None) or getattr(
            self.main_window, "game", None)

    def _log_msg(self, msg):
        try:
            self._log.append(msg)
        except Exception:
            pass

    def _on_host(self):
        dlg = HostDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        cfg = dlg.get_config()
        if not cfg["name"]:
            QMessageBox.warning(self, "Host", "Enter your name.")
            return
        game = self._game()
        if game is None:
            QMessageBox.warning(self, "Host", "No game loaded.")
            return
        if getattr(game, "save_manager", None) is None:
            QMessageBox.warning(
                self, "Host",
                "Save system unavailable -- cannot host without it.")
            return
        self._teardown_session()

        def _state_provider():
            import gzip
            import pickle
            blob = gzip.compress(pickle.dumps(
                game.save_manager.create_save_data(),
                protocol=pickle.HIGHEST_PROTOCOL))
            return blob, str(getattr(game, "current_date", "")), "host-sync"

        def _get_teams():
            try:
                return [{"id": t.team_name, "name": t.team_name}
                        for t in game.league.teams]
            except Exception:
                return []

        try:
            from multiplayer.net_host import MultiplayerHost
            host = MultiplayerHost(
                _state_provider,
                host_name=cfg["name"],
                port=cfg["port"],
                get_teams=_get_teams)
            host.start()
        except OSError as e:
            QMessageBox.warning(
                self, "Host", f"Could not bind port {cfg['port']}: {e}")
            return
        except Exception as e:
            QMessageBox.warning(self, "Host", f"Failed to host: {e}")
            return
        try:
            reservations, names = {}, {}
            for t in game.league.teams:
                tok = getattr(t, "mp_gm_token", "") or ""
                if tok:
                    reservations[tok] = t.team_name
                    names[tok] = getattr(t, "mp_gm_name", "") or ""
            host.seed_reservations(reservations, names)
        except Exception:
            pass
        try:
            user_team = getattr(game, "user_team", None)
            if user_team is not None:
                host.host_team_id = getattr(user_team, "team_name", None)
        except Exception:
            pass
        self._host = host
        self._role = "host"
        game.mp_host = host
        game.mp_client = None
        self._status.setText(
            f"Hosting on port {cfg['port']} as {cfg['name']}")
        self._start_btn.setVisible(True)
        self._ready_box.setVisible(True)
        self._host_btn.setEnabled(False)
        self._join_btn.setEnabled(False)
        self._disconnect_btn.setVisible(True)
        self._log_msg(f"Hosting on port {cfg['port']}")

    def _on_join(self):
        dlg = JoinDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        cfg = dlg.get_config()
        if not cfg["name"] or not cfg["host"]:
            QMessageBox.warning(self, "Join", "Enter your name and host IP.")
            return
        game = self._game()
        if game is None:
            QMessageBox.warning(self, "Join", "No game loaded.")
            return
        self._teardown_session()
        try:
            from multiplayer.net_client import MultiplayerClient
            client = MultiplayerClient(cfg["name"])
            welcome = client.connect(cfg["host"], cfg["port"])
        except Exception as e:
            QMessageBox.warning(self, "Join", f"Failed to join: {e}")
            return
        self._client = client
        self._role = "client"
        self._welcome = welcome or {}
        game.mp_client = client
        game.mp_host = None
        self._status.setText(
            f"Connected to {cfg['host']}:{cfg['port']} as {cfg['name']}")
        self._claim_box.setVisible(True)
        self._ready_box.setVisible(True)
        self._host_btn.setEnabled(False)
        self._join_btn.setEnabled(False)
        self._disconnect_btn.setVisible(True)
        self._refresh_team_combo()
        self._log_msg(f"Connected to {cfg['host']}:{cfg['port']}")

    def _refresh_team_combo(self):
        self._team_combo.clear()
        if not self._welcome:
            return
        teams = self._welcome.get("teams") or []
        taken = self._welcome.get("teams_taken") or {}
        for t in teams:
            tid = t.get("id", "")
            name = t.get("name", tid)
            if tid and tid not in taken:
                self._team_combo.addItem(name, tid)
        if self._team_combo.count() == 0:
            self._team_combo.addItem("(no teams available)", "")

    def _on_claim_team(self):
        if not self._client:
            return
        team_id = self._team_combo.currentData()
        if not team_id:
            QMessageBox.information(self, "Claim Team", "No team selected.")
            return
        try:
            self._client.claim_team(team_id)
            self._status.setText(f"Claimed {team_id} -- waiting for host...")
            self._log_msg(f"Claimed team {team_id}")
        except Exception as e:
            QMessageBox.warning(self, "Claim Team", f"Failed to claim: {e}")

    def _on_ready_toggle(self):
        game = self._game()
        ready = self._ready_btn.isChecked()
        self._ready_btn.setText("Ready!" if ready else "I'm Ready")
        try:
            if self._role == "host" and game is not None:
                game._mp_host_ready = bool(ready)
                game._mp_evaluate_advance_gate("host ready toggle")
            elif self._role == "client" and self._client is not None:
                if ready:
                    self._client.send_ready()
                else:
                    self._client.send_unready()
        except Exception as e:
            self._log_msg(f"Ready toggle failed: {e}")

    def _on_start(self):
        if not self._host:
            return
        try:
            game = self._game()
            gm = getattr(game, "game_manager", None) or game
            pending_draft = getattr(gm, "pending_fantasy_draft", False)
            if pending_draft:
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
            self._log_msg("Game started")
        except Exception as e:
            QMessageBox.warning(self, "Start", f"Failed to start: {e}")

    def _start_mp_fantasy_draft(self):
        try:
            game = self._game()
            gm = getattr(game, "game_manager", None) or game
            if gm is not None and hasattr(gm, "start_interactive_fantasy_draft"):
                gm.start_interactive_fantasy_draft()
            try:
                self.main_window.show_screen("fantasy_draft")
            except Exception:
                pass
            self._status.setText("Fantasy draft starting...")
            self._log_msg("Fantasy draft started")
        except Exception as e:
            QMessageBox.warning(self, "Draft", f"Failed to start draft: {e}")

    def _on_disconnect(self):
        self._teardown_session()
        self._status.setText("Not connected")
        self._log_msg("Disconnected")

    def _teardown_session(self):
        game = self._game()
        if self._host is not None:
            try:
                self._host.stop()
            except Exception:
                pass
            self._host = None
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        if game is not None:
            try:
                game.mp_host = None
            except Exception:
                pass
            try:
                game.mp_client = None
            except Exception:
                pass
        self._role = None
        self._welcome = None
        self._start_btn.setVisible(False)
        self._claim_box.setVisible(False)
        self._ready_box.setVisible(False)
        self._ready_btn.setChecked(False)
        self._ready_btn.setText("I'm Ready")
        self._host_btn.setEnabled(True)
        self._join_btn.setEnabled(True)
        self._disconnect_btn.setVisible(False)
        self._player_list.clear()

    def _pump_mp_events(self):
        game = self._game()
        if game is None:
            return
        host = getattr(game, "mp_host", None) or self._host
        if host is not None:
            try:
                handler = getattr(game, "_handle_host_event", None)
                if callable(handler):
                    for kind, payload in host.poll_events():
                        try:
                            handler(kind, payload)
                        except Exception as e:
                            self._log_msg(f"host event {kind} failed: {e}")
            except Exception:
                pass
        client = getattr(game, "mp_client", None) or self._client
        if client is not None and host is None:
            try:
                handler = getattr(game, "_handle_client_event", None)
                if callable(handler):
                    for kind, payload in client.poll_events():
                        try:
                            handler(kind, payload)
                        except Exception as e:
                            self._log_msg(f"client event {kind} failed: {e}")
            except Exception:
                pass

    def _poll(self):
        self._pump_mp_events()
        try:
            host = self._host
            if self._role == "host" and host:
                managers = host.active_managers()
                self._player_list.clear()
                for m in managers:
                    item = QListWidgetItem(
                        f"{m.get('name', '?')} -- {m.get('team_id', 'no team')}")
                    self._player_list.addItem(item)
            elif self._role == "client" and self._client:
                managers = getattr(self._client, "managers", []) or []
                self._player_list.clear()
                for m in managers:
                    item = QListWidgetItem(
                        f"{m.get('name', '?')} -- {m.get('team_id', 'no team')}")
                    self._player_list.addItem(item)
        except Exception:
            pass

    def _on_mp_notify(self, kind, *args, **kwargs):
        if kind == "info":
            msg = str(args[0]) if args else ""
            if msg:
                self._status.setText(msg)
                self._log_msg(msg)
        elif kind == "warning":
            msg = str(args[0]) if args else ""
            if msg:
                self._log_msg(f"WARN: {msg}")
        elif kind == "error":
            title = str(args[0]) if len(args) > 0 else "Error"
            msg = str(args[1]) if len(args) > 1 else str(args[0]) if args else ""
            QMessageBox.warning(self, title, msg)
            self._log_msg(f"ERROR: {title}: {msg}")
        elif kind == "mp_trade_offer":
            self._show_trade_offer_dialog(args[0] if args else {})
        elif kind == "mp_ntc_request":
            self._show_ntc_dialog(args[0] if args else {})
        elif kind == "mp_draft_clock":
            self._show_draft_clock_dialog(args[0] if args else {})
        elif kind == "mp_disconnected":
            self._show_disconnect_dialog(str(args[0]) if args else "connection lost")
        elif kind == "mp_state_synced":
            label = str(args[0]) if args else ""
            self._log_msg(f"Synced: {label}")
            self._status.setText(f"Synced: {label}" if label else self._status.text())
        elif kind == "mp_snapshot_failed":
            self._teardown_session()
            self._status.setText("Not connected")
        elif kind == "mp_promote_to_host":
            self._promote_to_host(args[0] if args else "")
        elif kind == "mp_refresh":
            pass

    def _show_trade_offer_dialog(self, payload):
        game = self._game()
        if game is None:
            return
        offer_id = payload.get("offer_id", "")
        from_team = payload.get("from_team", "?")
        from_manager = payload.get("from_manager", "?")
        offer = payload.get("offer", {})
        detail = str(offer)[:500] if offer else "(no details)"
        reply = QMessageBox.question(
            self, "Trade Offer",
            f"{from_manager} ({from_team}) offers a trade:\n\n{detail}\n\nAccept?",
            QMessageBox.Yes | QMessageBox.No)
        try:
            game._mp_answer_trade_offer(
                offer_id, "accept" if reply == QMessageBox.Yes else "reject")
        except Exception as e:
            self._log_msg(f"Trade answer failed: {e}")

    def _show_ntc_dialog(self, payload):
        game = self._game()
        if game is None:
            return
        waiver_id = payload.get("waiver_id", "")
        player_id = payload.get("player_id", "")
        name = payload.get("player_name", "A player")
        clause = payload.get("clause", "clause")
        dest = payload.get("dest_team", "?")
        context = payload.get("context", "trade")
        if context == "waivers":
            question = (f"{name} has a {clause}.\n\n"
                        f"He must approve being exposed on waivers. Ask him?\n\n"
                        f"Yes = ask him | No = keep him | Cancel = stop")
        else:
            question = (f"{name} has a {clause}.\n\n"
                        f"Ask him to waive it for a move to {dest}?\n\n"
                        f"Yes = ask him | No = remove him | Cancel = stop")
        reply = QMessageBox.question(
            self, "No-Trade Clause", question,
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        choice = ("ask" if reply == QMessageBox.Yes
                  else "remove" if reply == QMessageBox.No else "cancel")
        try:
            game._mp_answer_ntc_request_choice(waiver_id, player_id, choice)
        except Exception as e:
            self._log_msg(f"NTC answer failed: {e}")

    def _show_draft_clock_dialog(self, payload):
        game = self._game()
        if game is None:
            return
        dlg = DraftPickDialog(payload, self)
        if dlg.exec() == QDialog.Accepted and dlg.picked_id:
            try:
                game._mp_answer_draft_clock(
                    payload.get("clock_id", ""),
                    payload.get("action_name", ""),
                    payload.get("answer_attr", ""),
                    payload.get("my_team_id", ""),
                    dlg.picked_id)
            except Exception as e:
                self._log_msg(f"Draft pick failed: {e}")
        else:
            self._log_msg(payload.get("expire_toast", "Draft clock expired."))

    def _show_disconnect_dialog(self, reason):
        reply = QMessageBox.question(
            self, "Disconnected",
            f"Lost connection to the host.\n\n{reason}\n\n"
            f"Your last synced state was kept as a fallback checkpoint.\n"
            f"Promote this client to host so the session can continue?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            game = self._game()
            if game is not None:
                try:
                    game._mp_promote_to_host()
                except Exception as e:
                    QMessageBox.warning(
                        self, "Promote Failed",
                        f"Couldn't take over as host:\n{e}")

    def _promote_to_host(self, ckpt_path):
        game = self._game()
        if game is None:
            return
        dlg = HostDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        cfg = dlg.get_config()
        if not cfg["name"]:
            QMessageBox.warning(self, "Host", "Enter your name.")
            return
        self._teardown_session()

        def _state_provider():
            import gzip
            import pickle
            blob = gzip.compress(pickle.dumps(
                game.save_manager.create_save_data(),
                protocol=pickle.HIGHEST_PROTOCOL))
            return blob, str(getattr(game, "current_date", "")), "promoted-host"

        def _get_teams():
            try:
                return [{"id": t.team_name, "name": t.team_name}
                        for t in game.league.teams]
            except Exception:
                return []

        try:
            from multiplayer.net_host import MultiplayerHost
            host = MultiplayerHost(
                _state_provider, host_name=cfg["name"],
                port=cfg["port"], get_teams=_get_teams)
            try:
                reservations, names = {}, {}
                for t in game.league.teams:
                    tok = getattr(t, "mp_gm_token", "") or ""
                    if tok:
                        reservations[tok] = t.team_name
                        names[tok] = getattr(t, "mp_gm_name", "") or ""
                host.seed_reservations(reservations, names)
            except Exception:
                pass
            try:
                claimed = getattr(game, "user_team", None)
                if claimed is not None:
                    host.host_team_id = getattr(claimed, "team_name", None)
            except Exception:
                pass
            host.start()
        except Exception as e:
            QMessageBox.warning(self, "Host", f"Failed to host: {e}")
            return
        self._host = host
        self._role = "host"
        game.mp_host = host
        self._status.setText(
            f"Hosting (promoted) on port {cfg['port']} as {cfg['name']}")
        self._start_btn.setVisible(False)
        self._ready_box.setVisible(True)
        self._host_btn.setEnabled(False)
        self._join_btn.setEnabled(False)
        self._disconnect_btn.setVisible(True)
        self._log_msg("Promoted to host")

    def refresh(self):
        self._poll()
