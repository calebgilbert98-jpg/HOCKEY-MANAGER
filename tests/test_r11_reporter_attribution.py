"""R11 — Reporter attribution: personas frame the same premise differently
at TEMPLATE level (not just a per-persona question bank on identical body
text).

Acceptance: the same premise renders in >=2 persona-distinct framings,
and a blind read can't match them to the same template. The blind read
itself is done by an independent reviewer over hidden_files probe output;
these tests pin the mechanism:

  1. Quote events produced by _run_interview carry the premise
     ("result" win/loss, "heated") the framing renders from.
  2. The same premise (identical question AND reporter name, only the
     archetype differs) renders to distinct outputs per persona.
  3. No template string is shared between persona banks.
  4. Every template in every bank is reachable.
  5. The renderer never raises on junk input.
  6. The premise content (question, quote) survives rendering verbatim.
  7. Rendered stories never assert a false result (a win story never
     claims a loss and vice versa).

Tests 1-4 FAIL on pre-R11 code (no "result" key, byte-identical flat
render across archetypes, no _frame_quote_story / template banks).
"""
import random
import re
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, ".")

import media_engine as me


Q = "\u201cIs the coach\u2019s message still getting through in here?\u201d"
QUOTE = "\u201cWe\u2019ve got to be better. That\u2019s on us.\u201d"


def _premise(archetype, result="loss", outcome="bland", heated=True):
    """One fixed premise; only the persona varies."""
    return {
        "kind": "quote",
        "team": "Boston Bruins",
        "player": "David Pastrnak",
        "reporter": "Press Row",
        "archetype": archetype,
        "outcome": outcome,
        "result": result,
        "heated": heated,
        "question": Q,
        "quote": QUOTE,
    }


def _stub_interview(won, archetype="stirrer"):
    """Run the real _run_interview with stub objects; the stub player is
    deliberately ordinary (not a leader, not a hot head) so the normal
    quote path fires deterministically in structure."""
    player = SimpleNamespace(
        full_name="Test Player", last_name="Player",
        composure=60, controversy=30, leadership=50, pressure_player=50,
        nhl_games_played=200, morale=70, team_chemistry=60,
    )
    team = SimpleNamespace(
        team_name="Test Team", roster=[], wins=10, losses=10, ot_losses=0,
        media_games_covered=0, media_moment_cd={},
    )
    league = SimpleNamespace(
        media_narratives=[], media_fines=[], coach_media_beefs=[],
        media_recent_faces=[],
    )
    reporter = me.Reporter("Test Reporter", "Test Market", archetype)
    events = []
    rng = random.Random(1234)
    me._run_interview(league, team, player, reporter, won,
                      heated_loss=False, spiraling=False,
                      game_date=None, rng=rng, events=events, ctx={})
    return events


def test_r11_quote_events_carry_result_premise():
    won_events = _stub_interview(True)
    lost_events = _stub_interview(False)
    assert won_events, "expected a quote event on a win"
    assert lost_events, "expected a quote event on a loss"
    for ev in won_events:
        if ev["kind"] == "quote":
            assert ev["result"] == "win"
            assert "heated" in ev
    for ev in lost_events:
        if ev["kind"] == "quote":
            assert ev["result"] == "loss"
            assert "heated" in ev


def test_r11_same_premise_distinct_framings():
    """Identical premise (same question, same reporter name) through the
    three personas must render three distinct stories -- the persona
    distinction lives in the template, not the question bank."""
    outs = {}
    for arch in ("stirrer", "loyalist", "neutral"):
        rng = random.Random(42)
        outs[arch] = me._frame_quote_story(_premise(arch), rng=rng)
    assert len(set(outs.values())) == 3, (
        f"personas rendered indistinguishably: {outs}")
    # ... and through the public _news_line path too.
    news = {a: me._news_line(_premise(a)) for a in outs}
    assert len(set(news.values())) == 3


