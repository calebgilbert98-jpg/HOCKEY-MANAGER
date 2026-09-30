"""BUG-2 QA: draft re-entry + save/load mid-draft (entry + fantasy).

Run under xvfb (the UI sections need the real DraftView):
    xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_draft_reentry.py

Part A -- headless EntryDraftSession unit tests (journal, idempotency,
owner sync, audit, conductor deferral).
Part B -- real DraftView under Xvfb: drive picks, destroy the view,
re-enter, verify the SAME session/cursor/picks; mid-draft pick trade
repoints on re-entry; save/load mid-draft; corrupt journal -> honest
unavailable; complete the draft cleanly (no orphans/duplicates).
Part C -- fantasy draft: manager journal round-trip headless, mid-draft
save/load through the real GameSaveManager, FA identity (no duplicate
live objects), stale-manager -> unavailable.
"""
import datetime
import gzip
import os
import pickle
import random
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260930)

from qa_draft_common import make_league, StubAIMgr

PASS = 0
FAIL = 0
SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "qa_shots_reentry")
os.makedirs(SHOT_DIR, exist_ok=True)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}", flush=True)
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}", flush=True)


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


# ----------------------------------------------------------------------
# Part A: headless EntryDraftSession unit tests
# ----------------------------------------------------------------------
def part_a():
    print("\n=== Part A: EntryDraftSession units (headless) ===", flush=True)
    from qa_draft_common import make_league
    from draft_generator import generate_draft_class
    from draft_night import (EntryDraftSession, conduct_entry_draft,
                             resume_entry_draft_session)

    lg, nhl = make_league(2027)
    lg.draft_prospects = generate_draft_class(num_prospects=224,
                                              quality="Normal")
    lg.draft_prospects_year = 2027
    order = lg.get_draft_order(2027)
    vorder = []
    for overall, team, dp in order:
        try:
            rnd = int(getattr(dp, 'round', 0) or 0)
        except Exception:
            rnd = 0
        vorder.append([rnd, team, dp])
    check("order is 224 slots", len(vorder) == 224, str(len(vorder)))

    rng = random.Random(1234)
    sess = EntryDraftSession.begin(lg, 2027, vorder, None, rng)
    check("begin: 224 slots", len(sess.slots) == 224)
    check("is_live_for(2027)", sess.is_live_for(2027) is True)
    check("not live for 2028", sess.is_live_for(2028) is False)
    check("not complete at start", sess.is_complete() is False)

    # record_pick idempotency
    p0 = lg.draft_prospects[0]
    t0 = vorder[0][1]
    check("record_pick #1 -> True",
          sess.record_pick(1, t0.team_name, p0.id) is True)
    check("record_pick #1 again -> False (idempotent)",
          sess.record_pick(1, t0.team_name, p0.id) is False)
    check("has_pick(1)", sess.has_pick(1) is True)
    check("no phantom second entry", len(sess.picks) == 1,
          str(len(sess.picks)))
    sess.current_pick = 1
    # Production's execute_pick also commits the player to the selecting
    # team; mirror that here so the orphan audit sees a real state.
    t0.add_player(p0, "prospects")

    # to_dict / from_dict round-trip (incl. a pickle hop like a save)
    d = sess.to_dict()
    s2 = EntryDraftSession.from_dict(pickle.loads(pickle.dumps(d)))
    check("round-trip: 224 slots", len(s2.slots) == 224)
    check("round-trip: owner[0] preserved",
          s2.slots[0]['owner'] == sess.slots[0]['owner'])
    check("round-trip: 1 committed pick",
          len(s2.picks) == 1 and s2.picks[0]['player_id'] == p0.id)
    check("round-trip: cursor", s2.current_pick == 1, str(s2.current_pick))
    check("round-trip: rng state", s2.rng_state == sess.rng_state)
    check("round-trip: still live", s2.is_live_for(2027) is True)

    # Owner sync: trade a FUTURE pick while "away", re-entry repoints.
    slot5 = sess.slots[4]
    dp5 = next(dp for _o, _t, dp in order
               if str(getattr(dp, 'id', '')) == str(slot5['pick_id']))
    old_owner = slot5['owner']
    other = next(t for t in nhl if t.team_name != old_owner)
    dp5.current_team = other
    sess.sync_owners_from_league(lg)
    check("owner sync follows mid-draft trade",
          sess.slots[4]['owner'] == other.team_name,
          f"{old_owner} -> {sess.slots[4]['owner']}")
    check("committed pick keeps selecting team",
          sess.picks[0]['team'] == t0.team_name)
    dp5.current_team = next(t for _o, t, _d in order
                            if t.team_name == old_owner)
    # Revert the trade; re-sync like a real re-entry would, so the
    # session and the league agree again before the audit.
    sess.sync_owners_from_league(lg)

    # Audit on a consistent league
    issues = sess.audit(lg)
    check("audit clean on consistent state", issues == [],
          str(issues[:3]))

    # Conductor DEFERS to a live in-progress session (no hidden picks).
    lg.entry_draft_session = sess
    n_prospects_before = len(lg.draft_prospects)
    out = conduct_entry_draft(lg, 2027)
    check("conductor defers to live session (returns [])", out == [],
          str(len(out)))
    check("no hidden picks while parked",
          len(sess.picks) == 1 and len(lg.draft_prospects) ==
          n_prospects_before)
    check("year not stamped conducted",
          2027 not in set(getattr(lg, 'draft_conducted_years', None) or []))

    # resume_entry_draft_session never advances an in-progress session.
    out2 = resume_entry_draft_session(lg, sess)
    check("resume does not advance in-progress session",
          len(sess.picks) == 1, str(len(sess.picks)))

    # Complete-but-unfinalized session: resume finalizes, makes no picks.
    sess_all = EntryDraftSession.begin(lg, 2027, vorder, None,
                                       random.Random(7))
    for i, entry in enumerate(vorder):
        _r, _t, _dp = entry
        _pp = lg.draft_prospects[i % len(lg.draft_prospects)]
        sess_all.record_pick(i + 1, _t.team_name, _pp.id)
    sess_all.current_pick = len(vorder)
    check("full session is_complete", sess_all.is_complete() is True)
    lg.entry_draft_session = None
    print("Part A done.", flush=True)


