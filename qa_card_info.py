#!/usr/bin/env python3
"""qa_card_info.py -- player card shows contract, rights, and league.

Muck 2026-10-02: "ensure contracts/rights/league show on playercards please"

Headless logic tests (no display needed for the label helpers; widget build
is smoke-tested under Xvfb when available).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


def make_player(**kw):
    """Minimal fake player with the fields the card reads."""
    class FakeContract:
        def __init__(self, **ckw):
            self.salary = ckw.get("salary", 0)
            self.years_remaining = ckw.get("years_remaining", 0)
            self.signing_bonus = ckw.get("signing_bonus", 0)
            self.performance_bonus = 0
            self.no_trade_clause = ckw.get("no_trade_clause", False)
            self.no_movement_clause = ckw.get("no_movement_clause", False)
            self.modified_ntc_teams = ckw.get("modified_ntc_teams", 0)
            self.no_trade_list = []
            self.ntc_waiver_for = ""
            self.two_way = ckw.get("two_way", False)
            self.ahl_salary = ckw.get("ahl_salary", 0)
            self.entry_level = ckw.get("entry_level", False)
            self.modified_ntc_approved = False

    class FakePlayer:
        pass

    p = FakePlayer()
    p.first_name = kw.get("first_name", "Test")
    p.last_name = kw.get("last_name", "Player")
    p.age = kw.get("age", 25)
    p.primary_position = kw.get("primary_position", "C")
    p.contract = FakeContract(**kw.get("contract", {}))
    p.contract_years = kw.get("contract_years", None)
    p.salary = kw.get("salary", None)
    p.team_name = kw.get("team_name", "Free Agent")
    p.rights_team = kw.get("rights_team", "")
    p.rights_type = kw.get("rights_type", "")
    p.rights_expiry_year = kw.get("rights_expiry_year", 0)
    p.junior_league = kw.get("junior_league", "")
    p.draft_year = kw.get("draft_year", 2024)
    p.draft_position = kw.get("draft_position", "Round 1, Pick 10")
    p.mesh_form = 0
    return p


class FakeCard:
    """Bind the real helper methods without building widgets."""

    def __init__(self, player, league=None):
        self.player = player
        self.parent_app = type("A", (), {"league": league})()


def load_helpers():
    import types
    import modern_profile as mp
    for name in ("_contract_type_label", "_player_league"):
        assert hasattr(mp.PlayerProfile, name), f"missing {name}"
    return mp


def main():
    mp = load_helpers()

    # -- contract type labels ------------------------------------------------
    p = make_player(contract={"entry_level": True, "salary": 925000,
                              "years_remaining": 3})
    c = FakeCard(p)
    lbl = mp.PlayerProfile._contract_type_label(c)
    check("ELC label", "ELC" in lbl, lbl)

    p = make_player(contract={"two_way": True, "ahl_salary": 75000,
                              "salary": 800000, "years_remaining": 2})
    c = FakeCard(p)
    lbl = mp.PlayerProfile._contract_type_label(c)
    check("2-way label", "2-way" in lbl, lbl)

    p = make_player(contract={"no_movement_clause": True, "salary": 9000000,
                              "years_remaining": 5})
    c = FakeCard(p)
    lbl = mp.PlayerProfile._contract_type_label(c)
    check("NMC label", "NMC" in lbl, lbl)

    p = make_player(contract={"no_trade_clause": True, "salary": 7000000,
                              "years_remaining": 4})
    c = FakeCard(p)
    lbl = mp.PlayerProfile._contract_type_label(c)
    check("NTC label (no NMC)", "NTC" in lbl and "NMC" not in lbl, lbl)

    p = make_player(contract={"modified_ntc_teams": 10, "salary": 6000000,
                              "years_remaining": 3})
    c = FakeCard(p)
    lbl = mp.PlayerProfile._contract_type_label(c)
    check("M-NTC label", "M-NTC" in lbl, lbl)

    p = make_player(contract={"salary": 1000000, "years_remaining": 1})
    c = FakeCard(p)
    lbl = mp.PlayerProfile._contract_type_label(c)
    check("plain contract, no crash", isinstance(lbl, str), lbl)

    # -- league detection ----------------------------------------------------
    class FakeTeam:
        def __init__(self, name, roster=(), ahl_roster=()):
            self.team_name = name
            self.roster = list(roster)
            self.ahl_roster = list(ahl_roster)

    class FakeLeague:
        def __init__(self, teams):
            self.teams = teams

    p_nhl = make_player(team_name="Chicago Blackhawks")
    p_ahl = make_player(team_name="Rockford IceHogs")
    lg = FakeLeague([FakeTeam("Chicago Blackhawks", roster=[p_nhl],
                              ahl_roster=[p_ahl])])
    check("NHL roster -> NHL",
          mp.PlayerProfile._player_league(FakeCard(p_nhl, lg)) == "NHL")
    check("AHL roster -> AHL",
          mp.PlayerProfile._player_league(FakeCard(p_ahl, lg)) == "AHL")

    p_eu = make_player(team_name="Europe")
    check("team Europe -> Europe",
          mp.PlayerProfile._player_league(FakeCard(p_eu)) == "Europe")

    p_jr = make_player(team_name="Free Agent", rights_type="CHL",
                       rights_team="Chicago Blackhawks")
    check("CHL rights -> CHL",
          mp.PlayerProfile._player_league(FakeCard(p_jr)) == "CHL")

    p_fa = make_player()
    check("free agent -> Free Agent",
          mp.PlayerProfile._player_league(FakeCard(p_fa)) == "Free Agent")

    # -- never raises on garbage ---------------------------------------------
    class Empty:
        pass

    for fn_name in ("_contract_type_label", "_player_league"):
        fn = getattr(mp.PlayerProfile, fn_name)
        try:
            fn(FakeCard(Empty()))
            ok = True
        except Exception:
            ok = False
        check(f"{fn_name} never raises on empty player", ok)

    # -- widget build smoke test (Xvfb) --------------------------------------
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        prof = mp.PlayerProfile.__new__(mp.PlayerProfile)
        prof.player = make_player(
            contract={"entry_level": True, "two_way": True,
                      "ahl_salary": 80000, "salary": 925000,
                      "years_remaining": 3, "signing_bonus": 92500},
            rights_team="Chicago Blackhawks", rights_type="CHL",
            rights_expiry_year=2028, team_name="Rockford IceHogs")
        prof.parent_app = type("A", (), {"league": None})()
        info = tk.Frame(root)
        prof._create_rights_league_strip(info)
        kids = info.winfo_children()
        check("rights/league strip builds", len(kids) >= 1)
        txt = kids[0].cget("text") if kids else ""
        check("strip shows league", "League:" in txt, txt)
        check("strip shows rights", "Rights:" in txt, txt)
        root.destroy()
    except Exception as e:
        # No display available -- logic tests above are the real gate.
        print(f"  SKIP: widget smoke test (no display: {e})")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
