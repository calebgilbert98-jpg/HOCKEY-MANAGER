"""QA: player card, comparison, and universal right-click bindings."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import game_classes as g
from game_classes import PlayerPosition

passed, failed = 0, []
def check(name, fn):
    global passed
    try:
        fn(); passed += 1; print(f"  PASS {name}")
    except Exception as e:
        import traceback; traceback.print_exc(); failed.append(name); print(f"  FAIL {name}: {e}")

p1 = g.Player("Test", "Player", 25, PlayerPosition.CENTER, 75)
p2 = g.Player("Other", "Guy", 27, PlayerPosition.LEFT_WING, 72)

root = tk.Tk(); root.geometry("1600x900")
root.BG_COLOR="#1E1E1E"; root.CONTENT_BG="#2D2D2D"; root.HEADER_COLOR="#FFFFFF"; root.TEXT_COLOR="#FFFFFF"
root.user_team = type('T', (), {'roster': [p1, p2], 'ahl_roster': [], 'prospects': []})()

def t_card_modern():
    from modern_profile import PlayerProfile
    w = PlayerProfile(root, p1); root.update(); w.destroy()
def t_compare():
    from player_context_menu import PlayerContextMenu
    mgr = PlayerContextMenu(root); mgr.parent = root
    mgr._compare_players(p1); root.update()
    for w in root.winfo_children():
        try: w.destroy()
        except Exception: pass
def t_compare_legacy_entry():
    # Legacy _create_comparison_window must not crash (delegates to enhanced)
    from player_context_menu import PlayerContextMenu
    mgr = PlayerContextMenu(root); mgr.parent = root
    mgr._create_comparison_window(p1); root.update()
    for w in root.winfo_children():
        try: w.destroy()
        except Exception: pass
def t_bind_helper():
    from player_context_menu import bind_player_context
    lbl = tk.Label(root, text=p1.full_name); lbl.pack()
    mgr = bind_player_context(lbl, p1, root)
    assert mgr is not None
    lbl.destroy()
def t_boxscore_grid_players_param():
    import inspect
    from game_box_score import GameBoxScoreView
    sig = inspect.signature(GameBoxScoreView._grid_table)
    assert 'players' in sig.parameters, "players param missing"

print("player card / comparison / right-click QA:")
check("modern_profile card constructs", t_card_modern)
check("enhanced comparison constructs", t_compare)
check("legacy comparison entry delegates", t_compare_legacy_entry)
check("bind_player_context helper works", t_bind_helper)
check("box score grid accepts players", t_boxscore_grid_players_param)
root.destroy()
print(f"\n{passed} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
