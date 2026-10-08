# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Televised draft lottery (additive, spectacle wave).

Real NHL rules (2022+): the bottom 11 teams by regular-season points are
eligible; two weighted draws decide #1 and #2 overall (the first-draw
winner is excluded from the second draw). Picks 3-16 fall by reverse
standings. A traded pick keeps its ORIGINAL team's lottery slot.

Public API:
- run_lottery(league, year, rng=None) -> reveal rows (picks 1..16), each
  {pick, team, original_team, odds_pct, movement}. Persists to
  league.lottery_results[year] (idempotent -- re-running returns the
  stored rows).
- lottery_reveal_text(rows) -> short plain-text summary for the inbox.
- LotteryRevealView(ctk.CTkFrame): the televised countdown, 16 -> 1,
  as a Tier-1 screen (show_screen "draft_lottery"). In-progress reveal
  progress writes through to app.pending_sessions["draft_lottery"].

Wiring:
- game_classes.League.simulate_draft_lottery delegates here (real odds);
  League.get_draft_order applies the round-1 reorder.
- main.py runs it on lottery day (May 8) and delivers the inbox card with
  a "watch the reveal" action; the reveal window routes into Draft
  Central when finished.
"""

import random
from typing import Any, Dict, List, Optional

try:
    import customtkinter as ctk
except ImportError:
    # Headless environments (sim bots, servers) don't have customtkinter.
    # The lottery logic (run_lottery/lottery_reveal_text) is pure Python;
    # only LotteryRevealView needs the GUI toolkit. Import must not fail
    # headless -- without this the offseason draft lottery is silently
    # skipped and the season-transition stalls.
    ctk = None

# Reverse-standings rank (1 = worst) -> odds %. Real NHL numbers.
LOTTERY_ODDS: List[float] = [
    25.5, 13.5, 11.5, 9.5, 8.5, 7.5, 6.5, 6.0, 5.0, 3.5, 3.0,
]

LOTTERY_DAY_MONTH = 5
LOTTERY_DAY_DAY = 8


def _team_name(t: Any) -> str:
    return getattr(t, "team_name", "") or ""


def _nhl_teams(league: Any) -> List[Any]:
    try:
        return [t for t in (getattr(league, "teams", []) or [])
                if getattr(t, "league_name", "") == "National Hockey League"]
    except Exception:
        return []


def _points(league: Any, team: Any) -> float:
    try:
        return float((getattr(league, "standings", {}) or {})
                     .get(_team_name(team), {}).get("Points", 0))
    except Exception:
        return 0.0


def _wins(league: Any, team: Any) -> int:
    try:
        return int((getattr(league, "standings", {}) or {})
                   .get(_team_name(team), {}).get("W", 0))
    except Exception:
        return 0


def _seed_key(league: Any, team: Any):
    """Lottery seeding: fewest points, then fewest wins.

    Real NHL breaks lottery ties by regulation wins; the game tracks
    only total W, so fewer total wins is the closest faithful proxy.
    Without this, ties fell back to roster order -- arbitrary odds."""
    return (_points(league, team), _wins(league, team))


def eligible_teams(league: Any) -> List[Any]:
    """Bottom 11 NHL teams by regular-season points (worst first)."""
    teams = _nhl_teams(league)
    teams.sort(key=lambda t: _seed_key(league, t))
    return teams[:11]


def _current_owner_name(league: Any, original_name: str, year: int) -> str:
    """Who actually selects with the original team's first-rounder."""
    try:
        for t in _nhl_teams(league):
            for p in (t.get_picks_for_year(year) or []):
                if getattr(p, "round", 0) == 1 and \
                   getattr(p, "original_team", "") == original_name:
                    # The trade engine tracks ownership on the pick itself
                    # (current_team); the pick object stays in the original
                    # club's list, so the dict holder is NOT the owner.
                    return (getattr(p, "current_team", "") or
                            _team_name(t))
    except Exception:
        pass
    return original_name


def _weighted_draw(cands: List[Any], weights: List[float],
                   rng: random.Random) -> Any:
    total = sum(weights)
    r = rng.uniform(0, total)
    upto = 0.0
    for c, w in zip(cands, weights):
        upto += w
        if r <= upto:
            return c
    return cands[-1]


