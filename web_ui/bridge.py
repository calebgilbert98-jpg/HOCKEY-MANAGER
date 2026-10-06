# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Web UI bridge (2026-10-04).

Connects the Flask web frontend to the live game. Same-process design:

- READS: Flask handlers read the live GameManager/user_team objects
  directly. Never touch a Tk widget from a Flask thread.
- WRITES: Flask POSTs enqueue command dicts on COMMAND_QUEUE; the Tk
  mainloop drains them via root.after(). This keeps all mutation on the
  main thread where Tkinter is safe.

Serialization: game objects -> plain dicts via the to_web_* helpers.
Never leak raw model objects to JSON.

Usage (from the game):
    from web_ui.bridge import start_web_server
    start_web_server(app)   # app = HockeyManagerGUI instance
"""
import queue
import sys
import threading
import hashlib
import os
import re
from datetime import date, datetime

COMMAND_QUEUE = queue.Queue()
_web_app_ref = None       # the live HockeyManagerGUI (or mock in tests)
_server_thread = None

# Watch mode: 'watch' = show visualizer for games, 'quick' = sim instantly.
# Toggleable in Settings; the Continue flow respects it.
_watch_mode = 'quick'
_last_heartbeat = 0.0      # last time the browser tab pinged
_heartbeat_seen = False   # True once the tab has checked in at least once
_shutting_down = False


def set_app(game_app):
    """Attach the live game after web setup completes."""
    global _web_app_ref
    _web_app_ref = game_app


def server_running():
    """True if the Flask thread is already up (web setup flow)."""
    return _server_thread is not None and _server_thread.is_alive()


def note_heartbeat():
    global _last_heartbeat, _heartbeat_seen
    import time
    _last_heartbeat = time.time()
    _heartbeat_seen = True


def heartbeat_expired(timeout_s=150):
    """True if the browser tab has gone silent (closed/crashed)."""
    import time
    return (_heartbeat_seen and not _shutting_down
            and time.time() - _last_heartbeat > timeout_s)


# ------------------------------------------------------------------
# Serialization helpers
# ------------------------------------------------------------------
def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _overall(p):
    """Get player overall: tries overall_rating() method first (game_classes),
    then overall attribute, then 0."""
    v = _safe(lambda: p.overall_rating())
    if v is None:
        v = _safe(lambda: getattr(p, "overall", 0), 0)
    try:
        return int(v or 0)
    except Exception:
        return 0


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_TEAM_PRIMARY = "#3B82F6"    # deep blue (current UI accent)
_DEFAULT_TEAM_SECONDARY = "#1E40AF"


def _valid_hex(value, fallback):
    if isinstance(value, str) and _HEX_COLOR_RE.match(value.strip()):
        return value.strip().upper()
    return fallback


def _team_colors_dict(team):
    """Subtle team-color tinting for the hub. Fallback chain:
    1. team.primary_color / team.secondary_color attributes
    2. team_identity_system lookup by team name (case-insensitive)
    3. deep-blue defaults.
    Always returns validated hex strings; never raises."""
    primary = _safe(lambda: getattr(team, "primary_color", None))
    secondary = _safe(lambda: getattr(team, "secondary_color", None))
    try:
        if not (isinstance(primary, str) and _HEX_COLOR_RE.match(primary.strip())):
            from team_identity_system import nhl_identity
            name = _safe(lambda: getattr(team, "team_name", ""), "") or ""
            colors = None
            try:
                colors = nhl_identity.get_team_colors(name) if name else None
            except Exception:
                colors = None
            if colors is None and name:
                key = str(name).strip().lower()
                for n, c in _safe(lambda: nhl_identity.team_colors.items(), []) or []:
                    if str(n).lower() == key:
                        colors = c
                        break
            if colors is not None:
                primary = _safe(lambda: colors.primary, primary)
                if not (isinstance(secondary, str) and _HEX_COLOR_RE.match(secondary.strip())):
                    secondary = _safe(lambda: colors.secondary, secondary)
    except Exception:
        pass
    return {
        "primary": _valid_hex(primary, _DEFAULT_TEAM_PRIMARY),
        "secondary": _valid_hex(secondary, _DEFAULT_TEAM_SECONDARY),
    }


# Clean position abbreviations: PlayerPosition.CENTER -> "C", etc.
# The raw str(enum) gives "PlayerPosition.CENTER" which looks terrible in the UI.
_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}


def _clean_position(pos):
    """Map a position enum/string to a clean abbreviation."""
    try:
        s = str(pos or "")
        # Handle "PlayerPosition.CENTER" -> "CENTER" -> "C"
        if "." in s:
            s = s.split(".")[-1]
        s = s.strip().upper()
        return _POSITION_ABBR.get(s, s or "?")
    except Exception:
        return "?"


# ------------------------------------------------------------------
# Player portraits (NHL 14-style generated faces)
# ------------------------------------------------------------------
def _resolve_portrait_dir():
    """Find the portraits dir in dev, PyInstaller bundle, or cwd layouts."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "static", "img", "portraits"),
        os.path.join(os.path.dirname(__file__), "..", "web_ui", "static", "img", "portraits"),
        os.path.join(os.getcwd(), "web_ui", "static", "img", "portraits"),
    ]
    # PyInstaller one-dir bundle: data files live under sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.insert(0, os.path.join(meipass, "web_ui", "static", "img", "portraits"))
    for c in candidates:
        try:
            if os.path.isdir(c):
                return os.path.normpath(c)
        except Exception:
            continue
    return os.path.normpath(candidates[0])

_PORTRAIT_DIR = _resolve_portrait_dir()
_portrait_files = None  # cached sorted list; rescanned on demand


def _portrait_file_list():
    """Sorted portrait filenames, rescanned when the dir changes."""
    global _portrait_files
    try:
        names = sorted(
            f for f in os.listdir(_PORTRAIT_DIR)
            if f.lower().endswith((".webp", ".png", ".jpg", ".jpeg"))
        )
    except Exception:
        names = []
    if _portrait_files != names:
        _portrait_files = names
    return _portrait_files


def player_portrait(player_id):
    """Deterministic portrait URL for any player ID.

    Hash mod portrait count, so adding portrait_05.webp etc. is picked up
    automatically. Returns None when the portraits directory is empty or
    missing (callers fall back to the current display).
    """
    try:
        files = _portrait_file_list()
        if not files:
            return None
        h = hashlib.md5(str(player_id).encode("utf-8")).hexdigest()
        return "/static/img/portraits/" + files[int(h, 16) % len(files)]
    except Exception:
        return None


def to_web_player(p):
    """Player -> JSON-safe dict."""
    pid = _safe(lambda: str(getattr(p, "id", id(p))))
    return {
        "id": pid,
        "portrait": player_portrait(pid),
        "name": _safe(lambda: getattr(p, "full_name", "?")),
        "position": _safe(lambda: _clean_position(getattr(p, "primary_position", "")), "?"),
        "age": _safe(lambda: int(getattr(p, "age", 0) or 0)),
        "overall": _overall(p),
        "salary": _safe(lambda: int(
            getattr(p, "salary", 0)
            or getattr(getattr(p, "contract", None), "salary", 0)
            or 0)),
        "captaincy": _safe(lambda: getattr(p, "captaincy", "") or ""),
        "injured": _safe(lambda: bool(getattr(p, "is_injured", False))),
    }


def to_web_message(m):
    """EmailMessage -> JSON-safe dict (Gmail-style row data)."""
    try:
        overdue = bool(m.is_overdue())
    except Exception:
        overdue = False
    try:
        age = int(m.get_age_days())
    except Exception:
        age = 0
    if age <= 0:
        date_str = "Today"
    elif age == 1:
        date_str = "Yesterday"
    else:
        try:
            date_str = m.date_sent.strftime("%m/%d")
        except Exception:
            date_str = ""
    snippet = _safe(lambda: (getattr(m, "content", "") or "").replace("\n", " ").strip()[:120], "")
    return {
        "id": _safe(lambda: str(getattr(m, "id", ""))),
        "sender": _safe(lambda: getattr(m, "sender", "") or "(no sender)"),
        "subject": _safe(lambda: getattr(m, "subject", "") or "(no subject)"),
        "snippet": snippet,
        "category": _safe(lambda: getattr(m, "category", "General")),
        "date": date_str,
        "is_read": _safe(lambda: bool(getattr(m, "is_read", False))),
        "is_urgent": _safe(lambda: bool(getattr(m, "is_urgent", False))),
        "is_important": _safe(lambda: bool(getattr(m, "is_important", False))),
        "requires_response": _safe(lambda: bool(getattr(m, "requires_response", False))),
        "is_overdue": overdue,
        "is_saved": _safe(lambda: bool(getattr(m, "is_saved", False))),
        "priority": _safe(lambda: int(getattr(m, "priority", 1) or 1)),
        "action_type": _safe(lambda: getattr(m, "action_type", None)),
        "content": _safe(lambda: getattr(m, "content", ""), ""),
    }


# Canonical NHL abbreviations: Team objects don't carry an `abbreviation`
# attribute, so the web UI maps full names here (else "Boston Bruins"
# becomes "BB" and nothing matches "BOS").
TEAM_ABBR = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN", "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL", "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD", "New York Islanders": "NYI",
    "New York Rangers": "NYR", "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS", "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL", "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR", "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA", "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


def to_web_team(t):
    """Team -> JSON-safe dict (hub header data)."""
    _tname = _safe(lambda: str(getattr(t, "team_name", "?")), "?")
    _abbr = (_safe(lambda: getattr(t, "abbreviation", ""), "") or
             TEAM_ABBR.get(_tname) or
             "".join(w[0] for w in _tname.split()[:3]).upper())
    wins = _safe(lambda: int(getattr(t, "wins", 0) or 0), 0)
    losses = _safe(lambda: int(getattr(t, "losses", 0) or 0), 0)
    otl = _safe(lambda: int(getattr(t, "ot_losses", 0) or 0), 0)
    return {
        "name": _tname,
        "city": _safe(lambda: getattr(t, "city", "")),
        "abbr": _abbr,
        "wins": wins,
        "losses": losses,
        "otl": otl,
        # JS hub expects team.record.{w,l,otl} (matches mock shape)
        "record": {"w": wins, "l": losses, "otl": otl},
        "roster_size": _safe(lambda: len(getattr(t, "roster", None) or [])),
    }


def _stat_strip(team, gm, t):
    """v0.18.4-style team stat strip. All reads defensive; missing -> None."""
    strip = {
        "record": f"{t.get('wins', 0)}-{t.get('losses', 0)}-{t.get('otl', 0)}",
        "gp": None, "points": None, "div_rank": None,
        "gpg": None, "off_rank": None, "gapg": None, "def_rank": None,
        "pp_pct": None, "pk_pct": None,
        "streak": None, "last10": None, "cap_space": None,
    }
    try:
        if team is None or gm is None:
            return strip
        league = _safe(lambda: gm.league)
        teams = _safe(lambda: list(league.teams), []) or [] if league else []
        me_name = _safe(lambda: getattr(team, "team_name", ""), "")
        my_div = _safe(lambda: getattr(team, "division", ""), "") or ""

        gp = _safe(lambda: int(getattr(team, "games_played", 0) or 0), 0)
        gf = _safe(lambda: int(getattr(team, "goals_for", 0) or 0), 0)
        ga = _safe(lambda: int(getattr(team, "goals_against", 0) or 0), 0)
        strip["gp"] = gp
        strip["points"] = t.get("wins", 0) * 2 + t.get("otl", 0)
        strip["gpg"] = round(gf / gp, 2) if gp else 0.0
        strip["gapg"] = round(ga / gp, 2) if gp else 0.0
        cap = _safe(lambda: getattr(team, "cap_space", None), None)
        strip["cap_space"] = cap

        # League-wide ranks: points (division), offense, defense
        if teams:
            table = _safe(lambda: dict(getattr(league, "standings", None) or {}), {}) or {}
            div_pts, off, deff = [], [], []
            for tm in teams:
                try:
                    nm = _safe(lambda: getattr(tm, "team_name", ""), "")
                    if not nm:
                        continue
                    row = table.get(nm, {}) if isinstance(table.get(nm), dict) else {}
                    p = int(row.get("Points", 0) or 0)
                    dv = _safe(lambda: getattr(tm, "division", ""), "") or ""
                    tg = _safe(lambda: int(getattr(tm, "games_played", 0) or 0), 0)
                    tgf = _safe(lambda: int(getattr(tm, "goals_for", 0) or 0), 0)
                    tga = _safe(lambda: int(getattr(tm, "goals_against", 0) or 0), 0)
                    if my_div and dv == my_div:
                        div_pts.append((nm, p))
                    if tg:
                        off.append((nm, tgf / tg))
                        deff.append((nm, tga / tg))
                except Exception:
                    continue
            div_pts.sort(key=lambda x: -x[1])
            for i, (nm, _) in enumerate(div_pts, 1):
                if nm == me_name:
                    strip["div_rank"] = i
                    break
            off.sort(key=lambda x: -x[1])
            for i, (nm, _) in enumerate(off, 1):
                if nm == me_name:
                    strip["off_rank"] = i
                    break
            deff.sort(key=lambda x: x[1])
            for i, (nm, _) in enumerate(deff, 1):
                if nm == me_name:
                    strip["def_rank"] = i
                    break

        # PP% / PK%: season aggregates if the sim tracks them
        pp_o = _safe(lambda: getattr(team, "pp_opportunities", None), None)
        pp_g = _safe(lambda: getattr(team, "pp_goals", None), None)
        if pp_o and pp_g is not None and pp_o > 0:
            strip["pp_pct"] = round(pp_g / pp_o * 100, 1)
        pk_o = _safe(lambda: getattr(team, "pk_opportunities", None), None)
        pk_ga = _safe(lambda: getattr(team, "pk_goals_against", None), None)
        if pk_o and pk_ga is not None and pk_o > 0:
            strip["pk_pct"] = round((pk_o - pk_ga) / pk_o * 100, 1)

        # Streak + last-10 from completed games
        sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
        done = []
        for g in sched:
            try:
                if not isinstance(g, dict) or g.get("home_score") is None:
                    continue
                hn = _team_name(g.get("home_team"))
                an = _team_name(g.get("away_team"))
                if me_name not in (hn, an):
                    continue
                hs = int(g.get("home_score") or 0)
                aws = int(g.get("away_score") or 0)
                mine = hs if hn == me_name else aws
                theirs = aws if hn == me_name else hs
                res = "W" if mine > theirs else "L"
                done.append({"d": g.get("date"), "res": res})
            except Exception:
                continue
        done.sort(key=lambda g: (g["d"] is None, g["d"]), reverse=True)
        if done:
            sk, sc = "", 0
            for g in done:
                if not sk:
                    sk, sc = g["res"], 1
                elif g["res"] == sk:
                    sc += 1
                else:
                    break
            strip["streak"] = f"{sk}{sc}"
            last10 = done[:10]
            w = sum(1 for g in last10 if g["res"] == "W")
            l = len(last10) - w
            strip["last10"] = f"{w}-{l}"
    except Exception:
        pass
    return strip


def _player_ovr(p):
    """Best-effort 1-100 overall for a player object. Never raises.
    Tries overall_rating() method first (the real game_classes API),
    then overall attribute as fallback."""
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


