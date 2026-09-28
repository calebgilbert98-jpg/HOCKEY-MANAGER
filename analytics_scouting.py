"""Analytics scouting for Puck Dynasty: the "right guy, wrong situation" puzzle.

The analytics department sees through surface stats to process: expected
goals, possession share, luck (PDO), workload. A skater with elite xGF%
and a 0.965 PDO on a lottery team is not a 45-point player; he's a
70-point player having a 45-point season.

But the game never hands you the answer. The finders below compute the
GROUND TRUTH -- what the numbers really say. What the USER sees is
filtered through their scouts: a scout's judging ability determines
whether they spot the real find, and whether they chase ghosts. An
analytical GM studies the raw numbers themselves (Advanced Stats tabs)
and solves the puzzle directly; a scout-reliant GM hires elite eyes and
follows their tips; an old-school GM trusts the eye test. All three are
valid play styles.

Scout ability -> correctness is direct and transparent:
- JPA 16-20 (elite): sees ~90% of real finds, ~5% false positives
- JPA 11-15 (good):  ~65% of real finds, ~15% false positives
- JPA  6-10 (avg):   ~35% of real finds, ~30% false positives
- JPA  1-5  (poor):  ~15% of real finds, ~45% false positives (sees ghosts)

Subtlety matters too: a 30-point value gap screams; an 8-point gap
whispers. Better scouts hear whispers.
"""

from typing import Any, Dict, List, Optional, Tuple

try:
    import advanced_metrics as am
    _HAS_AM = True
except Exception:
    _HAS_AM = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gp(p) -> int:
    return getattr(p, "games_played", 0) or 0


def _pts(p) -> int:
    return (getattr(p, "goals", 0) or 0) + (getattr(p, "assists", 0) or 0)


def _is_goalie(p) -> bool:
    pos = getattr(p, "primary_position", None)
    name = getattr(pos, "name", str(pos or "")).upper()
    return "GOAL" in name


def _team_pct(team) -> float:
    gp = getattr(team, "games_played", 0) or 0
    pts = getattr(team, "points", 0) or 0
    return (pts / (2 * gp)) if gp > 0 else 0.5


def _team_map(teams) -> Dict[str, Any]:
    return {getattr(t, "team_name", ""): t for t in (teams or [])}


def _age(p) -> int:
    return getattr(p, "age", 27) or 27


def _contract_years(p) -> int:
    c = getattr(p, "contract", None)
    return getattr(c, "years_remaining", 0) or 0


def _salary(p) -> int:
    c = getattr(p, "contract", None)
    return getattr(c, "salary", 0) or 0


# ---------------------------------------------------------------------------
# Buy-low finder
# ---------------------------------------------------------------------------

def _skater_value_signals(p, team_pct: float) -> Tuple[float, List[str], List[str]]:
    """Return (value_score, signals, risks) for a skater.

    value_score: estimated surplus -- how much better the underlying
    process is than the surface results suggest. Higher = bigger steal.
    """
    if not _HAS_AM:
        return 0.0, [], []
    try:
        m = am.skater_advanced(p)
    except Exception:
        return 0.0, [], []
    gp = _gp(p)
    goals = getattr(p, "goals", 0) or 0
    pts = _pts(p)

    score = 0.0
    signals: List[str] = []
    risks: List[str] = []

    # 1. Due for goals: individual xG well above actual goals.
    #    Finishers regress toward their xG; an 8-goal gap is ~2 months of luck.
    ixg_gap = m.ixg - goals
    if ixg_gap >= 8 and gp >= 25:
        score += min(30.0, ixg_gap * 1.5)
        signals.append(f"Due for goals: {m.ixg:.0f} ixG vs {goals} actual "
                       f"({ixg_gap:.0f} goals of bad finishing luck)")

    # 2. Snake-bitten driver: elite process, terrible luck.
    if m.pdo < 0.985 and m.xgf_pct >= 52.0 and gp >= 25:
        unluck = (0.985 - m.pdo) * 1000
        score += min(25.0, unluck * 1.2 + (m.xgf_pct - 52.0) * 1.5)
        signals.append(f"Snake-bitten: {m.xgf_pct:.1f}% xGF% but {m.pdo:.3f} PDO "
                       f"-- driving play, pucks aren't going in")

    # 3. Elite rate, buried situation: top-tier per-60 on a bad team.
    if m.p_per60 >= 2.6 and team_pct < 0.450 and gp >= 20:
        score += min(20.0, (m.p_per60 - 2.6) * 12.0 + (0.450 - team_pct) * 60.0)
        signals.append(f"Elite rate in a bad room: {m.p_per60:.2f} P/60 on a "
                       f"{team_pct:.3f} team -- production is real, help isn't")

    # 4. Process over results: strong two-way game, point total lags.
    #    (Catches the Selke-type who's about to get power-play time.)
    if m.xgf_pct >= 55.0 and m.cf_pct >= 55.0 and pts < gp * 0.75 and gp >= 25:
        score += min(15.0, (m.xgf_pct - 55.0) * 2.0)
        signals.append(f"Process over results: {m.xgf_pct:.1f}% xGF% / "
                       f"{m.cf_pct:.1f}% CF% but only {pts} pts in {gp} GP")

    # 5. Young driver: under-25 with top-decile process. The breakout bet.
    age = _age(p)
    if age <= 24 and m.xgf_pct >= 54.0 and gp >= 20:
        score += min(12.0, (24 - age) * 2.0 + (m.xgf_pct - 54.0))
        signals.append(f"Young driver: age {age} with {m.xgf_pct:.1f}% xGF% "
                       f"-- breakout curve ahead of production curve")

    # --- Risks (the puzzle must be fair) ---
    if gp < 30:
        risks.append(f"Small sample: only {gp} GP")
    if age >= 32:
        risks.append(f"Age curve: {age} -- process may be the peak, not the floor")
    if m.pdo > 1.015:
        risks.append(f"Some luck already baked in (PDO {m.pdo:.3f})")

    return round(score, 1), signals, risks


def _goalie_value_signals(p, team_pct: float) -> Tuple[float, List[str], List[str]]:
    """Value signals for a goaltender."""
    if not _HAS_AM:
        return 0.0, [], []
    try:
        m = am.goalie_advanced(p)
    except Exception:
        return 0.0, [], []
    gp = _gp(p)
    wins = getattr(p, "wins", 0) or 0

    score = 0.0
    signals: List[str] = []
    risks: List[str] = []

    # 1. Standing on his head: elite shot-stopping, no run support.
    if m.gsax >= 8.0 and team_pct < 0.475 and gp >= 20:
        score += min(30.0, m.gsax * 1.2 + (0.475 - team_pct) * 50.0)
        signals.append(f"Standing on his head: +{m.gsax:.1f} GSAx on a "
                       f"{team_pct:.3f} team -- wins ({wins}) lie, saves don't")

    # 2. High-danger wall: stops the hard ones; team hangs him out.
    if m.hdsv_pct >= 0.830 and m.sv_pct < 0.910 and gp >= 15:
        score += min(15.0, (m.hdsv_pct - 0.830) * 500.0)
        signals.append(f"High-danger wall: {m.hdsv_pct:.3f} HDSV% but "
                       f"{m.sv_pct:.3f} overall -- facing a shooting gallery")

    # 3. Workhorse undervalued: heavy workload, above-expected results.
    if m.sa_per60 >= 32.0 and m.gsax > 0 and gp >= 20:
        score += min(10.0, (m.sa_per60 - 32.0) * 1.5 + m.gsax * 0.3)
        signals.append(f"Workhorse: {m.sa_per60:.1f} SA/60 and still +{m.gsax:.1f} GSAx")

    if gp < 20:
        risks.append(f"Small sample: only {gp} GP")
    age = _age(p)
    if age >= 33:
        risks.append(f"Goalie age cliff: {age}")

    return round(score, 1), signals, risks


