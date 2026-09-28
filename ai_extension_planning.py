"""AI GM extension planning: think like a user with a franchise piece due.

A user who has his franchise center needing $15M next summer does not burn
$9M on a questionable second-pair guy today. He plans a year out: the core
gets its money reserved first, and everything else is spent from what's
left. This module gives every AI GM the same forward book.

A "franchise piece" is deliberately NOT just current star power. It
includes the young players the GM considers crucial to the franchise's
future -- the 20-year-old B-potential first-rounder at 74 overall whose
second contract is the coming crunch -- regardless of face value. Which
young players count as "crucial" moves with the GM: a loyal GM treasures
his homegrown kids, a patient GM bets on development, an aggressive GM
only sees the finished product.

One rulebook, both sides: eligibility for an actual extension offer goes
through transaction_windows.check_window("extension", ...), the exact
function gating the user's path. The AI never gets a wider or narrower
window than the user.

Public surface:
    plan(team, identity, strategy, ask_fn, cap_ceiling, current_charge,
         current_date, league_min) -> ExtensionPlan

ExtensionPlan fields:
    pieces        ordered list of (player, score) -- franchise core, best first
    queue         ordered candidate list of dicts for the current pass:
                  {player, priority (0..1), is_piece, max_offer, reason}
    reserved      dollars that must stay unspent (future core raises)
    discretionary dollars safe to spend on non-core deals right now
    crunch        True when even the core doesn't fit -- pieces only, no depth
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

_POTENTIAL_PTS = {"A": 40.0, "B": 30.0, "C": 15.0, "D": 5.0, "F": 0.0}

_PIECE_SCORE_THRESHOLD = 50.0
_STAR_OVERRIDE_OVR = 86  # 86+ overall is a star by any measure


def _ovr100(player) -> int:
    try:
        from game_classes import to_100_scale as _t100
        return int(_t100(player.overall_rating()))
    except Exception:
        try:
            return int(player.overall_rating())
        except Exception:
            return 75


def _years_remaining(player) -> int:
    try:
        return int(getattr(getattr(player, "contract", None),
                           "years_remaining", 0) or 0)
    except Exception:
        return 0


def _current_salary(player) -> int:
    try:
        return int(getattr(getattr(player, "contract", None), "salary", 0) or 0)
    except Exception:
        return 0


def _age(player) -> int:
    try:
        return int(getattr(player, "age", 27) or 27)
    except Exception:
        return 27


def _potential_grade(player) -> str:
    try:
        g = str(getattr(player, "potential_grade", "") or "").strip().upper()
        if g in _POTENTIAL_PTS:
            return g
        tg = str(getattr(player, "true_potential_grade", "") or "").strip().upper()
        return tg if tg in _POTENTIAL_PTS else ""
    except Exception:
        return ""


def gm_ability01(identity) -> float:
    """0..1 read on how good this GM is at the money side of the job.

    Tenure + experience + reputation. A 20-year Cup winner projects the
    market; a first-year interim gets surprised by it.
    """
    try:
        exp = float(getattr(identity, "experience_years", 10) or 0)
        ten = float(getattr(identity, "tenure_years", 2) or 0)
        rep = float(getattr(identity, "reputation", 50) or 50)
        ability = 0.45 * min(1.0, exp / 18.0) + 0.25 * min(1.0, ten / 8.0) \
            + 0.30 * max(0.0, min(1.0, rep / 100.0))
        return max(0.05, min(1.0, ability))
    except Exception:
        return 0.5


def franchise_score(player, identity=None, strategy=None) -> float:
    """0..100: how much of a franchise piece this player is to this GM.

    Star power counts, but so does the future the GM sees in a young
    player -- potential grade, draft pedigree, homegrown status -- even
    when the current overall doesn't show it yet.
    """
    ovr = _ovr100(player)
    age = _age(player)
    try:
        patience = float(getattr(identity, "patience", 0.5) or 0.5)
        loyalty = float(getattr(identity, "loyalty", 0.5) or 0.5)
        aggression = float(getattr(identity, "aggression", 0.5) or 0.5)
    except Exception:
        patience = loyalty = aggression = 0.5

    # Face value: what he is right now.
    star_part = max(0.0, min(1.0, (ovr - 75) / 20.0)) * 55.0
    # An aggressive GM only respects the finished product.
    star_part *= 0.85 + 0.3 * aggression

    # Future value: what the GM believes he's becoming, regardless of
    # today's overall. Youth-gated: a 30-year-old "B prospect" isn't one.
    grade = _potential_grade(player)
    if age <= 21:
        youth_mult = 1.0
    elif age <= 23:
        youth_mult = 0.8
    elif age <= 25:
        youth_mult = 0.5
    else:
        youth_mult = 0.12
    future_part = _POTENTIAL_PTS.get(grade, 0.0) * youth_mult
    # A patient GM bets on development; an impatient one discounts it.
    future_part *= 0.7 + 0.6 * patience

    # Draft pedigree: the room remembers where you were picked.
    try:
        rnd = int(getattr(player, "draft_round", 0) or 0)
    except Exception:
        rnd = 0
    pedigree = 8.0 if rnd == 1 else (4.0 if rnd == 2 else 0.0)

    # Homegrown: drafted/signed by this club. A loyal GM treasures his own.
    homegrown = 0.0
    try:
        team_name = getattr(getattr(identity, "team_name", ""), "strip",
                            lambda: "")() if identity is not None else ""
    except Exception:
        team_name = ""
    try:
        drafted_by = str(getattr(player, "drafted_by", "") or "")
        rights_team = str(getattr(player, "rights_team", "") or "")
        if team_name and (drafted_by == team_name or rights_team == team_name):
            homegrown = 10.0 * (0.5 + loyalty)
    except Exception:
        pass

    # ELC kicker: the second contract is the classic cap crunch, and a
    # GM who lived it plans for it.
    elc_kicker = 0.0
    try:
        if bool(getattr(getattr(player, "contract", None),
                        "entry_level", False)):
            elc_kicker = 5.0
    except Exception:
        pass

    return min(100.0, star_part + future_part + pedigree + homegrown
               + elc_kicker)


def is_franchise_piece(player, identity=None, strategy=None) -> bool:
    """True when this GM treats the player as core -- now or in the future."""
    if _ovr100(player) >= _STAR_OVERRIDE_OVR:
        return True
    return franchise_score(player, identity, strategy) >= _PIECE_SCORE_THRESHOLD


def project_extension_cost(player, ask_fn: Callable, identity=None,
                           cap_ceiling: int = 104_000_000) -> int:
    """What the GM *thinks* the next deal costs: the shared ask machinery,
    bent by his ability.

    Good GMs project within a couple percent. Bad GMs misjudge both ways:
    they lowball what stars will demand (cap surprise coming) and overrate
    what depth is worth (the overpay pipeline). Deterministic -- no RNG, so
    plans are stable and testable.
    """
    try:
        ask = int(ask_fn(player) or 0)
    except Exception:
        ask = 0
    if ask <= 0:
        return 0
    ability = gm_ability01(identity)
    miss = max(0.0, 0.5 - ability)  # 0 for a good GM, up to ~0.45 for a bad one
    is_star_ask = ask >= 0.08 * cap_ceiling
    if is_star_ask:
        # Underestimates the star market -- the surprise is coming.
        factor = 1.0 - miss * 0.25
    else:
        # Overrates depth -- the overpay pipeline.
        factor = 1.0 + miss * 0.20
    try:
        from salary_cap_system import league_minimum_salary as _lms
        floor = int(_lms())
    except Exception:
        floor = 775_000
    return max(floor, int(ask * factor))


@dataclass
class ExtensionPlan:
    team_name: str = ""
    pieces: List[Tuple[Any, float]] = field(default_factory=list)
    queue: List[Dict[str, Any]] = field(default_factory=list)
    reserved: int = 0
    discretionary: int = 0
    crunch: bool = False
    reasoning: List[str] = field(default_factory=list)


def _priority_of_strategy(strategy) -> str:
    try:
        p = getattr(strategy, "priority", None)
        return str(getattr(p, "value", p) or "").upper()
    except Exception:
        return ""


def plan(team, identity=None, strategy=None,
         ask_fn: Optional[Callable] = None,
         cap_ceiling: int = 104_000_000,
         current_charge: int = 0,
         current_date=None,
         league_min: int = 775_000) -> ExtensionPlan:
    """Build the forward book for one club.

    1. Identify franchise pieces (stars + the young future core).
    2. Project each piece's next deal; reserve the *raise* (new money).
    3. Everything else spends from what's left.
    """
    roster = list(getattr(team, "roster", None) or [])
    team_name = str(getattr(team, "team_name", "") or "")
    strat = _priority_of_strategy(strategy)
    try:
        aggression = float(getattr(identity, "aggression", 0.5) or 0.5)
        loyalty = float(getattr(identity, "loyalty", 0.5) or 0.5)
        patience = float(getattr(identity, "patience", 0.5) or 0.5)
    except Exception:
        aggression = loyalty = patience = 0.5

    ep = ExtensionPlan(team_name=team_name)

    # -- 1. who is core -------------------------------------------------
    scored = []
    for p in roster:
        try:
            if getattr(p, "contract", None) is None:
                continue
            s = franchise_score(p, identity, strategy)
            piece = s >= _PIECE_SCORE_THRESHOLD or _ovr100(p) >= _STAR_OVERRIDE_OVR
            # A rebuilder's "core" is the kids; a 33-year-old 84 is an asset.
            if piece and strat == "REBUILD" and _age(p) > 28 \
                    and _ovr100(p) < _STAR_OVERRIDE_OVR:
                piece = False
            scored.append((p, s, piece))
        except Exception:
            continue
    scored.sort(key=lambda t: t[1], reverse=True)
    ep.pieces = [(p, s) for (p, s, piece) in scored if piece]

    # -- 2. reserve the raises ------------------------------------------
    # years_remaining==1: extendable now. ==0 in June: exclusive re-sign
    # window (post-decrement, pre-July-1). ==2: can't extend yet (window
    # closed) but the money must still be there next summer.
    reserved = 0
    for (p, s, piece) in scored:
        if not piece:
            continue
        yr = _years_remaining(p)
        if yr not in (0, 1, 2):
            continue
        proj = project_extension_cost(p, ask_fn, identity, cap_ceiling) \
            if ask_fn else 0
        if proj <= 0:
            continue
        delta = max(0, proj - _current_salary(p))
        reserved += delta
        if yr == 2:
            ep.reasoning.append(
                f"reserved ${delta:,} raise for "
                f"{getattr(p, 'full_name', 'piece')} (due next year)")
    ep.reserved = reserved

    # -- 3. what's left ---------------------------------------------------
    # Next year's committed money: this year's charge minus the deals that
    # end (they're either re-signed above or walk), plus roster-fill floor.
    expiring_now = sum(_current_salary(p) for (p, s, piece) in scored
                       if _years_remaining(p) <= 1)
    signed_beyond = sum(1 for (p, s, piece) in scored
                        if _years_remaining(p) >= 2)
    fill_need = max(0, 20 - signed_beyond)
    committed_next = max(0, current_charge - expiring_now)
    need_next = committed_next + reserved + fill_need * league_min
    ep.discretionary = int(cap_ceiling - need_next)
    ep.crunch = ep.discretionary < league_min
    if ep.crunch:
        ep.reasoning.append(
            f"cap crunch: ${ep.discretionary:,} discretionary -- pieces only")

    # -- 4. the queue -----------------------------------------------------
    # Extension window check is the shared rulebook (same as the user).
    try:
        import transaction_windows as _tw
    except Exception:
        _tw = None
    for (p, s, piece) in scored:
        yr = _years_remaining(p)
        if yr not in (0, 1):
            continue
        eligible = True
        if _tw is not None:
            try:
                eligible, _why = _tw.check_window(
                    "extension", current_date, ctx={"player": p})
            except Exception:
                eligible = True
        if not eligible:
            continue
        try:
            from player_decision import wants_out as _wo
            if _wo(p):
                continue  # holdout path, not the extension table
        except Exception:
            pass
        proj = project_extension_cost(p, ask_fn, identity, cap_ceiling) \
            if ask_fn else 0
        # Priority: pieces first, then by value. Personality moves it:
        # aggression extends early and pays to lock; patience waits.
        priority = 0.55 + 0.45 * (s / 100.0) if piece else 0.20 + 0.35 * (s / 100.0)
        max_offer = proj
        if piece and aggression >= 0.65:
            # Lock him now: pay the ask plus a sweetener, beat next year's
            # market (the Carlsson lesson).
            max_offer = int(proj * 1.03)
            priority = min(1.0, priority + 0.08)
        if piece and patience >= 0.65:
            # Won't bid against himself.
            max_offer = min(max_offer, proj)
        try:
            drafted_by = str(getattr(p, "drafted_by", "") or "")
            if piece and loyalty >= 0.65 and drafted_by == team_name:
                max_offer = int(max_offer * 1.05)
        except Exception:
            pass
        ep.queue.append({
            "player": p,
            "priority": round(min(1.0, max(0.0, priority)), 3),
            "is_piece": piece,
            "score": round(s, 1),
            "years_remaining": yr,
            "projected": proj,
            "max_offer": max_offer,
            "reason": ("franchise piece" if piece else "depth")
                      + f" (score {s:.0f})",
        })
    ep.queue.sort(key=lambda q: q["priority"], reverse=True)
    return ep
