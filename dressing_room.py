"""Dressing-room dynamics (module 03): morale as a social system.

Turns morale from a number into a social system that creates stories,
built on the reputation (01) and coaching-engagement (02) foundations.

What it models:
- Hierarchy: the captain and alternates carry extra influence; veteran
  voices outrank fringe players. Influence is visible, never hidden.
- Social groups: cliques form by tenure and -- only where the data
  exists -- nationality. Players with no group are floaters.
- Cascades: trades and press answers ripple through individuals AND
  their groups. A captain with real influence steadies the room.
- Team talks: pre-game and intermission talks in calm / fired-up /
  cautious tones. Outcomes feed the existing first- and third-period
  momentum (via impact_system.nudge_momentum -- additive, capped).

Design law: additive, backfilled on old saves, no hidden truth. User
and AI share every mechanic -- AI clubs get automatic coach talks
through the same give_talk() path the user's talks use.
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional

TONES = ("calm", "fired-up", "cautious")

# tone -> score_state -> fit (0-100). Fired-up chases a deficit,
# calm steadies nerves, cautious protects a lead.
TONE_FIT = {
    ("fired-up", "trailing"): 85, ("fired-up", "tied"): 65,
    ("fired-up", "leading"): 30,
    ("calm", "trailing"): 55, ("calm", "tied"): 70,
    ("calm", "leading"): 80,
    ("cautious", "trailing"): 30, ("cautious", "tied"): 60,
    ("cautious", "leading"): 85,
}

_TENURE_YEARS = {
    "This season": 0, "2 years": 2, "3 years": 3, "4+ years": 4,
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _clamp(v: float, lo: float = 1, hi: float = 100) -> int:
    try:
        return max(int(lo), min(int(hi), int(round(v))))
    except Exception:
        return int(lo)


def _name(p: Any) -> str:
    for attr in ("full_name", "name"):
        v = getattr(p, attr, None)
        if v:
            return str(v)
    return "Unknown"


def _pid(p: Any) -> Any:
    return getattr(p, "id", id(p))


def _roster(team: Any) -> List[Any]:
    try:
        return list(getattr(team, "roster", []) or [])
    except Exception:
        return []


def ensure_dressing_room_fields(team: Any) -> Dict[str, Any]:
    """Backfill the dressing-room state dict on a team (old saves safe)."""
    dr = getattr(team, "dressing_room", None)
    if not isinstance(dr, dict):
        dr = {}
    dr.setdefault("mood_log", [])          # recent room story lines (newest last)
    dr.setdefault("pregame", None)         # pending pre-game talk dict
    dr.setdefault("intermission", None)    # pending intermission talk dict
    dr.setdefault("arrivals", {})          # pid -> {"gp_at_arrival": int}
    try:
        team.dressing_room = dr
    except Exception:
        pass
    return dr


def is_user_team(team: Any, game_manager: Any = None) -> bool:
    """Canonical check: is this the human GM's club?

    The ``is_user_team`` flag is the primary signal (set at team select
    and on save restore), with the game manager's ``user_team`` as the
    backstop for old saves where the flag was never stamped. Identity
    first, team-name match second -- a name match alone is only a
    fallback, never the first word.
    """
    try:
        if bool(getattr(team, "is_user_team", False)):
            return True
    except Exception:
        pass
    try:
        gm = game_manager
        if gm is None:
            return False
        ut = getattr(gm, "user_team", None)
        if ut is None:
            return False
        if ut is team:
            return True
        tname = getattr(team, "team_name", None)
        uname = getattr(ut, "team_name", None)
        return bool(tname) and tname == uname
    except Exception:
        return False


def _log(team: Any, line: str, cap: int = 40) -> None:
    dr = ensure_dressing_room_fields(team)
    try:
        dr["mood_log"].append(str(line))
        del dr["mood_log"][:-cap]
    except Exception:
        pass


# --------------------------------------------------------------------------
# Hierarchy
# --------------------------------------------------------------------------

def tenure_years(player: Any) -> int:
    """Tenure in years from the native team_tenure string."""
    return _TENURE_YEARS.get(str(getattr(player, "team_tenure", "This season")), 0)


def influence_of(player: Any) -> int:
    """A player's pull in the room (1-100). Letters carry weight."""
    base = 35
    letter = str(getattr(player, "captaincy", "") or "").upper()
    if letter == "C":
        base = 70
    elif letter == "A":
        base = 60
    try:
        base += float(getattr(player, "leadership", 50) or 50) * 0.22
    except Exception:
        pass
    ty = tenure_years(player)
    base += {4: 8, 3: 5, 2: 2}.get(ty, 0)
    # League stature: a bona fide vet carries weight from day one, so a
    # new arrival with a real resume doesn't enter as "Fringe".
    try:
        base += league_stature_of(player)
    except Exception:
        pass
    return _clamp(base, 5, 99)


def _tier(player: Any, influence: int) -> str:
    letter = str(getattr(player, "captaincy", "") or "").upper()
    if letter == "C":
        return "Captain"
    if letter == "A":
        return "Alternate"
    if influence >= 70:
        return "Veteran core"
    # A hyped kid is never "Fringe" or "Regular" in the room's eyes --
    # everyone knows why the top-10 pick is here.
    try:
        if influence < 70 and arrival_archetype(player) == "blue_chip":
            return "Top prospect"
    except Exception:
        pass
    if influence >= 45:
        return "Regular"
    return "Fringe"


# --------------------------------------------------------------------------
# Arrival archetypes: the room reacts to WHO walks in, not just that
# someone did. A top-10 pick and a bona fide vet move the room in
# different ways -- felt, never fatal. Every delta here is small and
# one-time; nothing compounds into a death spiral or a free Cup.
# --------------------------------------------------------------------------

def _draft_overall(player: Any) -> Optional[int]:
    """Overall draft number from the 'Round R, Pick P' string, else None."""
    try:
        s = str(getattr(player, "draft_position", "") or "")
        m = re.search(r"Round\s*(\d+)\s*,\s*Pick\s*(\d+)", s, re.IGNORECASE)
        if m:
            return (int(m.group(1)) - 1) * 32 + int(m.group(2))
    except Exception:
        pass
    return None


def arrival_archetype(player: Any) -> str:
    """Classify a newcomer: 'blue_chip' | 'veteran' | 'regular'.

    blue_chip: a top-10 draft pick (or an elite teenager) -- the room
      knows the hype before he says a word.
    veteran: a bona fide league vet -- 30+ with a real resume (rating,
      mileage, or a letter). A 34-year-old depth plug is 'regular'.
    regular: everyone else.
    """
    try:
        age = int(getattr(player, "age", 25) or 25)
    except Exception:
        age = 25
    try:
        ovr = int(player.overall_rating())
    except Exception:
        ovr = 70
    try:
        gp = int(getattr(getattr(player, "stats", None),
                         "games_played", 0) or 0)
    except Exception:
        gp = 0
    pick = _draft_overall(player)
    if age <= 21 and pick is not None and pick <= 10:
        return "blue_chip"
    if age <= 20 and ovr >= 80:
        return "blue_chip"
    letter = str(getattr(player, "captaincy", "") or "").upper() in ("C", "A")
    if age >= 30 and (ovr >= 82 or gp >= 500 or letter):
        return "veteran"
    # Stardom doesn't wait for 30: a bona fide star or a thousand-game
    # man is a vet in any room, at any age.
    if ovr >= 86 or gp >= 700:
        return "veteran"
    return "regular"


