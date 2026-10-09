# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Smoke: FM24-style player/staff cards, contract popup fit, inbox routing."""
import sys, types
sys.path.insert(0, ".")
from types import SimpleNamespace

import tkinter as tk
import popup_system
from popup_system import register

PASS, FAIL = [], []
def check(n, c, d=""):
    (PASS if c else FAIL).append(n)
    print(("  ok  " if c else "  FAIL") + f" {n}" + (f" -- {d}" if d and not c else ""))

root = tk.Tk(); root.geometry("1600x900"); root.update()
register(root)

import game_classes as g
import reputation_system as rs

# ---------------------------------------------------------------- player
player = g.Player(first_name="Test", last_name="Player", age=24,
                  primary_position=g.PlayerPosition.CENTER, jersey_number=9)
rs.ensure_reputation_fields(player)
team = SimpleNamespace(team_name="Test Club", roster=[player], staff=[])
league = SimpleNamespace(teams=[team], free_agents=[])
app = SimpleNamespace(league=league, user_team=team, open_windows={},
                      BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11",
                      TEXT_COLOR="#ffffff", FONT_FAMILY="Helvetica")

from modern_profile import PlayerProfile
w = PlayerProfile(app, player)
root.update()

labels = set()
def walk(widget, fn):
    for ch in widget.winfo_children():
        try: fn(ch)
        except Exception: pass
        walk(ch, fn)
def grab_labels(ch):
    if isinstance(ch, tk.Label):
        try: labels.add(ch.cget("text"))
        except Exception: pass
walk(w, grab_labels)
check("player card builds", w.winfo_exists())
check("FM24 groups Technical/Mental/Physical",
      {"Technical", "Mental", "Physical"} <= labels, str(sorted(labels)[:5]))
check("player tab strip",
      {"Overview", "Personality", "Scout Report", "Dynamics"} <= labels,
      "all four tabs present")
check("Personality tab card", "Personality" in labels)
# flip to the Dynamics + Scout tabs and confirm their cards build
w._switch_tab("Dynamics"); root.update(); labels.clear(); walk(w, grab_labels)
check("Dynamics tab card", "Team Dynamics" in labels)
w._switch_tab("Scout Report"); root.update(); labels.clear(); walk(w, grab_labels)
check("Scout Report tab card", "Scout Report" in labels)
w._switch_tab("Overview"); root.update(); labels.clear(); walk(w, grab_labels)
check("NHL Readiness kept", "NHL Readiness" in labels)
check("contract strip in header",
      any("Test Club" in t for t in labels), "team line present")

# ---------------------------------------------------------------- staff card
from staff_management_window import StaffManagementView
staff_app = SimpleNamespace(
    league=league, user_team=team, open_windows={},
    tree_maps={}, BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11",
    TEXT_COLOR="#ffffff", FONT_FAMILY="Helvetica",
    game_manager=SimpleNamespace(user_team=team, league=league))
staff_holder = tk.Frame(root, width=1600, height=900)
staff_holder.pack(fill="both", expand=True)
smv = StaffManagementView(staff_holder, app=staff_app)
root.update()

staff = g.Staff(first_name="Test", last_name="Coach",
                role=g.StaffRole.HEAD_COACH, age=50)
staff.ambition = "stanley_cup"; staff.favorite_team = "Test Club"
staff.control_need = 80; staff.gm_trust = 70
try:
    smv.show_staff_details_window(staff, True)
    root.update()
    check("staff details window builds", True)
except Exception as e:
    check("staff details window builds", False, f"{type(e).__name__}: {e}")

slabels = set()
def walk2(node):
    for ch in node.winfo_children():
        walk2(ch)
walk2(root)  # labels collected below via text scan
def collect(ch):
    try:
        import customtkinter as ctk
        if isinstance(ch, (tk.Label, ctk.CTkLabel)):
            slabels.add(str(ch.cget("text")))
    except Exception: pass
walk(root, collect)
for grp in ("Coaching", "Tactical", "Development", "Management", "Personality"):
    check(f"staff attribute group '{grp}'", grp in slabels)
check("staff identity line (style/ambition)",
      any("Stanley Cup" in t for t in slabels), "ambition shown")
