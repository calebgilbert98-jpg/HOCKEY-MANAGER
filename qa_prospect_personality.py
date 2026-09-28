"""QA: newly generated prospects get a real mix of personalities.

Covers: every prospect gets a locked personality blend (drama / temper /
difficulty as separate axes); each draft class is diverse; the class tilt
shifts the mix; re-entries keep their dealt identity; the deal is
one-time (idempotent); all reshaped traits stay in bounds.
"""
import random
import sys

sys.path.insert(0, "/home/hatch/workspace/hockey-push/HOCKEY-MANAGER")

from draft_generator import create_prospect, generate_draft_class
import reputation_system as rs
from player_generator import PlayerGenerator

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name} {detail}")


def temper_of(p):
    aggr = p.aggressiveness
    comp = p.composure
    if max(aggr, comp) <= 20:
        aggr, comp = aggr * 5, comp * 5
    return aggr * 0.6 + (100 - comp) * 0.4


# ---------------------------------------------------------------- every
# prospect gets a locked blend
random.seed(20260928)
batch = [create_prospect() for _ in range(60)]
check("every prospect has int base_controversy",
      all(isinstance(getattr(p, "base_controversy", None), int)
          and 0 <= p.base_controversy <= 100 for p in batch))
check("every prospect has 1-100 selfishness",
      all(1 <= getattr(p, "selfishness", 0) <= 99 for p in batch))
check("every prospect carries a blend fingerprint",
      all(getattr(p, "personality_blend", "") in rs._GENERATION_BLENDS
          for p in batch))
check("reshaped traits in bounds",
      all(1 <= getattr(p, a) <= 99
          for p in batch
          for a in ("discipline", "composure", "aggressiveness",
                    "teamwork", "selfishness")))

# ---------------------------------------------------------------- diversity
random.seed(7)
cls = [create_prospect() for _ in range(224)]
blends = {getattr(p, "personality_blend", "") for p in cls}
check("a class shows at least 4 distinct blends", len(blends) >= 4,
      f"got {sorted(blends)}")
dramas = [p.base_controversy for p in cls]
mean_d = sum(dramas) / len(dramas)
var_d = sum((d - mean_d) ** 2 for d in dramas) / len(dramas)
check("drama is spread, not flat", var_d > 120, f"var {var_d:.1f}")
check("class has a tough sell",
      any(getattr(p, "personality_blend", "") == "tough_sell" for p in cls))
check("class has a saint-hothead",
      any(getattr(p, "personality_blend", "") == "saint_hothead"
          for p in cls))
check("class has a showman",
      any(getattr(p, "personality_blend", "") == "showman" for p in cls))
check("class has a volatile",
      any(getattr(p, "personality_blend", "") == "volatile" for p in cls))
# combos, not labels: saint-hothead reads low drama + high temper
sh = [p for p in cls
      if getattr(p, "personality_blend", "") == "saint_hothead"
      and not getattr(p, "personality_twist", "")]
check("saint-hothead: low drama, high temper",
      all(p.base_controversy < 40 and temper_of(p) >= 65 for p in sh),
      f"n={len(sh)}")
ts = [p for p in cls
      if getattr(p, "personality_blend", "") == "tough_sell"]
check("tough-sell: low drama, high selfishness, low teamwork",
      all(p.base_controversy < 40 and p.selfishness >= 65 and p.teamwork < 55
          for p in ts), f"n={len(ts)}")

# ------------------------------------------------------------- class tilt
def _temper_high(p):
    _b = getattr(p, "personality_blend", "")
    _t = getattr(p, "personality_twist", "")
    return _b in ("saint_hothead", "volatile") or _t in (
        "hidden_temper", "spotlight_bite", "thin_skin")

for _seed in (99, 1234):
    random.seed(_seed)
    _fiery = [create_prospect(personality_tilt="fiery") for _ in range(600)]
    random.seed(_seed)
    _plain = [create_prospect() for _ in range(600)]
    _cf = sum(1 for p in _fiery if _temper_high(p))
    _cp = sum(1 for p in _plain if _temper_high(p))
    check(f"fiery class runs hotter (seed {_seed})", _cf > _cp,
          f"fiery {_cf} vs plain {_cp}")

random.seed(1234)
tilts = [rs.roll_class_tilt() for _ in range(400)]
check("most classes are neutral",
      tilts.count(None) >= 180, f"neutral {tilts.count(None)}/400")