def find_buy_low(players: List[Any], teams: List[Any],
                 limit: int = 25, min_gp: int = 15,
                 exclude_team: str = "") -> List[Dict[str, Any]]:
    """League-wide buy-low scan: the right guy in the wrong situation.

    Ranks every skater and goalie by estimated surplus value -- how much
    better their underlying game is than their surface stats suggest.
    exclude_team: skip this team's players (usually the user's own roster).
    """
    tmap = _team_map(teams)
    out = []
    for p in players or []:
        tname = getattr(p, "team_name", "") or ""
        if exclude_team and tname == exclude_team:
            continue
        gp = _gp(p)
        if gp < min_gp:
            continue
        team = tmap.get(tname)
        tpct = _team_pct(team) if team is not None else 0.5
        if _is_goalie(p):
            score, signals, risks = _goalie_value_signals(p, tpct)
            kind = "G"
        else:
            score, signals, risks = _skater_value_signals(p, tpct)
            kind = "F/D"
        if score < 8.0 or not signals:
            continue
        out.append({
            "player": p,
            "name": getattr(p, "full_name", getattr(p, "name", "?")),
            "kind": kind,
            "team": tname,
            "team_pct": round(tpct, 3),
            "value_score": score,
            "signals": signals,
            "risks": risks,
            "age": _age(p),
            "salary": _salary(p),
            "years_left": _contract_years(p),
            "points": _pts(p),
            "gp": gp,
        })
    out.sort(key=lambda r: r["value_score"], reverse=True)
    return out[:limit]


# ---------------------------------------------------------------------------
# Sell-high finder (your own roster)
# ---------------------------------------------------------------------------

def find_sell_high(players: List[Any], limit: int = 15,
                   min_gp: int = 20) -> List[Dict[str, Any]]:
    """Your roster: who's running hot and about to regress.

    The other half of the puzzle. A 30-goal season built on a 1.030 PDO
    and 47% xGF% is a depreciating asset -- move him while the league
    still sees 30 goals.
    """
    out = []
    for p in players or []:
        gp = _gp(p)
        if gp < min_gp or _is_goalie(p):
            continue
        if not _HAS_AM:
            continue
        try:
            m = am.skater_advanced(p)
        except Exception:
            continue
        goals = getattr(p, "goals", 0) or 0
        pts = _pts(p)

        score = 0.0
        signals: List[str] = []

        # 1. Running hot: sky-high PDO on mediocre process.
        if m.pdo >= 1.015 and m.xgf_pct < 50.0:
            score += min(25.0, (m.pdo - 1.015) * 800.0 + (50.0 - m.xgf_pct))
            signals.append(f"Running hot: {m.pdo:.3f} PDO on {m.xgf_pct:.1f}% xGF% "
                           f"-- luck is doing the heavy lifting")

        # 2. Finishing above xG: goals well ahead of chance quality.
        xg_gap = goals - m.ixg
        if xg_gap >= 8:
            score += min(20.0, xg_gap * 1.2)
            signals.append(f"Finishing above xG: {goals} goals on {m.ixg:.0f} ixG "
                           f"({m.sh_pct:.1f}% SH%) -- shooting % will cool")

        # 3. Results over process at even strength.
        if m.pdo >= 1.010 and pts >= gp * 0.8 and m.cf_pct < 48.0:
            score += 10.0
            signals.append(f"Results over process: {pts} pts in {gp} GP but "
                           f"{m.cf_pct:.1f}% CF% -- getting outplayed and outscored")

        if score < 8.0 or not signals:
            continue
        out.append({
            "player": p,
            "name": getattr(p, "full_name", getattr(p, "name", "?")),
            "team": getattr(p, "team_name", ""),
            "value_score": round(score, 1),
            "signals": signals,
            "age": _age(p),
            "salary": _salary(p),
            "years_left": _contract_years(p),
            "points": pts,
            "gp": gp,
        })
    out.sort(key=lambda r: r["value_score"], reverse=True)
    return out[:limit]


# ---------------------------------------------------------------------------
# Fit: does he make YOUR team better?
# ---------------------------------------------------------------------------

def fit_note(candidate: Dict[str, Any], user_team: Any) -> str:
    """One-line fit assessment: why this player helps this team.

    "Among other things" -- analytics find the guy, but fit, cap, and
    need decide the deal.
    """
    p = candidate["player"]
    notes = []
    # Positional need: thin position on the user roster?
    pos = getattr(getattr(p, "primary_position", None), "name",
                  str(getattr(p, "primary_position", "")))
    try:
        roster = list(getattr(user_team, "roster", []) or [])
        same_pos = [r for r in roster
                    if getattr(getattr(r, "primary_position", None), "name", "") == pos]
        if len(same_pos) <= 2:
            notes.append(f"Fills a thin {pos} group ({len(same_pos)} on roster)")
    except Exception:
        pass
    # Cap: is the price right for the production?
    sal = candidate.get("salary", 0) or 0
    pts = candidate.get("points", 0) or 0
    if sal and pts:
        per_m = pts / (sal / 1_000_000) if sal else 0
        if per_m >= 12:
            notes.append(f"Cap bargain: ~{per_m:.0f} pts per $1M")
        elif per_m < 6:
            notes.append(f"Pricey: ~{per_m:.0f} pts per $1M -- negotiate")
    # Contender vs rebuild timeline
    age = candidate.get("age", 27)
    try:
        upct = _team_pct(user_team)
        if upct >= 0.550 and age <= 30:
            notes.append("Timeline fit: win-now piece in his prime")
        elif upct < 0.450 and age <= 25:
            notes.append("Timeline fit: young core piece for the rebuild")
        elif upct >= 0.550 and age > 32:
            notes.append("Timeline risk: contender window vs age curve")
    except Exception:
        pass
    return "; ".join(notes) if notes else "No strong fit signal -- trust the process numbers"


# ---------------------------------------------------------------------------
# Media storylines: the press notices what the numbers say
# ---------------------------------------------------------------------------

