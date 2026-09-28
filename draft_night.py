"""Draft night systems for Puck Dynasty: ticker, pick valuation, draft grades.

Pure logic, no GUI. Powers the Entry Draft war room.
"""
from __future__ import annotations

import hashlib
import random
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Ticker commentary
# ---------------------------------------------------------------------------

TICKER_TEMPLATES = [
    "Pick #{pick}: {team} select {player} ({pos}).",
    "#{pick} — {player} is off the board to {team}.",
    "{team} take {player} at #{pick}.",
    "With the #{pick} pick, {team} grab {pos} {player}.",
    "{player} heads to {team} at #{pick}.",
    "Draft floor buzz: {team} love {player}'s upside at #{pick}.",
    "#{pick}: {team} go with {player}.",
]

STEAL_TEMPLATES = [
    "{player} at #{pick} could be the steal of the draft for {team}.",
    "Great value for {team}: {player} slips to #{pick}.",
]

REACH_TEMPLATES = [
    "Bold move: {team} reach for {player} at #{pick}.",
    "A surprise at #{pick} — {team} take {player} earlier than expected.",
]


def ticker_line(overall: int, team_name: str, player, round_num: int,
                reach: bool = False, steal: bool = False, rng=None) -> str:
    """One ticker line for a completed pick.

    rng: an optional random.Random (or the random module). The war room
    passes its per-draft RNG so replays are deterministic; headless callers
    may pass a seeded RNG. None = legacy global-random behavior.
    """
    _r = rng if rng is not None else random
    try:
        pos = player.primary_position.value
    except Exception:
        pos = "?"
    name = getattr(player, 'full_name', str(player))
    if steal:
        tpl = _r.choice(STEAL_TEMPLATES)
    elif reach:
        tpl = _r.choice(REACH_TEMPLATES)
    else:
        tpl = _r.choice(TICKER_TEMPLATES)
    return tpl.format(pick=overall, team=team_name, player=name, pos=pos,
                      round=round_num)


# ---------------------------------------------------------------------------
# Pick + player valuation for grades and draft-day trades
# ---------------------------------------------------------------------------

def pick_slot_value(overall: int) -> int:
    """Expected value of a draft slot by overall pick number."""
    if overall < 1:
        return 50
    return max(20, int(3000 * (0.965 ** (overall - 1))))


_POT_VALUES = {'F': 60, 'D': 170, 'C-': 320, 'C': 520, 'C+': 850,
               'B-': 1250, 'B': 1850, 'B+': 2650,
               'A-': 3700, 'A': 5100, 'A+': 7200}


def drafted_player_value(player) -> int:
    grade = getattr(player, 'potential_grade', 'C') or 'C'
    base = _POT_VALUES.get(grade.strip(), 520)
    try:
        base += max(0, (player.overall_rating() - 35) * 8)
    except Exception:
        pass
    return base


def draft_grades(picks_made: List[Tuple[str, int, object]]) -> List[Tuple[str, str, float]]:
    """Grade every team's draft. Returns [(team, grade, score)] sorted best-first."""
    by_team: Dict[str, List[Tuple[int, object]]] = {}
    for team_name, overall, player in picks_made:
        by_team.setdefault(team_name, []).append((overall, player))
    ratios = []
    for team_name, picks in by_team.items():
        expected = sum(pick_slot_value(o) for o, _ in picks)
        actual = sum(drafted_player_value(p) for _, p in picks)
        ratios.append((team_name, (actual / expected) if expected else 1.0))
    ratios.sort(key=lambda r: r[1], reverse=True)
    # Curve grades by percentile so the spread is always meaningful
    n = len(ratios)
    results = []
    for i, (team_name, ratio) in enumerate(ratios):
        pct = i / max(1, n - 1)
        if pct <= 0.10:
            grade = 'A+'
        elif pct <= 0.30:
            grade = 'A'
        elif pct <= 0.45:
            grade = 'B+'
        elif pct <= 0.60:
            grade = 'B'
        elif pct <= 0.75:
            grade = 'C'
        elif pct <= 0.90:
            grade = 'D'
        else:
            grade = 'F'
        results.append((team_name, grade, ratio))
    return results


def grade_color(grade: str) -> str:
    return {'A+': '#46c93a', 'A': '#46c93a', 'B+': '#7bd747', 'B': '#a3d84b',
            'C': '#e8b93c', 'D': '#d97f3c', 'F': '#e74c3c'}.get(grade, '#e8ecf4')


# ---------------------------------------------------------------------------
# Shared draft conductor (war room AI + headless auto-draft use ONE path)
# ---------------------------------------------------------------------------

