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


def publish_analytics_storylines(media_system: Any, players: List[Any],
                                 teams: List[Any], game_manager: Any = None,
                                 limit: int = 4) -> int:
    """Push analytics storylines into the media system (best-effort).

    Non-invasive: if the media system isn't available or doesn't accept
    them, this silently does nothing.
    """
    try:
        seeds = analytics_storylines(players, teams, limit=limit)
        if not seeds or media_system is None:
            return 0
        from media_system import MediaStoryline, StorylineType
        import random
        import datetime
        now = None
        try:
            now = game_manager.current_date if game_manager else None
        except Exception:
            now = None
        added = 0
        for s in seeds:
            try:
                sl = MediaStoryline(
                    id=f"analytics_{random.randint(1000, 9999)}",
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
    """Pro-scouting eye: judging current ability (1-20 EHM scale)."""
    try:
        return max(1, min(20, int(getattr(scout, "judging_player_ability", 10) or 10)))
    except (TypeError, ValueError):
        return 10


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