def run_lottery(league: Any, year: int,
                rng: Optional[random.Random] = None) -> List[Dict[str, Any]]:
    """Run the lottery (or return the stored result). Real weighted odds."""
    rng = rng or random.Random()
    stored = getattr(league, "lottery_results", None) or {}
    if year in stored and stored[year]:
        return list(stored[year])

    elig = eligible_teams(league)
    if len(elig) < 2:
        return []

    odds = LOTTERY_ODDS[:len(elig)]
    first = _weighted_draw(elig, odds, rng)
    rest = [t for t in elig if t is not first]
    rest_odds = [odds[elig.index(t)] for t in rest]
    # Renormalize the second draw over the remaining teams.
    second = _weighted_draw(rest, rest_odds, rng)

    # Reverse-standings rank among ALL NHL teams (pre-lottery pick).
    # Same tiebreak as eligibility so pre_rank and odds agree on ties.
    all_sorted = sorted(_nhl_teams(league),
                        key=lambda t: _seed_key(league, t))
    pre_rank = {_team_name(t): i + 1 for i, t in enumerate(all_sorted)}

    winners = [_team_name(first), _team_name(second)]
    # Picks 3-16: remaining teams by reverse standings.
    tail = [_team_name(t) for t in all_sorted
            if _team_name(t) not in winners][:14]

    rows: List[Dict[str, Any]] = []
    _elig_names = [_team_name(t) for t in elig]
    for pos, name in enumerate(winners + tail, start=1):
        pre = pre_rank.get(name, pos)
        try:
            odds_pct = odds[_elig_names.index(name)]
        except ValueError:
            odds_pct = 0.0  # picks 12-16 by standings: outside the lottery
        rows.append({
            "pick": pos,
            "team": _current_owner_name(league, name, year),
            "original_team": name,
            "odds_pct": round(odds_pct, 1),
            "movement": pre - pos,  # + = jumped up
        })

    try:
        if getattr(league, "lottery_results", None) is None:
            league.lottery_results = {}
        league.lottery_results[year] = [dict(r) for r in rows]
    except Exception:
        pass
    return rows


def lottery_reveal_text(rows: List[Dict[str, Any]], year: int) -> str:
    """Plain-text summary for the inbox card."""
    if not rows:
        return "The draft lottery could not be held."
    lines = [f"The {year} NHL Draft Lottery is complete. The televised "
             f"reveal ran down from 16 to 1:"]
    for r in rows:
        mv = r["movement"]
        arrow = f" (+{mv} ▲)" if mv > 0 else (f" ({mv} ▼)" if mv < 0 else "")
        lines.append(f"#{r['pick']}: {r['team']}{arrow}")
    return "\n".join(lines)


def reaction_line(row: Dict[str, Any]) -> str:
    """One televised reaction line for a revealed pick.

    House grammar: no emoji, no double-dash. Movement is carried by the
    +/- number (never color alone) on the results board.
    """
    mv, team, pick = row["movement"], row["team"], row["pick"]
    if pick == 1:
        return f"{team} wins the lottery \u2014 #1 overall!"
    if pick == 2:
        return f"{team} takes #2 \u2014 the consolation prize nobody hates."
    if mv >= 5:
        return f"{team} leaps {mv} spots to #{pick} \u2014 the room erupts!"
    if mv >= 2:
        return f"{team} jumps to #{pick} (+{mv})."
    if mv <= -3:
        return f"{team} slides to #{pick} ({mv}) \u2014 groans in the war room."
    if mv < 0:
        return f"{team} falls to #{pick}."
    return f"{team} holds at #{pick}."


def apply_user_reactions(app: Any, rows: List[Dict[str, Any]]) -> None:
    """Fan/room teeth for the user's team (light, via the dynamics feed)."""
    try:
        user = getattr(app, "user_team", None)
        if user is None:
            return
        uname = _team_name(user)
        mine = [r for r in rows if r["team"] == uname or
                r["original_team"] == uname]
        if not mine:
            return
        from reputation_system import record_team_event
        for r in mine:
            mv = r["movement"]
            if r["pick"] == 1:
                record_team_event(user, "draft_lottery",
                                  f"Won the draft lottery -- selecting #1 "
                                  f"overall!", morale_delta=2, tone="up")
            elif mv >= 4:
                record_team_event(user, "draft_lottery",
                                  f"Jumped {mv} spots to #{r['pick']} in the "
                                  f"lottery.", morale_delta=1, tone="up")
            elif mv <= -3:
                record_team_event(user, "draft_lottery",
                                  f"Slid to #{r['pick']} in the lottery "
                                  f"({mv}).", morale_delta=-1, tone="down")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# The televised reveal window
# ---------------------------------------------------------------------------

