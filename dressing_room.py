"""Dressing-room dynamics (module 03): morale as a social system.

Turns morale from a number into a social system that creates stories,
built on the reputation (01) and coaching-engagement (02) foundations.

What it models:
- Hierarchy: the captain and alternates carry extra influence; veteran
  voices outrank fringe players. Influence is visible, never hidden.
- Social groups: cliques form by tenure and -- only where the data
  exists -- nationality. Players with no group are floaters.
- Cascades: trades and press answers ripple through individuals AND
  their groups. A captain with real influence steadies the room.
- Team talks: pre-game and intermission talks in calm / fired-up /
  cautious tones. Outcomes feed the existing first- and third-period
  momentum (via impact_system.nudge_momentum -- additive, capped).

Design law: additive, backfilled on old saves, no hidden truth. User
and AI share every mechanic -- AI clubs get automatic coach talks
through the same give_talk() path the user's talks use.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

TONES = ("calm", "fired-up", "cautious")

# tone -> score_state -> fit (0-100). Fired-up chases a deficit,
# calm steadies nerves, cautious protects a lead.
TONE_FIT = {
    ("fired-up", "trailing"): 85, ("fired-up", "tied"): 65,
    ("fired-up", "leading"): 30,
    ("calm", "trailing"): 55, ("calm", "tied"): 70,
    ("calm", "leading"): 80,
    ("cautious", "trailing"): 30, ("cautious", "tied"): 60,
    ("cautious", "leading"): 85,
}

_TENURE_YEARS = {
    "This season": 0, "2 years": 2, "3 years": 3, "4+ years": 4,
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _clamp(v: float, lo: float = 1, hi: float = 100) -> int:
    try:
        return max(int(lo), min(int(hi), int(round(v))))
    except Exception:
        return int(lo)


def _name(p: Any) -> str:
    for attr in ("full_name", "name"):
        v = getattr(p, attr, None)
        if v:
            return str(v)
    return "Unknown"


def _pid(p: Any) -> Any:
    return getattr(p, "id", id(p))


def _roster(team: Any) -> List[Any]:
    try:
        return list(getattr(team, "roster", []) or [])
    except Exception:
        return []


def ensure_dressing_room_fields(team: Any) -> Dict[str, Any]:
    """Backfill the dressing-room state dict on a team (old saves safe)."""
    dr = getattr(team, "dressing_room", None)
    if not isinstance(dr, dict):
        dr = {}
    dr.setdefault("mood_log", [])          # recent room story lines (newest last)
    dr.setdefault("pregame", None)         # pending pre-game talk dict
    dr.setdefault("intermission", None)    # pending intermission talk dict
    dr.setdefault("arrivals", {})          # pid -> {"gp_at_arrival": int}
    try:
        team.dressing_room = dr
    except Exception:
        pass
    return dr


def _log(team: Any, line: str, cap: int = 40) -> None:
    dr = ensure_dressing_room_fields(team)
    try:
        dr["mood_log"].append(str(line))
        del dr["mood_log"][:-cap]
    except Exception:
        pass


# --------------------------------------------------------------------------
# Hierarchy
# --------------------------------------------------------------------------

def tenure_years(player: Any) -> int:
    """Tenure in years from the native team_tenure string."""
    return _TENURE_YEARS.get(str(getattr(player, "team_tenure", "This season")), 0)


def influence_of(player: Any) -> int:
    """A player's pull in the room (1-100). Letters carry weight."""
    base = 35
    letter = str(getattr(player, "captaincy", "") or "").upper()
    if letter == "C":
        base = 70
    elif letter == "A":
        base = 60
    try:
        base += float(getattr(player, "leadership", 50) or 50) * 0.22
    except Exception:
        pass
    ty = tenure_years(player)
    base += {4: 8, 3: 5, 2: 2}.get(ty, 0)
    return _clamp(base, 5, 99)


def _tier(player: Any, influence: int) -> str:
    letter = str(getattr(player, "captaincy", "") or "").upper()
    if letter == "C":
        return "Captain"
    if letter == "A":
        return "Alternate"
    if influence >= 70:
        return "Veteran core"
    if influence >= 45:
        return "Regular"
    return "Fringe"


def hierarchy(team: Any) -> List[Dict[str, Any]]:
    """The room's pecking order, most influential first."""
    rows = []
    for p in _roster(team):
        inf = influence_of(p)
        rows.append({
            "player": p, "id": _pid(p), "name": _name(p),
            "letter": str(getattr(p, "captaincy", "") or "").upper() or "-",
            "influence": inf, "tier": _tier(p, inf),
            "morale": _clamp(getattr(p, "morale", 70)),
        })
    rows.sort(key=lambda r: (-r["influence"], r["name"]))
    return rows


def captain_of(team: Any) -> Optional[Any]:
    for p in _roster(team):
        if str(getattr(p, "captaincy", "") or "").upper() == "C":
            return p
    # No letter? The most influential player is the de facto voice.
    rows = hierarchy(team)
    return rows[0]["player"] if rows else None


# --------------------------------------------------------------------------
# Social groups (cliques)
# --------------------------------------------------------------------------

def _tenure_bucket(player: Any) -> str:
    ty = tenure_years(player)
    if ty >= 4:
        return "core"
    if ty >= 2:
        return "established"
    return "new"


def form_cliques(team: Any, min_size: int = 3,
                 extra: Any = None) -> List[Dict[str, Any]]:
    """Group the room by tenure + nationality (only where data exists).

    Returns clique dicts; players in no clique are floaters.

    ``extra``: a player no longer on the roster (e.g. just traded away)
    to include in the grouping anyway. Departure cascades run after the
    roster move, so without this the room can't tell which clique it lost.
    """
    roster = _roster(team)
    if extra is not None:
        try:
            eid = _pid(extra)
            if all(_pid(p) != eid for p in roster):
                roster = list(roster) + [extra]
        except Exception:
            pass
    buckets: Dict[tuple, List[Any]] = {}
    for p in roster:
        nat = str(getattr(p, "nationality", "") or "").strip() or "Unknown"
        key = (_tenure_bucket(p), nat)
        buckets.setdefault(key, []).append(p)

    cliques = []
    for (tb, nat), members in buckets.items():
        if len(members) < min_size:
            continue
        moods = [_clamp(getattr(m, "morale", 70)) for m in members]
        # Bond: shared tenure + shared nationality is the whole bond here.
        bond = round(0.45 + 0.10 * min(len(members), 6) / 6 + 0.15, 2)
        if tb == "core":
            label = f"The {nat} core"
        elif tb == "established":
            label = f"{nat} regulars"
        else:
            label = f"{nat} newcomers"
        cliques.append({
            "name": label, "kind": tb, "nationality": nat,
            "member_ids": {_pid(m) for m in members},
            "members": [_name(m) for m in members],
            "bond": min(0.95, bond),
            "mood": int(round(sum(moods) / len(moods))) if moods else 70,
        })
    cliques.sort(key=lambda c: (-len(c["members"]), c["name"]))
    return cliques


def clique_of(team: Any, player: Any,
              extra: Any = None) -> Optional[Dict[str, Any]]:
    pid = _pid(player)
    for c in form_cliques(team, extra=extra):
        if pid in c["member_ids"]:
            return c
    return None


def floaters(team: Any) -> List[Dict[str, Any]]:
    """Players with no clique -- higher integration risk, lower cascade."""
    cliques = form_cliques(team)
    grouped = set()
    for c in cliques:
        grouped |= c["member_ids"]
    return [{"name": _name(p), "id": _pid(p)}
            for p in _roster(team) if _pid(p) not in grouped]


def room_mood(team: Any) -> int:
    """Mean morale of the room (1-100)."""
    roster = _roster(team)
    if not roster:
        return 70
    return _clamp(sum(_clamp(getattr(p, "morale", 70)) for p in roster)
                  / len(roster))


# --------------------------------------------------------------------------
# Morale cascades
# --------------------------------------------------------------------------

def _bump(player: Any, delta: float) -> None:
    try:
        player.morale = _clamp(getattr(player, "morale", 70) + delta)
    except Exception:
        pass


