"""Auto-resolution for game-stopping blockers.

Every day-advance blocker gets a smart "Auto" option that resolves it using
real hockey logic. The cardinal rule: NEVER expose valuable players to
waivers. A valuable player is young, highly-rated, or on a good contract --
demoting them risks losing them for nothing.

Safety hierarchy for demotions:
  1. Waiver-exempt players (no risk) -- prefer lowest overall first
  2. Injured players -> LTIR/IR (no risk, keeps them in org)
  3. Waiver-eligible but LOW value (old, low-rated, replaceable)
  4. NEVER: waiver-eligible + high value (young star, top-6 F, top-4 D)

If no safe move exists, the auto option reports why instead of making
a bad move. The user can always resolve manually.
"""

from waiver_logic import is_waiver_eligible


def _player_overall(p):
    """Real overall for value judgments.

    Player has no ``overall`` attribute (overall_rating() is the method);
    the old getattr defaulted every generated player to 50, which made
    90-overall stars look like replacement-level depth and classified
    them as safe waiver demotions -- exactly what the safety rules
    forbid.
    """
    try:
        _or = getattr(p, 'overall_rating', None)
        if callable(_or):
            return float(_or() or 50)
    except Exception:
        pass
    try:
        return float(getattr(p, 'overall', 50) or 50)
    except Exception:
        return 50.0


def _player_value(p):
    """Rough trade/waiver-claim value: higher = more likely to be claimed.
    Considers overall, age (young = valuable), and role."""
    overall = _player_overall(p)
    try:
        age = int(getattr(p, 'age', 30) or 30)
    except Exception:
        age = 30
    # Young high-overall players are the most valuable (would be claimed)
    age_factor = max(0.5, 1.5 - (age - 20) * 0.05)  # 20yo=1.5x, 30yo=1.0x, 40yo=0.5x
    return overall * age_factor


def _is_safe_demotion(p):
    """True if demoting this player risks nothing.
    Safe = waiver-exempt (no waivers needed) OR low value (won't be claimed)."""
    try:
        if not is_waiver_eligible(p):
            return True  # Exempt -- no waivers, no risk
    except Exception:
        pass
    # Waiver-eligible but low value: unlikely to be claimed
    return _player_value(p) < 55.0


def _is_valuable_waiver_eligible(p):
    """True if demoting this player would risk losing a good player.
    These players must NEVER be auto-demoted."""
    try:
        eligible = is_waiver_eligible(p)
    except Exception:
        eligible = True  # Unknown -> assume eligible (safe side)
    if not eligible:
        return False
    return _player_value(p) >= 65.0


def rank_demotion_candidates(players):
    """Sort players for demotion: safest first.
    Returns (safe_list, risky_list). Safe = auto-demote OK.
    Risky = valuable waiver-eligible, never auto-demote."""
    safe, risky = [], []
    for p in players:
        if _is_valuable_waiver_eligible(p):
            risky.append(p)
        else:
            safe.append(p)
    # Safest first: waiver-exempt before low-value eligible,
    # then lowest overall within each group
    def _key(p):
        try:
            exempt = not is_waiver_eligible(p)
        except Exception:
            exempt = False
        try:
            ov = float(getattr(p, 'overall', 50) or 50)
        except Exception:
            ov = 50.0
        return (0 if exempt else 1, ov)
    safe.sort(key=_key)
    # Riskiest last (for display): highest value first
    risky.sort(key=_player_value, reverse=True)
    return safe, risky


