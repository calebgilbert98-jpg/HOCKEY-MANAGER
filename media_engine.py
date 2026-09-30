# media_engine.py — the press as a living ecosystem.
#
# Real NHL markets behave differently. Toronto is a fishbowl, Montreal is a
# pressure cooker, Edmonton has its Jim Matheson types, and half the league
# barely gets asked about the power play. This engine models that:
#
#   * 32 market profiles: intensity / adversarialness / loyalty / patience.
#   * Reporters per market: a mix of stirrers, loyalists and neutrals, each
#     with credibility and fan approval that move with events.
#   * Post-game interviews, Hockey Night in Canada style: a different player
#     every night. Some guys are naturals on camera; some are not.
#   * Ongoing narratives (hot seat, leadership questions, goalie
#     controversy, trade chatter) that persist across days, get poked at by
#     stirrers, get shut down by composed players -- and mostly fizzle out.
#   * Rare, realistic discipline: hot-headed players popping off after a
#     heated loss get fined; Tortorella types who stonewall the press get
#     fined; coach-vs-reporter arguments can escalate into real beefs.
#
# Design constraints (per direction): ongoing stories, nothing ridiculous.
# Drama is rare by construction, effects are small (morale +/-1, chemistry
# -2, controversy +3), fines are realistic, and the whole thing costs a few
# attribute reads per game -- it never slows the sim and never blows up
# teams. Everything degrades gracefully on partial data.

from __future__ import annotations

import random
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Market profiles: intensity, adversarial, loyalty, patience (0-100)
# ---------------------------------------------------------------------------
# intensity:    how much coverage -- is there even a scrum?
# adversarial:  how hostile the questions get when things go bad
# loyalty:      do the local press defend the team or pile on
# patience:     how long a skid runs before the heat arrives (high = patient)

MARKET_PROFILES: Dict[str, Tuple[int, int, int, int]] = {
    # Atlantic
    "Boston Bruins": (80, 60, 55, 50),
    "Buffalo Sabres": (60, 50, 60, 55),
    "Detroit Red Wings": (68, 50, 60, 60),
    "Florida Panthers": (58, 42, 68, 68),
    "Montréal Canadiens": (92, 70, 35, 30),
    "Ottawa Senators": (70, 60, 50, 50),
    "Tampa Bay Lightning": (60, 40, 70, 70),
    "Toronto Maple Leafs": (95, 75, 30, 25),
    # Metropolitan
    "Carolina Hurricanes": (55, 40, 70, 70),
    "Columbus Blue Jackets": (55, 45, 65, 65),
    "New Jersey Devils": (62, 52, 58, 58),
    "New York Islanders": (60, 55, 60, 60),
    "New York Rangers": (85, 65, 40, 40),
    "Philadelphia Flyers": (82, 70, 45, 40),
    "Pittsburgh Penguins": (72, 55, 60, 55),
    "Washington Capitals": (65, 50, 60, 60),
    # Central
    "Chicago Blackhawks": (70, 55, 55, 55),
    "Colorado Avalanche": (62, 45, 65, 65),
    "Dallas Stars": (58, 42, 68, 68),
    "Minnesota Wild": (60, 45, 68, 65),
    "Nashville Predators": (55, 40, 72, 70),
    "St. Louis Blues": (60, 48, 65, 62),
    "Utah Hockey Club": (45, 35, 75, 75),
    "Winnipeg Jets": (65, 50, 65, 55),
    # Pacific
    "Anaheim Ducks": (50, 40, 70, 72),
    "Calgary Flames": (70, 60, 55, 50),
    "Edmonton Oilers": (78, 65, 55, 45),
    "Los Angeles Kings": (62, 48, 62, 62),
    "San Jose Sharks": (52, 42, 68, 70),
    "Seattle Kraken": (55, 40, 70, 72),
    "Vancouver Canucks": (75, 60, 50, 45),
    "Vegas Golden Knights": (66, 55, 55, 50),
}

_DEFAULT_MARKET = (55, 45, 65, 65)


def market_of(team_name: str) -> Dict[str, int]:
    prof = MARKET_PROFILES.get(team_name or "", _DEFAULT_MARKET)
    return {"intensity": prof[0], "adversarial": prof[1],
            "loyalty": prof[2], "patience": prof[3]}


# ---------------------------------------------------------------------------
# Reporters
# ---------------------------------------------------------------------------

_REPORTER_FIRST = [
    "Jim", "Mike", "Dave", "Steve", "Paul", "Mark", "Chris", "Dan",
    "Sarah", "Jen", "Katie", "Laura", "Megan", "Erin", "Alex", "Sam",
    "Tony", "Rob", "Kevin", "Brian", "Scott", "Jeff", "Andy", "Nick",
]
_REPORTER_LAST = [
    "Matheson", "Thompson", "Reynolds", "Callahan", "Brennan", "Foster",
    "Gallagher", "Hughes", "Kowalski", "Lindgren", "Marsh", "Nolan",
    "O'Brien", "Petrov", "Quinn", "Rossi", "Sutter", "Tremblay",
    "Vance", "Whitaker", "Yamamoto", "Zajac", "Bishop", "Crane",
]

# archetype -> question-tone bias
_ARCHETYPES = ("stirrer", "loyalist", "neutral")


class Reporter:
    """One media personality on a beat. Pickle-friendly plain class."""

    def __init__(self, name: str, market: str, archetype: str):
        self.id = f"{market}|{name}"
        self.name = name
        self.market = market
        self.archetype = archetype  # stirrer | loyalist | neutral
        self.credibility = 60.0     # 0-100; dings when narratives collapse
        self.fan_approval = 50.0    # 0-100; fans love loyalists, hate wrong stirrers

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Reporter {self.name} ({self.archetype})>"


class Narrative:
    """An ongoing media storyline. Heat decays daily; most die quietly."""

    def __init__(self, kind: str, team_name: str, title: str,
                 subjects: Optional[List[str]] = None, heat: float = 45.0):
        self.id = f"{kind}:{team_name}:{random.randrange(10**6)}"
        self.kind = kind  # hot_seat | leadership | goalie | trade_rumor
        self.team_name = team_name
        self.title = title
        self.subjects = list(subjects or [])
        self.heat = float(heat)  # 0-100

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Narrative {self.title} heat={self.heat:.0f}>"


class CoachMediaBeef:
    """An escalating coach-vs-reporter conflict."""

    def __init__(self, coach_name: str, reporter_id: str, reporter_name: str,
                 team_name: str):
        self.coach_name = coach_name
        self.reporter_id = reporter_id
        self.reporter_name = reporter_name
        self.team_name = team_name
        self.level = 1  # 1: testy exchange, 2: open hostility, 3: full circus
        self.days_quiet = 0


def ensure_media_state(league: Any) -> None:
    """Build reporters / narrative lists on first use. Idempotent."""
    if getattr(league, "reporters", None) is None:
        reporters: List[Reporter] = []
        for team_name in MARKET_PROFILES:
            seed = abs(hash(team_name)) % (2 ** 32)
            rng = random.Random(seed)
            firsts = rng.sample(_REPORTER_FIRST, 3)
            lasts = rng.sample(_REPORTER_LAST, 3)
            for i, arch in enumerate(_ARCHETYPES):
                reporters.append(Reporter(
                    f"{firsts[i]} {lasts[i]}", team_name, arch))
        league.reporters = reporters
    for attr, default in (("media_narratives", []),
                          ("coach_media_beefs", []),
                          ("media_fines", []),
                          ("media_recent_faces", [])):
        if getattr(league, attr, None) is None:
            setattr(league, attr, default)


def reporters_for(market: str, league: Any) -> List[Reporter]:
    ensure_media_state(league)
    return [r for r in league.reporters if r.market == market]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _f(player: Any, name: str, default: float = 50.0) -> float:
    try:
        v = getattr(player, name, default)
        return float(default if v is None else v)
    except (TypeError, ValueError):
        return float(default)


def _overall(player: Any) -> float:
    try:
        return float(player.overall_rating())
    except Exception:
        return 70.0


def _team_name(team: Any) -> str:
    return (getattr(team, "team_name", None)
            or getattr(team, "name", None) or "Unknown")


def _win_pct(team: Any) -> float:
    w = float(getattr(team, "wins", 0) or 0)
    l = float(getattr(team, "losses", 0) or 0)
    ot = float(getattr(team, "ot_losses", 0) or 0)
    return w / (w + l + ot) if (w + l + ot) > 0 else 0.5


def _games_played(team: Any) -> int:
    return int((getattr(team, "wins", 0) or 0)
               + (getattr(team, "losses", 0) or 0)
               + (getattr(team, "ot_losses", 0) or 0))


def _head_coach_of(team: Any) -> Optional[Any]:
    try:
        import reputation_system as _rs
        return _rs._head_coach_of(team)
    except Exception:
        return None


def _captain_of(team: Any) -> Optional[Any]:
    try:
        for p in (getattr(team, "roster", []) or []):
            role = (getattr(getattr(p, "role", None), "value", "")
                    or getattr(p, "role", "") or "")
            if "captain" in str(role).lower() and "assistant" not in str(role).lower():
                return p
    except Exception:
        pass
    return None


def media_savvy(player: Any) -> float:
    """0-100: how equipped is this guy for a camera in his face?

    Composure does the heavy lifting; low controversy helps (boring is
    safe); leadership and NHL miles round it out.
    """
    g = _f(player, "nhl_games_played", 0)
    savvy = (_f(player, "composure", 60) * 0.35
             + (100.0 - _f(player, "controversy", 30)) * 0.25
             + _f(player, "leadership", 50) * 0.15
             + min(g / 150.0, 1.0) * 15.0
             + _f(player, "pressure_player", 50) * 0.10)
    return max(0.0, min(100.0, savvy))


# ---------------------------------------------------------------------------
# Interview content
# ---------------------------------------------------------------------------

_QUOTES = {
    "great": [
        "“We stuck to our game for sixty minutes. When we play like that, we're a tough out.”",
        "“The fans were unbelievable tonight — we fed off that energy.”",
        "“It's about the two points. Nothing else matters right now.”",
        "“We've got a room that believes. That's all I'll say.”",
    ],
    "bland": [
        "“Yeah, you know, we just tried to play our game out there.”",
        "“It's a long season. We'll take the two points and move on.”",
        "“I thought we competed hard. That's what we're asking for.”",
    ],
    "awkward": [
        "“Uh... yeah. I mean. We scored more than them, so. Yeah.”",
        "“I don't really know what to tell you. We won? That's good.”",
    ],
}

_STIRRER_QUESTIONS = [
    "“There's a sense the room is frustrated — fair or unfair?”",
    "“Fans are calling this a wasted season. Your response?”",
    "“Is the coach's message still getting through in here?”",
]
_LOYALIST_QUESTIONS = [
    "“What did you like about the group's compete level tonight?”",
    "“How close is this team to putting it all together?”",
]
_NEUTRAL_QUESTIONS = [
    "“Walk us through the game from your perspective.”",
    "“What was the difference tonight?”",
]


def _pick_reporter(market: str, league: Any, rng: random.Random,
                   adversarial_boost: bool = False) -> Optional[Reporter]:
    reps = reporters_for(market, league)
    if not reps:
        return None
    prof = market_of(market)
    weights = []
    for r in reps:
        w = 1.0
        if r.archetype == "stirrer":
            w = prof["adversarial"] / 50.0 + (0.5 if adversarial_boost else 0.0)
        elif r.archetype == "loyalist":
            w = prof["loyalty"] / 50.0
        weights.append(max(0.1, w))
    return rng.choices(reps, weights=weights, k=1)[0]


def _pick_interviewee(team: Any, league: Any, rng: random.Random,
                      loser_side: bool = False) -> Optional[Any]:
    """Hockey Night in Canada rule: a different player every night."""
    roster = [p for p in (getattr(team, "roster", []) or [])
              if not getattr(p, "is_injured", False)]
    if not roster:
        return None
    recent = set(getattr(league, "media_recent_faces", []) or [])
    pool = [p for p in roster if getattr(p, "id", None) not in recent]
    if not pool:
        pool = roster
    if loser_side:
        # After a bad loss the captain faces the music.
        cap = _captain_of(team)
        if cap is not None and cap in pool:
            return cap
    # Star of the night: best player available, with a little randomness
    # so it's not the same superstar 82 nights a year.
    scored = sorted(((_overall(p) + rng.uniform(-6, 6), p) for p in pool),
                    reverse=True)
    pick = scored[0][1]
    try:
        faces = league.media_recent_faces
        faces.append(getattr(pick, "id", None))
        league.media_recent_faces = faces[-12:]
    except Exception:
        pass
    return pick


