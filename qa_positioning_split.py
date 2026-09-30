"""QA: positioning-split generation wiring (per Muck 2026-09-28).

Locks: draft prospects and database players get offensive/defensive
positioning from archetype/position; goalies keep the single positioning;
~1.5% unicorns are elite at both ends; old saves (split=None) fall back
to positioning via the mesh helpers.
"""
import sys, random
sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

PASS = 0
FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

import mesh_system as mesh
from draft_generator import create_prospect
from database_generator import DatabaseGenerator, DATABASE_CONFIGURATIONS
from game_classes import PlayerPosition

# 1. Draft prospects: split populated by archetype, goalies excluded
random.seed(99)
arch_off, arch_def = {}, {}
for _ in range(400):
    p = create_prospect(position=PlayerPosition.CENTER)
    a = p.archetype
    arch_off.setdefault(a, []).append(p.offensive_positioning)
    arch_def.setdefault(a, []).append(p.defensive_positioning)
    assert p.offensive_positioning is not None and p.defensive_positioning is not None
check("all skater prospects get the split", True)
if "Sniper" in arch_off and "Grinder" in arch_off:
    s_off = sum(arch_off["Sniper"]) / len(arch_off["Sniper"])
    g_off = sum(arch_off["Grinder"]) / len(arch_off["Grinder"])
    check(f"snipers out-position grinders offensively ({s_off:.0f}>{g_off:.0f})",
          s_off > g_off + 5, f"{s_off:.1f} vs {g_off:.1f}")
    s_def = sum(arch_def["Sniper"]) / len(arch_def["Sniper"])
    g_def = sum(arch_def["Grinder"]) / len(arch_def["Grinder"])
    check(f"grinders out-position snipers defensively ({g_def:.0f}>{s_def:.0f})",
          g_def > s_def + 3, f"{g_def:.1f} vs {s_def:.1f}")
g = create_prospect(position=PlayerPosition.GOALIE)
check("goalie keeps single positioning (no split)",
      g.offensive_positioning is None and g.defensive_positioning is None
      and g.positioning is not None)

# 2. Unicorn rate ~1.5% (Bergeron/Coffey mold: both ends high)
random.seed(7)
n = sum(1 for _ in range(20000)
        if (lambda p: p.offensive_positioning >= 70
            and p.defensive_positioning >= 70)(
            create_prospect(position=PlayerPosition.CENTER)))
rate = n / 20000
check(f"unicorn-ish rate sane ({rate:.2%})", 0.002 < rate < 0.03, f"{rate:.3%}")

# 3. Database generator: position-tilted split on the 100-scale
gen = DatabaseGenerator(DATABASE_CONFIGURATIONS["Small"])
random.seed(21)
fw = [gen._create_enhanced_player(26, PlayerPosition.CENTER, 1.0) for _ in range(60)]
dm = [gen._create_enhanced_player(26, PlayerPosition.LEFT_DEFENSE, 1.0) for _ in range(60)]
fw_off = sum(p.offensive_positioning for p in fw) / 60
fw_def = sum(p.defensive_positioning for p in fw) / 60
dm_off = sum(p.offensive_positioning for p in dm) / 60
dm_def = sum(p.defensive_positioning for p in dm) / 60
check(f"DB forwards tilt offensive ({fw_off:.0f}>{fw_def:.0f})", fw_off > fw_def + 5)
check(f"DB defense tilt defensive ({dm_def:.0f}>{dm_off:.0f})", dm_def > dm_off + 5)
check("DB split in 1-100 for all",
      all(1 <= p.offensive_positioning <= 100 and 1 <= p.defensive_positioning <= 100
          for p in fw + dm))
gl = gen._create_enhanced_player(26, PlayerPosition.GOALIE, 1.0)
check("DB goalie keeps single positioning",
      gl.offensive_positioning is None and gl.defensive_positioning is None)

# 4. Old-save fallback: split=None -> mesh helpers read `positioning`
class _Old: pass
o = _Old(); o.positioning = 77
o.offensive_positioning = None; o.defensive_positioning = None
check("mesh offensive_positioning falls back to positioning",
      mesh.offensive_positioning(o) == 77)
check("mesh defensive_positioning falls back to positioning",
      mesh.defensive_positioning(o) == 77)

print(f"\nPASS: {PASS}  FAIL: {FAIL}")
sys.exit(1 if FAIL else 0)
