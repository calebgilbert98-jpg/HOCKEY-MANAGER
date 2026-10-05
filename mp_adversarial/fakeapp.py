# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Handler-layer fixtures: bind the real HockeyManagerGUI._mp_* host
handlers to a synthetic league. Lets chaos tests fire every routed action
with hostile params and verify the handlers reject cleanly, never crash,
and never mutate the wrong team's state.
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as main_mod
from game_classes import Contract, Player, PlayerPosition, Team

GUI = main_mod.HockeyManagerGUI

# Methods the _mp_* handlers need, bound from the real GUI class.
HANDLER_METHODS = [
    "_mp_find_team", "_mp_team_player", "_mp_team_pick",
    "_mp_find_free_agent", "_mp_cap_room", "_mp_peer_session_for_team",
    "_mp_is_claimed", "_mp_set_lines", "_mp_set_tactics",
    "_mp_set_captaincy", "_mp_set_trade_block", "_mp_sign_free_agent",
    "_mp_release_player", "_mp_send_to_minors", "_mp_demote_player",
    "_mp_call_up", "_mp_return_to_junior", "_mp_claim_waivers",
    "_mp_buyout_player", "_mp_extend_contract", "_mp_hire_staff",
    "_mp_fire_staff", "_mp_assign_scout", "_mp_practice_session",
    "_mp_set_practice", "_mp_start_practice_plan", "_mp_offer_sheet",
    "_mp_request_save", "_mp_team_talk", "_mp_press_conference",
    "_mp_propose_trade", "_mp_draft_pick", "_mp_execute_mp_trade",
    "_mp_route_trade_offer", "_mp_resolve_trade_response",
    "_mp_clear_proposal_waivers", "_apply_management_action",
    "_apply_multiplayer_action", "_mp_is_goalie",
    "_mp_place_on_waivers", "_mp_answer_ai_offer",
    "_mp_rfa_qualify", "_mp_staff_renew", "_mp_offer_sheet_match",
    "_mp_offer_sheet_trade_alt", "_mp_arbitration_walkaway",
    "_mp_coach_checkin", "_mp_emergency_fill", "_mp_owner_meeting",
    "_mp_fantasy_draft_pick",
]


def make_player(pid, first="Chaos", last="Player", age=25, pos=None,
                salary=2_000_000, years=2):
    pos = pos or PlayerPosition.CENTER
    p = Player(first, f"{last}{pid}", age, pos)
    p.id = f"p{pid}"
    p.contract = Contract(salary=salary, years_remaining=years)
    p.on_waivers = False
    p.waiver_days = 0
    p.team_name = ""
    return p


def make_team(name, n_players=20):
    t = Team(team_name=name, city="Chaos", division="X", conference="Y")
    t.roster, t.ahl_roster, t.prospects = [], [], []
    t.staff = []
    t.lineup = {}
    t.trade_block = []
    # NOTE: Team.cap_space is a read-only property; _mp_cap_room computes
    # from league.salary_cap_system or falls back. Leave it unset.
    from game_classes import PlayerPosition as _PP
    for i in range(n_players):
        _pos = _PP.GOALIE if i < 2 else None
        p = make_player(f"{name}{i}", last=f"{name}Guy", pos=_pos)
        p.team_name = name
        t.roster.append(p)
    return t


class FakeLeague:
    def __init__(self, teams):
        self.teams = teams
        self.season_year = 2027
        self.draft_prospects = []
        self.free_agent_staff = []
        self.overseas_staff = []


class ChaosApp:
    """Fake host app with two synthetic teams and a free-agent pool."""

    def __init__(self):
        self.team_a = make_team("CHAOSA")
        self.team_b = make_team("CHAOSB")
        self.league = FakeLeague([self.team_a, self.team_b])
        self.free_agent_pool = [make_player(f"fa{i}", last=f"FreeAgent",
                                            salary=1_500_000)
                                for i in range(4)]
        self.waiver_list = []
        self.current_date = "2027-01-15"
        self.news_log = []
        self._mp_pending_offers = {}
        self._mp_draft_clock = None
        self.mp_host = None  # set by tests that need broadcast paths
        for meth in HANDLER_METHODS:
            fn = getattr(GUI, meth, None)
            if fn is not None:
                setattr(self, meth, fn.__get__(self))

    # -- dependencies the handlers call --------------------------------
    def free_agents(self):
        return self.free_agent_pool

    def add_news(self, msg):
        self.news_log.append(msg)

    def _validate_contract_terms(self, player, salary, years,
                                 extension=False, team=None):
        # Mirror the real gate's shape: reject garbage, accept sane.
        try:
            salary = int(salary)
            years = int(years)
        except (TypeError, ValueError):
            return False, "Invalid contract terms."
        if salary < 0 or years <= 0 or years > 8:
            return False, "Invalid contract terms."
        return True, ""

    def handle_elc_offer(self, prospect, salary, signing_bonus,
                         performance_bonus, team=None):
        return {"verdict": "accepted", "note": "ok"}


def apply(app, action, params, team_name, manager="ChaosGM"):
    """Run one action through the real dispatch; returns (ok, detail)."""
    res = app._apply_multiplayer_action(action, dict(params), manager)
    if isinstance(res, tuple) and len(res) == 3:
        return res[0], res[1]
    return res[0], res[1]
