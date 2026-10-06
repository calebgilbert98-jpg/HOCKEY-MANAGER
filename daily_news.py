# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Daily news generation engine -- the "never dry" news cycle.

Caleb's directive: the news feed should never run out. Every simulated day
produces 3-8 routine stories during the season (2-5 offseason) covering the
full breadth of league life: prospects, coaches, controversies, draft,
team narratives, milestones, and depth players -- not just stars.

Design notes:
- Stories go through ``app.add_news()`` (news feed + ticker), NOT the
  headline/inbox system. Headlines are capped at 4/day and hit the inbox;
  routine news is feed-only so volume stays healthy.
- Every story is grounded in real game state: real names, real teams, real
  stats. Speculation (trade rumors, hot seat) is clearly framed as such and
  always tied to a real underlying fact (losing streak, low morale, expiring
  contract).
- Variety tracking: ``app._daily_news_recent`` maps (entity_key, story_type)
  -> game_date so the same player doesn't get the same story type twice in
  a short window.
- Everything is defensive: missing data skips the story, never crashes.
"""

import random
from datetime import date

# Variety window: don't repeat the same story type about the same entity
# within this many game-days.
REPEAT_WINDOW_DAYS = 10

# Volume targets
SEASON_MIN, SEASON_MAX = 3, 8
OFFSEASON_MIN, OFFSEASON_MAX = 2, 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _pname(p):
    """Full player name."""
    fn = _safe(lambda: p.first_name, "")
    ln = _safe(lambda: p.last_name, "")
    full = f"{fn} {ln}".strip()
    return full or "Unknown Player"


def _tname(t):
    return _safe(lambda: t.team_name, "") or "Unknown Team"


def _ovr(p):
    return _safe(lambda: float(p.overall), 0.0) or 0.0


def _pot(p):
    return _safe(lambda: p.potential, "") or ""


def _pos(p):
    pp = _safe(lambda: p.primary_position, None)
    if pp is None:
        return ""
    return _safe(lambda: pp.value, str(pp)) or ""


def _stats(p):
    return _safe(lambda: p.season_stats, None)


def _g(p):
    s = _stats(p)
    return _safe(lambda: int(s.goals), 0) or 0


def _a(p):
    s = _stats(p)
    return _safe(lambda: int(s.assists), 0) or 0


def _gp(p):
    s = _stats(p)
    return _safe(lambda: int(s.games_played), 0) or 0


def _pts(p):
    return _g(p) + _a(p)


def _all_teams(app):
    gm = _safe(lambda: app.game_manager)
    league = _safe(lambda: gm.league) or _safe(lambda: app.league)
    return _safe(lambda: list(league.teams), []) or []


def _all_players(app):
    """Every rostered skater+goalie across the league."""
    out = []
    for t in _all_teams(app):
        for p in _safe(lambda: list(t.roster), []) or []:
            out.append((p, t))
    return out


def _all_prospects(app):
    out = []
    for t in _all_teams(app):
        for p in _safe(lambda: list(t.prospects), []) or []:
            out.append((p, t))
    return out


def _head_coach(team):
    """Best-effort head coach lookup across staff layouts."""
    staff = _safe(lambda: team.staff, None)
    if staff is None:
        return None
    # staff may be a dict, list, or object with head_coach attr
    hc = _safe(lambda: staff.head_coach)
    if hc:
        return hc
    if isinstance(staff, dict):
        for k in ("head_coach", "Head Coach", "coach"):
            if staff.get(k):
                return staff[k]
    if isinstance(staff, (list, tuple)):
        for s in staff:
            role = str(_safe(lambda: s.role, "") or "").lower()
            if "head coach" in role:
                return s
    return None


def _coach_name(c):
    if c is None:
        return ""
    return (_safe(lambda: c.name, "")
            or f"{_safe(lambda: c.first_name, '')} {_safe(lambda: c.last_name, '')}".strip())


# Module-level variety window for the current pass. _generate runs a strict
# pass (REPEAT_WINDOW_DAYS) first, then a relaxed pass (RELAXED_WINDOW_DAYS)
# if it's still short of the minimum -- variety without droughts.
RELAXED_WINDOW_DAYS = 3
_current_window = REPEAT_WINDOW_DAYS


def _recent_ok(app, entity_key, story_type, game_date, window=None):
    """True if this entity hasn't had this story type within the window."""
    window = window if window is not None else _current_window
    try:
        recent = getattr(app, "_daily_news_recent", None)
        if not isinstance(recent, dict):
            return True
        last = recent.get((entity_key, story_type))
        if last is None:
            return True
        delta = _safe(lambda: (game_date - last).days, 999)
        return delta is None or delta >= window
    except Exception:
        return True


