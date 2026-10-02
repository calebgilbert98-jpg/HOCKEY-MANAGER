# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Screenshots of the new views + filter UI for review (Xvfb).

Pattern note: views must be packed DIRECTLY into the ctk.CTk root --
packing into an intermediate tk.Frame holder renders blank in grabs.
"""
import os
import sys
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa_player_views_filters as q

OUT = os.path.expanduser("~/workspace/uiaudit/shots-20261002")
os.makedirs(OUT, exist_ok=True)


def big_roster():
    import game_classes as g
    import reputation_system as rs
    from game_classes import Contract
    first = ["Auston", "Cale", "Connor", "Leon", "Nathan", "David",
             "Artemi", "Mikko", "Sebastian", "Brayden", "Jake", "Quinn",
             "Adam", "Victor", "Roman", "Miro", "Charlie", "Igor",
             "Andrei", "Juuse"]
    last = ["Matthews", "Makar", "McDavid", "Draisaitl", "MacKinnon",
            "Pastrnak", "Panarin", "Rantanen", "Aho", "Point", "Guentzel",
            "Hughes", "Fox", "Hedman", "Josi", "Heiskanen", "McAvoy",
            "Shesterkin", "Vasilevskiy", "Saros"]
    pos = [g.PlayerPosition.CENTER, g.PlayerPosition.RIGHT_DEFENSE,
           g.PlayerPosition.CENTER, g.PlayerPosition.CENTER,
           g.PlayerPosition.CENTER, g.PlayerPosition.RIGHT_WING,
           g.PlayerPosition.LEFT_WING, g.PlayerPosition.RIGHT_WING,
           g.PlayerPosition.CENTER, g.PlayerPosition.CENTER,
           g.PlayerPosition.LEFT_WING, g.PlayerPosition.LEFT_DEFENSE,
           g.PlayerPosition.RIGHT_DEFENSE, g.PlayerPosition.LEFT_DEFENSE,
           g.PlayerPosition.LEFT_DEFENSE, g.PlayerPosition.LEFT_DEFENSE,
           g.PlayerPosition.RIGHT_DEFENSE, g.PlayerPosition.GOALIE,
           g.PlayerPosition.GOALIE, g.PlayerPosition.GOALIE]
    players = []
    for i in range(20):
        p = g.Player(first_name=first[i], last_name=last[i],
                     age=22 + (i * 7) % 15, primary_position=pos[i],
                     jersey_number=i + 1)
        rs.ensure_reputation_fields(p)
        p.skating = 78 + (i * 5) % 20
        p.shooting = 75 + (i * 7) % 22
        p.strength = 70 + (i * 3) % 25
        p.checking = 65 + (i * 4) % 25
        p.goaltending = 88 + (i % 5) if pos[i] == g.PlayerPosition.GOALIE else 30
        p.contract = Contract()
        p.contract.salary = 3_000_000 + (i * 900_000) % 9_000_000
        p.contract.years_remaining = 1 + (i % 6)
        st = p.stats
        st.games_played = 82 - (i % 8)
        if pos[i] == g.PlayerPosition.GOALIE:
            st.wins = 25 + (i % 12)
            st.losses = 12 + (i % 8)
            st.goals_against_avg = 2.3 + (i % 10) * 0.08
            st.save_percentage = 0.908 + (i % 10) * 0.001
            st.shutouts = 2 + (i % 4)
        else:
            st.goals = 15 + (i * 3) % 35
            st.assists = 25 + (i * 5) % 45
            st.shots = 120 + (i * 13) % 160
            st.hits = 30 + (i * 7) % 90
            st.blocked_shots = 20 + (i * 5) % 60
            st.takeaways = 20 + (i * 3) % 40
            st.penalties_in_minutes = 10 + (i * 3) % 40
        p.plus_minus = 15 - (i % 25)
        p.morale = 6 + (i % 4)
        p.current_point_streak = i % 6
        p.team_name = "Test Club"
        players.append(p)
    return players


def settle(root, secs=8):
    root.deiconify()
    root.lift()
    end = time.time() + secs
    while time.time() < end:
        root.update_idletasks()
        root.update()
        time.sleep(0.1)


def shoot(name):
    from PIL import ImageGrab
    img = ImageGrab.grab()
    path = os.path.join(OUT, name)
    img.save(path)
    print("saved", path)


def main():
    import customtkinter as ctk
    root = ctk.CTk()
    root.geometry("1600x900+0+0")
    players = big_roster()
    app = q._stub_app(players)

    with patch("tkinter.messagebox.askyesno", return_value=True), \
         patch("tkinter.messagebox.showinfo", return_value=None), \
         patch("tkinter.messagebox.showerror", return_value=None), \
         patch("tkinter.messagebox.showwarning", return_value=None):
        # ---- 1. Roster: Offense view + attribute filter chip ----
        from windows import RosterView
        rv = RosterView(root, app=app)
        rv.pack(fill="both", expand=True)
        settle(root)
        rv._set_roster_view("nhl", "Offense")
        from player_filters import AttrThreshold
        fb = rv._roster_filterbars["nhl"]
        th = AttrThreshold(key="attr:shooting", label="Shooting", min=85)
        fb._filter.thresholds.append(th)
        fb._make_chip(th)
        fb._changed()
        settle(root, 4)
        shoot("roster-offense-view-filter.png")

        # ---- 2. Roster: Composites view ----
        fb.clear()
        rv._set_roster_view("nhl", "Composites")
        settle(root, 4)
        shoot("roster-composites-view.png")
        rv.destroy()

        # ---- 3. Scouting: prospect pool, Physical view ----
        from windows import ScoutingView
        sv = ScoutingView(root, app=app)
        sv.pack(fill="both", expand=True)
        settle(root)
        sv._set_scout_view("Physical")
        settle(root, 4)
        shoot("scouting-physical-view.png")
        sv.destroy()

    root.destroy()


if __name__ == "__main__":
    main()
