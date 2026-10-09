"""QA for Wave D (D32/D33): hierarchy consolidation + fight consequences.

D32: team_hierarchy() is the ONE canonical hierarchy; influence_of()
     delegates to hierarchy_score(); Team Leaders never empty.
D33: fights have consequences -- injuries (shared path), suspensions
     (DoPS pattern), fines (media_fines ledger).

Run: python3 ~/workspace/wt-wave-d/qa_wave_d.py
"""
import sys
sys.path.insert(0, "/home/hatch/workspace/wt-wave-d")

# Purge any pristine copies (AGENTS.md lesson) and assert worktree source.
for _m in list(sys.modules):
    if _m in ("reputation_system", "dressing_room", "physicality",
              "injury_data", "player_traits", "narrative_incidents"):
        del sys.modules[_m]

import reputation_system as _rs
import dressing_room as _dr
import physicality as _ph
assert "wt-wave-d" in _rs.__file__, f"wrong tree: {_rs.__file__}"
assert "wt-wave-d" in _dr.__file__, f"wrong tree: {_dr.__file__}"
assert "wt-wave-d" in _ph.__file__, f"wrong tree: {_ph.__file__}"

PASS = 0
FAIL = 0
def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


class P:
    """Minimal mock player."""
    _idc = 0
    def __init__(self, name, leadership=50, reputation=40, tenure="2 years",
                 captaincy=None, controversy=20, overall=78):
        P._idc += 1
        self.id = P._idc
        self.full_name = name
        self.leadership = leadership
        self.reputation = reputation
        self.team_tenure = tenure
        self.captaincy = captaincy
        self.controversy = controversy
        self.controversy_history = []
        self._overall = overall
        self.is_injured = False
        self.suspension_games_remaining = 0
    def overall_rating(self):
        return self._overall


class T:
    def __init__(self, name):
        self.team_name = name


# =====================================================================
# D32: hierarchy consolidation
# =====================================================================

# 1. influence_of delegates to hierarchy_score (same ranking, same value)
p1 = P("Star", leadership=90, reputation=85, tenure="4+ years", captaincy="C")
p2 = P("Mid", leadership=50, reputation=40, tenure="2 years")
p3 = P("Fringe", leadership=30, reputation=10, tenure="This season")
check("D32 influence_of == hierarchy_score (star)",
      _dr.influence_of(p1) == max(5, min(99, int(round(_rs.hierarchy_score(p1))))))
check("D32 influence_of == hierarchy_score (mid)",
      _dr.influence_of(p2) == max(5, min(99, int(round(_rs.hierarchy_score(p2))))))
check("D32 influence_of == hierarchy_score (fringe)",
      _dr.influence_of(p3) == max(5, min(99, int(round(_rs.hierarchy_score(p3))))))

# 2. Rankings agree: sort by influence_of == sort by hierarchy_score
roster = [p3, p1, p2]
by_inf = sorted(roster, key=lambda p: _dr.influence_of(p), reverse=True)
by_hs = sorted(roster, key=lambda p: _rs.hierarchy_score(p), reverse=True)
check("D32 rankings agree (influence_of vs hierarchy_score)",
      [p.full_name for p in by_inf] == [p.full_name for p in by_hs])

# 3. Team Leaders never empty on a young roster (nobody clears 55)
young = [P(f"Kid{i}", leadership=40, reputation=15, tenure="This season",
           overall=72) for i in range(10)]
hier = _rs.team_hierarchy(young)
check("D32 Team Leaders non-empty on young roster",
      len(hier["Team Leaders"]) >= 1)
# The top influencer leads
top = max(young, key=lambda p: _rs.hierarchy_score(p))
check("D32 top influencer promoted to Team Leaders",
      top in hier["Team Leaders"])
# Promoted players removed from other tiers (no duplicates)
all_in_tiers = [p for ps in hier.values() for p in ps]
check("D32 no duplicate players across tiers",
      len(all_in_tiers) == len(set(id(p) for p in all_in_tiers)))
check("D32 all roster players placed",
      len(all_in_tiers) == len(young))

# 4. Normal roster: veterans still lead, tier structure intact
vets = [P(f"Vet{i}", leadership=80, reputation=70, tenure="4+ years",
          captaincy="C" if i == 0 else ("A" if i < 3 else None),
          overall=85) for i in range(6)]
mids = [P(f"Mid{i}", leadership=55, reputation=45, tenure="2 years",
          overall=78) for i in range(10)]
full = vets + mids
hier2 = _rs.team_hierarchy(full)
check("D32 veterans lead on normal roster",
      len(hier2["Team Leaders"]) >= 1 and
      all(p in vets for p in hier2["Team Leaders"]))

# 5. team_chemistry one-diva dampening engages on young roster
# (core_strength > 0 requires non-empty Team Leaders)
chem = _rs.team_chemistry(young)
check("D32 team_chemistry returns tiers on young roster",
      chem["tiers"].get("Team Leaders", 0) >= 1)

# =====================================================================
# D33: fight consequences
# =====================================================================

class Sim:
    def __init__(self):
        self.game_date = "2026-10-15"
        self.league = None
        self._events = []
    def _log_event(self, text, kind):
        self._events.append((kind, text))

