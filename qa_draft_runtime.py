"""Runtime QA: full 224-pick entry draft through the REAL DraftView.

Run under xvfb (never headless -- this validates the real UI):
    xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_draft_runtime.py

- Builds a 32-team league + 224-prospect class.
- Instantiates the real DraftView in a 1600x900 window.
- Auto-declines incoming user calls (deterministic; the dialog itself is
  screenshotted separately through the real code path).
- Drives all 224 picks synchronously (AI steps + user auto-picks), with
  the real round-1 AI-AI and AI-user trade checks live.
- Validates completion, pick counts, ownership propagation, no crashes.
- Screenshots: available tab, prospect card, results tab, my picks tab,
  incoming-call dialog, Draft Day Central hub.
"""
import datetime
import os
import random
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260928)


def _probe_market_deals():
    """Deterministic multi-seed probe that the draft-day trade market fires.

    The market is probabilistic by design, so one pinned seed can go silent;
    this runs round 1 on a few seeds in a withdrawn root and returns every
    recorded deal. The dialog is auto-declined (no user in the harness).
    """
    from windows import DraftView
    import draft_day_trades as ddt
    from draft_generator import generate_draft_class
    from ai_team_management import ManagementPriority
    from qa_draft_common import make_league
    _real = ddt._incoming_call_dialog
    ddt._incoming_call_dialog = lambda *a, **k: 'decline'
    found = []
    _pr = tk.Tk()
    _pr.withdraw()
    try:
        for _ms in (7, 99, 1234):
            random.seed(_ms)
            _lg, _nhl = make_league(2027)
            _lg.draft_prospects = generate_draft_class(num_prospects=224,
                                                       quality="Normal")
            _u = _nhl[3]
            _u.is_user_team = True
            _mp = {t.team_name: (ManagementPriority.REBUILD if i < 10
                                 else ManagementPriority.CONTEND)
                   for i, t in enumerate(_nhl)}
            _app = RuntimeApp(_lg, _u, _mp)
            _v = DraftView(_pr, app=_app)
            _v.pack(fill="both", expand=True)
            _pr.update()
            while _v.current_pick < 32:
                _r, _t, _dp = _v.draft_order[_v.current_pick]
                if _t == _app.user_team or _v._mp_clock_for(_t):
                    break
                _v._ai_step()
                _pr.update()
            _d = list(getattr(_lg, 'draft_day_deals', None) or [])
            print(f"info: market probe seed {_ms}: {len(_d)} deals", flush=True)
            found.extend(_d)
            _v.destroy()
            if found:
                break
    finally:
        _pr.destroy()
        ddt._incoming_call_dialog = _real
    random.seed(20260928)
    return found


import draft_day_trades as ddt
from draft_generator import generate_draft_class
from ai_team_management import ManagementPriority
from qa_draft_common import make_league, StubAIMgr

PASS = 0
FAIL = 0
SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "qa_shots_draft")
os.makedirs(SHOT_DIR, exist_ok=True)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}", flush=True)
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}", flush=True)


class RuntimeApp:
    """Enough app surface for DraftView to run for real."""
    def __init__(self, league, user_team, mapping):
        self.league = league
        self.user_team = user_team
        self.ai_manager = StubAIMgr(mapping)
        self.current_date = datetime.date(2027, 6, 28)
        self.news_log = []
        self.open_windows = {}
        self.mp_host = None

    def add_news_story(self, s):
        self.news_log.append(s)

    def add_news(self, s):
        self.news_log.append(s)

    def open_player_profile(self, *a, **k):
        pass

    def _sort_treeview_generic(self, *a, **k):
        pass

    def _bind_player_context_menu(self, *a, **k):
        pass

    def show_screen(self, *a, **k):
        pass

    def _mp_clear_draft_clock(self):
        pass


def grab(win, name):
    win.update()
    win.update_idletasks()
    from PIL import ImageGrab
    x, y = win.winfo_rootx(), win.winfo_rooty()
    w, h = win.winfo_width(), win.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    path = os.path.join(SHOT_DIR, name)
    img.save(path)
    print(f"shot {name} ({w}x{h})", flush=True)
    return path