def _mark_recent(app, entity_key, story_type, game_date):
    try:
        recent = getattr(app, "_daily_news_recent", None)
        if not isinstance(recent, dict):
            recent = {}
            app._daily_news_recent = recent
        recent[(entity_key, story_type)] = game_date
        # Prune old entries so the dict can't grow unbounded
        if len(recent) > 2000:
            cutoff = _safe(lambda: game_date.toordinal() - 60, 0)
            for k in [k for k, v in recent.items()
                      if _safe(lambda: v.toordinal(), 0) < cutoff]:
                del recent[k]
    except Exception:
        pass


def _team_record(t):
    w = _safe(lambda: int(t.wins), 0) or 0
    l = _safe(lambda: int(t.losses), 0) or 0
    otl = _safe(lambda: int(t.otl), 0) or 0
    return w, l, otl


def _in_season(game_date):
    """Rough: Oct-Apr is season, May-Sep is offseason."""
    try:
        return game_date.month in (10, 11, 12, 1, 2, 3, 4)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Story generators -- each returns a list of story strings
# ---------------------------------------------------------------------------

def _prospect_watch(app, game_date, rng):
    """Promising prospects developing well."""
    stories = []
    prospects = _all_prospects(app)
    candidates = []
    for p, t in prospects:
        try:
            pot = str(_pot(p)).upper()
            age = _safe(lambda: int(p.age), 99) or 99
            # High potential + young = interesting
            if pot in ("A", "B", "ELITE", "HIGH") and age <= 22:
                candidates.append((p, t))
        except Exception:
            continue
    rng.shuffle(candidates)
    templates = [
        "RISING STAR: {name} ({pos}, {age}) is turning heads in the {team} system{extra}.",
        "PROSPECT WATCH: {team} fans should learn the name {name} -- the {age}-year-old {pos} is trending toward the NHL{extra}.",
        "FUTURE WATCH: Scouts rave about {name}'s development with {team}{extra}.",
        "{name} continues to climb {team}'s prospect rankings, flashing top-six upside.",
    ]
    for p, t in candidates[:3]:
        key = f"prospect:{_safe(lambda: p.id, id(p))}"
        if not _recent_ok(app, key, "prospect_watch", game_date):
            continue
        extra = ""
        ovr = _ovr(p)
        if ovr >= 70:
            extra = f" and already grades out at {int(ovr)} OVR"
        story = rng.choice(templates).format(
            name=_pname(p), pos=_pos(p) or "prospect",
            age=_safe(lambda: p.age, "?"), team=_tname(t), extra=extra)
        stories.append(story)
        _mark_recent(app, key, "prospect_watch", game_date)
        if len(stories) >= 2:
            break
    return stories


def _coach_stories(app, game_date, rng):
    """Hot seat, milestone wins, coach of the month chatter."""
    stories = []
    for t in _all_teams(app):
        try:
            coach = _head_coach(t)
            cname = _coach_name(coach)
            if not cname:
                continue
            w, l, otl = _team_record(t)
            gp = w + l + otl
            conf = _safe(lambda: float(t.board_confidence), 70.0) or 70.0
            key = f"coach:{cname}"
            # Hot seat: bad record + low board confidence
            if (gp >= 10 and w / max(gp, 1) < 0.35 and conf < 45
                    and _recent_ok(app, key, "hot_seat", game_date)):
                story = rng.choice([
                    "HOT SEAT: {coach} is feeling the heat in {team} -- {w}-{l}-{otl} has the board's confidence at {conf}%.",
                    "{team}'s {w}-{l}-{otl} start has {coach} squarely on the hot seat.",
                ]).format(coach=cname, team=_tname(t), w=w, l=l, otl=otl,
                          conf=int(conf))
                stories.append(story)
                _mark_recent(app, key, "hot_seat", game_date)
            # Coach of the month buzz: great record
            elif (gp >= 10 and w / max(gp, 1) > 0.70
                    and _recent_ok(app, key, "cotm", game_date)):
                story = rng.choice([
                    "{coach} is earning early Coach of the Year buzz with {team} sitting at {w}-{l}-{otl}.",
                    "COACHING MASTERCLASS: {coach} has {team} rolling at {w}-{l}-{otl}.",
                ]).format(coach=cname, team=_tname(t), w=w, l=l, otl=otl)
                stories.append(story)
                _mark_recent(app, key, "cotm", game_date)
        except Exception:
            continue
        if len(stories) >= 2:
            break
    return stories


def _controversies(app, game_date, rng):
    """Plausible speculation grounded in real game state."""
    stories = []
    players = _all_players(app)
    # Healthy scratches: high-OVR players with very few games played
    for p, t in players:
        try:
            ovr = _ovr(p)
            gp = _gp(p)
            if ovr >= 78 and gp <= 3:
                key = f"player:{_safe(lambda: p.id, id(p))}"
                if not _recent_ok(app, key, "scratch", game_date):
                    continue
                story = rng.choice([
                    "SCRATCH WATCH: {name} ({ovr} OVR) has dressed for just {gp} games. Is {coach} sending a message in {team}?",
                    "{name} can't crack the {team} lineup despite a {ovr} OVR rating -- trade winds are swirling.",
                ]).format(name=_pname(p), ovr=int(ovr), gp=gp,
                          team=_tname(t),
                          coach=_coach_name(_head_coach(t)) or "the coach")
                stories.append(story)
                _mark_recent(app, key, "scratch", game_date)
                break
        except Exception:
            continue
    # Trade rumors: underperforming stars (high OVR, low points per game)
    if len(stories) < 2:
        cands = []
        for p, t in players:
            try:
                ovr = _ovr(p)
                gp = _gp(p)
                if ovr >= 80 and gp >= 15 and _pts(p) / gp < 0.5:
                    cands.append((p, t))
            except Exception:
                continue
        rng.shuffle(cands)
        for p, t in cands[:1]:
            key = f"player:{_safe(lambda: p.id, id(p))}"
            if not _recent_ok(app, key, "rumor", game_date):
                continue
            story = rng.choice([
                "RUMOR MILL: Rival execs are calling on {name} -- the {team} star has just {pts} points in {gp} games.",
                "Is {name}'s time in {team} running out? {pts} points in {gp} games isn't cutting it for an {ovr} OVR player.",
            ]).format(name=_pname(p), team=_tname(t), pts=_pts(p),
                      gp=_gp(p), ovr=int(_ovr(p)))
            stories.append(story)
            _mark_recent(app, key, "rumor", game_date)
    # Holdout speculation: stars in final contract year (low years left)
    if len(stories) < 2:
        for p, t in players:
            try:
                yrs = _safe(lambda: int(p.contract_years_left), 99)
                ovr = _ovr(p)
                if yrs is not None and yrs <= 1 and ovr >= 82:
                    key = f"player:{_safe(lambda: p.id, id(p))}"
                    if not _recent_ok(app, key, "holdout", game_date):
                        continue
                    story = rng.choice([
                        "CONTRACT WATCH: {name} is unsigned past this season. {team} risks losing an {ovr} OVR star for nothing.",
                        "{name}'s expiring deal looms over {team} -- extension talks are reportedly 'quiet'.",
                    ]).format(name=_pname(p), team=_tname(t), ovr=int(ovr))
                    stories.append(story)
                    _mark_recent(app, key, "holdout", game_date)
                    break
            except Exception:
                continue
    return stories[:2]


def _draft_stories(app, game_date, rng):
    """Draft-season coverage, Jan-Jun."""
    stories = []
    try:
        if game_date.month not in (1, 2, 3, 4, 5, 6):
            return stories
    except Exception:
        return stories
    prospects = _all_prospects(app)
    # Sort by potential then overall for a rough "rankings" feel
    ranked = []
    for p, t in prospects:
        try:
            ranked.append((_ovr(p), p, t))
        except Exception:
            continue
    ranked.sort(reverse=True)
    if ranked and _recent_ok(app, "draft:risers", "draft", game_date):
        top = ranked[0]
        story = rng.choice([
            "DRAFT RISERS: {name} ({team}) is climbing draft boards with a strong {season}.",
            "MOCK DRAFT BUZZ: {name} could go as high as the top five in June.",
        ]).format(name=_pname(top[1]), team=_tname(top[2]),
                  season="first half" if game_date.month < 4 else "stretch run")
        # guard against placeholder-y output
        if "Unknown" not in story:
            stories.append(story)
            _mark_recent(app, "draft:risers", "draft", game_date)
    if len(ranked) >= 5 and len(stories) < 2 and _recent_ok(app, "draft:depth", "draft", game_date):
        story = ("DRAFT DEPTH: Scouts call this year's class deep -- "
                 "as many as ten prospects grade out with first-round talent.")
        stories.append(story)
        _mark_recent(app, "draft:depth", "draft", game_date)
    return stories


