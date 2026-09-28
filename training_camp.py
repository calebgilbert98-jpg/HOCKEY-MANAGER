"""EHM-style training camp.

Runs every September 12-30, right before the early-October roster cuts
(waiver_logic camp cuts). Every club's signed players plus invited
rights-held prospects attend; scrimmage days (every 3rd day from Sep 15)
pit intra-squad Red vs White in a lightweight sim that produces
per-player 1-10 ratings, exactly the kind of camp report EHM managers
read before making cuts.

Ratings persist on the player (player.camp_ratings / player.camp_avg)
so the TrainingCampView can show them all season and the AI camp-cut
logic (waiver_logic) can prefer cutting campers who stank.

Camp matters on the ice too: standout youngsters (22 or under,
7.5+ average over 2+ scrimmages) earn a small bounded attribute bump;
poor camps cost veterans a little morale.

Entry point: run_camp_day(league, on_date, app=None, rng=None), called
from the daily advance in main.py. Idempotent per date.
"""

import random
from datetime import date as _date

CAMP_START = (9, 12)
CAMP_END = (9, 30)
SCRIMMAGE_INTERVAL = 3          # every 3rd day, starting Sep 15
STANDOUT_AGE_MAX = 22
STANDOUT_AVG = 7.5
STANDOUT_MIN_GAMES = 2

_SKATER_BUMP_ATTRS = ("skating", "shooting", "passing", "deking",
                      "offensive_awareness", "defensive_awareness")


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def is_camp_day(on_date):
    try:
        return (on_date.month, on_date.day) >= CAMP_START and \
               (on_date.month, on_date.day) <= CAMP_END
    except Exception:
        return False


def is_scrimmage_day(on_date):
    try:
        if not is_camp_day(on_date):
            return False
        # Sep 12 = fitness testing / camp opens; scrimmages from the 15th.
        return on_date.day >= 15 and (on_date.day - 12) % SCRIMMAGE_INTERVAL == 0
    except Exception:
        return False


def is_camp_open_day(on_date):
    try:
        return (on_date.month, on_date.day) == CAMP_START
    except Exception:
        return False


def is_camp_close_day(on_date):
    try:
        return (on_date.month, on_date.day) == CAMP_END
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Camp roster
# ---------------------------------------------------------------------------

def _is_nhl_team(team):
    return str(getattr(team, "league_name", "") or "") == "National Hockey League"


def _camp_invitees(team):
    """NHL roster + AHL roster + invited rights-held prospects (<25)."""
    seen = set()
    out = []
    for pool in (getattr(team, "roster", None),
                 getattr(team, "ahl_roster", None),
                 getattr(team, "prospects", None)):
        for p in (pool or []):
            pid = getattr(p, "id", None)
            if pid in seen:
                continue
            seen.add(pid)
            out.append(p)
    # Unsigned rights-held prospects get a camp invite (EHM: they attend).
    tname = str(getattr(team, "team_name", "") or "")
    for p in (getattr(team, "prospects", None) or []):
        if getattr(p, "id", None) in seen:
            continue
        try:
            if str(getattr(p, "rights_team", "") or "") == tname and \
                    int(getattr(p, "age", 99) or 99) < 25:
                seen.add(getattr(p, "id", None))
                out.append(p)
        except Exception:
            continue
    return out


