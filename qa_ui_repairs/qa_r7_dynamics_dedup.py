# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA R7: practice event fires once per day; feed dedupes identical
same-day entries; distinct events are never dropped.

Run: DISPLAY=:99 python3 qa_r7_dynamics_dedup.py   (headless; Xvfb on :99)
"""
import os
import random
import sys
from datetime import date, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")

random.seed(20260929)

import reputation_system as rs
from game_classes import Staff, StaffRole

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


def make_team(name="Test Club"):
    coach = Staff("Dan", "Davis", StaffRole.HEAD_COACH,
                  age=55, experience=20, assignment="nhl")
    roster = [SimpleNamespace(full_name=f"Player {i}", happiness=70,
                              id=f"p{i}") for i in range(5)]
    return SimpleNamespace(team_name=name, staff=[coach],
                           roster=roster), coach


# --- 1. the reported bug: 6 rapid fires -> exactly ONE feed entry ------------
team, coach = make_team()
for _ in range(6):
    rs.apply_great_practice(team, coach, list(team.roster))
feed = rs.get_dynamics_feed(team)
practice = [e for e in feed if e.get("type") == "practice"]
check("6x apply_great_practice -> exactly 1 practice entry", len(practice) == 1)
check("entry text is a practice variant for this coach",
      practice and practice[0]["text"].startswith(
          "Great practice after the loss -- Dan Davis "))
check("entry tone/icon is 'up' (green triangle)",
      practice and practice[0]["tone"] == "up")
check("morale lift applied once (single variant delta 1-3, not stacked)",
      len({p.happiness for p in team.roster}) == 1
      and 71 <= team.roster[0].happiness <= 73)

# --- 2. append-time defense: direct record_team_event dedupes ---------------
team2, coach2 = make_team("Second Club")
for _ in range(3):
    rs.record_team_event(team2, "speech", "Same speech text",
                         morale_delta=1, tone="up")
feed2 = rs.get_dynamics_feed(team2)
check("3x identical record_team_event -> 1 entry",
      len([e for e in feed2 if e["text"] == "Same speech text"]) == 1)

# --- 3. distinct events are never dropped ------------------------------------
team3, coach3 = make_team("Third Club")
rs.apply_great_practice(team3, coach3, list(team3.roster))
rs.apply_inspiring_speech(team3, coach3, list(team3.roster))
rs.apply_bag_skate(team3, coach3, list(team3.roster))
rs.record_team_event(team3, "media", "Paul Wilson went on the record.",
                     morale_delta=2, tone="up")
# same text, different tone -> distinct entry (different icon)
rs.record_team_event(team3, "media", "Paul Wilson went on the record.",
                     morale_delta=-1, tone="down")
feed3 = rs.get_dynamics_feed(team3)
texts = [(e["text"], e["tone"]) for e in feed3]
check("all distinct events appear (5 entries)",
      len(feed3) == 5)
check("same text + different tone kept as separate entries",
      ("Paul Wilson went on the record.", "up") in texts
      and ("Paul Wilson went on the record.", "down") in texts)
check("practice + speech + bag_skate all present",
      {"practice", "speech", "bag_skate"} <=
      {e["type"] for e in feed3})

# --- 4. yesterday's identical event does not block today's -------------------
team4, coach4 = make_team("Fourth Club")
yesterday = (date.today() - timedelta(days=1)).isoformat()
team4.dynamics_log = [{"date": yesterday, "type": "practice",
                       "text": "Great practice after the loss -- Dan Davis "
                               "had them sharp and focused.",
                       "morale_delta": 2, "tone": "up"}]
rs.apply_great_practice(team4, coach4, list(team4.roster))
feed4 = rs.get_dynamics_feed(team4)
pr4 = [e for e in feed4 if e["type"] == "practice"]
check("prior-day practice does not suppress today's",
      len(pr4) == 2 and {e["date"] for e in pr4} == {yesterday,
                                                    date.today().isoformat()})

# --- 5. once-per-day holds even across a mid-day coaching change -------------
team5, coach5 = make_team("Fifth Club")
first5 = rs.apply_great_practice(team5, coach5, list(team5.roster))
coach5b = Staff("New", "Guy", StaffRole.HEAD_COACH,
                age=48, experience=10, assignment="nhl")
second5 = rs.apply_great_practice(team5, coach5b, list(team5.roster))
feed5 = [e for e in rs.get_dynamics_feed(team5) if e["type"] == "practice"]
check("mid-day coaching change does not double-fire (still one entry)",
      len(feed5) == 1 and second5 is first5)

# --- 6. log cap still enforced -------------------------------------------------
team6, _ = make_team("Sixth Club")
for i in range(120):
    rs.record_team_event(team6, "note", f"distinct note {i}", tone="neutral")
check("log stays capped at 100 entries",
      len(team6.dynamics_log) == 100)

# --- 7. variety: each coaching button yields multiple distinct outcomes ----
import media_engine as me


def mkcoach(**kw):
    base = dict(motivating=60, discipline=60, man_management=60,
                leadership=60, tactical_knowledge=60, game_preparation=60,
                working_with_youngsters=60, player_development=60)
    base.update(kw)
    c = Staff("Test", "Coach", StaffRole.HEAD_COACH,
              age=55, experience=15, assignment="nhl")
    for k, v in base.items():
        setattr(c, k, v)
    return c


def fresh_team(coach, mood=70, n=8):
    roster = [SimpleNamespace(full_name=f"P{i}", happiness=mood, age=28,
                              id=f"p{i}") for i in range(n)]
    return SimpleNamespace(team_name="T", staff=[coach], roster=roster,
                           dynamics_log=[])


COACHES = {
    # style keys resolve via coach_style: discipline-heavy -> drill_sergeant
    "drill_sergeant": mkcoach(discipline=95, motivating=55,
                              man_management=40),
    "players_coach": mkcoach(man_management=95, motivating=80,
                             discipline=40),
    "tactician": mkcoach(tactical_knowledge=95, game_preparation=80,
                         motivating=40, discipline=40, man_management=40),
    "motivator": mkcoach(motivating=95, leadership=90),
    "developer": mkcoach(working_with_youngsters=95,
                         player_development=90, discipline=40,
                         man_management=40, motivating=40),
    "flat": mkcoach(motivating=40, leadership=40, discipline=40,
                    man_management=40),
}

random.seed(20260929)
practice_texts = set()
for i in range(40):
    coach = COACHES[["drill_sergeant", "players_coach", "tactician",
                     "motivator", "developer"][i % 5]]
    t = fresh_team(coach)
    practice_texts.add(rs.apply_great_practice(
        t, coach, list(t.roster))["text"])
check("practice: >=3 distinct outcomes over 40 trials",
      len(practice_texts) >= 3)

random.seed(20260930)
skate_texts = set()
for i in range(40):
    coach = COACHES[["drill_sergeant", "players_coach", "tactician"][i % 3]]
    t = fresh_team(coach, mood=50 + (i % 40))
    skate_texts.add(rs.apply_bag_skate(t, coach, list(t.roster))["text"])
check("bag skate: >=3 distinct outcomes over 40 trials",
      len(skate_texts) >= 3)

random.seed(20261001)
speech_texts = set()
for i in range(40):
    coach = COACHES[["motivator", "flat", "drill_sergeant",
                     "players_coach"][i % 4]]
    t = fresh_team(coach, mood=45 + (i % 40))
    speech_texts.add(rs.apply_inspiring_speech(
        t, coach, list(t.roster))["text"])
check("speech: >=3 distinct outcomes over 40 trials",
      len(speech_texts) >= 3)

random.seed(20261002)
backing_texts = set()
for i in range(40):
    t = fresh_team(COACHES["players_coach"], mood=45 + (i % 40))
    me.gm_public_backing(None, t, "room")
    backing_texts.add(t.dynamics_log[-1]["text"])
check("back room: >=2 distinct outcomes over 40 trials",
      len(backing_texts) >= 2)

# --- 8. style actually steers the variants ------------------------------------
random.seed(5)
ds_texts = [rs.apply_great_practice(
    fresh_team(COACHES["drill_sergeant"]),
    COACHES["drill_sergeant"],
    list(fresh_team(COACHES["drill_sergeant"]).roster))["text"]
    for _ in range(30)]
check("drill sergeant's hard-skate variant appears in his practices",
      any("no-nonsense skate" in t for t in ds_texts))

random.seed(5)
pc_texts = [rs.apply_great_practice(
    fresh_team(COACHES["players_coach"]),
    COACHES["players_coach"],
    list(fresh_team(COACHES["players_coach"]).roster))["text"]
    for _ in range(30)]
check("players' coach's battle-drill variant appears in his practices",
      any("battle-drill competition" in t for t in pc_texts))

# --- 9. variety + dedup coexist: same-day repeats stay single ---------------
random.seed(9)
t9 = fresh_team(COACHES["motivator"])
first = rs.apply_great_practice(t9, COACHES["motivator"],
                                list(t9.roster))["text"]
again = rs.apply_great_practice(t9, COACHES["motivator"],
                                list(t9.roster))["text"]
check("same-day repeat returns today's variant (no second entry)",
      first == again and len(t9.dynamics_log) == 1)

print(f"\nR7: {len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