def league_stature_of(player: Any) -> int:
    """Bonus room influence from league stature (0-24, never raises)."""
    try:
        ovr = int(player.overall_rating())
    except Exception:
        ovr = 70
    try:
        gp = int(getattr(getattr(player, "stats", None),
                         "games_played", 0) or 0)
    except Exception:
        gp = 0
    s = 0
    if ovr >= 85:
        s += 14
    elif ovr >= 80:
        s += 7
    s += min(10, gp // 100)
    return min(24, s)


def _room_vet_core(team: Any, arriving: Any):
    """(veteran_count, top5_avg_influence), ignoring the arrival himself."""
    try:
        rows = [r for r in hierarchy(team) if r["id"] != _pid(arriving)]
    except Exception:
        return 0, 0
    n_vets = sum(1 for r in rows
                 if r["tier"] in ("Captain", "Alternate", "Veteran core"))
    top = rows[:5]
    avg = (sum(r["influence"] for r in top) / len(top)) if top else 0
    return n_vets, avg


def _vet_character(team: Any, arriving: Any):
    """Mean (leadership, drama, temper) of the vet core, ignoring the
    arrival himself. Drama is the public circus; temper is the hot head
    that tests rookies -- a room of saints can still be a hard room."""
    leads: List[float] = []
    dramas: List[float] = []
    tempers: List[float] = []
    try:
        me = _pid(arriving)
        rows = hierarchy(team)
    except Exception:
        return 50.0, 20.0, 45.0
    for r in rows:
        if r["id"] == me:
            continue
        if r["tier"] not in ("Captain", "Alternate", "Veteran core"):
            continue
        p = r["player"]
        try:
            leads.append(float(getattr(p, "leadership", 50) or 50))
        except Exception:
            pass
        try:
            # LOCKED baseline, not the incident ratchet -- who they are.
            _e = getattr(p, "base_controversy", 20)
            dramas.append(20.0 if _e is None else float(_e))
        except Exception:
            pass
        try:
            tempers.append(_temper_of(p))
        except Exception:
            pass
    lead = sum(leads) / len(leads) if leads else 50.0
    drama = sum(dramas) / len(dramas) if dramas else 20.0
    temper = sum(tempers) / len(tempers) if tempers else 45.0
    return lead, drama, temper


def _norm_pair(player: Any, name1: str, default1: float,
               name2: str, default2: float):
    """Read two traits on a shared 0-100 scale. Same convention as the
    reputation system's locked baseline: if both read <= 20 the player
    is on the EHM 1-20 scale and both are scaled up."""
    try:
        v1 = float(getattr(player, name1, default1))
    except Exception:
        v1 = float(default1)
    try:
        v2 = float(getattr(player, name2, default2))
    except Exception:
        v2 = float(default2)
    if max(v1, v2) <= 20:
        v1, v2 = v1 * 5, v2 * 5
    return max(0.0, min(100.0, v1)), max(0.0, min(100.0, v2))


def _temper_of(player: Any) -> float:
    """Hot-headedness: temper that snaps. Distinct from public drama --
    a saint can have a hot head."""
    aggr, comp = _norm_pair(player, "aggressiveness", 50, "composure", 60)
    return aggr * 0.6 + (100 - comp) * 0.4


def _difficult_of(player: Any) -> float:
    """Me-first difficulty: the tough sell. Low drama by definition --
    he doesn't do circuses -- but hard to work with when the
    circumstances displease him."""
    self_, team = _norm_pair(player, "selfishness", 50, "teamwork", 60)
    return self_ * 0.5 + (100 - team) * 0.5


def _personality_of(arriving: Any):
    """The arrival's personality blend: (cocky, hothead, tough_sell,
    quiet, spotlight). Drama, temper, and difficulty are separate axes --
    saints can have hot heads, and quiet men can be difficult."""
    _cont = getattr(arriving, "base_controversy", 20)
    try:
        drama = 20.0 if _cont is None else float(_cont)
    except Exception:
        drama = 20.0
    temper = _temper_of(arriving)
    difficult = _difficult_of(arriving)
    pick = _draft_overall(arriving)
    cocky = drama >= 40
    hothead = temper >= 65
    tough_sell = difficult >= 65 and drama < 40
    quiet = drama <= 15 and temper < 65
    return (cocky, hothead, tough_sell, quiet,
            pick is not None and pick <= 3)


def _room_situation(team: Any, arriving: Any):
    """The team's side: room mood (mean morale, results proxy) and roster
    strength (mean overall, contender proxy), ignoring the arrival.
    Returns (mood, strength)."""
    me = _pid(arriving)
    moods: List[float] = []
    ovrs: List[float] = []
    for p in _roster(team):
        try:
            if _pid(p) == me:
                continue
        except Exception:
            pass
        try:
            moods.append(float(getattr(p, "morale", 70) or 70))
        except Exception:
            pass
        try:
            ovrs.append(float(p.overall_rating()))
        except Exception:
            ovrs.append(70.0)
    mood = sum(moods) / len(moods) if moods else 70.0
    strength = sum(ovrs) / len(ovrs) if ovrs else 70.0
    return mood, strength


def _cohort_character(team: Any, arriving: Any):
    """The young-talent cluster (23 and under, ignoring the arrival):
    drama, temper, and results. Returns (members, drama, temper, mood).
    A driven cluster thrives together; a hot, showy, or losing one is a
    bad influence -- each for its own reason."""
    me = _pid(arriving)
    members: List[Any] = []
    for p in _roster(team):
        try:
            if _pid(p) == me:
                continue
            age = int(getattr(p, "age", 99) or 99)
        except Exception:
            continue
        if age <= 23:
            members.append(p)
    dramas: List[float] = []
    tempers: List[float] = []
    moods: List[float] = []
    for p in members:
        try:
            _e = getattr(p, "base_controversy", 20)
            dramas.append(20.0 if _e is None else float(_e))
        except Exception:
            pass
        try:
            tempers.append(_temper_of(p))
        except Exception:
            pass
        try:
            moods.append(float(getattr(p, "morale", 70) or 70))
        except Exception:
            pass
    drama = sum(dramas) / len(dramas) if dramas else 20.0
    temper = sum(tempers) / len(tempers) if tempers else 45.0
    mood = sum(moods) / len(moods) if moods else 70.0
    return members, drama, temper, mood


def _arrival_reaction(team: Any, arriving: Any, how: str = "signing",
                      date_str: str = "") -> List[str]:
    """Shared arrival core: record him, then let the room react to WHO
    he is. Used by trades (arriving branch) and every non-trade join
    (signings, offer sheets, waiver claims, callups). All callers are
    exception-guarded; this never raises."""
    lines: List[str] = []
    dr = ensure_dressing_room_fields(team)
    aname = _name(arriving)
    arch = arrival_archetype(arriving)

    # Record the arrival (idempotent): powers integration_of and the
    # first-appearance guard in cascade_on_arrival.
    try:
        pid = _pid(arriving)
        if pid not in dr["arrivals"]:
            try:
                gp = int(getattr(getattr(arriving, "stats", None),
                                 "games_played", 0) or 0)
            except Exception:
                gp = 0
            dr["arrivals"][pid] = {"gp_at_arrival": gp,
                                   "archetype": arch, "how": how}
    except Exception:
        pass

    # Best-fit clique: nationality match first (shared with the old
    # trade path -- regulars keep their exact old behavior).
    best = None
    anat = str(getattr(arriving, "nationality", "") or "")
    for c in form_cliques(team):
        if c["nationality"] == anat:
            best = c
            break

    cap = captain_of(team)
    cap_is_arriving = cap is not None and cap is arriving
    n_vets, _top_avg = _room_vet_core(team, arriving)

    if arch == "blue_chip":
        pick = _draft_overall(arriving)
        pick_txt = f"the #{pick} overall pick" if pick else "the blue-chip kid"
        cocky, hothead, tough_sell, quiet, spotlight = \
            _personality_of(arriving)
        mood, strength = _room_situation(team, arriving)
        crisis = mood < 55
        content = mood >= 72
        win_now = strength >= 81
        if n_vets >= 3:
            # A veteran room's PERSONALITIES decide the welcome, not the
            # headcount: a great leadership group is the best possible
            # landing for a rookie; only a demanding room tests him. The
            # kid's own swagger and the team's situation shape it further.
            _lead, _drama, _temper = _vet_character(team, arriving)
            fiery = _temper >= 65
            circus = _drama >= 40
            demanding = fiery or circus
            sheltering = _lead >= 70 and not demanding
            if demanding:
                flavor = "fiery" if _temper >= _drama else "circus"
                if flavor == "fiery":
                    if cocky and hothead:
                        kid_delta = -4
                        story = (f"{aname}, {pick_txt}, walks in talking "
                                 f"and looking for a fight. This will be "
                                 f"fun for everyone but him.")
                    elif cocky:
                        kid_delta = -4
                        story = (f"{aname}, {pick_txt}, walks in talking. "
                                 f"This room eats rookies with mouths.")
                    elif hothead:
                        kid_delta = -3
                        story = (f"{aname}, {pick_txt}, doesn't say a word "
                                 f"and doesn't take a step back. They'll "
                                 f"respect that -- after the test.")
                    elif tough_sell:
                        kid_delta = -4
                        story = (f"{aname}, {pick_txt}, walks into a room "
                                 f"that eats rookies. The vets will find "
                                 f"out what he's made of -- and who it's for.")
                    elif quiet:
                        kid_delta = -3
                        story = (f"{aname}, {pick_txt}, keeps his head "
                                 f"down. The vets will test him anyway.")
                    else:
                        kid_delta = -4
                        story = (f"{aname}, {pick_txt}, walks into a room "
                                 f"that eats rookies. The vets will test "
                                 f"him; the kids are buzzing.")
                else:
                    if cocky and not hothead:
                        kid_delta = -1
                        story = (f"{aname}, {pick_txt}, walks into a "
                                 f"circus -- and he'll fit right into it.")
                    elif hothead:
                        kid_delta = -4
                        story = (f"{aname}, {pick_txt}, walks into a "
                                 f"circus. They'll try to get a rise out of him.")
                    elif quiet:
                        kid_delta = -3
                        story = (f"{aname}, {pick_txt}, walks into a "
                                 f"circus. Every word he says will be a "
                                 f"headline -- he doesn't say many.")
                    else:
                        kid_delta = -4
                        story = (f"{aname}, {pick_txt}, walks into a "
                                 f"circus. The cameras love a new act.")
                if kid_delta <= -3:
                    for p in _roster(team):
                        if p is arriving:
                            continue
                        try:
                            pa = int(getattr(p, "age", 99) or 99)
                        except Exception:
                            pa = 99
                        if pa <= 23:
                            _bump(p, +2)
            elif sheltering:
                if cocky:
                    kid_delta = +2
                    story = (f"{aname}, {pick_txt}, couldn't ask for a "
                             f"better room. The vets will keep the kid's "
                             f"feet on the ground.")
                elif hothead:
                    kid_delta = +3
                    story = (f"{aname}, {pick_txt}, couldn't ask for a "
                             f"better room. The vets will point that "
                             f"temper at the other team.")
                elif tough_sell:
                    kid_delta = +2
                    story = (f"{aname}, {pick_txt}, lands in a well-led "
                             f"room. The vets know how to handle his type.")
                else:
                    kid_delta = +3
                    story = (f"{aname}, {pick_txt}, couldn't ask for a "
                             f"better room. The vets will look after the kid.")
            else:
                kid_delta = -1
                story = (f"{aname}, {pick_txt}, joins a veteran room. "
                         f"All eyes on the kid.")
            # One situational beat: the room's situation gets a say, but
            # never more than one -- legible, never making or breaking.
            if crisis:
                kid_delta -= 1
                if tough_sell:
                    story += " He already doesn't like the circumstances."
                else:
                    story += (" The room is losing, and nobody's in the "
                              "mood to babysit.")
            elif win_now and not sheltering:
                kid_delta -= 1
                story += " They need him to produce right now."
            elif spotlight and not sheltering:
                kid_delta -= 1
                story += " The spotlight follows him everywhere he goes."
            elif content and not demanding and not sheltering:
                kid_delta += 1
                story += " A happy room makes for a soft landing."
            kid_delta = max(-4, min(3, kid_delta))
            _bump(arriving, kid_delta)
            lines.append(story)
        else:
            # Young room: the kid cohort's character decides whether he
            # thrives or drifts -- drama, temper, results, situation, each
            # with its own flavor.
            cohort, c_drama, c_temper, c_mood = _cohort_character(
                team, arriving)
            wild = c_temper >= 65 or c_drama >= 40 or c_mood < 55
            driven = c_drama < 30 and c_temper < 55 and c_mood >= 60
            if driven and cohort:
                _bump(arriving, +3)
                for p in cohort:
                    _bump(p, +1)
                story = (f"{aname}, {pick_txt}, lands with a young core "
                         f"that pushes each other. Iron sharpens iron.")
            elif wild and cohort:
                _bump(arriving, +1)
                if c_temper >= 65 and c_temper >= c_drama:
                    story = (f"{aname}, {pick_txt}, joins a young room "
                             f"that runs hot. He'll have to keep his head "
                             f"straight.")
                elif c_drama >= 40 and c_drama > c_temper:
                    story = (f"{aname}, {pick_txt}, joins a young room "
                             f"that loves the spotlight. He'll have to "
                             f"keep his head straight.")
                else:
                    story = (f"{aname}, {pick_txt}, joins a young room "
                             f"that's losing and pointing fingers. He'll "
                             f"have to keep his head straight.")
                if cocky or hothead:
                    story += (" He looks like he'll fit right in -- "
                              "that's the worry.")
            else:
                _bump(arriving, +2)
                for p in _roster(team):
                    if p is not arriving:
                        _bump(p, +1)
                story = (f"{aname}, {pick_txt}, joins a young room. "
                         f"The future just walked in.")
            if spotlight:
                story += " Everyone already knows his name."
            lines.append(story)
    elif arch == "veteran":
        # Respect travels: a softer landing than a nobody gets.
        if best is not None:
            lines.append(f"{aname} lands with the {best['name'].lower()} -- "
                         f"a vet knows how to find his people.")
        else:
            _bump(arriving, -2)
            lines.append(f"{aname} arrives. Even outsiders respect the resume.")
        _vcocky, _vhot, _vtough, _vquiet, _vspot = _personality_of(arriving)
        try:
            _vmood, _vstr = _room_situation(team, arriving)
        except Exception:
            _vmood = 70.0
        if _vtough and _vmood < 55:
            # Tough sell, bad circumstances: difficult until they change.
            _bump(arriving, -2)
            lines.append(f"{aname} doesn't like the circumstances. "
                         f"He'll be difficult until they change.")
        vet_inf = influence_of(arriving)
        cap_letter = (str(getattr(cap, "captaincy", "") or "").upper()
                      if cap is not None else "")
        cap_inf = influence_of(cap) if cap is not None else 0
        try:
            vet_age = int(getattr(arriving, "age", 35) or 35)
        except Exception:
            vet_age = 35
        if cap is not None and not cap_is_arriving and cap_letter == "C":
            if vet_inf > cap_inf and vet_age < 33:
                # Alpha meets alpha: bounded friction, they'll sort it out.
                _bump(cap, -2)
                _bump(arriving, -2)
                lines.append(f"Two alphas, one room: {aname} and "
                             f"{_name(cap)} will sort out the pecking order.")
            elif cap_inf >= 70:
                # Strong captain: the vet slots in as a trusted lieutenant.
                _bump(cap, +2)
                lines.append(f"{_name(cap)} has a lieutenant he trusts. "
                             f"The hierarchy holds.")
            # Else: a middling captain and a vet who knows his place --
            # the room just nods. No drama needed.
        elif cap_is_arriving or cap_letter != "C" or cap_inf < 55:
            # No real voice in the room: the vet fills the vacuum.
            for p in _roster(team):
                if p is not arriving:
                    _bump(p, +1)
            lines.append(f"{aname} fills the leadership vacuum. "
                         f"The room stands a little taller.")
        # Else: solid non-letter voice the vet doesn't outrank -- quiet
        # respect, no lines needed.
    else:
        # Regular: the long-standing behavior, unchanged.
        if best is not None:
            _bump(arriving, -2)
            lines.append(f"{aname} lands with the {best['name'].lower()} -- "
                         f"familiar faces help.")
        else:
            _bump(arriving, -6)
            lines.append(f"{aname} arrives an outsider. The room will "
                         f"decide about him.")

    prefix = f"[{date_str}] " if date_str else ""
    # NOTE: no logging here -- the caller logs (cascade_on_trade logs
    # every line once at the end; cascade_on_arrival logs below).
    return [(prefix + ln) for ln in lines]


def cascade_on_arrival(team: Any, arriving: Any, how: str = "signing",
                       date_str: str = "") -> List[str]:
    """A new man joins the NHL room outside a trade: UFA signing, offer
    sheet, waiver claim, ELC promotion / callup.

    First NHL-room appearance per team only -- a re-callup doesn't
    re-shake the room. (Departures pop the arrival record, so a
    re-acquired player counts as new again.)
    """
    try:
        dr = ensure_dressing_room_fields(team)
        if _pid(arriving) in dr["arrivals"]:
            return []
        lines = _arrival_reaction(team, arriving, how=how, date_str=date_str)
        for ln in lines:
            _log(team, ln)
        return lines
    except Exception:
        return []


def hierarchy(team: Any) -> List[Dict[str, Any]]:
    """The room's pecking order, most influential first."""
    rows = []
    for p in _roster(team):
        inf = influence_of(p)
        rows.append({
            "player": p, "id": _pid(p), "name": _name(p),
            "letter": str(getattr(p, "captaincy", "") or "").upper() or "-",
            "influence": inf, "tier": _tier(p, inf),
            "morale": _clamp(getattr(p, "morale", 70)),
        })
    rows.sort(key=lambda r: (-r["influence"], r["name"]))
    return rows


def captain_of(team: Any) -> Optional[Any]:
    for p in _roster(team):
        if str(getattr(p, "captaincy", "") or "").upper() == "C":
            return p
    # No letter? The most influential player is the de facto voice.
    rows = hierarchy(team)
    return rows[0]["player"] if rows else None


# --------------------------------------------------------------------------
# Social groups (cliques)
# --------------------------------------------------------------------------

def _tenure_bucket(player: Any) -> str:
    ty = tenure_years(player)
    if ty >= 4:
        return "core"
    if ty >= 2:
        return "established"
    return "new"


def form_cliques(team: Any, min_size: int = 3,
                 extra: Any = None) -> List[Dict[str, Any]]:
    """Group the room by tenure + nationality (only where data exists).

    Returns clique dicts; players in no clique are floaters.

    ``extra``: a player no longer on the roster (e.g. just traded away)
    to include in the grouping anyway. Departure cascades run after the
    roster move, so without this the room can't tell which clique it lost.
    """
    roster = _roster(team)
    if extra is not None:
        try:
            eid = _pid(extra)
            if all(_pid(p) != eid for p in roster):
                roster = list(roster) + [extra]
        except Exception:
            pass
    buckets: Dict[tuple, List[Any]] = {}
    for p in roster:
        nat = str(getattr(p, "nationality", "") or "").strip() or "Unknown"
        key = (_tenure_bucket(p), nat)
        buckets.setdefault(key, []).append(p)

    cliques = []
    for (tb, nat), members in buckets.items():
        if len(members) < min_size:
            continue
        moods = [_clamp(getattr(m, "morale", 70)) for m in members]
        # Bond: shared tenure + shared nationality is the whole bond here.
        bond = round(0.45 + 0.10 * min(len(members), 6) / 6 + 0.15, 2)
        if tb == "core":
            label = f"The {nat} core"
        elif tb == "established":
            label = f"{nat} regulars"
        else:
            label = f"{nat} newcomers"
        cliques.append({
            "name": label, "kind": tb, "nationality": nat,
            "member_ids": {_pid(m) for m in members},
            "members": [_name(m) for m in members],
            "bond": min(0.95, bond),
            "mood": int(round(sum(moods) / len(moods))) if moods else 70,
        })
    cliques.sort(key=lambda c: (-len(c["members"]), c["name"]))
    return cliques


def clique_of(team: Any, player: Any,
              extra: Any = None) -> Optional[Dict[str, Any]]:
    pid = _pid(player)
    for c in form_cliques(team, extra=extra):
        if pid in c["member_ids"]:
            return c
    return None


def floaters(team: Any) -> List[Dict[str, Any]]:
    """Players with no clique -- higher integration risk, lower cascade."""
    cliques = form_cliques(team)
    grouped = set()
    for c in cliques:
        grouped |= c["member_ids"]
    return [{"name": _name(p), "id": _pid(p)}
            for p in _roster(team) if _pid(p) not in grouped]


def room_mood(team: Any) -> int:
    """Mean morale of the room (1-100)."""
    roster = _roster(team)
    if not roster:
        return 70
    return _clamp(sum(_clamp(getattr(p, "morale", 70)) for p in roster)
                  / len(roster))


# --------------------------------------------------------------------------
# Morale cascades
# --------------------------------------------------------------------------

def _bump(player: Any, delta: float) -> None:
    try:
        player.morale = _clamp(getattr(player, "morale", 70) + delta)
    except Exception:
        pass


def cascade_on_trade(team: Any, traded: Any = None, arriving: Any = None,
                     date_str: str = "") -> List[str]:
    """A trade shakes the room. Departures hurt; arrivals must integrate.

    Called for BOTH sides: the old team loses `traded`, the new team
    gains `arriving`.
    """
    lines: List[str] = []
    dr = ensure_dressing_room_fields(team)
    tname = str(getattr(team, "team_name", "the club"))

    if traded is not None:
        tname_p = _name(traded)
        letter = str(getattr(traded, "captaincy", "") or "").upper()
        base_hit = 8 if letter == "C" else (5 if letter == "A" else 3)
        # The captain steadies the room -- unless he was the one traded.
        cap = captain_of(team)
        steady = (cap is not None and cap is not traded
                  and influence_of(cap) >= 70)
        if steady:
            base_hit = max(1, int(round(base_hit * 0.5)))
        # The departed player is already off the roster by the time the
        # post-trade hook runs -- include him in the grouping so the room
        # knows which clique it lost.
        clique = clique_of(team, traded, extra=traded)
        for p in _roster(team):
            if p is traded:
                continue
            if clique is not None and _pid(p) in clique["member_ids"]:
                _bump(p, -base_hit * (0.5 + clique["bond"]))
            else:
                _bump(p, -1)
        if letter == "C":
            lines.append(f"{tname_p} (C) is gone -- the room looks for a new voice.")
        elif steady:
            lines.append(f"{tname_p} was dealt. {_name(cap)} steadied the room.")
        else:
            lines.append(f"{tname_p} was dealt. The room feels it.")
        if clique is not None:
            lines.append(f"The {clique['name'].lower()} take it hardest.")
        # A departure clears his arrival record: if he's ever re-acquired,
        # the room treats him as a new face again.
        try:
            dr["arrivals"].pop(_pid(traded), None)
        except Exception:
            pass

    if arriving is not None:
        # Who he is shapes the welcome -- blue chips and bona fide vets
        # move the room differently than a depth plug. Shared core with
        # every non-trade arrival path.
        try:
            lines.extend(_arrival_reaction(team, arriving, how="trade",
                                           date_str=date_str))
        except Exception:
            pass

    for ln in lines:
        # _arrival_reaction already date-prefixes its lines; the trade's own
        # departure lines still need it. Never double-prefix.
        if date_str and not ln.startswith("["):
            ln = f"[{date_str}] " + ln
        _log(team, ln)
    return lines


def integration_of(team: Any, player: Any) -> int:
    """How settled an arrival is (0-100). Grows ~8 pts per game played."""
    dr = ensure_dressing_room_fields(team)
    rec = dr["arrivals"].get(_pid(player))
    if not rec:
        return 100
    try:
        gp_now = int(getattr(player, "stats", None)
                     and getattr(player.stats, "games_played", 0) or 0)
        played = max(0, gp_now - int(rec.get("gp_at_arrival", 0)))
    except Exception:
        played = 0
    base = 25 if clique_of(team, player) is None else 60
    return _clamp(base + played * 8, 0, 100)


def _event_player_names(event: Any):
    """Yield candidate player-name strings from a media event payload.

    media_system.py is inconsistent: some events are plain dicts, others
    are MediaEvent dataclasses carrying a ``details`` dict. Trade events
    name players under list keys (``traded_players``/``received_players``),
    signings under ``player``. This normalizes every shape the backend
    actually produces.
    """
    data = event
    if not isinstance(data, dict):
        try:
            data = getattr(event, "details", None)
        except Exception:
            data = None
    if not isinstance(data, dict):
        return
    for key in ("player_name", "player", "target", "subject"):
        try:
            v = data.get(key)
        except Exception:
            v = None
        if isinstance(v, str) and v.strip():
            yield v.strip()
    for key in ("players_involved", "traded_players", "received_players",
                "players"):
        try:
            v = data.get(key)
        except Exception:
            v = None
        if isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str) and item.strip():
                    yield item.strip()