# ---------------------------------------------------------------------------
# The nightly show
# ---------------------------------------------------------------------------

def _spiraling(team: Any) -> bool:
    return _games_played(team) >= 10 and _win_pct(team) <= 0.400


def _playoff_context(league: Any, home_team: Any,
                     away_team: Any) -> Optional[Dict[str, Any]]:
    """None in the regular season; otherwise round / game number /
    elimination flags. Defensive: any missing piece -> regular season."""
    try:
        bracket = getattr(league, "playoff_bracket", None)
        series_map = getattr(bracket, "playoff_series", None)
        if not series_map:
            return None
        hn, an = _team_name(home_team), _team_name(away_team)
        for round_key, series_list in series_map.items():
            for s in series_list or []:
                names = {_team_name(getattr(s, "team1", None)),
                         _team_name(getattr(s, "team2", None))}
                if {hn, an} <= names and not getattr(s, "is_complete", True):
                    w1 = int(getattr(s, "team1_wins", 0) or 0)
                    w2 = int(getattr(s, "team2_wins", 0) or 0)
                    gp = int(getattr(s, "games_played", 0) or 0)
                    elim = (w1 == 3 or w2 == 3)
                    return {"round": getattr(s, "round_name", round_key),
                            "game_number": gp + 1,
                            "is_elimination": elim,
                            "is_game_7": gp == 6}
    except Exception:
        pass
    return None


def _gm_of(team: Any) -> Optional[Any]:
    """Best-effort GM lookup; None is fine (we write around it)."""
    try:
        for stf in getattr(team, "staff", []) or []:
            if "General Manager" in str(
                    getattr(getattr(stf, "role", None), "value", "")):
                return stf
    except Exception:
        pass
    return None


def _bump(roster: List[Any], attr: str, delta: float,
          predicate=None) -> None:
    for p in roster or []:
        try:
            if predicate is not None and not predicate(p):
                continue
            cur = _f(p, attr, 70)
            setattr(p, attr, max(1, min(100, cur + delta)))
        except Exception:
            continue


def _record(team: Any, event_type: str, text: str,
            morale_delta: int = 0, tone: str = "neutral") -> None:
    try:
        import reputation_system as _rs
        _rs.record_team_event(team, event_type, text,
                              morale_delta=morale_delta, tone=tone)
    except Exception:
        pass


def _is_leader(player: Any, team: Any) -> bool:
    if _captain_of(team) is player:
        return True
    return _f(player, "leadership", 50) >= 75


_PLAYOFF_QUOTES = [
    "“It's the playoffs. Nothing else matters but the next one.”",
    "“We knew it would be tight. We'll be ready for the next one.”",
    "“Full credit to them. We've got to be better.”",
    "“You don't get style points this time of year.”",
]

_STANDUP_QUOTES = [
    "“That's on all of us in here. You don't hang that on one guy.”",
    "“We win together, we lose together. That's the room we've got.”",
    "“Ask me about our team. I'm not pointing fingers at anyone.”",
]


# ---------------------------------------------------------------------------
# Personality-driven likelihoods. Who steps up is who they are, not a dice
# roll: the same guy behaves the same way all season, and across the league
# you get every shade -- the saint captain, the hothead leader, the
# players' coach, the control freak who shields his kids. Flat chances are
# gone; every probability below is built from attributes.
# ---------------------------------------------------------------------------

def _clamp_p(p: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, p))


def _bullet_likelihood(player: Any, team: Any, heated_loss: bool) -> float:
    """A leader takes the bullet when he's wired that way: high leadership,
    low controversy (doesn't make it about himself), composure to face the
    cameras. The C multiplies it -- that's literally the job. Hotheads get
    discounted: the room knows they'd turn it into a show."""
    lead = _f(player, "leadership", 50)
    comp = _f(player, "composure", 50)
    cont = _f(player, "controversy", 30)
    p = (0.05 + 0.45 * (lead / 100.0) + 0.20 * ((100.0 - cont) / 100.0)
         + 0.10 * (comp / 100.0))
    if _captain_of(team) is player:
        p *= 1.25
    if heated_loss:
        p *= 1.15  # the room needs it most after a bad one
    if cont >= 60:
        p *= 0.70  # guys tune out the hothead's noble act
    return _clamp_p(p, 0.05, 0.80)


def _shield_likelihood(coach: Any, player: Any) -> float:
    """A coach steps in front of his guy when protecting people is his
    nature: man-management first, then leadership, then the control freak's
    instinct that nobody talks to his players but him. Kids get covered
    far more than veterans."""
    mm = _f(coach, "man_management", 50)
    lead = _f(coach, "leadership", 50)
    ctrl = _f(coach, "control_need", 50)
    try:
        age = int(getattr(player, "age", 26) or 26)
    except Exception:
        age = 26
    p = (0.05 + 0.50 * (mm / 100.0) + 0.15 * (lead / 100.0)
         + 0.10 * (ctrl / 100.0))
    if age <= 23:
        p += 0.20
    return _clamp_p(p, 0.05, 0.90)


def _rally_speaker(team: Any):
    """Who gives the intermission word, by personality score. The best
    voice in the room wins -- a saint captain outranks a flat coach."""
    cap = _captain_of(team)
    coach = _head_coach_of(team)
    best, best_attr = None, 0.0
    if cap is not None:
        score = _f(cap, "leadership", 50) / 100.0 + 0.10
        if score > best_attr:
            best, best_attr = ("captain", cap), score
    if coach is not None:
        score = _f(coach, "motivating", 50) / 100.0
        if score > best_attr:
            best, best_attr = ("coach", coach), score
    if best is None or best_attr < 0.55:
        return None, 0.0
    return best[1], best_attr