def analytics_storylines(players: List[Any], teams: List[Any],
                         limit: int = 6) -> List[Dict[str, Any]]:
    """Generate media storyline seeds from advanced analytics.

    The press corps reads the same numbers the analytics department does.
    A goalie with +20 GSAx on a lottery team becomes "is he wasting his
    prime?"; a rookie with elite xGF% becomes the breakout watch. These
    are seeds -- the media system decides which ones catch fire.

    Returns dicts with title/description/intensity/players_involved,
    ready for the media system to adopt.
    """
    stories: List[Dict[str, Any]] = []
    if not _HAS_AM:
        return stories
    tmap = _team_map(teams)

    for p in players or []:
        if len(stories) >= limit * 3:
            break
        gp = _gp(p)
        if gp < 20:
            continue
        tname = getattr(p, "team_name", "") or ""
        team = tmap.get(tname)
        tpct = _team_pct(team) if team is not None else 0.5
        pname = getattr(p, "full_name", getattr(p, "name", "?"))

        try:
            if _is_goalie(p):
                m = am.goalie_advanced(p)
                # Wasting his prime: elite shot-stopping, lottery team.
                if m.gsax >= 15.0 and tpct < 0.450:
                    stories.append({
                        "title": f"Is {pname} wasting his prime in {tname}?",
                        "description":
                            f"+{m.gsax:.1f} goals saved above expected on a "
                            f"{tpct:.3f} club. Contenders are circling.",
                        "intensity": 7,
                        "players_involved": [pname],
                        "kind": "wasted_prime_goalie",
                    })
                # Due for regression: gaudy record, shaky underlying.
                elif m.gsax <= -8.0 and gp >= 25:
                    stories.append({
                        "title": f"{pname}'s numbers are a house of cards",
                        "description":
                            f"{m.gsax:.1f} GSAx despite the record -- the "
                            f"analytics crowd says regression is coming.",
                        "intensity": 5,
                        "players_involved": [pname],
                        "kind": "goalie_regression",
                    })
            else:
                m = am.skater_advanced(p)
                # Breakout watch: young, elite process, points haven't caught up.
                if _age(p) <= 24 and m.xgf_pct >= 55.0 and _pts(p) < gp * 0.7:
                    stories.append({
                        "title": f"Breakout watch: {pname}",
                        "description":
                            f"Age {_age(p)} with {m.xgf_pct:.1f}% xGF% -- "
                            f"the underlying game is top-line, the scoresheet "
                            f"hasn't caught up yet.",
                        "intensity": 6,
                        "players_involved": [pname],
                        "kind": "breakout_watch",
                    })
                # Snake-bitten star: the goals will come.
                elif m.ixg - (getattr(p, "goals", 0) or 0) >= 10 and gp >= 30:
                    gap = m.ixg - (getattr(p, "goals", 0) or 0)
                    stories.append({
                        "title": f"{pname} can't buy a goal",
                        "description":
                            f"{m.ixg:.0f} expected goals, {getattr(p, 'goals', 0)} "
                            f"actual. {gap:.0f} goals of bad luck -- or is the "
                            f"finishing really this cold?",
                        "intensity": 5,
                        "players_involved": [pname],
                        "kind": "snake_bitten",
                    })
                # Carrying the team: elite two-way on a bad club.
                elif m.xgf_pct >= 57.0 and tpct < 0.450 and _pts(p) >= gp * 0.8:
                    stories.append({
                        "title": f"{pname} is doing it all alone",
                        "description":
                            f"{m.xgf_pct:.1f}% xGF% while {tname} drowns at "
                            f"{tpct:.3f}. One man can't outskate a roster.",
                        "intensity": 6,
                        "players_involved": [pname],
                        "kind": "carrying_bad_team",
                    })
        except Exception:
            continue

    # Sort by intensity, return the hottest.
    stories.sort(key=lambda s: s["intensity"], reverse=True)
    return stories[:limit]


def _analytics_story_log(media_system) -> dict:
    """Dedup log: {(kind, player_id): iso_date} of published analytics stories."""
    try:
        log = getattr(media_system, "analytics_story_log", None)
        if log is None:
            log = {}
            media_system.analytics_story_log = log
        return log
    except Exception:
        return {}


def _season_phase(month: int):
    """Which analytics narratives fit this point of the season.

    Returns (allowed_kinds, priority_kinds). September (preseason) is
    skipped entirely -- there is no sample to analyze yet.
    """
    if month == 9:
        return None  # preseason: no stories
    if month in (10, 11):
        return ({"breakout_watch", "snake_bitten"},
                ["breakout_watch", "snake_bitten"])
    if month in (12, 1):
        return ({"breakout_watch", "snake_bitten", "goalie_regression",
                 "carrying_bad_team", "wasted_prime_goalie"},
                ["breakout_watch", "wasted_prime_goalie", "snake_bitten",
                 "carrying_bad_team", "goalie_regression"])
    if month in (2, 3):
        # Deadline approach: "is he available?" narratives lead.
        return ({"wasted_prime_goalie", "goalie_regression",
                 "carrying_bad_team", "snake_bitten"},
                ["wasted_prime_goalie", "carrying_bad_team",
                 "goalie_regression", "snake_bitten"])
    # Apr+: playoffs -- only stakes stories.
    return ({"carrying_bad_team", "wasted_prime_goalie"},
            ["carrying_bad_team", "wasted_prime_goalie"])


# Minimum significance bar per story kind. A story must clear its bar
# AND intensity >= 5 to reach the press; anything weaker stays in the
# analytics department's notebooks.
_STORY_SIGNIFICANCE = {
    "wasted_prime_goalie": 15.0,   # GSAx
    "goalie_regression": 8.0,      # |GSAx|
    "breakout_watch": 55.0,        # xGF%
    "snake_bitten": 10.0,          # ixG - goals gap
    "carrying_bad_team": 57.0,     # xGF%
}

_PLAYER_COOLDOWN_DAYS = 45
_KIND_ACTIVE_CAP = 2


def _story_active(media_system, kind: str, now) -> int:
    """How many analytics stories of this kind are currently active."""
    n = 0
    try:
        for sl in getattr(media_system, "storylines", []) or []:
            sid = getattr(sl, "id", "") or ""
            if not sid.startswith("analytics_"):
                continue
            created = getattr(sl, "created_date", None)
            dur = int(getattr(sl, "duration_days", 21) or 21)
            try:
                alive = (now - created).days < dur if (now and created) else True
            except Exception:
                alive = True
            if not alive:
                continue
            title = (getattr(sl, "title", "") or "").lower()
            # Kind is encoded in the seed; match loosely on title markers.
            markers = {
                "wasted_prime_goalie": "wasting his prime",
                "goalie_regression": "house of cards",
                "breakout_watch": "breakout watch",
                "snake_bitten": "can't buy a goal",
                "carrying_bad_team": "all alone",
            }
            if markers.get(kind, "") in title:
                n += 1
    except Exception:
        pass
    return n


def publish_analytics_storylines(media_system: Any, players: List[Any],
                                 teams: List[Any], game_manager: Any = None,
                                 limit: int = 4) -> int:
    """Push analytics storylines into the media system.

    Season-aware cadence (call monthly, e.g. the 15th):
    - Preseason: nothing -- no sample yet.
    - Early season: breakout watch / snake-bitten.
    - Deadline approach: wasted-prime (trade bait) leads.
    - Playoffs: only stakes stories.

    Dedup: a (kind, player) combo never publishes twice; each player
    has a 45-day cooldown between analytics stories; at most 2 active
    stories of the same kind league-wide.

    Significance: intensity >= 5 AND the kind's statistical bar must
    clear, or the story stays in the analytics department's notebook.
    """
    try:
        import datetime
        now = None
        try:
            now = game_manager.current_date if game_manager else None
        except Exception:
            now = None
        month = now.month if now is not None else 1
        phase = _season_phase(month)
        if phase is None:
            return 0
        allowed, priority = phase

        seeds = analytics_storylines(players, teams, limit=limit * 3)
        if not seeds or media_system is None:
            return 0
        from media_system import MediaStoryline, StorylineType

        log = _analytics_story_log(media_system)

        def _pid_of(seed) -> int:
            try:
                nm = (seed.get("players_involved") or ["?"])[0]
                for p in players or []:
                    pn = getattr(p, "full_name", getattr(p, "name", "?"))
                    if pn == nm:
                        return int(getattr(p, "id", -1) or -1)
            except Exception:
                pass
            return -1

        def _cooled_down(pid: int) -> bool:
            try:
                for (k, q), dstr in log.items():
                    if q != pid:
                        continue
                    d = datetime.date.fromisoformat(dstr)
                    if now is not None and (now - d).days < _PLAYER_COOLDOWN_DAYS:
                        return False
                return True
            except Exception:
                return True

        def _significant(seed) -> bool:
            try:
                if int(seed.get("intensity", 0) or 0) < 5:
                    return False
                return True  # generator already enforces per-kind bars
            except Exception:
                return False

        # Order by phase priority, then intensity.
        def _rank(seed):
            kind = seed.get("kind", "")
            try:
                pri = priority.index(kind)
            except ValueError:
                pri = len(priority)
            return (pri, -int(seed.get("intensity", 0) or 0))
        seeds.sort(key=_rank)

        added = 0
        for s in seeds:
            if added >= limit:
                break
            kind = s.get("kind", "")
            if kind not in allowed:
                continue
            if not _significant(s):
                continue
            pid = _pid_of(s)
            if (kind, pid) in log:
                continue  # never repeat a (kind, player) combo
            if not _cooled_down(pid):
                continue
            if _story_active(media_system, kind, now) >= _KIND_ACTIVE_CAP:
                continue
            try:
                sl = MediaStoryline(
                    id=f"analytics_{kind}_{pid}_{(now or datetime.date.today()).isoformat()}",
                    type=StorylineType.PLAYER_DEVELOPMENT,
                    title=s["title"],
                    description=s["description"],
                    players_involved=s["players_involved"],
                    intensity=s["intensity"],
                    duration_days=21,
                    created_date=now or datetime.date.today(),
                    last_mentioned=now or datetime.date.today(),
                )
                media_system.storylines.append(sl)
                log[(kind, pid)] = (now or datetime.date.today()).isoformat()
                added += 1
            except Exception:
                continue
        return added
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Scout perception: the filter between truth and the user
# ---------------------------------------------------------------------------

def _scout_jpa(scout) -> int:
    """Pro-scouting eye on the canonical 1-20 EHM scale.

    Staff attributes are native 1-100; the tip/detection math below
    was tuned on the 1-20 scale (16-20 ~ elite, 1-5 ~ guesswork),
    so normalize once, here: 80/100 -> 16/20, 50 -> 10, 5 -> 1.
    Every consumer of this function gets the tuned scale.
    """
    try:
        raw = int(getattr(scout, "judging_player_ability", 50) or 50)
    except (TypeError, ValueError):
        raw = 50
    raw = max(1, min(100, raw))
    return max(1, min(20, int(round(raw / 5.0))))


def _detect_chance(jpa: int, value_score: float) -> float:
    """P(scout spots this particular find).

    Elite scouts see almost everything; average scouts only the obvious.
    Subtlety = value_score: a 30-point gap screams, an 8-point gap whispers.
    """
    # Base by JPA tier, then subtlety shifts it.
    base = {20: 0.95, 19: 0.93, 18: 0.90, 17: 0.88, 16: 0.85,
            15: 0.75, 14: 0.70, 13: 0.65, 12: 0.60, 11: 0.55,
            10: 0.45, 9: 0.40, 8: 0.35, 7: 0.30, 6: 0.25,
            5: 0.20, 4: 0.17, 3: 0.14, 2: 0.12, 1: 0.10}.get(jpa, 0.45)
    # Obvious finds (+20%) are easier; subtle ones (-15%) harder.
    obvious = max(-0.15, min(0.20, (value_score - 15.0) / 100.0))
    return max(0.05, min(0.98, base + obvious))


def _false_positive_chance(jpa: int) -> float:
    """P(scout flags a fairly-priced player as a find). Bad scouts see ghosts."""
    if jpa >= 16:
        return 0.05
    if jpa >= 11:
        return 0.15
    if jpa >= 6:
        return 0.30
    return 0.45


def scout_value_tips(scout: Any, players: List[Any], teams: List[Any],
                     user_team: Any = None, limit: int = 3,
                     rng=None) -> List[Dict[str, Any]]:
    """A single scout's value tips: truth filtered through their ability.

    The scout scans the league's pro talent and reports who THEY think
    is undervalued. Good scouts mostly name real finds; bad scouts name
    ghosts -- and miss the real ones. Each tip carries the scout's name
    so the user learns who to trust.

    This is where play styles diverge: the analytical GM cross-checks
    tips against the raw numbers; the trusting GM follows them blind;
    the skeptic ignores them entirely.
    """
    import random as _r
    rng = rng or _r
    jpa = _scout_jpa(scout)
    sname = getattr(scout, "full_name", getattr(scout, "name", "Your scout"))
    uname = getattr(user_team, "team_name", "") if user_team else ""

    truth = find_buy_low(players, teams, limit=40, exclude_team=uname)
    truth_ids = {id(c["player"]) for c in truth}

    tips: List[Dict[str, Any]] = []

    # True positives: the scout spots some fraction of real finds.
    for c in truth:
        if len(tips) >= limit:
            break
        if rng.random() < _detect_chance(jpa, c["value_score"]):
            tips.append({
                "player": c["player"],
                "name": c["name"],
                "team": c["team"],
                "scout": sname,
                "scout_jpa": jpa,
                "correct": True,
                # The scout states the real signal -- they saw it clearly.
                "reason": c["signals"][0] if c["signals"] else "Underlying numbers stand out",
                "risks": c["risks"],
                "confidence": "High" if jpa >= 16 else "Medium" if jpa >= 11 else "Low",
            })

    # False positives: bad scouts chase ghosts.
    if len(tips) < limit and rng.random() < _false_positive_chance(jpa):
        # Pick a fairly-priced player (not a real find) as the ghost.
        candidates = [p for p in (players or [])
                      if id(p) not in truth_ids
                      and (getattr(p, "team_name", "") or "") != uname
                      and _gp(p) >= 20 and not _is_goalie(p)]
        if candidates:
            ghost = rng.choice(candidates)
            gname = getattr(ghost, "full_name", getattr(ghost, "name", "?"))
            # The ghost's "reason" is plausible-sounding but wrong --
            # the numbers don't actually support it.
            ghost_reasons = [
                "I love his compete level -- the points are coming",
                "He passes the eye test every shift",
                "His underlying game is better than the scoresheet shows",
                "Trust me on this one -- he's a gamer",
            ]
            tips.append({
                "player": ghost,
                "name": gname,
                "team": getattr(ghost, "team_name", "?"),
                "scout": sname,
                "scout_jpa": jpa,
                "correct": False,
                "reason": rng.choice(ghost_reasons),
                "risks": ["Scout's call -- verify against the numbers yourself"],
                "confidence": "Low",
            })

    return tips[:limit]


def scout_ability_label(jpa: int) -> str:
    """Human-readable scout tier for the UI."""
    if jpa >= 16:
        return "Elite eye"
    if jpa >= 11:
        return "Good eye"
    if jpa >= 6:
        return "Average eye"
    return "Poor eye"


def scout_sell_high_tips(scout: Any, team: Any,
                         limit: int = 2, rng=None) -> List[Dict[str, Any]]:
    """A scout's sell-high reads on their OWN team's roster.

    The mirror of scout_value_tips: who does the scout believe is
    overvalued and should be moved while the league still sees the
    surface production? Same perception filter -- good scouts name real
    regression candidates; bad scouts want to dump the wrong guys.

    AI GMs use this to shop veterans at peak value, exactly like a
    human GM would after reading the same numbers.
    """
    import random as _r
    rng = rng or _r
    jpa = _scout_jpa(scout)
    sname = getattr(scout, "full_name", getattr(scout, "name", "Your scout"))
    roster = list(getattr(team, "roster", []) or [])
    truth = find_sell_high(roster, limit=20)
    truth_ids = {id(c["player"]) for c in truth}

    tips: List[Dict[str, Any]] = []
    for c in truth:
        if len(tips) >= limit:
            break
        if rng.random() < _detect_chance(jpa, c["value_score"]):
            tips.append({
                "player": c["player"],
                "name": c["name"],
                "scout": sname,
                "scout_jpa": jpa,
                "correct": True,
                "reason": c["signals"][0] if c["signals"] else "Selling high window",
                "confidence": "High" if jpa >= 16 else "Medium" if jpa >= 11 else "Low",
            })
    # Bad scouts want to sell the wrong guys (ghost sell tips).
    if len(tips) < limit and rng.random() < _false_positive_chance(jpa):
        candidates = [p for p in roster
                      if id(p) not in truth_ids and _gp(p) >= 20
                      and not _is_goalie(p)]
        if candidates:
            ghost = rng.choice(candidates)
            gname = getattr(ghost, "full_name", getattr(ghost, "name", "?"))
            tips.append({
                "player": ghost,
                "name": gname,
                "scout": sname,
                "scout_jpa": jpa,
                "correct": False,
                "reason": "I think we've seen his best hockey",
                "confidence": "Low",
            })
    return tips[:limit]


# ======================================================================
# WAVE 1 -- INFORMATION ASYMMETRY
# "Analytics should create a puzzle, not solve it."
#
# Four systems, one pipeline:
#   Scout tip -> User hypothesis -> Trade bet -> Performance window
#   -> Reputation + story
#
# 1. Scout track records: every past tip is graded against what happened
#    later. Users see samples and hit rates -- never hidden JPA.
# 2. Analytics department: department quality controls confidence
#    intervals, data lag and noise in the numbers the user SEES. It
#    never touches player outcomes or ground-truth analysis.
# 3. AI arms race: AI clubs evaluate, renew and poach scouting staff.
#    Their reads improve only when their people improve.
# 4. Market ecology: trade AI adopts process metrics by organizational
#    philosophy and staff quality, then regresses on leadership change.
#    The league never converges on one formula.
#
# Design law: never show "buy low" / "sell high". Show evidence,
# uncertainty, provenance, and the people responsible for the read.
# ======================================================================

TIP_GRADE_WINDOW_DAYS = 40
TIP_GRADE_MIN_GP_SKATER = 15
TIP_GRADE_MIN_GP_GOALIE = 10

_PRO_SCOUT_ROLES = None


def _pro_roles():
    global _PRO_SCOUT_ROLES
    if _PRO_SCOUT_ROLES is None:
        try:
            from game_classes import StaffRole
            _PRO_SCOUT_ROLES = {StaffRole.HEAD_SCOUT,
                                StaffRole.PROFESSIONAL_SCOUT}
        except Exception:
            _PRO_SCOUT_ROLES = set()
    return _PRO_SCOUT_ROLES


def ensure_analytics_fields(entity: Any) -> None:
    """Backfill wave-1 fields on entities loaded from old saves.

    Old pickles predate these fields; without this, attribute access
    raises AttributeError. Safe to call on every load / every tick.
    """
    try:
        if hasattr(entity, "role") or hasattr(
                entity, "judging_player_ability"):  # Staff / scout-like
            if not hasattr(entity, "tip_record"):
                entity.tip_record = {"calls": 0, "hits": 0}
            if not hasattr(entity, "tip_history"):
                entity.tip_history = []
        if hasattr(entity, "roster"):  # Team
            if not hasattr(entity, "tip_ledger"):
                entity.tip_ledger = {}
            if not hasattr(entity, "sell_watch"):
                entity.sell_watch = {}
            if not hasattr(entity, "analytics_quality"):
                entity.analytics_quality = 35
            if not hasattr(entity, "analytics_philosophy"):
                entity.analytics_philosophy = 30.0
            if not hasattr(entity, "philosophy_baseline"):
                entity.philosophy_baseline = float(
                    getattr(entity, "analytics_philosophy", 30.0) or 30.0)
            if not hasattr(entity, "_prev_gm_name"):
                entity._prev_gm_name = ""
            if not hasattr(entity, "_analytics_snapshot"):
                entity._analytics_snapshot = {}
    except Exception:
        pass


def seed_analytics_identities(teams: List[Any], rng=None) -> None:
    """Give each club its own analytics identity at league creation.

    Quality and philosophy vary club to club -- old-school organizations
    and analytics-heavy ones both exist on day one, and neither is the
    league default. Called once per new league.
    """
    import random as _r
    rng = rng or _r
    for t in teams:
        try:
            ensure_analytics_fields(t)
            t.analytics_quality = int(rng.randint(20, 70))
            philo = float(rng.uniform(15, 60))
            t.analytics_philosophy = philo
            t.philosophy_baseline = philo
            t._prev_gm_name = getattr(t, "gm_name", "") or ""
        except Exception:
            pass


def find_scout_by_id(team: Any, scout_id: str) -> Optional[Any]:
    """Resolve a scout id back to the Staff object on a team."""
    try:
        for s in list(getattr(team, "staff", []) or []):
            if getattr(s, "id", None) == scout_id:
                return s
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------
# 1. Scout track records
# ----------------------------------------------------------------------

def record_tip_call(scout: Any, team: Any, kind: str, player: Any,
                    date_str: str, reason: str = "") -> Optional[str]:
    """File a tip in the team's ledger and credit the scout with a call.

    kind: "buy" | "sell". Snapshots the player's pre-tip pace so the
    call can be graded against what happens later. Returns the ledger
    key, or None if it could not be filed.
    """
    try:
        ensure_analytics_fields(scout)
        ensure_analytics_fields(team)
        pid = getattr(player, "id", id(player))
        key = f"{kind}:{pid}:{date_str}"
        ledger = team.tip_ledger
        if key in ledger:
            return key
        try:
            from game_classes import PlayerPosition
            is_goalie = (getattr(player, "primary_position", None)
                         == PlayerPosition.GOALIE)
        except Exception:
            is_goalie = False
        gp = int(getattr(player, "games_played", 0) or 0)
        if is_goalie:
            sa = int(getattr(player, "shots_against", 0) or 0)
            sv = int(getattr(player, "saves", 0) or 0)
            pre_sv = (sv / sa) if sa > 0 else None
            pre_pgp = 0.0
        else:
            pts = int(getattr(player, "goals", 0) or 0) + int(
                getattr(player, "assists", 0) or 0)
            pre_pgp = (pts / gp) if gp > 0 else 0.0
            pre_sv = None
        pname = getattr(player, "full_name", getattr(player, "name", "?"))
        ledger[key] = {
            "scout_id": getattr(scout, "id", ""),
            "scout_name": getattr(scout, "full_name",
                                  getattr(scout, "name", "?")),
            "player_id": pid,
            "player_name": pname,
            "kind": kind,
            "date": date_str,
            "reason": str(reason or ""),
            "is_goalie": bool(is_goalie),
            "pre_gp": gp,
            "pre_pgp": float(pre_pgp),
            "pre_sv": pre_sv,
        }
        rec = scout.tip_record
        rec["calls"] = int(rec.get("calls", 0) or 0) + 1
        return key
    except Exception:
        return None


def grade_scout_call(scout: Any, result: str, player_name: str,
                     kind: str, date_str: str) -> None:
    """Grade one of a scout's calls: result is "hit" or "miss".

    Hits build the record; misses are recorded too -- a famous veteran
    gets exposed by the same ledger that builds a young scout's name.
    """
    try:
        ensure_analytics_fields(scout)
        rec = scout.tip_record
        if result == "hit":
            rec["hits"] = int(rec.get("hits", 0) or 0) + 1
        hist = scout.tip_history
        hist.append({"player_name": player_name, "kind": kind,
                     "result": result, "date": date_str})
        del hist[:-12]
    except Exception:
        pass


def scout_record_line(scout: Any) -> str:
    """User-facing track record. Samples and hit rates -- never JPA."""
    try:
        ensure_analytics_fields(scout)
        rec = getattr(scout, "tip_record", None) or {}
        calls = int(rec.get("calls", 0) or 0)
        hits = int(rec.get("hits", 0) or 0)
        if calls <= 0:
            return "no graded calls yet"
        pct = int(round(100.0 * hits / calls))
        return f"{hits} hits in {calls} graded calls ({pct}%)"
    except Exception:
        return "no graded calls yet"


def _player_pace(player: Any, is_goalie: bool):
    """Current (gp, ppg, sv%) triple for grading."""
    gp = int(getattr(player, "games_played", 0) or 0)
    if is_goalie:
        sa = int(getattr(player, "shots_against", 0) or 0)
        sv = int(getattr(player, "saves", 0) or 0)
        return gp, 0.0, (sv / sa) if sa > 0 else None
    pts = int(getattr(player, "goals", 0) or 0) + int(
        getattr(player, "assists", 0) or 0)
    return gp, (pts / gp) if gp > 0 else 0.0, None


def mark_tip_acted_on(team: Any, kind: str, player_id: Any,
                      date_str: str) -> None:
    """Mark a team's open ledger reads on a player as acted on.

    Called when a trade consumes a tip (buy-tip acquisition, sell-tip
    move). The steal/sell watch grades that call against the post-trade
    window -- grade_tip_ledger() must skip it so the scout isn't graded
    twice for the same call. Idempotent.
    """
    try:
        ensure_analytics_fields(team)
        ledger = team.tip_ledger
        for e in list(ledger.values()):
            try:
                if (str(e.get("kind", "")) == str(kind)
                        and e.get("player_id") == player_id
                        and not e.get("acted_on")):
                    e["acted_on"] = str(date_str)
            except Exception:
                continue
    except Exception:
        pass


def grade_tip_ledger(teams: List[Any], date_str: str) -> Dict[str, int]:
    """Grade every ledger tip old enough to judge. Called monthly.

    Tips acted on (acquired buy-tips, traded sell-tips) are graded by
    the steal/sell watches instead -- this handles the rest: reads the
    GM never bet on, judged purely on whether production moved the way
    the scout said it would. Returns {"hits": n, "misses": n}.
    """
    from datetime import date as _date
    out = {"hits": 0, "misses": 0}
    try:
        as_of = _date.fromisoformat(date_str)
    except Exception:
        return out
    # Player lookup across every roster (players change teams).
    by_id: Dict[Any, Any] = {}
    for t in teams or []:
        for p in list(getattr(t, "roster", []) or []):
            by_id[getattr(p, "id", id(p))] = p
    for team in teams or []:
        try:
            ensure_analytics_fields(team)
            ledger = team.tip_ledger
            for key in list(ledger.keys()):
                e = ledger[key]
                try:
                    filed = _date.fromisoformat(str(e.get("date", date_str)))
                except Exception:
                    del ledger[key]
                    continue
                if (as_of - filed).days < TIP_GRADE_WINDOW_DAYS:
                    continue
                if e.get("acted_on"):
                    # The GM bet on this read -- the steal/sell watch
                    # owns the grade, so the ledger never grades it
                    # twice. Retire the entry once mature; the watch
                    # entry itself is independent of the ledger.
                    if (as_of - filed).days >= TIP_GRADE_WINDOW_DAYS:
                        del ledger[key]
                    continue
                player = by_id.get(e.get("player_id"))
                if player is None:
                    # Can't observe him -- drop, don't punish the scout.
                    del ledger[key]
                    continue
                is_goalie = bool(e.get("is_goalie"))
                gp_now, ppg_now, sv_now = _player_pace(player, is_goalie)
                gp_then = int(e.get("pre_gp", 0) or 0)
                window_gp = gp_now - gp_then
                if window_gp < 0:
                    # Season rollover: re-baseline, keep watching.
                    e["pre_gp"] = gp_now
                    e["pre_pgp"] = ppg_now
                    e["pre_sv"] = sv_now
                    e["date"] = date_str
                    continue
                min_gp = (TIP_GRADE_MIN_GP_GOALIE if is_goalie
                          else TIP_GRADE_MIN_GP_SKATER)
                if window_gp < min_gp:
                    continue  # not enough evidence yet; keep the tip open
                kind = e.get("kind", "buy")
                hit = False
                if is_goalie:
                    pre_sv = e.get("pre_sv")
                    if pre_sv is not None and sv_now is not None:
                        d = sv_now - pre_sv
                        hit = d >= 0.010 if kind == "buy" else d <= -0.010
                else:
                    pre = float(e.get("pre_pgp", 0.0) or 0.0)
                    if kind == "buy":
                        hit = ((ppg_now - pre) >= 0.25) or (ppg_now >= 0.80)
                    else:
                        hit = (pre > 0.15) and (ppg_now <= pre * 0.75)
                scout = find_scout_by_id(team, e.get("scout_id", ""))
                if scout is not None:
                    grade_scout_call(
                        scout, "hit" if hit else "miss",
                        str(e.get("player_name", "?")), kind, date_str)
                out["hits" if hit else "misses"] += 1
                del ledger[key]
        except Exception:
            pass
    return out


# ----------------------------------------------------------------------
# 2. Analytics department (display-only lens)
# ----------------------------------------------------------------------

def analytics_director_quality(staff: Any) -> int:
    """Department quality implied by one analytics director's attributes.

    0-100 from the attributes that actually drive the work: reading
    players, tactical understanding, adaptability. All 1-100 scales.
    """
    try:
        jpa = float(getattr(staff, "judging_player_ability", 50) or 50)
        tk = float(getattr(staff, "tactical_knowledge", 50) or 50)
        ad = float(getattr(staff, "adaptability", 50) or 50)
        return int(max(5, min(99, round((jpa + tk + ad) / 3.0))))
    except Exception:
        return 35


def refresh_analytics_quality(team: Any) -> int:
    """Recompute a club's department quality from its analytics staff.

    Hiring a real analytics director upgrades the lens; losing him
    drops the club back toward a bare-bones baseline. Never touches
    player outcomes -- only what the user sees.
    """
    try:
        ensure_analytics_fields(team)
        try:
            from game_classes import StaffRole
            want = StaffRole.ANALYTICS_DIRECTOR
        except Exception:
            want = None
        best = 0
        if want is not None:
            for s in list(getattr(team, "staff", []) or []):
                if getattr(s, "role", None) == want:
                    best = max(best, analytics_director_quality(s))
        team.analytics_quality = int(best if best > 0 else 25)
        # New lens, stale snapshot: force a rebuild on next view.
        team._analytics_snapshot = {}
        return int(team.analytics_quality)
    except Exception:
        return 35


def department_tier_label(quality: int) -> str:
    """Honest label for the department behind the numbers."""
    try:
        q = int(quality)
    except Exception:
        q = 35
    if q >= 75:
        return "Elite analytics department"
    if q >= 50:
        return "Solid analytics department"
    if q >= 30:
        return "Thin analytics department"
    return "Bare-bones analytics operation"


# ----------------------------------------------------------------------
# 4. Market ecology -- philosophy drift, leadership regress
# ----------------------------------------------------------------------

def nudge_philosophy(team: Any, delta: float) -> float:
    """Event-driven philosophy shift, clamped and anti-convergent.

    Evidence moves a club's formula, but slowly and never past the
    guardrails -- the league must never converge on one formula.
    """
    try:
        ensure_analytics_fields(team)
        p = float(getattr(team, "analytics_philosophy", 30.0) or 30.0)
        p = max(5.0, min(95.0, p + float(delta)))
        team.analytics_philosophy = p
        return p
    except Exception:
        return 30.0


def tick_analytics_philosophy(league: Any) -> None:
    """Monthly market-ecology tick. Called on the 1st.

    - Slow drift back toward each club's organizational baseline
      (the anti-convergence spring).
    - Leadership change regress: a new GM brings his own formula, so
      the club's philosophy jumps partway to a fresh draw.
    """
    import random as _r
    try:
        teams = list(getattr(league, "teams", []) or [])
    except Exception:
        return
    for team in teams:
        try:
            ensure_analytics_fields(team)
            gm = getattr(team, "gm_name", "") or ""
            prev = getattr(team, "_prev_gm_name", "") or ""
            if prev and gm and gm != prev:
                fresh = _r.uniform(15, 70)
                cur = float(team.analytics_philosophy or 30.0)
                team.analytics_philosophy = max(
                    5.0, min(95.0, 0.5 * cur + 0.5 * fresh))
                team.philosophy_baseline = fresh
            team._prev_gm_name = gm
            base = float(team.philosophy_baseline or 30.0)
            cur = float(team.analytics_philosophy or 30.0)
            team.analytics_philosophy = cur + (base - cur) * 0.05
        except Exception:
            pass


# ----------------------------------------------------------------------
# 3. AI arms race -- evaluate, renew, poach
# ----------------------------------------------------------------------

_SCOUT_FIRST = ("Adam", "Barry", "Cam", "Doug", "Eddie", "Frank", "Gord",
                "Howie", "Ian", "Jack", "Ken", "Lorne", "Murray", "Norm",
                "Pete", "Rick", "Steve", "Terry", "Vic", "Walt")
_SCOUT_LAST = ("Button", "Clarke", "Dineen", "Esposito", "Ferguson",
               "Gadsby", "Harvey", "Imlach", "Keon", "Lindsay", "Mikita",
               "Neely", "Orr", "Park", "Quinn", "Ratelle", "Sittler",
               "Trottier", "Ullman", "Watson")


def _make_scout(rng, role, jpa_lo=25, jpa_hi=85):
    """A fresh scout off the street: ability drawn, record clean.

    jpa bounds are native 1-100 staff scale (25/85 ~= 5/17 on the
    1-20 eye scale used by the tip math). A young scout builds his
    name from a blank ledger -- exactly what the track-record
    system is for.
    """
    try:
        from game_classes import Staff
    except Exception:
        return None
    try:
        s = Staff(first_name=rng.choice(_SCOUT_FIRST),
                  last_name=rng.choice(_SCOUT_LAST),
                  role=role)
        s.judging_player_ability = int(rng.randint(jpa_lo, jpa_hi))
        s.judging_player_potential = int(rng.randint(jpa_lo, jpa_hi))
        s.experience = int(rng.randint(1, 12))
        s.age = int(rng.randint(28, 55))
        s.salary = int(rng.randint(90000, 400000))
        s.contract_years = int(rng.randint(1, 4))
        ensure_analytics_fields(s)
        return s
    except Exception:
        return None