def cascade_on_trade(team: Any, traded: Any = None, arriving: Any = None,
                     date_str: str = "") -> List[str]:
    """A trade shakes the room. Departures hurt; arrivals must integrate.

    Called for BOTH sides: the old team loses `traded`, the new team
    gains `arriving`.
    """
    lines: List[str] = []
    dr = ensure_dressing_room_fields(team)
    tname = str(getattr(team, "team_name", "the club"))

    if traded is not None:
        tname_p = _name(traded)
        letter = str(getattr(traded, "captaincy", "") or "").upper()
        base_hit = 8 if letter == "C" else (5 if letter == "A" else 3)
        # The captain steadies the room -- unless he was the one traded.
        cap = captain_of(team)
        steady = (cap is not None and cap is not traded
                  and influence_of(cap) >= 70)
        if steady:
            base_hit = max(1, int(round(base_hit * 0.5)))
        # The departed player is already off the roster by the time the
        # post-trade hook runs -- include him in the grouping so the room
        # knows which clique it lost.
        clique = clique_of(team, traded, extra=traded)
        for p in _roster(team):
            if p is traded:
                continue
            if clique is not None and _pid(p) in clique["member_ids"]:
                _bump(p, -base_hit * (0.5 + clique["bond"]))
            else:
                _bump(p, -1)
        if letter == "C":
            lines.append(f"{tname_p} (C) is gone -- the room looks for a new voice.")
        elif steady:
            lines.append(f"{tname_p} was dealt. {_name(cap)} steadied the room.")
        else:
            lines.append(f"{tname_p} was dealt. The room feels it.")
        if clique is not None:
            lines.append(f"The {clique['name'].lower()} take it hardest.")

    if arriving is not None:
        aname = _name(arriving)
        # Best-fit clique: nationality match first, then tenure.
        best = None
        anat = str(getattr(arriving, "nationality", "") or "")
        for c in form_cliques(team):
            if c["nationality"] == anat:
                best = c
                break
        try:
            gp = int(getattr(arriving, "stats", None)
                     and getattr(arriving.stats, "games_played", 0) or 0)
        except Exception:
            gp = 0
        try:
            dr["arrivals"][_pid(arriving)] = {"gp_at_arrival": gp}
        except Exception:
            pass
        if best is not None:
            _bump(arriving, -2)
            lines.append(f"{aname} lands with the {best['name'].lower()} -- "
                         f"familiar faces help.")
        else:
            _bump(arriving, -6)
            lines.append(f"{aname} arrives an outsider. The room will "
                         f"decide about him.")

    for ln in lines:
        _log(team, (f"[{date_str}] " if date_str else "") + ln)
    return lines


def integration_of(team: Any, player: Any) -> int:
    """How settled an arrival is (0-100). Grows ~8 pts per game played."""
    dr = ensure_dressing_room_fields(team)
    rec = dr["arrivals"].get(_pid(player))
    if not rec:
        return 100
    try:
        gp_now = int(getattr(player, "stats", None)
                     and getattr(player.stats, "games_played", 0) or 0)
        played = max(0, gp_now - int(rec.get("gp_at_arrival", 0)))
    except Exception:
        played = 0
    base = 25 if clique_of(team, player) is None else 60
    return _clamp(base + played * 8, 0, 100)


def _event_player_names(event: Any):
    """Yield candidate player-name strings from a media event payload.

    media_system.py is inconsistent: some events are plain dicts, others
    are MediaEvent dataclasses carrying a ``details`` dict. Trade events
    name players under list keys (``traded_players``/``received_players``),
    signings under ``player``. This normalizes every shape the backend
    actually produces.
    """
    data = event
    if not isinstance(data, dict):
        try:
            data = getattr(event, "details", None)
        except Exception:
            data = None
    if not isinstance(data, dict):
        return
    for key in ("player_name", "player", "target", "subject"):
        try:
            v = data.get(key)
        except Exception:
            v = None
        if isinstance(v, str) and v.strip():
            yield v.strip()
    for key in ("players_involved", "traded_players", "received_players",
                "players"):
        try:
            v = data.get(key)
        except Exception:
            v = None
        if isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str) and item.strip():
                    yield item.strip()