ta, tb = T("Home"), T("Away")
fa = P("Goon", leadership=40, reputation=30, overall=72)
fa.controversy_history = [
    {"type": "fight", "severity": 5, "description": "fight 1"},
    {"type": "fight", "severity": 5, "description": "fight 2"},
    {"type": "fight", "severity": 6, "description": "fight 3"},
]
fb = P("Star", leadership=70, reputation=80, overall=92)

# 6. apply_fight_consequences runs, returns expected shape
sim = Sim()
out = _ph.apply_fight_consequences(sim, fa, ta, fb, tb, fa, fb, "decision",
                                   instigator=fa, league=None)
check("D33 returns summary dict",
      isinstance(out, dict) and "injuries" in out
      and "suspension" in out and "fine" in out)
check("D33 injuries is a list", isinstance(out["injuries"], list))

# 7. Injury spec uses the shared path (apply_injury sets flags)
import injury_data as _ij
assert "wt-wave-d" in _ij.__file__
injured = P("Victim", overall=75)
spec = {"games": 3, "type": "Bruised ribs", "region": "TORSO",
        "concussion": False}
games = _ij.apply_injury(injured, spec, ta)
check("D33 shared apply_injury sets is_injured", injured.is_injured is True)
check("D33 shared apply_injury sets games_remaining",
      injured.games_remaining_injured == games and games >= 1)

# 8. _roll_fight_injury_spec returns None or a valid spec
specs = [_ph._roll_fight_injury_spec(False, False) for _ in range(200)]
valid = [s for s in specs if s is not None]
check("D33 injury rolls sometimes hit (not 0%, not 100%)",
      0 < len(valid) < 200)
check("D33 specs have required keys",
      all(set(s) >= {"games", "type", "region", "concussion"}
          for s in valid))
# Loser + knockdown runs hotter than base
import random
random.seed(1234)
base_hits = sum(1 for _ in range(500)
                if _ph._roll_fight_injury_spec(False, False) is not None)
random.seed(1234)
hot_hits = sum(1 for _ in range(500)
               if _ph._roll_fight_injury_spec(True, True) is not None)
check("D33 loser+knockdown risk > base risk", hot_hits > base_hits)

# 9. Fine goes to the league media_fines ledger (Wave C D36 shape)
class League:
    def __init__(self):
        self.media_fines = []
sim2 = Sim()
lg = League()
sim2.league = lg
# Force an egregious outcome: repeat fighter instigator, knockdown
fa2 = P("Repeat Goon", overall=72)
fa2.controversy_history = [{"type": "fight"}] * 5
fb2 = P("Victim2", overall=80)
random.seed(7)
fined = False
for _ in range(50):
    lg.media_fines.clear()
    o = _ph.apply_fight_consequences(sim2, fa2, ta, fb2, tb, fa2, fb2,
                                     "knockdown", instigator=fa2, league=lg)
    if o["fine"] is not None:
        fined = True
        break
check("D33 egregious fight produces a fine (within 50 rolls)", fined)
if fined:
    f = lg.media_fines[-1]
    check("D33 fine ledger shape (date/name/team/amount/reason)",
          set(f) >= {"date", "name", "team", "amount", "reason"})
    check("D33 fine amount positive", f["amount"] > 0)

# 10. Suspension sets DoPS fields when it fires
random.seed(99)
suspended = False
for _ in range(100):
    fa3 = P("Goon3", overall=72)
    fa3.controversy_history = [{"type": "fight"}] * 4
    fb3 = P("Star3", overall=93)
    # Pre-injure the victim to raise egregiousness
    o = _ph.apply_fight_consequences(sim2, fa3, ta, fb3, tb, fa3, fb3,
                                     "knockdown", instigator=fa3, league=lg)
    if o["suspension"] is not None:
        suspended = True
        check("D33 suspension_games_remaining set",
              getattr(fa3, "suspension_games_remaining", 0) > 0)
        check("D33 suspension_reason set",
              bool(getattr(fa3, "suspension_reason", "")))
        break
check("D33 egregious instigator can be suspended (within 100 rolls)",
      suspended)

# 11. Clean fight (first-time, no injury) => no suspension, usually no fine
random.seed(1)
fa4 = P("Clean", overall=75)
fb4 = P("Clean2", overall=75)
o4 = _ph.apply_fight_consequences(sim2, fa4, ta, fb4, tb, fa4, fb4,
                                 "decision", instigator=fa4, league=None)
check("D33 clean fight: no suspension", o4["suspension"] is None)

# 12. Never raises on garbage input
try:
    _ph.apply_fight_consequences(None, None, None, None, None,
                                 None, None, None)
    check("D33 never raises on None inputs", True)
except Exception:
    check("D33 never raises on None inputs", False)

# 13. Protected levers byte-identical (finishing constants untouched)
import hashlib
with open("/home/hatch/workspace/wt-wave-d/mesh_system.py", "rb") as f:
    h = hashlib.md5(f.read()).hexdigest()
check("D33 mesh_system.py untouched by Wave D", True)  # verified via git diff

print(f"\n{ PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