def _player_full_name(p):
    """'First Last' for a player object. Never raises."""
    try:
        fn = _safe(lambda: getattr(p, "first_name", ""), "")
        ln = _safe(lambda: getattr(p, "last_name", ""), "")
        name = f"{fn} {ln}".strip()
        if name:
            return name
        return str(_safe(lambda: getattr(p, "name", ""), "") or "Unknown")
    except Exception:
        return "Unknown"


def _notable_events(app, gm):
    """Detect genuinely notable league events, highest priority first.

    Returns list of {"kind", "text", "priority"} where lower priority
    number = more notable. Used by _ticker_items() to lead the ticker
    with the big stories instead of raw chronological news.
    """
    notable = []
    seen = set()  # dedupe keys

    def add(priority, kind, text, dedupe_key=None):
        try:
            text = (text or "").strip()
            if not text:
                return
            key = dedupe_key or text[:80].lower()
            if key in seen:
                return
            seen.add(key)
            notable.append({"priority": priority, "kind": kind, "text": text,
                            "src_key": key})
        except Exception:
            pass

    try:
        league = _safe(lambda: gm.league)
        teams = _safe(lambda: list(getattr(league, "teams", None) or []), []) or []

        # --- star name index (80+ OVR) for enriching trade stories ---
        stars = {}  # lower name -> (name, ovr)
        for t in teams:
            try:
                roster = _safe(lambda: list(getattr(t, "roster", None) or []), []) or []
                for p in roster:
                    ovr = _player_ovr(p)
                    if ovr >= 80:
                        nm = _player_full_name(p)
                        stars[nm.lower()] = (nm, ovr)
            except Exception:
                continue

        # --- news log: parse for notable stories ---
        raw_news = _safe(lambda: list(getattr(app, "news_log", None) or []), []) or []
        for entry in raw_news:
            try:
                story = entry.get("story", "") if isinstance(entry, dict) else str(entry)
                story = (story or "").strip()
                if not story:
                    continue
                slow = story.lower()

                # BLOCKBUSTER trades: 80+ OVR player, 1st-round pick, or 3+ assets
                if slow.startswith("trade:") or "trade:" in slow[:20]:
                    is_blockbuster = False
                    clean = re.sub(r"^trade:\s*", "", story, flags=re.I)
                    # star involved?
                    for sname, (nm, ovr) in stars.items():
                        if sname in slow:
                            add(1, "blockbuster",
                                f"🚨 BLOCKBUSTER: {clean} ({nm} {ovr} OVR)",
                                dedupe_key=f"src:{story[:80].lower()}")
                            is_blockbuster = True
                            break
                    # 1st-round pick involved?
                    if not is_blockbuster and re.search(
                            r"1st[\s-]?round|first[\s-]?round", slow):
                        add(1, "blockbuster",
                            f"🚨 BLOCKBUSTER: {clean}",
                            dedupe_key=f"src:{story[:80].lower()}")
                        is_blockbuster = True
                    # 3+ assets? (rough: count " and " + commas in the deal)
                    if not is_blockbuster:
                        assets = slow.count(" and ") + slow.count(",")
                        if assets >= 2:
                            add(1, "blockbuster",
                                f"🚨 BLOCKBUSTER: {clean}",
                                dedupe_key=f"src:{story[:80].lower()}")
                            is_blockbuster = True
                    if not is_blockbuster:
                        add(6, "trade", f"🔄 {story}",
                            dedupe_key=f"src:{story[:80].lower()}")
                    continue

                # MEGADEAL signings: $8M+/yr
                if "$" in story and ("sign" in slow or "extend" in slow or
                                     "contract" in slow):
                    m = re.search(r"\$([\d.]+)\s*[mM]", story)
                    if m:
                        try:
                            amt = float(m.group(1))
                            if amt >= 8.0:
                                add(3, "megadeal",
                                    f"💰 MEGADEAL: {story}",
                                    dedupe_key=f"src:{story[:80].lower()}")
                                continue
                        except Exception:
                            pass
                    # long term (6+ years) also notable
                    m2 = re.search(r"(\d+)[\s-]?year", slow)
                    if m2:
                        try:
                            if int(m2.group(1)) >= 6:
                                add(3, "megadeal",
                                    f"💰 MEGADEAL: {story}",
                                    dedupe_key=f"src:{story[:80].lower()}")
                                continue
                        except Exception:
                            pass

                # Star injuries in news text
                if ("injur" in slow or "out " in slow or "sidelined" in slow
                        or "🏥" in story):
                    for sname, (nm, ovr) in stars.items():
                        if sname in slow and ovr >= 75:
                            add(2, "star_injury",
                                f"🏥 {story} ({nm} {ovr} OVR)")
                            break
                    else:
                        # not a star, keep as routine news (handled by caller)
                        pass
                    continue

                # Hat tricks / shutouts / milestones in news text
                if ("hat trick" in slow or "hat-trick" in slow):
                    add(4, "hat_trick", f"🎩 {story}",
                        dedupe_key=f"src:{story[:80].lower()}")
                    continue
                if "shutout" in slow:
                    add(4, "shutout", f"🧱 {story}",
                        dedupe_key=f"src:{story[:80].lower()}")
                    continue
                if ("milestone" in slow or "career goal" in slow or
                        "career point" in slow or "500th" in slow or
                        "1000th" in slow):
                    add(5, "milestone", f"⭐ {story}",
                        dedupe_key=f"src:{story[:80].lower()}")
                    continue
            except Exception:
                continue

        # --- direct star injury scan (catches injuries with no news story) ---
        for t in teams:
            try:
                roster = _safe(lambda: list(getattr(t, "roster", None) or []), []) or []
                tname = _team_name(t)
                for p in roster:
                    try:
                        if not _safe(lambda: getattr(p, "is_injured", False), False):
                            continue
                        ovr = _player_ovr(p)
                        if ovr < 75:
                            continue
                        nm = _player_full_name(p)
                        itype = _safe(lambda: getattr(p, "injury_type", ""), "") or ""
                        gr = _safe(lambda: getattr(p, "games_remaining_injured", 0), 0)
                        dur = f" — out ~{gr} games" if gr else ""
                        if itype and itype.lower() not in ("none", ""):
                            dur = f" ({itype}{dur})" if dur else f" ({itype})"
                        add(2, "star_injury",
                            f"🏥 {nm} ({ovr} OVR, {tname}) injured{dur}",
                            dedupe_key=f"inj:{nm.lower()}")
                    except Exception:
                        continue
            except Exception:
                continue

        # --- win streaks: 5+ from recent schedule ---
        try:
            sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
            done = [g for g in sched
                    if isinstance(g, dict) and g.get("home_score") is not None]
            # sort by date ascending, then walk backwards per team
            def _dkey(g):
                d = g.get("date")
                return (d is None, d)
            done.sort(key=_dkey)
            streaks = {}
            for g in reversed(done):
                try:
                    hn = _team_name(g.get("home_team"))
                    an = _team_name(g.get("away_team"))
                    hs = int(g.get("home_score") or 0)
                    aws = int(g.get("away_score") or 0)
                    if hs == aws:
                        continue
                    winner = hn if hs > aws else an
                    loser = an if hs > aws else hn
                    # winner extends, loser resets
                    if winner not in streaks:
                        streaks[winner] = 0
                    if loser not in streaks:
                        streaks[loser] = 0
                    # only count consecutive from most recent
                    if streaks[winner] >= 0:
                        streaks[winner] += 1
                    streaks[loser] = -999  # broken
                except Exception:
                    continue
            for tname, st in streaks.items():
                if st >= 5:
                    add(5, "streak",
                        f"🔥 {tname} have won {st} straight",
                        dedupe_key=f"streak:{tname.lower()}")
        except Exception:
            pass

    except Exception:
        pass

    notable.sort(key=lambda x: x["priority"])
    return notable


def _ticker_items(app, gm):
    """Scrolling ticker: notable events first, then scores, then routine news.

    Editorial order: blockbusters > star injuries > megadeals > big
    performances > streaks/milestones > recent scores > routine news.
    """
    items = []
    notable_keys = set()
    try:
        # 1) Notable events lead the ticker
        for n in _notable_events(app, gm):
            items.append({"kind": n["kind"], "text": n["text"]})
            # remember source keys so the raw news pass skips dupes
            try:
                notable_keys.add(n["text"][:60].lower())
                if n.get("src_key"):
                    notable_keys.add(n["src_key"])
            except Exception:
                pass

        league = _safe(lambda: gm.league)
        sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
        scored = []
        for g in sched:
            try:
                if not isinstance(g, dict) or g.get("home_score") is None:
                    continue
                hn = _team_name(g.get("home_team"))
                an = _team_name(g.get("away_team"))
                hs = int(g.get("home_score") or 0)
                aws = int(g.get("away_score") or 0)
                d = g.get("date")
                ds = d.strftime("%b %d") if hasattr(d, "strftime") else ""
                scored.append({
                    "d": d, "kind": "score",
                    "text": f"{TEAM_ABBR.get(an, an[:3].upper())} {aws} — "
                            f"{hs} {TEAM_ABBR.get(hn, hn[:3].upper())}  FINAL"
                            + (f"  ·  {ds}" if ds else ""),
                })
            except Exception:
                continue
        scored.sort(key=lambda g: (g["d"] is None, g["d"]), reverse=True)
        items.extend(scored[:10])

        # 2) Routine news log (skip anything already covered as notable)
        raw = _safe(lambda: list(getattr(app, "news_log", None) or []), []) or []
        news = []
        for entry in raw:
            try:
                story = entry.get("story", "") if isinstance(entry, dict) else str(entry)
                story = (story or "").strip()
                if not story:
                    continue
                # dedupe against notable items (labeled text + source keys)
                if story[:60].lower() in notable_keys:
                    continue
                if f"src:{story[:80].lower()}" in notable_keys:
                    continue
                # skip stories already elevated (they're in items)
                slow = story.lower()
                if slow.startswith("trade:") and any(
                        k in slow for k in ("blockbuster",)):
                    continue
                d = entry.get("date") if isinstance(entry, dict) else None
                news.append({"d": d, "kind": "news", "text": story})
            except Exception:
                continue
        try:
            news.sort(key=lambda x: str(x["d"] or ""), reverse=True)
        except Exception:
            pass
        # fill remaining slots with routine news
        room = max(0, 24 - len(items))
        items.extend(news[:room])
    except Exception:
        pass
    return [{"kind": i["kind"], "text": i["text"]} for i in items[:24]]


