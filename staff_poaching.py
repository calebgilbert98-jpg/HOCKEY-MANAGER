# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Offseason staff poaching (D5): the coaching carousel has a heartbeat.

Once per offseason, clubs may approach EXPIRING staff (contract_years
<= 1) on rival clubs. The signature case is a stud assistant/associate
coach in his final year with "climb" ambition getting a head-coach offer
from a club with a bench vacancy; a secondary lane lets a club poach a
high-reputation staffer laterally with a raise.

NHL contract law (asymmetric for now -- the user is excluded as poacher
and victim; symmetric AI<->user poaching with inbox permission decisions
is future work):
  * Expiring staff (<= 1 year): fair game -- no permission needed, the
    approach goes straight to the staffer.
  * Staff under contract (> 1 year): the poacher must request permission
    from the staffer's club. Permission is customarily GRANTED for a
    promotion (assistant -> head coach) and usually DENIED for a lateral
    move, unless the staffer is unhappy (low morale) or the club is
    indifferent. No draft-pick compensation (NHL abolished it in 2016).
  * AI clubs only, both sides. The user's staff cannot be approached and
    the user cannot initiate approaches (yet).

Bounds (so the carousel never churns cartoonishly):
  * each club makes at most one approach per offseason
  * each staffer is approached at most once per offseason
  * league-wide cap: 4 successful moves
"""

from __future__ import annotations

import random

# Signature lane: the "stud assistant in his final year who wants a
# head-coach job" case.
_CLIMB_LANES = {"Assistant Coach", "Associate Coach", "Power Play Coach",
                "Penalty Kill Coach", "Goalie Coach", "Skills Coach"}
# League-wide cap on successful poach moves per offseason.
_LEAGUE_MOVE_CAP = 4
# Reputation floor for the lateral (same-role, raise-driven) lane.
_LATERAL_REP_FLOOR = 75
# Reputation floor for the climb (head-coach offer) lane.
_CLIMB_REP_FLOOR = 60


def _team_name(team):
    try:
        return str(getattr(team, "team_name", "") or "?")
    except Exception:
        return "?"


def _staff_name(s):
    try:
        nm = (f"{getattr(s, 'first_name', '')} "
              f"{getattr(s, 'last_name', '')}").strip()
        return nm or "A staffer"
    except Exception:
        return "A staffer"


def _role_value(s):
    try:
        return str(getattr(getattr(s, "role", None), "value",
                           getattr(s, "role", None)) or "staff")
    except Exception:
        return "staff"


def _has_head_coach(team) -> bool:
    try:
        return any(_role_value(s) == "Head Coach"
                   for s in (getattr(team, "staff", None) or []))
    except Exception:
        return False


def _candidate_lane(s, offered_hc: bool):
    """Return 'climb' / 'lateral' / None for an expiring staffer."""
    try:
        from game_classes import is_staff_expiring
        if not is_staff_expiring(s):
            return None
        role = _role_value(s)
        rep = int(getattr(s, "reputation", 0) or 0)
        ambition = str(getattr(s, "ambition", "") or "")
        if (offered_hc and role in _CLIMB_LANES
                and rep >= _CLIMB_REP_FLOOR and ambition == "climb"):
            return "climb"
        if (not offered_hc and rep >= _LATERAL_REP_FLOOR
                and role != "Head Coach"):
            return "lateral"
    except Exception:
        pass
    return None


def _accepts(s, lane, poacher_rep: int) -> bool:
    """Bounded acceptance roll. Climb-ambition staff offered a head-coach
    job almost always take it; lateral moves need a real raise + a
    prestige edge to pry a staffer loose."""
    try:
        ambition = str(getattr(s, "ambition", "") or "")
        rep = int(getattr(s, "reputation", 50) or 50)
        if lane == "climb":
            p = 0.65 + (0.15 if ambition == "climb" else 0.0)
        else:  # lateral
            p = 0.15
            if ambition == "climb":
                p += 0.10  # ambitious staffers like upward moves
            if poacher_rep > rep + 10:
                p += 0.10
        return random.random() < min(0.9, p)
    except Exception:
        return False


def offseason_staff_poach(league, user_team=None) -> list:
    """Run one bounded offseason poach pass. Returns news lines for the
    inbox; never raises."""
    news = []
    try:
        from game_classes import StaffRole
    except Exception:
        return news
    try:
        teams = [t for t in (getattr(league, "teams", None) or [])
                 if t is not None and t is not user_team
                 and not getattr(t, "is_user_controlled", False)]
        random.shuffle(teams)
        moves = 0
        approached = set()
        for poacher in teams:
            if moves >= _LEAGUE_MOVE_CAP:
                break
            vacancy = not _has_head_coach(poacher)
            # Find one candidate on one rival club.
            # P15: the user is never a poach victim -- poachers already
            # exclude the user's club, and the victim pool matches
            # (one mechanic for everyone; the fuller fix -- a user
            # poach action -- is a feature decision for Chris/Caleb).
            rivals = [t for t in (getattr(league, "teams", None) or [])
                      if t is not None and t is not poacher
                      and t is not user_team
                      and not getattr(t, "is_user_controlled", False)]
            random.shuffle(rivals)
            done = False
            for rival in rivals:
                if done:
                    break
                staff = list(getattr(rival, "staff", None) or [])
                random.shuffle(staff)
                for s in staff:
                    if id(s) in approached:
                        continue
                    lane = _candidate_lane(s, vacancy)
                    if lane is None:
                        continue
                    approached.add(id(s))
                    try:
                        poacher_rep = int(
                            getattr(poacher, "reputation", 50) or 50)
                    except Exception:
                        poacher_rep = 50
                    if not _accepts(s, lane, poacher_rep):
                        done = True
                        break
                    # Move the staffer.
                    try:
                        rival.staff.remove(s)
                    except (ValueError, AttributeError):
                        pass
                    old_role = _role_value(s)
                    if lane == "climb":
                        s.role = StaffRole.HEAD_COACH
                    try:
                        s.assignment = "nhl"
                    except Exception:
                        pass
                    try:
                        s.contract_years = random.randint(2, 4)
                        s.salary = int(
                            getattr(s, "salary", 0) or 0) * 6 // 5
                    except Exception:
                        pass
                    try:
                        poacher.staff.append(s)
                    except Exception:
                        pass
                    moves += 1
                    if lane == "climb":
                        news.append(
                            f"{_team_name(poacher)} hired {_staff_name(s)} "
                            f"away from {_team_name(rival)} as head coach.")
                    else:
                        news.append(
                            f"{_team_name(poacher)} poached {_staff_name(s)} "
                            f"({old_role}) from {_team_name(rival)}.")
                    done = True
                    break
    except Exception:
        pass
    return news
