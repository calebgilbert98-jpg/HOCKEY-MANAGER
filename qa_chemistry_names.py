#!/usr/bin/env python3
"""qa_chemistry_names.py — Chemistry Watch headlines name the line/players,
and non-user-team chemistry routes to the news feed, not the inbox."""
import os
import sys
import types
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed, failed = [], []


def check(name, cond):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name)


import line_chemistry as lc
import headlines as hl

# --- Fake players / team / sim -------------------------------------------


class FakePlayer:
    _next_id = 1000

    def __init__(self, first, last, pos="C"):
        FakePlayer._next_id += 1
        self.id = FakePlayer._next_id
        self.first_name = first
        self.last_name = last
        self.full_name = f"{first} {last}"
        self.position = pos


class FakeTeam:
    def __init__(self, name, lineup):
        self.team_name = name
        self.lineup = lineup
        self.inbox = FakeInbox()


class FakeInbox:
    def __init__(self):
        self.messages = []

    def add_message(self, m):
        self.messages.append(m)


class FakeApp:
    def __init__(self, user_team):
        self.user_team = user_team
        self.current_date = date(2026, 10, 8)
        self.news = []

    def add_news(self, line):
        self.news.append(line)


# --- 1. _unit_line_label -------------------------------------------------
p1 = FakePlayer("Connor", "McDavid", "C")
p2 = FakePlayer("Leon", "Draisaitl", "C")
p3 = FakePlayer("Zach", "Hyman", "LW")
d1 = FakePlayer("Evan", "Bouchard", "RD")
d2 = FakePlayer("Mattias", "Ekholm", "LD")

lineup = {
    "Forwards": [
        [FakePlayer("A", "One"), FakePlayer("B", "Two"), FakePlayer("C", "Three")],
        [p1, p2, p3],
        [FakePlayer("D", "Four"), FakePlayer("E", "Five"), FakePlayer("F", "Six")],
        [FakePlayer("G", "Seven"), FakePlayer("H", "Eight"), FakePlayer("I", "Nine")],
    ],
    "Defense": [[d1, d2]],
    "PP1": {"Forwards": [p1, p2, p3], "Defense": [d1, d2]},
    "PP2": {"Forwards": [], "Defense": []},
    "PK1": {"Forwards": [], "Defense": []},
    "PK2": {"Forwards": [], "Defense": []},
}
team = FakeTeam("Edmonton Oilers", lineup)

check("EV line identified as Line 2",
      lc._unit_line_label([p1, p2, p3, d1, d2], team, "ev") == "Line 2")
check("PP unit identified as PP1",
      lc._unit_line_label([p1, p2, p3, d1, d2], team, "pp") == "PP1")
check("unknown unit returns None",
      lc._unit_line_label([FakePlayer("X", "Y")], team, "ev") is None)
check("no lineup returns None",
      lc._unit_line_label([p1, p2, p3], FakeTeam("T", {}), "ev") is None)
check("never raises on garbage",
      lc._unit_line_label(None, None, None) is None)

# --- 2. _try_emit_story payload ------------------------------------------


class FakeSim:
    def __init__(self):
        self.pending_headlines = []


sim = FakeSim()
lc._try_emit_story(sim, ("k1",), "clicking", "story text here",
                   "ev", 1.20, skaters=[p1, p2, p3, d1, d2], team=team)
check("story emitted", len(sim.pending_headlines) == 1)
pl = sim.pending_headlines[0]
check("payload has player names",
      pl.get("players") == ["Connor McDavid", "Leon Draisaitl",
                            "Zach Hyman", "Evan Bouchard", "Mattias Ekholm"])
check("payload has team name", pl.get("team_name") == "Edmonton Oilers")
check("payload has line label", pl.get("line_label") == "Line 2")
check("payload keeps hook/text/situation",
      pl.get("hook") == "clicking" and pl.get("text") == "story text here"
      and pl.get("situation") == "ev")

# dedupe: same key twice -> one story
lc._try_emit_story(sim, ("k1",), "clicking", "story text here",
                   "ev", 1.20, skaters=[p1], team=team)
