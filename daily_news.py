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

import logging
import math
import random
from datetime import date, timedelta

_log = logging.getLogger(__name__)

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
    """Full player name. None-safe: None parts coalesce to '', never render."""
    fn = _safe(lambda: p.first_name, "") or ""
    ln = _safe(lambda: p.last_name, "") or ""
    full = f"{fn} {ln}".strip()
    return full or "Unknown Player"


def _tname(t):
    return _safe(lambda: t.team_name, "") or "Unknown Team"


# R9: post-render backstop. Individual buckets already fail closed on
# unknown names at the gate level ("Unknown Player"/"Unknown Team" checks
# per bucket), but this is the global safety net: any RENDERED story that
# still carries a placeholder name/team is suppressed here -- fail closed,
# logged, never surfaced. Checked at the single choke point in _generate
# where finalized stories are handed to app.add_news().
_UNKNOWN_ENTITY_MARKERS = ("Unknown Player", "Unknown Team")


def _story_has_unknown_entity(story):
    return (isinstance(story, str)
            and any(m in story for m in _UNKNOWN_ENTITY_MARKERS))


def _ovr(p):
    """Overall rating, defensive about where it lives.

    F-1 root cause: the real Player class has no ``p.overall`` attribute --
    overall is the ``overall_rating()`` METHOD (game_classes.py). Try the
    plain attribute first (duck-typed player-likes/mocks may carry one),
    then the method, else 0.0. Non-finite results are normalized to 0.0
    here; the _ovr_ok gate downstream still rejects out-of-range values.
    """
    v = _safe(lambda: float(p.overall), None)
    if v is None:
        v = _safe(lambda: float(p.overall_rating()), None)
    if v is None or not math.isfinite(v):
        return 0.0
    return v


