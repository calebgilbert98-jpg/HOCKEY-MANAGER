"""
QA: Wave B GM-respect decay system (D48) + GM firing/hiring turnover (D20).

D48 (the GM respect system) commits covered:
  b1a21da "GM respect decay (D48): ... plus no-fleece-sting enforcement (D20)"

Covers:
  D48: GM_RESPECT_TUNABLES constants; respect_baseline_for (stature-derived,
       clamped [30, 70]); respect_tier labels; decay_gm_respect asymmetric
       drift (goodwill k=0.25, forgiveness k=0.10) toward baseline at
       deadline + season end; recency-weighted deal ledger; diminishing
       returns per GM; NO separate respect-sting on fleeces (the anti-
       "objective fairness judge" rule); respect_trend; tier-change inbox
       notes; reset_gm_ledger_on_hire; main.py wiring (deadline + season
       end).
  D20: AITeamManager._hire_replacement_gm (old GM to pool, best-reputation
       hire, gm_name sync, pending news, empty pool -> None, name fallback,
       non-GM staff never picked); the gm_fired branch of
       _weekly_board_review (respect ledger reset, identity rebuilt,
       security re-armed).

Provenance: reputation_system, ai_team_management, ai_gm_identity and
game_classes MUST be the worktree copies -- we re-run the league's
reputation logic, not the pristine repo's.

Usage: python3 qa_wave_b_respect.py   (0 failures expected)
"""
import os
import sys

sys.path.insert(0, "/home/hatch/workspace/wt-wave-b")
import reputation_system as rs
import ai_team_management as atm
from game_classes import StaffRole
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

for mod in (rs, atm):
    assert "wt-wave-b" in mod.__file__, mod.__file__
import game_classes as gc
assert "wt-wave-b" in gc.__file__, gc.__file__

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS: " if cond else "FAIL: ") + name +
          ("" if cond or not detail else " -- %r" % (detail,)))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------- fixtures
def team(name, gm="GM of " + "X"):
    return SimpleNamespace(team_name=name, gm_name=gm, is_user_team=False,
                           inbox=None)


class FakeInbox:
    def __init__(self):
        self.messages = []

    def add_message(self, msg):
        self.messages.append(msg)


def league_of(names):
    teams = [team(n) for n in names]
    return SimpleNamespace(teams=teams, free_agent_staff=[], season_year=2026)


def mkstaff(fn, ln, rep, role=StaffRole.GENERAL_MANAGER):
    return SimpleNamespace(first_name=fn, last_name=ln, role=role,
                           reputation=rep, ambition="climb",
                           determination=60, controversy=30, adaptability=60,
                           working_with_youngsters=50, player_development=50,
                           man_management=60, leadership=60, control_need=50)


# ---------------------------------------------------------------- D48
def test_d48_tunables():
    print("== D48: GM_RESPECT_TUNABLES ==")
    t = rs.GM_RESPECT_TUNABLES
    check("tunable keys", set(t) == {"k_goodwill", "k_forgive", "wary_prior",
                                     "baseline_stature_pull", "baseline_hi",
                                     "baseline_lo", "diminish_per_deal",
                                     "diminish_window_days",
                                     "diminish_floor"}, set(t))
    check("k_goodwill 0.25", t["k_goodwill"] == 0.25, t["k_goodwill"])
    check("k_forgive 0.10", t["k_forgive"] == 0.10, t["k_forgive"])
    check("wary_prior 42", t["wary_prior"] == 42, t["wary_prior"])
    check("stature pull 0.4, clamps [30, 70]",
          (t["baseline_stature_pull"], t["baseline_lo"],
           t["baseline_hi"]) == (0.4, 30.0, 70.0))
    check("diminish 0.35/deal, 90-day window, 0.25 floor",
          (t["diminish_per_deal"], t["diminish_window_days"],
           t["diminish_floor"]) == (0.35, 90, 0.25))
    check("goodwill > forgive (asymmetric memory)",
          t["k_goodwill"] > t["k_forgive"])


