# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Voluntary captaincy changes: deposing a captain has consequences.

Fantasy drafts leave every roster letter-less by design; captains are set
at the start of preseason. But when a GM *replaces* an established captain
mid-stream -- stripping the C from X to hand it to Y -- X reacts. The
reaction depends on:

- the worthiness gap: does the room see Y as plainly more worthy?
- X's personality: controversy (volatility), loyalty, determination
- X's situation: captaincy tenure, happiness, team form
- whether the GM spoke with X first (the conversation)

Tiers, mild to extreme:

- graceful:  X accepts; a classy handover, small dip.
- grumbles:  X sulks; morale/happiness dip, minor controversy bump.
- pushback:  X goes public; the GM faces a judgment call --
             stand firm, compromise (name him alternate), or back down.
- extreme:   X requests a trade, or goes cold on the organization
             (a GM grudge needing major repair to lose).

User and AI share assess/apply. The user gets the judgment-call dialogs;
the AI resolves the conversation by die roll.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

try:
    from reputation_system import (ensure_reputation_fields,
                                   contract_loyalty)
except Exception:  # pragma: no cover - headless import safety
    def ensure_reputation_fields(e):
        return None

    def contract_loyalty(p):
        return 0.5


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _name(p: Any) -> str:
    try:
        return getattr(p, "full_name", None) or "the captain"
    except Exception:
        return "the captain"


def _num(p: Any, attr: str, default: float = 50.0) -> float:
    try:
        v = getattr(p, attr, default)
        return float(v if v is not None else default)
    except Exception:
        return float(default)


def _win_pct(team: Any, league: Any) -> float:
    try:
        st = (getattr(league, "standings", None) or {}).get(
            getattr(team, "team_name", ""), {})
        w = float(st.get("W", 0) or 0)
        l = float(st.get("L", 0) or 0)
        o = float(st.get("OTL", 0) or 0)
        gp = w + l + o
        return (w + 0.5 * o) / gp if gp > 0 else 0.5
    except Exception:
        return 0.5


def is_established_captain(p: Any) -> bool:
    """A deposition only stings when the C was truly his.

    Tenure accrues in the offseason growth pass, so a captain named five
    minutes ago (tenure 0) doesn't trigger drama when re-picked.
    """
    try:
        return int(getattr(p, "captain_tenure_years", 0) or 0) >= 1
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

def worthiness_gap(old: Any, new: Any) -> float:
    """How much more worthy is the successor? Leadership first, impact
    second. Positive means the room can see why."""
    try:
        gap = _num(new, "leadership", 50) - _num(old, "leadership", 50)
    except Exception:
        gap = 0.0
    if new is None:
        return -6.0  # stripped with no successor: nobody to respect
    try:
        # Star impact counts: a point-per-game successor is plainly the guy.
        s = getattr(new, "stats", None)
        pts = float(getattr(s, "points", 0) or 0)
        gp = float(getattr(s, "games_played", 0) or 0)
        if gp >= 20:
            ppg = pts / gp
            if ppg >= 1.0:
                gap += 3.0
            elif ppg >= 0.75:
                gap += 1.5
    except Exception:
        pass
    return gap


def assess_deposition(old: Any, new: Any, team: Any,
                      league: Any = None) -> Dict[str, Any]:
    """How will `old` react to losing the C to `new`?

    Returns acceptance (0..1), the tier on a neutral roll, the worthiness
    gap, and human-readable reasons for the dialog.
    """
    try:
        ensure_reputation_fields(old)
    except Exception:
        pass
    gap = worthiness_gap(old, new)
    vol = _num(old, "controversy", 20) / 100.0
    try:
        loyalty = float(contract_loyalty(old))
    except Exception:
        loyalty = 0.5
    tenure = _num(old, "captain_tenure_years", 0)
    happy = _num(old, "happiness", 70)
    deter = _num(old, "determination", 60)
    win_pct = _win_pct(team, league)

    acceptance = 0.55
    acceptance += max(-0.30, min(0.30, gap * 0.022))
    acceptance += (loyalty - 0.5) * 0.60
    acceptance -= vol * 0.45
    acceptance -= min(tenure, 6) * 0.05
    acceptance += (0.5 - win_pct) * 0.50
    acceptance += (deter - 60) / 100.0 * 0.20
    acceptance += (happy - 70) / 100.0 * 0.30
    acceptance = max(0.02, min(0.98, acceptance))

    reasons: List[str] = []
    if gap >= 8:
        reasons.append(
            f"{_name(new)} has plainly passed him as a leader "
            f"({int(_num(new, 'leadership'))} vs "
            f"{int(_num(old, 'leadership'))}) -- the room can see why.")
    elif gap <= -4:
        reasons.append(
            f"On merit {_name(old)} is still the stronger leader -- "
            "this will look political.")
    if tenure >= 4:
        reasons.append(
            f"{int(tenure)} years wearing the C -- it's part of his "
            "identity now.")
    if vol >= 0.6:
        reasons.append("He's volatile; embarrassment turns to anger fast.")
    if loyalty >= 0.75:
        reasons.append("He's a loyal soldier -- betrayal will cut deeper "
                       "than anger.")
    if win_pct < 0.42:
        reasons.append("The losing gives you cover: something had to change.")
    if win_pct > 0.60:
        reasons.append("The team is winning -- he'll ask what he did wrong.")
    if happy < 55:
        reasons.append("He's already unhappy; this may be the last straw.")

    return {
        "acceptance": round(acceptance, 3),
        "worthiness_gap": round(gap, 1),
        "reasons": reasons,
        "volatility": round(vol, 3),
        "loyalty": round(loyalty, 3),
    }


