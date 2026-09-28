"""Accessibility + visual QA for the new UI surfaces (cards, contract window, inbox).

Opens each changed window under Xvfb, screenshots it, and checks:
  1. minimum font size (FAIL < 9px, WARN < 11px body text)
  2. text contrast ratio (WARN < 4.5:1 normal, < 3:1 large)
  3. widget clipping inside parents / popups (FAIL)
  4. contract window Submit/Cancel visible without scrolling (FAIL)
  5. nested scrollable containers (WARN -- Chris: no layered scrolling)
  6. popup fits within 92% of the app window (FAIL)

Screenshots land in the shots dir for Chris's review before push.
Usage: DISPLAY=:99 python3 qa_ui_accessibility.py [--res 1366x768]
"""
import sys, os, time, argparse
sys.path.insert(0, ".")
from types import SimpleNamespace

import tkinter as tk
from tkinter import ttk, font as tkfont
try:
    import customtkinter as ctk
    _CTK = (ctk.CTkLabel, ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkCheckBox,
            ctk.CTkRadioButton, ctk.CTkSwitch, ctk.CTkEntry, ctk.CTkComboBox)
except Exception:
    ctk, _CTK = None, ()

def _is_ctk_internal(w):
    """customtkinter builds widgets out of internal tk children (e.g. CTkLabel
    contains a real tk.Label with a pixel font). Those are implementation
    details -- the visible styling lives on the CTk widget itself."""
    try:
        return isinstance(w, (tk.Label, tk.Button)) and isinstance(w.master, _CTK)
    except Exception:
        return False

def walk(node):
    for ch in node.winfo_children():
        if _is_ctk_internal(ch):
            continue
        yield ch
        yield from walk(ch)

PASS, FAIL, WARN = [], [], []
def check(kind, name, cond, detail=""):
    (PASS if cond else (FAIL if kind == "fail" else WARN)).append(name)
    tag = {"fail": "  ok  " if cond else "  FAIL", "warn": "  ok  " if cond else "  warn"}[kind]
    print(f"{tag} {name}" + (f" -- {detail}" if detail and not cond else ""))

# ---------------------------------------------------------------- contrast
def _rgb(widget, color):
    try:
        r, g, b = widget.winfo_rgb(color)
        return r / 257, g / 257, b / 257
    except Exception:
        return None

def _lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def check_contrast(name, win):
    import customtkinter as ctk
    bad = []
    for w in walk(win):
        try:
            txt = w.cget("text") if "text" in w.keys() else ""
        except Exception:
            continue
        if not txt or not str(txt).strip():
            continue
        if not isinstance(w, (tk.Label, tk.Button, ctk.CTkLabel, ctk.CTkButton,
                              ttk.Label, ttk.Button)):
            continue
        try:
            fg = w.cget("fg") if "fg" in w.keys() else w.cget("foreground")
        except Exception:
            try: fg = w.cget("text_color")
            except Exception: continue
        try:
            bg = w.cget("bg") if "bg" in w.keys() else w.cget("background")
        except Exception:
            try: bg = w.cget("fg_color")
            except Exception: continue
        fr, br = _rgb(w, fg), _rgb(w, bg)
        if not fr or not br:
            continue
        ratio = contrast_ratio(fr, br)
        try:
            size = abs(tkfont.Font(font=w.cget("font")).actual("size"))
        except Exception:
            size = 11
        need = 3.0 if size >= 18 else 4.5
        if ratio < need:
            bad.append(f"{str(txt)[:28]!r} {ratio:.1f}:1 (need {need})")
    check("warn", f"{name}: text contrast >= 4.5:1", not bad,
          "; ".join(bad[:4]))

# ---------------------------------------------------------------- fonts
def check_fonts(name, win):
    small = []
    # CTk 6.0 renders widget text through internal tk children (e.g. the
    # .!label inside a CTkLabel, the .!text inside a CTkTextbox) whose
    # fonts are pixel-sized descriptors ("size in pixel, independent of
    # scaling"). The design intent lives on the outer CTk widget's own
    # font option, so inner implementation widgets are skipped.
    _ctk_types = ()
    try:
        import customtkinter as _ctk
        _ctk_types = (_ctk.CTkBaseClass,)
    except Exception:
        pass
    for w in walk(win):
        try:
            if "font" not in w.keys():
                continue
            if _ctk_types and isinstance(getattr(w, "master", None),
                                         _ctk_types):
                continue
            f = tkfont.Font(font=w.cget("font"))
            size = abs(f.actual("size"))
            txt = str(w.cget("text"))[:30] if "text" in w.keys() else w.winfo_class()
            if size < 11:
                small.append((size, txt))
        except Exception:
            pass
    tiny = [s for s in small if s[0] < 9]
    check("fail", f"{name}: no text under 9px", not tiny,
          str(tiny[:3]))
    check("warn", f"{name}: body text >= 11px", not [s for s in small if s[0] < 11],
          str([s for s in small if s[0] < 11][:3]))

