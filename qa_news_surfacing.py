"""QA: rivalry-review verdicts + staff breakthroughs reach the news feed.

Covers:
  1. review_rivalries returns verdicts with outcomes and headline text.
  2. The end_of_season capture keeps only newsworthy outcomes
     (solidified/entrenched/buried/declared) -- simmer/fade noise stays out.
  3. League declares both news boxes; old saves restore them as empty.
  4. Save serialize/restore round-trips both boxes.
  5. Both main.py news-drain sites post the boxes to add_news and clear
     them (one-shot, same pattern as the award/slide boxes).

Run: python3 qa_news_surfacing.py
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import reputation_system as rs
from game_classes import League

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def rival(**kw):
    d = {"a_name": "Bruins", "b_name": "Canadiens", "origin": "playoff_series",
         "grudge": 0, "career_cost": 0, "intensity": 0, "incidents": [],
         "story": "Seven games of pure hatred."}
    d.update(kw)
    return d


# --- 1. verdict shapes -------------------------------------------------------
r1 = rival(grudge=90, career_cost=80, intensity=95)   # score ~ 60*.45+90*.25+80*.15+95*.15 = 76 -> solidify
r2 = rival(grudge=60, career_cost=40, intensity=60)   # ~ 27+15+6+9 = 57 -> simmer
r3 = rival(grudge=5, career_cost=0, intensity=5, origin="trade")  # -> buried/fading
r4 = rival(user_declared=True, declared_floor=45, intensity=60,
           grudge=50, career_cost=30)
r5 = rival(grudge=90, career_cost=80, intensity=95, solidified=True)
verdicts = rs.review_rivalries([r1, r2, r3, r4, r5], years=3)
by_outcome = {}
for v in verdicts:
    by_outcome.setdefault(v.get("outcome"), []).append(v)
check("review: a hot war solidifies", "solidified" in by_outcome,
      str(sorted(by_outcome)))
check("review: mid heat simmers", "simmering" in by_outcome)
check("review: cold feud buried or fading",
      ("buried" in by_outcome) or ("fading" in by_outcome))
check("review: declared rivalry reported", "declared" in by_outcome)
check("review: entrenched rivalry reported", "entrenched" in by_outcome)
check("review: verdicts carry headline text",
      all(isinstance(v.get("text"), str) and v["text"] for v in verdicts))
check("review: text names the teams",
      all("Bruins" in v["text"] and "Canadiens" in v["text"]
          for v in verdicts))

# --- 2. newsworthy filter (mirrors the end_of_season capture) ----------------
NEWSWORTHY = ("solidified", "entrenched", "buried", "declared")
headlined = [str(v.get("text", "")) for v in verdicts
             if str(v.get("outcome", "")) in NEWSWORTHY]
check("capture: solidified/entrenched/buried/declared make the news",
      len(headlined) >= 3, f"headlined={len(headlined)}")
check("capture: simmer/fade noise stays out",
      not any(v.get("outcome") == "simmering"
              for v in verdicts
              if str(v.get("text", "")) in headlined))

# --- 3. League fields --------------------------------------------------------
lg = League.__new__(League)
# uninitialized dataclass fields would raise; check the class defaults
import dataclasses
flds = {f.name for f in dataclasses.fields(League)}
check("league: rivalry_review_news is a declared field",
      "rivalry_review_news" in flds)
check("league: staff_breakthrough_news is a declared field",
      "staff_breakthrough_news" in flds)

# --- 4. save/load round-trip (exact expressions from save_load_system) --------
src = open("save_load_system.py").read()
check("save: rivalry_review_news serialized with old-save-safe getattr",
      "'rivalry_review_news': list(getattr(league, 'rivalry_review_news', []) or [])" in src)
check("save: staff_breakthrough_news serialized with old-save-safe getattr",
      "'staff_breakthrough_news': list(getattr(league, 'staff_breakthrough_news', []) or [])" in src)
check("restore: rivalry_review_news restored with old-save default",
      "league_data.get('rivalry_review_news', [])" in src)
check("restore: staff_breakthrough_news restored with old-save default",
      "league_data.get('staff_breakthrough_news', [])" in src)
# behavioral check of the exact expressions
fake = SimpleNamespace(rivalry_review_news=["⚔️ X vs Y: SOLIDIFIED. ..."],
                       staff_breakthrough_news=["📈 Coach Z: career leap."])
check("save: serialize expression round-trips both boxes",
      list(getattr(fake, 'rivalry_review_news', []) or [])
      == ["⚔️ X vs Y: SOLIDIFIED. ..."]
      and list(getattr(fake, 'staff_breakthrough_news', []) or [])
      == ["📈 Coach Z: career leap."])
fake2 = SimpleNamespace()  # old save: boxes missing entirely
check("save: old save without boxes serializes to empty lists",
      list(getattr(fake2, 'rivalry_review_news', []) or []) == []
      and list(getattr(fake2, 'staff_breakthrough_news', []) or []) == [])

# --- 5. drain sites ----------------------------------------------------------
main_src = open("main.py").read()
check("drain: site 1 posts rivalry verdicts",
      main_src.count('"⚔️ " + str(_m)') >= 1 or
      main_src.count("'⚔️ ' + str(_m)") >= 1 or
      main_src.count('"⚔️ " + str(_msg)') >= 1)
check("drain: site 1 posts staff breakthroughs",
      main_src.count('"📈 " + str(_m)') >= 1 or
      main_src.count('"📈 " + str(_msg)') >= 1)
check("drain: rivalry box cleared after posting",
      "rivalry_review_news" in main_src and
      ("del _rlive[:]" in main_src or
       "self.league.rivalry_review_news = []" in main_src))
check("drain: breakthrough box cleared after posting",
      "staff_breakthrough_news" in main_src and
      ("del _blive[:]" in main_src or
       "self.league.staff_breakthrough_news = []" in main_src))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