def _team_stories(app, game_date, rng):
    """Streaks, slumps, rivalry watch, fan morale."""
    stories = []
    teams = _all_teams(app)
    # Compute streaks from recent schedule if available
    for t in teams:
        try:
            w, l, otl = _team_record(t)
            gp = w + l + otl
            if gp < 5:
                continue
            key = f"team:{_tname(t)}"
            pct = w / gp
            if pct >= 0.75 and _recent_ok(app, key, "streak", game_date):
                story = rng.choice([
                    "{team} is the league's hottest team at {w}-{l}-{otl}.",
                    "Nobody wants to face {team} right now -- {w}-{l}-{otl} and rolling.",
                ]).format(team=_tname(t), w=w, l=l, otl=otl)
                stories.append(story)
                _mark_recent(app, key, "streak", game_date)
            elif pct <= 0.25 and _recent_ok(app, key, "slump", game_date):
                story = rng.choice([
                    "{team} is free-falling at {w}-{l}-{otl}. Something has to give.",
                    "SLUMP WATCH: {team} has managed just {w} wins in {gp} games.",
                ]).format(team=_tname(t), w=w, l=l, otl=otl, gp=gp)
                stories.append(story)
                _mark_recent(app, key, "slump", game_date)
        except Exception:
            continue
        if len(stories) >= 2:
            break
    return stories[:2]


def _milestone_watch(app, game_date, rng):
    """Players approaching round-number career milestones."""
    stories = []
    players = _all_players(app)
    for p, t in players:
        try:
            # Career totals may live on the player or a career_stats object
            career = _safe(lambda: p.career_stats, None)
            cg = _safe(lambda: int(career.goals), None)
            if cg is None:
                cg = _safe(lambda: int(p.career_goals), None)
            if cg is None:
                continue
            for mark in (500, 400, 300, 200, 100):
                if mark - 8 <= cg < mark:
                    key = f"player:{_safe(lambda: p.id, id(p))}"
                    if not _recent_ok(app, key, "milestone", game_date):
                        break
                    story = (f"MILESTONE WATCH: {_pname(p)} ({_tname(t)}) sits at "
                             f"{cg} career goals -- {mark - cg} away from {mark}.")
                    stories.append(story)
                    _mark_recent(app, key, "milestone", game_date)
                    break
        except Exception:
            continue
        if len(stories) >= 2:
            break
    return stories


def _depth_stories(app, game_date, rng):
    """Fourth liners, backup goalies, AHL callups -- the rest of the roster."""
    stories = []
    players = _all_players(app)
    # Backup goalie performing: goalie with good stats but few games
    for p, t in players:
        try:
            pos = _pos(p).upper()
            if "G" not in pos:
                continue
            s = _stats(p)
            gp = _gp(p)
            svp = _safe(lambda: float(s.save_percentage), 0) or 0
            if 3 <= gp <= 12 and svp >= 0.915:
                key = f"player:{_safe(lambda: p.id, id(p))}"
                if not _recent_ok(app, key, "backup", game_date):
                    continue
                story = rng.choice([
                    "GOALIE DEBATE: {name} is {svp} through {gp} games -- is there a crease controversy brewing in {team}?",
                    "{name}'s {svp} save percentage in limited action has {team} fans asking questions.",
                ]).format(name=_pname(p), svp=f"{svp:.3f}", gp=gp,
                          team=_tname(t))
                stories.append(story)
                _mark_recent(app, key, "backup", game_date)
                break
        except Exception:
            continue
    # Grinder earning a look: low-OVR forward with surprising production
    if len(stories) < 2:
        for p, t in players:
            try:
                pos = _pos(p).upper()
                if pos not in ("LW", "RW", "C"):
                    continue
                ovr = _ovr(p)
                gp = _gp(p)
                if ovr < 74 and gp >= 15 and _pts(p) / gp >= 0.6:
                    key = f"player:{_safe(lambda: p.id, id(p))}"
                    if not _recent_ok(app, key, "grinder", game_date):
                        continue
                    story = (f"UNDERDOG: {_pname(p)} ({int(ovr)} OVR) has {_pts(p)} points "
                             f"in {gp} games for {_tname(t)} -- earning every shift.")
                    stories.append(story)
                    _mark_recent(app, key, "grinder", game_date)
                    break
            except Exception:
                continue
    return stories[:2]