# LotteryRevealView base: ctk.CTkFrame when the GUI toolkit is present,
# plain object headless (the view is never instantiated without a GUI --
# the lottery sim logic above doesn't touch it).
_LotteryRevealViewBase = ctk.CTkFrame if ctk is not None else object


class LotteryRevealView(_LotteryRevealViewBase):
    """Broadcast-style countdown reveal, picks 16 -> 1, as a Tier-1 screen.

    Same televised countdown behavior as the old InGamePopup window, now
    embedded via ``HockeyManagerGUI.show_screen("draft_lottery", ...)``.
    In-progress state (revealed picks) writes through to a thin Tier-B
    session (``app.pending_sessions["draft_lottery"]``); the canonical
    rows persist on ``league.lottery_results[year]``.
    """

    def __init__(self, parent, year, rows, on_done=None, app=None):
        import tkinter as tk
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen()
        self._year = year
        self._rows = list(rows)
        self._on_done = on_done
        # Reveal order: 16..3, then the #2/#1 drama.
        tail = [r for r in self._rows if r["pick"] >= 3]
        head = [r for r in self._rows if r["pick"] < 3]
        tail.sort(key=lambda r: -r["pick"])
        head.sort(key=lambda r: -r["pick"])
        self._queue = tail + head
        self._revealed: List[Dict[str, Any]] = []
        self._timers: List[str] = []

        # Thin Tier-B session (write-through as picks are revealed).
        self._session_id = "draft_lottery"
        self._write_session(complete=False)

        # Job 3 polish: full house-grammar restyle on the shared card
        # components (ctk_theme). No emoji headings, no double-dash,
        # body text at the 12px floor through ui_scale.
        # (customtkinter is imported at module level.)
        from ctk_theme import (init_ctk_theme, heading, body, primary_button,
                               secondary_button, wire_focus_ring,
                               PANEL, BORDER, GOLD)
        from ui_scale import scaled
        init_ctk_theme()
        self.configure(fg_color="transparent")

        # Controls pinned to the bottom of the screen. Packed BEFORE the
        # scroll frame so the packer docks them first and the scroll gets
        # only the remaining cavity -- never drawn underneath the bar.
        # Creation order = keyboard tab order.
        ctrls = ctk.CTkFrame(self, fg_color="transparent")
        ctrls.pack(fill="x", side="bottom", padx=24, pady=(8, 14))
        self._skip_btn = secondary_button(
            ctrls, text="Skip to results", command=self._skip)
        self._skip_btn.pack(side="left")
        rc = ctk.CTkFrame(ctrls, fg_color="transparent")
        rc.pack(side="right")
        self._close_btn = secondary_button(
            rc, text="Close", command=self._close)
        self._close_btn.pack(side="left")
        self._draft_btn = primary_button(
            rc, text="Open Draft Central", command=self._open_draft,
            state="disabled")
        self._draft_btn.pack(side="left", padx=(10, 0))
        for _b in (self._skip_btn, self._close_btn, self._draft_btn):
            wire_focus_ring(_b)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(18, 4))
        heading(hdr, "NHL Draft Lottery", size=22).pack(anchor="w")
        body(hdr, f"{year} \u00b7 The televised reveal \u00b7 picks 16 to 1",
             dim=True, size=12).pack(anchor="w", pady=(2, 0))

        # Stage: the current pick.
        stage = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=12,
                             border_width=1, border_color=BORDER)
        stage.pack(fill="x", padx=24, pady=8)
        self._pick_var = tk.StringVar(value="\u2026")
        self._team_var = tk.StringVar(
            value="The balls are in the machine\u2026")
        self._detail_var = tk.StringVar(value="")
        heading(stage, "", size=32, text_color=GOLD,
                textvariable=self._pick_var).pack(pady=(14, 0))
        heading(stage, "", size=16, textvariable=self._team_var,
                wraplength=scaled(560)).pack(pady=2)
        body(stage, "", size=12, dim=True, textvariable=self._detail_var,
             wraplength=scaled(560), justify="center").pack(pady=(0, 14))

        # Results board (fills as revealed).
        body(scroll, "Results", dim=True, size=12).pack(
            anchor="w", padx=24, pady=(10, 4))
        results_card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=12)
        results_card.pack(fill="x", padx=24, pady=(0, 8))
        self._results_inner = ctk.CTkFrame(results_card,
                                           fg_color="transparent")
        self._results_inner.pack(fill="x", padx=8, pady=8)

        self._next()

    # -- Tier-B session ---------------------------------------------------
    def _write_session(self, complete=False):
        try:
            from popup_system import get_pending_session
            sess = get_pending_session(self.app, self._session_id)
            if sess is not None:
                sess.update(
                    kind="draft_lottery",
                    screen_id=self._session_id,
                    title=f"NHL Draft Lottery {self._year}",
                    year=self._year,
                    revealed=[r["pick"] for r in self._revealed],
                    complete=bool(complete),
                )
        except Exception:
            pass

    def _clear_session(self):
        try:
            sessions = getattr(self.app, "pending_sessions", None)
            if isinstance(sessions, dict):
                sessions.pop(self._session_id, None)
        except Exception:
            pass

    # -- reveal driver ----------------------------------------------------
    def _after(self, ms, fn):
        try:
            self._timers.append(self.after(ms, fn))
        except Exception:
            fn()

    def _next(self):
        if not self._queue:
            self._finale()
            return
        row = self._queue.pop(0)
        self._revealed.append(row)
        mv = row["movement"]
        arrow = f"  +{mv} ▲" if mv > 0 else (f"  {mv} ▼" if mv < 0 else "")
        odds = (f"{row['odds_pct']:.1f}% odds" if row["odds_pct"] > 0
                else "outside the lottery")
        self._pick_var.set(f"Pick {row['pick']}")
        self._team_var.set(row["team"])
        self._detail_var.set(f"{odds}{arrow}\n{reaction_line(row)}")
        self._board_append(row)
        self._write_session(complete=False)
        pause = 4200 if row["pick"] == 2 else 2300
        self._after(pause, self._next)

    def _board_append(self, row):
        # One house-grammar row per revealed pick: gold pick number, team,
        # and a signed movement figure -- never color alone.
        from ctk_theme import heading, body, GOLD, GREEN, RED, TEXT_DIM
        mv = row["movement"]
        if mv > 0:
            mv_txt, mv_color = f"+{mv}", GREEN
        elif mv < 0:
            mv_txt, mv_color = f"{mv}", RED
        else:
            mv_txt, mv_color = "\u2014", TEXT_DIM
        try:
            r = ctk.CTkFrame(self._results_inner, fg_color="transparent")
        except Exception:
            return
        r.pack(fill="x", pady=2)
        heading(r, f"#{row['pick']}", size=12,
                text_color=GOLD).pack(side="left", padx=(8, 10))
        label = row["team"]
        body(r, label, size=12).pack(side="left")
        body(r, mv_txt, size=12, text_color=mv_color).pack(
            side="right", padx=8)

    def _skip(self):
        for t in self._timers:
            try:
                self.after_cancel(t)
            except Exception:
                pass
        self._timers = []
        while self._queue:
            row = self._queue.pop(0)
            self._revealed.append(row)
            self._board_append(row)
        self._finale()

    def _finale(self):
        self._pick_var.set("Lottery complete")
        top = next((r for r in self._revealed if r["pick"] == 1), None)
        self._team_var.set(
            f"{top['team']} selects #1 overall" if top else "")
        self._detail_var.set(
            "The order is set. Time to plan the draft.")
        try:
            self._draft_btn.configure(state="normal")
        except Exception:
            pass
        self._write_session(complete=True)
        if self._on_done:
            try:
                self._on_done()
            except Exception:
                pass
        # The reveal is finished: no in-progress state remains.
        self._clear_session()

    def _set_busy(self, busy, busy_text="Opening\u2026"):
        """Honest loading state for the Draft Central handoff.

        While Draft Central builds, the buttons are visibly disabled
        (never dead-clickable); on error they recover so the user can
        retry or close. Never raises.
        """
        try:
            if busy:
                self._skip_btn.configure(state="disabled")
                self._close_btn.configure(state="disabled")
                self._draft_btn.configure(state="disabled",
                                          text=busy_text)
                # Paint the busy state synchronously before the
                # (synchronous) handoff runs.
                self.update_idletasks()
            else:
                self._skip_btn.configure(state="normal")
                self._close_btn.configure(state="normal")
                self._draft_btn.configure(state="normal",
                                          text="Open Draft Central")
        except Exception:
            pass

    def _open_draft(self):
        self._set_busy(True)
        try:
            fn = getattr(self.app, "open_draft_day_central", None)
            if fn:
                fn()
        except Exception:
            # Error case recovers: buttons come back, user can retry.
            self._set_busy(False)
            return
        self._close()

    def _close(self):
        for t in self._timers:
            try:
                self.after_cancel(t)
            except Exception:
                pass
        self._clear_session()
        # Screen mode: return to the dashboard; the timers are cancelled
        # above so nothing keeps running after navigation.
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            try:
                fn()
                return
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass
