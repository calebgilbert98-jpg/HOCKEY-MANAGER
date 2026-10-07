"""NHL roster limits, dressed minimums, rights lifecycle, emergency fillers.

True-NHL rules (Chris's rulings, 2026-10-01):
  - 23-man active roster max: day gate, user AND AI.
  - 50 standard-player-contract limit: day gate + AI prevention.
  - No NHL roster minimum: enforced at the dressed lineup instead --
    18 skaters + 2 goalies must be available (not injured, not
    season-ineligible). Outbound moves that would break the ability to
    dress a lineup are blocked.
  - Over-cap/under-minimum deadlock: emergency fillers -- league-minimum,
    replacement-level (<=65 by construction) players auto-summoned even
    over the cap (the league exception), exempt from the 23-man count and
    cap-exempt at the day gate, clearly marked, user+AI identical,
    auto-released when unneeded. The dressed-lineup day gate is
    Eastside-style auto: shortfalls summon fill-ins with an FYI note,
    never a hard blocker (the 23-man and 50-contract gates stay hard).
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
EMERGENCY_OVERALL_CAP = 65    # fillers are replacement-level+, never more
                             # (Chris's Part 3 spec: decent, not scrub-useless)
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
    """Can dress tonight: under contract, not injured, not Dec-1 ineligible,
    not stashed on IR/LTIR (ir_system.py -- a healed player blocked from
    activation by the 7-day minimum or LTIR cap room stays on IR and
    cannot dress)."""
    try:
        if not has_active_contract(p):
            return False
        if bool(getattr(p, "is_injured", False)):
            return False
        if bool(getattr(p, "season_ineligible", False)):
            return False
        if str(getattr(p, "ir_status", "None") or "None") in ("IR", "LTIR"):
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
    fillers exempt (NHL emergency-recall exemption). Players currently on
    the waiver wire are excluded -- they're in transit off the roster and
    the 2-day clock ticks in daily maintenance; counting them softlocked
    the day advance (blocker armed, clock never ticked). IR/LTIR players
    are excluded -- they don't count against the 23-man limit (real NHL;
    ir_system.py)."""
    try:
        return sum(1 for p in (getattr(team, "roster", None) or [])
                   if has_active_contract(p) and not is_emergency_filler(p)
                   and not getattr(p, "on_waivers", False)
                   and str(getattr(p, "ir_status", "None") or "None")
                   not in ("IR", "LTIR"))
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


def would_break_dress_minimum(team, outgoing, incoming=None) -> bool:
    """True if removing `outgoing` players leaves the club unable to dress
    18+2. `incoming` (trade acquisitions) counts toward the post-deal
    lineup, so a 1-for-1 swap at exactly 18+2 stays legal (UI-BUG-04).
    Used to guard demotions, waiver placements, and trades."""
    try:
        out_ids = {id(p) for p in (outgoing or [])}
        sk = sum(1 for p in (getattr(team, "roster", None) or [])
                 if is_available(p) and not _is_goalie(p) and id(p) not in out_ids)
        go = sum(1 for p in (getattr(team, "roster", None) or [])
                 if is_available(p) and _is_goalie(p) and id(p) not in out_ids)
        # Incoming trade acquisitions dress for their new club (UI-BUG-04).
        for p in (incoming or []):
            if not is_available(p):
                continue
            if _is_goalie(p):
                go += 1
            else:
                sk += 1
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
def _warn_spc_over_limit(app, team, s):
    """Soft FYI when over the 50-contract NHL limit (Chris's call 2026-10-02:
    the only HARD pre-game gates are cap compliance + the 23-man active
    roster; the 50 SPC total is advisory). News_log + inbox, once per day.
    Never raises, never blocks."""
    try:
        date = _current_date(app)
        if getattr(team, "_spc_warn_date", None) == date:
            return
        team._spc_warn_date = date
        story = (f"Roster note: {s} standard player contracts on the books "
                 f"-- over the NHL's 50-contract limit. Not a blocker, but "
                 f"the league office frowns on it: move contracts out when "
                 f"you get a chance.")
        try:
            log = getattr(app, "news_log", None)
            if isinstance(log, list):
                log.append({"date": date, "story": f"📋 {story}"})
        except Exception:
            pass
        try:
            from game_classes import EmailMessage
            msg = EmailMessage(
                sender="League Office",
                sender_type="System",
                subject="Over the 50-contract limit",
                content=(story + "\n\nThis won't stop you playing -- only "
                         "the salary cap and the 23-man active roster are "
                         "hard gates before a game. But a big contract "
                         "ledger ties up flexibility."),
                category="Roster",
                is_important=False,
                requires_response=False,
                action_type="spc_over_limit_notice",
            )
            inbox = getattr(app, "inbox_messages", None)
            if isinstance(inbox, list):
                inbox.append(msg)
        except Exception:
            pass
    except Exception:
        pass


def roster_limit_blockers(app):
    """Blocker dicts in the get_continue_state shape. Hard pre-game gates
    (Chris's call 2026-10-02): the 23-man active max and the dressed-lineup
    minimum (with a summon-fillers action). The 50-contract total is
    advisory only -- a daily FYI, never a blocker."""
    blockers = []
    try:
        team = getattr(app, "user_team", None)
        if team is None:
            return blockers
        n = active_roster_count(team)
        if n > ACTIVE_ROSTER_MAX:
            # Eastside-style quick fixes: IR-eligible injured players can
            # be stashed in one click; the rest need manual demotion.
            _ir_cands = ir_quick_fix_candidates(team)
            _ir_bit = ""
            _ir_action = None
            if _ir_cands:
                _names = ", ".join(
                    getattr(p, "full_name", "?") for p, _k in _ir_cands[:3])
                _ir_bit = (f" {len(_ir_cands)} injured player(s) can go "
                           f"straight to IR/LTIR ({_names}"
                           f"{'...' if len(_ir_cands) > 3 else ''}).")
                def _do_ir_fix(_t=team, _app=app):
                    try:
                        _n, _who = apply_ir_quick_fix(
                            _t, getattr(_app, "current_date", None))
                        if _n:
                            _app.add_news(
                                f"🏥 Placed {', '.join(_who)} on "
                                f"IR/LTIR ({n - _n} active).")
                    except Exception:
                        pass
                _ir_action = ('IR injured players', _do_ir_fix)
            def _auto_demote(_t=team, _app=app, _n=n):
                """Auto-resolve: demote waiver-safe players to get to 23."""
                try:
                    from auto_resolve import auto_fix_roster_limit
                    over_by = _n - ACTIVE_ROSTER_MAX
                    demoted, err = auto_fix_roster_limit(_t, over_by)
                    if err:
                        _app.add_news(f"Auto-demote failed: {err}")
                        return
                    for p in demoted:
                        try:
                            # Move to minors: remove from NHL roster, add to
                            # AHL affiliate. The 23-man count reads
                            # team.roster directly, so removal is what clears
                            # the blocker. Add to BOTH ahl_roster (the
                            # recall pool read by recall_candidates) and
                            # farm_team.roster (O-2: demoted players were
                            # invisible to future recalls).
                            if p in _t.roster:
                                _t.roster.remove(p)
                            _ahl = getattr(_t, 'ahl_roster', None)
                            if _ahl is not None and p not in _ahl:
                                _ahl.append(p)
                            _ft = getattr(_t, 'farm_team', None)
                            if _ft is not None:
                                _fr = getattr(_ft, 'roster', None)
                                if _fr is not None and p not in _fr:
                                    _fr.append(p)
                        except Exception:
                            pass
                    _names = ", ".join(
                        getattr(p, 'full_name', '?') for p in demoted)
                    _app.add_news(
                        f"Auto-demoted {len(demoted)} player(s) to AHL "
                        f"({_names}). All were waiver-exempt or low-risk.")
                except Exception as e:
                    try:
                        _app.add_news(f"Auto-demote failed: {e}")
                    except Exception:
                        pass
            blockers.append({
                'id': 'roster_limit_23',
                'title': 'Active roster over the 23-man limit',
                'detail': (f"{n} players on the active roster -- the NHL "
                           f"limit is {ACTIVE_ROSTER_MAX} (emergency fill-ins "
                           f"don't count).{_ir_bit} Demote or waive players "
                           f"before advancing."),
                'action': ('Open Roster', getattr(app, 'open_roster_window',
                                                  lambda: None)),
                'secondary_action': _ir_action,
                'auto_action': ('Auto-demote (waiver-safe)', _auto_demote),
            })
        s = spc_count(team)
        if s > SPC_LIMIT:
            # Advisory only (Chris's call 2026-10-02): the 50-contract total
            # is not a hard gate -- only cap + 23-man block games. Warn once
            # per day; never block.
            _warn_spc_over_limit(app, team, s)
        _recall_blocker_added = False
        if not can_dress_lineup(team):
            sk_need, go_need = lineup_shortfall(team)
            cands = recall_candidates(team, sk_need, go_need)
            if cands:
                # Real players are available on the farm -- don't mint
                # fakes; route the user to the recall picker instead.
                _recall_blocker_added = True
                _need_bits = []
                if sk_need:
                    _need_bits.append(
                        f"{sk_need} skater{'s' if sk_need != 1 else ''}")
                if go_need:
                    _need_bits.append(
                        f"{go_need} goalie{'s' if go_need != 1 else ''}")
                _top = ", ".join(
                    f"{getattr(p, 'first_name', '?')} "
                    f"{getattr(p, 'last_name', '')} "
                    f"({_overall(p)})"
                    for p in cands[:3])
                def _auto_recall(_cands=cands, _t=team, _app=app,
                                _sk=sk_need, _go=go_need):
                    """Auto-resolve: recall best available from AHL."""
                    try:
                        recalled = []
                        # Recall highest-overall candidates first
                        for p in sorted(_cands,
                                        key=lambda x: _overall(x),
                                        reverse=True):
                            if len(recalled) >= _sk + _go:
                                break
                            try:
                                # Move from AHL to NHL roster. The dressed-
                                # lineup check reads team.roster, so the
                                # player must actually be on it.
                                # Candidates come from team.ahl_roster
                                # (see recall_candidates) -- remove there
                                # FIRST, then farm_team.roster if present
                                # (O-2: stale double-listing caused the
                                # dress_minimum <-> roster_limit_23
                                # ping-pong).
                                _ahl = getattr(_t, 'ahl_roster', None)
                                if _ahl is not None and p in _ahl:
                                    _ahl.remove(p)
                                _ft = getattr(_t, 'farm_team', None)
                                if _ft is not None:
                                    _fr = getattr(_ft, 'roster', None)
                                    if _fr is not None and p in _fr:
                                        _fr.remove(p)
                                if p not in _t.roster:
                                    _t.roster.append(p)
                                recalled.append(p)
                            except Exception:
                                pass
                        _names = ", ".join(
                            f"{getattr(p, 'first_name', '?')} "
                            f"{getattr(p, 'last_name', '')}"
                            for p in recalled)
                        _app.add_news(
                            f"Auto-recalled {len(recalled)} player(s) from "
                            f"AHL ({_names}) to dress a legal lineup.")
                    except Exception as e:
                        try:
                            _app.add_news(f"Auto-recall failed: {e}")
                        except Exception:
                            pass
                blockers.append({
                    'id': 'dress_minimum',
                    'title': "Can't dress a legal lineup",
                    'detail': (
                        f"Only {dressable_skaters(team)} skaters and "
                        f"{dressable_goalies(team)} goalies available "
                        f"({', '.join(_need_bits)} short). Your AHL club "
                        f"has recallable players -- {_top}. Recall them "
                        f"instead of icing emergency fill-ins."),
                    'action': ('Review AHL recalls',
                               lambda: app.open_recall_picker()),
                    'auto_action': ('Auto-recall best available',
                                    _auto_recall),
                })
            else:
                # Eastside-style auto: summon the fill-ins and keep the day
                # moving (FYI note, never a hard blocker). The old blocker
                # survives only as a last resort if summoning somehow failed.
                ensure_dressed_lineup_auto(
                    team,
                    notify=lambda summoned: _notify_filler_summon(app, team,
                                                                  summoned),
                )
        if not can_dress_lineup(team) and not _recall_blocker_added:
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
                           f"(18+2 needed) -- even emergency fill-ins "
                           f"couldn't be summoned ({', '.join(need)} still "
                           f"short). Sign players before advancing."),
            })
    except Exception:
        pass
    return blockers