check("staff standing section", "Standing" in slabels)

# ---------------------------------------------------------------- contract popup fit
from windows import ContractNegotiationWindow
for mode, kw in (("offer", {}), ("extension", {"is_extension": True})):
    cw = ContractNegotiationWindow(app, player, **kw)
    root.update()
    ok = cw.winfo_exists()
    # find Submit button; it must sit inside the visible card
    found = []
    def find_btn(ch):
        from tkinter import ttk
        if isinstance(ch, ttk.Button) and ch.cget("text") == "Submit Offer":
            found.append(ch)
    walk(cw, find_btn)
    inside = False
    if found:
        b = found[0]
        card_h = cw._popup_size[1]
        inside = (b.winfo_y() + b.winfo_height()) <= card_h + 60  # pinned bottom bar
    check(f"contract window builds + submit visible ({mode})", ok and inside,
          f"btn_inside={inside}")

# ---------------------------------------------------------------- inbox routing
from main import HockeyManagerGUI, GameManager
fake = SimpleNamespace(
    league=SimpleNamespace(teams=[team], free_agents=[],
                           salary_cap_system=None, season_year=2026),
    user_team=SimpleNamespace(team_name="Test Club", payroll=0,
                              add_player=lambda p, r: team.roster.append(p)),
    news_log=[], current_date=__import__("datetime").date(2026, 9, 27),
    media_system=None, update_all_views=lambda: None,
    inbox=[],
)
fake.send_email_to_user = lambda m: fake.inbox.append(m)
for meth in ("handle_contract_offer", "_finalize_contract_signing",
             "_clear_offered_clause",
             "_notify_contract_result", "_inbox_contract_result",
             "_find_inbox_player", "accept_contract_counter",
             "_validate_contract_terms", "get_live_cap",
             "reopen_contract_negotiation"):
    _fn = getattr(HockeyManagerGUI, meth, None) or getattr(GameManager, meth)
    setattr(fake, meth, types.MethodType(_fn, fake))

fa = SimpleNamespace(
    full_name="Free Agent", id="fa1", age=27,
    primary_position=g.PlayerPosition.LEFT_WING,
    salary=0, contract_years=0,
    contract=SimpleNamespace(salary=0, years_remaining=0),
    overall_rating=lambda: 75, value=5_000_000)
fake.league.free_agents.append(fa)

from salary_cap_system import base_ask_dollars as _bad_inbox
def _prod_ask(_pos):
    # Production ask for this fake (ovr 75, age 27, no cap system attached
    # -> base dollars at the 104M cap, floored at the 750k ask floor).
    return max(_bad_inbox(75, 27, False, _pos), 750_000)
asking = _prod_ask("LEFT_WING")   # fa is a winger...
asking_c = _prod_ask("C")         # ...p2/p3/p4 are centers (5% nudge)

# accept path via inbox notify -> consideration period (Muck 2026-10-02):
# no more instant UFA signings; a qualifying offer becomes a bid.
fa.salary, fa.contract_years = asking, 3
res = fake.handle_contract_offer(fa, extension=False, notify="inbox")
check("accept returns 'consideration'", res == "consideration", repr(res))
check("accept -> consideration inbox message",
      len(fake.inbox) == 1 and "considering" in fake.inbox[0].subject.lower(),
      str([m.subject for m in fake.inbox]))
check("accept -> consideration active",
      any(getattr(m, "category", "") == "Contracts" and "considering" in
          getattr(m, "subject", "").lower() for m in fake.inbox))
check("accept -> stays in FA until decided",
      fa in fake.league.free_agents)

# counter path -> interactive inbox message
p2 = SimpleNamespace(
    full_name="Picky Player", id="p2", age=27,
    primary_position=g.PlayerPosition.CENTER,
    salary=int(asking_c * 0.87), contract_years=2,
    contract=SimpleNamespace(salary=0, years_remaining=0),
    overall_rating=lambda: 75, value=5_000_000)
team.roster.append(p2)
fake.inbox.clear()
res = fake.handle_contract_offer(p2, extension=True, notify="inbox")
# extension path uses negotiate_contract; force the free-agent counter path instead
p3 = SimpleNamespace(
    full_name="Counter Player", id="p3", age=27,
    primary_position=g.PlayerPosition.CENTER,
    salary=int(asking_c * 0.87), contract_years=2,
    contract=SimpleNamespace(salary=0, years_remaining=0),
    overall_rating=lambda: 75, value=5_000_000)
fake.league.free_agents.append(p3)
fake.inbox.clear()
res = fake.handle_contract_offer(p3, extension=False, notify="inbox")
check("counter returns False", res is False)
cm = [m for m in fake.inbox if m.action_type == "contract_counter"]
check("counter -> interactive inbox message", len(cm) == 1)
check("counter action_data pickle-safe",
      all(isinstance(v, (str, int, float, bool)) for v in cm[0].action_data.values()))

# accept the counter from the inbox -> consideration (Muck 2026-10-02)
ok = fake.accept_contract_counter(cm[0])
check("inbox accept starts consideration",
      ok and cm[0].action_done)
check("inbox accept posts consideration notice",
      any("considering" in m.subject.lower() for m in fake.inbox))

# reject path
p4 = SimpleNamespace(
    full_name="Reject Player", id="p4", age=27,
    primary_position=g.PlayerPosition.CENTER,
    salary=int(asking_c * 0.65), contract_years=2,
    contract=SimpleNamespace(salary=0, years_remaining=0),
    overall_rating=lambda: 75, value=5_000_000)
fake.league.free_agents.append(p4)
fake.inbox.clear()
res = fake.handle_contract_offer(p4, extension=False, notify="inbox")
check("reject returns False", res is False)
check("reject -> inbox message",
      len(fake.inbox) == 1 and "break down" in fake.inbox[0].subject)

# quiet mode: bulk flows get nothing per player
fake.inbox.clear()
fake.handle_contract_offer(p4, extension=True, notify="quiet")
check("quiet -> no inbox spam", len(fake.inbox) == 0)

# ---------------------------------------------------------------- inbox renderer
from inbox_window import InboxView
from game_classes import EmailMessage
iw = InboxView.__new__(InboxView)
from ctk_theme import (primary_button, secondary_button, heading, body, TEAL, BG, PANEL, CARD, BORDER, TEXT, TEXT_DIM, TEXT_FAINT, GOLD, GREEN, RED, BLUE, ROW_HOVER, ROW_SELECTED)
iw._ct = dict(TEAL=TEAL, BG=BG, PANEL=PANEL, CARD=CARD, BORDER=BORDER,
              TEXT=TEXT, TEXT_DIM=TEXT_DIM, TEXT_FAINT=TEXT_FAINT, GOLD=GOLD,
              GREEN=GREEN, RED=RED, BLUE=BLUE, ROW_HOVER=ROW_HOVER,
              ROW_SELECTED=ROW_SELECTED)
iw._primary_button = primary_button
iw._secondary_button = secondary_button
iw._heading = heading; iw._body = body
import customtkinter as ctk
iw.interactive_frame = ctk.CTkFrame(root)
iw.interactive_frame.pack()
iw.app = fake
msg = EmailMessage(sender="Agent", subject="Counter-offer: X",
                   action_type="contract_counter",
                   action_data={"player_id": "p3", "player_name": "Counter Player",
                                "asking_price": asking, "years": 2,
                                "is_extension": False})
try:
    iw._render_contract_counter(msg)
    root.update()
    btns = [ch.cget("text") for ch in iw.interactive_frame.winfo_children()
            if isinstance(ch, ctk.CTkFrame) for ch in ch.winfo_children()]
    # flatten one level for the button row
    flat = []
    def flatwalk(node):
        for ch in node.winfo_children():
            try:
                if isinstance(ch, ctk.CTkButton): flat.append(ch.cget("text"))
            except Exception: pass
            flatwalk(ch)
    flatwalk(iw.interactive_frame)
    check("counter renderer shows 3 actions",
          any("Accept" in t for t in flat) and "New Offer" in flat and "Walk Away" in flat,
          str(flat))
except Exception as e:
    check("counter renderer builds", False, f"{type(e).__name__}: {e}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
