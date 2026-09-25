"""
Event Day Hubs - immersive standalone pages for the league's three tentpole days:
  * Draft Day Central   (June 23-25, rookie draft)
  * Trade Deadline      (existing TradeDeadlineCenter, March 8)
  * Free Agent Frenzy   (July 1, start of free agency)

Each hub is a full-screen, broadcast-style page with a live wire feed,
done-deals tracker, and quick actions into the relevant management windows.
"""
import tkinter as tk
from tkinter import ttk
from datetime import date


# ----------------------------------------------------------------------------
# Event-day detection helpers
# ----------------------------------------------------------------------------
def is_draft_day(d=None):
    """Rookie draft runs June 23-25."""
    d = d or date.today()
    return d.month == 6 and 23 <= d.day <= 25


def is_free_agency_day(d=None):
    """Free agency opens July 1."""
    d = d or date.today()
    return d.month == 7 and d.day == 1


def get_todays_event(d=None):
    """Return 'draft', 'deadline', 'free_agency', or None for the given date."""
    d = d or date.today()
    if is_draft_day(d):
        return 'draft'
    if is_free_agency_day(d):
        return 'free_agency'
    try:
        from trade_deadline_center import is_trade_deadline_day
        # is_trade_deadline_day() uses the real calendar; approximate by month/day
        if d.month == 3 and d.day == 8:
            return 'deadline'
    except Exception:
        pass
    return None


def days_until_event(d=None):
    """Days until the next tentpole event (for dashboard banners)."""
    from datetime import date as _date
    d = d or _date.today()
    cands = []
    for month, day, name in ((6, 23, 'draft'), (7, 1, 'free_agency'), (3, 8, 'deadline')):
        for yr in (d.year, d.year + 1):
            try:
                ev = _date(yr, month, day)
            except ValueError:
                continue
            if ev >= d:
                cands.append(((ev - d).days, name, ev))
                break
    cands.sort()
    return cands[0] if cands else (None, None, None)