def _open_camp(league, on_date, app=None, rng=None):
    year = on_date.year
    if int(getattr(league, "_camp_opened_year", 0) or 0) == year:
        return
    league._camp_opened_year = year
    league._camp_scrimmage_dates = []
    league._camp_closed_year = 0
    for team in (getattr(league, "teams", None) or []):
        if not _is_nhl_team(team):
            continue
        roster = _camp_invitees(team)
        team.camp_roster = list(roster)
        team.camp_scrimmages = []
        for p in roster:
            try:
                p.camp_ratings = []
                p.camp_avg = 0.0
                p.camp_standout = False
            except Exception:
                continue
    if app is not None:
        try:
            app.add_news("Training camps open across the league -- "
                         "scrimmages begin September 15.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Scrimmage sim
# ---------------------------------------------------------------------------

def _is_goalie(p):
    try:
        return str(getattr(getattr(p, "primary_position", None),
                           "name", "")) == "GOALIE"
    except Exception:
        return False


def _ovr(p):
    try:
        return float(p.overall_rating())
    except Exception:
        return 70.0


def _split_squads(roster, rng):
    """Alternate draft by overall: balanced Red vs White (vets + kids mix)."""
    ordered = sorted(roster, key=_ovr, reverse=True)
    red, white = [], []
    for i, p in enumerate(ordered):
        (red if i % 2 == 0 else white).append(p)
    return red, white


def _squad_strength(squad):
    if not squad:
        return 70.0
    return sum(_ovr(p) for p in squad) / len(squad)


def _sim_scrimmage(team, on_date, rng):
    """One intra-squad game. Returns the log dict; stamps player ratings."""
    roster = list(getattr(team, "camp_roster", None) or [])
    if len(roster) < 10:
        return None
    red, white = _split_squads(roster, rng)
    rs, ws = _squad_strength(red), _squad_strength(white)

    def _goals(strength, opp_strength):
        mu = 3.2 + (strength - opp_strength) * 0.10
        return max(0, int(round(rng.gauss(mu, 1.3))))

    red_goals = _goals(rs, ws)
    white_goals = _goals(ws, rs)
    red_won = red_goals > white_goals

    rated = []  # (player, rating)
    for squad, gf, ga, won in ((red, red_goals, white_goals, red_won),
                               (white, white_goals, red_goals, not red_won)):
        for p in squad:
            age = int(getattr(p, "age", 27) or 27)
            if _is_goalie(p):
                # Goals allowed vs a ~3.0 expected line.
                base = 6.2 - (ga - 3.0) * 0.9
                noise = rng.gauss(0, 0.8)
                rating = base + noise
            else:
                ovr = _ovr(p)
                base = 4.5 + (ovr - 65) * 0.09
                noise = rng.gauss(0, 0.9)
                # Kids are boom/bust in camp -- exactly what EHM shows.
                if age <= 21:
                    noise += rng.gauss(0, 0.5)
                rating = base + noise + (0.3 if won else -0.2)
            rating = round(max(3.0, min(10.0, rating)), 1)
            try:
                p.camp_ratings.append(rating)
            except Exception:
                pass
            rated.append((p, rating))

    rated.sort(key=lambda pr: pr[1], reverse=True)
    stars = [getattr(p, "full_name", "?") for p, _r in rated[:3]]
    log = {"date": on_date.isoformat(), "red": red_goals,
           "white": white_goals, "stars": stars,
           "ratings": {str(getattr(p, "id", "?")): r for p, r in rated}}
    try:
        team.camp_scrimmages.append(log)
    except Exception:
        pass
    return log


def _run_scrimmages(league, on_date, app=None, rng=None):
    rng = rng or random
    iso = on_date.isoformat()
    done = getattr(league, "_camp_scrimmage_dates", None)
    if not isinstance(done, list):
        done = []
        league._camp_scrimmage_dates = done
    if iso in done:
        return
    done.append(iso)
    for team in (getattr(league, "teams", None) or []):
        if not _is_nhl_team(team):
            continue
        try:
            _sim_scrimmage(team, on_date, rng)
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Camp close: report + development
# ---------------------------------------------------------------------------

def _avg(ratings):
    return round(sum(ratings) / len(ratings), 1) if ratings else 0.0


def _bump_standout(p, rng):
    """Small bounded attribute bump for a standout young camper."""
    try:
        if _is_goalie(p):
            attrs = ("goaltending", "goaltending")
        else:
            attrs = tuple(rng.sample(_SKATER_BUMP_ATTRS, 2))
        for a in attrs:
            cur = int(getattr(p, a, 0) or 0)
            setattr(p, a, min(99, cur + 1))
        p.camp_standout = True
        try:
            p.morale = max(1, min(100, int(getattr(p, "morale", 70)) + 5))
        except Exception:
            pass
        return attrs
    except Exception:
        return ()


def _close_camp(league, on_date, app=None, rng=None):
    year = on_date.year
    if int(getattr(league, "_camp_closed_year", 0) or 0) == year:
        return
    league._camp_closed_year = year
    rng = rng or random
    for team in (getattr(league, "teams", None) or []):
        if not _is_nhl_team(team):
            continue
        roster = list(getattr(team, "camp_roster", None) or [])
        for p in roster:
            try:
                ratings = list(getattr(p, "camp_ratings", None) or [])
                p.camp_avg = _avg(ratings)
            except Exception:
                continue
        # Development: standout youngsters earn a small bump; poor camps
        # cost a little morale (bounded).
        for p in roster:
            try:
                ratings = list(getattr(p, "camp_ratings", None) or [])
                age = int(getattr(p, "age", 99) or 99)
                avg = float(getattr(p, "camp_avg", 0.0) or 0.0)
                if (age <= STANDOUT_AGE_MAX and len(ratings) >= STANDOUT_MIN_GAMES
                        and avg >= STANDOUT_AVG):
                    _bump_standout(p, rng)
                elif len(ratings) >= STANDOUT_MIN_GAMES and avg <= 4.5:
                    p.morale = max(1, min(100, int(getattr(p, "morale", 70)) - 5))
            except Exception:
                continue
    # The user's camp report goes to the inbox (EHM-style camp news).
    if app is not None:
        try:
            _post_camp_report(league, on_date, app)
            app.add_news("Training camps close -- final cuts due next week.")
        except Exception:
            pass


def _fmt_line(p):
    try:
        ratings = list(getattr(p, "camp_ratings", None) or [])
        avg = float(getattr(p, "camp_avg", 0.0) or 0.0)
        rstr = ", ".join(f"{r:.1f}" for r in ratings) if ratings else "DNP"
        return (f"{getattr(p, 'full_name', '?')} "
                f"({getattr(getattr(p, 'primary_position', None), 'name', '')}, "
                f"{getattr(p, 'age', '?')}) -- avg {avg:.1f} [{rstr}]")
    except Exception:
        return "?"


def _post_camp_report(league, on_date, app):
    """Inbox the user their club's camp report: standouts, disappointments,
    prospects pushing for a roster spot, and the scrimmage log."""
    try:
        user_team = app.user_team
    except Exception:
        return
    roster = list(getattr(user_team, "camp_roster", None) or [])
    if not roster:
        return
    rated = [p for p in roster
             if len(getattr(p, "camp_ratings", None) or []) >= 2]
    rated.sort(key=lambda p: float(getattr(p, "camp_avg", 0.0) or 0.0),
               reverse=True)
    lines = [f"TRAINING CAMP REPORT -- {getattr(user_team, 'team_name', '')}",
             f"Camp closed {on_date.isoformat()}. "
             f"{len(roster)} players attended, "
             f"{len(getattr(user_team, 'camp_scrimmages', None) or [])} scrimmages.",
             ""]
    if rated:
        lines.append("TOP CAMP PERFORMERS:")
        for p in rated[:5]:
            lines.append("  * " + _fmt_line(p))
        lines.append("")
        lines.append("DISAPPOINTMENTS:")
        for p in rated[-3:]:
            lines.append("  * " + _fmt_line(p))
        lines.append("")
    pushing = [p for p in rated
               if int(getattr(p, "age", 99) or 99) <= 21
               and float(getattr(p, "camp_avg", 0.0) or 0.0) >= 7.0]
    if pushing:
        lines.append("PROSPECTS PUSHING FOR A ROSTER SPOT:")
        for p in pushing[:5]:
            lines.append("  * " + _fmt_line(p))
        lines.append("")
    scrims = list(getattr(user_team, "camp_scrimmages", None) or [])
    if scrims:
        lines.append("SCRIMMAGE RESULTS (Red vs White):")
        for s in scrims:
            stars = ", ".join(s.get("stars", []) or [])
            lines.append(f"  * {s.get('date', '')}: {s.get('red', 0)}-{s.get('white', 0)}"
                         + (f" -- 3 stars: {stars}" if stars else ""))
    content = "\n".join(lines)
    try:
        from game_classes import EmailMessage
        msg = EmailMessage(
            sender="Head Coach",
            sender_type="Staff",
            subject=f"Training Camp Report -- {on_date.year}",
            content=content,
            date_sent=on_date,
            is_important=True,
            category="Development",
            priority=3,
            game_date_sent=on_date,
        )
        user_team.inbox.add_message(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Daily entry point
# ---------------------------------------------------------------------------

def run_camp_day(league, on_date, app=None, rng=None):
    """Drive the camp calendar for one day. Safe to call every day."""
    try:
        if is_camp_open_day(on_date):
            _open_camp(league, on_date, app=app, rng=rng)
        # A save loaded mid-camp (opened year set, rosters missing) heals
        # itself: opening is idempotent per year.
        if is_camp_day(on_date):
            if int(getattr(league, "_camp_opened_year", 0) or 0) != on_date.year:
                _open_camp(league, on_date, app=app, rng=rng)
            if is_scrimmage_day(on_date):
                _run_scrimmages(league, on_date, app=app, rng=rng)
            if is_camp_close_day(on_date):
                _close_camp(league, on_date, app=app, rng=rng)
    except Exception:
        pass


def get_camp_table(team):
    """Rows for the TrainingCampView: (player, ratings, avg, standout)."""
    rows = []
    for p in (getattr(team, "camp_roster", None) or []):
        try:
            ratings = list(getattr(p, "camp_ratings", None) or [])
            avg = float(getattr(p, "camp_avg", 0.0) or 0.0)
            if not ratings:
                avg = _avg(ratings)
            rows.append((p, ratings, avg,
                         bool(getattr(p, "camp_standout", False))))
        except Exception:
            continue
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows
