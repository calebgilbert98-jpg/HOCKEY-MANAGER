"""Behavioral QA for the full-screen navigation manager in main.py.

Calls the real HockeyManagerGUI.show_screen / _teardown_screen /
show_dashboard methods unbound against a lightweight harness with a real
Tk container. Verifies: dashboard hide/show, screen replacement, navbar,
open_windows registration/removal, same-screen reuse, fresh=True rebuild,
and that the menu bar row is never disturbed.
"""
import sys
import tkinter as tk
from types import SimpleNamespace

sys.path.insert(0, ".")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  FAIL") + f" {name}" +
          (f" -- {detail}" if detail and not cond else ""))


class FakeView(tk.Frame):
    def __init__(self, parent, app=None, tag=""):
        super().__init__(parent)
        self.app = app
        self.tag = tag
        self._close_screen = None
        tk.Label(self, text=f"view:{tag}").pack()

    def close_view(self):
        fn = getattr(self, "_close_screen", None)
        if callable(fn):
            fn()
        else:
            self.destroy()


def make_harness():
    import main as m
    root = tk.Tk()
    root.geometry("1600x900")
    h = SimpleNamespace()
    h.main_container = tk.Frame(root)
    h.main_container.pack(fill="both", expand=True)
    h.main_container.grid_rowconfigure(0, weight=0)   # menu bar row
    h.main_container.grid_rowconfigure(1, weight=1)   # content row
    h.main_container.grid_columnconfigure(0, weight=1)
    menubar = tk.Frame(h.main_container, height=28)
    menubar.grid(row=0, column=0, sticky="ew")
    dash = tk.Frame(h.main_container)
    dash.grid(row=1, column=0, sticky="nsew")
    tk.Label(dash, text="DASHBOARD").pack()
    h._dashboard_frame = dash
    h._dashboard_grid = {"row": 1, "column": 0, "sticky": "nsew"}
    h._current_screen = None
    h.open_windows = {}
    h.update_dashboard_data = lambda: setattr(h, "dashboard_refreshed", True)
    h.show_screen = m.HockeyManagerGUI.show_screen.__get__(h)
    h._teardown_screen = m.HockeyManagerGUI._teardown_screen.__get__(h)
    h.show_dashboard = m.HockeyManagerGUI.show_dashboard.__get__(h)
    return root, h, menubar


def cur_view(h):
    return h._current_screen["view"] if h._current_screen else None


def cur_holder(h):
    return h._current_screen["holder"] if h._current_screen else None


def find_back_button(holder):
    for c in holder.winfo_children():
        for sub in c.winfo_children():
            try:
                if "Dashboard" in str(sub.cget("text")):
                    return sub
            except Exception:  # noqa: BLE001
                pass
    return None


def main():
    root, h, menubar = make_harness()

    # 1. dashboard -> screen
    h.show_screen("roster", "Roster", FakeView, tag="roster")
    root.update()
    holder = cur_holder(h)
    check("screen holder embeds in row 1", holder.grid_info()["row"] == 1)
    check("dashboard hidden", h._dashboard_frame.grid_info() == {})
    check("menu bar row intact",
          menubar.winfo_exists() and menubar.grid_info()["row"] == 0)
    check("view registered in open_windows",
          h.open_windows.get("roster") is cur_view(h))
    check("close callback wired to show_dashboard",
          cur_view(h)._close_screen == h.show_dashboard)
    back_btn = find_back_button(holder)
    check("navbar has back button + title", back_btn is not None)

    first_view, first_holder = cur_view(h), holder

    # 2. screen -> another screen (replacement, old destroyed)
    h.show_screen("draft", "Draft", FakeView, tag="draft")
    root.update()
    check("old holder destroyed", not first_holder.winfo_exists())
    check("old registration removed", "roster" not in h.open_windows)
    check("new screen registered",
          h.open_windows.get("draft") is cur_view(h))

    # 3. same screen id reuses the view (no rebuild)
    second_view = cur_view(h)
    h.show_screen("draft", "Draft", FakeView, tag="draft")
    root.update()
    check("same-screen reuse", cur_view(h) is second_view)

    # 4. fresh=True forces rebuild
    h.show_screen("draft", "Draft", FakeView, tag="draft2", fresh=True)
    root.update()
    check("fresh rebuild replaces view",
          cur_view(h) is not second_view
          and not second_view.winfo_exists()
          and cur_view(h).tag == "draft2")

    # 5. back button -> dashboard restored + refreshed
    h.dashboard_refreshed = False
    back_btn = find_back_button(cur_holder(h))
    if back_btn is not None:
        back_btn.invoke()
        root.update()
    check("dashboard restored", h._dashboard_frame.grid_info() != {})
    check("screen torn down", h._current_screen is None)
    check("registration cleared", "draft" not in h.open_windows)
    check("dashboard refreshed on return",
          getattr(h, "dashboard_refreshed", False))

    # 6. view's own close_view() returns to dashboard
    h.show_screen("news", "News", FakeView, tag="news")
    root.update()
    cur_view(h).close_view()
    root.update()
    check("close_view returns to dashboard",
          h._dashboard_frame.grid_info() != {} and h._current_screen is None)

    # 7. teardown with nothing showing is a safe no-op
    try:
        h._teardown_screen()
        h.show_dashboard()
        root.update()
        noop_ok = True
    except Exception:  # noqa: BLE001
        noop_ok = False
    check("empty teardown/show_dashboard safe", noop_ok)

    root.destroy()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
