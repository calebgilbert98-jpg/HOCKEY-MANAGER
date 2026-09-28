"""QA: EHM-style GM value tags on the trade screen.

Run: DISPLAY=:99 python3 qa_trade_values.py   (widget test needs a display)
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai_extension_planning as aep

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


class C:
    def __init__(self, s, y, elc=False):
        self.salary = s
        self.years_remaining = y
        self.entry_level = elc


class P:
    def __init__(self, n, ovr, age, sal, yrs, grade="C", rnd=0, elc=False,
                 db=""):
        self.full_name = n
        self._ovr = ovr
        self.age = age
        self.contract = C(sal, yrs, elc)
        self.potential_grade = grade
        self.true_potential_grade = ""
        self.draft_round = rnd
        self.drafted_by = db
        self.rights_team = db

    def overall_rating(self):
        return self._ovr


def GM(patience=0.5, loyalty=0.5, aggression=0.5, adaptability=0.5):
    return SimpleNamespace(team_name="X", patience=patience, loyalty=loyalty,
                           aggression=aggression, adaptability=adaptability,
                           experience_years=10, tenure_years=2, reputation=50)


GENERATIONAL = P("Generational", 98, 23, 13_000_000, 4, "A", 1, False, "X")
STAR = P("Star", 91, 28, 10_000_000, 2, "A", 1, False, "X")
KID = P("Kid", 74, 20, 925_000, 1, "B", 1, True, "X")
SECOND = P("Second", 85, 24, 6_000_000, 2, "B", 2, False, "")
GRINDER = P("Grinder", 76, 30, 2_500_000, 1, "D", 5, False, "")


def test_tiers():
    print("== value tiers ==")
    loyal = GM(loyalty=0.9)
    label, color, s = aep.trade_value_tier(GENERATIONAL, loyal, None)
    check("generational cornerstone -> UNTOUCHABLE", label == "UNTOUCHABLE",
          f"{label} ({s})")
    check("untouchable is rare (only true cornerstones)",
          aep.trade_value_tier(STAR, GM(), None)[0] != "UNTOUCHABLE")
    for p, want in ((STAR, "CORE"), (KID, "CORE"), (SECOND, "VALUED"),
                    (GRINDER, "GETTABLE")):
        label, color, s = aep.trade_value_tier(p, GM(), None)
        check(f"{p.full_name} ({p._ovr} ovr) -> {want}", label == want,
              f"{label} ({s})")
    check("tier colors are hex", all(
        aep.trade_value_tier(p, GM(), None)[1].startswith("#")
        for p in (STAR, KID, SECOND, GRINDER)))
    # The tag and the forward book agree
    check("CORE tag implies forward-book piece",
          aep.is_franchise_piece(KID, GM(), None))
    check("GETTABLE tag implies not a piece",
          not aep.is_franchise_piece(GRINDER, GM(), None))


def test_gm_subjectivity():
    print("== GM subjectivity moves the tag ==")
    check("loyal GM: homegrown kid reads CORE",
          aep.trade_value_tier(KID, GM(loyalty=0.9), None)[0] == "CORE")
    cold = GM(patience=0.05, loyalty=0.05, aggression=0.9)
    check("cold win-now GM: same kid is just a chip (GETTABLE)",
          aep.trade_value_tier(KID, cold, None)[0] == "GETTABLE",
          aep.trade_value_tier(KID, cold, None)[2])
    vet = P("Vet", 84, 33, 6_000_000, 1, "C", 2)
    strat_rb = SimpleNamespace(priority=SimpleNamespace(value="REBUILD"))
    check("rebuilder: 33yo 84 is GETTABLE (asset, not core)",
          aep.trade_value_tier(vet, GM(), strat_rb)[0] == "GETTABLE")
    check("neutral GM: 33yo 84 is a movable asset, not a piece",
          aep.trade_value_tier(vet, GM(), None)[0] == "GETTABLE")


def test_badge_fn_wiring():
    print("== badge_fn wiring ==")
    import windows
    from ai_team_management import AITeamManager
    from ai_gm_identity import GMIdentity
    mgr = AITeamManager()
    team = SimpleNamespace(team_name="X", roster=[STAR, KID, GRINDER])
    mgr.gm_identities["X"] = GMIdentity(
        team_name="X", gm_name="T. Est", aggression=0.4, patience=0.6,
        loyalty=0.85, experience_years=12, tenure_years=4, reputation=70)
    mgr.team_strategies["X"] = SimpleNamespace(
        priority=SimpleNamespace(value="CONTEND"))
    fn = windows.gm_trade_value_badges(mgr, team)
    check("badge_fn built from the real manager", callable(fn))
    got = {p.full_name: fn(p)[0] for p in team.roster}
    check("badges reflect the GM's read",
          got == {"Star": "CORE", "Kid": "CORE", "Grinder": "GETTABLE"}, str(got))
    # Fallbacks: no manager, no identity -- still a neutral read, never None-crash
    fn2 = windows.gm_trade_value_badges(None, team)
    check("missing manager falls back gracefully",
          callable(fn2) and fn2(STAR)[0] == "CORE")
    # The window actually passes badge_fn to the partner list
    import inspect
    src = inspect.getsource(windows.TradeWindow.update_trade_partner_roster)
    check("partner refresh passes badge_fn", "badge_fn=_badge_fn" in src)
    check("badges come from gm_trade_value_badges",
          "gm_trade_value_badges" in src)


def test_widget_badges():
    print("== widget badge rendering (headless) ==")
    import customtkinter as ctk
    from ctk_theme import CTkPlayerList
    root = ctk.CTk()
    root.geometry("500x400")
    lst = CTkPlayerList(root)
    lst.pack(fill="both", expand=True)
    gm = GM()

    def _badge(p):
        label, color, _s = aep.trade_value_tier(p, gm, None)
        return (label, color)

    lst.set_players([STAR, SECOND, GRINDER], badge_fn=_badge)
    root.update()
    found = {}
    for frame, player in lst._rows:
        texts = []
        for w in frame.winfo_children():
            try:
                texts.append(w.cget("text"))
            except Exception:
                pass
        hit = [t for t in texts
               if t in ("UNTOUCHABLE", "CORE", "VALUED", "GETTABLE")]
        found[player.full_name] = hit[0] if hit else None
    check("row badges render with the right tiers",
          found == {"Star": "CORE", "Second": "VALUED", "Grinder": "GETTABLE"},
          str(found))
    # Backward compat: no badge_fn -> no badges, no crash
    lst.set_players([STAR, GRINDER])
    root.update()
    def _texts(frame):
        out = []
        for w in frame.winfo_children():
            try:
                out.append(w.cget("text"))
            except Exception:
                pass
        return out
    nb = sum(1 for frame, _p in lst._rows for t in _texts(frame)
             if t in ("UNTOUCHABLE", "CORE", "VALUED", "GETTABLE"))
    check("no badge_fn -> no badges (backward compatible)", nb == 0)
    # Selection still works with badges present
    lst.set_players([STAR, GRINDER], badge_fn=_badge)
    root.update()
    check("selection API intact", lst.get_selected() is None)
    root.destroy()


def test_scout_perception():
    print("== scout perception vs the GM's eyes ==")
    check("no identity -> neutral trust 0.5", aep.scout_trust(None) == 0.5)
    check("stubborn old-school GM barely reads the reports",
          abs(aep.scout_trust(GM(patience=0.0, adaptability=0.0)) - 0.15) < 1e-9)
    check("adaptable modern GM leans fully on his scouts",
          abs(aep.scout_trust(GM(patience=1.0, adaptability=1.0)) - 1.0) < 1e-9)
    check("adaptability leads, patience follows",
          aep.scout_trust(GM(patience=0.0, adaptability=1.0))
          > aep.scout_trust(GM(patience=1.0, adaptability=0.0)))
    # Gut mapping: the GM's eyes on the ladder
    check("gut: 92 ovr reads A+", aep._gut_grade_index(
        SimpleNamespace(overall_rating=lambda: 92)) >= 10)
    check("gut: 74 ovr reads C-range", 3 <= aep._gut_grade_index(
        SimpleNamespace(overall_rating=lambda: 74)) <= 5)
    check("gut: 64 ovr reads F", aep._gut_grade_index(
        SimpleNamespace(overall_rating=lambda: 64)) == 0)

    kid = P("Kid", 74, 20, 925_000, 1, "B", 1, True, "X")  # scouts say B
    modern = GM(patience=0.9, adaptability=0.9)
    oldschool = GM(patience=0.2, adaptability=0.1)
    s_modern = aep.franchise_score(kid, modern, None)
    s_mid = aep.franchise_score(kid, GM(), None)
    s_old = aep.franchise_score(kid, oldschool, None)
    check("trusting GM values the B-kid at the scout's read",
          s_modern > s_mid > s_old, f"{s_modern:.1f}/{s_mid:.1f}/{s_old:.1f}")
    t_modern = aep.trade_value_tier(kid, modern, None)[0]
    t_old = aep.trade_value_tier(kid, oldschool, None)[0]
    check("the tag follows: modern CORE, old-school demotes",
          t_modern == "CORE" and t_old != "CORE", f"{t_modern}/{t_old}")

    # The overrule: scouts are down on him (D), the old GM's eyes like him
    bust = P("Bust?", 76, 20, 925_000, 1, "D", 3, True, "")
    s_trust = aep.franchise_score(bust, modern, None)
    s_gut = aep.franchise_score(bust, oldschool, None)
    check("old-school GM overrules a bad scout report with his eyes",
          s_gut > s_trust, f"gut {s_gut:.1f} vs trust {s_trust:.1f}")

    # Established stars: the information blend doesn't move finished products
    s1 = aep.franchise_score(STAR, modern, None)
    s2 = aep.franchise_score(STAR, oldschool, None)
    check("star valuation barely moves with trust",
          abs(s1 - s2) < 8.0, f"{s1:.1f} vs {s2:.1f}")

    # Deterministic: no RNG in the hot path
    check("scores are deterministic",
          aep.franchise_score(kid, modern, None) == s_modern
          and aep.trade_value_tier(kid, oldschool, None)
          == aep.trade_value_tier(kid, oldschool, None))


if __name__ == "__main__":
    test_tiers()
    test_scout_perception()
    test_gm_subjectivity()
    test_badge_fn_wiring()
    try:
        test_widget_badges()
    except Exception as e:
        if "display" in str(e).lower() or "DISPLAY" in str(e):
            print("  SKIP widget test (no display)")
        else:
            raise
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