def ir_quick_fix_candidates(team):
    """Players eligible for IR right now (Eastside-style quick fix).

    Returns [(player, 'IR'|'LTIR')] for injured roster players who can
    be stashed to free 23-man spots. The game-day blocker offers this
    as a one-click action.
    """
    out = []
    try:
        import ir_system as _irs
        for p in (getattr(team, "roster", None) or []):
            try:
                if _irs.is_on_any_ir(p):
                    continue
                _ok_ltir, _ = _irs.eligible_for_ltir(p)
                if _ok_ltir:
                    out.append((p, "LTIR"))
                    continue
                _ok_ir, _ = _irs.eligible_for_ir(p)
                if _ok_ir:
                    out.append((p, "IR"))
            except Exception:
                continue
    except Exception:
        pass
    return out


def apply_ir_quick_fix(team, current_date=None):
    """Place all IR-eligible injured players on IR/LTIR (one click).

    Returns (placed_count, [names]). Eastside-style: clear the injured
    off the active roster so the club is game-day compliant.
    """
    placed = []
    try:
        import ir_system as _irs
        for p, kind in ir_quick_fix_candidates(team):
            try:
                if kind == "LTIR":
                    ok, _ = _irs.place_on_ltir(team, p, current_date)
                else:
                    ok, _ = _irs.place_on_ir(team, p, current_date)
                if ok:
                    placed.append(getattr(p, "full_name", "Player"))
            except Exception:
                continue
    except Exception:
        pass
    return len(placed), placed