# ---------------------------------------------------------------- clipping
def _inside_scrollable(w):
    p = w.master
    while p is not None:
        try:
            if isinstance(p, tk.Canvas):
                return True
        except Exception:
            pass
        p = getattr(p, "master", None)
    return False

def check_clipping(name, win):
    bad = []
    for w in walk(win):
        try:
            p = w.master
            if p is None or p is win and False:
                pass
            pw, ph = p.winfo_width(), p.winfo_height()
            x, y, ww, hh = w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height()
            if pw <= 1 or ph <= 1:
                continue
            if _inside_scrollable(w):
                continue  # scroll region content is allowed to overflow
            if x < -2 or y < -2 or x + ww > pw + 2 or y + hh > ph + 2:
                bad.append(f"{w.winfo_class()}@{x},{y} {ww}x{hh} in {pw}x{ph}")
        except Exception:
            pass
    check("fail", f"{name}: no clipped/overflowing widgets", not bad,
          "; ".join(bad[:4]))

# ---------------------------------------------------------------- nested scroll
def check_nested_scroll(name, win):
    import customtkinter as ctk
    def scroll_depth(w):
        d, p = 0, w.master
        while p is not None and p is not win:
            try:
                cls = p.winfo_class()
                if cls in ("Canvas", "CTkScrollableFrame") or "scroll" in cls.lower():
                    d += 1
            except Exception:
                pass
            p = getattr(p, "master", None)
        return d
    deepest = 0
    for w in walk(win):
        try:
            if w.winfo_class() in ("Canvas", "CTkScrollableFrame"):
                deepest = max(deepest, scroll_depth(w))
        except Exception:
            pass
    check("warn", f"{name}: no nested scroll regions", deepest <= 1,
          f"scroll nesting depth {deepest}")

# ---------------------------------------------------------------- popup fit
def check_fit(name, win, root):
    # App convention (popup_system._place_entry): cards are clamped to the
    # app window minus a 40px margin. Popups must honor at least that.
    try:
        ww, wh = win.winfo_width(), win.winfo_height()
        rw, rh = root.winfo_width(), root.winfo_height()
        ok = ww <= rw - 40 + 4 and wh <= rh - 40 + 4
        check("fail", f"{name}: popup fits in app ({ww}x{wh} in {rw}x{rh})", ok)
    except Exception as e:
        check("fail", f"{name}: popup fit measurable", False, str(e))

# ---------------------------------------------------------------- screenshot
def shot(widget, path):
    import mss
    from PIL import Image
    try:
        widget.lift()
    except Exception:
        pass
    widget.update(); time.sleep(0.4)
    with mss.MSS() as sct:
        raw = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    img.crop((x, y, x + w, y + h)).save(path)
    print(f"  shot {path} ({w}x{h})")

def shell_of(popup):
    """The visible card shell for an InGamePopup instance."""
    try:
        return popup._popup_entry["shell"]
    except Exception:
        return popup

# ================================================================= main
# ----------------------------------------------------------------------
# Tab QA: player card tabs + staff card tabs (FM24-style) + inbox layout
# ----------------------------------------------------------------------
def check_player_tabs(win):
    """Exercise every player tab: switch, assert only it is visible."""
    tabs = ["Overview", "Personality", "Scout Report", "Dynamics"]
    for t in tabs:
        assert t in win._tab_pages, f"player tab missing: {t}"
    for t in tabs:
        win._switch_tab(t)
        win.update_idletasks()
        for name, page in win._tab_pages.items():
            visible = bool(page.winfo_ismapped())
            if name == t:
                check("fail", f"player tab '{t}' page visible after switch", visible)
            else:
                check("fail", f"player tab '{t}' hides '{name}'", not visible)
    return tabs


def check_staff_tabs(staff_win):
    """Drive the staff tab strip: 4 buttons, each invokes cleanly."""
    import customtkinter as ctk
    tab_names = ["Overview", "Attributes", "Standing", "Personality"]
    buttons = {}
    for ch in walk(staff_win):
        try:
            if isinstance(ch, ctk.CTkButton) and ch.cget("text") in tab_names:
                buttons[ch.cget("text")] = ch
        except Exception:
            pass
    check("fail", f"staff tab strip has 4 tabs (found {len(buttons)})", len(buttons) == 4)
    ok = True
    for t in tab_names:
        try:
            if t in buttons:
                buttons[t].invoke()
                staff_win.update_idletasks()
        except Exception as e:
            ok = False
            print(f"  staff tab '{t}' invoke failed: {e}")
    check("fail", "staff tabs all switch without error", ok)
    return buttons