# ----------------------------------------------------------------------
# Part B: real DraftView re-entry + save/load (Xvfb)
# ----------------------------------------------------------------------
class ReentryApp:
    """Stub app surface DraftView needs (mirrors qa_draft_runtime)."""

    def __init__(self, league, user_team, mapping):
        self.league = league
        self.user_team = user_team
        self.ai_manager = StubAIMgr(mapping)
        self.current_date = datetime.date(2027, 6, 28)
        self.news_log = []
        self.open_windows = {}
        self.mp_host = None
        self.tree_maps = {}
        self.free_agents = []
        self.game_results = []
        self.settings = {}
        self.player_stats_history = {}
        self.team_stats_history = {}
        self.draft_classes = {}
        self.scouting_reports = {}

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


def drive_picks(view, root, app, n, guard_extra=0):
    """Synchronously drive up to n picks (AI steps + user auto-picks).
    Counts real cursor advancement: _ai_step() fires _do_ai_pick() and
    then returns False on round-1 drama, so its return value undercounts.
    Neutralizes the pace driver so this loop owns advancement."""
    import draft_day_trades as ddt
    try:
        if view._ai_after_id:
            view.after_cancel(view._ai_after_id)
    except Exception:
        pass
    view._ai_after_id = None
    view._sim_active = True
    _orig_pace = view._set_pace
    view._set_pace = lambda *a, **k: None
    start = view.current_pick
    guard = 0
    try:
        while (view.current_pick - start < n
               and view.current_pick < len(view.draft_order)
               and guard < n + 500 + guard_extra):
            guard += 1
            _r, _t, _dp = view.draft_order[view.current_pick]
            if _t == app.user_team or getattr(_t, 'is_user_team', False):
                view.auto_pick()
            else:
                view._ai_step()
            root.update()
    finally:
        view._set_pace = _orig_pace
        view._sim_active = False
        try:
            if getattr(view, '_ai_after_id', None):
                view.after_cancel(view._ai_after_id)
        except Exception:
            pass
        view._ai_after_id = None
    root.update()
    return view.current_pick - start


def picks_snapshot(view):
    return [(ov, tn, getattr(pl, 'id', None))
            for tn, ov, pl in view.picks_made]