# --- Emergency fillers ---------------------------------------------------------
# Chris's deadlock ruling: when a club can't dress 18+2 and can't afford
# (or fit under the cap for) a real signing, the league provides
# replacement-level emergency fill-ins -- the NHL emergency-recall idea.
# League-minimum salary, replacement-level+ overall (<=65 by
# construction), F/F potential, mid-career age (no prospect shine),
# clearly flagged, always assigned to the club (team back-pointer).
# They are summonable even over the cap and exempt from the 23-man/SPC counts and
# the day-gate cap check (the league exception). They cannot be traded,
# extended, waived, or developed, and they auto-release the moment the
# club can dress a lineup without them (plus a July sweep).

# Filler attribute band (Chris's Part 3 spec: replacement-level+, not
# scrub-useless, and not exploitable). overall_rating weights sum to
# 0.98-1.20 by position (Caleb's tuning -- protected ground, not
# touched), so 48-53 lands every filler at overall <= 63: decent enough
# to keep a short-handed club competitive, never a backdoor for cheap
# talent. Verified empirically in qa_roster_limits.
_FILLER_ATTR_MIN, _FILLER_ATTR_MAX = 48, 53

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


def _assign_filler_to_team(filler, team):
    """Attach a filler to a team so he always has a club back-pointer:
    prefer Team.add_player (sets team_name + opens a stint), fall back to
    a direct roster append + explicit team_name, then belt-and-braces
    verify team_name is set. Never raises. This is the fix for the
    None-team root cause behind the BUG-003/004/005 drop saga."""
    try:
        if filler is None or team is None:
            return
        roster = getattr(team, "roster", None)
        already = False
        try:
            already = roster is not None and filler in roster
        except Exception:
            pass
        if not already:
            try:
                team.add_player(filler)
            except Exception:
                try:
                    roster.append(filler)
                except Exception:
                    return
        try:
            if not getattr(filler, "team_name", None):
                filler.team_name = getattr(team, "team_name", None)
        except Exception:
            pass
    except Exception:
        pass


def make_emergency_filler(position, rng=None, team=None):
    """Build a replacement-level filler. Overall lands ~58-65 by
    construction; never a backdoor for cheap talent. When `team` is
    given, the filler is assigned to it (team back-pointer guaranteed)."""
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
    if team is not None:
        _assign_filler_to_team(p, team)
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
            filler = make_emergency_filler(skate_positions[i % len(skate_positions)], rng, team)
            _assign_filler_to_team(filler, team)
            summoned.append(filler)
        for _ in range(go_need):
            filler = make_emergency_filler(PlayerPosition.GOALIE, rng, team)
            _assign_filler_to_team(filler, team)
            summoned.append(filler)
    except Exception:
        pass
    return summoned


# --- AHL recalls ---------------------------------------------------------------
# Real-NHL behavior: when a club is short-handed (usually injuries), it
# recalls players from its own farm team BEFORE the league mints emergency
# exception players. Previously the compliance paths went straight to
# fillers, so every routine injury produced a fake player instead of a real
# recall -- and AHL prospects never got their NHL auditions. Recalls are
# real transactions: the player moves to the NHL roster, his salary counts
# against the cap, and the dressing-room/audition machinery fires exactly
# as it does for a user-initiated call-up (user/AI symmetric).


def _recall_block_reason(p):
    """None if this AHL player can be recalled, else a human reason."""
    try:
        import ahl_system as _ahl
        return _ahl.ahl_recall_block_reason(p)
    except Exception:
        return None