def stable_draft_seed(draft_year, salt="") -> int:
    """Deterministic per-draft seed, stable across processes (unlike
    hash() of str, which is salted per run). One seed per draft; every
    slot draws from the same RNG, so a replay with the same seed is
    deterministic without removing any within-draft uncertainty."""
    h = hashlib.sha256(
        f"entry-draft:{draft_year}:{salt}".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


def ai_select_prospect(team, available, team_board, needs, round_num,
                       priority, rng, overall=1):
    """The canonical AI pick selection. Shared by the war room's
    _do_ai_pick and the headless conductor -- one implementation, so the
    sim and the interactive draft can't diverge.

    team: the picking Team. available: draft_prospects sorted by consensus
    draft_ranking, already re-entry filtered. team_board: the club's own
    board (or None -> consensus fallback). needs: positional needs list.
    round_num: 1-7. priority: franchise priority ('rebuild' etc, or None).
    rng: random.Random (never the global module in new code). overall: the
    pick's overall number, used for steal detection.

    Returns (selected, reach, steal). selected is None when available is
    empty.
    """
    if not available:
        return None, False, False
    # Candidates: top 12 *of the picking team's own board* (built once per
    # draft); prospects missing from the board fall behind everyone.
    # Consensus ordering is the fallback when boards are unavailable.
    candidates = available[:12]
    try:
        if team_board:
            _bidx = {getattr(_p, 'id', None): _i
                     for _i, _p in enumerate(team_board)}
            _n = len(team_board)
            candidates = sorted(
                available,
                key=lambda _p: (_bidx.get(getattr(_p, 'id', None), _n),
                                -getattr(_p, 'draft_ranking', 0)))[:12]
    except Exception:
        candidates = available[:12]
    try:
        from draft_day_trades import franchise_pick_multiplier as _fpm
    except Exception:
        _fpm = None
    scored = []
    for p in candidates:
        try:
            pos = p.primary_position.value
        except Exception:
            pos = "?"
        base = getattr(p, 'draft_ranking', 0) or 0
        if pos in (needs or [])[:2]:
            base *= 1.08
        if pos == 'G' and round_num <= 1:
            base *= 0.80  # goalies rarely go top-10
        # Franchise situation: contenders draft for readiness (higher
        # current overall), rebuilders draft for ceiling (potential
        # grade). Modest tilt -- BPA still rules the board.
        if _fpm is not None:
            try:
                base *= _fpm(p, priority)
            except Exception:
                pass
        try:
            base *= rng.uniform(0.94, 1.06)
        except Exception:
            base *= random.uniform(0.94, 1.06)
        scored.append((base, p))
    scored.sort(key=lambda s: s[0], reverse=True)
    selected = scored[0][1]
    # Reach / steal detection for the ticker
    try:
        idx = available.index(selected)
    except ValueError:
        idx = 0
    reach = idx >= 8
    steal = idx == 0 and overall >= 5
    return selected, reach, steal


def persist_draft_grades(league, draft_year, picks_made):
    """Grade the draft and persist to league.draft_grades_history (keyed by
    year) so the war room's review modal and future seasons can look back.
    Returns the grades list [(team, grade, ratio)]."""
    grades = draft_grades(picks_made)
    try:
        hist = getattr(league, 'draft_grades_history', None)
        if not isinstance(hist, dict):
            hist = {}
            league.draft_grades_history = hist
        hist[str(int(draft_year))] = [(t, g, float(r))
                                      for t, g, r in grades]
    except Exception:
        pass
    return grades


def _conducted_years(league):
    try:
        return set(getattr(league, 'draft_conducted_years', None) or [])
    except Exception:
        return set()


def mark_draft_conducted(league, draft_year):
    """Stamp a draft year as conducted (idempotency guard). Used by the
    war room's end_draft and the headless conductor alike."""
    try:
        done = _conducted_years(league)
        done.add(int(draft_year))
        league.draft_conducted_years = sorted(done)
    except Exception:
        pass


def conduct_entry_draft(league, draft_year, app=None, seed=None):
    """Conduct the entry draft with no UI -- the ONE headless conductor.

    Used by main's offseason tentpole (pure sim seasons) and the
    automated season flow (auto-advance). The war room (DraftView) is the
    interactive path; both pick through ai_select_prospect, so the sim
    and the war room can't diverge.

    Idempotent per draft year via league.draft_conducted_years: a draft
    the war room already completed (or an earlier tick) is a no-op.
    draft_year is authoritative when given; falls back to
    league.draft_prospects_year, then league.season_year.

    Returns picks_made [(team_name, overall, player)] with player objects
    (draft_grades-compatible). News: top 10 + the user's haul.
    """
    try:
        year = int(draft_year)
    except (TypeError, ValueError):
        year = None
    if year is None:
        try:
            year = int(getattr(league, 'draft_prospects_year', None)
                       or getattr(league, 'season_year', 0) or 0)
        except Exception:
            year = 0
    if not year:
        return []
    if year in _conducted_years(league):
        return []
    prospects = list(getattr(league, 'draft_prospects', None) or [])
    if not prospects:
        return []

    rng = random.Random(seed if seed is not None
                        else stable_draft_seed(year))

    # Draft order: post-lottery, post-draft-day-trades ownership.
    # get_draft_order returns (overall_pick, team, draft_pick); the ROUND
    # lives on draft_pick.round (1-7). The overall pick number is the
    # authoritative first element -- never the enumeration index.
    try:
        league.initialize_all_draft_picks()
    except Exception:
        pass
    order = []
    try:
        order = list(league.get_draft_order(year) or [])
    except Exception:
        order = []
    slots = []  # (overall, round_num, team, draft_pick)
    for overall, team, draft_pick in (order or []):
        try:
            round_num = int(getattr(draft_pick, 'round', 0) or 0)
        except Exception:
            round_num = 0
        try:
            draft_pick.overall_pick = overall
        except Exception:
            pass
        slots.append((overall, round_num, team, draft_pick))
    if not slots:
        standings = getattr(league, 'standings', None) or {}
        nhl = [t for t in getattr(league, 'teams', [])
               if getattr(t, 'league_name', '') == 'National Hockey League'] \
            or list(getattr(league, 'teams', []))
        by_pts = sorted(nhl, key=lambda t: standings.get(
            getattr(t, 'team_name', ''), {}).get('Points', 0))
        _o = 0
        for rnd in range(1, 8):
            for team in by_pts:
                _o += 1
                slots.append((_o, rnd, team, None))

    # Per-team boards, built ONCE per draft (same as the war room).
    boards = {}
    try:
        from team_draft_boards import build_draft_reports
        reports = build_draft_reports(
            league, [[rnd, t, dp] for _o, rnd, t, dp in slots]) or {}
        boards = {_n: _r.get('board', []) for _n, _r in reports.items()}
    except Exception:
        boards = {}

    try:
        import trade_engine as _te
    except Exception:
        _te = None
    ai_manager = getattr(app, 'ai_manager', None) if app is not None else None

    def _redraft_banned(team, player):
        try:
            banned_from = str(getattr(player, 'draft_reentry_from', '') or '')
            return bool(banned_from) and \
                banned_from == getattr(team, 'team_name', None)
        except Exception:
            return False

    def _priority_of(team):
        try:
            if ai_manager is not None:
                strat = ai_manager.get_team_strategy(
                    getattr(team, 'team_name', ''))
                return getattr(strat, 'priority', None)
        except Exception:
            pass
        return None

    pool = sorted(prospects,
                  key=lambda p: getattr(p, 'draft_ranking', 0), reverse=True)
    picks_made = []
    for overall, round_num, team, _dp in slots:
        if not pool:
            break
        tname = getattr(team, 'team_name', '')
        avail = [p for p in pool if not _redraft_banned(team, p)]
        if not avail:
            continue
        needs = []
        if _te is not None:
            try:
                needs = _te.team_needs(team) or []
            except Exception:
                needs = []
        selected, _reach, _steal = ai_select_prospect(
            team, avail, boards.get(tname), needs, round_num,
            _priority_of(team), rng, overall=overall)
        if selected is None:
            continue
        # --- state mutation (mirrors DraftView.execute_pick, minus UI) ---
        try:
            team.add_player(selected, 'prospects')
        except Exception:
            continue
        try:
            league.stamp_draft_rights(selected, tname, year)
        except Exception:
            pass
        try:
            selected.draft_reentry_from = ''
        except Exception:
            pass
        try:
            pool.remove(selected)
        except ValueError:
            pass
        picks_made.append((tname, overall, selected))

    if not picks_made:
        return []
    # What's left of the pool re-enters next year's draft (same as the
    # war room's end_draft); the one-draft re-draft ban is spent.
    try:
        for _p in pool:
            try:
                _p.draft_reentry_from = ''
            except Exception:
                pass
        league.undrafted_pool = list(pool)
    except Exception:
        pass
    try:
        league.draft_prospects = []
    except Exception:
        pass
    mark_draft_conducted(league, year)
    persist_draft_grades(league, year, picks_made)

    # News wire (established behavior): top 10 + the user's haul.
    try:
        _add_news = getattr(app, 'add_news', None) if app is not None else None
        if _add_news is not None:
            _lines = [f"#{ov} {getattr(p, 'full_name', '?')} ({tn})"
                      for tn, ov, p in picks_made[:10]]
            _user_name = getattr(getattr(app, 'user_team', None),
                                 'team_name', '')
            _user_picks = [f"#{ov} {getattr(p, 'full_name', '?')}"
                           for tn, ov, p in picks_made
                           if tn == _user_name][:7]
            _story = (f"The {year} NHL Entry Draft is complete. "
                      f"Top 10: " + "; ".join(_lines) + ".")
            if _user_picks:
                _story += " Your picks: " + "; ".join(_user_picks) + "."
            _add_news(_story)
    except Exception:
        pass
    return picks_made