def auto_choose_captains(team):
    """Pick C and 2 As using real logic: leadership + tenure + role.
    Prefers veterans with high leadership. Never picks a rookie or
    a player likely to be traded/demoted."""
    try:
        skaters = [p for p in getattr(team, 'roster', [])
                   if getattr(p, 'primary_position', None) is not None
                   and 'goalie' not in str(getattr(p, 'primary_position', '')).lower()]
        if not skaters:
            return None, "No skaters on roster"
    except Exception:
        return None, "Could not read roster"

    def _score(p):
        try:
            leadership = float(getattr(p, 'leadership', 50) or 50)
        except Exception:
            leadership = 50.0
        try:
            age = int(getattr(p, 'age', 25) or 25)
        except Exception:
            age = 25
        try:
            overall = float(getattr(p, 'overall', 50) or 50)
        except Exception:
            overall = 50.0
        try:
            gp = int(getattr(p, 'nhl_games_played', 0) or 0)
        except Exception:
            gp = 0
        # Veterans with leadership and games played score highest
        # Peak captain age is 28-34; rookies (under 23, <100 GP) are excluded
        if age < 23 and gp < 100:
            return -1
        age_score = 10 - abs(age - 30) * 0.5  # Peak at 30
        return leadership * 0.5 + overall * 0.2 + age_score + min(gp / 50.0, 10)

    ranked = sorted(skaters, key=_score, reverse=True)
    ranked = [p for p in ranked if _score(p) > 0]
    if len(ranked) < 3:
        return None, f"Not enough eligible skaters ({len(ranked)})"
    captain = ranked[0]
    alternates = ranked[1:3]
    # O-3: apply the picks here too (idempotent -- callers that apply
    # manually just repeat a no-op). Direct callers previously got picks
    # that were never set on the players.
    try:
        for _p in getattr(team, 'roster', []) or []:
            if getattr(_p, 'captaincy', '') in ('C', 'A'):
                _p.captaincy = ''
        captain.captaincy = 'C'
        for _a in alternates:
            _a.captaincy = 'A'
    except Exception:
        pass
    return (captain, alternates), None


def auto_fix_roster_limit(team, over_by):
    """Demote `over_by` players using waiver-safe logic.
    Returns (demoted_list, error_msg). Never demotes valuable
    waiver-eligible players, and never demotes a player whose removal
    would leave the club unable to dress 18+2 -- that caused the
    dress_minimum <-> roster_limit_23 ping-pong (demote a skater to
    clear 23, dress_minimum re-fires, auto-recall pushes back over 23,
    repeat until the calendar freezes forever)."""
    try:
        # Deferred: roster_limits imports this module lazily too.
        from roster_limits import would_break_dress_minimum
    except Exception:
        would_break_dress_minimum = None
    try:
        roster = list(getattr(team, 'roster', []) or [])
    except Exception:
        return [], "Could not read roster"
    # Only consider active roster players (not already in minors/IR)
    candidates = [p for p in roster
                  if not getattr(p, 'is_injured', False)
                  and not getattr(p, 'on_ir', False)]
    safe, risky = rank_demotion_candidates(candidates)
    # Walk the safe list in rank order, skipping anyone whose removal --
    # on top of already-chosen demotions -- would break the dressed
    # lineup minimum. The check is cumulative: removing several players
    # at once compounds, so test demoted+[p] each step.
    demoted = []
    for p in safe:
        if len(demoted) >= over_by:
            break
        try:
            if (would_break_dress_minimum is not None
                    and would_break_dress_minimum(team, demoted + [p])):
                continue
        except Exception:
            pass
        demoted.append(p)
    if len(demoted) < over_by:
        names = ", ".join(getattr(p, 'full_name', '?') for p in risky[:3])
        return demoted, (
            f"Only {len(demoted)} safe demotion(s) available without "
            f"breaking the dressed lineup, need {over_by}. "
            f"Remaining players ({names}) are too valuable to risk on "
            f"waivers. IR the injured first, then resolve manually."
        )
    return demoted, None