def cascade_on_press(team: Any, event: Any,
                     response_choice: str) -> List[str]:
    """Press answers ripple through the room -- individuals AND groups."""
    lines: List[str] = []
    roster = _roster(team)
    if not roster:
        return lines
    by_name = {_name(p).lower(): p for p in roster}
    target = None
    for cand in _event_player_names(event):
        if cand.lower() in by_name:
            target = by_name[cand.lower()]
            break

    def _clique_bump(player: Any, delta: float) -> None:
        c = clique_of(team, player)
        if c is None:
            return
        for p in roster:
            if p is not player and _pid(p) in c["member_ids"]:
                _bump(p, delta)

    rc = str(response_choice or "").lower()
    if rc == "critical" and target is not None:
        _bump(target, -6)
        _clique_bump(target, -3)
        lines.append(f"You hung {_name(target)} out to dry. His group noticed.")
    elif rc == "supportive" and target is not None:
        _bump(target, 4)
        _clique_bump(target, 2)
        lines.append(f"Backing {_name(target)} publicly lifted his corner of the room.")
    elif rc == "confident":
        for p in roster:
            _bump(p, 2)
        cap = captain_of(team)
        if cap is not None and influence_of(cap) >= 70:
            for p in roster:
                _bump(p, 1)
            lines.append(f"Confident words, and {_name(cap)} echoed them. Room +.")
        else:
            lines.append("Confident words in front of the cameras. Room +.")
    elif rc in ("dismissive", "hostile"):
        for p in roster:
            _bump(p, -2)
        lines.append("The room saw the brush-off. Nobody loves a siege -- yet.")
    elif rc == "controversial":
        if target is not None:
            _bump(target, -4)
            _clique_bump(target, -2)
        for p in roster:
            _bump(p, -1)
        lines.append("A controversial answer always costs someone in the room.")
    elif rc in ("professional", "thoughtful", "diplomatic"):
        lines.append("A calm, professional answer. The room barely blinked.")

    for ln in lines:
        _log(team, ln)
    return lines


def auto_press_response(team: Any, event: Any) -> List[str]:
    """AI press handling -- the same cascade a user's answers trigger.

    The only difference is who picks the answer: a simple situational read
    (room mood + a little noise) instead of a human at the podium. This is
    the automation/sim difference the even-playing-field rule allows --
    same mechanic, same magnitudes, no human in the loop.

    A content room gets confident answers; a neutral room gets professional
    ones; an unhappy room gets diplomatic/supportive spin, with the odd
    dismissive brush-off or controversial slip, exactly as a human GM's
    choices would land through cascade_on_press.
    """
    import random
    mood = room_mood(team)
    r = random.random()
    if mood >= 60:
        choice = ("confident" if r < 0.60
                  else "supportive" if r < 0.85 else "professional")
    elif mood >= 40:
        choice = ("professional" if r < 0.50
                  else "confident" if r < 0.75 else "diplomatic")
    else:
        choice = ("diplomatic" if r < 0.40
                  else "supportive" if r < 0.70
                  else "dismissive" if r < 0.90 else "controversial")
    lines = cascade_on_press(team, event, choice)
    _log(team, f"(Automated press answer: {choice}.)")
    return lines


# --------------------------------------------------------------------------
# Team talks -> momentum
# --------------------------------------------------------------------------

def _coach_influence(team: Any) -> int:
    """Head-coach influence (1-100). Mirrors the engagement foundation."""
    try:
        staff = list(getattr(team, "staff", []) or [])
        for s in staff:
            role = str(getattr(s, "role", "")).upper()
            if "HEAD" in role and "COACH" in role:
                return _clamp(getattr(s, "influence", 65) or 65, 40, 99)
        if staff:
            return _clamp(getattr(staff[0], "influence", 65) or 65, 40, 99)
    except Exception:
        pass
    return 65


def give_talk(team: Any, tone: str, context: Dict[str, Any],
              speaker: str = "coach", rng: Any = None) -> Dict[str, Any]:
    """Deliver a team talk. Returns the outcome dict and queues momentum.

    tone: calm | fired-up | cautious.
    context: {situation: pregame|intermission, score_state:
              leading|trailing|tied, rival: bool, streak: int}.
    speaker: coach | captain.
    Outcome tiers: landed (+2) / steady (+1) / flat (0) / backfired (-1).
    """
    rng = rng or random
    tone = tone if tone in TONES else "calm"
    score_state = str(context.get("score_state", "tied"))
    situation = str(context.get("situation", "pregame"))

    if speaker == "captain":
        cap = captain_of(team)
        speaker_inf = influence_of(cap) if cap is not None else 50
        speaker_name = _name(cap) if cap is not None else "the captain"
    else:
        speaker_inf = _coach_influence(team)
        speaker_name = "the coach"

    fit = TONE_FIT.get((tone, score_state), 55)
    # Losing streaks crave calm; rivalry games crave fire.
    try:
        streak = int(context.get("streak", 0) or 0)
    except Exception:
        streak = 0
    if streak <= -2 and tone == "calm":
        fit = min(100, fit + 12)
    if context.get("rival") and tone == "fired-up" and situation == "pregame":
        fit = min(100, fit + 12)
    # A fired-up talk when comfortably ahead reads as panic.
    if score_state == "leading" and tone == "fired-up":
        fit = max(5, fit - 10)

    effectiveness = (0.55 * speaker_inf + 0.45 * fit
                     + rng.uniform(-10, 10))
    if effectiveness >= 78:
        outcome, boost, room = "landed", 2, 3
        note = "The room is buzzing."
    elif effectiveness >= 55:
        outcome, boost, room = "steady", 1, 1
        note = "Nods around the room."
    elif effectiveness >= 35:
        outcome, boost, room = "flat", 0, 0
        note = "It didn't quite land."
    else:
        outcome, boost, room = "backfired", -1, -2
        note = "A few eye-rolls. Wrong tone, wrong moment."

    # The room absorbs it.
    for p in _roster(team):
        _bump(p, room)

    dr = ensure_dressing_room_fields(team)
    record = {"tone": tone, "speaker": speaker, "speaker_name": speaker_name,
              "outcome": outcome, "boost": boost, "note": note,
              "context": dict(context)}
    try:
        if situation == "intermission":
            dr["intermission"] = record
        else:
            dr["pregame"] = record
    except Exception:
        pass
    _log(team, f"{speaker_name.title()} gave a {tone} talk -- {outcome}. "
               f"{note}")
    return record