def roll_tier(acceptance: float,
              rng: Any = random) -> str:
    """graceful / grumbles / pushback / extreme from an acceptance 0..1."""
    r = rng.random()
    if r < acceptance * 0.5:
        return "graceful"
    if r < acceptance:
        return "grumbles"
    if r < acceptance + (1.0 - acceptance) * 0.6:
        return "pushback"
    return "extreme"


# ---------------------------------------------------------------------------
# Applying the change (shared user + AI)
# ---------------------------------------------------------------------------

def _bump(p: Any, attr: str, delta: float, lo: float = 0.0,
          hi: float = 100.0) -> None:
    try:
        v = _num(p, attr, 70.0) + delta
        setattr(p, attr, max(lo, min(hi, v)))
    except Exception:
        pass


def gm_grudge(p: Any) -> float:
    """0..100 how adversarial the player is toward management."""
    try:
        return float(getattr(p, "_gm_grudge", 0.0) or 0.0)
    except Exception:
        return 0.0


def decay_gm_grudge(p: Any, win_pct: float) -> float:
    """Monthly repair: winning heals, time heals slowly. Returns new value."""
    g = gm_grudge(p)
    if g <= 0:
        return 0.0
    decay = 3.0
    if win_pct > 0.55:
        decay = 12.0
    elif win_pct > 0.45:
        decay = 8.0
    g = max(0.0, g - decay)
    try:
        p._gm_grudge = g
    except Exception:
        pass
    return g


def apply_gm_grudge_effects(p: Any) -> None:
    """While the grudge burns: happiness capped, trade risk elevated."""
    if gm_grudge(p) <= 0:
        return
    try:
        if _num(p, "happiness", 70) > 45:
            p.happiness = 45
    except Exception:
        pass
    try:
        p.trade_request_risk = min(
            100, float(getattr(p, "trade_request_risk", 0) or 0) + 1.0)
    except Exception:
        pass


def apply_deposition(team: Any, old: Any, new: Any, tier: str,
                     talked: bool, date_str: str = "",
                     compromise_alternate: bool = False) -> Dict[str, Any]:
    """Apply the letter change and the reaction. Returns a report with
    story lines, news lines, and the applied effects.

    compromise_alternate: the judgment call softened the blow -- the old
    captain keeps an A. Improves the tier one step for effect purposes.
    """
    if compromise_alternate and tier in ("pushback", "extreme"):
        tier = {"pushback": "grumbles", "extreme": "pushback"}[tier]

    try:
        old.captaincy = "A" if compromise_alternate else ""
    except Exception:
        pass
    try:
        old.captain_tenure_years = 0
    except Exception:
        pass
    if new is not None:
        try:
            new.captaincy = "C"
        except Exception:
            pass

    oname = _name(old)
    nname = _name(new) if new is not None else "no one"
    report: Dict[str, Any] = {"tier": tier, "lines": [], "news": [],
                              "effects": {}}
    lines = report["lines"]

    if tier == "graceful":
        _bump(old, "happiness", -5)
        _bump(old, "morale", -2)
        lines.append(f"{oname} took it with class -- shook {nname}'s hand "
                     "in front of the room.")
        report["news"].append(
            f"© {nname} named captain; {oname} hands over the C with class.")
        report["effects"] = {"happiness": -5, "morale": -2}
    elif tier == "grumbles":
        _bump(old, "morale", -5)
        _bump(old, "happiness", -12)
        _bump(old, "controversy", 4)
        lines.append(f"{oname} is saying all the right things. His body "
                     "language says otherwise.")
        report["news"].append(
            f"{oname} stripped of the C; {nname} takes over. "
            "The old captain is saying the right things -- for now.")
        report["effects"] = {"morale": -5, "happiness": -12,
                             "controversy": +4}
    elif tier == "pushback":
        _bump(old, "morale", -8)
        _bump(old, "happiness", -20)
        _bump(old, "controversy", 12)
        try:
            old.trade_request_risk = min(
                100, float(getattr(old, "trade_request_risk", 0) or 0) + 15)
        except Exception:
            pass
        lines.append(f"{oname} went public with his frustration -- this is "
                     "a story now, and the room is watching.")
        report["news"].append(
            f"CAPTAINCY FALLOUT: {oname} blasts the decision to hand "
            f"the C to {nname}.")
        report["effects"] = {"morale": -8, "happiness": -20,
                             "controversy": +12, "trade_request_risk": +15}
    else:  # extreme
        vol = _num(old, "controversy", 20)
        try:
            loyalty = float(contract_loyalty(old))
        except Exception:
            loyalty = 0.5
        if vol >= 55:
            # The hothead demands out.
            try:
                old.transfer_requested = True
            except Exception:
                pass
            _bump(old, "happiness", -30)
            _bump(old, "morale", -12)
            _bump(old, "controversy", 15)
            lines.append(f"{oname} has requested a trade. He doesn't want "
                         "to be here anymore.")
            report["news"].append(
                f"TRADE DEMAND: {oname}, stripped of the captaincy, "
                "has asked out.")
            report["effects"] = {"transfer_requested": True, "happiness": -30,
                                 "morale": -12, "controversy": +15}
            report["extreme_kind"] = "trade_request"
        else:
            # The loyal soldier goes cold: adversarial toward management.
            try:
                old._gm_grudge = 85.0
                old._gm_grudge_since = date_str
            except Exception:
                pass
            _bump(old, "happiness", -25)
            _bump(old, "morale", -10)
            apply_gm_grudge_effects(old)
            lines.append(f"{oname} said nothing. He just looks through you "
                         "now -- winning him back will take major repair.")
            report["news"].append(
                f"{oname} stripped of the C; insiders say the relationship "
                "with management is fractured.")
            report["effects"] = {"gm_grudge": 85, "happiness": -25,
                                 "morale": -10}
            report["extreme_kind"] = "gm_grudge"

    if not talked and tier in ("pushback", "extreme"):
        lines.append("He never saw it coming -- no conversation first made "
                     "it worse.")
    if compromise_alternate:
        lines.append(f"He keeps an 'A' -- a face-saving compromise.")
    return report


# ---------------------------------------------------------------------------
# AI: voluntary torch-passing in the offseason (same logic, headless)
# ---------------------------------------------------------------------------

def _skater(p: Any) -> bool:
    try:
        from game_classes import PlayerPosition as _PP
        return getattr(p, "primary_position", None) != _PP.GOALIE
    except Exception:
        return True


def ai_consider_captaincy_change(team: Any, league: Any,
                                 date_str: str = "",
                                 rng: Any = random) -> Optional[Dict[str, Any]]:
    """One AI club's offseason torch-passing decision. Rare and
    conservative: only when the successor is plainly more worthy and the
    old guard is fading. Returns the deposition report, or None."""
    roster = [p for p in (getattr(team, "roster", None) or []) if _skater(p)]
    caps = [p for p in roster if getattr(p, "captaincy", "") == "C"]
    if len(caps) != 1:
        return None
    old = caps[0]
    if not is_established_captain(old):
        return None
    try:
        if getattr(getattr(league, "playoff_bracket", None),
                   "stanley_cup_champion", None) is team:
            return None  # never fix a Cup captain
    except Exception:
        pass

    old_age = _num(old, "age", 30)
    cands = [p for p in roster
             if p is not old and _num(p, "leadership", 0) >= 82]
    if not cands:
        return None
    new = max(cands, key=lambda p: (_num(p, "leadership", 0),
                                    -_num(p, "age", 99)))
    gap = worthiness_gap(old, new)
    torch_pass = (_num(new, "age", 99) < old_age - 2 and gap >= 8)
    fading = (old_age >= 34 and gap >= 10)
    if not (torch_pass or fading):
        return None
    if rng.random() > 0.35:
        return None  # GMs are conservative; most years nothing happens

    info = assess_deposition(old, new, team, league)
    # The AI's "conversation": a closed-door meeting, resolved by roll.
    tier = roll_tier(min(0.98, info["acceptance"] + 0.18), rng)
    report = apply_deposition(team, old, new, tier, talked=True,
                              date_str=date_str)
    report["old_name"] = _name(old)
    report["new_name"] = _name(new)
    report["team_name"] = getattr(team, "team_name", "the club")
    return report


# ---------------------------------------------------------------------------
# Clear-the-air repair (extreme grudge)
# ---------------------------------------------------------------------------

def clear_the_air(old: Any, team: Any, league: Any,
                  rng: Any = random) -> Dict[str, Any]:
    """One direct conversation to repair a fractured relationship.

    Returns {success, lines}. One attempt per 30 days is enforced by the
    caller via the _grudge_talk_stamp.
    """
    g = gm_grudge(old)
    win_pct = _win_pct(team, league)
    chance = 0.45 + (win_pct - 0.5) * 0.8 + max(0.0, (30 - g) / 100.0)
    chance = max(0.1, min(0.9, chance))
    ok = rng.random() < chance
    if ok:
        reduction = 45.0
        new_g = max(0.0, g - reduction)
        try:
            old._gm_grudge = new_g
        except Exception:
            pass
        _bump(old, "happiness", 15)
        _bump(old, "morale", 8)
        lines = [f"{_name(old)} heard you out. The ice is thawing -- "
                 "keep winning and he'll come all the way back."]
    else:
        new_g = min(100.0, g + 8.0)
        try:
            old._gm_grudge = new_g
        except Exception:
            pass
        lines = [f"{_name(old)} wasn't ready to hear it. Give it time -- "
                 "pushing harder will only deepen it."]
    return {"success": ok, "lines": lines, "grudge": round(new_g, 1)}