def _ovr_ok(v):
    """OVR sanity gate: the display scale is 1-100. Reject non-finite
    (inf/nan), non-numeric, and out-of-range values so garbage OVR can
    never qualify a player for a story or render in one."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and 1.0 <= f <= 100.0


def _pot(p):
    """Letter potential grade (the A-F ladder), not the numeric potential.

    F-1 root cause: ``p.potential`` exists but is a NUMERIC int, while every
    consumer does ``str(_pot(p)).upper()`` and compares against letter
    grades ("A", "B", "ELITE", "HIGH") -- so a numeric read could never
    match and the draft-riser / prospect-watch buckets were dead. Read the
    scouted letter grade ``potential_grade`` first, then the hidden
    ``true_potential_grade`` (mirrors ai_extension_planning._potential_grade),
    getattr-safe for old saves; else "".
    """
    for attr in ("potential_grade", "true_potential_grade"):
        g = _safe(lambda: str(getattr(p, attr, "")), "") or ""
        g = g.strip().upper()
        if g:
            return g
    return ""


def _pos(p):
    pp = _safe(lambda: p.primary_position, None)
    if pp is None:
        return ""
    return _safe(lambda: pp.value, str(pp)) or ""


def _contract_years_left(p):
    """Years remaining on the player's deal.

    F-1 root cause: the real Contract class uses ``years_remaining``
    (game_classes.py); ``contract_years_left`` never existed on Player or
    Contract, so the holdout bucket could never fire. Duck-typed fallbacks
    kept for player-likes that carry the years directly.
    """
    c = _safe(lambda: p.contract, None)
    if c is not None:
        for attr in ("years_remaining", "contract_years_left"):
            yrs = _safe(lambda: int(getattr(c, attr, None)), None)
            if yrs is not None:
                return yrs
    return _safe(lambda: int(p.contract_years_left), 99)


def _stats(p):
    """Season stat source.

    F-1 root cause: the real Player class has no p.season_stats. The live
    season ledger is p.stats (PlayerStats) -- written by the sim's per-game
    flush (simulation.py / game_manager.py / main.py, dozens of write
    sites, with _update_goalie_stats() keeping save_percentage live) and
    read the same way by the game's own code (potential evaluator,
    validators, game_manager). Direct player attrs (p.goals, ...) are the
    fallback for duck-typed player-likes that carry stats directly, and
    for objects with no stats store at all (consumers are _safe-wrapped).
    """
    st = _safe(lambda: p.stats, None)
    if st is not None:
        return st
    return p


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


def _unavailable(p):
    """True if the player is missing games for a known non-scratch reason.

    A star with a low game count who is injured, on IR/LTIR, or serving a
    suspension is NOT a healthy scratch -- the absence is explained, not a
    coach's message. Scratch-watch (and any similar bucket) must skip them.
    Reads getattr-safe: old saves / duck-typed player-likes may lack these.
    """
    if _safe(lambda: bool(p.is_injured), False):
        return True
    if (_safe(lambda: int(p.games_remaining_injured), 0) or 0) > 0:
        return True
    ir = str(_safe(lambda: p.ir_status, "") or "").upper()
    if ir in ("IR", "LTIR"):
        return True
    if (_safe(lambda: int(p.suspension_games_remaining), 0) or 0) > 0:
        return True
    return False


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
    name = _safe(lambda: c.name, "") or ""
    if name:
        return name
    fn = _safe(lambda: c.first_name, "") or ""
    ln = _safe(lambda: c.last_name, "") or ""
    return f"{fn} {ln}".strip()


# Module-level variety window for the current pass. _generate runs a strict
# pass (REPEAT_WINDOW_DAYS) first, then a relaxed pass (RELAXED_WINDOW_DAYS)
# if it's still short of the minimum -- variety without droughts.
RELAXED_WINDOW_DAYS = 3
_current_window = REPEAT_WINDOW_DAYS


def _recent_ok(app, entity_key, story_type, game_date, window=None):
    """True if this entity hasn't had this story type within the window.

    F3 (R8g adversarial): an unreadable date delta used to fail OPEN
    (default 999 >= window -> True), so a non-date game_date re-fired the
    same one-shot story every day. An unreadable delta now fails CLOSED
    (suppress) -- for repeat-suppression this is the safe direction.
    """
    window = window if window is not None else _current_window
    try:
        recent = getattr(app, "_daily_news_recent", None)
        if not isinstance(recent, dict):
            return True
        last = recent.get((entity_key, story_type))
        if last is None:
            return True
        # Marks are (date, window) tuples; bare dates are legacy values
        # from before marks carried their window.
        last_date = last[0] if isinstance(last, tuple) else last
        delta = (game_date - last_date).days
        return delta >= window
    except Exception:
        return False


def _mark_age_days(v, today):
    d = v[0] if isinstance(v, tuple) else v
    return _safe(lambda: today - d.toordinal(), 10 ** 9)


def _mark_window_days(v):
    w = v[1] if isinstance(v, tuple) and len(v) == 2 else None
    try:
        w = int(w)
    except (TypeError, ValueError):
        w = None
    # Legacy bare-date marks fall back to the old flat 60-day cutoff.
    return w if w and w > 0 else 60


def _mark_recent(app, entity_key, story_type, game_date, window=None):
    """Record a story firing. The mark's window travels with it (B1):
    the old flat 60-day prune deleted 400-day one-shot marks early,
    allowing same-season re-fires (R8g, R8e). Prune now drops only marks
    older than their own window.
    """
    try:
        recent = getattr(app, "_daily_news_recent", None)
        if not isinstance(recent, dict):
            recent = {}
            app._daily_news_recent = recent
        w = window if window is not None else _current_window
        recent[(entity_key, story_type)] = (game_date, w)
        # Prune marks older than their own window so the dict can't grow
        # unbounded; long-window one-shot marks survive their full window.
        if len(recent) > 2000:
            today = _safe(lambda: game_date.toordinal(), None)
            if today is None:
                return
            for k in [k for k, v in recent.items()
                      if _mark_age_days(v, today) > _mark_window_days(v)]:
                del recent[k]
    except Exception:
        pass


# Scratch-gate GP-delta window (REV-B2 follow-up, FIX-BACK): cumulative GP
# alone cannot tell "currently scratched" from "recently returned" -- an 86
# OVR star back from a 20-game suspension plays every night, yet
# gp*2 < team_gp still fires "can't crack the lineup" for weeks (and
# ir_status resets on return, so _unavailable can't see the past either).
# Player.days_missed is never incremented anywhere and there is no
# per-player game log, so instead we track per-player
# (date, gp, team_gp, unavailable) snapshots on the app -- mirroring the
# _recent_ok/_mark_recent pattern -- and demand GP be essentially static
# over the trailing window while the TEAM played real games: a genuine
# scratch accrues nothing while his team plays, whereas a returned regular
# accrues ~3-4/week. Measuring the evidence window in TEAM GAMES (not
# calendar days) closes the residual hole where a star returning into a
# 1-game week read as scratched: gp_delta <= 1 over 7 days is evidence of
# nothing when the team only played ~1 game.
SCRATCH_GP_WINDOW_DAYS = 7
SCRATCH_GP_MAX_DELTA = 1
# Minimum team games inside the evidence window before any scratch verdict.
SCRATCH_MIN_TEAM_GAMES = 2


def _gp_static(app, entity_key, game_date, gp, team_gp, unavailable):
    """True only if the player dressed for ~no games while his TEAM played
    >= SCRATCH_MIN_TEAM_GAMES games in the trailing SCRATCH_GP_WINDOW_DAYS
    days -- evidence he is sitting NOW.

    Sliding snapshot: the first sighting seeds (date, gp, team_gp,
    unavailable) and returns False (no history yet, so no scratch claim can
    be made). A verdict requires BOTH a full window elapsed AND enough team
    games inside it; until the team-games floor is met the baseline is kept
    (not refreshed) and there is no verdict, so the window extends
    gracefully through light weeks. Once both gates pass, gp is compared
    against the snapshot: advancing by more than SCRATCH_GP_MAX_DELTA means
    he's dressing, so the verdict is False; either way the baseline then
    refreshes for the next window.

    Any availability transition (suspension/injury began or ended) reseeds:
    the absence tail can never be evidence again -- the window restarts at
    the transition, so every team game in it is one the player was
    available for. A backward team-game clock (trade to a team with fewer
    games played, season rollover via reset_season_record) reseeds the same
    way a backward calendar clock does. Legacy 2-tuple entries (pre-upgrade
    saves) are tolerated by reseeding -- verdicts just start ~7 days later,
    no crash.

    Callers must pass EVERY evaluated candidate through here -- including
    injured/suspended ones -- so baselines stay fresh across an absence;
    otherwise a stale pre-suspension snapshot would read as "hasn't played
    in weeks" the day he returns.
    Fail-closed (False) on unexpected errors: this is an EVIDENCE gate, and
    failing open would assert "sitting" with no evidence -- the exact bug
    class being fixed. (The inner _safe calls already fail closed, so the
    outer except is effectively dead.)
    """
    try:
        seen = getattr(app, "_daily_news_gp_seen", None)
        if not isinstance(seen, dict):
            seen = {}
            app._daily_news_gp_seen = seen
        entry = seen.get(entity_key)
        last = (entry if isinstance(entry, (tuple, list)) and len(entry) == 4
                else None)
        delta_days = (_safe(lambda: (game_date - last[0]).days, None)
                      if last is not None else None)
        if delta_days is None or delta_days < 0:
            # No usable history, legacy 2-tuple / malformed entry, or the
            # calendar clock moved backward: reseed, no verdict yet.
            seen[entity_key] = (game_date, gp, team_gp, unavailable)
            _prune_gp_seen(seen, game_date)
            return False
        team_delta = _safe(lambda: int(team_gp) - int(last[2]), None)
        if unavailable != last[3] or (team_delta is not None
                                      and team_delta < 0):
            # Availability flipped, or the team-game clock moved backward
            # (trade to a team with fewer games played / season rollover):
            # the old baseline is meaningless -- reseed, no verdict yet.
            seen[entity_key] = (game_date, gp, team_gp, unavailable)
            _prune_gp_seen(seen, game_date)
            return False
        if delta_days < SCRATCH_GP_WINDOW_DAYS:
            return False  # window not elapsed yet -- no verdict
        if team_delta is None or team_delta < SCRATCH_MIN_TEAM_GAMES:
            # Too few team games in the window for a verdict (light
            # schedule / post-return week): keep the OLD baseline (don't
            # refresh) so the window extends until real evidence
            # accumulates.
            return False
        gp_delta = _safe(lambda: int(gp) - int(last[1]), 999)
        seen[entity_key] = (game_date, gp, team_gp, unavailable)
        _prune_gp_seen(seen, game_date)
        return gp_delta is not None and gp_delta <= SCRATCH_GP_MAX_DELTA
    except Exception:
        return False


def _prune_gp_seen(seen, game_date):
    """Bound the GP-snapshot dict (same 2000-entry policy as _mark_recent)."""
    try:
        if len(seen) > 2000:
            cutoff = _safe(lambda: game_date.toordinal() - 60, 0)
            for k in [k for k, v in seen.items()
                      if _safe(lambda: v[0].toordinal(), 0) < cutoff]:
                del seen[k]
    except Exception:
        pass


def _team_record(t):
    w = _safe(lambda: int(t.wins), 0) or 0
    l = _safe(lambda: int(t.losses), 0) or 0
    # REV-B2 root cause: Team uses ot_losses (game_classes.py ~4060);
    # t.otl never existed, so _safe silently yielded 0 and every OT loss
    # was dropped from the record string and the games-played sum.
    otl = _safe(lambda: int(t.ot_losses), 0) or 0
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
        "FUTURE WATCH: {name}'s development with {team} is tracking well{extra}.",
        "{name} keeps flashing top-six upside in the {team} system.",
        "The {team} pipeline keeps producing -- {name} ({pos}, {age}) is next in line{extra}.",
        "{name} is making a strong case for an NHL look with {team}, and he's only {age}{extra}.",
        "{name}'s two-way game is ahead of schedule{extra} -- {team} may have a steal.",
        "{team} development staff are thrilled with {age}-year-old {pos} {name}{extra}.",
        "Don't be surprised if {name} forces {team}'s hand at camp next fall{extra}.",
        "RISING: {name} ({pos}) keeps impressing and knocking on {team}'s door.",
        "{name}'s compete level has {team} brass talking -- the {age}-year-old {pos} keeps getting better{extra}.",
        "PROSPECT NOTEBOOK: {name}'s development has {team} excited about the {age}-year-old {pos}.",
        "The jump {name} has made this year is exactly what {team} hoped to see{extra}.",
        "{age}-year-old {name} is separating himself in the {team} system{extra}.",
        "If {name} keeps this up, {team} will have a decision to make.",
        "PROSPECT WATCH: {name}'s edge work and pace are turning heads{extra}.",
        "{team} may have found a keeper in {pos} {name}, still just {age}{extra}.",
        "{name} is a name to remember from {team}'s prospect camp.",
        "The {team} system is deep, and {age}-year-old {name} is a big reason why{extra}.",
        "RISING STAR: {name}'s development curve has {team} fast-tracking his timeline.",
        "{name} ({pos}) plays a pro-style game well beyond his {age} years{extra}.",
        "{team} fans, circle the name {name} -- the {pos} is coming{extra}.",
        "PROSPECT WATCH: {name} is checking every box for {team} this season.",
        "The patience {team} is showing with {name} is paying off in a big way{extra}.",
        "{name}'s hockey sense sets him apart -- {team} sees a future regular{extra}.",
        "RISING: {age}-year-old {pos} {name} keeps turning heads in the {team} system.",
        "{team}'s scouts nailed the pick with {name}, who's thriving at {age}{extra}.",
        "PROSPECT WATCH: {name}'s upside has {team} dreaming big{extra}.",
        "The {team} pipeline is high on {name} -- the {age}-year-old keeps trending up.",
        "{name} has that pro frame and pro pace -- {team} likes what it sees{extra}.",
        "RISING STAR: {name} ({age}) is forcing {team} to rethink its timeline.",
        "PROSPECT NOTEBOOK: {name} has real upside -- the tools are obvious in the {team} system{extra}.",
        "{name} plays the game the right way -- {team}'s coaches love his habits{extra}.",
        "RISING STAR: The {team} system has a gem in {age}-year-old {name}.",
        "{name} ({pos}) keeps showing why {team} is high on him{extra}.",
        "PROSPECT WATCH: {name}'s trajectory points straight at the NHL{extra}.",
        "{team} keeps liking what it sees from {age}-year-old {pos} {name}{extra}.",
        "RISING: {name} keeps answering every challenge {team} throws at him.",
        "{name} is tracking toward the pro game -- {team} is impressed with the {age}-year-old{extra}.",
        "FUTURE WATCH: {name} has the tools to make the jump for {team}{extra}.",
    ]
    for p, t in candidates[:3]:
        key = f"prospect:{_safe(lambda: p.id, id(p))}"
        if not _recent_ok(app, key, "prospect_watch", game_date):
            continue
        extra = ""
        ovr = _ovr(p)
        # B3/B6: only finite, in-range OVR may render -- int(inf) would
        # OverflowError and kill the whole generator.
        if _ovr_ok(ovr) and ovr >= 70:
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
                    "The seat is getting warm: {coach}'s {team} sits at {w}-{l}-{otl} and the room is searching for answers.",
                    "HOT SEAT WATCH: {coach} needs wins -- {team} is {w}-{l}-{otl} and board confidence is down to {conf}%.",
                    "Fair or not, {coach} is taking the heat for {team}'s {w}-{l}-{otl} slide.",
                    "{team} has dropped to {w}-{l}-{otl}, and {coach}'s seat keeps getting warmer.",
                    "HOT SEAT: At {w}-{l}-{otl}, {coach} is coaching for his job in {team}.",
                    "{team}'s {w}-{l}-{otl} record is doing the talking -- and it isn't saying much for {coach}.",
                    "{w}-{l}-{otl} wasn't the plan in {team} -- and {coach} is feeling it.",
                    "HOT SEAT WATCH: {conf}% board confidence and a {w}-{l}-{otl} record -- {coach} is on thin ice in {team}.",
                    "{coach} is running out of answers as {team} sinks to {w}-{l}-{otl}.",
                    "Another loss and the {coach} questions in {team} will only get louder -- they're {w}-{l}-{otl}.",
                    "HOT SEAT: {team} is {w}-{l}-{otl} and sinking under {coach}.",
                    "{team} still sits at {w}-{l}-{otl} -- and the questions for {coach} keep coming.",
                    "The vultures are circling: {coach}'s {team} is {w}-{l}-{otl} with confidence at {conf}%.",
                    "The {team} room can't hide from {w}-{l}-{otl} -- and it all falls on {coach}.",
                    "The {team} slide continues at {w}-{l}-{otl} -- and the pressure on {coach} keeps building.",
                    "HOT SEAT: {team}'s {w}-{l}-{otl} start has {coach}'s job security at {conf}% and falling.",
                    "If {team} doesn't turn {w}-{l}-{otl} around soon, {coach} may not get the chance.",
                    "The heat is on {coach}: {team} sits {w}-{l}-{otl}, and the board's patience is wearing thin.",
                ]).format(coach=cname, team=_tname(t), w=w, l=l, otl=otl,
                          conf=int(conf))
                stories.append(story)
                _mark_recent(app, key, "hot_seat", game_date)
            # Coach of the month buzz: great record
            elif (gp >= 10 and w / max(gp, 1) > 0.70
                    and _recent_ok(app, key, "cotm", game_date)):
                story = rng.choice([
                    "{coach} is earning Coach of the Year buzz with {team} sitting at {w}-{l}-{otl}.",
                    "COACHING MASTERCLASS: {coach} has {team} rolling at {w}-{l}-{otl}.",
                    "{coach} has {team} playing sixty full minutes a night -- {w}-{l}-{otl} speaks for itself.",
                    "Give {coach} credit: {team} is {w}-{l}-{otl} and buying in completely.",
                    "COACH OF THE YEAR WATCH: {coach}'s {team} keeps winning at a {w}-{l}-{otl} clip.",
                    "{team} is {w}-{l}-{otl}, and {coach} is pushing all the right buttons.",
                    "The {coach} system is humming -- {team} sits at {w}-{l}-{otl}.",
                    "{coach} has turned {team} into a wagon at {w}-{l}-{otl}.",
                    "COACHING MASTERCLASS: {team}'s structure under {coach} has them at {w}-{l}-{otl}.",
                    "Opponents are running out of answers for {coach}'s {team} ({w}-{l}-{otl}).",
                    "{coach} deserves real Coach of the Year consideration with {team} at {w}-{l}-{otl}.",
                    "{team} plays hard for {coach} -- that's how you get to {w}-{l}-{otl}.",
                    "The buy-in is total: {coach} has {team} at {w}-{l}-{otl} and climbing.",
                    "COACH OF THE YEAR WATCH: Nobody is getting more out of a roster than {coach} ({w}-{l}-{otl}).",
                    "{team}'s {w}-{l}-{otl} record is a testament to {coach}'s preparation.",
                    "{coach} has {team} defending with structure and attacking with pace -- {w}-{l}-{otl}.",
                    "The {team} room believes, and {w}-{l}-{otl} shows why -- credit to {coach}.",
                    "COACHING MASTERCLASS: {coach} is squeezing every drop out of {team} at {w}-{l}-{otl}.",
                    "{w}-{l}-{otl} doesn't happen by accident -- {coach} has {team} dialed in.",
                    "Credit where it's due: {coach} has {team} at {w}-{l}-{otl}.",
                ]).format(coach=cname, team=_tname(t), w=w, l=l, otl=otl)
                stories.append(story)
                _mark_recent(app, key, "cotm", game_date)
        except Exception:
            continue
        if len(stories) >= 2:
            break
    return stories


def _rumor_pts_bar(p):
    """Position-aware underperformance bar (pts/gp) for the trade-rumor gate.

    R9: the old flat 0.5 bar framed shutdown defensemen as underperforming
    trade bait -- a 0.40 pts/gp shutdown D-man is playing his role, not
    slumping. League-wide, defensemen produce roughly 60% of forward point
    rates, so a 0.30 bar for D is the positional equivalent of the 0.50
    forward bar: genuinely slumping offensive D-men stay eligible, on-role
    shutdown D-men (and goalies, who get no bar at all) can no longer
    qualify. Returns None when the position can't be established -- fail
    closed: no rumor without a position to judge production against.
    """
    pos = _pos(p).upper()
    if pos in ("C", "LW", "RW"):
        return 0.50
    if pos in ("D", "LD", "RD"):
        return 0.30
    return None


def _controversies(app, game_date, rng):
    """Plausible speculation grounded in real game state."""
    stories = []
    players = _all_players(app)
    # Healthy scratches: high-OVR players with very few games played --
    # gated on REAL scratch candidacy (REV-A3 follow-up to F-1, REV-B2
    # follow-up to the REV-A3 gate). The bare "gp <= 3" gate fired for every
    # 78+ OVR player in week 1 (everyone has gp <= 3 when the season just
    # started) and for injured stars -- false premises. A scratch story now
    # requires ALL of:
    #   * the player's TEAM has played >= 10 games (season-progress floor:
    #     nobody is "scratched" two games into the season),
    #   * the player is not sidelined by injury/IR/suspension
    #     (_unavailable: a known absence is not a coach's message),
    #   * the player is a skater (backup goalies sit by roster design),
    #   * the player has dressed for fewer than HALF the team's games
    #     (a star who dressed 2 of 2 is not scratched; 2 of 12 might be),
    #   * the player's GP is essentially STATIC over the trailing ~7 days
    #     (_gp_static: evidence he is sitting NOW, not a star who just
    #     returned from suspension/IR and dresses every night).
    for p, t in players:
        try:
            ovr = _ovr(p)
            gp = _gp(p)
            # B6: garbage OVR must not qualify or render
            if not (_ovr_ok(ovr) and ovr >= 78):
                continue
            w, l, otl = _team_record(t)
            # REV-B2: games_played is exact (Team.update_record maintains
            # it); W+L+OTL+ties is the fallback for duck-typed team-likes.
            ties = _safe(lambda: int(t.ties), 0) or 0
            team_gp = (_safe(lambda: int(t.games_played), 0)
                       or (w + l + otl + ties))
            if team_gp < 10:
                continue
            if _pos(p).upper() in ("G", "GOALIE"):
                continue
            key = f"player:{_safe(lambda: p.id, id(p))}"
            # REV-B2: pass every candidate through _gp_static (even
            # unavailable ones) so baselines stay fresh across absences;
            # the verdict gates the story below. FIX-BACK: the evidence
            # window is measured in team games, so pass team_gp and the
            # availability flag (reseeds on transition) in.
            unav = _unavailable(p)
            sitting_now = _gp_static(app, key, game_date, gp, team_gp, unav)
            if unav:
                continue
            if gp * 2 >= team_gp:
                continue
            if not sitting_now:
                continue
            if not _recent_ok(app, key, "scratch", game_date):
                continue
            story = rng.choice([
                "SCRATCH WATCH: {name} ({ovr} OVR) has dressed for just {gp} {games_word}. Is {coach} sending a message in {team}?",
                "{name} can't crack the {team} lineup -- {gp} {games_word} for a {ovr} OVR talent is hard to justify.",
                "SCRATCH WATCH: {name} watched again -- {gp} {games_word} for a {ovr} OVR player is raising eyebrows in {team}.",
                "{coach} keeps going back to the same lineup card, and {name} ({ovr} OVR) keeps sitting -- {gp} {games_word} and counting.",
                "SCRATCH WATCH: {team} is healthy-scratching a {ovr} OVR talent in {name}. Something has to give.",
                "{name} has played {gp} {games_word}. For a {ovr} OVR player in {team}, that's a statement from {coach}.",
                "The {team} press box has a {ovr} OVR regular in {name} -- {coach} isn't budging.",
                "SCRATCH WATCH: {name}'s situation in {team} is one to watch -- {gp} {games_word}, {ovr} OVR, and questions piling up.",
                "Whatever the reason in {team}, {name} sitting at {gp} {games_word} tells its own story.",
                "With {ovr} OVR and {gp} {games_word}, {name} has no clear path back in {team} -- something has to give.",
                "A {ovr} OVR player should not be watching from the press box -- {name} has {gp} {games_word} in {team}.",
                "{name} is out of the lineup again -- in {team}, people notice these things.",
                "SCRATCH WATCH: {name} needs a fresh start -- {gp} {games_word} in {team} isn't it for a {ovr} OVR talent.",
                "The message from {coach} is clear, even if the reason isn't: {name} sits again for {team}.",
                "{team} paid for a {ovr} OVR contributor and is getting {gp} {games_word} from {name} -- the math doesn't work.",
                "SCRATCH WATCH: {name} keeps sitting -- {gp} {games_word} in {team} is a long stretch to go unnoticed.",
                "The {team} brass are preaching patience with {name} -- {gp} {games_word} into the season, fans aren't buying it.",
                "You don't healthy-scratch {ovr} OVR talent without a reason -- but {coach} isn't sharing his in {team}.",
                "SCRATCH WATCH: {name} keeps sitting -- that's the {team} story at {gp} {games_word}.",
                "If {name} isn't in {coach}'s plans, {team} owes it to a {ovr} OVR asset to find him a new home.",
            ]).format(name=_pname(p), ovr=int(ovr), gp=gp,
                      games_word="game" if gp == 1 else "games",
                      team=_tname(t),
                      coach=_coach_name(_head_coach(t)) or "the coach")
            stories.append(story)
            _mark_recent(app, key, "scratch", game_date)
            break
        except Exception:
            continue
    # Trade rumors: underperforming stars (high OVR, low points per game).
    # R9: the pts/gp bar is position-aware (_rumor_pts_bar) -- shutdown
    # defensemen at 0.3-0.49 pts/gp are on-role, not underperforming, so
    # they must not be framed as trade bait; goalies have no bar and are
    # excluded entirely.
    if len(stories) < 2:
        cands = []
        for p, t in players:
            try:
                ovr = _ovr(p)
                gp = _gp(p)
                bar = _rumor_pts_bar(p)
                if (bar is not None and _ovr_ok(ovr) and ovr >= 80
                        and gp >= 15 and _pts(p) / gp < bar):
                    cands.append((p, t))
            except Exception:
                continue
        rng.shuffle(cands)
        for p, t in cands[:1]:
            key = f"player:{_safe(lambda: p.id, id(p))}"
            if not _recent_ok(app, key, "rumor", game_date):
                continue
            pts = _pts(p)
            # R9: fail closed on placeholder names/teams at the bucket level
            # too (the _generate guard is the global backstop) -- a rumor
            # about "Unknown Player" must never render.
            name = _pname(p)
            team = _tname(t)
            if not name or name == "Unknown Player":
                continue
            if not team or team == "Unknown Team":
                continue
            story = rng.choice([
                "RUMOR MILL: {name} is a natural speculation target -- the {team} star has just {pts} {points_word} in {gp} games.",
                "Is {name}'s time in {team} running out? {pts} {points_word} in {gp} games isn't cutting it for an {ovr} OVR player.",
                "RUMOR MILL: {name}'s name keeps surfacing -- {pts} {points_word} in {gp} games and the speculation isn't dying down.",
                "RUMOR MILL: With {pts} {points_word} in {gp} games, {name} is the name that keeps coming up in {team} speculation.",
                "RUMOR MILL: A change of scenery could unlock {name} -- {ovr} OVR talent always draws trade speculation.",
                "{pts} {points_word} in {gp} games isn't the {name} {team} paid for -- and it's starting to show.",
                "RUMOR MILL: {team} won't say {name} is available. They won't say he isn't, either.",
                "The {name} watch is on: {pts} in {gp} for a {ovr} OVR player rarely stays quiet in {team}.",
                "RUMOR MILL: Could a contender buy low on {name}? {pts} {points_word} in {gp} games makes it a debate worth having.",
                "Is {name}'s future in {team} in doubt? {pts} {points_word} in {gp} games keeps the rumor mill fed.",
                "RUMOR MILL: {name}'s production has dipped in {team} -- and the rumor mill is only getting louder.",
                "Don't be shocked if {name} is wearing different colors by spring -- {pts} in {gp} has {team} rethinking.",
                "RUMOR MILL: Landing {name} won't come cheap -- {team} knows what a {ovr} OVR star is worth.",
                "{name} would look good in a lot of top sixes -- {team} knows it, and {pts} {points_word} in {gp} hasn't scared anyone off.",
                "RUMOR MILL: If {name} were ever available, {ovr} OVR talent wouldn't stay on the market long.",
                "The longer {name} sits at {pts} {points_word} in {gp} games, the louder the {team} rumor mill gets.",
                "RUMOR MILL: {name} is the big swing -- {ovr} OVR talent at {pts} {points_word} in {gp} games.",
                "Retool or reload? {team}'s answer may decide {name}'s future -- {pts} {points_word} in {gp} games.",
                "{team} fans are split on {name} -- but {pts} {points_word} in {gp} games is below the {ovr} OVR bar.",
                "RUMOR MILL: If {team} sells, {name} is the headline piece -- {pts} {points_word} in {gp} games.",
            ]).format(name=_pname(p), team=team, pts=pts,
                      gp=_gp(p), ovr=int(_ovr(p)),
                      points_word="point" if pts == 1 else "points")
            stories.append(story)
            _mark_recent(app, key, "rumor", game_date)
    # Holdout speculation: stars in final contract year (low years left)
    if len(stories) < 2:
        for p, t in players:
            try:
                yrs = _contract_years_left(p)
                ovr = _ovr(p)
                if _ovr_ok(ovr) and yrs is not None and yrs <= 1 and ovr >= 82:
                    key = f"player:{_safe(lambda: p.id, id(p))}"
                    if not _recent_ok(app, key, "holdout", game_date):
                        continue
                    story = rng.choice([
                        "CONTRACT WATCH: {name} is unsigned past this season. {team} risks losing an {ovr} OVR star for nothing.",
                        "{name}'s expiring deal looms over {team} -- and the {ovr} OVR star still hasn't signed.",
                        "CONTRACT WATCH: The clock is ticking on {name} in {team} -- no extension for the {ovr} OVR star.",
                        "{team} can't let {name} walk for nothing -- but the {ovr} OVR star remains unsigned.",
                        "CONTRACT WATCH: {name} holds all the cards -- {team} needs the {ovr} OVR cornerstone locked up.",
                        "Every day without a deal, {name}'s price goes up -- {team} is playing with fire.",
                        "CONTRACT WATCH: {team}'s priority list starts and ends with {name} ({ovr} OVR).",
                        "{name} is unsigned past this season -- and {team} fans are focused on the contract.",
                        "CONTRACT WATCH: Letting an {ovr} OVR player like {name} reach free agency would haunt {team}.",
                        "The {name} negotiation is the story in {team} -- until the {ovr} OVR star signs, it stays that way.",
                        "{name} is unsigned -- now {team} has to pay the {ovr} OVR market rate or risk losing him.",
                        "CONTRACT WATCH: No news is bad news on the {name} front in {team}.",
                        "If {team} won't pay {name}, someone will -- that's the fear with the {ovr} OVR star unsigned.",
                        "CONTRACT WATCH: Time is {team}'s enemy here -- leverage belongs to the {ovr} OVR star in {name}.",
                        "{team}'s window and {name}'s contract are on the same clock -- the {ovr} OVR star needs a deal.",
                        "CONTRACT WATCH: The longer this drags, the more {name} costs {team}.",
                        "July 1 gets closer every day -- {team} still has no deal with {ovr} OVR star {name}.",
                        "CONTRACT WATCH: {name} is {team}'s most important signature -- and it's still missing.",
                        "The {team} faithful are getting nervous: no extension yet for {name}, the {ovr} OVR engine.",
                        "CONTRACT WATCH: {name} to the open market is {team}'s nightmare scenario -- {ovr} OVR talent doesn't grow on trees.",
                    ]).format(name=_pname(p), team=_tname(t), ovr=int(ovr))
                    stories.append(story)
                    _mark_recent(app, key, "holdout", game_date)
                    break
            except Exception:
                continue
    return stories[:2]


def _draft_stories(app, game_date, rng):
    """Prospect-riser coverage during draft season (Jan-Jun).

    Draws from team-owned prospects (``t.prospects``), so every template is
    framed as organizational riser coverage -- never as draft-eligible
    hype, which these players are not."""
    stories = []
    try:
        if game_date.month not in (1, 2, 3, 4, 5, 6):
            return stories
    except Exception:
        return stories
    prospects = _all_prospects(app)
    # Sort by overall for a rough "rankings" feel. Key-based sort only:
    # tuples hold player objects, and tuple comparison on an OVR tie
    # would fall through to comparing players -> TypeError (B1).
    ranked = []
    for p, t in prospects:
        try:
            ovr = _ovr(p)
            if _ovr_ok(ovr):
                ranked.append((ovr, p, t))
        except Exception:
            continue
    ranked.sort(key=lambda r: r[0], reverse=True)
    if ranked and _recent_ok(app, "draft:risers", "draft", game_date):
        top = ranked[0]
        story = rng.choice([
            "PROSPECT RISERS: {name} ({team}) has impact-player upside -- one to watch this {season}.",
            "PROSPECT RISERS: {name} is an exciting name to watch for {team} heading into the {season}.",
            "{name} has star-level upside in the {team} system -- keep an eye on him this {season}.",
            "PROSPECT RISERS: {name} keeps demanding a longer look from the big club -- all the tools are there for {team}.",
            "PROSPECT RISERS: Don't be surprised if {name} pushes for NHL ice time soon -- the {team} prospect has the toolkit for it.",
            "PROSPECT RISERS: {name} ({team}) is a legitimate NHL prospect on tools alone.",
            "{name}'s ceiling is real -- a gem worth watching in {team}'s system this {season}.",
            "PROSPECT RISERS: {name} plays a pro-style game -- {team} likes how he projects for the {season}.",
            "PROSPECT RISERS: {name}'s projection keeps rising -- {team} may have something special here.",
            "PROSPECT RISERS: {name} plays with the kind of compete {team} covets in a prospect.",
            "{name}'s stock has never been higher -- {team} sees a future impact player for the {season} ahead.",
            "PROSPECT RISERS: {name} ({team}) checks a lot of boxes -- the upside is obvious this {season}.",
            "PROSPECT RISERS: {name} is on the call-up radar -- the toolkit says he's getting close.",
            "PROSPECT RISERS: {name}'s two-way detail is advanced for his age -- {team} may have a steal.",
            "The way {name} is trending for {team} is knocking-on-the-door material -- a big {season} ahead.",
            "PROSPECT RISERS: {name} is making {team}'s drafting look smart -- the upside keeps getting harder to ignore.",
            "PROSPECT RISERS: {name} is turning heads on tools alone.",
            "PROSPECT RISERS: {name} projects as a real young talent for {team} -- the ceiling is real.",
            "{name} has that coveted blend of skill and compete -- a rising {season} storyline for {team}.",
            "PROSPECT RISERS: {name} ({team}) is a name to know this {season} -- the upside speaks for itself.",
        ]).format(name=_pname(top[1]), team=_tname(top[2]),
                  season="first half" if game_date.month < 4 else "stretch run")
        # guard against placeholder-y output
        if "Unknown" not in story:
            stories.append(story)
            _mark_recent(app, "draft:risers", "draft", game_date)
    if len(ranked) >= 5 and len(stories) < 2 and _recent_ok(app, "draft:depth", "draft", game_date):
        story = rng.choice([
            "DRAFT DEPTH: This year's class looks deep -- quality options stretch well into round one.",
            "DRAFT DEPTH: It's a deep year -- the first round looks loaded with legitimate talent.",
            "DRAFT DEPTH: Teams picking late in round one could still land top-end talent -- that's how deep this class is.",
            "DRAFT DEPTH: It's a deep draft, with first-round grades reaching far down the board.",
            "DRAFT DEPTH: The first round might as well be two rounds -- this class is that deep.",
            "DRAFT DEPTH: The depth is real: first-round talent and quality well into round two.",
            "DRAFT DEPTH: It's a deep first round -- difference-makers available well past the lottery.",
            "DRAFT DEPTH: Deep and balanced -- first-round talents headline a class with contributors into the middle rounds.",
            "DRAFT DEPTH: A deep first round is prime trade-up territory.",
            "DRAFT DEPTH: A deep class, with first-round grades up and down the board.",
            "DRAFT DEPTH: The drop-off doesn't come for a while -- talent runs deep in this class.",
            "DRAFT DEPTH: Quality and quantity -- this deep class boasts first-round talent throughout the round.",
            "DRAFT DEPTH: A deep draft means talent everywhere -- this class has real quantity.",
            "DRAFT DEPTH: The second tier of this class runs deep -- quality well past the lottery.",
            "DRAFT DEPTH: A class this deep doesn't come along every year -- first-round talent everywhere.",
        ])
        stories.append(story)
        _mark_recent(app, "draft:depth", "draft", game_date)
    return stories


def _team_stories(app, game_date, rng):
    """Streaks, slumps, rivalry watch, fan morale."""
    stories = []
    teams = _all_teams(app)
    # High-win% team coverage. No recent-game data is available here, so
    # these celebrate the record -- they never claim an active streak,
    # a standings gap, or unit-level (PP/PK/goaltending/line) causes.
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
                    "What a record: {team} sits at {w}-{l}-{otl}.",
                    "{w}-{l}-{otl}. Read it twice -- that's {team}'s record.",
                    "{w} wins in {gp} games: {team} owns a {w}-{l}-{otl} record.",
                    "RECORD WATCH: The numbers are loud -- {team} is {w}-{l}-{otl}.",
                    "No asterisks, no fine print: {team}'s record reads {w}-{l}-{otl}.",
                    "Take a bow, {team}: {w}-{l}-{otl} through {gp} games.",
                    "{team} is {w}-{l}-{otl}, and that's worth savoring.",
                    "RECORD WATCH: A dream start for {team} -- {w}-{l}-{otl} through {gp}.",
                    "Do the math: {w} wins in {gp} games. {team} is {w}-{l}-{otl}.",
                    "RECORD WATCH: {w}-{l}-{otl} -- {team} is having some kind of season.",
                    "Just look at it: {team}, {w}-{l}-{otl}.",
                    "{team}'s record is {w}-{l}-{otl} -- the kind of number that needs no spin.",
                    "RECORD WATCH: {w}-{l}-{otl} for {team}. Some records need no explanation.",
                    "A {w}-{l}-{otl} ledger for {team} -- the record speaks for itself.",
                    "Bank the points: {team} is {w}-{l}-{otl}.",
                    "{team} has authored a {w}-{l}-{otl} record through {gp} games.",
                    "RECORD WATCH: {w}-{l}-{otl}. That's {team}'s record, plain and simple.",
                    "Say it out loud: {team} is {w}-{l}-{otl} through {gp} games.",
                    "Pin this one to the board: {team} is {w}-{l}-{otl}.",
                    "One more look at the ledger: {team}, {w}-{l}-{otl}.",
                ]).format(team=_tname(t), w=w, l=l, otl=otl, gp=gp)
                stories.append(story)
                _mark_recent(app, key, "streak", game_date)
            elif pct <= 0.25 and _recent_ok(app, key, "slump", game_date):
                story = rng.choice([
                    "SLUMP WATCH: {team} has managed just {w} {wins_word} in {gp} games.",
                    "The numbers are ugly: {team} is {w}-{l}-{otl} and searching for answers.",
                    "SLUMP WATCH: {w}-{l}-{otl} -- {team}'s record needs no sugarcoating.",
                    "Ouch. {team} is {w}-{l}-{otl} through {gp} games.",
                    "SLUMP WATCH: Just {w} {wins_word} in {gp} games for {team} -- the record says it all.",
                    "{team}'s {w}-{l}-{otl} mark is the kind that gives a beat writer nightmares.",
                    "SLUMP WATCH: {w}-{l}-{otl}. There's no way to dress that up for {team}.",
                    "The ledger is brutal: {team} sits at {w}-{l}-{otl}.",
                    "SLUMP WATCH: {team} is {w}-{l}-{otl} -- the losses column is doing the talking.",
                    "{w} {wins_word}. {gp} games. {team}'s record is {w}-{l}-{otl}, and it's rough.",
                    "SLUMP WATCH: Read the record and wince: {team} is {w}-{l}-{otl}.",
                    "Not much to like in {team}'s {w}-{l}-{otl} record through {gp}.",
                    "SLUMP WATCH: {team} is staring at {w}-{l}-{otl} through {gp} games.",
                    "A {w}-{l}-{otl} record for {team} -- the kind that gets circled in red ink.",
                    "SLUMP WATCH: {w} {wins_word} in {gp} games. That is {team}'s season so far.",
                    "Yikes: {team} is {w}-{l}-{otl} through {gp} games.",
                    "SLUMP WATCH: The {team} ledger reads {w}-{l}-{otl} -- and it's not pretty.",
                    "{team}'s {w}-{l}-{otl} record is a tough look through {gp} games.",
                    "SLUMP WATCH: {w}-{l}-{otl} for {team}. The record is what it is.",
                    "File this under rough: {team} is {w}-{l}-{otl} through {gp} games.",
                ]).format(team=_tname(t), w=w, l=l, otl=otl, gp=gp,
                          wins_word="win" if w == 1 else "wins")
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
                    story = rng.choice([
                        "MILESTONE WATCH: {name} ({team}) sits at {cg} career goals -- {away} away from {mark}.",
                        "The countdown is on: {name} needs {away} more for {mark} career goals -- he's at {cg} with {team}.",
                        "MILESTONE WATCH: {name} ({team}) is {away} goals shy of {mark} for his career.",
                        "{cg} down, {away} to go -- {name} is closing in on {mark} career goals with {team}.",
                        "MILESTONE WATCH: History beckons for {name} -- {away} goals from {mark}.",
                        "{name} ({team}) keeps climbing the all-time list -- {cg} goals, {away} from {mark}.",
                        "MILESTONE WATCH: The {team} faithful are counting down -- {name} needs {away} for {mark}.",
                        "Elite company awaits: {name} is {away} goals away from {mark} in his career.",
                        "MILESTONE WATCH: {name}'s next {away} goals carry history -- {mark} is within reach.",
                        "{team}'s {name} sits at {cg} -- the march to {mark} is nearly over.",
                        "MILESTONE WATCH: {name} needs {away} -- the {mark}-goal club is calling.",
                        "Chase for {mark}: {name} ({team}) is at {cg}, just {away} back.",
                        "MILESTONE WATCH: {away} to go for {name} -- {team} fans are ready to celebrate {mark}.",
                        "The building will be loud when {name} gets {away} more -- {mark} career goals is close.",
                        "MILESTONE WATCH: {name} ({team}): {cg} career goals and counting -- {mark} is {away} away.",
                    ]).format(name=_pname(p), team=_tname(t), cg=cg,
                              away=mark - cg, mark=mark)
                    stories.append(story)
                    _mark_recent(app, key, "milestone", game_date)
                    break
        except Exception:
            continue
        if len(stories) >= 2:
            break
    return stories


def _team_goalie_svps(players, t):
    """(goalie, save_percentage) for every goalie on team t carrying a sane,
    finite save percentage in [0.0, 1.0]. Powers the R9 crease-controversy
    gate in _depth_stories: the controversy premise needs the team's
    netminders ranked so the named goalie can be shown to be out-saving
    the rest. Junk numerics (inf/nan/None/out-of-range) are dropped, never
    ranked."""
    out = []
    for q, qt in players:
        try:
            if qt is not t:
                continue
            if "G" not in _pos(q).upper():
                continue
            svp = _safe(lambda: float(_stats(q).save_percentage), None)
            if svp is None or not math.isfinite(svp):
                continue
            if not 0.0 <= svp <= 1.0:
                continue
            out.append((q, svp))
        except Exception:
            continue
    return out


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
            svp = _safe(lambda: float(s.save_percentage), 0.0)
            # B4: bound the save percentage. _safe/or doesn't filter inf/nan
            # (both truthy), so reject non-finite and anything above 1.0 --
            # impossible values must never qualify or render.
            if not math.isfinite(svp if svp is not None else 0.0):
                continue
            svp = svp or 0.0
            if 3 <= gp <= 12 and 0.915 <= svp <= 1.0:
                # R9: the crease-controversy premise requires the named
                # goalie to actually be out-saving the team's other
                # netminders -- a .918 backup behind a .925 starter is not
                # a controversy. Mirror the presser's gate (media_engine
                # _maybe_spawn_narrative): sort the team's goalies by
                # save_percentage, require top - second > 0.010. The story
                # names p, so p must be the top goalie; a team with fewer
                # than two sane goalies cannot have a controversy.
                mates = _team_goalie_svps(players, t)
                if len(mates) < 2:
                    continue
                mates.sort(key=lambda gs: gs[1], reverse=True)
                if mates[0][0] is not p:
                    continue
                if mates[0][1] - mates[1][1] <= 0.010:
                    continue
                # R9: fail closed on placeholder names/teams at the bucket
                # level too (the _generate guard is the global backstop) --
                # a crease-controversy story about "Unknown Player" must
                # never render.
                name = _pname(p)
                team = _tname(t)
                if not name or name == "Unknown Player":
                    continue
                if not team or team == "Unknown Team":
                    continue
                key = f"player:{_safe(lambda: p.id, id(p))}"
                if not _recent_ok(app, key, "backup", game_date):
                    continue
                story = rng.choice([
                    "GOALIE DEBATE: {name} is {svp} through {gp} games -- is there a crease controversy brewing in {team}?",
                    "{name}'s {svp} save percentage in limited action has {team} fans asking questions.",
                    "GOALIE DEBATE: {name} keeps stopping pucks ({svp} in {gp} games) -- how long before {team} leans on him more?",
                    "{team} has a good problem in the crease: {name} is {svp} through {gp} games.",
                    "GOALIE DEBATE: The numbers don't lie -- {name}'s {svp} in {gp} games demands a longer look in {team}.",
                    "{name} is making his case between the pipes -- {svp} across {gp} appearances for {team}.",
                    "GOALIE DEBATE: {team}'s crease is getting crowded -- {name} is {svp} in {gp} games.",
                    "Small sample, big numbers: {name} sits at {svp} through {gp} games for {team}.",
                    "GOALIE DEBATE: {name} has been rock solid ({svp}) -- {team} may have a tandem on its hands.",
                    "{team} fans are taking notice of {name} -- {svp} in {gp} games is hard to ignore.",
                    "GOALIE DEBATE: Is {name} {team}'s best goalie right now? {svp} through {gp} says maybe.",
                    "{name} is stopping everything in sight -- {svp} across {gp} games for {team}.",
                    "GOALIE DEBATE: {team} didn't expect a controversy, but {name}'s {svp} is forcing the conversation.",
                    "The crease competition is heating up: {name} is {svp} in {gp} games for {team}.",
                    "GOALIE DEBATE: {name}'s calm, positional game has him at {svp} -- {team} is taking notice.",
                    "{gp} games, {svp} save percentage -- {name} is earning {team}'s trust one start at a time.",
                    "GOALIE DEBATE: Split the starts? {name}'s {svp} through {gp} makes the case in {team}.",
                    "{name} has given {team} quality minutes -- {svp} in {gp} games.",
                    "GOALIE DEBATE: {name} keeps the net small -- {svp} through {gp} for {team}.",
                    "{team}'s goaltending depth is showing -- {name} is {svp} across {gp} games.",
                ]).format(name=name, svp=f"{svp:.3f}", gp=gp,
                          team=team)
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
                # B6: garbage OVR must not qualify or render
                if _ovr_ok(ovr) and ovr < 74 and gp >= 15 and _pts(p) / gp >= 0.6:
                    key = f"player:{_safe(lambda: p.id, id(p))}"
                    if not _recent_ok(app, key, "grinder", game_date):
                        continue
                    story = rng.choice([
                        "UNDERDOG: {name} ({ovr} OVR) has {pts} points in {gp} games for {team} -- earning every shift.",
                        "Nobody outworks {name}: the {ovr} OVR grinder has {pts} points in {gp} games for {team}.",
                        "UNDERDOG: {name}'s play is making a statement -- {pts} points in {gp} games for {team}.",
                        "UNDERDOG: {name} ({ovr} OVR) has {pts} in {gp} for {team} -- production nobody saw coming.",
                        "UNDERDOG: {name} does the dirty work and the scoresheet is noticing -- {pts} points in {gp} games.",
                        "Ice time is earned, and {name} is earning his -- the {team} grinder has {pts} points in {gp} games.",
                        "UNDERDOG: {ovr} OVR, {pts} points, zero quit -- {name} is {team}'s heartbeat.",
                        "{name} does the little things right, and now he's scoring -- {pts} in {gp} for {team}.",
                        "UNDERDOG: {team} found a gem in {name} -- {pts} points in {gp} games from a {ovr} OVR depth piece.",
                        "The {team} room loves {name} -- {pts} points in {gp} games of honest hockey.",
                        "UNDERDOG: {name} is making the most of every shift -- {pts} in {gp}.",
                        "Shift after shift, {name} does the dirty work -- with {pts} points in {gp} games to show for it.",
                        "UNDERDOG: Don't look now, but {name} ({ovr} OVR) is producing -- {pts} in {gp}.",
                        "{name} is the kind of player who wins you playoff games -- {team} is seeing it now with {pts} in {gp}.",
                        "UNDERDOG: {name}'s compete never wavers -- {pts} points in {gp} games for {team}.",
                    ]).format(name=_pname(p), ovr=int(ovr), pts=_pts(p),
                              gp=gp, team=_tname(t))
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
    # Training focus: position-gated summer work. Goalies never take
    # faceoffs, kill penalties, or take one-timers, so they draw from a
    # goalie-only list; skaters draw from position-appropriate lists.
    # (Deliberately flavor, not a scouting report: the item is not tied
    # to the player's real weak attributes.)
    cands = [(p, t) for p, t in players
             if _ovr_ok(_ovr(p)) and _ovr(p) >= 70]
    rng.shuffle(cands)
    for p, t in cands[:2]:
        key = f"player:{_safe(lambda: p.id, id(p))}"
        if not _recent_ok(app, key, "offseason", game_date):
            continue
        pos = _pos(p).upper()
        # Explicit goalie check first: a blank/missing position must never
        # fall through to skater items (one-timer timing, penalty-kill
        # reads) for someone who is actually a goalie.
        if pos in ("G", "GOALIE"):
            focus_items = [
                "lateral quickness", "rebound control",
                "tracking pucks through screens",
                "post-to-post explosiveness", "glove positioning",
                "playing the puck", "crease depth management",
                "second-effort recoveries", "reading releases",
                "staying square through traffic",
            ]
        elif pos in ("D", "LD", "RD", "DEFENSE", "DEFENCE"):
            focus_items = [
                "gap control", "first-pass accuracy",
                "defensive positioning", "point shot",
                "penalty-kill reads", "skating stride",
                "stick-on-puck defending", "core strength",
                "net-front battles", "transition passing",
            ]
        elif pos in ("C", "CENTER", "LW", "RW", "F", "FORWARD", "W", "WINGER"):
            focus_items = [
                "skating stride", "shot release", "defensive positioning",
                "core strength", "first-step quickness",
                "stickhandling in traffic", "net-front presence",
                "penalty-kill reads", "one-timer timing",
                "faceoff technique" if pos in ("C", "CENTER") else "backchecking detail",
            ]
        else:
            # Blank/unknown position: stick to items true of any skater
            # AND goalie, so nobody gets position-nonsense items.
            focus_items = [
                "conditioning", "core strength", "flexibility",
                "lower-body power", "recovery and nutrition",
                "durability", "off-ice cardio", "mobility",
                "mental preparation", "leadership",
            ]
        focus = rng.choice(focus_items)
        story = rng.choice([
            "{name} ({team}) is focused on {focus} this summer.",
            "{team} expects big things from {name} after a summer dedicated to {focus}.",
            "SUMMER WORK: {name} is putting in the hours on {focus} -- {team} will reap the benefits.",
            "OFFSEASON: {name}'s summer priority is {focus}, and {team} loves the commitment.",
            "OFFSEASON: Improving {focus} is {name}'s summer mission -- {team} loves the commitment.",
            "SUMMER WORK: The {focus} gains are showing for {name} -- {team} is optimistic.",
            "{name} knows {focus} is the next step -- {team} expects a leap this fall.",
            "OFFSEASON: {name} has attacked his {focus} all summer long.",
            "The {team} staff made {focus} {name}'s summer project.",
            "SUMMER WORK: {name} is determined to sharpen his {focus} before camp.",
            "{focus} is {name}'s summer priority -- he's determined to take a step.",
            "OFFSEASON: {team} loves {name}'s dedication to improving his {focus}.",
            "SUMMER WORK: {name} has {focus} circled as the key to his next step with {team}.",
            "{team} is counting on {name} taking a step -- {focus} is where it starts.",
            "OFFSEASON: The work {name} is putting into {focus} hasn't gone unnoticed in {team}.",
            "{name} wants a bigger role -- it starts with {focus} this summer.",
            "SUMMER WORK: {team} development staff are thrilled with {name}'s commitment to {focus}.",
            "{focus}, {focus}, {focus} -- that's been {name}'s summer mantra.",
            "OFFSEASON: {name} is betting a summer of {focus} turns into a breakout fall with {team}.",
            "{team} fans should watch {name} at camp -- a summer of {focus} could unlock another level.",
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
                    story = rng.choice([
                        "DEVELOPMENT CAMP: {tname} prospect {pname} impressed coaches with his compete level.",
                        "DEVELOPMENT CAMP: {pname} stood out among {tname} prospects with his pace and detail.",
                        "DEVELOPMENT CAMP: {tname} prospect {pname} looked like a standout all week at camp.",
                        "DEVELOPMENT CAMP: {pname} opened eyes at {tname} development camp.",
                        "DEVELOPMENT CAMP: The {tname} staff loves {pname}'s habits -- a strong week at camp.",
                        "DEVELOPMENT CAMP: {pname} was a noticeable presence all week at {tname} camp.",
                        "DEVELOPMENT CAMP: {tname} prospect {pname} keeps trending the right way.",
                        "DEVELOPMENT CAMP: {pname}'s compete level set the tone at {tname} camp.",
                        "DEVELOPMENT CAMP: {tname} coaches came away impressed with {pname}'s two-way detail.",
                        "DEVELOPMENT CAMP: Keep an eye on {pname} -- {tname}'s camp standout.",
                        "DEVELOPMENT CAMP: {pname} looked like he belonged at {tname} camp.",
                        "DEVELOPMENT CAMP: {tname} prospect {pname} finished the week strong.",
                    ]).format(tname=(t and _tname(t)), pname=_pname(p))
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
                lead_pts = _pts(lead)
                # B7: gap can be 0 when the leader is tied (or alone, when
                # there is no second qualifier). Never render "0 clear of
                # second place" -- split templates on tied-vs-leading.
                gap = (lead_pts - _pts(skaters[1][0])
                       if len(skaters) > 1 else None)
                if gap is not None and gap > 0:
                    story = rng.choice([
                        "SCORING RACE: {name} ({team}) leads the league with {pts} points in {gp} games.",
                        "{name} sits atop the scoring charts at {pts} points -- {gap} clear of second place.",
                        "SCORING RACE: {name} is setting the pace -- {pts} points in {gp} games for {team}.",
                        "{name} can't be stopped -- {pts} points in {gp} games leads the league.",
                        "SCORING RACE: {gap} points separate {name} from the pack -- {pts} in {gp} for {team}.",
                        "The {team} superstar is lapping the field: {name} has {pts} points in {gp} games.",
                        "SCORING RACE: {name}'s {pts} points in {gp} games have him {gap} clear at the top.",
                        "{name} is playing chess while everyone else plays checkers -- {pts} in {gp}.",
                        "SCORING RACE: Nobody is keeping pace with {name} ({pts} points, {gp} games).",
                        "The scoring title runs through {name} -- {pts} points in {gp} games for {team}.",
                        "SCORING RACE: {name} is on another planet -- {pts} in {gp}, {gap} ahead of second.",
                        "{team} rides {name} nightly -- the league leader has {pts} points in {gp} games.",
                        "SCORING RACE: The gap is {gap} and growing -- {name} keeps piling up points.",
                        "{name} makes it look easy: {pts} points in {gp} games for {team}.",
                        "SCORING RACE: Second place is playing for pride -- {name} is {gap} points clear.",
                        "Night after night, {name} delivers -- {pts} points in {gp} games.",
                        "SCORING RACE: {name} ({team}) is threatening to run away with it at {pts} in {gp}.",
                        "The {name} show continues: {pts} points in {gp} games, best in the league.",
                        "SCORING RACE: {gap} points of daylight between {name} and the field.",
                        "{name} is the engine of {team} -- and the league's scoring leader at {pts} in {gp}.",
                    ]).format(name=_pname(lead), team=_tname(skaters[0][1]),
                              pts=lead_pts, gp=_gp(lead), gap=gap)
                elif gap == 0:
                    story = rng.choice([
                        "SCORING RACE: {name} ({team}) shares the league lead with {pts} points in {gp} games.",
                        "{name} sits in a tie atop the scoring charts at {pts} points.",
                        "SCORING RACE: Dead even at the top -- {name} has {pts} points in {gp} games for {team}.",
                        "Nobody has separated from the pack: {name} is tied for the league lead at {pts} points.",
                        "SCORING RACE: {name} and the chasing pack are deadlocked at {pts} points in {gp} games.",
                        "{name} holds a share of the scoring lead -- {pts} in {gp} for {team}.",
                        "SCORING RACE: It's a logjam at the top, and {name} ({pts} in {gp}) is right in it.",
                        "The scoring title is up for grabs -- {name} is tied at the top with {pts} points.",
                        "SCORING RACE: {name} ({team}) is knotted at the top of the charts with {pts} points.",
                        "{pts} points in {gp} games -- {name} shares the league lead.",
                        "SCORING RACE: Dead heat at the top -- {name} has {pts} in {gp} for {team}.",
                        "It's anyone's scoring title -- {name} is tied at the top with {pts} points in {gp} games.",
                    ]).format(name=_pname(lead), team=_tname(skaters[0][1]),
                              pts=lead_pts, gp=_gp(lead))
                else:
                    story = rng.choice([
                        "SCORING RACE: {name} ({team}) sets the pace with {pts} points in {gp} games.",
                        "{name} is the man to catch -- {pts} points in {gp} games for {team}.",
                        "SCORING RACE: {name} leads the way at {pts} in {gp}.",
                        "The scoring lead belongs to {name} -- {pts} points in {gp} games.",
                        "SCORING RACE: {name} ({pts} points, {gp} games) is the early pacesetter.",
                        "{name} is setting the standard -- {pts} points in {gp} games for {team}.",
                        "SCORING RACE: All eyes on {name} -- {pts} in {gp}, tops in the league.",
                        "The {team} star is out front: {name} has {pts} points in {gp} games.",
                    ]).format(name=_pname(lead), team=_tname(skaters[0][1]),
                              pts=lead_pts, gp=_gp(lead))
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
            # B2: key-based sort only -- tuples hold team objects, and a
            # win-pct tie would fall through to comparing them -> TypeError.
            ranked.sort(key=lambda r: r[0], reverse=True)
            if ranked:
                pct, t, w, l, otl = ranked[0]
                key = "league:best_team"
                if _recent_ok(app, key, "notes", game_date):
                    story = rng.choice([
                        "POWER RANKINGS: {team} holds the league's best record at {w}-{l}-{otl}.",
                        "POWER RANKINGS: Nobody has been better than {team} -- {w}-{l}-{otl} leads the league.",
                        "POWER RANKINGS: {team} sits at the top at {w}-{l}-{otl}.",
                        "POWER RANKINGS: The team to beat is {team} -- {w}-{l}-{otl}.",
                        "POWER RANKINGS: {team}'s {w}-{l}-{otl} mark is the league's gold standard.",
                        "POWER RANKINGS: The numbers say {team} is the league's best -- {w}-{l}-{otl}.",
                        "POWER RANKINGS: {team} keeps banking points -- {w}-{l}-{otl}, best in the league.",
                        "POWER RANKINGS: The view from the top belongs to {team} at {w}-{l}-{otl}.",
                        "POWER RANKINGS: {w}-{l}-{otl} -- that's {team}, the league's measuring stick.",
                        "POWER RANKINGS: {team} is setting the pace at {w}-{l}-{otl}.",
                        "POWER RANKINGS: Contenders are chasing {team} and its league-best {w}-{l}-{otl}.",
                        "POWER RANKINGS: {team} owns the league's best record at {w}-{l}-{otl}.",
                    ]).format(team=_tname(t), w=w, l=l, otl=otl)
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
            "SCORCHING: {name}'s {ppg}-point pace speaks for itself.",
            "SCORCHING: {name} can't stop scoring -- {pts} points in {gp} games for {team}.",
            "{name} is torching the league at a {ppg}-point clip -- {pts} in {gp}.",
            "SCORCHING: The puck is finding {name} -- {pts} points in {gp} games ({ppg}/game).",
            "{team}'s {name} is on fire: {pts} points in {gp} games.",
            "SCORCHING: {name}'s {ppg} points-per-game pace is elite -- {pts} in {gp}.",
            "Good luck stopping {name} -- {pts} points in {gp} games for {team}.",
            "SCORCHING: {name} is producing at {ppg} a game -- video-game numbers.",
            "{name} is in the zone -- {pts} points in {gp} games ({ppg}/game).",
            "SCORCHING: {team} leans on {name}, and he delivers -- {pts} in {gp}.",
            "Nobody wants to see {name} coming -- {pts} points in {gp} games.",
            "SCORCHING: {name} keeps the line moving -- {pts} in {gp} at {ppg} a night.",
            "{ppg} points a night. That's {name} through {gp} games for {team}.",
            "SCORCHING: {name} is driving {team}'s offense -- {pts} points in {gp} games.",
            "Pick your poison with {name} -- he's at {pts} points in {gp} games.",
            "SCORCHING: {name}'s vision is on another level -- {pts} in {gp} ({ppg}/game).",
            "{name} is filling the scoresheet -- {pts} points in {gp} games.",
            "SCORCHING: {team} goes as {name} goes -- {pts} in {gp}.",
            "The league has no answer for {name} -- {pts} points in {gp} games at {ppg} a night.",
        ]).format(name=_pname(p), pts=_pts(p), gp=_gp(p),
                  ppg=f"{ppg:.2f}", team=_tname(t))
        stories.append(story)
        _mark_recent(app, key, "hot", game_date)
    return stories


# ---------------------------------------------------------------------------
# Playoff race bucket (R8a)
#
# Covers the biggest Press Box gap: the stretch run. Three premises, all
# derived from real team records via playoff-cutoff math (never invented):
#   - PLAYOFF RACE: a playoff spot is genuinely contested (first team out
#     is alive and within PLAYOFF_RACE_BAND_PTS of the last team in).
#   - CLINCHED: a team has mathematically locked a postseason berth.
#   - ELIMINATED: a team can no longer reach the postseason.
#
# FORMAT-AWARE (REV-C adversarial finding): the engine's default playoff
# format is divisional (top 3 per division + 2 wild cards per conference;
# game_classes.py). Conference top-half math under that format produces
# FALSE stories -- e.g. a team locked 6th in its division (five division
# rivals above its ceiling, 3rd in the wild-card race) still counted as
# "top 8 by points" and got a CLINCHED story. Each format therefore gets
# its own cutoff math, read from league.playoff_format ('divisional'
# default, old-save safe -- the same default playoff_system uses).
#
# Every clinch/elimination rule below is conservative and airtight: a
# story fires only when the premise holds in EVERY possible completion
# of the season. Ties block a clinch (a tie + lost tiebreaker knocks a
# team out); elimination needs teams strictly above the ceiling.
#
# Fail-closed gates: NHL teams only; in-season only; the stretch-run
# window requires median GP >= 60, every team's season still alive
# (remaining >= 1), and a sane GP spread -- anything off and the bucket
# stays silent. Clinch/elimination stories are once-per-season per team.
# Team identity in the math is the team OBJECT, never the display name
# (duplicate names / "Unknown Team" must not cross-contaminate sets).
# ---------------------------------------------------------------------------

# Stretch-run window: median team games played before the race is real.
PLAYOFF_RACE_MIN_MEDIAN_GP = 60
# Max GP spread inside a pool before the state is distrusted.
PLAYOFF_RACE_MAX_GP_SPREAD = 10
# Points band around the final playoff spot that counts as "the race".
PLAYOFF_RACE_BAND_PTS = 4
# One-shot story types use a window longer than any season so they fire at
# most once per season per team (season_year is part of the repeat key).
PLAYOFF_RACE_SEASON_WINDOW = 400


def _pr_league(app):
    gm = _safe(lambda: app.game_manager)
    return _safe(lambda: gm.league) or _safe(lambda: app.league)


def _pr_season_len(app):
    """Games per team this season. None when unknown or unserious.

    The engine stores this on the league (game_classes.py); fall back to
    the game manager for duck-typed fixtures, else fail closed.
    """
    n = _safe(lambda: int(_pr_league(app).season_games_count), None)
    if n is None:
        gm = _safe(lambda: app.game_manager) or app
        n = _safe(lambda: int(gm.season_games_count), None)
    if not n or n < 60:
        return None
    return n


def _pr_season_year(app, game_date):
    lg = _pr_league(app)
    y = _safe(lambda: int(lg.season_year), None)
    if y:
        return y
    return _safe(lambda: int(game_date.year), 0) or 0


def _pr_conference(t):
    """Conference grouping mirroring playoff_system._conference_of."""
    conf = _safe(lambda: t.conference, "") or ""
    if conf in ("Eastern", "Western"):
        return conf
    div = _safe(lambda: t.division, "") or ""
    if div in ("Atlantic", "Metropolitan"):
        return "Eastern"
    if div in ("Central", "Pacific"):
        return "Western"
    return "Eastern"


def _pr_division(t):
    """Division grouping (Atlantic/Metropolitan/Central/Pacific)."""
    return _safe(lambda: t.division, "") or ""


def _pr_playoff_format(app):
    """'divisional' (default, old-save safe) or 'conference'.

    Mirrors playoff_system._playoff_format's default: leagues pickled
    before the format existed have no attribute.
    """
    lg = _pr_league(app)
    pf = _safe(lambda: lg.playoff_format, "divisional") or "divisional"
    return pf if pf in ("divisional", "conference") else "divisional"


def _pr_pool_records(pool, season_len):
    """(team, gp, pts, max_pts, name, wins) for every pool team.

    None on bad state (fail closed -- a pool whose records can't be read
    gets no stories, never a guessed one)."""
    rows = []
    for t in pool:
        try:
            w, l, otl = _team_record(t)
            gp = w + l + otl
            if gp < 0 or gp > season_len:
                return None
            pts = 2 * w + otl
            rows.append((t, gp, pts, pts + 2 * (season_len - gp),
                         _tname(t), w))
        except Exception:
            return None
    return rows


def _pr_window_ok(rows, season_len):
    """The stretch-run window: late season, everyone still alive, sane GP."""
    if not rows:
        return False
    gps = sorted(r[1] for r in rows)
    if gps[-1] - gps[0] > PLAYOFF_RACE_MAX_GP_SPREAD:
        return False
    median_gp = gps[len(gps) // 2]
    if median_gp < PLAYOFF_RACE_MIN_MEDIAN_GP:
        return False
    if min(season_len - gp for gp in gps) < 1:
        return False
    return True


def _pr_cutoff_math(rows, spots):
    """Classic top-`spots` cutoff math for one pool.

    Used for the 'conference' playoff format (spots = half the pool) and
    for per-division 3rd-place math under the divisional format (spots=3).
    Conservative on both ends: a competitor who can only TIE still blocks
    a clinch, and a team is only eliminated when `spots` teams already sit
    strictly above its ceiling. Team identity is the team object, never
    the display name (duplicate names must not cross-contaminate).
    """
    ranked = sorted(rows, key=lambda r: (-r[2], -r[5], r[4]))
    clinched, eliminated = set(), set()
    for t, gp, pts, max_pts, name, w in ranked:
        if sum(1 for o in ranked if o[0] is not t and o[3] >= pts) < spots:
            clinched.add(id(t))
        if sum(1 for o in ranked if o[0] is not t and o[2] > max_pts) >= spots:
            eliminated.add(id(t))
    return {
        "ranked": ranked,
        "clinched": clinched,
        "eliminated": eliminated,
        "last_in": ranked[spots - 1] if len(ranked) >= spots else None,
        "first_out": ranked[spots] if len(ranked) > spots else None,
    }


def _pr_divisional_sets(conf_rows, div_rows):
    """Airtight clinch/elimination sets under divisional qualifying.

    conf_rows: every row in the conference. div_rows: {division: [rows]}.
    Returns (div_locked, wc_locked, eliminated, div_maths):
      - div_locked: teams guaranteed a division top-3 berth (<3 division
        rivals can still reach their points -- airtight: at most 2 rivals
        can finish above-or-tied, so the team is top-3 in every
        completion regardless of tiebreaks).
      - wc_locked: teams guaranteed a wild-card berth (at most one team
        that could ever share the wild-card pool can still reach their
        points -- airtight: locked teams never enter the pool, so at most
        one pool rival finishes above-or-tied in any completion).
      - eliminated: teams with no path at all (division-dead AND
        wild-card-dead, both airtight -- see below).
      - div_maths: {division: _pr_cutoff_math(rows, 3)} for race stories.
    All sets hold id(team) (never names -- and never the team
    objects themselves, which may be unhashable); the dicts are
    session-scoped and team objects live in the league, so ids are
    stable for the dedup window's purposes.
    """
    div_maths = {}
    for div, rows in div_rows.items():
        if len(rows) >= 4:
            div_maths[div] = _pr_cutoff_math(rows, 3)
    div_locked = set()
    for m in div_maths.values():
        div_locked |= m["clinched"]
    # Division-dead: >=3 division rivals strictly above the ceiling --
    # no division path in any completion (ceilings are fixed).
    div_out = set()
    for div, rows in div_rows.items():
        for t, gp, pts, max_pts, name, w in rows:
            if sum(1 for o in rows if o[0] is not t and o[2] > max_pts) >= 3:
                div_out.add(id(t))
    # Division of each team, for the wild-card-dead count below.
    div_of = {}
    for div, rows in div_rows.items():
        for r in rows:
            div_of[id(r[0])] = div

    wc_locked, eliminated = set(), set()
    for t, gp, pts, max_pts, name, w in conf_rows:
        if id(t) in div_locked:
            continue
        pool_rivals = [o for o in conf_rows
                       if o[0] is not t and id(o[0]) not in div_locked]
        if sum(1 for o in pool_rivals if o[3] >= pts) < 2:
            wc_locked.add(id(t))
    for t, gp, pts, max_pts, name, w in conf_rows:
        if id(t) in div_locked or id(t) not in div_out:
            continue
        # Wild-card-dead, airtight: let A be the conference rivals already
        # strictly above our ceiling -- in every completion they all
        # finish above us (their points only grow; our ceiling is fixed).
        # At most 3 per division can take division berths, so the rest
        # are FORCED into the wild-card pool, still above us. If >=2 are
        # forced in, we are at best 3rd in the pool in every completion.
        # Combined with div_out (no division path), elimination holds in
        # every completion.
        per_div = {}
        for o in conf_rows:
            if o[0] is not t and o[2] > max_pts:
                d = div_of.get(id(o[0]))
                per_div[d] = per_div.get(d, 0) + 1
        forced_pool = sum(c - min(3, c) for c in per_div.values())
        if forced_pool >= 2:
            eliminated.add(id(t))
    return div_locked, wc_locked, eliminated, div_maths


# Race templates without a games-remaining clause (always safe).
_PR_RACE_TEMPLATES = [
    "It's a logjam in the {conf}: {teams} separated by almost nothing "
    "around the final playoff spot.",
    "Nobody wants to blink in the {conf}: {teams} within {band} points "
    "of the last playoff berth.",
    "The {conf} stretch run is chaos: {teams} all within {band} points "
    "of the final spot.",
    "PLAYOFF RACE: Every point matters now -- {teams} are jammed "
    "together at the {conf} cutoff.",
    "PLAYOFF RACE: The {conf} bubble is a traffic jam -- {teams}, all "
    "within {band} points of the line.",
    "The {conf} cutoff is a knife fight: {teams} within {band} points.",
    "PLAYOFF RACE: {teams} -- separated by almost nothing, with the "
    "final {conf} spot on the line.",
    "PLAYOFF RACE: The last {conf} berth runs through {teams}.",
    "It's coming down to the wire in the {conf}: {teams} within "
    "{band} points of the final spot.",
    "The {conf} playoff picture is a mess -- {teams}, all within "
    "{band} points of the line.",
]

# Race templates with a games-remaining clause -- only used when every
# named team has the same number of games left (else the shared number
# would be false for some of them). {games_str} is pre-pluralized.
_PR_RACE_TEMPLATES_GAMES = [
    "PLAYOFF RACE: {teams} are all within {band} points of the final "
    "{conf} playoff spot with {games_str} to go.",
    "PLAYOFF RACE: The final {conf} spot is up for grabs -- {teams}, "
    "with {games_str} left to settle it.",
    "PLAYOFF RACE: {teams} -- that's the {conf} bubble, with {games_str} "
    "left to sort it out.",
    "{teams}: the {conf} playoff race, with {games_str} to decide it.",
    "Down the stretch in the {conf}: {teams}, and only {games_str} "
    "to separate them.",
    "PLAYOFF RACE: {teams} are fighting for one {conf} playoff spot -- "
    "{games_str} left.",
    "Scoreboard watching season in the {conf}: {teams}, {games_str} to go.",
    "PLAYOFF RACE: {games_str} left, and the {conf} bubble reads {teams}.",
]


def _pr_race_story(label, math, rng):
    """The final spot is genuinely contested: story or None.

    `label` is the conference name (conference format / wild-card race)
    or division name (division 3rd-place race) rendered in templates.
    Team identity in the sets is id(team).
    """
    last_in = math["last_in"]
    first_out = math["first_out"]
    if last_in is None or first_out is None:
        return None
    if id(first_out[0]) in math["eliminated"]:
        return None
    if id(last_in[0]) in math["clinched"]:
        return None
    gap = last_in[2] - first_out[2]
    if gap < 0 or gap > PLAYOFF_RACE_BAND_PTS:
        return None
    # Name the teams in the band around the line (never the decided ones).
    line_pts = last_in[2]
    bubble = [r for r in math["ranked"]
              if abs(r[2] - line_pts) <= PLAYOFF_RACE_BAND_PTS
              and id(r[0]) not in math["clinched"]
              and id(r[0]) not in math["eliminated"]
              and r[4] != "Unknown Team"]
    if len(bubble) < 2:
        return None
    # At least one team on each side of the line -- otherwise it isn't
    # a race, it's a coronation. Teams sitting exactly ON the line count
    # for both sides: a tie at the cutoff is the most contested a race
    # gets (with strict <, a dead-even final spot would stay silent).
    above = [r for r in bubble if r[2] >= line_pts]
    below = [r for r in bubble if r[2] <= line_pts]
    if not above or not below:
        return None
    bubble.sort(key=lambda r: (-r[2], r[4]))
    named = bubble[:4]
    teams_str = ", ".join(f"{r[4]} ({r[2]} pts)" for r in named[:-1])
    teams_str += f" and {named[-1][4]} ({named[-1][2]} pts)"
    # r[3] is max_pts, r[2] is pts: (max_pts - pts) / 2 = games remaining.
    # A shared games number is only stated when every named team has the
    # same number left; otherwise the templates without a games clause are
    # used (stating the minimum would be false for the teams with more).
    remainings = sorted({(r[3] - r[2]) // 2 for r in named})
    templates = _PR_RACE_TEMPLATES
    fmt = dict(teams=teams_str, band=PLAYOFF_RACE_BAND_PTS, conf=label)
    if len(remainings) == 1:
        n = remainings[0]
        fmt["games_str"] = f"{n} game" if n == 1 else f"{n} games"
        templates = templates + _PR_RACE_TEMPLATES_GAMES
    return rng.choice(templates).format(**fmt)


def _pr_team_key(season_year, t, name):
    """Repeat key for one-shot team stories. The id() disambiguates teams
    that share a display name (or are both nameless); the dict is
    session-scoped and team objects live in the league, so it is stable
    for the dedup window's purposes."""
    return f"playoff:{season_year}:{name}#{id(t)}"