def auto_talk(team: Any, context: Dict[str, Any], rng: Any = None
              ) -> Dict[str, Any]:
    """The AI path: the coach addresses the room through give_talk().

    Same mechanics as a user talk -- tone chosen by a simple read of the
    situation, effectiveness from real coach influence.
    """
    rng = rng or random
    state = str(context.get("score_state", "tied"))
    situation = str(context.get("situation", "pregame"))
    if state == "trailing":
        tone = "fired-up"
    elif state == "leading":
        tone = "cautious" if situation == "intermission" else "calm"
    else:
        tone = "calm"
    return give_talk(team, tone, context, speaker="coach", rng=rng)


def consume_pregame_boost(team: Any) -> int:
    """Read and clear the pending pre-game boost (sim calls this)."""
    dr = ensure_dressing_room_fields(team)
    talk = dr.get("pregame")
    if talk is None:
        talk = auto_talk(team, {"situation": "pregame", "score_state": "tied",
                               "rival": False, "streak": 0})
    try:
        dr["pregame"] = None
    except Exception:
        pass
    try:
        return int(talk.get("boost", 0))
    except Exception:
        return 0


def consume_intermission_boost(team: Any, score_diff: int = 0) -> int:
    """Read and clear the pending intermission boost (sim calls this)."""
    dr = ensure_dressing_room_fields(team)
    talk = dr.get("intermission")
    if talk is None:
        if score_diff > 0:
            state = "leading"
        elif score_diff < 0:
            state = "trailing"
        else:
            state = "tied"
        talk = auto_talk(team, {"situation": "intermission",
                               "score_state": state,
                               "rival": False, "streak": 0})
    try:
        dr["intermission"] = None
    except Exception:
        pass
    try:
        return int(talk.get("boost", 0))
    except Exception:
        return 0


def apply_pregame_talks(sim: Any) -> None:
    """Sim hook: read both rooms' pre-game words, nudge opening momentum.

    Called once at game start. Additive: nudge_momentum caps the swing.
    """
    try:
        home = getattr(sim, "home_team", None)
        away = getattr(sim, "away_team", None)
        if home is None or away is None:
            return
        import impact_system as _imp
    except Exception:
        return
    boosts = {}
    for team, is_home in ((home, True), (away, False)):
        try:
            boosts[is_home] = consume_pregame_boost(team)
        except Exception:
            boosts[is_home] = 0
    net = boosts.get(True, 0) - boosts.get(False, 0)
    try:
        if net > 0:
            for _ in range(min(2, net)):
                _imp.nudge_momentum(sim, home, strength=1.0)
        elif net < 0:
            for _ in range(min(2, -net)):
                _imp.nudge_momentum(sim, away, strength=1.0)
    except Exception:
        pass


def apply_intermission_talk(sim: Any) -> None:
    """Sim hook: second-intermission words nudge third-period momentum."""
    try:
        home = getattr(sim, "home_team", None)
        away = getattr(sim, "away_team", None)
        if home is None or away is None:
            return
        import impact_system as _imp
        diff = int(getattr(sim, "home_score", 0) or 0) - int(
            getattr(sim, "away_score", 0) or 0)
    except Exception:
        return
    boosts = {}
    for team, is_home in ((home, True), (away, False)):
        try:
            boosts[is_home] = consume_intermission_boost(
                team, score_diff=diff if is_home else -diff)
        except Exception:
            boosts[is_home] = 0
    net = boosts.get(True, 0) - boosts.get(False, 0)
    try:
        if net > 0:
            for _ in range(min(2, net)):
                _imp.nudge_momentum(sim, home, strength=1.0)
        elif net < 0:
            for _ in range(min(2, -net)):
                _imp.nudge_momentum(sim, away, strength=1.0)
    except Exception:
        pass
# --------------------------------------------------------------------------
# DressingRoomView -- the FM24-style dedicated screen
# --------------------------------------------------------------------------