# ----------------------------------------------------------------------------
# Base hub
# ----------------------------------------------------------------------------
class EventDayHub(tk.Toplevel):
    """Shared immersive shell: header, 3-column content, scrolling wire ticker."""

    BG = '#0B1220'
    PANEL = '#141D31'
    CARD = '#1B2740'
    GOLD = '#FFD54A'
    WHITE = '#F2F5FA'
    MUTED = '#8FA0B8'
    GREEN = '#3DDC84'
    RED = '#FF5A5A'
    ACCENT = '#4DA3FF'

    EVENT_TITLE = "EVENT DAY"
    EVENT_TAGLINE = ""
    EVENT_EMOJI = ""

    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self.parent = parent
        self.gm = game_manager
        self.configure(bg=self.BG)
        self.title(self.EVENT_TITLE)
        try:
            self.state('zoomed')
        except Exception:
            self.geometry("1600x950")
        self.minsize(1200, 750)

        self._ticker_text = ""
        self._ticker_x = 0

        self._build_shell()
        self._build_columns()   # subclass fills left/center/right
        self._build_ticker()
        self._animate_ticker()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # -- shell -------------------------------------------------------------
    def _build_shell(self):
        header = tk.Frame(self, bg=self.BG)
        header.pack(fill='x', padx=24, pady=(18, 6))

        title_row = tk.Frame(header, bg=self.BG)
        title_row.pack(fill='x')
        tk.Label(title_row, text=f"{self.EVENT_EMOJI}  {self.EVENT_TITLE}  {self.EVENT_EMOJI}",
                 bg=self.BG, fg=self.GOLD, font=('Segoe UI', 30, 'bold')).pack(side='left')
        try:
            datestr = self.gm.current_date.strftime("%B %d, %Y") if hasattr(self.gm, 'current_date') else ""
        except Exception:
            datestr = ""
        tk.Label(title_row, text=datestr, bg=self.BG, fg=self.MUTED,
                 font=('Segoe UI', 13)).pack(side='right', pady=10)

        if self.EVENT_TAGLINE:
            tk.Label(header, text=self.EVENT_TAGLINE, bg=self.BG, fg=self.WHITE,
                     font=('Segoe UI', 13)).pack(anchor='w', pady=(2, 8))

        # quick actions bar
        self.actions_bar = tk.Frame(header, bg=self.BG)
        self.actions_bar.pack(fill='x', pady=(4, 6))
        self._build_actions(self.actions_bar)

        # 3-column content
        content = tk.Frame(self, bg=self.BG)
        content.pack(fill='both', expand=True, padx=24, pady=6)
        self.left_col = self._make_column(content, "left")
        self.center_col = self._make_column(content, "center")
        self.right_col = self._make_column(content, "right")

    def _make_column(self, parent, side):
        frame = tk.Frame(parent, bg=self.PANEL, relief='flat', bd=0,
                         highlightbackground='#26334F', highlightthickness=1)
        if side == 'left':
            frame.pack(side='left', fill='both', expand=True, padx=(0, 8))
        elif side == 'right':
            frame.pack(side='right', fill='both', expand=True, padx=(8, 0))
        else:
            frame.pack(side='left', fill='both', expand=True, padx=8)
        return frame

    def _column_title(self, parent, text):
        tk.Label(parent, text=text, bg=self.PANEL, fg=self.GOLD,
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=14, pady=(12, 6))

    def _feed_box(self, parent, height=20):
        box = tk.Text(parent, bg=self.BG, fg=self.WHITE, font=('Segoe UI', 10),
                      wrap='word', relief='flat', highlightthickness=0, height=height,
                      state='disabled')
        box.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        return box

    def _feed_write(self, box, lines):
        box.config(state='normal')
        box.delete('1.0', 'end')
        for line in lines:
            box.insert('end', line + "\n")
        box.config(state='disabled')

    def _action_button(self, text, command, accent=False):
        btn = tk.Button(self.actions_bar, text=text,
                        bg=self.ACCENT if accent else self.CARD,
                        fg='white', activebackground=self.ACCENT,
                        font=('Segoe UI', 11, 'bold'), relief='flat',
                        padx=18, pady=8, cursor='hand2', command=command)
        btn.pack(side='left', padx=(0, 10))
        return btn

    def _close_button(self):
        tk.Button(self.actions_bar, text="Close", bg=self.PANEL, fg=self.MUTED,
                  font=('Segoe UI', 11), relief='flat', padx=18, pady=8,
                  cursor='hand2', command=self.destroy).pack(side='right')

    # -- ticker ------------------------------------------------------------
    def _build_ticker(self):
        tick = tk.Frame(self, bg='#101827', height=36)
        tick.pack(fill='x', side='bottom')
        tick.pack_propagate(False)
        self._ticker_label = tk.Label(tick, text="", bg='#101827', fg=self.GOLD,
                                      font=('Segoe UI', 11, 'bold'), anchor='w')
        self._ticker_label.place(x=0, y=8)
        self._ticker_text = self._ticker_content()

    def _ticker_content(self):
        return "Welcome to event day."

    def _animate_ticker(self):
        try:
            x = self._ticker_label.winfo_x() - 2
            if x < -self._ticker_label.winfo_width():
                x = self.winfo_width()
            self._ticker_label.config(text=self._ticker_text)
            self._ticker_label.place(x=x, y=8)
        except Exception:
            pass
        if self.winfo_exists():
            self.after(60, self._animate_ticker)

    # -- subclass hooks ------------------------------------------------------
    def _build_actions(self, bar):
        self._close_button()

    def _build_columns(self):
        pass

    # -- helpers -------------------------------------------------------------
    def _user_team(self):
        try:
            return self.gm.user_team
        except Exception:
            return None

    def _pos_code(self, p):
        """Short position code (C/LW/RW/LD/RD/G) from any player object."""
        try:
            pp = getattr(p, 'primary_position', None)
            if pp is not None:
                return getattr(pp, 'value', str(pp))
            return str(getattr(p, 'position', '?'))
        except Exception:
            return '?'

    def _team_payroll(self, team):
        total = 0
        try:
            for player in getattr(team, 'roster', []) or []:
                if hasattr(player, 'contract') and hasattr(player.contract, 'salary'):
                    total += player.contract.salary or 0
                elif hasattr(player, 'salary'):
                    total += player.salary or 0
        except Exception:
            pass
        return total

    def _nhl_teams(self):
        try:
            return [t for t in self.gm.league.teams
                    if getattr(t, 'league_name', '') == 'National Hockey League']
        except Exception:
            return []


