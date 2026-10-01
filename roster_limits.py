"""NHL roster limits, dressed minimums, rights lifecycle, emergency fillers.

True-NHL rules (Chris's rulings, 2026-10-01):
  - 23-man active roster max: day gate, user AND AI.
  - 50 standard-player-contract limit: day gate + AI prevention.
  - No NHL roster minimum: enforced at the dressed lineup instead --
    18 skaters + 2 goalies must be available (not injured, not
    season-ineligible). Outbound moves that would break the ability to
    dress a lineup are blocked.
  - Over-cap/under-minimum deadlock: emergency fillers -- league-minimum,
    scrub-overall (<=60) players summonable even over the cap, exempt from
    the 23-man count and cap-exempt at the day gate (the league exception),
    clearly marked, user+AI identical, auto-released when unneeded.
  - Rights: RFA rights retained indefinitely (never relinquished);
    qualified-but-unsigned RFA past Dec 1 is ineligible for the rest of
    that season; unsigned UFAs (expired contracts) leave the roster AND the
    cap at the July pass (the structural fix for Sim A's $31.36M phantom
    overage). Drafted-prospect rights use the existing
    _rollover_draft_rights windows.

All helpers are defensive (getattr-based) so old saves and odd states
fail soft, never crash. Additive: nothing here edits Caleb's systems, it
only reads them.
"""

import random

# --- Limits -----------------------------------------------------------------
ACTIVE_ROSTER_MAX = 23          # NHL 23-man active roster
SPC_LIMIT = 50                # NHL 50 standard player contracts
DRESSED_SKATERS_MIN = 18      # NHL dressed lineup: 18 skaters...
DRESSED_GOALIES_MIN = 2       # ...and 2 goalies
EMERGENCY_OVERALL_CAP = 60    # fillers are replacement-level, never more
DEC1_MONTH, DEC1_DAY = 12, 1  # RFA ineligibility date (real NHL: Dec 1)


# --- Predicates --------------------------------------------------------------
def is_emergency_filler(p) -> bool:
    return bool(getattr(p, "emergency_filler", False))


def _is_goalie(p) -> bool:
    try:
        pos = getattr(p, "primary_position", None)
        return str(getattr(pos, "value", pos)) == "G"
    except Exception:
        return False


def has_active_contract(p) -> bool:
    """True NHL: only players under contract count as roster/SPC members.
    Unsigned players (expired deals, rights retained) are attached to the
    club but occupy no roster or contract slot."""
    try:
        c = getattr(p, "contract", None)
        if c is None:
            return False
        return int(getattr(c, "years_remaining", 0) or 0) > 0
    except Exception:
        return False


def is_available(p) -> bool:
    """Can dress tonight: under contract, not injured, not Dec-1 ineligible."""
    try:
        if not has_active_contract(p):
            return False
        if bool(getattr(p, "is_injured", False)):
            return False
        if bool(getattr(p, "season_ineligible", False)):
            return False
        return True
    except Exception:
        return False


# --- Counts ------------------------------------------------------------------
def _all_players(team):
    try:
        return (list(getattr(team, "roster", None) or [])
                + list(getattr(team, "ahl_roster", None) or [])
                + list(getattr(team, "prospects", None) or []))
    except Exception:
        return []


def active_roster_count(team) -> int:
    """NHL 23-man count: active contracts on the NHL roster, emergency
    fillers exempt (NHL emergency-recall exemption)."""
    try:
        return sum(1 for p in (getattr(team, "roster", None) or [])
                   if has_active_contract(p) and not is_emergency_filler(p))
    except Exception:
        return 0


def spc_count(team) -> int:
    """Standard player contracts across the organization (fillers exempt --
    the league exception)."""
    try:
        return sum(1 for p in _all_players(team)
                   if has_active_contract(p) and not is_emergency_filler(p))
    except Exception:
        return 0


def dressable_skaters(team) -> int:
    try:
        return sum(1 for p in (getattr(team, "roster", None) or [])
                   if is_available(p) and not _is_goalie(p))
    except Exception:
        return 0


def dressable_goalies(team) -> int:
    try:
        return sum(1 for p in (getattr(team, "roster", None) or [])
                   if is_available(p) and _is_goalie(p))
    except Exception:
        return 0


def can_dress_lineup(team) -> bool:
    return (dressable_skaters(team) >= DRESSED_SKATERS_MIN
            and dressable_goalies(team) >= DRESSED_GOALIES_MIN)