def _player_nhl_salary(p) -> int:
    try:
        c = getattr(p, "contract", None)
        return int(getattr(c, "salary", 0) or 0)
    except Exception:
        return 0


def _recall_fits_cap(team, player) -> bool:
    """Best-effort: would recalling this player keep the club cap-compliant?
    Honors LTIR relief (ir_system.effective_cap_ceiling). Fillers are
    cap-exempt, so a recall that breaks the cap is skipped and the
    shortfall falls through to fillers. If the cap infrastructure is
    unavailable, allow the recall -- the day-gate cap check is the backstop."""
    try:
        from salary_cap_system import compliance_charge
        current = int(compliance_charge(team) or 0)
        cap = 0
        try:
            import ir_system as _irs
            cap = int(_irs.effective_cap_ceiling(team) or 0)
        except Exception:
            pass
        if cap <= 0:
            try:
                from salary_cap_system import cap_breakdown
                bd = cap_breakdown(team)
                cap = int((bd or {}).get("cap", 0) or 0)
            except Exception:
                pass
        if cap <= 0:
            return True
        return current + _player_nhl_salary(player) <= cap
    except Exception:
        return True


def _overall(p) -> int:
    try:
        return int(p.overall_rating() or 0)
    except Exception:
        return 0


def recall_candidates(team, need_skaters=0, need_goalies=0):
    """Best-first list of AHL players legally recallable right now to cover
    a dressed-lineup shortfall. Sorted: goalies first when goalies are
    needed, then by overall (best available), preferring two-way deals
    (no waiver exposure on re-demotion -- the real NHL recall order).
    Never raises; returns [] when no one is eligible."""
    try:
        ahl = list(getattr(team, "ahl_roster", None) or [])
    except Exception:
        return []
    cands = []
    for p in ahl:
        try:
            if not is_available(p):
                continue
            if is_emergency_filler(p):
                continue
            if _recall_block_reason(p):
                continue
            cands.append(p)
        except Exception:
            continue
    def _two_way(p):
        try:
            return 1 if bool(getattr(getattr(p, "contract", None),
                                     "two_way", False)) else 0
        except Exception:
            return 0
    def _sort_key(p):
        goalie_first = 0 if (_is_goalie(p) and need_goalies > 0) else 1
        skater_first = 0 if (not _is_goalie(p) and need_skaters > 0) else 1
        # Best available for the need first; two-way deals break ties
        # (no waiver exposure on re-demotion -- the real NHL recall order).
        return (goalie_first, skater_first, -_overall(p), -_two_way(p))
    try:
        cands.sort(key=_sort_key)
    except Exception:
        pass
    return cands


def _stamp_recall_effects(team, player):
    """Ecosystem effects of a recall, mirroring app.call_up_to_nhl:
    audition baseline + dressing-room arrival cascade. Guarded; never raises."""
    try:
        player.nhl_audition = {
            "goals": getattr(player, "goals", 0) or 0,
            "assists": getattr(player, "assists", 0) or 0,
            "games_played": getattr(player, "games_played", 0) or 0,
        }
    except Exception:
        try:
            player.nhl_audition = None
        except Exception:
            pass
    try:
        import dressing_room as _dr
        _dr.cascade_on_arrival(team, player, how="callup", date_str="")
    except Exception:
        pass


def recall_best_available(team, need_skaters=0, need_goalies=0, rng=None):
    """Recall real AHL players to cover a dressed-lineup shortfall.
    Fills goalies first, then skaters, skipping anyone who fails the cap
    check (fillers are the cap-exempt fallback). Returns the recalled
    players. Never raises."""
    recalled = []
    try:
        if need_skaters <= 0 and need_goalies <= 0:
            return recalled
        roster = getattr(team, "roster", None)
        ahl = getattr(team, "ahl_roster", None)
        if roster is None or ahl is None:
            return recalled
        go_need, sk_need = int(need_goalies or 0), int(need_skaters or 0)
        for p in recall_candidates(team, sk_need, go_need):
            if go_need <= 0 and sk_need <= 0:
                break
            try:
                want_goalie = _is_goalie(p)
                if want_goalie and go_need <= 0:
                    continue
                if not want_goalie and sk_need <= 0:
                    continue
                if not _recall_fits_cap(team, p):
                    continue
                ahl.remove(p)
                roster.append(p)
                _stamp_recall_effects(team, p)
                recalled.append(p)
                if want_goalie:
                    go_need -= 1
                else:
                    sk_need -= 1
            except Exception:
                continue
    except Exception:
        pass
    return recalled