# ----------------------------------------------------------------------------
# Draft Day Central
# ----------------------------------------------------------------------------
class DraftDayCentral(EventDayHub):
    EVENT_TITLE = "DRAFT DAY CENTRAL"
    EVENT_TAGLINE = "Seven rounds. 224 picks. One future. Follow every selection live."
    EVENT_EMOJI = "\U0001F3D2"  # hockey stick+puck approx

    def _build_actions(self, bar):
        self._action_button("Open Draft Board", self._open_draft, accent=True)
        self._action_button("War Room / Auto-Draft", self._open_draft)
        self._action_button("Trade This Pick", self._open_trade)
        self._action_button("Scouting Department", self._open_scouting)
        self._close_button()

    def _build_columns(self):
        # LEFT: pick-by-pick wire
        self._column_title(self.left_col, "PICK-BY-PICK WIRE")
        self.wire_box = self._feed_box(self.left_col)
        self._feed_write(self.wire_box, self._wire_lines())

        # CENTER: on the clock + top available
        self._column_title(self.center_col, "ON THE CLOCK")
        clock = tk.Frame(self.center_col, bg=self.CARD, highlightbackground='#26334F',
                         highlightthickness=1)
        clock.pack(fill='x', padx=14, pady=(0, 10))
        team, pickinfo = self._on_the_clock()
        tk.Label(clock, text=team, bg=self.CARD, fg=self.WHITE,
                 font=('Segoe UI', 16, 'bold')).pack(pady=(10, 2))
        tk.Label(clock, text=pickinfo, bg=self.CARD, fg=self.MUTED,
                 font=('Segoe UI', 11)).pack(pady=(0, 10))

        self._column_title(self.center_col, "TOP AVAILABLE PROSPECTS")
        avail = tk.Frame(self.center_col, bg=self.PANEL)
        avail.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        for i, line in enumerate(self._top_available()):
            bg = self.CARD if i % 2 == 0 else self.PANEL
            row = tk.Frame(avail, bg=bg)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=line, bg=bg, fg=self.WHITE,
                     font=('Segoe UI', 10), anchor='w').pack(fill='x', padx=10, pady=4)

        # RIGHT: draft-day deals + class snapshot
        self._column_title(self.right_col, "DRAFT-DAY DEALS")
        self.deals_box = self._feed_box(self.right_col, height=12)
        self._feed_write(self.deals_box, self._deals_lines())
        self._column_title(self.right_col, "CLASS SNAPSHOT")
        snap = tk.Frame(self.right_col, bg=self.CARD, highlightbackground='#26334F',
                        highlightthickness=1)
        snap.pack(fill='x', padx=14, pady=(0, 12))
        for label, value in self._class_snapshot():
            r = tk.Frame(snap, bg=self.CARD)
            r.pack(fill='x', padx=12, pady=3)
            tk.Label(r, text=label, bg=self.CARD, fg=self.MUTED,
                     font=('Segoe UI', 10)).pack(side='left')
            tk.Label(r, text=value, bg=self.CARD, fg=self.GOLD,
                     font=('Segoe UI', 10, 'bold')).pack(side='right')

    # -- data ----------------------------------------------------------------
    def _prospects(self):
        try:
            return list(self.gm.league.draft_prospects or [])
        except Exception:
            return []

    def _top_available(self, n=8):
        prosp = self._prospects()
        if not prosp:
            return ["No draft class generated yet."]
        def key(p):
            try:
                return p.overall_rating()
            except Exception:
                return 0
        top = sorted(prosp, key=key, reverse=True)[:n]
        lines = []
        for i, p in enumerate(top, 1):
            try:
                name = getattr(p, 'full_name', str(p))
                pos = self._pos_code(p)
                pot = getattr(p, 'potential_grade', '') or ''
                lines.append(f"{i}. {name}  ({pos})  {pot}")
            except Exception:
                continue
        return lines or ["No draft class generated yet."]

    def _on_the_clock(self):
        # If the live draft window is open, mirror it; otherwise show user's next pick
        try:
            dw = self.parent.open_windows.get('draft')
            if dw is not None and dw.winfo_exists():
                clock = getattr(dw, 'clock_label', None)
                info = getattr(dw, 'pick_info_label', None)
                t = clock.cget('text') if clock else "Draft in progress"
                i = info.cget('text') if info else ""
                return t, i
        except Exception:
            pass
        try:
            ut = self._user_team()
            if ut is not None:
                return getattr(ut, 'team_name', 'Your team'), "Your war room is ready - open the draft board to make your picks."
        except Exception:
            pass
        return "Draft Day", "Open the draft board to begin."

    def _wire_lines(self):
        lines = []
        try:
            dw = self.parent.open_windows.get('draft')
            picks = getattr(dw, 'picks_made', []) if dw is not None and dw.winfo_exists() else []
            for team_name, overall, player in picks[-30:]:
                pname = getattr(player, 'full_name', str(player))
                lines.append(f"Pick #{overall}: {team_name} select {pname}")
        except Exception:
            pass
        if not lines:
            lines = ["The draft floor is buzzing. Picks will appear here live,",
                     "selection by selection, as the night unfolds.",
                     "",
                     "Open the Draft Board to run your war room."]
        return lines

    def _deals_lines(self):
        # Draft-day trades involving picks show up here when the draft runs
        return ["No draft-day trades yet.",
                "Pick swaps will be tracked here as they happen."]

    def _class_snapshot(self):
        prosp = self._prospects()
        if not prosp:
            return [("Prospects", "—")]
        from collections import Counter
        pos = Counter(self._pos_code(p) for p in prosp)
        top3 = ", ".join(f"{k}: {v}" for k, v in pos.most_common(3))
        nat = Counter(str(getattr(p, 'nationality', getattr(p, 'nation', '?'))) for p in prosp)
        top_nat = nat.most_common(1)[0][0] if nat else "—"
        return [("Eligible prospects", str(len(prosp))),
                ("Top positions", top3),
                ("Top nation", top_nat),
                ("Rounds", "7")]

    def _ticker_content(self):
        top = self._top_available(3)
        names = "  •  ".join(t.split(". ", 1)[-1] for t in top[:3] if ". " in t)
        return f"DRAFT DAY  •  Top names on the board: {names}  •  224 picks across 7 rounds  •  "

    # -- actions ---------------------------------------------------------------
    def _open_draft(self):
        try:
            self.parent.open_draft_window()
        except Exception:
            pass

    def _open_trade(self):
        try:
            self.parent.open_trade_window()
        except Exception:
            pass

    def _open_scouting(self):
        try:
            self.parent.open_scouting_window()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Free Agent Frenzy