def lineup_shortfall(team):
    """(skaters_needed, goalies_needed) to dress a legal lineup."""
    try:
        return (max(0, DRESSED_SKATERS_MIN - dressable_skaters(team)),
                max(0, DRESSED_GOALIES_MIN - dressable_goalies(team)))
    except Exception:
        return (0, 0)


def would_break_dress_minimum(team, outgoing) -> bool:
    """True if removing `outgoing` players leaves the club unable to dress
    18+2. Used to guard demotions, waiver placements, and trades."""
    try:
        out_ids = {id(p) for p in (outgoing or [])}
        sk = sum(1 for p in (getattr(team, "roster", None) or [])
                 if is_available(p) and not _is_goalie(p) and id(p) not in out_ids)
        go = sum(1 for p in (getattr(team, "roster", None) or [])
                 if is_available(p) and _is_goalie(p) and id(p) not in out_ids)
        return sk < DRESSED_SKATERS_MIN or go < DRESSED_GOALIES_MIN
    except Exception:
        return False


def emergency_filler_charge(team) -> int:
    """Total cap charge of emergency fillers -- excluded from the day-gate
    compliance check (the league exception: summonable even over the cap)."""
    try:
        total = 0
        for p in (getattr(team, "roster", None) or []):
            if not is_emergency_filler(p):
                continue
            c = getattr(p, "contract", None)
            total += int(getattr(c, "salary", 0) or 0)
        return max(0, total)
    except Exception:
        return 0


# --- Signing guard -----------------------------------------------------------
def can_sign_player(player):
    """(ok, reason). Dec-1 ineligible RFAs can't sign anywhere; emergency
    fillers can't be extended or re-signed (they're summoned, not signed)."""
    try:
        if bool(getattr(player, "season_ineligible", False)):
            return (False, "He's ineligible to sign -- an unsigned RFA past "
                           "the December 1 deadline can't play this season "
                           "(rights retained).")
        if is_emergency_filler(player):
            return (False, "Emergency fill-ins can't be signed to standard "
                           "deals -- they're league-exception recalls, not "
                           "roster players.")
        return (True, "")
    except Exception:
        return (True, "")


# --- Day gates (user) ----------------------------------------------------------
def roster_limit_blockers(app):
    """Blocker dicts in the get_continue_state shape. 23-man max, 50 SPC,
    and the dressed-lineup minimum (with a summon-fillers action)."""
    blockers = []
    try:
        team = getattr(app, "user_team", None)
        if team is None:
            return blockers
        n = active_roster_count(team)
        if n > ACTIVE_ROSTER_MAX:
            blockers.append({
                'id': 'roster_limit_23',
                'title': 'Active roster over the 23-man limit',
                'detail': (f"{n} players on the active roster -- the NHL "
                           f"limit is {ACTIVE_ROSTER_MAX} (emergency fill-ins "
                           f"don't count). Demote or waive players before "
                           f"advancing."),
                'action': ('Open Roster', getattr(app, 'open_roster_window',
                                                  lambda: None)),
            })
        s = spc_count(team)
        if s > SPC_LIMIT:
            blockers.append({
                'id': 'roster_limit_50',
                'title': 'Over the 50-contract limit',
                'detail': (f"{s} standard player contracts -- the NHL limit "
                           f"is {SPC_LIMIT}. Move contracts out before "
                           f"advancing."),
                'action': ('Open Roster', getattr(app, 'open_roster_window',
                                                  lambda: None)),
            })
        if not can_dress_lineup(team):
            sk, go = lineup_shortfall(team)
            need = []
            if sk:
                need.append(f"{sk} skater{'s' if sk != 1 else ''}")
            if go:
                need.append(f"{go} goalie{'s' if go != 1 else ''}")
            blockers.append({
                'id': 'dress_minimum',
                'title': "Can't dress a legal lineup",
                'detail': (f"Only {dressable_skaters(team)} skaters and "
                           f"{dressable_goalies(team)} goalies available "
                           f"(18+2 needed). You can summon emergency "
                           f"fill-ins -- league-minimum, replacement-level, "
                           f"available even over the cap."),
                'action': ('Summon emergency fill-ins',
                           lambda: summon_emergency_fillers(team)),
            })
    except Exception:
        pass
    return blockers