def main():
    from windows import DraftView

    # Deterministic market probe (multi-seed; the market is probabilistic).
    # Runs once here so the deals check below can rely on it.
    market_probe_deals = _probe_market_deals()

    lg, nhl = make_league(2027)
    lg.draft_prospects = generate_draft_class(num_prospects=224,
                                              quality="Normal")
    _shot_prospect = lg.draft_prospects[0]  # class is consumed by the draft
    user_team = nhl[3]
    user_team.is_user_team = True
    mapping = {t.team_name: (ManagementPriority.REBUILD if i < 10
                             else ManagementPriority.CONTEND)
               for i, t in enumerate(nhl)}
    app = RuntimeApp(lg, user_team, mapping)

    # Deterministic: the user always declines the phone in the full run.
    # (The dialog itself is exercised + screenshotted separately below.)
    _real_dialog = ddt._incoming_call_dialog
    ddt._incoming_call_dialog = lambda *a, **k: 'decline'

    root = tk.Tk()
    root.geometry("1600x900")
    root.title("Puck Dynasty - draft runtime QA")
    try:
        from popup_system import register as _register_popups
        _register_popups(root)
    except Exception:
        pass
    view = DraftView(root, app=app)
    view.pack(fill="both", expand=True)
    root.update()

    # NOTE: DraftView.__init__ already calls start_draft(). An explicit
    # second call used to live here; it rebuilt the order AFTER draft-day
    # trades fired, showing 225 rows for 224 slots and re-rolling the 32
    # team boards mid-draft. start_draft() now guards against re-entry,
    # so this stays a single start.
    # The driver below owns advancement: cancel the after()-scheduled
    # pick and suppress re-scheduling so nothing double-drives.
    try:
        if view._ai_after_id:
            view.after_cancel(view._ai_after_id)
    except Exception:
        pass
    view._ai_after_id = None
    view._sim_active = True
    root.update()
    check("draft order is 224 picks", len(view.draft_order) == 224,
          str(len(view.draft_order)))
    grab(root, "01_available_tab.png")

    # Prospect card: select the first available prospect.
    kids = view.available_tree.get_children()
    check("available tree populated", len(kids) > 0, str(len(kids)))
    if kids:
        view.available_tree.selection_set(kids[0])
        view._on_available_select()
        root.update()
    grab(root, "02_prospect_card.png")
    card_texts = []

    def _collect(w):
        try:
            t = w.cget("text")
            if t:
                card_texts.append(str(t))
        except Exception:
            pass
        try:
            for c in w.winfo_children():
                _collect(c)
        except Exception:
            pass

    try:
        _collect(view.prospect_card)
    except Exception:
        pass
    card_text = " ".join(card_texts)
    check("prospect card shows a name", bool(card_text.strip()),
          card_text[:80])

    # Two-step confirm visual: arm the button, screenshot, disarm.
    if kids and view.selected_prospect is not None:
        view._arm_draft_button(view.selected_prospect)
        root.update()
    grab(root, "02b_confirm_armed.png")
    armed_text = ""
    try:
        armed_text = view.draft_button.cget("text")
    except Exception:
        pass
    check("arm shows CONFIRM label", "CONFIRM" in armed_text, armed_text)
    view._disarm_draft_button()

    # Drive the full draft synchronously. _sim_active suppresses the
    # after()-scheduled driver so this loop owns advancement.
    guard = 0
    phone_rang = 0
    orig_incoming = ddt.incoming_offer_for_user
    while view.current_pick < len(view.draft_order) and guard < 2000:
        guard += 1
        if view.current_pick >= len(view.draft_order):
            break
        _r, _t, _dp = view.draft_order[view.current_pick]
        if _t == app.user_team or getattr(_t, 'is_user_team', False):
            if _r == 1:
                # Real user-call path (auto-declined above).
                try:
                    orig_incoming(view)
                    phone_rang += 1
                except Exception as e:
                    check("incoming call path crash-free", False, str(e))
                    break
                _r2, _t2, _dp2 = view.draft_order[view.current_pick]
                if _t2 == app.user_team or getattr(_t2, 'is_user_team',
                                                   False):
                    view.auto_pick()
            else:
                view.auto_pick()
        else:
            if not view._ai_step():
                # user clock / drama pause / end: loop re-evaluates
                continue
    view._sim_active = False
    root.update()
    check("draft loop terminated", guard < 2000, f"guard={guard}")
    check("all 224 picks made", len(view.picks_made) == 224,
          str(len(view.picks_made)))
    check("draft order exhausted",
          view.current_pick >= len(view.draft_order),
          f"{view.current_pick}/{len(view.draft_order)}")
    try:
        view.end_draft()
    except Exception as e:
        check("end_draft crash-free", False, str(e))
    root.update()

    # Results + My Picks tabs render.
    view._draft_board_tab("Results")
    root.update()
    grab(root, "03_results_tab.png")
    check("results tree shows 224 rows",
          len(view.draft_results_tree.get_children()) == 224,
          str(len(view.draft_results_tree.get_children())))
    view._draft_board_tab("My Picks")
    root.update()
    grab(root, "04_mypicks_tab.png")
    my_rows = view.mypicks_tree.get_children()
    check("my picks tab non-empty", len(my_rows) > 0, str(len(my_rows)))

    # Ownership: every pick object lives in its current team's year list.
    year = lg.season_year
    bad = 0
    for _r, _t, _dp in view.draft_order:
        if _dp is not None and not any(
                _dp is q for q in _t.get_picks_for_year(year)):
            bad += 1
    check("every pick object owned by its current team", bad == 0,
          str(bad))

    # Draft-day deals recorded (AI-AI market ran live in round 1). The market
    # is probabilistic by design (0.45 gate per slot + offer/negotiation can
    # fail), so a single pinned seed may legitimately go silent -- the
    # multi-seed probe at startup (market_probe_deals) verifies it fires.
    deals = list(getattr(lg, 'draft_day_deals', None) or [])
    print(f"info: {len(deals)} draft-day deals in the full run", flush=True)
    for _d in deals[:6]:
        print(f"  deal: {_d}", flush=True)
    deals.extend(market_probe_deals)
    check("draft-day market produced deals", len(deals) > 0,
          "silent draft day")

    # Incoming-call dialog: real code path, screenshot, auto-dismiss.
    # (Source picks from the draft order -- the class is spent by now.)
    _r1 = [row for row in view.draft_order if row[0] == 1 and row[2]]
    _caller = _r1[10][1] if len(_r1) > 10 else nhl[10]
    _gives = [_r1[10][2]] if len(_r1) > 10 else []
    _gets = [row[2] for row in view.draft_order
             if row[0] == 1 and row[2] and row[1] == user_team][:1]
    _prospects = [_shot_prospect]
    if _gives and _prospects:
        import trade_engine as te
        _prosp = _prospects[0]
        _why = ddt._call_why_lines(te, _caller, _prosp,
                                   ddt._draft_board(lg), "rebuild")
        orig_ww = tk.Misc.wait_window

        def fake_wait(self, w):
            root.after(900, lambda: grab(root, "05_incoming_call.png"))
            root.after(1800, lambda: w.destroy())
            return orig_ww(self, w)

        tk.Misc.wait_window = fake_wait
        ddt._incoming_call_dialog = _real_dialog
        try:
            choice = ddt._incoming_call_dialog(
                view, _caller, list(_gives), list(_gets), _prosp, 4, _why)
        finally:
            tk.Misc.wait_window = orig_ww
        root.update()
        check("call dialog dismisses via destroy", choice == 'decline',
              str(choice))
        check("call dialog screenshot taken",
              os.path.exists(os.path.join(SHOT_DIR, "05_incoming_call.png")))

    # Draft Day Central hub: live sections + screenshot (own window so the
    # draft's grades popup doesn't cover it).
    from event_day_hubs import DraftDayCentral
    gm = type("GM", (), {"league": lg, "user_team": user_team})()
    hub_win = tk.Toplevel(root)
    hub_win.geometry("1600x900")
    hub_win.title("Draft Day Central")
    hub = DraftDayCentral(hub_win, gm, app=app)
    hub.pack(fill="both", expand=True)
    hub_win.update()
    hub._refresh_live_sections()
    hub_win.update()
    grab(hub_win, "06_draft_day_central.png")
    try:
        hub.close_view()
        check("hub close cancels refresh timer",
              getattr(hub, '_live_after_id', None) is None)
    except Exception as e:
        check("hub close crash-free", False, str(e))
    hub_win.destroy()

    # A11y spot checks at 1600x900: the action buttons must be visible
    # (mapped with real size) -- the shortlist cap keeps them on screen.
    view._draft_board_tab("Available")
    root.update()
    grab(root, "07_final_available.png")
    problems = []
    for w in (view.draft_button, view.auto_button, view.trade_pick_button):
        try:
            if not w.winfo_ismapped() or w.winfo_height() < 10:
                problems.append(
                    f"button hidden (mapped={w.winfo_ismapped()}, "
                    f"h={w.winfo_height()})")
        except Exception as e:
            problems.append(str(e))
    check("war-room buttons visible", not problems, str(problems))

    root.destroy()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
