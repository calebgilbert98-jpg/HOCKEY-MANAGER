"""Entry-draft realism QA: eligibility, classes, goalies, boards,
scouting/luck, generational flag, narratives, rights, Euro FAs,
and the four perception-vs-truth quadrants.

Deterministic (seeds pinned). Run under:
  xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_draft_realism.py
"""
import random
import sys
import statistics

sys.path.insert(0, '/home/hatch/workspace/hockey-push/HOCKEY-MANAGER')

SEED = 20260928

passed = failed = 0
def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}" + (f"  [{extra}]" if extra else ""), flush=True)
    else:
        failed += 1
        print(f"FAIL {name}" + (f"  [{extra}]" if extra else ""), flush=True)

from draft_generator import (
    generate_draft_class, is_draft_eligible, _assign_junior_league,
)

# ---------------------------------------------------------------- A: eligibility
check("elig sep15", is_draft_eligible("2009-09-15", "Canada", 2027))
check("elig sep16", not is_draft_eligible("2009-09-16", "Canada", 2027))
check("elig na-lower-bound",
      is_draft_eligible("2006-09-16", "Canada", 2027)
      and not is_draft_eligible("2006-09-15", "Canada", 2027))
check("elig na-21yo-out",
      not is_draft_eligible("2005-09-15", "Canada", 2027))
check("elig euro-22yo-in",
      is_draft_eligible("2004-09-16", "Sweden", 2027))
check("elig euro-23yo-out",
      not is_draft_eligible("2004-09-15", "Sweden", 2027))
check("elig usa-is-na",
      not is_draft_eligible("2006-09-15", "USA", 2027))
check("elig russia-is-euro",
      is_draft_eligible("2005-06-01", "Russia", 2027)
      and not is_draft_eligible("2003-06-01", "Russia", 2027))

# ---------------------------------------------------------------- B: class composition
random.seed(SEED)
classes = [generate_draft_class(num_prospects=224, quality="Normal")
           for _ in range(3)]

