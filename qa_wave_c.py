"""QA: Wave C fans/media/market (D22/D34/D36/D37/D39). Headless.

Run via: python3 /tmp/run_qa_wt_c.py /home/hatch/workspace/wt-wave-c/qa_wave_c.py
"""
import random
from datetime import date
from types import SimpleNamespace

import fan_sentiment as fs
import arena_atmosphere as atm
import manager_career as mc
import reputation_system as rs
import media_engine as me
import headlines

PASS, FAIL = 0, 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {extra}")


def fake_team(name, **kw):
    t = SimpleNamespace(team_name=name, roster=[], recent_results=[],
                        wins=0, losses=0, ot_losses=0, games_played=0)
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def fake_player(name, pid=1, **kw):
    fn, ln = (name.split(" ", 1) + [""])[:2]
    p = SimpleNamespace(first_name=fn, last_name=ln, full_name=name, id=pid,
                        primary_position="C", morale=70, happiness=70,
                        games_played=0, birthplace="Toronto, ON",
                        nationality="Canada", squad_status="Top 6")
    for k, v in kw.items():
        setattr(p, k, v)
    return p


print("== D22/D34 fan_sentiment module ==")
t = fake_team("Toronto Maple Leafs")
check("default is 60", fs.get_fan_sentiment(t) == 60.0)
check("nudge up", fs.nudge_fan_sentiment(t, 5, reason="presser", current_date=date(2026, 10, 1)) == 65.0)
check("nudge clamps at 0", fs.nudge_fan_sentiment(t, -500, current_date=date(2026, 10, 1)) == 0.0)
check("nudge clamps at 100", fs.nudge_fan_sentiment(t, 500, current_date=date(2026, 10, 1)) == 100.0)
check("trail recorded", len(getattr(t, "fan_sentiment_trail", [])) > 0)

# baseline from recent results: 10 straight wins -> hot baseline
hot = fake_team("X", recent_results=["W"] * 10)
check("hot baseline high", fs.sentiment_baseline(hot) > 85, fs.sentiment_baseline(hot))
cold = fake_team("X", recent_results=["L"] * 10)
check("cold baseline low", fs.sentiment_baseline(cold) < 35, fs.sentiment_baseline(cold))

# drift: 90 with a cold team, 30 days ago -> drifts down toward baseline
t2 = fake_team("Y", recent_results=["L"] * 10)
t2.fan_sentiment = 90.0
t2.fan_sentiment_date = "2026-09-01"
v = fs.get_fan_sentiment(t2, date(2026, 10, 1))
check("drift moves toward baseline", v < 90.0, v)
check("drift bounded by rate", v >= 90.0 - 1.5 * 30, v)
check("labels", fs.sentiment_label(90) == "Electric" and fs.sentiment_label(10) == "Toxic")

print("== D34 pregame_crowd additions ==")
home = fake_team("Toronto Maple Leafs", recent_results=["W"] * 5)
away = fake_team("Buffalo Sabres")
base = atm.pregame_crowd(home, away)
happy = atm.pregame_crowd(home, away, fan_sentiment=90)
sad = atm.pregame_crowd(home, away, fan_sentiment=20)
check("happy fans lift mood", happy["mood"] > base["mood"], (base["mood"], happy["mood"]))
check("angry fans sink mood", sad["mood"] < base["mood"], (base["mood"], sad["mood"]))
check("buzzing driver", any("buzzing" in d for d in happy["drivers"]), happy["drivers"])
check("win streak driver", any("Winners of 5 straight" in d for d in base["drivers"]), base["drivers"])
fav = atm.pregame_crowd(home, away, fan_fav_names=["Auston Matthews"])
check("fan favourite driver", any("Buzzing for Auston Matthews" in d for d in fav["drivers"]), fav["drivers"])
check("favourite lifts energy", fav["energy"] > base["energy"])
hate = atm.pregame_crowd(home, away, hated_returnee_names=["John Tavares"])
check("simmering hate driver", any("Still not forgiven" in d for d in hate["drivers"]), hate["drivers"])

# live eruption for a fan favourite goal
st = {"energy": 50.0, "mood": 30.0}
st2 = {"energy": 50.0, "mood": 30.0}
atm.live_crowd_update(st, True, 1, 0, scorer_is_fan_favourite=False)
atm.live_crowd_update(st2, True, 1, 0, scorer_is_fan_favourite=True)
check("favourite goal erupts more", st2["energy"] > st["energy"], (st["energy"], st2["energy"]))

print("== D37 market happiness ==")
leafs = fake_team("Toronto Maple Leafs", wins=20, losses=10)
utah = fake_team("Utah Hockey Club", wins=20, losses=10)

rus_rookie = fake_player("Ivan Petrov", pid=7, birthplace="Moscow, Russia",
                         nationality="Russia", morale=40, games_played=5)
d, r = mc.market_happiness_delta(rus_rookie, leafs)
check("homesick rookie in fishbowl is unhappy", d < 0, (d, r))
check("bounded", -6 <= d <= 5, d)