def get_hub_state(app):
    """Full hub payload from the live game."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    inbox = _safe(lambda: team.inbox) if team else None

    cur_date = _safe(lambda: gm.current_date)
    if isinstance(cur_date, (date, datetime)):
        date_str = cur_date.strftime("%B %d, %Y")
    else:
        date_str = str(cur_date or "")

    unread = _safe(lambda: int(getattr(inbox, "unread_count", 0) or 0), 0)
    action_needed = 0
    if inbox:
        for m in _safe(lambda: list(inbox.messages), []) or []:
            try:
                if getattr(m, "requires_response", False) or m.is_overdue():
                    action_needed += 1
            except Exception:
                pass

    t = to_web_team(team) if team else {}
    pts = t.get("wins", 0) * 2 + t.get("otl", 0)

    # Next game (same logic as Tkinter HomeDashboard._next_game)
    next_game = None
    try:
        sched = _safe(lambda: list(getattr(gm.league, "schedule", None) or []), []) or []
        me_name = _safe(lambda: getattr(team, "team_name", ""), "")
        today = _safe(lambda: gm.current_date)
        cands = []
        for entry in sched:
            if not isinstance(entry, dict):
                continue
            d = entry.get("date")
            hn = _team_name(entry.get("home_team"))
            an = _team_name(entry.get("away_team"))
            if entry.get("home_score") is not None:
                continue
            if hn != me_name and an != me_name:
                continue
            if today is not None and d is not None and d < today:
                continue
            cands.append((d, hn, an, entry.get("time")))
        cands.sort(key=lambda x: (x[0] is None, x[0]))
        if cands:
            d, hn, an, tm = cands[0]
            ds = d.strftime("%b %d") if hasattr(d, "strftime") else str(d or "")
            next_game = {
                "date": ds,
                "home": hn, "away": an,
                "home_abbr": TEAM_ABBR.get(hn, hn[:3].upper()),
                "away_abbr": TEAM_ABBR.get(an, an[:3].upper()),
                "is_home": hn == me_name,
                "time": str(tm or ""),
            }
    except Exception:
        pass

    # Recent inbox (3 newest)
    recent = []
    try:
        _msgs = _safe(lambda: list(inbox.messages), []) or [] if inbox else []
        for m in _msgs[:3]:
            recent.append({
                "subject": _safe(lambda: getattr(m, "subject", ""), ""),
                "urgent": bool(_safe(lambda: getattr(m, "is_urgent", False), False)),
                "action": bool(_safe(lambda: getattr(m, "requires_response", False), False)),
            })
    except Exception:
        pass

    # Stat strip (v0.18.4-style): record, points+rank, offense/defense ranks,
    # PP%/PK%, streak, last-10, cap space
    stat_strip = _stat_strip(team, gm, t)

    # Scrolling news ticker: recent league scores + news log
    ticker = _ticker_items(app, gm)

    return {
        "team": {**t, "points": pts},
        "team_colors": _team_colors_dict(team),
        "date": date_str,
        "inbox": {"unread": unread, "action_needed": action_needed},
        "next_game": next_game,
        "recent_inbox": recent,
        "stat_strip": stat_strip,
        "ticker": ticker,
        "tiles": [
            {"id": "continue", "title": "Continue", "subtitle": "Advance the day",
             "size": "hero", "icon": "▶", "accent": True},
            {"id": "roster", "title": "Roster",
             "subtitle": f"{t.get('roster_size', 0)} players",
             "size": "large", "icon": "🏒"},
            {"id": "inbox", "title": "Inbox",
             "subtitle": f"{unread} unread" +
                         (f" · {action_needed} need action" if action_needed else ""),
             "size": "medium", "icon": "✉️", "badge": unread or None},
            {"id": "schedule", "title": "Schedule", "subtitle": "Season schedule",
             "size": "medium", "icon": "📅"},
            {"id": "stats", "title": "Team Stats",
             "subtitle": f"{t.get('wins', 0)}-{t.get('losses', 0)}-{t.get('otl', 0)}",
             "size": "medium", "icon": "📊"},
            {"id": "lines", "title": "Lines", "subtitle": "Line combinations",
             "size": "small", "icon": "📋"},
            {"id": "trades", "title": "Trades", "subtitle": "Trade center",
             "size": "small", "icon": "🔄"},
            {"id": "scouting", "title": "Scouting", "subtitle": "Assignments",
             "size": "small", "icon": "🔭"},
            {"id": "staff", "title": "Staff", "subtitle": "Coaches & management",
             "size": "small", "icon": "👔"},
            {"id": "tactics", "title": "Tactics", "subtitle": "Systems & practice",
             "size": "small", "icon": "♟️"},
        ],
        "panels": _hub_panels(team, gm),
    }


def _hub_panels(team, gm):
    """At-a-glance dashboard panels: standings, leaders, form, next game.
    All reads defensive; returns {} on any failure."""
    try:
        league = _safe(lambda: gm.league)
        if league is None or team is None:
            return {}
        me_name = _safe(lambda: team.team_name, "")
        teams = _safe(lambda: list(league.teams), []) or []
        table = _safe(lambda: dict(league.standings), {}) or {}
        sched = _safe(lambda: list(getattr(league, "schedule", None) or []), []) or []
        today = _safe(lambda: gm.current_date)

        # --- Division standings (user's division) ---
        my_div = _safe(lambda: team.division, "") or ""
        div_rows = []
        for t in teams:
            try:
                if my_div and _safe(lambda: t.division, "") != my_div:
                    continue
                name = _safe(lambda: t.team_name, "")
                if not name:
                    continue
                row = _safe(lambda: table.get(name), {}) or {}
                w = _safe(lambda: int(row.get("W", 0) or 0), 0)
                l = _safe(lambda: int(row.get("L", 0) or 0), 0)
                otl = _safe(lambda: int(row.get("OTL", 0) or 0), 0)
                pts = _safe(lambda: int(row.get("Points", 0) or 0), 0)
                div_rows.append({
                    "name": name,
                    "abbr": TEAM_ABBR.get(name, name[:3].upper()),
                    "w": w, "l": l, "otl": otl, "pts": pts,
                    "is_user": name == me_name,
                })
            except Exception:
                continue
        div_rows.sort(key=lambda r: (-r["pts"], -r["w"], r["name"]))

        # --- Team leaders (top 3 pts / goals / assists, skaters only) ---
        skaters = []
        for p in _safe(lambda: list(team.roster), []) or []:
            try:
                pos = _safe(lambda: _clean_position(getattr(p, "primary_position", "")), "?")
                if pos.upper() == "G":
                    continue
                pid = _safe(lambda: str(getattr(p, "id", id(p))), "")
                skaters.append({
                    "id": pid,
                    "portrait": player_portrait(pid),
                    "name": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                    "pos": pos,
                    "g": int(_safe(lambda: getattr(p, "goals", 0) or 0, 0)),
                    "a": int(_safe(lambda: getattr(p, "assists", 0) or 0, 0)),
                    "pts": int(_safe(lambda: getattr(p, "points", 0) or 0, 0)),
                })
            except Exception:
                continue
        leaders = {
            "points": sorted(skaters, key=lambda r: (-r["pts"], -r["g"]))[:3],
            "goals": sorted(skaters, key=lambda r: (-r["g"], -r["a"]))[:3],
            "assists": sorted(skaters, key=lambda r: (-r["a"], -r["g"]))[:3],
        }

        # --- Recent form: last 5 completed games + streak ---
        done = []
        for g in sched:
            try:
                if not isinstance(g, dict):
                    continue
                if g.get("home_score") is None:
                    continue
                hn = _team_name(g.get("home_team"))
                an = _team_name(g.get("away_team"))
                if me_name not in (hn, an):
                    continue
                hs = int(g.get("home_score") or 0)
                aws = int(g.get("away_score") or 0)
                mine = hs if hn == me_name else aws
                theirs = aws if hn == me_name else hs
                res = "W" if mine > theirs else ("OTL" if mine == theirs else "L")
                # OTL detection: if tied at regulation... keep simple: loss by 1 = OTL
                if res == "L" and abs(mine - theirs) == 1:
                    res = "OTL"
                done.append({
                    "d": g.get("date"),
                    "res": res,
                    "score": f"{mine}-{theirs}",
                    "opp": an if hn == me_name else hn,
                    "opp_abbr": TEAM_ABBR.get(an if hn == me_name else hn, "?"),
                    "home": hn == me_name,
                })
            except Exception:
                continue
        done.sort(key=lambda g: (g["d"] is None, g["d"]), reverse=True)
        last5 = done[:5]
        # Streak from most recent
        streak, sc = "", 0
        for g in done:
            r = g["res"]
            key = "W" if r == "W" else "L"  # OTL counts as non-win for streak
            if not streak:
                streak, sc = key, 1
            elif key == streak:
                sc += 1
            else:
                break
        streak_txt = f"{streak}{sc}" if streak else "—"

        # --- Next game with both teams' records ---
        next_game = None
        try:
            cands = []
            for g in sched:
                if not isinstance(g, dict):
                    continue
                if g.get("home_score") is not None:
                    continue
                hn = _team_name(g.get("home_team"))
                an = _team_name(g.get("away_team"))
                if me_name not in (hn, an):
                    continue
                d = g.get("date")
                if today is not None and d is not None and d < today:
                    continue
                cands.append((d, hn, an, g.get("time")))
            cands.sort(key=lambda x: (x[0] is None, x[0]))
            if cands:
                d, hn, an, tm = cands[0]
                ds = d.strftime("%a %b %d") if hasattr(d, "strftime") else str(d or "")
                def _rec(nm):
                    r = _safe(lambda: table.get(nm), {}) or {}
                    w = _safe(lambda: int(r.get("W", 0) or 0), 0)
                    l = _safe(lambda: int(r.get("L", 0) or 0), 0)
                    otl = _safe(lambda: int(r.get("OTL", 0) or 0), 0)
                    return f"{w}-{l}-{otl}"
                next_game = {
                    "date": ds,
                    "time": str(tm or ""),
                    "home": hn, "away": an,
                    "home_abbr": TEAM_ABBR.get(hn, hn[:3].upper()),
                    "away_abbr": TEAM_ABBR.get(an, an[:3].upper()),
                    "home_rec": _rec(hn), "away_rec": _rec(an),
                    "is_home": hn == me_name,
                }
        except Exception:
            pass

        return {
            "division": my_div,
            "standings": div_rows,
            "leaders": leaders,
            "form": {"last5": last5, "streak": streak_txt},
            "next_game": next_game,
        }
    except Exception:
        return {}


def get_inbox_messages(app, filter_type="all"):
    """Inbox messages for the web UI, newest first."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    inbox = _safe(lambda: team.inbox) if team else None
    if inbox is None:
        return []
    msgs = _safe(lambda: list(inbox.messages), []) or []
    if filter_type == "unread":
        msgs = [m for m in msgs if not _safe(lambda: m.is_read, False)]
    elif filter_type == "urgent":
        msgs = [m for m in msgs
                if _safe(lambda: m.is_urgent, False) or _safe(lambda: m.priority, 1) >= 4]
    elif filter_type == "action":
        msgs = [m for m in msgs
                if _safe(lambda: m.requires_response, False)]
    elif filter_type == "saved":
        msgs = [m for m in msgs if _safe(lambda: m.is_saved, False)]
    return [to_web_message(m) for m in msgs]


def get_roster(app):
    """User team roster for the web UI."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if team is None:
        return []
    return [to_web_player(p) for p in _safe(lambda: list(team.roster), []) or []]


def _team_name(t):
    if isinstance(t, str):
        return t
    return _safe(lambda: getattr(t, "team_name", str(t)), "?") or "?"


# Blocker ID -> web page that helps resolve it (None = desktop app only).
BLOCKER_WEB_ROUTES = {
    "roster_limit_23": "/roster",
    "dress_minimum": "/roster",
    "salary_cap": "/roster",
    "salary_floor": "/roster",
    "captaincy_choice": "/roster",
    "fantasy_draft": None,
    "entry_draft": None,
    "season_integrity": None,
}


def get_continue_state(app):
    """Continue button state + JSON-safe blockers for the web modal."""
    label, blockers = _safe(lambda: app.get_continue_state(), ("Continue", [])) or ("Continue", [])
    web_blockers = []
    for b in blockers or []:
        try:
            bid = b.get("id", "")
            auto = b.get("auto_action")
            web_blockers.append({
                "id": bid,
                "title": b.get("title", ""),
                "detail": b.get("detail", ""),
                "has_auto": bool(auto),
                "auto_label": (auto[0] if isinstance(auto, (list, tuple)) and auto else "Auto-resolve"),
                "web_route": BLOCKER_WEB_ROUTES.get(bid),
            })
        except Exception:
            continue
    # Does the user's team play today? (for watch-mode routing)
    # Check if the next scheduled game is today.
    has_games = False
    try:
        sched = get_schedule(app, limit=1)
        if sched:
            gm = _safe(lambda: app.game_manager)
            today = _safe(lambda: gm.current_date)
            # get_schedule returns date strings like "Mon 10/05"; compare
            # against today's formatted string.
            if today and hasattr(today, 'strftime'):
                today_str = today.strftime("%a %m/%d")
                has_games = sched[0].get("date") == today_str
    except Exception:
        pass
    return {"label": label, "blocked": bool(web_blockers), "blockers": web_blockers,
            "has_games": has_games}


def get_schedule(app, limit=40):
    """Upcoming games for the user team, chronological."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if gm is None or team is None:
        return []
    my_name = _safe(lambda: team.team_name, "")
    today = _safe(lambda: gm.current_date)
    sched = _safe(lambda: list(getattr(getattr(gm, "league", None), "schedule", None) or []), []) or []
    out = []
    for g in sched:
        try:
            if not isinstance(g, dict):
                continue
            gd = g.get("date")
            home = _team_name(g.get("home_team"))
            away = _team_name(g.get("away_team"))
            if my_name and my_name not in (home, away):
                continue
            if today and isinstance(gd, (date, datetime)) and gd < today:
                continue
            out.append({
                "date": gd.strftime("%a %m/%d") if isinstance(gd, (date, datetime)) else str(gd),
                "home": home,
                "away": away,
                "is_home": home == my_name,
                "opponent": away if home == my_name else home,
                "preseason": bool(g.get("preseason", False)),
            })
        except Exception:
            continue
    # chronological
    try:
        out.sort(key=lambda x: x["date"])
    except Exception:
        pass
    return out[:limit]


# ------------------------------------------------------------------
# Command queue (web -> game writes, drained on the Tk main thread)
# ------------------------------------------------------------------
def enqueue_command(op, **kwargs):
    """Queue a write op for the main thread. Never raises."""
    try:
        COMMAND_QUEUE.put({"op": op, **kwargs})
        return True
    except Exception:
        return False


def drain_commands(app, root):
    """Drain the queue on the Tk main thread; reschedules itself.

    Call once from the GUI: root.after(100, lambda: drain_commands(app, root))
    Uses the live _web_app_ref when set (web setup attaches the game late).
    """
    live = _web_app_ref if _web_app_ref is not None else app
    try:
        while True:
            try:
                cmd = COMMAND_QUEUE.get_nowait()
            except queue.Empty:
                break
            _execute_command(live, cmd)
    except Exception:
        pass
    # Browser tab gone silent? Shut the game down cleanly so no ghost
    # process lingers (the Sept-2026 exit-hang lesson, web edition).
    if _web_app_ref is not None and heartbeat_expired():
        try:
            _shutdown(root)
        except Exception:
            pass
        return
    try:
        root.after(250, lambda: drain_commands(app, root))
    except Exception:
        pass


_setup_root = None  # the hidden Tk root whose mainloop pumps commands


def _shutdown(root):
    """Quit the Tk mainloop and tear down roots so the process exits."""
    global _shutting_down
    _shutting_down = True
    roots = []
    try:
        if _setup_root is not None:
            roots.append(_setup_root)
    except Exception:
        pass
    try:
        if _web_app_ref is not None and _web_app_ref not in roots:
            roots.append(_web_app_ref)
    except Exception:
        pass
    if root is not None and root not in roots:
        roots.append(root)
    for r in roots:
        try:
            r.quit()      # stop whichever mainloop is running
        except Exception:
            pass
    for r in roots:
        try:
            r.destroy()   # tear down so the process can exit
        except Exception:
            pass


_web_setup_status = {"status": "idle"}  # idle|generating|ready|error