def part_b():
    print("\n=== Part B: DraftView re-entry + save/load (Xvfb) ===",
          flush=True)
    from qa_draft_common import make_league, StubAIMgr
    from draft_generator import generate_draft_class
    from ai_team_management import ManagementPriority
    import draft_day_trades as ddt
    from windows import DraftView

    ddt._incoming_call_dialog = lambda *a, **k: 'decline'

    lg, nhl = make_league(2027)
    lg.draft_prospects = generate_draft_class(num_prospects=224,
                                              quality="Normal")
    lg.draft_prospects_year = 2027
    user_team = nhl[3]
    user_team.is_user_team = True
    mapping = {t.team_name: ManagementPriority.MAINTAIN for t in nhl}
    app = ReentryApp(lg, user_team, mapping)

    root = tk.Tk()
    root.geometry("1600x900")
    root.title("Puck Dynasty - draft re-entry QA")
    try:
        from popup_system import register as _register_popups
        _register_popups(root)
    except Exception:
        pass

    # --- view 1: fresh draft, drive 12 picks -------------------------
    view1 = DraftView(root, app=app)
    view1.pack(fill="both", expand=True)
    root.update()
    check("view1: 224-slot order", len(view1.draft_order) == 224,
          str(len(view1.draft_order)))
    check("view1: league owns the session",
          lg.entry_draft_session is view1._session and
          lg.entry_draft_session is not None)
    made = drive_picks(view1, root, app, 12)
    check("view1: drove 12 picks", made == 12 and
          view1.current_pick == 12, f"{made}/{view1.current_pick}")
    snap1 = picks_snapshot(view1)
    sess1 = lg.entry_draft_session
    check("session journal has 12 picks", len(sess1.picks) == 12,
          str(len(sess1.picks)))
    check("session cursor at 12", sess1.current_pick == 12,
          str(sess1.current_pick))

    # --- trade a FUTURE pick while "away" (no sync call) ------------
    _r20, _t20, _dp20 = view1.draft_order[19]
    _new_owner = nhl[10] if nhl[10] != _t20 else nhl[11]
    _dp20.current_team = _new_owner
    # NOTE: deliberately NOT calling view1._sync_session_owners() --
    # the re-entry path must pick this up via sync_owners_from_league.

    # --- destroy view 1 (the _teardown_screen path) ------------------
    view1.destroy()
    root.update()
    check("session survives view destruction",
          lg.entry_draft_session is sess1)

    # --- view 2: re-entry -------------------------------------------
    view2 = DraftView(root, app=app)
    view2.pack(fill="both", expand=True)
    root.update()
    check("view2 re-attached the SAME session",
          view2._session is sess1 and lg.entry_draft_session is sess1)
    check("view2 cursor resumed at 12", view2.current_pick == 12,
          str(view2.current_pick))
    snap2 = picks_snapshot(view2)
    check("view2 picks identical to view1", snap2 == snap1,
          f"{len(snap2)} vs {len(snap1)}")
    check("view2 results tree rebuilt (12 rows)",
          len(view2.draft_results_tree.get_children()) == 12,
          str(len(view2.draft_results_tree.get_children())))
    _r20b, _t20b, _dp20b = view2.draft_order[19]
    check("mid-draft trade repointed on re-entry",
          _t20b.team_name == _new_owner.team_name,
          f"{_t20b.team_name} vs {_new_owner.team_name}")
    check("session slot owner follows trade",
          sess1.slots[19]['owner'] == _new_owner.team_name)
    grab(root, "reentry_mid_draft.png")

    # --- idempotency: re-firing an already-committed overall --------
    _saved_cur = view2.current_pick
    view2.current_pick = 5  # overall #6 already committed
    _rr, _tt, _ddp = view2.draft_order[5]
    _avail = view2._available_prospects()
    _dup = view2.execute_pick(_tt, _avail[0] if _avail else None)
    view2.current_pick = _saved_cur
    root.update()
    check("re-fired committed pick rejected",
          _dup is False and len(view2.picks_made) == 12,
          f"dup={_dup} picks={len(view2.picks_made)}")
    check("session journal still 12", len(sess1.picks) == 12)

    # --- save/load mid-draft (real GameSaveManager path) ------------
    from save_load_system import GameSaveManager
    os.makedirs("/tmp/qa_reentry_saves", exist_ok=True)
    sls = GameSaveManager(app)
    sls.save_directory = "/tmp/qa_reentry_saves"
    save_data = sls.create_save_data()
    check("save journal has entry session",
          isinstance(save_data['league'].get('entry_draft_session'),
                     dict),
          str(type(save_data['league'].get('entry_draft_session'))))
    spath = "/tmp/qa_reentry_saves/middraft.hm"
    with gzip.open(spath, 'wb') as f:
        pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Load into a FRESH app (new objects everywhere).
    with gzip.open(spath, 'rb') as f:
        loaded_data = pickle.load(f)
    app2 = ReentryApp(None, None, mapping)
    sls2 = GameSaveManager(app2)
    ok = sls2._restore_game_state(loaded_data)
    lg2 = app2.league
    check("load ok", ok is True and lg2 is not None)
    sess2 = getattr(lg2, 'entry_draft_session', None)
    check("session restored from journal", sess2 is not None)
    check("restored cursor at 12",
          sess2 is not None and sess2.current_pick == 12,
          str(getattr(sess2, 'current_pick', None)))
    check("restored 12 journaled picks",
          sess2 is not None and len(sess2.picks) == 12)
    if sess2 is not None:
        _ids1 = [p.get('player_id') for p in sess1.picks]
        _ids2 = [p.get('player_id') for p in sess2.picks]
        check("restored pick log identical", _ids1 == _ids2)
    check("no unavailable marker on good load",
          not getattr(lg2, 'entry_draft_unavailable_reason', None))

    # Re-entry on the LOADED league resumes the draft.
    app2.user_team = next(t for t in lg2.teams
                          if t.team_name == user_team.team_name)
    app2.user_team.is_user_team = True
    view2.destroy()
    root.update()
    view3 = DraftView(root, app=app2)
    view3.pack(fill="both", expand=True)
    root.update()
    check("loaded league: view re-attaches restored session",
          view3._session is sess2 and view3.current_pick == 12,
          str(view3.current_pick))
    made3 = drive_picks(view3, root, app2, 4)
    check("loaded league: draft continues (4 more picks)",
          made3 == 4 and view3.current_pick == 16,
          f"{made3}/{view3.current_pick}")

    # --- corrupt journal -> honest unavailable, never silent restart --
    bad_data = pickle.loads(pickle.dumps(loaded_data))
    bad_data['league']['entry_draft_session'] = {'bogus': 'journal'}
    app3 = ReentryApp(None, None, mapping)
    sls3 = GameSaveManager(app3)
    ok3 = sls3._restore_game_state(bad_data)
    lg3 = app3.league
    check("corrupt journal: session NOT restored",
          getattr(lg3, 'entry_draft_session', None) is None)
    check("corrupt journal: unavailable reason set",
          bool(getattr(lg3, 'entry_draft_unavailable_reason', None)),
          str(getattr(lg3, 'entry_draft_unavailable_reason', None))[:60])
    view3.destroy()
    root.update()
    app3.user_team = next(t for t in lg3.teams
                          if t.team_name == user_team.team_name)
    view4 = DraftView(root, app=app3)
    view4.pack(fill="both", expand=True)
    root.update()
    check("corrupt journal: view shows unavailable, no fresh draft",
          getattr(view4, '_session', None) is None and
          view4.current_pick == 0 and len(view4.picks_made) == 0)
    grab(root, "reentry_unavailable.png")
    view4.destroy()
    root.update()

    # --- complete the draft cleanly on the loaded league -------------
    view5 = DraftView(root, app=app2)
    view5.pack(fill="both", expand=True)
    root.update()
    check("re-entry after failed-load detour still resumes",
          view5.current_pick == 16, str(view5.current_pick))
    made5 = drive_picks(view5, root, app2, 500, guard_extra=2000)
    root.update()
    check("all 224 picks made", len(view5.picks_made) == 224,
          str(len(view5.picks_made)))
    try:
        view5.end_draft()
    except Exception as e:
        check("end_draft crash-free", False, str(e))
    root.update()
    check("year stamped conducted",
          2027 in set(getattr(lg2, 'draft_conducted_years', None) or []))
    check("session released after completion",
          getattr(lg2, 'entry_draft_session', None) is None)

    # No orphaned/duplicate prospects.
    _pids = [getattr(pl, 'id', None) for _tn, _ov, pl in view5.picks_made]
    check("224 unique drafted prospects",
          len(set(_pids)) == 224, f"{len(set(_pids))}")
    locs = {}
    for t in lg2.teams:
        for attr in ('prospects', 'roster', 'ahl_roster'):
            for p in (getattr(t, attr, None) or []):
                locs.setdefault(getattr(p, 'id', None), []).append(
                    t.team_name)
    _orph, _dup = 0, 0
    for pid in _pids:
        at = locs.get(pid, [])
        if not at:
            _orph += 1
        elif len(at) > 1:
            _dup += 1
    check("no orphaned drafted prospects", _orph == 0, str(_orph))
    check("no double-listed drafted prospects", _dup == 0, str(_dup))
    _leftover = [p for p in (lg2.draft_prospects or [])
                 if getattr(p, 'id', None) in set(_pids)]
    check("drafted prospects left the class", not _leftover,
          str(len(_leftover)))
    from draft_night import EntryDraftSession as _EDS
    check("grades persisted for 2027",
          "2027" in (getattr(lg2, 'draft_grades_history', None) or {}),
          str(list((getattr(lg2, 'draft_grades_history', None)
                    or {}).keys())[:4]))
    grab(root, "reentry_complete.png")
    view5.destroy()
    root.destroy()
    print("Part B done.", flush=True)