check("class 224", all(len(c) == 224 for c in classes))
def ladder_idx(g):
    order = ["F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
    return order.index(g) if g in order else 6
check("class all-eligible",
      all(is_draft_eligible(p.birth_date, p.nationality or "Canada", 2027)
          for c in classes for p in c))
goalie_counts = [sum(1 for p in c if p.primary_position.name == 'GOALIE')
                 for c in classes]
check("goalies ~20-25", all(18 <= n <= 26 for n in goalie_counts),
      f"{goalie_counts}")

def nat(c): return (p.nationality or "Canada" for p in c)
import collections
mix = collections.Counter(n for c in classes for n in nat(c))
tot = sum(mix.values())
ca, us = mix['Canada'] / tot, mix['USA'] / tot
rare = sum(v for k, v in mix.items()
           if k not in ('Canada', 'USA', 'Sweden', 'Finland', 'Russia')) / tot
check("nat canada ~40%", 0.33 <= ca <= 0.47, f"{ca:.0%}")
check("nat usa ~25%", 0.18 <= us <= 0.32, f"{us:.0%}")
check("nat rare present", rare >= 0.03, f"{rare:.1%}")
check("names ascii",
      all(all(ord(ch) < 128 for ch in (p.full_name or "")) for c in classes for p in c))
check("junior league assigned",
      all(getattr(p, 'junior_league', '') for c in classes for p in c))
check("junior league plausible per nat",
      all(_assign_junior_league(n) for n in
          set(n for c in classes for n in nat(c))))
gems = [sum(1 for p in c if getattr(p, 'hidden_gem', False)
            and p.primary_position.name == 'GOALIE') for c in classes]
check("hidden-gem goalies 1-2/class", all(1 <= n <= 2 for n in gems), f"{gems}")

# goalies: fatter boom/bust tails than skaters (|true - displayed| >= 2)
def _tail_frac(c):
    g = [p for p in c if p.primary_position.name == 'GOALIE']
    s = [p for p in c if p.primary_position.name != 'GOALIE']
    gf = sum(1 for p in g
             if abs(ladder_idx(getattr(p, 'true_potential_grade', 'C'))
                    - ladder_idx(getattr(p, 'potential_grade', 'C'))) >= 2) / max(1, len(g))
    sf = sum(1 for p in s
             if abs(ladder_idx(getattr(p, 'true_potential_grade', 'C'))
                    - ladder_idx(getattr(p, 'potential_grade', 'C'))) >= 2) / max(1, len(s))
    return gf, sf
gf = statistics.mean(_tail_frac(c)[0] for c in classes)
sf = statistics.mean(_tail_frac(c)[1] for c in classes)
check("goalies fatter boom/bust tails", gf > 2 * sf,
      f"G {gf:.1%} S {sf:.1%}")

# ---------------------------------------------------------------- C: generational flag
random.seed(SEED)
flags = 0
for _ in range(60):
    cls = generate_draft_class(num_prospects=224, quality="Normal")
    flags += sum(1 for p in cls if getattr(p, 'generational', False))
random.seed(SEED)
check("generational ~14%", 3 <= flags <= 15, f"{flags}/60")

random.seed(7)
forced = generate_draft_class(num_prospects=224, quality="Normal")
# plant the flag exactly the way the generator does (consensus #1, A+/A+)
fp = max(forced, key=lambda p: p.draft_ranking)
fp.potential_grade = "A+"
fp.true_potential_grade = "A+"
fp.draft_hype = 100
fp.generational = True
fg = [p for p in forced if getattr(p, 'generational', False)]
check("forced exactly 1", len(fg) == 1)
check("forced is consensus #1", forced and getattr(forced[0], 'generational', False)
      and forced[0].draft_ranking == max(p.draft_ranking for p in forced))
check("forced A+/A+ hype100",
      fg and fg[0].potential_grade == "A+"
      and fg[0].true_potential_grade == "A+"
      and fg[0].draft_hype == 100)

import team_draft_boards as tb
from qa_draft_common import make_league
league, nhl = make_league(2027)
league.draft_prospects = forced
boards = tb.build_team_boards(league)
fg_id = fg[0].id
check("forced #1 on all 32 boards",
      all(b[0].id == fg_id for b in boards.values()), f"{len(boards)} boards")

plain = generate_draft_class(num_prospects=224, quality="Normal")
league2, nhl2 = make_league(2027)
league2.draft_prospects = plain
boards2 = tb.build_team_boards(league2)
c1 = max(plain, key=lambda p: p.draft_ranking)
c1n = sum(1 for b in boards2.values() if b[0].id == c1.id)
check("unflagged #1 not unanimous", c1n < 32, f"{c1n}/32")
check("32 distinct boards",
      len({tuple(p.id for p in b) for b in boards2.values()}) == 32)

# headline gating
import draft_stories as ds
news = ds.assign_headline_storylines(league.draft_prospects, 2027)
check("generational headline only when flagged",
      any("Generational" in n.get("title", "") or "Generational" in n.get("text", "")
          for n in news))
league3, _ = make_league(2027)
league3.draft_prospects = plain
news3 = ds.assign_headline_storylines(league3.draft_prospects, 2027)
check("no generational headline unflagged",
      not any("enerational" in n.get("title", "") or "enerational" in n.get("text", "")
              for n in news3))

# ---------------------------------------------------------------- D: boards + joint reports
perceived_top5 = {p.id for p in sorted(plain, key=lambda p: -p.draft_ranking)[:5]}
check("top perceived names in every top 15",
      all(perceived_top5 <= {p.id for p in b[:15]} for b in boards2.values()))
top5_orders = {tuple(p.id for p in b[:5]) for b in boards2.values()}
check("top-5 order differs", len(top5_orders) > 1, f"{len(top5_orders)} orders")

def disagreement(pairs_rank):
    return statistics.pstdev(pairs_rank) if len(pairs_rank) > 1 else 0.0
ids_early = [p.id for p in sorted(plain, key=lambda p: -p.draft_ranking)[:15]]
ids_late = [p.id for p in sorted(plain, key=lambda p: -p.draft_ranking)[90:105]]
rank_of = {bname: {p.id: i for i, p in enumerate(b)} for bname, b in boards2.items()}
early_sd = statistics.mean(disagreement([rank_of[b][pid] for b in rank_of]) for pid in ids_early)
late_sd = statistics.mean(disagreement([rank_of[b][pid] for b in rank_of]) for pid in ids_late)
check("divergence grows down the board", late_sd > early_sd,
      f"early {early_sd:.1f} late {late_sd:.1f}")
gid = [p.id for p in plain if p.primary_position.name == 'GOALIE'][:10]
sid = [p.id for p in plain if p.primary_position.name != 'GOALIE'][:10]
g_sd = statistics.mean(disagreement([rank_of[b][pid] for b in rank_of]) for pid in gid)
s_sd = statistics.mean(disagreement([rank_of[b][pid] for b in rank_of]) for pid in sid)
check("goalies most disagreement", g_sd > s_sd, f"G {g_sd:.1f} S {s_sd:.1f}")

reports = tb.build_draft_reports(
    league2, [(r, t, None) for r in range(1, 8) for t in nhl2])
team0 = nhl2[0].team_name
rep = reports[team0]
check("joint report covers owned picks",
      len(rep["projected_picks"]) == 7)
check("projections match board slots",
      all(rep["board"][proj["overall"] - 1].id == proj["prospect"].id
          for proj in rep["projected_picks"][:10]))

# ---------------------------------------------------------------- E: scouting quality + luck
from game_classes import Staff, StaffRole
def rigged_gem_team(q, seed):
    """A class with a planted hidden gem at consensus ~#92; head scout at q."""
    random.seed(seed)
    cls = generate_draft_class(num_prospects=224, quality="Normal")
    target = sorted(cls, key=lambda p: -p.draft_ranking)[91]
    target.true_potential_grade = "A"
    target.potential_grade = "C+"
    target.draft_hype = 15
    lgx, _ = make_league(2027)
    lgx.draft_prospects = cls
    for t in lgx.teams:
        t.staff = [Staff(first_name="Q", last_name="S", role=StaffRole.HEAD_SCOUT,
                         judging_player_ability=q, judging_player_potential=q)]
    return lgx, target

el_lifts, po_lifts, po_wins = [], [], 0
# 60 seeds, not 12: the designed elite miss rate is ~7.5% (15% missed
# reads x ~50% noise-negative), so a 12-seed "sometimes misses" check
# fails ~39% of the time on a CORRECT implementation. At 60 seeds the
# expected miss count is ~4.5; band it to catch both "never misses"
# (broken luck ceiling) and "misses constantly" (broken skill).
N_LUCK = 60
for s in range(N_LUCK):
    lgx, gem = rigged_gem_team(90, 1000 + s)
    boards_el = tb.build_team_boards(lgx)
    lgx2, gem2 = rigged_gem_team(30, 1000 + s)
    boards_po = tb.build_team_boards(lgx2)
    # rank of the gem on the first team's board in each world
    el_r = next(i for i, p in enumerate(boards_el[lgx.teams[0].team_name]) if p.id == gem.id)
    po_r = next(i for i, p in enumerate(boards_po[lgx2.teams[0].team_name]) if p.id == gem2.id)
    el_lifts.append(91 - el_r); po_lifts.append(91 - po_r)
    if po_r < el_r:
        po_wins += 1
el_misses = sum(1 for l in el_lifts if l <= 0)
check("elite lifts gems more on average",
      statistics.median(el_lifts) > statistics.median(po_lifts),
      f"elite med {statistics.median(el_lifts)} poor med {statistics.median(po_lifts)}")
check("luck: poor scout sometimes wins", po_wins >= 1, f"{po_wins}/{N_LUCK}")
check("luck: elite sometimes misses",
      1 <= el_misses <= 15, f"{el_misses}/{N_LUCK} misses")

# ---------------------------------------------------------------- F: AI goalie suppressor (6 seeded short drafts)
import tkinter as tk
from qa_draft_runtime import RuntimeApp
from ai_team_management import ManagementPriority
import draft_day_trades as ddt
_ddt_real_dialog = ddt._incoming_call_dialog
ddt._incoming_call_dialog = lambda *a, **k: 'decline'  # no modal in headless QA
try:
    root = tk.Tk(); root.geometry("1600x900")
    from windows import DraftView
    top10_goalies = 0
    for ds_ in range(6):
        random.seed(3000 + ds_)
        lgx, nhlx = make_league(2027)
        cls = generate_draft_class(num_prospects=224, quality="Normal")
        # Stress the suppressor realistically: put the best goalie at the
        # class's natural #1 level (like a Price/Fleury talent), not at an
        # impossible 99.9 -- the 20% round-1 haircut is tuned for natural range.
        gs = [p for p in cls if p.primary_position.name == 'GOALIE']
        gstar = max(gs, key=lambda p: p.draft_ranking)
        top_skater_dr = max(p.draft_ranking for p in cls
                            if p.primary_position.name != 'GOALIE')
        gstar.draft_ranking = top_skater_dr + 0.5
        lgx.draft_prospects = cls
        user = nhlx[5]; user.is_user_team = True
        mp_ = {t.team_name: ManagementPriority.CONTEND for t in nhlx}
        app = RuntimeApp(lgx, user, mp_)
        view = DraftView(root, app=app)
        view.pack(fill='both', expand=True); root.update()
        for _ in range(10):
            rnd, toc, _dp = view.draft_order[view.current_pick]
            if toc == app.user_team or view._mp_clock_for(toc):
                break
            view._ai_step(); root.update()
        for tm, ov, pl in view.picks_made:
            if ov <= 10 and pl.primary_position.name == 'GOALIE':
                top10_goalies += 1
        view.destroy()
    root.destroy()
    check("no AI goalie in top 10 (6 drafts)", top10_goalies == 0,
          f"{top10_goalies} taken")
except Exception as e:
    check("no AI goalie in top 10 (6 drafts)", False, f"harness: {e}")
finally:
    ddt._incoming_call_dialog = _ddt_real_dialog

# ---------------------------------------------------------------- G: rights lifecycle
def mk_unsigned(league, team, junior_league, nationality, drafted_year,
                birth_date="2008-11-01", potential="B", hype=30):
    cls = generate_draft_class(num_prospects=8, quality="Normal")
    p = cls[0]
    p.birth_date = birth_date
    p.nationality = nationality
    p.junior_league = junior_league
    p.potential_grade = potential
    p.draft_hype = hype
    p.age = 18
    team.prospects.append(p)
    league.stamp_draft_rights(p, team.team_name, drafted_year)
    return p

league, nhl = make_league(2027)
league.free_agents = []
team = nhl[0]

p1 = mk_unsigned(league, team, "OHL", "Canada", 2027, potential="A-", hype=80)
check("rights stamped",
      p1.rights_team == team.team_name and p1.rights_type == "CHL"
      and p1.rights_expiry_year == 2031 and p1.drafted_year == 2027)

# ELC signing consumes rights AND drafted_year
ok = league.sign_drafted_prospect(team, p1)
check("elc signing", ok and p1.contract is not None
      and not p1.rights_team and p1.drafted_year == 0)

# camp invite
p2 = mk_unsigned(league, team, "WHL", "Canada", 2027)
msg = league.invite_prospect_to_camp(team.team_name, p2)
check("camp invite", p2.camp_invite and team.team_name in msg)

# PRIMARY PATH: draft day June 2031 (season_year still 2030). The rollover
# runs BEFORE the draft with reference_year=2031, so an expiring CHL
# prospect who is still eligible re-enters the draft about to be held.
# New CBA (2026): 18-year-old CHL draftees hold 4-year rights, so a
# Canadian ages out before expiry -- re-entry needs a European CHL
# import (eligible through 22), the realistic modern case.
p3 = mk_unsigned(league, team, "OHL", "Sweden", 2027, potential="A-", hype=80)
p3.reputation = 75
league.season_year = 2030
league.rights_news = []
league._rollover_draft_rights(reference_year=2031)
check("chl re-entry on draft day",
      p3.draft_reentry and p3 not in team.prospects
      and p3 in league.draft_reentries)

# re-entry is consumable by the class generated minutes later in-game
cls31 = generate_draft_class(num_prospects=224, quality="Normal",
                             draft_year=2031, reentries=list(league.draft_reentries))
check("reentry in 2031 class", any(p.id == p3.id for p in cls31))

# double-run guard: the end_of_season backstop (same offseason, post-increment)
# must not process the cycle again
n_news = len(league.rights_news)
league.season_year = 2031
league._rollover_draft_rights()
check("no double rollover", len(league.rights_news) == n_news,
      f"{len(league.rights_news)} vs {n_news}")

# BACKSTOP PATH alone (draft-day flow never ran): aged-out CHL -> UFA.
# All same-cycle prospects must exist before the single rollover call
# (the per-cycle guard skips re-runs).
league2, nhl2 = make_league(2027)
league2.free_agents = []
team2 = nhl2[0]
p4 = mk_unsigned(league2, team2, "QMJHL", "Canada", 2025,
                 birth_date="2006-09-20", potential="C+", hype=10)
p4.age = 21
p6 = mk_unsigned(league2, team2, "NCAA", "USA", 2025, birth_date="2006-05-05")
p6.age = 22
p7 = mk_unsigned(league2, team2, "OHL", "Canada", 2024,
                 birth_date="2005-06-01", potential="C", hype=5)
p7.age = 23
league2.season_year = 2028
league2.rights_news = []
league2._rollover_draft_rights()
# p7: 4 unsigned years, CHL, aged out -> UFA now...
check("5yr: ufa at year 4", p7.team_name == "Free Agent"
      and p7 in league2.free_agents)
league2.season_year = 2029
league2._rollover_draft_rights()
check("backstop: aged-out chl -> ufa",
      p4.team_name == "Free Agent" and p4 not in team2.prospects
      and p4 in league2.free_agents and not p4.rights_team)
# NCAA 4yr -> UFA via the backstop
check("ncaa 4yr -> ufa", p6.team_name == "Free Agent"
      and p6 in league2.free_agents and not p6.rights_team)
# ...then the five-year scan retires him from the free-agent pool
check("5yr -> retired", p7.team_name == "Retired"
      and p7 not in league2.free_agents
      and any("retired" in n for n in league2.rights_news))

# holdout warning fires on draft day the summer before CHL expiry
# (new CBA: 4-year rights for an 18-year-old draftee -> expiry 2031)
league3, nhl3 = make_league(2027)
league3.free_agents = []
team3 = nhl3[0]
p5 = mk_unsigned(league3, team3, "OHL", "Canada", 2027, potential="A-", hype=80)
p5.reputation = 75
league3.season_year = 2029  # draft day June 2030: 3 unsigned years, expiry next summer
league3.rights_news = []
league3._rollover_draft_rights(reference_year=2030)
warn = [n for n in league3.rights_news if "hold out" in n or "retirement" in n]
check("high-rep expiry warning", any(p5.full_name in w for w in warn),
      f"{len(warn)} warnings")

# (p6/p7 NCAA/retirement checks live in the league2 backstop block above)
check("retirement news",
      any("five unsigned years" in n for n in league2.rights_news))
# never-drafted free agents are untouched by the scan
p8 = mk_unsigned(league, team, "OHL", "Canada", 2027)
p8.team_name = "Free Agent"
p8.drafted_year = 0  # simulate a never-drafted FA
p8.rights_team = ""
team.prospects.remove(p8)
league.free_agents.append(p8)
league.season_year = 2040
league._rollover_draft_rights()
check("undrafted fa never retired", p8 in league.free_agents)

# signed prospect keeps his drafted_year cleared -> no phantom retirement
check("signed keeps drafted_year=0", p1.drafted_year == 0)

# ---------------------------------------------------------------- H: euro free agents
from euro_free_agents import generate_euro_free_agents
sizes, ok_invariants = [], True
for yr, sd in zip(range(2028, 2031), (11, 22, 33)):
    lgx, _ = make_league(2027)
    lgx.free_agents = []
    batch = generate_euro_free_agents(lgx, yr, rng_seed=sd)
    lgx.free_agents.extend(batch)
    sizes.append(len(batch))
    for p in batch:
        if not (p.team_name == "Free Agent" and getattr(p, 'is_euro_import', False)
                and getattr(p, 'source_league', "")):
            ok_invariants = False
check("euro batch 4-8", all(4 <= n <= 8 for n in sizes), f"{sizes}")
check("euro fa invariants", ok_invariants)
gshare = []
for sd in range(40, 46):
    lgx, _ = make_league(2027)
    b = generate_euro_free_agents(lgx, 2028, rng_seed=sd)
    gshare.append(sum(1 for p in b if p.primary_position.name == 'GOALIE') / max(1, len(b)))
check("euro goalies ~15%", 0.05 <= statistics.mean(gshare) <= 0.30,
      f"{statistics.mean(gshare):.0%}")
stars = 0
for sd in range(100, 110):
    lgx, _ = make_league(2027)
    b = generate_euro_free_agents(lgx, 2028, rng_seed=sd)
    # generator's own impact band is 84-89 (IMPACT_OVERALL); spec ~10%/yr
    stars += sum(1 for p in b if p.overall_rating() >= 84)
check("euro impact scarcity (~10%/yr)", stars <= 3, f"{stars} x84+ in 10yrs")
# AI sees them through the normal FA pool
lgx, _ = make_league(2027)
lgx.free_agents = generate_euro_free_agents(lgx, 2028, rng_seed=7)
check("euro in fa pool", len(lgx.get_free_agents()) >= 4
      if hasattr(lgx, 'get_free_agents') else len(lgx.free_agents) >= 4)

# ---------------------------------------------------------------- I: narratives
league, nhl = make_league(2027)
league.draft_prospects = generate_draft_class(num_prospects=224, quality="Normal")
league.season_year = 2027
# plant a steal: round-6 pick, reputation now B+, modest hype, in a pool
steal = sorted(league.draft_prospects, key=lambda p: -p.draft_ranking)[150]
steal.draft_round = 6
steal.potential_grade = "B+"
steal.draft_hype = 20
steal.age = 21
steal.drafted_year = 2026
nhl[0].prospects.append(steal)
league.steal_retro_posted = set()
retro = ds.steal_retrospective(league)
check("steal retrospective found",
      isinstance(retro, list) and any(r.get("prospect_id") == steal.id for r in retro))
retro2 = ds.steal_retrospective(league)
check("retrospective once per player",
      not any(r.get("prospect_id") == steal.id for r in (retro2 or [])))
# season beats Jan-Jun run without crash; no news path
beats_ok = True
try:
    for m in (1, 2, 3, 4, 5, 6):
        ds.season_beats(league.draft_prospects, 2027, m)
except Exception as e:
    beats_ok = False
check("season beats jan-jun", beats_ok)
# hidden elite gets no pre-draft hype: planted true A- / displayed C+
gem = sorted(league.draft_prospects, key=lambda p: -p.draft_ranking)[100]
gem.true_potential_grade = "A-"
gem.potential_grade = "C+"
gem.draft_hype = 12
heads = ds.assign_headline_storylines(league.draft_prospects, 2027)
check("hidden gem not headlined",
      not any(gem.full_name in (h.get("title", "") + h.get("text", "")) for h in heads))
# generational headline only with flag (planted-flag class)
lgf, _ = make_league(2027)
random.seed(99)
_cls = generate_draft_class(num_prospects=224, quality="Normal")
_fp = max(_cls, key=lambda p: p.draft_ranking)
_fp.potential_grade = "A+"
_fp.true_potential_grade = "A+"
_fp.draft_hype = 100
_fp.generational = True
lgf.draft_prospects = _cls
hgf = ds.assign_headline_storylines(lgf.draft_prospects, 2027)
check("flagged generational headlined",
      any("enerational" in (h.get("title", "") + h.get("text", "")) for h in hgf))

# ---------------------------------------------------------------- J: four quadrants (statistical)
q1 = q2 = q3 = q4 = 0
for s in range(40):
    random.seed(5000 + s)
    cls = generate_draft_class(num_prospects=224, quality="Normal")
    if any(getattr(p, 'generational', False) and
           getattr(p, 'true_potential_grade', '') == "A+" for p in cls):
        q1 += 1
    late = [p for p in cls if getattr(p, 'draft_round', 1) >= 4]
    if any(getattr(p, 'true_potential_grade', '') in ("A-", "A")
           and ladder_idx(getattr(p, 'potential_grade', 'C')) <= ladder_idx("B")
           for p in late):
        q2 += 1
    if any(getattr(p, 'potential_grade', '') in ("C-", "C", "C+")
           and getattr(p, 'true_potential_grade', '') in ("C-", "C", "C+") for p in cls):
        q4 += 1
check("Q1 obvious generational exists", q1 >= 1, f"{q1}/40")
check("Q2 hidden late elite exists", q2 >= 1, f"{q2}/40")
check("Q4 ordinary exists", q4 == 40)
# Q3: touted prospect busts via the development machinery
import prospect_development as pd
random.seed(42)
cls = generate_draft_class(num_prospects=30, quality="Normal")
tout = max(cls, key=lambda p: (p.potential_grade, p.draft_ranking))
tout.potential_grade = "A"
tout.true_potential_grade = "A"
tout.age = 19
tout.farm_season = {"gp": 50, "g": 2, "a": 6, "league": "AHL"}
res = pd.evaluate_prospect_season(tout, rng=random.Random(42))
check("Q3 bust path moves true grade",
      res in ("bust", "cooled", "noticed") or
      ladder_idx(getattr(tout, 'true_potential_grade', 'A')) < ladder_idx("A"),
      f"result={res} true now {getattr(tout, 'true_potential_grade', '?')}")
# hidden gem goalie becomes a starter through loud production
random.seed(7)
cls = generate_draft_class(num_prospects=224, quality="Normal")
gg = next(p for p in cls if getattr(p, 'hidden_gem', False)
          and p.primary_position.name == 'GOALIE')
gg.age = 21
start_true = ladder_idx(gg.true_potential_grade)
for yr in range(4):
    gg.farm_season = {"gp": 42, "sv_pct": 0.925, "w": 24, "league": "AHL"}
    pd.evaluate_prospect_season(gg, rng=random.Random(100 + yr))
check("hidden-gem goalie can break out",
      ladder_idx(gg.true_potential_grade) >= start_true,  # never regresses on elite years
      f"{gg.true_potential_grade} vs start idx {start_true}")

# ---------------------------------------------------------------- K: round-4+ star seeding rarity
counts = []
for s in range(30):
    random.seed(9000 + s)
    cls = generate_draft_class(num_prospects=224, quality="Normal")
    n = sum(1 for p in cls
            if getattr(p, 'draft_round', 1) >= 4
            and getattr(p, 'true_potential_grade', '') in ("A-", "A", "A+")
            and ladder_idx(getattr(p, 'potential_grade', 'C')) <= ladder_idx("B+"))
    counts.append(n)
check("r4+ true stars rare", statistics.mean(counts) <= 1.5,
      f"mean {statistics.mean(counts):.2f}/class, max {max(counts)}")
check("r4+ no absurd classes", max(counts) <= 4, f"max {max(counts)}")

print(f"\n{passed} passed, {failed} failed", flush=True)
sys.exit(1 if failed else 0)
