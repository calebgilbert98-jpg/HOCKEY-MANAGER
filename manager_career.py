# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Football Manager-style career systems for Puck Dynasty.

Pure logic module (no tkinter) so it can be unit-tested headless.
Covers: board confidence & job security, player happiness & private chats,
press conferences, team talks, opposition scout reports, training schedules,
youth intake, and manager reputation.

All state is plain data (dicts/lists/str/int/float) so CareerState can be
pickled into save files via to_dict()/from_dict().
"""

import math
import random
import importlib  # R18: deferred Tk-module imports use importlib.import_module
                  # (invisible to PyInstaller's static analysis).
from datetime import date
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Board & job security
# ---------------------------------------------------------------------------

EXPECTATIONS = {
    "win_cup": {
        "label": "Win the Stanley Cup",
        "description": "The board expects a championship. Anything less is failure.",
        "min_confidence_for_sack": 15,
    },
    "contend": {
        "label": "Contend (reach Conference Final)",
        "description": "The board expects a deep playoff run.",
        "min_confidence_for_sack": 10,
    },
    "playoffs": {
        "label": "Make the playoffs",
        "description": "The board expects postseason hockey.",
        "min_confidence_for_sack": 5,
    },
    "rebuild": {
        "label": "Rebuild and develop youth",
        "description": "The board is patient. Develop young players; results matter less.",
        "min_confidence_for_sack": 0,
    },
}


class OwnerProfile:
    """The person signing the cheques. Personality drives the patience game.

    Archetypes:
      patient_builder  - believes in projects; grants patience easily, means it.
      demanding        - win-now; grants rarely and remembers refusals.
      meddler          - grants, but attaches conditions (play the kids / cut spending).
      distant          - barely watches; coin-flip, decided on vibes.
    """

    ARCHETYPES = {
        "patient_builder": {
            "label": "Patient builder",
            "grant": 0.75,
            "grant_line": ("\"I hired you to build something, not to win October. "
                           "You've got time — spend it well.\""),
            "refuse_line": ("\"I'd love to give you more rope, but the partners "
                            "are asking questions I can't answer.\""),
        },
        "demanding": {
            "label": "Demanding win-now owner",
            "grant": 0.35,
            "grant_line": ("\"Fine. Sixty days. But I want to see a plan, not excuses — "
                           "and the next skid ends this conversation.\""),
            "refuse_line": ("\"Patience? I bought a hockey team, not a trust fund. "
                            "Win games.\""),
        },
        "meddler": {
            "label": "Meddling owner",
            "grant": 0.55,
            "grant_line": ("\"Alright — but I'm watching the lineup card. The kids play, "
                           "the veterans earn it. We do this my way now.\""),
            "refuse_line": ("\"I gave you my patience when I signed the cheques. "
                            "Don't ask me twice.\""),
        },
        "distant": {
            "label": "Distant financier",
            "grant": 0.50,
            "grant_line": ("\"My people say the underlying numbers are fine. "
                           "Keep me out of the papers and we're good.\""),
            "refuse_line": ("\"The accountants are nervous. So am I. "
                            "That's all I have to say about that.\""),
        },
    }

    def __init__(self, archetype: str = "patient_builder"):
        if archetype not in self.ARCHETYPES:
            archetype = "patient_builder"
        self.archetype = archetype

    @classmethod
    def random(cls, rng=None) -> "OwnerProfile":
        import random as _r
        r = rng or _r
        # League-wide ownership mix: most owners understand projects take time.
        roll = r.random()
        if roll < 0.35:
            return cls("patient_builder")
        if roll < 0.60:
            return cls("demanding")
        if roll < 0.80:
            return cls("meddler")
        return cls("distant")

    @property
    def label(self) -> str:
        return self.ARCHETYPES[self.archetype]["label"]

    @property
    def base_grant(self) -> float:
        return self.ARCHETYPES[self.archetype]["grant"]

    def to_dict(self) -> dict:
        return {"archetype": self.archetype}

    @classmethod
    def from_dict(cls, data: dict) -> "OwnerProfile":
        return cls((data or {}).get("archetype", "patient_builder"))


# Monthly review bands per board expectation: (min_points_pct, tone, delta).
# Below the last band = "alarmed" with the expectation's alarmed_delta.
# Boards judge trends, not games — and a rebuild board judges development,
# not the standings.
MONTHLY_BANDS = {
    "win_cup":  {"bands": [(0.68, "delighted", 5), (0.58, "satisfied", 2),
                           (0.48, "concerned", -4)], "alarmed": -8},
    "contend":  {"bands": [(0.62, "delighted", 5), (0.54, "satisfied", 2),
                           (0.44, "concerned", -3)], "alarmed": -7},
    "playoffs": {"bands": [(0.58, "delighted", 4), (0.50, "satisfied", 2),
                           (0.40, "concerned", -3)], "alarmed": -6},
    "rebuild":  {"bands": [(0.50, "delighted", 4), (0.42, "satisfied", 2),
                           (0.32, "concerned", -2)], "alarmed": -5},
}

# Crisis triggers: the only per-game board channel. Boards don't review
# every game — they intervene when the situation is dire or disastrous.
CRISIS_LOSS_STREAK = 8      # -10 + formal warning
CRISIS_WIN_STREAK = 8       # +5, a run worth noticing
DISASTER_START_GAMES = 12   # winless-ish start over this many games...
DISASTER_START_PCT = 0.15   # ...at or below this points% = -12


class BoardSystem:
    """Tracks board confidence and job security."""

    def __init__(self):
        self.expectation: Optional[str] = None
        self.confidence: int = 60  # 0-100
        self.season_wins: int = 0
        self.season_losses: int = 0
        self.season_otl: int = 0
        self.last_review: str = ""
        self.warnings_given: int = 0
        self.sacked: bool = False
        # Muck's flag: if False, board cannot sack (confidence still matters
        # for budgets/morale). Set from settings.json -> career.gm_can_be_sacked.
        self.can_be_sacked: bool = True
        # -- patience model (Muck's retune): boards judge trends, not games --
        self.season_number: int = 1      # career year at this club
        self.streak: int = 0            # signed: +win streak / -loss streak
        self.patience_factor: float = 1.0  # >1 = patient board (divides negatives)
        self.owner: OwnerProfile = OwnerProfile()
        self.inherited_rebuild: bool = False  # hired into a mess?
        self.roster_youth: bool = False       # young roster buys slack
        self.recent_cups: int = 0             # banked goodwill
        self.patience_until: str = ""         # ISO date: granted-patience window
        self.patience_cooldown_until: str = ""
        self.refusal_hangover_until: str = ""
        self.patience_refusals: int = 0
        self.disaster_start_flagged: bool = False
        self._disaster: bool = False    # scandal / catastrophic skid: no honeymoon
        self.last_crisis: str = ""      # surfaced by main.py after record_result
        # -- anti-double-jeopardy: one bad stretch, one punishment -----------
        self._month_key: str = ""       # "YYYY-MM" of tracked deltas
        self._month_delta: int = 0      # signed confidence movement this month

    # -- setup ------------------------------------------------------------
    def set_expectation(self, key: str):
        if key in EXPECTATIONS:
            self.expectation = key

    def auto_expectation(self, team_strength: float):
        """Pick a sensible expectation from team strength (0-100)."""
        if team_strength >= 72:
            self.set_expectation("win_cup")
        elif team_strength >= 62:
            self.set_expectation("contend")
        elif team_strength >= 52:
            self.set_expectation("playoffs")
        else:
            self.set_expectation("rebuild")

    # -- patience model ---------------------------------------------------
    def on_hired(self, team_strength: float, roster_avg_age: float,
                 date_iso: str, recent_cups: int = 0,
                 owner: Optional[OwnerProfile] = None):
        """Seed the patience model on day one.

        A first-year GM inheriting a mess gets a honeymoon: the board knows
        projects take time and owners don't want to rotate GMs every year.
        """
        self.season_number = 1
        self.inherited_rebuild = (self.expectation == "rebuild"
                                  or team_strength < 52)
        self.roster_youth = roster_avg_age < 26
        self.recent_cups = recent_cups
        self.owner = owner or OwnerProfile.random()
        self._compute_patience_factor()

    def _compute_patience_factor(self):
        """Patience > 1 divides every negative delta. Finite, and earned."""
        f = 1.0
        if self.season_number == 1:
            f += 0.4                      # honeymoon: bumpy starts expected
        elif self.season_number == 2:
            f += 0.15
        if self.inherited_rebuild:
            f += 0.2                      # "the team wasn't in a good spot"
        if self.roster_youth:
            f += 0.1
        f += 0.3 * min(self.recent_cups, 2)  # banked goodwill, decays with time
        self.patience_factor = max(0.7, min(1.8, f))

    @staticmethod
    def _on_or_after(today_iso: str, until_iso: str) -> bool:
        """True if today is within a window ending at until_iso."""
        if not today_iso or not until_iso:
            return False
        try:
            import datetime as _dt
            return (_dt.date.fromisoformat(today_iso)
                    <= _dt.date.fromisoformat(until_iso))
        except Exception:
            return False

    @staticmethod
    def _add_days(date_iso: str, days: int) -> str:
        import datetime as _dt
        try:
            d = _dt.date.fromisoformat(date_iso) + _dt.timedelta(days=days)
            return d.isoformat()
        except Exception:
            return date_iso

    def _dampen_negative(self, delta: int, today_iso: str = "") -> int:
        """Apply the patience model to a negative delta. Min -1."""
        d = delta / max(0.7, self.patience_factor)
        if self._on_or_after(today_iso, self.patience_until):
            d *= 0.5                      # owner publicly backed you
        if self._on_or_after(today_iso, self.refusal_hangover_until):
            d *= 1.25                     # spent your capital, kept losing
        return -max(1, int(round(-d)))

    def _apply_delta(self, delta: int, today_iso: str = "",
                     channel: str = "other") -> int:
        """Central confidence mover. Enforces the anti-pile-on rules:

        - Monthly negative cap (-12): a bad stretch gets punished ONCE, not
          once per channel (crisis trigger + monthly review + press answers
          can't stack into a death spiral).
        - Comeback boost: positive movement counts 1.5x when confidence is
          under 25 — a win at rock bottom is a lifeline, not a footnote.
        Big one-off events (scandal etc.) bypass the cap: they're discrete,
        not the same stretch twice.
        """
        if not delta:
            return 0
        month = (today_iso or "")[:7]
        if month and month != self._month_key:
            self._month_key = month
            self._month_delta = 0
        if delta > 0 and self.confidence < 25:
            delta = int(round(delta * 1.5))
        if delta < 0 and channel != "big_event":
            if self._month_delta <= -12:
                return 0                    # already punished this month
            allowed = -12 - self._month_delta  # e.g. -5 when -7 banked
            delta = max(delta, allowed)
        self.confidence = max(0, min(100, self.confidence + delta))
        self._month_delta += delta
        self._check_sack()
        return delta

    # -- results ----------------------------------------------------------
    def record_result(self, won: bool, went_ot: bool, was_favorite: bool,
                      is_playoff: bool = False, today_iso: str = "") -> int:
        """Track the result. The board does NOT review every game — it only
        intervenes when the situation is dire or disastrous. Returns the
        confidence delta applied (usually 0). Check self.last_crisis after."""
        if won:
            self.season_wins += 1
            self.streak = self.streak + 1 if self.streak >= 0 else 1
        elif went_ot:
            self.season_otl += 1
            self.streak = 0               # a point stops the bleeding
        else:
            self.season_losses += 1
            self.streak = self.streak - 1 if self.streak <= 0 else -1
        self.last_crisis = ""
        delta = 0
        games = self.season_wins + self.season_losses + self.season_otl

        if is_playoff:
            # Short series: every game matters, but modestly.
            delta = 2 if won else -3
        elif self.streak == -CRISIS_LOSS_STREAK:
            delta = self._dampen_negative(-10, "")
            self.warnings_given += 1
            self.last_crisis = (
                f"Board alarmed: {CRISIS_LOSS_STREAK}-game losing streak. "
                "A formal warning has been issued — turn it around.")
        elif self.streak <= -12:
            # Burning it to the ground: honeymoon over, even in year one.
            self._disaster = True
            self.warnings_given += 1
            self.last_crisis = (
                "The board has seen enough. This is a disaster — "
                "the next review decides your future.")
            delta = self._dampen_negative(-10, "")
        elif self.streak == CRISIS_WIN_STREAK:
            delta = 5
            self.last_crisis = (
                f"Board delighted: {CRISIS_WIN_STREAK}-game winning streak. "
                "The project is ahead of schedule.")
        elif (not self.disaster_start_flagged and games <= DISASTER_START_GAMES
                and games >= 8
                and (self.season_wins * 2 + self.season_otl) / (games * 2)
                <= DISASTER_START_PCT):
            # 0-10 start puts a fire under anyone — honeymoon or not.
            delta = -12
            self.disaster_start_flagged = True
            self._disaster = True
            self.warnings_given += 1
            self.last_crisis = (
                "Disastrous start: the board is furious. Win now or else.")
        if delta:
            return self._apply_delta(delta, today_iso, channel="crisis")
        return 0

    def apply_press_board_effect(self, total: int, today_iso: str = "") -> int:
        """Route press-conference board effects through the monthly cap so a
        bad month plus a bad presser can't stack into a spiral."""
        return self._apply_delta(total, today_iso, channel="press")

    def record_big_event(self, kind: str) -> int:
        """Off-ice events: 'good_trade', 'bad_trade', 'star_signing',
        'star_leaves', 'scandal'."""
        deltas = {
            "good_trade": 4, "bad_trade": -5, "star_signing": 6,
            "star_leaves": -7, "scandal": -10,
        }
        delta = deltas.get(kind, 0)
        if kind == "scandal":
            self._disaster = True  # no honeymoon for this
        if delta:
            self._apply_delta(delta, "", channel="big_event")
        return delta

    def _sack_threshold(self) -> int:
        """D2 (2026-09-30): the board's sack line follows the club's
        expectation -- a win-now board loses patience while confidence is
        still positive; a rebuild board only acts at rock bottom."""
        exp = self.expectation or "playoffs"
        try:
            return int(EXPECTATIONS.get(exp, {}).get(
                "min_confidence_for_sack", 0))
        except (TypeError, ValueError):
            return 0

    def _check_sack(self):
        # Respect the user's "GM can be sacked" setting. If disabled,
        # confidence floors just above the sack line (job safe, but
        # budgets/morale still suffer).
        threshold = self._sack_threshold()
        if not self.can_be_sacked:
            if self.confidence <= threshold:
                self.confidence = threshold + 1
            return
        # First-year honeymoon: owners don't rotate GMs after one bumpy
        # season — unless it's a genuine disaster (scandal, catastrophic skid).
        if self.season_number == 1 and not self._disaster:
            if self.confidence <= threshold:
                self.confidence = threshold + 1
            return
        if self.confidence <= threshold and not self.sacked:
            self.sacked = True

    # -- reviews ----------------------------------------------------------
    @property
    def job_status(self) -> str:
        if self.sacked:
            return "Sacked"
        if self.confidence >= 70:
            return "Secure"
        if self.confidence >= 40:
            return "Stable"
        if self.confidence >= 20:
            return "Under Pressure"
        return "In Danger"

    def current_consequences(self) -> List[str]:
        """Concrete teeth: what low confidence costs the GM right now.

        Used by the Manager Hub to show stakes, and by main.py to apply
        budget/morale effects. Empty list = no consequences (Secure).
        """
        out = []
        c = self.confidence
        if self.sacked:
            return ["You have been sacked."]
        if c < 20:
            out.append("Transfer budget frozen — board will not approve spending.")
            out.append("Players are unsettled: morale dips across the roster.")
            out.append("Media pressure is intense; every loss is a crisis.")
            if self.can_be_sacked:
                out.append("ONE more bad stretch and the board will act.")
        elif c < 40:
            out.append("Transfer budget cut by 25% — the board is watching the money.")
            out.append("Star players are questioning the project.")
        elif c < 70:
            out.append("The board expects improvement; no new spending without approval.")
        return out

    def monthly_review(self, points_pct: float,
                       today_iso: str = "") -> Tuple[str, str]:
        """The board's real channel: a monthly review against bands set by
        the club's expectation — a rebuild board judges development, not the
        standings. Negatives run through the patience model and the monthly
        anti-pile-on cap."""
        exp = self.expectation or "playoffs"
        spec = MONTHLY_BANDS.get(exp, MONTHLY_BANDS["playoffs"])
        tone, delta = "alarmed", spec["alarmed"]
        for min_pct, t, d in spec["bands"]:
            if points_pct >= min_pct:
                tone, delta = t, d
                break
        if delta < 0:
            delta = self._dampen_negative(delta, today_iso)
        applied = self._apply_delta(delta, today_iso, channel="monthly")
        # If the cap absorbed part of it, say so honestly.
        absorbed = delta - applied
        self._check_sack()
        label = EXPECTATIONS.get(exp, {}).get("label", exp)
        headline = f"Board review: {tone.capitalize()} with progress"
        body = (
            f"The board is {tone} with the team's direction. "
            f"Expectation: {label}. Current points percentage: {points_pct:.1%}. "
            f"Board confidence is now {self.confidence}/100 ({self.job_status})."
        )
        if absorbed < 0:
            body += (" The board is already accounting for this stretch — "
                     "it won't punish you twice for the same run of results.")
        self.last_review = body
        return headline, body

    def request_patience(self, today_iso: str) -> Tuple[bool, str, str]:
        """Ask the owner for time. A GM-initiated meeting when the walls are
        closing in.

        Granted: +3 confidence, negatives halved for 60 days, the room settles.
        Refused: -4, and the next two months' negatives sting 25% more — you
        spent your political capital and kept losing.
        One ask per 120 days; only when confidence is under 55.
        """
        arch = OwnerProfile.ARCHETYPES[self.owner.archetype]
        if self.confidence >= 55:
            return (False, "No meeting needed",
                    "The board is content enough — no need to ask for patience "
                    "while things are stable.")
        if self._on_or_after(today_iso, self.patience_cooldown_until):
            return (False, "Too soon",
                    "You only just asked. Give it time before going back — "
                    f"not before {self.patience_cooldown_until}.")
        import random as _r
        chance = self.owner.base_grant
        if self.season_number == 1:
            chance += 0.10            # new GM, inherited situation
        if self.inherited_rebuild:
            chance += 0.05
        chance -= 0.15 * self.patience_refusals
        chance = max(0.05, min(0.95, chance))
        self.patience_cooldown_until = self._add_days(today_iso, 120)
        if _r.random() < chance:
            self.patience_until = self._add_days(today_iso, 60)
            self._apply_delta(3, today_iso, channel="patience")
            headline = "The owner backs you — publicly"
            body = (arch["grant_line"] + " For the next 60 days the board "
                    "will judge the trend, not the week. The dressing room "
                    "settles knowing the manager is safe.")
            return (True, headline, body)
        self.patience_refusals += 1
        self.refusal_hangover_until = self._add_days(today_iso, 60)
        self._apply_delta(-4, today_iso, channel="patience")
        headline = "The owner refuses to wait"
        body = (arch["refuse_line"] + " The refusal is public. For the next "
                "60 days every setback will sting more — you asked for time "
                "and the answer was no.")
        return (False, headline, body)

    def patience_status(self, today_iso: str = "") -> str:
        """One-liner for the Manager Hub."""
        if self._on_or_after(today_iso, self.patience_until):
            return f"Owner backing active until {self.patience_until}."
        if self._on_or_after(today_iso, self.patience_cooldown_until):
            return ("Patience already requested — next ask available after "
                    f"{self.patience_cooldown_until}.")
        if self.confidence < 55:
            return "You can request a meeting with the owner."
        return ""

    def season_review(self, made_playoffs: bool, playoff_rounds_won: int,
                      won_cup: bool) -> Tuple[str, str, int]:
        """End-of-season review. Returns (headline, body, confidence_delta)."""
        exp = self.expectation or "playoffs"
        met = (
            (exp == "win_cup" and won_cup)
            or (exp == "contend" and playoff_rounds_won >= 2)
            or (exp == "playoffs" and made_playoffs)
            or (exp == "rebuild")
        )
        delta = 15 if met else -20
        if won_cup:
            delta = max(delta, 20)
            self.recent_cups = min(2, self.recent_cups + 1)
        if delta < 0:
            # Patience applies at season's end too — a year-one GM who missed
            # with a rebuild roster doesn't eat the full -20.
            delta = self._dampen_negative(delta)
        self._apply_delta(delta, "", channel="season")
        headline = ("Board delighted: expectations met"
                    if met else "Board disappointed: expectations missed")
        body = (
            f"Season review complete. Expectation was '{EXPECTATIONS[exp]['label']}'. "
            f"{'You met it. ' if met else 'You fell short. '}"
            f"Board confidence is now {self.confidence}/100 ({self.job_status})."
        )
        # Roll the clock: patience is finite. Each missed year erodes it;
        # meeting expectations rebuilds a little. Owners don't rotate GMs
        # yearly, but they don't wait forever either.
        self.season_number += 1
        if met:
            self.patience_factor = min(1.8, self.patience_factor + 0.1)
        else:
            self.patience_factor = max(0.7, self.patience_factor - 0.15)
        if self.recent_cups and not won_cup:
            self.recent_cups = max(0, self.recent_cups - 1)  # goodwill decays
        # Reset season counters
        self.season_wins = self.season_losses = self.season_otl = 0
        self.streak = 0
        self.warnings_given = 0
        self.disaster_start_flagged = False
        self._disaster = False
        return headline, body, delta

    # -- persistence ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "expectation": self.expectation,
            "confidence": self.confidence,
            "season_wins": self.season_wins,
            "season_losses": self.season_losses,
            "season_otl": self.season_otl,
            "last_review": self.last_review,
            "warnings_given": self.warnings_given,
            "sacked": self.sacked,
            "season_number": self.season_number,
            "streak": self.streak,
            "patience_factor": self.patience_factor,
            "owner": self.owner.to_dict(),
            "inherited_rebuild": self.inherited_rebuild,
            "roster_youth": self.roster_youth,
            "recent_cups": self.recent_cups,
            "patience_until": self.patience_until,
            "patience_cooldown_until": self.patience_cooldown_until,
            "refusal_hangover_until": self.refusal_hangover_until,
            "patience_refusals": self.patience_refusals,
            "disaster_start_flagged": self.disaster_start_flagged,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoardSystem":
        b = cls()
        for k, v in (data or {}).items():
            if k == "owner":
                b.owner = OwnerProfile.from_dict(v)
            elif hasattr(b, k):
                setattr(b, k, v)
        # Migration: a sack issued under the pre-retune model must not stand
        # into a year-1 career -- under the new honeymoon rule a bumpy first
        # season (no disaster) floors confidence at 1 instead of ending the
        # career. Clear the stale flag so old saves continue correctly.
        if b.season_number == 1 and not b._disaster and b.sacked:
            b.sacked = False
            b.confidence = max(1, b.confidence)
        return b


# ---------------------------------------------------------------------------
# Player happiness, squad status & private chats
# ---------------------------------------------------------------------------

SQUAD_STATUSES = [
    "Star Player", "Key Player", "Regular Starter",
    "Rotation", "Prospect", "Surplus",
]

# Expected share of team games played for each status
STATUS_EXPECTED_SHARE = {
    "Star Player": 0.95,
    "Key Player": 0.85,
    "Regular Starter": 0.70,
    "Rotation": 0.40,
    "Prospect": 0.15,
    "Surplus": 0.05,
}

PERSONALITIES = [
    "Driven", "Professional", "Laid-back", "Volatile", "Loyal", "Ambitious",
]


def get_player_personality(player) -> str:
    """Stable personality derived from player id (no extra storage needed)."""
    pid = getattr(player, "id", 0) or 0
    return PERSONALITIES[pid % len(PERSONALITIES)]


def morale_label(morale: int) -> str:
    if morale >= 85:
        return "Superb"
    if morale >= 65:
        return "Good"
    if morale >= 45:
        return "Okay"
    if morale >= 25:
        return "Poor"
    return "Abysmal"


def happiness_label(happiness: int) -> str:
    if happiness >= 80:
        return "Delighted"
    if happiness >= 60:
        return "Happy"
    if happiness >= 40:
        return "Content"
    if happiness >= 25:
        return "Unhappy"
    return "Very unhappy"


# ---------------------------------------------------------------------------
# Wave C (D37): the market matters. A star is not equally happy in a
# hockey-mad fishbowl and a desert -- and a homesick kid far from home
# isn't equally happy anywhere. Market fit feeds happiness weekly, on top
# of ice time / personality / promises (which were the whole story before).
# ---------------------------------------------------------------------------

_TEAM_CITIES = {
    "Boston Bruins": "Boston", "Buffalo Sabres": "Buffalo",
    "Detroit Red Wings": "Detroit", "Florida Panthers": "Sunrise",
    "Montréal Canadiens": "Montréal", "Ottawa Senators": "Ottawa",
    "Tampa Bay Lightning": "Tampa", "Toronto Maple Leafs": "Toronto",
    "Carolina Hurricanes": "Raleigh", "Columbus Blue Jackets": "Columbus",
    "New Jersey Devils": "Newark", "New York Islanders": "New York",
    "New York Rangers": "New York", "Philadelphia Flyers": "Philadelphia",
    "Pittsburgh Penguins": "Pittsburgh", "Washington Capitals": "Washington",
    "Chicago Blackhawks": "Chicago", "Colorado Avalanche": "Denver",
    "Dallas Stars": "Dallas", "Minnesota Wild": "Saint Paul",
    "Nashville Predators": "Nashville", "St. Louis Blues": "St. Louis",
    "Utah Hockey Club": "Salt Lake City", "Winnipeg Jets": "Winnipeg",
    "Anaheim Ducks": "Anaheim", "Calgary Flames": "Calgary",
    "Edmonton Oilers": "Edmonton", "Los Angeles Kings": "Los Angeles",
    "San Jose Sharks": "San Jose", "Seattle Kraken": "Seattle",
    "Vancouver Canucks": "Vancouver", "Vegas Golden Knights": "Las Vegas",
}

_NA_COUNTRIES = {"canada", "united states", "usa", "u.s.a.", "mexico"}
_EUROPE_COUNTRIES = {
    "russia", "sweden", "finland", "czech republic", "czechia", "slovakia",
    "germany", "switzerland", "latvia", "denmark", "norway", "belarus",
    "ukraine", "kazakhstan", "austria", "slovenia", "france", "italy",
    "united kingdom", "england", "netherlands", "poland", "hungary",
}


def _market_city(team_name: str) -> str:
    try:
        name = str(team_name or "")
        if name in _TEAM_CITIES:
            return _TEAM_CITIES[name]
        parts = name.rsplit(" ", 1)
        return parts[0] if len(parts) == 2 else name
    except Exception:
        return ""


def _birth_city(birthplace: str) -> str:
    try:
        return str(birthplace or "").split(",")[0].strip()
    except Exception:
        return ""


def _continent(country: str) -> str:
    try:
        c = str(country or "").strip().lower()
        if c in _NA_COUNTRIES:
            return "NA"
        if c in _EUROPE_COUNTRIES:
            return "EU"
        return "other" if c else "NA"
    except Exception:
        return "NA"


def market_happiness_delta(player, team) -> Tuple[int, str]:
    """Weekly happiness delta from market fit (D37). Returns (delta, reason).

    Homesickness (birthplace vs team city/country/continent), cushioned by
    clique membership, tenure, winning, and loyal/patient markets; fishbowl
    pressure (high intensity + adversarial) on struggling players; a stage
    boost for thriving stars. Bounded [-6, +5]. Never raises.
    """
    try:
        if team is None or player is None:
            return (0, "")
        team_name = getattr(team, "team_name", "") or ""
        city = _market_city(team_name)
        home_city = _birth_city(getattr(player, "birthplace", "") or "")
        nationality = getattr(player, "nationality", "") or ""
        morale = getattr(player, "morale", 70) or 70
        gp = getattr(player, "games_played", 0) or 0

        delta = 0
        reasons = []

        # --- homesickness: distance from home ------------------------------
        if home_city and home_city.lower() == city.lower():
            delta += 2
            reasons.append("playing at home")
        else:
            home_cont = _continent(nationality)
            team_cont = "NA"  # all 32 clubs are North American
            if home_cont == "NA":
                home_base = 0
            elif home_cont == "EU":
                home_base = -3
            else:
                home_base = -2
            if home_base < 0:
                delta += home_base
                reasons.append("far from home")

        # --- cushions -------------------------------------------------------
        homesick = delta < 0
        if homesick:
            try:
                clique_of = importlib.import_module("dressing_room").clique_of
                if clique_of(team, player) is not None:
                    delta += 2
                    reasons.append("his clique looks after him")
            except Exception:
                pass
        if gp >= 150:
            delta += 2
            if homesick:
                reasons.append("settled in now")
        elif gp >= 60:
            delta += 1
        try:
            wins = float(getattr(team, "wins", 0) or 0)
            losses = float(getattr(team, "losses", 0) or 0)
            otl = float(getattr(team, "ot_losses", 0) or 0)
            games = wins + losses + otl
            if games > 5:
                wpct = (wins + 0.5 * otl) / games
                if wpct > 0.550:
                    delta += 1
                elif wpct < 0.450:
                    delta -= 1
                    if homesick:
                        reasons.append("losing far from home stings")
        except Exception:
            pass

        # --- the market's character -----------------------------------------
        intensity = adversarial = loyalty = patience = None
        try:
            from media_engine import MARKET_PROFILES
            prof = MARKET_PROFILES.get(team_name)
            if prof:
                intensity, adversarial, loyalty, patience = prof
        except Exception:
            pass
        personality = get_player_personality(player)
        if intensity is not None and intensity >= 80 \
                and (adversarial or 0) >= 60:
            # fishbowl: Toronto, Montréal, Philly, New York...
            if morale < 45:
                delta -= 2
                reasons.append("the fishbowl is eating him alive")
                if personality == "Volatile":
                    delta -= 1
                    reasons.append("clashing with the media")
            elif morale >= 75:
                delta += 1
                reasons.append("loves the big stage")
            elif personality == "Laid-back":
                delta += 1  # shrugs the papers off
        if homesick and loyalty is not None and loyalty >= 68 \
                and (patience or 0) >= 68:
            delta += 1
            reasons.append("the fans embraced him")

        delta = max(-6, min(5, int(round(delta))))
        reason = "; ".join(reasons[:2])
        return (delta, reason)
    except Exception:
        return (0, "")


def update_player_happiness(player, team_games_played: int,
                            team=None) -> List[str]:
    """Weekly happiness update. Returns noteworthy event strings."""
    events = []
    # BUG-030: the base player.games_played attribute is a stale legacy
    # field (always 0) -- live games live on player.stats.games_played.
    # Reading the stale field made actual_share 0 for everyone, so the
    # whole roster accumulated max playing-time concern and hit happiness
    # 0 -> mass transfer requests on a 1st-place team.
    try:
        _st = getattr(player, 'stats', None)
        gp = int(getattr(_st, 'games_played', 0) or 0)
    except Exception:
        gp = 0
    if not gp:
        try:
            gp = int(getattr(player, "games_played", 0) or 0)
        except Exception:
            gp = 0
    status = getattr(player, "squad_status", "Rotation") or "Rotation"
    expected = STATUS_EXPECTED_SHARE.get(status, 0.4)
    happiness = getattr(player, "happiness", 70) or 70
    concern = getattr(player, "playing_time_concern", 0) or 0

    if team_games_played > 0:
        actual_share = gp / team_games_played
        shortfall = expected - actual_share
        if shortfall > 0.25:
            concern = min(100, concern + 12)
            happiness = max(0, happiness - 8)
        elif shortfall > 0.10:
            concern = min(100, concern + 5)
            happiness = max(0, happiness - 3)
        elif shortfall < -0.05:
            # Playing more than expected: small boost
            concern = max(0, concern - 8)
            happiness = min(100, happiness + 2)

    # Personality drift
    personality = get_player_personality(player)
    if personality == "Volatile":
        happiness = max(0, min(100, happiness + random.randint(-6, 4)))
    elif personality == "Laid-back":
        happiness = max(0, min(100, happiness + random.randint(-2, 2)))
    elif personality == "Loyal":
        concern = max(0, concern - 2)

    # Promise tracking
    promise = getattr(player, "promise_made", "") or ""
    if promise == "more_icetime" and team_games_played > 0:
        recent_share = gp / team_games_played
        if recent_share >= expected * 0.8:
            promise = ""
            happiness = min(100, happiness + 10)
            events.append(f"{player.first_name} {player.last_name} is pleased you kept your playing-time promise.")

    # Market fit (Wave C D37): the market a player lives in moves
    # happiness -- homesickness, fishbowl pressure, the big stage.
    if team is not None:
        _mdelta, _mreason = market_happiness_delta(player, team)
        if _mdelta:
            happiness = max(0, min(100, happiness + _mdelta))
            if abs(_mdelta) >= 3 and _mreason:
                events.append(
                    f"{player.first_name} {player.last_name}: market fit "
                    f"({'+' if _mdelta > 0 else ''}{_mdelta}) -- {_mreason}.")

    # Transfer request trigger
    if happiness < 25 and concern > 70 and not getattr(player, "transfer_requested", False):
        player.transfer_requested = True
        events.append(f"TRANSFER REQUEST: {player.first_name} {player.last_name} has asked to leave the club.")

    # Morale follows happiness loosely (both 1-100)
    morale = getattr(player, "morale", 70) or 70
    if happiness >= 70 and morale < 100:
        player.morale = min(100, morale + 5)
    elif happiness < 30 and morale > 1:
        player.morale = max(1, morale - 5)

    player.happiness = happiness
    player.playing_time_concern = concern
    player.promise_made = promise
    return events


def check_squad_concerns(team) -> List[Tuple]:
    """Return [(player, concern_text)] for players needing attention."""
    concerns = []
    for p in getattr(team, "roster", []) or []:
        happiness = getattr(p, "happiness", 70) or 70
        concern = getattr(p, "playing_time_concern", 0) or 0
        if getattr(p, "transfer_requested", False):
            concerns.append((p, f"{p.first_name} {p.last_name} has requested a transfer and is refusing to back down."))
        elif concern >= 60:
            concerns.append((p, f"{p.first_name} {p.last_name} ({getattr(p, 'squad_status', 'Rotation')}) is concerned about his lack of playing time."))
        elif happiness <= 30:
            concerns.append((p, f"{p.first_name} {p.last_name} is unhappy. His agent hints he may seek a move."))
    return concerns


CHAT_ACTIONS = {
    "praise": {
        "label": "Praise his recent form",
        "desc": "Boosts morale and happiness. Works best when the player is performing.",
    },
    "criticize": {
        "label": "Criticize his performances",
        "desc": "Risky: may motivate driven players but anger others.",
    },
    "promise_icetime": {
        "label": "Promise more playing time",
        "desc": "Calms playing-time concerns, but you must deliver.",
    },
    "reassure_future": {
        "label": "Reassure him about his future",
        "desc": "Small happiness boost. Safe option.",
    },
    "discipline": {
        "label": "Discipline for poor attitude",
        "desc": "For very unhappy players. May backfire with volatile personalities.",
    },
    "discuss_transfer": {
        "label": "Discuss his transfer request",
        "desc": "Try to convince him to stay.",
    },
}


def chat_with_player(player, action: str, today=None) -> Tuple[str, Dict[str, int]]:
    """Apply a private chat action. Returns (result_text, effects_dict).

    Anti-farming: a player who's been chatted with in the last 3 days
    tunes out -- "we just talked." Repeated praise goes stale fast.
    """
    import datetime as _dt
    personality = get_player_personality(player)
    happiness = getattr(player, "happiness", 70) or 70
    morale = getattr(player, "morale", 70) or 70
    name = f"{player.first_name} {player.last_name}"
    effects = {"happiness": 0, "morale": 0, "concern": 0}

    # --- chat-fatigue: same player, recent chat -> diminished ----------
    try:
        if today is None:
            today = _dt.date.today()
        elif isinstance(today, str):
            today = _dt.date.fromisoformat(today[:10])
        _last = getattr(player, "_last_chat_date", None)
        if isinstance(_last, str):
            _last = _dt.date.fromisoformat(_last[:10])
        stale = (isinstance(_last, _dt.date)
                 and (today - _last).days < 3)
    except Exception:
        stale = False
    try:
        player._last_chat_date = today
    except Exception:
        pass
    if stale:
        return (f"{name} shrugged -- \"We just talked, coach.\" "
                f"(Private chats lose their punch when repeated.)"), effects

    if action == "praise":
        dh, dm = 8, 5
        if personality == "Driven":
            dh, dm = 12, 10
        text = f"{name} appreciated the praise and looks motivated."
    elif action == "criticize":
        if personality in ("Driven", "Professional"):
            dh, dm = -4, 5
            text = f"{name} took the criticism on the chin and vows to respond on the ice."
        else:
            dh, dm = -12, -10
            text = f"{name} reacted badly to the criticism. His agent called to complain."
    elif action == "promise_icetime":
        player.promise_made = "more_icetime"
        dh, dm, dc = 10, 5, -25
        effects["concern"] = dc
        text = f"You promised {name} more ice time. He'll be watching your line selections."
        player.happiness = max(0, min(100, happiness + dh))
        player.morale = max(1, min(100, morale + dm))
        player.playing_time_concern = max(0, (getattr(player, "playing_time_concern", 0) or 0) + dc)
        return text, {"happiness": dh, "morale": dm, "concern": dc}
    elif action == "reassure_future":
        dh, dm = 5, 5
        text = f"{name} seemed reassured by your words."
    elif action == "discipline":
        if personality == "Volatile":
            dh, dm = -15, -10
            text = f"{name} exploded at the discipline. This could get ugly."
        else:
            dh, dm, dc = -5, 0, -15
            effects["concern"] = dc
            text = f"{name} accepted the discipline sullenly."
    elif action == "discuss_transfer":
        if personality in ("Loyal", "Professional") and happiness >= 35:
            player.transfer_requested = False
            dh, dm = 10, 1
            text = f"Your talk worked — {name} has withdrawn his transfer request."
        else:
            dh, dm = -8, -1
            text = f"{name} isn't listening. He still wants out."
    else:
        return "Nothing was said.", effects

    effects["happiness"] = dh
    effects["morale"] = dm
    player.happiness = max(0, min(100, happiness + dh))
    player.morale = max(1, min(100, morale + dm))
    if effects["concern"]:
        player.playing_time_concern = max(0, (getattr(player, "playing_time_concern", 0) or 0) + effects["concern"])
    return text, effects


# ---------------------------------------------------------------------------
# Press conferences
# ---------------------------------------------------------------------------

# Each answer: (label, tone, morale_effect, board_effect, fan_effect, media_reaction)
PREMATCH_QUESTIONS = [
    {
        "id": "form",
        "ask": "Your team's form has been {form_word} lately. Are you confident going into this one?",
        "answers": [
            ("Very confident — we'll win", "confident", 1, 0, 2,
             "The press loves the confidence. Players feel backed."),
            ("We take it one game at a time", "calm", 0, 1, 0,
             "A measured response. The board appreciates the professionalism."),
            ("We need to be much better", "honest", -1, 0, -1,
             "Honest but gloomy. Some players took it personally."),
        ],
    },
    {
        "id": "opponent",
        # F-3: opp_word is high/medium/low -- the bare "{opp_word}" read
        # "Edmonton are high this season". Rewritten to the
        # "{opp_word}-danger" pattern used by specialteams/scoring.
        "ask": "{opp} are a {opp_word}-danger team this season. How do you rate them?",
        "answers": [
            ("They're a top side, we respect them", "respectful", 0, 1, 1,
             "Classy. No bulletin-board material for the opponent."),
            ("We're better than them, simple as that", "confident", 1, -1, 2,
             "Bold! The fans love it, but the board winces at the arrogance."),
            ("No comment on the opposition", "defensive", 0, 0, -1,
             "Terse. Journalists grumble about your media manner."),
        ],
    },
    {
        "id": "pressure",
        # F-5: this used to fire on ANY form -- including "excellent",
        # asking if your job is under threat after a great run. Same
        # when-guard treatment as 'scoring': only fires on poor form.
        "when": lambda ctx: (ctx or {}).get("form_word") == "poor",
        "ask": "There's pressure on you after recent results. Is your job under threat?",
        "answers": [
            ("I have the full backing of the board", "calm", 0, 2, 1,
             "The board liked hearing that. Whether it's true is another matter."),
            ("I don't listen to the noise", "defensive", 1, -1, 0,
             "Defiant. The dressing room respects the siege mentality."),
            ("Every manager is under pressure", "honest", 0, 0, 0,
             "A shrug. Nobody learned anything."),
        ],
    },
    {
        "id": "injuries",
        "ask": "Any team news? Are the injured players close to returning?",
        "answers": [
            ("The squad is in great shape", "confident", 1, 0, 1,
             "Positive vibes around the camp."),
            ("We're managing a few knocks", "honest", 0, 0, 0,
             "Straightforward injury update."),
            ("I'd rather not discuss injuries", "defensive", -1, 0, -1,
             "Cagey. Fans speculate the worst."),
        ],
    },
    {
        "id": "youth",
        "ask": "Will we see any young players given a chance soon?",
        "answers": [
            ("If they're good enough, they'll play", "confident", 1, 1, 2,
             "The drafted prospects are buzzing."),
            ("They need to earn it in practice", "calm", 0, 1, 0,
             "Sensible. Nobody is upset."),
            ("We're not a development charity", "defensive", -2, 0, -2,
             "Harsh. Young players were hurt by that."),
        ],
    },
    {
        "id": "netminder",
        # DEV-B4: reworded premise-safe -- no assertion about crease
        # controversy or form (that state isn't in the prematch ctx).
        "ask": "The crease is always under the microscope. Who starts in goal against {opp} tonight?",
        "answers": [
            ("We're riding the hot hand", "confident", 1, 0, 1,
             "The starter hears the vote of confidence loud and clear."),
            ("We'll keep them guessing", "evasive", 0, 0, 0,
             "Nobody learns anything. Both goalies stay on edge."),
            ("Whoever earns it in warmup", "calm", 0, 1, 0,
             "Meritocracy. The board likes the accountability."),
        ],
    },
    {
        "id": "specialteams",
        # DEV-B4: gated on real state -- danger_level is computed from the
        # opponent's offense+goaltending (generate_opposition_report), so
        # only a "high"-danger side enters this pool.
        # DEV-B5: reworded -- the guard measures overall danger, not the
        # power play specifically, so the ask no longer asserts a "lethal
        # power play". Keeps the special-teams/discipline topical frame the
        # answers need.
        "when": lambda ctx: (ctx or {}).get("opp_word") == "high",
        "ask": "Facing a {opp_word}-danger {opp} team, how do you keep the special-teams battle from swinging it?",
        "answers": [
            ("Discipline wins hockey games", "calm", 1, 1, 0,
             "The room nods. Simple message, well received."),
            ("Let them take penalties too -- we'll match them", "passionate", 1, -1, 1,
             "Fire and brimstone. The fans are buzzing, the board less so."),
            ("Our PK can handle anything", "confident", 1, 0, 1,
             "Bold. The penalty killers stand a little taller."),
        ],
    },
    {
        "id": "matchup",
        # F-4: form_word is excellent/decent/poor/mixed -- the bare
        # "With the team {form_word}" rendered "With the team excellent".
        "ask": "They'll try to dictate the matchups. With the team's form {form_word}, how do you respond against {opp}?",
        "answers": [
            ("We roll four lines regardless", "confident", 1, 0, 1,
             "The depth players love hearing that."),
            ("We'll take the matchups we want, wherever we play", "calm", 0, 1, 0,
             "Tactical. The assistants get to work."),
            ("Match their best with our best, all night", "passionate", 1, 0, 1,
             "Old school. The top line is fired up."),
        ],
    },
    {
        "id": "captaincy",
        # DEV-B4: reworded premise-safe -- the prematch ctx carries no
        # captain-production state, so the ask no longer asserts he has
        # been quiet.
        # REV-A3/F-4: "with the club playing {form_word}" rendered
        # "with the club playing poor" -- adjective where an adverb is
        # needed. Reworked to "in {form_word} form", grammatical for all
        # form_word values (excellent/decent/poor/mixed).
        "ask": "What do you need from your leaders against {opp} with the club in {form_word} form?",
        "answers": [
            ("They lead in ways you don't always see", "defensive", 1, 0, 0,
             "The captain appreciates the shield."),
            ("Every leader needs to step up", "honest", 0, 1, 1,
             "A challenge laid down. The room heard it."),
            ("They'll answer on the ice", "confident", 1, 0, 1,
             "Faith shown publicly. The fans like the loyalty."),
        ],
    },
    {
        "id": "physicality",
        # DEV-B4: reworded premise-safe -- per-facet opponent physicality
        # isn't in the prematch ctx, so the ask no longer asserts {opp}
        # play a heavy game.
        "ask": "How do you handle the physical battle against {opp} tonight?",
        "answers": [
            ("We're not backing down from anyone", "passionate", 1, -1, 2,
             "The building will be rocking. The board worries about the fines."),
            ("We play our game, not theirs", "calm", 1, 1, 0,
             "Composed. The veterans approve."),
            ("We can play heavy too", "confident", 1, 0, 1,
             "The fourth line is grinning."),
        ],
    },
    {
        "id": "schedule",
        # DEV-B4: reworded premise-safe -- the prematch ctx carries no
        # schedule-demand state, so the ask no longer asserts a demanding
        # schedule. Keeps the real form_word premise.
        # DEV-B5: dropped the "demanding schedule" assertion (untracked in
        # the prematch ctx); ask is now form-only.
        # F-4: "The form's been {form_word}" was clumsy phrasing.
        "ask": "The team's form has been {form_word}. How do you manage the energy against {opp}?",
        "answers": [
            ("Short shifts, smart changes", "calm", 1, 1, 0,
             "Sports science approves. So does the board."),
            ("Adrenaline takes care of it", "confident", 1, 0, 1,
             "The room feeds off the energy."),
            ("No excuses -- everyone plays", "demanding", 0, 0, -1,
             "Tough love. A few veterans exchange glances."),
        ],
    },
    {
        "id": "rookie",
        # DEV-B4: reworded premise-safe -- no assertion that a prospect is
        # knocking; the question is now hypothetical, which the answers
        # already were.
        # REV-A3/F-3: "in town" asserted a home game but the prematch ctx
        # carries no home/away state -- dropped so the ask is venue-neutral.
        "ask": "When does a prospect get his chance? With a {opp_word}-danger {opp} on the schedule, could it be tonight?",
        "answers": [
            ("If he's ready, he plays", "confident", 1, 1, 1,
             "The kids in the system are buzzing."),
            ("Not against this opposition", "calm", 0, 0, -1,
             "Protective. The fans wanted to see the kid."),
            ("He'll get his chance soon", "calm", 0, 1, 0,
             "Patient. Nobody's upset."),
        ],
    },
    {
        "id": "blueline",
        "ask": "Your system asks a lot of the defense. Against a {opp_word}-danger {opp} team, does anything change?",
        "answers": [
            ("The system is the system", "confident", 1, 0, 0,
             "Belief. The defensemen stand taller."),
            ("We tighten up the gaps", "calm", 0, 1, 0,
             "Adjustment made. The coaches' room nods."),
            ("They'll have to earn every inch", "passionate", 1, 0, 1,
             "The D corps loves the backing."),
        ],
    },
    {
        "id": "faithful",
        # DEV-B4: reworded premise-safe -- the earlier "restless with the
        # team excellent" was ungrammatical.
        # DEV-B5: reworded premise-safe -- no home/away state in the
        # prematch ctx and poor form can mean quiet or booing fans, so the
        # ask no longer asserts the fans will be loud.
        # REV-A3/F-4: "with the club playing {form_word}" rendered
        # "with the club playing poor" -- reworked to "in {form_word} form".
        "ask": "What's your message to the fans before puck drop against {opp}, with the club in {form_word} form?",
        "answers": [
            ("Stick with us -- we'll give you a show", "passionate", 1, 0, 2,
             "The faithful roar their approval."),
            ("Judge us at the final horn", "calm", 0, 1, 1,
             "Measured. Most fans accept the deal."),
            ("They pay to see effort, and they'll get it", "honest", 1, 0, 1,
             "A promise made. The room knows the standard now."),
        ],
    },
    {
        "id": "rivalry",
        # DEV-B4: reworded premise-safe -- no rivalry state in the
        # prematch ctx, so not every opponent gets a rivalry edge.
        "ask": "Games against {opp} can carry an edge. With them a {opp_word}-danger side, how do you keep the emotions in check?",
        "answers": [
            ("Channel it, don't fight it", "calm", 1, 1, 0,
             "Sports psychology 101. The room buys in."),
            ("Emotion is fuel", "passionate", 1, -1, 2,
             "The barn will be shaking. The board holds its breath."),
            ("It's just two points", "honest", 0, 1, -1,
             "Cold water. Some fans wanted fire."),
        ],
    },
    {
        "id": "overtime",
        # DEV-B4: reworded premise-safe -- no assertion of frequent OT
        # nights (not tracked in the prematch ctx); answers were already
        # plans, which fit the new ask unchanged.
        "ask": "Overtime's always a possibility in a tight one. With the team's form {form_word}, what's the plan if it goes past sixty against {opp}?",
        "answers": [
            ("We finish it in regulation", "confident", 1, 0, 1,
             "Intent stated. The room likes the ambition."),
            ("We'll take the point and run", "calm", 0, 1, -1,
             "Pragmatic. The fans wanted more swagger."),
            ("Our 3-on-3 needs work, we know", "honest", 0, 1, 0,
             "Accountability. The skills coaches get to work."),
        ],
    },
    {
        "id": "rumors",
        # DEV-B4: reworded premise-safe -- there is deliberately no
        # recent-trade log to gate on (see _situational_postmatch), so the
        # ask no longer asserts chatter is swirling.
        "ask": "The rumor mill never sleeps. With a {opp_word}-danger {opp} tonight, how do you keep outside noise out of the room?",
        "answers": [
            ("The room is locked in", "confident", 1, 0, 1,
             "The players appreciate the public trust."),
            ("It's part of the business", "calm", 0, 1, 0,
             "Veteran answer. Nobody blinks."),
            ("I don't discuss rumors", "defensive", -1, 0, -1,
             "Terse. The rumor mill spins faster."),
        ],
    },
    {
        "id": "homeice",
        # DEV-B4: reworded premise-safe -- no home/away state in the
        # prematch ctx, so the ask no longer assumes home ice. Answers
        # were already crowd-general and fit unchanged.
        "ask": "How much can the crowd swing a night like this against {opp}?",
        "answers": [
            ("They're our seventh skater", "passionate", 1, 0, 2,
             "The fans will bring the noise now."),
            ("We have to give them something to cheer", "honest", 1, 0, 1,
             "A fair deal, and the room knows it."),
            ("It matters, but we win it on the ice", "calm", 0, 1, 0,
             "Grounded. The board nods."),
        ],
    },
    {
        "id": "scoring",
        # DEV-B4: gated on real state -- form_word comes from
        # _career_form_word() (excellent/decent/poor/mixed), so this
        # "goals are hard to come by" premise only enters the pool when
        # the form is genuinely poor.
        # DEV-B5: fixed grammar -- the old "while {form_word}" rendered
        # "while poor"; the form word now reads as a proper clause.
        "when": lambda ctx: (ctx or {}).get("form_word") == "poor",
        "ask": "Goals have been hard to come by while the form's been {form_word}. What's the fix against a {opp_word}-danger {opp} team?",
        "answers": [
            ("Get pucks to the net, crash the crease", "passionate", 1, 0, 1,
             "Simple hockey. The forwards nod."),
            ("Trust the process -- the chances are there", "calm", 0, 1, 0,
             "Patience. The analytics staff agrees."),
            ("We need our finishers to finish", "honest", 0, 0, 0,
             "A gentle prod at the top six."),
        ],
    },
    {
        "id": "veterans",
        # DEV-B4: reworded premise-safe -- no assertion that the veterans
        # have carried the load (not in the prematch ctx).
        # REV-A3/F-4: "With the club playing {form_word}" rendered
        # "With the club playing poor" -- reworked to "in {form_word} form".
        "ask": "Veterans set the standard. With the club in {form_word} form, do the young guys need to step up against {opp}?",
        "answers": [
            ("Everyone pulls the rope", "demanding", 1, 0, 0,
             "The kids heard that loud and clear."),
            ("The vets set the tone, kids follow", "calm", 1, 1, 0,
             "Hierarchy respected. The room is settled."),
            ("Our depth is a strength", "confident", 1, 0, 1,
             "The bottom six skates a little taller."),
        ],
    },
]

POSTMATCH_QUESTIONS_WIN = [
    {
        "id": "verdict",
        "ask": "A {score} win over {opp}. Your verdict?",
        "answers": [
            ("The players were magnificent", "confident", 2, 1, 2,
             "The dressing room is bouncing after that praise."),
            ("A good win, but we can improve", "calm", 0, 2, 1,
             "The board loves the standards you're setting."),
            ("We got lucky today", "honest", -1, -1, -1,
             "Nobody likes hearing the win dismissed."),
        ],
    },
    {
        "id": "star",
        # DEV-B4: reworded premise-safe -- pre-existing HEAD original;
        # the unguarded win bank can't assert any player was superb.
        "ask": "How did you rate {star}'s game in the {score} win over {opp}?",
        "answers": [
            ("He's world class, no doubt", "confident", 2, 0, 2,
             "{star} is thrilled. Teammates slightly less so."),
            ("It's a team game", "calm", 1, 1, 0,
             "Diplomatic. The squad appreciates it."),
            ("Let's not get carried away", "defensive", -1, 0, -1,
             "{star} looked stung by that."),
        ],
    },
    {
        "id": "comeback",
        "ask": "You found a way in the {score} win over {opp}. What was the difference?",
        "answers": [
            # DEV-B4: reaction rewritten premise-safe -- the reworded ask
            # deliberately stopped asserting a comeback.
            ("The room refused to lose", "passionate", 2, 0, 2,
             "The dressing room is bouncing. The fans are delirious."),
            ("We adjusted the forecheck", "calm", 1, 1, 0,
             "Coaching credit. The board notes the adjustments."),
            ("Sometimes you just need a bounce", "honest", 0, 0, 0,
             "A shrug and a smile. Nobody minds."),
        ],
    },
    {
        "id": "powerplay",
        "ask": "What was your read on the special teams battle in the {score} win over {opp}?",
        "answers": [
            ("Puck movement, pure and simple", "calm", 1, 1, 0,
             "The video coaches take a quiet bow."),
            ("Our guys are just better", "confident", 1, -1, 2,
             "Swagger. The fans love it; the board winces."),
            ("We've been working on the entries", "honest", 1, 1, 0,
             "Credit shared. The assistants appreciate it."),
        ],
    },
    {
        "id": "depth",
        "ask": "How big a role did roster depth play in the {score} win over {opp}?",
        "answers": [
            ("Deep enough to win in spring", "confident", 2, 1, 2,
             "Now that's a statement. The room believes it."),
            ("Everyone contributed tonight", "calm", 1, 1, 1,
             "The fourth line will remember this."),
            ("Let's see it again next game", "honest", 0, 1, 0,
             "Standards. The board loves the message."),
        ],
    },
    {
        "id": "goaltending",
        # DEV-B4: reworded premise-safe -- the unguarded win bank can't
        # assert a standout goalie game; ask and answers now assess the
        # goaltending without presuming it was heroic.
        "ask": "How did you assess the goaltending in the {score} win over {opp}?",
        "answers": [
            ("He was solid when it mattered", "honest", 2, 0, 1,
             "The goalie hears it. The skaters owe him dinner."),
            ("He gives us a chance every night", "calm", 1, 1, 1,
             "Steady praise. The crease is calm."),
            ("The shots he faced tell the real story", "defensive", 0, 0, -1,
             "Deflecting the question. The D corps shifts uncomfortably."),
        ],
    },
    {
        "id": "statement",
        # DEV-B4: reworded premise-safe -- not every win is a statement;
        # the question now floats it instead of asserting it.
        "ask": "The {score} win over {opp} -- is this a message to the rest of the league?",
        "answers": [
            ("Let them all take notice", "confident", 2, 0, 2,
             "Bulletin-board material league-wide. The fans are loud."),
            ("It's two points, nothing more", "calm", 0, 2, 0,
             "The board loves the even keel."),
            ("We're just getting started", "passionate", 2, 0, 2,
             "The room is bouncing off the walls."),
        ],
    },
    {
        "id": "topline",
        # DEV-B4: reworded premise-safe -- the unguarded win bank can't
        # assert the top line drove the win; the question now asks for a
        # rating instead.
        "ask": "How did you rate {star}'s line in the {score} win over {opp}?",
        "answers": [
            ("On their night, nobody touches them", "confident", 2, 0, 2,
             "{star} is beaming. The linemates too."),
            ("They did their job, shift after shift", "calm", 1, 1, 1,
             "Praise with perspective. Everyone's happy."),
            ("Plenty of great lines out there", "respectful", 0, 1, 0,
             "Classy. No extra motivation for opponents."),
        ],
    },
    {
        "id": "lockdown",
        "ask": "What was your read on the defensive side of the game in the {score} win over {opp}?",
        "answers": [
            ("Defense wins championships", "confident", 1, 1, 1,
             "The D corps puffs its chest."),
            ("It's how we're built", "calm", 1, 1, 0,
             "Identity embraced. The board approves."),
            ("We can score too, don't forget", "defensive", 0, 0, 0,
             "A reminder. The forwards smirk."),
        ],
    },
    {
        "id": "crowd_win",
        # DEV-B5: reworded premise-safe -- no home/away or attendance
        # state in the postmatch ctx, so the ask no longer asserts a loud
        # building or whose crowd it was; the first answer and the third
        # answer + reaction were reworded the same way.
        "ask": "How big a part did the atmosphere play in the {score} win over {opp}?",
        "answers": [
            ("The bench fed off it all night", "passionate", 1, 0, 2,
             "The whole bench is still buzzing."),
            ("It helps, but the players won it", "honest", 1, 0, 0,
             "Credit where due. The room nods."),
            ("Nothing beats a night like that", "confident", 1, 0, 2,
             "The noise never let up."),
        ],
    },
]

POSTMATCH_QUESTIONS_LOSS = [
    {
        "id": "verdict",
        "ask": "A {score} defeat to {opp}. What went wrong?",
        "answers": [
            ("I take full responsibility", "honest", 1, 2, 1,
             "The players respect a coach who shields them."),
            ("The players didn't show up", "defensive", -2, -1, -1,
             "The dressing room is furious at being thrown under the bus."),
            ("The officials were poor", "defensive", 0, -2, 1,
             "Fans agree, but the board hates excuses."),
        ],
    },
    {
        "id": "future",
        # DEV-B4: reworded premise-safe -- pre-existing HEAD original;
        # the losing-streak count is not computable in the builder (Team
        # tracks win_streak only; the caller hardcodes {n} as "a few"),
        # so the ask no longer asserts a count.
        "ask": "Where does the response start after the {score} defeat to {opp}?",
        "answers": [
            ("We'll turn it around, I promise", "confident", 1, 0, 1,
             "Fighting talk. The fans needed to hear it."),
            ("We need to work harder", "calm", 0, 1, 0,
             "Steady. Nobody panics."),
            ("Ask me after the next game", "defensive", -1, -1, -1,
             "Snappy. The vultures are circling."),
        ],
    },
    {
        "id": "slowstart",
        # DEV-B4: reworded premise-safe -- the unguarded loss bank can't
        # assert a slow start; the question now asks for a first-period
        # read instead.
        "ask": "What did you make of the first period in the {score} loss to {opp}?",
        "answers": [
            ("That's on me -- preparation starts with the coach", "honest", 1, 2, 1,
             "The room respects a coach who takes the heat."),
            ("We can be sharper from puck drop", "demanding", 0, 0, 0,
             "A challenge. Morning skate will be brisk."),
            ("The margins didn't go our way early", "defensive", -1, -1, 0,
             "Excuses. Nobody's buying it."),
        ],
    },
    {
        "id": "goalie_loss",
        # DEV-B4: reworded premise-safe -- no assertion about the quality
        # of the goals; the confidence answers fit the new ask unchanged
        # in stance.
        "ask": "The {score} loss to {opp} puts the spotlight on the crease. Do you still have faith in your goalie?",
        "answers": [
            ("Complete faith -- he's our guy", "confident", 2, 0, 1,
             "The goalie exhales. The crease is settled."),
            ("The group in front of him has to be better", "honest", 1, 1, 0,
             "The defense takes the message."),
            ("Everyone's job is under review", "defensive", -2, 0, -1,
             "Chilling. The whole room feels it."),
        ],
    },
    {
        "id": "powerplay_loss",
        "ask": "What was your read on the special teams battle in the {score} loss to {opp}?",
        "answers": [
            ("We're looking at everything", "calm", 0, 1, 0,
             "The assistants start drawing on whiteboards."),
            ("The chances are there -- stay the course", "confident", 1, 0, 0,
             "Patience. The top unit appreciates it."),
            ("Execution, not the system", "demanding", -1, 0, -1,
             "Blunt. The power-play quarterbacks feel the heat."),
        ],
    },
    {
        "id": "effort",
        # DEV-B4: reworded premise-safe -- the unguarded loss bank can't
        # assert the effort was flat; the question now asks for a compete
        # read instead.
        "ask": "What did you make of the compete level in the {score} loss to {opp}?",
        "answers": [
            ("The message is fine -- the response wasn't", "demanding", 0, 0, -1,
             "The room goes quiet. Point made."),
            ("I'll take responsibility for the energy", "honest", 1, 1, 1,
             "The players respect the accountability."),
            ("Every team has nights like this", "calm", 0, 0, 0,
             "Perspective. The veterans nod."),
        ],
    },
    {
        "id": "stars_quiet",
        "ask": "How did you assess your top line's performance in the {score} loss to {opp}?",
        "answers": [
            ("They'll answer -- they always do", "confident", 1, 0, 1,
             "Faith shown. The top line hears it."),
            ("We need more from everyone, not just them", "calm", 0, 1, 0,
             "Shared burden. The depth guys nod."),
            # DEV-B4: reworded premise-safe -- no longer presupposes a bad
            # top-line game; the coach now offers a reading, which fits the
            # neutral assessment question.
            ("The chances were there -- the finish wasn't", "honest", 0, 0, 0,
             "An honest read. The top line takes note."),
        ],
    },
    {
        "id": "discipline",
        # DEV-B4: reworded premise-safe -- penalty counts aren't in the
        # postmatch ctx, so the ask no longer asserts too many penalties.
        "ask": "How did you assess the discipline in the {score} loss to {opp}?",
        "answers": [
            ("It ends now -- that's a promise", "demanding", 1, 0, 1,
             "The repeat offenders feel the stare."),
            ("We play on the edge, sometimes it costs us", "honest", 0, 0, 1,
             "The fans love the edge. The board less so."),
            ("The calls didn't go our way", "defensive", -1, -1, 1,
             "The fans agree. The league office won't."),
        ],
    },
    {
        "id": "positives",
        "ask": "Any positives to take from the {score} loss to {opp}?",
        "answers": [
            ("The kids didn't look out of place", "calm", 1, 1, 1,
             "The young guys skate taller tomorrow."),
            ("We pushed until the final horn", "passionate", 1, 0, 1,
             "Heart recognized. The room appreciates it."),
            ("Honestly? Not many", "honest", -1, 0, -1,
             "Bleak. The mood dips further."),
        ],
    },
    {
        "id": "bounceback",
        # DEV-B4: reworded premise-safe -- the real losing-streak count is
        # not computable in the builder (Team tracks win_streak only; the
        # only signed streak lives on the career board, which the presser
        # builder never receives), so the ask no longer asserts a count
        # the caller hardcodes as "a few".
        "ask": "The {score} defeat to {opp} stings. Where does the turnaround start?",
        "answers": [
            ("In our own zone -- defend first", "calm", 1, 1, 0,
             "Back to basics. The D corps nods."),
            ("With me -- I need to be better", "honest", 1, 2, 1,
             "The room respects the accountability."),
            ("One shift at a time", "confident", 1, 0, 1,
             "Cliche, but the room buys in."),
        ],
    },
    {
        "id": "hook",
        # DEV-B4: answers rewritten premise-safe -- the neutral ask can't
        # assume a mid-game pull, so the pull-presuming answers are now
        # goalie-assessment answers true whether he was pulled or not.
        "ask": "How did you assess the goaltending in the {score} loss to {opp}?",
        "answers": [
            ("He battled -- the scoreboard doesn't tell the story", "calm", 0, 1, 0,
             "Measured. The goalie appreciates the shield."),
            ("Some nights the puck finds holes. We move on", "honest", 0, 0, 0,
             "Candor. The room moves on."),
            ("He's our guy -- full confidence for the next one", "confident", 1, 0, 1,
             "Loyalty. The goalie is grateful."),
        ],
    },
    {
        "id": "identity_loss",
        "ask": "The {score} loss to {opp} -- is this team losing its identity?",
        "answers": [
            ("Our identity is fine -- our execution isn't", "demanding", 1, 0, 0,
             "Sharp. The room takes note."),
            ("We're still finding out who we are", "honest", 0, 1, 0,
             "Patience. The board accepts the project."),
            ("No -- one loss doesn't define us", "confident", 1, 0, 1,
             "Perspective. The veterans steady the room."),
        ],
    },
]

# F-2: there are NO ties in the sim (STEP 0 verified 2026-10-11 --
# simulation.py: tied after regulation -> _handle_overtime(); still tied
# and not a playoff game -> _handle_shootout(); a marathon shootout still
# tied after 18 rounds is decided by a coin flip that always awards a goal
# and a winner (simulation.py:8240-8255); winner/loser is always assigned
# (simulation.py:2394-2395). record_result() tracks only W/OTL/L -- in
# parity_engine.record_result(home_won: bool), BoardSystem.record_result,
# and ManagerProfile.record_result alike. So the old
# POSTMATCH_QUESTIONS_DRAW bank's premise was FALSE 100% of the time:
# both live callers (game_manager.py:6497, main.py:20392) pass went_ot
# into the builder's "drew" parameter, so every OT win AND OT loss fired
# questions asserting a non-existent draw ("A 4-3 draw with Boston").
#
# Root-cause fix: the draw bank is gone. `drew` keeps its name (both
# callers pass positionally) but is now documented as the legacy name for
# went_ot. OT results get their own banks -- OT_WIN when won, OT_LOSS
# when not. No question may ever assert a draw again.
POSTMATCH_QUESTIONS_OT_WIN = [
    {
        "id": "verdict",
        "ask": "A {score} overtime win over {opp}. Your verdict?",
        "answers": [
            ("We deserved the two points", "confident", 1, 0, 1,
             "The players feel their effort was recognized."),
            ("A win is a win", "calm", 0, 1, 0,
             "Pragmatic. The board nods along."),
            ("We left it too late", "honest", -1, 0, -1,
             "Gloomy. The mood dips."),
        ],
    },
    {
        "id": "ot_point",
        "ask": "It took overtime to beat {opp} {score}. Happy with how you got there?",
        "answers": [
            ("We'll take the points and move on", "calm", 0, 1, 0,
             "Pragmatic. Nobody's thrilled, nobody's crushed."),
            ("We wanted it done in sixty -- no question", "honest", 1, 0, 1,
             "Ambition. The fans like the hunger."),
            ("Overtime is a coin flip -- we'll take it", "defensive", 0, 0, -1,
             "A shrug. The fans wanted more fire."),
        ],
    },
    {
        "id": "shootout",
        # DEV-B4 (carried over): OT can end 3-on-3 or in a shootout
        # (drama_events.py), so nothing may assume a shootout happened.
        "ask": "It went past regulation in the {score} win over {opp}. What did you make of the overtime?",
        "answers": [
            ("We stayed patient and it paid off", "honest", 0, 1, 0,
             "Accountability. The extra-time group puts in extra work."),
            ("We deserved to win it before the extra frame", "defensive", 0, 0, 1,
             "The fans agree loudly."),
            ("We'll be ready for the next one, however it ends", "confident", 1, 0, 1,
             "Faith. The skill guys feel backed."),
        ],
    },
    {
        "id": "late_lead",
        "ask": "The {score} overtime win over {opp} -- how close were you to finishing it in regulation?",
        "answers": [
            ("We should have put it away earlier", "honest", 1, 1, 0,
             "The room respects the accountability."),
            ("Tight games turn on small moments", "defensive", 0, 0, 0,
             "Hockey happens. The room moves on."),
            ("Two points is two points", "confident", 1, 0, 1,
             "Forward-looking. The fans buy in."),
        ],
    },
    {
        "id": "goalie_ot",
        # DEV-B4 (carried over): the bank can't assert the goalie kept the
        # team in it; ask and answers assess the goaltending without
        # presuming it was heroic.
        "ask": "How did you assess the goaltending in the {score} overtime win over {opp}?",
        "answers": [
            ("He gave us every chance to win it", "honest", 2, 0, 1,
             "The goalie hears it. The skaters feel it."),
            ("Steady all night -- exactly what we need", "calm", 1, 1, 1,
             "Steady praise for steady play."),
            ("We all need to be better in front of him", "demanding", 0, 0, 0,
             "The defense takes the message."),
        ],
    },
    {
        "id": "playoff_point",
        "ask": "Tight one with {opp}, {score}. Are these the points that decide playoff spots?",
        "answers": [
            ("Every point matters from here", "calm", 0, 1, 1,
             "The room understands the math."),
            ("We'll be playing past April", "confident", 1, 0, 2,
             "Bold. The fans are dreaming."),
            ("Too early for that talk", "defensive", 0, 0, -1,
             "Cautious. The fans wanted ambition."),
        ],
    },
]

POSTMATCH_QUESTIONS_OT_LOSS = [
    {
        "id": "verdict",
        "ask": "A {score} overtime defeat to {opp}. Your verdict?",
        "answers": [
            ("We deserved more", "confident", 1, 0, 1,
             "The players feel their effort was recognized."),
            ("A point is a point", "calm", 0, 1, 0,
             "Pragmatic. The board nods along."),
            ("Two points dropped", "honest", -1, 0, -1,
             "Gloomy. The mood dips."),
        ],
    },
    {
        "id": "ot_point",
        "ask": "A point from the {score} overtime loss to {opp}. Good enough?",
        "answers": [
            ("We'll take the point and move on", "calm", 0, 1, 0,
             "Pragmatic. Nobody's thrilled, nobody's crushed."),
            ("We wanted two -- no question", "honest", 1, 0, 1,
             "Ambition. The fans like the hunger."),
            ("Overtime is a coin flip", "defensive", 0, 0, -1,
             "A shrug. The fans wanted more fire."),
        ],
    },
    {
        "id": "shootout",
        # DEV-B4 (carried over): OT can end 3-on-3 or in a shootout
        # (drama_events.py), so nothing may assume a shootout happened.
        "ask": "It went past regulation in the {score} loss to {opp}. What did you make of the overtime?",
        "answers": [
            ("Overtime can go either way -- we have to be better at it", "honest", 0, 1, 0,
             "Accountability. The extra-time group puts in extra work."),
            ("We deserved better than a coin flip", "defensive", 0, 0, 1,
             "The fans agree loudly."),
            ("We'll be ready for the next one, however it ends", "confident", 1, 0, 1,
             "Faith. The skill guys feel backed."),
        ],
    },
    {
        "id": "late_lead",
        "ask": "The {score} overtime loss to {opp} -- how close were you to taking both points?",
        "answers": [
            ("We left points on the table tonight", "honest", 1, 1, 0,
             "The room respects the accountability."),
            ("Tight games turn on small moments", "defensive", 0, 0, 0,
             "Hockey happens. The room moves on."),
            ("We take the point and get back to work", "confident", 1, 0, 1,
             "Forward-looking. The fans buy in."),
        ],
    },
    {
        "id": "goalie_ot",
        # DEV-B4 (carried over): the bank can't assert the goalie kept the
        # team in it; ask and answers assess the goaltending without
        # presuming it was heroic.
        "ask": "How did you assess the goaltending in the {score} overtime loss to {opp}?",
        "answers": [
            ("He gave us every chance to win it", "honest", 2, 0, 1,
             "The goalie hears it. The skaters feel it."),
            ("Steady all night -- exactly what we need", "calm", 1, 1, 1,
             "Steady praise for steady play."),
            ("We all need to be better in front of him", "demanding", 0, 0, 0,
             "The defense takes the message."),
        ],
    },
    {
        "id": "playoff_point",
        "ask": "Tight one with {opp}, {score}. Are these the points that decide playoff spots?",
        "answers": [
            ("Every point matters from here", "calm", 0, 1, 1,
             "The room understands the math."),
            ("We'll be playing past April", "confident", 1, 0, 2,
             "Bold. The fans are dreaming."),
            ("Too early for that talk", "defensive", 0, 0, -1,
             "Cautious. The fans wanted ambition."),
        ],
    },
]


def _fill(template: str, ctx: dict) -> str:
    """Fill {slots} from ctx.

    Fail-SAFE (was fail-open): a missing slot substitutes an empty string
    instead of returning the raw template -- a literal "{slot}" must never
    render in-game. Missing slots also can't re-trigger on a second pass
    because there is nothing left to fill.

    REV-A3 (prematch None-coercion gap): a key PRESENT with value None
    rendered the literal word "None" ("With them a None-danger side",
    "form None") because only missing keys were blanked. None values are
    now coerced to "" up front, in the render copy only -- 'when'
    predicates and builders still see the original ctx, and the postmatch
    builder's full_ctx fallbacks ("your star"/"them") are applied before
    _fill, so the postmatch path's expectations are unchanged."""
    if not isinstance(ctx, dict):
        ctx = {}
    else:
        ctx = {k: ("" if v is None else v) for k, v in ctx.items()}
    try:
        return template.format(**ctx)
    except KeyError:
        safe = dict(ctx or {})

        class _BlankMissing(dict):
            def __missing__(self, key):
                return ""

        return template.format_map(_BlankMissing(safe))


def _presser_when_ok(q: dict, ctx: dict) -> bool:
    """Evaluate a question's optional 'when' predicate against ctx.

    Questions without a predicate are always eligible (premise-safe
    generics). A predicate that errors excludes its question rather
    than crashing the presser -- a misbehaving guard fails closed."""
    pred = q.get("when")
    if pred is None:
        return True
    try:
        return bool(pred(ctx or {}))
    except Exception:
        return False


def build_prematch_presser(user_team, opponent, ctx: dict) -> List[dict]:
    """Return 2 question dicts: {id, journalist, question, answers[...]}.

    Muck 2026-10-02: trimmed from 3 to 2 -- the pre-game presser was
    too long. Two sharp questions keep the flavor without the drag.

    DEV-B4: questions may carry an optional 'when' predicate on ctx;
    gated questions are filtered BEFORE sampling so a question that
    asserts a premise (e.g. scoring only when form_word == 'poor') can
    never be asked when the premise is false. If gating shrinks the
    pool below 2, it is padded back up with the unguarded
    (premise-safe) generics so the 2-question contract always holds."""
    if not isinstance(ctx, dict):
        ctx = {}
    journalists = ["Sarah Chen (Hockey Night)", "Mike Ross (The Athletic)",
                   "Dave Tremblay (TSN)", "Lisa Park (Sportsnet)",
                   "Emma Walsh (Sportsnet)", "Marc Dubois (TSN)"]
    pool = [q for q in PREMATCH_QUESTIONS if _presser_when_ok(q, ctx)]
    if len(pool) < 2:
        seen = {id(q) for q in pool}
        pool += [q for q in PREMATCH_QUESTIONS
                 if q.get("when") is None and id(q) not in seen]
    picked = random.sample(pool, min(2, len(pool)))
    out = []
    for i, q in enumerate(picked):
        answers = []
        for label, tone, me, be, fe, reaction in q["answers"]:
            answers.append({
                "label": label, "tone": tone,
                "morale_effect": me, "board_effect": be, "fan_effect": fe,
                "reaction": _fill(reaction, ctx),
            })
        out.append({
            "id": q["id"],
            "journalist": journalists[i % len(journalists)],
            "question": _fill(q["ask"], ctx),
            "answers": answers,
        })
    return out


def _drama_questions(drama: list) -> List[dict]:
    """Incident-driven press questions, asked before the routine ones --
    the room wants to know where the coach stands on the night's
    flashpoint. Answers move morale, the board, and the fans, exactly
    like the rest of the presser. Each drama kind has three phrasings;
    one is picked at random so repeat incidents don't read identically."""
    out = []
    for d in drama or []:
        if not isinstance(d, dict):
            continue
        kind = d.get("kind")
        if kind == "line_brawl":
            brawl_asks = [
                ("It turned ugly out there -- the gloves came "
                 "off all over the ice late. What's your message "
                 "to the room?"),
                ("Five fights in the third -- it was a line brawl "
                 "waiting to happen. Do you condone what we saw out there?"),
                ("The benches were banging their sticks and the ice was "
                 "pure chaos late. What's your message to the room after that?"),
            ]
            out.append({
                "id": "drama_brawl",
                "journalist": "Dave Tremblay (TSN)",
                "question": random.choice(brawl_asks),
                "answers": [
                    {"label": "Back them: 'That's playoff hockey. I love it.'",
                     "tone": "passionate", "morale_effect": 1,
                     "board_effect": -1, "fan_effect": 2,
                     "reaction": ("The room roars its approval -- the "
                                  "players love a coach who has their back. "
                                  "The board winces at the circus.")},
                    {"label": "Calm it: 'We can't take ourselves out of games.'",
                     "tone": "calm", "morale_effect": 0,
                     "board_effect": 1, "fan_effect": 0,
                     "reaction": ("The veterans nod. The board appreciates "
                                  "a steady hand.")},
                    {"label": "Deflect: 'Ask the league office.'",
                     "tone": "evasive", "morale_effect": -1,
                     "board_effect": 0, "fan_effect": -1,
                     "reaction": ("The players wanted their coach to pick a "
                                  "side. The fans wanted one too.")},
                ],
            })
        elif kind == "controversial_hit":
            hitter = d.get("hitter", "your player")
            victim = d.get("victim", "their player")
            fined = d.get("fined", False)
            fine_phrase = " and handed down a fine" if fined else ""
            hit_asks = [
                (f"The league reviewed {hitter}'s hit on {victim}"
                 f"{fine_phrase}. Any concern about how your player handled it?"),
                (f"Everyone's talking about {hitter}'s hit on {victim}"
                 f"{fine_phrase}. Is that the kind of hockey you want "
                 f"this team playing?"),
                (f"Your phone must be ringing off the hook about {hitter}'s "
                 f"hit on {victim}{fine_phrase}. Your take, coach?"),
            ]
            out.append({
                "id": "drama_hit",
                "journalist": "Sarah Chen (Hockey Night)",
                "question": random.choice(hit_asks),
                "answers": [
                    {"label": "Defend him: 'Clean hit. He plays on the edge.'",
                     "tone": "passionate", "morale_effect": 1,
                     "board_effect": 0, "fan_effect": 1,
                     "reaction": (f"{hitter} hears his coach went to bat for "
                                  "him -- the room tightens. The fans eat it up.")},
                    {"label": "Measured: 'We'll accept whatever comes.'",
                     "tone": "calm", "morale_effect": -1,
                     "board_effect": 1, "fan_effect": 0,
                     "reaction": ("The board likes the professionalism. "
                                  "The room wanted more fight.")},
                    {"label": "No comment.",
                     "tone": "evasive", "morale_effect": 0,
                     "board_effect": 0, "fan_effect": -1,
                     "reaction": ("Nobody believes a coach has no opinion on "
                                  "a hit like that. The fans grumble.")},
                ],
            })
    return out


# ---------------------------------------------------------------------------
# Situational post-match questions
# ---------------------------------------------------------------------------
# Built from REAL team state only (read defensively -- a missing attribute
# skips the question instead of crashing). Each situation below names the
# game-code source it reads from. Situations with no reliable source
# (losing streak -- Team tracks win_streak only, fan_losing_streak counts
# losing *seasons*; playoff race -- standings live on the league object,
# unreachable from (team, ctx); blockbuster trade -- no recent-trade log
# exists on team or league) are deliberately NOT implemented.

def _pq_name(p) -> str:
    fn = str(getattr(p, "first_name", "") or "").strip()
    ln = str(getattr(p, "last_name", "") or "").strip()
    nm = f"{fn} {ln}".strip()
    if nm:
        return nm
    nm = str(getattr(p, "name", "") or "").strip()
    return nm or "your veteran"


def _pq_ovr(p) -> int:
    o = getattr(p, "overall", None)
    if o is None:
        f = getattr(p, "overall_rating", None)
        try:
            o = f() if callable(f) else f
        except Exception:
            o = None
    try:
        return int(o or 0)
    except (TypeError, ValueError):
        return 0


def _pq_num(p, *names) -> int:
    for n in names:
        try:
            v = getattr(p, n, None)
            if v is not None:
                return int(v)
        except (TypeError, ValueError):
            pass
    try:
        st = getattr(p, "stats", None)
    except Exception:
        st = None
    for n in names:
        try:
            v = getattr(st, n, None) if st is not None else None
            if v is not None:
                return int(v)
        except (TypeError, ValueError):
            pass
    return 0


def _pq_pts(p) -> int:
    return _pq_num(p, "points", "pts")


def _pq_gp(p) -> int:
    return _pq_num(p, "gp", "games_played")


def _pq_sane_svp(v) -> float:
    """daily_news-style finiteness gate for save percentages. Mirrors the
    gate in daily_news._depth_stories: non-finite (inf/nan) or
    out-of-bounds (>1.0, <0.0) values must never qualify or render --
    without it, float('inf') formats straight into press text."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(f) or f < 0.0 or f > 1.0:
        return 0.0
    return f


def _pq_svp(p) -> float:
    for n in ("save_percentage", "save_pct"):
        try:
            v = getattr(p, n, None)
            if v is not None:
                return _pq_sane_svp(v)
        except (TypeError, ValueError):
            pass
    try:
        st = getattr(p, "stats", None)
        if st is not None:
            v = getattr(st, "save_percentage", None)
            if v is not None:
                return _pq_sane_svp(v)
    except (TypeError, ValueError):
        pass
    return 0.0


def _pq_career_goals(p):
    """Career goal total, mirroring daily_news._milestone_watch: prefers
    career_stats.goals, falls back to career_goals. None when unknown."""
    try:
        cs = getattr(p, "career_stats", None)
        if cs is not None:
            g = getattr(cs, "goals", None)
            if g is not None:
                return int(g)
    except (TypeError, ValueError):
        pass
    try:
        g = getattr(p, "career_goals", None)
        return int(g) if g is not None else None
    except (TypeError, ValueError):
        return None


def _pq_is_goalie(p) -> bool:
    pos = getattr(p, "primary_position", None)
    if pos is None:
        pos = getattr(p, "position", "")
    token = str(pos or "").upper().split(".")[-1].strip()
    return token in ("GOALIE", "G")


def _pq_is_injured(p) -> bool:
    try:
        return bool(getattr(p, "is_injured", False))
    except Exception:
        return False


def _pq_fmt_svp(svp: float) -> str:
    try:
        return f"{float(svp):.3f}".lstrip("0")
    except (TypeError, ValueError):
        return ".000"


def _situational_postmatch(team, ctx, rng) -> List[dict]:
    """Questions driven by real team state, asked after drama and before
    the routine bank. Returns question dicts in the exact builder shape:
    {id, journalist, question, answers:[{label, tone, morale_effect,
    board_effect, fan_effect, reaction}]}. Every situation is wrapped so a
    missing/odd attribute skips that question -- never raises.

    Live situations and their sources:
      win streak 5+      -- team.win_streak (game_classes.Team)
      star injured        -- roster scan: is_injured + overall>=85
      slumping star       -- roster scan: overall>=80, gp>=15, pts/gp<0.5
      goalie controversy  -- roster scan: backup (fewer gp) out-saving starter
      hot backup          -- roster scan, mirrors daily_news._depth_stories
                             (3<=gp<=12, save%>=.915), skipped when the
                             controversy question already fired
      milestone watch     -- roster scan, mirrors daily_news._milestone_watch
                             (career goals within 8 below 500/400/300/200/100)
    """
    out = []

    def _add(qid, journalist, question, answers):
        built = []
        for label, tone, me, be, fe, reaction in answers:
            built.append({
                "label": label, "tone": tone,
                "morale_effect": int(me), "board_effect": int(be),
                "fan_effect": int(fe), "reaction": reaction,
            })
        out.append({
            "id": qid, "journalist": journalist,
            "question": question, "answers": built,
        })

    try:
        roster = list(getattr(team, "roster", None) or [])
    except Exception:
        return out
    if not roster:
        return out
    won = bool((ctx or {}).get("won", False))

    # 1. Winning streak -- Team.win_streak counts consecutive wins and is
    #    snapped by update_record() on any non-win, so streak>=5 after a win
    #    is a genuine streak.
    try:
        ws = int(getattr(team, "win_streak", 0) or 0)
        if won and ws >= 5:
            _add("sit_winstreak", "Mike Ross (The Athletic)",
                 f"That's {ws} straight wins now, coach. Is this the best "
                 f"hockey this club has played all year?",
                 [
                     ("The room believes it can beat anyone", "confident", 2, 0, 2,
                      "The streak rolls on good vibes."),
                     ("We're taking it one game at a time", "calm", 1, 1, 1,
                      "Grounded. The board loves the maturity."),
                     ("We haven't played our best yet", "honest", 1, 1, 0,
                      "Standards. The room nods -- there's another level."),
                 ])
    except Exception:
        pass

    # 2. Star injured -- a real absence the press would ask about.
    try:
        hurt = [p for p in roster
                if _pq_is_injured(p) and _pq_ovr(p) >= 85]
        if hurt:
            star = rng.choice(hurt) if len(hurt) > 1 else hurt[0]
            nm = _pq_name(star)
            _add("sit_star_injured", "Sarah Chen (Hockey Night)",
                 f"Losing {nm} hurts -- he's one of your best. "
                 f"How do you fill that hole?",
                 [
                     ("Next man up -- that's the culture", "confident", 1, 1, 1,
                      "The room rallies. The replacement skates taller."),
                     ("You don't replace a player like that", "honest", 0, 0, 0,
                      "Candor. The fans share the worry."),
                     ("Our depth is about to be tested", "calm", 0, 1, 0,
                      "Measured. The board notes the depth question."),
                 ])
    except Exception:
        pass

    # 3. Slumping star -- real production dip on a top player.
    try:
        slumpers = []
        for p in roster:
            if _pq_is_goalie(p) or _pq_is_injured(p):
                continue
            if _pq_ovr(p) < 80:
                continue
            gp = _pq_gp(p)
            if gp < 15:
                continue
            pts = _pq_pts(p)
            if gp > 0 and pts / gp < 0.5:
                slumpers.append((pts / gp, p))
        if slumpers:
            slumpers.sort(key=lambda t: t[0])
            _, p = slumpers[0]
            nm, pts, gp = _pq_name(p), _pq_pts(p), _pq_gp(p)
            _add("sit_slump", "Dave Tremblay (TSN)",
                 f"{nm} has {pts} points in {gp} games. What's going on with him?",
                 [
                     ("He's working through it -- I believe in him", "confident", 1, 0, 1,
                      f"{nm} hears the public backing."),
                     ("He needs to be better, simple as that", "demanding", -1, 0, 0,
                      f"Blunt. {nm} didn't love hearing it secondhand."),
                     ("The chances are there -- they'll fall", "calm", 0, 1, 0,
                      "Patience. The video staff keeps working."),
                 ])
    except Exception:
        pass

    # 4. Goalie controversy -- the backup (fewer games) is out-saving the
    #    starter. Starter = most games played; both need a real sample.
    controversy_fired = False
    try:
        goalies = [(p, _pq_gp(p), _pq_svp(p)) for p in roster
                   if _pq_is_goalie(p)]
        goalies = [t for t in goalies if t[1] >= 3 and t[2] > 0]
        if len(goalies) >= 2:
            goalies.sort(key=lambda t: t[1], reverse=True)
            sp, sgp, ssvp = goalies[0]
            cands = [t for t in goalies[1:] if t[2] > ssvp]
            if cands:
                bp, bgp, bsvp = max(cands, key=lambda t: t[2])
                bnm, snm = _pq_name(bp), _pq_name(sp)
                svp_txt = _pq_fmt_svp(bsvp)
                controversy_fired = True
                _add("sit_goalie", "Lisa Park (Sportsnet)",
                     f"{bnm} is stopping everything at {svp_txt} while {snm} "
                     f"struggles. Is there a goalie controversy brewing?",
                     [
                         ("No controversy -- we trust both", "calm", 1, 1, 0,
                          "The goalies stay united. The room moves on."),
                         ("The crease is earned, not given", "demanding", 0, 0, 1,
                          f"{snm} hears the challenge. {bnm} hears the door open."),
                         (f"{snm} is our guy, full stop", "confident", 1, 0, -1,
                          f"{snm} is relieved. Some fans think {bnm} deserves better."),
                     ])
    except Exception:
        pass

    # 5. Hot backup -- mirrors daily_news._depth_stories (3<=gp<=12,
    #    save%>=.915). Skipped when the controversy question already fired
    #    so one presser never carries two crease questions.
    try:
        if not controversy_fired:
            goalies = [(p, _pq_gp(p), _pq_svp(p)) for p in roster
                       if _pq_is_goalie(p)]
            if goalies:
                max_gp = max(t[1] for t in goalies)
                hot = [t for t in goalies
                       if 3 <= t[1] <= 12 and t[2] >= 0.915 and t[1] < max_gp]
                if hot:
                    hot.sort(key=lambda t: t[2], reverse=True)
                    bp, bgp, bsvp = hot[0]
                    bnm = _pq_name(bp)
                    svp_txt = _pq_fmt_svp(bsvp)
                    _add("sit_backup_goalie", "Emma Walsh (Sportsnet)",
                         f"{bnm} is running {svp_txt} in limited action. "
                         f"Does he deserve more starts?",
                         [
                             ("He's earned a longer look", "honest", 1, 0, 1,
                              f"{bnm} hears the public vote of confidence."),
                             ("We like our rotation as it is", "calm", 0, 1, 0,
                              "Steady. The starter appreciates the loyalty."),
                             ("Wins decide who plays", "demanding", 0, 0, 0,
                              "Meritocracy. Both goalies stay sharp."),
                         ])
    except Exception:
        pass

    # 6. Milestone watch -- mirrors daily_news._milestone_watch: career
    #    goals within 8 below 500/400/300/200/100.
    try:
        best = None
        for p in roster:
            cg = _pq_career_goals(p)
            if cg is None:
                continue
            for mark in (500, 400, 300, 200, 100):
                if mark - 8 <= cg < mark:
                    away = mark - cg
                    if best is None or away < best[0]:
                        best = (away, p, cg, mark)
                    break
        if best is not None:
            away, p, cg, mark = best
            nm = _pq_name(p)
            _add("sit_milestone", "Marc Dubois (TSN)",
                 f"{nm} sits at {cg} career goals -- {away} away from {mark}. "
                 f"Is the room aware of how close he is?",
                 [
                     ("The room knows -- we'll get him there", "confident", 2, 0, 2,
                      f"The fans are already counting down. {nm} is touched."),
                     ("We're focused on wins, not milestones", "calm", 0, 1, 0,
                      "Team-first. The board approves."),
                     ("He'd trade it for two points", "honest", 1, 0, 0,
                      f"{nm} nods along. Milestones come when they come."),
                 ])
    except Exception:
        pass

    return out


def build_postmatch_presser(user_team, opponent, won: bool, drew: bool,
                            score: str, star_name: str, ctx: dict) -> List[dict]:
    """Build the post-match presser.

    drew: legacy parameter name -- both live callers pass went_ot
    (game_manager.py:6497, main.py:20392). Ties are impossible in the sim
    (STEP 0 verified 2026-10-11: OT -> shootout -> coin flip always
    produces a winner; record_result tracks only W/OTL/L), so drew==True
    means "the game went to overtime": OT wins draw from
    POSTMATCH_QUESTIONS_OT_WIN, OT losses from POSTMATCH_QUESTIONS_OT_LOSS.
    No bank ever asserts a draw.
    """
    if not isinstance(ctx, dict):
        ctx = {}
    journalists = ["Sarah Chen (Hockey Night)", "Mike Ross (The Athletic)",
                   "Dave Tremblay (TSN)", "Lisa Park (Sportsnet)",
                   "Emma Walsh (Sportsnet)", "Marc Dubois (TSN)"]
    bank = ((POSTMATCH_QUESTIONS_OT_WIN if won else POSTMATCH_QUESTIONS_OT_LOSS)
            if drew else
            (POSTMATCH_QUESTIONS_WIN if won else POSTMATCH_QUESTIONS_LOSS))
    full_ctx = dict(ctx)
    full_ctx.update({"score": score or "", "star": star_name or "your star",
                     "opp": getattr(opponent, "team_name", "them") or "them",
                     "won": won, "drew": drew})
    # F-7: the postmatch path was iterating the bank UNFILTERED -- postmatch
    # questions now run through the same 'when' guard as prematch. A guard
    # that errors still excludes its question (fail-closed, see
    # _presser_when_ok).
    bank = [q for q in bank if _presser_when_ok(q, full_ctx)]
    out = []
    for i, q in enumerate(bank):
        answers = []
        for label, tone, me, be, fe, reaction in q["answers"]:
            answers.append({
                "label": label, "tone": tone,
                "morale_effect": me, "board_effect": be, "fan_effect": fe,
                "reaction": _fill(_fill(reaction, full_ctx), full_ctx),
            })
        out.append({
            "id": q["id"],
            "journalist": journalists[i % len(journalists)],
            "question": _fill(q["ask"], full_ctx),
            "answers": answers,
        })
    # The night's flashpoints get asked about first, then the
    # situational questions, then the routine bank.
    return (_drama_questions(full_ctx.get("drama"))
            + _situational_postmatch(user_team, full_ctx, random)
            + out)


# ---------------------------------------------------------------------------
# Team talks
# ---------------------------------------------------------------------------

TEAM_TALK_OPTIONS = {
    "prematch": [
        {"id": "passionate_fav", "label": "Passionate: 'Go out and dominate!'",
         "tone": "passionate",
         "text": "You're the better team — prove it from the first shift!",
         "best_when": "favorite", "boost": 1.04, "morale": 1},
        {"id": "calm_fav", "label": "Calm: 'Stick to the game plan'",
         "tone": "calm",
         "text": "Trust the system, stay patient, the chances will come.",
         "best_when": "favorite", "boost": 1.02, "morale": 0},
        {"id": "siege", "label": "Siege mentality: 'Nobody believes in us'",
         "tone": "passionate",
         "text": "Nobody gives us a chance tonight. Let's shock them all!",
         "best_when": "underdog", "boost": 1.05, "morale": 1},
        {"id": "relaxed_dog", "label": "Relaxed: 'No pressure, enjoy it'",
         "tone": "calm",
         "text": "No pressure tonight — go out, work hard, enjoy your hockey.",
         "best_when": "underdog", "boost": 1.01, "morale": 1},
        {"id": "demanding", "label": "Demanding: 'I expect a response'",
         "tone": "demanding",
         "text": "Last game wasn't good enough. I expect a response tonight.",
         "best_when": "after_loss", "boost": 1.03, "morale": 0},
    ],
    "intermission": [
        {"id": "encourage_win", "label": "Encouraged: 'More of the same!'",
         "tone": "encouraging",
         "text": "Excellent period — more of the same and this game is ours.",
         "best_when": "winning", "boost": 1.03, "morale": 1},
        {"id": "demand_win", "label": "Demanding: 'Don't sit back!'",
         "tone": "demanding",
         "text": "The lead means nothing if we sit back. Keep pushing!",
         "best_when": "winning", "boost": 1.02, "morale": 0},
        {"id": "rally", "label": "Passionate: 'We can turn this around!'",
         "tone": "passionate",
         "text": "One goal changes everything. Win the next period!",
         "best_when": "losing", "boost": 1.04, "morale": 1},
        {"id": "calm_lose", "label": "Calm: 'Stick with it'",
         "tone": "calm",
         "text": "Stay calm, stick to the plan. The game is still there for us.",
         "best_when": "losing", "boost": 1.02, "morale": 0},
        {"id": "tied_push", "label": "Encouraging: 'The next goal wins it'",
         "tone": "encouraging",
         "text": "Dead even. Who wants it more? Go take it!",
         "best_when": "tied", "boost": 1.03, "morale": 1},
    ],
    "postmatch": [
        {"id": "praise_win", "label": "Praise the performance",
         "tone": "encouraging",
         "text": "Outstanding — that's the standard now.",
         "best_when": "won", "boost": 1.0, "morale": 2},
        {"id": "grounded_win", "label": "Keep them grounded",
         "tone": "calm",
         "text": "Good win, but the next game starts 0-0.",
         "best_when": "won", "boost": 1.0, "morale": 1},
        {"id": "angry_loss", "label": "Angry: 'Not good enough!'",
         "tone": "demanding",
         "text": "That was nowhere near good enough. Think about it tonight.",
         "best_when": "lost", "boost": 1.0, "morale": -2},
        {"id": "support_loss", "label": "Supportive: 'Heads up'",
         "tone": "encouraging",
         "text": "Heads up. We win together, we lose together.",
         "best_when": "lost", "boost": 1.0, "morale": 1},
    ],
}


def get_team_talk_options(when: str, context: dict) -> List[dict]:
    """Return talk options annotated with a 'fit' hint for the UI."""
    opts = TEAM_TALK_OPTIONS.get(when, [])
    situation = context.get("situation", "")
    out = []
    for o in opts:
        fit = "good" if o["best_when"] == situation else "neutral"
        # Demanding talks after poor runs risk backlash; passionate as favorite can fall flat
        if o["tone"] == "demanding" and context.get("losing_streak", 0) >= 3:
            fit = "risky"
        out.append({**o, "fit": fit})
    return out


def apply_team_talk(team, option: dict, context: dict) -> Tuple[str, float]:
    """Apply a team talk. Returns (reaction_text, sim_boost_multiplier).

    Anti-farming: players tune out repeated speeches. Talks are logged
    per team; each talk within the last 7 days halves the effectiveness
    of the next one, and 4+ talks in a week risks the room tuning out
    entirely (flat or negative reaction). One heartfelt speech before a
    big game matters; five in a week is wallpaper.
    """
    import datetime as _dt
    boost = float(option.get("boost", 1.0))
    morale_delta = int(option.get("morale", 0))
    fit = option.get("fit", "neutral")

    # --- speech-fatigue bookkeeping -------------------------------------
    try:
        today = context.get("today")
        if isinstance(today, str):
            today = _dt.date.fromisoformat(today[:10])
        elif not hasattr(today, "year"):
            today = _dt.date.today()
    except Exception:
        today = _dt.date.today()
    try:
        log = getattr(team, "_team_talk_log", None)
        if not isinstance(log, list):
            log = []
            team._team_talk_log = log
        week_ago = today - _dt.timedelta(days=7)
        log = [d for d in log
               if isinstance(d, _dt.date) and d >= week_ago]
        recent = len(log)
        log.append(today)
        team._team_talk_log = log
    except Exception:
        recent = 0

    # Diminishing returns: 1.0, 0.5, 0.25, 0.1, then ~nothing
    fatigue = [1.0, 0.5, 0.25, 0.1, 0.0][min(recent, 4)]

    if recent >= 3:
        # The room has heard it all before -- tuned out, maybe annoyed
        import random as _r
        if _r.random() < 0.35:
            for p in getattr(team, "roster", []) or []:
                m = getattr(p, "morale", 70) or 70
                p.morale = max(1, min(100, m - 5))
            return ("You said the same thing again -- a few players "
                    "exchanged glances. The room has tuned you out."), 0.99

    if fit == "risky":
        # Backlash: half the squad tunes out
        morale_delta = -1
        boost = 0.98
        reaction = "Your harsh words fell flat — several players stared at the floor."
    elif fit == "good":
        morale_delta += 1
        boost = min(1.08, boost + 0.01)
        reaction = "The room responded — sticks banging, everyone locked in."
    else:
        reaction = "The players nodded along."

    if fatigue < 1.0 and morale_delta > 0:
        morale_delta = max(0, int(round(morale_delta * fatigue)))
        boost = 1.0 + (boost - 1.0) * fatigue
        if recent >= 1:
            reaction = ("Heard it before -- a polite nod, nothing more. "
                        "(Speech fatigue: talks lose punch when repeated.)")

    for p in getattr(team, "roster", []) or []:
        m = getattr(p, "morale", 70) or 70
        # Leaders and big-game players respond more
        leadership = getattr(p, "leadership", 50) or 50
        adj = morale_delta + (1 if leadership >= 75 and morale_delta > 0 else 0)
        # Fatigue also dulls the leadership bonus on repeats
        if fatigue < 1.0 and leadership >= 75 and morale_delta > 0:
            adj = morale_delta
        p.morale = max(1, min(100, m + adj * 5))

    return reaction, boost


# ---------------------------------------------------------------------------
# Opposition scout report
# ---------------------------------------------------------------------------

def _team_avg(players, attr: str) -> float:
    vals = [getattr(p, attr, 10) or 10 for p in players
            if getattr(p, "primary_position", None) is not None
            and str(getattr(p, "primary_position", "")).upper() != "GOALIE"]
    return sum(vals) / len(vals) if vals else 10.0


def _player_rating(p) -> float:
    attrs = ["skating", "shooting", "passing", "defense", "physicality",
             "goaltending", "offensive_awareness", "defensive_awareness"]
    vals = [getattr(p, a, 10) or 10 for a in attrs if hasattr(p, a)]
    return sum(vals) / len(vals) if vals else 10.0


def generate_opposition_report(opponent, standings: dict) -> dict:
    """Build a pre-match scout report on the opponent."""
    roster = [p for p in (getattr(opponent, "roster", []) or [])
              if not getattr(p, "is_injured", False)]
    skaters = [p for p in roster
               if str(getattr(p, "primary_position", "")).upper() != "GOALIE"]
    goalies = [p for p in roster
               if str(getattr(p, "primary_position", "")).upper() == "GOALIE"]

    offense = _team_avg(skaters, "shooting")
    defense = _team_avg(skaters, "defense")
    physical = _team_avg(skaters, "physicality")
    skating = _team_avg(skaters, "skating")
    goaltending = (_team_avg(goalies, "goaltending") if goalies else 10.0)

    strengths, weaknesses = [], []
    facets = [("Attack", offense, "their forwards finish chances clinically"),
              ("Defense", defense, "they defend the slot very well"),
              ("Physicality", physical, "they outhit and wear teams down"),
              ("Skating", skating, "their transition game is dangerous"),
              ("Goaltending", goaltending, "their goalie steals games")]
    for name, val, desc in sorted(facets, key=lambda f: f[1], reverse=True)[:2]:
        strengths.append(f"{name} ({val:.1f}): {desc}.")
    for name, val, desc in sorted(facets, key=lambda f: f[1])[:2]:
        weaknesses.append(f"{name} ({val:.1f}): exploitable — {desc} is lacking.")

    key_players = sorted(skaters, key=_player_rating, reverse=True)[:3]
    key_names = [f"{p.first_name} {p.last_name} ({_player_rating(p):.1f})"
                 for p in key_players]

    rec = standings.get(getattr(opponent, "team_name", ""), {}) if standings else {}
    record = f"{rec.get('W', '?')}-{rec.get('L', '?')}-{rec.get('OTL', '?')}" if rec else "unknown"

    advice = []
    if offense >= 14:
        advice.append("Contain their top line — double-shift your shutdown pair against them.")
    if goaltending < 11:
        advice.append("Their goaltending is shaky: shoot early and crash the net for rebounds.")
    if physical < 11:
        advice.append("They don't like physical hockey — finish every check.")
    if skating >= 14:
        advice.append("Beware their rush: keep a forward high and protect the blue line.")
    if not advice:
        advice.append("No glaring weakness — win the special-teams battle.")

    danger = "High" if (offense + goaltending) / 2 >= 14 else (
        "Medium" if (offense + goaltending) / 2 >= 11.5 else "Low")

    return {
        "team": getattr(opponent, "team_name", None) or "Opponent",
        "record": record,
        "danger_level": danger,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "key_players": key_names,
        "tactical_advice": advice,
    }


# ---------------------------------------------------------------------------
# Training schedules
# ---------------------------------------------------------------------------

TRAINING_INTENSITIES = ["Light", "Normal", "Intense"]
TRAINING_FOCI = ["Balanced", "Attacking", "Defensive", "Physical", "Tactical", "Recovery"]
TRAINING_UNITS = ["Forwards", "Defense", "Goalies"]

TRAINING_PRESETS = {
    "Balanced Week": {"Forwards": ("Normal", "Balanced"),
                      "Defense": ("Normal", "Balanced"),
                      "Goalies": ("Normal", "Balanced")},
    "Attacking Blitz": {"Forwards": ("Intense", "Attacking"),
                        "Defense": ("Normal", "Attacking"),
                        "Goalies": ("Normal", "Balanced")},
    "Defensive Lockdown": {"Forwards": ("Normal", "Defensive"),
                           "Defense": ("Intense", "Defensive"),
                           "Goalies": ("Normal", "Balanced")},
    "Physical Camp": {"Forwards": ("Intense", "Physical"),
                      "Defense": ("Intense", "Physical"),
                      "Goalies": ("Normal", "Recovery")},
    "Tactical Week": {"Forwards": ("Normal", "Tactical"),
                      "Defense": ("Normal", "Tactical"),
                      "Goalies": ("Light", "Tactical")},
    "Recovery Week": {"Forwards": ("Light", "Recovery"),
                      "Defense": ("Light", "Recovery"),
                      "Goalies": ("Light", "Recovery")},
}


class TrainingSystem:
    """Weekly training schedule per unit."""

    def __init__(self):
        self.schedule: Dict[str, Tuple[str, str]] = {
            u: ("Normal", "Balanced") for u in TRAINING_UNITS
        }
        self.preset_name: str = "Balanced Week"

    def set_preset(self, name: str):
        if name in TRAINING_PRESETS:
            self.schedule = {u: v for u, v in TRAINING_PRESETS[name].items()}
            self.preset_name = name

    def set_unit(self, unit: str, intensity: str, focus: str):
        if unit in TRAINING_UNITS and intensity in TRAINING_INTENSITIES \
                and focus in TRAINING_FOCI:
            self.schedule[unit] = (intensity, focus)
            self.preset_name = "Custom"

    def weekly_effects(self) -> dict:
        """Aggregate effects across units."""
        dev_mult = 1.0
        injury_mult = 1.0
        morale_delta = 0
        notes = []
        for unit, (intensity, focus) in self.schedule.items():
            if intensity == "Intense":
                dev_mult *= 1.18
                injury_mult *= 1.35
                morale_delta -= 1
            elif intensity == "Light":
                dev_mult *= 0.85
                injury_mult *= 0.7
                morale_delta += 1
            if focus == "Recovery":
                injury_mult *= 0.8
                morale_delta += 1
                notes.append(f"{unit}: recovery focus — players feel fresh.")
            elif focus == "Physical":
                injury_mult *= 1.15
                notes.append(f"{unit}: heavy contact work — bruises expected.")
            elif focus == "Attacking":
                notes.append(f"{unit}: attacking patterns sharpened.")
            elif focus == "Defensive":
                notes.append(f"{unit}: defensive structure drilled.")
            elif focus == "Tactical":
                notes.append(f"{unit}: video + systems work.")
        return {
            "development_mult": round(dev_mult, 2),
            "injury_risk_mult": round(injury_mult, 2),
            "morale_delta": morale_delta,
            "notes": notes,
        }

    def to_dict(self) -> dict:
        return {"schedule": {u: list(v) for u, v in self.schedule.items()},
                "preset_name": self.preset_name}

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingSystem":
        t = cls()
        sched = (data or {}).get("schedule", {})
        for u in TRAINING_UNITS:
            if u in sched and len(sched[u]) == 2:
                t.schedule[u] = (sched[u][0], sched[u][1])
        t.preset_name = (data or {}).get("preset_name", "Balanced Week")
        return t


# ---------------------------------------------------------------------------
# Manager reputation
# ---------------------------------------------------------------------------

REPUTATION_LEVELS = [
    (95, "Legend"), (80, "Elite"), (60, "Renowned"),
    (40, "Respected"), (20, "Promising"), (0, "Unknown"),
]


class ManagerProfile:
    def __init__(self):
        self.reputation: int = 30
        self.career_wins: int = 0
        self.career_losses: int = 0
        self.career_otl: int = 0
        self.titles_won: int = 0
        self.playoff_appearances: int = 0
        self.seasons_managed: int = 0

    @property
    def level(self) -> str:
        for threshold, name in REPUTATION_LEVELS:
            if self.reputation >= threshold:
                return name
        return "Unknown"

    def record_result(self, won: bool, went_ot: bool, is_playoff: bool):
        if won:
            self.career_wins += 1
            self.reputation = min(100, self.reputation + (2 if is_playoff else 1))
        elif went_ot:
            self.career_otl += 1
        else:
            self.career_losses += 1
            self.reputation = max(0, self.reputation - 1)

    def record_title(self, title: str):
        self.titles_won += 1
        self.reputation = min(100, self.reputation + 15)

    def to_dict(self) -> dict:
        return {
            "reputation": self.reputation, "career_wins": self.career_wins,
            "career_losses": self.career_losses, "career_otl": self.career_otl,
            "titles_won": self.titles_won,
            "playoff_appearances": self.playoff_appearances,
            "seasons_managed": self.seasons_managed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ManagerProfile":
        m = cls()
        for k, v in (data or {}).items():
            if hasattr(m, k):
                setattr(m, k, v)
        return m


# ---------------------------------------------------------------------------
# CareerState container
# ---------------------------------------------------------------------------

class CareerState:
    """All FM-style career state for one manager career."""

    def __init__(self):
        self.board = BoardSystem()
        self.training = TrainingSystem()
        self.profile = ManagerProfile()
        self.press_history: List[dict] = []   # {date, type, summary}
        self.youth_history: List[dict] = []   # past intakes
        self.last_intake_year: int = 0
        self.intake_preview_sent: int = 0
        self.prompts_enabled: bool = True
        self.career_start_date: str = ""
        self.sack_announced: bool = False

    def to_dict(self) -> dict:
        return {
            "board": self.board.to_dict(),
            "training": self.training.to_dict(),
            "profile": self.profile.to_dict(),
            "press_history": self.press_history[-50:],
            "youth_history": self.youth_history[-10:],
            "last_intake_year": self.last_intake_year,
            "intake_preview_sent": self.intake_preview_sent,
            "prompts_enabled": self.prompts_enabled,
            "career_start_date": self.career_start_date,
            "sack_announced": self.sack_announced,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CareerState":
        c = cls()
        data = data or {}
        c.board = BoardSystem.from_dict(data.get("board", {}))
        c.training = TrainingSystem.from_dict(data.get("training", {}))
        c.profile = ManagerProfile.from_dict(data.get("profile", {}))
        c.press_history = data.get("press_history", [])
        c.youth_history = data.get("youth_history", [])
        c.last_intake_year = data.get("last_intake_year", 0)
        c.intake_preview_sent = data.get("intake_preview_sent", 0)
        c.prompts_enabled = data.get("prompts_enabled", True)
        c.career_start_date = data.get("career_start_date", "")
        c.sack_announced = data.get("sack_announced", False)
        return c