def ai_scout_staff_review(league: Any, date_str: str, rng=None) -> Dict[str, int]:
    """AI clubs evaluate, renew and poach scouting staff. Twice a season.

    - Scouts with 10+ graded calls under a 40% hit rate get fired; the
      club hires a replacement (or pulls one from the free-agent pool).
    - Scouts with 15+ calls at 65%+ become poaching targets: a rival
      whose own best eye is worse may lure them away for more money.
    - Reads improve only when the people improve: JPA never drifts on
      its own. An elite scout is labor-market value, not a difficulty
      slider.
    Returns {"fired": n, "hired": n, "poached": n}.
    """
    import random as _r
    rng = rng or _r
    out = {"fired": 0, "hired": 0, "poached": 0}
    try:
        import game_classes as _gc
        teams = [t for t in list(getattr(league, "teams", []) or [])
                 if not _gc.is_human_managed(t)]
    except Exception:
        return out
    roles = _pro_roles()
    if not roles:
        return out

    def _record(s):
        ensure_analytics_fields(s)
        rec = getattr(s, "tip_record", None) or {}
        return int(rec.get("calls", 0) or 0), int(rec.get("hits", 0) or 0)

    def _best_jpa(team):
        best = 0
        for s in list(getattr(team, "staff", []) or []):
            if getattr(s, "role", None) in roles:
                best = max(best, int(getattr(s, "judging_player_ability",
                                             0) or 0))
        return best

    # 1. Evaluate + renew.
    for team in teams:
        try:
            ensure_analytics_fields(team)
            staff = list(getattr(team, "staff", []) or [])
            for s in staff:
                if getattr(s, "role", None) not in roles:
                    continue
                calls, hits = _record(s)
                if calls >= 10 and (hits / calls) < 0.40:
                    # Exposed by the ledger: the famous veteran can fail.
                    try:
                        team.staff.remove(s)
                    except Exception:
                        pass
                    try:
                        pool = getattr(league, "free_agent_staff", None)
                        if pool is None:
                            league.free_agent_staff = pool = []
                        pool.append(s)
                    except Exception:
                        pass
                    out["fired"] += 1
                    # Renew: best available scout eye the club can afford under
                    # its league-wide staff budget, else a fresh face.
                    hired = None
                    try:
                        from game_classes import team_can_afford_staff as _afford
                        cands = [c for c in pool
                                 if getattr(c, "role", None) in roles]
                        if cands:
                            cands.sort(key=lambda c: int(
                                getattr(c, "judging_player_ability",
                                        0) or 0), reverse=True)
                            for cand in cands:
                                if _afford(team, getattr(cand, "salary", 0) or 0):
                                    hired = cand
                                    break
                            if hired is not None:
                                pool.remove(hired)
                    except Exception:
                        hired = None
                    if hired is None:
                        hired = _make_scout(rng, getattr(
                            s, "role", next(iter(roles))))
                        try:
                            from game_classes import team_can_afford_staff as _afford2
                            if not _afford2(team, getattr(hired, "salary", 0) or 0):
                                hired = None
                        except Exception:
                            pass
                    if hired is not None:
                        try:
                            team.staff.append(hired)
                            out["hired"] += 1
                        except Exception:
                            pass
        except Exception:
            pass

    # 2. Poach: elite eyes are labor-market value.
    try:
        targets = []  # (scout, team)
        for team in teams:
            for s in list(getattr(team, "staff", []) or []):
                if getattr(s, "role", None) not in roles:
                    continue
                calls, hits = _record(s)
                if calls >= 15 and (hits / calls) >= 0.65:
                    targets.append((s, team))
        for scout, home in targets:
            if rng.random() > 0.25:
                continue
            seekers = [t for t in teams
                       if t is not home and _best_jpa(t) < int(
                           getattr(scout, "judging_player_ability",
                                   0) or 0)]
            if not seekers:
                continue
            dest = rng.choice(seekers)
            try:
                # League-wide staff budget: the destination must afford the
                # raise. Otherwise the poach dies quietly.
                from game_classes import team_can_afford_staff as _afford3
                bumped = int((getattr(scout, "salary", 150000)
                              or 150000) * 1.35)
                if not _afford3(dest, bumped):
                    continue
                home.staff.remove(scout)
                scout.salary = bumped
                scout.contract_years = 3
                dest.staff.append(scout)
                out["poached"] += 1
            except Exception:
                pass
    except Exception:
        pass

    # 3. Analytics arms race: clubs without a director may hire one.
    # Analytics-heavy philosophies invest first; old-school rooms hold
    # out. A hired director upgrades the club's lens via
    # refresh_analytics_quality(). Directors are never fired on scout
    # track records -- their output is the lens, not calls.
    try:
        from game_classes import StaffRole as _SR
        _want = _SR.ANALYTICS_DIRECTOR
    except Exception:
        _want = None
    if _want is not None:
        try:
            pool = list(getattr(league, "free_agent_staff", None) or [])
        except Exception:
            pool = []
        for team in teams:
            try:
                ensure_analytics_fields(team)
                has = any(getattr(s, "role", None) == _want
                          for s in list(getattr(team, "staff", []) or []))
                if has:
                    continue
                philo = float(getattr(team, "analytics_philosophy",
                                      30.0) or 30.0)
                # ~10% per review for analytics-heavy, ~2% old-school.
                if rng.random() > 0.02 + 0.08 * (philo / 100.0):
                    continue
                cands = [c for c in pool
                         if getattr(c, "role", None) == _want]
                hired = None
                if cands:
                    cands.sort(key=lambda c: analytics_director_quality(c),
                               reverse=True)
                    try:
                        from game_classes import team_can_afford_staff as _afford4
                        hired = next(
                            (c for c in cands
                             if _afford4(team, getattr(c, "salary", 0) or 0)),
                            None)
                    except Exception:
                        hired = cands[0]
                    try:
                        if hired is not None:
                            pool.remove(hired)
                            league.free_agent_staff.remove(hired)
                    except Exception:
                        pass
                else:
                    hired = _make_director(rng)
                    try:
                        from game_classes import team_can_afford_staff as _afford5
                        if not _afford5(team, getattr(hired, "salary", 0) or 0):
                            hired = None
                    except Exception:
                        pass
                if hired is not None:
                    team.staff.append(hired)
                    refresh_analytics_quality(team)
                    out["hired"] += 1
            except Exception:
                pass
    return out


def _make_director(rng) -> Any:
    """A fresh analytics director: strong model-reading attributes."""
    try:
        from game_classes import Staff, StaffRole
    except Exception:
        return None
    try:
        s = Staff(first_name=rng.choice(_SCOUT_FIRST),
                  last_name=rng.choice(_SCOUT_LAST),
                  role=StaffRole.ANALYTICS_DIRECTOR,
                  age=rng.randint(28, 55))
        s.judging_player_ability = int(rng.randint(55, 95))
        s.tactical_knowledge = int(rng.randint(55, 95))
        s.adaptability = int(rng.randint(55, 95))
        s.salary = int(rng.randint(120000, 300000))
        s.contract_years = int(rng.randint(2, 4))
        ensure_analytics_fields(s)
        return s
    except Exception:
        return None
