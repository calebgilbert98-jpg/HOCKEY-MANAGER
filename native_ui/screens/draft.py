"""Entry draft war room: native Qt port of the web UI draft page.

Ports web_ui/templates/draft.html + web_ui/screens/draft.py +
web_ui/static/js/draft.js. Calls the game object DIRECTLY -- no Flask,
no HTTP, no command queue.

Game methods / engine functions used (all real, same as the web bridge):
  - league.entry_draft_session (EntryDraftSession: slots, picks,
    current_pick, year, is_complete(), record_pick(), sync_owners_...)
  - league.draft_prospects, team.prospects, team.roster, league.teams
  - league.draft_day_deals, league.draft_grades_history, league.stamp_draft_rights
  - draft_night.ticker_line, pick_slot_value, drafted_player_value,
    draft_grades, grade_color, ai_select_prospect, stable_draft_seed
  - draft_stories.assign_headline_storylines, season_beats
  - draft_day_trades: _round1_order, _draft_board, _is_human,
    _priority_of, _priority_name, _trade_up_target, _owned_picks,
    _build_trade_up_offer, _call_why_lines, _pos_of, _sync_pick_lists
  - scouting.consensus_range
  - trade_engine.ai_consider_trade, execute_trade, asset_label,
    asset_value, pick_trade_value, CompletedTrade
  - gm.trade_history, gm.user_team, gm.league, gm.current_date
  - app.add_news_story

MP fantasy-draft contract (see native_ui/MP_FANTASY_DRAFT_BUG.md):
  this screen is the single-player ENTRY draft only. It never reads or
  writes ``pending_fantasy_draft`` -- that flag belongs to the fantasy
  draft flow and must stay untouched.
"""

from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from .base import BaseScreen
from ..widgets.attribute_bar import AttributeBar


# ---------------------------------------------------------------------------
# helpers (ported from web_ui/screens/draft.py, Flask removed)
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _resolve_gm(game):
    return _safe(lambda: getattr(game, "game_manager", None)) or game


def _user_team(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.user_team)
            or _safe(lambda: getattr(game, "user_team", None)))


def _league(game):
    gm = _resolve_gm(game)
    return (_safe(lambda: gm.league)
            or _safe(lambda: getattr(game, "league", None)))


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


def _player_ovr(p):
    try:
        fn = getattr(p, "overall_rating", None)
        if callable(fn):
            v = fn()
            if v:
                return int(v)
        v = getattr(p, "overall", None)
        if v:
            return int(v)
    except Exception:
        pass
    return 0


def _prospect_pos(p):
    """Position string from primary_position enum or position attr."""
    try:
        pp = getattr(p, "primary_position", None)
        if pp is not None:
            v = getattr(pp, "value", None) or str(pp)
            v = str(v).split(".")[-1].replace("RIGHT_", "R").replace(
                "LEFT_", "L").replace("_DEFENSE", "D").replace(
                "_WING", "W").replace("CENTER", "C").replace("GOALIE", "G")
            return v
    except Exception:
        pass
    return _safe(lambda: str(getattr(p, "primary_position", "?") or "?"), "?")


def _session(game):
    league = _league(game)
    return _safe(lambda: getattr(league, "entry_draft_session", None))


def _prospect_index(league):
    """Every draftable prospect by id: live class + drafted ones on team
    lists (mirrors EntryDraftSession._prospect_index, read-only)."""
    idx = {}
    for p in _safe(lambda: list(getattr(league, "draft_prospects", None)
                                or []), []) or []:
        try:
            pid = getattr(p, "id", None)
            if pid is not None:
                idx.setdefault(pid, p)
        except Exception:
            continue
    for t in _safe(lambda: list(getattr(league, "teams", None) or []), []) \
            or []:
        for attr in ("prospects", "roster", "ahl_roster"):
            for p in _safe(lambda: list(getattr(t, attr, None) or []),
                           []) or []:
                try:
                    pid = getattr(p, "id", None)
                    if pid is not None:
                        idx.setdefault(pid, p)
                except Exception:
                    continue
    return idx


def get_draft_state(game):
    """Serialize the entry draft session for the board (port of the web
    get_draft_state, reading native objects directly)."""
    gm = _resolve_gm(game)
    league = _safe(lambda: gm.league) or _safe(lambda: game.league)
    team = _safe(lambda: gm.user_team) or _safe(lambda: game.user_team)
    if league is None:
        return {"active": False}

    session = _safe(lambda: getattr(league, "entry_draft_session", None))
    if session is None or _safe(lambda: bool(session.is_complete()), True):
        return {"active": False}

    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    slots = _safe(lambda: list(getattr(session, "slots", None) or []), []) \
        or []
    picks = _safe(lambda: list(getattr(session, "picks", None) or []), []) \
        or []
    cur_idx = _safe(lambda: int(getattr(session, "current_pick", 0) or 0), 0)
    user_name = _safe(lambda: getattr(team, "team_name", ""), "") or ""

    pick_by_overall = {}
    for p in picks:
        try:
            pick_by_overall[int(p.get("overall", -1))] = p
        except Exception:
            continue

    prospects = _prospect_index(league)

    def _to_prospect(p):
        return {
            "id": _safe(lambda: str(getattr(p, "id", id(p)))),
            "name": _safe(lambda: getattr(p, "full_name", "?")),
            "position": _prospect_pos(p),
            "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
            "overall": _player_ovr(p),
        }

    board = []
    rounds = set()
    for s in slots:
        try:
            overall = int(s.get("overall", 0) or 0)
            rnd = int(s.get("round", 0) or 0)
            rounds.add(rnd)
            owner = str(s.get("owner", "") or "")
            rec = pick_by_overall.get(overall)
            prospect = None
            if rec is not None:
                prospect = prospects.get(rec.get("player_id"))
            board.append({
                "overall": overall,
                "round": rnd,
                "owner": owner,
                "is_user_pick": bool(user_name and owner == user_name),
                "is_current": overall == cur_idx + 1,
                "made": rec is not None,
                "team": str(rec.get("team", "")) if rec is not None else None,
                "prospect": _to_prospect(prospect)
                if prospect is not None else None,
            })
        except Exception:
            continue

    made_count = len(pick_by_overall)
    user_picks = sorted(
        [b["overall"] for b in board if b["is_user_pick"] and not b["made"]])
    return {
        "active": True,
        "year": year,
        "current_overall": cur_idx + 1,
        "total_slots": len(board),
        "made_count": made_count,
        "rounds": sorted(rounds),
        "user_picks": user_picks,
        "board": board,
    }


def available_prospects(game):
    """Draftable prospects not yet picked (port of _available_prospects)."""
    league = _league(game)
    if league is None:
        return []
    session = _session(game)
    picked_ids = set()
    if session is not None:
        for p in (_safe(lambda: list(getattr(session, "picks", None)
                                     or []), []) or []):
            try:
                picked_ids.add(str(p.get("player_id")))
            except Exception:
                pass
    prospects = _safe(lambda: list(getattr(league, "draft_prospects",
                                          None) or []), []) or []
    out = []
    for p in prospects:
        try:
            pid = str(getattr(p, "id", ""))
            if pid in picked_ids:
                continue
            out.append({
                "id": pid,
                "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                "position": _prospect_pos(p),
                "age": _safe(lambda: int(getattr(p, "age", 0) or 0), 0),
                "overall": _player_ovr(p),
                "potential": _safe(lambda: str(getattr(
                    p, "potential_grade", "?") or "?"), "?"),
            })
        except Exception:
            continue
    try:
        out.sort(key=lambda d: d.get("overall", 0), reverse=True)
    except Exception:
        pass
    return out


def filter_prospects(prospects, pos, q):
    out = prospects
    if pos != "All":
        out = [p for p in out
               if (p.get("position") or "").upper() == pos
               or (pos == "D" and (p.get("position") or "").upper()
                   in ("LD", "RD"))
               or (pos == "W" and (p.get("position") or "").upper()
                   in ("LW", "RW"))]
    q = (q or "").strip().lower()
    if q:
        out = [p for p in out if q in (p.get("name") or "").lower()]
    return out


def scout_report(game, pid):
    """Scout report for one prospect (port of api_draft_scout_report)."""
    league = _league(game)
    if league is None:
        return {"error": "no game"}
    target = None
    for q in (_safe(lambda: list(getattr(league, "draft_prospects",
                                        None) or []), []) or []):
        if str(getattr(q, "id", "")) == str(pid):
            target = q
            break
    if target is None:
        return {"error": "prospect not found"}
    attrs = {}
    for a in ("shooting_accuracy", "shooting_power", "passing", "skating",
              "checking", "defensive_awareness", "offensive_awareness",
              "strength", "hockey_iq"):
        try:
            v = getattr(target, a, None)
            if v is not None:
                attrs[a] = int(v)
        except Exception:
            pass
    return {
        "id": str(pid),
        "name": _safe(lambda: getattr(target, "full_name", "?"), "?"),
        "position": _prospect_pos(target),
        "age": _safe(lambda: int(getattr(target, "age", 0) or 0), 0),
        "overall": _player_ovr(target),
        "potential": _safe(lambda: str(getattr(target, "potential_grade",
                                              "?") or "?"), "?"),
        "attributes": attrs,
        "report": _safe(lambda: getattr(target, "scout_report", "") or "",
                        ""),
        "strengths": _safe(lambda: list(getattr(target, "strengths",
                                               None) or []), []) or [],
        "weaknesses": _safe(lambda: list(getattr(target, "weaknesses",
                                                None) or []), []) or [],
    }


# --- engine mutations (ports of the bridge command ops; in native Qt the
# game object is called directly -- the command queue only existed for
# the Flask thread boundary) ----------------------------------------------

def do_draft_pick(game, pid):
    """User drafts a prospect (desktop windows.py execute_pick parity).

    Only valid when the user's club is on the clock: records the pick,
    advances the cursor, moves the prospect to the club's prospect list
    and stamps draft rights.
    """
    try:
        league = _league(game)
        team = _user_team(game)
        session = _session(game)
        if league is None or team is None or session is None or not pid:
            return False, "Draft is not active."
        cur = int(getattr(session, "current_pick", 0) or 0)
        overall = cur + 1
        tname = getattr(team, "team_name", "")
        # The on-clock pick must belong to the user.
        owner = None
        for s in (getattr(session, "slots", None) or []):
            try:
                if int(s.get("overall", 0) or 0) == overall:
                    owner = s.get("owner")
                    break
            except Exception:
                continue
        if owner != tname:
            return False, "It's not your pick -- you can only draft " \
                          "when you're on the clock."
        # Find the prospect object.
        prospect = None
        for q in list(getattr(league, "draft_prospects", None) or []):
            if str(getattr(q, "id", "")) == str(pid):
                prospect = q
                break
        if prospect is None:
            return False, "Prospect is no longer available."
        if not session.record_pick(overall, tname, pid):
            return False, "That pick was already made."
        session.current_pick = overall
        try:
            getattr(league, "draft_prospects").remove(prospect)
        except Exception:
            pass
        try:
            plist = getattr(team, "prospects", None)
            if plist is None:
                team.prospects = []
                plist = team.prospects
            plist.append(prospect)
        except Exception:
            pass
        try:
            league.stamp_draft_rights(prospect, tname,
                                      int(getattr(session, "year", 0) or 0))
        except Exception:
            pass
        try:
            prospect.draft_reentry_from = ""
        except Exception:
            pass
        return True, f"{tname} select {getattr(prospect, 'full_name', '?')} " \
                     f"#{overall} overall."
    except Exception as e:
        return False, f"Draft failed: {e}"


def do_sim_pick(game):
    """AI auto-picks for the current slot (port of the draft_sim_pick op)."""
    try:
        import draft_night as dn
        league = _league(game)
        session = _session(game)
        if league is None or session is None:
            return False, "Draft is not active."
        cur = int(getattr(session, "current_pick", 0) or 0)
        overall = cur + 1
        slots = list(getattr(session, "slots", None) or [])
        owner = None
        for s in slots:
            try:
                if int(s.get("overall", 0)) == overall:
                    owner = s.get("owner")
                    break
            except Exception:
                continue
        picked = set()
        for p in list(getattr(session, "picks", None) or []):
            try:
                picked.add(str(p.get("player_id")))
            except Exception:
                pass
        avail = [q for q in list(getattr(league, "draft_prospects",
                                        None) or [])
                 if str(getattr(q, "id", "")) not in picked]
        if not avail or not owner:
            return False, "No prospects available."
        oteam = None
        for t in list(getattr(league, "teams", None) or []):
            if getattr(t, "team_name", "") == owner:
                oteam = t
                break
        if oteam is None:
            return False, "Owning team not found."
        import random as _rnd
        pick = None
        try:
            avail_sorted = sorted(
                avail,
                key=lambda q: int(getattr(q, "draft_ranking", 9999) or 9999))
            rnd = _rnd.Random()
            # Returns (selected, reach, steal) -- the web op assigned the
            # raw tuple and recorded an empty player_id; unpack it like
            # the desktop conductor does.
            res = dn.ai_select_prospect(oteam, avail_sorted, None, None,
                                        1, None, rnd, overall=overall)
            pick = res[0] if isinstance(res, tuple) else res
        except Exception:
            pick = None
        if pick is None:
            avail.sort(key=lambda q: int(getattr(q, "overall", 0) or 0),
                       reverse=True)
            pick = avail[0] if avail else None
        if pick is None:
            return False, "No prospects available."
        pid = str(getattr(pick, "id", ""))
        session.record_pick(overall, owner, pid)
        session.current_pick = overall
        try:
            getattr(league, "draft_prospects").remove(pick)
        except Exception:
            pass
        try:
            plist = getattr(oteam, "prospects", None)
            if plist is None:
                oteam.prospects = []
                plist = oteam.prospects
            plist.append(pick)
        except Exception:
            pass
        return True, f"{owner} select " \
                     f"{getattr(pick, 'full_name', '?')} #{overall}."
    except Exception as e:
        return False, f"Sim pick failed: {e}"

