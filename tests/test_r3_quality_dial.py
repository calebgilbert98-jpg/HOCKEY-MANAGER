"""R3 anti-rot tests: the quality dial must scale every overall input.

_R3_QUALITY_ATTRS in database_generator.py mirrors the attributes read by
Player.overall_rating() in game_classes.py. If overall_rating gains an
attribute and the generator doesn't scale it, the dial silently caps out
again (the R3 root cause). These tests fail loudly on any drift.

Also covers: max-quality rolls reach 93+ organically, draft class doesn't
inflate, generated elites carry truthful grades (no development melt), and
the overall weight sums still equal 1.0 (spec: keep game_classes.py:1053
true).
"""
import ast
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database_generator as dg
from game_classes import Player, PlayerPosition


def _overall_attrs_by_branch():
    """Parse overall_rating source; return {branch: {attrs}} via AST.

    Walks only each branch's own `body` (not `orelse`, where the elif
    chain nests) and does not descend into nested Ifs, so each branch
    reports exactly the attributes ITS formula reads.
    """
    import game_classes
    src = open(game_classes.__file__).read()
    tree = ast.parse(src)
    result = {}

    def _branch_attrs(if_node):
        attrs = set()

        def _walk_no_if(n):
            for ch in ast.iter_child_nodes(n):
                if isinstance(ch, ast.If):
                    continue  # nested branch -- not this formula
                if (isinstance(ch, ast.Attribute)
                        and isinstance(ch.value, ast.Name)
                        and ch.value.id == "self"):
                    attrs.add(ch.attr)
                _walk_no_if(ch)

        for stmt in if_node.body:
            _walk_no_if(stmt)
        return attrs

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "overall_rating":
            # The top-level if/elif/else chain: each elif is an If nested
            # in the previous If's orelse. Walk the chain explicitly.
            chain = [n for n in ast.walk(node)
                     if isinstance(n, ast.If) and any(
                         isinstance(t, ast.Compare) for t in ast.walk(n.test))]
            # Simpler robust approach: find the outermost If and follow
            # orelse links.
            outer = None
            for n in ast.walk(node):
                if isinstance(n, ast.If):
                    # Heuristic: the dispatch If tests primary_position.
                    if "primary_position" in ast.dump(n.test):
                        # Take the shallowest such If.
                        outer = n
                        break
            cur, is_first = outer, True
            while isinstance(cur, ast.If):
                test_src = ast.dump(cur.test)
                if "GOALIE" in test_src:
                    branch = "goalie"
                elif "CENTER" in test_src:
                    branch = "center"
                elif "WING" in test_src:
                    branch = "wing"
                elif "DEFENSE" in test_src:
                    branch = "defense"
                else:
                    branch = "fallback" if not is_first else "unknown"
                if branch != "unknown":
                    result.setdefault(branch, set()).update(
                        _branch_attrs(cur))
                # elif -> single If in orelse; else -> bare body (fallback).
                nxt = None
                if (len(cur.orelse) == 1
                        and isinstance(cur.orelse[0], ast.If)):
                    nxt = cur.orelse[0]
                elif cur.orelse:
                    fb_attrs = set()

                    def _walk_fb(n):
                        for ch in ast.iter_child_nodes(n):
                            if isinstance(ch, ast.If):
                                continue
                            if (isinstance(ch, ast.Attribute)
                                    and isinstance(ch.value, ast.Name)
                                    and ch.value.id == "self"):
                                fb_attrs.add(ch.attr)
                            _walk_fb(ch)

                    for stmt in cur.orelse:
                        _walk_fb(stmt)
                    result.setdefault("fallback", set()).update(fb_attrs)
                cur, is_first = nxt, False
            break
    return result