def test_r11_distinct_across_results_and_outcomes():
    # Deterministic: pin rng.choice to each template in turn, then vary
    # outcome/heated. Theoretical max distinct renders:
    #   stirrer: win 12 (t0/t3/t5 x3 textures; t1/t2/t4 x1)
    #          + loss 12 (t0/t3 x2 heats; t1/t4 x3 textures; t2/t5 x1) = 24
    #   loyalist: win 10 (t2/t5 x3; rest x1)
    #           + loss 11 (t0/t5 x3; t2 x2 heats; t1/t3/t4 x1) = 21
    #   neutral: 3 (no texture/heat slots) = 3
    # Total 48. Anything less means templates are collapsing into each
    # other.
    class _FixedChoice(random.Random):
        def __init__(self, pick):
            super().__init__(0)
            self._pick = pick

        def choice(self, seq):  # noqa: ARG002
            return self._pick

    banks = {"stirrer": me._R11_STIRRER_FRAMES,
             "loyalist": me._R11_LOYALIST_FRAMES,
             "neutral": me._R11_NEUTRAL_FRAMES}
    seen = set()
    for arch, bank in banks.items():
        for result, templates in bank.items():
            for t in templates:
                rng = _FixedChoice(t)
                for outcome in ("great", "bland", "awkward"):
                    for heated in (True, False):
                        seen.add(me._frame_quote_story(
                            _premise(arch, result, outcome, heated),
                            rng=rng))
    assert len(seen) == 48, f"{len(seen)} distinct renders, expected 48"


def test_r11_template_banks_disjoint():
    banks = {
        "stirrer": [t for rs in me._R11_STIRRER_FRAMES.values() for t in rs],
        "loyalist": [t for rs in me._R11_LOYALIST_FRAMES.values() for t in rs],
        "neutral": [t for rs in me._R11_NEUTRAL_FRAMES.values() for t in rs],
    }
    for a in banks:
        assert len(banks[a]) >= 3, f"{a} bank too thin for a blind read"
        assert len(set(banks[a])) == len(banks[a]), f"{a} bank has dupes"
    all_templates = [t for ts in banks.values() for t in ts]
    assert len(set(all_templates)) == len(all_templates), (
        "a template string is shared between persona banks -- a blind read "
        "could match those two personas to the same template")


def test_r11_every_template_reachable():
    fired = {a: set() for a in ("stirrer", "loyalist", "neutral")}
    bank_of = {"stirrer": me._R11_STIRRER_FRAMES,
               "loyalist": me._R11_LOYALIST_FRAMES,
               "neutral": me._R11_NEUTRAL_FRAMES}
    for seed in range(400):
        for arch in fired:
            for result in bank_of[arch]:
                ev = _premise(arch, result=result)
                out = me._frame_quote_story(ev, rng=random.Random(seed))
                heat_phrase = me._R11_HEAT.get(arch, "") if ev["heated"] \
                    else ""
                tex = me._R11_TEXTURE.get(arch, {}).get("bland", "")
                tex = tex.replace("{player}", ev["player"])
                for t in bank_of[arch][result]:
                    probe = t
                    for k, v in (("player", ev["player"]),
                                 ("team", ev["team"]),
                                 ("reporter", ev["reporter"]),
                                 ("question", ev["question"]),
                                 ("quote", ev["quote"])):
                        probe = probe.replace("{%s}" % k, v)
                    probe = probe.replace("{texture}", tex).replace(
                        "{heat}", heat_phrase).strip()
                    if out.startswith(probe[:40]):
                        fired[arch].add(t)
    for arch in fired:
        total = sum(len(v) for v in bank_of[arch].values())
        assert len(fired[arch]) == total, (
            f"{arch}: only {len(fired[arch])}/{total} templates fired")