def auto_run_practice(team, app=None):
    """Coach runs practice: for each player, pick the best drill type
    based on position needs and weakest attributes, with intensity
    matched to fatigue/age/injury. Uses real coaching staff via
    execute_practice(team=...).

    Smart logic:
      - Young players: develop weakest key attributes (moderate+ intensity)
      - Veterans: maintenance (conditioning, hockey IQ, light-moderate)
      - Centers weak on draws: faceoffs
      - Goalies: goalie-specific focus
      - High fatigue or injured: light or skip
    Returns (sessions_run, error_msg)."""
    try:
        from enhanced_practice_system import (
            PracticeType, PracticeIntensity)
    except Exception as e:
        return 0, f"Practice system unavailable: {e}"
    try:
        roster = [p for p in (getattr(team, 'roster', None) or [])
                  if not getattr(p, 'is_injured', False)]
    except Exception:
        return 0, "Could not read roster"
    if not roster:
        return 0, "No healthy players available"

    # We need a practice engine instance. PracticeEngine is the real
    # headless-safe engine (no tkinter); the old PracticeSystem name
    # never existed, and instantiating the ctk PracticeCenterView as a
    # fallback only ever failed (a Team is not a tkinter master).
    try:
        from enhanced_practice_system import PracticeEngine
        ps = PracticeEngine()
    except Exception as e:
        return 0, f"Could not init practice system: {e}"

    def _attr(p, name, default=50):
        try:
            return float(getattr(p, name, default) or default)
        except Exception:
            return float(default)

    def _is_goalie(p):
        try:
            pos = str(getattr(p, 'primary_position', '')).lower()
            return 'goalie' in pos or 'goaltender' in pos
        except Exception:
            return False

    def _is_center(p):
        try:
            pos = str(getattr(p, 'primary_position', '')).lower()
            return 'center' in pos or pos.strip() == 'c'
        except Exception:
            return False

    def _is_defense(p):
        try:
            pos = str(getattr(p, 'primary_position', '')).lower()
            return 'defens' in pos or pos.strip() == 'd'
        except Exception:
            return False

    sessions = 0
    for p in roster:
        try:
            age = int(getattr(p, 'age', 25) or 25)
        except Exception:
            age = 25
        try:
            fatigue = float(getattr(p, 'fatigue', 0) or 0)
        except Exception:
            fatigue = 0

        # Pick drill type by biggest weakness in role-relevant attributes
        if _is_goalie(p):
            # Goalies: weakest of the key goalie attributes
            cands = [
                (PracticeType.DEFENSE, _attr(p, 'positioning', 50)),
                (PracticeType.CONDITIONING, _attr(p, 'agility', 50)),
                (PracticeType.HOCKEY_IQ, _attr(p, 'rebound_control', 50)),
            ]
        elif _is_defense(p):
            cands = [
                (PracticeType.DEFENSE, _attr(p, 'defensive_awareness', 50)),
                (PracticeType.CHECKING, _attr(p, 'checking', 50)),
                (PracticeType.PASSING, _attr(p, 'passing', 50)),
                (PracticeType.SKATING, _attr(p, 'skating', 50)),
            ]
        else:  # Forwards
            cands = [
                (PracticeType.SHOOTING, _attr(p, 'shooting', 50)),
                (PracticeType.SKATING, _attr(p, 'skating', 50)),
                (PracticeType.PASSING, _attr(p, 'passing', 50)),
            ]
            if _is_center(p):
                cands.append(
                    (PracticeType.FACEOFFS, _attr(p, 'faceoffs', 50)))
        # Veterans: maintenance focus overrides development
        if age >= 32:
            cands = [
                (PracticeType.CONDITIONING, _attr(p, 'conditioning', 50)),
                (PracticeType.HOCKEY_IQ,
                 _attr(p, 'offensive_awareness', 50)),
            ] + cands
        # Pick the weakest attribute's drill
        cands.sort(key=lambda x: x[1])
        drill = cands[0][0]

        # Pick intensity: young + fresh = harder; old/tired = lighter
        if fatigue > 70:
            intensity = PracticeIntensity.LIGHT
        elif age >= 34 or fatigue > 50:
            intensity = PracticeIntensity.MODERATE
        elif age <= 24 and fatigue < 30:
            intensity = PracticeIntensity.INTENSE
        else:
            intensity = PracticeIntensity.MODERATE

        try:
            can, _why = ps.can_practice(p, drill, intensity)
            if not can:
                # Fall back to light if the chosen intensity isn't allowed
                intensity = PracticeIntensity.LIGHT
                can, _why = ps.can_practice(p, drill, intensity)
            if can:
                ps.execute_practice(p, drill, intensity, team=team)
                sessions += 1
        except Exception:
            continue

    if sessions == 0:
        return 0, "No practice sessions could be run"
    return sessions, None