# --- Emergency fillers ---------------------------------------------------------
# Chris's deadlock ruling: when a club can't dress 18+2 and can't afford
# (or fit under the cap for) a real signing, the league provides
# replacement-level emergency fill-ins -- the NHL emergency-recall idea.
# League-minimum salary, scrub overall (<=60 by construction), F/F
# potential, mid-career age (no prospect shine), clearly flagged. They are
# summonable even over the cap and exempt from the 23-man/SPC counts and
# the day-gate cap check (the league exception). They cannot be traded,
# extended, waived, or developed, and they auto-release the moment the
# club can dress a lineup without them (plus a July sweep).

# Filler attribute band. overall_rating weights sum to 0.98-1.20 by
# position (Caleb's tuning -- protected ground, not touched), so 44-49
# lands every filler at overall <= 58: replacement-level, never a
# backdoor for cheap talent. Verified empirically in qa_roster_limits.
_FILLER_ATTR_MIN, _FILLER_ATTR_MAX = 44, 49

# Every attribute the overall formula reads (game_classes.Player.
# overall_rating). Clamping ALL of them pins the filler at ~55-60 with no
# backdoor for cheap talent via an unset high default.
_FILLER_ATTRS = (
    "skating", "shooting", "shooting_accuracy", "shooting_power", "passing",
    "passing_accuracy", "passing_creativity", "deking", "stickhandling",
    "vision", "hockey_iq", "offensive_awareness", "defensive_awareness",
    "checking", "faceoffs", "faceoff_wins", "strength", "balance",
    "aggressiveness", "bodycheck", "pokecheck", "shot_blocking",
    "stick_side", "screen_shots", "backhand", "wristshot", "slapshot",
    "one_timer", "loose_puck", "off_the_puck", "composure", "confidence",
    "focus", "determination", "endurance", "anticipation", "pressure_player",
    # goalie
    "goaltending", "reflexes", "positioning", "rebound_control",
    "puck_handling", "glove_hand", "breakaway_skill",
)


def _filler_name(rng):
    try:
        import database_generator as _dg
        nat = rng.choice(["Canada", "USA", "Sweden", "Finland", "Russia",
                          "Czech", "Other"])
        first = rng.choice(_dg.EXTENDED_FIRST_NAMES.get(nat) or ["Alex"])
        last = rng.choice(_dg.EXTENDED_LAST_NAMES.get(nat)
                          or _dg.EXTENDED_LAST_NAMES.get("Canada")
                          or ["Smith"])
        return f"{first} {last}", nat
    except Exception:
        return "Alex Smith", "Canada"


def make_emergency_filler(position, rng=None):
    """Build a replacement-level scrub. Overall lands ~55-60 by
    construction; never a backdoor for cheap talent."""
    from game_classes import Player, PlayerPosition, Contract
    rng = rng or random.Random()
    pos = position
    if isinstance(position, str):
        try:
            pos = PlayerPosition(position)
        except Exception:
            pos = PlayerPosition.CENTER
    name, nat = _filler_name(rng)
    try:
        _first, _last = name.split(" ", 1)
    except Exception:
        _first, _last = "Alex", "Smith"
    p = Player(_first, _last, age=rng.randint(26, 32),
               primary_position=pos)
    try:
        p.nationality = nat
    except Exception:
        pass
    for attr in _FILLER_ATTRS:
        try:
            setattr(p, attr, rng.randint(_FILLER_ATTR_MIN, _FILLER_ATTR_MAX))
        except Exception:
            pass
    try:
        p.potential_grade = "F"
        p.true_potential_grade = "F"
        p.emergency_filler = True
        p.injury_proneness = 5
    except Exception:
        pass
    try:
        from rfa_system import LEAGUE_MIN_SALARY
    except Exception:
        LEAGUE_MIN_SALARY = 775_000
    try:
        p.contract = Contract(salary=int(LEAGUE_MIN_SALARY),
                              years_remaining=1)
    except Exception:
        pass
    return p