def ensure_dressed_lineup_auto(team, notify=None):
    """Eastside-style auto: if the club can't dress 18+2, summon exactly
    the shortfall (team back-pointers guaranteed) and hand the summoned
    list to `notify(list)` when given. No-op on a healthy lineup.
    Identical rule for user and AI. Never raises."""
    summoned = []
    try:
        if can_dress_lineup(team):
            return summoned
        summoned = summon_emergency_fillers(team)
        if summoned and notify is not None:
            try:
                notify(summoned)
            except Exception:
                pass
    except Exception:
        pass
    return summoned


def _notify_filler_summon(app, team, summoned):
    """FYI note for an auto-summon (Eastside-style): news_log + inbox.
    Not a blocker. Never raises."""
    try:
        sk = sum(1 for p in (summoned or []) if not _is_goalie(p))
        go = sum(1 for p in (summoned or []) if _is_goalie(p))
        bits = []
        if sk:
            bits.append(f"{sk} skater{'s' if sk != 1 else ''}")
        if go:
            bits.append(f"{go} goalie{'s' if go != 1 else ''}")
        story = (f"Emergency fill-ins summoned: {', '.join(bits)} -- "
                 f"league-minimum, released automatically when your lineup "
                 f"is healthy.")
        date = _current_date(app)
        try:
            log = getattr(app, "news_log", None)
            if isinstance(log, list):
                log.append({"date": date, "story": f"🆘 {story}"})
        except Exception:
            pass
        try:
            from game_classes import EmailMessage
            msg = EmailMessage(
                sender="League Office",
                sender_type="System",
                subject="Emergency fill-ins summoned",
                content=(story + "\n\nThey're league-exception recalls -- "
                         "they don't count against the 23-man roster or the "
                         "50-contract limit, and they leave automatically "
                         "once you can dress a full lineup without them."),
                category="Roster",
                is_important=False,
                requires_response=False,
                action_type="emergency_fillers_summoned",
            )
            inbox = getattr(app, "inbox_messages", None)
            if isinstance(inbox, list):
                inbox.append(msg)
        except Exception:
            pass
    except Exception:
        pass


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
            pick = None
            for c in cands:
                # Never paper down below a dressable 18+2 -- a demotion
                # that breaks the dressed minimum is skipped (the summon
                # step below covers genuine shortfalls with fill-ins).
                # Clubs that already can't dress skip the guard: paper
                # moves can't make a short lineup shorter.
                try:
                    if (can_dress_lineup(team)
                            and would_break_dress_minimum(team, [c])):
                        continue
                except Exception:
                    pass
                pick = c
                break
            if pick is None:
                break  # every demotable player is needed to dress
            try:
                roster.remove(pick)
                ahl.append(pick)
                done["demoted"] += 1
            except Exception:
                break
        done["released"] = release_unneeded_fillers(team)
        if not can_dress_lineup(team):
            # Real clubs recall from the farm before the league mints
            # exception players: try real AHL recalls first, fillers only
            # for whatever shortfall remains (cap-strapped or empty farm).
            sk_need, go_need = lineup_shortfall(team)
            done["recalled"] = len(recall_best_available(
                team, sk_need, go_need, rng=rng))
            if not can_dress_lineup(team):
                done["summoned"] = len(summon_emergency_fillers(team, rng))
    except Exception:
        pass
    return done


def user_roster_compliance(team):
    """Daily user backstop, same rules as the AI: release fillers no longer
    needed to dress a lineup, then cover any shortfall. Recalls stay a human
    decision -- when recallable AHL players exist the shortfall is left for
    the user to fill via the recall picker (surfaced by the dress_minimum
    blocker); fillers auto-summon only when the farm can't help. NO
    paper-down step -- demotions stay a human decision (the 23/SPC day
    gates surface an overage to the user instead). Never raises."""
    done = {"summoned": 0, "released": 0}
    try:
        done["released"] = release_unneeded_fillers(team)
        if not can_dress_lineup(team):
            sk_need, go_need = lineup_shortfall(team)
            if not recall_candidates(team, sk_need, go_need):
                done["summoned"] = len(ensure_dressed_lineup_auto(team))
    except Exception:
        pass
    return done


def ai_can_sign_spc(team) -> bool:
    """Prevention for AI auto-sign paths: don't take a 51st contract."""
    try:
        return spc_count(team) < SPC_LIMIT
    except Exception:
        return True