def auto_fix_salary_cap(team, over_amount):
    """Shed salary via releases (unsigned players), LTIR (eligible injured
    players) and safe demotions.

    Uses the game's real cap accounting (salary_cap_system), so the
    predicted relief matches what cap_breakdown() shows after the moves
    are applied:

    - Release relief = full hit (no contract = no burial rule). Unsigned
      players (years_remaining == 0) count against the cap until the GM
      acts; releasing them is zero-risk (no buyout, no waivers, no NMC)
      and clears "phantom" overages LTIR/demotions cannot touch.
    - LTIR relief = max(0, hit - cap_space_at_placement), predicted exactly
      the way ir_system.place_on_ltir() computes it at apply time. The
      club is over the cap here, so space is normally $0 and relief is the
      full hit.
    - Demote relief = active-roster hit MINUS the player's minor-league
      charge (burial rule: a one-way deal in the AHL only sheds the
      $1.225M burial exemption; a two-way deal sheds everything). The old
      code used a ``cap_hit`` attribute that does not exist on Player, so
      every move computed $0 of relief and the auto-fix silently did
      nothing -- the day-advance blocker it was supposed to clear could
      never clear.

    Safety rules (unchanged): waiver-exempt players first, then low-value
    waiver-eligible; NMC players are never demoted; injured players are
    never demoted; demotions stop before breaking the dressed 18+2
    minimum; emergency fillers are skipped (their charge is already
    excluded from the compliance check, so demoting them frees nothing).
    Valuable waiver-eligible players are never risked on waivers.

    Returns (moves, err): moves is [('release'|'ltir'|'demote', player,
    predicted_relief_dollars), ...] for apply_cap_fix_moves(); err is None
    when the moves cover over_amount, otherwise a plain-language reason
    naming the actual constraint (locked dollars, NMCs, ineligible
    injuries). Partial moves are still returned so the caller can make
    real progress and re-check.
    """
    try:
        over_amount = float(over_amount or 0)
    except Exception:
        over_amount = 0.0
    if over_amount <= 0:
        return [], None
    try:
        roster = list(getattr(team, 'roster', []) or [])
    except Exception:
        return [], "Could not read roster"
    # Deferred imports: roster_limits imports this module lazily, so keep
    # the module import light and cycle-free.
    try:
        from salary_cap_system import (
            _active_roster_hit, minor_league_cap_charge, DEFAULT_CAP)
    except Exception:
        return [], "Cap accounting unavailable (salary_cap_system)"
    try:
        import ir_system as _irs
    except Exception:
        _irs = None
    try:
        from roster_limits import (would_break_dress_minimum,
                                   is_emergency_filler)
    except Exception:
        would_break_dress_minimum = None
        is_emergency_filler = None

    def _hit(p):
        try:
            return int(_active_roster_hit(p) or 0)
        except Exception:
            return 0

    def _shed_of(p):
        """Real dollars freed by demoting p to the AHL (burial rule)."""
        try:
            return max(0,
                       int(_active_roster_hit(p) or 0)
                       - int(minor_league_cap_charge(p) or 0))
        except Exception:
            return 0

    def _is_nmc(p):
        try:
            return bool(getattr(getattr(p, 'contract', None),
                                'no_movement_clause', False))
        except Exception:
            return False

    def _is_filler(p):
        if is_emergency_filler is None:
            return False
        try:
            return bool(is_emergency_filler(p))
        except Exception:
            return False

    def _on_any_ir(p):
        if _irs is None:
            return False
        try:
            return bool(_irs.is_on_any_ir(p))
        except Exception:
            return False

    moves = []
    covered = 0.0
    ltir_ineligible = []

    # -- Step 0: release unsigned players (expired contracts).
    # A player with years_remaining == 0 is not under contract -- they
    # count against the cap only until the GM acts (re-sign or move on).
    # Releasing them is zero-risk: no buyout penalty, no waiver exposure,
    # no NMC issue. This clears "phantom" overages that LTIR/demotions
    # cannot touch. (2026-10-08: 5-year sim froze $0.90M over because a
    # single unsigned player counted against the cap and no safe move
    # existed to shed it.)
    #
    # Scan BOTH roster and ahl_roster: an unsigned player on a one-way AHL
    # deal still counts (hit - burial exemption) via minor_league_cap_charge,
    # which also ignores years_remaining. Same phantom-overage freeze, one
    # list over.
    #
    # Sort cheapest-first: shed minimum talent. If a $1M unsigned player
    # covers the overage, don't release the $8M star.
    def _is_unsigned(p):
        # Match the blocker's definition (game_manager.py): years_remaining
        # == 0. A missing contract (None) has $0 AAV and is skipped by the
        # relief gate below anyway.
        try:
            c = getattr(p, "contract", None)
            if c is None:
                return False
            return int(getattr(c, "years_remaining", 1) or 0) == 0
        except Exception:
            return False

    def _release_relief(p, on_ahl):
        # NHL roster: full hit clears. AHL: the minor-league charge clears
        # (burial rule -- one-way deals keep hit minus exemption).
        try:
            if on_ahl:
                return int(minor_league_cap_charge(p) or 0)
            return _hit(p)
        except Exception:
            return 0

    _unsigned = []
    try:
        _ros = list(getattr(team, 'roster', None) or [])
    except Exception:
        _ros = []
    try:
        _ahl_list = list(getattr(team, 'ahl_roster', None) or [])
    except Exception:
        _ahl_list = []
    for p in _ros:
        if _is_unsigned(p) and not _is_filler(p):
            _unsigned.append((p, False))
    for p in _ahl_list:
        if _is_unsigned(p) and not _is_filler(p):
            _unsigned.append((p, True))
    # Cheapest first -- minimum talent shed. Emergency fillers excluded:
    # their charge is already excluded from the compliance check, so
    # releasing one frees $0 in reality.
    _unsigned.sort(key=lambda t: _release_relief(t[0], t[1]))
    for p, _on_ahl in _unsigned:
        if covered >= over_amount:
            break
        # Dressed-minimum guard (NHL roster only; unsigned players are never
        # in the dressed pool anyway since has_active_contract is False,
        # but keep the guard for safety).
        if not _on_ahl:
            try:
                if (would_break_dress_minimum is not None
                        and would_break_dress_minimum(team, [p])):
                    continue
            except Exception:
                pass
        _relief = _release_relief(p, _on_ahl)
        if _relief <= 0:
            continue
        moves.append(('release', p, _relief))
        covered += _relief
    _chosen = {id(p) for _, p, _ in moves}

    # -- Step 1: LTIR for eligible injured players (no risk, real relief).
    # place_on_ltir() snapshots cap space at placement; releases run first
    # (Step 0) so the phantom overage clears before the snapshot. In the
    # over-cap regime space is 0 either way, so predicted relief (full hit)
    # matches applied relief. LTIRs must be applied before any demotion
    # for the snapshot to match.
    if _irs is not None:
        try:
            _cap = int(getattr(team, 'salary_cap', DEFAULT_CAP)
                       or DEFAULT_CAP)
        except Exception:
            _cap = int(DEFAULT_CAP)
        try:
            _space = max(0, _cap - sum(_hit(p) for p in roster))
        except Exception:
            _space = 0
        for p in roster:
            if covered >= over_amount:
                break
            if id(p) in _chosen:
                continue
            try:
                _ok, _why = _irs.eligible_for_ltir(p)
            except Exception:
                _ok, _why = False, ""
            if not _ok:
                if bool(getattr(p, 'is_injured', False)):
                    ltir_ineligible.append((p, _why))
                continue
            _relief = max(0, _hit(p) - _space)
            if _relief <= 0:
                continue
            moves.append(('ltir', p, _relief))
            covered += _relief
    _chosen = {id(p) for _, p, _ in moves}

    # -- Step 2: safe demotions, biggest REAL shed first.
    candidates = [p for p in roster
                  if id(p) not in _chosen
                  and not bool(getattr(p, 'is_injured', False))
                  and not _on_any_ir(p)
                  and not _is_nmc(p)
                  and not _is_filler(p)]
    safe, risky = rank_demotion_candidates(candidates)
    safe.sort(key=_shed_of, reverse=True)
    demoted = []
    dress_skipped = 0
    for p in safe:
        if covered >= over_amount:
            break
        _shed = _shed_of(p)
        if _shed <= 0:
            continue
        try:
            if (would_break_dress_minimum is not None
                    and would_break_dress_minimum(team, demoted + [p])):
                dress_skipped += 1
                continue
        except Exception:
            pass
        moves.append(('demote', p, _shed))
        demoted.append(p)
        covered += _shed

    if covered < over_amount:
        # Name the actual constraint so the report is actionable.
        try:
            _locked = sum(_hit(p) for p in risky)
        except Exception:
            _locked = 0
        try:
            _nmc_n = sum(1 for p in roster if _is_nmc(p))
        except Exception:
            _nmc_n = 0
        _inj = list(ltir_ineligible)
        parts = [f"Safe moves free ${covered:,.0f}, need "
                 f"${over_amount:,.0f}."]
        if _locked > 0:
            parts.append(
                f"${_locked:,.0f} is locked in valuable waiver-eligible "
                f"contracts the auto-fix will not risk on waivers.")
        if _nmc_n:
            parts.append(
                f"{_nmc_n} no-movement clause(s) can't be demoted "
                f"without consent.")
        if _inj:
            _reasons = "; ".join(
                f"{getattr(p, 'full_name', '?')}: {why or 'not eligible'}"
                for p, why in _inj[:3])
            parts.append(
                f"{len(_inj)} injured player(s) aren't LTIR-eligible "
                f"({_reasons}).")
        if dress_skipped:
            parts.append(
                f"{dress_skipped} otherwise-safe demotion(s) would break "
                f"the dressed 18+2 minimum.")
        parts.append("Resolve manually (trade or buyout).")
        return moves, " ".join(parts)
    return moves, None