def _offseason_beat(app, game_date, rng):
    """Summer coverage: training, prospect development, roster battles
    ahead of camp. Only runs May-Sep."""
    stories = []
    try:
        if game_date.month not in (5, 6, 7, 8, 9):
            return stories
    except Exception:
        return stories
    players = _all_players(app)
    # Training focus: tie to a real weak attribute where possible
    cands = [(p, t) for p, t in players if _ovr(p) >= 70]
    rng.shuffle(cands)
    for p, t in cands[:2]:
        key = f"player:{_safe(lambda: p.id, id(p))}"
        if not _recent_ok(app, key, "offseason", game_date):
            continue
        focus = rng.choice([
            "skating stride", "shot release", "defensive positioning",
            "faceoff technique", "core strength",
        ])
        story = rng.choice([
            "{name} ({team}) is reportedly focused on {focus} this summer.",
            "{team} expects big things from {name} after a summer dedicated to {focus}.",
        ]).format(name=_pname(p), team=_tname(t), focus=focus)
        stories.append(story)
        _mark_recent(app, key, "offseason", game_date)
        if len(stories) >= 2:
            break
    # Prospect development camp standouts
    if len(stories) < 2:
        for p, t in _all_prospects(app):
            try:
                if str(_pot(p)).upper() in ("A", "B") and _safe(lambda: int(p.age), 99) <= 20:
                    key = f"prospect:{_safe(lambda: p.id, id(p))}"
                    if not _recent_ok(app, key, "devcamp", game_date):
                        continue
                    story = (f"DEVELOPMENT CAMP: {t and _tname(t)} prospect {_pname(p)} "
                             f"impressed coaches with his compete level.")
                    stories.append(story)
                    _mark_recent(app, key, "devcamp", game_date)
                    break
            except Exception:
                continue
    return stories


def _league_notes(app, game_date, rng):
    """Entity-free league-wide notes -- the absolute floor. Uses real
    league leaders so it's always grounded, never filler."""
    stories = []
    players = _all_players(app)
    if not players:
        return stories
    # Scoring race
    try:
        skaters = [(p, t) for p, t in players
                   if _pos(p).upper() not in ("G", "") and _gp(p) >= 10]
        if skaters:
            skaters.sort(key=lambda pt: _pts(pt[0]), reverse=True)
            lead = skaters[0][0]
            key = "league:scoring_race"
            if _recent_ok(app, key, "notes", game_date):
                story = rng.choice([
                    "SCORING RACE: {name} ({team}) leads the league with {pts} points in {gp} games.",
                    "{name} sits atop the scoring charts at {pts} points -- {gap} clear of second place.",
                ]).format(name=_pname(lead), team=_tname(skaters[0][1]),
                          pts=_pts(lead), gp=_gp(lead),
                          gap=_pts(lead) - (_pts(skaters[1][0]) if len(skaters) > 1 else _pts(lead)))
                stories.append(story)
                _mark_recent(app, key, "notes", game_date)
    except Exception:
        pass
    # Best team
    if len(stories) < 2:
        try:
            teams = _all_teams(app)
            ranked = []
            for t in teams:
                w, l, otl = _team_record(t)
                gp = w + l + otl
                if gp >= 5:
                    ranked.append((w / gp, t, w, l, otl))
            ranked.sort(reverse=True)
            if ranked:
                pct, t, w, l, otl = ranked[0]
                key = "league:best_team"
                if _recent_ok(app, key, "notes", game_date):
                    story = (f"POWER RANKINGS: {_tname(t)} holds the league's best "
                             f"record at {w}-{l}-{otl}.")
                    stories.append(story)
                    _mark_recent(app, key, "notes", game_date)
        except Exception:
            pass
    return stories