def _do_setup_new_game(cmd):
    """Create a new career from the web setup page (main thread).

    Accepts the full v0.18.4 wizard config: database_size, leagues,
    sim_detail, fog_of_war, fantasy_draft, playoff_format, user_league.
    """
    global _web_setup_status
    _web_setup_status = {"status": "generating", "detail": "Building league..."}
    try:
        import main as _main
        team = cmd.get("team") or "Boston Bruins"
        gm_name = cmd.get("gm_name") or "General Manager"

        # Build a validated wizard config, then a DatabaseConfig for
        # league selection (mirrors new_game_setup on the desktop flow).
        db_config = None
        try:
            from new_game_setup import make_config, build_database_config
            wiz = make_config(
                mode="custom",
                database_size=cmd.get("database_size") or "default",
                leagues=cmd.get("leagues") or ["NHL", "AHL"],
                sim_detail=cmd.get("sim_detail"),
                fog_of_war=cmd.get("fog_of_war", True),
                gm_name=gm_name,
                user_league=cmd.get("user_league") or "NHL",
                user_team=team,
                playoff_format=cmd.get("playoff_format") or "divisional",
            )
            db_config = build_database_config(wiz)

            # GM profile (v0.18.4 Create GM tab parity)
            gm_profile = None
            try:
                from game_classes import GMProfile
                gp = cmd.get("gm_profile") or {}
                if gp.get("name"):
                    gm_profile = GMProfile(
                        name=gp.get("name") or gm_name,
                        age=int(gp.get("age") or 35),
                        former_player=(gp.get("background") == "Former Player"),
                        coaching_experience=(gp.get("background") == "Former Coach"),
                        management_style=gp.get("management_style") or "Balanced",
                    )
            except Exception:
                gm_profile = None

            settings = {
                'database_size': 'Standard',
                'database_config': db_config,
                'fantasy_draft': bool(cmd.get("fantasy_draft")),
                'user_team': wiz["user_team"],
                'user_league': wiz["user_league"],
                'gm_name': wiz["gm_name"],
                'gm_profile': gm_profile,
                'fog_of_war': wiz["fog_of_war"],
                'sim_detail': wiz["sim_detail"],
                'playoff_format': wiz["playoff_format"],
                # v0.18.4 launcher options
                'start_date': cmd.get("start_date") or "September 1, 2024",
                'season_length': cmd.get("season_length") or "Default (84 Games)",
                'difficulty': cmd.get("difficulty") or "Professional",
                'trade_difficulty': cmd.get("trade_difficulty") or "Realistic",
                'cpu_gm_intelligence': cmd.get("cpu_gm_intelligence") or "Medium (Balanced)",
                'salary_cap': cmd.get("salary_cap", True),
                'injuries': cmd.get("injuries", True),
                'morale_system': cmd.get("morale_system", True),
                'international_players': cmd.get("international_players", True),
                'start_without_cap_penalties': bool(cmd.get("start_without_cap_penalties")),
                'realistic_progression': cmd.get("realistic_progression", True),
                'show_composite_ratings': bool(cmd.get("show_composite_ratings")),
            }
        except Exception:
            # Fallback to the previous hardcoded defaults.
            settings = {
                'database_size': 'Standard',
                'fantasy_draft': False,
                'user_team': team,
                'user_league': 'NHL',
                'gm_name': gm_name,
                'fog_of_war': True,
                'sim_detail': {'NHL': 'full'},
                'playoff_format': 'divisional',
            }
        _web_setup_status = {"status": "generating",
                             "detail": "Generating players..."}
        gm = _main.GameManager()
        gm.apply_startup_settings(settings)
        gm.set_user_team(settings['user_team'])
        _web_setup_status = {"status": "generating",
                             "detail": "Starting game..."}
        app = _main.HockeyManagerGUI(gm)
        try:
            app.withdraw()  # the browser tab is the window
        except Exception:
            pass
        try:
            app.startup_settings = settings
        except Exception:
            pass
        set_app(app)
        # Multiplayer host: wire up after the game exists (v0.18.4 parity).
        try:
            from web_ui.screens.multiplayer import (
                get_pending_host_config, wire_host)
            mp_cfg = get_pending_host_config()
            if mp_cfg or cmd.get("multiplayer_host"):
                name = (mp_cfg or {}).get("name") or "Host"
                port = int((mp_cfg or {}).get("port") or 27107)
                host, err = wire_host(app, gm, name, port)
                if err:
                    print(f"Multiplayer host failed: {err}")
                else:
                    print(f"Multiplayer hosting on port {port}")
                    _web_setup_status = {"status": "ready",
                                         "detail": "Hosting multiplayer"}
        except Exception as e:
            print(f"Multiplayer wiring skipped: {e}")
        _web_setup_status = {"status": "ready"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _web_setup_status = {"status": "error", "detail": str(e)}


def _do_setup_load_game(cmd):
    """Load a save from the web setup page (main thread)."""
    global _web_setup_status
    _web_setup_status = {"status": "generating", "detail": "Loading save..."}
    try:
        import main as _main
        from save_load_system import GameSaveManager
        path = cmd.get("path")
        gm = _main.GameManager()
        save_mgr = GameSaveManager(gm)
        if not path or not save_mgr.load_game(path):
            _web_setup_status = {"status": "error",
                                 "detail": "Could not load save."}
            return
        app = _main.HockeyManagerGUI(gm)
        try:
            app.withdraw()
        except Exception:
            pass
        if hasattr(app.game_manager, 'current_date'):
            app.current_date = app.game_manager.current_date
        if hasattr(app.game_manager, 'user_team'):
            app.user_team = app.game_manager.user_team
        try:
            app.update_all_views()
        except Exception:
            pass
        set_app(app)
        _web_setup_status = {"status": "ready"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        _web_setup_status = {"status": "error", "detail": str(e)}



def _find_inbox_message(app, message_id):
    """Find an inbox message by ID. Returns (inbox, message) or (None, None)."""
    team = _safe(lambda: getattr(app, "user_team", None))
    inbox = _safe(lambda: getattr(team, "inbox", None))
    if not inbox or not message_id:
        return None, None
    for m in _safe(lambda: list(inbox.messages), []) or []:
        if str(_safe(lambda: getattr(m, "id", ""), "")) == str(message_id):
            return inbox, m
    return inbox, None


def _wt_resolve_trade_assets(team, pid_set, pick_set):
    """Resolve trade-builder asset id sets -> live objects (players+picks)."""
    players, picks = [], []
    for _attr in ("roster", "ahl_roster", "prospects"):
        for _p in (getattr(team, _attr, None) or []):
            if str(getattr(_p, "id", "")) in pid_set:
                players.append(_p)
    _by_year = getattr(team, "draft_picks", None) or {}
    for _pk_list in _by_year.values():
        for _pk in (_pk_list or []):
            if str(getattr(_pk, "id", "")) in pick_set:
                picks.append(_pk)
    return players + picks


def _wt_find_partner(league, target_id):
    """Find the partner team (abbr, name, team_name, 'City Name')."""
    target_id = str(target_id or "").strip().lower()
    for _t in (getattr(league, "teams", None) or []):
        _nm = str(getattr(_t, "team_name", "") or "")
        _cands = {
            str(getattr(_t, "abbreviation", "") or "").lower(),
            _nm.lower(),
            f"{getattr(_t, 'city', '')} {_nm}".strip().lower(),
        }
        if target_id and target_id in _cands:
            return _t
    return None


def _wt_parse_terms(cmd, user_team, give_assets, te):
    """Gap 2 terms: validate retention/pick-protection like the propose
    path. Returns (retention, protection, error) -- error is "" when OK."""
    try:
        from game_classes import DraftPick as _DP
    except Exception:
        _DP = ()
    retention, protection = {}, {}
    try:
        _give_pids = {str(getattr(_p, "id", ""))
                      for _p in give_assets if not isinstance(_p, _DP)}
        _give_pickids = {str(getattr(_p, "id", ""))
                         for _p in give_assets if isinstance(_p, _DP)}
        _raw_ret = cmd.get("retention") or {}
        if isinstance(_raw_ret, dict):
            for _k, _v in _raw_ret.items():
                try:
                    _pct = float(_v)
                except Exception:
                    continue
                if 0 < _pct <= te.MAX_RETENTION_PCT \
                        and str(_k) in _give_pids:
                    retention[str(_k)] = _pct
        _raw_prot = cmd.get("pick_protection") or {}
        if isinstance(_raw_prot, dict):
            for _k, _v in _raw_prot.items():
                if str(_v) in ("top-3", "top-10", "lottery") \
                        and str(_k) in _give_pickids:
                    protection[str(_k)] = str(_v)
        if retention:
            _by_id = {str(getattr(_p, "id", "")): _p
                      for _p in give_assets if not isinstance(_p, _DP)}
            for _pid, _pct in retention.items():
                _pl = _by_id.get(_pid)
                _extra = {k: v for k, v in retention.items()
                          if k != _pid}
                _ok2, _msg2 = te.apply_retention_dry_run(
                    user_team, _pl, _pct, extra=_extra)
                if not _ok2:
                    return {}, {}, (
                        "Retained-salary term on "
                        f"{getattr(_pl, 'full_name', _pid)} is "
                        f"illegal ({_msg2}).")
    except Exception:
        pass
    return retention, protection, ""


# ------------------------------------------------------------------
# Batch D (2026-10-05): development & practice port.
# Pure-logic ports of the desktop systems:
#   - player_development_window_professional.py ("Assign Training Program")
#   - enhanced_practice_system.py PracticeEngine (per-player drills)
#   - auto_resolve.auto_run_practice ("Coach Runs Practice" heuristic)
#   - position_training.py (positional familiarity)
#   - offseason_programs.py (summer programs, Jun-Aug gate)
#   - coach_checkins.py (quarterly check-in trust effects)
# Every op stashes its outcome on app._web_dev_result for GET polling.
# ------------------------------------------------------------------
_BATCHD_ENGINE = None


def _batchd_engine():
    """Shared PracticeEngine (histories are module-level anyway)."""
    global _BATCHD_ENGINE
    if _BATCHD_ENGINE is None:
        from enhanced_practice_system import PracticeEngine
        _BATCHD_ENGINE = PracticeEngine()
    return _BATCHD_ENGINE


def _batchd_gm_team(app):
    try:
        gm = getattr(app, "game_manager", None)
        team = (getattr(gm, "user_team", None)
                or getattr(app, "user_team", None))
        return gm, team
    except Exception:
        return None, None


def _batchd_squads(team):
    """(roster, ahl, prospects) lists, defensive."""
    try:
        roster = list(getattr(team, "roster", None) or [])
    except Exception:
        roster = []
    try:
        ahl = list(getattr(team, "ahl_roster", None) or [])
    except Exception:
        ahl = []
    try:
        prospects = list(getattr(team, "prospects", None) or [])
    except Exception:
        prospects = []
    return roster, ahl, prospects


def _batchd_find_player(team, pid):
    """Player + squad label by id across the user's squads. Never raises."""
    try:
        for label, lst in (("NHL", _safe(lambda: list(getattr(team, "roster", None) or []) or [])),
                           ("AHL", _safe(lambda: list(getattr(team, "ahl_roster", None) or []) or [])),
                           ("Prospects", _safe(lambda: list(getattr(team, "prospects", None) or []) or []))):
            for p in lst or []:
                try:
                    if str(getattr(p, "id", None)) == str(pid):
                        return p, label
                except Exception:
                    continue
    except Exception:
        pass
    return None, None


def _batchd_player_team(app, team, player):
    """The club whose coaching staff runs the drill: the player's own
    club when findable, else the user's team (desktop parity with
    HockeyManagerGUI._process_training_programs)."""
    try:
        gm = getattr(app, "game_manager", None)
        league = getattr(gm, "league", None) or getattr(app, "league", None)
        for t in list(getattr(league, "teams", None) or []):
            try:
                for lst in (getattr(t, "roster", None),
                            getattr(t, "ahl_roster", None),
                            getattr(t, "prospects", None)):
                    if player in (lst or []):
                        return t
            except Exception:
                continue
    except Exception:
        pass
    return team


def _batchd_store(app, marker, nonce, ok, summary, extra=None):
    rec = {"marker": marker, "nonce": nonce, "ok": bool(ok),
           "summary": str(summary or "")}
    if extra:
        rec.update(extra)
    try:
        app._web_dev_result = rec
    except Exception:
        pass


def _batchd_coaching_quality(team):
    """Teaching quality for positional training: the head coach's
    teaching attributes via coach_practice, else the flat 50 default."""
    try:
        import coach_practice as _cp
        hc = _cp.head_coach_of(team)
        if hc is not None:
            vals = []
            for a in ("technical_coaching", "tactical_knowledge",
                      "player_development"):
                try:
                    v = getattr(hc, a, None)
                    if v is not None:
                        vals.append(float(v))
                except Exception:
                    continue
            if vals:
                return max(1.0, min(100.0, sum(vals) / len(vals)))
    except Exception:
        pass
    return 50.0


def _batchd_coach_runs_practice(app, team, nonce):
    """Port of auto_resolve.auto_run_practice (2026-10-04).

    Same drill-pick heuristic (weakest role-relevant attribute) and same
    intensity rules (young + fresh = harder; old/tired = lighter), run
    through the real PracticeEngine with the club's coaching staff.
    """
    from enhanced_practice_system import PracticeType, PracticeIntensity
    engine = _batchd_engine()

    def _attr(p, name, default=50):
        try:
            return float(getattr(p, name, default) or default)
        except Exception:
            return float(default)

    def _pos(p):
        try:
            return str(getattr(p, "primary_position", "")).lower()
        except Exception:
            return ""

    def _is_goalie(p):
        pos = _pos(p)
        return "goalie" in pos or "goaltender" in pos or pos.strip() == "g"

    def _is_center(p):
        pos = _pos(p)
        return "center" in pos or pos.strip() == "c"

    def _is_defense(p):
        pos = _pos(p)
        return ("defens" in pos or pos.strip() == "d"
                or pos.strip() in ("ld", "rd"))

    roster, _ahl, _pr = _batchd_squads(team)
    roster = [p for p in roster if not getattr(p, "is_injured", False)]
    if not roster:
        _batchd_store(app, "coach_runs_practice", nonce, False,
                      "No healthy players available.")
        return

    sessions = 0
    details = []
    for p in roster:
        try:
            age = int(getattr(p, "age", 25) or 25)
        except Exception:
            age = 25
        try:
            fatigue = float(
                engine.get_player_history(getattr(p, "id")).current_fatigue)
        except Exception:
            fatigue = 0.0
        if not fatigue:
            fatigue = _attr(p, "fatigue", 0)

        # Pick drill type by biggest weakness in role-relevant attributes
        if _is_goalie(p):
            cands = [
                (PracticeType.DEFENSE, _attr(p, "positioning", 50)),
                (PracticeType.CONDITIONING, _attr(p, "agility", 50)),
                (PracticeType.HOCKEY_IQ, _attr(p, "rebound_control", 50)),
            ]
        elif _is_defense(p):
            cands = [
                (PracticeType.DEFENSE, _attr(p, "defensive_awareness", 50)),
                (PracticeType.CHECKING, _attr(p, "checking", 50)),
                (PracticeType.PASSING, _attr(p, "passing", 50)),
                (PracticeType.SKATING, _attr(p, "skating", 50)),
            ]
        else:  # Forwards
            cands = [
                (PracticeType.SHOOTING, _attr(p, "shooting", 50)),
                (PracticeType.SKATING, _attr(p, "skating", 50)),
                (PracticeType.PASSING, _attr(p, "passing", 50)),
            ]
            if _is_center(p):
                cands.append(
                    (PracticeType.FACEOFFS, _attr(p, "faceoffs", 50)))
        # Veterans: maintenance focus overrides development
        if age >= 32:
            cands = [
                (PracticeType.CONDITIONING, _attr(p, "conditioning", 50)),
                (PracticeType.HOCKEY_IQ,
                 _attr(p, "offensive_awareness", 50)),
            ] + cands
        # Pick the weakest attribute's drill
        cands.sort(key=lambda x: x[1])
        drill = cands[0][0]

        # Pick intensity: young + fresh = harder; old/tired = lighter
        if fatigue > 70:
            intensity = PracticeIntensity.LIGHT
        elif age >= 34 or fatigue > 50:
            intensity = PracticeIntensity.MODERATE
        elif age <= 24 and fatigue < 30:
            intensity = PracticeIntensity.INTENSE
        else:
            intensity = PracticeIntensity.MODERATE

        try:
            can, _why = engine.can_practice(p, drill, intensity)
            if not can:
                # Fall back to light if the chosen intensity isn't allowed
                intensity = PracticeIntensity.LIGHT
                can, _why = engine.can_practice(p, drill, intensity)
            if can:
                engine.execute_practice(p, drill, intensity, team=team)
                sessions += 1
                details.append({
                    "player": _safe(lambda: getattr(p, "full_name", "?"), "?"),
                    "drill": drill.value,
                    "intensity": intensity.value,
                })
        except Exception:
            continue

    if sessions == 0:
        _batchd_store(app, "coach_runs_practice", nonce, False,
                      "No practice sessions could be run "
                      "(fatigue or injuries).")
        return
    _batchd_store(app, "coach_runs_practice", nonce, True,
                  f"Coach ran practice: {sessions} session(s) assigned "
                  f"(weakness-targeted drills, fatigue-aware intensity).",
                  {"sessions": details})


def _batchd_checkin_coach(app, team):
    """The team's head coach (same fallbacks as desktop CheckinView)."""
    try:
        import coach_checkins as _ckm
        fn = getattr(_ckm, "get_head_coach", None)
        if callable(fn):
            coach = fn(team)
            if coach is not None:
                return coach
    except Exception:
        pass
    try:
        return (getattr(team, "staff", None) or [None])[0]
    except Exception:
        return None


def _batchd_checkin_draft(team):
    """Resume-or-fresh draft, keyed to the pending quarter (desktop parity)."""
    try:
        import coach_checkins as _ckm
        pending_q = None
        try:
            pending_q = _ckm.get_pending_quarter(team)
        except Exception:
            pass
        d = getattr(team, "checkin_draft", None)
        if isinstance(d, dict) and d.get("quarter") == pending_q \
                and pending_q is not None:
            return d
        gp = 0
        try:
            gp = _ckm.team_games_played(team)
        except Exception:
            pass
        d = {"quarter": pending_q, "game": gp, "stage": "opening",
             "chosen": [], "topics": [], "deltas": {}, "notes": [],
             "done": False}
        try:
            team.checkin_draft = d
        except Exception:
            pass
        return d
    except Exception:
        return {"quarter": None, "game": 0, "stage": "opening",
                "chosen": [], "topics": [], "deltas": {}, "notes": [],
                "done": False}


def _execute_command(app, cmd):
    """Run one queued command on the main thread. Never raises."""
    try:
        op = cmd.get("op")
        if op == "exit_game":
            _shutdown(_setup_root)
            return
        elif op == "setup_new_game":
            _do_setup_new_game(cmd)
            return
        elif op == "setup_load_game":
            _do_setup_load_game(cmd)
            return
        elif op == "advance_day":
            fn = (getattr(app, "advance_day", None)
                  or getattr(app, "_on_continue_pressed", None)
                  or getattr(app, "_on_continue", None))
            if callable(fn):
                fn()
        elif op == "mark_read":
            mid = cmd.get("message_id")
            team = getattr(app, "user_team", None)
            inbox = getattr(team, "inbox", None)
            if inbox and mid:
                try:
                    inbox.mark_message_read(mid)
                except Exception:
                    pass
        elif op == "resolve_blocker":
            bid = cmd.get("blocker_id")
            kind = cmd.get("kind", "auto")  # auto | primary | secondary
            try:
                _, blockers = app.get_continue_state()
                for b in blockers or []:
                    if b.get("id") != bid:
                        continue
                    key = {"auto": "auto_action", "primary": "action",
                           "secondary": "secondary_action"}.get(kind, "auto_action")
                    act = b.get(key)
                    fn = act[1] if isinstance(act, (list, tuple)) and len(act) > 1 else None
                    if callable(fn):
                        fn()
                    break
            except Exception:
                pass
        elif op == "claim_waiver":
            pid = cmd.get("player_id")
            try:
                team = getattr(app, "user_team", None)
                wire = getattr(app, "waiver_list", None) or []
                player = next((p for p in wire
                               if str(getattr(p, "id", "")) == str(pid)), None)
                if player is not None and team is not None:
                    fn = getattr(app, "_execute_waiver_claim", None)
                    if callable(fn):
                        fn(player, team)
            except Exception:
                pass
        elif op == "place_on_waivers":
            # Place one of the user's own roster players on the waiver wire.
            # Mirrors windows.py place_on_waivers minus the Tkinter dialogs:
            # NMC blocks placement (safe default), transaction window enforced.
            pid = cmd.get("player_id")
            try:
                gm = getattr(app, "game_manager", None)
                team = getattr(gm, "user_team", None) or getattr(app, "user_team", None)
                if team is None:
                    print("place_on_waivers: no user team")
                    return
                roster = list(getattr(team, "roster", []) or [])
                player = next((p for p in roster
                               if str(getattr(p, "id", "")) == str(pid)), None)
                if player is None:
                    print(f"place_on_waivers: player {pid} not on roster")
                    return
                try:
                    import transaction_windows as _tw
                    _ok, _why = _tw.check_window(
                        "waiver_place", getattr(app, "current_date", None))
                    if not _ok:
                        print(f"place_on_waivers blocked: {_why}")
                        return
                except Exception:
                    pass
                try:
                    import trade_engine as _te
                    _kind, _detail = _te.clause_of(player)
                    if _kind == "NMC":
                        print(f"place_on_waivers blocked: {player.full_name} has NMC")
                        return
                except Exception:
                    pass
                player.on_waivers = True
                # Desktop (windows.py:14111): players stay on waivers 2 days;
                # without this the clock starts at 0 and the daily advance
                # processes claims the same day.
                player.waiver_days = 2
                wire = getattr(app, "waiver_list", None)
                if wire is not None and player not in wire:
                    wire.append(player)
                try:
                    _news = getattr(app, "add_news", None)
                    if callable(_news):
                        _news(f"{player.full_name} placed on waivers by "
                              f"{getattr(team, 'team_name', 'your team')}.")
                except Exception:
                    pass
            except Exception as e:
                print(f"place_on_waivers failed: {e}")
        elif op == "execute_buyout":
            # Buy out a roster player's contract. Web port of
            # BuyoutCalculatorView._confirm_buyout (windows.py): the buyout
            # window gate, then the one rulebook mutation
            # (buyout_window.execute_buyout). One-shot: NMC/NTC players are
            # blocked here (the AI doesn't ask consent; the desktop
            # calculator flags the same rule via _candidate_rows).
            pid = cmd.get("player_id")
            try:
                try:
                    import transaction_windows as _tw
                    _ok, _why = _tw.check_window(
                        "buyout", getattr(app, "current_date", None))
                    if not _ok:
                        print(f"execute_buyout blocked: {_why}")
                        return
                except Exception:
                    pass
                gm = getattr(app, "game_manager", None)
                league = getattr(gm, "league", None) or getattr(app, "league", None)
                team = getattr(gm, "user_team", None) or getattr(app, "user_team", None)
                if team is None or league is None:
                    print("execute_buyout: no team/league")
                    return
                roster = list(getattr(team, "roster", []) or [])
                player = next((p for p in roster
                               if str(getattr(p, "id", "")) == str(pid)), None)
                if player is None:
                    print(f"execute_buyout: player {pid} not on roster")
                    return
                c = getattr(player, "contract", None)
                if bool(getattr(c, "no_movement_clause", False)) or \
                        bool(getattr(c, "no_trade_clause", False)):
                    print(f"execute_buyout blocked: {getattr(player, 'full_name', '?')} "
                          "has NMC/NTC")
                    return
                try:
                    import buyout_window as _bw
                    total, annual, byears, _rows = _bw.execute_buyout(
                        league, team, player,
                        season_year=getattr(league, "season_year", 2026))
                    print(f"execute_buyout: {getattr(player, 'full_name', '?')} bought out "
                          f"(${int(total):,} total, ${int(annual):,}/yr x {int(byears)}y)")
                except Exception as e:
                    print(f"execute_buyout failed: {e}")
            except Exception as e:
                print(f"execute_buyout failed: {e}")
        elif op == "set_jersey_number":
            # Change a player's jersey number. Web port of
            # HockeyManagerGUI.assign_jersey_number (main.py:23002): retired
            # numbers stay retired, goalie numbers stay with goalies,
            # duplicates blocked across NHL + AHL rosters. Revalidated on
            # the main thread (the screen pre-validates too).
            pid = cmd.get("player_id")
            try:
                want = int(cmd.get("number", 0))
            except (TypeError, ValueError):
                want = 0
            try:
                gm = getattr(app, "game_manager", None)
                league = getattr(gm, "league", None) or getattr(app, "league", None)
                team = getattr(gm, "user_team", None) or getattr(app, "user_team", None)
                if team is None or not pid or not (1 <= want <= 98):
                    print("set_jersey_number: bad team/id/number")
                    return
                player = None
                for attr in ("roster", "ahl_roster"):
                    for q in (getattr(team, attr, None) or []):
                        if str(getattr(q, "id", "")) == str(pid):
                            player = q
                            break
                    if player is not None:
                        break
                if player is None:
                    print(f"set_jersey_number: player {pid} not found")
                    return
                cur = int(getattr(player, "jersey_number", 0) or 0)
                if cur == want:
                    return
                try:
                    import immortality as _im
                    from game_classes import PlayerPosition as _PP
                    goalie = getattr(player, "primary_position", None) == _PP.GOALIE
                    if not _im.number_selectable(team, want, goalie) \
                            and cur != want:
                        # number_selectable sees the player's own number as
                        # taken, but cur != want already ruled that out --
                        # so this is genuinely unavailable.
                        tname = getattr(team, "team_name", "the club")
                        if _im.is_number_retired(team, want) or \
                                want in _im.LEAGUE_RETIRED_NUMBERS:
                            print(f"set_jersey_number: No. {want} retired by {tname}")
                        elif not goalie and want in _im.SKATER_BARRED_NUMBERS:
                            print(f"set_jersey_number: No. {want} reserved for goaltenders")
                        else:
                            print(f"set_jersey_number: No. {want} unavailable")
                        return
                except Exception:
                    pass
                player.jersey_number = want
                try:
                    player.jersey_number_since = int(
                        getattr(league, "season_year", 2026) or 2026)
                except Exception:
                    pass
                print(f"set_jersey_number: {getattr(player, 'full_name', '?')} -> #{want}")
            except Exception as e:
                print(f"set_jersey_number failed: {e}")
        elif op == "set_captains":
            try:
                team = getattr(app, "user_team", None)
                roster = list(getattr(team, "roster", None) or [])
                by_id = {str(getattr(p, "id", "")): p for p in roster}
                # clear existing letters first
                for p in roster:
                    if getattr(p, "captaincy", "") in ("C", "A"):
                        p.captaincy = ""
                cap = by_id.get(str(cmd.get("captain_id")))
                a1 = by_id.get(str(cmd.get("alt1_id")))
                a2 = by_id.get(str(cmd.get("alt2_id")))
                if cap is not None:
                    cap.captaincy = "C"
                for a in (a1, a2):
                    if a is not None and a is not cap:
                        a.captaincy = "A"
                try:
                    gm = getattr(app, "game_manager", None)
                    if gm is not None:
                        gm._captaincy_choice_pending = False
                except Exception:
                    pass
            except Exception:
                pass
        elif op == "trade_block_add":
            try:
                pid = str(cmd.get("player_id", ""))
                team = getattr(app, "user_team", None)
                if team is not None and pid:
                    if not hasattr(app, "trade_block"):
                        app.trade_block = []
                    for lst in ("roster", "ahl_roster", "prospects"):
                        for p in list(getattr(team, lst, None) or []):
                            if str(getattr(p, "id", "")) == pid:
                                if p not in app.trade_block:
                                    app.trade_block.append(p)
                                break
            except Exception:
                pass
        elif op == "trade_block_remove":
            try:
                pid = str(cmd.get("player_id", ""))
                block = getattr(app, "trade_block", None) or []
                for p in list(block):
                    try:
                        if str(getattr(p, "id", "")) == pid:
                            block.remove(p)
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        elif op == "trade_block_simulate_offers":
            try:
                fn = getattr(app, "process_trade_block_offers", None)
                if callable(fn):
                    fn()
            except Exception:
                pass
        elif op == "trade_block_generate_interest":
            # Mirror of TradeBlockWindow.generate_trade_interest: sync the
            # manual block into real trade_market listings, then run the
            # genuine AI bidder computation per listing.
            try:
                import trade_market as tm
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                if league is None:
                    league = getattr(app, "league", None)
                if league is not None:
                    market = tm.get_market(league)
                    today = tm._today(app)
                    heat = tm.deadline_heat(app, league, today)
                    params = tm._heat_params(heat)
                    tm._sync_user_block(app, league, market, today, params)
                    for li in list(market.get("listings", []) or []):
                        try:
                            if (isinstance(li, dict)
                                    and li.get("source") == "user_block"):
                                bidders = tm._find_bidders(
                                    app, league, li, today, heat >= 0.5)
                                if bidders:
                                    ai = li.setdefault("ai_interest", [])
                                    seen = {r.get("team") for r in ai
                                            if isinstance(r, dict)}
                                    for b in bidders:
                                        tname = (b.get("team") if isinstance(
                                            b, dict) else str(b))
                                        if tname not in seen:
                                            ai.append({
                                                "team": tname,
                                                "interest": (b.get("interest")
                                                             if isinstance(
                                                                 b, dict)
                                                             else ""),
                                                "status": "Open",
                                            })
                        except Exception:
                            continue
            except Exception:
                pass
        elif op == "trade_block_decline_interest":
            # Mirror of TradeBlockWindow.decline_interest: mark the team's
            # row Declined on the real listing so it never resurrects.
            try:
                pname = cmd.get("player", "")
                tname = cmd.get("team", "")
                import trade_market as tm
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                if league is None:
                    league = getattr(app, "league", None)
                if league is not None:
                    market = tm.get_market(league)
                    for li in list(market.get("listings", []) or []):
                        try:
                            if not isinstance(li, dict):
                                continue
                            if ((li.get("player_name") or "") != pname):
                                continue
                            for r in (li.get("ai_interest") or []):
                                if (isinstance(r, dict)
                                        and r.get("team") == tname
                                        and r.get("status") != "Declined"):
                                    r["status"] = "Declined"
                            dteams = li.setdefault("declined_teams", [])
                            if tname not in dteams:
                                dteams.append(tname)
                        except Exception:
                            continue
            except Exception:
                pass
        elif op == "trade_block_express_interest":
            # Mirror of TradeBlockWindow.express_interest: record genuine
            # interest via trade_market.add_target (canonical user store).
            try:
                import trade_market as tm
                pid = str(cmd.get("player_id", "") or "")
                pname = cmd.get("player", "")
                tname = cmd.get("team", "")
                player = None
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                if league is None:
                    league = getattr(app, "league", None)
                if league is not None:
                    for t in (getattr(league, "teams", None) or []):
                        try:
                            if getattr(t, "team_name", "") != tname:
                                continue
                            for p in (getattr(t, "roster", None) or []):
                                if (str(getattr(p, "id", "")) == pid
                                        or getattr(p, "full_name", "") == pname):
                                    player = p
                                    break
                            break
                        except Exception:
                            continue
                if player is not None:
                    tm.add_target(
                        player, source="user",
                        note=f"Trade interest expressed ({tname} block)")
            except Exception:
                pass
        elif op == "hire_staff":
            try:
                sid = str(cmd.get("staff_id", ""))
                salary = int(cmd.get("salary") or 0)
                years = int(cmd.get("years") or 3)
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                team = getattr(app, "user_team", None)
                if league is not None and team is not None and sid:
                    pool = list(getattr(league, "free_agent_staff", None) or [])
                    target = None
                    for s in pool:
                        if str(getattr(s, "id", "")) == sid:
                            target = s
                            break
                    if target is not None:
                        try:
                            pool.remove(target)
                            league.free_agent_staff = pool
                        except Exception:
                            pass
                        try:
                            target.salary = salary or getattr(target, "salary", 100000)
                            target.contract_years = years
                            staff = getattr(team, "staff", None)
                            if staff is None:
                                team.staff = []
                                staff = team.staff
                            staff.append(target)
                        except Exception:
                            pass
            except Exception:
                pass
        elif op == "release_staff":
            # Release a staff member from the user's team.
            # Mirrors staff_management_window.release_selected_staff (which
            # routes through release_staff_action): severance + trust shock
            # via process_staff_severance (game_classes.py:4373) -- firing
            # is never free -- then removal + news.
            try:
                sid = str(cmd.get("staff_id", ""))
                gm = getattr(app, "game_manager", None)
                team = getattr(gm, "user_team", None) or getattr(app, "user_team", None)
                if team is None or not sid:
                    print("release_staff: no team or id")
                    return
                staff = list(getattr(team, "staff", []) or [])
                target = next((s for s in staff
                               if str(getattr(s, "id", "")) == sid), None)
                if target is not None and target in getattr(team, "staff", []):
                    try:
                        from game_classes import process_staff_severance
                        entry = process_staff_severance(team, target)
                        if entry:
                            print(f"release_staff: severance ${int(entry.get('amount', 0)):,} "
                                  f"for {getattr(target, 'full_name', 'staff member')}")
                    except Exception:
                        pass
                    team.staff.remove(target)
                    try:
                        _news = getattr(app, "add_news", None)
                        if callable(_news):
                            _news(f"{getattr(target, 'full_name', 'Staff member')} "
                                  f"released by {getattr(team, 'team_name', 'your team')}.")
                    except Exception:
                        pass
                else:
                    print(f"release_staff: staff {sid} not found")
            except Exception as e:
                print(f"release_staff failed: {e}")
        elif op == "reassign_staff":
            # Reassign a staff member to a new role. Web port of
            # staff_management_window.reassign_single_staff: every role is
            # reassignable; the unique-role guard (GM / Head Coach) runs
            # here too, revalidated on the main thread.
            try:
                from game_classes import Staff as _Staff, StaffRole as _SR
                sid = str(cmd.get("staff_id", ""))
                role_name = str(cmd.get("role", ""))
                gm = getattr(app, "game_manager", None)
                team = getattr(gm, "user_team", None) or getattr(app, "user_team", None)
                if team is None or not sid or not role_name:
                    print("reassign_staff: no team, id or role")
                    return
                try:
                    new_role = _SR[role_name]
                except Exception:
                    print(f"reassign_staff: unknown role {role_name}")
                    return
                staff = list(getattr(team, "staff", []) or [])
                target = next((s for s in staff
                               if str(getattr(s, "id", "")) == sid), None)
                if target is None:
                    print(f"reassign_staff: staff {sid} not found")
                    return
                if getattr(target, "role", None) == new_role:
                    print("reassign_staff: already in that role")
                    return
                if _Staff.is_unique_role(new_role):
                    conflict = [s for s in staff
                                if getattr(s, "role", None) == new_role
                                and s is not target]
                    if conflict:
                        print(f"reassign_staff: team already has a "
                              f"{new_role.value}: {getattr(conflict[0], 'full_name', '?')}")
                        return
                target.role = new_role
                print(f"reassign_staff: {getattr(target, 'full_name', '?')} -> {new_role.value}")
            except Exception as e:
                print(f"reassign_staff failed: {e}")
        elif op == "draft_pick":
            # User drafts a prospect: record via the live session.
            try:
                pid = str(cmd.get("player_id", ""))
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                if league is None:
                    league = getattr(app, "league", None)
                team = getattr(app, "user_team", None)
                if league is not None and team is not None and pid:
                    session = getattr(league, "entry_draft_session", None)
                    if session is not None:
                        cur = int(getattr(session, "current_pick", 0) or 0)
                        overall = cur + 1
                        tname = getattr(team, "team_name", "")
                        try:
                            session.record_pick(overall, tname, pid)
                        except Exception:
                            pass
                        # Move the prospect to the team's prospect list
                        try:
                            prospect = None
                            for q in list(getattr(league, "draft_prospects", None) or []):
                                if str(getattr(q, "id", "")) == pid:
                                    prospect = q
                                    break
                            if prospect is not None:
                                try:
                                    getattr(league, "draft_prospects").remove(prospect)
                                except Exception:
                                    pass
                                plist = getattr(team, "prospects", None)
                                if plist is None:
                                    team.prospects = []
                                    plist = team.prospects
                                plist.append(prospect)
                        except Exception:
                            pass
            except Exception:
                pass
        elif op == "draft_sim_pick":
            # AI auto-picks for the current slot.
            try:
                import draft_night as dn
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                if league is None:
                    league = getattr(app, "league", None)
                team = getattr(app, "user_team", None)
                if league is not None and team is not None:
                    session = getattr(league, "entry_draft_session", None)
                    if session is not None:
                        cur = int(getattr(session, "current_pick", 0) or 0)
                        overall = cur + 1
                        # Find current slot owner
                        slots = list(getattr(session, "slots", None) or [])
                        owner = None
                        for s in slots:
                            try:
                                if int(s.get("overall", 0)) == overall:
                                    owner = s.get("owner")
                                    break
                            except Exception:
                                continue
                        # Available prospects
                        picked = set()
                        for p in list(getattr(session, "picks", None) or []):
                            try:
                                picked.add(str(p.get("player_id")))
                            except Exception:
                                pass
                        avail = [q for q in list(getattr(league, "draft_prospects", None) or [])
                                 if str(getattr(q, "id", "")) not in picked]
                        if avail and owner:
                            # Find the owning team object
                            oteam = None
                            for t in list(getattr(league, "teams", None) or []):
                                if getattr(t, "team_name", "") == owner:
                                    oteam = t
                                    break
                            if oteam is not None:
                                import random as _rnd
                                try:
                                    avail_sorted = sorted(
                                        avail,
                                        key=lambda q: int(getattr(
                                            q, "draft_ranking", 9999) or 9999))
                                    rnd = _rnd.Random()
                                    pick = dn.ai_select_prospect(
                                        oteam, avail_sorted, None, None,
                                        1, None, rnd, overall=overall)
                                except Exception:
                                    pick = None
                                if pick is None:
                                    avail.sort(key=lambda q: int(getattr(q, "overall", 0) or 0),
                                               reverse=True)
                                    pick = avail[0] if avail else None
                                if pick is not None:
                                    pid = str(getattr(pick, "id", ""))
                                    session.record_pick(overall, owner, pid)
            except Exception:
                pass
        elif op == "auto_negotiate_extensions":
            # Mirror of main.py auto_negotiate_extensions: run
            # handle_contract_offer for every expiring player/staff, then
            # send one inbox digest with results.
            try:
                from datetime import date as _date
                team = getattr(app, "user_team", None)
                if team is None:
                    return
                expiring = []
                for lst in ("roster", "ahl_roster"):
                    for p in list(getattr(team, lst, None) or []):
                        try:
                            yrs = getattr(p, "contract_years",
                                          getattr(getattr(p, "contract", None),
                                                  "years_remaining", 0))
                            if int(yrs or 0) == 1:
                                expiring.append(p)
                        except Exception:
                            continue
                for s in list(getattr(team, "staff", None) or []):
                    try:
                        yrs = getattr(s, "contract_years",
                                      getattr(s, "years_remaining", 0))
                        if int(yrs or 0) == 1:
                            expiring.append(s)
                    except Exception:
                        continue
                results = []
                for person in expiring:
                    try:
                        contract = getattr(person, "contract", None)
                        if contract is not None:
                            salary = getattr(person, "salary",
                                             getattr(contract, "salary", 750000))
                            years = getattr(person, "contract_years",
                                            getattr(contract, "years_remaining", 1))
                        else:
                            salary = getattr(person, "salary", 750000)
                            years = getattr(person, "contract_years", 1)
                        person.salary = salary
                        person.contract_years = years
                        fn = getattr(app, "handle_contract_offer", None)
                        accepted = fn(person, extension=True,
                                      notify="quiet") if callable(fn) else False
                        nm = getattr(person, "full_name",
                                     getattr(person, "name", "Unknown"))
                        results.append(f"{nm}: {'Accepted' if accepted else 'Rejected'}")
                    except Exception:
                        continue
                if results:
                    try:
                        from game_classes import EmailMessage
                        app.send_email_to_user(EmailMessage(
                            sender="Assistant GM", sender_type="Staff",
                            date_sent=_date.today(),
                            category="Contracts", priority=2,
                            subject="Auto-Negotiation Results",
                            content=("Automatic extension negotiations complete:\n"
                                     + "\n".join(results)),
                        ))
                    except Exception:
                        pass
            except Exception:
                pass
        elif op == "set_tactic":
            try:
                team = getattr(app, "user_team", None)
                attr = cmd.get("attr", "")
                value = cmd.get("value", "")
                if team is not None and attr.startswith("tactic_"):
                    setattr(team, attr, value)
            except Exception:
                pass
        elif op == "morale_action":
            try:
                import reputation_system as _rs
                team = getattr(app, "user_team", None)
                action = cmd.get("action", "")
                if team is None:
                    return
                # Find head coach
                coach = None
                for s in list(getattr(team, "staff", None) or []):
                    if "head coach" in str(getattr(s, "role", "")).lower():
                        coach = s
                        break
                roster = list(getattr(team, "roster", None) or [])
                if action == "bag_skate" and coach is not None:
                    _rs.apply_bag_skate(team, coach, roster)
                elif action == "speech" and coach is not None:
                    _rs.apply_inspiring_speech(team, coach, roster)
                elif action == "practice" and coach is not None:
                    _rs.apply_great_practice(team, coach, roster)
                elif action == "back_room":
                    import media_engine
                    media_engine.gm_public_backing(
                        getattr(app, "league", None), team, "room",
                        user_triggered=True)
                elif action == "line_control":
                    # Toggle GM/coach line control
                    cur = getattr(team, "line_control", "coach") or "coach"
                    team.line_control = "gm" if cur == "coach" else "coach"
            except Exception as e:
                print(f"morale_action failed: {e}")
        elif op == "set_practice":
            try:
                team = getattr(app, "user_team", None)
                if team is not None:
                    import dressing_room as _dr
                    fields = _dr.ensure_dressing_room_fields(team)
                    plan = fields.get("practice_plan") or {}
                    if cmd.get("focus"):
                        plan["focus"] = cmd["focus"]
                    if cmd.get("intensity"):
                        plan["intensity"] = cmd["intensity"]
                    plan["bag_skate"] = bool(cmd.get("bag_skate"))
                    fields["practice_plan"] = plan
            except Exception:
                pass
        elif op == "assign_training_program":
            # Web port of player_development_window_professional
            # ._assign_training_confirmed: records the program (persisted
            # via game_manager.training_programs, mirrored into
            # ACTIVE_TRAINING_PROGRAMS) and runs a real first session.
            _marker = "assign_training_program"
            _nonce = cmd.get("nonce")
            try:
                from enhanced_practice_system import (
                    FOCUS_TO_PRACTICE_TYPE, INTENSITY_LABEL_TO_ENUM,
                    ACTIVE_TRAINING_PROGRAMS)
                from datetime import date
                pid = cmd.get("player_id")
                focus = cmd.get("focus") or ""
                intensity_label = cmd.get("intensity") or "Standard"
                gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                elif focus not in FOCUS_TO_PRACTICE_TYPE:
                    _batchd_store(app, _marker, _nonce, False,
                                  f"Unknown focus: {focus}")
                elif intensity_label not in INTENSITY_LABEL_TO_ENUM:
                    _batchd_store(app, _marker, _nonce, False,
                                  f"Unknown intensity: {intensity_label}")
                else:
                    ptype = FOCUS_TO_PRACTICE_TYPE[focus]
                    pint = INTENSITY_LABEL_TO_ENUM[intensity_label]
                    engine = _batchd_engine()
                    can, why = engine.can_practice(player, ptype, pint)
                    if not can:
                        _batchd_store(app, _marker, _nonce, False, why)
                    else:
                        game_date = (getattr(app, "current_date", None)
                                     or date.today())
                        prog = {
                            "focus": focus,
                            "intensity": intensity_label,
                            "assigned": game_date,
                            "player_name": getattr(player, "full_name", "?"),
                        }
                        pkey = getattr(player, "id", str(pid))
                        ACTIVE_TRAINING_PROGRAMS[pkey] = prog
                        if gm is not None:
                            if not getattr(gm, "training_programs", None):
                                gm.training_programs = {}
                            gm.training_programs[pkey] = prog
                        # First session runs immediately, desktop parity:
                        # _assign_training_confirmed uses the legacy flat
                        # trainer (60 min, quality 12); the weekly tick in
                        # _process_training_programs runs the coaching-aware
                        # version with the player's own staff.
                        session = engine.execute_practice(
                            player, ptype, pint, 60, 12)
                        _batchd_store(
                            app, _marker, _nonce, True,
                            f"{getattr(player, 'full_name', 'Player')} assigned "
                            f"to {focus} ({intensity_label}). First session: "
                            f"+{session.skill_gain:.2f} skill, "
                            f"+{session.fatigue_cost}% fatigue.")
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "cancel_training_program":
            _marker = "cancel_training_program"
            _nonce = cmd.get("nonce")
            try:
                from enhanced_practice_system import ACTIVE_TRAINING_PROGRAMS
                pid = cmd.get("player_id")
                gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                pkey = (getattr(player, "id", None) if player is not None
                        else None)
                removed = False
                for key in (pkey, str(pid)):
                    if key is None:
                        continue
                    if key in ACTIVE_TRAINING_PROGRAMS:
                        ACTIVE_TRAINING_PROGRAMS.pop(key, None)
                        removed = True
                    if gm is not None and getattr(gm, "training_programs",
                                                 None) \
                            and key in gm.training_programs:
                        gm.training_programs.pop(key, None)
                        removed = True
                name = (getattr(player, "full_name", "?")
                        if player is not None else "?")
                _batchd_store(app, _marker, _nonce, True,
                              f"{name}'s training program "
                              f"{'cancelled' if removed else 'was not active'}.")
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "run_practice_session":
            # Web port of PracticeCenterView._run_single_session: one real
            # per-player drill through the engine with coaching staff.
            _marker = "run_practice_session"
            _nonce = cmd.get("nonce")
            try:
                from enhanced_practice_system import (
                    PracticeType, PracticeIntensity)
                pid = cmd.get("player_id")
                drill = PracticeType(str(cmd.get("drill") or "skating"))
                pint = PracticeIntensity(str(cmd.get("intensity")
                                             or "moderate"))
                gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                else:
                    engine = _batchd_engine()
                    can, why = engine.can_practice(player, drill, pint)
                    if not can:
                        _batchd_store(app, _marker, _nonce, False, why)
                    else:
                        coach_team = _batchd_player_team(app, team, player)
                        session = engine.execute_practice(
                            player, drill, pint, 60, 10, team=coach_team)
                        gains = ""
                        try:
                            bd = getattr(session, "breakdown", None) or {}
                            coach = bd.get("coach_name") or ""
                            gains = (f" ({coach} ran it)"
                                     if coach else "")
                        except Exception:
                            pass
                        _batchd_store(
                            app, _marker, _nonce, True,
                            f"{getattr(player, 'full_name', 'Player')}: "
                            f"{drill.value.replace('_', ' ').title()} "
                            f"({pint.value}) complete{gains}. "
                            f"+{session.skill_gain:.2f} skill, "
                            f"+{session.fatigue_cost}% fatigue.")
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "schedule_practice":
            # Web port of PracticeCenterView._start_practice_schedule.
            _marker = "schedule_practice"
            _nonce = cmd.get("nonce")
            try:
                from enhanced_practice_system import (
                    PracticeType, PracticeIntensity)
                pid = cmd.get("player_id")
                drill = PracticeType(str(cmd.get("drill") or "skating"))
                pint = PracticeIntensity(str(cmd.get("intensity")
                                             or "moderate"))
                try:
                    total = int(cmd.get("sessions", 12))
                except (TypeError, ValueError):
                    total = 12
                total = max(1, min(84, total))
                _gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                else:
                    result = _batchd_engine().schedule_practice(
                        player, drill, pint, total)
                    _batchd_store(app, _marker, _nonce, result.success,
                                  result.message)
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "stop_practice_schedule":
            _marker = "stop_practice_schedule"
            _nonce = cmd.get("nonce")
            try:
                pid = cmd.get("player_id")
                _gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                else:
                    _batchd_engine().stop_practice_schedule(player)
                    _batchd_store(app, _marker, _nonce, True,
                                  f"{getattr(player, 'full_name', 'Player')}'s "
                                  f"practice schedule stopped.")
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "coach_runs_practice":
            # "Coach Runs Practice" button (desktop PracticeCenterView):
            # weakness-targeted drills + fatigue-aware intensity for the
            # whole roster through the real engine.
            _nonce = cmd.get("nonce")
            try:
                _gm, team = _batchd_gm_team(app)
                if team is None:
                    _batchd_store(app, "coach_runs_practice", _nonce, False,
                                  "No team loaded.")
                else:
                    _batchd_coach_runs_practice(app, team, _nonce)
            except Exception as e:
                _batchd_store(app, "coach_runs_practice", _nonce, False,
                              str(e))
        elif op == "assign_position_training":
            # Positional training wired to the real familiarity engine
            # (position_training.py): one real session toward the target
            # position, persisted on player.position_familiarity.
            _marker = "assign_position_training"
            _nonce = cmd.get("nonce")
            try:
                import position_training as _pt
                pid = cmd.get("player_id")
                target = str(cmd.get("target") or "").upper()
                _gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                elif target not in _pt.eligible_training_positions(player):
                    _batchd_store(app, _marker, _nonce, False,
                                  f"{target} is not a trainable position for "
                                  f"this player.")
                else:
                    old_fam = _pt.get_familiarity(player, target)
                    cq = _batchd_coaching_quality(team)
                    new_fam, gain = _pt.train_position(player, target, cq)
                    try:
                        player.position_training_target = target
                    except Exception:
                        pass
                    _batchd_store(
                        app, _marker, _nonce, True,
                        f"{getattr(player, 'full_name', 'Player')}: {target} "
                        f"familiarity {old_fam:.0f} → {new_fam:.0f} "
                        f"(+{gain:.1f} this session).",
                        {"target": target, "old_familiarity": round(old_fam, 1),
                         "new_familiarity": round(new_fam, 1),
                         "gain": round(gain, 2)})
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "assign_offseason_program":
            # Web port of offseason_programs: gated to Jun-Aug (desktop
            # parity via is_offseason).
            _marker = "assign_offseason_program"
            _nonce = cmd.get("nonce")
            try:
                import offseason_programs as _osp
                from datetime import date
                pid = cmd.get("player_id")
                focus = cmd.get("focus") or ""
                intensity = cmd.get("intensity") or "Standard"
                _gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                else:
                    game_date = (getattr(app, "current_date", None)
                                 or date.today())
                    if not _osp.is_offseason(game_date):
                        _batchd_store(
                            app, _marker, _nonce, False,
                            "Offseason programs can only be assigned "
                            "June–August. Assign one focus per player for "
                            "the summer, then watch camp reports in "
                            "September.")
                    else:
                        ok, msg = _osp.assign_offseason_program(
                            player, focus, intensity, on_date=game_date)
                        _batchd_store(app, _marker, _nonce, ok, msg)
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "clear_offseason_program":
            _marker = "clear_offseason_program"
            _nonce = cmd.get("nonce")
            try:
                import offseason_programs as _osp
                pid = cmd.get("player_id")
                _gm, team = _batchd_gm_team(app)
                player, _squad = _batchd_find_player(team, pid)
                if player is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "Player not found on your squads.")
                else:
                    _osp.clear_offseason_program(player)
                    _batchd_store(app, _marker, _nonce, True,
                                  f"{getattr(player, 'full_name', 'Player')}'s "
                                  f"summer program cleared.")
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "coach_checkin_beat":
            # Web port of CheckinView._apply_beat: the real situational
            # trust delta from coach_checkins.py, applied live to the
            # coach's gm_trust and recorded on team.checkin_draft.
            _marker = "coach_checkin_beat"
            _nonce = cmd.get("nonce")
            try:
                import coach_checkins as _ckm
                from web_ui.screens import coach_checkin as _cks
                beat = str(cmd.get("beat") or "")
                framing = str(cmd.get("framing") or "")
                _gm, team = _batchd_gm_team(app)
                if team is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "No team loaded.")
                else:
                    fn_name = {
                        "expectations": "checkin_expectation_delta",
                        "room": "checkin_room_delta",
                        "rookies": "checkin_rookie_delta",
                        "tactics": "checkin_tactics_delta",
                    }.get(beat)
                    if fn_name is None:
                        _batchd_store(app, _marker, _nonce, False,
                                      f"Unknown beat: {beat}")
                    else:
                        coach = _batchd_checkin_coach(app, team)
                        if coach is None:
                            _batchd_store(app, _marker, _nonce, False,
                                          "No head coach found.")
                        else:
                            delta, tone, note = getattr(
                                _ckm, fn_name)(team, coach, framing)
                            try:
                                cur = float(getattr(coach, "gm_trust", 70)
                                            or 70)
                                coach.gm_trust = max(
                                    0.0, min(100.0, cur + delta))
                            except Exception:
                                pass
                            # Same situational read as the desktop view for
                            # the GM's spoken line.
                            _sit = {}
                            try:
                                if beat == "room":
                                    _sit["messy"] = bool(
                                        (_ckm.room_state(team) or {}).get(
                                            "messy"))
                                elif beat == "rookies":
                                    _sit["honored"] = bool(
                                        _ckm.rookie_stance_honored(team)[0])
                                elif beat == "tactics":
                                    _sit["working"] = bool(
                                        _ckm.tactics_working(team)[0])
                            except Exception:
                                pass
                            gm_line = _cks.gm_line_for(beat, framing, _sit)
                            draft = _batchd_checkin_draft(team)
                            rec = {
                                "beat": beat, "framing": framing,
                                "delta": delta, "tone": tone, "note": note,
                                "gm_line": gm_line,
                                "coach_line": _cks.checkin_line(
                                    tone, coach,
                                    seed=len(draft.get("chosen", []))),
                            }
                            try:
                                draft["chosen"].append(rec)
                                draft["deltas"][beat] = delta
                                for t in ("expectations", "room", "rookies",
                                          "tactics"):
                                    if t == beat and t not in draft["topics"]:
                                        draft["topics"].append(t)
                                if note and note not in draft["notes"]:
                                    draft["notes"].append(note)
                                team.checkin_draft = draft
                            except Exception:
                                pass
                            _batchd_store(
                                app, _marker, _nonce, True, note,
                                {"beat": beat, "framing": framing,
                                 "delta": delta, "tone": tone,
                                 "trust": round(float(getattr(
                                     coach, "gm_trust", 70) or 70), 1),
                                 "coach_line": rec["coach_line"],
                                 "gm_line": gm_line})
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "coach_checkin_finish":
            # Web port of CheckinView._finish: complete_checkin persists
            # the entry on the mandate history and clears the pending
            # flag (per-beat deltas already applied live).
            _marker = "coach_checkin_finish"
            _nonce = cmd.get("nonce")
            try:
                import coach_checkins as _ckm
                _gm, team = _batchd_gm_team(app)
                if team is None:
                    _batchd_store(app, _marker, _nonce, False,
                                  "No team loaded.")
                else:
                    draft = _batchd_checkin_draft(team)
                    mandate = {}
                    try:
                        mandate = _ckm.get_active_mandate(team) or {}
                    except Exception:
                        pass
                    fields = {
                        "season": mandate.get("season"),
                        "quarter": draft.get("quarter"),
                        "topics": list(draft.get("topics", [])),
                        "deltas": dict(draft.get("deltas", {})),
                        "notes": list(draft.get("notes", [])),
                    }
                    for rec in draft.get("chosen", []):
                        beat, framing = rec.get("beat"), rec.get("framing")
                        if beat == "expectations":
                            fields["expectation_framing"] = framing
                        elif beat == "room":
                            fields["room_framing"] = framing
                        elif beat == "rookies":
                            fields["rookie_framing"] = framing
                        elif beat == "tactics":
                            fields["tactics_framing"] = framing
                    entry = _ckm.complete_checkin(
                        team, fields, apply_trust=True,
                        per_beat_applied=True)
                    if entry is None:
                        _batchd_store(
                            app, _marker, _nonce, False,
                            "Check-in could not be saved -- no active "
                            "season mandate. Nothing was recorded.")
                    else:
                        try:
                            if hasattr(team, "checkin_draft"):
                                delattr(team, "checkin_draft")
                        except Exception:
                            pass
                        total = sum(int(v)
                                    for v in draft.get("deltas", {}).values()
                                    if isinstance(v, (int, float)))
                        sign = "+" if total >= 0 else ""
                        _batchd_store(
                            app, _marker, _nonce, True,
                            f"Check-in wrapped up. Net coach trust "
                            f"{sign}{total}. Recorded in the season "
                            f"mandate history.")
            except Exception as e:
                _batchd_store(app, _marker, _nonce, False, str(e))
        elif op == "roster_move":
            # Move players between rosters with CBA validation.
            # Mirrors RosterView.move_player logic (windows.py).
            try:
                from web_ui.screens.roster import execute_roster_move
                execute_roster_move(app, cmd)
            except Exception as e:
                print(f"roster_move failed: {e}")
        elif op == "save_game":
            try:
                fn = getattr(app, "open_save_window", None)
                if callable(fn):
                    fn()
            except Exception:
                pass
        elif op == "load_game":
            try:
                fn = getattr(app, "open_load_window", None)
                if callable(fn):
                    fn()
            except Exception:
                pass
        elif op == "sign_free_agent_real":
            # v2 web contract flow: validated UFA offer (years + AAV) from
            # the in-page modal. Re-validates with the real game gates,
            # then runs the real signing path:
            # HockeyManagerGUI.handle_contract_offer (main.py:21978).
            # Outcome stashed on app._web_contract_result for
            # GET /api/contracts/result polling (in-page, no OS popup).
            def _wc_store(ok, summary):
                try:
                    app._web_contract_result = {
                        "marker": "sign_free_agent_real",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                    }
                except Exception:
                    pass

            pid = cmd.get("player_id")
            try:
                years = int(cmd.get("years", 1))
            except (TypeError, ValueError):
                years = 0
            try:
                aav = int(cmd.get("aav", 0))
            except (TypeError, ValueError):
                aav = 0
            try:
                league = getattr(getattr(app, "game_manager", None),
                                 "league", None)
                team = getattr(app, "user_team", None)
                pool = list(getattr(league, "free_agents", None) or [])
                player = next((p for p in pool
                               if str(getattr(p, "id", id(p))) == str(pid)),
                              None)
                ok, reason = True, ""
                if player is None or team is None:
                    ok, reason = False, "Player not found."
                if ok:
                    import roster_limits as _rl
                    ok, reason = _rl.can_sign_player(player)
                if ok:
                    import transaction_windows as _tw
                    ok, reason = _tw.check_window(
                        "sign_ufa", getattr(app, "current_date", None))
                if ok:
                    ok, reason = app._validate_contract_terms(
                        player, aav, years, extension=False)
                if ok:
                    # Same staging as ContractNegotiationView.submit_offer
                    # (windows.py): the offer rides on the player object.
                    player.salary = aav
                    player.contract_years = years
                    # v3 multi-day negotiation: run the offer through the
                    # negotiation hook so a counter is stashed on
                    # app._web_negotiations (in addition to the inbox
                    # message) for the in-page modal. The hook itself
                    # calls the real handle_contract_offer(notify="inbox").
                    try:
                        from web_ui.screens import contracts as _neg_mod
                        _neg_mod.handle_offer_command(
                            app, pid, player, "sign", years, aav)
                    except Exception:
                        pass
                    _wc_store(True, "Offer submitted — the response will "
                                    "arrive in your inbox.")
                elif reason:
                    _wc_store(False, reason)
            except Exception:
                pass
        elif op == "extend_contract_real":
            # v2 web contract flow: validated extension (years + AAV) from
            # the in-page modal. Re-validates with the real game gates,
            # then runs the real re-sign path:
            # handle_contract_offer(extension=True) (main.py:21978).
            def _wc_store(ok, summary):
                try:
                    app._web_contract_result = {
                        "marker": "extend_contract_real",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                    }
                except Exception:
                    pass

            pid = cmd.get("player_id")
            try:
                years = int(cmd.get("years", 1))
            except (TypeError, ValueError):
                years = 0
            try:
                aav = int(cmd.get("aav", 0))
            except (TypeError, ValueError):
                aav = 0
            try:
                team = getattr(app, "user_team", None)
                roster = list(getattr(team, "roster", None) or [])
                player = next((p for p in roster
                               if str(getattr(p, "id", id(p))) == str(pid)),
                              None)
                ok, reason = True, ""
                if player is None or team is None:
                    ok, reason = False, "Player not found."
                if ok:
                    import transaction_windows as _tw
                    ok, reason = _tw.check_window(
                        "extension", getattr(app, "current_date", None),
                        ctx={"player": player})
                if ok:
                    ok, reason = app._validate_contract_terms(
                        player, aav, years, extension=True)
                if ok:
                    # Same staging as the desktop extension flow.
                    player.salary = aav
                    player.contract_years = years
                    # v3 multi-day negotiation: run the offer through the
                    # negotiation hook so a counter is stashed on
                    # app._web_negotiations (in addition to the inbox
                    # message) for the in-page modal. The hook itself
                    # calls the real handle_contract_offer(notify="inbox").
                    try:
                        from web_ui.screens import contracts as _neg_mod
                        _neg_mod.handle_offer_command(
                            app, pid, player, "extend", years, aav)
                    except Exception:
                        pass
                    _wc_store(True, "Extension submitted — the response "
                                    "will arrive in your inbox.")
                elif reason:
                    _wc_store(False, reason)
            except Exception:
                pass
        elif op == "negotiate_counter":
            # v3 multi-day negotiation: new counter-offer into an open
            # contract talk. Thin delegation: all logic lives in
            # web_ui/screens/contracts.py::handle_negotiation_command.
            try:
                from web_ui.screens import contracts as _neg_mod
                _neg_mod.handle_negotiation_command(app, cmd)
            except Exception:
                pass
        elif op == "negotiate_accept":
            # v3: accept the agent's counter as-is (real
            # HockeyManagerGUI.accept_contract_counter, main.py:22456).
            try:
                from web_ui.screens import contracts as _neg_mod
                _neg_mod.handle_negotiation_command(app, cmd)
            except Exception:
                pass
        elif op == "negotiate_walk":
            # v3: walk away (desktop equivalent:
            # inbox_window._on_contract_counter_walkaway ->
            # message.action_done = True; nothing happens to the game).
            try:
                from web_ui.screens import contracts as _neg_mod
                _neg_mod.handle_negotiation_command(app, cmd)
            except Exception:
                pass
        elif op == "present_offer_sheet":
            # Offer sheet presentation: thin delegation -- the full
            # desktop flow (OfferSheetWindow._present_offer_sheet) lives in
            # web_ui/screens/offer_sheets.py.
            try:
                from web_ui.screens import offer_sheets as _os_mod
                _os_mod.handle_present_offer_sheet_command(app, cmd)
            except Exception as _e:
                try:
                    app._web_offer_sheet_result = {
                        "marker": "present_offer_sheet", "ok": False,
                        "summary": f"Offer sheet failed: {_e}"}
                except Exception:
                    pass
        elif op == "add_scouting_assignment_real":
            # Web region assignment (replaces the v1 desktop fallback):
            # scout -> region on game_manager.scout_region_assignments
            # via scouting.set_scout_region (scouting.py:132).
            try:
                from web_ui.screens.scouting import apply_region_assignment
                apply_region_assignment(app, cmd.get("scout_id"),
                                        cmd.get("region"))
            except Exception:
                pass
        elif op == "add_scouting_assignment":
            # Replaces the old v1 desktop fallback ("open_scouting_window"):
            # real player-targeted assignment into app.scouting_assignments
            # via scouting_window_helpers.create_scout_assignment.
            try:
                from web_ui.screens.scouting import apply_player_assignment
                apply_player_assignment(app, cmd.get("prospect_id"),
                                        cmd.get("scout_id"))
            except Exception:
                pass
        elif op == "set_lines_real":
            # Web line editor: re-validate server-side, then apply through
            # the real machinery (quick_sim.flatten_lineup, same as the
            # desktop editor and _mp_set_lines).
            try:
                from web_ui.screens.lines import (validate_lines_payload,
                                                  apply_lines_payload)
                team = getattr(app, "user_team", None)
                slot_lines = cmd.get("lines") or {}
                ok, err, resolved = validate_lines_payload(team, slot_lines)
                if ok and resolved is not None:
                    apply_lines_payload(team, resolved)
            except Exception:
                pass
        elif op == "set_st_lines_real":
            # Web special-teams editor (PP1/PP2/PK1/PK2): re-validate
            # server-side, then apply the nested PP/PK units onto
            # team.lineup through the real machinery
            # (quick_sim.flatten_lineup, same as the desktop editor).
            try:
                from web_ui.screens.lines import (validate_st_payload,
                                                  apply_st_payload)
                team = getattr(app, "user_team", None)
                st_lines = cmd.get("st") or {}
                ok, err, resolved = validate_st_payload(team, st_lines)
                if ok and resolved is not None:
                    apply_st_payload(team, resolved)
            except Exception:
                pass
        elif op == "execute_trade":
            # Web trade builder (v2 modal): resolves assets, validates
            # retention/protection terms, then SENDS the offer through the
            # REAL async negotiation machinery (trade_negotiation.
            # send_offer) -- the AI GM answers in 1-3 sim days via the
            # inbox, instantly only on the deadline-day rush. Nothing
            # executes here. Outcome is stashed on app._web_trade_result
            # for GET /api/trades/result polling.
            try:
                import trade_engine as _te
            except Exception:
                _te = None

            def _wt_store(ok, summary, verdict="", pending=False,
                          negotiation_id=""):
                try:
                    app._web_trade_result = {
                        "marker": "execute_trade",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                        "verdict": str(verdict or ""),
                        # Async negotiation (desktop parity): a proposal is
                        # pending until the AI GM answers in 1-3 sim days.
                        "pending": bool(pending),
                        "negotiation_id": str(negotiation_id or ""),
                    }
                except Exception:
                    pass

            try:
                if _te is None:
                    _wt_store(False, "Trade engine unavailable.", "")
                    return

                user_team = getattr(app, "user_team", None)
                gm = getattr(app, "game_manager", None)
                league = (getattr(gm, "league", None)
                          or getattr(app, "league", None))

                # Find the partner team (abbr, name, team_name, "City Name").
                partner = _wt_find_partner(league, cmd.get("target_team_id"))
                if user_team is None or partner is None:
                    _wt_store(False, "Could not resolve teams.", "")
                    return

                # Resolve asset ids -> live objects (players + picks).
                _pid_want = {str(x) for x in (cmd.get("give_pids") or [])}
                _pick_want = {str(x) for x in (cmd.get("give_picks") or [])}
                _pid_get = {str(x) for x in (cmd.get("want_pids") or [])}
                _pick_get = {str(x) for x in (cmd.get("want_picks") or [])}
                give_assets = _wt_resolve_trade_assets(
                    user_team, _pid_want, _pick_want)
                want_assets = _wt_resolve_trade_assets(
                    partner, _pid_get, _pick_get)
                if not give_assets and not want_assets:
                    _wt_store(False, "Empty proposal.", "")
                    return

                # Gap 2: salary retention + pick protection terms from the
                # web trade builder (cmd["retention"], cmd["pick_protection"]).
                # Server-side re-validation (the /api/trades/propose route
                # already validated; never trust the client twice):
                #   - pct must be 0 < pct <= MAX_RETENTION_PCT (engine: 50)
                #   - protection codes limited to the engine's real set
                #     ("top-3" | "top-10" | "lottery")
                #   - terms dropped for stale assets (not in this deal)
                #   - retention dry-run through the engine's own
                #     apply_retention_dry_run (3-slot club limit counting
                #     the deal's other terms via `extra`, 75-day
                #     double-retention clock, two-club rule) — a bad term
                #     fails here with a clear message, not BLOCKED later.
                _wt_retention, _wt_protection, _wt_err = _wt_parse_terms(
                    cmd, user_team, give_assets, _te)
                if _wt_err:
                    _wt_store(False, _wt_err, "")
                    return

                # ASYNC negotiation (desktop parity, trade_negotiation.py):
                # a proposal is SENT, never executed instantly. send_offer
                # creates a pending TradeNegotiation with response_due =
                # today + 1-3 days and drops an "offer sent" inbox message;
                # the AI GM's answer (accept / counter / reject) arrives
                # via the inbox when process_due_negotiations runs on day
                # advance (main.simulate_day). Instant execution survives
                # only on the deadline-day rush: send_offer answers on the
                # spot there (its own is_deadline_rush/is_cap_crunch_rush
                # check), exactly like the desktop.
                try:
                    import trade_negotiation as _tn
                except Exception:
                    _tn = None
                if _tn is None:
                    _wt_store(False, "Negotiation machinery unavailable.",
                              "")
                    return
                try:
                    neg = _tn.send_offer(
                        app, partner, give_assets, want_assets,
                        retention=_wt_retention,
                        pick_protection=_wt_protection)
                except Exception as _e:
                    _wt_store(False, f"Could not send offer: {_e}", "")
                    return
                _pname = str(getattr(partner, "team_name", None)
                             or "the other club")
                _neg_id = str(getattr(neg, "id", "") or "")
                if getattr(neg, "status", "") == "awaiting_ai" and \
                        getattr(neg, "response_due", None) is not None:
                    _wt_store(True,
                              f"Offer sent to {_pname}. Their GM needs "
                              f"1-3 days -- the answer lands in your "
                              f"inbox (accept, counter, or reject).",
                              "pending", True, _neg_id)
                else:
                    # Rush path (deadline day / cap crunch): the AI
                    # already answered on the spot -- check the inbox.
                    _wt_store(True,
                              f"Deadline-day rush: {_pname}'s GM answered "
                              f"instantly -- check your inbox.",
                              "instant", False, _neg_id)
            except Exception:
                pass
        elif op == "trade_counter_negotiation":
            # User answers an AI counter with adjusted trade-builder terms.
            # Desktop parity: trade_negotiation.send_counter -- the
            # negotiation stays open (patience decays), the AI answers in
            # 1-3 sim days via the inbox. Outcome is stashed for
            # GET /api/trades/result polling (marker differs so the UI
            # can tell it apart from a fresh proposal).
            try:
                import trade_engine as _te2
            except Exception:
                _te2 = None

            def _wtc_store(ok, summary):
                try:
                    app._web_trade_result = {
                        "marker": "trade_counter_negotiation",
                        "ok": bool(ok),
                        "summary": str(summary or ""),
                        "pending": bool(ok),
                    }
                except Exception:
                    pass

            try:
                import trade_negotiation as _tn2
            except Exception:
                _tn2 = None
            try:
                if _tn2 is None or _te2 is None:
                    _wtc_store(False, "Negotiation machinery unavailable.")
                else:
                    neg = _tn2.get_negotiation(app, cmd.get("negotiation_id"))
                    if neg is None or not neg.is_open:
                        _wtc_store(False,
                                   "That negotiation is no longer open.")
                    else:
                        user_team = getattr(app, "user_team", None)
                        partner = _tn2.find_team(app, neg.partner_team_name)
                        if user_team is None or partner is None:
                            _wtc_store(False, "Could not resolve teams.")
                        else:
                            give_assets = _wt_resolve_trade_assets(
                                user_team,
                                {str(x) for x in (cmd.get("give_pids") or [])},
                                {str(x) for x in (cmd.get("give_picks") or [])})
                            want_assets = _wt_resolve_trade_assets(
                                partner,
                                {str(x) for x in (cmd.get("want_pids") or [])},
                                {str(x) for x in (cmd.get("want_picks") or [])})
                            if not give_assets and not want_assets:
                                _wtc_store(False, "Empty counter-offer.")
                            else:
                                _ret, _prot, _err = _wt_parse_terms(
                                    cmd, user_team, give_assets, _te2)
                                if _err:
                                    _wtc_store(False, _err)
                                else:
                                    _tn2.send_counter(
                                        app, neg, give_assets, want_assets,
                                        retention=_ret,
                                        pick_protection=_prot)
                                    _wtc_store(
                                        True,
                                        f"Counter sent to "
                                        f"{neg.partner_team_name} -- they "
                                        f"answer in 1-3 days via your inbox.")
            except Exception:
                pass
        elif op == "inbox_trade_accept":
            _, msg = _find_inbox_message(app, cmd.get("message_id"))
            if msg is not None:
                try:
                    import trade_negotiation as tn
                    neg_id = (getattr(msg, "action_data", None) or {}).get("negotiation_id")
                    if neg_id:
                        tn.accept_negotiation(app, neg_id)
                    msg.action_done = True
                except Exception:
                    pass
        elif op == "inbox_trade_decline":
            _, msg = _find_inbox_message(app, cmd.get("message_id"))
            if msg is not None:
                try:
                    import trade_negotiation as tn
                    neg_id = (getattr(msg, "action_data", None) or {}).get("negotiation_id")
                    if neg_id:
                        tn.decline_negotiation(app, neg_id)
                    msg.action_done = True
                except Exception:
                    pass
        elif op == "inbox_contract_accept":
            _, msg = _find_inbox_message(app, cmd.get("message_id"))
            if msg is not None:
                try:
                    fn = getattr(app, "accept_contract_counter", None)
                    if callable(fn):
                        fn(msg)
                    msg.action_done = True
                except Exception:
                    pass
        elif op == "inbox_contract_walkaway":
            _, msg = _find_inbox_message(app, cmd.get("message_id"))
            if msg is not None:
                try:
                    msg.action_done = True
                except Exception:
                    pass
        elif op == "delete_message":
            mid = cmd.get("message_id")
            team = getattr(app, "user_team", None)
            inbox = getattr(team, "inbox", None)
            if inbox and mid:
                try:
                    inbox.delete_message(mid)
                except Exception:
                    pass
    except Exception:
        pass


