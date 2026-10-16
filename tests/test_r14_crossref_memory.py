#!/usr/bin/env python3
"""R14: Cross-reference memory tests (S item).

"As reported last week..." callbacks quote only stories that actually
fired. Conventions: synthetic SimpleNamespace fixtures (same shape as the
R8* tests); script-style check() accounting like the other R-item tests.

Acceptance gates asserted here:
  1. mark-only-surfaced invariant: a finalized story's premise reaches
     _daily_news_surfaced ONLY via _r14_commit_surfaced (the _generate add
     choke point); a story that never commits is never quotable.
  2. Callback truthfulness: the quoted fragment is a genuine fragment of
     the surfaced premise (verbatim prefix up to the truncation marker).
  3. Lookback: only surfaced stories 1..7 game-days old are quotable
     (same-day and 8+-day-old stories never match).
  4. Unknown fail-closed: premises carrying Unknown markers are never
     quoted; garbage inputs never raise.
  5. No-fire -> no callback: with no surfaced stories the story passes
     through unchanged (still marked for repeat-suppression).
  6. Entity isolation: callbacks only match the same entity tag; league /
     matchup keys get no callback.
  7. Name cross-check: bare player:<p.id> keys with disagreeing display
     names do not match.
  8. Suppression semantics unchanged: _mark_recent still marks 2-tuples
     and _recent_ok still suppresses within the window.
"""
import sys
import os
import types
from datetime import date, timedelta