def _pr_clinch_pending(math, game_date, rng, season_year, app):
    """(story, key, story_type) for newly-clinched teams -- marking is left
    to the caller so keys are only marked for stories actually returned."""
    pending = []
    for t, gp, pts, max_pts, name, _w in math["ranked"]:
        if id(t) in math["eliminated"] or name == "Unknown Team":
            continue
        if id(t) not in math["clinched"]:
            continue
        key = _pr_team_key(season_year, t, name)
        if not _recent_ok(app, key, "clinch", game_date,
                          window=PLAYOFF_RACE_SEASON_WINDOW):
            continue
        w, l, otl = _team_record(t)
        story = rng.choice([
            "CLINCHED: {team} has officially punched its playoff ticket at "
            "{w}-{l}-{otl} ({pts} points).",
            "{team} is in -- a {w}-{l}-{otl} record ({pts} points) locks up "
            "a playoff berth.",
            "CLINCHED: The math says {team} can't miss now -- {w}-{l}-{otl}, "
            "{pts} points, playoffs bound.",
            "Party time: {team} has clinched a playoff spot at "
            "{w}-{l}-{otl}.",
            "CLINCHED: {team} ({w}-{l}-{otl}, {pts} points) is officially "
            "playing past April.",
            "No more scoreboard watching for {team} -- {w}-{l}-{otl} seals "
            "a playoff berth.",
            "CLINCHED: {team} locks it up at {w}-{l}-{otl} with {pts} "
            "points banked.",
            "{w}-{l}-{otl} and in: {team} has clinched its playoff spot.",
            "CLINCHED: {team} can start printing playoff tickets -- "
            "{w}-{l}-{otl} gets it done.",
            "CLINCHED: {pts} points ({w}-{l}-{otl}) -- {team} is officially "
            "a playoff team.",
            "CLINCHED: The {team} are going dancing -- {w}-{l}-{otl} "
            "clinch the berth.",
            "{team} takes care of business: {w}-{l}-{otl}, and the "
            "playoffs are official.",
            "CLINCHED: {pts} points does it -- {team} is playoff-bound at "
            "{w}-{l}-{otl}.",
            "Book the travel: {team} has clinched at {w}-{l}-{otl}.",
            "CLINCHED: {team} ({pts} points) officially joins the playoff "
            "field.",
            "The {team} celebration is real -- {w}-{l}-{otl} clinches a "
            "playoff berth.",
            "CLINCHED: {team} needed the points and got them -- "
            "{w}-{l}-{otl}, playoffs secured.",
            "{team} is officially in the tournament at {w}-{l}-{otl}.",
        ]).format(team=name, w=w, l=l, otl=otl, pts=pts)
        pending.append((story, key, "clinch"))
        if len(pending) >= 1:
            break
    return pending


