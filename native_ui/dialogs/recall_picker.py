"""Recall picker dialog: emergency AHL recalls.

Ports main.py open_recall_picker. Tier-2 UI: when the club can't dress
18+2 and the farm has recallable players, show them best-first with
one-click Recall buttons (reuses call_up_to_nhl, so the paper-transaction
rule, dressing-room cascade and audition stamping all fire).

Non-modal in spirit -- in Qt this is a modeless QDialog.

Game functions used (all real):
  - roster_limits.lineup_shortfall(team) -> (sk_need, go_need)
  - roster_limits.recall_candidates(team, sk_need, go_need)
  - game.call_up_to_nhl(player)
"""
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class RecallPickerDialog(QDialog):
    """Modeless dialog listing recall candidates best-first."""

    def __init__(self, game, parent=None):
        super().__init__(parent)
        self.game = game
        # Modeless: user can navigate away and come back
        self.setModal(False)
        self.setWindowTitle("AHL Recalls — Cover the Shortfall")
        self.setMinimumSize(560, 520)

        layout = QVBoxLayout(self)

        self._need_label = QLabel("")
        self._need_label.setStyleSheet(
            "font-size: 14px; font-weight: 800; color: #ffffff;")
        self._need_label.setWordWrap(True)
        layout.addWidget(self._need_label)

        note = QLabel(
            "Recall from your farm team — same as real NHL clubs do. "
            "Emergency fill-ins stay the last resort.")
        note.setStyleSheet("color: #8b95ab; font-size: 12px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._load()

    def _load(self):
        try:
            import roster_limits as _rl
            game = getattr(self.game, "game_manager", None) or self.game
            team = _safe(lambda: game.user_team)
            if team is None:
                return
            sk_need, go_need = _rl.lineup_shortfall(team)
            if sk_need <= 0 and go_need <= 0:
                self._need_label.setText("No shortfall — lineup is complete.")
                return
            cands = _rl.recall_candidates(team, sk_need, go_need)

            bits = []
            if sk_need:
                bits.append(f"{sk_need} skater{'s' if sk_need != 1 else ''}")
            if go_need:
                bits.append(f"{go_need} goalie{'s' if go_need != 1 else ''}")
            self._need_label.setText(
                f"Short-handed: {', '.join(bits)} needed to dress a lineup.")

            self._list.clear()
            for p in cands:
                name = getattr(p, "full_name", "?")
                try:
                    ovr = int(p.overall_rating())
                except Exception:
                    ovr = getattr(p, "overall", "?")
                pos = getattr(p, "position", "?")
                pos_s = getattr(pos, "value", str(pos))
                item = QListWidgetItem(f"{name} ({pos_s}, {ovr} OVR)")
                item.setData(Qt.UserRole, p)
                self._list.addItem(item)

            self._list.itemDoubleClicked.connect(self._recall)
        except Exception as e:
            self._need_label.setText(f"Could not load candidates: {e}")

    def _recall(self, item):
        player = item.data(Qt.UserRole)
        if player is None:
            return
        name = getattr(player, "full_name", "?")
        reply = QMessageBox.question(
            self, "Recall",
            f"Recall {name} from the AHL?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            game = getattr(self.game, "game_manager", None) or self.game
            if hasattr(game, "call_up_to_nhl"):
                game.call_up_to_nhl(player)
            else:
                # Fallback: move via roster_limits
                import roster_limits as _rl
                if hasattr(_rl, "call_up"):
                    _rl.call_up(game.user_team, player)
            QMessageBox.information(
                self, "Recalled", f"{name} recalled to the NHL roster.")
            self._load()  # refresh the list
        except Exception as e:
            QMessageBox.warning(self, "Recall", f"Failed: {e}")


def maybe_open_recall_picker(game, parent=None):
    """Open the picker if there's a shortfall. Returns the dialog or None."""
    try:
        import roster_limits as _rl
        gm = getattr(game, "game_manager", None) or game
        team = _safe(lambda: gm.user_team)
        if team is None:
            return None
        sk_need, go_need = _rl.lineup_shortfall(team)
        if sk_need <= 0 and go_need <= 0:
            return None
        cands = _rl.recall_candidates(team, sk_need, go_need)
        if not cands:
            return None
        dlg = RecallPickerDialog(game, parent)
        dlg.show()  # modeless
        return dlg
    except Exception:
        return None