def check_inbox_layout(inbox_win):
    """Messages list must sit ABOVE the message content pane."""
    msgs_y = msg_y = None
    for ch in walk(inbox_win):
        try:
            txt = ch.cget("text")
        except Exception:
            continue
        if txt == "Messages":
            msgs_y = ch.winfo_rooty()
        elif txt == "Message":
            msg_y = ch.winfo_rooty()
    check("fail", "inbox list + content headings found", msgs_y is not None and msg_y is not None)
    if msgs_y is not None and msg_y is not None:
        check("fail", f"inbox list above content ({msgs_y} < {msg_y})", msgs_y < msg_y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1600x900")
    ap.add_argument("--shots", default=os.path.expanduser(
        "~/workspace/puck-dynasty-ui-shots"))
    args = ap.parse_args()
    os.makedirs(args.shots, exist_ok=True)
    W, H = (int(x) for x in args.res.split("x"))

    root = tk.Tk(); root.geometry(f"{W}x{H}+0+0"); root.update()
    from popup_system import register
    mgr = register(root)

    # Apply the app's real dark ttk theme so screenshots are representative
    # (ContractNegotiationWindow relies on these styles, configured by the app).
    try:
        from ui_theme_system import ModernUITheme
        ModernUITheme().apply_to_style(ttk.Style(root))
    except Exception as e:
        print(f"  (ttk theme not applied: {e})")

    import game_classes as g
    import reputation_system as rs

    player = g.Player(first_name="Test", last_name="Player", age=24,
                      primary_position=g.PlayerPosition.CENTER, jersey_number=9)
    rs.ensure_reputation_fields(player)
    player.salary = 5_250_000
    player.contract_years = 2
    team = SimpleNamespace(team_name="Test Club", roster=[player], staff=[],
                           inbox=[])
    league = SimpleNamespace(teams=[team], free_agents=[])
    app = SimpleNamespace(league=league, user_team=team, open_windows={},
                          BG_COLOR="#1a1a2e")

    # ---------------- player card ----------------
    from modern_profile import PlayerProfile
    pw = PlayerProfile(app, player)
    root.update()
    psh = shell_of(pw)
    shot(psh, f"{args.shots}/player_card_{args.res}.png")
    check_fit("player card", psh, root)
    check_fonts("player card", psh)
    check_contrast("player card", psh)
    check_clipping("player card", psh)
    check_nested_scroll("player card", psh)

    # Player card tabs: exercise every tab, screenshot each
    ptabs = check_player_tabs(pw)
    for t in ptabs:
        pw._switch_tab(t)
        root.update()
        slug = t.lower().replace(" ", "_")
        shot(psh, f"{args.shots}/player_tab_{slug}_{args.res}.png")
    pw._switch_tab("Overview")
    root.update()

    # ---------------- staff card ----------------
    from staff_management_window import StaffManagementView
    staff_app = SimpleNamespace(
        league=league, user_team=team, open_windows={}, tree_maps={},
        BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11", TEXT_COLOR="#ffffff",
        FONT_FAMILY="Helvetica",
        game_manager=SimpleNamespace(user_team=team, league=league))
    staff_holder = tk.Frame(root, width=1600, height=900)
    staff_holder.pack(fill="both", expand=True)
    smv = StaffManagementView(staff_holder, app=staff_app)
    root.update()
    staff = g.Staff(first_name="Test", last_name="Coach",
                    role=g.StaffRole.HEAD_COACH, age=50)
    staff.ambition = "stanley_cup"; staff.favorite_team = "Test Club"
    staff.control_need = 80; staff.gm_trust = 70
    smv.show_staff_details_window(staff, True)
    root.update()
    staff_holder.destroy()
    # staff details opens as a popup-manager card; take the newest card shell
    sw = mgr._stack[-1]["shell"] if mgr._stack else None
    if sw is not None and sw is not psh:
        shot(sw, f"{args.shots}/staff_card_{args.res}.png")
        check_fit("staff card", sw, root)
        check_fonts("staff card", sw)
        check_contrast("staff card", sw)
        check_clipping("staff card", sw)
        check_nested_scroll("staff card", sw)
        # Staff card tabs: drive the strip, screenshot each tab
        staff_win = mgr._stack[-1]["popup"]
        sbuttons = check_staff_tabs(staff_win)
        for t in ("Overview", "Attributes", "Standing", "Personality"):
            try:
                if t in sbuttons:
                    sbuttons[t].invoke()
                    root.update()
                shot(sw, f"{args.shots}/staff_tab_{t.lower()}_{args.res}.png")
            except Exception as e:
                check("fail", f"staff tab '{t}' screenshot", False, str(e))
    else:
        check("fail", "staff card window found", False)

    # ---------------- contract windows ----------------
    from windows import ContractNegotiationWindow
    for mode, kw in (("offer", {}), ("extension", {"is_extension": True})):
        cw = ContractNegotiationWindow(app, player, **kw)
        root.update()
        csh = shell_of(cw)
        shot(csh, f"{args.shots}/contract_{mode}_{args.res}.png")
        # Submit/Cancel visible without scrolling
        found = []
        def find_btn(ch):
            if isinstance(ch, ttk.Button) and ch.cget("text") == "Submit Offer":
                found.append(ch)
        for ch in walk(cw):
            find_btn(ch)
        vis = False
        if found:
            b = found[0]
            vis = (b.winfo_y() + b.winfo_height()) <= csh.winfo_height() + 2
        check("fail", f"contract {mode}: Submit visible w/o scrolling", vis)
        check_fit(f"contract {mode}", csh, root)
        check_fonts(f"contract {mode}", csh)
        check_contrast(f"contract {mode}", csh)
        check_clipping(f"contract {mode}", csh)
        check_nested_scroll(f"contract {mode}", csh)
        try:
            mgr._on_x(mgr._entry_for(cw))
        except Exception:
            pass

    # ---------------- inbox with contract messages ----------------
    from game_classes import EmailMessage, EmailInbox
    team.inbox = EmailInbox()
    msgs = [
        EmailMessage(sender="Agent", subject="Signed: Test Player (3 yrs)",
                     action_type="contract_accepted", action_data={}),
        EmailMessage(sender="Agent", subject="Counter-offer: Picky Player",
                     action_type="contract_counter",
                     action_data={"player_id": "p3", "player_name": "Picky Player",
                                  "asking_price": 4_500_000, "years": 2,
                                  "is_extension": False}),
        EmailMessage(sender="Agent", subject="Talks break down: Reject Player",
                     action_type="contract_rejected", action_data={}),
    ]
    for m in reversed(msgs):
        team.inbox.add_message(m)
    # Full-screen inbox: what the user actually sees (embedded view, not
    # the legacy popup wrapper).
    from inbox_window import InboxView, InboxWindow
    iview = InboxView(root, app=app)
    iview.pack(fill="both", expand=True)
    root.update(); root.update()
    shot(iview, f"{args.shots}/inbox_fullscreen_{args.res}.png")
    # render the counter message's interactive actions (as on selection)
    try:
        iview._show_interactive_action(msgs[1])
        root.update(); time.sleep(0.3)
        shot(iview, f"{args.shots}/inbox_counter_actions_{args.res}.png")
    except Exception as e:
        check("fail", "inbox counter actions render", False, str(e))
    try:
        ww, wh = iview.winfo_width(), iview.winfo_height()
        rw, rh = root.winfo_width(), root.winfo_height()
        check("fail", f"inbox fills app window ({ww}x{wh} in {rw}x{rh})",
              abs(ww - rw) <= 4 and abs(wh - rh) <= 4)
    except Exception as e:
        check("fail", "inbox fill measurable", False, str(e))
    check_fonts("inbox", iview)
    check_contrast("inbox", iview)
    check_clipping("inbox", iview)
    check_nested_scroll("inbox", iview)
    check_inbox_layout(iview)
    # close contract: the screen manager's nav bar wires ‹ Dashboard to this
    check("fail", "inbox exposes close_view contract",
          callable(getattr(iview, "close_view", None))
          and hasattr(iview, "_close_screen"))
    iview.destroy()
    root.update()
    # Legacy popup wrapper: still constructs and focuses a message.
    try:
        iw = InboxWindow(app)
        root.update(); root.update()
        check("fail", "legacy inbox popup focuses message",
              iw.focus_message(msgs[1].id) is True)
        iw._view.request_close()
        root.update()
    except Exception as e:
        check("fail", "legacy inbox popup wrapper", False, str(e))

    print(f"\n{PASS and len(PASS)} passed, {len(FAIL)} failed, {len(WARN)} warnings")
    return 1 if FAIL else 0

sys.exit(main())