def _pr_elimination_pending(math, game_date, rng, season_year, app):
    """(story, key, story_type) for newly-eliminated teams -- marking is
    left to the caller so keys are only marked for stories returned."""
    pending = []
    for t, gp, pts, max_pts, name, _w in reversed(math["ranked"]):
        if name == "Unknown Team":
            continue
        if id(t) not in math["eliminated"]:
            continue
        key = _pr_team_key(season_year, t, name)
        if not _recent_ok(app, key, "eliminated", game_date,
                          window=PLAYOFF_RACE_SEASON_WINDOW):
            continue
        w, l, otl = _team_record(t)
        story = rng.choice([
            "ELIMINATED: {team} is officially out of the playoff picture "
            "at {w}-{l}-{otl}.",
            "The math is cruel: {team} ({w}-{l}-{otl}) can't reach the "
            "playoffs anymore.",
            "ELIMINATED: The {team} season ends in April -- {w}-{l}-{otl} "
            "isn't enough.",
            "{team} is playing out the string now -- officially eliminated "
            "at {w}-{l}-{otl}.",
            "ELIMINATED: The {team} are done -- {w}-{l}-{otl} can't get "
            "there.",
            "It's over for {team}: eliminated from playoff contention at "
            "{w}-{l}-{otl}.",
            "ELIMINATED: {team} ({w}-{l}-{otl}) runs out of road -- the "
            "playoffs are out of reach.",
            "The {team} nightmare is official: eliminated at {w}-{l}-{otl}.",
            "ELIMINATED: {w}-{l}-{otl} for {team} -- the math finally says "
            "no.",
            "{team} won't see the postseason -- eliminated at {w}-{l}-{otl}.",
            "ELIMINATED: The {team} season is a {w}-{l}-{otl} what-could-"
            "have-been.",
            "Turn out the lights: {team} is eliminated at {w}-{l}-{otl}.",
            "ELIMINATED: {team} can't climb back into the race from "
            "{w}-{l}-{otl}.",
            "The {team} are officially planning for next year -- "
            "{w}-{l}-{otl}.",
            "ELIMINATED: No miracle left for {team} ({w}-{l}-{otl}).",
            "{team} joins the eliminated list at {w}-{l}-{otl}.",
            "ELIMINATED: The {team} fall short -- {w}-{l}-{otl} ends the "
            "dream.",
            "Mathematically done: {team} is out at {w}-{l}-{otl}.",
        ]).format(team=name, w=w, l=l, otl=otl)
        pending.append((story, key, "eliminated"))
        if len(pending) >= 1:
            break
    return pending


def _pr_divisional_stories(app, conf, rows, season_len, season_year,
                           game_date, rng):
    """Clinch/elimination stories, division 3rd-place races, and the
    wild-card race under divisional qualifying."""
    out = []
    div_rows = {}
    for r in rows:
        div_rows.setdefault(_pr_division(r[0]), []).append(r)
    div_locked, wc_locked, eliminated, div_maths = _pr_divisional_sets(
        rows, div_rows)
    conf_math = {
        "ranked": sorted(rows, key=lambda r: (-r[2], -r[5], r[4])),
        "clinched": div_locked | wc_locked,
        "eliminated": eliminated,
        "last_in": None,
        "first_out": None,
    }
    out.extend(_pr_clinch_pending(conf_math, game_date, rng,
                                  season_year, app))
    out.extend(_pr_elimination_pending(conf_math, game_date, rng,
                                        season_year, app))
    # Division 3rd-place races.
    for div in sorted(div_rows):
        drows = div_rows[div]
        if len(drows) < 4 or div not in div_maths:
            continue
        if not _pr_window_ok(drows, season_len):
            continue
        race = _pr_race_story(div or conf, div_maths[div], rng)
        if race is not None:
            key = f"league:playoff_race:{season_year}:{div or conf}"
            if _recent_ok(app, key, "race", game_date):
                out.append((race, key, "race"))
        if len(out) >= 2:
            break
    # Wild-card race among teams not locked into a division berth.
    wc_pool = [r for r in rows if id(r[0]) not in div_locked]
    if len(wc_pool) >= 3 and len(out) < 2:
        wc_ranked = sorted(wc_pool, key=lambda r: (-r[2], -r[5], r[4]))
        wc_math = {
            "ranked": wc_ranked,
            "clinched": set(wc_locked),
            "eliminated": set(eliminated),
            "last_in": wc_ranked[1],
            "first_out": wc_ranked[2],
        }
        race = _pr_race_story(conf, wc_math, rng)
        if race is not None:
            key = f"league:playoff_race:{season_year}:{conf}:wc"
            if _recent_ok(app, key, "race", game_date):
                out.append((race, key, "race"))
    return out


def _playoff_race_stories(app, game_date, rng):
    """Playoff race / clinch / elimination coverage for the stretch run.

    Repeat keys are marked ONLY for stories actually returned: marking a
    key for a story that gets truncated would suppress it forever (the
    one-shot window is longer than a season).
    """
    pending = []
    try:
        if not _in_season(game_date):
            return []
        season_len = _pr_season_len(app)
        if season_len is None:
            return []
        season_year = _pr_season_year(app, game_date)
        if not season_year:
            return []
        nhl = [t for t in _all_teams(app)
               if (_safe(lambda: t.league_name, "") or "")
               == "National Hockey League"]
        if len(nhl) < 4:
            return []
        fmt = _pr_playoff_format(app)
        pools = {}
        for t in nhl:
            pools.setdefault(_pr_conference(t), []).append(t)
        for conf in sorted(pools):
            pool = pools[conf]
            if len(pool) < 4:
                continue
            rows = _pr_pool_records(pool, season_len)
            if not rows or not _pr_window_ok(rows, season_len):
                continue
            if fmt == "conference":
                spots = len(pool) // 2
                if spots < 1:
                    continue
                math = _pr_cutoff_math(rows, spots)
                pending.extend(_pr_clinch_pending(math, game_date, rng,
                                                  season_year, app))
                pending.extend(_pr_elimination_pending(math, game_date, rng,
                                                       season_year, app))
                race = _pr_race_story(conf, math, rng)
                if race is not None:
                    key = f"league:playoff_race:{season_year}:{conf}"
                    if _recent_ok(app, key, "race", game_date):
                        pending.append((race, key, "race"))
            else:
                pending.extend(_pr_divisional_stories(
                    app, conf, rows, season_len, season_year, game_date, rng))
            if len(pending) >= 2:
                break
    except Exception:
        logging.getLogger(__name__).exception("playoff race bucket failed")
        return []
    chosen = pending[:2]
    for story, key, stype in chosen:
        _mark_recent(app, key, stype, game_date)
    return [s for s, _k, _t in chosen]


# ---------------------------------------------------------------------------
# Trade deadline week bucket (R8b)
#
# Covers the deadline-week Press Box gap: buyers-vs-sellers framing tied to
# the real trade-deadline window. The deadline DATE is the canonical one the
# Trade Deadline Center uses -- trade_deadline_manager.trade_deadline_date
# (last regular-season game minus 40 days per CBA 13.12(j); March 8
# fallback). The center reads it via TradeDeadlineManager.deadline_date();
# this bucket reads the same module-level function directly so the calendar
# always agrees (the center's screen module is never imported -- it drags
# tkinter into headless).
#
# Story premises, all derived from real league state (never invented):
#   - DEADLINE FRAME: the countdown (days to the deadline) plus the real
#     points leader as the buyers' headliner and the real cellar team as
#     the sellers' headliner.
#   - BUYER WATCH: a top-third-by-points club is buying; its shopping list
#     is the positional group with the biggest real roster shortfall
#     (12F/6D/2G complement), with its real cap space when readable.
#   - SELLER WATCH: a bottom-third club is selling; the chip named is a
#     real roster player on a real expiring contract (years_remaining == 0
#     via _contract_years_left), best OVR first.
#   - TRADE REPORT: a real completed deal from gm.trade_history whose
#     defensively parsed date falls in the deadline window, between two
#     clubs that exist in the live league.
#
# Fail-closed gates: the window is exactly deadline-7..deadline inclusive;
# anything outside stays silent (never renders). NHL teams only;
# in-season only; sane GP (median >= 40, spread <= 15, every team still
# has >= 1 game left). One-shot stories per season (season_year is in the
# repeat key). Team identity in the buyer/seller split is the team OBJECT,
# never the display name (duplicate names must not cross-contaminate).
# ---------------------------------------------------------------------------