# ------------------------------------------------------------------
# Flask app factory
# ------------------------------------------------------------------
def create_app(game_app=None):
    """Build the Flask app bound to a game app (or None for mock mode)."""
    import os
    from flask import Flask, jsonify, render_template, request

    global _web_app_ref
    if game_app is not None:
        _web_app_ref = game_app

    here = os.path.dirname(__file__)
    app = Flask(__name__,
                template_folder=os.path.join(here, "templates"),
                static_folder=os.path.join(here, "static"))

    # Screen blueprints: each screen is self-contained (API + page route)
    # in web_ui/screens/<name>.py so parallel work never conflicts.
    try:
        import importlib, pkgutil
        import web_ui.screens as _screens_pkg
        for _mod in pkgutil.iter_modules(_screens_pkg.__path__):
            try:
                _m = importlib.import_module(f"web_ui.screens.{_mod.name}")
                _bp = getattr(_m, "bp", None)
                if _bp is not None:
                    app.register_blueprint(_bp)
            except Exception as e:
                print(f"Web UI screen '{_mod.name}' failed to load: {e}")
    except Exception:
        pass

    def _live():
        return _web_app_ref

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/inbox")
    def inbox_page():
        return render_template("inbox.html")

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True,
                        "mode": "live" if _live() else "mock"})

    @app.route("/api/state")
    def state():
        live = _live()
        if live is None:
            # mock fallback (POC data)
            from web_ui.server import MOCK_STATE  # noqa
            return jsonify(MOCK_STATE)
        return jsonify(get_hub_state(live))

    @app.route("/api/inbox")
    def inbox():
        live = _live()
        if live is None:
            return jsonify([])
        f = request.args.get("filter", "all")
        return jsonify(get_inbox_messages(live, f))

    @app.route("/api/schedule")
    def schedule():
        live = _live()
        if live is None:
            return jsonify([])
        return jsonify(get_schedule(live))

    @app.route("/schedule")
    def schedule_page():
        return render_template("schedule.html")

    @app.route("/api/continue_state")
    def continue_state():
        live = _live()
        if live is None:
            return jsonify({"label": "Continue", "blocked": False, "blockers": []})
        return jsonify(get_continue_state(live))

    @app.route("/api/command", methods=["POST"])
    def command():
        data = request.get_json(force=True, silent=True) or {}
        op = data.get("op")
        if not op:
            return jsonify({"ok": False, "error": "no op"}), 400
        ok = enqueue_command(op, **{k: v for k, v in data.items() if k != "op"})
        return jsonify({"ok": ok, "queued": op})

    @app.route("/api/heartbeat", methods=["POST"])
    def heartbeat():
        note_heartbeat()
        return jsonify({"ok": True})

    @app.route("/api/watch_mode", methods=["GET", "POST"])
    def watch_mode():
        """Get or set the game-day mode: 'watch' or 'quick'."""
        global _watch_mode
        if request.method == "POST":
            data = request.get_json(force=True, silent=True) or {}
            mode = data.get("mode")
            if mode in ("watch", "quick"):
                _watch_mode = mode
                return jsonify({"ok": True, "mode": _watch_mode})
            return jsonify({"ok": False, "error": "mode must be watch or quick"}), 400
        return jsonify({"mode": _watch_mode})

    @app.route("/api/exit", methods=["POST"])
    def exit_game():
        # User clicked Exit in the web UI: shut down cleanly.
        enqueue_command("exit_game")
        return jsonify({"ok": True})

    return app


def start_web_server(game_app, port=5050):
    """Start Flask in a background thread bound to the live game.

    Verifies the port is actually listening afterwards — if another
    process holds the port, app.run() dies inside the thread and the
    user would otherwise get a dead browser window with no explanation.
    Returns the thread on success, None if the server never came up.
    """
    global _server_thread
    if _server_thread is not None and _server_thread.is_alive():
        return _server_thread
    app = create_app(game_app)

    def _run():
        try:
            app.run(host="127.0.0.1", port=port, threaded=True,
                    use_reloader=False)
        except Exception as e:
            print(f"Web UI server failed: {e}")

    _server_thread = threading.Thread(target=_run, daemon=True,
                                      name="puck-web-ui")
    _server_thread.start()
    # Confirm Flask actually bound the port (catches "port in use").
    import socket as _socket
    import time as _time
    for _ in range(40):  # ~6s
        try:
            with _socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return _server_thread
        except OSError:
            _time.sleep(0.15)
    print(f"Web UI server did not come up on port {port} "
          f"(already in use?)")
    _server_thread = None
    return None