def buzz_items(game):
    """Draft buzz ticker (port of api_draft_buzz): pick drama from real
    made picks, engine headline storylines + monthly beats over real
    prospects (deterministic RNG pinned + restored), and a read-only
    steal watch. Never mutates league state."""
    league = _league(game)
    if league is None:
        return []
    import random as _random
    try:
        import draft_night as _dn
        import draft_stories as _ds
    except Exception:
        return []

    prospects = _safe(lambda: list(getattr(league, "draft_prospects",
                                          None) or []), []) or []
    session = _session(game)
    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    if not year:
        year = _safe(lambda: int(getattr(league, "season_year", 0) or 0),
                     0)
        year = year + 1 if year else 0
    items = []

    def _rank_score(p):
        try:
            return float(getattr(p, "draft_ranking", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    board_pos = {}
    for i, p in enumerate(sorted(prospects, key=_rank_score,
                                 reverse=True), 1):
        try:
            pid = getattr(p, "id", None)
            if pid is not None:
                board_pos.setdefault(str(pid), i)
        except Exception:
            continue

    # 1. Live pick drama from picks actually made (engine ticker lines).
    slot_round = {}
    for s in (_safe(lambda: list(getattr(session, "slots", None) or []),
                    []) or []):
        try:
            slot_round[int(s.get("overall", 0) or 0)] = int(
                s.get("round", 0) or 0)
        except Exception:
            continue
    pidx = _prospect_index(league)
    made = []
    for p in (_safe(lambda: list(getattr(session, "picks", None) or []),
                    []) or []):
        try:
            made.append((int(p.get("overall", 0) or 0), p))
        except Exception:
            continue
    made.sort()
    trng = _random.Random(_dn.stable_draft_seed(year, "ticker"))
    for overall, p in made[-12:]:
        try:
            player = pidx.get(p.get("player_id"))
            if player is None:
                continue
            team = str(p.get("team", "") or "")
            proj = board_pos.get(str(getattr(player, "id", "")))
            diff = (proj - overall) if proj else 0
            reach, steal = diff >= 10, diff <= -10
            kind = ("reach" if reach else
                    "steal" if steal else
                    "milestone" if overall <= 3 and abs(diff) <= 2 else
                    "pick")
            rnd = slot_round.get(overall) or ((overall - 1) // 32 + 1)
            items.append({
                "kind": kind,
                "title": "Reach Alert" if reach else
                         "Steal Watch" if steal else "Pick #%d" % overall,
                "text": _dn.ticker_line(overall, team, player, rnd,
                                        reach=reach, steal=steal, rng=trng),
                "prospect_id": str(getattr(player, "id", "")),
                "team": team,
                "overall": overall,
            })
        except Exception:
            continue
    items.reverse()

    # 2 + 3. Engine chatter over real prospects (RNG pinned + restored).
    state = _random.getstate()
    try:
        _random.seed(_dn.stable_draft_seed(year, "buzz"))
        try:
            for s in (_ds.assign_headline_storylines(prospects, year)
                      or []):
                items.append({
                    "kind": "headline",
                    "title": str(s.get("title", "")),
                    "text": str(s.get("text", "")),
                    "prospect_id": (str(s.get("prospect_id"))
                                    if s.get("prospect_id") is not None
                                    else None),
                    "tags": list(s.get("tags", []) or []),
                })
        except Exception:
            pass
        try:
            gm = _resolve_gm(game)
            d = _safe(lambda: gm.current_date)
            try:
                month = int(getattr(d, "month", 6) or 6)
            except Exception:
                month = 6
            beats_month = month if 1 <= month <= 6 else 6
            for s in (_ds.season_beats(prospects, year, beats_month)
                      or []):
                items.append({
                    "kind": "beat",
                    "title": str(s.get("title", "")),
                    "text": str(s.get("text", "")),
                    "prospect_id": (str(s.get("prospect_id"))
                                    if s.get("prospect_id") is not None
                                    else None),
                    "tags": list(s.get("tags", []) or []),
                })
        except Exception:
            pass
    finally:
        _random.setstate(state)

    # 4. Steal watch (read-only: late-round picks with exploded potential).
    try:
        _steal_grades = {"B+", "A-", "A", "A+"}
        found = []
        teams = _safe(lambda: list(getattr(league, "teams", None)
                                  or []), []) or []
        for t in teams:
            pool = []
            for attr in ("roster", "prospects"):
                pool += _safe(lambda: list(getattr(t, attr, None)
                                          or []), []) or []
            for p in pool:
                try:
                    dround = int(getattr(p, "draft_round", 0) or 0)
                    if dround < 4:
                        continue
                    if int(getattr(p, "age", 99) or 99) > 26:
                        continue
                    grade = (getattr(p, "potential_grade", "") or "").strip()
                    if grade not in _steal_grades:
                        continue
                    if float(getattr(p, "draft_hype", 100) or 100) > 45:
                        continue
                    dyear = _safe(lambda: int(getattr(
                        p, "drafted_year", 0) or 0), 0)
                    found.append((dround, p, dyear, grade))
                except Exception:
                    continue
        _grade_order = {"B+": 0, "A-": 1, "A": 2, "A+": 3}
        found.sort(key=lambda x: (-x[0], _grade_order.get(x[3], 0)),
                   reverse=False)
        for dround, p, dyear, grade in found[:3]:
            name = _safe(lambda: getattr(p, "full_name", "?"), "?")
            when = ("round %d of the %s draft" % (dround, dyear)
                    if dyear else "round %d" % dround)
            items.append({
                "kind": "steal",
                "title": "Steal Watch: %s" % name,
                "text": ("%s, taken in %s, has developed into a "
                         "%s-potential player -- the Datsyuk story nobody "
                         "saw coming." % (name, when, grade)),
                "prospect_id": str(getattr(p, "id", "")),
                "tags": ["draft", "steal"],
            })
    except Exception:
        pass
    return items


def trade_feed(game):
    """Draft-day trade feed from league.draft_day_deals, newest first."""
    import re
    league = _league(game)
    gm = _resolve_gm(game)
    if league is None:
        return []
    deals = _safe(lambda: list(getattr(league, "draft_day_deals",
                                      None) or []), []) or []

    date_by_summary = {}
    try:
        for ct in (_safe(lambda: list(getattr(gm, "trade_history",
                                             None) or []), []) or []):
            s = _safe(lambda: str(getattr(ct, "summary", "") or ""), "")
            d = _safe(lambda: str(getattr(ct, "date", "") or ""), "")
            if s:
                date_by_summary.setdefault(s, d)
    except Exception:
        pass

    team_names = []
    for t in (_safe(lambda: list(getattr(league, "teams", None)
                                or []), []) or []):
        n = _safe(lambda: str(getattr(t, "team_name", "") or ""), "")
        if n:
            team_names.append(n)

    out = []
    for raw in reversed(deals[-50:]):
        try:
            text = str(raw or "").strip()
            if not text:
                continue
            kind = "rumor" if text.upper().startswith("RUMOR") else "deal"
            text = re.sub(r"^(DRAFT TRADE|RUMOR)\s*:\s*", "", text,
                          flags=re.I)
            year = None
            dd = (date_by_summary.get("DRAFT TRADE: " + text)
                  or date_by_summary.get(text))
            if dd:
                m = re.search(r"(\d{4})", dd)
                if m:
                    year = int(m.group(1))
            involved = sorted([n for n in team_names if n in text],
                              key=len, reverse=True)
            out.append({"text": text, "year": year, "teams": involved,
                        "kind": kind})
        except Exception:
            continue
    return out


def draft_grades(game):
    """Draft grades: live projection while underway, else persisted final
    grades from the newest completed draft (port of api_draft_grades)."""
    league = _league(game)
    if league is None:
        return {"source": "none", "year": None, "grades": []}
    try:
        import draft_night as _dn
    except Exception:
        return {"source": "none", "year": None, "grades": []}

    session = _session(game)
    complete = (_safe(lambda: bool(session.is_complete()), True)
                if session else True)
    picks = _safe(lambda: list(getattr(session, "picks", None)
                               or []), []) or []
    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    if not year:
        year = _safe(lambda: int(getattr(league, "season_year", 0) or 0),
                     0)
        year = year + 1 if year else 0

    def _grade_entry(team, grade, ratio, detail):
        return {"name": team, "grade": grade,
                "color": _dn.grade_color(grade),
                "score": round(float(ratio), 3), "picks": detail or []}

    # Live projection: draft underway and picks have been made.
    if session is not None and not complete and picks:
        pidx = _prospect_index(league)
        slot_round = {}
        for s in (_safe(lambda: list(getattr(session, "slots", None)
                                     or []), []) or []):
            try:
                slot_round[int(s.get("overall", 0) or 0)] = int(
                    s.get("round", 0) or 0)
            except Exception:
                continue
        picks_made = []
        detail = {}
        for p in picks:
            try:
                overall = int(p.get("overall", 0) or 0)
                team = str(p.get("team", "") or "")
                player = pidx.get(p.get("player_id"))
                if player is None or not team:
                    continue
                picks_made.append((team, overall, player))
                exp = _dn.pick_slot_value(overall)
                act = _dn.drafted_player_value(player)
                detail.setdefault(team, []).append({
                    "overall": overall,
                    "round": slot_round.get(overall)
                    or ((overall - 1) // 32 + 1),
                    "player": _safe(lambda: getattr(player, "full_name",
                                                   "?"), "?"),
                    "player_id": str(getattr(player, "id", "")),
                    "expected": exp,
                    "value": act,
                    "delta": act - exp,
                })
            except Exception:
                continue
        grades = _dn.draft_grades(picks_made)
        rows = [_grade_entry(t, g, r,
                             sorted(detail.get(t, []),
                                    key=lambda d: d["overall"]))
                for t, g, r in grades]
        return {"source": "live", "year": year or None,
                "note": "Projected -- draft in progress. Grades update "
                        "with every pick.",
                "grades": rows}

    # Final: newest completed draft from the persisted history.
    hist = _safe(lambda: dict(getattr(league, "draft_grades_history",
                                     None) or {}), {}) or {}
    years = []
    for k in hist.keys():
        try:
            years.append(int(k))
        except (TypeError, ValueError):
            continue
    if years:
        y = max(years)
        rows = []
        for entry in (hist.get(str(y)) or []):
            try:
                t, g, r = entry[0], entry[1], float(entry[2])
                rows.append(_grade_entry(str(t), str(g), r, []))
            except Exception:
                continue
        return {"source": "final", "year": y, "grades": rows}
    return {"source": "none", "year": None, "grades": []}


def trade_pick_info(game):
    """Trade-this-pick dialog data (port of api_draft_trade_pick_info).

    Uses real DraftPick objects where the session journal can resolve
    them (session.materialize_order), falling back to slot-value curve
    valuations exactly like the web dialog.
    """
    league = _league(game)
    team = _user_team(game)
    session = _session(game)
    state = get_draft_state(game)
    if league is None or session is None or not state.get("active"):
        return {"can_trade": False, "reason": "No draft active."}
    cur = state.get("current_overall")
    board = state.get("board", [])
    cur_row = next((b for b in board if b.get("overall") == cur), None)
    user_name = _safe(lambda: getattr(team, "team_name", ""), "") or ""
    if cur_row is None or cur_row.get("owner") != user_name:
        return {"can_trade": False,
                "reason": "Not your pick -- you can only trade your own "
                          "pick.",
                "owner": cur_row.get("owner") if cur_row else None,
                "overall": cur}

    try:
        import trade_engine as te  # noqa: F401 (parity import)
        import draft_night as dn
    except Exception:
        return {"can_trade": False, "reason": "Engine unavailable."}

    # Real DraftPick objects by overall, for ai_consider_trade parity.
    dp_by_overall = {}
    try:
        for rnd, tm, dp in session.materialize_order(league):
            if dp is not None:
                pid = _safe(lambda: str(getattr(dp, "id", "")), "")
                for s in (getattr(session, "slots", None) or []):
                    if str(s.get("pick_id") or "") == pid:
                        dp_by_overall[int(s.get("overall", 0) or 0)] = dp
                        break
    except Exception:
        pass

    class _SlotPick:
        def __init__(self, slot):
            self._slot = slot
            self.current_team = slot.get("owner")

    rnd = cur_row.get("round", 0)
    partners = []
    for b in board:
        try:
            if b.get("made") or b.get("overall", 0) <= (cur or 0):
                continue
            pname = b.get("owner", "")
            if not pname or pname == user_name:
                continue
            val = 0
            try:
                val = int(dn.pick_slot_value(b["overall"]))
            except Exception:
                pass
            pe = next((p for p in partners if p["name"] == pname), None)
            if pe is None:
                pe = {"name": pname, "picks": []}
                partners.append(pe)
            pe["picks"].append({"overall": b["overall"],
                               "round": b.get("round", 0), "value": val,
                               "dp": dp_by_overall.get(b["overall"])
                               or _SlotPick({"owner": pname})})
        except Exception:
            continue
    partners.sort(key=lambda p: p["name"])
    for pe in partners:
        pe["picks"].sort(key=lambda x: x["overall"])

    my_value = 0
    try:
        my_value = int(dn.pick_slot_value(cur))
    except Exception:
        pass
    return {
        "can_trade": True,
        "overall": cur,
        "round": rnd,
        "my_value": my_value,
        "my_dp": dp_by_overall.get(cur) or _SlotPick({"owner": user_name}),
        "partners": partners,
    }


def do_trade_pick_propose(game, partner, partner_overall, info=None):
    """Propose the pick swap (port of the draft_trade_pick bridge op).

    Synchronous here -- the native UI calls the game directly, so there
    is no command-queue round trip. AI verdict via
    trade_engine.ai_consider_trade; slot owners swap on accept; counter
    details returned for the dialog.
    """
    try:
        import trade_engine as te
        league = _league(game)
        user_team = _user_team(game)
        session = _session(game)
        partner_overall = int(partner_overall or 0)
        result = {"ok": False, "error": "draft not active"}
        if (league is not None and user_team is not None
                and session is not None and partner and partner_overall):
            slots = list(getattr(session, "slots", None) or [])
            cur = int(getattr(session, "current_pick", 0) or 0)
            overall = cur + 1
            user_name = getattr(user_team, "team_name", "")
            my_slot = next((s for s in slots
                            if int(s.get("overall", 0) or 0) == overall),
                           None)
            tgt_slot = next(
                (s for s in slots
                 if int(s.get("overall", 0) or 0) == partner_overall),
                None)
            if my_slot is None or my_slot.get("owner") != user_name:
                result = {"ok": False,
                          "error": "Pick is no longer on the clock."}
            elif (tgt_slot is None
                    or tgt_slot.get("owner") != partner):
                result = {"ok": False,
                          "error": "Partner pick no longer available."}
            elif any(int(p.get("overall", 0) or 0) == overall
                     for p in list(getattr(session, "picks", None)
                                   or [])):
                result = {"ok": False,
                          "error": "Pick was just made -- no trade."}
            else:
                partner_team = next(
                    (t for t in list(getattr(league, "teams", None)
                                     or [])
                     if getattr(t, "team_name", "") == partner),
                    None)
                if partner_team is None:
                    result = {"ok": False,
                              "error": "Partner team not found."}
                else:
                    my_dp = (info or {}).get("my_dp")
                    tgt_dp = None
                    for pe in (info or {}).get("partners", []):
                        if pe.get("name") == partner:
                            for pk in pe.get("picks", []):
                                if pk.get("overall") == partner_overall:
                                    tgt_dp = pk.get("dp")
                                    break
                    if my_dp is None:
                        class _SlotPick:
                            def __init__(self, slot):
                                self.current_team = slot.get("owner")
                        my_dp = _SlotPick(my_slot)
                    if tgt_dp is None:
                        class _SlotPick2:
                            def __init__(self, slot):
                                self.current_team = slot.get("owner")
                        tgt_dp = _SlotPick2(tgt_slot)
                    resp = te.ai_consider_trade(
                        partner_team, [my_dp], [tgt_dp],
                        user_team=user_team)
                    decision = getattr(resp, "decision", "reject")
                    if decision == "reject":
                        result = {"ok": False, "error": "rejected",
                                  "message": getattr(resp, "message",
                                                     "")}
                    elif decision == "counter":
                        result = {
                            "ok": False, "counter": True,
                            "message": getattr(resp, "message", ""),
                            "want_added": [te.asset_label(a)
                                           for a in getattr(
                                               resp, "want_added", [])
                                           or []],
                            "will_add": [te.asset_label(a)
                                         for a in getattr(
                                             resp, "will_add", [])
                                         or []],
                            "partner": partner,
                            "partner_overall": partner_overall,
                        }
                    else:
                        # Accept: swap slot owners (the durable journal).
                        my_slot["owner"] = partner
                        tgt_slot["owner"] = user_name
                        for dp, nm in ((my_dp, partner),
                                       (tgt_dp, user_name)):
                            try:
                                dp.current_team = nm
                            except Exception:
                                pass
                        gm = _resolve_gm(game)
                        summary = (f"{user_name} acquires pick "
                                   f"#{partner_overall} from {partner} "
                                   f"(gives #{overall}).")
                        if gm is not None:
                            if not hasattr(gm, "trade_history"):
                                gm.trade_history = []
                            try:
                                gm.trade_history.append(
                                    te.CompletedTrade(
                                        str(getattr(gm, "current_date",
                                                    "")),
                                        user_name, partner,
                                        [f"#{overall} pick"],
                                        [f"#{partner_overall} pick"],
                                        summary))
                            except Exception:
                                pass
                        try:
                            deals = getattr(league, "draft_day_deals",
                                            None)
                            if deals is None:
                                league.draft_day_deals = []
                                deals = league.draft_day_deals
                            deals.append("DRAFT TRADE: " + summary)
                        except Exception:
                            pass
                        try:
                            game.add_news("DRAFT TRADE: " + summary)
                        except Exception:
                            pass
                        result = {"ok": True, "summary": summary}
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- war-room shortlist (in-memory scratch state, desktop caps at 8) ---

_shortlists = {}


def _shortlist_key(game):
    league = _league(game)
    return id(league) if league is not None else 0


def shortlist_get(game):
    ids = _shortlists.setdefault(_shortlist_key(game), [])
    avail = {p["id"]: p for p in available_prospects(game)}
    return [avail[i] for i in ids if i in avail]


def shortlist_add(game, pid):
    ids = _shortlists.setdefault(_shortlist_key(game), [])
    pid = str(pid or "")
    if pid and pid not in ids:
        ids.append(pid)
        _shortlists[_shortlist_key(game)] = ids[:8]
    return len(_shortlists[_shortlist_key(game)])


def shortlist_remove(game, pid):
    ids = _shortlists.setdefault(_shortlist_key(game), [])
    pid = str(pid or "")
    if pid in ids:
        ids.remove(pid)
    return len(ids)


# ---------------------------------------------------------------------------
# Batch D: draft-day incoming calls (port of web_ui/screens/draft.py's DDT
# helpers; desktop parity via draft_day_trades.incoming_offer_for_user).
# When the user's club is on the clock in round 1, the most motivated AI
# club may call with a trade-up offer. Accept / Decline / Counter.
# At most one call per pick; declining never re-rings for that slot.
# ---------------------------------------------------------------------------

def _ddt_get(game, name, default=None):
    try:
        v = getattr(game, name, None)
        return v if v is not None else default
    except Exception:
        return default


def _ddt_pending(game):
    v = _ddt_get(game, "_native_ddt_call", None)
    return v if isinstance(v, dict) else None


def _ddt_store(game, call):
    try:
        game._native_ddt_call = call
    except Exception:
        pass


def _ddt_offered(game):
    return _ddt_get(game, "_native_ddt_offered_pick", None)


def _ddt_mark_offered(game, overall):
    try:
        game._native_ddt_offered_pick = int(overall)
    except Exception:
        pass


def _ddt_declined(game):
    try:
        d = getattr(game, "_native_ddt_declined", None)
        if not isinstance(d, set):
            d = set()
            game._native_ddt_declined = d
        return d
    except Exception:
        return set()


def _ddt_serialize_asset(a):
    """Draft pick -> dict. Draft-day calls only ever move picks."""
    try:
        from game_classes import DraftPick
        is_pick = isinstance(a, DraftPick)
    except Exception:
        is_pick = False
    if not is_pick:
        return None
    try:
        import trade_engine as te
        label = te.asset_label(a)
    except Exception:
        label = (f"{getattr(a, 'year', '?')} "
                 f"round {getattr(a, 'round', '?')} pick")
    return {
        "id": str(_safe(lambda: getattr(a, "id", ""), "")),
        "kind": "pick",
        "label": str(label),
        "year": _safe(lambda: int(getattr(a, "year", 0) or 0), 0),
        "round": _safe(lambda: int(getattr(a, "round", 0) or 0), 0),
        "overall_pick": _safe(lambda: getattr(a, "overall_pick", None)),
    }


def ddt_build_call(game):
    """Build the incoming call for the current pick, or None.

    Reuses draft_day_trades' offer-building + AI-verdict helpers.
    Never raises.
    """
    try:
        import draft_day_trades as ddt
        import trade_engine as te
    except Exception:
        return None
    try:
        import random as _rng
    except Exception:
        return None
    session = _session(game)
    if session is None:
        return None
    league = _league(game)
    user_team = _user_team(game)
    year = _safe(lambda: int(getattr(session, "year", 0) or 0), 0)
    cur_idx = _safe(lambda: int(getattr(session, "current_pick", 0) or 0),
                    0)
    overall = cur_idx + 1
    # Already rang / already declined for this slot.
    if _ddt_offered(game) == overall or overall in _ddt_declined(game):
        return None
    # Current slot must be round 1 and owned by the user.
    slots = _safe(lambda: list(getattr(session, "slots", None) or []),
                  []) or []
    cur_slot = next((s for s in slots
                     if int(s.get("overall", 0) or 0) == overall), None)
    if cur_slot is None or int(cur_slot.get("round", 0) or 0) != 1:
        return None
    uname = _safe(lambda: getattr(user_team, "team_name", ""), "")
    if str(cur_slot.get("owner", "") or "") != uname:
        return None
    _ddt_mark_offered(game, overall)
    if _rng.random() > 0.35:
        return None
    order = ddt._round1_order(league, year)
    board = ddt._draft_board(league)
    if not order or not board:
        return None
    try:
        ai_manager = _safe(lambda: getattr(game, "ai_manager", None))
    except Exception:
        ai_manager = None
    best = None
    for o2, t2, pk2 in order:
        try:
            if o2 <= overall or ddt._is_human(t2):
                continue
            pname = ddt._priority_name(ddt._priority_of(t2, ai_manager))
            tgt = ddt._trade_up_target(t2, o2, board, pname)
            if tgt is None:
                continue
            t_overall, prosp = tgt
            if t_overall != overall:
                continue
            mine = ddt._owned_picks(t2, year, 1)
            if not mine:
                continue
            offer = ddt._build_trade_up_offer(te, t2, mine[0], user_team,
                                              year)
            if offer is None:
                continue
            gives, gets = offer
            try:
                resp = te.ai_consider_trade(
                    user_team, list(gives), list(gets), user_team=t2)
            except Exception:
                continue
            if getattr(resp, "decision", "reject") == "reject":
                continue
            score = _rng.uniform(0, 1)
            if best is None or score > best[0]:
                best = (score, t2, gives, gets, prosp, resp)
        except Exception:
            continue
    if best is None:
        return None
    _s, caller, gives, gets, prosp, resp = best
    # Fold any AI counter into the terms before the user sees them
    # (desktop parity: the dialog shows exactly what accepting executes).
    if getattr(resp, "decision", "") == "counter":
        gives = list(gives) + list(getattr(resp, "want_added", None) or [])
        gets = list(gets) + list(getattr(resp, "will_add", None) or [])
    ser_gives = [a for a in (_ddt_serialize_asset(a) for a in gives) if a]
    ser_gets = [a for a in (_ddt_serialize_asset(a) for a in gets) if a]
    if not ser_gives or not ser_gets:
        return None
    try:
        why = ddt._call_why_lines(
            te, caller, prosp, board,
            ddt._priority_name(ddt._priority_of(caller, ai_manager)))
    except Exception:
        why = {}
    try:
        import scouting as _scmod
        tpot = _scmod.consensus_range(prosp)
    except Exception:
        tpot = "?"
    try:
        v_in = sum(te.asset_value(a) for a in gives)
        v_out = sum(te.asset_value(a) for a in gets)
        share = v_in / (v_in + v_out) if (v_in + v_out) > 0 else 0.5
    except Exception:
        share = 0.5
    vlabel = ("Value favors you" if share >= 0.55
              else "Value favors them" if share <= 0.45
              else "Roughly fair value")
    call = {
        "caller": _safe(lambda: getattr(caller, "team_name", "?"), "?"),
        "caller_id": str(_safe(lambda: getattr(caller, "id", ""), "")),
        "overall": overall,
        "year": year,
        "why_title": str(why.get("direction_short", "") or ""),
        "why_bullets": [str(b) for b in (why.get("bullets", None) or [])],
        "target": {
            "name": _safe(lambda: getattr(prosp, "full_name", "?"), "?"),
            "position": ddt._pos_of(prosp),
            "age": _safe(lambda: int(getattr(prosp, "age", 0) or 0), 0),
            "potential": str(tpot),
            "potential_grade": str(
                _safe(lambda: getattr(prosp, "potential_grade", "?"),
                      "?")),
        },
        "you_send": ser_gets,     # gets: the user's pick going out
        "you_receive": ser_gives,  # gives: the caller's assets coming in
        "value_label": vlabel,
        "give_ids": [a["id"] for a in ser_gives if a.get("id")],
        "get_ids": [a["id"] for a in ser_gets if a.get("id")],
    }
    _ddt_store(game, call)
    return call


def _ddt_find_pick(league, pid):
    for t in (getattr(league, "teams", None) or []):
        try:
            vals = (t.draft_picks or {}).values()
        except Exception:
            continue
        for v in vals:
            items = v if isinstance(v, list) else [v]
            for pko in items:
                try:
                    if str(getattr(pko, "id", "")) == str(pid):
                        return pko
                except Exception:
                    continue
    return None


def ddt_answer(game, action):
    """Answer the parked call: 'accept' | 'decline' | 'counter'.

    decline -> never re-rings for this slot.
    counter -> deeplink payload for the Trade Center (call stays parked).
    accept  -> execute the real engine trade synchronously, sync pick
               lists + session slot owners, record the deal. Returns
               (ok, summary_or_error, deeplink).
    """
    call = _ddt_pending(game)
    if call is None:
        return False, "No incoming call.", None
    if action == "decline":
        try:
            _ddt_declined(game).add(int(call.get("overall", 0) or 0))
        except Exception:
            pass
        _ddt_store(game, None)
        return True, "declined", None
    if action == "counter":
        deeplink = {
            "team": call.get("caller"),
            "give_picks": call.get("give_ids") or [],
            "want_picks": call.get("get_ids") or [],
            "note": (f"Counter {call.get('caller')}: adjust their "
                     f"trade-up offer for #{call.get('overall')}."),
        }
        try:
            game._native_draft_counter = deeplink
        except Exception:
            pass
        return True, "counter", deeplink
    if action == "accept":
        try:
            import trade_engine as _te
            import draft_day_trades as _ddt
        except Exception:
            return False, "Engine unavailable.", None
        league = _league(game)
        user_team = _user_team(game)
        caller = next(
            (t for t in (getattr(league, "teams", None) or [])
             if str(getattr(t, "team_name", ""))
             == str(call.get("caller") or "")),
            None)
        if caller is None or user_team is None:
            return False, "Could not resolve the clubs.", None
        caller_gives = [p for p in
                        (_ddt_find_pick(league, i)
                         for i in (call.get("give_ids") or []))
                        if p is not None]
        user_gives = [p for p in
                      (_ddt_find_pick(league, i)
                       for i in (call.get("get_ids") or []))
                      if p is not None]
        if not caller_gives or not user_gives:
            return False, "The picks are no longer available.", None
        try:
            done = _te.execute_trade(
                caller, user_team, caller_gives, user_gives,
                str(getattr(game, "current_date", "") or ""),
                league=league)
        except Exception as e:
            return False, f"Trade failed: {e}", None
        if str(getattr(done, "summary", "")).startswith("BLOCKED:"):
            return False, getattr(done, "summary",
                                  "Trade blocked."), None
        try:
            _ddt._sync_pick_lists(caller, user_team, caller_gives,
                                  user_gives)
        except Exception:
            pass
        try:
            sess = getattr(league, "entry_draft_session", None)
            slots = list(getattr(sess, "slots", None) or [])
            swaps = {}
            for pk in caller_gives:
                op_ = getattr(pk, "overall_pick", None)
                if op_:
                    swaps[int(op_)] = caller.team_name
            for pk in user_gives:
                op_ = getattr(pk, "overall_pick", None)
                if op_:
                    swaps[int(op_)] = user_team.team_name
            for s in slots:
                try:
                    o = int(s.get("overall", 0) or 0)
                    if o in swaps:
                        s["owner"] = swaps[o]
                except Exception:
                    continue
        except Exception:
            pass
        try:
            deals = getattr(league, "draft_day_deals", None)
            if deals is None:
                league.draft_day_deals = []
                deals = league.draft_day_deals
            deals.append("DRAFT TRADE: " + str(getattr(
                done, "summary", "Draft-day trade completed.")))
        except Exception:
            pass
        _ddt_store(game, None)
        return True, str(getattr(done, "summary",
                                 "Trade completed.")), None
    return False, "Unknown action.", None


# ---------------------------------------------------------------------------
# dialogs
# ---------------------------------------------------------------------------

def _ovr_color(v):
    if v >= 75:
        return "#4CAF50"
    if v >= 60:
        return "#8BC34A"
    if v >= 45:
        return "#FFC107"
    if v >= 30:
        return "#FF9800"
    return "#F44336"


class ScoutDialog(QDialog):
    """Scout report for one prospect."""

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scout Report -- " + report.get("name", "?"))
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        head = QLabel(f"<b>{report.get('name', '?')}</b>  "
                      f"{report.get('position', '')} \u00b7 "
                      f"Age {report.get('age', 0)} \u00b7 "
                      f"{report.get('overall', 0)} OVR \u00b7 "
                      f"Potential {report.get('potential', '?')}")
        head.setWordWrap(True)
        layout.addWidget(head)

        if report.get("report"):
            r = QLabel(report["report"])
            r.setWordWrap(True)
            layout.addWidget(r)

        for key, title in (("strengths", "Strengths"),
                           ("weaknesses", "Weaknesses")):
            vals = report.get(key) or []
            if vals:
                layout.addWidget(QLabel(f"<b>{title}</b>"))
                for s in vals:
                    lab = QLabel("\u2022 " + str(s))
                    lab.setWordWrap(True)
                    layout.addWidget(lab)

        attrs = report.get("attributes") or {}
        if attrs:
            layout.addWidget(QLabel("<b>Attributes</b>"))
            for k, v in attrs.items():
                layout.addWidget(
                    AttributeBar(k.replace("_", " ").title(), v))

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


class ProspectRow(QWidget):
    """One selectable prospect card for the Available/Shortlist tabs."""

    def __init__(self, prospect, on_name=None, parent=None):
        super().__init__(parent)
        self._prospect = prospect
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        ovr = QLabel(str(prospect.get("overall", 0)))
        ovr.setFixedSize(44, 44)
        ovr.setAlignment(Qt.AlignCenter)
        c = _ovr_color(prospect.get("overall", 0))
        ovr.setStyleSheet(
            f"background: {c}; color: #101418; font-weight: bold; "
            "font-size: 16px; border-radius: 6px;")
        layout.addWidget(ovr)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_btn = QPushButton(prospect.get("name", "?"))
        name_btn.setFlat(True)
        name_btn.setCursor(Qt.PointingHandCursor)
        name_btn.setStyleSheet(
            "text-align: left; font-weight: bold; font-size: 14px; "
            "color: #7cc4ff; padding: 0;")
        if on_name is not None:
            name_btn.clicked.connect(
                lambda _=False: on_name(prospect))
        info.addWidget(name_btn)
        sub = QLabel(f"{prospect.get('position', '')} \u00b7 "
                     f"Age {prospect.get('age', 0)} \u00b7 "
                     f"Potential {prospect.get('potential', '?')}")
        sub.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        info.addWidget(sub)
        layout.addLayout(info, 1)

        bar_wrap = QWidget()
        bar_l = QVBoxLayout(bar_wrap)
        bar_l.setContentsMargins(0, 0, 0, 0)
        bar_l.addWidget(AttributeBar("OVR",
                                     prospect.get("overall", 0) or 0))
        bar_wrap.setFixedWidth(180)
        layout.addWidget(bar_wrap)


class TradePickDialog(QDialog):
    """Trade-this-pick dialog (desktop windows.py DraftView parity)."""

    def __init__(self, game, info, parent=None):
        super().__init__(parent)
        self.game = game
        self.info = info
        self.sel = None  # (partner, overall)
        self.setWindowTitle("Trade This Pick")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        sub = QLabel(f"Your pick: #{info['overall']} "
                     f"(Round {info['round']}) \u00b7 slot value "
                     f"{info['my_value']}")
        sub.setObjectName("section-header")
        layout.addWidget(sub)

        prow = QHBoxLayout()
        prow.addWidget(QLabel("Partner"))
        self._partner = QComboBox()
        for pe in info["partners"]:
            self._partner.addItem(pe["name"])
        self._partner.currentTextChanged.connect(self._render_picks)
        prow.addWidget(self._partner, 1)
        layout.addLayout(prow)

        self._picks = QListWidget()
        self._picks.itemClicked.connect(self._on_pick_clicked)
        layout.addWidget(self._picks)

        self._note = QLabel("")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)

        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        self._propose = QPushButton("Propose Trade")
        self._propose.setObjectName("primary-btn")
        self._propose.setEnabled(False)
        self._propose.clicked.connect(self._on_propose)
        btns.addButton(self._propose, QDialogButtonBox.AcceptRole)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self._render_picks(self._partner.currentText())

    def _partner_entry(self, name):
        for pe in self.info["partners"]:
            if pe["name"] == name:
                return pe
        return None

    def _render_picks(self, name):
        self._picks.clear()
        self.sel = None
        self._propose.setEnabled(False)
        self._note.setText("")
        pe = self._partner_entry(name)
        for pk in (pe or {}).get("picks", []):
            item = QListWidgetItem(
                f"#{pk['overall']}  -- Round {pk['round']} "
                f"(slot value {pk['value']})")
            item.setData(Qt.UserRole, (pe["name"], pk["overall"],
                                       pk["value"]))
            self._picks.addItem(item)

    def _on_pick_clicked(self, item):
        partner, overall, value = item.data(Qt.UserRole)
        self.sel = (partner, overall)
        self._propose.setEnabled(True)
        uv, tv = self.info["my_value"], value
        if uv > tv:
            self._note.setText(
                f"You give #{self.info['overall']} (value {uv}), get "
                f"#{overall} (value {tv}). They may want more.")
        elif tv > uv:
            self._note.setText(
                f"You give #{self.info['overall']} (value {uv}), get "
                f"#{overall} (value {tv}). Good value for you.")
        else:
            self._note.setText("Even swap on paper.")

    def _on_propose(self):
        if not self.sel:
            return
        partner, overall = self.sel
        self._propose.setEnabled(False)
        self._note.setText("Proposing... the other GM is thinking.")
        # Synchronous in native (same thread as the game).
        res = do_trade_pick_propose(self.game, partner, overall,
                                    info=self.info)
        if res.get("ok"):
            self._note.setText("\u2705 " + str(res.get("summary", "")))
            QTimer.singleShot(1200, self.accept)
        elif res.get("counter"):
            parts = [f"Counter-offer: {res.get('message', '')}"]
            if res.get("want_added"):
                parts.append("They want: "
                             + ", ".join(res["want_added"]))
            if res.get("will_add"):
                parts.append("They add: "
                             + ", ".join(res["will_add"]))
            parts.append("Counters with extra assets aren't supported "
                         "here -- adjust in the Trade Center.")
            self._note.setText("\n".join(parts))
        else:
            self._note.setText("\u274c " + str(
                res.get("message") or res.get("error")
                or "Trade rejected."))


class IncomingCallDialog(QDialog):
    """Incoming draft-day trade call: Answer(Decline) / Counter / Accept."""

    def __init__(self, call, parent=None):
        super().__init__(parent)
        self.call = call
        self.action = None  # 'accept' | 'decline' | 'counter'
        self.setWindowTitle("\U0001f4de Incoming call")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        kicker = QLabel("\U0001f4de Incoming call")
        kicker.setStyleSheet("color: #e8b93c; font-weight: bold;")
        layout.addWidget(kicker)

        caller = QLabel(f"<b>{call.get('caller', '?')}</b>"
                        + (f"  <i>{call.get('why_title', '')}</i>"
                           if call.get("why_title") else ""))
        caller.setWordWrap(True)
        layout.addWidget(caller)

        bullets = call.get("why_bullets") or []
        if bullets:
            layout.addWidget(QLabel("<b>Why they're calling</b>"))
            for b in bullets:
                lab = QLabel("\u2022 " + str(b))
                lab.setWordWrap(True)
                layout.addWidget(lab)

        t = call.get("target") or {}
        layout.addWidget(QLabel("<b>Their target</b>"))
        tlab = QLabel(f"<b>{t.get('name', '?')}</b> \u00b7 "
                      f"{t.get('position', '')} \u00b7 "
                      f"Age {t.get('age', '')}"
                      + (f" \u00b7 Consensus potential: "
                         f"{t.get('potential', '')}"
                         if t.get("potential") else ""))
        tlab.setWordWrap(True)
        layout.addWidget(tlab)

        cols = QHBoxLayout()
        send_box = QGroupBox("You send")
        sl = QVBoxLayout(send_box)
        for a in call.get("you_send") or []:
            lab = QLabel("\u2022 " + str(a.get("label", "?")))
            lab.setWordWrap(True)
            sl.addWidget(lab)
        cols.addWidget(send_box)
        recv_box = QGroupBox("You receive")
        rl = QVBoxLayout(recv_box)
        for a in call.get("you_receive") or []:
            lab = QLabel("\u2022 " + str(a.get("label", "?")))
            lab.setWordWrap(True)
            rl.addWidget(lab)
        cols.addWidget(recv_box)
        layout.addLayout(cols)

        if call.get("value_label"):
            vlab = QLabel(call["value_label"])
            vlab.setStyleSheet("color: #9aa4b8; font-style: italic;")
            layout.addWidget(vlab)

        self._note = QLabel("")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)

        row = QHBoxLayout()
        row.addStretch()
        decline = QPushButton("Decline")
        decline.clicked.connect(lambda: self._done("decline"))
        row.addWidget(decline)
        counter = QPushButton("Counter")
        counter.clicked.connect(lambda: self._done("counter"))
        row.addWidget(counter)
        accept = QPushButton("Accept")
        accept.setObjectName("primary-btn")
        accept.clicked.connect(lambda: self._done("accept"))
        row.addWidget(accept)
        layout.addLayout(row)

    def _done(self, action):
        self.action = action
        self.accept()

    def set_note(self, text):
        self._note.setText(text)


# ---------------------------------------------------------------------------
# screen
# ---------------------------------------------------------------------------

_PACE_SECS = {"1x": 8, "4x": 2}

_BUZZ_KINDS = {
    "headline": "Headline",
    "beat": "Beat",
    "reach": "Reach",
    "steal": "Steal",
    "milestone": "Milestone",
    "pick": "Pick",
}


class DraftScreen(BaseScreen):
    """Draft war room: 7 tabs, draft clock + pace, incoming trade calls."""

    title = "Draft"

    def _build_body(self):
        # Summary line
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: #9aa4b8; font-size: 13px;")
        self._layout.addWidget(self._summary)

        # Draft clock + pace
        clock = QHBoxLayout()
        clock.addWidget(QLabel("<b>On the clock</b>"))
        self._clock_team = QLabel("--")
        clock.addWidget(self._clock_team)
        clock.addWidget(QLabel("|"))
        self._clock_time = QLabel("manual")
        clock.addWidget(self._clock_time)
        clock.addStretch()
        clock.addWidget(QLabel("Pace"))
        self._pace_group = QButtonGroup(self)
        self._pace_group.setExclusive(True)
        self._pace_btns = {}
        for i, (mode, label) in enumerate(
                (("off", "\u23f8 Manual"), ("1x", "1\u00d7"),
                 ("4x", "4\u00d7"), ("sim", "\u25b6\u25b6 My pick"))):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setProperty("pace", mode)
            b.clicked.connect(lambda _=False, m=mode: self.set_pace(m))
            self._pace_group.addButton(b, i)
            self._pace_btns[mode] = b
            clock.addWidget(b)
        self._pace_btns["off"].setChecked(True)
        self._clockbar = QWidget()
        self._clockbar.setLayout(clock)
        self._layout.addWidget(self._clockbar)

        # Tabs
        self._tabs = QTabWidget()
        self._board_tab = self._make_tab()
        self._tabs.addTab(self._board_tab, "Draft Board")
        self._avail_tab = self._make_tab()
        self._tabs.addTab(self._avail_tab, "Available")
        self._short_tab = self._make_tab()
        self._tabs.addTab(self._short_tab, "Shortlist")
        self._mypicks_tab = self._make_tab()
        self._tabs.addTab(self._mypicks_tab, "My Picks")
        self._buzz_tab = self._make_tab()
        self._tabs.addTab(self._buzz_tab, "Buzz")
        self._trades_tab = self._make_tab()
        self._tabs.addTab(self._trades_tab, "Trade Feed")
        self._grades_tab = self._make_tab()
        self._tabs.addTab(self._grades_tab, "Grades")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._layout.addWidget(self._tabs, 1)

        self._build_available_tab()

        # Pace / sim / call-poll timers
        self._pace = "off"
        self._pace_left = 0
        self._pace_timer = QTimer(self)
        self._pace_timer.setInterval(1000)
        self._pace_timer.timeout.connect(self._pace_tick)
        self._sim_timer = QTimer(self)
        self._sim_timer.setInterval(150)
        self._sim_timer.timeout.connect(self._sim_tick)
        self._call_timer = QTimer(self)
        self._call_timer.setInterval(5000)
        self._call_timer.timeout.connect(self._call_poll)
        self._parked_call = None

        # Available-tab state
        self._avail_pos = "All"
        self._avail_q = ""
        self._selected = None
        self._avail = []

    def _make_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        scroll.setWidget(inner)
        return scroll

    def _tab_inner(self, scroll):
        return scroll.widget()

    # -- Available tab widgets -----------------------------------------
    def _build_available_tab(self):
        inner = self._tab_inner(self._avail_tab)
        inner.layout().setAlignment(Qt.AlignTop)

        filt = QHBoxLayout()
        self._av_q = QLineEdit()
        self._av_q.setPlaceholderText("Search prospects...")
        self._av_q.textChanged.connect(self._on_av_q)
        filt.addWidget(self._av_q, 1)
        self._pos_group = QButtonGroup(self)
        self._pos_group.setExclusive(True)
        for i, pos in enumerate(("All", "C", "W", "D", "G")):
            b = QPushButton(pos)
            b.setCheckable(True)
            b.setChecked(pos == "All")
            b.clicked.connect(lambda _=False, p=pos: self._on_av_pos(p))
            self._pos_group.addButton(b, i)
            filt.addWidget(b)
        inner.layout().addLayout(filt)

        acts = QHBoxLayout()
        self._btn_draft = QPushButton("Draft Selected")
        self._btn_draft.setObjectName("primary-btn")
        self._btn_draft.setEnabled(False)
        self._btn_draft.clicked.connect(self._on_draft_selected)
        acts.addWidget(self._btn_draft)
        self._btn_sim = QPushButton("Sim Pick")
        self._btn_sim.clicked.connect(self._on_sim_pick)
        acts.addWidget(self._btn_sim)
        self._btn_scout = QPushButton("Scout Report")
        self._btn_scout.clicked.connect(self._on_scout)
        acts.addWidget(self._btn_scout)
        self._btn_short = QPushButton("+ Shortlist")
        self._btn_short.setEnabled(False)
        self._btn_short.clicked.connect(self._on_shortlist_add)
        acts.addWidget(self._btn_short)
        self._btn_tradepick = QPushButton("\u21c4 Trade This Pick")
        self._btn_tradepick.setVisible(False)
        self._btn_tradepick.clicked.connect(self._on_trade_pick)
        acts.addWidget(self._btn_tradepick)
        acts.addStretch()
        inner.layout().addLayout(acts)

        self._avail_list = QListWidget()
        self._avail_list.itemClicked.connect(self._on_avail_clicked)
        self._avail_list.itemDoubleClicked.connect(
            self._on_avail_double_clicked)
        inner.layout().addWidget(self._avail_list, 1)

    # -- navigation helper (show_screen lands when the shell wires it) -
    def _navigate(self, name):
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn(name)
            except Exception:
                pass

    def _open_profile(self, prospect):
        # Prospect profile deep-link: hands to the player profile screen
        # when the shell wires show_screen; otherwise falls back to the
        # scout report so the click always lands somewhere real.
        pid = prospect.get("id")
        fn = getattr(self.main_window, "show_screen", None)
        if callable(fn):
            try:
                fn("player_profile")
                return
            except Exception:
                pass
        rep = scout_report(self.game, pid)
        if not rep.get("error"):
            ScoutDialog(rep, self).exec()

    # -- lifecycle -------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        if not self._call_timer.isActive():
            self._call_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._stop_timers()

    def _stop_timers(self):
        self._pace_timer.stop()
        self._sim_timer.stop()
        self._call_timer.stop()

    def refresh(self):
        state = get_draft_state(self.game)
        self._refresh_summary(state)
        self._refresh_clock(state)
        self._refresh_board(state)
        self._refresh_mypicks(state)
        self._on_tab_changed(self._tabs.currentIndex())

    def _refresh_summary(self, state):
        if not state.get("active"):
            self._summary.setText("No draft in progress. The entry draft "
                                  "appears here once the season reaches "
                                  "draft day.")
            return
        my = state.get("user_picks") or []
        if my:
            nxt = ", ".join("#%d" % p for p in my[:5])
            if len(my) > 5:
                nxt += f" +{len(my) - 5} more"
            mine = f"Your next pick{'s' if len(my) > 1 else ''}: {nxt}"
        else:
            mine = "No remaining picks"
        self._summary.setText(
            f"Pick {state['current_overall']} of {state['total_slots']} "
            f"({state['made_count']} made)  \u00b7  {mine}")

    def _refresh_clock(self, state):
        active = bool(state.get("active"))
        self._clockbar.setVisible(active)
        if not active:
            return
        cur = next((b for b in state.get("board", [])
                    if b.get("is_current")), None)
        on_clock_user = bool(cur and cur.get("is_user_pick")
                             and not cur.get("made"))
        self._on_clock_user = on_clock_user
        if cur:
            self._clock_team.setText(
                cur.get("owner", "--")
                + (" \u2b50 (you)" if cur.get("is_user_pick") else ""))
        else:
            self._clock_team.setText("--")
        if self._pace == "off":
            self._clock_time.setText("manual")
        elif self._pace == "sim":
            self._clock_time.setText("\u25b6\u25b6 to your pick")
        else:
            self._clock_time.setText(f"{self._pace_left}s")
        self._btn_tradepick.setVisible(on_clock_user)

    # -- tabs ------------------------------------------------------------
    def _on_tab_changed(self, idx):
        name = self._tabs.tabText(idx)
        if name == "Available":
            self._reload_available()
        elif name == "Shortlist":
            self._reload_shortlist()
        elif name == "My Picks":
            self._refresh_mypicks(get_draft_state(self.game))
        elif name == "Buzz":
            self._reload_buzz()
        elif name == "Trade Feed":
            self._reload_trades()
        elif name == "Grades":
            self._reload_grades()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh_board(self, state):
        inner = self._tab_inner(self._board_tab)
        layout = inner.layout()
        self._clear_layout(layout)
        layout.setAlignment(Qt.AlignTop)
        if not state.get("active"):
            layout.addWidget(QLabel("No draft in progress."))
            return
        last_round = None
        for b in state.get("board", []):
            if b.get("round") != last_round:
                last_round = b.get("round")
                h = QLabel(f"Round {last_round}"
                           if last_round else "Picks")
                h.setObjectName("section-header")
                layout.addWidget(h)
            row = QHBoxLayout()
            num = QLabel(f"#{b['overall']}")
            num.setFixedWidth(56)
            num.setStyleSheet("font-weight: bold;")
            row.addWidget(num)
            owner = QLabel(b.get("owner", "")
                           + (" \u2b50" if b.get("is_user_pick") else ""))
            owner.setFixedWidth(200)
            row.addWidget(owner)
            pr = b.get("prospect") or {}
            if b.get("made"):
                pl = QLabel(f"{pr.get('name', '?')}  "
                            f"<span style='color:#9aa4b8'>"
                            f"{pr.get('position', '')}"
                            f"{' \u00b7 ' + str(pr['age']) + ' yrs' if pr.get('age') else ''}"
                            f"{' \u00b7 OVR ' + str(pr['overall']) if pr.get('overall') else ''}"
                            f"</span>")
            else:
                pl = QLabel("<i>To be selected...</i>")
                pl.setStyleSheet("color: #9aa4b8;")
            row.addWidget(pl, 1)
            wrap = QWidget()
            wrap.setLayout(row)
            if b.get("is_current"):
                wrap.setStyleSheet(
                    "background: #24314d; border: 1px solid #3B82F6; "
                    "border-radius: 6px;")
            elif b.get("is_user_pick"):
                wrap.setStyleSheet(
                    "background: #1c2438; border-radius: 6px;")
            layout.addWidget(wrap)

    # -- Available tab ---------------------------------------------------
    def _on_av_pos(self, pos):
        self._avail_pos = pos
        self._reload_available()

    def _on_av_q(self, text):
        self._avail_q = text
        self._reload_available()

    def _reload_available(self):
        self._avail = filter_prospects(available_prospects(self.game),
                                       self._avail_pos, self._avail_q)
        self._selected = None
        self._btn_draft.setEnabled(False)
        self._btn_short.setEnabled(False)
        self._avail_list.clear()
        for p in self._avail:
            item = QListWidgetItem()
            row = ProspectRow(p, on_name=self._open_profile)
            item.setSizeHint(row.sizeHint())
            self._avail_list.addItem(item)
            self._avail_list.setItemWidget(item, row)
            item.setData(Qt.UserRole, p)

    def _on_avail_clicked(self, item):
        p = item.data(Qt.UserRole)
        self._selected = p
        self._btn_draft.setEnabled(True)
        self._btn_short.setEnabled(True)

    def _on_avail_double_clicked(self, item):
        p = item.data(Qt.UserRole)
        if p:
            self._selected = p
            self._ask_draft_confirm(p)

    def _ask_draft_confirm(self, p):
        reply = QMessageBox.question(
            self, "Confirm Draft Pick",
            f"Draft {p['name']} ({p['position']}, {p['overall']} OVR)? "
            "This cannot be undone.",
            QMessageBox.Cancel | QMessageBox.Ok,
            QMessageBox.Cancel)
        if reply != QMessageBox.Ok:
            return
        ok, msg = do_draft_pick(self.game, p["id"])
        if not ok:
            QMessageBox.warning(self, "Draft", msg)
        self.set_pace("off")
        self.refresh()

    def _on_draft_selected(self):
        if self._selected:
            self._ask_draft_confirm(self._selected)

    def _on_scout(self):
        p = self._selected
        if not p:
            QMessageBox.information(self, "Scout Report",
                                    "Select a prospect first.")
            return
        rep = scout_report(self.game, p["id"])
        if rep.get("error"):
            QMessageBox.warning(self, "Scout Report", rep["error"])
            return
        ScoutDialog(rep, self).exec()

    def _on_shortlist_add(self):
        if self._selected:
            shortlist_add(self.game, self._selected["id"])
            self._reload_shortlist()

    def _on_trade_pick(self):
        info = trade_pick_info(self.game)
        if not info.get("can_trade"):
            QMessageBox.warning(self, "Trade This Pick",
                                info.get("reason",
                                         "Cannot trade this pick."))
            return
        dlg = TradePickDialog(self.game, info, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()

    # -- Shortlist tab ---------------------------------------------------
    def _reload_shortlist(self):
        inner = self._tab_inner(self._short_tab)
        layout = inner.layout()
        self._clear_layout(layout)
        layout.setAlignment(Qt.AlignTop)
        rows = shortlist_get(self.game)
        note = QLabel("Your war-room shortlist -- prospects you're "
                      "watching. Capped at 8.")
        note.setStyleSheet("color: #9aa4b8; font-size: 12px;")
        layout.addWidget(note)
        if not rows:
            layout.addWidget(QLabel("Shortlist is empty. Select a "
                                    "prospect on the Available tab and "
                                    "hit + Shortlist."))
            return
        for p in rows:
            h = QHBoxLayout()
            card = ProspectRow(p, on_name=self._open_profile)
            h.addWidget(card, 1)
            rm = QPushButton("Remove")
            rm.clicked.connect(
                lambda _=False, pid=p["id"]: self._shortlist_remove(pid))
            h.addWidget(rm)
            wrap = QWidget()
            wrap.setLayout(h)
            layout.addWidget(wrap)

    def _shortlist_remove(self, pid):
        shortlist_remove(self.game, pid)
        self._reload_shortlist()

    # -- My Picks tab ----------------------------------------------------
    def _refresh_mypicks(self, state):
        inner = self._tab_inner(self._mypicks_tab)
        layout = inner.layout()
        self._clear_layout(layout)
        layout.setAlignment(Qt.AlignTop)
        if not state.get("active"):
            layout.addWidget(QLabel("No draft in progress."))
            return
        mine = [b for b in state.get("board", [])
                if b.get("is_user_pick")]
        if not mine:
            layout.addWidget(QLabel("You have no picks in this draft."))
            return
        for b in mine:
            if b.get("made"):
                pr = b.get("prospect") or {}
                txt = f"#{b['overall']}  Round {b['round']}  -- " \
                      f"{pr.get('name', 'picked')}"
            else:
                txt = f"#{b['overall']}  Round {b['round']}  -- Available"
            lab = QLabel(txt)
            if not b.get("made"):
                lab.setStyleSheet("font-weight: bold;")
            layout.addWidget(lab)

    # -- Buzz tab --------------------------------------------------------
    def _reload_buzz(self):
        inner = self._tab_inner(self._buzz_tab)
        layout = inner.layout()
        self._clear_layout(layout)
        layout.setAlignment(Qt.AlignTop)
        items = buzz_items(self.game)
        if not items:
            layout.addWidget(QLabel("No buzz yet.\nThe rumor mill fires "
                                    "up once the draft class takes "
                                    "shape."))
            return
        for it in items:
            box = QGroupBox()
            bl = QVBoxLayout(box)
            top = QHBoxLayout()
            kind = QLabel(_BUZZ_KINDS.get(it.get("kind"), "Pick"))
            kind.setStyleSheet("color: #7cc4ff; font-weight: bold; "
                               "font-size: 12px;")
            top.addWidget(kind)
            if it.get("overall"):
                top.addWidget(QLabel(f"Pick #{it['overall']}"))
            if it.get("team"):
                tb = QPushButton(it["team"])
                tb.setFlat(True)
                tb.setCursor(Qt.PointingHandCursor)
                tb.setStyleSheet("color: #7cc4ff; text-align: left; "
                                 "padding: 0;")
                tb.clicked.connect(
                    lambda _=False: self._navigate("team"))
                top.addWidget(tb)
            top.addStretch()
            bl.addLayout(top)
            title = QLabel(f"<b>{it.get('title', '')}</b>")
            title.setWordWrap(True)
            bl.addWidget(title)
            text = QLabel(it.get("text", ""))
            text.setWordWrap(True)
            text.setStyleSheet("color: #c7cede;")
            bl.addWidget(text)
            if it.get("prospect_id"):
                sb = QPushButton("View scout report \u2192")
                sb.setFlat(True)
                sb.setCursor(Qt.PointingHandCursor)
                sb.setStyleSheet("color: #7cc4ff; text-align: left; "
                                 "padding: 0;")
                pid = it["prospect_id"]
                sb.clicked.connect(
                    lambda _=False, _pid=pid: self._open_scout(_pid))
                bl.addWidget(sb)
            layout.addWidget(box)

    def _open_scout(self, pid):
        rep = scout_report(self.game, pid)
        if rep.get("error"):
            QMessageBox.warning(self, "Scout Report", rep["error"])
            return
        ScoutDialog(rep, self).exec()

    # -- Trade feed tab --------------------------------------------------
    def _reload_trades(self):
        inner = self._tab_inner(self._trades_tab)
        layout = inner.layout()
        self._clear_layout(layout)
        layout.setAlignment(Qt.AlignTop)
        deals = trade_feed(self.game)
        if not deals:
            layout.addWidget(QLabel("No draft-day trades recorded yet.\n"
                                    "Deals made on draft day land here, "
                                    "newest first."))
            return
        for d in deals:
            box = QGroupBox()
            bl = QVBoxLayout(box)
            top = QHBoxLayout()
            kind = QLabel("Rumor" if d["kind"] == "rumor" else "Deal")
            kind.setStyleSheet(
                "color: #e8b93c; font-weight: bold;"
                if d["kind"] == "rumor"
                else "color: #46c93a; font-weight: bold;")
            top.addWidget(kind)
            if d.get("year"):
                top.addWidget(QLabel(str(d["year"])))
            top.addStretch()
            bl.addLayout(top)
            text = QLabel(d["text"])
            text.setWordWrap(True)
            bl.addWidget(text)
            if d.get("teams"):
                chips = QHBoxLayout()
                for tn in d["teams"]:
                    tb = QPushButton(tn)
                    tb.setFlat(True)
                    tb.setCursor(Qt.PointingHandCursor)
                    tb.setStyleSheet("color: #7cc4ff; padding: 0;")
                    tb.clicked.connect(
                        lambda _=False: self._navigate("team"))
                    chips.addWidget(tb)
                chips.addStretch()
                bl.addLayout(chips)
            layout.addWidget(box)

    # -- Grades tab ------------------------------------------------------
    def _reload_grades(self):
        inner = self._tab_inner(self._grades_tab)
        layout = inner.layout()
        self._clear_layout(layout)
        data = draft_grades(self.game)
        rows = data.get("grades") or []
        if not rows:
            layout.addWidget(QLabel("No drafts to grade yet.\nGrades post "
                                    "here once a draft finishes -- or "
                                    "mid-draft as a live projection."))
            return
        head = QLabel(
            f"{'Live Projection' if data.get('source') == 'live' else 'Final Grades'}"
            + (f" -- {data['year']} Entry Draft" if data.get("year")
               else ""))
        head.setObjectName("section-header")
        layout.addWidget(head)
        if data.get("note"):
            note = QLabel(data["note"])
            note.setWordWrap(True)
            note.setStyleSheet("color: #9aa4b8; font-size: 12px;")
            layout.addWidget(note)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Team", "Grade", "Score"])
        tree.setColumnWidth(0, 260)
        for i, g in enumerate(rows):
            top = QTreeWidgetItem(
                tree, [f"{i + 1}. {g['name']}", g["grade"],
                       f"{g['score']:.2f}\u00d7"])
            top.setBackground(1, self._grade_bg(g.get("color")))
            for p in g.get("picks") or []:
                delta = p.get("delta", 0)
                dstr = f"{'+' if delta >= 0 else ''}{delta:,}"
                QTreeWidgetItem(
                    top, [f"#{p['overall']} Rd {p['round']} "
                          f"{p['player']}", "",
                          f"slot {p['expected']:,} vs value "
                          f"{p['value']:,} ({dstr})"])
            if not g.get("picks"):
                QTreeWidgetItem(
                    top, ["Graded on total player value vs expected slot "
                          "value across the class (engine curve): "
                          f"{g['score']:.2f}\u00d7 expected value.", "",
                          ""])
        tree.expandToDepth(0)
        layout.addWidget(tree, 1)

    @staticmethod
    def _grade_bg(color):
        from PySide6.QtGui import QColor, QBrush
        try:
            return QBrush(QColor(str(color or "#666666")))
        except Exception:
            return QBrush(QColor("#666666"))

    # -- pace / clock ----------------------------------------------------
    def set_pace(self, mode):
        self._stop_pace()
        self._pace = mode
        for m, b in self._pace_btns.items():
            b.setChecked(m == mode)
        if mode == "off":
            self.refresh()
            return
        if mode == "sim":
            self._sim_timer.start()
            self.refresh()
            return
        self._pace_left = _PACE_SECS.get(mode, 8)
        self._pace_timer.start()
        self.refresh()

    def _stop_pace(self):
        self._pace_timer.stop()
        self._sim_timer.stop()
        self._pace = "off"
        for m, b in self._pace_btns.items():
            b.setChecked(m == "off")

    def _pace_tick(self):
        self._pace_left -= 1
        if self._pace_left <= 0:
            self._pace_left = _PACE_SECS.get(self._pace, 8)
            ok, _msg = do_sim_pick(self.game)
            if not ok:
                self.set_pace("off")
                return
            self.refresh()
            state = get_draft_state(self.game)
            if not state.get("active") or getattr(self, "_on_clock_user",
                                                  False):
                self.set_pace("off")
        else:
            self._clock_time.setText(f"{self._pace_left}s")

    def _sim_tick(self):
        # "My pick" mode: sim one pick at a time until the user's pick
        # is on the clock (or the draft ends).
        state = get_draft_state(self.game)
        if not state.get("active"):
            self.set_pace("off")
            return
        cur = next((b for b in state.get("board", [])
                    if b.get("is_current")), None)
        if cur and cur.get("is_user_pick") and not cur.get("made"):
            self.set_pace("off")
            return
        ok, _msg = do_sim_pick(self.game)
        if not ok:
            self.set_pace("off")
            return
        self.refresh()

    def _on_sim_pick(self):
        ok, msg = do_sim_pick(self.game)
        if not ok:
            QMessageBox.warning(self, "Sim Pick", msg)
        self.refresh()

    # -- incoming calls --------------------------------------------------
    def _call_poll(self):
        if self._parked_call is not None:
            return
        try:
            state = get_draft_state(self.game)
        except Exception:
            return
        if not state.get("active"):
            return
        call = ddt_build_call(self.game)
        if call:
            self._parked_call = call
            self.set_pace("off")
            self._show_call(call)

    def _show_call(self, call):
        dlg = IncomingCallDialog(call, self)
        dlg.exec()
        action = dlg.action
        self._parked_call = None
        if action is None:
            # Dialog closed without answering: treat as decline so it
            # doesn't park forever, but let it re-ring on a later pick.
            _ddt_store(self.game, None)
            self.refresh()
            return
        if action == "counter":
            _ddt_store(self.game, call)  # stays parked (web parity)
            self._parked_call = call
        ok, msg, deeplink = ddt_answer(self.game, action)
        if action == "counter":
            self._parked_call = None
            QMessageBox.information(
                self, "Counter Offer",
                "Their offer is staged in the Trade Center.\n"
                f"{(deeplink or {}).get('note', '')}\n\n"
                "Adjust the assets there to send your counter.")
            self._navigate("trades")
        elif action == "accept":
            if ok:
                QMessageBox.information(self, "Trade Accepted", msg)
            else:
                QMessageBox.warning(self, "Trade Failed", msg)
        self.refresh()