# Deadline-week window: stories fire on deadline day and the 7 days before.
TRADE_DEADLINE_WEEK_DAYS = 7
# Stretch GP sanity inside the window (the deadline lands ~75% through).
TRADE_DEADLINE_MIN_MEDIAN_GP = 40
TRADE_DEADLINE_MAX_GP_SPREAD = 15
# One-shot story types use a window longer than any season so they fire at
# most once per season per team (season_year is part of the repeat key).
TRADE_DEADLINE_SEASON_WINDOW = 400
# Standard NHL complement the buyer-need math is measured against
# (same 12F/6D/2G the deadline manager's _team_needs uses).
_TD_COMPLEMENT = (("Forward", 12), ("Defense", 6), ("Goalie", 2))


def _td_league(app):
    gm = _safe(lambda: app.game_manager)
    return _safe(lambda: gm.league) or _safe(lambda: app.league)


def _td_deadline(app):
    """This season's real trade deadline as a date, or None (fail closed).

    Canonical source: trade_deadline_manager.trade_deadline_date -- the
    same function the Trade Deadline Center's manager reads. Imported
    lazily so a broken manager module degrades to silence, never to a
    crashed news cycle.
    """
    try:
        from trade_deadline_manager import trade_deadline_date
    except Exception:
        return None
    try:
        dd = trade_deadline_date(_td_league(app))
    except Exception:
        return None
    # trade_deadline_date promises a date. datetime is a date subclass,
    # but date-vs-datetime arithmetic raises downstream, so only a true
    # date is accepted -- anything else fails closed here.
    return dd if type(dd) is date else None


