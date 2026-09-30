"""Screenshot: unified Targets tab (one surface, no duplicate entries).

Usage: xvfb-run -a -s "-screen 0 1680x1050x24" python3 shot_unified_targets.py
Writes ~/workspace/puck-dynasty-ui-shots/trade_targets_unified.png
"""
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, ".")

import qa_screens as qs
import qa_trade_market as qtm
import trade_market as tm
from ctk_theme import init_ctk_theme


def main():
    qtm.clear_shortlist_store()
    app = qs.build_app()

    # Swap in the richer QA league so the tab has real rows to show.
    league = qtm.build_league()
    user_team = league.teams[2]  # Buyer0
    app.league = league
    app.user_team = user_team
    app.game_manager.league = league
    app.game_manager.user_team = user_team

    # Seed the ONE unified surface: user targets + scout suggestions.
    sellers = league.teams[0]
    p_user1 = sellers.roster[1]
    p_user2 = league.teams[1].roster[2]
    p_sug1 = league.teams[4].roster[0]
    p_sug2 = league.teams[5].roster[1]
    tm.add_target(p_user1, source="user", note="need a middle-six center")
    tm.add_target(p_user2, source="user", note="rental winger?")
    tm.add_target(p_sug1, source="Elite Eye",
                  note="(High confidence): underlying numbers stand out")
    tm.add_target(p_sug2, source="Poor Guess",
                  note="(Low confidence): worth a look")

    init_ctk_theme()
    root = tk.Tk()
    root.geometry("1600x900+0+0")
    root.title("Scouting")
    try:
        from modern_theme_bridge import apply_modern_theme
        apply_modern_theme(root)
    except Exception:
        pass

    from modern_scouting_window import ModernScoutingView
    view = ModernScoutingView(root, app=app)
    view.pack(fill="both", expand=True)
    root.update()

    # Select the Targets tab.
    nb = view.notebook
    for i in range(len(nb.tabs())):
        if nb.tab(i, "text") == "Targets":
            nb.select(i)
            break
    for _ in range(3):
        root.update()
        time.sleep(0.5)
    view._populate_targets()
    root.update()
    time.sleep(0.5)

    import mss
    from PIL import Image
    with mss.MSS() as sct:
        raw = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    out = os.path.expanduser("~/workspace/puck-dynasty-ui-shots/trade_targets_unified.png")
    img.crop((x, y, x + w, y + h)).save(out)
    print("saved", out)

    qtm.clear_shortlist_store()
    root.destroy()


if __name__ == "__main__":
    main()