def test_d48_baseline():
    print("== D48: respect baseline from stature ==")
    with patch.object(rs, "gm_stature", return_value=90):
        check("stature 90 -> 66.0", rs.respect_baseline_for(team("A")) == 66.0)
    with patch.object(rs, "gm_stature", return_value=10):
        check("stature 10 -> 34.0", rs.respect_baseline_for(team("A")) == 34.0)
    with patch.object(rs, "gm_stature", return_value=100):
        check("clamped at 70", rs.respect_baseline_for(team("A")) == 70.0)
    with patch.object(rs, "gm_stature", return_value=0):
        check("clamped at 30", rs.respect_baseline_for(team("A")) == 30.0)
    # No GM on file -> stature 50 -> baseline 50 (new-GM prior handled by
    # the wary reset, not the baseline).
    check("no GM on file -> 50.0",
          rs.respect_baseline_for(team("A")) == 50.0)


def test_d48_tiers():
    print("== D48: respect tier labels ==")
    for v, want in [(20, "cold"), (34, "cold"), (35, "wary"), (49, "wary"),
                    (50, "cordial"), (64, "cordial"), (65, "warm"),
                    (90, "warm")]:
        check("respect %d -> %s" % (v, want),
              rs.respect_tier_label(v) == want, rs.respect_tier_label(v))


def test_d48_decay_asymmetric():
    print("== D48: decay is asymmetric, team-scoped, kind-scoped ==")
    lg = league_of(["A", "B", "C"])
    ta, tb, tc = lg.teams
    rs._bump_gm_respect(lg, ta, tb, +40)   # 90: strong goodwill
    rs._bump_gm_respect(lg, ta, tc, -40)   # 10: deep grudge
    # A non-gm_respect record between the same GMs must be untouched.
    rs._respect_store(lg).append({"a": ("team", "A"), "b": ("team", "B"),
                                  "kind": "team_team", "intensity": 70})
    moved = rs.decay_gm_respect(lg)
    ra = rs.gm_gm_respect(lg, ta, tb)
    rb = rs.gm_gm_respect(lg, ta, tc)
    check("goodwill 90 -> 80", ra == 80, ra)
    check("grudge 10 -> 14 (slower)", rb == 14, rb)
    check("goodwill drop (10) > forgiveness rise (4)", (90 - ra) > (rb - 10))
    check("two gm_respect records moved", moved == 2, moved)
    store = rs._respect_store(lg)
    tt = [r for r in store if r["kind"] == "team_team"][0]
    check("team_team record untouched", tt["intensity"] == 70,
          tt["intensity"])
    # Scoped call: only A's pairs move.
    lg2 = league_of(["A", "B", "C"])
    ta2, tb2, tc2 = lg2.teams
    rs._bump_gm_respect(lg2, ta2, tb2, +40)
    rs._bump_gm_respect(lg2, tb2, tc2, +40)
    rs.decay_gm_respect(lg2, team=ta2)
    check("scoped: A's pair decayed",
          rs.gm_gm_respect(lg2, ta2, tb2) == 80)
    check("scoped: other pair untouched",
          rs.gm_gm_respect(lg2, tb2, tc2) == 90)


def test_d48_decay_converges():
    print("== D48: decay converges toward baseline, never overshoots ==")
    lg = league_of(["A", "B"])
    ta, tb = lg.teams
    rs._bump_gm_respect(lg, ta, tb, +40)
    vals = []
    for _ in range(12):
        rs.decay_gm_respect(lg)
        vals.append(rs.gm_gm_respect(lg, ta, tb))
    check("monotonic toward baseline",
          all(b <= a for a, b in zip(vals, vals[1:])), vals)
    check("never overshoots below baseline", all(v >= 50 for v in vals),
          vals)
    check("converges near baseline", abs(vals[-1] - 50) <= 2, vals[-1])


def test_d48_diminishing_returns():
    print("== D48: repeated dealing has diminishing returns ==")
    lg = league_of(["D", "E"])
    td, te_ = lg.teams
    bumps = []
    prev = rs.gm_gm_respect(lg, td, te_)
    for _ in range(8):
        now = rs.record_gm_dealing(lg, td, te_, +4)
        bumps.append(now - prev)
        prev = now
    check("first four bumps are [4, 3, 2, 2]", bumps[:4] == [4, 3, 2, 2],
          bumps[:4])
    check("bumps never drop below 1 (floor)", all(b >= 1 for b in bumps),
          bumps)
    check("later bumps decay to the floor", bumps[-1] == 1, bumps)