check("every tilt value appears across classes",
      all(t in tilts for t in ("fiery", "circus", "sulky", "professional")))

# ------------------------------------------------- re-entries keep theirs
random.seed(31337)
vet_prospect = create_prospect()
locked = vet_prospect.base_controversy
blend0 = vet_prospect.personality_blend
random.seed(555)
out = generate_draft_class(num_prospects=6, reentries=[vet_prospect])
kept = [p for p in out if p is vet_prospect]
check("re-entry survives the class", len(kept) == 1)
check("re-entry keeps locked personality",
      kept and kept[0].base_controversy == locked
      and kept[0].personality_blend == blend0,
      f"{getattr(kept[0], 'base_controversy', '?') if kept else '?'} vs "
      f"{locked}")

# legacy re-entry with no personality gets one dealt, once
random.seed(777)
legacy = create_prospect()
del legacy.base_controversy
legacy.personality_blend = "professional"
before = legacy.base_controversy if hasattr(legacy, "base_controversy") \
    else None
random.seed(778)
out2 = generate_draft_class(num_prospects=6, reentries=[legacy])
kept2 = [p for p in out2 if p is legacy]
check("legacy re-entry gets a personality",
      kept2 and isinstance(kept2[0].base_controversy, int),
      f"before={before}")

# ------------------------------------------------------------- idempotent
random.seed(4242)
p = create_prospect()
b0, d0 = p.base_controversy, p.personality_blend
traits0 = (p.discipline, p.composure, p.aggressiveness, p.teamwork,
           p.selfishness)
rs.deal_generation_blend(p, tilt="fiery")
check("second deal keeps locked controversy", p.base_controversy == b0)
check("second deal keeps blend fingerprint", p.personality_blend == d0)
check("second deal touches no traits",
      (p.discipline, p.composure, p.aggressiveness, p.teamwork,
       p.selfishness) == traits0)

# ------------------------------------------------------- create_player too
random.seed(818)
gen = PlayerGenerator()
gp = gen.create_player(skill_tier="NHL_DEPTH", age_category="PRIME")
check("create_player deals a blend",
      getattr(gp, "personality_blend", "") in rs._GENERATION_BLENDS)
check("create_player locks controversy",
      isinstance(getattr(gp, "base_controversy", None), int))


# ------------------------------------------------------- wildcards: rare
random.seed(20260601)
wild_batch = [create_prospect() for _ in range(2000)]
wild_rate = sum(1 for p in wild_batch
                if getattr(p, "personality_twist", "")) / len(wild_batch)
check("wildcards are rare but present",
      0.01 <= wild_rate <= 0.10, f"rate {wild_rate:.3f}")
check("every twist is legal for its blend",
      all(getattr(p, "personality_twist", "") in
          rs._WILDCARD_TWISTS.get(getattr(p, "personality_blend", ""), ())
          or not getattr(p, "personality_twist", "")
          for p in wild_batch))

# ------------------------------------------------- wildcards: still coherent
_old_chance = rs._WILDCARD_CHANCE
rs._WILDCARD_CHANCE = 1.0
try:
    random.seed(99)
    forced = [create_prospect() for _ in range(120)]
finally:
    rs._WILDCARD_CHANCE = _old_chance
check("forced deal always twists",
      all(getattr(p, "personality_twist", "") for p in forced))
check("forced twists stay in bounds",
      all(1 <= getattr(p, a) <= 99
          for p in forced
          for a in ("discipline", "composure", "aggressiveness",
                    "teamwork", "selfishness")))
_ht = [p for p in forced
       if getattr(p, "personality_twist", "") == "hidden_temper"]
check("hidden temper: low drama, high temper",
      all(p.base_controversy < 40 and temper_of(p) >= 65 for p in _ht),
      f"n={len(_ht)}")
_qe = [p for p in forced
       if getattr(p, "personality_twist", "") == "quiet_edge"]
check("quiet edge: low drama, high selfishness",
      all(p.base_controversy < 40 and p.selfishness >= 65 for p in _qe),
      f"n={len(_qe)}")
_pe = [p for p in forced
       if getattr(p, "personality_twist", "") == "public_edge"]
check("public edge: drama reads now",
      all(p.base_controversy >= 40 for p in _pe), f"n={len(_pe)}")
check("twist fingerprint never overwrites the blend",
      all(getattr(p, "personality_blend", "") in rs._GENERATION_BLENDS
          for p in forced))

print(f"\nQA prospect_personality: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
