"""QA for playtest bug fixes: P-4 (draft need-boost decay) and P-5 (famous-name blocklist)."""
import os, sys, random
os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")
from types import SimpleNamespace

from draft_night import ai_select_prospect
from draft_generator import get_random_name, _is_famous_real_name, _FAMOUS_REAL_NAMES

POSITIONS = ['LW', 'C', 'RW', 'LD', 'RD', 'G']

def make_prospects(n=12, seed=0):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        pos = POSITIONS[i % len(POSITIONS)]
        out.append(SimpleNamespace(
            id=f"p{i}",
            primary_position=SimpleNamespace(value=pos),
            draft_ranking=100 - i,  # slight spread so noise matters, not rank
        ))
    return out

# --- P-4: need-boost decays by round -------------------------------------
# Team with a glaring RW hole; needs=['RW','C'] every round (the playtest trap).
# Both top-2 need positions get the boost, so measure the combined rate.
round1_need = 0
round7_need = 0
N = 60
for s in range(N):
    avail = make_prospects(seed=s)
    rng = random.Random(1000 + s)
    sel, _, _ = ai_select_prospect(None, list(avail), None, ['RW', 'C'], 1, None, rng)
    if sel.primary_position.value in ('RW', 'C'):
        round1_need += 1
    avail = make_prospects(seed=s)
    rng = random.Random(1000 + s)
    sel, _, _ = ai_select_prospect(None, list(avail), None, ['RW', 'C'], 7, None, rng)
    if sel.primary_position.value in ('RW', 'C'):
        round7_need += 1

print(f"P-4 round-1 need-position rate: {round1_need}/{N} (baseline 2/6 = {N//3}; expect clearly above)")
print(f"P-4 round-7 need-position rate: {round7_need}/{N} (expect ~= baseline {N//3}, pure BPA)")
assert round1_need >= N * 0.5, "round-1 need boost lost!"
assert abs(round7_need - N / 3) <= N * 0.15, f"round-7 not BPA: {round7_need}/{N}"

# And the playtest scenario: 7 straight rounds, same hole every round,
# pool depleting like a real draft (picked players leave the pool).
picks = []
avail = make_prospects(seed=42) * 3  # deep enough pool for 7 picks
for i, p in enumerate(avail):
    p.id = f"p{i}"
for rnd in range(1, 8):
    sel, _, _ = ai_select_prospect(None, list(avail), None, ['RW', 'C'], rnd,
                                   None, random.Random(700 + rnd))
    picks.append(sel.primary_position.value)
    avail = [p for p in avail if p.id != sel.id]
print("P-4 seven-round positions with persistent RW hole:", picks)
assert not all(p == 'RW' for p in picks), "still drafting RW 7 straight times!"
assert picks.count('RW') <= 4, f"RW still over-drafted late: {picks}"

# --- P-5: no famous real names generated ----------------------------------
assert _is_famous_real_name("Mikko", "Rantanen")
assert _is_famous_real_name("Leon", "Draisaitl")
assert not _is_famous_real_name("Mikko", "Virtanen")  # real surname, obscure first: fine
assert len(_FAMOUS_REAL_NAMES) >= 40

seen_famous = 0
for i in range(20000):
    fn, ln = get_random_name("Finland")
    if _is_famous_real_name(fn, ln):
        seen_famous += 1
        print("COLLISION:", fn, ln)
for i in range(20000):
    fn, ln = get_random_name("Germany")
    if _is_famous_real_name(fn, ln):
        seen_famous += 1
        print("COLLISION:", fn, ln)
print(f"P-5 famous-name collisions in 40k generated names: {seen_famous}")
assert seen_famous == 0

# --- P-4b: dynamic pivot -- a need filled early stops pulling ---------
# RW drafted in round 1 (solid early pick): round-2 RW boost must be dead.
pivot_r2_rw = 0
for s in range(N):
    avail = make_prospects(seed=s)
    sel, _, _ = ai_select_prospect(None, list(avail), None, ['RW', 'C'], 2,
                                   None, random.Random(2000 + s),
                                   drafted=[('RW', 1)])
    if sel.primary_position.value == 'RW':
        pivot_r2_rw += 1
print(f"P-4b round-2 RW rate after R1 RW picked: {pivot_r2_rw}/{N} (expect ~= baseline {N//6})")
assert pivot_r2_rw <= N * 0.35, f"pivot failed: still drafting RW: {pivot_r2_rw}/{N}"

# RW drafted in round 3 only: round 4 keeps half boost (2nd RW possible),
# but after two RWs the pivot kills it.
half_r4_rw = 0
for s in range(N):
    avail = make_prospects(seed=s)
    sel, _, _ = ai_select_prospect(None, list(avail), None, ['RW', 'C'], 4,
                                   None, random.Random(3000 + s),
                                   drafted=[('RW', 3)])
    if sel.primary_position.value == 'RW':
        half_r4_rw += 1
dead_r5_rw = 0
for s in range(N):
    avail = make_prospects(seed=s)
    sel, _, _ = ai_select_prospect(None, list(avail), None, ['RW', 'C'], 5,
                                   None, random.Random(4000 + s),
                                   drafted=[('RW', 3), ('RW', 4)])
    if sel.primary_position.value == 'RW':
        dead_r5_rw += 1
print(f"P-4b round-4 RW rate after one R3 RW: {half_r4_rw}/{N} (half boost: between {N//6} and round-1)")
print(f"P-4b round-5 RW rate after two RWs: {dead_r5_rw}/{N} (expect ~= baseline {N//6})")
assert dead_r5_rw <= N * 0.35, f"pivot failed after 2 RWs: {dead_r5_rw}/{N}"

print("ALL PLAYTEST-FIX QA PASSED")