def cascade_on_press(team: Any, event: Any,
                     response_choice: str) -> List[str]:
    """Press answers ripple through the room -- individuals AND groups."""
    lines: List[str] = []
    roster = _roster(team)
    if not roster:
        return lines
    by_name = {_name(p).lower(): p for p in roster}
    target = None
    for cand in _event_player_names(event):
        if cand.lower() in by_name:
            target = by_name[cand.lower()]
            break

    def _clique_bump(player: Any, delta: float) -> None:
        c = clique_of(team, player)
        if c is None:
            return
        for p in roster:
            if p is not player and _pid(p) in c["member_ids"]:
                _bump(p, delta)

    rc = str(response_choice or "").lower()
    if rc == "critical" and target is not None:
        _bump(target, -6)
        _clique_bump(target, -3)
        lines.append(f"You hung {_name(target)} out to dry. His group noticed.")
    elif rc == "supportive" and target is not None:
        _bump(target, 4)
        _clique_bump(target, 2)
        lines.append(f"Backing {_name(target)} publicly lifted his corner of the room.")
    elif rc == "confident":
        for p in roster:
            _bump(p, 2)
        cap = captain_of(team)
        if cap is not None and influence_of(cap) >= 70:
            for p in roster:
                _bump(p, 1)
            lines.append(f"Confident words, and {_name(cap)} echoed them. Room +.")
        else:
            lines.append("Confident words in front of the cameras. Room +.")
    elif rc in ("dismissive", "hostile"):
        for p in roster:
            _bump(p, -2)
        lines.append("The room saw the brush-off. Nobody loves a siege -- yet.")
    elif rc == "controversial":
        if target is not None:
            _bump(target, -4)
            _clique_bump(target, -2)
        for p in roster:
            _bump(p, -1)
        lines.append("A controversial answer always costs someone in the room.")
    elif rc in ("professional", "thoughtful", "diplomatic"):
        lines.append("A calm, professional answer. The room barely blinked.")

    for ln in lines:
        _log(team, ln)
    return lines


# --------------------------------------------------------------------------
# Team talks -> momentum
# --------------------------------------------------------------------------

def _coach_influence(team: Any) -> int:
    """Head-coach influence (1-100). Mirrors the engagement foundation."""
    try:
        staff = list(getattr(team, "staff", []) or [])
        for s in staff:
            role = str(getattr(s, "role", "")).upper()
            if "HEAD" in role and "COACH" in role:
                return _clamp(getattr(s, "influence", 65) or 65, 40, 99)
        if staff:
            return _clamp(getattr(staff[0], "influence", 65) or 65, 40, 99)
    except Exception:
        pass
    return 65


def give_talk(team: Any, tone: str, context: Dict[str, Any],
              speaker: str = "coach", rng: Any = None) -> Dict[str, Any]:
    """Deliver a team talk. Returns the outcome dict and queues momentum.

    tone: calm | fired-up | cautious.
    context: {situation: pregame|intermission, score_state:
              leading|trailing|tied, rival: bool, streak: int}.
    speaker: coach | captain.
    Outcome tiers: landed (+2) / steady (+1) / flat (0) / backfired (-1).
    """
    rng = rng or random
    tone = tone if tone in TONES else "calm"
    score_state = str(context.get("score_state", "tied"))
    situation = str(context.get("situation", "pregame"))

    if speaker == "captain":
        cap = captain_of(team)
        speaker_inf = influence_of(cap) if cap is not None else 50
        speaker_name = _name(cap) if cap is not None else "the captain"
    else:
        speaker_inf = _coach_influence(team)
        speaker_name = "the coach"

    fit = TONE_FIT.get((tone, score_state), 55)
    # Losing streaks crave calm; rivalry games crave fire.
    try:
        streak = int(context.get("streak", 0) or 0)
    except Exception:
        streak = 0
    if streak <= -2 and tone == "calm":
        fit = min(100, fit + 12)
    if context.get("rival") and tone == "fired-up" and situation == "pregame":
        fit = min(100, fit + 12)
    # A fired-up talk when comfortably ahead reads as panic.
    if score_state == "leading" and tone == "fired-up":
        fit = max(5, fit - 10)

    effectiveness = (0.55 * speaker_inf + 0.45 * fit
                     + rng.uniform(-10, 10))
    if effectiveness >= 78:
        outcome, boost, room = "landed", 2, 3
        note = "The room is buzzing."
    elif effectiveness >= 55:
        outcome, boost, room = "steady", 1, 1
        note = "Nods around the room."
    elif effectiveness >= 35:
        outcome, boost, room = "flat", 0, 0
        note = "It didn't quite land."
    else:
        outcome, boost, room = "backfired", -1, -2
        note = "A few eye-rolls. Wrong tone, wrong moment."

    # The room absorbs it.
    for p in _roster(team):
        _bump(p, room)

    dr = ensure_dressing_room_fields(team)
    record = {"tone": tone, "speaker": speaker, "speaker_name": speaker_name,
              "outcome": outcome, "boost": boost, "note": note,
              "context": dict(context)}
    try:
        if situation == "intermission":
            dr["intermission"] = record
        else:
            dr["pregame"] = record
    except Exception:
        pass
    _log(team, f"{speaker_name.title()} gave a {tone} talk -- {outcome}. "
               f"{note}")
    return record


