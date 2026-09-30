# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
                       priority, rng, overall=1, drafted=None):
    """The canonical AI pick selection. Shared by the war room's
    _do_ai_pick and the headless conductor -- one implementation, so the
    sim and the interactive draft can't diverge.

    team: the picking Team. available: draft_prospects sorted by consensus
    draft_ranking, already re-entry filtered. team_board: the club's own
    board (or None -> consensus fallback). needs: positional needs list.
    round_num: 1-7. priority: franchise priority ('rebuild' etc, or None).
    rng: random.Random (never the global module in new code). overall: the
    pick's overall number, used for steal detection. drafted: optional
    list of (position_value, round_num) tuples this team already picked
    in this draft -- drives the dynamic need pivot (None -> no pivot).

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
            # Need-boost decays by round: full 1.08x in round 1, fading to
            # pure BPA by round 4. A flat boost beats the ±6% noise every
            # round, so a persistent hole got drafted 7 straight times
            # (playtest P-4: 13 of 14 Toronto picks were RW).
            _decay = 1.0 + 0.08 * max(0.0, (4 - round_num) / 3.0)
            # Dynamic pivot: a need filled earlier in THIS draft stops
            # pulling. First pick at the position keeps full boost; a
            # second keeps half (2-3 of a kind isn't insane -- wingers move
            # around the lineup); beyond that it's pure BPA. A round-1/2
            # pick counts double: one solid early pick fills the need.
            _filled = 0
            for _dp_pos, _dp_round in (drafted or []):
                if _dp_pos == pos:
                    try:
                        _filled += 2 if int(_dp_round) <= 2 else 1
                    except (TypeError, ValueError):
                        _filled += 1
            _pivot = 1.0 if _filled <= 0 else (0.5 if _filled == 1 else 0.0)
            base *= 1.0 + (_decay - 1.0) * _pivot
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


# ---------------------------------------------------------------------------
# League-owned war-room session (BUG-2 fix, 2026-09-30)
#
# The interactive entry draft's mutable state -- the pick order with live
# owners, the cursor, the committed pick log, the per-team boards and the
# per-draft RNG stream -- lives here, on the league
# (league.entry_draft_session), never on the DraftView. Destroying the
# view detaches; a rebuilt view re-attaches and resumes exactly where the
# draft left off, instead of starting a fresh draft (which silently
# restarted the order, duplicated picks and orphaned prospects).
#
# Picks commit transactionally: record_pick() is idempotent per overall
# pick number, so re-entry or a double event can never double-process a
# slot. Boards persist as prospect-id orderings (never re-rolled), and
# the RNG stream persists via getstate/setstate, so a resumed draft
# continues the exact same draft rather than a lookalike.
# ---------------------------------------------------------------------------

class EntryDraftSession:
    """League-owned journal of an in-progress entry-draft war room."""

    VERSION = 1

    def __init__(self):
        self.year = 0
        # slots: [{overall:int, round:int, owner:str (team name),
        #          pick_id:str|None (game_classes DraftPick.id)}]
        self.slots = []
        self.current_pick = 0  # index into slots
        # picks: [{overall:int, team:str, player_id}] committed, in order
        self.picks = []
        # boards: {team_name: [prospect ids in that team's board order]}
        self.boards = {}
        self.rng_state = None
        self.completed = False

    # -- construction -----------------------------------------------
    @classmethod
    def begin(cls, league, year, draft_order, team_reports, rng):
        """Snapshot a freshly built war-room draft into a session.

        draft_order: [[round_num, team, draft_pick], ...] as built by
        DraftView.start_draft. team_reports: {name: {"board": [...]}} or
        None. rng: the per-draft random.Random.
        """
        s = cls()
        s.year = int(year)
        for i, entry in enumerate(draft_order or []):
            try:
                rnd, team, dp = entry
            except Exception:
                continue
            try:
                owner = str(getattr(team, 'team_name', '') or '')
            except Exception:
                owner = ''
            try:
                pid = str(getattr(dp, 'id', '') or '') or None
            except Exception:
                pid = None
            try:
                rnd = int(rnd or 0)
            except Exception:
                rnd = 0
            s.slots.append({'overall': i + 1, 'round': rnd,
                            'owner': owner, 'pick_id': pid})
        try:
            s.rng_state = rng.getstate() if rng is not None else None
        except Exception:
            s.rng_state = None
        try:
            for name, rep in (team_reports or {}).items():
                board = (rep or {}).get('board') or []
                ids = []
                for p in board:
                    try:
                        pid = getattr(p, 'id', None)
                    except Exception:
                        pid = None
                    if pid is not None:
                        ids.append(pid)
                s.boards[str(name)] = ids
        except Exception:
            pass
        return s

    # -- liveness ----------------------------------------------------
    def is_live_for(self, year) -> bool:
        """True when this session is an in-progress draft for `year`."""
        try:
            return (not self.completed
                    and int(self.year) == int(year)
                    and 0 <= int(self.current_pick) < len(self.slots))
        except Exception:
            return False

    def is_complete(self) -> bool:
        try:
            return bool(self.completed) or \
                int(self.current_pick) >= len(self.slots)
        except Exception:
            return True

    # -- transactional pick commit -----------------------------------
    def has_pick(self, overall) -> bool:
        try:
            o = int(overall)
        except Exception:
            return False
        return any(int(p.get('overall', -1)) == o for p in self.picks)

    def record_pick(self, overall, team_name, player_id) -> bool:
        """Record a committed pick. Idempotent per overall: returns False
        (and records nothing) when this overall is already logged."""
        try:
            o = int(overall)
        except Exception:
            return False
        if self.has_pick(o):
            return False
        self.picks.append({'overall': o, 'team': str(team_name or ''),
                           'player_id': player_id})
        return True

    # -- owner sync (mid-draft pick trades) ----------------------------
    def sync_owners_from_league(self, league):
        """Repoint slot owners from the live pick objects.

        A pick traded mid-draft changes draft_pick.current_team; the
        session journal follows it so re-entry shows the real owners.
        Already-committed picks keep their selecting team in the log.
        """
        try:
            picks_by_id = self._pick_index(league)
            for slot in self.slots:
                pid = slot.get('pick_id')
                if not pid:
                    continue
                dp = picks_by_id.get(str(pid))
                if dp is None:
                    continue
                owner = self._pick_owner_name(dp)
                if owner:
                    slot['owner'] = owner
        except Exception:
            pass

    # -- materialization (view re-attachment) --------------------------
    def _team_index(self, league):
        idx = {}
        for t in (getattr(league, 'teams', None) or []):
            try:
                idx[str(getattr(t, 'team_name', ''))] = t
            except Exception:
                continue
        return idx

    def _prospect_index(self, league):
        """Every draftable prospect by id: the live class plus any
        prospect already assigned to a team (defensive; picks resolve
        through the team lists first)."""
        idx = {}
        try:
            pool = list(getattr(league, 'draft_prospects', None) or [])
        except Exception:
            pool = []
        for p in pool:
            try:
                pid = getattr(p, 'id', None)
            except Exception:
                pid = None
            if pid is not None:
                idx.setdefault(pid, p)
        for t in (getattr(league, 'teams', None) or []):
            for attr in ('prospects', 'roster', 'ahl_roster'):
                try:
                    lst = getattr(t, attr, None) or []
                except Exception:
                    lst = []
                for p in lst:
                    try:
                        pid = getattr(p, 'id', None)
                    except Exception:
                        pid = None
                    if pid is not None:
                        idx.setdefault(pid, p)
        return idx

    def _pick_index(self, league):
        idx = {}
        for t in (getattr(league, 'teams', None) or []):
            try:
                dpd = getattr(t, 'draft_picks', None) or {}
            except Exception:
                dpd = {}
            try:
                vals = dpd.values() if isinstance(dpd, dict) else dpd
            except Exception:
                vals = []
            for v in (vals or []):
                # draft_picks is {year: [DraftPick, ...]}; flatten it.
                items = v if isinstance(v, list) else [v]
                for dp in items:
                    try:
                        pid = str(getattr(dp, 'id', '') or '')
                    except Exception:
                        continue
                    if pid:
                        idx[pid] = dp
        return idx

    @staticmethod
    def _pick_owner_name(dp) -> str:
        """current_team may be a team-name string (canonical) or a Team."""
        try:
            cur = getattr(dp, 'current_team', '')
            name = getattr(cur, 'team_name', cur)
            return str(name or '').strip()
        except Exception:
            return ''

    def materialize_order(self, league):
        """Rebuild the view's [[round, team, draft_pick], ...] order."""
        teams = self._team_index(league)
        picks = self._pick_index(league)
        order = []
        for slot in self.slots:
            try:
                rnd = int(slot.get('round', 0) or 0)
            except Exception:
                rnd = 0
            team = teams.get(str(slot.get('owner', '')))
            dp = picks.get(str(slot.get('pick_id') or ''))
            order.append([rnd, team, dp])
        return order

    def materialize_boards(self, league):
        """Rebuild {team_name: [prospects in board order]}."""
        prospects = self._prospect_index(league)
        out = {}
        for name, ids in (self.boards or {}).items():
            out[str(name)] = [prospects[i] for i in (ids or [])
                              if i in prospects]
        return out

    def materialize_picks(self, league):
        """Rebuild [(team_name, overall, player), ...] for the results log."""
        prospects = self._prospect_index(league)
        out = []
        for p in sorted(self.picks,
                        key=lambda r: int(r.get('overall', 0) or 0)):
            try:
                player = prospects.get(p.get('player_id'))
            except Exception:
                player = None
            if player is None:
                continue
            out.append((str(p.get('team', '')), int(p.get('overall', 0)),
                        player))
        return out

    # -- audit ---------------------------------------------------------
    def audit(self, league) -> list:
        """Honest-state audit: every committed pick's prospect must be on
        exactly one team's prospect list; no prospect picked twice; slot
        owners must match the live pick objects. Read-only."""
        issues = []
        try:
            prospects = self._prospect_index(league)
            # locations per prospect id across team lists
            locs = {}
            for t in (getattr(league, 'teams', None) or []):
                tname = str(getattr(t, 'team_name', '?'))
                for attr in ('prospects', 'roster', 'ahl_roster'):
                    try:
                        lst = getattr(t, attr, None) or []
                    except Exception:
                        lst = []
                    for p in lst:
                        try:
                            pid = getattr(p, 'id', None)
                        except Exception:
                            pid = None
                        if pid is not None:
                            locs.setdefault(pid, []).append(
                                f"{tname}.{attr}")
            seen = {}
            for p in self.picks:
                pid = p.get('player_id')
                o = p.get('overall')
                if pid in seen:
                    issues.append(f"duplicate pick: prospect taken at "
                                  f"#{seen[pid]} and #{o}")
                else:
                    seen[pid] = o
                at = locs.get(pid, [])
                if not at:
                    nm = '?'
                    try:
                        nm = getattr(prospects.get(pid), 'full_name', '?')
                    except Exception:
                        pass
                    issues.append(f"orphaned prospect: #{o} {nm} is on no "
                                  f"team's list")
                elif len(at) > 1:
                    issues.append(f"double-listed prospect: #{o} on "
                                  f"{', '.join(at)}")
            # slot owners vs live pick objects
            picks = self._pick_index(league)
            for slot in self.slots:
                pid = slot.get('pick_id')
                if not pid:
                    continue
                dp = picks.get(str(pid))
                if dp is None:
                    continue
                live = self._pick_owner_name(dp)
                if live and live != slot.get('owner'):
                    issues.append(
                        f"slot #{slot.get('overall')}: owner is {live} "
                        f"but the session still shows {slot.get('owner')}")
        except Exception as e:
            issues.append(f"audit failed: {e}")
        return issues

    # -- save/load journal ----------------------------------------------
    def to_dict(self) -> dict:
        return {
            'version': self.VERSION,
            'year': int(self.year or 0),
            'slots': [dict(s) for s in self.slots],
            'current_pick': int(self.current_pick or 0),
            'picks': [dict(p) for p in self.picks],
            'boards': {str(k): list(v)
                       for k, v in (self.boards or {}).items()},
            'rng_state': self.rng_state,
            'completed': bool(self.completed),
        }

    @classmethod
    def from_dict(cls, d):
        """Rebuild from a save journal. Raises ValueError when the
        journal can't be honored -- the caller degrades to an honest
        'draft unavailable' state, never a fresh draft."""
        if not isinstance(d, dict):
            raise ValueError("entry draft journal is not a dict")
        s = cls()
        try:
            s.year = int(d.get('year', 0) or 0)
        except Exception:
            s.year = 0
        if not s.year:
            raise ValueError("entry draft journal has no year")
        slots = d.get('slots') or []
        if not slots:
            raise ValueError("entry draft journal has no slots")
        s.slots = [dict(x) for x in slots if isinstance(x, dict)]
        try:
            s.current_pick = int(d.get('current_pick', 0) or 0)
        except Exception:
            s.current_pick = 0
        s.current_pick = max(0, min(s.current_pick, len(s.slots)))
        picks = d.get('picks') or []
        s.picks = [dict(x) for x in picks if isinstance(x, dict)]
        boards = d.get('boards') or {}
        s.boards = {str(k): list(v) for k, v in boards.items()
                    if isinstance(v, (list, tuple))}
        s.rng_state = d.get('rng_state')
        s.completed = bool(d.get('completed', False))
        return s


