"""Contract negotiation screen: dedicated negotiation UI.

Ports main.py open_contract_negotiation_window (ContractNegotiationView)
+ web_ui/screens/contracts.py negotiation endpoints. Separate from the
contracts list screen -- this is the one-on-one negotiation table.

Features:
  - Years slider (1-7)
  - AAV stepper with cap-fit gating
  - No-trade/no-movement clause picker
  - Signing + performance bonus inputs
  - Counter / Accept / Walk away flow
  - ELC mode for unsigned prospects

Game methods used (all real):
  - game._validate_contract_terms(player, aav, years, extension=...)
  - player.negotiate_contract(...) / agent counter logic
"""
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class ContractNegotiationScreen(BaseScreen):
    title = "Negotiation"

    def __init__(self, game, main_window, parent=None):
        self._player = None
        self._is_extension = False
        self._is_elc = False
        self._agent_ask = None  # agent's current demand
        super().__init__(game, main_window, parent)

    def set_negotiation(self, player, is_extension=False, is_elc=False):
        """Open negotiation for a player. Called by contracts screen."""
        self._player = player
        self._is_extension = is_extension
        self._is_elc = is_elc
        self._agent_ask = None
        self.refresh()

    def _build_body(self):
        # Player header
        self._player_label = QLabel("No player selected")
        self._player_label.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #ffffff;")
        self._layout.addWidget(self._player_label)

        self._mode_label = QLabel("")
        self._mode_label.setStyleSheet("color: #8b95ab; font-size: 13px;")
        self._layout.addWidget(self._mode_label)

        # Agent demand display
        self._demand_box = QGroupBox("Agent's Demand")
        demand_layout = QVBoxLayout(self._demand_box)
        self._demand_label = QLabel("—")
        self._demand_label.setStyleSheet(
            "font-size: 16px; color: #fbbf24; font-weight: 700;")
        demand_layout.addWidget(self._demand_label)
        self._layout.addWidget(self._demand_box)

        # Offer form
        form_box = QGroupBox("Your Offer")
        form = QFormLayout(form_box)

        # Years slider 1-7
        years_row = QHBoxLayout()
        self._years_slider = QSlider(Qt.Horizontal)
        self._years_slider.setRange(1, 7)
        self._years_slider.setValue(4)
        self._years_slider.setTickPosition(QSlider.TicksBelow)
        self._years_slider.setTickInterval(1)
        self._years_slider.valueChanged.connect(self._update_preview)
        self._years_label = QLabel("4 years")
        self._years_label.setMinimumWidth(70)
        years_row.addWidget(self._years_slider, 1)
        years_row.addWidget(self._years_label)
        form.addRow("Term:", years_row)

        # AAV stepper
        aav_row = QHBoxLayout()
        self._aav_spin = QDoubleSpinBox()
        self._aav_spin.setRange(0.75, 15.0)
        self._aav_spin.setSingleStep(0.1)
        self._aav_spin.setValue(3.0)
        self._aav_spin.setPrefix("$")
        self._aav_spin.setSuffix("M")
        self._aav_spin.setDecimals(2)
        self._aav_spin.valueChanged.connect(self._update_preview)
        aav_row.addWidget(self._aav_spin)
        aav_row.addStretch()
        form.addRow("AAV:", aav_row)

        # Clause picker
        self._clause_combo = QComboBox()
        self._clause_combo.addItems(
            ["None", "No-Trade Clause (NTC)", "No-Movement Clause (NMC)"])
        form.addRow("Clause:", self._clause_combo)

        # Signing bonus
        self._sb_spin = QDoubleSpinBox()
        self._sb_spin.setRange(0, 5.0)
        self._sb_spin.setSingleStep(0.1)
        self._sb_spin.setPrefix("$")
        self._sb_spin.setSuffix("M")
        form.addRow("Signing bonus:", self._sb_spin)

        # Performance bonus
        self._pb_spin = QDoubleSpinBox()
        self._pb_spin.setRange(0, 2.0)
        self._pb_spin.setSingleStep(0.1)
        self._pb_spin.setPrefix("$")
        self._pb_spin.setSuffix("M")
        form.addRow("Performance bonus:", self._pb_spin)

        self._layout.addWidget(form_box)

        # Cap fit preview
        self._preview_label = QLabel("")
        self._preview_label.setStyleSheet(
            "color: #8b95ab; font-size: 13px;")
        self._preview_label.setWordWrap(True)
        self._layout.addWidget(self._preview_label)

        # Action buttons
        btn_row = QHBoxLayout()
        self._counter_btn = QPushButton("Make Offer / Counter")
        self._counter_btn.setObjectName("primary-btn")
        self._counter_btn.setCursor(Qt.PointingHandCursor)
        self._counter_btn.clicked.connect(self._on_counter)
        btn_row.addWidget(self._counter_btn)

        self._accept_btn = QPushButton("Accept Agent's Terms")
        self._accept_btn.setCursor(Qt.PointingHandCursor)
        self._accept_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(self._accept_btn)

        walk_btn = QPushButton("Walk Away")
        walk_btn.setStyleSheet(
            "color: #ef4444; background: transparent; border: 1px solid #ef4444;"
            " border-radius: 6px; padding: 10px 20px;")
        walk_btn.setCursor(Qt.PointingHandCursor)
        walk_btn.clicked.connect(self._on_walk)
        btn_row.addWidget(walk_btn)

        btn_row.addStretch()
        self._layout.addLayout(btn_row)
        self._layout.addStretch()

    def _update_preview(self):
        years = self._years_slider.value()
        self._years_label.setText(f"{years} year{'s' if years != 1 else ''}")
        aav = self._aav_spin.value()
        total = aav * years
        # Cap fit check
        try:
            from salary_cap_system import cap_breakdown
            team = _safe(
                lambda: (getattr(self.game, "game_manager", None)
                         or self.game).user_team)
            if team is not None:
                bd = cap_breakdown(team)
                space = bd.get("space", 0) / 1e6
                fits = aav <= space
                color = "#22c55e" if fits else "#ef4444"
                self._preview_label.setText(
                    f"Total: ${total:.2f}M over {years} years. "
                    f"Cap space: ${space:.2f}M. "
                    f"<span style='color:{color}'>"
                    f"{'Fits under cap' if fits else 'OVER CAP'}</span>")
                self._counter_btn.setEnabled(fits)
                return
        except Exception:
            pass
        self._preview_label.setText(f"Total: ${total:.2f}M over {years} years.")

    def _get_offer(self):
        clause_map = {0: None, 1: "NTC", 2: "NMC"}
        return {
            "years": self._years_slider.value(),
            "aav": int(self._aav_spin.value() * 1_000_000),
            "clause": clause_map[self._clause_combo.currentIndex()],
            "signing_bonus": int(self._sb_spin.value() * 1_000_000),
            "performance_bonus": int(self._pb_spin.value() * 1_000_000),
        }

    def _on_counter(self):
        if not self._player:
            return
        offer = self._get_offer()
        try:
            game = getattr(self.game, "game_manager", None) or self.game
            # Validate through the game's own gate
            ok, reason = _safe(
                lambda: game._validate_contract_terms(
                    self._player, offer["aav"], offer["years"],
                    extension=self._is_extension),
                (True, ""))
            if not ok:
                QMessageBox.warning(
                    self, "Invalid Terms", str(reason or "Invalid terms."))
                return
            # Submit the offer — the agent responds via the game's
            # negotiation logic (may accept, counter, or reject)
            result = _safe(
                lambda: game.handle_contract_offer(
                    self._player, offer["aav"], offer["years"],
                    extension=self._is_extension))
            self._handle_agent_response(result, offer)
        except Exception as e:
            QMessageBox.warning(self, "Offer", f"Failed: {e}")

    def _handle_agent_response(self, result, offer):
        """Process the agent's verdict on our offer."""
        if not result:
            QMessageBox.information(
                self, "Offer Submitted",
                "Your offer has been submitted to the agent.")
            return
        verdict = str(result.get("verdict", "")).lower() if isinstance(
            result, dict) else ""
        if verdict == "accept":
            QMessageBox.information(
                self, "Deal!",
                f"{getattr(self._player, 'full_name', 'Player')} accepts!")
            self.navigate_to("contracts")
        elif verdict == "counter":
            counter = result.get("counter", {}) if isinstance(result, dict) else {}
            self._show_counter(counter)
        else:
            note = result.get("note", "The agent rejected the offer.") \
                if isinstance(result, dict) else "The agent rejected the offer."
            QMessageBox.information(self, "Rejected", str(note))

    def _show_counter(self, counter):
        """Display the agent's counter-offer."""
        try:
            aav = counter.get("aav", 0) / 1_000_000
            years = counter.get("years", 0)
            self._agent_ask = counter
            self._demand_label.setText(
                f"${aav:.2f}M × {years} years")
            # Pre-fill our form near their ask for one-click accept
            self._aav_spin.setValue(aav)
            self._years_slider.setValue(max(1, min(7, years)))
            QMessageBox.information(
                self, "Counter-Offer",
                f"The agent counters at ${aav:.2f}M × {years} years.\n"
                "Your offer form has been updated — adjust or accept.")
        except Exception:
            pass

    def _on_accept(self):
        if not self._player or not self._agent_ask:
            QMessageBox.information(
                self, "Accept",
                "No agent offer to accept yet. Make an offer first.")
            return
        try:
            aav = self._agent_ask.get("aav", 0)
            years = self._agent_ask.get("years", 0)
            game = getattr(self.game, "game_manager", None) or self.game
            result = _safe(
                lambda: game.handle_contract_offer(
                    self._player, aav, years,
                    extension=self._is_extension))
            QMessageBox.information(self, "Signed!", "Contract signed.")
            self.navigate_to("contracts")
        except Exception as e:
            QMessageBox.warning(self, "Accept", f"Failed: {e}")

    def _on_walk(self):
        reply = QMessageBox.question(
            self, "Walk Away",
            "Walk away from this negotiation?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Clear negotiation state
            try:
                game = getattr(self.game, "game_manager", None) or self.game
                negs = getattr(game, "_web_negotiations", None)
                if negs is not None and self._player is not None:
                    negs.pop(str(getattr(self._player, "id", "")), None)
            except Exception:
                pass
            self.navigate_to("contracts")

    def refresh(self):
        p = self._player
        if p is None:
            self._player_label.setText("No player selected")
            return
        name = getattr(p, "full_name", "?")
        self._player_label.setText(name)
        if self._is_elc:
            mode = "Entry-Level Contract"
        elif self._is_extension:
            mode = "Contract Extension"
        else:
            mode = "New Contract (Free Agent)"
        try:
            pos = getattr(p, "position", "?")
            pos_s = getattr(pos, "value", str(pos))
            age = getattr(p, "age", "?")
            mode += f" — {pos_s}, age {age}"
        except Exception:
            pass
        self._mode_label.setText(mode)
        # Seed the agent demand from the player's ask if available
        try:
            ask = getattr(p, "contract_ask", None) or getattr(p, "ask", None)
            if ask:
                aav = (ask.get("aav", 0) / 1_000_000) if isinstance(ask, dict) else 0
                years = ask.get("years", 0) if isinstance(ask, dict) else 0
                if aav and years:
                    self._demand_label.setText(f"${aav:.2f}M × {years} years")
                    self._aav_spin.setValue(min(15.0, aav))
                    self._years_slider.setValue(max(1, min(7, years)))
        except Exception:
            pass
        self._update_preview()