_REPO = os.environ.get("R14_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn

check_failed = 0


def check(name, cond):
    global check_failed
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check_failed += 1


def mkapp():
    return types.SimpleNamespace(_daily_news_recent={})


D0 = date(2026, 11, 10)

# -- 1. entity tag shapes ----------------------------------------------------
tag = dn._r14_entity_tag
check("tag player:<id>", tag("player:42") == ("player", "42"))
check("tag prospect:<id>", tag("prospect:7") == ("player", "7"))
check("tag awards key", tag("awards:2026:hart:John Smith#99") == ("player", "99"))
check("tag heroics key",
      tag("heroics:2026:hat_trick:2026-11-01:John Smith#99") == ("player", "99"))
check("tag debuts key",
      tag("debuts:2026:first_goal:Kid Rookie#12345") == ("player", "12345"))
check("tag extension key",
      tag("extension:2026:John Smith#99") == ("player", "99"))
check("tag coach key", tag("coach:Al Arbour") == ("coach", "al arbour"))
check("tag team key", tag("team:Oilers") == ("team", "oilers", None))
check("tag losing_streak key",
      tag("losing_streak:2026:Oilers#555:6") == ("team", "oilers", "555"))
check("tag playoff key",
      tag("playoff:2026:Oilers#555") == ("team", "oilers", "555"))
check("tag deadline buyer key",
      tag("deadline:2026:buyer:Oilers#555") == ("team", "oilers", "555"))
check("tag deadline seller key",
      tag("deadline:2026:seller:Flames#556") == ("team", "flames", "556"))
check("no tag: deadline frame", tag("deadline:2026:frame") is None)
check("no tag: deadline trade (two teams)",
      tag("deadline:2026:trade:2027-03-01:Oilers#Flames") is None)
check("no tag: league key", tag("league:best_team") is None)
check("no tag: draft key", tag("draft:risers") is None)
check("no tag: playoff race league key",
      tag("league:playoff_race:2026:Eastern") is None)
check("no tag: garbage", tag("nonsense") is None)
check("no tag: non-string", tag(None) is None)
check("no tag: empty coach", tag("coach:   ") is None)
check("no tag: non-numeric player", tag("player:abc") is None)
check("tag: empty string", tag("") is None)

# -- 2. mark-only-surfaced invariant ------------------------------------------
app = mkapp()
story_a = "RUMOR MILL: John Smith's production has dipped in Oilers."
# Finalize registers pending + marks, but does NOT surface.
out = dn._r14_finalize_story(app, "player:42", "rumor", story_a, D0,
                             entity_name="John Smith")
check("finalize returns story unchanged with no history", out == story_a)
check("finalize marks for suppression",
      not dn._recent_ok(app, "player:42", "rumor", D0))
check("pending registered, surfaced empty",
      isinstance(getattr(app, "_daily_news_pending", None), dict)
      and len(app._daily_news_pending) == 1
      and getattr(app, "_daily_news_surfaced", None) is None)
# A story that never reaches the add choke point is never quotable.
out2 = dn._r14_finalize_story(app, "player:42", "holdout", "CONTRACT WATCH: no deal for John Smith in Oilers.",
                              D0 + timedelta(days=3), entity_name="John Smith")
check("uncommitted story cannot seed a callback", "As reported" not in out2)
# Commit = the story truly fired.
dn._r14_commit_surfaced(app, story_a, D0)
check("commit surfaces the premise",
      ("player:42", "rumor") in app._daily_news_surfaced)
check("only the uncommitted story's pending entry remains",
      len(app._daily_news_pending) == 1)
check("commit of unknown story is a no-op",
      dn._r14_commit_surfaced(app, "never finalized", D0) is None)

# -- 3. truthfulness + lookback -----------------------------------------------
# Day 3: a new story for the same player quotes the day-0 story.
day3 = D0 + timedelta(days=3)
story_b = "CONTRACT WATCH: no deal yet for John Smith in Oilers."
out3 = dn._r14_finalize_story(app, "player:42", "holdout", story_b, day3,
                              entity_name="John Smith")
check("callback attached within lookback", "As reported last week:" in out3)
check("callback quotes the real premise verbatim",
      f'"{story_a}"' in out3 or story_a[:60] in out3)
check("callback appended after the story", out3.startswith(story_b))
# Stored premise excludes our own callback (no nesting).
dn._r14_commit_surfaced(app, out3, day3)
prem = app._daily_news_surfaced[("player:42", "holdout")][1]
check("stored premise has no callback of its own", "As reported" not in prem)
# Yesterday vs last-week lead.
app2 = mkapp()
s0 = "The Oilers are rolling at 5-1-0."
dn._r14_finalize_story(app2, "team:Oilers", "streak", s0, D0, entity_name="Oilers")
dn._r14_commit_surfaced(app2, s0, D0)
out_y = dn._r14_finalize_story(app2, "team:Oilers", "slump", "Tough night for Oilers.",
                               D0 + timedelta(days=1), entity_name="Oilers")
check("'yesterday' lead for 1-day delta", "As reported yesterday:" in out_y)
check("no 'last week' for 1-day delta", "As reported last week:" not in out_y)
# Same-day: never.
out_same = dn._r14_finalize_story(app2, "team:Oilers", "streak", "Oilers win again.",
                                  D0, entity_name="Oilers")
check("same-day story gets no callback", "As reported" not in out_same)
# 8 days: outside the lookback.
out_old = dn._r14_finalize_story(app2, "team:Oilers", "streak", "Oilers win again.",
                                 D0 + timedelta(days=8), entity_name="Oilers")
check("8-day-old story gets no callback", "As reported" not in out_old)
# 7 days: inside.
out_7 = dn._r14_finalize_story(app2, "team:Oilers", "streak", "Oilers win again.",
                               D0 + timedelta(days=7), entity_name="Oilers")
check("7-day-old story still quotable", "As reported last week:" in out_7)
# Most recent wins.
app3 = mkapp()
p_old = "Old news about Jane Doe."
p_new = "Fresh news about Jane Doe."
dn._r14_finalize_story(app3, "player:9", "hot", p_old, D0, entity_name="Jane Doe")
dn._r14_commit_surfaced(app3, p_old, D0)
p_new_final = dn._r14_finalize_story(app3, "player:9", "grinder", p_new,
                                     D0 + timedelta(days=2), entity_name="Jane Doe")
dn._r14_commit_surfaced(app3, p_new_final, D0 + timedelta(days=2))
out_r = dn._r14_finalize_story(app3, "player:9", "backup", "More Jane Doe news.",
                               D0 + timedelta(days=4), entity_name="Jane Doe")
check("callback quotes the most recent premise", p_new[:40] in out_r)
check("callback does not quote the older premise", p_old[:40] not in out_r)

# -- 4. Unknown fail-closed -----------------------------------------------------
app4 = mkapp()
bad_premise = "Unknown Player is on another level for Unknown Team."
dn._r14_finalize_story(app4, "player:1", "hot", bad_premise, D0, entity_name="Unknown Player")
dn._r14_commit_surfaced(app4, bad_premise, D0)
out_u = dn._r14_finalize_story(app4, "player:1", "grinder", "A real story here.",
                               D0 + timedelta(days=2), entity_name="Some Guy")
check("Unknown premise is never quoted", "As reported" not in out_u)
check("finalize never raises on garbage app",
      dn._r14_finalize_story(None, None, None, None, None) is None)
check("find_callback never raises on garbage",
      dn._r14_find_callback(None, None, None) is None)
check("entity_tag never raises", dn._r14_entity_tag(object()) is None)
check("commit_surfaced never raises on garbage",
      dn._r14_commit_surfaced(None, None, None) is None)

# -- 5. entity isolation ----------------------------------------------------------
app5 = mkapp()
ps = "Star FA shines for Aurora."
dn._r14_finalize_story(app5, "player:100", "hot", ps, D0, entity_name="Star FA")
dn._r14_commit_surfaced(app5, ps, D0)
# Different player, same day+1: no callback.
out_iso = dn._r14_finalize_story(app5, "player:101", "hot", "Other Guy scores.",
                                 D0 + timedelta(days=1), entity_name="Other Guy")
check("different player gets no callback", "As reported" not in out_iso)
# Different kind (team vs player): no callback.
out_iso2 = dn._r14_finalize_story(app5, "team:Aurora", "streak", "Aurora keeps winning.",
                                  D0 + timedelta(days=1), entity_name="Aurora")
check("team story does not quote player story", "As reported" not in out_iso2)
# League keys degrade to a plain mark.
app_lg = mkapp()
out_lg = dn._r14_finalize_story(app_lg, "league:best_team", "notes",
                               "POWER RANKINGS: Aurora leads.", D0)
check("league key: no callback", "As reported" not in out_lg)
check("league key: still marked",
      not dn._recent_ok(app_lg, "league:best_team", "notes", D0))
check("league key: no pending registered",
      getattr(app_lg, "_daily_news_pending", None) in (None, {}))

# -- 6. name cross-check for bare player: keys --------------------------------------
app6 = mkapp()
pa = "Big night for John Smith."
dn._r14_finalize_story(app6, "player:0", "hot", pa, D0, entity_name="John Smith")
dn._r14_commit_surfaced(app6, pa, D0)
# Same bare key, different display name (p.id reuse across objects): no match.
out_nc = dn._r14_finalize_story(app6, "player:0", "grinder", "Jane Doe grinding.",
                                D0 + timedelta(days=2), entity_name="Jane Doe")
check("bare-key name mismatch: no callback", "As reported" not in out_nc)
# Same bare key, same name: match.
out_nc2 = dn._r14_finalize_story(app6, "player:0", "backup", "John Smith again.",
                                 D0 + timedelta(days=2), entity_name="John Smith")
check("bare-key name agreement: callback", "As reported last week:" in out_nc2)

# -- 6b. same-named teams: #id(t) disambiguator (reviewer B finding 1) ------
check("tags_match: same name+id",
      dn._r14_tags_match(("team", "oilers", "555"), ("team", "oilers", "555")))
check("tags_match: same name, different ids -> no match",
      not dn._r14_tags_match(("team", "springfield", "140001"),
                             ("team", "springfield", "140002")))
check("tags_match: missing id falls back to name-only",
      dn._r14_tags_match(("team", "oilers", None), ("team", "oilers", "555")))
check("tags_match: different names -> no match",
      not dn._r14_tags_match(("team", "oilers", "555"),
                             ("team", "flames", "555")))
check("tags_match: kind mismatch -> no match",
      not dn._r14_tags_match(("team", "oilers", "555"),
                             ("player", "555")))
check("tags_match: never raises on garbage",
      dn._r14_tags_match(None, object()) is False)
app6b = mkapp()
s_sell = "Springfield is selling at the deadline."
s_buy = "Springfield is loading up for a deep run."
dn._r14_finalize_story(app6b, "deadline:2026:seller:Springfield#140001",
                       "trade_deadline", s_sell, D0, entity_name="Springfield")
dn._r14_commit_surfaced(app6b, s_sell, D0)
# Different team object, same display name: must NOT cross-quote.
out_x = dn._r14_finalize_story(app6b, "deadline:2026:buyer:Springfield#140002",
                               "trade_deadline", "Springfield buys big.",
                               D0 + timedelta(days=2), entity_name="Springfield")
check("same-named different team: no callback", "As reported" not in out_x)
# Same team object (same id): quotes fine.
out_ok = dn._r14_finalize_story(app6b, "deadline:2026:buyer:Springfield#140001",
                                "trade_deadline", "Springfield buys bigger.",
                                D0 + timedelta(days=2), entity_name="Springfield")
check("same team object: callback", "As reported last week:" in out_ok)
# Bare team: key (no id) still matches an id-carrying key by name.
app6c = mkapp()
dn._r14_finalize_story(app6c, "team:Oilers", "streak", s0, D0,
                       entity_name="Oilers")
dn._r14_commit_surfaced(app6c, s0, D0)
out_mix = dn._r14_finalize_story(app6c, "losing_streak:2026:Oilers#777:6",
                                 "losing_streak", "Oilers keep sliding.",
                                 D0 + timedelta(days=3), entity_name="Oilers",
                                 window=30)
check("bare team key matches id-carrying key by name",
      "As reported last week:" in out_mix)

# -- 6c. id() reuse: key-derived entity_name closes the cross-check gap ------
# (reviewer C BREAK 1: awards/heroics sites pass no entity_name; an id()
# address reused by a new object -- GC freelist, save/load -- must not
# cross-quote when the names disagree).
check("key_display_name: awards",
      dn._r14_key_display_name("awards:2026:hart:John Smith#99") == "John Smith")
check("key_display_name: heroics",
      dn._r14_key_display_name("heroics:2026:hat_trick:2026-11-01:Jane Doe#100")
      == "Jane Doe")
check("key_display_name: debuts",
      dn._r14_key_display_name("debuts:2026:debut:Kid Rookie#7") == "Kid Rookie")
check("key_display_name: playoff team",
      dn._r14_key_display_name("playoff:2026:Oilers#555") == "Oilers")
check("key_display_name: losing_streak team",
      dn._r14_key_display_name("losing_streak:2026:Oilers#555:6") == "Oilers")
check("key_display_name: bare player key -> None",
      dn._r14_key_display_name("player:42") is None)
check("key_display_name: coach key -> None",
      dn._r14_key_display_name("coach:Al Arbour") is None)
check("key_display_name: garbage -> None",
      dn._r14_key_display_name(None) is None)
app6d = mkapp()
s_hart = "John Smith takes home the Hart Trophy."
# Awards-style key, NO entity_name passed (the exposed shape).
dn._r14_finalize_story(app6d, "awards:2026:hart:John Smith#999", "award",
                       s_hart, D0)
dn._r14_commit_surfaced(app6d, s_hart, D0)
check("key-derived name stored on commit",
      app6d._daily_news_surfaced[("awards:2026:hart:John Smith#999",
                                  "award")][2] == "John Smith")
# A different player reusing the numeric id: names disagree -> no callback.
out_reuse = dn._r14_finalize_story(
    app6d, "awards:2026:hart:Jane Doe#999", "award",
    "Jane Doe takes home the Hart Trophy.", D0 + timedelta(days=3))
check("id reuse with different name: no callback", "As reported" not in out_reuse)
# Same player, same id: callback works (no regression).
out_same_p = dn._r14_finalize_story(
    app6d, "awards:2026:art_ross:John Smith#999", "award",
    "John Smith leads the scoring race.", D0 + timedelta(days=3))
check("same player, key-derived names: callback",
      "As reported last week:" in out_same_p)

# -- 6d. pending first-wins: no nested callback smuggling -------------------------
app6e = mkapp()
base = "RUMOR MILL: John Smith's production has dipped in Oilers."
f1 = dn._r14_finalize_story(app6e, "player:42", "rumor", base, D0,
                            entity_name="John Smith")
# A second finalize producing the identical final string must not replace
# the first premise.
f2 = dn._r14_finalize_story(app6e, "player:42", "rumor", base, D0,
                            entity_name="John Smith")
check("identical finalize is idempotent", f1 == f2)
dn._r14_commit_surfaced(app6e, f1, D0)
prem2 = app6e._daily_news_surfaced[("player:42", "rumor")][1]
check("surfaced premise is the first registration", prem2 == base)

# -- 6e. surfaced hard cap: bound is unconditional ----------------------------------
app6f = mkapp()
for i in range(4100):
    k = f"player:{i}"
    dn._r14_finalize_story(app6f, k, "hot", f"Story {i}.", D0,
                           entity_name=f"Player {i}")
    dn._r14_commit_surfaced(app6f, f"Story {i}.", D0)
check("surfaced hard cap enforced",
      len(app6f._daily_news_surfaced) <= dn._R14_SURFACED_HARD_CAP)
check("newest entries survive the cap",
      ("player:4099", "hot") in app6f._daily_news_surfaced)

# -- 7. suppression semantics unchanged ---------------------------------------------
app7 = mkapp()
dn._mark_recent(app7, "player:5", "rumor", D0)
check("_recent_ok suppresses within window",
      not dn._recent_ok(app7, "player:5", "rumor", D0 + timedelta(days=3)))
check("_recent_ok allows after window",
      dn._recent_ok(app7, "player:5", "rumor", D0 + timedelta(days=30)))
check("marks are still 2-tuples (shape unchanged)",
      app7._daily_news_recent[("player:5", "rumor")] == (D0, dn.REPEAT_WINDOW_DAYS))

# -- 8. structural: bare _mark_recent sites are the documented skips ------------------
import re as _re
src = open(os.path.join(_REPO, "daily_news.py")).read()
in_r14 = False
bad = []
for i, line in enumerate(src.splitlines(), 1):
    if line.startswith("# R14 -- Cross-reference memory"):
        in_r14 = True
        continue
    if in_r14 and line.startswith("def ") \
            and not line.startswith("def _r14_"):
        in_r14 = False
    if "_mark_recent(app, key," in line and not in_r14:
        m = _re.search(r'_mark_recent\(app, key,\s*"([^"]+)"', line)
        stype = m.group(1) if m else "?"
        if stype not in ("notes", "rivalry_hype"):
            bad.append((i, stype))
    if "_mark_recent(app, k," in line and not in_r14:
        # Only the debuts secondary-key loop may use the `k` form.
        ctx = "\n".join(src.splitlines()[max(0, i - 8):i])
        if "secondary keys" not in ctx:
            bad.append((i, "k-form"))
check("bare key-form marks only for notes/rivalry_hype", not bad)
lit_bad = []
in_r14b = False
for i, line in enumerate(src.splitlines(), 1):
    if line.startswith("# R14 -- Cross-reference memory"):
        in_r14b = True
        continue
    if in_r14b and line.startswith("def ") \
            and not line.startswith("def _r14_"):
        in_r14b = False
    if '_mark_recent(app, "' in line and not in_r14b:
        if '"draft:' not in line:
            lit_bad.append(i)
check("literal-key marks only for draft league keys", not lit_bad)
# Every bucket's entity-scoped mark site routes through finalize.
n_finalize = (src.count("_r14_finalize_story(app, key")
              + src.count("_r14_finalize_story(app, keys[0]"))
check(">=20 finalize call sites", n_finalize >= 20)

# -- 9. _generate hooks present ---------------------------------------------------------
gsrc = open(os.path.join(_REPO, "daily_news.py")).read()
check("_generate resets pending", "_r14_reset_pending(app)" in gsrc)
check("_generate commits surfaced at the add choke point",
      "_r14_commit_surfaced(app, s, game_date)" in gsrc)

print()
if check_failed:
    print(f"{check_failed} CHECK(S) FAILED")
    sys.exit(1)
print("ALL CHECKS PASSED")
