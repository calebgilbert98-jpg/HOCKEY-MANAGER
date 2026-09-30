"""QA: draft UX backlog -- the 8 items.

Covers: shared headless conductor (item 4), deterministic per-draft RNG
(item 3), name dedup with deterministic fallback (item 5), counter-asset
revalidation (item 2), SP draft countdown wiring (item 1), draft grades
persistence (item 8), rights UX (item 6), trade-up rumor mill (item 7),
save/load round-trip of the new draft state, and the overall_pick fix.

Bug history: this work was half-applied, then held back from a push for
three defects -- a duplicate headless conductor alongside
main._auto_conduct_entry_draft, draft_conducted_years serialized without
restore (save/load would wipe the idempotency guard and allow a
double-conduct), and name dedup with no fallback and no tests. All three
are resolved and pinned here.
"""
import os
import random
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


from game_classes import (League, Team)


def make_team(i):
    t = Team(f"Club{i}", f"City{i}", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    return t


from game_classes import DraftPick  # noqa: E402


class FakePick(DraftPick):
    def __init__(self, rnd, team_name):
        super().__init__(year=2029, round=rnd, original_team=team_name,
                         current_team=team_name)
        self.overall_pick = None


def make_draft_league(n_teams=4, n_prospects=40, year=2029, seed=1234):
    """Small league with a real generated prospect class and a stubbed
    7-round draft order in the REAL get_draft_order shape:
    (overall_pick, team, draft_pick) -- the round lives on the pick."""
    import draft_generator
    random.seed(seed)
    league = League("NHL")
    league.season_year = year
    league.draft_prospects_year = year
    teams = [make_team(i) for i in range(n_teams)]
    league.teams = teams
    league.draft_prospects = draft_generator.generate_draft_class(
        n_prospects, draft_year=year)
    order = []
    _ov = 0
    for rnd in range(1, 8):
        for t in teams:
            _ov += 1
            order.append((_ov, t, FakePick(rnd, t.team_name)))
    league.get_draft_order = lambda _y: order  # noqa: E731
    league.initialize_all_draft_picks = lambda: None  # noqa: E731
    return league, teams, order


def make_app(league, teams):
    news = []
    app = SimpleNamespace(
        league=league, user_team=teams[0], ai_manager=None,
        add_news=lambda s: news.append(s),
        mp_host=None, current_date="2029-06-27")
    app._news = news
    return app


# ---------------------------------------------------------------------------
# Item 4: shared conductor
# ---------------------------------------------------------------------------
from draft_night import (conduct_entry_draft, ai_select_prospect, ticker_line, stable_draft_seed)

league, teams, order = make_draft_league()
app = make_app(league, teams)
picks = conduct_entry_draft(league, 2029, app=app, seed=99)

check("conductor: every slot conducted once",
      len(picks) == 28, f"got {len(picks)}")
_slots = [(tn, ov) for tn, ov, _p in picks]
check("conductor: (team, overall) unique",
      len(set(_slots)) == len(_slots))
check("conductor: overalls are 1..N in order",
      [ov for _tn, ov, _p in picks] == list(range(1, 29)))
check("conductor: picks stamped with overall not round on DraftPick",
      all(getattr(_dp, 'overall_pick', None) == _ov
          for _ov, (_r, _t, _dp) in zip(range(1, 29), order)),
      "overall_pick mislabeled")
check("conductor: rights stamped to picking club",
      all(getattr(_p, 'rights_team', '') == _tn
          and int(getattr(_p, 'rights_expiry_year', 0) or 0) > 2029
          for _tn, _ov, _p in picks))
check("conductor: prospects land in club pools",
      all(any(_p is _q for _q in
              next(t for t in teams if t.team_name == _tn).prospects)
          for _tn, _ov, _p in picks))
check("conductor: conducted year stamped",
      2029 in set(getattr(league, 'draft_conducted_years', []) or []))
check("conductor: draft_prospects drained, leftovers in undrafted_pool",
      (getattr(league, 'draft_prospects', None) or []) == []
      and len(getattr(league, 'undrafted_pool', []) or []) == 40 - 28)
check("conductor: news names top-10 by OVERALL (not round)",
      any("#1 " in _n and "#10 " in _n for _n in app._news),
      str(app._news[:1]))
check("conductor: grades persisted",
      isinstance(getattr(league, 'draft_grades_history', None), dict)
      and "2029" in league.draft_grades_history
      and len(league.draft_grades_history["2029"]) == 4)

# get_draft_order contract: (overall_pick, team, draft_pick). The round the
# AI sees must come from draft_pick.round (1-7) -- never the overall number.
import draft_night as _dn_mod
_cleague, _cteams, _ = make_draft_league(n_teams=4, n_prospects=40, seed=606)
_capp = make_app(_cleague, _cteams)
_seen_rounds = []
_orig_sel = _dn_mod.ai_select_prospect


def _spy_select(team, available, team_board, needs, round_num,
                priority, rng, overall=1, drafted=None):
    _seen_rounds.append(round_num)
    return _orig_sel(team, available, team_board, needs, round_num,
                     priority, rng, overall=overall, drafted=drafted)


_dn_mod.ai_select_prospect = _spy_select
try:
    _cpicks = _dn_mod.conduct_entry_draft(_cleague, 2029, app=_capp, seed=606)
finally:
    _dn_mod.ai_select_prospect = _orig_sel
check("contract: AI sees rounds 1-7 (not overalls 1..N)",
      _seen_rounds and all(1 <= _r <= 7 for _r in _seen_rounds),
      f"rounds seen: {sorted(set(_seen_rounds))}")
check("contract: all 7 rounds reached",
      sorted(set(_seen_rounds)) == list(range(1, 8)),
      str(sorted(set(_seen_rounds))))

# Idempotency: second run is a no-op.
_pools_before = [len(t.prospects) for t in teams]
picks2 = conduct_entry_draft(league, 2029, app=app, seed=99)
check("conductor: double-run is a no-op",
      picks2 == [] and [len(t.prospects) for t in teams] == _pools_before)

# Draft-year source: explicit > draft_prospects_year > season_year.
league_b, teams_b, _o2 = make_draft_league(year=2030, seed=7)
app_b = make_app(league_b, teams_b)
league_b.draft_prospects_year = 2031
conduct_entry_draft(league_b, None, app=app_b, seed=5)
check("conductor: falls back to draft_prospects_year when year is None",
      2031 in set(league_b.draft_conducted_years or []))
league_c, teams_c, _o3 = make_draft_league(year=2032, seed=8)
league_c.draft_prospects_year = None
app_c = make_app(league_c, teams_c)
conduct_entry_draft(league_c, None, app=app_c, seed=5)
check("conductor: falls back to season_year",
      2032 in set(league_c.draft_conducted_years or []))

# Re-entry ban: a club can't re-select the kid it lost unsigned.
league_d, teams_d, _o4 = make_draft_league(n_prospects=40, seed=11)
_banned = league_d.draft_prospects[0]
_banned.draft_reentry_from = teams_d[1].team_name
app_d = make_app(league_d, teams_d)
picks_d = conduct_entry_draft(league_d, 2029, app=app_d, seed=21)
check("conductor: re-entry ban honored",
      all(not (_tn == teams_d[1].team_name and _p is _banned)
          for _tn, _ov, _p in picks_d))

# ---------------------------------------------------------------------------
# Item 3: deterministic per-draft RNG (one seed, replay-identical)
# ---------------------------------------------------------------------------
def _seq(seed_league, conduct_seed):
    lg, tms, _o = make_draft_league(seed=seed_league)
    _app = make_app(lg, tms)
    _picks = conduct_entry_draft(lg, 2029, app=_app, seed=conduct_seed)
    return [getattr(_p, 'full_name', '') for _tn, _ov, _p in _picks]


_s1, _s2 = _seq(4242, 99), _seq(4242, 99)
check("rng: same seed replays identically", _s1 == _s2 and len(_s1) == 28,
      f"{len(_s1)} vs {len(_s2)}")
check("rng: stable_draft_seed is process-stable",
      stable_draft_seed(2029) == stable_draft_seed(2029)
      and stable_draft_seed(2029) != stable_draft_seed(2030))

_pl = league.draft_prospects[0] if getattr(league, 'draft_prospects', None) \
    else teams[0].prospects[0]
_t1 = ticker_line(1, "Club0", _pl, 1, rng=random.Random(5))
_t2 = ticker_line(1, "Club0", _pl, 1, rng=random.Random(5))
check("rng: seeded ticker is deterministic", _t1 == _t2, f"{_t1} vs {_t2}")
_t3 = ticker_line(1, "Club0", _pl, 1)  # legacy unseeded path still works
check("rng: unseeded ticker still renders", isinstance(_t3, str) and _t3)

# War room funnels through the same selector (no divergent engines).
import inspect as _inspect
import windows as _windows_mod
_src = _inspect.getsource(_windows_mod.DraftView._do_ai_pick)
check("parity: war room _do_ai_pick uses draft_night.ai_select_prospect",
      "ai_select_prospect" in _src)
check("parity: war room seeds ticker from per-draft rng",
      "rng=self._draft_rng" in
      _inspect.getsource(_windows_mod.DraftView.execute_pick))
import main as _main_mod
_cls_with = None
for _nm in dir(_main_mod):
    _obj = getattr(_main_mod, _nm)
    if isinstance(_obj, type) and hasattr(_obj, '_auto_conduct_entry_draft'):
        _cls_with = _obj
        break
_src_main = _inspect.getsource(_cls_with._auto_conduct_entry_draft) \
    if _cls_with else ""
check("parity: main delegates to conduct_entry_draft (no second engine)",
      "conduct_entry_draft" in _src_main
      and "random.uniform(0.94, 1.06)" not in _src_main)

# ---------------------------------------------------------------------------
# Item 5: name dedup (+ deterministic fallback)
# ---------------------------------------------------------------------------
import draft_generator as _dg

random.seed(31337)
_cls = _dg.generate_draft_class(224, draft_year=2033)
_names = [f"{getattr(_p, 'first_name', '')} {getattr(_p, 'last_name', '')}"
          for _p in _cls]
check("names: 224-prospect class has no duplicate full names",
      len(set(_names)) == len(_names),
      f"{len(_names) - len(set(_names))} dupes")

# Re-entry collision: generated kids can't take a re-entry's name.
_re1 = _cls[0]
_re2 = _cls[1]
random.seed(777)
_cls2 = _dg.generate_draft_class(30, draft_year=2034,
                                 reentries=[_re1, _re2])
_n2 = [f"{getattr(_p, 'first_name', '')} {getattr(_p, 'last_name', '')}"
       for _p in _cls2]
check("names: no collisions incl. re-entries",
      len(set(_n2)) == len(_n2))

# Duplicate re-entry names: two eligible re-entries sharing a full name are
# normalized deterministically (first keeps it, second takes Jr.) -- never
# by random re-roll, which would rewrite a real player's identity.
random.seed(4242)
_rbase = _dg.generate_draft_class(10, draft_year=2036)
_ra, _rb = _rbase[0], _rbase[1]
_ra.first_name, _ra.last_name = "Alex", "Duplicate"
_rb.first_name, _rb.last_name = "Alex", "Duplicate"
_cls4 = _dg.generate_draft_class(12, draft_year=2037,
                                 reentries=[_ra, _rb])
_n4 = [f"{getattr(_p, 'first_name', '')} {getattr(_p, 'last_name', '')}"
       for _p in _cls4]
check("names: duplicate re-entry names normalized deterministically",
      len(set(_n4)) == len(_n4) == 12
      and _n4[0] == "Alex Duplicate"
      and _n4[1] == "Alex Duplicate Jr.",
      str(_n4[:3]))

# Pathological pool: every roll collides -> suffix fallback terminates.
_orig_grn = _dg.get_random_name
_dg.get_random_name = lambda _c: ("Test", "Collision")
try:
    random.seed(99)
    _cls3 = _dg.generate_draft_class(12, draft_year=2035)
    _n3 = [f"{getattr(_p, 'first_name', '')} {getattr(_p, 'last_name', '')}"
           for _p in _cls3]
    check("names: pathological pool terminates with unique names",
          len(set(_n3)) == len(_n3) == 12, str(_n3[:4]))
    check("names: suffix fallback used (Jr./II/III/IV or numeric)",
          any(" " in _n and _n.split(" ")[-1] in
              ("Jr.", "II", "III", "IV") or _n.split(" ")[-1].isdigit()
              for _n in _n3[1:]), str(_n3[:4]))
finally:
    _dg.get_random_name = _orig_grn

# ---------------------------------------------------------------------------
# Item 2: counter-asset revalidation
# ---------------------------------------------------------------------------
import trade_engine as _te

_DV = _windows_mod.DraftView


def _fake_view(league, user_team):
    """Minimal DraftView-shaped self for the validation/mutation methods."""
    gm_hist = []
    gm = SimpleNamespace(trade_history=gm_hist,
                         current_date="2029-06-27")
    app = SimpleNamespace(league=league, user_team=user_team,
                          game_manager=gm, current_date="2029-06-27",
                          add_news_story=lambda s: None)
    return SimpleNamespace(te=_te, app=app, _ticker=lambda s: None,
                           _swap_pick_owner=lambda _pk, _tm: setattr(
                               _pk, 'current_team', _tm.team_name))


def _mk_player(name, salary, team_name):
    """Lightweight trade asset: cap hit lives on contract.salary (the
    canonical location trade_engine reads)."""
    return SimpleNamespace(
        full_name=name, team_name=team_name,
        contract=SimpleNamespace(salary=salary, no_trade_clause=False,
                                 no_movement_clause=False,
                                 modified_ntc_teams=0,
                                 modified_ntc_approved=False,
                                 ntc_waiver_for=""))


league_v, teams_v, _ov = make_draft_league(n_teams=2, n_prospects=0, seed=55)
_user, _partner = teams_v[0], teams_v[1]
_upick = FakePick(1, _user.team_name)
_ppick = FakePick(1, _partner.team_name)
_vet = _mk_player("Veteran Plug", 1_000_000, _user.team_name)
_user.roster.append(_vet)
_fv = _fake_view(league_v, _user)

# Happy path: all assets legal.
_ok, _why = _DV._validate_pick_swap(_fv, _partner, _upick, _ppick,
                                    [_vet], [])
check("validate: clean counter passes", _ok, _why)

# Counter-added asset moved since the counter: blocked.
_user.roster.remove(_vet)
_ok, _why = _DV._validate_pick_swap(_fv, _partner, _upick, _ppick,
                                    [_vet], [])
check("validate: moved counter asset blocked",
      not _ok and "no longer on your roster" in _why, _why)
_user.roster.append(_vet)

# Partner's sweetener moved: blocked.
_sweet = _mk_player("Sweetener Lou", 900_000, _partner.team_name)
_partner.roster.append(_sweet)
_partner.roster.remove(_sweet)
_ok, _why = _DV._validate_pick_swap(_fv, _partner, _upick, _ppick,
                                    [], [_sweet])
check("validate: moved partner asset blocked",
      not _ok and "no longer on their roster" in _why, _why)

# NTC veto wiring: a vetoed clause blocks when the player won't waive.
_ntc = _mk_player("Clause Guy", 2_000_000, _partner.team_name)
try:
    _ntc.contract.no_trade_clause = True
except Exception:
    pass
_partner.roster.append(_ntc)
_vetoes = _te.trade_vetoes(_partner, _user, [_ntc], league_v)
_orig_waive = _te.will_waive_ntc
_te.will_waive_ntc = lambda *a, **k: (False, "He won't waive for them.")
try:
    _ok, _why = _DV._validate_pick_swap(_fv, _partner, _upick, _ppick,
                                        [], [_ntc])
    check("validate: unwaived NTC blocks",
          (not _vetoes and _ok) or (bool(_vetoes) and not _ok), _why)
finally:
    _te.will_waive_ntc = _orig_waive

# Cap gate is consulted both directions (wire it to fail closed).
_orig_cap = _te._cap_ok_after
_te._cap_ok_after = lambda *a, **k: False
try:
    _ok, _why = _DV._validate_pick_swap(_fv, _partner, _upick, _ppick,
                                        [], [])
    check("validate: cap failure blocks", not _ok and "cap" in _why, _why)
finally:
    _te._cap_ok_after = _orig_cap

# CompletedTrade records the FULL deal (base picks + counter assets).
_fv2 = _fake_view(league_v, _user)
_fv2._validate_pick_swap = lambda *a: _DV._validate_pick_swap(_fv2, *a)
_fv2.draft_order = [[1, _partner, _ppick]]
_DV._execute_pick_swap(_fv2, 0, _upick, _ppick, [_vet], [])
_hist = _fv2.app.game_manager.trade_history
check("history: CompletedTrade recorded", len(_hist) == 1)
if _hist:
    _ct = _hist[0]
    _ug = " ".join(getattr(_ct, 'a_gave', []) or [])
    _pg = " ".join(getattr(_ct, 'b_gave', []) or [])
    check("history: counter-added asset present in record",
          "Veteran" in _ug or "Plug" in _ug, f"out={_ug} in={_pg}")
    check("history: base picks present in record",
          bool(_ug) and bool(_pg), f"out={_ug} in={_pg}")

# ---------------------------------------------------------------------------
# Item 1: SP draft countdown wiring
# ---------------------------------------------------------------------------
_src_pdp = _inspect.getsource(_DV.process_draft_pick)
check("clock: armed only in single-player (mp_host guard)",
      "mp_host" in _src_pdp and "_start_sp_draft_clock" in _src_pdp)
check("clock: cancelled for AI/MP turns",
      "_cancel_sp_draft_clock" in _src_pdp)
_src_tick = _inspect.getsource(_DV._sp_clock_tick)
check("clock: defers while a modal holds the grab",
      "grab_current" in _src_tick)
check("clock: expiry auto-picks (never stalls)",
      "self.auto_pick()" in _src_tick)
check("clock: multiplayer path untouched",
      "_mp_open_draft_clock" in _src_pdp
      and "60" in _src_pdp)

# Runtime: start/cancel schedule bookkeeping; expiry fires auto_pick.
_calls = []
_after_seq = [0]


def _fake_after(_ms, _fn):
    _after_seq[0] += 1
    _calls.append((_ms, _fn))
    return _after_seq[0]


_fself = SimpleNamespace(
    _sp_clock_id=None, _sp_clock_left=0,
    app=SimpleNamespace(
        get_settings=lambda: {'draft': {'clock_seconds': 60}}),
    after=_fake_after,
    after_cancel=lambda _i: _calls.append(('cancel', _i)),
    grab_current=lambda: None,
    clock_label=SimpleNamespace(
        configure=lambda **k: _calls.append(('label', k))),
    _ticker=lambda s: _calls.append(('ticker', s)),
    auto_pick=lambda: _calls.append(('auto_pick',)),
    current_pick=0,
    draft_order=[[1, SimpleNamespace(team_name="ClubX"), None]])
_fself.app.user_team = _fself.draft_order[0][1]
for _m in ("_start_sp_draft_clock", "_cancel_sp_draft_clock",
           "_sp_clock_tick"):
    setattr(_fself, _m, (lambda _mm: lambda *_a: getattr(_DV, _mm)(_fself, *_a))(_m))
_DV._start_sp_draft_clock(_fself)
check("clock: start schedules a tick",
      _fself._sp_clock_id == 1 and _fself._sp_clock_left == 59,
      f"id={_fself._sp_clock_id} left={_fself._sp_clock_left}")
_DV._cancel_sp_draft_clock(_fself)
check("clock: cancel clears the schedule",
      _fself._sp_clock_id is None and ('cancel', 1) in _calls)
_DV._start_sp_draft_clock(_fself)
_fself._sp_clock_left = 0
_calls.clear()
_DV._sp_clock_tick(_fself)
check("clock: expiry calls auto_pick",
      ('auto_pick',) in _calls, str(_calls[-3:]))
# Modal open: tick defers instead of firing.
_calls.clear()
_fself._sp_clock_left = 0
_fself.grab_current = lambda: object()
_DV._sp_clock_tick(_fself)
check("clock: modal grab defers expiry",
      ('auto_pick',) not in _calls and _fself._sp_clock_id is not None)

# ---------------------------------------------------------------------------
# Item 6: rights UX (lives on RosterView's Prospects tab)
# ---------------------------------------------------------------------------
_RV = _windows_mod.RosterView
_rself = SimpleNamespace(
    app=SimpleNamespace(
        league=SimpleNamespace(season_year=2029),
        user_team=SimpleNamespace(team_name="Club0")))

_signed = SimpleNamespace(
    contract=SimpleNamespace(salary=925_000, years_remaining=3),
    rights_team="", rights_expiry_year=0)
check("rights: signed prospect reads Signed",
      _RV._rights_status(_rself, _signed) == "Signed")

# Placeholder contracts (salary set, 0 years left -- what generated
# draftees carry) are NOT signed: they still show rights status.
_placeholder = SimpleNamespace(
    contract=SimpleNamespace(salary=750_000, years_remaining=0),
    rights_team="Club0", rights_expiry_year=2033)
check("rights: placeholder contract reads rights, not Signed",
      _RV._rights_status(_rself, _placeholder) == "Rights '33")

_expiring = SimpleNamespace(contract=None, rights_team="Club0",
                            rights_expiry_year=2029)
check("rights: expiring this year warns",
      _RV._rights_status(_rself, _expiring) == "⚠ Rights '29",
      _RV._rights_status(_rself, _expiring))
_future = SimpleNamespace(contract=None, rights_team="Club0",
                          rights_expiry_year=2032)
check("rights: future expiry calm",
      _RV._rights_status(_rself, _future) == "Rights '32")
_bare = SimpleNamespace(contract=None, rights_team="",
                        rights_expiry_year=0)
check("rights: no rights reads blank",
      _RV._rights_status(_rself, _bare) == "—")

# Rights Watch lists soonest-expiry first.
_rpool = SimpleNamespace(
    prospects=[_future, _expiring, _signed],
    team_name="Club0")
_rself2 = SimpleNamespace(
    app=SimpleNamespace(user_team=_rpool,
                        league=SimpleNamespace(season_year=2029)))
_watch = _RV._unsigned_rights_prospects(_rself2)
check("rights: watch lists unsigned only, soonest first",
      _watch == [_expiring, _future], str(_watch))

# ---------------------------------------------------------------------------
# Item 7: trade-up rumor mill
# ---------------------------------------------------------------------------
import draft_day_trades as _ddt

_rleague = SimpleNamespace()
_rnews = []
_rapp = SimpleNamespace(league=_rleague,
                        add_news=lambda s: _rnews.append(s))
for _i in range(5):
    _ddt._emit_trade_rumor(_rleague, _rapp, f"RUMOR: test {_i}")
check("rumor: capped at 3 per draft", len(_rnews) == 3, str(_rnews))
check("rumor: labeled RUMOR, never a completed deal",
      all(_n.startswith("RUMOR:") for _n in _rnews)
      and not any("TRADE:" in _n and "RUMOR" not in _n for _n in _rnews))

# Failed negotiation -> rumor (not silence, not a fake deal).
_nleague, _nteams, _ = make_draft_league(n_teams=4, n_prospects=0, seed=5)
_nleague.draft_prospects = []
_napp = SimpleNamespace(league=_nleague, ai_manager=None,
                        add_news=lambda s: _rnews.append(s))
_prosp = SimpleNamespace(full_name="Rumor Kid",
                         primary_position=SimpleNamespace(value="C"))
_teamA, _teamB = _nteams[2], _nteams[0]
_apick = FakePick(1, _teamA.team_name)
_bpick = FakePick(1, _teamB.team_name)
_order = [(1, _nteams[0], _bpick), (2, _nteams[1], FakePick(1, _nteams[1].team_name)),
          (3, _teamA, _apick), (4, _nteams[3], FakePick(1, _nteams[3].team_name))]
_orig_neg = _ddt._negotiate
_orig_board = _ddt._draft_board
_orig_target = _ddt._trade_up_target
_orig_offer = _ddt._build_trade_up_offer
_ddt._negotiate = lambda *a, **k: None  # talks collapse
_ddt._draft_board = lambda _lg: [_prosp]
_ddt._trade_up_target = lambda *a, **k: (1, _prosp)
_ddt._build_trade_up_offer = lambda *a, **k: ([_apick], [_bpick])
_nleague._trade_up_rumors = 0
try:
    _done = _ddt._attempt_trade_up(_teamA, 3, _apick, _nleague, 2029,
                                   [_prosp], _napp, None, _order)
    check("rumor: failed trade-up talks surface as rumor, not a deal",
          _done is None and any("RUMOR:" in _n and "Rumor Kid" in _n
                                for _n in _rnews), str(_rnews[-2:]))
finally:
    _ddt._negotiate = _orig_neg
    _ddt._draft_board = _orig_board
    _ddt._trade_up_target = _orig_target
    _ddt._build_trade_up_offer = _orig_offer

# ---------------------------------------------------------------------------
# Item 8: grades persistence
# ---------------------------------------------------------------------------
_gleague, _gteams, _ = make_draft_league(seed=202)
_gapp = make_app(_gleague, _gteams)
_gpicks = conduct_entry_draft(_gleague, 2029, app=_gapp, seed=7)
_hist = _gleague.draft_grades_history.get("2029")
check("grades: persisted per year with (team, grade, ratio)",
      isinstance(_hist, list) and len(_hist) == 4
      and all(len(_r) == 3 for _r in _hist))
check("grades: every club graded exactly once",
      sorted(_t for _t, _g, _r in _hist)
      == sorted(_t.team_name for _t in _gteams))

# ---------------------------------------------------------------------------
# Save/load round-trip: conducted years + grades history
# ---------------------------------------------------------------------------
import tempfile as _tf
from save_load_system import GameSaveManager as _SLS

_gm = SimpleNamespace(league=_gleague, league_history=None,
                      narrative_ledger=None)
_saver = _SLS(_gm)
_tmp = _tf.mkdtemp()
_path = os.path.join(_tmp, "draft_test.save")
check("save: succeeds", _saver.save_game(_path), _path)
_gm2 = SimpleNamespace(league=None, league_history=None,
                       narrative_ledger=None)
_loader = _SLS(_gm2)
check("load: succeeds", _loader.load_game(_path), _path)
_lg2 = _gm2.league
check("save/load: draft_conducted_years survives",
      list(getattr(_lg2, 'draft_conducted_years', []) or []) == [2029],
      str(getattr(_lg2, 'draft_conducted_years', None)))
check("save/load: draft_grades_history survives",
      isinstance(getattr(_lg2, 'draft_grades_history', None), dict)
      and "2029" in (_lg2.draft_grades_history or {})
      and len(_lg2.draft_grades_history["2029"]) == 4)

# Old save without the keys -> graceful defaults, no crash.
_orig_ser = _saver._serialize_league
def _stripped_ser():
    _d = _orig_ser()
    _d.pop('draft_conducted_years', None)
    _d.pop('draft_grades_history', None)
    return _d
_saver._serialize_league = _stripped_ser
_path_old = os.path.join(_tmp, "draft_test_old.save")
_old_ok = _saver.save_game(_path_old)
_gm3 = SimpleNamespace(league=None, league_history=None,
                       narrative_ledger=None)
_s3 = _SLS(_gm3)
_old_ok = _old_ok and _s3.load_game(_path_old)
_lg3 = _gm3.league
_old_ok = (_old_ok
           and list(getattr(_lg3, 'draft_conducted_years', None) or []) == []
           and getattr(_lg3, 'draft_grades_history', None) == {})
check("save/load: old save without keys loads with defaults",
      _old_ok is True, str(_old_ok)[:120])

print(f"\n{'='*60}\nQA draft_ux: {PASS} passed, {FAIL} failed")
for _f in FAILURES:
    print("FAIL:", _f)
sys.exit(1 if FAIL else 0)