# ----------------------------------------------------------------------------
class FreeAgencyFrenzy(EventDayHub):
    EVENT_TITLE = "FREE AGENT FRENZY"
    EVENT_TAGLINE = "The market is open. Every contender is on the phone. Don't get left behind."
    EVENT_EMOJI = "\U0001F4B0"  # money bag

    def _build_actions(self, bar):
        self._action_button("Open FA Market", self._open_fa, accent=True)
        self._action_button("Make an Offer", self._open_fa)
        self._action_button("My Cap Space", self._open_finances)
        self._action_button("Trade Center", self._open_trade)
        self._close_button()

    def _build_columns(self):
        # LEFT: signing wire
        self._column_title(self.left_col, "SIGNING WIRE")
        self.wire_box = self._feed_box(self.left_col)
        self._feed_write(self.wire_box, self._wire_lines())

        # CENTER: top UFAs
        self._column_title(self.center_col, "TOP AVAILABLE FREE AGENTS")
        ufa_frame = tk.Frame(self.center_col, bg=self.PANEL)
        ufa_frame.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        for i, line in enumerate(self._top_ufas()):
            bg = self.CARD if i % 2 == 0 else self.PANEL
            row = tk.Frame(ufa_frame, bg=bg)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=line, bg=bg, fg=self.WHITE,
                     font=('Segoe UI', 10), anchor='w').pack(fill='x', padx=10, pady=4)

        # RIGHT: done deals + cap snapshot
        self._column_title(self.right_col, "DONE DEALS")
        self.deals_box = self._feed_box(self.right_col, height=12)
        self._feed_write(self.deals_box, ["No signings yet today.",
                                          "Done deals will be tracked here with terms."])
        self._column_title(self.right_col, "YOUR CAP PICTURE")
        cap = tk.Frame(self.right_col, bg=self.CARD, highlightbackground='#26334F',
                       highlightthickness=1)
        cap.pack(fill='x', padx=14, pady=(0, 12))
        for label, value in self._cap_snapshot():
            r = tk.Frame(cap, bg=self.CARD)
            r.pack(fill='x', padx=12, pady=3)
            tk.Label(r, text=label, bg=self.CARD, fg=self.MUTED,
                     font=('Segoe UI', 10)).pack(side='left')
            tk.Label(r, text=value, bg=self.CARD, fg=self.GREEN,
                     font=('Segoe UI', 10, 'bold')).pack(side='right')

    # -- data ----------------------------------------------------------------
    def _ufa_list(self):
        try:
            return list(self.gm.free_agents or [])
        except Exception:
            return []

    def _top_ufas(self, n=10):
        fas = self._ufa_list()
        if not fas:
            return ["No free agents on the market."]
        def key(p):
            try:
                return p.overall_rating()
            except Exception:
                return 0
        top = sorted(fas, key=key, reverse=True)[:n]
        lines = []
        for i, p in enumerate(top, 1):
            try:
                name = getattr(p, 'full_name', str(p))
                pos = self._pos_code(p)
                ovr = p.overall_rating()
                age = getattr(p, 'age', '?')
                lines.append(f"{i}. {name}  ({pos}, {age})  OVR {ovr}")
            except Exception:
                continue
        return lines or ["No free agents on the market."]

    def _wire_lines(self):
        fas = self._ufa_list()
        if not fas:
            return ["The market hasn't opened yet."]
        top = self._top_ufas(3)
        lines = ["The floodgates are open - teams are racing to call agents.",
                 "",
                 "Headliners still available:"]
        lines += [f"  {t}" for t in top]
        lines += ["",
                  f"{len(fas)} free agents on the market.",
                  "Signings will stream in here live."]
        return lines

    def _cap_snapshot(self):
        ut = self._user_team()
        if ut is None:
            return [("Team", "—")]
        try:
            payroll = self._team_payroll(ut)
            cap = getattr(self.gm.league, 'salary_cap', 83500000) if hasattr(self.gm, 'league') else 83500000
            space = cap - payroll
            def fmt(v):
                return f"${v/1e6:.1f}M"
            return [("Payroll", fmt(payroll)),
                    ("Cap ceiling", fmt(cap)),
                    ("Cap space", fmt(space))]
        except Exception:
            return [("Cap space", "—")]

    def _ticker_content(self):
        top = self._top_ufas(3)
        names = "  •  ".join(t.split(". ", 1)[-1] for t in top[:3] if ". " in t)
        n = len(self._ufa_list())
        return f"FREE AGENT FRENZY  •  {n} players available  •  Top names: {names}  •  "

    # -- actions ---------------------------------------------------------------
    def _open_fa(self):
        try:
            self.parent.open_free_agency_window()
        except Exception:
            pass

    def _open_finances(self):
        try:
            self.parent.open_finances_window()
        except Exception:
            pass

    def _open_trade(self):
        try:
            self.parent.open_trade_window()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Auto-open prompt
# ----------------------------------------------------------------------------
def prompt_event_day(parent, game_manager, event):
    """Ask the user whether to open the event hub when the day arrives."""
    from tkinter import messagebox
    titles = {
        'draft': ("Draft Day is here!",
                  "The NHL Entry Draft begins today.\n\nOpen Draft Day Central for the live pick-by-pick experience?"),
        'deadline': ("Trade Deadline Day!",
                     "The trade deadline is TODAY.\n\nOpen the Trade Deadline Center?"),
        'free_agency': ("Free Agency is open!",
                        "The free agent market opens today.\n\nOpen Free Agent Frenzy?"),
    }
    title, msg = titles.get(event, ("Event Day!", "A league event day has arrived."))
    if not messagebox.askyesno(title, msg):
        return
    try:
        if event == 'draft':
            DraftDayCentral(parent, game_manager)
        elif event == 'deadline':
            from trade_deadline_center import TradeDeadlineCenter
            TradeDeadlineCenter(parent)
        elif event == 'free_agency':
            FreeAgencyFrenzy(parent, game_manager)
    except Exception:
        pass