class DressingRoomView(__import__("customtkinter").CTkFrame):
    """Dressing Room: hierarchy, social groups, team talks, room feed."""

    def __init__(self, parent, app=None):
        import customtkinter as ctk
        from ctk_theme import (
            init_ctk_theme, primary_button, secondary_button, heading, body,
            TEAL, TEAL_HOVER, BG, PANEL, CARD, BORDER,
            TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE,
            ROW_HOVER, ROW_SELECTED,
        )
        self._ctk = ctk
        self._ct = dict(TEAL=TEAL, TEAL_HOVER=TEAL_HOVER, BG=BG, PANEL=PANEL,
                        CARD=CARD, BORDER=BORDER, TEXT=TEXT, TEXT_DIM=TEXT_DIM,
                        TEXT_FAINT=TEXT_FAINT, GOLD=GOLD, GREEN=GREEN,
                        RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
                        ROW_SELECTED=ROW_SELECTED)
        self._primary_button = primary_button
        self._secondary_button = secondary_button
        self._heading = heading
        self._body = body
        init_ctk_theme()

        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None
        self.configure(fg_color=BG)

        self._tone_var = ctk.StringVar(value="calm")
        self._speaker_var = ctk.StringVar(value="coach")
        self._itone_var = ctk.StringVar(value="calm")
        self._ispeaker_var = ctk.StringVar(value="coach")
        self._rival_var = ctk.BooleanVar(value=False)

        self._create_interface()
        self.refresh()
        try:
            self.app.open_windows["dressing_room"] = self
        except Exception:
            pass

    # -- lifecycle ------------------------------------------------------
    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _on_closing(self):
        try:
            if "dressing_room" in self.app.open_windows:
                del self.app.open_windows["dressing_room"]
        except Exception:
            pass
        self.close_view()

    def _team(self):
        return getattr(self.app, "user_team", None)

    # -- layout ---------------------------------------------------------
    def _make_card(self, parent, title):
        ctk = self._ctk
        ct = self._ct
        card = ctk.CTkFrame(parent, fg_color=ct["CARD"], corner_radius=10,
                            border_width=1, border_color=ct["BORDER"])
        self._heading(card, text=title, size=14).pack(anchor="w", padx=12,
                                                     pady=(8, 4))
        return card

    def _create_interface(self):
        ctk = self._ctk
        ct = self._ct
        # Single scroll level for the whole view: one outer scroll, no
        # nested scrollable cards inside (they used to clip row 3 off the
        # bottom of the window at 1600x900).
        main = ctk.CTkScrollableFrame(self, fg_color=ct["BG"])
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        header = ctk.CTkFrame(main, fg_color=ct["PANEL"], corner_radius=10)
        header.pack(fill="x", pady=(0, 10))
        self._heading(header, text="Dressing Room").pack(side="left", padx=16,
                                                        pady=10)
        self.header_mood = ctk.CTkLabel(header, text="",
                                       font=("Segoe UI", 15, "bold"))
        self.header_mood.pack(side="right", padx=16, pady=10)
        self.header_line = ctk.CTkLabel(header, text="", font=("Segoe UI", 12),
                                        text_color=ct["TEXT_DIM"])
        self.header_line.pack(side="left", padx=8, pady=10)

        # Captaincy-crisis banner (hidden unless the weekly tick flags one)
        self.crisis_banner = self._build_crisis_banner(main)
        self.crisis_banner.pack(fill="x", pady=(0, 10))
        self.crisis_banner.pack_forget()

        # Row 1: hierarchy | team talk
        row1 = ctk.CTkFrame(main, fg_color=ct["BG"])
        row1.pack(fill="x", pady=(0, 10))
        self._row1 = row1

        hier_card = self._make_card(row1, "Hierarchy")
        hier_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.hier_scroll = ctk.CTkFrame(hier_card, fg_color=ct["CARD"])
        self.hier_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        talk_card = self._make_card(row1, "Team Talk")
        talk_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.talk_body = ctk.CTkFrame(talk_card, fg_color=ct["CARD"])
        self.talk_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_talk_ui(self.talk_body, pregame=True)

        # Row 2: social groups | intermission + feed
        row2 = ctk.CTkFrame(main, fg_color=ct["BG"])
        row2.pack(fill="x")

        sg_card = self._make_card(row2, "Social Groups")
        sg_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.sg_scroll = ctk.CTkFrame(sg_card, fg_color=ct["CARD"])
        self.sg_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = ctk.CTkFrame(row2, fg_color=ct["BG"])
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        italk_card = self._make_card(right, "Intermission Talk (3rd period)")
        italk_card.pack(fill="x", pady=(0, 10))
        self.italk_body = ctk.CTkFrame(italk_card, fg_color=ct["CARD"])
        self.italk_body.pack(fill="x", padx=8, pady=(0, 8))
        self._build_talk_ui(self.italk_body, pregame=False)

        feed_card = self._make_card(right, "Room Feed")
        feed_card.pack(fill="both", expand=True)
        self.feed_label = ctk.CTkLabel(feed_card, text="", justify="left",
                                       anchor="nw", font=("Segoe UI", 11),
                                       wraplength=430)
        self.feed_label.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Row 3: coaching (carousel) | decisions (causal receipts)
        row3 = ctk.CTkFrame(main, fg_color=ct["BG"])
        row3.pack(fill="x", pady=(10, 0))

        coach_card = self._make_card(row3, "Coaching")
        coach_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.coach_body = ctk.CTkFrame(coach_card, fg_color=ct["CARD"])
        self.coach_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_coach_ui(self.coach_body)

        dec_card = self._make_card(row3, "Decisions")
        dec_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.decisions_label = ctk.CTkLabel(
            dec_card, text="", justify="left", anchor="nw",
            font=("Segoe UI", 10), wraplength=430,
            text_color=ct["TEXT_DIM"])
        self.decisions_label.pack(fill="both", expand=True, padx=12,
                                  pady=(0, 10))

    def _build_crisis_banner(self, parent):
        """Captaincy-crisis decision event banner (hidden unless a crisis is
        flagged by the weekly tick)."""
        ctk = self._ctk
        ct = self._ct
        banner = ctk.CTkFrame(parent, fg_color="#3a2a12", corner_radius=10)
        self._crisis_title = ctk.CTkLabel(
            banner, text="", font=("Segoe UI", 12, "bold"),
            text_color=ct["GOLD"], wraplength=900, justify="left")
        self._crisis_title.pack(side="left", padx=14, pady=8)
        btnrow = ctk.CTkFrame(banner, fg_color="transparent")
        btnrow.pack(side="right", padx=12, pady=8)
        self._reassign_var = ctk.StringVar(value="")
        self._reassign_menu = ctk.CTkOptionMenu(btnrow, variable=self._reassign_var,
                                               values=[""], width=140)
        self._reassign_menu.pack(side="left", padx=(0, 6))
        for key, label in (("keep", "Keep the C"),
                           ("challenge", "Challenge privately"),
                           ("strip", "Strip the C"),
                           ("reassign", "Reassign")):
            b = ctk.CTkButton(btnrow, text=label, width=130, height=28,
                              fg_color=ct["TEAL"], hover_color=ct["TEAL_HOVER"],
                              font=("Segoe UI", 10, "bold"),
                              command=lambda k=key: self._resolve_crisis(k))
            b.pack(side="left", padx=(0, 6))
        return banner

    def _resolve_crisis(self, choice):
        team = self._team()
        if team is None:
            return
        try:
            new_c = None
            if choice == "reassign":
                want = self._reassign_var.get()
                for p in _roster(team):
                    if _name(p) == want:
                        new_c = p
                        break
            date_str = ""
            try:
                date_str = self.app.current_date.isoformat()
            except Exception:
                pass
            resolve_captaincy_crisis(team, choice, new_captain=new_c,
                                    date_str=date_str)
            ensure_dressing_room_fields(team)["captaincy_crisis"] = False
        except Exception:
            pass
        self.refresh()

    def _build_coach_ui(self, parent):
        """Head-coach card: style, demanding axis, trust, shelf life, and
        the carousel (fire -> candidates -> hire)."""
        ctk = self._ctk
        ct = self._ct
        self._coach_info = ctk.CTkLabel(parent, text="", justify="left",
                                       anchor="nw", font=("Segoe UI", 11),
                                       wraplength=400)
        self._coach_info.pack(anchor="w", padx=10, pady=(6, 4))
        btnrow = ctk.CTkFrame(parent, fg_color="transparent")
        btnrow.pack(anchor="w", padx=10, pady=(0, 4))
        fire = ctk.CTkButton(btnrow, text="Fire coach", width=110, height=28,
                             fg_color="#7a2d2d", hover_color="#5f2222",
                             font=("Segoe UI", 10, "bold"),
                             command=self._fire_coach)
        fire.pack(side="left", padx=(0, 6))
        self._cand_var = ctk.StringVar(value="")
        self._cand_menu = ctk.CTkOptionMenu(btnrow, variable=self._cand_var,
                                            values=[""], width=200)
        self._cand_menu.pack(side="left", padx=(0, 6))
        hire = ctk.CTkButton(btnrow, text="Hire", width=80, height=28,
                             fg_color=ct["TEAL"], hover_color=ct["TEAL_HOVER"],
                             font=("Segoe UI", 10, "bold"),
                             command=self._hire_coach)
        hire.pack(side="left")
        self._coach_cands = []

    def _fire_coach(self):
        team = self._team()
        if team is None:
            return
        try:
            date_str = ""
            try:
                date_str = self.app.current_date.isoformat()
            except Exception:
                pass
            fire_coach(team, reason="fired", date_str=date_str,
                       league=getattr(getattr(self, "app", None),
                                      "league", None))
        except Exception:
            pass
        self.refresh()

    def _hire_coach(self):
        team = self._team()
        if team is None:
            return
        try:
            want = self._cand_var.get()
            cand = next((c for c in self._coach_cands
                         if f"{c['name']} ({c['archetype']})" == want), None)
            if cand is None:
                return
            date_str = ""
            try:
                date_str = self.app.current_date.isoformat()
            except Exception:
                pass
            hire_coach(team, cand, date_str=date_str)
        except Exception:
            pass
        self.refresh()

    def _build_talk_ui(self, parent, pregame=True):
        ctk = self._ctk
        ct = self._ct
        tone_var = self._tone_var if pregame else self._itone_var
        speaker_var = self._speaker_var if pregame else self._ispeaker_var

        ctk.CTkLabel(parent, text="Tone:", font=("Segoe UI", 11),
                     text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=4,
                                                    pady=(4, 0))
        ctk.CTkSegmentedButton(parent, values=list(TONES),
                               variable=tone_var).pack(anchor="w", padx=4,
                                                       pady=4)
        ctk.CTkLabel(parent, text="Speaker:", font=("Segoe UI", 11),
                     text_color=ct["TEXT_DIM"]).pack(anchor="w", padx=4)
        ctk.CTkSegmentedButton(parent, values=["coach", "captain"],
                               variable=speaker_var).pack(anchor="w", padx=4,
                                                          pady=4)
        if pregame:
            ctk.CTkCheckBox(parent, text="Rivalry game",
                            variable=self._rival_var).pack(anchor="w", padx=4,
                                                          pady=4)
        btn_row = ctk.CTkFrame(parent, fg_color=ct["CARD"])
        btn_row.pack(fill="x", pady=6)
        label = "Give pre-game talk" if pregame else "Queue intermission talk"
        cmd = self._give_pregame_talk if pregame else self._give_intermission_talk
        self._primary_button(btn_row, text=label, command=cmd).pack(
            side="left", padx=4)
        result = ctk.CTkLabel(btn_row, text="", font=("Segoe UI", 11),
                              wraplength=260, justify="left")
        result.pack(side="left", padx=8)
        if pregame:
            self.talk_result = result
        else:
            self.italk_result = result
        pending = ctk.CTkLabel(parent, text="", font=("Segoe UI", 11, "italic"),
                               text_color=ct["GOLD"], wraplength=380,
                               justify="left")
        pending.pack(anchor="w", padx=4, pady=(0, 4))
        if pregame:
            self.pregame_pending = pending
        else:
            self.intermission_pending = pending

    # -- actions ----------------------------------------------------------
    def _talk_context(self, situation):
        team = self._team()
        streak = 0
        try:
            streak = int(getattr(team, "streak", 0) or 0)
        except Exception:
            pass
        if streak <= -2:
            state = "trailing"
        elif streak >= 3:
            state = "leading"
        else:
            state = "tied"
        try:
            rival = bool(self._rival_var.get())
        except Exception:
            rival = False
        return {"situation": situation, "score_state": state,
                "rival": rival, "streak": streak}

    def _give_pregame_talk(self):
        team = self._team()
        if team is None:
            return
        try:
            tone = self._tone_var.get()
            speaker = self._speaker_var.get()
        except Exception:
            tone, speaker = "calm", "coach"
        outcome = give_talk(team, tone, self._talk_context("pregame"),
                            speaker=speaker)
        self._show_outcome(self.talk_result, outcome)
        self.refresh()

    def _give_intermission_talk(self):
        team = self._team()
        if team is None:
            return
        try:
            tone = self._itone_var.get()
            speaker = self._ispeaker_var.get()
        except Exception:
            tone, speaker = "calm", "coach"
        outcome = give_talk(team, tone, self._talk_context("intermission"),
                            speaker=speaker)
        self._show_outcome(self.italk_result, outcome)
        self.refresh()

    def _show_outcome(self, label, outcome):
        ct = self._ct
        colors = {"landed": ct["GREEN"], "steady": ct["TEXT"],
                  "flat": ct["GOLD"], "backfired": ct["RED"]}
        try:
            label.configure(
                text=f"{outcome['tone'].title()} talk {outcome['outcome']}: "
                     f"{outcome['note']}",
                text_color=colors.get(outcome["outcome"], ct["TEXT"]))
        except Exception:
            pass

    # -- refresh ----------------------------------------------------------
    def refresh(self):
        ctk = self._ctk
        ct = self._ct
        team = self._team()
        if team is None:
            return
        ensure_dressing_room_fields(team)

        mood = room_mood(team)
        cap = captain_of(team)
        try:
            self.header_mood.configure(
                text=f"Room mood {mood}/100",
                text_color=ct["GREEN"] if mood >= 70 else (
                    ct["GOLD"] if mood >= 50 else ct["RED"]))
            cap_line = f"Captain: {_name(cap)}" if cap is not None else "No captain"
            self.header_line.configure(text=f"{cap_line}  |  "
                                            f"{len(_roster(team))} players")
        except Exception:
            pass

        # Hierarchy rows with influence bars
        try:
            for w in self.hier_scroll.winfo_children():
                w.destroy()
            for row in hierarchy(team)[:24]:
                fr = ctk.CTkFrame(self.hier_scroll, fg_color="transparent")
                fr.pack(fill="x", pady=1)
                badge = row["letter"] if row["letter"] != "-" else " "
                ctk.CTkLabel(fr, text=badge, width=22,
                             font=("Segoe UI", 11, "bold"),
                             text_color=ct["GOLD"] if badge in "CA"
                             else ct["TEXT_FAINT"]).pack(side="left")
                ctk.CTkLabel(fr, text=row["name"], width=150, anchor="w",
                             font=("Segoe UI", 11)).pack(side="left")
                bar = ctk.CTkProgressBar(fr, width=90, height=8)
                bar.pack(side="left", padx=6)
                try:
                    bar.set(row["influence"] / 100.0)
                except Exception:
                    pass
                ctk.CTkLabel(fr, text=f"{row['influence']}  {row['tier']}",
                             font=("Segoe UI", 10),
                             text_color=ct["TEXT_DIM"]).pack(side="left")
        except Exception:
            pass

        # Social groups
        try:
            for w in self.sg_scroll.winfo_children():
                w.destroy()
            cliques = form_cliques(team)
            if not cliques:
                ctk.CTkLabel(self.sg_scroll,
                             text="No settled groups yet -- a room of "
                                  "individuals.",
                             font=("Segoe UI", 11),
                             text_color=ct["TEXT_DIM"]).pack(anchor="w",
                                                             pady=4)
            for c in cliques:
                fr = ctk.CTkFrame(self.sg_scroll, fg_color=ct["PANEL"],
                                  corner_radius=8)
                fr.pack(fill="x", pady=4, padx=2)
                ctk.CTkLabel(fr, text=f"{c['name']}  (mood {c['mood']})",
                             font=("Segoe UI", 11, "bold")).pack(anchor="w",
                                                                 padx=8,
                                                                 pady=(6, 0))
                ctk.CTkLabel(fr, text=", ".join(c["members"]),
                             font=("Segoe UI", 10),
                             text_color=ct["TEXT_DIM"],
                             wraplength=400,
                             justify="left").pack(anchor="w", padx=8,
                                                  pady=(0, 6))
            fl = floaters(team)
            if fl:
                ctk.CTkLabel(
                    self.sg_scroll,
                    text="Floaters: " + ", ".join(f["name"] for f in fl[:8]),
                    font=("Segoe UI", 10, "italic"),
                    text_color=ct["TEXT_FAINT"], wraplength=400,
                    justify="left").pack(anchor="w", pady=4)
            # New arrivals still integrating
            for p in _roster(team):
                integ = integration_of(team, p)
                if integ < 100:
                    _arch = ""
                    try:
                        _rec = (ensure_dressing_room_fields(team)
                                ["arrivals"].get(_pid(p)) or {})
                        _arch = str(_rec.get("archetype", "") or "")
                    except Exception:
                        _arch = ""
                    _tag = {"blue_chip": " (top-10 pick)",
                            "veteran": " (veteran presence)"}.get(_arch, "")
                    ctk.CTkLabel(
                        self.sg_scroll,
                        text=f"{_name(p)}{_tag} settling in: "
                             f"{integ}% integrated",
                        font=("Segoe UI", 10, "italic"),
                        text_color=ct["BLUE"]).pack(anchor="w", pady=1)
        except Exception:
            pass

        # Pending boosts
        try:
            dr = ensure_dressing_room_fields(team)
            pg = dr.get("pregame")
            self.pregame_pending.configure(
                text=(f"Queued for period 1: {pg['tone']} talk "
                      f"({pg['outcome']}, {pg['boost']:+d} momentum)")
                if pg else "No pre-game talk queued.")
            im = dr.get("intermission")
            self.intermission_pending.configure(
                text=(f"Queued for period 3: {im['tone']} talk "
                      f"({im['outcome']}, {im['boost']:+d} momentum)")
                if im else "No intermission talk queued.")
        except Exception:
            pass

        # Room feed
        try:
            dr = ensure_dressing_room_fields(team)
            lines = dr.get("mood_log", [])[-10:]
            self.feed_label.configure(
                text="\n".join(f"- {ln}" for ln in reversed(lines))
                if lines else "Quiet in here. Give it time.")
        except Exception:
            pass

        # Captaincy-crisis banner
        try:
            dr = ensure_dressing_room_fields(team)
            if dr.get("captaincy_crisis"):
                detail = dr.get("captaincy_crisis_detail", {})
                cname = detail.get("captain_name", "The captain")
                chall = detail.get("challenger_names", [])
                self._crisis_title.configure(
                    text=f"Captaincy crisis: {cname} is losing the room. "
                         f"Challengers: {', '.join(chall) or 'none named'}. "
                         "No decision fixes this instantly -- choose the "
                         "politics you can live with.")
                vals = chall or [""]
                self._reassign_menu.configure(values=vals)
                self._reassign_var.set(vals[0])
                self.crisis_banner.pack(fill="x", pady=(0, 10),
                                        before=self._row1)
            else:
                self.crisis_banner.pack_forget()
        except Exception:
            pass

        # Coaching card
        try:
            coach = _room_head_coach(team)
            if coach is None:
                info = "No head coach. The carousel is your friend -- pick below."
            else:
                import reputation_system as _rs
                cname = getattr(coach, "name",
                                getattr(coach, "full_name", "Coach"))
                style = _rs.coach_style(coach).get("key", "balanced")
                axis = coach_demanding_axis(coach)
                ax_label = ("Demanding" if axis >= 0.7 else "Players' coach"
                            if axis <= 0.3 else "Balanced")
                trust = int(getattr(coach, "gm_trust", 70) or 70)
                weeks = int(getattr(coach, "shelf_weeks", 0) or 0)
                shelf = (f" -- message going stale ({weeks} wks)"
                         if axis > 0.65 and weeks > 30 else "")
                info = (f"{cname}\n{style.replace('_', ' ').title()} "
                        f"({ax_label})\nGM trust {trust}/100{shelf}")
            self._coach_info.configure(text=info)
            self._coach_cands = coaching_candidates(team)
            vals = [f"{c['name']} ({c['archetype']})"
                    for c in self._coach_cands] or ["No candidates"]
            self._cand_menu.configure(values=vals)
            self._cand_var.set(vals[0])
        except Exception:
            pass

        # Decisions: causal receipts, newest first
        try:
            dr = ensure_dressing_room_fields(team)
            receipts = dr.get("practice_receipts", [])[-6:]
            out = []
            for r in reversed(receipts):
                date = r.get("date", "")
                if r.get("kind") == "practice":
                    title = (f"{date} Practice: {r.get('focus', '')}/"
                             f"{r.get('intensity', '')}")
                    if r.get("bag_skate"):
                        title += " + bag skate"
                    title += f" -- {r.get('goal', '')}"
                else:
                    title = f"{date} {r.get('title', 'Decision')}"
                met = r.get("goal_met")
                tail = (" [goal met]" if met else
                        " [goal missed]" if met is False else "")
                gained = ", ".join(f"{n} ({d:+})"
                                   for n, d in (r.get("gained") or [])[:3])
                paid = ", ".join(f"{n} ({d:+})"
                                 for n, d in (r.get("paid") or [])[:3])
                detail = f"  approved by {r.get('approved_by', '?')}"
                if gained:
                    detail += f"; gained: {gained}"
                if paid:
                    detail += f"; paid: {paid}"
                rels = r.get("relationships") or []
                if rels:
                    detail += f"; {rels[0]}"
                out.append(title + tail + "\n" + detail)
            self.decisions_label.configure(
                text="\n\n".join(out) if out else "No decisions logged yet.")
        except Exception:
            pass


# --------------------------------------------------------------------------
# Room politics (Wave 2 roadmap): weekly practice planner, captaincy
# crises, coaching carousel.
#
# Guiding law: short-term gains create long-term political cost. Every
# practice or authority decision writes a causal receipt -- who approved
# it, who gained, who paid, which relationship shifted, and whether the
# on-ice goal was achieved. The formula stays hidden; the hockey reason
# stays visible.
#
# Even playing field: AI clubs run the same functions through
# auto_weekly_practice / auto_resolve_crisis / ai_room_politics_tick.
# --------------------------------------------------------------------------

PRACTICE_FOCI = {
    "special_teams": {
        "label": "Special Teams",
        "hint": "PP/PK sharpness -- the units learn the system faster",
        "goal": "sharpen the special-teams units",
    },
    "conditioning": {
        "label": "Conditioning",
        "hint": "Skate the fatigue out -- fitness up, legs back",
        "goal": "bring team fatigue down",
    },
    "systems": {
        "label": "Systems",
        "hint": "Tactical familiarity -- the room learns the system",
        "goal": "raise tactics familiarity",
    },
    "skills": {
        "label": "Skills",
        "hint": "Individual development push for the young core",
        "goal": "push individual development",
    },
    "recovery": {
        "label": "Recovery",
        "hint": "Rest and reset -- legs and mood recover together",
        "goal": "rest legs and reset the mood",
    },
}

PRACTICE_INTENSITIES = {
    "light": {"label": "Light", "load": 0.5, "effect": 0.6},
    "moderate": {"label": "Moderate", "load": 1.0, "effect": 1.0},
    "hard": {"label": "Hard", "load": 1.6, "effect": 1.35},
    "brutal": {"label": "Brutal", "load": 2.3, "effect": 1.6},
}

# Practice focus -> assistant specialties that matter for THIS session.
_FOCUS_SPECIALTY = {
    "special_teams": ("offense", "defense"),
    "conditioning": ("general",),
    "systems": ("defense", "offense"),
    "skills": ("offense", "defense", "goalie"),
    "recovery": ("general",),
}

# coach_style() key -> demanding axis. 1.0 = drill sergeant, 0.0 = players' coach.
_DEMANDING_BY_STYLE = {
    "drill_sergeant": 1.0,
    "motivator": 0.7,
    "tactician": 0.5,
    "balanced": 0.5,
    "developer": 0.3,
    "players_coach": 0.0,
}


def coach_demanding_axis(coach: Any) -> float:
    """Where the coach sits on the demanding <-> players'-coach axis."""
    try:
        import reputation_system as _rs
        key = _rs.coach_style(coach).get("key", "balanced")
    except Exception:
        key = "balanced"
    return _DEMANDING_BY_STYLE.get(key, 0.5)


def _room_head_coach(team: Any) -> Any:
    try:
        import reputation_system as _rs
        coach = _rs._head_coach_of(team)
        if coach is not None:
            return coach
    except Exception:
        pass
    return getattr(team, "head_coach", None)


def team_fatigue(team: Any) -> float:
    dr = ensure_dressing_room_fields(team)
    try:
        return float(dr.get("team_fatigue", 25.0))
    except Exception:
        return 25.0


def _set_team_fatigue(team: Any, value: float) -> None:
    dr = ensure_dressing_room_fields(team)
    dr["team_fatigue"] = max(0.0, min(100.0, float(value)))


def assistant_session_match(team: Any, focus: str) -> List[Dict[str, Any]]:
    """Assistants whose strengths matter for THIS session, not just by title.

    Returns [{name, specialty, prowess, matched}]. Matched specialties add
    effectiveness; a mismatched room still gets a whisper of general help.
    """
    out: List[Dict[str, Any]] = []
    try:
        import assistant_coaches as _ac
        wanted = _FOCUS_SPECIALTY.get(focus, ())
        for stf in _ac._assistants_of(team):
            spec = _ac.assistant_specialty(stf)
            try:
                prow = float(_ac.assistant_prowess(stf))
            except Exception:
                prow = 65.0
            out.append({
                "name": getattr(stf, "name",
                                getattr(stf, "full_name", "Assistant")),
                "specialty": spec,
                "prowess": round(prow, 1),
                "matched": spec in wanted,
            })
    except Exception:
        pass
    return out


def practice_effectiveness(team: Any, coach: Any, focus: str,
                           intensity: str) -> Dict[str, Any]:
    """How well the week's practice lands -- and why.

    Coach style changes effectiveness AND emotional cost: demanding coaches
    drill conditioning/systems better and teach/restore worse; players'
    coaches are the mirror. Tired rooms learn less.
    """
    spec = PRACTICE_INTENSITIES.get(intensity, PRACTICE_INTENSITIES["moderate"])
    demanding = coach_demanding_axis(coach) if coach is not None else 0.5
    if focus in ("conditioning", "systems"):
        style_mult = 0.85 + 0.30 * demanding
    elif focus in ("recovery", "skills"):
        style_mult = 1.15 - 0.30 * demanding
    else:  # special_teams: preparation matters more than personality
        style_mult = 0.95 + 0.10 * demanding
    matched = assistant_session_match(team, focus)
    asst_bonus = sum(m["prowess"] / 100.0 * 0.15 for m in matched
                     if m["matched"])
    fatigue_drag = team_fatigue(team) / 100.0 * 0.30
    eff = spec["effect"] * style_mult * (1.0 + asst_bonus) * (1.0 - fatigue_drag)
    return {
        "effectiveness": round(max(0.2, eff), 3),
        "demanding": round(demanding, 2),
        "style_mult": round(style_mult, 3),
        "assistant_bonus": round(asst_bonus, 3),
        "fatigue_drag": round(fatigue_drag, 3),
        "load": spec["load"],
        "assistants": matched,
    }


def _practice_receipt(team: Any, **fields: Any) -> Dict[str, Any]:
    """A causal receipt: who approved it, who gained, who paid, which
    relationship shifted, and whether the on-ice goal was achieved."""
    dr = ensure_dressing_room_fields(team)
    receipts = dr.setdefault("practice_receipts", [])
    rec = {"goal_met": None}
    rec.update(fields)
    receipts.append(rec)
    del receipts[:-20]
    return rec


def resolve_practice_receipts(team: Any) -> None:
    """Score last week's stated goal against what actually happened."""
    dr = ensure_dressing_room_fields(team)
    for rec in dr.get("practice_receipts", []):
        if rec.get("goal_met") is not None:
            continue
        kind = rec.get("kind", "practice")
        target = rec.get("target")
        try:
            if kind == "practice" and isinstance(target, dict):
                tkind = target.get("type")
                if tkind == "familiarity":
                    import tactics as _tx
                    cur = float(getattr(team, "tactics_familiarity", 85.0))
                    rec["goal_met"] = cur >= float(target.get("value", 0)) - 0.5
                    rec["actual"] = round(cur, 1)
                elif tkind == "fatigue":
                    cur = team_fatigue(team)
                    rec["goal_met"] = cur <= float(target.get("value", 100)) + 2.0
                    rec["actual"] = round(cur, 1)
                elif tkind == "immediate":
                    rec["goal_met"] = True
                    rec["actual"] = target.get("note", "done")
        except Exception:
            continue


def _week_key(date_str: str) -> str:
    """ISO year-week for a date string ("2026-W40"), or "" when unparseable.

    Used to make the weekly practice scheduler idempotent: one execution
    per team per week, no matter how many paths (button, Sunday tick) try
    to run it.
    """
    try:
        from datetime import date as _date
        d = _date.fromisoformat(str(date_str)[:10])
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    except Exception:
        return ""


def _practice_already_ran(team: Any, date_str: str) -> bool:
    wk = _week_key(date_str)
    if not wk:
        return False
    try:
        return ensure_dressing_room_fields(team).get(
            "practice_last_run_week") == wk
    except Exception:
        return False


def _stamp_practice_run(team: Any, date_str: str) -> None:
    wk = _week_key(date_str)
    if not wk:
        return
    try:
        ensure_dressing_room_fields(team)["practice_last_run_week"] = wk
    except Exception:
        pass


def _engagement_key(player: Any) -> str:
    try:
        import reputation_system as _rs
        return str(_rs.engagement_style(player).get("key", "steady_professional"))
    except Exception:
        return "steady_professional"


def run_weekly_practice(team: Any, focus: str = "systems",
                        intensity: str = "moderate", bag_skate: bool = False,
                        approved_by: str = "Head coach",
                        date_str: str = "") -> Dict[str, Any]:
    """Execute one week of practice: on-ice gains, room costs, causal receipt.

    Short-term gains create long-term political cost: bag skates can stop a
    slide now, but each one is logged and repeated punishment erodes trust
    (coach.gm_trust) and recovery (team fatigue climbs).
    """
    roster = _roster(team)
    if not roster:
        return {}
    if focus not in PRACTICE_FOCI:
        focus = "systems"
    if intensity not in PRACTICE_INTENSITIES:
        intensity = "moderate"

    # Idempotency stamp: one execution per team per week. Explicit runs
    # (the Practice tab button) always execute and move the stamp; the
    # automatic weekly ticks skip a week that already ran.
    _stamp_practice_run(team, date_str)

    # Score last week's goal before writing this week's receipt.
    resolve_practice_receipts(team)

    coach = _room_head_coach(team)
    calc = practice_effectiveness(team, coach, focus, intensity)
    eff = calc["effectiveness"]
    demanding = calc["demanding"]
    load = calc["load"]
    coach_name = getattr(coach, "name", getattr(coach, "full_name", "Coach")) \
        if coach is not None else "No head coach"
    style_key = None
    try:
        import reputation_system as _rs
        style_key = _rs.coach_style(coach).get("key", "balanced") \
            if coach is not None else "balanced"
    except Exception:
        style_key = "balanced"

    gained: List[List[Any]] = []  # [name, delta]
    paid: List[List[Any]] = []
    relationships: List[str] = []
    lines: List[str] = []

    def _delta(player: Any, d: float, why: str = "") -> None:
        before = _clamp(getattr(player, "morale", 70))
        _bump(player, d)
        after = _clamp(getattr(player, "morale", 70))
        real = round(after - before, 1)
        if real > 0:
            gained.append([_name(player), real])
        elif real < 0:
            paid.append([_name(player), real])

    # -- on-ice effects -------------------------------------------------
    fam0 = float(getattr(team, "tactics_familiarity", 85.0))
    target: Dict[str, Any] = {"type": "immediate", "note": "week completed"}
    if focus in ("systems", "special_teams"):
        try:
            import tactics as _tx
            _tx.tick_tactics_familiarity(team, amount=2.0 * eff)
        except Exception:
            team.tactics_familiarity = min(
                95.0, fam0 + 2.0 * eff)
        fam1 = float(getattr(team, "tactics_familiarity", 85.0))
        lines.append(f"Systems work: familiarity {fam0:.0f} -> {fam1:.0f}.")
        target = {"type": "familiarity",
                  "value": round(min(95.0, fam0 + 2.0 * eff), 1)}
    elif focus == "conditioning":
        fat0 = team_fatigue(team)
        _set_team_fatigue(team, fat0 - 12.0 * eff)
        lines.append(f"Conditioning: team fatigue {fat0:.0f} -> "
                     f"{team_fatigue(team):.0f}.")
        target = {"type": "fatigue",
                  "value": round(max(0.0, fat0 - 12.0 * eff), 1)}
    elif focus == "skills":
        young = sorted([p for p in roster
                        if getattr(p, "age", 30) <= 26],
                       key=lambda p: getattr(p, "age", 30))[:3]
        bumped = 0
        for p in young:
            attr = "shooting" if getattr(p, "position", "") != "G" else "reflexes"
            try:
                cur = float(getattr(p, attr, 60) or 60)
                setattr(p, attr, min(99.0, cur + 0.4 * eff))
                bumped += 1
                _delta(p, 1, "invested")
            except Exception:
                continue
        lines.append(f"Skills: {bumped} young players pushed.")
        target = {"type": "immediate",
                  "note": f"{bumped} development bumps applied"}
    elif focus == "recovery":
        fat0 = team_fatigue(team)
        _set_team_fatigue(team, fat0 - 20.0)
        for p in roster:
            _delta(p, 2 * eff, "rest")
        lines.append(f"Recovery week: fatigue {fat0:.0f} -> "
                     f"{team_fatigue(team):.0f}, room breathes.")
        target = {"type": "fatigue",
                  "value": round(max(0.0, fat0 - 20.0), 1)}

    # -- emotional cost: intensity x demanding, filtered by engagement ----
    harshness = load * (0.5 + demanding)
    for p in roster:
        ek = _engagement_key(p)
        d = 0.0
        if ek == "thrives_on_structure":
            d += 1.0 if harshness > 1.2 else 0.0
        elif ek in ("veteran_autonomy", "needs_freedom"):
            d -= round(harshness, 1)
        elif ek == "fragile_confidence":
            d -= 2.0 if (bag_skate or harshness > 1.5) else 0.5
        elif ek == "needs_guidance":
            d += 1.0 if demanding > 0.6 else -0.5
        # steady_professional: nothing. Pros bring it regardless.
        if d:
            _delta(p, d, "practice load")

    # -- bag skate: stop the slide now, pay later ------------------------
    dr = ensure_dressing_room_fields(team)
    if bag_skate:
        # Rolling count: punishment compounds when it becomes a pattern.
        recent = (dr.get("bag_skate_dates", []) or [])[-4:]
        n_recent = len(recent)
        dr["practice_edge"] = 0.02  # one-game compete response, sim-consumed
        trust_cost = 3 + 2 * n_recent
        if coach is not None:
            try:
                coach.gm_trust = max(
                    0, float(getattr(coach, "gm_trust", 70) or 70) - trust_cost)
            except Exception:
                pass
        _set_team_fatigue(team, team_fatigue(team) + 8 + 4 * n_recent)
        for p in roster:
            ek = _engagement_key(p)
            if ek in ("veteran_autonomy", "needs_freedom", "fragile_confidence"):
                _delta(p, -2, "bag skate")
            elif ek == "thrives_on_structure":
                _delta(p, 1, "accountability")
        if date_str:
            dr.setdefault("bag_skate_dates", []).append(date_str)
        relationships.append(
            f"Bag skate #{n_recent + 1} in recent memory -- trust -{trust_cost}.")
        lines.append(f"Bag skate: one-game compete edge banked "
                     f"(+2%). Trust cost {trust_cost}.")
    else:
        # Hard weeks without punishment still tire legs.
        _set_team_fatigue(team, team_fatigue(team) + load * 6 - 4)

    # -- demanding-coach shelf life --------------------------------------
    if coach is not None and demanding > 0.65:
        try:
            coach.shelf_weeks = int(getattr(coach, "shelf_weeks", 0) or 0) + 1
            if coach.shelf_weeks > 30:
                for p in roster:
                    _delta(p, -1, "stale message")
                coach.gm_trust = max(
                    0, float(getattr(coach, "gm_trust", 70) or 70) - 1)
                relationships.append("The message is getting stale "
                                     f"({coach.shelf_weeks} weeks).")
        except Exception:
            pass

    goal_label = PRACTICE_FOCI[focus]["goal"]
    rec = _practice_receipt(
        team,
        kind="practice", date=date_str, focus=focus, intensity=intensity,
        bag_skate=bool(bag_skate), approved_by=approved_by,
        coach=coach_name, coach_style=style_key,
        effectiveness=round(eff, 3),
        gained=sorted(gained, key=lambda x: -x[1])[:4],
        paid=sorted(paid, key=lambda x: x[1])[:4],
        relationships=relationships,
        goal=f"{PRACTICE_FOCI[focus]['label']}: {goal_label}",
        target=target, goal_met=None,
        assistants=[f"{m['name']} ({m['specialty']}, {m['prowess']})"
                    for m in calc["assistants"] if m["matched"]],
    )
    dr["practice_plan"] = {"focus": focus, "intensity": intensity,
                           "bag_skate": bool(bag_skate)}
    for ln in lines:
        _log(team, ln)
    _log(team, f"Practice: {PRACTICE_FOCI[focus]['label']} / "
               f"{PRACTICE_INTENSITIES[intensity]['label']} "
               f"({approved_by}).")
    rec["lines"] = lines
    return rec


def auto_weekly_practice(team: Any, date_str: str = "",
                         league: Any = None) -> Dict[str, Any]:
    """AI weekly planning: the same practice function, the choice automated.

    Heuristic, not optimal: losing rooms skate, tired rooms rest, lost rooms
    drill the system. The automation is the only difference.
    """
    roster = _roster(team)
    if not roster:
        return {}
    mood = room_mood(team)
    form = _team_form(team, league)
    fatigue = team_fatigue(team)
    dr = ensure_dressing_room_fields(team)
    recent_bags = len((dr.get("bag_skate_dates", []) or [])[-4:])
    fam = float(getattr(team, "tactics_familiarity", 85.0))

    focus, intensity, bag = "systems", "moderate", False
    if mood < 40 or fatigue >= 70:
        focus, intensity = "recovery", "light"
    elif form.get("losing_streak", 0) >= 3 and recent_bags < 2 and fatigue < 70:
        focus, intensity, bag = "conditioning", "hard", True
    elif form.get("losing_streak", 0) >= 2:
        focus, intensity = "conditioning", "moderate"
    elif fam < 80:
        focus, intensity = "systems", "moderate"
    else:
        # Rotate the developmental focus so every area gets work.
        week = 0
        try:
            week = int(str(date_str).replace("-", "") or 0) % 3
        except Exception:
            pass
        focus = ["skills", "special_teams", "systems"][week]
    return run_weekly_practice(team, focus=focus, intensity=intensity,
                               bag_skate=bag, approved_by="AI head coach",
                               date_str=date_str)


def _team_form(team: Any, league: Any = None) -> Dict[str, Any]:
    """Win pct + losing streak from the standings, defensively."""
    form = {"win_pct": 0.5, "losing_streak": 0}
    try:
        st = (getattr(league, "standings", None) or {}).get(
            getattr(team, "team_name", ""), {})
        w = st.get("W", st.get("Wins", 0)) or 0
        l = st.get("L", st.get("Losses", 0)) or 0
        otl = st.get("OTL", 0) or 0
        form["win_pct"] = w / max(1, w + l + otl)
        form["losing_streak"] = int(
            st.get("losing_streak", st.get("streak", 0)) or 0)
    except Exception:
        pass
    return form


# --------------------------------------------------------------------------
# Captaincy crises
# --------------------------------------------------------------------------

def detect_captaincy_crisis(team: Any,
                            league: Any = None) -> Optional[Dict[str, Any]]:
    """A crisis triggers only when leaders, room response and performance
    agree: the captain is losing the leaders, the room is sour, and the
    standings back the grumbling."""
    roster = _roster(team)
    cap = captain_of(team)
    if cap is None or not roster:
        return None
    cap_inf = influence_of(cap)
    leaders = [p for p in roster
               if p is not cap and influence_of(p) >= 70]
    # The leaders agree when someone has overtaken the captain's pull --
    # the C still on his chest, the room already following someone else.
    overtaken = any(influence_of(p) >= cap_inf for p in leaders)
    leaders_agree = False
    try:
        import reputation_system as _rs
        coach = _room_head_coach(team)
        resp = _rs.player_coach_response(
            cap, coach).get("label", "") if coach else ""
        leaders_agree = overtaken or resp in ("Tuning out", "Quit on coach")
    except Exception:
        leaders_agree = overtaken
    room_agrees = room_mood(team) < 45
    form = _team_form(team, league)
    perf_agrees = (form.get("losing_streak", 0) >= 3
                   or form.get("win_pct", 0.5) < 0.40)
    if leaders_agree and room_agrees and perf_agrees:
        severity = 1
        if sum(1 for p in leaders if influence_of(p) >= cap_inf) >= 2:
            severity += 1
        if form.get("losing_streak", 0) >= 5:
            severity += 1
        return {
            "captain": cap,
            "captain_name": _name(cap),
            "challengers": leaders[:3],
            "challenger_names": [_name(p) for p in leaders[:3]],
            "severity": min(3, severity),
        }
    return None


def _crisis_receipt(team: Any, title: str, choice: str, gained: list,
                    paid: list, relationships: list, date_str: str) -> None:
    _practice_receipt(
        team, kind="authority", date=date_str, title=title, choice=choice,
        approved_by="GM", coach="", coach_style="", effectiveness=None,
        gained=gained, paid=paid, relationships=relationships,
        goal="settle the captaincy", target={"type": "immediate",
                                             "note": "decision logged"},
        goal_met=True)


def resolve_captaincy_crisis(team: Any, choice: str,
                            new_captain: Any = None,
                            date_str: str = "") -> List[str]:
    """Resolve a captaincy crisis. No path instantly fixes morale -- every
    option moves hierarchy, relationships, and legitimacy, not just a number.

    choice: keep | challenge | strip | reassign
    """
    import random
    roster = _roster(team)
    cap = captain_of(team)
    lines: List[str] = []
    if cap is None or not roster:
        return lines
    cname = _name(cap)
    gained: List[List[Any]] = []
    paid: List[List[Any]] = []
    relationships: List[str] = []

    def _d(player: Any, d: float) -> None:
        before = _clamp(getattr(player, "morale", 70))
        _bump(player, d)
        after = _clamp(getattr(player, "morale", 70))
        (gained if after > before else paid).append([_name(player),
                                                    round(after - before, 1)])

    if choice == "keep":
        for p in roster:
            _d(p, 1)
        _d(cap, -2)
        relationships.append(f"{cname} keeps the C -- on notice, not exonerated.")
        lines.append(f"The C stays with {cname}. The room steadies, barely.")
    elif choice == "challenge":
        # Private meeting: he responds, or he resents it.
        if random.random() < 0.55:
            try:
                cap.leadership = _clamp(
                    float(getattr(cap, "leadership", 60) or 60) + 3)
            except Exception:
                pass
            _d(cap, 2)
            for p in roster:
                if p is not cap:
                    _d(p, 1)
            relationships.append(f"{cname} took the challenge -- "
                                 "leadership +3, GM relationship steadier.")
            lines.append(f"Behind closed doors, {cname} took it like a pro.")
        else:
            _d(cap, -6)
            for p in roster:
                if p is not cap:
                    _d(p, -1)
            relationships.append(f"{cname} resented the meeting -- "
                                 "trade-request risk up.")
            try:
                cap.trade_request_risk = min(
                    100, float(getattr(cap, "trade_request_risk", 0) or 0) + 15)
            except Exception:
                pass
            lines.append(f"{cname} didn't take the challenge well. Watch him.")
    elif choice in ("strip", "reassign"):
        successor = None
        if choice == "reassign":
            cands = [p for p in roster if p is not cap]
            if new_captain is not None and any(
                    _pid(p) == _pid(new_captain) for p in cands):
                successor = next(p for p in cands
                                 if _pid(p) == _pid(new_captain))
            else:
                successor = max(cands, key=lambda p: influence_of(p),
                                default=None)
        try:
            cap.captaincy = ""
        except Exception:
            pass
        _d(cap, -8)
        cap_clique = clique_of(team, cap)
        for p in roster:
            if p is cap:
                continue
            if cap_clique is not None and _pid(p) in cap_clique["member_ids"]:
                _d(p, -3)  # loyalists grieve
            else:
                _d(p, 1)   # everyone else exhales
        relationships.append(f"{cname} stripped of the C -- his corner of "
                             "the room grieves, the rest exhales.")
        lines.append(f"The C is off {cname}'s chest.")
        if successor is not None:
            sname = _name(successor)
            legitimacy = 0.30 + influence_of(successor) / 200.0
            if getattr(successor, "captaincy", "") == "A":
                legitimacy += 0.15
            try:
                if int(getattr(successor, "team_tenure_years",
                               0) or 0) >= 3:
                    legitimacy += 0.10
            except Exception:
                pass
            legitimacy = min(1.0, legitimacy)
            try:
                successor.captaincy = "C"
            except Exception:
                pass
            if legitimacy >= 0.70:
                for p in roster:
                    _d(p, 2)
                relationships.append(
                    f"{sname} takes the C -- legitimacy "
                    f"{legitimacy:.0%}, the room buys it.")
                lines.append(f"{sname} gets the C, and the room buys it.")
            else:
                for p in roster:
                    if p is not successor:
                        _d(p, -2)
                _d(successor, -3)
                relationships.append(
                    f"{sname} takes the C -- legitimacy only "
                    f"{legitimacy:.0%}. The room doesn't buy it... yet.")
                lines.append(f"{sname} gets the C. The room isn't sold.")
    else:
        return lines

    _crisis_receipt(team, f"Captaincy crisis: {cname}", choice,
                    sorted(gained, key=lambda x: -x[1])[:4],
                    sorted(paid, key=lambda x: x[1])[:4],
                    relationships, date_str)
    for ln in lines:
        _log(team, ln)
    return lines


def auto_resolve_crisis(team: Any, crisis: Dict[str, Any],
                        date_str: str = "") -> List[str]:
    """AI crisis management: challenge a salvageable captain, otherwise hand
    the C to the strongest challenger. Same resolutions, automated choice."""
    cap = crisis.get("captain")
    challengers = crisis.get("challengers") or []
    cap_inf = influence_of(cap)
    overtaken = any(influence_of(p) >= cap_inf for p in challengers)
    if not overtaken:
        choice, new_c = "challenge", None
    elif challengers:
        choice, new_c = "reassign", challengers[0]
    else:
        choice, new_c = "keep", None
    return resolve_captaincy_crisis(team, choice, new_captain=new_c,
                                   date_str=date_str)


# --------------------------------------------------------------------------
# Coaching carousel
# --------------------------------------------------------------------------

# Fired/available coaches waiting for their next chair. Entries:
# {coach, name, style, hot_seat, bonds, grudges, past_clubs, reason, date}
COACH_CAROUSEL: List[Dict[str, Any]] = []


def remember_coach(coach: Any, team: Any = None, reason: str = "fired",
                   date_str: str = "") -> Dict[str, Any]:
    """A coach leaves a chair carrying hot-seat reputation, tactical
    identity, prior player bonds and grudges."""
    try:
        import reputation_system as _rs
        style = _rs.coach_style(coach).get("key", "balanced")
    except Exception:
        style = "balanced"
    bonds, grudges = [], []
    if team is not None:
        try:
            import reputation_system as _rs
            cid = getattr(coach, "id", None)
            for p in _roster(team):
                cbs = getattr(p, "coach_bonds", None) or {}
                if cid is not None and cid in cbs:
                    bonds.append(_name(p))
                    continue
                try:
                    if _rs.player_coach_response(
                            p, coach).get("label") == "Quit on coach":
                        grudges.append(_name(p))
                except Exception:
                    continue
        except Exception:
            pass
    hot_seat = 70 if reason == "fired" else 40
    past = list(getattr(coach, "past_clubs", None) or [])
    tname = getattr(team, "team_name", "") if team is not None else ""
    if tname and tname not in past:
        past.append(tname)
    entry = {
        "coach": coach,
        "name": getattr(coach, "name",
                        getattr(coach, "full_name", "Coach")),
        "style": style,
        "hot_seat": hot_seat,
        "bonds": bonds,
        "grudges": grudges,
        "past_clubs": past,
        "reason": reason,
        "date": date_str,
    }
    cid = getattr(coach, "id", id(coach))
    COACH_CAROUSEL[:] = [e for e in COACH_CAROUSEL
                         if getattr(e.get("coach"), "id", id(e.get("coach")))
                         != cid]
    COACH_CAROUSEL.append(entry)
    try:
        coach.past_clubs = past
    except Exception:
        pass
    return entry


def _staff_id(stf: Any) -> Any:
    return getattr(stf, "id", id(stf))


def _is_head_coach_role(stf: Any) -> bool:
    return "Head Coach" in str(
        getattr(getattr(stf, "role", None), "value", ""))


def _set_head_coach_role(stf: Any) -> None:
    """Give a staff member the Head Coach role, preserving the role
    object's shape (StaffRole enum in prod, SimpleNamespace in tests)."""
    role = getattr(stf, "role", None)
    try:
        stf.role = type(role).HEAD_COACH
    except Exception:
        try:
            from types import SimpleNamespace as _SN
            stf.role = _SN(value="Head Coach")
        except Exception:
            pass


def _remove_staff_member(team: Any, coach: Any) -> None:
    try:
        cid = _staff_id(coach)
        staff = getattr(team, "staff", None)
        if isinstance(staff, list):
            staff[:] = [s for s in staff if _staff_id(s) != cid]
    except Exception:
        pass


def fire_coach(team: Any, reason: str = "fired",
               date_str: str = "", league: Any = None) -> Optional[Dict[str, Any]]:
    """Fire the head coach: he joins the carousel, the room reacts.

    Addition by subtraction for the quit-on-coach crowd; grief for the
    bonded; uncertainty for everyone else.

    league (optional): when provided, the firing is recorded in the
    league's rivalries -- the coach blames the GM, and the grudge
    follows the coach to his next job. Additive: rivalries only.
    """
    coach = _room_head_coach(team)
    if coach is None:
        return None
    if league is not None:
        try:
            from reputation_system import record_firing as _rf
            _rivs = getattr(league, "rivalries", None)
            if isinstance(_rivs, list):
                _rf(_rivs, coach, team)
        except Exception:
            pass
    entry = remember_coach(coach, team, reason=reason, date_str=date_str)
    cname = entry["name"]
    roster = _roster(team)
    gained, paid, rels, lines = [], [], [], []
    bonded = set(entry["bonds"])
    grudges = set(entry["grudges"])
    for p in roster:
        nm = _name(p)
        if nm in bonded:
            _bump(p, -4)
            paid.append([nm, -4])
        elif nm in grudges:
            _bump(p, 3)
            gained.append([nm, 3])
        else:
            _bump(p, -1)
    rels.append(f"{cname} fired ({reason}). {len(bonded)} bonded players "
                f"grieve, {len(grudges)} exhale.")
    lines.append(f"{cname} is out. The room absorbs the shock.")
    try:
        team.head_coach = None
    except Exception:
        pass
    # The chair is empty everywhere: staff list included, or
    # _room_head_coach() would keep finding him via team.staff.
    _remove_staff_member(team, coach)
    _practice_receipt(
        team, kind="authority", date=date_str,
        title=f"Head coach fired: {cname}", choice=reason,
        approved_by="GM", coach=cname,
        coach_style=entry["style"], effectiveness=None,
        gained=gained, paid=paid, relationships=rels,
        goal="change the voice behind the bench",
        target={"type": "immediate", "note": "coach dismissed"},
        goal_met=True)
    for ln in lines:
        _log(team, ln)
    return entry


def coaching_candidates(team: Any) -> List[Dict[str, Any]]:
    """The carousel plus coordinators who earned interviews.

    Archetypes: the decorated retread (multiple past clubs, hot seat),
    the system specialist (tactician identity), fresh blood (young,
    motivating coordinator).
    """
    cands: List[Dict[str, Any]] = []
    for e in COACH_CAROUSEL:
        past = e.get("past_clubs", [])
        if len(past) >= 2:
            arch = "retread"
        elif e.get("style") == "tactician":
            arch = "specialist"
        else:
            arch = "retread"
        cands.append({
            "coach": e["coach"], "name": e["name"], "source": "carousel",
            "archetype": arch, "style": e["style"],
            "hot_seat": e["hot_seat"],
            "note": (f"{len(past)} past clubs; hot seat {e['hot_seat']}. "
                     f"Bonds: {', '.join(e['bonds'][:3]) or 'none'}."),
        })
    # Coordinators earn interviews: high-prowess assistants.
    try:
        import assistant_coaches as _ac
        for stf in _ac._assistants_of(team):
            try:
                prow = float(_ac.assistant_prowess(stf))
            except Exception:
                prow = 60.0
            if prow < 70:
                continue
            age = int(getattr(stf, "age", 45) or 45)
            try:
                motiv = float(getattr(stf, "motivating", 60) or 60)
            except Exception:
                motiv = 60.0
            arch = "fresh blood" if (age < 40 and motiv >= 70) else "specialist"
            cands.append({
                "coach": stf,
                "name": getattr(stf, "name",
                                getattr(stf, "full_name", "Coordinator")),
                "source": "promotion", "archetype": arch,
                "style": "developer" if arch == "fresh blood" else "tactician",
                "hot_seat": 10,
                "note": f"In-house coordinator, prowess {prow:.0f}.",
            })
    except Exception:
        pass
    return cands


def hire_coach(team: Any, candidate: Dict[str, Any],
               date_str: str = "") -> List[str]:
    """A hire changes practice, fit, staff roles and expectations together.

    Prior bonds/grudges with the current roster carry through the door with
    him -- the carousel has a memory.
    """
    coach = candidate.get("coach")
    lines: List[str] = []
    if coach is None:
        return lines
    cname = candidate.get("name", getattr(
        coach, "name", getattr(coach, "full_name", "Coach")))
    roster = _roster(team)
    gained, paid, rels = [], [], []
    try:
        import reputation_system as _rs
        cid = getattr(coach, "id", None)
        for p in roster:
            nm = _name(p)
            cbs = getattr(p, "coach_bonds", None) or {}
            if cid is not None and cid in cbs:
                _bump(p, 4)
                gained.append([nm, 4])
                continue
            try:
                if _rs.player_coach_response(
                        p, coach).get("label") == "Quit on coach":
                    _bump(p, -5)
                    paid.append([nm, -5])
            except Exception:
                continue
    except Exception:
        pass
    try:
        team.head_coach = coach
        coach.shelf_weeks = 0
        coach.gm_trust = 70  # a new voice gets a clean ledger
    except Exception:
        pass
    # The hire lands in team.staff with the Head Coach role: promotions
    # get their role updated (no duplicate entry), outside hires are
    # appended, and any stale head-coach listing vacates the chair.
    try:
        cid = _staff_id(coach)
        staff = getattr(team, "staff", None)
        if not isinstance(staff, list):
            staff = []
            team.staff = staff
        kept = []
        for stf in staff:
            if _staff_id(stf) == cid:
                _set_head_coach_role(stf)
                kept.append(stf)
            elif _is_head_coach_role(stf):
                continue  # stale listing vacates the chair
            else:
                kept.append(stf)
        if all(_staff_id(s) != cid for s in kept):
            _set_head_coach_role(coach)
            kept.append(coach)
        staff[:] = kept
    except Exception:
        pass
    cid = getattr(coach, "id", id(coach))
    COACH_CAROUSEL[:] = [e for e in COACH_CAROUSEL
                         if getattr(e.get("coach"), "id", id(e.get("coach")))
                         != cid]
    arch = candidate.get("archetype", "")
    rels.append(f"{cname} hired ({arch or 'coach'}). "
                f"{len(gained)} reunions lift the room, "
                f"{len(paid)} old grudges walk back in.")
    lines.append(f"{cname} takes over behind the bench ({arch}).")
    try:
        style = _rs.coach_style(coach).get("key", "balanced")
    except Exception:
        style = "balanced"
    _practice_receipt(
        team, kind="authority", date=date_str,
        title=f"Head coach hired: {cname}", choice=arch,
        approved_by="GM", coach=cname, coach_style=style,
        effectiveness=None, gained=gained, paid=paid,
        relationships=rels,
        goal="new voice, new expectations",
        target={"type": "immediate", "note": "coach hired"},
        goal_met=True)
    for ln in lines:
        _log(team, ln)
    return lines


# --------------------------------------------------------------------------
# Weekly ticks -- user and AI run the same functions
# --------------------------------------------------------------------------

def user_room_politics_tick(team: Any, date_str: str = "",
                            league: Any = None) -> Dict[str, Any]:
    """Execute the user's stored weekly plan (set in the Practice tab; the
    plan persists until changed). Flags a captaincy crisis for the GM's
    decision instead of auto-resolving it.

    The practice run is idempotent per week: if the GM already hit
    "Set & Run This Week" this week, the Sunday repeat is skipped.
    """
    dr = ensure_dressing_room_fields(team)
    plan = dr.get("practice_plan") or {"focus": "systems",
                                       "intensity": "moderate",
                                       "bag_skate": False}
    out = {}
    if not _practice_already_ran(team, date_str):
        out = run_weekly_practice(
            team, focus=plan.get("focus", "systems"),
            intensity=plan.get("intensity", "moderate"),
            bag_skate=bool(plan.get("bag_skate", False)),
            approved_by="Head coach", date_str=date_str)
    crisis = detect_captaincy_crisis(team, league)
    dr["captaincy_crisis"] = crisis is not None
    if crisis is not None:
        dr["captaincy_crisis_detail"] = {
            "captain_name": crisis["captain_name"],
            "challenger_names": crisis["challenger_names"],
            "severity": crisis["severity"],
        }
        _log(team, f"Captaincy crisis: {crisis['captain_name']} is losing "
                    "the room. A decision is due.")
    return {"practice": out, "crisis": crisis}


def ai_room_politics_tick(team: Any, date_str: str = "",
                          league: Any = None) -> Dict[str, Any]:
    """AI weekly tick: same practice function, automated choices; crises
    auto-resolved; an empty chair gets filled from the carousel.

    The practice run is idempotent per week, same as the user's tick.
    """
    out = {}
    if not _practice_already_ran(team, date_str):
        out = auto_weekly_practice(team, date_str=date_str, league=league)
    crisis = detect_captaincy_crisis(team, league)
    res = None
    if crisis is not None:
        res = auto_resolve_crisis(team, crisis, date_str=date_str)
    hired = None
    if _room_head_coach(team) is None:
        cands = coaching_candidates(team)
        if cands:
            # Prefer the specialist; hot seats scare AI GMs too.
            cands.sort(key=lambda c: (c.get("hot_seat", 50),
                                      0 if c.get("archetype") == "specialist"
                                      else 1))
            hired = hire_coach(team, cands[0], date_str=date_str)
    return {"practice": out, "crisis": crisis, "resolution": res,
            "hired": hired}


def apply_practice_edge(sim: Any) -> None:
    """Sim hook: consume one-game practice edges (the bag-skate compete
    response). Called once at game start; the edge zeroes after use."""
    try:
        home = getattr(sim, "home_team", None)
        away = getattr(sim, "away_team", None)
        if home is None or away is None:
            return
        import impact_system as _imp
    except Exception:
        return

    def _take(team: Any) -> float:
        try:
            dr = ensure_dressing_room_fields(team)
            e = float(dr.get("practice_edge", 0) or 0)
            dr["practice_edge"] = 0.0
            return e
        except Exception:
            return 0.0

    eh, ea = _take(home), _take(away)
    try:
        if eh > ea:
            _imp.nudge_momentum(sim, home, strength=1.0)
        elif ea > eh:
            _imp.nudge_momentum(sim, away, strength=1.0)
    except Exception:
        pass
