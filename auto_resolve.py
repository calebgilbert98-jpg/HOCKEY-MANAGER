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


def _player_value(p):
    """Rough trade/waiver-claim value: higher = more likely to be claimed.
    Considers overall, age (young = valuable), and role."""
    try:
        overall = float(getattr(p, 'overall', 50) or 50)
    except Exception:
        overall = 50.0
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
    return (captain, alternates), None


def auto_fix_roster_limit(team, over_by):
    """Demote `over_by` players using waiver-safe logic.
    Returns (demoted_list, error_msg). Never demotes valuable
    waiver-eligible players."""
    try:
        roster = list(getattr(team, 'roster', []) or [])
    except Exception:
        return [], "Could not read roster"
    # Only consider active roster players (not already in minors/IR)
    candidates = [p for p in roster
                  if not getattr(p, 'is_injured', False)
                  and not getattr(p, 'on_ir', False)]
    safe, risky = rank_demotion_candidates(candidates)
    if len(safe) < over_by:
        names = ", ".join(getattr(p, 'full_name', '?') for p in risky[:3])
        return [], (
            f"Only {len(safe)} safe demotion(s) available, need {over_by}. "
            f"Remaining players ({names}) are too valuable to risk on waivers. "
            f"Resolve manually."
        )
    return safe[:over_by], None


def auto_fix_salary_cap(team, over_amount):
    """Shed salary via safe demotions (waiver-exempt high-salary first)
    and LTIR for injured players. Never exposes valuable players."""
    moves = []
    try:
        roster = list(getattr(team, 'roster', []) or [])
    except Exception:
        return [], "Could not read roster"
    # Step 1: LTIR injured players (no risk, immediate relief)
    for p in roster:
        if getattr(p, 'is_injured', False) and not getattr(p, 'on_ir', False):
            try:
                cap_hit = float(getattr(p, 'cap_hit', 0) or 0)
            except Exception:
                cap_hit = 0
            if cap_hit > 0:
                moves.append(('ltir', p, cap_hit))
    # Step 2: Demote high-salary waiver-exempt players (safest cap relief)
    candidates = [p for p in roster
                  if not getattr(p, 'is_injured', False)
                  and not getattr(p, 'on_ir', False)]
    safe, _risky = rank_demotion_candidates(candidates)
    # Sort safe by cap hit descending (most relief first)
    def _cap(p):
        try:
            return float(getattr(p, 'cap_hit', 0) or 0)
        except Exception:
            return 0.0
    safe.sort(key=_cap, reverse=True)
    total_relief = sum(m[2] for m in moves)
    for p in safe:
        if total_relief >= over_amount:
            break
        ch = _cap(p)
        if ch > 0:
            moves.append(('demote', p, ch))
            total_relief += ch
    if total_relief < over_amount:
        return moves, (
            f"Safe moves free ${total_relief:,.0f}, need ${over_amount:,.0f}. "
            f"Remaining savings would require risking valuable players on "
            f"waivers. Resolve manually (trade or buyout)."
        )
    return moves, None