def test_d48_recency():
    print("== D48: only recent deals diminish (90-day window) ==")
    lg = league_of(["F", "G"])
    tf, tg = lg.teams
    rs._bump_gm_respect(lg, tf, tg, +8)
    r = rs.rivalry_between(rs._respect_store(lg),
                           rs.gm_persona(tf), rs.gm_persona(tg),
                           kind="gm_respect")
    old = (date.today() - timedelta(days=200)).isoformat()
    rs._deal_log(r).append({"date": old, "delta": 4, "outcome": "deal"})
    check("200-day-old entry not counted recent",
          rs._recent_deal_count(r, 90) == 0)
    before = rs.gm_gm_respect(lg, tf, tg)
    after = rs.record_gm_dealing(lg, tf, tg, +4)
    check("stale history -> full bump", after - before == 4,
          (before, after))


def test_d48_no_fleece_sting():
    print("== D48: NO separate respect-sting on fleeces (D48 + D20 rule) ==")
    lg = league_of(["H", "I"])
    th, ti = lg.teams
    after = rs.record_gm_dealing(lg, th, ti, -6, outcome="fleece")
    check("fleece logged at face value (-6, not amplified)",
          after == 44, after)
    r = rs.rivalry_between(rs._respect_store(lg),
                           rs.gm_persona(th), rs.gm_persona(ti),
                           kind="gm_respect")
    entries = rs._deal_log(r)
    check("ledger records the fleece plainly",
          entries and entries[-1]["outcome"] == "fleece", entries)


def test_d48_trend():
    print("== D48: respect_trend reads the ledger ==")
    lg = league_of(["J", "K", "L", "M", "N", "O"])
    tj, tk, tl, tm_, tn, to_ = lg.teams
    rs.record_gm_dealing(lg, tj, tk, +4)
    rs.record_gm_dealing(lg, tj, tk, +4)
    rs.record_gm_dealing(lg, tl, tm_, -4)
    rs.record_gm_dealing(lg, tl, tm_, -4)
    rs._bump_gm_respect(lg, tn, to_, +10)   # no ledger entries
    check("warming", rs.respect_trend(lg, tj, tk) == "warming")
    check("cooling", rs.respect_trend(lg, tl, tm_) == "cooling")
    check("steady (no ledger)", rs.respect_trend(lg, tn, to_) == "steady")
    check("trend(None) safe", rs.respect_trend(None, tj, tk) == "steady")


def test_d48_inbox_note():
    print("== D48: tier-change inbox note for the user's GM ==")
    lg = league_of(["U", "X"])
    tu, tx = lg.teams
    tu.is_user_team = True
    tu.inbox = FakeInbox()
    tu.gm_name = "User GM"
    rs._bump_gm_respect(lg, tu, tx, -4)          # 46, no notification
    assert tu.inbox.messages == []
    rs.record_gm_dealing(lg, tu, tx, +8)         # 54: wary -> cordial
    msgs = tu.inbox.messages
    check("one tier-change message", len(msgs) == 1, len(msgs))
    check("subject names the tier move",
          msgs and "wary -> cordial" in msgs[0].subject,
          msgs[0].subject if msgs else None)
    check("league-office sender", msgs and msgs[0].sender == "League Office",
          msgs[0].sender if msgs else None)
    check("landed in the user's inbox only",
          tu.inbox.messages is msgs and tx.inbox is None)