def summon_emergency_fillers(team, rng=None):
    """Summon exactly the shortfall -- no stockpiling. Returns the list
    summoned. Safe to call when there's no shortfall (no-op)."""
    summoned = []
    try:
        rng = rng or random.Random()
        sk_need, go_need = lineup_shortfall(team)
        if sk_need <= 0 and go_need <= 0:
            return summoned
        roster = getattr(team, "roster", None)
        if roster is None:
            return summoned
        from game_classes import PlayerPosition
        skate_positions = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
                           PlayerPosition.RIGHT_WING, PlayerPosition.LEFT_DEFENSE,
                           PlayerPosition.RIGHT_DEFENSE]
        for i in range(sk_need):
            filler = make_emergency_filler(skate_positions[i % len(skate_positions)], rng)
            roster.append(filler)
            summoned.append(filler)
        for _ in range(go_need):
            filler = make_emergency_filler(PlayerPosition.GOALIE, rng)
            roster.append(filler)
            summoned.append(filler)
    except Exception:
        pass
    return summoned


def release_unneeded_fillers(team):
    """Release fillers the club no longer needs to dress a lineup.
    Returns the count released."""
    released = 0
    try:
        roster = getattr(team, "roster", None)
        if roster is None:
            return 0
        for p in list(roster):
            if not is_emergency_filler(p):
                continue
            roster.remove(p)
            if not can_dress_lineup(team):
                roster.append(p)  # still needed -- put him back
            else:
                released += 1
    except Exception:
        pass
    return released


def release_all_fillers(team):
    """July sweep: no fillers carry over the summer."""
    try:
        roster = getattr(team, "roster", None)
        if roster is None:
            return 0
        n = 0
        for p in list(roster):
            if is_emergency_filler(p):
                try:
                    roster.remove(p)
                    n += 1
                except Exception:
                    pass
        return n
    except Exception:
        return 0


# --- Dec 1 ineligibility (true NHL) ---------------------------------------------
def _current_date(app):
    for attr in ("current_date", "game_date"):
        try:
            d = getattr(app, attr, None)
            if d is not None and hasattr(d, "month"):
                return d
        except Exception:
            pass
    gm = getattr(app, "game_manager", None)
    for attr in ("current_date", "game_date"):
        try:
            d = getattr(gm, attr, None) if gm is not None else None
            if d is not None and hasattr(d, "month"):
                return d
        except Exception:
            pass
    return None


def _is_qualified_unsigned_rfa(player):
    """Qualified (QO extended) but never signed: rights retained, no deal."""
    try:
        if not bool(getattr(player, "qo_extended", False)):
            return False
        c = getattr(player, "contract", None)
        return int(getattr(c, "years_remaining", 0) or 0) <= 0
    except Exception:
        return False


def apply_dec1_ineligibility(league, current_date):
    """True NHL: a qualified-but-unsigned RFA past Dec 1 can't play the rest
    of that season. Rights are retained -- he just sits. Returns count."""
    n = 0
    try:
        if current_date is None:
            return 0
        # Stamp once the calendar reaches Dec 1 (idempotent: skips players
        # already stamped, so running daily is safe).
        if not (int(getattr(current_date, "month", 0)) == DEC1_MONTH
                and int(getattr(current_date, "day", 0)) >= DEC1_DAY):
            return 0
        for team in (getattr(league, "teams", None) or []):
            for p in (getattr(team, "roster", None) or []):
                try:
                    if (not bool(getattr(p, "season_ineligible", False))
                            and _is_qualified_unsigned_rfa(p)):
                        p.season_ineligible = True
                        n += 1
                except Exception:
                    continue
    except Exception:
        pass
    return n


# --- July: unsigned UFAs leave (the structural fix) ------------------------------
def july_release_unsigned_ufas(league, app=None):
    """True NHL: on July 1, unsigned UFAs (expired contracts) come off the
    roster AND off the cap -- for the user team too. This is the structural
    fix for Sim A's $31.36M phantom overage (expired deals piling up for
    five seasons because nothing ever moved them). RFAs are untouched:
    rights retained, handled by the QO flow. Returns {team_name: [names]}."""
    released = {}
    try:
        import rfa_system as _rfa
    except Exception:
        return released
    try:
        user_team = None
        for team in (getattr(league, "teams", None) or []):
            try:
                from rfa_system import _is_user_team as _isut
                if _isut(team):
                    user_team = team
                    break
            except Exception:
                pass
        if user_team is None and app is not None:
            user_team = getattr(app, "user_team", None)
        for team in list(getattr(league, "teams", None) or []):
            # AI clubs already release non-core UFAs in process_rfa_offseason
            # §4; run the sweep for every club so stragglers (and the user)
            # are covered identically.
            walked = []
            for p in list(getattr(team, "roster", None) or []):
                try:
                    if not _rfa.contract_expired(p):
                        continue
                    if _rfa.is_rfa(p):
                        continue  # rights retained -- QO flow owns him
                    if is_emergency_filler(p):
                        continue  # July sweep handles fillers separately
                    name = getattr(p, "full_name",
                                   getattr(p, "name", "Unknown"))
                    _rfa._move_to_free_agents(league, p)
                    walked.append(name)
                except Exception:
                    continue
            if walked:
                try:
                    released[getattr(team, "team_name", "?")] = walked
                except Exception:
                    pass
        # Tell the user what happened (FYI, Eastside-style -- not a blocker).
        if app is not None and user_team is not None:
            try:
                tname = getattr(user_team, "team_name", "")
                names = released.get(tname, [])
                if names:
                    _notify_user_ufa_release(app, names)
            except Exception:
                pass
    except Exception:
        pass
    return released


def _notify_user_ufa_release(app, names):
    try:
        from game_classes import EmailMessage
    except Exception:
        return
    try:
        shown = ", ".join(names[:8])
        if len(names) > 8:
            shown += f", +{len(names) - 8} more"
        msg = EmailMessage(
            sender="League Office",
            sender_type="System",
            subject=f"July 1: {len(names)} unsigned player(s) hit free agency",
            content=("Your unsigned unrestricted free agents are now free "
                     "agents -- off your roster and off your cap, as of "
                     "July 1:\n" + shown + "\n\nYou can re-sign any of them "
                     "from the free-agent market."),
            category="Contracts",
            is_important=False,
            requires_response=False,
            action_type="ufa_release_notice",
        )
        inbox = getattr(app, "inbox_messages", None)
        if isinstance(inbox, list):
            inbox.append(msg)
    except Exception:
        pass


# --- Daily tick ------------------------------------------------------------------
def daily_roster_tick(app):
    """Called from _process_daily_maintenance: Dec-1 stamping + filler
    auto-release. Never raises."""
    try:
        league = getattr(app, "league", None)
        if league is None:
            gm = getattr(app, "game_manager", None)
            league = getattr(gm, "league", None) if gm is not None else None
        if league is None:
            return
        apply_dec1_ineligibility(league, _current_date(app))
        for team in (getattr(league, "teams", None) or []):
            try:
                release_unneeded_fillers(team)
            except Exception:
                continue
    except Exception:
        pass


# --- AI compliance ---------------------------------------------------------------
def ai_roster_compliance(team, league=None, rng=None):
    """Daily AI backstop, same rules as the user. Demote (two-ways /
    waiver-exempt first) down to 23; summon fillers when short; release
    unneeded fillers. Never raises; returns a dict of what it did."""
    done = {"demoted": 0, "summoned": 0, "released": 0}
    try:
        rng = rng or random.Random()
        roster = getattr(team, "roster", None)
        ahl = getattr(team, "ahl_roster", None)
        if roster is None or ahl is None:
            return done
        # Over 23: paper down the cheapest demotable players first.
        while active_roster_count(team) > ACTIVE_ROSTER_MAX:
            cands = [p for p in roster
                     if has_active_contract(p)
                     and not is_emergency_filler(p)
                     and not bool(getattr(p, "no_movement_clause", False))
                     and not bool(getattr(getattr(p, "contract", None),
                                          "no_movement_clause", False))]
            if not cands:
                break  # NMC-locked -- leave it; the gate only hits users
            def _key(p):
                # Two-ways first (fully cap-exempt in the minors), then the
                # cheapest one-way deals -- the real paper-down order.
                try:
                    c = getattr(p, "contract", None)
                    two_way = 1 if bool(getattr(c, "two_way", False)) else 0
                    return (-two_way, int(getattr(c, "salary", 0) or 0))
                except Exception:
                    return (0, 0)
            cands.sort(key=_key)
            pick = cands[0]
            try:
                roster.remove(pick)
                ahl.append(pick)
                done["demoted"] += 1
            except Exception:
                break
        done["released"] = release_unneeded_fillers(team)
        if not can_dress_lineup(team):
            done["summoned"] = len(summon_emergency_fillers(team, rng))
    except Exception:
        pass
    return done


def ai_can_sign_spc(team) -> bool:
    """Prevention for AI auto-sign paths: don't take a 51st contract."""
    try:
        return spc_count(team) < SPC_LIMIT
    except Exception:
        return True