def test_r11_never_raises_on_junk():
    junks = [{}, {"kind": "quote"}, {"kind": "quote", "archetype": "weird",
                                     "result": "draw", "outcome": "???"},
             {"kind": "quote", "archetype": None, "question": "{brace}",
              "quote": "{also brace}", "player": "{x}"},
             {"kind": "quote", "archetype": "stirrer", "heated": "yes"}]
    for j in junks:
        out = me._frame_quote_story(j, rng=random.Random(1))
        assert isinstance(out, str) and out, f"bad render for {j!r}"
        out2 = me._news_line(dict(j, kind="quote"))
        assert isinstance(out2, str) and out2


def test_r11_premise_content_preserved():
    for arch in ("stirrer", "loyalist", "neutral"):
        out = me._frame_quote_story(_premise(arch), rng=random.Random(3))
        assert Q in out, f"{arch} dropped the question"
        assert QUOTE in out, f"{arch} dropped the quote"
        assert "David Pastrnak" in out
        assert "Boston Bruins" in out


def test_r11_no_false_result_claims():
    for arch in ("stirrer", "loyalist"):
        for seed in range(60):
            w = me._frame_quote_story(_premise(arch, result="win"),
                                      rng=random.Random(seed))
            assert not re.search(r"\bloss\b|\bloses\b|\blost\b", w,
                                 re.IGNORECASE), f"win story claims loss: {w}"
            l = me._frame_quote_story(_premise(arch, result="loss"),
                                      rng=random.Random(seed))
            assert not re.search(r"\bwon\b", l, re.IGNORECASE), (
                f"loss story claims win: {l}")


def test_r11_framing_markers_persona_distinct():
    """Each persona's bank carries exclusive diction -- the stirrer's
    inquest language never appears in loyalist/neutral output and vice
    versa. This is the objective shadow of the blind-read acceptance."""
    stirrer_only = ["turned the screws", "press row smells blood",
                    "felt like an inquest", "getting off easy"]
    loyalist_only = ["room was still buzzing", "took the bullet",
                     "room's together", "didn't duck it"]
    corpus = {a: " ".join(
        me._frame_quote_story(_premise(a, result=r),
                               rng=random.Random(s))
        for r in ("win", "loss") for s in range(30))
        for a in ("stirrer", "loyalist", "neutral")}
    for m in stirrer_only:
        assert m in corpus["stirrer"]
        assert m not in corpus["loyalist"] and m not in corpus["neutral"], m
    for m in loyalist_only:
        assert m in corpus["loyalist"]
        assert m not in corpus["stirrer"] and m not in corpus["neutral"], m


def test_r11_never_raises_on_non_dict():
    # Reviewer C finding 1: the "never raises" contract covers non-dict
    # input too -- the except handler reads ev.get(), so ev is
    # normalized up front. FAILED on the round-1 commit (AttributeError
    # re-raised from the handler itself).
    for bad in (None, "a string", 123, ["kind", "quote"], 4.5):
        out = me._frame_quote_story(bad, rng=random.Random(1))
        assert isinstance(out, str) and out


def test_r11_free_text_braces_not_corrupted():
    # Reviewer C finding 2: slot-shaped text inside free content must
    # survive verbatim -- single-pass substitution over the template
    # only. FAILED on the round-1 commit (sequential .replace() spliced
    # the heat/texture phrases into the question and quote).
    ev = _premise("stirrer", heated=True)
    ev["question"] = "\u201cCoach, is {heat} a factor tonight?\u201d"
    ev["quote"] = "\u201cWe will fix {texture} issues, {player}.\u201d"
    out = me._frame_quote_story(ev, rng=random.Random(1))
    assert "\u201cCoach, is {heat} a factor tonight?\u201d" in out
    assert "\u201cWe will fix {texture} issues, {player}.\u201d" in out


def test_r11_heat_lead_in_grammatical():
    # Reviewer B wart: the heated lead-in must read as a standalone
    # sentence, never ", The ..." mid-sentence. FAILED on round-1.
    for arch in ("stirrer", "loyalist"):
        for seed in range(40):
            out = me._frame_quote_story(
                _premise(arch, result="loss", heated=True),
                rng=random.Random(seed))
            assert ", The " not in out, out