def test_d48_reset_on_hire():
    print("== D48: new GM resets the ledger to the wary prior ==")
    lg = league_of(["P", "Q", "ZZ"])
    tp, tq, tz = lg.teams
    rs._bump_gm_respect(lg, tp, tq, +40)     # 90, keyed ("gm","P")
    rs._bump_gm_respect(lg, tz, tq, +20)     # 70, another team's record
    r = rs.rivalry_between(rs._respect_store(lg),
                           rs.gm_persona(tp), rs.gm_persona(tq),
                           kind="gm_respect")
    rs._deal_log(r).append({"date": date.today().isoformat(), "delta": 4,
                            "outcome": "deal"})
    heat = {"a": ("gm", "P"), "b": ("gm", "Q"), "kind": "gm_gm",
            "intensity": 60}
    rs._respect_store(lg).append(heat)
    # The record key carries the TEAM name, never the GM's: a new GM means
    # the predecessor's warmth does not transfer. The hire API takes the
    # team name.
    rs.reset_gm_ledger_on_hire(lg, "P")
    check("respect reset to wary prior 42",
          rs.gm_gm_respect(lg, tp, tq) == 42,
          rs.gm_gm_respect(lg, tp, tq))
    check("deal log cleared", rs._deal_log(r) == [])
    check("gm_gm heat reset to 0", heat["intensity"] == 0,
          heat["intensity"])
    check("another team's record untouched",
          rs.gm_gm_respect(lg, tz, tq) == 70,
          rs.gm_gm_respect(lg, tz, tq))


def test_d48_decay_wiring():
    print("== D48: decay wired at deadline + season end (main.py) ==")
    with open("/home/hatch/workspace/wt-wave-b/main.py") as f:
        src = f.read()
    check("decay_gm_respect referenced at least twice",
          src.count("decay_gm_respect") >= 2,
          src.count("decay_gm_respect"))
    check("deadline hook present",
          "Wave B D48: deadline respect decay" in src)
    check("season-end hook present",
          "Wave B D48: season-end respect decay" in src)


# ---------------------------------------------------------------- D20
def test_d20_hire_replacement_gm():
    print("== D20: _hire_replacement_gm ==")
    mgr = atm.AITeamManager()
    old = mkstaff("Old", "GM", 40)
    teamx = SimpleNamespace(team_name="X", gm_name="Old GM",
                            staff=[old], roster=[])
    pool = [mkstaff("Low", "Hire", 60), mkstaff("Top", "Hire", 80),
            mkstaff("Mid", "Hire", 70),
            mkstaff("Scout", "Guy", 99, StaffRole.HEAD_SCOUT)]
    lg = SimpleNamespace(teams=[teamx], free_agent_staff=list(pool),
                         season_year=2026)
    mgr._league_ref = lg
    with patch("random.choice", side_effect=lambda xs: xs[0]):
        new = mgr._hire_replacement_gm(teamx)
    check("highest-rep GM hired", new.first_name == "Top", new.first_name)
    check("old GM returned to the pool", old in lg.free_agent_staff)
    check("new hire removed from the pool",
          new not in lg.free_agent_staff)
    check("staff synced", new in teamx.staff and old not in teamx.staff)
    check("gm_name synced to hire",
          teamx.gm_name == "Top Hire", teamx.gm_name)
    check("nhl assignment", getattr(new, "assignment", None) == "nhl")
    check("news recorded",
          any("Top Hire" in str(n) for n in mgr._pending_news),
          mgr._pending_news)
    check("non-GM staff never hired",
          all(s.first_name != "Scout" for s in teamx.staff))


def test_d20_hire_empty_pool():
    print("== D20: empty pool -> None (no phantom GM) ==")
    mgr = atm.AITeamManager()
    old = mkstaff("Old", "GM", 40)
    teamx = SimpleNamespace(team_name="X", gm_name="Old GM",
                            staff=[old], roster=[])
    lg = SimpleNamespace(teams=[teamx], free_agent_staff=[],
                         season_year=2026)
    mgr._league_ref = lg
    with patch("random.choice", side_effect=lambda xs: xs[0]):
        new = mgr._hire_replacement_gm(teamx)
    check("returns None", new is None, new)
    check("old GM parked back in the pool", old in lg.free_agent_staff)
    check("gm_name unchanged", teamx.gm_name == "Old GM")


