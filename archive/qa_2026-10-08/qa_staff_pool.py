"""QA: staff pool expansion — size, diversity, philosophy, load time."""
import sys, time, random
sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("== Staff pool expansion ==")
random.seed(42)

from database_generator import DatabaseGenerator, HIREABLE_STAFF_ROLES
from game_classes import StaffRole

gen = DatabaseGenerator.__new__(DatabaseGenerator)

# 1. Pool size
t0 = time.time()
pool = gen._generate_free_agent_staff(450)
gen_time = time.time() - t0
check(f"pool size >= 420 (got {len(pool)})", len(pool) >= 420)
check(f"generation fast (<2s, got {gen_time:.2f}s)", gen_time < 2.0)

# 2. Per-role depth
from collections import Counter
roles = Counter(s.role for s in pool)
check(f"HEAD_COACH >= 25 (got {roles[StaffRole.HEAD_COACH]})",
      roles[StaffRole.HEAD_COACH] >= 25)
check(f"GENERAL_MANAGER >= 20 (got {roles[StaffRole.GENERAL_MANAGER]})",
      roles[StaffRole.GENERAL_MANAGER] >= 20)
check(f"HEAD_SCOUT >= 20 (got {roles[StaffRole.HEAD_SCOUT]})",
      roles[StaffRole.HEAD_SCOUT] >= 20)
# Every hireable role has at least 8
thin = [r for r in HIREABLE_STAFF_ROLES if roles[r] < 8]
check(f"no thin roles (thin: {[r.value for r in thin]})", not thin)

# 3. Philosophy diversity
coaches = [s for s in pool if s.role == StaffRole.HEAD_COACH]
phils = Counter(getattr(s, "coaching_philosophy", "") for s in coaches)
check(f"HC philosophies diverse ({dict(phils)})",
      len([p for p in phils if p]) >= 4)
gms = [s for s in pool if s.role == StaffRole.GENERAL_MANAGER]
gstyles = Counter(getattr(s, "gm_style", "") for s in gms)
check(f"GM styles diverse ({dict(gstyles)})",
      len([g for g in gstyles if g]) >= 4)

# 4. Philosophy coherence: defensive coaches actually defend better
d_coaches = [s for s in coaches if s.coaching_philosophy == "defensive"]
o_coaches = [s for s in coaches if s.coaching_philosophy == "offensive"]
if d_coaches and o_coaches:
    d_avg = sum(s.defensive_coaching for s in d_coaches) / len(d_coaches)
    o_avg_d = sum(s.defensive_coaching for s in o_coaches) / len(o_coaches)
    check(f"defensive coaches defend better ({d_avg:.0f} vs {o_avg_d:.0f})",
          d_avg > o_avg_d)
    o_avg = sum(s.attacking_coaching for s in o_coaches) / len(o_coaches)
    d_avg_a = sum(s.attacking_coaching for s in d_coaches) / len(d_coaches)
    check(f"offensive coaches attack better ({o_avg:.0f} vs {d_avg_a:.0f})",
          o_avg > d_avg_a)

# 5. Ratings spread: elites, solid, projects all present
reps = [s.reputation for s in pool]
check(f"elites present (90+: {sum(1 for r in reps if r >= 85)})",
      any(r >= 85 for r in reps))
check(f"projects present (<55: {sum(1 for r in reps if r < 55)})",
      any(r < 55 for r in reps))

# 6. Age variety
ages = [s.age for s in pool]
check(f"young innovators present (<38: {sum(1 for a in ages if a < 38)})",
      any(a < 38 for a in ages))
check(f"veterans present (>58: {sum(1 for a in ages if a > 58)})",
      any(a > 58 for a in ages))

# 7. Serialization round-trip (save/load safe)
try:
    import pickle
    t0 = time.time()
    blob = pickle.dumps(pool, protocol=pickle.HIGHEST_PROTOCOL)
    ser_time = time.time() - t0
    size_kb = len(blob) / 1024
    check(f"pool serializes ({size_kb:.0f}KB)", size_kb < 2000)
    check(f"serialization fast (<1s, got {ser_time:.2f}s)", ser_time < 1.0)
    back = pickle.loads(blob)
    check(f"round-trip preserves count ({len(back)})", len(back) == len(pool))
    # Philosophy survives
    b_phils = {getattr(s, "coaching_philosophy", "") for s in back
               if s.role == StaffRole.HEAD_COACH}
    check(f"philosophy survives round-trip ({len(b_phils)} distinct)",
          len(b_phils) >= 4)
except Exception as e:
    check(f"serialization (exc: {e})", False)

# 8. Never raises on garbage
try:
    empty = gen._generate_free_agent_staff(0)
    check("zero count doesn't crash", isinstance(empty, list))
except Exception as e:
    check(f"zero count (exc: {e})", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
