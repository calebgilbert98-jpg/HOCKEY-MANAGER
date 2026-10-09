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
from native_ui.safe import safe_call


#: Contract-term widget limits. These mirror the engine's contract rules;
#: verify against the engine before changing.
MIN_CONTRACT_YEARS = 1
MAX_CONTRACT_YEARS = 7
MIN_OFFER_AAV_M = 0.75
MAX_OFFER_AAV_M = 15.0
MAX_SIGNING_BONUS_M = 5.0
MAX_PERFORMANCE_BONUS_M = 2.0


#: Shared contract-offer outcome wording. Use for both inline labels and
#: dialogs; reserve "Signed" for confirmed acceptance only.
OFFER_OUTCOME_TEXT = {
    "accepted": "Signed \u2014 the contract is filed.",
    "countered": "The player countered. Review the proposed terms.",
    "awaiting_agent": "Offer submitted; awaiting the agent's response.",
    "consideration": "Offer is under consideration; no contract is signed.",
    "rejected": "Offer rejected. No contract was signed.",
}


def offer_outcome_text(status):
    """Player-facing text for a contract-offer outcome status."""
    return OFFER_OUTCOME_TEXT.get(
        status, "Offer status unavailable.")


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
        self._offer_form = form  # for showing/hiding ELC-only rows

        # Years slider 1-7
        years_row = QHBoxLayout()
        self._years_slider = QSlider(Qt.Horizontal)
        self._years_slider.setRange(MIN_CONTRACT_YEARS, MAX_CONTRACT_YEARS)
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
        self._aav_spin.setRange(MIN_OFFER_AAV_M, MAX_OFFER_AAV_M)
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
        self._sb_spin.setRange(0, MAX_SIGNING_BONUS_M)
        self._sb_spin.setSingleStep(0.1)
        self._sb_spin.setPrefix("$")
        self._sb_spin.setSuffix("M")
        form.addRow("Signing bonus:", self._sb_spin)

        # Performance bonus
        self._pb_spin = QDoubleSpinBox()
        self._pb_spin.setRange(0, MAX_PERFORMANCE_BONUS_M)
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
            team = safe_call(
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
            if self._is_elc:
                # ELC path: the engine's handle_elc_offer takes salary and
                # both bonus types as params (band validation, prospect
                # handshake inside). No player-attribute staging needed.
                result = safe_call(
                    lambda: game.handle_elc_offer(
                        self._player, offer["aav"],
                        offer["signing_bonus"],
                        offer["performance_bonus"]))
                self._handle_agent_response(result, offer)
                return
            # Validate through the game's own gate
            ok, reason = safe_call(
                lambda: game._validate_contract_terms(
                    self._player, offer["aav"], offer["years"],
                    extension=self._is_extension),
                (True, ""))
            if not ok:
                QMessageBox.warning(
                    self, "Invalid Terms", str(reason or "Invalid terms."))
                return
            # The engine reads offer terms from person.salary and
            # person.contract_years — the caller MUST set these on the
            # player BEFORE calling. Passing dollars positionally would
            # land them in the extension/notify params (real signature:
            # handle_contract_offer(person, extension=False, notify="popup")).
            # It also reads person.offered_clause_kind /
            # person.offered_clause_list_size for trade protection, so the
            # clause picker is staged there too. Snapshot first: if the
            # deal isn't accepted, the offered terms must not leak into
            # the player's attributes.
            staged = ("salary", "contract_years", "offered_clause_kind",
                      "offered_clause_list_size")
            orig = {a: getattr(self._player, a, None) for a in staged}
            self._player.salary = offer["aav"]
            self._player.contract_years = offer["years"]
            self._player.offered_clause_kind = offer["clause"] or "none"
            self._player.offered_clause_list_size = 10
            # Submit the offer — the agent responds via the game's
            # negotiation logic (may accept, counter, or reject)
            result = safe_call(
                lambda: game.handle_contract_offer(
                    self._player, extension=self._is_extension,
                    notify="popup"))
            accepted = self._handle_agent_response(result, offer)
            if not accepted:
                for a in staged:
                    try:
                        setattr(self._player, a, orig[a])
                    except Exception:
                        pass
        except Exception as e:
            QMessageBox.warning(self, "Offer", f"Failed: {e}")

    def _set_bonus_rows_visible(self, visible):
        """Signing/performance bonuses only exist on ELCs (the engine's
        handle_elc_offer takes them as params; handle_contract_offer has
        no bonus support). Hide the rows in non-ELC mode so the UI never
        presents terms as applied when the engine would ignore them."""
        try:
            form = self._offer_form
            for spin in (self._sb_spin, self._pb_spin):
                spin.setVisible(visible)
                lbl = form.labelForField(spin)
                if lbl is not None:
                    lbl.setVisible(visible)
        except Exception:
            pass

    def _set_clause_row_visible(self, visible):
        """Trade-protection clauses only exist on standard contracts
        (the engine's handle_elc_offer has no clause parameter).
        Hide the clause picker in ELC mode so the UI never presents
        a term the engine would silently ignore."""
        try:
            form = self._offer_form
            self._clause_combo.setVisible(visible)
            lbl = form.labelForField(self._clause_combo)
            if lbl is not None:
                lbl.setVisible(visible)
        except Exception:
            pass

    def _offer_accepted(self, result):
        """True iff the engine actually signed the deal.

        Real engine shapes: True = signed (standard path),
        dict verdict "accept" = signed (standard path),
        dict verdict "accepted" = signed (ELC path via
        handle_elc_offer). False/None = refused or blocked (buyout ban,
        Dec-1 RFA ineligibility, already-signed player, failed
        validation), "consideration" = UFA bid period, still no deal.
        Everything else — counter, invalid, missing verdict,
        unrecognized — is not an acceptance.
        """
        if result is True:
            return True
        if isinstance(result, dict):
            return str(result.get("verdict", "")).lower() in ("accept",
                                                              "accepted")
        return False

    def _handle_agent_response(self, result, offer, signed_title="Deal!",
                               signed_text=None):
        """Process the agent's verdict on our offer.

        Returns True iff the deal was actually accepted (the only case
        where staged terms may stay on the player and we navigate away).
        signed_title/signed_text let the accept flow keep its "Signed!"
        wording while sharing the exact same verdict logic.
        """
        name = getattr(self._player, "full_name", "Player")
        if self._offer_accepted(result):
            QMessageBox.information(
                self, signed_title,
                signed_text if signed_text is not None
                else offer_outcome_text("accepted"))
            self.navigate_to("contracts")
            return True
        if result == "consideration":
            QMessageBox.information(
                self, "Under Consideration",
                offer_outcome_text("consideration"))
            return False
        if isinstance(result, dict):
            verdict = str(result.get("verdict", "")).lower()
            if verdict == "counter":
                counter = result.get("counter", {}) or {}
                self._show_counter(counter)
                return False
            note = result.get("note") or offer_outcome_text("rejected")
            QMessageBox.information(self, "Rejected", str(note))
            return False
        # Falsy or unrecognized: the engine refused or blocked the offer.
        QMessageBox.information(
            self, "Offer Not Accepted",
            offer_outcome_text("rejected") +
            " Your negotiation is still open.")
        return False

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
            self._years_slider.setValue(
                max(MIN_CONTRACT_YEARS,
                    min(MAX_CONTRACT_YEARS, years)))
            QMessageBox.information(
                self, "Counter-Offer",
                offer_outcome_text("countered") +
                f"\n${aav:.2f}M × {years} years.\n"
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
            game = getattr(self.game, "game_manager", None) or self.game
            if self._is_elc:
                # ELC accept: the agent's counter carries salary and both
                # bonus types; handle_elc_offer takes them as params.
                ask = self._agent_ask
                salary = ask.get("salary", ask.get("aav", 0))
                sb = ask.get("signing_bonus", 0)
                pb = ask.get("performance_bonus", 0)
                result = safe_call(
                    lambda: game.handle_elc_offer(
                        self._player, salary, sb, pb))
                self._handle_agent_response(
                    result, {"aav": salary, "years": 3,
                             "signing_bonus": sb,
                             "performance_bonus": pb},
                    signed_title="Signed!",
                    signed_text="Contract signed.")
                return
            aav = self._agent_ask.get("aav", 0)
            years = self._agent_ask.get("years", 0)
            # Validate the agent's terms through the same gate as our own
            # offers — a stale or illegal ask must not slip through.
            ok, reason = safe_call(
                lambda: game._validate_contract_terms(
                    self._player, aav, years,
                    extension=self._is_extension),
                (True, ""))
            if not ok:
                QMessageBox.warning(
                    self, "Invalid Terms", str(reason or "Invalid terms."))
                return
            # Same contract as _on_counter: the engine reads the terms from
            # person.salary / person.contract_years, so set them first —
            # plus the clause the agent asked for — but snapshot them so a
            # non-acceptance can't leak the ask into the player's
            # attributes.
            staged = ("salary", "contract_years", "offered_clause_kind",
                      "offered_clause_list_size")
            orig = {a: getattr(self._player, a, None) for a in staged}
            self._player.salary = aav
            self._player.contract_years = years
            ask_clause = self._agent_ask.get("clause")
            self._player.offered_clause_kind = ask_clause or "none"
            self._player.offered_clause_list_size = 10
            result = safe_call(
                lambda: game.handle_contract_offer(
                    self._player, extension=self._is_extension,
                    notify="popup"))
            accepted = self._handle_agent_response(
                result, {"aav": aav, "years": years},
                signed_title="Signed!", signed_text="Contract signed.")
            if not accepted:
                for a in staged:
                    try:
                        setattr(self._player, a, orig[a])
                    except Exception:
                        pass
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
        # Bonuses only exist on ELCs — hide the rows otherwise so the UI
        # never presents terms the engine would silently ignore.
        # Clauses only exist on standard contracts — hide in ELC mode.
        self._set_bonus_rows_visible(self._is_elc)
        self._set_clause_row_visible(not self._is_elc)
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
                    self._aav_spin.setValue(min(MAX_OFFER_AAV_M, aav))
                    self._years_slider.setValue(
                        max(MIN_CONTRACT_YEARS,
                            min(MAX_CONTRACT_YEARS, years)))
        except Exception:
            pass
        self._update_preview()
