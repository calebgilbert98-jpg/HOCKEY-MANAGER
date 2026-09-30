# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Per-team draft boards + pre-draft joint scouting reports.

There is ONE public media consensus board (``prospect.draft_ranking``,
Bob McKenzie-style -- shown in the draft UI). Every club ALSO has its
own private rankings: a team's *board* is the consensus list re-sorted
through the eyes of its own scouting staff. Two independent axes:

1. True ceiling (hidden) -- ``prospect.true_potential_grade``, dealt at
   generation by prospect_development.seed_true_potential. Reality;
   scouts can't see it directly.
2. Perceived ranking (visible) -- consensus + team lists, built from
   scouted signals with noise.

The team score mixes both:

    team_score = (1 - skill_w) * consensus_signal
               + skill_w * true_signal_read
               + noise

``skill_w`` grows with scouting quality (0.05 for terrible departments
-> 0.45 for elite), and ``true_signal_read`` is the staff's read of the
hidden gap between a prospect's true ceiling grade and his displayed
grade: with probability ``read_p`` (0.10 for terrible scouts -> 0.85
for elite) the staff's read lands on the true grade, otherwise they see
only consensus. The gap is measured in ladder steps (true minus
displayed) scaled to ranking points, so a hidden gem (true two steps
above displayed, perceived mid-round) genuinely climbs a good scout's
list -- ~2-3 rounds when read -- while a bad scout's list stays
consensus+noise.

Luck is in the mix by design -- probabilities, not gates:

- Luck floor: even the worst departments keep skill_w = 0.05 and a 10%
  read chance, so they very occasionally stumble into a late gem.
- Luck ceiling: even the best departments keep a 15% miss chance per
  prospect, so elite boards still whiff on gems sometimes.
- No code path hard-gates an outcome to 0% or 100% for any tier.

Awareness (tight, perception-driven): nobody buries a famous name.
Every elite prospect -- consensus top ELITE_TIER_SIZE, plus high-hype
headline prospects (draft_hype >= HYPE_LOCK_THRESHOLD), plus any
``generational`` talent -- appears in every team's top AWARENESS_FLOOR.
The no-brainer clause: ONLY a perceived-generational ``generational``
flag (the obvious McDavid everyone sees coming -- read defensively via
getattr, at most one per class, many classes have none) locks #1 on
all 32 boards. Ordering (loose): after the floor, each team uniformly
shuffles the elite prospects among the top slots they occupy, so all 32
teams agree the elite *names* belong up top but rank them 1st/5th/12th
differently. Hidden elite (true ceiling elite, perceived mid-round, no
flag) get no floor and no lock -- they are treated like any mid-round
prospect, except good scouts' true-signal read lifts them meaningfully
above consensus (never into the top 15; the lift is structurally
capped). Obvious elite busts (high perceived, ordinary true) keep the
awareness floor -- it is perception-driven -- while good scouts
discount them in ordering via the true read.

Down the board, divergence grows with consensus rank (rank-dependent):
picks ~15-90 get the normal scout-quality-scaled divergence; picks 90+
get the largest divergence (late-round chaos, where the goalie gambles
live). Goalies get 1.5x noise on top, because scouts genuinely disagree
most about goalies.

``build_draft_reports`` produces each team's pre-draft joint scouting
report: their private board (full ranking) plus projected picks -- for
each pick the team owns, who they'd take if the draft fell per their
board (overall pick #k -> board[k-1]). Generated ONCE per draft, never
per pick.

Determinism: the module consumes the GLOBAL ``random`` RNG (gauss for
scores, random() for true-signal reads, shuffle for elite ordering).
Callers pin ``random.seed(...)`` before building; the same seed +
league state always yields the same boards and reports. Generation is
stream-neutral -- the global RNG state is snapshot on entry and
restored on exit -- so it never perturbs the rest of the sim's
randomness (e.g. the draft-day trade market's probabilistic draws,
which run downstream of draft setup).

Fog of war: this module reads true_potential_grade only to model each
staff's *perception* -- the grade itself is never surfaced. A team's
own board/report is shown to the user; other teams' boards stay
internal, and the true signal is never exposed directly.
"""

import random

# ----------------------------------------------------------------------
# Tuning (documented rationale)
# ----------------------------------------------------------------------

# BASE_SIGMA = 1.5 ranking points.
#
# Rationale: a draft class spans ~30 draft_ranking points across 224
# prospects. In the dense middle of the class prospects sit ~0.13 points
# apart, but near the top (rounds 1-2, where the money is) consensus
# tiers are ~2-4 points apart.
#
#   sigma = BASE_SIGMA * (1.6 - quality/100)
#
#   - Elite scouts (quality 95): sigma = 1.5 * 0.65 = 0.975.
#     ~68% of their noise falls within +/-1 ranking point, so they
#     re-shuffle *within* a tier but almost never cross tier lines.
#   - League-average scouts (quality 50): sigma = 1.5 * 1.10 = 1.65.
#   - Bad scouts (quality 25): sigma = 1.5 * 1.35 = 2.025.
#     A +/-2 sigma swing (~4 points) crosses a full tier, so bad-scout
#     teams genuinely reach on players and let talent slide.
#
# Chosen small *relative to the 30-point span* (5%) so even the worst
# scouts don't produce absurd boards, while still creating real
# separation between good and bad departments that Spearman correlation
# can measure.
BASE_SIGMA = 1.5

# GOALIE_NOISE_MULT = 1.5.
#
# Rationale: scouts disagree most on goalies (technique vs athleticism
# reads, smaller sample of tracked junior games). Scaled by the same
# rank factor as everyone else, so goalie gambles concentrate where
# they belong: late.
GOALIE_NOISE_MULT = 1.5

# NEED_BUMP = +0.8 ranking points for a prospect at one of the team's
# two weakest position groups (per trade_engine.team_needs), scaled by
# the rank factor (so it nudges within tiers but never overrides the
# awareness floor at the top, and matters more in the chaotic late
# rounds).
#
# Rationale: expressed in ranking points (not a multiplier). 0.8 sits
# between the dense-middle prospect spacing (~0.13, so it flips several
# adjacent names -- the "we like the center a bit more than the winger"
# effect) and the typical top-of-class tier gap (~2-4 points, which it
# cannot cross).
NEED_BUMP = 0.8

# Teams with no scout at all draft at this quality (league average).
DEFAULT_SCOUTING_QUALITY = 50.0

# Rank-dependent divergence: sigma_eff = sigma_base(quality) *
# rank_factor(consensus_rank).
#   1-10   -> 0.15   elite tier: well-scouted, tight awareness cluster
#   10-15  -> ramp 0.15 -> 1.0 (linear)
#   15-90  -> 1.0    normal scout-quality-scaled divergence
#   90-115 -> ramp 1.0 -> 1.8 (linear)
#   115+   -> 1.8    late-round chaos
RANK_FACTOR_TOP = 0.15
RANK_FACTOR_MID = 1.0
RANK_FACTOR_LATE = 1.8
_TOP_BAND_END = 10
_MID_BAND_START = 15
_MID_BAND_END = 90
_LATE_BAND_FULL = 115

# ELITE_TIER_SIZE = 12: the consensus top-12 are "elite" for awareness
# purposes. AWARENESS_FLOOR = 15: no elite prospect sits below rank 15
# on any team's board. The top ~10-15 is where the shuffle happens, so
# the floor has headroom above the tier.
ELITE_TIER_SIZE = 12
AWARENESS_FLOOR = 15

# HYPE_LOCK_THRESHOLD = 80: draft_hype >= 80 joins the elite awareness
# set (the headline name appears in every team's top-15) but gets NO
# order lock -- hype is an awareness guarantee only. draft_hype is read
# defensively via getattr (it may be absent).
HYPE_LOCK_THRESHOLD = 80

# ANCHOR_WINDOW / ANCHOR_DAMP: prospects within +-8 consensus slots of
# an elite rank get 0.5x divergence. Rationale: boards are calibrated
# *around* consensus anchors -- the tier sitting right below famous
# names stays coherent instead of churning through them.
ANCHOR_WINDOW = 8
ANCHOR_DAMP = 0.5


# Skill-weighted true signal.
#
# Rationale: scouting must be REWARDED through the lists, not pure
# luck. prospect_development.seed_true_potential deals every prospect a
# hidden true_potential_grade (letter ladder F..A+); some mid/late
# prospects secretly carry a higher true ceiling than their perceived
# (consensus) value -- the Datsyuk/Zetterberg seeds. A team's list mixes
# the perceived consensus signal with the staff's read of that hidden
# gap:
#
#     team_score = (1 - skill_w) * consensus_pts
#                + skill_w * true_read_pts
#                + gauss(0, sigma)
#
# true_read_pts: with probability read_p(quality) the staff's read of
# THIS prospect lands on his true grade; otherwise the staff sees only
# consensus (read = consensus_pts, i.e. no lift). The read moves the
# score by w * gap_pts, where gap_pts is (true grade - displayed grade)
# in ladder steps scaled to ranking points (one step = class span /
# 11). Ordinary prospects (true == displayed) have gap exactly 0, so
# reads never move them -- their ordering stays pure consensus+noise,
# and no grade->points mapping bias can leak in. A natural max gem
# (+2 steps, the Datsyuk/Zetterberg tier) is worth ~2/11 of the class
# span when read: an elite staff lifts him ~2-3 rounds above consensus,
# never into the top 15 from mid-round.
#
# Calibration -- luck floor AND ceiling (probabilities, never gates):
#   skill_w(q) = 0.05 + 0.40 * clamp((q - 35) / 65, 0, 1)
#     q <= 35 -> 0.05  (luck floor: terrible departments still move a
#                        whisper toward truth when they get a read)
#     q = 90  -> ~0.39 (elite: a true "A" hidden at consensus ~#100
#                        lifts ~30 slots when read)
#     q = 100 -> 0.45
#   read_p(q)  = 0.10 + 0.75 * clamp((q - 35) / 55, 0, 1)
#     q <= 35 -> 0.10  (luck floor: bad scouts very occasionally
#                        stumble into a gem -- right place, right time)
#     q >= 90 -> 0.85  (luck ceiling: elite departments still miss
#                        ~15% of prospects completely)
#
# No tier is hard-gated: every team has read_p strictly between 0 and 1
# and skill_w > 0, so every outcome stays on the table for every team;
# quality only shifts the odds.
SKILL_W_FLOOR = 0.05
SKILL_W_MAX = 0.45
SKILL_W_BASE_Q = 35.0
READ_P_FLOOR = 0.10
READ_P_CEIL = 0.85
READ_P_BASE_Q = 35.0
READ_P_FULL_Q = 90.0

# Letter ladder for true_potential_grade (mirrors
# prospect_development.POTENTIAL_LADDER; hardcoded to avoid an import).
_GRADE_LADDER = ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+",
                 "A-", "A", "A+"]


def _head_scout(team):
    """Return the team's head scout Staff, or None if none is found.

    Defensive: Team.staff may be missing, None, or non-list; a staff
    member's role may be a StaffRole enum or a plain string.
    """
    staff = getattr(team, "staff", None) or []
    head = None
    for s in staff:
        try:
            role = getattr(s, "role", None)
            val = getattr(role, "value", role)
            text = str(val or "").upper()
        except Exception:
            continue
        if "HEAD" in text and "SCOUT" in text:
            return s  # head scout always wins
        if head is None and "SCOUT" in text:
            head = s  # fallback: best available scout
    return head


def scouting_quality(team) -> float:
    """Scouting quality 0-100 for a team: the head scout's average of
    judging_player_ability and judging_player_potential.

    Returns DEFAULT_SCOUTING_QUALITY (50.0, league average) when the team
    has no scout on staff or the attributes are unavailable. Clamped to
    [0, 100].
    """
    scout = _head_scout(team)
    if scout is None:
        return DEFAULT_SCOUTING_QUALITY
    try:
        jpa = float(getattr(scout, "judging_player_ability"))
        jpp = float(getattr(scout, "judging_player_potential"))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_SCOUTING_QUALITY
    q = (jpa + jpp) / 2.0
    return max(0.0, min(100.0, q))


def _rank_factor(consensus_rank: int) -> float:
    """Divergence multiplier for a consensus rank (1-based)."""
    r = consensus_rank
    if r <= _TOP_BAND_END:
        return RANK_FACTOR_TOP
    if r < _MID_BAND_START:
        # linear ramp 0.15 -> 1.0 across ranks 10..15
        t = (r - _TOP_BAND_END) / (_MID_BAND_START - _TOP_BAND_END)
        return RANK_FACTOR_TOP + t * (RANK_FACTOR_MID - RANK_FACTOR_TOP)
    if r <= _MID_BAND_END:
        return RANK_FACTOR_MID
    if r < _LATE_BAND_FULL:
        # linear ramp 1.0 -> 1.8 across ranks 90..115
        t = (r - _MID_BAND_END) / (_LATE_BAND_FULL - _MID_BAND_END)
        return RANK_FACTOR_MID + t * (RANK_FACTOR_LATE - RANK_FACTOR_MID)
    return RANK_FACTOR_LATE


def _sigma_for(quality: float, is_goalie: bool) -> float:
    sigma = BASE_SIGMA * (1.6 - quality / 100.0)
    if is_goalie:
        sigma *= GOALIE_NOISE_MULT
    return max(sigma, 0.05)


def _skill_weight(quality: float) -> float:
    """Mix weight on the true-signal read: 0.05 (luck floor) at
    quality <= 35, ramping to 0.45 at quality 100."""
    t = (quality - SKILL_W_BASE_Q) / (100.0 - SKILL_W_BASE_Q)
    t = max(0.0, min(1.0, t))
    return SKILL_W_FLOOR + (SKILL_W_MAX - SKILL_W_FLOOR) * t


def _read_prob(quality: float) -> float:
    """Per-prospect probability the staff's read lands on the true
    grade: 0.10 (luck floor) at quality <= 35, 0.85 (luck ceiling) at
    quality >= 90. Never 0 or 1."""
    t = (quality - READ_P_BASE_Q) / (READ_P_FULL_Q - READ_P_BASE_Q)
    t = max(0.0, min(1.0, t))
    return READ_P_FLOOR + (READ_P_CEIL - READ_P_FLOOR) * t


def _true_gap_pts(prospect, pts_per_step: float) -> float:
    """Hidden gap in draft_ranking points: (true grade - displayed grade)
    in ladder steps, scaled to ranking points.

    The hidden information is exactly what generation dealt on top of
    the displayed grade (seed_true_potential's 0/+1/+2 bumps, the goalie
    boom/bust pre-rolls). Ordinary prospects -- true == displayed --
    have gap exactly 0, so reads never move them: their ordering stays
    pure consensus+noise, and the grade->points mapping can carry no
    systematic bias. Unparseable/missing grades -> 0."""
    try:
        true_g = (getattr(prospect, "true_potential_grade", "")
                  or "").strip().upper()
        disp_g = (getattr(prospect, "potential_grade", "")
                  or "").strip().upper()
    except Exception:
        return 0.0
    if true_g not in _GRADE_LADDER or disp_g not in _GRADE_LADDER:
        return 0.0
    steps = _GRADE_LADDER.index(true_g) - _GRADE_LADDER.index(disp_g)
    return steps * pts_per_step


def _elite_set(prospects, consensus_rank):
    """(elite_ids, generational) for a consensus-sorted prospect list.

    elite_ids: id()s of the awareness set -- consensus top
    ELITE_TIER_SIZE plus high-hype (draft_hype >= HYPE_LOCK_THRESHOLD)
    prospects. generational: the (single, optional) prospect with the
    generational flag, read defensively.
    """
    elite_ids = set()
    generational = None
    for p in prospects:
        cr = consensus_rank[id(p)]
        try:
            hype = float(getattr(p, "draft_hype", 0) or 0)
        except (TypeError, ValueError):
            hype = 0.0
        try:
            is_gen = bool(getattr(p, "generational", False))
        except Exception:
            is_gen = False
        if cr <= ELITE_TIER_SIZE or hype >= HYPE_LOCK_THRESHOLD:
            elite_ids.add(id(p))
        if is_gen and generational is None:
            generational = p  # at most one per class; first wins
    return elite_ids, generational


def build_team_boards(league) -> dict:
    """Build every NHL team's draft board.

    Returns {team_name: [prospects in that team's order]}. Pipeline per
    team: score = (1 - skill_w) * consensus + skill_w * true_read +
    rank-dependent noise -> sort -> awareness floor (elite prospects
    can't sit below AWARENESS_FLOOR) -> uniform shuffle of the elite prospects among the top slots they occupy (loose
    ordering: tight awareness, staff's own call on order) ->
    generational #1 lock (only a generational talent is #1 on all 32
    lists). Deterministic given a pinned global RNG seed.

    Stream-neutral: the global RNG state is snapshot on entry and
    restored on exit, so board generation never perturbs the rest of
    the sim's randomness (e.g. the draft-day trade market's
    probabilistic draws, which run downstream of draft setup).
    Internally it still uses random.gauss / random.shuffle on the
    global RNG -- a pinned seed therefore reproduces identical boards.

    Team needs come from trade_engine.team_needs (read-only use).
    """
    _rng_state = random.getstate()
    try:
        return _build_team_boards_inner(league)
    finally:
        random.setstate(_rng_state)


def _build_team_boards_inner(league) -> dict:
    try:
        import trade_engine as te
        _team_needs = te.team_needs
    except Exception:
        _team_needs = lambda _t: []  # noqa: E731 -- degrade to no need bump

    prospects = list(getattr(league, "draft_prospects", None) or [])
    # Fixed iteration order so RNG consumption is deterministic: one
    # gaussian per (team, prospect) in a stable order, then one shuffle
    # per team in a stable team order.
    prospects = sorted(prospects,
                       key=lambda p: getattr(p, "draft_ranking", 0),
                       reverse=True)
    consensus_rank = {id(p): i + 1 for i, p in enumerate(prospects)}
    elite_ids, generational = _elite_set(prospects, consensus_rank)

    # Anchor ranks for the calibration damping (elite consensus ranks).
    anchor_ranks = {consensus_rank[pid] for pid in elite_ids}

    def _anchor_damp(cr):
        for lr in anchor_ranks:
            if abs(cr - lr) <= ANCHOR_WINDOW:
                return ANCHOR_DAMP
        return 1.0

    # Class scale: one ladder step of hidden grade gap is worth this many
    # ranking points (class span / 11 steps). A natural max gem (+2 steps)
    # is therefore worth ~2/11 of the class span when read.
    _rank_vals = [float(getattr(p, "draft_ranking", 0) or 0)
                  for p in prospects]
    _span = (max(_rank_vals) - min(_rank_vals)) if _rank_vals else 0.0
    _pts_per_step = (_span / (len(_GRADE_LADDER) - 1)) if _span > 0 else 0.0

    teams = [t for t in getattr(league, "teams", None) or []
             if getattr(t, "league_name", "") == "National Hockey League"]
    boards = {}
    for team in teams:
        quality = scouting_quality(team)
        try:
            needs = list(_team_needs(team) or [])[:2]
        except Exception:
            needs = []
        w = _skill_weight(quality)
        read_p = _read_prob(quality)
        scored = []
        for p in prospects:
            base = float(getattr(p, "draft_ranking", 0) or 0)
            try:
                pos = p.primary_position.value
            except Exception:
                pos = "?"
            crank = consensus_rank[id(p)]
            factor = _rank_factor(crank) * _anchor_damp(crank)
            sigma = _sigma_for(quality, is_goalie=(pos == "G")) * factor
            # Skill-weighted true signal: the staff's read of the hidden
            # gap between true ceiling and perceived value. With
            # probability read_p the read lands on the true grade (the
            # list moves w * gap toward truth); otherwise the staff sees
            # only consensus. One uniform draw per (team, prospect) in
            # fixed order keeps the RNG stream deterministic.
            gap = _true_gap_pts(p, _pts_per_step)
            lift = w * gap if random.random() < read_p else 0.0
            score = base + lift + random.gauss(0.0, sigma)
            if pos in needs:
                score += NEED_BUMP * factor
            scored.append((score, p))
        scored.sort(key=lambda s: s[0], reverse=True)
        ordered = [p for _s, p in scored]

        # Awareness floor: no elite prospect below AWARENESS_FLOOR.
        # Batch the pull-ups so they can't push each other back down:
        # remove all stragglers, then reinsert at ranks floor, floor-1,
        # ... (all within the top AWARENESS_FLOOR).
        stragglers = [p for p in ordered
                      if id(p) in elite_ids
                      and ordered.index(p) >= AWARENESS_FLOOR]
        for p in stragglers:
            ordered.remove(p)
        for i, p in enumerate(stragglers):
            ordered.insert(max(0, AWARENESS_FLOOR - 1 - i), p)

        # Loose elite ordering: uniformly shuffle the elite prospects
        # among the top slots they occupy. Every team agrees the elite
        # names belong up top; the ORDER is the staff's own call.
        # Non-elite prospects that earned top-15 slots keep them.
        elite_slots = [i for i in range(min(AWARENESS_FLOOR, len(ordered)))
                       if id(ordered[i]) in elite_ids]
        elite_here = [ordered[i] for i in elite_slots]
        random.shuffle(elite_here)
        for i, p in zip(elite_slots, elite_here):
            ordered[i] = p

        # The no-brainer clause: ONLY a generational talent is #1 on
        # every team's list.
        if generational is not None:
            _gid = id(generational)
            for _i, _p in enumerate(ordered):
                if id(_p) == _gid:
                    del ordered[_i]
                    break
            ordered.insert(0, generational)

        try:
            name = team.team_name
        except Exception:
            name = str(team)
        boards[name] = ordered
    return boards


def build_draft_reports(league, draft_order) -> dict:
    """Build every NHL team's pre-draft joint scouting report.

    Returns {team_name: {"team_name", "board", "projected_picks"}}.

    - "board": the team's TRUE draft ranking -- the FULL board (all
      prospects; cheap object references -- the UI shows the top 40).
    - "projected_picks": [{"round", "overall", "prospect"}] for each
      pick the team owns in this draft, mapping rankings onto owned
      slots: if the draft fell exactly per their board, overall pick #k
      would land them board[k-1]. "prospect" is None if the board is
      exhausted (can't happen with a full 224-class, guarded anyway).

    draft_order is the DraftView.draft_order shape: iterable of
    (round_num, team, draft_pick). Generated ONCE per draft, never per
    pick. Deterministic given a pinned global RNG seed (via
    build_team_boards).
    """
    boards = build_team_boards(league)
    owned = {}
    for overall, entry in enumerate(draft_order or [], 1):
        try:
            rnd, team, _dp = entry
            tname = team.team_name
        except Exception:
            continue
        owned.setdefault(tname, []).append((rnd, overall))
    reports = {}
    for tname, board in boards.items():
        proj = []
        for rnd, overall in owned.get(tname, []):
            p = board[overall - 1] if 0 <= overall - 1 < len(board) else None
            proj.append({"round": rnd, "overall": overall,
                         "prospect": p})
        reports[tname] = {"team_name": tname, "board": board,
                          "projected_picks": proj}
    return reports


def team_rank_of(board_dict, team_name, prospect):
    """1-based rank of a prospect on a team's board, or None."""
    board = (board_dict or {}).get(team_name)
    if not board:
        return None
    pid = getattr(prospect, "id", None)
    for i, p in enumerate(board, 1):
        if getattr(p, "id", None) == pid:
            return i
    return None