check("dedupe by unit key", len(sim.pending_headlines) == 1)

# non-notable efficiency -> no story
sim2 = FakeSim()
lc._try_emit_story(sim2, ("k2",), "ordinary", "meh", "ev", 1.01,
                   skaters=[p1], team=team)
check("ordinary units get no ink", len(sim2.pending_headlines) == 0)

# string team (quick_sim style) -> team_name passthrough, no crash
sim3 = FakeSim()
lc._try_emit_story(sim3, ("k3",), "clicking", "story", "ev", 1.20,
                   skaters=[p1, p2, p3], team="Boston Bruins")
check("string team passthrough",
      sim3.pending_headlines[0].get("team_name") == "Boston Bruins"
      and sim3.pending_headlines[0].get("line_label") == "")

# --- 3. headline rendering -----------------------------------------------
msg = hl._line_chemistry_headline(
    date(2026, 10, 8), hook="clicking", text="The setup man has someone to feed.",
    situation="ev", players=["Connor McDavid", "Leon Draisaitl", "Zach Hyman"],
    team_name="Edmonton Oilers", line_label="Line 2")
check("headline built", msg is not None)
check("subject names team+line",
      "Edmonton Oilers" in msg.subject and "Line 2" in msg.subject)
check("content names players",
      "Connor McDavid" in msg.content and "Zach Hyman" in msg.content)
check("content keeps story", "setup man has someone to feed" in msg.content)
check("no efficiency leak", "1.2" not in msg.content and "1.20" not in msg.content)

# graceful degradation: no names/team/line -> old generic form
msg2 = hl._line_chemistry_headline(
    date(2026, 10, 8), hook="ordinary", text="Some story.", situation="ev")
check("generic fallback subject",
      msg2 is not None and "a ordinary unit at even strength" in msg2.subject)
check("generic fallback content", "One even strength unit" in msg2.content)

# empty story -> None
check("empty story returns None",
      hl._line_chemistry_headline(date(2026, 10, 8), text="") is None)

# --- 4. routing: user team -> inbox, others -> news only -----------------
user_team = FakeTeam("Edmonton Oilers", lineup)
app = FakeApp(user_team)

# user-team chemistry
spec_user = {"kind": "line_chemistry", "hook": "clicking",
             "text": "User team story.", "situation": "ev",
             "players": ["Connor McDavid"], "team_name": "Edmonton Oilers",
             "line_label": "Line 2"}
check("user-team spec delivers", hl.deliver_spec(app, spec_user) is True)
check("user-team chemistry in inbox",
      len(user_team.inbox.messages) == 1
      and "Edmonton Oilers" in user_team.inbox.messages[0].subject)
check("user-team chemistry on news feed", len(app.news) == 1)

# other-team chemistry
spec_other = {"kind": "line_chemistry", "hook": "clicking",
              "text": "Other team story.", "situation": "ev",
              "players": ["Auston Matthews"], "team_name": "Toronto Maple Leafs",
              "line_label": "Line 1"}
# reset daily cap so the second delivery isn't blocked
app._headline_daily = {"date": date(2026, 10, 8), "count": 0}
check("other-team spec delivers", hl.deliver_spec(app, spec_other) is True)
check("other-team chemistry NOT in user inbox",
      len(user_team.inbox.messages) == 1)  # still just the first one
check("other-team chemistry on news feed",
      len(app.news) == 2 and "Toronto Maple Leafs" in app.news[1])

# unknown team -> news only, never raises, never inbox
spec_unknown = {"kind": "line_chemistry", "hook": "clicking",
                "text": "Mystery story.", "situation": "ev",
                "players": [], "team_name": "", "line_label": ""}
app._headline_daily = {"date": date(2026, 10, 8), "count": 0}
check("unknown-team spec delivers", hl.deliver_spec(app, spec_unknown) is True)
check("unknown-team not in inbox", len(user_team.inbox.messages) == 1)
check("unknown-team on news feed", len(app.news) == 3)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