def _td_gate(app, game_date, rows, season_len):
    """(deadline_date, days_left) when the deadline-week window is live.

    (None, None) otherwise -- fail closed on every bad input: outside
    Oct-Apr, no derivable deadline, outside deadline-7..deadline, ragged
    GP, or no games left.
    """
    if not _in_season(game_date):
        return None, None
    deadline = _td_deadline(app)
    if deadline is None:
        return None, None
    try:
        days_left = (deadline - game_date).days
    except Exception:
        return None, None
    if days_left < 0 or days_left > TRADE_DEADLINE_WEEK_DAYS:
        return None, None
    if not rows:
        return None, None
    gps = sorted(r[1] for r in rows)
    if gps[-1] - gps[0] > TRADE_DEADLINE_MAX_GP_SPREAD:
        return None, None
    if gps[len(gps) // 2] < TRADE_DEADLINE_MIN_MEDIAN_GP:
        return None, None
    if min(season_len - gp for gp in gps) < 1:
        return None, None
    return deadline, days_left


def _td_buyers_sellers(rows):
    """Top third by points = buyers; bottom third = sellers (worst-first).

    Mirrors trade_deadline_manager._buyer_seller_split's rule. Team
    identity is the object; duplicate display names can't cross the line.
    """
    ranked = sorted(rows, key=lambda r: (-r[2], -r[5], r[4]))
    n = max(2, len(ranked) // 3)
    return ranked[:n], list(reversed(ranked[-n:]))


def _td_pos_group(p):
    """'Forward' | 'Defense' | 'Goalie' | None from the real position."""
    pos = str(_pos(p) or "").upper()
    if pos in ("C", "LW", "RW"):
        return "Forward"
    if pos in ("LD", "RD", "D"):
        return "Defense"
    if pos == "G":
        return "Goalie"
    return None


def _td_roster_counts(team):
    """Real F/D/G body counts. None when the roster can't be read."""
    counts = {"Forward": 0, "Defense": 0, "Goalie": 0}
    try:
        roster = list(team.roster)
    except Exception:
        return None
    for p in roster:
        g = _td_pos_group(p)
        if g is not None:
            counts[g] += 1
    return counts


def _td_primary_need(team):
    """Biggest positional shortfall vs the 12F/6D/2G complement.

    'Depth' when the complement is full; None when the roster can't be
    read (fail closed -- no need story without a real roster).
    """
    counts = _td_roster_counts(team)
    if counts is None:
        return None
    needs = {k: max(0, want - counts[k]) for k, want in _TD_COMPLEMENT}
    if not any(needs.values()):
        return "Depth"
    # Tie-break: scarcest real-world commodity first (same order the
    # deadline manager's _team_primary_need uses).
    best = max(needs.values())
    for key, _want in _TD_COMPLEMENT:
        if needs[key] == best:
            return key
    return "Depth"


def _td_rental_chips(team):
    """Real expiring-contract players (years_remaining == 0), best OVR first.

    Each chip: (player, name, group, ovr_int). Nameless players
    ("Unknown Player") and insane OVRs never qualify -- the seller story
    stays silent instead of rendering one.
    """
    chips = []
    for p in _safe(lambda: list(team.roster), []) or []:
        try:
            if _contract_years_left(p) != 0:
                continue
            name = _pname(p)
            if not name or name == "Unknown Player":
                continue
            ovr = _ovr(p)
            if not _ovr_ok(ovr):
                continue
            group = _td_pos_group(p)
            if group is None:
                continue
            chips.append((p, name, group, int(ovr)))
        except Exception:
            continue
    chips.sort(key=lambda c: -c[3])
    return chips


def _td_parse_trade_date(value):
    """Parse a CompletedTrade.date (free-form) to a date, or None.

    Never raises. tzinfo is stripped so naive and aware values always
    compare cleanly.
    """
    try:
        from datetime import datetime as _dt
        if isinstance(value, _dt):
            return value.replace(tzinfo=None).date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return _dt.strptime(text, fmt).date()
            except Exception:
                continue
        try:
            return _dt.fromisoformat(text).replace(tzinfo=None).date()
        except Exception:
            return None
    except Exception:
        return None


def _td_recent_trades(app, game_date, deadline):
    """Real completed trades in the deadline window, newest first.

    Source: gm.trade_history (trade_engine.CompletedTrade records). Each
    item: {'date', 'a', 'b', 'summary', 'a_gave', 'b_gave'}. Only trades
    where BOTH teams exist in the live league AND differ from each other;
    BLOCKED preflight records (no assets moved) are not deals and never
    render; the trade date must not be after the current game day.
    Stray names never leak in. Deterministic. Never raises.
    """
    items = []
    league = _td_league(app)
    real = {_tname(t) for t in _safe(lambda: list(league.teams), []) or []}
    real.discard("Unknown Team")
    gm = _safe(lambda: app.game_manager) or app
    try:
        history = list(getattr(gm, "trade_history", None) or [])
    except Exception:
        history = []
    lo = deadline - timedelta(days=TRADE_DEADLINE_WEEK_DAYS)
    for tr in history:
        try:
            a = str(getattr(tr, "team_a", "") or "").strip()
            b = str(getattr(tr, "team_b", "") or "").strip()
            if not a or not b or a == b or a not in real or b not in real:
                continue
            summary = str(getattr(tr, "summary", "") or "").strip()
            if summary.startswith("BLOCKED:"):
                continue
            d = _td_parse_trade_date(getattr(tr, "date", None))
            if d is None or d < lo or d > deadline:
                continue
            try:
                if d > game_date:
                    continue
            except Exception:
                continue
            items.append({
                "date": d, "a": a, "b": b, "summary": summary,
                "a_gave": [str(x) for x in
                           (getattr(tr, "a_gave", None) or [])],
                "b_gave": [str(x) for x in
                           (getattr(tr, "b_gave", None) or [])],
            })
        except Exception:
            continue
    items.sort(key=lambda i: (i["date"], i["a"], i["b"]), reverse=True)
    return items


def _td_team_key(season_year, t, name, kind):
    """Repeat key for one-shot team stories. id() disambiguates teams that
    share a display name (or are both nameless); the dict is
    session-scoped and team objects live in the league, so it is stable
    for the dedup window's purposes."""
    return f"deadline:{season_year}:{kind}:{name}#{id(t)}"


_TD_FRAME_TEMPLATES = [
    "DEADLINE WEEK: The trade deadline {when} -- {lead} ({lrec}, {lpts} "
    "points) headline the buyers' market while {cellar} ({crec}, {cpts} "
    "points) top the sellers' board.",
    "The trade deadline {when}. Buyers are circling: {lead} leads the "
    "league at {lrec} ({lpts} points). Sellers are listening: {cellar} "
    "sits last at {crec} ({cpts} points).",
    "DEADLINE WEEK: {days} to the deadline ({ddate}). {lead} ({lrec}, "
    "{lpts} points) are the team to beat in the buyers' market; {cellar} "
    "({crec}, {cpts} points) headline the sellers.",
    "The clock is ticking -- the trade deadline {when}. {lead} ({lrec}, "
    "{lpts} points) set the pace for buyers; {cellar} ({crec}, {cpts} "
    "points) lead the sellers' list.",
]


def _td_frame_pending(buyers, sellers, days_left, deadline,
                      season_year, app, game_date, rng):
    """(story, key, story_type) for the deadline-week frame -- one shot per
    season. Marking is left to the caller so the key is only marked for a
    story actually returned."""
    if not buyers or not sellers:
        return []
    lead, cellar = buyers[0], sellers[0]
    if lead[4] == "Unknown Team" or cellar[4] == "Unknown Team":
        return []
    key = f"deadline:{season_year}:frame"
    if not _recent_ok(app, key, "frame", game_date,
                      window=TRADE_DEADLINE_SEASON_WINDOW):
        return []
    lw, ll, lotl = _team_record(lead[0])
    cw, cl, cotl = _team_record(cellar[0])
    dstr = deadline.strftime("%b %d")
    if days_left == 0:
        when = f"is TODAY ({dstr})"
    elif days_left == 1:
        when = f"is tomorrow ({dstr})"
    else:
        when = f"is {days_left} days away ({dstr})"
    story = rng.choice(_TD_FRAME_TEMPLATES).format(
        when=when, lead=lead[4], cellar=cellar[4],
        lrec=f"{lw}-{ll}-{lotl}", crec=f"{cw}-{cl}-{cotl}",
        lpts=lead[2], cpts=cellar[2],
        days=("Deadline day" if days_left == 0
              else "1 day" if days_left == 1
              else f"{days_left} days"),
        ddate=dstr)
    return [(story, key, "frame")]


_TD_BUYER_TEMPLATES = [
    "BUYER WATCH: {team} ({rec}, {pts} points) are deadline buyers -- "
    "shopping for {need}{cap}.",
    "{team} ({rec}) is buying at the deadline: {need} tops the shopping "
    "list{cap}.",
    "BUYER WATCH: At {pts} points ({rec}), {team} is all-in -- the ask "
    "around the league is {need}{cap}.",
    "Deadline buyers: {team} ({rec}, {pts} points) want {need}{cap}.",
]

_TD_NEED_LABEL = {
    "Forward": "forward help",
    "Defense": "blue-line help",
    "Goalie": "goaltending depth",
    "Depth": "depth pieces",
}


def _td_buyer_pending(buyers, season_year, app, game_date, rng):
    """(story, key, story_type) for buyer clubs -- one per team per season.
    Marking is left to the caller."""
    pending = []
    for t, gp, pts, max_pts, name, w in buyers:
        if name == "Unknown Team":
            continue
        need = _td_primary_need(t)
        if need is None:
            continue
        key = _td_team_key(season_year, t, name, "buyer")
        if not _recent_ok(app, key, "buyer", game_date,
                          window=TRADE_DEADLINE_SEASON_WINDOW):
            continue
        rw, rl, rotl = _team_record(t)
        cap = _safe(lambda: int(t.cap_space), None)
        cap_str = (f" with ${cap / 1_000_000:.1f}M in cap space"
                   if isinstance(cap, int) and cap > 0 else "")
        story = rng.choice(_TD_BUYER_TEMPLATES).format(
            team=name, rec=f"{rw}-{rl}-{rotl}", pts=pts,
            need=_TD_NEED_LABEL[need], cap=cap_str)
        pending.append((story, key, "buyer"))
        if len(pending) >= 1:
            break
    return pending


_TD_SELLER_TEMPLATES = [
    "SELLER WATCH: {team} ({rec}) are listening on offers -- {chip} "
    "({pos}, {ovr} OVR) is playing on an expiring contract.",
    "{team} ({rec}) headline the sellers' market: {chip} ({pos}, "
    "{ovr} OVR) is the rental chip drawing calls.",
    "SELLER WATCH: {team} is selling at {rec} -- {chip} ({pos}, {ovr} "
    "OVR) is on an expiring deal and could move.",
    "Rental market: {chip} ({pos}, {ovr} OVR) of the {rec} {team} is the "
    "name rival GMs keep asking about.",
]

_TD_POS_LABEL = {"Forward": "forward", "Defense": "defenseman",
                 "Goalie": "goaltender"}


def _td_seller_pending(sellers, season_year, app, game_date, rng):
    """(story, key, story_type) for seller clubs -- one per team per season.
    A seller with no real expiring-contract chip stays silent (fail
    closed). Marking is left to the caller."""
    pending = []
    for t, gp, pts, max_pts, name, w in sellers:
        if name == "Unknown Team":
            continue
        chips = _td_rental_chips(t)
        if not chips:
            continue
        key = _td_team_key(season_year, t, name, "seller")
        if not _recent_ok(app, key, "seller", game_date,
                          window=TRADE_DEADLINE_SEASON_WINDOW):
            continue
        _p, chip_name, group, ovr = chips[0]
        rw, rl, rotl = _team_record(t)
        story = rng.choice(_TD_SELLER_TEMPLATES).format(
            team=name, rec=f"{rw}-{rl}-{rotl}", chip=chip_name,
            pos=_TD_POS_LABEL[group], ovr=ovr)
        pending.append((story, key, "seller"))
        if len(pending) >= 1:
            break
    return pending


_TD_TRADE_TEMPLATES = [
    "DEADLINE DEAL: {a} and {b} struck a deal -- {detail}",
    "Done deal at the deadline: {a} and {b} completed a trade -- {detail}",
    "DEADLINE DEAL: It's official -- {a} and {b} made a trade: {detail}",
]


def _td_trade_pending(trades, season_year, app, game_date, rng):
    """(story, key, story_type) for real completed deadline deals.

    One story per trade (the key carries the date + both clubs). A trade
    with no usable detail (no summary, no asset lists) stays silent.
    Marking is left to the caller."""
    pending = []
    for tr in trades[:3]:
        if tr["summary"]:
            detail = tr["summary"]
        else:
            bits = []
            if tr["a_gave"]:
                bits.append(f"{tr['a']} gets {', '.join(tr['a_gave'])}")
            if tr["b_gave"]:
                bits.append(f"{tr['b']} gets {', '.join(tr['b_gave'])}")
            if not bits:
                continue
            detail = "; ".join(bits)
        key = (f"deadline:{season_year}:trade:"
               f"{tr['date'].isoformat()}:{tr['a']}#{tr['b']}")
        if not _recent_ok(app, key, "trade", game_date,
                          window=TRADE_DEADLINE_SEASON_WINDOW):
            continue
        story = rng.choice(_TD_TRADE_TEMPLATES).format(
            a=tr["a"], b=tr["b"], detail=detail)
        pending.append((story, key, "trade"))
        if len(pending) >= 1:
            break
    return pending


def _trade_deadline_stories(app, game_date, rng):
    """Trade-deadline week coverage: buyers-vs-sellers framing + real deals.

    Repeat keys are marked ONLY for stories actually returned: marking a
    key for a story that gets truncated would suppress it forever (the
    one-shot window is longer than a season).
    """
    pending = []
    try:
        if not _in_season(game_date):
            return []
        season_len = _pr_season_len(app)
        if season_len is None:
            return []
        season_year = _pr_season_year(app, game_date)
        if not season_year:
            return []
        league = _td_league(app)
        nhl = [t for t in _safe(lambda: list(league.teams), []) or []
               if (_safe(lambda: t.league_name, "") or "")
               == "National Hockey League"]
        if len(nhl) < 4:
            return []
        rows = _pr_pool_records(nhl, season_len)
        deadline, days_left = _td_gate(app, game_date, rows, season_len)
        if deadline is None:
            return []
        buyers, sellers = _td_buyers_sellers(rows)
        # Newsworthiness order: the frame anchors the week, then real
        # completed deals, then buyer/seller watches.
        pending.extend(_td_frame_pending(buyers, sellers, days_left,
                                         deadline, season_year, app,
                                         game_date, rng))
        pending.extend(_td_trade_pending(_td_recent_trades(app, game_date,
                                                         deadline),
                                         season_year, app, game_date, rng))
        pending.extend(_td_buyer_pending(buyers, season_year, app,
                                         game_date, rng))
        pending.extend(_td_seller_pending(sellers, season_year, app,
                                           game_date, rng))
    except Exception:
        logging.getLogger(__name__).exception("trade deadline bucket failed")
        return []
    chosen = pending[:2]
    for story, key, stype in chosen:
        _mark_recent(app, key, stype, game_date)
    return [s for s, _k, _t in chosen]


# ---------------------------------------------------------------------------
# Award races bucket (R8c)
#
# Covers the Press Box gap for Hart / Art Ross / Vezina / Norris / Calder
# via awards_race.py (the same race functions the awards UI reads -- no
# re-derived math, the bucket is a presentation layer over real
# computations on real player stats).
#
# Story premises, all derived from real league state (never invented):
#   - HART RACE: the hart_race leader -- name, points, goals, real team
#     (authoritative roster_map, never the stale team_name label), and
#     the real points gap to the runner-up when one exists.
#   - ART ROSS RACE: the scoring-title leader and the real points margin.
#   - NORRIS RACE: the defenseman leader (points + plus/minus). A forward
#     outscoring every defenseman is correctly NOT named.
#   - VEZINA RACE: the goalie leader (real SV% / GAA / wins).
#   - CALDER RACE: the eligible-rookie leader (calder_eligible's real
#     age + prior-games rules decide eligibility; skaters and goalies
#     each render in their own stat frame).
#
# Fail-closed gates: in-season only; the race window is the second half
# of the regular season (median team GP >= 50% of season length, GP
# spread sane, every team still has >= 1 game left) -- award races are
# not meaningful in October and must never fire in the offseason or
# after the schedule ends. One-shot stories per season per leader
# (season_year is in the repeat key, and the leader's identity is part
# of it, so a changed leader later in the season gets his own story).
# Player identity is the object (id() disambiguates duplicate display
# names; per the R8a adversarial finding, id() reuse can only suppress
# a story, never fabricate one).
# ---------------------------------------------------------------------------

# Award races are only meaningful once teams are well into the season.
AWARD_RACE_MIN_GP_FRACTION = 0.5
# One-shot story types use a window longer than any season so each race
# leader fires at most once per season.
AWARD_RACE_SEASON_WINDOW = 400


def _ar_stat(p, *names):
    """Season-stat read mirroring awards_race._stat: p.stats.* first,
    then the flat attribute (QA fakes / old saves hand-set flat attrs).
    Zero/None reads as 0 -- a premise built on missing stats is a
    premise that must not render."""
    stats = _safe(lambda: p.stats)
    for n in names:
        if stats is not None:
            v = _safe(lambda: getattr(stats, n))
            if v:
                return v
        v = _safe(lambda: getattr(p, n))
        if v:
            return v
    return 0


def _ar_team_of(player, roster_map):
    """Authoritative team name for a player: roster membership first,
    the (possibly stale) team_name label second. Never invents one.

    Roster membership is authoritative: when the player's id IS in the
    map, its value stands even when empty (a nameless team must fail
    closed, not fall back to a possibly stale label). The label is only
    a fallback for players absent from the map entirely."""
    try:
        pid = int(getattr(player, "id", -1) or -1)
    except Exception:
        pid = -1
    if roster_map is not None and pid in roster_map:
        return roster_map[pid] or ""
    return _safe(lambda: player.team_name, "") or ""


def _ar_window_ok(rows, season_len):
    """The award-race window: second half of the regular season, sane GP
    spread, and nobody's schedule finished yet."""
    if not rows:
        return False
    gps = sorted(r[1] for r in rows)
    if gps[-1] - gps[0] > PLAYOFF_RACE_MAX_GP_SPREAD:
        return False
    median_gp = gps[len(gps) // 2]
    if median_gp < AWARD_RACE_MIN_GP_FRACTION * season_len:
        return False
    if min(season_len - gp for gp in gps) < 1:
        return False
    return True


def _ar_lead(race):
    """(player, name, gp) for a race leader, or None on degenerate state."""
    if not race:
        return None
    p = race[0].get("player")
    if p is None:
        return None
    name = _pname(p)
    if not name or name == "Unknown Player":
        return None
    gp = _ar_stat(p, "games_played")
    if not isinstance(gp, (int, float)) or gp <= 0:
        return None
    return p, name, int(gp)


def _ar_key(season_year, kind, name, player):
    """One-shot repeat key per season per race per leader. id()
    disambiguates players that share a display name."""
    return f"awards:{season_year}:{kind}:{name}#{id(player)}"


def _ar_trail(race):
    """(runner_name, points_gap) for the runner-up, or (None, None)."""
    if len(race) < 2:
        return None, None
    runner = race[1].get("player")
    rname = _pname(runner) if runner is not None else ""
    if not rname or rname == "Unknown Player":
        return None, None
    try:
        gap = int(race[0].get("points") or 0) - int(race[1].get("points") or 0)
    except Exception:
        logging.getLogger(__name__).exception("award race trail gap failed")
        return None, None
    return rname, gap


_HART_TEMPLATES = [
    "HART RACE: {name} ({team}) is setting the MVP pace -- {pts} points "
    "({g} goals) in {gp} games{trail}.",
    "{name} leads the Hart race: {pts} points in {gp} games for {team}"
    "{trail}.",
    "HART RACE: The MVP frontrunner is {name} -- {pts} points ({g} "
    "goals), pacing {team}{trail}.",
]


def _ar_hart_pending(race, roster_map, season_year, app, game_date, rng):
    """(story, key, stype, tightness) for the Hart leader. Marking is left
    to the caller so the key is only marked for a story actually
    returned. tightness = points gap to the runner-up (smaller = more
    newsworthy); None when there is no runner-up."""
    lead = _ar_lead(race)
    if lead is None:
        return None
    p, name, gp = lead
    row = race[0]
    pts = row.get("points") or 0
    goals = row.get("goals") or 0
    if pts <= 0:
        return None
    team = _ar_team_of(p, roster_map)
    if not team or team == "Unknown Team":
        return None
    key = _ar_key(season_year, "hart", name, p)
    if not _recent_ok(app, key, "award", game_date,
                      window=AWARD_RACE_SEASON_WINDOW):
        return None
    rname, gap = _ar_trail(race)
    trail = (f", {gap} clear of {rname}" if rname and gap and gap > 0
             else (f" with {rname} in pursuit" if rname else ""))
    story = rng.choice(_HART_TEMPLATES).format(
        name=name, team=team, pts=pts, g=goals, gp=gp, trail=trail)
    tightness = gap if isinstance(gap, int) and gap >= 0 else 10 ** 6
    return story, key, "award", tightness


_ART_ROSS_TEMPLATES = [
    "ART ROSS RACE: {name} ({team}) leads the scoring-title chase at "
    "{pts} points in {gp} games{trail}.",
    "{name} paces the Art Ross race -- {pts} points ({g} goals, {a} "
    "assists) for {team}{trail}.",
    "ART ROSS RACE: Nobody has more points than {name} ({team}): {pts} "
    "in {gp} games{trail}.",
]


def _ar_art_ross_pending(race, roster_map, season_year, app, game_date,
                         rng):
    lead = _ar_lead(race)
    if lead is None:
        return None
    p, name, gp = lead
    row = race[0]
    pts = row.get("points") or 0
    if pts <= 0:
        return None
    team = _ar_team_of(p, roster_map)
    if not team or team == "Unknown Team":
        return None
    key = _ar_key(season_year, "art_ross", name, p)
    if not _recent_ok(app, key, "award", game_date,
                      window=AWARD_RACE_SEASON_WINDOW):
        return None
    rname, gap = _ar_trail(race)
    trail = (f", {gap} clear of {rname}" if rname and gap and gap > 0
             else (f" with {rname} in pursuit" if rname else ""))
    # Template 3 ("Nobody has more points than X") asserts strict points
    # maximality over the WHOLE field, but art_ross_race sorts by score
    # = points + 3-star bonus -- a star-boosted player can lead the race
    # while a third player (not the runner-up) holds the points lead.
    # That template is only eligible when the leader strictly outscores
    # EVERY other candidate on points (vacuously true with no
    # runner-up); the other two assert race leadership, which holds by
    # construction.
    lead_pts = race[0].get("points") or 0
    strict_points_lead = all(lead_pts > (r.get("points") or 0)
                             for r in race[1:])
    templates = (_ART_ROSS_TEMPLATES if strict_points_lead
                 else _ART_ROSS_TEMPLATES[:2])
    story = rng.choice(templates).format(
        name=name, team=team, pts=pts, g=row.get("goals") or 0,
        a=row.get("assists") or 0, gp=gp, trail=trail)
    tightness = gap if isinstance(gap, int) and gap >= 0 else 10 ** 6
    return story, key, "award", tightness


_NORRIS_TEMPLATES = [
    "NORRIS RACE: {name} ({team}) is the defenseman to beat -- {pts} "
    "points and a {pm} rating in {gp} games{trail}.",
    "{name} leads the Norris race: {pts} points from the blue line for "
    "{team}{trail}.",
    "NORRIS RACE: The best defenseman in hockey right now is {name} "
    "({team}) -- {pts} points, {pm}{trail}.",
]


def _ar_norris_pending(race, roster_map, season_year, app, game_date, rng):
    lead = _ar_lead(race)
    if lead is None:
        return None
    p, name, gp = lead
    row = race[0]
    pts = row.get("points") or 0
    if pts <= 0:
        return None
    team = _ar_team_of(p, roster_map)
    if not team or team == "Unknown Team":
        return None
    key = _ar_key(season_year, "norris", name, p)
    if not _recent_ok(app, key, "award", game_date,
                      window=AWARD_RACE_SEASON_WINDOW):
        return None
    rname, gap = _ar_trail(race)
    trail = (f", {gap} clear of {rname}" if rname and gap and gap > 0
             else (f" with {rname} in pursuit" if rname else ""))
    try:
        pm = f"{int(row.get('plus_minus') or 0):+d}"
    except Exception:
        pm = "+0"
    story = rng.choice(_NORRIS_TEMPLATES).format(
        name=name, team=team, pts=pts, pm=pm, gp=gp, trail=trail)
    tightness = gap if isinstance(gap, int) and gap >= 0 else 10 ** 6
    return story, key, "award", tightness


_VEZINA_TEMPLATES = [
    "VEZINA RACE: {name} ({team}) is the goalie to beat -- a {sv} save "
    "percentage, {gaa} GAA and {w} wins{trail}.",
    "{name} leads the Vezina race: {sv} SV%, {gaa} GAA for {team}{trail}.",
    "VEZINA RACE: Between the pipes, nobody has been better than {name} "
    "({team}) -- {sv}, {gaa} GAA, {w} wins{trail}.",
]


def _ar_vezina_pending(race, roster_map, season_year, app, game_date, rng):
    lead = _ar_lead(race)
    if lead is None:
        return None
    p, name, gp = lead
    row = race[0]
    sv = row.get("sv_pct") or 0.0
    gaa = row.get("gaa")
    wins = row.get("wins") or 0
    # A .000 SV% or negative GAA is degenerate stat state, not a race.
    if not (0.5 < sv < 1.0) or gaa is None or gaa < 0:
        return None
    team = _ar_team_of(p, roster_map)
    if not team or team == "Unknown Team":
        return None
    key = _ar_key(season_year, "vezina", name, p)
    if not _recent_ok(app, key, "award", game_date,
                      window=AWARD_RACE_SEASON_WINDOW):
        return None
    runner = race[1].get("player") if len(race) > 1 else None
    rname = _pname(runner) if runner is not None else ""
    if not rname or rname == "Unknown Player":
        rname = None
    trail = f" with {rname} in pursuit" if rname else ""
    story = rng.choice(_VEZINA_TEMPLATES).format(
        name=name, team=team, sv=f"{sv:.3f}", gaa=f"{gaa:.2f}", w=wins,
        gp=gp, trail=trail)
    if len(race) < 2:
        tightness = 10 ** 6
    else:
        try:
            gap = abs(float(sv) - float(race[1].get("sv_pct") or sv))
        except Exception:
            gap = 0.0
        # Same tightness units as the skater races (points): a .010 SV%
        # gap is roughly as newsworthy as a 1-point gap.
        tightness = gap * 100.0
    return story, key, "award", tightness


_CALDER_TEMPLATES = [
    "CALDER RACE: Rookie {name} ({team}) leads the freshman class -- "
    "{statline} in {gp} games{trail}.",
    "{name} ({team}) is the rookie to beat: {statline} in {gp} games"
    "{trail}.",
    "CALDER RACE: The top rookie so far is {name} -- {statline} for "
    "{team}{trail}.",
]


def _ar_calder_pending(race, roster_map, season_year, app, game_date, rng):
    lead = _ar_lead(race)
    if lead is None:
        return None
    p, name, gp = lead
    row = race[0]
    is_goalie = bool(row.get("goalie"))
    if is_goalie:
        sv = row.get("sv_pct") or 0.0
        if not (0.5 < sv < 1.0):
            return None
        statline = (f"a {sv:.3f} save percentage and "
                    f"{row.get('wins') or 0} wins")
        tightness = 10 ** 6
    else:
        pts = row.get("points")
        if pts is None or pts <= 0:
            return None
        statline = f"{pts} points ({row.get('goals') or 0} goals)"
        _rname, gap = _ar_trail(race)
        tightness = gap if isinstance(gap, int) and gap >= 0 else 10 ** 6
    team = _ar_team_of(p, roster_map)
    if not team or team == "Unknown Team":
        return None
    key = _ar_key(season_year, "calder", name, p)
    if not _recent_ok(app, key, "award", game_date,
                      window=AWARD_RACE_SEASON_WINDOW):
        return None
    rname, gap = _ar_trail(race)
    trail = (f", {gap} clear of {rname}" if rname and gap and gap > 0
             else (f" with {rname} in pursuit" if rname else ""))
    story = rng.choice(_CALDER_TEMPLATES).format(
        name=name, team=team, statline=statline, gp=gp, trail=trail)
    return story, key, "award", tightness


def _award_race_stories(app, game_date, rng):
    """Award-race coverage for the second half of the season.

    Repeat keys are marked ONLY for stories actually returned: marking a
    key for a story that gets truncated would suppress it forever (the
    one-shot window is longer than a season).
    """
    pending = []
    try:
        if not _in_season(game_date):
            return []
        season_len = _pr_season_len(app)
        if season_len is None:
            return []
        season_year = _pr_season_year(app, game_date)
        if not season_year:
            return []
        nhl = [t for t in _all_teams(app)
               if (_safe(lambda: t.league_name, "") or "")
               == "National Hockey League"]
        if len(nhl) < 4:
            return []
        rows = _pr_pool_records(nhl, season_len)
        if not rows or not _ar_window_ok(rows, season_len):
            return []
        try:
            import awards_race as _ar
        except Exception:
            logging.getLogger(__name__).exception(
                "award race bucket: awards_race import failed")
            return []
        nhl_ids = {id(t) for t in nhl}
        players = [p for p, t in _all_players(app) if id(t) in nhl_ids]
        if not players:
            return []
        roster_map = _ar.roster_team_map(nhl)
        team_pct = {r[4]: (r[2] / (2 * r[1]) if r[1] > 0 else 0.0)
                    for r in rows}
        skaters = [p for p in players
                   if _td_pos_group(p) in ("Forward", "Defense")]
        goalies = [p for p in players if _td_pos_group(p) == "Goalie"]
        cseason = _ar.calder_season_year(game_date)
        races = [
            (_ar_hart_pending,
             _ar.hart_race(players, team_pct, roster_map=roster_map)),
            (_ar_art_ross_pending, _ar.art_ross_race(skaters)),
            (_ar_norris_pending, _ar.norris_race(players)),
            (_ar_vezina_pending, _ar.vezina_race(goalies)),
            (_ar_calder_pending,
             _ar.calder_race(players, season_year=cseason)),
        ]
        for builder, race in races:
            try:
                item = builder(race, roster_map, season_year, app,
                               game_date, rng)
            except Exception:
                logging.getLogger(__name__).exception(
                    "award race builder failed")
                continue
            if item is not None:
                pending.append(item)
    except Exception:
        logging.getLogger(__name__).exception("award race bucket failed")
        return []
    # Newsworthiness order: the tightest race leads; the window is long
    # enough that every race still gets its one shot per season.
    pending.sort(key=lambda item: item[3])
    chosen = pending[:2]
    for story, key, stype, _tight in chosen:
        _mark_recent(app, key, stype, game_date)
    return [s for s, _k, _t, _x in chosen]


# ---------------------------------------------------------------------------
# Game heroics bucket (R8d)
#
# Covers the Press Box gap for single-game heroics -- hat tricks,
# shutouts, 4/5-point nights, OT winners -- as a presentation layer over
# the league's persisted per-game recap feed (league.game_results /
# league._results_by_date: the same result dicts the box score, the
# three-star logger and the career-moments system read). Nothing is
# re-derived from season totals: every premise comes from one finished
# game's result dict -- its per-player game_stats lines, its scores,
# its overtime/shootout flags, its notable Goal events.
#
# Where the per-game state comes from (verified against the sim core,
# reviewer B): GameSim writes per-player g/a/saves lines into
# game_stats on full-detail leagues (the user's league runs full, so
# user-team AND CPU-vs-CPU NHL games all carry lines); the quick-sim
# flattening in _process_single_game_result covers the detailed
# non-GameSim path. 'Quick'-detail leagues record no per-game lines in
# batch results -- the bucket stays silent there (fail silent, never
# synthesize). Notable 'Goal'-with-period events are the same feed
# stars._ot_scorer_id reads for the three-star OT bonus; current
# production paths don't emit them, so the OT-winner kind fails silent
# unless a sim path records them -- again per spec.
#
# Story premises, all derived from real finished-game state:
#   - HAT TRICK: a skater's game_stats line has g >= 3.
#   - FIVE/FOR POINT: a skater's line has g + a >= 5 / >= 4 (a 5-point
#     night that includes 3+ goals names the hat trick inside).
#   - SHUTOUT: the team's opponent scored 0 AND the starter (the first
#     goalie on the roster -- the same attribution rule the engine uses
#     when it bumps stats.shutouts) has a game_stats line with
#     saves >= 1. The line's own goals_against is NOT trusted (the
#     quick-sim flattening hardcodes it to 0); the score is the witness.
#   - OT WINNER: the result went to overtime (not a shootout), the
#     final margin is exactly 1, and the last 'Goal' notable event with
#     period > 3 names a real player on the winning team. Shootout
#     winners never fire (a shootout is not an OT winner). Fails silent
#     when no sim path records such events (see above).
#
# Fail-closed gates: the in-season gate tests the GAME day (Oct-Apr;
# preseason exhibitions are September, never read -- even when the news
# runs on Oct 1); NHL results only; every result must be a
# well-formed dict with real team objects and non-negative integer
# scores; hero subjects must be real player objects with real names and
# real teams -- "Unknown Player"/"Unknown Team" never render; one story
# per (game, player) (the biggest feat wins); at most 3 stories per day.
# One-shot keys carry the game day, so a second heroic night later in
# the season gets its own story but a re-generated news day never
# repeats one; keys are marked ONLY for stories actually returned.
# Player identity is the object (id() disambiguates duplicate display
# names; per the R8a adversarial finding, id() reuse can only suppress
# a story, never fabricate one).
# ---------------------------------------------------------------------------

# One-shot window longer than any season -- each (game day, player,
# feat) fires at most once.
HEROICS_WINDOW_DAYS = 400
# At most this many heroics stories per news day.
HEROICS_MAX_PER_DAY = 3
# Newsworthiness per feat (mirrors narrative_incidents' weights).
_HEROICS_WEIGHTS = {
    "five_point": 16,
    "hat_trick": 15,
    "shutout": 12,
    "ot_winner": 11,
    "four_point": 10,
}


def _hero_int(v):
    """Strict int or None. Strings, floats and bools never coerce: a
    premise built on junk numerics must not render (reviewer C
    killshot: g="3", saves="25", g=3.9 all fired)."""
    if isinstance(v, bool):
        return None
    return v if isinstance(v, int) else None


def _hero_line_num(line, *names):
    """First integer value under any of the names in a game_stats line;
    0 on missing/junk (a premise built on missing stats must not
    render)."""
    for n in names:
        try:
            v = (line or {}).get(n)
        except Exception:
            v = None
        iv = _hero_int(v)
        if iv is not None:
            return iv
    return 0


def _hero_results(app, game_date):
    """The finished games of the day just simmed. Daily news runs after
    the date increment (simulate_day / mainline advance), so the games
    belong to game_date - 1 day. Returns a list of result dicts, [] on
    any degenerate state."""
    try:
        league = getattr(app, "league", None)
        idx = getattr(league, "_results_by_date", None)
        if not isinstance(idx, dict):
            return []
        day = _safe(lambda: game_date - timedelta(days=1))
        if day is None:
            return []
        results = idx.get(day)
        return results if isinstance(results, list) else []
    except Exception:
        return []


def _hero_teams_ok(home, away):
    """Both real NHL team objects with real names."""
    for t in (home, away):
        if t is None:
            return False
        if not (_safe(lambda: t.team_name, "") or ""):
            return False
        if ((_safe(lambda: t.league_name, "") or "")
                != "National Hockey League"):
            return False
    return True


def _hero_team_of(p, home, away):
    """Authoritative team for a player: roster membership (object
    identity) ONLY. A per-game line always names a rostered player in
    production; a player on neither roster is corrupt state, and the
    team_name label fallback would let a phantom object fire (reviewer
    C killshot). Never invents a team: "" fails every gate downstream.
    """
    try:
        pidn = id(p)
        for t in (home, away):
            for rp in getattr(t, "roster", None) or []:
                if id(rp) == pidn:
                    return _safe(lambda: t.team_name, "") or ""
    except Exception:
        pass
    return ""


def _hero_starter_goalie(team):
    """The starter by the engine's own attribution rule: the first
    goalie on the roster -- the same rule _process_single_game_result
    uses when crediting stats.shutouts. None when no goalie is on the
    roster."""
    try:
        for p in getattr(team, "roster", None) or []:
            if _td_pos_group(p) == "Goalie":
                return p
    except Exception:
        pass
    return None


def _hero_ot_scorer(result):
    """(event, player) for the OT winner: the last 'Goal' notable event
    with period > 3. Shootout goals are separate 'Shootout Goal'
    events and never match. None on degenerate state."""
    try:
        evs = result.get("notable_events") or []
        last = None
        for e in evs:
            if not isinstance(e, dict):
                continue
            if e.get("event") != "Goal":
                continue
            per = _hero_int(e.get("period"))
            if per is None or per <= 3:
                continue
            if e.get("player") is None:
                continue
            last = e
        return last
    except Exception:
        return None


_HAT_TRICK_TEMPLATES = [
    "HAT TRICK: {name} ({team}) lit the lamp {g} times as {team} beat "
    "{opp} {score}.",
    "HAT TRICK: {name} put on a show -- {g} goals -- in {team}'s "
    "{score} win over {opp}.",
    "HAT TRICK: {opp} had no answer for {name}, whose {g}-goal night "
    "powered {team} to a {score} victory.",
]

_HAT_TRICK_LOSS_TEMPLATES = [
    "HAT TRICK: {name}'s {g}-goal night wasn't enough as {team} fell "
    "{score} to {opp}.",
    "HAT TRICK: {name} scored {g} for {team}, but {opp} still took it "
    "{score}.",
]

_FIVE_POINT_TEMPLATES = [
    "FIVE-POINT NIGHT: {name} ({team}) torched {opp} for {pts} points "
    "({g} goals, {a} assists){hat} in a {score} win.",
    "FIVE-POINT NIGHT: {name} was unstoppable -- {pts} points{hat} -- "
    "as {team} beat {opp} {score}.",
    "FIVE-POINT NIGHT: {name}'s {pts}-point{hat} explosion carried "
    "{team} past {opp} {score}.",
]

_FIVE_POINT_LOSS_TEMPLATES = [
    "FIVE-POINT NIGHT: {name} put up {pts} points{hat} for {team}, but "
    "{opp} won {score} anyway.",
]

_FOUR_POINT_TEMPLATES = [
    "BIG NIGHT: {name} ({team}) piled up {pts} points ({g} goals, {a} "
    "assists) in {team}'s {score} win over {opp}.",
    "BIG NIGHT: {name} factored in on {pts} points as {team} beat "
    "{opp} {score}.",
    "BIG NIGHT: {pts} points for {name} ({team}) in a {score} win over "
    "{opp}.",
]

_FOUR_POINT_LOSS_TEMPLATES = [
    "BIG NIGHT: {name}'s {pts}-point effort for {team} came in a "
    "{score} loss to {opp}.",
]

_SHUTOUT_TEMPLATES = [
    "SHUTOUT: {name} ({team}) turned aside all {saves} shots as {team} "
    "blanked {opp} {score}.",
    "SHUTOUT: {name} was perfect -- {saves} saves, zero goals against "
    "-- in {team}'s {score} shutout of {opp}.",
    "SHUTOUT: {opp} couldn't solve {name} ({saves} saves) as {team} "
    "won {score}.",
]

_OT_WINNER_TEMPLATES = [
    "OT HERO: {name} ({team}) ended it in overtime -- {score} over "
    "{opp}.",
    "OT HERO: {name} played overtime hero, lifting {team} to a "
    "{score} OT win over {opp}.",
    "OVERTIME WINNER: {name} ({team}) beat {opp} {score} with the "
    "extra-frame decider.",
]


def _heroics_stories(app, game_date, rng):
    """Game-heroics coverage for the day just simmed.

    Repeat keys are marked ONLY for stories actually returned: marking
    a key for a story that gets truncated would suppress it forever
    (the one-shot window is longer than a season).
    """
    try:
        game_day = _safe(lambda: game_date - timedelta(days=1))
        if game_day is None:
            return []
        # The in-season gate tests the GAME day, not the news day: the
        # results belong to game_day, so a Sept 30 preseason game stays
        # unread even when the news runs on Oct 1 (reviewer B F4).
        if not _in_season(game_day):
            return []
        season_year = _pr_season_year(app, game_date)
        if not season_year:
            return []
        results = _hero_results(app, game_date)
        if not results:
            return []
        day_iso = _safe(lambda: game_day.isoformat(), "") or ""
        if not day_iso:
            return []
        candidates = []
        for res in results:
            if not isinstance(res, dict):
                continue
            home = res.get("home_team")
            away = res.get("away_team")
            if not _hero_teams_ok(home, away):
                continue
            hn = home.team_name
            an = away.team_name
            hs = _hero_int(res.get("home_score"))
            aws = _hero_int(res.get("away_score"))
            if hs is None or aws is None or hs < 0 or aws < 0:
                continue
            winner = res.get("winner")
            wname = _safe(lambda: winner.team_name, "") or ""
            if wname not in (hn, an):
                # A finished game has a winner; anything else is
                # uninterpretable state, not a story.
                continue
            overtime = bool(res.get("overtime"))
            shootout = bool(res.get("shootout"))
            gstats = res.get("game_stats")
            if not isinstance(gstats, dict):
                gstats = {}
            # One story per (game, player): the biggest feat wins.
            best = {}
            for _pid, line in gstats.items():
                if not isinstance(line, dict):
                    continue
                p = line.get("player")
                name = _pname(p)
                if not name or name == "Unknown Player":
                    continue
                if _td_pos_group(p) not in ("Forward", "Defense"):
                    continue
                team = _hero_team_of(p, home, away)
                if not team or team == "Unknown Team":
                    continue
                if team not in (hn, an):
                    continue
                g = _hero_line_num(line, "g", "goals")
                a = _hero_line_num(line, "a", "assists")
                if g < 0 or a < 0:
                    continue
                pts = g + a
                # Cross-check the line against the team score: one player
                # cannot earn two points on the same goal, so g and pts
                # can never exceed his team's goals. A line that does is
                # corrupt state (reviewer C killshot: a "3-goal" night in
                # a 2-0 game disproves itself) -- fail silent.
                team_goals = hs if team == hn else aws
                if g > team_goals or pts > team_goals:
                    continue
                # A 5-point night outranks a bare hat trick (the five-point
                # templates name the hat trick inside when one is part
                # of it).
                if pts >= 5:
                    kind = "five_point"
                elif g >= 3:
                    kind = "hat_trick"
                elif pts >= 4:
                    kind = "four_point"
                else:
                    continue
                weight = _HEROICS_WEIGHTS[kind]
                cur = best.get(id(p))
                if cur is not None and cur[1] >= weight:
                    continue
                best[id(p)] = (kind, weight, p, name, team, g, a, pts)
            # Shutout: opponent held scoreless, the team scored too (a
            # 0-0 final is degenerate state, not a shutout), and the
            # starter faced rubber.
            for t, own_score, opp_score, opp in ((home, hs, aws, an),
                                                (away, aws, hs, hn)):
                try:
                    if opp_score != 0 or own_score < 1:
                        continue
                    tname = t.team_name
                    if wname != tname:
                        continue
                    sg = _hero_starter_goalie(t)
                    if sg is None:
                        continue
                    line = None
                    for _pid, _ln in gstats.items():
                        if (isinstance(_ln, dict)
                                and _ln.get("player") is not None
                                and id(_ln.get("player")) == id(sg)):
                            line = _ln
                            break
                    if line is None:
                        continue
                    saves = _hero_line_num(line, "saves")
                    if saves < 1:
                        continue
                    sname = _pname(sg)
                    if not sname or sname == "Unknown Player":
                        continue
                    cur = best.get(id(sg))
                    if cur is not None and cur[1] >= _HEROICS_WEIGHTS[
                            "shutout"]:
                        continue
                    best[id(sg)] = ("shutout", _HEROICS_WEIGHTS["shutout"],
                                    sg, sname, tname, 0, 0, saves)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "heroics shutout check failed")
                    continue
            # OT winner: overtime (never shootout), one-goal final, the
            # last OT Goal event names a real player on the winner.
            if overtime and not shootout and abs(hs - aws) == 1:
                try:
                    ev = _hero_ot_scorer(res)
                    if ev is not None:
                        p = ev.get("player")
                        name = _pname(p)
                        team = _hero_team_of(p, home, away)
                        if (name and name != "Unknown Player" and team
                                and team != "Unknown Team"
                                and team == wname):
                            cur = best.get(id(p))
                            if cur is None or cur[1] < _HEROICS_WEIGHTS[
                                    "ot_winner"]:
                                best[id(p)] = (
                                    "ot_winner",
                                    _HEROICS_WEIGHTS["ot_winner"],
                                    p, name, team, 0, 0, 0)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "heroics OT check failed")
            # Render the per-game winners.
            for _pidn, (kind, weight, p, name, team, g, a, pts) in \
                    best.items():
                try:
                    if team == hn:
                        mine, theirs, opp = hs, aws, an
                    else:
                        mine, theirs, opp = aws, hs, hn
                    score = f"{mine}-{theirs}"
                    won = (team == wname)
                    if kind == "hat_trick":
                        tpls = (_HAT_TRICK_TEMPLATES if won
                                else _HAT_TRICK_LOSS_TEMPLATES)
                        story = rng.choice(tpls).format(
                            name=name, team=team, g=g, opp=opp,
                            score=score)
                    elif kind == "five_point":
                        hat = (" -- including a hat trick"
                               if g >= 3 else "")
                        tpls = (_FIVE_POINT_TEMPLATES if won
                                else _FIVE_POINT_LOSS_TEMPLATES)
                        story = rng.choice(tpls).format(
                            name=name, team=team, pts=pts, g=g, a=a,
                            hat=hat, opp=opp, score=score)
                    elif kind == "four_point":
                        tpls = (_FOUR_POINT_TEMPLATES if won
                                else _FOUR_POINT_LOSS_TEMPLATES)
                        story = rng.choice(tpls).format(
                            name=name, team=team, pts=pts, g=g, a=a,
                            opp=opp, score=score)
                    elif kind == "shutout":
                        story = rng.choice(_SHUTOUT_TEMPLATES).format(
                            name=name, team=team, saves=pts, opp=opp,
                            score=score)
                    elif kind == "ot_winner":
                        story = rng.choice(_OT_WINNER_TEMPLATES).format(
                            name=name, team=team, opp=opp, score=score)
                    else:
                        continue
                    key = (f"heroics:{season_year}:{kind}:{day_iso}:"
                           f"{name}#{id(p)}")
                    if not _recent_ok(app, key, "heroics", game_date,
                                      window=HEROICS_WINDOW_DAYS):
                        continue
                    candidates.append((weight, story, key))
                except Exception:
                    logging.getLogger(__name__).exception(
                        "heroics render failed")
                    continue
    except Exception:
        logging.getLogger(__name__).exception("heroics bucket failed")
        return []
    # Newsworthiness order; the window is long enough that every feat
    # still gets its one shot on a later heroics day.
    candidates.sort(key=lambda c: c[0], reverse=True)
    chosen = candidates[:HEROICS_MAX_PER_DAY]
    for _w, story, key in chosen:
        _mark_recent(app, key, "heroics", game_date)
    return [s for _w, s, _k in chosen]


# ---------------------------------------------------------------------------
# R8e -- Losing-streaks bucket
# ---------------------------------------------------------------------------
# The presser tracks a win-streak-5+ question; the Press Box had no losing
# side. This bucket is the mirror: active losing streaks derived from real
# game results.
#
# Grounding: GameManager._record_game_result appends one entry per game to
# team.recent_results -- 'W', 'L', or 'OTL', chronological with the newest
# game last, front-trimmed at 30 entries. The losing streak is the count of
# trailing non-win entries. 'L' and 'OTL' both extend it: an OT loss is a
# loss (update_record snaps win_streak on ANY loss and bumps ot_losses, and
# NHL standings print OTLs inside the L-column streak). The first 'W' -- or
# any unrecognized/missing entry -- snaps it. Sim paths that never call
# _record_game_result leave no trail, so the bucket stays silent there
# (fail-silent, spec-compliant).
#
# Cross-season guard: reset_season_record never clears recent_results, so a
# trailing April skid can leak into October. The streak is therefore capped
# at this season's games played -- a skid can never be longer than the
# games on the ledger (and never longer than the 30-entry trail trim) --
# and must be backed by at least that many losses+OTLs on the record
# (corrupt-state cross-check, cf. heroics' g <= team goals).
#
# Templates name only what the engine knows: the team, the streak length,
# and the true W-L-OTL record. They never claim causes (goaltending,
# coaching, schedule), never name a start date (the trail carries no
# dates), never assert day-over-day trends (the bucket reads one day's
# snapshot -- no "keeps getting worse"/"continues"), and never do
# playoff math.
# One story per (season, team, streak length): streak growth re-fires with
# the new number; repeat keys are marked ONLY for stories actually
# returned (the one-shot window outlasts a season).

# Mirror of the presser's win-streak-5+ threshold.
STREAKS_MIN = 5
# Escalation band: 8+ straight losses is a freefall, not a slump.
STREAKS_FREEFALL = 8
# At most this many losing-streak stories per news day.
STREAKS_MAX_PER_DAY = 2
# One-shot window longer than any season -- each (season, team, streak
# length) fires at most once.
STREAKS_WINDOW_DAYS = 400

_LOSING_TEMPLATES = [
    "SLUMP WATCH: {team} has lost {n} straight, and the {w}-{l}-{otl} ledger says it all.",
    "{n} straight losses for {team} -- the record reads {w}-{l}-{otl}.",
    "SLUMP WATCH: The losses are piling up -- {n} in a row for {team} ({w}-{l}-{otl}).",
    "{team} can't buy a win: {n} straight defeats, {w}-{l}-{otl} on the season.",
    "SLUMP WATCH: {n} in a row for {team}. The standings don't lie: {w}-{l}-{otl}.",
    "The skid hits {n}: {team} has dropped {n} straight ({w}-{l}-{otl}).",
    "SLUMP WATCH: {team} is {w}-{l}-{otl} after {n} consecutive losses.",
    "{n} straight defeats for {team} -- the record sits at {w}-{l}-{otl}.",
    "Another loss for {team}: {n} in a row, now {w}-{l}-{otl}.",
    "SLUMP WATCH: {n} straight losses have {team} at {w}-{l}-{otl}.",
]

_FREEFALL_TEMPLATES = [
    "FREEFALL: {team} has dropped {n} straight, now {w}-{l}-{otl}.",
    "FREEFALL: {n} consecutive losses for {team} -- the record is {w}-{l}-{otl}.",
    "{n} in a row. {team} is in freefall at {w}-{l}-{otl}.",
    "FREEFALL: The {team} skid is now {n} games ({w}-{l}-{otl}).",
    "FREEFALL: {n} straight losses for {team} ({w}-{l}-{otl}).",
    "FREEFALL: {team} hasn't won in {n} games -- the record is {w}-{l}-{otl}.",
    "The {team} freefall has reached {n} games ({w}-{l}-{otl}).",
    "FREEFALL: {n} losses on the bounce for {team} ({w}-{l}-{otl}).",
]


def _streak_current_losing(team):
    """Current losing streak from team.recent_results.

    Counts trailing 'L'/'OTL' entries; the first 'W' or any
    unrecognized/missing entry snaps it. Returns 0 when the feed is
    missing, empty, or unreadable.
    """
    try:
        trail = getattr(team, "recent_results", None)
        if not isinstance(trail, list) or not trail:
            return 0
        n = 0
        for entry in reversed(trail):
            code = str(entry).strip().upper()
            if code in ("L", "OTL"):
                n += 1
            else:
                break
        return n
    except Exception:
        return 0


def _streak_band(n):
    """Template band for a streak length: 'freefall' at 8+, else 'skid'."""
    return "freefall" if n >= STREAKS_FREEFALL else "skid"


def _streaks_stories(app, game_date, rng):
    """Losing-streak coverage for teams on a real skid.

    Repeat keys are marked ONLY for stories actually returned: marking
    a key for a story that gets truncated would suppress it forever
    (the one-shot window is longer than a season).
    """
    try:
        if not _in_season(game_date):
            return []
        season_year = _pr_season_year(app, game_date)
        if not season_year:
            return []
        candidates = []
        for t in _all_teams(app):
            try:
                n = _streak_current_losing(t)
                if n < STREAKS_MIN:
                    continue
                name = _tname(t)
                if not name or name == "Unknown Team":
                    continue
                w, l, otl = _team_record(t)
                gp = w + l + otl
                # Cross-season guard: the trail can hold last season's
                # games (reset_season_record never clears it), so the
                # streak can never exceed this season's games played.
                n = min(n, gp)
                if n < STREAKS_MIN:
                    continue
                # Corrupt-state cross-check: the ledger must hold the skid.
                if (l + otl) < n:
                    continue
                tpls = (_FREEFALL_TEMPLATES
                        if _streak_band(n) == "freefall"
                        else _LOSING_TEMPLATES)
                story = rng.choice(tpls).format(
                    team=name, n=n, w=w, l=l, otl=otl, gp=gp)
                # id(t) disambiguates duplicate team names (R8a lesson);
                # the name+length shape keeps keys stable day to day.
                key = f"losing_streak:{season_year}:{name}#{id(t)}:{n}"
                if not _recent_ok(app, key, "losing_streak", game_date,
                                  window=STREAKS_WINDOW_DAYS):
                    continue
                candidates.append((n, l + otl, name, story, key))
            except Exception:
                logging.getLogger(__name__).exception(
                    "losing-streaks team check failed")
                continue
    except Exception:
        logging.getLogger(__name__).exception("losing-streaks bucket failed")
        return []
    # Newsworthiness: longest skid first, worse ledger breaks ties; then
    # dedupe duplicate team names (same text would render twice) and cap.
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2]))
    deduped = []
    seen = set()
    for cand in candidates:
        if cand[2] in seen:
            continue
        seen.add(cand[2])
        deduped.append(cand)
    chosen = deduped[:STREAKS_MAX_PER_DAY]
    for _n, _lt, _nm, _story, key in chosen:
        _mark_recent(app, key, "losing_streak", game_date, STREAKS_WINDOW_DAYS)
    return [s for _n, _lt, _nm, s, _k in chosen]