def apply_cap_fix_moves(team, moves, current_date=None):
    """Apply ('ltir'|'demote'|'release', player, predicted_relief) moves from
    auto_fix_salary_cap().

    LTIRs go through ir_system.place_on_ltir (eligibility + relief-pool
    bookkeeping -- never just flag-flipping); demotions move the player
    from team.roster to team.ahl_roster, the list the cap accounting
    actually reads. (team.farm_team does not exist anywhere in the
    codebase; the old apply code dropped demoted players out of the
    organization entirely.) Releases remove unsigned (expired-contract)
    players from the roster entirely -- they have no contract, so there
    is no buyout, no waiver, no penalty; they become free agents.

    Returns (applied, skipped): applied = [(player, kind, relief)],
    skipped = [(player, reason)]. Never raises.
    """
    applied, skipped = [], []
    try:
        import ir_system as _irs
    except Exception:
        _irs = None
    # Releases first: unsigned players are the "phantom" overage -- clear
    # them before LTIR snapshots cap space.
    for kind, p, ch in (moves or []):
        if kind != 'release':
            continue
        try:
            # Use the game's canonical remove_player: sets team_name to
            # "Free Agent" (so they appear in the FA pool), records
            # last_team_name (loyalty model), and closes the stint history.
            # Raw roster.remove() would orphan them -- invisible to free
            # agency, corrupting downstream systems.
            _remover = getattr(team, "remove_player", None)
            if callable(_remover):
                _remover(p)
            else:
                # Fallback for duck-typed team objects without remove_player
                _ros = getattr(team, 'roster', None)
                if _ros is not None and p in _ros:
                    _ros.remove(p)
                _ahl = getattr(team, 'ahl_roster', None)
                if _ahl is not None and p in _ahl:
                    _ahl.remove(p)
                try:
                    p.team_name = "Free Agent"
                except Exception:
                    pass
            applied.append((p, kind, ch))
        except Exception as e:
            skipped.append((p, f"release failed: {e}"))
    # LTIR placement: place_on_ltir snapshots cap space at placement.
    # Releases (Step 0) run first so the phantom overage clears before the
    # snapshot; in the over-cap regime space is 0 either way, so the
    # planner's prediction (full hit) matches. LTIRs run before demotions
    # for the same snapshot reason.
    for kind, p, ch in (moves or []):
        if kind != 'ltir':
            continue
        try:
            if _irs is None:
                raise RuntimeError("ir_system unavailable")
            ok, why = _irs.place_on_ltir(team, p, current_date)
        except Exception as e:
            ok, why = False, str(e) or "LTIR placement failed"
        if ok:
            applied.append((p, kind, ch))
        else:
            skipped.append((p, f"LTIR refused: {why}"))
    for kind, p, ch in (moves or []):
        if kind != 'demote':
            continue
        try:
            _ros = getattr(team, 'roster', None)
            _ahl = getattr(team, 'ahl_roster', None)
            if _ahl is None:
                raise RuntimeError("no ahl_roster to receive demotion")
            if _ros is not None and p in _ros:
                _ros.remove(p)
            if p not in _ahl:
                _ahl.append(p)
            applied.append((p, kind, ch))
        except Exception as e:
            skipped.append((p, f"demote failed: {e}"))
    return applied, skipped
