#!/usr/bin/env python3
"""R8g: extensions-signed bucket tests (S item).

Bucket under test: daily_news._extension_stories. Conventions: synthetic
SimpleNamespace app/team/player fixtures (same shape as the R8a-f tests);
assertions on premises, not phrasing.

The bucket is a presentation layer over player.contract.years_remaining --
the real Contract field game_manager mutates on every signing. Tests assert
the bucket fires for stars (ovr >= 82) on long deals (years >= 4) with the
true years and the true signed-through year, and stays silent on short
deals, non-stars, missing/fallback contracts, unknown teams/players, junk
coercions, and false premises (one story per (season, player); 2/day cap;
cross-season re-fire; crash battery on malformed inputs).
"""
import sys
import os
import types
import random
from datetime import date

_REPO = os.environ.get("R8G_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn


def mkplayer(name, ovr, years, pid=None, team_name="Blades"):
    p = types.SimpleNamespace(full_name=name, first_name=name.split()[0],
                              last_name=" ".join(name.split()[1:]) or name)
    p.overall_rating = lambda ovr=ovr: ovr
    p.id = pid if pid is not None else abs(hash(name)) % 10**9
    if years is None:
        p.contract = None
    else:
        p.contract = types.SimpleNamespace(years_remaining=years)
    return p


def mkteam(name, players):
    t = types.SimpleNamespace(team_name=name, roster=list(players))
    return t


def mkapp(teams, season_year=2026):
    league = types.SimpleNamespace(teams=list(teams), season_year=season_year)
    app = types.SimpleNamespace(league=league, _daily_news_recent={})
    return app


def run_bucket(app, day, seed=424242):
    rng = random.Random(seed)
    return dn._extension_stories(app, day, rng)


DAY = date(2027, 1, 15)  # mid-season


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed += 1
check.failed = 0


# -- _ext_years fail-closed -------------------------------------------------
check("_ext_years: real 5-year deal -> 5",
      dn._ext_years(mkplayer("Star One", 90, 5)) == 5)
check("_ext_years: None contract -> None",
      dn._ext_years(mkplayer("Star Two", 90, None)) is None)
p = mkplayer("Star Three", 90, 5)
p.contract = types.SimpleNamespace()  # no years_remaining attr
check("_ext_years: contract w/o years attr -> None",
      dn._ext_years(p) is None)
p = mkplayer("Star Four", 90, 5)
p.contract.years_remaining = 0
check("_ext_years: 0 years -> None", dn._ext_years(p) is None)
p = mkplayer("Star Five", 90, 5)
p.contract.years_remaining = -2
check("_ext_years: negative years -> None", dn._ext_years(p) is None)
p = mkplayer("Star Six", 90, 5)
p.contract.years_remaining = 99  # the _contract_years_left fallback shape
check("_ext_years: absurd 99 treated as unknown -> None",
      dn._ext_years(p) is None)
p = mkplayer("Star Seven", 90, 5)
p.contract.years_remaining = None
check("_ext_years: None years -> None", dn._ext_years(p) is None)

# -- fires on star + long deal ----------------------------------------------
star = mkplayer("Elias Pettersson", 91, 5)
app = mkapp([mkteam("Blades", [star])])
stories = run_bucket(app, DAY)
check("star 91 OVR, 5 yrs -> fires", len(stories) == 1)
if stories:
    s = stories[0]
    check("renders true name", "Elias Pettersson" in s)
    check("renders true team", "Blades" in s)
    check("renders true OVR", "91" in s)
    check("renders true years", "5" in s)
    check("renders true through-year 2026+5=2031", "2031" in s)
    check("no placeholder leakage", "Unknown" not in s)

# -- silence gates -----------------------------------------------------------
quiet = mkplayer("Solid Guy", 81, 7)  # just under the star bar
check("81 OVR on 7-yr deal stays silent",
      run_bucket(mkapp([mkteam("Blades", [quiet])]), DAY) == [])
short = mkplayer("Star Eight", 90, 3)  # one year short of the bar
check("90 OVR on 3-yr deal stays silent",
      run_bucket(mkapp([mkteam("Blades", [short])]), DAY) == [])
edge = mkplayer("Star Nine", 82, 4)  # exactly on both bars
check("82 OVR on 4-yr deal fires (boundary inclusive)",
      len(run_bucket(mkapp([mkteam("Blades", [edge])]), DAY)) == 1)
nocontract = mkplayer("Star Ten", 95, None)
check("95 OVR with no contract stays silent",
      run_bucket(mkapp([mkteam("Blades", [nocontract])]), DAY) == [])
# the 99-fallback must not fabricate "through 2125"
p = mkplayer("Star Eleven", 95, 5)
p.contract.years_remaining = 99
stories = run_bucket(mkapp([mkteam("Blades", [p])]), DAY)
check("99-fallback contract stays silent", stories == [])
badteam = mkplayer("Star Twelve", 90, 5)
bt = types.SimpleNamespace(team_name="Unknown Team", players=[badteam])
check("Unknown Team stays silent",
      run_bucket(mkapp([bt]), DAY) == [])
check("missing season_year + unreadable date stays silent (fail closed)",
      run_bucket(mkapp([mkteam("Blades", [star])], season_year=None),
                 types.SimpleNamespace()) == [])
# Jan-Apr with missing league season_year derives the START year (2026),
# not the calendar year -- otherwise the through-year would be off by one.
s_der = run_bucket(mkapp([mkteam("Blades", [star])], season_year=None),
                   date(2027, 1, 15))
check("Jan date w/o season_year derives start-year: 5-yr -> through 2031",
      len(s_der) == 1 and "2031" in s_der[0])

# -- one story per (season, player); cross-season re-fire --------------------
star13 = mkplayer("Star Thirteen", 90, 6)
app = mkapp([mkteam("Blades", [star13])])
s1 = run_bucket(app, DAY)
s2 = run_bucket(app, date(2027, 2, 10))
check("second call same season -> suppressed", s1 and s2 == [])
s3 = run_bucket(app, date(2027, 11, 5))  # next season's key differs
check("next calendar season still suppressed (same season_year)",
      s3 == [])

# cross-season: season_year rolls -> fires again
app2 = mkapp([mkteam("Blades", [mkplayer("Star Thirteen", 90, 6,
                                        pid=star13.id)])], season_year=2027)
s4 = run_bucket(app2, date(2028, 1, 15))
check("new season_year re-fires with true 2027+6=2033",
      len(s4) == 1 and "2033" in s4[0])

# -- newsworthiness + 2/day cap ----------------------------------------------
players = [mkplayer(f"Star {i}", ovr, 5, pid=1000 + i)
           for i, ovr in enumerate((83, 88, 97, 85), start=1)]
app = mkapp([mkteam("Blades", players)])
stories = run_bucket(app, DAY)
check("4 qualifiers -> capped at 2", len(stories) == 2)
# biggest star first: the 97-OVR story must be among the returned
big = [s for s in stories if "97" in s or "Star 3" in s]
check("highest-OVR star among the chosen", len(big) >= 1)
# true duplicate entries (same name AND same id, e.g. a roster listed twice)
# collapse to one story
dup1 = mkplayer("Twin Star", 90, 5, pid=1)
dup2 = mkplayer("Twin Star", 90, 5, pid=1)
stories = run_bucket(mkapp([mkteam("Blades", [dup1, dup2])]), DAY)
check("true duplicate entries dedupe to 1 story", len(stories) == 1)

# -- off-season: contract state is true year-round (holdout mirror) ----------
off = run_bucket(app, date(2027, 7, 20))
check("fires in the offseason too", len(off) >= 1)

# -- crash battery: malformed inputs never raise -----------------------------
class ExplodingPlayer:
    @property
    def contract(self):
        raise RuntimeError("boom")
    def overall_rating(self):
        raise RuntimeError("boom")

weird = [
    mkplayer("OK Star", 90, 5),
    ExplodingPlayer(),
    types.SimpleNamespace(),  # nothing at all
]
wapp = mkapp([mkteam("Weird", weird)])
try:
    run_bucket(wapp, DAY)
    check("malformed players never raise", True)
except Exception:
    check("malformed players never raise", False)

# never raises without a league at all
try:
    run_bucket(types.SimpleNamespace(), DAY)
    check("no league -> [] not a raise", True)
except Exception:
    check("no league -> [] not a raise", False)

# NaN / inf OVR never qualifies
nan = mkplayer("Nan Star", 90, 5)
nan.overall_rating = lambda: float("nan")
inf = mkplayer("Inf Star", 90, 5)
inf.overall_rating = lambda: float("inf")
check("NaN/inf OVR stay silent",
      run_bucket(mkapp([mkteam("Blades", [nan, inf])]), DAY) == [])

# -- adversarial regression tests (Reviewer C findings, R8g round 1) --------
# F1: _ext_years must not coerce junk -- raw type checked pre-coercion.
for _bad in ("5", " 5 ", 4.9, 4.0, True, 10**6):
    _p = mkplayer("Junk Star", 90, 5)
    _p.contract.years_remaining = _bad
    check(f"F1 _ext_years rejects {type(_bad).__name__} {str(_bad)[:8]!r}",
          dn._ext_years(_p) is None)
    _q = mkplayer("Junk Star", 90, 5)
    _q.contract.years_remaining = _bad
    check(f"F1 junk years {type(_bad).__name__} stays silent",
          run_bucket(mkapp([mkteam("Blades", [_q])]), DAY) == [])

# F2: id-collision suppression -- two different stars sharing .id.
c1 = mkplayer("Alpha Star", 90, 5, pid=777)
c2 = mkplayer("Beta Star", 92, 5, pid=777)  # same id, different player
c3 = mkplayer("Gamma Star", 93, 2, pid=777)  # same id; becomes qualifying day 2
app = mkapp([mkteam("Blades", [c1, c2, c3])])
d1 = run_bucket(app, DAY)
check("F2 id-colliders both fire day 1", len(d1) == 2)
c3.contract.years_remaining = 5  # late qualifier: new deal signed day 2
d2 = run_bucket(app, date(2027, 2, 1))
check("F2 late qualifier with colliding id still fires day 2",
      len(d2) == 1 and "Gamma Star" in d2[0])
check("F2 day-1 colliders stay suppressed day 2",
      not any("Alpha Star" in s or "Beta Star" in s for s in d2))

# F3: one-shot holds even with a non-date game_date (fail-closed delta).
f3 = mkplayer("Delta Star", 90, 5)
app = mkapp([mkteam("Blades", [f3])])
s1 = run_bucket(app, "2027-01-15")
s2 = run_bucket(app, "2027-01-15")
check("F3 string game_date: day 1 fires", len(s1) == 1)
check("F3 string game_date: day 2 suppressed (not re-fired)", s2 == [])

# F4: same name, different teams -> both fire (text differs).
n1 = mkplayer("Same Name", 90, 5, pid=11)
n2 = mkplayer("Same Name", 91, 5, pid=12)
app = mkapp([mkteam("Blades", [n1]), mkteam("Sharks", [n2])])
stories = run_bucket(app, DAY)
check("F4 same-name different-team stars both fire",
      len(stories) == 2 and
      any("Blades" in s for s in stories) and
      any("Sharks" in s for s in stories))

# F5: insane season_year -> silent, never "signed through 6".
app = mkapp([mkteam("Blades", [mkplayer("Eon Star", 90, 5)])], season_year=True)
check("F5 season_year=True stays silent", run_bucket(app, DAY) == [])
app = mkapp([mkteam("Blades", [mkplayer("Eon Star", 90, 5)])], season_year=1)
check("F5 season_year=1 stays silent", run_bucket(app, DAY) == [])
s_a = run_bucket(mkapp([mkteam("Blades", [mkplayer("Det Star", 90, 5)])]),
                 DAY, seed=7)
s_b = run_bucket(mkapp([mkteam("Blades", [mkplayer("Det Star", 90, 5)])]),
                 DAY, seed=7)
check("deterministic per seed", s_a == s_b)

# -- B1: prune must respect long one-shot windows -------------------------------
# 2001 stale default-window marks + one 61-day-old extension mark: the
# prune must delete the stale ones but KEEP the 400-day one-shot mark.
from datetime import timedelta
b1app = mkapp([mkteam("Blades", [mkplayer("Prune Star", 90, 5, pid=4242)])])
old_day = DAY - timedelta(days=61)
for i in range(2001):
    b1app._daily_news_recent[(f"stale:{i}", "notes")] = (
        old_day, 10)  # (date, window) tuples, long dead
b1app._daily_news_recent[("extension:2026:Prune Star#4242", "extension")] = (
    old_day, 400)
# force a prune by marking one more
dn._mark_recent(b1app, "probe", "notes", DAY, 10)
kept = ("extension:2026:Prune Star#4242", "extension") in b1app._daily_news_recent
check("B1 61-day-old 400-day mark survives the prune", kept)
stale_left = sum(1 for k in b1app._daily_news_recent if str(k[0]).startswith("stale:"))
check("B1 stale 10-day marks pruned", stale_left == 0)
# and the surviving mark still suppresses
check("B1 surviving mark suppresses re-fire",
      not dn._recent_ok(b1app, "extension:2026:Prune Star#4242",
                        "extension", DAY, window=400))
# legacy bare-date marks still read fine
b1app._daily_news_recent[("legacy:k", "notes")] = old_day
check("B1 legacy bare-date mark suppresses within window",
      not dn._recent_ok(b1app, "legacy:k", "notes", DAY, window=400))
check("B1 legacy bare-date mark allows after window",
      dn._recent_ok(b1app, "legacy:k", "notes",
                    DAY + timedelta(days=500), window=400))

print()
print("FAILED:", check.failed)
sys.exit(1 if check.failed else 0)