# ---------------------------------------------------------------------------
# R8f -- Rivalry hype bucket
# ---------------------------------------------------------------------------
# Pregame buildup for scheduled matchups that the narrative systems have
# already marked as feuds. This is the league-wide daily-news surface --
# different from the user-game-only _rivalry_pregame headline (which fires
# at heat>=50 for the user's own games); user games may appear here too,
# but no text is shared with that headline.
#
# Grounding: narrative_ledger.matchup_narrative(home, away, league, ledger)
# reads the rivalry store (league.rivalries heat), the ledger's grudge
# memory + playoff-series history, and each club's iconic-games list. It
# never raises. Heat semantics: >=35 appends the "Heated rivalry" tag,
# >=65 inserts "Bad blood". A matchup is "live" at heat >= 35.
#
# Schedule: league.schedule holds (date, home_team, away_team) tuples but
# can ALSO hold (date, event_type, event_data) entries -- entries are
# validated defensively (3-tuple, both sides team-like, different teams,
# date in {today, tomorrow} for pregame buildup). Malformed entries are
# skipped, never raised.
#
# Templates name ONLY what the engine knows: the two teams, their real
# W-L-OTL records, the heat band, and REAL hype_tags. The band's own tag
# ("Bad blood"/"Heated rivalry") is filtered out of the rendered tag list
# -- the band is already stated -- and stories with no remaining tags
# stay true on teams + records + band alone. No invented causes, scores,
# streaks, or history.
#
# The {when} slot renders "tonight" for games scheduled today and
# "tomorrow night" for games scheduled tomorrow (via _rivalry_when, fail
# closed). Two templates are deliberately time-free.
#
# One story per (season, pair, band) -- the key is orientation-free:
# (t1,t2) and (t2,t1) are the same pair (matches the within-day dedupe).
# Keys are id(t)-disambiguated to survive duplicate team names (R8a lesson)
# and are marked ONLY for stories actually returned. Capped at 2/day,
# ordered by heat desc.

RIVALRY_HYPE_HEAT_MIN = 35       # "Heated rivalry" band floor
RIVALRY_HYPE_BAD_BLOOD = 65      # "Bad blood" band floor
RIVALRY_HYPE_MAX_PER_DAY = 2
# One-shot window outlasts a season (mirrors streaks' 400).
RIVALRY_HYPE_WINDOW_DAYS = 400
# Band labels already rendered as hype_tags by matchup_narrative -- the
# templates state the band themselves, so these are never listed twice.
_RIVALRY_BAND_TAGS = frozenset({"Bad blood", "Heated rivalry"})

_RIVALRY_HEATED_TEMPLATES = [
    "HEATED RIVALRY: {home} hosts {away} {when} -- {hw}-{hl}-{hotl} "
    "against {aw}-{al}-{aotl}.",
    "A heated rivalry hits the ice {when}: {away} ({aw}-{al}-{aotl}) "
    "visits {home} ({hw}-{hl}-{hotl}).",
    "Circle the calendar: {home} and {away} meet {when} in a heated "
    "rivalry -- {hw}-{hl}-{hotl} versus {aw}-{al}-{aotl}.",
    "{away} comes to town to face {home} in a heated rivalry matchup: "
    "{aw}-{al}-{aotl} against {hw}-{hl}-{hotl}.",
]

_RIVALRY_BADBLOOD_TEMPLATES = [
    "BAD BLOOD: {home} vs {away} {when} -- {hw}-{hl}-{hotl} against "
    "{aw}-{al}-{aotl}.",
    "Bad blood on the ice: {home} ({hw}-{hl}-{hotl}) hosts {away} "
    "({aw}-{al}-{aotl}) {when}.",
    "Expect a nasty one {when} -- {away} ({aw}-{al}-{aotl}) visits {home} "
    "({hw}-{hl}-{hotl}), and there is bad blood between these two.",
    "BAD BLOOD: {away} at {home}. The records read {aw}-{al}-{aotl} and "
    "{hw}-{hl}-{hotl}, but this one is never about the standings.",
]


def _rivalry_heat_band(heat):
    """Heat band label: 'bad blood' at 65+, else 'heated rivalry'."""
    return "bad blood" if heat >= RIVALRY_HYPE_BAD_BLOOD else "heated rivalry"


def _rivalry_sched_day_ok(sched_date, game_date):
    """True when the schedule entry is today or tomorrow (pregame buildup).
    Defensive about date vs datetime mixes; fail closed on anything
    unreadable."""
    try:
        d = sched_date.date() if hasattr(sched_date, "date") else sched_date
        if not isinstance(d, date):
            return False
        for delta in (0, 1):
            target = game_date + timedelta(days=delta)
            t = target.date() if hasattr(target, "date") else target
            if d == t:
                return True
        return False
    except Exception:
        return False


def _rivalry_when(sched_date, game_date):
    """'tonight' or 'tomorrow night' for the scheduled game day.
    Fail closed: None unless the scheduled day is exactly today or
    tomorrow (the caller already gates on _rivalry_sched_day_ok)."""
    try:
        d = sched_date.date() if hasattr(sched_date, "date") else sched_date
        g = game_date.date() if hasattr(game_date, "date") else game_date
        if not isinstance(d, date) or not isinstance(g, date):
            return None
        if d == g:
            return "tonight"
        if d == g + timedelta(days=1):
            return "tomorrow night"
        return None
    except Exception:
        return None


def _rivalry_resolve_team(ref, teams):
    """Resolve a schedule side to a team object. Objects pass through;
    bare name strings are looked up by team_name; anything else is None
    (fail closed)."""
    if ref is None or isinstance(ref, str):
        if not isinstance(ref, str) or not ref:
            return None
        for t in teams:
            if _tname(t) == ref:
                return t
        return None
    if _tname(ref) and _tname(ref) != "Unknown Team":
        return ref
    return None


def _rivalry_hype_stories(app, game_date, rng):
    """Pregame buildup for scheduled matchups between feuding teams.

    Repeat keys are marked ONLY for stories actually returned: marking
    a key for a story that gets truncated would suppress it forever
    (the one-shot window is longer than a season).
    """
    try:
        from narrative_ledger import get_ledger, matchup_narrative
    except Exception:
        logging.getLogger(__name__).exception(
            "rivalry-hype bucket: narrative_ledger unavailable")
        return []
    try:
        if not _in_season(game_date):
            return []
        season_year = _pr_season_year(app, game_date)
        if not season_year:
            return []
        league = _pr_league(app)
        if league is None:
            return []
        teams = _all_teams(app)
        schedule = _safe(lambda: list(getattr(league, "schedule", None) or []),
                         [])
        ledger = _safe(lambda: get_ledger(app), None)
        seen_pairs = set()
        candidates = []
        for entry in schedule:
            try:
                # Defensive: the schedule can also carry
                # (date, event_type, event_data) entries.
                if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                    continue
                sched_date, home_ref, away_ref = entry
                if not _rivalry_sched_day_ok(sched_date, game_date):
                    continue
                when = _rivalry_when(sched_date, game_date)
                if when is None:
                    continue
                home = _rivalry_resolve_team(home_ref, teams)
                away = _rivalry_resolve_team(away_ref, teams)
                if home is None or away is None:
                    continue
                hname, aname = _tname(home), _tname(away)
                if not hname or not aname or hname == aname:
                    continue  # same-team or nameless matchups
                pair = (hname, id(home), aname, id(away))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                narr = matchup_narrative(home, away, league=league,
                                         ledger=ledger)
                heat = _safe(lambda: float(narr.get("rivalry_heat", 0.0)), 0.0)
                if not math.isfinite(heat) or heat < RIVALRY_HYPE_HEAT_MIN:
                    continue
                band = _rivalry_heat_band(heat)
                tags = narr.get("hype_tags") or []
                dtags = [str(t).strip() for t in tags
                         if str(t).strip() and str(t).strip()
                         not in _RIVALRY_BAND_TAGS][:3]
                tagbit = f" Storylines: {', '.join(dtags)}." if dtags else ""
                hw, hl, hotl = _team_record(home)
                aw, al, aotl = _team_record(away)
                tpls = (_RIVALRY_BADBLOOD_TEMPLATES
                        if band == "bad blood"
                        else _RIVALRY_HEATED_TEMPLATES)
                story = rng.choice(tpls).format(
                    home=hname, away=aname, band=band, when=when,
                    hw=hw, hl=hl, hotl=hotl, aw=aw, al=al, aotl=aotl)
                if tagbit:
                    story = story + tagbit
                # Orientation-free key: (t1,t2) and (t2,t1) are the same
                # pair, matching the within-day dedupe below.
                i1, i2 = id(home), id(away)
                kn1, kn2 = (aname, hname) if i1 > i2 else (hname, aname)
                i1, i2 = (i2, i1) if i1 > i2 else (i1, i2)
                key = (f"rivalry_hype:{season_year}:{kn1}#{i1}:{kn2}#{i2}:"
                       f"{band}")
                if not _recent_ok(app, key, "rivalry_hype", game_date,
                                  window=RIVALRY_HYPE_WINDOW_DAYS):
                    continue
                # Orientation-free ids: a (t1,t2) schedule entry and the
                # (t2,t1) mirror are the same pair -- deduped below.
                candidates.append(
                    (heat, hname, aname, id(home), id(away), story, key))
            except Exception:
                logging.getLogger(__name__).exception(
                    "rivalry-hype matchup check failed")
                continue
    except Exception:
        logging.getLogger(__name__).exception("rivalry-hype bucket failed")
        return []
    # Newsworthiness: hottest feud first; then dedupe duplicate pairs
    # (same text would render twice) and cap.
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    deduped = []
    seen = set()
    for cand in candidates:
        pair_ids = tuple(sorted((cand[3], cand[4])))
        if pair_ids in seen:
            continue
        seen.add(pair_ids)
        deduped.append(cand)
    chosen = deduped[:RIVALRY_HYPE_MAX_PER_DAY]
    for _heat, _h, _a, _ih, _ia, _story, key in chosen:
        _mark_recent(app, key, "rivalry_hype", game_date)
    return [s for _heat, _h, _a, _ih, _ia, s, _k in chosen]


# ---------------------------------------------------------------------------
# R8g -- Extensions-signed bucket
# ---------------------------------------------------------------------------
# Positive mirror of the holdout bucket: where holdout fires on stars with
# <=1 year left ("the clock is ticking"), this fires on stars locked up
# long-term (years_remaining >= 4): "signed through" stories.
#
# Honest design decision: there is no signing-EVENT ledger anywhere in the
# engine. Verified in code: the write paths that raise years_remaining are
# the user negotiation flow (_finalize_contract_signing, multiplayer
# accept paths in game_manager.py) AND the AI UFA signing path
# (ufa_consideration.py:595 _sign_ai_winner, wired into the daily loop at
# game_manager.py:5460) -- so real signing events do occur in headless
# sims, and the state-based premise ("a star is secured long-term") holds
# for both user and AI signings. The mirror is therefore STATE-based: a
# star under a long deal is a true, independently verifiable fact, the same
# way holdout's "star with <=1 year" is. No claim of "just signed" -- only
# the deal that exists.
#
# Fact surface (tight, like holdout): player name, team name, OVR, years
# remaining, and the signed-through year (season_start_year +
# years_remaining; e.g. a 5-year deal during 2026-27 covers 26-27 through
# 30-31, expiring summer 2031). No salary/AAV claims.
#
# Fail-closed: `_ext_years` returns the years only from a REAL contract
# object. `_contract_years_left`'s 99-fallback (no contract info at all) is
# treated as unknown -- a fabricated "through 2125" is worse than silence.
# One story per (season, player) per season; the year-round gate mirrors
# holdout (contract state is true in-season and offseason alike).
#
# Mark-only-returned (R8e pattern): repeat keys are marked ONLY for stories
# actually returned, so the standing `_generate` target-cap key-drop issue
# (affecting R8a-f) cannot suppress this bucket's stories forever.

_EXT_STAR_OVR = 82       # same star bar as the holdout bucket
_EXT_MIN_YEARS = 4       # long-term security threshold
_EXT_MAX_PER_DAY = 2
_EXT_ONE_SHOT_WINDOW = 400  # longer than a season: one story per (season, player)

_EXTENSION_TEMPLATES = [
    "EXTENSION: {name} isn't going anywhere -- the {ovr} OVR star is signed through {through} with {team}.",
    "{team} has {name} locked up through {through}: {years} more {years_word} for the {ovr} OVR star.",
    "EXTENSION: {name} ({ovr} OVR) is {team}'s long-term cornerstone -- under contract through {through}.",
    "The {team} faithful can relax: {name} is signed through {through}, {years} {years_word} of {ovr} OVR hockey.",
    "EXTENSION: {name} committed to {team} through {through} -- long-term security for an {ovr} OVR talent.",
    "{name}'s future is settled in {team}: the {ovr} OVR star is locked up through {through}.",
    "EXTENSION: {team} locked up {name} through {through} -- {years} {years_word} of runway for their {ovr} OVR cornerstone.",
    "Long-term ink in {team}: {name} ({ovr} OVR) is signed through {through}.",
    "EXTENSION: {name} is {team} property through {through} -- the {ovr} OVR star's deal has {years} {years_word} left.",
    "{team} built around {name} for a reason -- the {ovr} OVR star is under contract through {through}.",
    "EXTENSION: No drama in {team} -- {name} ({ovr} OVR) is signed through {through}.",
    "{name} isn't hitting the market anytime soon: {years} {years_word} left on the {team} deal, through {through}.",
    "EXTENSION: {team}'s window stays open -- {name} ({ovr} OVR) is locked up through {through}.",
    "The {team} core has its anchor: {name} signed through {through}, {years} {years_word} at {ovr} OVR.",
    "EXTENSION: {name} chose {team} through {through} -- the {ovr} OVR star's long-term deal keeps the band together.",
]


def _ext_years(p):
    """Real years remaining on a real contract, or None.

    Mirrors _contract_years_left but FAIL-CLOSED: the type is checked on
    the RAW attribute BEFORE any coercion (F1: "5"/4.9/True must never
    qualify -- the docstring promises "only a genuine positive int"),
    the 99-fallback (no contract info) and out-of-range values are
    unknown, not "long-term".
    """
    c = _safe(lambda: p.contract, None)
    if c is None:
        return None
    raw = _safe(lambda: getattr(c, "years_remaining", None), None)
    if not isinstance(raw, int) or isinstance(raw, bool):
        return None
    if raw <= 0 or raw > 50:
        return None
    return raw


def _ext_season_year(app, game_date):
    """Season-start year for the through-year arithmetic, fail-closed.

    `_pr_season_year` falls back to the calendar year when the league does
    not carry one -- but Jan-Apr belongs to the season that STARTED the
    previous calendar year, so that fallback would overstate the
    signed-through year by one in the second half of the season. Prefer
    the game's own season_year; derive from the calendar only with the
    Oct-Dec vs Jan-Apr split applied; 0 when unknown.

    F5: insane years render them as fact -- so an insane league value must
    fail closed (silent), while a merely MISSING value may still derive
    from the calendar when unambiguous (Jan-Apr / Oct-Dec).
    """
    raw = _safe(lambda: getattr(_pr_league(app), "season_year", None), None)
    y = None
    if raw is not None:
        try:
            y = int(raw)
        except (TypeError, ValueError):
            y = None
    if y is not None:
        if 1900 <= y <= 2200:
            return y
        return 0  # corrupt league data: fail closed, never "through 6"
    try:
        m = game_date.month
        if m in (1, 2, 3, 4):
            return game_date.year - 1
        if m in (10, 11, 12):
            return game_date.year
    except Exception:
        pass
    return 0


def _extension_stories(app, game_date, rng):
    """Long-term lockup stories for star players (positive holdout mirror)."""
    try:
        season_year = _ext_season_year(app, game_date)
        if not season_year:
            return []
        candidates = []
        for p, t in _all_players(app):
            try:
                ovr = _ovr(p)
                if not _ovr_ok(ovr) or ovr < _EXT_STAR_OVR:
                    continue
                yrs = _ext_years(p)
                if yrs is None or yrs < _EXT_MIN_YEARS:
                    continue
                name = _pname(p)
                team = _tname(t)
                if not name or name == "Unknown Player" \
                        or not team or team == "Unknown Team":
                    continue
                through = season_year + yrs
                story = rng.choice(_EXTENSION_TEMPLATES).format(
                    name=name, team=team, ovr=int(ovr), years=yrs,
                    years_word="year" if yrs == 1 else "years",
                    through=through)
                # Guard against placeholder-y output.
                if "Unknown" in story:
                    continue
                # F2: id-only keys collide after save/load (player_id_counter
                # is never restored -- draft classes restart at 0), letting
                # an unrelated id-collider permanently suppress a star's
                # story. R8e pattern: name#id disambiguates.
                key = (f"extension:{season_year}:{name}#"
                       f"{_safe(lambda: p.id, id(p))}")
                if not _recent_ok(app, key, "extension", game_date,
                                  window=_EXT_ONE_SHOT_WINDOW):
                    continue
                candidates.append((ovr, yrs, name, story, key))
            except Exception:
                continue
    except Exception:
        logging.getLogger(__name__).exception("extensions bucket failed")
        return []
    # Newsworthiness: biggest star first, longest lockup breaks ties; then
    # dedupe identical (name, story-key) pairs and cap. F4: dedupe is on
    # name+key, not name alone -- two different stars sharing a name on
    # different teams render different text and both deserve to fire.
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2]))
    deduped = []
    seen = set()
    for cand in candidates:
        pair = (cand[2], cand[4])
        if pair in seen:
            continue
        seen.add(pair)
        deduped.append(cand)
    chosen = deduped[:_EXT_MAX_PER_DAY]
    for _ovr_, _yrs, _nm, _story, key in chosen:
        _mark_recent(app, key, "extension", game_date, _EXT_ONE_SHOT_WINDOW)
    return [s for _ovr_, _yrs, _nm, s, _k in chosen]


# ---------------------------------------------------------------------------
# R8h -- Debuts bucket
# ---------------------------------------------------------------------------
# Story premises, all derived from real finished-game state plus the
# engine's own career/service-time counters:
#   - NHL DEBUT: the player's nhl_games_played is 1 after the day's
#     credit. That counter is the engine's service-time truth
#     (game_manager._credit_nhl_games_played): +1 per completed NHL
#     game for every rostered player, NEVER for preseason exhibitions.
#     The credit covers the whole roster -- including healthy
#     scratches -- and per-game game_stats lines are ALSO initialized
#     roster-wide on both sim paths (simulation.py:806,
#     quick_sim.py:1076), so a line alone does NOT prove the player
#     dressed (reviewer B killshot: a toi==0 scratch fired a false
#     debut). The dressed proof is therefore:
#       - skaters: result['player_toi'][pid] > 0. Stamped on every
#         result-recording path (game_manager.py:8498/9546,
#         main.py:13105/14496) from ledgers that only dressed
#         players enter (quick_sim toi+=45 per shift for on-ice
#         skaters; GameSim player_toi_seconds accumulates per shift);
#         only truthy values are recorded, so missing/zero is
#         fail-closed silent.
#       - goalies: the game_stats line has saves >= 1 (the R8d
#         shutout precedent -- a goalie who played faced rubber).
#         player_toi can't be used: the snapshot fill-in stamps full-
#         game TOI on every roster goalie (game_manager.py:14386).
#     "Quick"-detail leagues record no per-game lines, so the bucket
#     stays silent there (fail silent, never synthesize) -- the R8d
#     precedent.
#   - FIRST NHL GOAL: a skater's line has g >= 1 (cross-checked g <=
#     his team's goals, the R8d self-disproving-line killshot) AND the
#     first-goal gate proves he had zero NHL goals before the game:
#       (1) p.stats.goals (post-game season total) == g -- all of this
#           season's goals came from this game. The live sim writes
#           season totals to p.stats.* (never the flat Player attrs;
#           awards_race._stat documents the real write path) and the
#           AHL sim never writes p.stats, so season totals are
#           NHL-only by construction.
#       (2) nhl_games_played == p.stats.games_played (post-game) --
#           every career NHL game is this season's; a 6-seasons-ago
#           veteran returning has a large nhl_games_played and fails
#           here (fail closed).
#       (3) sum(prior_nhl_gp) == 0 -- the live season rollover
#           archives each season's NHL GP to the flat
#           p.prior_nhl_gp (game_classes.py:7420-7435, Calder input;
#           the last five seasons are kept). Belt and suspenders on
#           (2); the stats-level copy is never populated in
#           production (PlayerStats.reset_season_stats has no
#           callers), so the helper reads the flat attribute first.
#     A non-debut first goal (rookie, scoreless in his first games,
#     scores in game 5) passes the same gate. A veteran with prior NHL
#     seasons is UNPROVABLE (no engine field archives prior-season
#     goals) and stays silent -- the R8c whole-field-maximality
#     lesson: a "first" claim must prove career-level maximality.
#   - CALL-UP: PRODUCTION-SILENT. There is no dated production
#     call-up log: dressing_room arrivals record {"how": "callup"} but
#     no date; player.nhl_audition is user-team-only and dateless;
#     there is no transaction/move feed. Debuts are the engine-honest
#     coverage of first NHL appearances -- nothing is fabricated.
#
# Fail-closed gates: the in-season gate tests the GAME day (Oct-Apr;
# preseason exhibitions are September and never credit NHL GP, so
# they can never fire -- even when the news runs on Oct 1); NHL
# results only; every result a well-formed dict with real team
# objects and non-negative strict-integer scores; a finished game
# names a real winner; debut/first-goal subjects are real player
# objects with real names on a real roster (identity by id(), never
# name-keyed); one story per (game, player) with first_goal
# outranking debut; one-shot keys per (season, player, kind), marked
# ONLY for stories actually returned -- per-kind, the R8d precedent:
# a scoreless debut and a later first NHL goal are two true premises
# of two different story kinds, and suppressing the first-goal story
# because the debut already fired would gut the item's "first NHL
# goals" kind (most debutants don't score on debut night). When a
# debutant scores, the story kind is first_goal and BOTH keys are
# marked -- the story delivers the debut news ("in his NHL debut"),
# so re-firing the bare debut on a regenerated news day would repeat
# delivered news. At most 2 stories per day, first goals first.
# ---------------------------------------------------------------------------

# One-shot window longer than any season -- each (season, player,
# kind) fires at most once.
DEBUTS_WINDOW_DAYS = 400
# At most this many debuts stories per news day.
DEBUTS_MAX_PER_DAY = 2
# Newsworthiness per kind.
_DEBUT_KIND_WEIGHTS = {
    "first_goal": 15,
    "debut": 14,
}

_DEBUT_TEMPLATES = [
    "DEBUT: {name} made his NHL debut in {team}'s {score} win over "
    "{opp}.",
    "DEBUT: {name} skated in his first NHL game as {team} beat {opp} "
    "{score}.",
    "DEBUT: A night to remember for {name}, who made his NHL debut "
    "for {team} in a {score} win over {opp}.",
]

_DEBUT_LOSS_TEMPLATES = [
    "DEBUT: {name} made his NHL debut as {team} fell {score} to {opp}.",
    "DEBUT: {name}'s first NHL game came in {team}'s {score} loss to "
    "{opp}.",
]

_FIRST_GOAL_TEMPLATES = [
    "FIRST NHL GOAL: {name} scored his first NHL goal{debut_note} in "
    "{team}'s {score} win over {opp}.",
    "FIRST NHL GOAL: A milestone for {name} -- his first NHL "
    "goal{debut_note} -- as {team} beat {opp} {score}.",
    "FIRST NHL GOAL: {name} found the net for the first time in the "
    "NHL{debut_note}, helping {team} past {opp} {score}.",
]

_FIRST_GOAL_LOSS_TEMPLATES = [
    "FIRST NHL GOAL: {name} scored his first NHL goal{debut_note}, "
    "but {team} fell {score} to {opp}.",
    "FIRST NHL GOAL: A bright spot for {team} -- {name}'s first NHL "
    "goal{debut_note} -- in a {score} loss to {opp}.",
]


def _debut_season_pair(p):
    """(season_games, season_goals) as strict ints from the sim's real
    write path (p.stats first, the never-called add_game_stats flat
    attrs only as fallback -- the awards_race._stat precedent).
    (None, None) on any junk: a "first" premise must not rest on
    coerced numerics."""
    try:
        stats = getattr(p, "stats", None)
        gp = getattr(stats, "games_played", None)
        if not isinstance(gp, bool) and isinstance(gp, int):
            pass
        else:
            gp = getattr(p, "games_played", None)
            if isinstance(gp, bool) or not isinstance(gp, int):
                return None, None
        gl = getattr(stats, "goals", None)
        if not isinstance(gl, bool) and isinstance(gl, int):
            pass
        else:
            gl = getattr(p, "goals", None)
            if isinstance(gl, bool) or not isinstance(gl, int):
                return None, None
        if gp < 0 or gl < 0:
            return None, None
        return gp, gl
    except Exception:
        return None, None


def _debut_prior_gp(p):
    """Sum of archived prior-season NHL GP. The live season rollover
    archives to the FLAT p.prior_nhl_gp (game_classes.py:7420-7435,
    Calder input -- the last five seasons are kept; non-NHL players
    get a 0 for the season). PlayerStats.reset_season_stats has no
    production callers, so the stats-level copy is never populated in
    production -- read the flat attribute first and only fall back to
    p.stats for fixtures/fakes. None on junk: fail closed, never
    treat unreadable history as zero history."""
    for src in (p, _safe(lambda: getattr(p, "stats", None))):
        try:
            if src is None:
                continue
            prior = getattr(src, "prior_nhl_gp", None)
        except Exception:
            continue
        if prior is None:
            continue  # absent on this source; try the other
        if not isinstance(prior, (list, tuple)):
            return None
        total = 0
        for v in prior:
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                return None
            total += v
        return total
    return 0


def _debut_dressed(res, p, line):
    """Dressed proof for a debut candidate: did he actually take the
    ice in this game? Skaters: result['player_toi'][pid] > 0 (only
    dressed players enter the TOI ledgers; only truthy values are
    recorded). Goalies: line saves >= 1 (player_toi is unusable --
    the snapshot fill-in stamps full-game TOI on every roster
    goalie). Strictly fail-closed: missing/junk TOI or saves never
    proves a debut."""
    try:
        pid = getattr(p, "id", None)
        if _td_pos_group(p) == "Goalie":
            return _hero_line_num(line, "saves") >= 1
        toi = res.get("player_toi")
        if not isinstance(toi, dict):
            return False
        v = toi.get(pid)
        if isinstance(v, bool):
            return False
        return isinstance(v, (int, float)) and v > 0
    except Exception:
        return False


def _debut_stories(app, game_date, rng):
    """NHL debuts and first NHL goals from the day just simmed.

    One-shot keys are marked ONLY for stories actually returned: a
    key marked for a story dropped by the day cap would suppress it
    forever (the window outlasts a season).
    """
    try:
        game_day = _safe(lambda: game_date - timedelta(days=1))
        if game_day is None:
            return []
        # The in-season gate tests the GAME day, not the news day (the
        # R8d/reviewer-B F4 lesson): preseason exhibitions are
        # September and never credit NHL GP.
        if not _in_season(game_day):
            return []
        season_year = _pr_season_year(app, game_date)
        if (not season_year or not isinstance(season_year, int)
                or season_year < 2000 or season_year > 2100):
            return []
        results = _hero_results(app, game_date)
        if not results:
            return []
        candidates = []
        for res in results:
            if not isinstance(res, dict):
                continue
            home = res.get("home_team")
            away = res.get("away_team")
            if not _hero_teams_ok(home, away):
                continue
            hn = home.team_name
            an = away.team_name
            if hn == an:
                # Same-team result is corrupt state, not a game.
                continue
            hs = _hero_int(res.get("home_score"))
            aws = _hero_int(res.get("away_score"))
            if hs is None or aws is None or hs < 0 or aws < 0:
                continue
            wname = _safe(lambda: res.get("winner").team_name, "") or ""
            if wname not in (hn, an):
                # A finished game has a winner; anything else is
                # uninterpretable state, not a story.
                continue
            gstats = res.get("game_stats")
            if not isinstance(gstats, dict):
                gstats = {}
            # One story per (game, player): first goal outranks debut.
            best = {}
            for _pid, line in gstats.items():
                try:
                    if not isinstance(line, dict):
                        continue
                    p = line.get("player")
                    name = _pname(p)
                    if not name or name == "Unknown Player":
                        continue
                    team = _hero_team_of(p, home, away)
                    if not team or team == "Unknown Team":
                        continue
                    if team not in (hn, an):
                        continue
                    g = _hero_line_num(line, "g", "goals")
                    if g < 0:
                        continue
                    # Cross-check the line against the team score
                    # (R8d killshot: a "3-goal" night in a 2-0 game
                    # disproves itself) -- fail silent.
                    team_goals = hs if team == hn else aws
                    if g > team_goals:
                        continue
                    nhl_gp = getattr(p, "nhl_games_played", None)
                    if (isinstance(nhl_gp, bool)
                            or not isinstance(nhl_gp, int)
                            or nhl_gp < 0):
                        continue
                    is_debut = (nhl_gp == 1)
                    if is_debut and not _debut_dressed(res, p, line):
                        # Service-time credit covers healthy scratches
                        # and lines are roster-wide: without dressed
                        # proof this is a press-box credit, not a debut
                        # (reviewer B killshot). Fail closed.
                        is_debut = False
                    first_goal = False
                    pos_group = _td_pos_group(p)
                    if (g >= 1
                            and pos_group in ("Forward", "Defense")):
                        sg, sgoals = _debut_season_pair(p)
                        # The whole-field maximality gate: every goal
                        # this season came from this game, every career
                        # NHL game is this season's, no archived prior
                        # NHL games. Anything less cannot prove "first".
                        if (sg is not None and sgoals == g
                                and nhl_gp == sg):
                            prior = _debut_prior_gp(p)
                            if prior == 0:
                                first_goal = True
                    if not is_debut and not first_goal:
                        continue
                    kind = ("first_goal" if first_goal else "debut")
                    weight = _DEBUT_KIND_WEIGHTS[kind]
                    cur = best.get(id(p))
                    if cur is not None and cur[1] >= weight:
                        continue
                    best[id(p)] = (kind, weight, p, name, team, g,
                                   is_debut)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "debuts line check failed")
                    continue
            for _pidn, (kind, weight, p, name, team, g,
                        is_debut) in best.items():
                try:
                    if team == hn:
                        mine, theirs, opp = hs, aws, an
                    else:
                        mine, theirs, opp = aws, hs, hn
                    score = f"{mine}-{theirs}"
                    won = (team == wname)
                    if kind == "first_goal":
                        debut_note = (" in his NHL debut"
                                      if is_debut else "")
                        tpls = (_FIRST_GOAL_TEMPLATES if won
                                else _FIRST_GOAL_LOSS_TEMPLATES)
                        story = rng.choice(tpls).format(
                            name=name, team=team, opp=opp, score=score,
                            debut_note=debut_note)
                    else:
                        tpls = (_DEBUT_TEMPLATES if won
                                else _DEBUT_LOSS_TEMPLATES)
                        story = rng.choice(tpls).format(
                            name=name, team=team, opp=opp, score=score)
                    # Guard against placeholder-y output.
                    if "Unknown" in story:
                        continue
                    keys = [f"debuts:{season_year}:{kind}:"
                            f"{name}#{id(p)}"]
                    if kind == "first_goal" and is_debut:
                        # The story delivers the debut news too -- mark
                        # the debut key so a regenerated news day can't
                        # repeat it as a bare debut.
                        keys.append(f"debuts:{season_year}:debut:"
                                    f"{name}#{id(p)}")
                    if not all(_recent_ok(app, k, "debuts", game_date,
                                          window=DEBUTS_WINDOW_DAYS)
                               for k in keys):
                        continue
                    candidates.append((weight, name, story, keys))
                except Exception:
                    logging.getLogger(__name__).exception(
                        "debuts render failed")
                    continue
    except Exception:
        logging.getLogger(__name__).exception("debuts bucket failed")
        return []
    # Newsworthiness: first goals before debuts, then name for
    # determinism; cap the day.
    candidates.sort(key=lambda c: (-c[0], c[1]))
    chosen = candidates[:DEBUTS_MAX_PER_DAY]
    for _w, _n, _s, keys in chosen:
        for k in keys:
            _mark_recent(app, k, "debuts", game_date,
                         DEBUTS_WINDOW_DAYS)
    return [s for _w, _n, s, _k in chosen]


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
    ("playoff_race", _playoff_race_stories, 0.65),
    ("trade_deadline", _trade_deadline_stories, 0.60),
    ("award_races", _award_race_stories, 0.58),
    ("heroics", _heroics_stories, 0.60),
    ("streaks", _streaks_stories, 0.60),
    ("rivalry_hype", _rivalry_hype_stories, 0.60),
    ("extension", _extension_stories, 0.60),
    ("debuts", _debut_stories, 0.60),
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
            if _story_has_unknown_entity(s):
                # R9 global backstop: a rendered placeholder name/team means
                # a bucket gate missed something upstream -- suppress the
                # story (fail closed, logged, never surfaced). It does not
                # count toward `added`.
                _log.warning("daily_news: suppressed story with unknown "
                             "entity placeholder: %s", repr(s)[:160])
                continue
            add(s)
            added += 1
        except Exception:
            continue
    return added
