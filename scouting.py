"""Scouting systems for Puck Dynasty: fog of war, regional assignments, draft board.

Pure logic, no GUI. Powers the Scouting Department window and the draft.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional


GRADE_ORDER = ['F', 'D', 'C-', 'C', 'C+', 'B-', 'B', 'B+', 'A-', 'A', 'A+']
GRADE_COLORS = {
    'A+': '#46c93a', 'A': '#46c93a', 'A-': '#7bd747',
    'B+': '#a3d84b', 'B': '#c9d44b', 'B-': '#e8d44b',
    'C+': '#e8b93c', 'C': '#e09a3c', 'C-': '#d97f3c',
    'D': '#d96a4b', 'F': '#e74c3c',
}

SCOUT_REGIONS = ['CHL', 'USHL / NCAA', 'Europe', 'International', 'Top 50 Prospects']

# Pro beats (refinement #4): leagues a pro scout can be assigned to. Kept
# separate from SCOUT_REGIONS (the amateur draft beat) so each tick only
# processes its own region kind. ALL_SCOUT_REGIONS is what the region
# dropdown offers.
PRO_BEATS = ['AHL', 'SHL', 'Liiga', 'KHL', 'NL']
ALL_SCOUT_REGIONS = SCOUT_REGIONS + PRO_BEATS

# Default beat by role for pro scouts that have no assignment yet.
# EUROPEAN_SCOUT cycles the four European pro leagues; PROFESSIONAL_SCOUT
# and ADVANCE_SCOUT default to the AHL (trade targets + call-up watch).
# HEAD_SCOUT manages the department (no auto beat); AMATEUR_SCOUT keeps
# the existing user-assigned amateur flow (no default).
_EURO_BEAT_CYCLE = ['SHL', 'Liiga', 'KHL', 'NL']


def scout_roles():
    """All StaffRole values that count as scouts."""
    from game_classes import StaffRole
    return {StaffRole.HEAD_SCOUT, StaffRole.PROFESSIONAL_SCOUT,
            StaffRole.AMATEUR_SCOUT, StaffRole.EUROPEAN_SCOUT,
            StaffRole.ADVANCE_SCOUT}


def is_scout(staff) -> bool:
    return getattr(staff, 'role', None) in scout_roles()

_NAT_TO_REGION = {
    'Canada': 'CHL',
    'USA': 'USHL / NCAA',
    'Sweden': 'Europe', 'Finland': 'Europe',
    'Czech': 'Europe', 'Czech Republic': 'Europe', 'Russia': 'Europe',
}


def prospect_region(player) -> str:
    """Region a prospect plays in, derived from nationality."""
    return _NAT_TO_REGION.get(getattr(player, 'nationality', ''), 'International')


def grade_index(grade: str) -> int:
    g = (grade or 'C').strip()
    if g in GRADE_ORDER:
        return GRADE_ORDER.index(g)
    # Tolerate single-letter grades
    for i, full in enumerate(GRADE_ORDER):
        if full.startswith(g):
            return i
    return 4


def grade_at(index: int) -> str:
    return GRADE_ORDER[max(0, min(len(GRADE_ORDER) - 1, index))]


def grade_color(grade: str) -> str:
    return GRADE_COLORS.get((grade or '').strip(), '#e8ecf4')


def consensus_range(player) -> str:
    """Public (pre-scouting) potential estimate: true grade +/- noise, stable per player."""
    rng = random.Random(f"consensus-{getattr(player, 'id', '')}")
    true = grade_index(getattr(player, 'potential_grade', 'C'))
    lo = grade_at(true - rng.randint(1, 2))
    hi = grade_at(true + rng.randint(1, 2))
    if lo == hi:
        return lo
    return f"{lo} – {hi}"


def report_potential_display(report, player) -> str:
    """Fog-of-war potential string: narrows with report accuracy."""
    if report is None:
        return "?"
    true = grade_index(getattr(player, 'potential_grade', 'C'))
    spread = {'A': 0, 'B': 0, 'C': 1, 'D': 2, 'F': 3}.get(
        getattr(report, 'accuracy', 'F'), 3)
    if spread == 0:
        return grade_at(true)
    # Scouted estimate may be off-center when accuracy is low
    center = true + random.Random(player.id).randint(-1, 1) if spread > 1 else true
    lo = grade_at(center - spread)
    hi = grade_at(center + spread)
    return lo if lo == hi else f"{lo} – {hi}"


def report_summary(report) -> Dict[str, str]:
    """Compact dict for the report card UI."""
    if report is None:
        return {}
    return {
        'accuracy': getattr(report, 'accuracy', '?'),
        'viewings': str(getattr(report, 'viewings', 0)),
        'scout': getattr(getattr(report, 'scout', None), 'full_name', '—'),
        'region': getattr(report, 'region_coverage', '—'),
        'strengths': list(getattr(report, 'strengths', []) or [])[:4],
        'weaknesses': list(getattr(report, 'weaknesses', []) or [])[:4],
        'comparable': ', '.join(getattr(report, 'comparable_players', []) or []) or '—',
        'projection': getattr(report, 'projected_nhl_arrival', '') or '—',
        'notes': getattr(report, 'notes', '') or '',
    }


# ---------------------------------------------------------------------------
# Regional scouting (passive, daily tick)
# ---------------------------------------------------------------------------

def get_scout_region(gm, scout) -> Optional[str]:
    regions = getattr(gm, 'scout_region_assignments', {})
    return regions.get(getattr(scout, 'id', None))


def set_scout_region(gm, scout, region: Optional[str]):
    if not hasattr(gm, 'scout_region_assignments'):
        gm.scout_region_assignments = {}
    if region:
        gm.scout_region_assignments[getattr(scout, 'id', None)] = region
    else:
        gm.scout_region_assignments.pop(getattr(scout, 'id', None), None)


def process_regional_scouting(gm):
    """Each region-assigned scout files viewings on prospects from that region."""
    from game_classes import ScoutingReport
    prospects = getattr(getattr(gm, 'league', None), 'draft_prospects', [])
    if not prospects:
        return
    regions: Dict[str, list] = getattr(gm, 'scout_region_assignments', {})
    if not regions:
        return
    user_team = getattr(gm, 'user_team', None)
    reports = getattr(user_team, 'scouting_reports', {}) if user_team else {}
    scouts = [s for s in getattr(user_team, 'staff', []) if is_scout(s)]
    by_id = {getattr(s, 'id', None): s for s in scouts}

    for scout_id, region in regions.items():
        scout = by_id.get(scout_id)
        if scout is None:
            continue
        # Efficiency scales with scout skill. Staff attrs are native
        # 1-100, so normalize to the 0-1 range the old 1-20 math had.
        eff = (getattr(scout, 'judging_player_ability', 50) +
               getattr(scout, 'judging_player_potential', 50)) / 200
        if random.random() > 0.35 * eff + 0.1:
            continue
        if region == 'Top 50 Prospects':
            pool = sorted(prospects,
                          key=lambda p: getattr(p, 'draft_ranking', 0),
                          reverse=True)[:50]
        else:
            pool = [p for p in prospects if prospect_region(p) == region]
        if not pool:
            continue
        # Prefer prospects with thin reports
        pool = sorted(pool, key=lambda p: reports.get(p.id).viewings
                      if p.id in reports else -1)
        player = random.choice(pool[:40])
        if player.id not in reports:
            reports[player.id] = ScoutingReport(player=player, scout=scout)
        reports[player.id].update_report(player, scout)


# ---------------------------------------------------------------------------
# Pro scouting (passive, daily tick): pro scouts file viewings on pro
# players in their beat. Same tick shape as process_regional_scouting.
#
# Beat pools (pools that actually persist in the sim):
#   AHL            -- every farm roster in the league (team.ahl_roster).
#                      Trade targets and call-up watch, ~800 players.
#   SHL / Liiga / KHL / NL -- undrafted European free agents currently in
#                      the FA pool (euro_free_agents tags them with
#                      source_league); the Panarin-pipeline watch.
#
# Ownership: ONE report per player, same as the amateur beat and the
# user-assignment flow. The first scout to file owns the report
# (report.scout never changes); later ticks from other scouts only add
# viewings to the existing report. This keeps the Scout Report tab's
# "which scout" resolution stable.
# ---------------------------------------------------------------------------

def pro_beat_pool(league, region):
    """Player pool for a pro beat region. Empty list for unknown regions."""
    if league is None:
        return []
    if region == 'AHL':
        pool = []
        for t in getattr(league, 'teams', None) or []:
            pool.extend(getattr(t, 'ahl_roster', None) or [])
        return pool
    if region in ('SHL', 'Liiga', 'KHL', 'NL'):
        fa = getattr(league, 'free_agents', None) or []
        return [p for p in fa
                if getattr(p, 'source_league', '') == region]
    return []


def _default_beat_for_role(role, euro_slot):
    """Sensible default beat for a pro-role scout with no assignment."""
    from game_classes import StaffRole
    if role == StaffRole.EUROPEAN_SCOUT:
        return _EURO_BEAT_CYCLE[euro_slot % len(_EURO_BEAT_CYCLE)]
    if role in (StaffRole.PROFESSIONAL_SCOUT, StaffRole.ADVANCE_SCOUT):
        return 'AHL'
    return None  # HEAD_SCOUT / AMATEUR_SCOUT: no auto beat


def ensure_default_pro_beats(gm):
    """Idempotent: every pro-role scout with no region assignment gets a
    sensible default beat. Covers new games, old saves, and hired scouts
    without touching the hiring flows -- the default is in place from the
    scout's first day on staff, i.e. from hire."""
    from game_classes import StaffRole
    user_team = getattr(gm, 'user_team', None)
    if user_team is None:
        return
    regions = getattr(gm, 'scout_region_assignments', None)
    if regions is None:
        gm.scout_region_assignments = regions = {}
    euro_slot = 0
    for s in getattr(user_team, 'staff', None) or []:
        try:
            if not is_scout(s):
                continue
            if getattr(s, 'id', None) in regions:
                continue
            role = getattr(s, 'role', None)
            if role in (StaffRole.HEAD_SCOUT, StaffRole.AMATEUR_SCOUT):
                continue
            beat = _default_beat_for_role(role, euro_slot)
            if role == StaffRole.EUROPEAN_SCOUT:
                euro_slot += 1
            if beat:
                regions[getattr(s, 'id')] = beat
        except Exception:
            continue


