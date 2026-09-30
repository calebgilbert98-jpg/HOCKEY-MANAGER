"""R3 QA: Trade Center data binding.

Covers the reported failure (NameError on CTkPlayerList aborting
__init__ mid-build):
  - the window opens fully with no exception;
  - both clubs' NHL / AHL / Prospects lists populate on tab switch;
  - "Their needs:" computes and displays;
  - the deal-construction side (offer lists, meter, Send Offer)
    renders and reacts.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_r3_trade_center.py
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/wt-ui-repairs")

import tkinter as tk
from popup_system import register
from game_classes import Player, PlayerPosition, Team

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


def make_player(pid, first, last, pos):
    p = Player(first_name=first, last_name=last, age=27,
               primary_position=pos)
    p.id = pid
    return p


def make_team(name, nhl_n=20, ahl_n=6, prosp_n=4):
    t = Team(team_name=name, city=name.split()[0],
             division="Pacific", conference="Western")
    t.league_name = "National Hockey League"
    poss = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
            PlayerPosition.RIGHT_WING, PlayerPosition.DEFENSE]
    t.roster = [make_player(i, f"N{i:02d}", f"Player{i:02d}", poss[i % 4])
                for i in range(nhl_n)]
    t.roster.append(make_player(90, "Net", "Minder", PlayerPosition.GOALIE))
    t.ahl_roster = [make_player(100 + i, f"A{i:02d}", f"Minor{i:02d}",
                                poss[i % 4]) for i in range(ahl_n)]
    t.prospects = [make_player(200 + i, f"P{i:02d}", f"Prosp{i:02d}",
                               poss[i % 4]) for i in range(prosp_n)]
    return t


user_team = make_team("Edmonton Oilers")
carolina = make_team("Carolina Hurricanes")
boston = make_team("Boston Bruins")
league = SimpleNamespace(
    teams=[user_team, carolina, boston],
    standings={user_team.team_name: {"W": 10, "L": 5, "OTL": 2, "Points": 22},
               carolina.team_name: {"W": 8, "L": 8, "OTL": 1, "Points": 17},
               boston.team_name: {"W": 12, "L": 3, "OTL": 1, "Points": 25}})
gm = SimpleNamespace(trade_history=[], user_team=user_team)
app = SimpleNamespace(
    BG_COLOR="#0e0e11", FONT_FAMILY="Segoe UI",
    user_team=user_team, league=league, game_manager=gm,
    ai_manager=SimpleNamespace(),
)

root = tk.Tk()
root.geometry("1500x950")
register(root)
root.update()

import windows

opened = True
try:
    win = windows.TradeWindow(app)
    root.update()
    root.update_idletasks()
except Exception as e:  # noqa: BLE001 -- the reported failure mode
    opened = False
    print(f"window __init__ raised: {type(e).__name__}: {e}")
check("Trade Center opens with no exception", opened)
if not opened:
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1)


def allw(w):
    out = [w]
    for ch in w.winfo_children():
        out.extend(allw(ch))
    return out


# both clubs' NHL lists populate on open (default partner: 1st alphabetical)
check("user NHL list populated",
      len(win.user_list._rows) == len(user_team.roster),
      f"{len(win.user_list._rows)} rows vs {len(user_team.roster)} roster")
check("partner NHL list populated",
      len(win.partner_list._rows) == len(boston.roster),
      f"{len(win.partner_list._rows)} rows vs {len(boston.roster)} roster")
check("partner title names the club",
      "Boston Bruins" in win.partner_title.cget("text"),  # 1st alphabetical
      repr(win.partner_title.cget("text")))

# their needs computes
needs = win.needs_label.cget("text")
check("'Their needs:' non-empty", bool(needs and needs.strip()),
      repr(needs))

# tab switches repopulate both sides
win._user_level.set("AHL")
win._refresh_user_list()
root.update_idletasks()
check("user AHL tab populates",
      len(win.user_list._rows) == len(user_team.ahl_roster),
      f"{len(win.user_list._rows)} rows")

win._user_level.set("Prospects")
win._refresh_user_list()
root.update_idletasks()
check("user Prospects tab populates",
      len(win.user_list._rows) == len(user_team.prospects),
      f"{len(win.user_list._rows)} rows")

win._user_level.set("NHL")
win._refresh_user_list()
win._partner_level.set("AHL")
win.update_trade_partner_roster()
root.update_idletasks()
check("partner AHL tab populates",
      len(win.partner_list._rows) == len(carolina.ahl_roster),
      f"{len(win.partner_list._rows)} rows")
check("partner title tracks level",
      "(AHL)" in win.partner_title.cget("text"),
      repr(win.partner_title.cget("text")))

win._partner_level.set("Prospects")
win.update_trade_partner_roster()
root.update_idletasks()
check("partner Prospects tab populates",
      len(win.partner_list._rows) == len(carolina.prospects),
      f"{len(win.partner_list._rows)} rows")

# deal-construction side renders
widgets = allw(win)
texts = set()
for w in widgets:
    try:
        texts.add(str(w.cget("text")))
    except Exception:
        pass
check("deal panel: offer lists present",
      win.user_offer_list.winfo_exists()
      and win.partner_offer_list.winfo_exists())
check("deal panel: trade meter present", win.meter_canvas.winfo_exists())
check("deal panel: Send Offer button present",
      win.propose_btn.winfo_exists()
      and "Send Offer" in str(win.propose_btn.cget("text")),
      repr(win.propose_btn.cget("text")))
check("deal panel: retention section present",
      win.retention_frame.winfo_exists())

# adding assets to the deal works and the meter reacts
win._partner_level.set("NHL")
win.update_trade_partner_roster()
p0 = win.user_list._players[0]
q0 = win.partner_list._players[0]
win.trade_offers["user"] = [p0]
win._asset_levels["user"] = {id(p0): "NHL"}
win.trade_offers["partner"] = [q0]
win._asset_levels["partner"] = {id(q0): "NHL"}
try:
    win._refresh_offer_lists()
    win._update_meter()
    root.update_idletasks()
    meter_ok = True
except Exception as e:  # noqa: BLE001
    meter_ok = False
    print(f"offer/meter refresh raised: {type(e).__name__}: {e}")
check("offer lists + meter refresh with assets", meter_ok)
check("meter label reacts to assets",
      win.meter_label.cget("text") != "Add assets to evaluate",
      repr(win.meter_label.cget("text")))

# partner switch repopulates + clears their side of the deal
win.partner_combo.set("Carolina Hurricanes")
win.update_trade_partner_roster()
root.update_idletasks()
check("partner switch repopulates list",
      len(win.partner_list._rows) == len(carolina.roster),
      f"{len(win.partner_list._rows)} rows")
check("partner switch clears their offer side",
      win.trade_offers["partner"] == [])

# ------------------------------------------------------------------
# R3(b): "Analyze Trade Value" -- engine breakdown + context menu
# ------------------------------------------------------------------
import random
import trade_engine as te

random.seed(20260929)
_mismatch = 0
for i in range(300):
    pos = random.choice(list(PlayerPosition))
    p = make_player(1000 + i, "Val", f"Player{i:03d}", pos)
    p.age = random.randint(18, 40)
    p.potential_grade = random.choice(["A", "B", "C", "D", "F"])
    p.contract = SimpleNamespace(
        salary=random.choice([800_000, 2_000_000, 6_000_000, 11_000_000]))
    total, comps = te.player_trade_value_breakdown(p)
    if total != te.player_trade_value(p):
        _mismatch += 1
check("R3(b) breakdown total == engine value (300 randomized)",
      _mismatch == 0, f"{_mismatch} mismatches")

# overpaid veteran -> contract discount line
old = make_player(2001, "Old", "Overpaid", PlayerPosition.CENTER)
old.age = 36
old.contract = SimpleNamespace(salary=11_000_000)
_, comps_o = te.player_trade_value_breakdown(old)
check("R3(b) overpaid veteran shows contract discount",
      any(c["label"] == "Contract efficiency" and c["delta"] < 0
          for c in comps_o),
      str([(c["label"], c["delta"]) for c in comps_o]))

# young A-potential -> premium + age-curve lines
kid = make_player(2002, "Young", "Star", PlayerPosition.CENTER)
kid.age = 20
kid.potential_grade = "A"
_, comps_k = te.player_trade_value_breakdown(kid)
check("R3(b) young A-potential shows premium lines",
      any(c["label"] == "Potential premium" and c["delta"] > 0
          for c in comps_k)
      and any(c["label"] == "Age curve" and c["delta"] > 0
              for c in comps_k))

# elite goalie -> goalie premium line
gel = make_player(2003, "Elite", "Goalie", PlayerPosition.GOALIE)
gel.overall_rating = lambda: 86
_, comps_g = te.player_trade_value_breakdown(gel)
check("R3(b) 86-OVR goalie shows starting-goalie premium",
      any(c["label"] == "Starting-goalie premium" and c["delta"] > 0
          for c in comps_g))

# context menu carries the entry (captured tk_popup)
from player_context_menu import PlayerContextMenu
mgr = PlayerContextMenu(win)
_captured = {}
_orig_popup = tk.Menu.tk_popup


def _fake_popup(self, x, y):
    _captured["menu"] = self


evt = SimpleNamespace(x_root=100, y_root=100, widget=root)
tk.Menu.tk_popup = _fake_popup
try:
    mgr.show_context_menu(evt, kid)
finally:
    tk.Menu.tk_popup = _orig_popup
_menu = _captured.get("menu")
_labels = []
if _menu is not None:
    try:
        _n = _menu.index("end")
        _labels = [_menu.entrycget(i, "label")
                   for i in range(_n + 1)
                   if _menu.type(i) == "command"]
    except Exception:
        _labels = []
check("R3(b) right-click menu has 'Analyze Trade Value'",
      "Analyze Trade Value" in _labels, str(_labels))


def _find_text(widget, substr):
    found = []
    try:
        for child in widget.winfo_children():
            try:
                if isinstance(child, (tk.Label, tk.Message)) \
                        and substr in str(child.cget("text")):
                    found.append(child)
            except Exception:
                pass
            found.extend(_find_text(child, substr))
    except Exception:
        pass
    return found


# the dialog itself renders the breakdown
mgr._analyze_trade_value(kid)
root.update_idletasks()
_dlg_hits = _find_text(root, "pick-points")
check("R3(b) Analyze dialog renders value + breakdown",
      len(_dlg_hits) >= 1, f"{len(_dlg_hits)} hits")
_prem_hits = _find_text(root, "Potential premium")
check("R3(b) Analyze dialog shows component rows",
      len(_prem_hits) >= 1)

# ------------------------------------------------------------------
# R3(c): AI trade rationale grounded in real systems
# ------------------------------------------------------------------
needs = te.team_needs(carolina)[:2]
_pos_for = {"C": PlayerPosition.CENTER, "LW": PlayerPosition.LEFT_WING,
            "RW": PlayerPosition.RIGHT_WING, "LD": PlayerPosition.LEFT_DEFENSE,
            "RD": PlayerPosition.RIGHT_DEFENSE, "G": PlayerPosition.GOALIE}
need_player = make_player(3001, "Need", "Filler", _pos_for[needs[0]])
need_player.overall_rating = lambda: 80
pts = te.trade_talking_points(
    carolina, [need_player], [],
    partner=user_team,
    situational={"notes": ["buying for a Cup run"], "greed_mult": 0.9})
check("R3(c) talking points cite the positional need",
      any(f"need at {needs[0]}" in p for p in pts), str(pts))
check("R3(c) talking points cite the contention window",
      any("Cup run" in p for p in pts), str(pts))

# ai_consider_trade: accept message carries specific rationale
star = make_player(3002, "Big", "Star", PlayerPosition.CENTER)
star.overall_rating = lambda: 94
star.age = 27
scrub = make_player(3003, "Small", "Scrub", PlayerPosition.CENTER)
scrub.overall_rating = lambda: 62
resp = te.ai_consider_trade(
    carolina, [star], [scrub], user_team=user_team, patience=1.0,
    situational={"notes": ["buying for a Cup run"], "greed_mult": 0.85})
check("R3(c) AI accept decision unchanged", resp.decision == "accept",
      f"{resp.decision}: {resp.message}")
check("R3(c) AI accept message has specific rationale",
      resp.message != "You've got a deal."
      and ("need at" in resp.message or "Cup run" in resp.message),
      resp.message)

# incoming_offer: AI-initiated proposal is specific, not filler
# (stub league gives situational_context real standings -> buyer stance)
gm_stub = SimpleNamespace(trade_negotiations=[], league=league)
app_stub = SimpleNamespace(
    user_team=user_team, game_manager=gm_stub,
    current_date=__import__("datetime").date(2026, 11, 15),
    update_inbox_notification=lambda: None,
)
user_team.inbox = SimpleNamespace(
    messages=[], add_message=lambda m: user_team.inbox.messages.append(m))
import trade_negotiation as tn
neg = tn.incoming_offer(app_stub, carolina, [scrub], player_wanted=star)
check("R3(c) AI proposal last_message is specific (not filler)",
      "interested in making a deal" not in neg.last_message
      and ("need at" in neg.last_message or "Our thinking" in neg.last_message),
      neg.last_message)

# ------------------------------------------------------------------
# R8(ii): busy/loading indicator on the trade center
# ------------------------------------------------------------------
check("R8(ii) busy label exists in trade center header",
      getattr(win, "_busy_label", None) is not None)
win._set_busy(True, "Loading rosters...")
root.update_idletasks()
check("R8(ii) busy shows status text",
      "Loading rosters..." in str(win._busy_label.cget("text")))
win._set_busy(False)
root.update_idletasks()
check("R8(ii) busy clears after work",
      str(win._busy_label.cget("text")) == "")
# heavy ops leave the indicator cleared
win.update_trade_partner_roster()
root.update_idletasks()
check("R8(ii) partner switch leaves busy cleared",
      str(win._busy_label.cget("text")) == "")

root.destroy()
print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