def auto_talk(team: Any, context: Dict[str, Any], rng: Any = None
              ) -> Dict[str, Any]:
    """The AI path: the coach addresses the room through give_talk().

    Same mechanics as a user talk -- tone chosen by a simple read of the
    situation, effectiveness from real coach influence.
    """
    rng = rng or random
    state = str(context.get("score_state", "tied"))
    situation = str(context.get("situation", "pregame"))
    if state == "trailing":
        tone = "fired-up"
    elif state == "leading":
        tone = "cautious" if situation == "intermission" else "calm"
    else:
        tone = "calm"
    return give_talk(team, tone, context, speaker="coach", rng=rng)


def consume_pregame_boost(team: Any) -> int:
    """Read and clear the pending pre-game boost (sim calls this)."""
    dr = ensure_dressing_room_fields(team)
    talk = dr.get("pregame")
    if talk is None:
        talk = auto_talk(team, {"situation": "pregame", "score_state": "tied",
                               "rival": False, "streak": 0})
    try:
        dr["pregame"] = None
    except Exception:
        pass
    try:
        return int(talk.get("boost", 0))
    except Exception:
        return 0


def consume_intermission_boost(team: Any, score_diff: int = 0) -> int:
    """Read and clear the pending intermission boost (sim calls this)."""
    dr = ensure_dressing_room_fields(team)
    talk = dr.get("intermission")
    if talk is None:
        if score_diff > 0:
            state = "leading"
        elif score_diff < 0:
            state = "trailing"
        else:
            state = "tied"
        talk = auto_talk(team, {"situation": "intermission",
                               "score_state": state,
                               "rival": False, "streak": 0})
    try:
        dr["intermission"] = None
    except Exception:
        pass
    try:
        return int(talk.get("boost", 0))
    except Exception:
        return 0


def apply_pregame_talks(sim: Any) -> None:
    """Sim hook: read both rooms' pre-game words, nudge opening momentum.

    Called once at game start. Additive: nudge_momentum caps the swing.
    """
    try:
        home = getattr(sim, "home_team", None)
        away = getattr(sim, "away_team", None)
        if home is None or away is None:
            return
        import impact_system as _imp
    except Exception:
        return
    boosts = {}
    for team, is_home in ((home, True), (away, False)):
        try:
            boosts[is_home] = consume_pregame_boost(team)
        except Exception:
            boosts[is_home] = 0
    net = boosts.get(True, 0) - boosts.get(False, 0)
    try:
        if net > 0:
            for _ in range(min(2, net)):
                _imp.nudge_momentum(sim, home, strength=1.0)
        elif net < 0:
            for _ in range(min(2, -net)):
                _imp.nudge_momentum(sim, away, strength=1.0)
    except Exception:
        pass


def apply_intermission_talk(sim: Any) -> None:
    """Sim hook: second-intermission words nudge third-period momentum."""
    try:
        home = getattr(sim, "home_team", None)
        away = getattr(sim, "away_team", None)
        if home is None or away is None:
            return
        import impact_system as _imp
        diff = int(getattr(sim, "home_score", 0) or 0) - int(
            getattr(sim, "away_score", 0) or 0)
    except Exception:
        return
    boosts = {}
    for team, is_home in ((home, True), (away, False)):
        try:
            boosts[is_home] = consume_intermission_boost(
                team, score_diff=diff if is_home else -diff)
        except Exception:
            boosts[is_home] = 0
    net = boosts.get(True, 0) - boosts.get(False, 0)
    try:
        if net > 0:
            for _ in range(min(2, net)):
                _imp.nudge_momentum(sim, home, strength=1.0)
        elif net < 0:
            for _ in range(min(2, -net)):
                _imp.nudge_momentum(sim, away, strength=1.0)
    except Exception:
        pass