hometown = fake_player("Mitch Marner", pid=2, birthplace="Toronto, ON",
                       nationality="Canada", morale=70, games_played=300)
d2, r2 = mc.market_happiness_delta(hometown, leafs)
check("hometown veteran comfortable", d2 > 0, (d2, r2))

star = fake_player("Auston Matthews", pid=3, birthplace="San Ramon, CA",
                   nationality="United States", morale=80, games_played=400)
d3, r3 = mc.market_happiness_delta(star, leafs)
check("thriving star likes the stage", d3 > 0 and "stage" in r3, (d3, r3))

vet_utah = fake_player("Ivan Petrov", pid=7, birthplace="Moscow, Russia",
                       nationality="Russia", morale=70, games_played=200)
d4, r4 = mc.market_happiness_delta(vet_utah, utah)
check("settled vet in loyal market cushioned", d4 >= 0, (d4, r4))
check("no team -> zero", mc.market_happiness_delta(star, None) == (0, ""))

# weekly hook applies it
p = fake_player("Test Player", pid=9, birthplace="Moscow, Russia",
                nationality="Russia", morale=40, games_played=5,
                happiness=70, playing_time_concern=0)
ev = mc.update_player_happiness(p, 20, team=leafs)
check("weekly applies market delta", 0 <= p.happiness <= 100 and isinstance(ev, list),
      (p.happiness, ev))
check("legacy signature still works", isinstance(mc.update_player_happiness(p, 20), list))

print("== D39 simmering hate ==")
home_t = fake_team("Toronto Maple Leafs")
away_t = fake_team("New York Islanders")
ret = fake_player("John Tavares", pid=11)
away_t.roster = [ret]
rivs = []
rs.record_fan_hate(rivs, ret, hated_by=home_t, origin="defection",
                   intensity=55, story="defected")
check("record created un-faced", len(rivs) == 1 and not rivs[0].get("faced"))
check("no simmer before first homecoming", rs.simmering_hate(rivs, home_t, away_t) == [])
res = rs.apply_homecoming_pregame(rivs, home_t, away_t)
check("first-timer consumed once", len(res["first_timers"]) == 1)
check("marked faced", rivs[0].get("faced") is True)
res2 = rs.apply_homecoming_pregame(rivs, home_t, away_t)
check("second visit is simmering", len(res2["first_timers"]) == 0 and len(res2["simmering"]) == 1,
      (len(res2["first_timers"]), len(res2["simmering"])))
check("simmer carries intensity", res2["simmering"][0]["intensity"] == 55)

# faced hate decays faster than un-faced
r_faced = dict(rivs[0])
r_fresh = dict(rivs[0]); r_fresh["faced"] = False
l1, l2 = [dict(r_faced)], [dict(r_fresh)]
rs.decay_rivalries(l1, years=1)
rs.decay_rivalries(l2, years=1)
check("faced decays faster", l1[0]["intensity"] < l2[0]["intensity"],
      (l1[0]["intensity"], l2[0]["intensity"]))

print("== D36 fine appeal + headline ==")
msg = headlines.make_headline("media_fine", date(2026, 10, 1), name="Ivan Petrov",
                              team="Toronto Maple Leafs", amount=10000,
                              reason="criticizing officiating", appealable=True)
check("appealable headline action", msg is not None and msg.action_type == "media_fine_response",
      getattr(msg, "action_type", None))
check("action data shape", (msg.action_data or {}).get("responded") is False)
plain = headlines.make_headline("media_fine", date(2026, 10, 1), name="X",
                                team="Buffalo Sabres", amount=5000, reason="yapping")
check("non-appealable stays plain", plain is not None and plain.action_type is None)

league = SimpleNamespace(media_fines=[
    {"date": date(2026, 10, 1), "name": "Ivan Petrov",
     "team": "Toronto Maple Leafs", "amount": 10000,
     "reason": "criticizing officiating"}])
app = SimpleNamespace(game_manager=SimpleNamespace(league=league),
                      news=[], add_news=lambda s: app.news.append(s))
random.seed(1)
data = dict(msg.action_data)
out = me.resolve_fine_appeal(app, data, "accept")
check("accept responds", data["responded"] is True and out, out)
check("accept marks ledger", league.media_fines[0].get("status") == "accepted",
      league.media_fines[0])
data2 = dict(msg.action_data)
random.seed(42)
out2 = me.resolve_fine_appeal(app, data2, "appeal")
rec = league.media_fines[0]
check("appeal responds", data2["responded"] is True and bool(out2), out2)
check("appeal marks ledger", rec.get("appealed") is True and rec.get("status") in ("reduced", "upheld"), rec)
if rec.get("status") == "reduced":
    check("reduction halves amount", rec["amount"] == 5000, rec["amount"])

print(f"\n{ PASS } passed, { FAIL } failed")
raise SystemExit(1 if FAIL else 0)