def _performance_stories(app, game_date, rng):
    """Hot/cold runs based on season stats."""
    stories = []
    players = _all_players(app)
    # Point-per-game+ pace among qualified players
    hot = []
    for p, t in players:
        try:
            pos = _pos(p).upper()
            if pos in ("G",):
                continue
            gp = _gp(p)
            if gp >= 20 and _pts(p) / gp >= 1.2:
                hot.append((p, t))
        except Exception:
            continue
    rng.shuffle(hot)
    for p, t in hot[:1]:
        key = f"player:{_safe(lambda: p.id, id(p))}"
        if not _recent_ok(app, key, "hot", game_date):
            continue
        ppg = _pts(p) / max(_gp(p), 1)
        story = rng.choice([
            "{name} is on another level -- {pts} points in {gp} games ({ppg}/game) for {team}.",
            "SCORCHING: {name}'s {ppg}-point pace has him in the scoring race.",
        ]).format(name=_pname(p), pts=_pts(p), gp=_gp(p),
                  ppg=f"{ppg:.2f}", team=_tname(t))
        stories.append(story)
        _mark_recent(app, key, "hot", game_date)
    return stories


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

_GENERATORS = [
    ("prospect", _prospect_watch, 0.55),
    ("coach", _coach_stories, 0.45),
    ("controversy", _controversies, 0.40),
    ("draft", _draft_stories, 0.50),
    ("team", _team_stories, 0.60),
    ("milestone", _milestone_watch, 0.35),
    ("depth", _depth_stories, 0.50),
    ("performance", _performance_stories, 0.55),
    ("league_notes", _league_notes, 0.70),
    ("offseason", _offseason_beat, 0.65),
]


def generate_daily_news(app, game_date=None) -> int:
    """Generate the day's routine news. Returns story count. Never raises.

    Wire into the day-advance path (main.py, next to media_daily_tick).
    Stories go to app.add_news() -> news feed + ticker. Feed-only: no inbox,
    no headline cap consumed.
    """
    try:
        return _generate(app, game_date)
    except Exception:
        return 0


def _generate(app, game_date) -> int:
    rng = random.Random()
    try:
        rng.seed(hash((str(game_date), "daily_news")))
    except Exception:
        pass
    game_date = game_date or _safe(lambda: app.current_date) or date.today()

    in_season = _in_season(game_date)
    lo, hi = (SEASON_MIN, SEASON_MAX) if in_season else (OFFSEASON_MIN, OFFSEASON_MAX)
    target = rng.randint(lo, hi)

    # Weighted shuffle of generators; run each until we hit the target.
    gens = list(_GENERATORS)
    rng.shuffle(gens)
    # Sort-ish by weight so high-weight generators tend to run first, but
    # keep randomness so the mix varies day to day.
    gens.sort(key=lambda g: (rng.random() < g[2], rng.random()), reverse=True)

    stories = []
    for _name, fn, _weight in gens:
        if len(stories) >= target:
            break
        try:
            got = fn(app, game_date, rng) or []
        except Exception:
            got = []
        for s in got:
            if s and len(stories) < target:
                stories.append(s)

    # Relaxed second pass: if we're still short of the minimum, allow
    # repeats outside a shorter window rather than going dry.
    global _current_window
    if len(stories) < lo:
        _current_window = RELAXED_WINDOW_DAYS
        try:
            for _name, fn, _weight in gens:
                if len(stories) < lo:
                    try:
                        got = fn(app, game_date, rng) or []
                    except Exception:
                        got = []
                    for s in got:
                        if s and len(stories) < lo and s not in stories:
                            stories.append(s)
                else:
                    break
        finally:
            _current_window = REPEAT_WINDOW_DAYS

    # Offseason: draft stories get a second look if we're still short
    if len(stories) < lo:
        try:
            for s in _draft_stories(app, game_date, rng) or []:
                if len(stories) < lo:
                    stories.append(s)
        except Exception:
            pass

    added = 0
    add = _safe(lambda: app.add_news, None)
    if add is None:
        return 0
    for s in stories:
        try:
            add(s)
            added += 1
        except Exception:
            continue
    return added