def process_pro_scouting(gm):
    """Each pro-beat-assigned scout files viewings on pro players from
    that beat. Mirrors process_regional_scouting's tick shape:
    efficiency-scaled daily chance, prefers thin reports, writes into
    user_team.scouting_reports via ScoutingReport.update_report."""
    from game_classes import ScoutingReport
    league = getattr(gm, 'league', None)
    if league is None:
        return
    user_team = getattr(gm, 'user_team', None)
    if user_team is None:
        return
    ensure_default_pro_beats(gm)
    regions: Dict[str, list] = getattr(gm, 'scout_region_assignments', {}) or {}
    reports = getattr(user_team, 'scouting_reports', None)
    if reports is None:
        user_team.scouting_reports = reports = {}
    scouts = [s for s in getattr(user_team, 'staff', []) if is_scout(s)]
    by_id = {getattr(s, 'id', None): s for s in scouts}

    for scout_id, region in regions.items():
        if region not in PRO_BEATS:
            continue  # amateur regions belong to process_regional_scouting
        scout = by_id.get(scout_id)
        if scout is None:
            continue
        # Same efficiency shape as the amateur tick. Staff attrs are
        # native 1-100, normalized to 0-1.
        eff = (getattr(scout, 'judging_player_ability', 50) +
               getattr(scout, 'judging_player_potential', 50)) / 200
        if random.random() > 0.35 * eff + 0.1:
            continue
        pool = pro_beat_pool(league, region)
        if not pool:
            continue
        # Prefer players with thin reports; one report per player, first
        # scout to file owns it.
        pool = sorted(pool, key=lambda p: reports.get(p.id).viewings
                      if p.id in reports else -1)
        player = random.choice(pool[:40])
        if player.id not in reports:
            reports[player.id] = ScoutingReport(player=player, scout=scout)
        reports[player.id].update_report(player, scout)


# ---------------------------------------------------------------------------
# Draft board
# ---------------------------------------------------------------------------

def get_draft_board(user_team) -> List[str]:
    """Player ids in user-ranked order."""
    return list(getattr(user_team, 'draft_board', []) or [])


def set_draft_board(user_team, ids: List[str]):
    user_team.draft_board = list(ids)


def board_rank_map(user_team) -> Dict[str, int]:
    return {pid: i for i, pid in enumerate(get_draft_board(user_team))}