def _rally_likelihood(speaker_attr: float, went_ot: bool,
                      avg_morale: float) -> float:
    """The better the voice, the more likely it speaks. Overtime and a
    flat room pull it out of people."""
    p = 0.05 + 0.50 * speaker_attr
    if went_ot:
        p *= 1.2
    if avg_morale < 60:
        p += 0.10  # someone has to say something
    return _clamp_p(p, 0.05, 0.85)


def _gm_backing_likelihood(gm: Any, narr: Any) -> float:
    """Steady GMs go on the record for their people; volatile ones let
    them twist. A burning hot-seat story forces even quiet GMs out."""
    cont = _f(gm, "controversy", 40) if gm is not None else 40
    heat = 0.0
    try:
        heat = float(getattr(narr, "heat", 0.0) or 0.0)
    except Exception:
        pass
    p = (0.008 + 0.06 * (heat / 100.0)
         + 0.025 * ((100.0 - cont) / 100.0))
    return _clamp_p(p, 0.005, 0.12)


# ---------------------------------------------------------------------------
# Key moments + cooldowns. Leadership moments land on nights that matter --
# blood rivalries, the March push, a room that's spiraling, a story hanging
# over the team -- and then the room goes quiet for a while. Nobody gives a
# speech every Tuesday.
# ---------------------------------------------------------------------------

_MOMENT_COOLDOWNS = {"bullet": 8, "rally": 10, "shield": 6, "backing": 25}


def _moment_clock(team: Any) -> int:
    return int(getattr(team, "media_games_covered", 0) or 0)


def _moment_ready(team: Any, kind: str) -> bool:
    try:
        last = (getattr(team, "media_moment_cd", None) or {}).get(kind)
        if last is None:
            return True
        return _moment_clock(team) - int(last) >= _MOMENT_COOLDOWNS[kind]
    except Exception:
        return True


def _mark_moment(team: Any, kind: str) -> None:
    try:
        cd = getattr(team, "media_moment_cd", None)
        if not isinstance(cd, dict):
            cd = {}
        cd[kind] = _moment_clock(team)
        team.media_moment_cd = cd
    except Exception:
        pass


def _key_moment_boost(league: Any, team: Any, opponent: Any,
                      game_date: Any) -> float:
    """1.0 on a random Tuesday; up to ~2x when the night matters."""
    boost = 1.0
    try:
        import reputation_system as _rs
        rivalries = getattr(league, "rivalries", None) or []
        heat = _rs.get_rivalry_heat(rivalries, team, opponent).get(
            "heat", 0)
        if heat >= 50:
            boost *= 1.4
    except Exception:
        pass
    try:
        month = getattr(game_date, "month", 0) or 0
        if month in (3, 4):
            boost *= 1.25  # the March/April push
    except Exception:
        pass
    try:
        if _spiraling(team):
            boost *= 1.3  # a sinking room needs a voice
        if _narrative_for(_team_name(team), league) is not None:
            boost *= 1.3  # a story hanging over them
    except Exception:
        pass
    return min(2.0, boost)


def cover_game(league: Any, home_team: Any, away_team: Any,
               winner: Any, loser: Any,
               scores: Tuple[int, int], went_ot: bool,
               game_date: Optional[date] = None,
               rng: Optional[random.Random] = None) -> List[Dict[str, Any]]:
    """Cover one finished game. Returns event dicts for the caller to route.

    Event kinds: quote, fine, beef, shutdown, narrative_spawn, narrative_poke.
    Cheap by design: two roster scans, a handful of rolls. Never raises.
    """
    rng = rng or random
    events: List[Dict[str, Any]] = []
    try:
        return _cover_game_inner(league, home_team, away_team, winner, loser,
                                 scores, went_ot, game_date, rng, events)
    except Exception:
        return events


def _cover_game_inner(league, home_team, away_team, winner, loser,
                      scores, went_ot, game_date, rng, events):
    ensure_media_state(league)
    home_name = _team_name(home_team)
    prof = market_of(home_name)

    # Low-intensity markets often have no scrum at all.
    if rng.random() > prof["intensity"] / 110.0:
        return events

    hs, aws = (scores or (0, 0))[:2]
    try:
        diff = abs(int(hs) - int(aws))
    except Exception:
        diff = 0
    home_won = winner is home_team
    heated_loss = diff >= 4 or (went_ot and not home_won)
    loser_spiraling = _spiraling(loser)

    # Context matters. In an elimination game / Game 7 the rooms close:
    # no narrative pokes, no beefs, no stonewalls, no pop-offs -- just
    # brief, respectful scrums. Earlier playoff rounds are muted too.
    poctx = _playoff_context(league, home_team, away_team)
    big_game = bool(poctx and (poctx["is_elimination"]
                               or poctx["is_game_7"]))
    playoffs = poctx is not None
    if big_game and rng.random() < 0.4:
        return events  # both rooms closed tonight
    try:
        home_team.media_games_covered = _moment_clock(home_team) + 1
    except Exception:
        pass
    ctx = {"big_game": big_game, "playoffs": playoffs,
           "key_boost": _key_moment_boost(league, home_team, away_team,
                                          game_date)}

    # ---- 1. The interview ----
    interviewee = _pick_interviewee(home_team, league, rng,
                                    loser_side=(not home_won and heated_loss))
    if interviewee is not None:
        reporter = _pick_reporter(
            home_name, league, rng,
            adversarial_boost=(not home_won and loser_spiraling
                               and not playoffs))
        if reporter is not None:
            _run_interview(league, home_team, interviewee, reporter,
                           home_won, heated_loss, loser_spiraling,
                           game_date, rng, events, ctx)

    # ---- 2. Coach availability ----
    _run_coach_availability(league, home_team, home_name, reporter,
                            heated_loss, loser_spiraling, game_date,
                            rng, events, ctx)

    # ---- 3. Narrative watch: regular season only. Playoffs freeze the
    # silly stuff -- nobody starts a goalie controversy in May.
    if not playoffs:
        _maybe_spawn_narrative(league, loser, game_date, rng, events)

    # ---- 4. Between-periods leadership: fully simmed, never interrupts.
    # A captain's/coach's intermission word in a tight game lifts the room.
    _room_leadership_moment(league, home_team, home_won, diff, went_ot,
                            game_date, rng, events, ctx)

    # ---- 5. The front office speaks: a steady GM with a burning story
    # goes on the record. Personality-gated, never scheduled, and rare
    # enough that it means something when it happens.
    if not playoffs:
        narr = _narrative_for(_team_name(home_team), league)
        if (_moment_ready(home_team, "backing")
                and rng.random()
                < _gm_backing_likelihood(_gm_of(home_team), narr)
                * ctx["key_boost"]):
            _mark_moment(home_team, "backing")
            _gm_backing(league, home_team, game_date, rng, events)

    return events


def _run_interview(league, team, player, reporter, won: bool,
                   heated_loss: bool, spiraling: bool,
                   game_date, rng, events,
                   ctx: Optional[Dict[str, Any]] = None) -> None:
    ctx = ctx or {}
    pname = getattr(player, "full_name",
                    getattr(player, "last_name", "A player"))
    savvy = media_savvy(player)
    hot_head = _f(player, "controversy", 30) >= 60

    # Game 7 / elimination: brief and respectful. Nobody pops off, nobody
    # gets cute. Just hockey clichés, the way it really is.
    if ctx.get("big_game"):
        events.append({
            "kind": "quote",
            "team": _team_name(team),
            "player": pname,
            "reporter": reporter.name,
            "archetype": "neutral",
            "outcome": "bland",
            "question": "“How do you sum this one up?”",
            "quote": rng.choice(_PLAYOFF_QUOTES),
        })
        return

    # The captain takes the bullet: after a loss, a real leader doesn't
    # let the room get carved up -- he stands in front of it. Whether he
    # does is personality, not luck (see _bullet_likelihood) -- and it
    # doesn't happen every night (cooldown).
    if (not won and not ctx.get("playoffs") and _is_leader(player, team)
            and _moment_ready(team, "bullet")
            and rng.random() < _bullet_likelihood(player, team,
                                                  heated_loss)
            * ctx.get("key_boost", 1.0)):
        _mark_moment(team, "bullet")
        _leader_stands_up(league, team, player, pname, reporter,
                          game_date, rng, events)
        return

    # The frustration override: hot head + bad situation + heated loss.
    # Rare even then -- most guys just give a bland answer and leave.
    # Muted in the playoffs (everyone bites their tongue in May).
    outburst_p = 0.35 * (0.3 if ctx.get("playoffs") else 1.0)
    if (hot_head and not won and (heated_loss or spiraling)
            and rng.random() < outburst_p):
        _run_outburst(league, team, player, pname, reporter,
                      game_date, rng, events)
        return

    # Narrative poke: a stirrer smells blood. Not in the playoffs.
    narr = _narrative_for(_team_name(team), league)
    if (narr is not None and not ctx.get("playoffs")
            and reporter.archetype == "stirrer"
            and rng.random() < 0.15 + narr.heat / 400.0):
        _run_narrative_poke(league, team, player, pname, savvy,
                            reporter, narr, game_date, rng, events, ctx)
        return

    # A normal night: the quote, shaped by who's holding the mic.
    if savvy >= 70:
        outcome = "great" if rng.random() < 0.6 else "bland"
    elif savvy >= 40:
        outcome = "awkward" if rng.random() < 0.2 else "bland"
    else:
        r = rng.random()
        outcome = "awkward" if r < 0.4 else ("great" if r > 0.92 else "bland")
    quote = rng.choice(_QUOTES[outcome])
    q_pool = (_STIRRER_QUESTIONS if reporter.archetype == "stirrer"
              else _LOYALIST_QUESTIONS if reporter.archetype == "loyalist"
              else _NEUTRAL_QUESTIONS)
    events.append({
        "kind": "quote",
        "team": _team_name(team),
        "player": pname,
        "reporter": reporter.name,
        "archetype": reporter.archetype,
        "outcome": outcome,
        "question": rng.choice(q_pool),
        "quote": quote,
    })
    if outcome == "great":
        # A great quote nudges the room, barely.
        try:
            player.morale = max(1, min(100, _f(player, "morale", 70) + 1))
        except Exception:
            pass


def _run_outburst(league, team, player, pname, reporter,
                  game_date, rng, events) -> None:
    """The rare pop-off. Two flavors: officials (fine) or the room (messy)."""
    team_name = _team_name(team)
    if rng.random() < 0.5:
        amount = int(rng.choice([2500, 5000]))
        events.append({
            "kind": "fine",
            "name": pname,
            "team": team_name,
            "amount": amount,
            "reason": ("criticizing the officiating after the loss -- "
                       "“I'm not going to sit here and pretend that was "
                       "fair.”"),
        })
        try:
            league.media_fines.append({"date": game_date, "name": pname,
                                       "team": team_name, "amount": amount,
                                       "reason": "criticizing officiating"})
        except Exception:
            pass
    else:
        events.append({
            "kind": "outburst_room",
            "team": team_name,
            "player": pname,
            "reporter": reporter.name if reporter else "beat reporter",
            "quote": ("“I'm sick of answering for everybody. Some guys in "
                      "here need to look in the mirror.”"),
        })
        try:
            player.controversy = max(0, min(100, _f(player, "controversy") + 3))
            player.team_chemistry = max(
                0, min(100, _f(player, "team_chemistry", 60) - 2))
        except Exception:
            pass
    # Stirrers gain credibility from a real pop-off; fans eat it up either way.
    if reporter is not None and reporter.archetype == "stirrer":
        reporter.credibility = min(100, reporter.credibility + 4)


def _leader_stands_up(league, team, player, pname, reporter,
                     game_date, rng, events) -> None:
    """A leader takes the bullet for the room. The guys notice."""
    team_name = _team_name(team)
    roster = list(getattr(team, "roster", []) or [])
    _bump(roster, "happiness", 1)
    # The kids who are struggling feel it most.
    low = sorted(roster, key=lambda p: _f(p, "morale", 70))[:2]
    for p in low:
        _bump([p], "morale", 1)
    narr = _narrative_for(team_name, league)
    if narr is not None:
        narr.heat = max(0, narr.heat - 15)
    _record(team, "leadership_stand",
            f"{pname} stood in front of the room after the loss and took "
            f"every question himself. The guys noticed.", morale_delta=1,
            tone="up")
    events.append({
        "kind": "defense",
        "team": team_name,
        "player": pname,
        "reporter": reporter.name if reporter else "beat",
        "quote": rng.choice(_STANDUP_QUOTES),
        "note": (f"{pname} took the bullet for the room -- no fingers "
                 f"pointed anywhere but at himself."),
    })


def _narrative_for(team_name: str, league: Any) -> Optional[Narrative]:
    narrs = [n for n in (getattr(league, "media_narratives", []) or [])
             if n.team_name == team_name]
    return max(narrs, key=lambda n: n.heat) if narrs else None


def _run_narrative_poke(league, team, player, pname, savvy, reporter,
                        narr, game_date, rng, events,
                        ctx: Optional[Dict[str, Any]] = None) -> None:
    """The Draisaitl moment: a ridiculous narrative meets a composed player
    and dies on camera -- or meets a rattled one and grows legs.

    Before either, a good coach may step in front of his guy -- especially
    a young one. That's what the good ones do. Whether he does is who he
    is (see _shield_likelihood), not a coin flip."""
    coach = _head_coach_of(team)
    kb = (ctx or {}).get("key_boost", 1.0)
    if (coach is not None and _moment_ready(team, "shield")
            and rng.random() < _shield_likelihood(coach, player) * kb):
        _mark_moment(team, "shield")
        cname = getattr(coach, "full_name",
                        getattr(coach, "last_name", "The coach"))
        narr.heat = max(0, narr.heat - 10)
        _bump([player], "morale", 2)
        _record(team, "coach_shield",
                f"{cname} cut off the {narr.title.lower()} questions and "
                f"took them himself. {pname} didn't have to say a word.",
                morale_delta=1, tone="up")
        events.append({
            "kind": "shield",
            "team": _team_name(team),
            "coach": cname,
            "player": pname,
            "reporter": reporter.name,
            "narrative": narr.title,
            "quote": ("“You're asking about a kid. Ask me about our team "
                      "game -- that's my job, not his.”"),
        })
        return
    if savvy >= 65:
        # Shut down. Cold.
        try:
            league.media_narratives.remove(narr)
        except Exception:
            pass
        reporter.credibility = max(0, reporter.credibility - 8)
        reporter.fan_approval = max(0, reporter.fan_approval - 10)
        events.append({
            "kind": "shutdown",
            "team": _team_name(team),
            "player": pname,
            "reporter": reporter.name,
            "narrative": narr.title,
            "quote": "“That's a ridiculous question. I'm done with this one.”",
        })
    elif savvy <= 45:
        narr.heat = min(100, narr.heat + 15)
        events.append({
            "kind": "narrative_poke",
            "team": _team_name(team),
            "player": pname,
            "reporter": reporter.name,
            "narrative": narr.title,
            "note": (f"{pname} stumbled through the answer -- the "
                     f"{narr.title.lower()} story isn't going away."),
        })
    else:
        narr.heat = max(0, narr.heat - 5)
        events.append({
            "kind": "quote",
            "team": _team_name(team),
            "player": pname,
            "reporter": reporter.name,
            "archetype": reporter.archetype,
            "outcome": "bland",
            "question": f"“Is there anything to the {narr.title.lower()} talk?”",
            "quote": "“We're focused on our game. That's all I can tell you.”",
        })


def _run_coach_availability(league, team, team_name, reporter,
                            heated_loss, spiraling, game_date,
                            rng, events,
                            ctx: Optional[Dict[str, Any]] = None) -> None:
    ctx = ctx or {}
    coach = _head_coach_of(team)
    if coach is None:
        return
    cname = getattr(coach, "full_name",
                    getattr(coach, "last_name", "The coach"))
    controversy = _f(coach, "controversy", 40)
    control = _f(coach, "control_need", 50)

    # Even the prickliest coach shows up for a Game 7 scrum.
    if ctx.get("big_game"):
        return

    # The Tortorella: stonewalls the scrum, eventually gets fined for it.
    stonewall = controversy / 100.0 * 0.5 + control / 100.0 * 0.5
    if stonewall >= 0.60 and rng.random() < 0.35:
        n = int(getattr(coach, "media_stonewalls", 0) or 0) + 1
        try:
            coach.media_stonewalls = n
        except Exception:
            pass
        if n >= 3:
            amount = 25000
            events.append({
                "kind": "fine",
                "name": cname,
                "team": team_name,
                "amount": amount,
                "role": "coach",
                "reason": ("failing to meet league media obligations -- "
                           "third straight scrum cut short"),
            })
            try:
                league.media_fines.append(
                    {"date": game_date, "name": cname, "team": team_name,
                     "amount": amount, "reason": "skipping media availability"})
                coach.media_stonewalls = 0
            except Exception:
                pass
        else:
            events.append({
                "kind": "quote",
                "team": team_name,
                "player": cname,
                "reporter": reporter.name if reporter else "beat",
                "archetype": "neutral",
                "outcome": "bland",
                "question": "“Coach, what happened out there tonight?”",
                "quote": "“I'm not getting into it. We're done here.”",
            })
        return

    # Coach vs stirrer: arguments that escalate across meetings.
    # Nobody's fighting the press in the playoffs -- too much at stake.
    beef_p = 0.30 * (0.5 if ctx.get("playoffs") else 1.0)
    if (reporter is not None and reporter.archetype == "stirrer"
            and controversy >= 55 and rng.random() < beef_p):
        beef = next((b for b in league.coach_media_beefs
                     if b.reporter_id == reporter.id
                     and b.coach_name == cname), None)
        if beef is None:
            beef = CoachMediaBeef(cname, reporter.id, reporter.name,
                                  team_name)
            league.coach_media_beefs.append(beef)
            prev_level = 0
        else:
            prev_level = beef.level
            beef.level = min(3, prev_level + 1)
        beef.days_quiet = 0
        reporter.fan_approval = max(0, reporter.fan_approval - 5)
        if beef.level >= 3 and prev_level < 3:
            # Full circus, once: a genuine distraction, then it burns out.
            try:
                for p in (getattr(team, "roster", []) or []):
                    m = _f(p, "morale", 70)
                    p.morale = max(1, min(100, m - 1))
            except Exception:
                pass
        events.append({
            "kind": "beef",
            "team": team_name,
            "coach": cname,
            "reporter": reporter.name,
            "level": beef.level,
        })


def _maybe_spawn_narrative(league, loser, game_date, rng, events) -> None:
    """Losing grows storylines. Rare, capped league-wide, most fizzle."""
    narrs = getattr(league, "media_narratives", None)
    if narrs is None or len(narrs) >= 6:
        return
    if rng.random() >= 0.05:
        return
    team_name = _team_name(loser)
    if _narrative_for(team_name, league) is not None:
        return  # one storyline per team at a time
    if not _spiraling(loser):
        return

    coach = _head_coach_of(loser)
    cap = _captain_of(loser)
    kind, title, subjects = None, "", []
    if coach is not None and rng.random() < 0.45:
        cname = getattr(coach, "full_name",
                        getattr(coach, "last_name", "the coach"))
        kind, title = "hot_seat", f"{cname} on the hot seat in {team_name}"
    elif cap is not None and rng.random() < 0.6:
        pname = getattr(cap, "full_name", getattr(cap, "last_name", "the captain"))
        kind = "leadership"
        title = f"Questions about the leadership in {team_name}"
        subjects = [getattr(cap, "id", "")]
    else:
        # Goalie controversy: the backup is outplaying the starter.
        goalies = [p for p in (getattr(loser, "roster", []) or [])
                   if str(getattr(getattr(p, "primary_position", None),
                                  "value", "")).upper() == "G"]
        if len(goalies) >= 2:
            try:
                g = sorted(goalies,
                           key=lambda p: _f(p, "save_percentage", 0.9),
                           reverse=True)
                if _f(g[0], "save_percentage", 0) - _f(g[1], "save_percentage", 0) > 0.010:
                    kind, title = "goalie", f"Goalie controversy brewing in {team_name}"
            except Exception:
                pass
    if kind is None:
        # Trade chatter: someone wants out, or a miserable star on a loser.
        for p in (getattr(loser, "roster", []) or []):
            if getattr(p, "transfer_requested", False):
                pname = getattr(p, "full_name", getattr(p, "last_name", "A star"))
                kind, title = "trade_rumor", f"{pname} trade chatter"
                subjects = [getattr(p, "id", "")]
                break
    if kind is None:
        return
    narr = Narrative(kind, team_name, title, subjects)
    narrs.append(narr)
    events.append({"kind": "narrative_spawn", "team": team_name,
                   "narrative": title})


# ---------------------------------------------------------------------------
# Between-periods leadership + the front office speaking up.
# Fully simmed, never interrupts: these resolve inside the sim and land
# as room effects + a line in the news feed.
# ---------------------------------------------------------------------------

def _room_leadership_moment(league, team, won: bool, diff: int,
                            went_ot: bool, game_date, rng, events,
                            ctx: Dict[str, Any]) -> None:
    """The intermission word. In a tight game, somebody stands up between
    periods and says the thing the room needs. No cameras, no drama --
    just a small lift the guys feel. Never in an elimination game: the
    stakes already have everyone's full attention."""
    if ctx.get("big_game"):
        return
    if not (diff <= 2 or went_ot):
        return  # blowouts don't get speeches; they get bag skates
    roster = list(getattr(team, "roster", []) or [])
    if not roster:
        return
    speaker, speaker_attr = _rally_speaker(team)
    if speaker is None:
        return
    if not _moment_ready(team, "rally"):
        return
    avg_morale = sum(_f(p, "morale", 70) for p in roster) / len(roster)
    if (rng.random() >= _rally_likelihood(speaker_attr, went_ot,
                                          avg_morale)
            * ctx.get("key_boost", 1.0)):
        return
    _mark_moment(team, "rally")
    speaker_name = getattr(speaker, "full_name",
                           getattr(speaker, "last_name", "The captain"))
    if _captain_of(team) is speaker:
        quote = ("Between periods, with the game on the line, "
                 f"{speaker_name} stood up and told the room to empty "
                 f"the tank.")
    else:
        quote = (f"{speaker_name} said the quiet part out loud between "
                 f"periods -- and the room responded.")
    lift = 2 if won else 1
    _bump(roster, "happiness", lift)
    _record(team, "intermission_rally", quote, morale_delta=lift, tone="up")
    events.append({"kind": "rally", "team": _team_name(team),
                   "speaker": speaker_name, "note": quote})


def gm_public_backing(league: Any, team: Any, target: str = "room",
                      game_date: Optional[date] = None,
                      rng: Optional[random.Random] = None,
                      user_triggered: bool = False) -> Dict[str, Any]:
    """A GM goes on the record for his people. target: 'room' | 'coach' |
    a Player (backs that player). Public so the Morale window can offer it
    to the user; the AI path calls it rarely on its own.

    Effects are deliberately small: a public vote of confidence steadies
    a room, it doesn't fix a broken team.
    """
    rng = rng or random
    team_name = _team_name(team)
    roster = list(getattr(team, "roster", []) or [])
    gm = _gm_of(team)
    gm_name = (getattr(gm, "full_name", getattr(gm, "last_name", None))
               if gm is not None else None) or f"the {team_name} GM"
    result: Dict[str, Any] = {"ok": True, "target": target}
    if target == "coach":
        coach = _head_coach_of(team)
        cname = (getattr(coach, "full_name",
                         getattr(coach, "last_name", "the coach"))
                 if coach is not None else "the coach")
        narr = next((n for n in (getattr(league, "media_narratives", []) or [])
                     if n.team_name == team_name and n.kind == "hot_seat"),
                    None)
        if narr is not None:
            narr.heat = max(0, narr.heat - 20)
        if coach is not None:
            try:
                coach.gm_trust = max(0, min(100,
                                           _f(coach, "gm_trust", 70) + 3))
            except Exception:
                pass
        _bump(roster, "happiness", 1)
        _record(team, "gm_backing",
                f"{gm_name} gave {cname} an unequivocal public vote of "
                f"confidence. The hot-seat talk cooled.",
                morale_delta=1, tone="up")
        result.update({"coach": cname,
                       "quote": ("“Let me be clear: this is our coach. "
                                 "The noise stops here.”")})
    elif target == "room":
        _bump(roster, "happiness", 2)
        _bump(roster, "morale", 1)
        # One backing, several ways to say it -- the wording follows the
        # room's temperature. (The feed dedupes identical same-day entries,
        # so repeats never spam.)
        try:
            mood_vals = [float(getattr(p, "happiness", 70) or 70)
                         for p in roster]
            mood = sum(mood_vals) / len(mood_vals) if mood_vals else 70.0
        except Exception:
            mood = 70.0
        _variants = [
            (3.0,
             f"{gm_name} went on the record for the room: the group "
             f"in there is the group he believes in.",
             "\u201cI believe in the twenty-three guys in "
             "that room. That's my statement.\u201d"),
            (2.0,
             f"{gm_name} told the press the panic is outside the "
             f"building, not in it.",
             "\u201cThe noise is out there. In here, we're "
             "fine.\u201d"),
            (2.0 if mood < 60 else 0.5,
             f"{gm_name} backed the group -- then challenged them to "
             f"prove him right.",
             "\u201cI believe in them. Now it's on them to show "
             "it.\u201d"),
            (1.5,
             f"{gm_name} kept it brief: he believes in this group, "
             f"full stop.",
             "\u201cI believe in this group. Next question.\u201d"),
        ]
        _eligible = [(w, t, q) for (w, t, q) in _variants if w > 0]
        _total = sum(w for w, _, _ in _eligible)
        _roll = rng.random() * _total
        _acc = 0.0
        _text, _quote = _eligible[0][1], _eligible[0][2]
        for _w, _t, _q in _eligible:
            _acc += _w
            if _roll < _acc:
                _text, _quote = _t, _q
                break
        _record(team, "gm_backing", _text, morale_delta=2, tone="up")
        result.update({"quote": _quote})
    else:
        # A specific player.
        player = target
        pname = getattr(player, "full_name",
                        getattr(player, "last_name", "the player"))
        _bump([player], "morale", 2)
        _bump([player], "happiness", 2)
        for n in (getattr(league, "media_narratives", []) or []):
            if (n.team_name == team_name
                    and getattr(player, "id", None) in (n.subjects or [])):
                n.heat = max(0, n.heat - 15)
        _record(team, "gm_backing",
                f"{gm_name} publicly backed {pname}: “He's part of what "
                f"we're building here.”", morale_delta=1, tone="up")
        result.update({"player": pname,
                       "quote": ("“He's part of what we're building here. "
                                 "I'm not entertaining anything else.”")})
    result["event"] = {"kind": "backing", "team": team_name,
                       "gm": gm_name, "quote": result["quote"]}
    return result


def _gm_backing(league, team, game_date, rng, events) -> None:
    """Rare AI front-office statement, routed into the news feed."""
    try:
        narr = _narrative_for(_team_name(team), league)
        target = "coach" if (narr is not None and narr.kind == "hot_seat") else "room"
        res = gm_public_backing(league, team, target, game_date, rng)
        events.append(res["event"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Daily decay: stories cool, beefs go quiet, reporters drift to the middle
# ---------------------------------------------------------------------------

def media_daily_tick(league: Any,
                     rng: Optional[random.Random] = None) -> None:
    """Cheap once-a-day maintenance. Never raises."""
    try:
        ensure_media_state(league)
        narrs = league.media_narratives
        league.media_narratives = [n for n in narrs if _tick_narrative(n)]
        for b in league.coach_media_beefs:
            b.days_quiet += 1
        league.coach_media_beefs = [b for b in league.coach_media_beefs
                                    if b.days_quiet < 7]
        for r in league.reporters:
            r.credibility += (50.0 - r.credibility) * 0.02
            r.fan_approval += (50.0 - r.fan_approval) * 0.02
    except Exception:
        pass


def _tick_narrative(n: Narrative) -> bool:
    n.heat -= 10.0
    return n.heat > 0


# ---------------------------------------------------------------------------
# Routing: turn events into headlines / news
# ---------------------------------------------------------------------------

def route_events(app: Any, events: List[Dict[str, Any]],
                 game_date: Optional[date] = None) -> int:
    """Deliver cover_game events. Headlines for the spicy stuff, news feed
    for quotes. Returns count delivered. Never raises."""
    n = 0
    for ev in events or []:
        try:
            kind = ev.get("kind")
            if kind in ("fine", "beef", "shutdown"):
                import headlines
                spec = {"kind": {"fine": "media_fine",
                                 "beef": "media_beef",
                                 "shutdown": "narrative_shutdown"}[kind]}
                spec.update({k: v for k, v in ev.items() if k != "kind"})
                if headlines.deliver_spec(app, spec):
                    n += 1
            elif kind in ("quote", "outburst_room", "narrative_spawn",
                          "narrative_poke", "defense", "shield",
                          "backing", "rally"):
                add = getattr(app, "add_news", None)
                if add is not None:
                    add(_news_line(ev))
                    n += 1
        except Exception:
            continue
    return n


def _news_line(ev: Dict[str, Any]) -> str:
    kind = ev.get("kind")
    if kind == "quote":
        return (f"Post-game ({ev.get('team')}): {ev.get('player')} to "
                f"{ev.get('reporter')}: {ev.get('question')} {ev.get('quote')}")
    if kind == "outburst_room":
        return (f"{ev.get('player')} ({ev.get('team')}) unloads post-game: "
                f"{ev.get('quote')}")
    if kind == "narrative_spawn":
        return f"Media notebook: {ev.get('narrative')}."
    if kind == "narrative_poke":
        return (f"{ev.get('reporter')} pressed {ev.get('player')} on the "
                f"{ev.get('narrative')} story. {ev.get('note')}")
    if kind == "defense":
        return (f"{ev.get('player')} ({ev.get('team')}) stood up for the "
                f"room: {ev.get('quote')} {ev.get('note')}")
    if kind == "shield":
        return (f"{ev.get('coach')} ({ev.get('team')}) stepped in front of "
                f"{ev.get('player')}: {ev.get('quote')}")
    if kind == "backing":
        return (f"{ev.get('gm')} goes on the record: {ev.get('quote')}")
    if kind == "rally":
        return f"Room note ({ev.get('team')}): {ev.get('note')}"
    return "Media: something happened."