def test_overall_inputs_all_scaled():
    """Every attribute overall_rating reads must be quality-scaled."""
    branches = _overall_attrs_by_branch()
    assert branches, "could not parse overall_rating branches"
    # 'primary_position' is read for dispatch, not a rating input.
    ignore = {"primary_position"}
    for branch, attrs in branches.items():
        attrs = attrs - ignore
        group = "goalie" if branch == "goalie" else "skater"
        scaled = set(dg._R3_QUALITY_ATTRS[group]) | set(
            dg._R3_QUALITY_ATTRS_FLAVOR)
        missing = attrs - scaled
        assert not missing, (
            f"R3 dial drift: overall_rating '{branch}' branch reads "
            f"{sorted(missing)} which the quality dial does not scale")


def test_overall_weights_sum_to_one():
    """Spec: game_classes.py overall weights must sum to 1.0 (all branches)."""
    import re
    import game_classes
    src = open(game_classes.__file__).read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "overall_rating":
            # Find each `rating = (...)` BinOp assignment and sum the
            # numeric coefficients.
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == "rating"
                        for t in sub.targets):
                    coefs = []

                    def _collect(n):
                        if isinstance(n, ast.BinOp) and isinstance(
                                n.op, ast.Mult):
                            # self.attr * coef  (either order)
                            for side in (n.left, n.right):
                                if isinstance(side, ast.Constant) and \
                                        isinstance(side.value, float):
                                    coefs.append(side.value)
                        for ch in ast.iter_child_nodes(n):
                            _collect(ch)

                    _collect(sub.value)
                    if coefs:
                        total = sum(coefs)
                        assert abs(total - 1.0) < 1e-9, (
                            f"overall weights sum to {total}, not 1.0")
            break


def test_max_quality_rolls_reach_93():
    """R3 acceptance (3): the dial produces 90+ organically."""
    random.seed(20261013)
    cfg = dg.DATABASE_CONFIGURATIONS["Small"]
    gen = dg.DatabaseGenerator(cfg)
    rolls = [gen._create_enhanced_player(27, PlayerPosition.CENTER, 1.7)
             .overall_rating() for _ in range(40)]
    assert max(rolls) >= 93, f"max-quality rolls topped out at {max(rolls)}"
    assert sum(1 for r in rolls if r >= 90) >= 30, (
        "max-quality dice should mostly land 90+")


def test_draft_class_not_inflated():
    """R3 acceptance (2): the age-18 draft class must not inflate."""
    random.seed(20261013)
    cfg = dg.DATABASE_CONFIGURATIONS["Small"]
    gen = dg.DatabaseGenerator(cfg)
    prospects = gen._generate_prospects_pool(336)
    age18 = [p for p in prospects if p.age == 18]
    assert age18, "no age-18 prospects generated"
    m = max(p.overall_rating() for p in age18)
    assert m <= 70, f"age-18 draft class inflated to {m}"


def test_generated_elite_has_truthful_grade():
    """A generated 95+ must carry a grade whose cap covers him (no melt)."""
    random.seed(7)
    cfg = dg.DATABASE_CONFIGURATIONS["Small"]
    gen = dg.DatabaseGenerator(cfg)
    elites = []
    for _ in range(60):
        p = gen._create_enhanced_player(27, PlayerPosition.CENTER, 1.7)
        if p.overall_rating() >= 95:
            elites.append(p)
    assert elites, "no 95+ generated at max quality"
    for p in elites:
        assert p._potential_cap() >= p.overall_rating(), (
            f"95+ player with grade {p.potential_grade} "
            f"(cap {p._potential_cap()}) would melt")


def test_no_development_melt_for_elite():
    """A 96 OVR veteran must not grind down over 12 development months."""
    random.seed(11)
    cfg = dg.DATABASE_CONFIGURATIONS["Small"]
    gen = dg.DatabaseGenerator(cfg)
    from player_development_system import PlayerDevelopmentEngine
    eng = PlayerDevelopmentEngine()
    made = None
    for _ in range(200):
        p = gen._create_enhanced_player(28, PlayerPosition.CENTER, 1.7)
        if p.overall_rating() >= 96:
            made = p
            break
    assert made is not None, "could not roll a 96+ veteran"
    o0 = made.overall_rating()
    for _ in range(12):
        eng.process_monthly_development(made)
    assert made.overall_rating() >= o0 - 1, (
        f"elite melted {o0} -> {made.overall_rating()} in 12 months")
