# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""
Event Day Hubs - immersive standalone pages for the league's three tentpole days:
  * Draft Day Central   (June 23-25, rookie draft)
  * Trade Deadline      (existing TradeDeadlineCenter, derived date:
                         40 days before the last regular-season game)
  * Free Agent Frenzy   (July 1, start of free agency)

Each hub is a full-screen, broadcast-style page with a live wire feed,
done-deals tracker, and quick actions into the relevant management windows.
"""
from player_context_menu import bind_player_context
import tkinter as tk
import customtkinter as ctk
from popup_system import InGamePopup
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




# ----------------------------------------------------------------------------
# Base hub
# ----------------------------------------------------------------------------
class EventDayHubView(ctk.CTkFrame):
    """Shared immersive shell: header, 3-column content, scrolling wire ticker."""

    BG = '#0e0e11'
    PANEL = '#16161a'
    CARD = '#1e1e24'
    GOLD = '#00ceb8'
    WHITE = '#F2F5FA'
    MUTED = '#9aa0aa'
    GREEN = '#3DDC84'
    RED = '#FF5A5A'
    ACCENT = '#00ceb8'
    BORDER = '#2a2a30'

    EVENT_TITLE = "EVENT DAY"
    EVENT_TAGLINE = ""
    EVENT_EMOJI = ""

    def __init__(self, parent, game_manager, app=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self.gm = game_manager
        self.configure(fg_color=self.BG)
        self._close_screen = None  # set by show_screen() or wrapper

        # Gating Phase 2: thin Tier-B session for this read-mostly hub
        # (no in-progress user input; the live data stays model-side).
        try:
            from popup_system import get_pending_session
            _sess = get_pending_session(self.app, self._session_id())
            if _sess is not None:
                _sess.update(kind="event_hub",
                             screen_id=self._session_id(),
                             title=self.EVENT_TITLE)
        except Exception:
            pass

        self._ticker_text = ""
        self._ticker_x = 0

        self._build_shell()
        self._build_columns()   # subclass fills left/center/right
        self._build_ticker()
        self._animate_ticker()

    def _session_id(self):
        """Screen id for this hub (matches the show_screen registration)."""
        return "draft_central" if isinstance(self, DraftDayCentral) else "fa_frenzy"

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # -- shell -------------------------------------------------------------
    def _build_shell(self):
        header = tk.Frame(self, bg=self.BG)
        header.pack(fill='x', padx=24, pady=(18, 6))

        title_row = tk.Frame(header, bg=self.BG)
        title_row.pack(fill='x')
        tk.Label(title_row, text=self.EVENT_TITLE,
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
                         highlightbackground=self.BORDER, highlightthickness=1)
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
        # Route through close_view so subclasses can cancel timers.
        tk.Button(self.actions_bar, text="Close", bg=self.PANEL, fg=self.MUTED,
                  font=('Segoe UI', 11), relief='flat', padx=18, pady=8,
                  cursor='hand2', command=self.close_view).pack(side='right')

    # -- ticker ------------------------------------------------------------
    def _build_ticker(self):
        tick = tk.Frame(self, bg=self.PANEL, height=36)
        tick.pack(fill='x', side='bottom')
        tick.pack_propagate(False)
        self._ticker_label = tk.Label(tick, text="", bg=self.PANEL, fg=self.GOLD,
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
class DraftDayCentral(EventDayHubView):
    EVENT_TITLE = "DRAFT DAY CENTRAL"
    EVENT_TAGLINE = "Seven rounds. 224 picks. One future. Follow every selection live."

    def _build_actions(self, bar):
        # M7: one board action; "Trade This Pick" routes to the live
        # draft-day pick swap when a board is open, else the Trade Center.
        self._action_button("Draft Board / War Room", self._open_draft, accent=True)
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
        clock = tk.Frame(self.center_col, bg=self.CARD, highlightbackground=self.BORDER,
                         highlightthickness=1)
        clock.pack(fill='x', padx=14, pady=(0, 10))
        team, pickinfo = self._on_the_clock()
        self._clock_team_lbl = tk.Label(clock, text=team, bg=self.CARD, fg=self.WHITE,
                                       font=('Segoe UI', 16, 'bold'))
        self._clock_team_lbl.pack(pady=(10, 2))
        self._clock_info_lbl = tk.Label(clock, text=pickinfo, bg=self.CARD, fg=self.MUTED,
                                        font=('Segoe UI', 11))
        self._clock_info_lbl.pack(pady=(0, 10))

        self._column_title(self.center_col, "TOP AVAILABLE PROSPECTS")
        self._prospect_wrap = tk.Frame(self.center_col, bg=self.PANEL)
        self._prospect_wrap.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        self._fill_prospect_cards()

        # RIGHT: draft-day deals + class snapshot
        self._column_title(self.right_col, "DRAFT-DAY DEALS")
        self.deals_box = self._feed_box(self.right_col, height=12)
        self._feed_write(self.deals_box, self._deals_lines())
        self._column_title(self.right_col, "CLASS SNAPSHOT")
        self._snap_frame = tk.Frame(self.right_col, bg=self.CARD, highlightbackground=self.BORDER,
                                    highlightthickness=1)
        self._snap_frame.pack(fill='x', padx=14, pady=(0, 12))
        self._fill_snapshot()

        # M6: keep the hub live while the draft moves.
        self._live_after_id = None
        self._live_tick()

    # -- live refresh (M6) ---------------------------------------------------
    def _clear(self, frame):
        try:
            for _c in frame.winfo_children():
                _c.destroy()
        except Exception:
            pass

    def _refresh_live_sections(self):
        """Rewrite every live section from current state. Safe to call on
        a timer: every read is guarded, and it no-ops if widgets are gone."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            self._feed_write(self.wire_box, self._wire_lines())
        except Exception:
            pass
        try:
            self._feed_write(self.deals_box, self._deals_lines())
        except Exception:
            pass
        try:
            team, pickinfo = self._on_the_clock()
            self._clock_team_lbl.configure(text=team)
            self._clock_info_lbl.configure(text=pickinfo)
        except Exception:
            pass
        try:
            self._fill_prospect_cards()
        except Exception:
            pass
        try:
            self._fill_snapshot()
        except Exception:
            pass

    def _live_tick(self):
        self._cancel_live_tick()
        try:
            self._refresh_live_sections()
        except Exception:
            pass
        try:
            self._live_after_id = self.after(4000, self._live_tick)
        except Exception:
            self._live_after_id = None

    def _cancel_live_tick(self):
        _aid = getattr(self, '_live_after_id', None)
        if _aid:
            try:
                self.after_cancel(_aid)
            except Exception:
                pass
        self._live_after_id = None

    def close_view(self):
        # M6: never leave a refresh timer running after the hub closes.
        try:
            self._cancel_live_tick()
        except Exception:
            pass
        super().close_view()

    # -- data ----------------------------------------------------------------
    def _prospects(self):
        try:
            return list(self.gm.league.draft_prospects or [])
        except Exception:
            return []

    def _sorted_prospects(self):
        """Prospects in consensus (draft_ranking) order; falls back to OVR."""
        prosp = self._prospects()
        def key(p):
            dr = getattr(p, 'draft_ranking', None)
            if dr:
                try:
                    return (1, float(dr))
                except Exception:
                    pass
            try:
                return (0, float(p.overall_rating()))
            except Exception:
                return (0, 0.0)
        return sorted(prosp, key=key, reverse=True)

    def _report_for(self, p):
        """The user's real scouting report on a prospect, or None."""
        try:
            ut = self._user_team()
            reports = getattr(ut, 'scouting_reports', None) or {}
            pid = getattr(p, 'id', None)
            if pid is None:
                return None
            return reports.get(pid)
        except Exception:
            return None

    def _scout_note(self, p):
        """Honest scout line: real report data, or an unscouted empty state."""
        r = self._report_for(p)
        try:
            viewings = int(getattr(r, 'viewings', 0) or 0)
        except Exception:
            viewings = 0
        if r is None or viewings <= 0:
            return "Unscouted \u2014 no report filed yet."
        bits = [f"{viewings} viewing{'s' if viewings != 1 else ''}"]
        acc = getattr(r, 'accuracy', '') or ''
        if acc:
            bits.append(f"{acc} accuracy")
        strengths = list(getattr(r, 'strengths', None) or [])
        weaknesses = list(getattr(r, 'weaknesses', None) or [])
        if strengths:
            bits.append("Strength: " + str(strengths[0]))
        if weaknesses:
            bits.append("Weakness: " + str(weaknesses[0]))
        proj = getattr(r, 'projected_draft_position', None)
        if proj:
            bits.append(f"Proj. pick #{proj}")
        return " \u00b7 ".join(bits)

    def _fill_prospect_cards(self):
        """Rebuild the top-available prospect cards from current state.

        M6: called once at build and again on every live refresh, so the
        cards stay honest as the board empties. Only public attributes
        (letter grade, scout notes) -- never true potential numbers.
        """
        wrap = self._prospect_wrap
        self._clear(wrap)
        ordered = self._sorted_prospects()
        cards = ordered[:6]
        if not cards:
            tk.Label(wrap, text="No draft class generated yet.", bg=self.PANEL,
                     fg=self.MUTED, font=('Segoe UI', 10)).pack(anchor='w', padx=6, pady=6)
            return
        rank_of = {id(p): i + 1 for i, p in enumerate(ordered)}
        for p in cards:
            card = tk.Frame(wrap, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1)
            card.pack(fill='x', pady=3)
            top = tk.Frame(card, bg=self.CARD)
            top.pack(fill='x', padx=10, pady=(8, 0))
            name = getattr(p, 'full_name', str(p))
            pos = self._pos_code(p)
            age = getattr(p, 'age', '?')
            _name_lbl = tk.Label(top, text=f"#{rank_of.get(id(p), '?')}  {name}", bg=self.CARD,
                     fg=self.WHITE, font=('Segoe UI', 11, 'bold'))
            _name_lbl.pack(side='left')
            try:
                bind_player_context(_name_lbl, p, self)
                bind_player_context(card, p, self)
            except Exception:
                pass
            tk.Label(top, text=f"{pos}  \u00b7  Age {age}", bg=self.CARD,
                     fg=self.MUTED, font=('Segoe UI', 10)).pack(side='right')
            mid = tk.Frame(card, bg=self.CARD)
            mid.pack(fill='x', padx=10, pady=(2, 0))
            pot = getattr(p, 'potential_grade', '') or ''
            tk.Label(mid, text=f"POT {pot}" if pot else "POT \u2014", bg=self.CARD,
                     fg=self.GOLD, font=('Segoe UI', 10, 'bold')).pack(side='left')
            nat = str(getattr(p, 'nationality', getattr(p, 'nation', '')) or '')
            if nat:
                tk.Label(mid, text=f"  {nat}", bg=self.CARD, fg=self.MUTED,
                         font=('Segoe UI', 10)).pack(side='left')
            tk.Label(card, text=self._scout_note(p), bg=self.CARD, fg=self.MUTED,
                     font=('Segoe UI', 9, 'italic'), anchor='w', justify='left',
                     wraplength=430).pack(fill='x', padx=10, pady=(2, 8))

    def _fill_snapshot(self):
        """Rebuild the class-snapshot rows (M6: live on refresh)."""
        snap = self._snap_frame
        self._clear(snap)
        for label, value in self._class_snapshot():
            r = tk.Frame(snap, bg=self.CARD)
            r.pack(fill='x', padx=12, pady=3)
            tk.Label(r, text=label, bg=self.CARD, fg=self.MUTED,
                     font=('Segoe UI', 10)).pack(side='left')
            tk.Label(r, text=value, bg=self.CARD, fg=self.GOLD,
                     font=('Segoe UI', 10, 'bold')).pack(side='right')

    def _top_available(self, n=8):
        prosp = self._sorted_prospects()[:n]
        if not prosp:
            return ["No draft class generated yet."]
        lines = []
        for i, p in enumerate(prosp, 1):
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
            dw = self.app.open_windows.get('draft')
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
            dw = self.app.open_windows.get('draft')
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
        # Part 3: draft-week buzz lines (within a few days of the draft
        # window). Guarded; never breaks the wire.
        try:
            for _buzz in self._draft_buzz_lines():
                lines.append(_buzz)
        except Exception:
            pass
        return lines

    def _draft_buzz_lines(self):
        """1-2 draft-week buzz lines off the top-hype prospects.

        Only fires inside the draft-week window (June 20-25); reads only
        league.draft_prospects and never touches game state.
        """
        lines = []
        try:
            _d = getattr(getattr(self, 'gm', None), 'current_date', None)
            if _d is None or getattr(_d, 'month', 0) != 6:
                return lines
            if not (20 <= getattr(_d, 'day', 0) <= 25):
                return lines
            prosp = self._prospects()
            if not prosp:
                return lines

            def _hype(p):
                try:
                    return float(getattr(p, 'draft_hype', 0) or 0)
                except Exception:
                    return 0.0

            ordered = sorted(prosp, key=_hype, reverse=True)
            _top = ordered[0] if ordered else None
            if _top is not None and _hype(_top) > 0:
                _name = getattr(_top, 'full_name', str(_top))
                # "Generational" is reserved for the flagged obvious-generational
                # prospect; anyone else gets ordinary top-prospect buzz even
                # when the hype is loudest.
                if getattr(_top, 'generational', False):
                    lines.append(
                        "BUZZ: %s is the name on every scout's lips — "
                        "the 'generational' whispers are getting louder." % _name)
                else:
                    lines.append(
                        "BUZZ: %s is the name on every scout's lips — "
                        "the consensus top prospect of this class." % _name)
            if len(ordered) > 1 and len(lines) < 2 and _hype(ordered[1]) > 0:
                _name2 = getattr(ordered[1], 'full_name', str(ordered[1]))
                lines.append(
                    "BUZZ: rival war rooms can't stop talking about "
                    "%s either — the top of this board is loaded." % _name2)
        except Exception:
            pass
        return lines[:2]

    def _deals_lines(self):
        # Draft-day trades involving picks show up here when the draft runs.
        # The draft-day deal engine records real deals on the league; fall
        # back to the empty state when none have happened yet.
        deals = []
        try:
            league = getattr(getattr(self, 'gm', None), 'league', None)
            deals = list(getattr(league, 'draft_day_deals', None) or [])
        except Exception:
            deals = []
        if deals:
            return deals[-8:]
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
        return [("Remaining prospects", str(len(prosp))),
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
            self.app.open_draft_window()
        except Exception:
            pass

    def _find_draft_view(self):
        """Locate an open DraftView (dashboard screen or popup card)."""
        try:
            from collections import deque
            seen = set()
            queue = deque([self.app])
            while queue:
                w = queue.popleft()
                if id(w) in seen:
                    continue
                seen.add(id(w))
                if callable(getattr(w, 'trade_current_pick', None)) \
                        and getattr(w, 'draft_order', None):
                    return w
                try:
                    queue.extend(w.winfo_children())
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _open_trade(self):
        # M7: "Trade This Pick" routes to the live draft-day pick-swap
        # dialog when a draft board is open; otherwise the Trade Center.
        try:
            dv = self._find_draft_view()
            if dv is not None:
                dv.trade_current_pick()
                return
        except Exception:
            pass
        try:
            self.app.open_trade_window()
        except Exception:
            pass

    def _open_scouting(self):
        try:
            self.app.open_scouting_window()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Free Agent Frenzy
# ----------------------------------------------------------------------------
class FreeAgencyFrenzy(EventDayHubView):
    EVENT_TITLE = "FREE AGENT FRENZY"
    EVENT_TAGLINE = "The market is open. Every contender is on the phone. Don't get left behind."

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
        self._build_ufa_cards(self.center_col)

        # RIGHT: done deals + cap snapshot
        self._column_title(self.right_col, "DONE DEALS")
        self.deals_box = self._feed_box(self.right_col, height=12)
        self._feed_write(self.deals_box, self._deals_lines())
        self._column_title(self.right_col, "YOUR CAP PICTURE")
        cap = tk.Frame(self.right_col, bg=self.CARD, highlightbackground=self.BORDER,
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
    def _deals_lines(self):
        """Done deals, read from the live news log -- real signings only.

        Both the SP contract-signing chokepoint and the MP signing path
        log to the news feed ("... have signed X to a N-year contract.",
        "X signed by Team: N years at $Y/year."), so filtering the log
        for signings shows what actually happened. Newest first, capped.
        Nothing is fabricated: with no signings in the log, the column
        says so honestly.
        """
        lines = []
        try:
            log = list(getattr(self.app, 'news_log', None) or [])
        except Exception:
            log = []
        for item in reversed(log):
            story = ""
            if isinstance(item, dict):
                story = str(item.get('story', '') or '')
            else:
                story = str(item or '')
            low = story.lower()
            # 'signed'/'signing' mark real deals; 'assign' is excluded so
            # AHL assignments ("... assigned to ...") don't leak in --
            # "assigned" contains "signed" as a substring.
            if (('signed' in low or 'signing' in low)
                    and 'assign' not in low):
                lines.append(f"\u2022 {story}")
            if len(lines) >= 12:
                break
        return lines or ["No signings yet today.",
                         "Done deals appear here as contracts are signed."]

    def _ufa_list(self):
        try:
            return list(self.gm.free_agents or [])
        except Exception:
            return []

    def _top_ufa_players(self, n=10):
        """Top free agents as player objects, sorted by OVR."""
        fas = self._ufa_list()
        # Draft lock: draft-eligible players aren't signable free agents.
        try:
            from draft_generator import player_locked_by_draft as _locked
            fas = [p for p in fas if not _locked(p)]
        except Exception:
            pass
        def key(p):
            try:
                return p.overall_rating()
            except Exception:
                return 0
        return sorted(fas, key=key, reverse=True)[:n]

    def _season_line(self, p):
        """Real season stat line; goalies get goalie stats. Honest when empty."""
        try:
            gp = int(getattr(p, 'games_played', 0) or 0)
        except Exception:
            gp = 0
        if gp <= 0:
            return "No games played this season"
        if self._pos_code(p) == 'G':
            w = getattr(p, 'wins', 0) or 0
            sv = getattr(p, 'save_percentage', 0) or 0
            gaa = getattr(p, 'goals_against_avg', 0) or 0
            return f"{gp} GP \u00b7 {w} W \u00b7 {sv:.3f} SV% \u00b7 {gaa:.2f} GAA"
        g = getattr(p, 'goals', 0) or 0
        a = getattr(p, 'assists', 0) or 0
        pts = getattr(p, 'points', g + a) or 0
        return f"{gp} GP \u00b7 {g} G \u00b7 {a} A \u00b7 {pts} P"

    def _build_ufa_cards(self, parent):
        """Multi-field UFA cards built only from real player attributes."""
        self._column_title(parent, "TOP AVAILABLE FREE AGENTS")
        wrap = tk.Frame(parent, bg=self.PANEL)
        wrap.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        cards = self._top_ufa_players(8)
        if not cards:
            tk.Label(wrap, text="No free agents on the market.", bg=self.PANEL,
                     fg=self.MUTED, font=('Segoe UI', 10)).pack(anchor='w', padx=6, pady=6)
            return
        for i, p in enumerate(cards, 1):
            card = tk.Frame(wrap, bg=self.CARD, highlightbackground=self.BORDER,
                            highlightthickness=1)
            card.pack(fill='x', pady=3)
            top = tk.Frame(card, bg=self.CARD)
            top.pack(fill='x', padx=10, pady=(8, 0))
            name = getattr(p, 'full_name', str(p))
            pos = self._pos_code(p)
            age = getattr(p, 'age', '?')
            _name_lbl = tk.Label(top, text=f"#{i}  {name}", bg=self.CARD, fg=self.WHITE,
                     font=('Segoe UI', 11, 'bold'))
            _name_lbl.pack(side='left')
            try:
                bind_player_context(_name_lbl, p, self)
                bind_player_context(card, p, self)
            except Exception:
                pass
            tk.Label(top, text=f"{pos}  \u00b7  Age {age}", bg=self.CARD, fg=self.MUTED,
                     font=('Segoe UI', 10)).pack(side='right')
            mid = tk.Frame(card, bg=self.CARD)
            mid.pack(fill='x', padx=10, pady=(2, 8))
            try:
                ovr = p.overall_rating()
            except Exception:
                ovr = None
            tk.Label(mid, text=f"OVR {ovr}" if ovr is not None else "OVR \u2014",
                     bg=self.CARD, fg=self.GOLD,
                     font=('Segoe UI', 10, 'bold')).pack(side='left')
            tk.Label(mid, text=f"  {self._season_line(p)}", bg=self.CARD, fg=self.MUTED,
                     font=('Segoe UI', 10)).pack(side='left')

    def _top_ufas(self, n=10):
        top = self._top_ufa_players(n)
        if not top:
            return ["No free agents on the market."]
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
            cap = getattr(self.gm.league, 'salary_cap', 104000000) if hasattr(self.gm, 'league') else 104000000
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
            self.app.open_free_agency_window()
        except Exception:
            pass

    def _open_finances(self):
        try:
            self.app.open_finances_window()
        except Exception:
            pass

    def _open_trade(self):
        try:
            self.app.open_trade_window()
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Auto-open prompt
# ----------------------------------------------------------------------------
_EVENT_DAY_APP = None


def _set_event_day_app(app):
    global _EVENT_DAY_APP
    _EVENT_DAY_APP = app


def _event_day_answer(session_id, dialog_id, value, **kwargs):
    """DIALOG_RESOLVERS['event_day_answer']: reserved for the event-day
    prompt. The prompt is fire-and-forget (same-day, transient), so a
    post-load answer is always a no-op -- the day has passed and the hub
    stays reachable from the navbar."""
    return False


try:
    from popup_system import register_dialog_resolver as _ed_reg
    _ed_reg("event_day_answer", _event_day_answer)
except Exception:
    pass


def prompt_event_day(parent, game_manager, event):
    """Ask the user whether to open the event hub when the day arrives."""
    from popup_system import (messagebox, ask_card, confirm_card,
                              cards_available)
    titles = {
        'draft': ("Draft Day is here!",
                  "The NHL Entry Draft begins today.\n\nOpen Draft Day Central for the live pick-by-pick experience?"),
        'deadline': ("Trade Deadline Day!",
                     "The trade deadline is TODAY.\n\nOpen the Trade Deadline Center?"),
        'free_agency': ("Free Agency is open!",
                        "The free agent market opens today.\n\nOpen Free Agent Frenzy?"),
    }
    title, msg = titles.get(event, ("Event Day!", "A league event day has arrived."))

    def _do_open():
        _open_event_hub(parent, game_manager, event)

    if confirm_card is not None and (cards_available is None
                                     or cards_available()):
        # Gating T2-Phase 3: non-modal; dismiss = stay on current screen.
        _set_event_day_app(parent)
        confirm_card(parent, title, msg, on_yes=_do_open)
        return

    if not messagebox.askyesno(title, msg):
        return
    _do_open()




def _open_event_hub(app, game_manager, event):
    """Open the event hub for the given event key. Honest no-op when the
    app or hub can't be resolved."""
    if app is None:
        return False
    try:
        if event == 'draft':
            show = getattr(app, 'show_screen', None)
            if callable(show):
                show("draft_central", "Draft Day Central", DraftDayCentral,
                     game_manager)
                return True
            return False
        elif event == 'deadline':
            opener = getattr(app, 'open_trade_deadline_center', None)
            if callable(opener):
                opener()
                return True
            from trade_deadline_center import TradeDeadlineCenter
            app.show_screen("trade_deadline", "Trade Deadline Center",
                            TradeDeadlineCenter)
            return True
        elif event == 'free_agency':
            FreeAgencyFrenzyWindow(app, game_manager)
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Legacy popup wrappers (backward compatibility)
# ---------------------------------------------------------------------------

class EventDayHub(InGamePopup):
    """Popup wrapper around EventDayHubView."""
    def __init__(self, parent, game_manager):
        InGamePopup.__init__(self, parent)
        self.title(self.EVENT_TITLE)
        try:
            self.state('zoomed')
        except Exception:
            self.geometry("1600x950")
        self.minsize(1200, 750)
        self._view = EventDayHubView(self, game_manager, app=parent)
        self._view.pack(fill="both", expand=True)
        self._view._close_screen = self.destroy
        self.protocol("WM_DELETE_WINDOW", self.destroy)


class FreeAgencyFrenzyWindow(EventDayHub):
    """Popup wrapper for Free Agency Frenzy."""
    def __init__(self, parent, game_manager):
        InGamePopup.__init__(self, parent)
        self.title("Free Agency Frenzy")
        try:
            self.state('zoomed')
        except Exception:
            self.geometry("1600x950")
        self._view = FreeAgencyFrenzy(self, game_manager, app=parent)
        self._view.pack(fill="both", expand=True)
        self._view._close_screen = self.destroy
        self.protocol("WM_DELETE_WINDOW", self.destroy)


# Keep the original name working as a popup wrapper for existing callers
# (Gating Phase 2: DraftDayCentralWindow/DraftDayCentralPopup were deleted --
# the hub is screen-only now).
FreeAgencyFrenzyPopup = FreeAgencyFrenzyWindow