def resume_entry_draft_session(league, session, app=None):
    """Finalize a complete-but-unfinalized war-room session, headlessly.

    The session's remaining slots are normally completed through the
    war-room view itself -- an in-progress session is NEVER advanced
    here (no hidden/off-screen AI picks; the draft pauses while its
    screen is closed). This entry point covers the session whose slots
    are all picked but never finalized (e.g. a save/load edge): it
    replays nothing (every overall is already journaled) and runs the
    standard finalize -- conducted stamp, grades, session release.

    Returns the full pick log [(team_name, overall, player)].
    """
    year = int(getattr(session, 'year', 0) or 0)
    if not year:
        return []
    # Structural guarantee: an in-progress session is NEVER advanced
    # headlessly. Only a session whose slots are all picked gets
    # finalized here. (The pick-completing loop below is retained for
    # explicit callers but is unreachable while this guard stands.)
    if not session.is_complete():
        try:
            return list(session.materialize_picks(league))
        except Exception:
            return []
    try:
        rng = random.Random()
        rng.setstate(session.rng_state)
    except Exception:
        rng = random.Random(stable_draft_seed(year))
    order = session.materialize_order(league)
    boards = session.materialize_boards(league)
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

    def _pos_of(player):
        try:
            return player.primary_position.value
        except Exception:
            return "?"

    try:
        pool = sorted(list(getattr(league, 'draft_prospects', None) or []),
                      key=lambda p: getattr(p, 'draft_ranking', 0),
                      reverse=True)
    except Exception:
        pool = []
    # Dynamic need pivot from the picks already committed in-session.
    _drafted_by_team = {}
    try:
        for _tn, _ov, _pl in session.materialize_picks(league):
            try:
                _rnd = next(s.get('round', 7) for s in session.slots
                            if int(s.get('overall', -1)) == int(_ov))
            except StopIteration:
                _rnd = 7
            _drafted_by_team.setdefault(_tn, []).append(
                (_pos_of(_pl), _rnd))
    except Exception:
        pass

    resumed = []
    for idx in range(int(session.current_pick or 0), len(order)):
        entry = order[idx]
        try:
            round_num, team, _dp = entry
        except Exception:
            continue
        if team is None:
            continue
        overall = idx + 1
        if session.has_pick(overall):
            # Already committed (idempotency): advance the cursor past it.
            session.current_pick = idx + 1
            continue
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
        try:
            board = (boards or {}).get(tname)
        except Exception:
            board = None
        selected, _reach, _steal = ai_select_prospect(
            team, avail, board, needs, round_num,
            _priority_of(team), rng, overall=overall,
            drafted=_drafted_by_team.get(tname))
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
        try:
            league.draft_prospects.remove(selected)
        except (ValueError, AttributeError):
            pass
        try:
            pid = getattr(selected, 'id', None)
        except Exception:
            pid = None
        session.record_pick(overall, tname, pid)
        session.current_pick = idx + 1
        try:
            session.rng_state = rng.getstate()
        except Exception:
            pass
        _drafted_by_team.setdefault(tname, []).append(
            (_pos_of(selected), round_num))
        resumed.append((tname, overall, selected))

    full_log = session.materialize_picks(league)
    if not full_log:
        return []
    # Finalize like the conductor: leftovers re-enter next year, the
    # one-draft re-draft ban is spent, the year is stamped conducted and
    # grades persist. The war room's end_draft does the same for its path.
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
    persist_draft_grades(league, year, full_log)
    try:
        session.completed = True
        league.entry_draft_session = None
    except Exception:
        pass
    # News: short honest summary of the resumed (headless-completed) tail.
    try:
        _add_news = getattr(app, 'add_news', None) if app is not None else None
        if _add_news is not None and resumed:
            _first, _last = resumed[0][1], resumed[-1][1]
            _add_news(
                f"The {year} NHL Entry Draft resumed from pick #{_first} "
                f"and completed ({len(resumed)} picks auto-conducted, "
                f"#{_first}-#{_last}).")
    except Exception:
        pass
    return full_log


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
    # BUG-2 fix: a live war-room session owns this draft. The draft is
    # PAUSED while its screen is closed -- never completed headlessly
    # (no hidden/off-screen AI picks). An in-progress session defers
    # honestly: the user resumes it in the war room. Only a session
    # whose slots are all picked but never finalized is finalized here,
    # which makes no picks (nothing left to pick).
    try:
        _sess = getattr(league, 'entry_draft_session', None)
    except Exception:
        _sess = None
    if _sess is not None and isinstance(_sess, EntryDraftSession) \
            and int(getattr(_sess, 'year', 0) or 0) == year:
        if _sess.is_complete():
            # Covers a session that finished its slots but never
            # finalized (resume finalizes idempotently, no picks made).
            return resume_entry_draft_session(league, _sess, app=app)
        try:
            print(f"Entry draft {year}: war-room session in progress "
                  f"({len(_sess.picks)}/{len(_sess.slots)} picks) -- "
                  "deferring headless conduct; the draft stays parked.",
                  flush=True)
        except Exception:
            pass
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
    # Dynamic need pivot: track (position, round) per team as the draft
    # unfolds, so a need filled early stops pulling later picks.
    _drafted_by_team = {}

    def _pos_of(player):
        try:
            return player.primary_position.value
        except Exception:
            return "?"

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
            _priority_of(team), rng, overall=overall,
            drafted=_drafted_by_team.get(tname))
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
        _drafted_by_team.setdefault(tname, []).append(
            (_pos_of(selected), round_num))

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