def test_d20_hire_name_fallback():
    print("== D20: old GM found by gm_name when staff record missing ==")
    mgr = atm.AITeamManager()
    coach = mkstaff("Coach", "Guy", 55, StaffRole.HEAD_COACH)
    teamx = SimpleNamespace(team_name="X", gm_name="Old GM",
                            staff=[coach], roster=[])
    lg = SimpleNamespace(teams=[teamx],
                         free_agent_staff=[mkstaff("New", "Guy", 75)],
                         season_year=2026)
    mgr._league_ref = lg
    with patch("random.choice", side_effect=lambda xs: xs[0]):
        new = mgr._hire_replacement_gm(teamx)
    check("new GM hired", new.first_name == "New")
    check("coach left alone", coach in teamx.staff)


def test_d20_firing_branch():
    print("== D20: gm_fired branch of _weekly_board_review ==")
    mgr = atm.AITeamManager()
    old = mkstaff("Old", "GM", 40)
    newgm = mkstaff("New", "Guy", 75)
    teamx = SimpleNamespace(team_name="X", gm_name="Old GM",
                            staff=[old], roster=[])
    teamy = SimpleNamespace(team_name="Y", gm_name="Other GM",
                            staff=[], roster=[])
    lg = SimpleNamespace(teams=[teamx, teamy],
                         free_agent_staff=[newgm], season_year=2026)
    mgr._league_ref = lg
    mgr.gm_security["X"] = SimpleNamespace(
        gm_fired=True, owner_warning=True, confidence=20.0, hot_seat=True,
        tenured_winner=False)
    mgr.gm_identities["X"] = SimpleNamespace(team_name="X",
                                             gm_name="Old GM")
    rs._bump_gm_respect(lg, teamx, teamy, +20)     # 70, then reset
    with patch("ai_team_management.update_job_security",
               lambda *a, **k: None), \
         patch.object(mgr, "_generate_team_strategy",
                      return_value=SimpleNamespace()), \
         patch("random.choice", side_effect=lambda xs: xs[0]):
        mgr._weekly_board_review(teamx, date(2026, 10, 1))
    sec = mgr.gm_security["X"]
    check("new GM hired", teamx.gm_name == "New Guy", teamx.gm_name)
    check("old GM in the pool", old in lg.free_agent_staff)
    check("respect ledger reset to wary prior",
          rs.gm_gm_respect(lg, teamx, teamy) == 42,
          rs.gm_gm_respect(lg, teamx, teamy))
    check("security re-armed", sec.gm_fired is False and
          sec.owner_warning is False and sec.confidence == 55.0 and
          sec.hot_seat is False,
          (sec.gm_fired, sec.owner_warning, sec.confidence, sec.hot_seat))
    check("identity rebuilt from the new hire",
          mgr.gm_identities["X"].gm_name == teamx.gm_name,
          mgr.gm_identities["X"].gm_name)
    check("firing news recorded",
          any("fired" in str(n).lower() and "Old GM" in str(n)
              for n in mgr._pending_news),
          mgr._pending_news)
    check("firing news precedes hire news",
          [i for i, n in enumerate(mgr._pending_news)
           if "fired" in str(n).lower()][0]
          < [i for i, n in enumerate(mgr._pending_news)
             if "hired" in str(n).lower()][0],
          mgr._pending_news)
    check("hire news recorded",
          any("hired" in str(n).lower() and "New Guy" in str(n)
              for n in mgr._pending_news),
          mgr._pending_news)


# ---------------------------------------------------------------- main
def run_all():
    test_d48_tunables()
    test_d48_baseline()
    test_d48_tiers()
    test_d48_decay_asymmetric()
    test_d48_decay_converges()
    test_d48_diminishing_returns()
    test_d48_recency()
    test_d48_no_fleece_sting()
    test_d48_trend()
    test_d48_inbox_note()
    test_d48_reset_on_hire()
    test_d48_decay_wiring()
    test_d20_hire_replacement_gm()
    test_d20_hire_empty_pool()
    test_d20_hire_name_fallback()
    test_d20_firing_branch()


if __name__ == "__main__":
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        run_all()
    out = buf.getvalue()
    print(out)
    print("%d passed, %d failed" % (out.count("PASS: "),
                                   out.count("FAIL: ")))
    if FAILURES:
        print("FAILURES:", FAILURES)
        sys.exit(1)