# --------------------------------------------------------------------------
# DressingRoomView -- the FM24-style dedicated screen
# --------------------------------------------------------------------------

class DressingRoomView(__import__("customtkinter").CTkFrame):
    """Dressing Room: hierarchy, social groups, team talks, room feed."""

    def __init__(self, parent, app=None):
        import customtkinter as ctk
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ctk = ctk
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None
        self.configure(fg_color=BG)

        self._tone_var = ctk.StringVar(value="calm")
        self._speaker_var = ctk.StringVar(value="coach")
        self._itone_var = ctk.StringVar(value="calm")
        self._ispeaker_var = ctk.StringVar(value="coach")
        self._rival_var = ctk.BooleanVar(value=False)

        self._create_interface()
        self.refresh()
        try:
            self.app.open_windows["dressing_room"] = self
        except Exception:
            pass

    # -- lifecycle ------------------------------------------------------
    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _on_closing(self):
        try:
            if "dressing_room" in self.app.open_windows:
                del self.app.open_windows["dressing_room"]
        except Exception:
            pass
        self.close_view()

    def _team(self):
        return getattr(self.app, "user_team", None)

    # -- layout ---------------------------------------------------------
    def _make_card(self, parent, title):
        ctk = self._ctk
        ct = self._ct
        card = ctk.CTkFrame(parent, fg_color=ct["CARD"], corner_radius=10,
                            border_width=1, border_color=ct["BORDER"])
        self._heading(card, text=title, size=14).pack(anchor="w", padx=12,
                                                     pady=(8, 4))
        return card

    def _create_interface(self):
        ctk = self._ctk
        ct = self._ct
        main = ctk.CTkFrame(self, fg_color=ct["BG"])
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        header = ctk.CTkFrame(main, fg_color=ct["PANEL"], corner_radius=10)
        header.pack(fill="x", pady=(0, 10))
        self._heading(header, text="Dressing Room").pack(side="left", padx=16,
                                                        pady=10)
        self.header_mood = ctk.CTkLabel(header, text="",
                                       font=("Segoe UI", 15, "bold"))
        self.header_mood.pack(side="right", padx=16, pady=10)
        self.header_line = ctk.CTkLabel(header, text="", font=("Segoe UI", 12),
                                        text_color=ct["TEXT_DIM"])
        self.header_line.pack(side="left", padx=8, pady=10)

        # Row 1: hierarchy | team talk
        row1 = ctk.CTkFrame(main, fg_color=ct["BG"])
        row1.pack(fill="both", expand=True, pady=(0, 10))

        hier_card = self._make_card(row1, "Hierarchy")
        hier_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.hier_scroll = ctk.CTkScrollableFrame(hier_card, fg_color=ct["CARD"])
        self.hier_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        talk_card = self._make_card(row1, "Team Talk")
        talk_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.talk_body = ctk.CTkFrame(talk_card, fg_color=ct["CARD"])
        self.talk_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_talk_ui(self.talk_body, pregame=True)

        # Row 2: social groups | intermission + feed
        row2 = ctk.CTkFrame(main, fg_color=ct["BG"])
        row2.pack(fill="both", expand=True)

        sg_card = self._make_card(row2, "Social Groups")
        sg_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.sg_scroll = ctk.CTkScrollableFrame(sg_card, fg_color=ct["CARD"])
        self.sg_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = ctk.CTkFrame(row2, fg_color=ct["BG"])
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        italk_card = self._make_card(right, "Intermission Talk (3rd period)")
        italk_card.pack(fill="x", pady=(0, 10))
        self.italk_body = ctk.CTkFrame(italk_card, fg_color=ct["CARD"])
        self.italk_body.pack(fill="x", padx=8, pady=(0, 8))
        self._build_talk_ui(self.italk_body, pregame=False)

        feed_card = self._make_card(right, "Room Feed")
        feed_card.pack(fill="both", expand=True)
        self.feed_label = ctk.CTkLabel(feed_card, text="", justify="left",
                                       anchor="nw", font=("Segoe UI", 11),
                                       wraplength=430)
        self.feed_label.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    def _build_talk_ui(self, parent, pregame=True):
        ctk = self._ctk
        ct = self._ct
        tone_var = self._tone_var if pregame else self._itone_var
        speaker_var = self._speaker_var if pregame else self._ispeaker_var

        ctk.CTkLabel(parent, text="Tone:", font=("Segoe UI", 11),
                     text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=4,
                                                    pady=(4, 0))
        ctk.CTkSegmentedButton(parent, values=list(TONES),
                               variable=tone_var).pack(anchor="w", padx=4,
                                                       pady=4)
        ctk.CTkLabel(parent, text="Speaker:", font=("Segoe UI", 11),
                     text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=4)
        ctk.CTkSegmentedButton(parent, values=["coach", "captain"],
                               variable=speaker_var).pack(anchor="w", padx=4,
                                                          pady=4)
        if pregame:
            ctk.CTkCheckBox(parent, text="Rivalry game",
                            variable=self._rival_var).pack(anchor="w", padx=4,
                                                          pady=4)
        btn_row = ctk.CTkFrame(parent, fg_color=ct["CARD"])
        btn_row.pack(fill="x", pady=6)
        label = "Give pre-game talk" if pregame else "Queue intermission talk"
        cmd = self._give_pregame_talk if pregame else self._give_intermission_talk
        self._primary_button(btn_row, text=label, command=cmd).pack(
            side="left", padx=4)
        result = ctk.CTkLabel(btn_row, text="", font=("Segoe UI", 11),
                              wraplength=260, justify="left")
        result.pack(side="left", padx=8)
        if pregame:
            self.talk_result = result
        else:
            self.italk_result = result
        pending = ctk.CTkLabel(parent, text="", font=("Segoe UI", 11, "italic"),
                               text_color=ct["GOLD"], wraplength=380,
                               justify="left")
        pending.pack(anchor="w", padx=4, pady=(0, 4))
        if pregame:
            self.pregame_pending = pending
        else:
            self.intermission_pending = pending

    # -- actions ----------------------------------------------------------
    def _talk_context(self, situation):
        team = self._team()
        streak = 0
        try:
            streak = int(getattr(team, "streak", 0) or 0)
        except Exception:
            pass
        if streak <= -2:
            state = "trailing"
        elif streak >= 3:
            state = "leading"
        else:
            state = "tied"
        try:
            rival = bool(self._rival_var.get())
        except Exception:
            rival = False
        return {"situation": situation, "score_state": state,
                "rival": rival, "streak": streak}

    def _give_pregame_talk(self):
        team = self._team()
        if team is None:
            return
        try:
            tone = self._tone_var.get()
            speaker = self._speaker_var.get()
        except Exception:
            tone, speaker = "calm", "coach"
        outcome = give_talk(team, tone, self._talk_context("pregame"),
                            speaker=speaker)
        self._show_outcome(self.talk_result, outcome)
        self.refresh()

    def _give_intermission_talk(self):
        team = self._team()
        if team is None:
            return
        try:
            tone = self._itone_var.get()
            speaker = self._ispeaker_var.get()
        except Exception:
            tone, speaker = "calm", "coach"
        outcome = give_talk(team, tone, self._talk_context("intermission"),
                            speaker=speaker)
        self._show_outcome(self.italk_result, outcome)
        self.refresh()

    def _show_outcome(self, label, outcome):
        ct = self._ct
        colors = {"landed": ct["GREEN"], "steady": ct["TEXT"],
                  "flat": ct["GOLD"], "backfired": ct["RED"]}
        try:
            label.configure(
                text=f"{outcome['tone'].title()} talk {outcome['outcome']}: "
                     f"{outcome['note']}",
                text_color=colors.get(outcome["outcome"], ct["TEXT"]))
        except Exception:
            pass

    # -- refresh ----------------------------------------------------------
    def refresh(self):
        ctk = self._ctk
        ct = self._ct
        team = self._team()
        if team is None:
            return
        ensure_dressing_room_fields(team)

        mood = room_mood(team)
        cap = captain_of(team)
        try:
            self.header_mood.configure(
                text=f"Room mood {mood}/100",
                text_color=ct["GREEN"] if mood >= 70 else (
                    ct["GOLD"] if mood >= 50 else ct["RED"]))
            cap_line = f"Captain: {_name(cap)}" if cap is not None else "No captain"
            self.header_line.configure(text=f"{cap_line}  |  "
                                            f"{len(_roster(team))} players")
        except Exception:
            pass

        # Hierarchy rows with influence bars
        try:
            for w in self.hier_scroll.winfo_children():
                w.destroy()
            for row in hierarchy(team)[:24]:
                fr = ctk.CTkFrame(self.hier_scroll, fg_color="transparent")
                fr.pack(fill="x", pady=1)
                badge = row["letter"] if row["letter"] != "-" else " "
                ctk.CTkLabel(fr, text=badge, width=22,
                             font=("Segoe UI", 11, "bold"),
                             text_color=ct["GOLD"] if badge in "CA"
                             else ct["TEXT_FAINT"]).pack(side="left")
                ctk.CTkLabel(fr, text=row["name"], width=150, anchor="w",
                             font=("Segoe UI", 11)).pack(side="left")
                bar = ctk.CTkProgressBar(fr, width=90, height=8)
                bar.pack(side="left", padx=6)
                try:
                    bar.set(row["influence"] / 100.0)
                except Exception:
                    pass
                ctk.CTkLabel(fr, text=f"{row['influence']}  {row['tier']}",
                             font=("Segoe UI", 10),
                             text_color=ct["TEXT_DIM"]).pack(side="left")
        except Exception:
            pass

        # Social groups
        try:
            for w in self.sg_scroll.winfo_children():
                w.destroy()
            cliques = form_cliques(team)
            if not cliques:
                ctk.CTkLabel(self.sg_scroll,
                             text="No settled groups yet -- a room of "
                                  "individuals.",
                             font=("Segoe UI", 11),
                             text_color=ct["TEXT_DIM"]).pack(anchor="w",
                                                             pady=4)
            for c in cliques:
                fr = ctk.CTkFrame(self.sg_scroll, fg_color=ct["PANEL"],
                                  corner_radius=8)
                fr.pack(fill="x", pady=4, padx=2)
                ctk.CTkLabel(fr, text=f"{c['name']}  (mood {c['mood']})",
                             font=("Segoe UI", 11, "bold")).pack(anchor="w",
                                                                 padx=8,
                                                                 pady=(6, 0))
                ctk.CTkLabel(fr, text=", ".join(c["members"]),
                             font=("Segoe UI", 10),
                             text_color=ct["TEXT_DIM"],
                             wraplength=400,
                             justify="left").pack(anchor="w", padx=8,
                                                  pady=(0, 6))
            fl = floaters(team)
            if fl:
                ctk.CTkLabel(
                    self.sg_scroll,
                    text="Floaters: " + ", ".join(f["name"] for f in fl[:8]),
                    font=("Segoe UI", 10, "italic"),
                    text_color=ct["TEXT_FAINT"], wraplength=400,
                    justify="left").pack(anchor="w", pady=4)
            # New arrivals still integrating
            for p in _roster(team):
                integ = integration_of(team, p)
                if integ < 100:
                    ctk.CTkLabel(
                        self.sg_scroll,
                        text=f"{_name(p)} settling in: {integ}% integrated",
                        font=("Segoe UI", 10, "italic"),
                        text_color=ct["BLUE"]).pack(anchor="w", pady=1)
        except Exception:
            pass

        # Pending boosts
        try:
            dr = ensure_dressing_room_fields(team)
            pg = dr.get("pregame")
            self.pregame_pending.configure(
                text=(f"Queued for period 1: {pg['tone']} talk "
                      f"({pg['outcome']}, {pg['boost']:+d} momentum)")
                if pg else "No pre-game talk queued.")
            im = dr.get("intermission")
            self.intermission_pending.configure(
                text=(f"Queued for period 3: {im['tone']} talk "
                      f"({im['outcome']}, {im['boost']:+d} momentum)")
                if im else "No intermission talk queued.")
        except Exception:
            pass

        # Room feed
        try:
            dr = ensure_dressing_room_fields(team)
            lines = dr.get("mood_log", [])[-10:]
            self.feed_label.configure(
                text="\n".join(f"- {ln}" for ln in reversed(lines))
                if lines else "Quiet in here. Give it time.")
        except Exception:
            pass