# ----------------------------------------------------------------------
# Part C: fantasy draft session (headless + save/load)
# ----------------------------------------------------------------------
def _gen_player(first, last, pid_suffix):
    import game_classes as g
    from game_classes import PlayerPosition
    p = g.Player(first_name=first, last_name=last, age=24,
                 primary_position=PlayerPosition.CENTER
                 if pid_suffix % 2 == 0 else PlayerPosition.LEFT_WING)
    try:
        p.id = f"qa-fantasy-{pid_suffix}"
    except Exception:
        pass
    return p


def part_c():
    print("\n=== Part C: fantasy draft session (headless + save/load) ===",
          flush=True)
    import game_classes as g
    from fantasy_draft import (FantasyDraftManager, DraftConfiguration,
                               fantasy_session_valid, audit_fantasy_draft)
    from save_load_system import GameSaveManager

    lg, nhl = make_league(2027)
    teams = nhl[:6]

    # Simulate pre-draft rosters (make_league leaves them empty): put 12
    # generated players on each team, then collect them into the pool
    # like the real flow does (collection clears the rosters).
    for i, t in enumerate(teams):
        for j in range(12):
            t.roster.append(_gen_player("Ros", f"T{i}P{j}",
                                        3000 + i * 12 + j))
    # Pool: 12 rostered per team (removed from rosters, like the real
    # collection), 8 free agents, 10 generated-only players.
    pool = []
    for t in teams:
        for p in list(t.roster):
            t.roster.remove(p)
            pool.append(p)
    fa_players = [_gen_player("Free", f"Agent{i}", 1000 + i)
                  for i in range(8)]
    gen_players = [_gen_player("Gen", f"Player{i}", 2000 + i)
                   for i in range(10)]
    pool.extend(fa_players)
    pool.extend(gen_players)
    check("fantasy pool built", len(pool) == 12 * 6 + 8 + 10,
          str(len(pool)))

    cfg = DraftConfiguration(rounds=8, serpentine=True,
                             draft_order_type="Randomized",
                             salary_cap_enabled=True)
    mgr = FantasyDraftManager(teams, pool, cfg)
    check("manager: 48 slots", len(mgr.draft_picks) == 48,
          str(len(mgr.draft_picks)))
    mgr.draft_started = True
    lg.fantasy_draft_manager = mgr

    # Make 10 picks: 4 rostered-origin, 2 FA-origin, 4 generated.
    avail = mgr.get_available_players()
    _by_id = {p.id: p for p in avail}
    picks_to_make = [pool[i] for i in (0, 1, 2, 3,     # rostered-origin
                                       72, 73,          # FA-origin
                                       80, 81, 82, 83)] # generated
    for p in picks_to_make:
        ok = mgr.make_pick(_by_id[p.id])
        if not ok:
            check("fantasy make_pick", False, f"pick failed for {p.id}")
            return
    check("10 fantasy picks made", mgr.current_pick == 10,
          str(mgr.current_pick))
    # Idempotency: rewind onto a committed overall -> rejected.
    _sv = mgr.current_pick
    mgr.current_pick = 3
    _dup = mgr.make_pick(mgr.get_available_players()[0])
    mgr.current_pick = _sv
    check("fantasy re-fired pick rejected",
          _dup is False and mgr.current_pick == 10, str(_dup))
    check("fantasy audit clean mid-draft",
          audit_fantasy_draft(mgr, lg) == [],
          str(audit_fantasy_draft(mgr, lg)[:2]))
    check("fantasy session valid", fantasy_session_valid(mgr, lg) is True)

    # --- save/load mid-draft through the real serializer -------------
    gm = ReentryApp(lg, teams[0], {})
    gm.free_agents = list(fa_players)
    gm.pending_fantasy_draft = True
    sls = GameSaveManager(gm)
    save_data = sls.create_save_data()
    jd = save_data['league'].get('fantasy_draft_session')
    check("save journal present", isinstance(jd, dict), str(type(jd)))
    if isinstance(jd, dict):
        check("journal: 10 committed picks", len(jd.get('picks', [])) == 10,
              str(len(jd.get('picks', []))))
        check("journal: drafted players carried",
              len(jd.get('drafted', [])) == 10,
              str(len(jd.get('drafted', []))))
        check("journal: cursor", jd.get('current_pick') == 10,
              str(jd.get('current_pick')))
    check("save: pending flag persisted",
          save_data.get('pending_fantasy_draft') is True)
    spath = "/tmp/qa_reentry_saves/fantasy_middraft.hm"
    with gzip.open(spath, 'wb') as f:
        pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    with gzip.open(spath, 'rb') as f:
        loaded = pickle.load(f)
    gm2 = ReentryApp(None, None, {})
    sls2 = GameSaveManager(gm2)
    ok = sls2._restore_game_state(loaded)
    lg2 = gm2.league
    check("fantasy load ok", ok is True and lg2 is not None)
    mgr2 = getattr(lg2, 'fantasy_draft_manager', None)
    check("fantasy manager restored", mgr2 is not None)
    if mgr2 is not None:
        check("restored cursor at 10", mgr2.current_pick == 10,
              str(mgr2.current_pick))
        _ids1 = [pk.player.id for pk in mgr.draft_picks if pk.player]
        _ids2 = [pk.player.id for pk in mgr2.draft_picks if pk.player]
        check("restored picks identical", _ids1 == _ids2,
              f"{len(_ids1)} vs {len(_ids2)}")
        check("restored pool size",
              len(mgr2.get_available_players()) == len(pool) - 10,
              f"{len(mgr2.get_available_players())} vs {len(pool) - 10}")
        # Identity: one live object per player -- drafted picks
        # reference the journal-restored objects, and the FA list was
        # repointed at the draft's live objects (no duplicates). The
        # restore writes FAs to league.free_agents when there is no
        # database_manager (pre-existing routing); the reconcile covers
        # every holder.
        _all_ids = [p.id for p in mgr2.all_players]
        check("no duplicate ids in restored all_players",
              len(set(_all_ids)) == len(_all_ids),
              f"{len(_all_ids) - len(set(_all_ids))} dups")
        _fa_list = (getattr(lg2, 'free_agents', None)
                    or getattr(gm2, 'free_agents', None) or [])
        _fa_ids = [getattr(p, 'id', None) for p in _fa_list]
        _live_by_id = {p.id: p for p in mgr2.all_players}
        _fa_dup = sum(1 for i, pid in enumerate(_fa_ids)
                      if pid in _live_by_id and
                      (_fa_list[i] is not _live_by_id[pid]))
        check("FA list repointed at draft live objects (no dupes)",
              _fa_dup == 0 and len(_fa_ids) == 8,
              f"dupes={_fa_dup} n={len(_fa_ids)}")
        check("restored audit clean",
              audit_fantasy_draft(mgr2, lg2) == [],
              str(audit_fantasy_draft(mgr2, lg2)[:2]))
        check("restored session valid",
              fantasy_session_valid(mgr2, lg2) is True)
    check("pending flag restored",
          bool(getattr(gm2, 'pending_fantasy_draft', False)) is True)
    check("no unavailable marker on good fantasy load",
          not getattr(lg2, 'fantasy_draft_unavailable_reason', None))

    # --- corrupt fantasy journal -> honest unavailable ----------------
    bad = pickle.loads(pickle.dumps(loaded))
    bad['league']['fantasy_draft_session'] = {'bogus': 'journal'}
    gm3 = ReentryApp(None, None, {})
    sls3 = GameSaveManager(gm3)
    sls3._restore_game_state(bad)
    lg3 = gm3.league
    check("corrupt fantasy journal: manager NOT restored",
          getattr(lg3, 'fantasy_draft_manager', None) is None)
    check("corrupt fantasy journal: unavailable reason set",
          bool(getattr(lg3, 'fantasy_draft_unavailable_reason', None)))

    # --- stale (non-manager) session object -> invalid ----------------
    check("stale session object invalid",
          fantasy_session_valid("not-a-manager", lg) is False)
    print("Part C done.", flush=True)


def main():
    part_a()
    part_b()
    part_c()
    print(f"\n==== RESULT: {PASS} passed, {FAIL} failed ====", flush=True)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
