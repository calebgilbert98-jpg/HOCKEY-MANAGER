"""Scouting profile manager dialog for Puck Dynasty.

Browse the pre-built archetype profiles, and create / edit / delete your own
custom profiles (attribute minimums + position scope). Pure Tkinter UI over
the scouting_profiles logic module.
"""

import tkinter as tk
from tkinter import ttk
from popup_system import messagebox, InGamePopup
from modern_widgets import RoundedButton
import customtkinter as ctk
from ctk_theme import BG, CARD

from scouting_profiles import (
    ALL_ATTRIBUTES, SKATER_ATTRIBUTES, GOALIE_ATTRIBUTES,
    ScoutingProfile, list_profiles, get_profile,
    save_custom_profile, delete_custom_profile,
)

POSITION_GROUPS = [
    ("Any position", []),
    ("Forwards", ["C", "LW", "RW"]),
    ("Defense", ["LD", "RD"]),
    ("Goalies", ["G"]),
]



def _focus_card(view, width=620):
    """Focus-card layout: full-screen view with content in a centered card."""
    outer = ctk.CTkFrame(view, fg_color=BG)
    outer.pack(fill="both", expand=True)
    card = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=12, width=width)
    card.pack(expand=True, padx=24, pady=24)
    return card


class ScoutingProfileView(ctk.CTkFrame):
    """Browse, create, edit and delete scouting profiles (focus-card view)."""

    def __init__(self, parent, app=None, on_apply=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ScoutingProfileDialog wrapper
        self.configure(fg_color=BG)
        self._on_apply = on_apply  # callback(profile_name) after Apply/close

        bg = getattr(self.app, "CONTENT_BG", "#1e2430")
        fg = getattr(self.app, "TEXT_COLOR", "#ffffff")
        self._bg, self._fg = bg, fg

        card = _focus_card(self, width=620)
        main = tk.Frame(card, bg=bg)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # -- left: profile list -------------------------------------------
        left = tk.LabelFrame(main, text="Profiles", bg=bg, fg=fg,
                             font=("Segoe UI", 10, "bold"))
        left.pack(side="left", fill="y", padx=(0, 10))
        self._list = tk.Listbox(left, width=24, height=22, bg="#141a24", fg=fg,
                                selectbackground="#2f6fed",
                                font=("Segoe UI", 10))
        self._list.pack(fill="y", expand=True, padx=6, pady=6)
        self._list.bind("<<ListboxSelect>>", self._on_select)

        # -- right: details -------------------------------------------------
        right = tk.Frame(main, bg=bg)
        right.pack(side="left", fill="both", expand=True)

        self._name_var = tk.StringVar()
        tk.Label(right, textvariable=self._name_var, bg=bg, fg=fg,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self._desc_var = tk.StringVar()
        tk.Label(right, textvariable=self._desc_var, bg=bg, fg="#9aa4b5",
                 font=("Segoe UI", 10), wraplength=380,
                 justify="left").pack(anchor="w", pady=(0, 8))

        cols = ("Attribute", "Minimum")
        self._attrs = ttk.Treeview(right, columns=cols, show="headings",
                                   height=10)
        self._attrs.heading("Attribute", text="Attribute")
        self._attrs.heading("Minimum", text="Minimum")
        self._attrs.column("Attribute", width=200)
        self._attrs.column("Minimum", width=80, anchor="center")
        self._attrs.pack(fill="x", pady=(0, 8))

        self._pos_var = tk.StringVar()
        tk.Label(right, textvariable=self._pos_var, bg=bg, fg="#9aa4b5",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

        # -- buttons --------------------------------------------------------
        btn = tk.Frame(right, bg=bg)
        btn.pack(fill="x", pady=(4, 0))
        self._new_btn = RoundedButton(btn, text="New Profile", command=self._new,
                                      bg="#2f6fed", fg="white",
                                      font=("Segoe UI", 10, "bold"),
                                      radius=9, padx=14, pady=7)
        self._new_btn.pack(side="left", padx=(0, 6))
        self._edit_btn = RoundedButton(btn, text="Edit", command=self._edit,
                                       bg="#1e1e24", fg=fg,
                                       font=("Segoe UI", 10),
                                       radius=9, padx=14, pady=7)
        self._edit_btn.pack(side="left", padx=(0, 6))
        self._del_btn = RoundedButton(btn, text="Delete", command=self._delete,
                                       bg="#1e1e24", fg=fg,
                                       font=("Segoe UI", 10),
                                       radius=9, padx=14, pady=7)
        self._del_btn.pack(side="left", padx=(0, 6))
        self._apply_btn = RoundedButton(btn, text="Apply & Close",
                                        command=self._apply_close,
                                        bg="#1f9d55", fg="white",
                                        font=("Segoe UI", 10, "bold"),
                                        radius=9, padx=16, pady=8)
        self._apply_btn.pack(side="right")

        self._refresh_list()


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass


    def _ask_confirm(self, text, on_yes, on_no=None):
        """Show an in-view Yes/No panel (replaces messagebox.askyesno)."""
        old = getattr(self, "_confirm_panel", None)
        if old is not None:
            try: old.destroy()
            except Exception: pass
        import customtkinter as ctk
        panel = ctk.CTkFrame(self, fg_color="#2a2a3a", corner_radius=8)
        panel.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(panel, text=text, wraplength=520).pack(padx=12, pady=(10, 6))
        btns = ctk.CTkFrame(panel, fg_color="transparent")
        btns.pack(pady=(0, 10))
        def _yes():
            try: panel.destroy()
            except Exception: pass
            self._confirm_panel = None
            on_yes()
        def _no():
            try: panel.destroy()
            except Exception: pass
            self._confirm_panel = None
            if on_no: on_no()
        ctk.CTkButton(btns, text="Yes", command=_yes, width=90).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="No", command=_no, width=90).pack(side="left", padx=6)
        self._confirm_panel = panel

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    # -- list --------------------------------------------------------------
    def _refresh_list(self, select=None):
        self._profiles = list_profiles()
        self._list.delete(0, "end")
        sel_idx = 0
        for i, p in enumerate(self._profiles):
            tag = "★ " if p.builtin else "✎ "
            self._list.insert("end", tag + p.name)
            if select and p.name == select:
                sel_idx = i
        if self._profiles:
            self._list.selection_set(sel_idx)
            self._on_select()
        else:
            self._clear_details()

    def _selected(self):
        sel = self._list.curselection()
        return self._profiles[sel[0]] if sel else None

    def _on_select(self, event=None):
        p = self._selected()
        if not p:
            self._clear_details()
            return
        self._name_var.set(("★ " if p.builtin else "✎ ") + p.name)
        self._desc_var.set(p.description or "—")
        for item in self._attrs.get_children():
            self._attrs.delete(item)
        for key, minimum in sorted(p.attributes.items(),
                                   key=lambda kv: ALL_ATTRIBUTES.get(kv[0], kv[0])):
            self._attrs.insert("", "end", values=(
                ALL_ATTRIBUTES.get(key, key), minimum))
        pos = ", ".join(p.positions) if p.positions else "Any position"
        self._pos_var.set(f"Positions: {pos}")
        can_edit = not p.builtin
        self._edit_btn.config(state="normal" if can_edit else "disabled")
        self._del_btn.config(state="normal" if can_edit else "disabled")

    def _clear_details(self):
        self._name_var.set("")
        self._desc_var.set("")
        for item in self._attrs.get_children():
            self._attrs.delete(item)
        self._pos_var.set("")

    # -- actions -------------------------------------------------------------
    def _new(self):
        self.app.show_screen('scouting_profile_editor', 'New Scouting Profile',
                             ProfileEditorView, bg=self._bg, fg=self._fg,
                             on_save=self._back_to_browser)

    def _edit(self):
        p = self._selected()
        if p and not p.builtin:
            self.app.show_screen('scouting_profile_editor', 'Edit Scouting Profile',
                                 ProfileEditorView, bg=self._bg, fg=self._fg,
                                 profile=p, on_save=self._back_to_browser)

    def _back_to_browser(self, name=None):
        """Return to the profile browser (fresh) after the editor closes."""
        view = self.app.show_screen('scouting_profiles', 'Scouting Profiles',
                                    ScoutingProfileView, fresh=True,
                                    on_apply=self._on_apply)
        if name:
            view._refresh_list(select=name)

    def _delete(self):
        p = self._selected()
        if not p or p.builtin:
            return
        self._ask_confirm(f"Delete your custom profile '{p.name}'?",
                          lambda: (delete_custom_profile(p.name), self._refresh_list()))

    def _apply_close(self):
        p = self._selected()
        if self._on_apply and p:
            self._on_apply(p.name)
        self.close_view()


class ScoutingProfileDialog(InGamePopup):
    """Popup wrapper around ScoutingProfileView (backward compatibility)."""

    def __init__(self, parent, on_apply=None):
        super().__init__(parent, modal=True)
        self.title("Scouting Profiles")
        app = (getattr(parent, 'app', None)
               or getattr(parent, 'parent', None) or parent)
        self._view = ScoutingProfileView(self, app=app, on_apply=on_apply)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)


class ProfileEditorView(ctk.CTkFrame):
    """Create or edit a single custom scouting profile (focus-card view)."""

    def __init__(self, parent, app=None, bg=None, fg=None,
                 profile=None, on_save=None):
        ctk.CTkFrame.__init__(self, parent)
        self.app = app if app is not None else parent
        self._close_screen = None  # set by show_screen() or the ProfileEditorDialog wrapper
        self.configure(fg_color=BG)
        self._on_save = on_save
        self._editing_name = profile.name if profile else None
        bg = bg or getattr(self.app, "CONTENT_BG", "#1e2430")
        fg = fg or getattr(self.app, "TEXT_COLOR", "#ffffff")
        self._bg, self._fg = bg, fg

        card = _focus_card(self, width=600)
        main = tk.Frame(card, bg=bg)
        main.pack(fill="both", expand=True, padx=14, pady=14)

        # name + description
        tk.Label(main, text="Profile name:", bg=bg, fg=fg,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._name = tk.StringVar(value=profile.name if profile else "")
        tk.Entry(main, textvariable=self._name, width=40,
                 font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 8))

        tk.Label(main, text="Description:", bg=bg, fg=fg,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._desc = tk.StringVar(
            value=profile.description if profile else "")
        tk.Entry(main, textvariable=self._desc, width=60,
                 font=("Segoe UI", 10)).pack(anchor="w", fill="x",
                                              pady=(2, 10))

        # position scope
        tk.Label(main, text="Position scope:", bg=bg, fg=fg,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._pos_choice = tk.StringVar()
        pos_frame = tk.Frame(main, bg=bg)
        pos_frame.pack(anchor="w", pady=(2, 10))
        current = profile.positions if profile else []
        for label, codes in POSITION_GROUPS:
            sel = (codes == current)
            if sel:
                self._pos_choice.set(label)
            tk.Radiobutton(pos_frame, text=label, variable=self._pos_choice,
                           value=label, bg=bg, fg=fg,
                           selectcolor="#141a24",
                           activebackground=bg).pack(side="left", padx=(0, 12))
        if not self._pos_choice.get():
            self._pos_choice.set("Any position")

        # attribute rows
        tk.Label(main, text="Attribute minimums:", bg=bg, fg=fg,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._rows_frame = tk.Frame(main, bg=bg)
        self._rows_frame.pack(fill="both", expand=True, pady=(4, 8))
        self._rows = []  # (attr_var, min_var, row_frame)

        add_btn = RoundedButton(main, text="+ Add Attribute",
                                command=self._add_row, bg="#1e1e24", fg=fg,
                                font=("Segoe UI", 10),
                                radius=9, padx=14, pady=7)
        add_btn.pack(anchor="w", pady=(0, 10))

        if profile:
            for key, minimum in profile.attributes.items():
                self._add_row(key, minimum)
        else:
            # starter rows matching the user's example: toughness/strength/aggressiveness
            self._add_row("toughness", 38)
            self._add_row("strength", 38)
            self._add_row("aggressiveness", 38)

        # save / cancel
        btn = tk.Frame(main, bg=bg)
        btn.pack(fill="x")
        RoundedButton(btn, text="Save Profile", command=self._save,
                      bg="#2f6fed", fg="white",
                      font=("Segoe UI", 10, "bold"),
                      radius=9, padx=14, pady=7).pack(side="left",
                                                     padx=(0, 8))
        RoundedButton(btn, text="Cancel", command=lambda: self._finish(),
                      bg="#1e1e24", fg=fg, font=("Segoe UI", 10),
                      radius=9, padx=14, pady=7).pack(side="left")


    def _show_banner(self, text, kind="info"):
        """Show an in-view message banner (replaces messagebox popups)."""
        colors = {"info": ("#1a3a5c", "#4a9eff"), "error": ("#5c1a1a", "#ff6b6b"),
                  "warn": ("#5c4a1a", "#ffcc00"), "ok": ("#1a5c2a", "#51cf66")}
        bg, fg = colors.get(kind, colors["info"])
        banner = getattr(self, "_banner", None)
        if banner is None:
            try:
                import customtkinter as ctk
                banner = ctk.CTkLabel(self, text="", fg_color=bg, text_color=fg,
                                      corner_radius=6)
                banner.pack(fill="x", padx=12, pady=(8, 0))
                try:
                    banner.lower()
                except Exception:
                    pass
                self._banner = banner
            except Exception:
                return
        banner.configure(text=text, fg_color=bg, text_color=fg)
        # auto-clear after 6s
        try:
            after = getattr(self, "_banner_after", None)
            if after:
                self.after_cancel(after)
            self._banner_after = self.after(6000, lambda: banner.configure(text=""))
        except Exception:
            pass

    def close_view(self):
        """Close this screen (dashboard in screen mode, card in popup mode)."""
        fn = getattr(self, '_close_screen', None)
        if callable(fn):
            fn()
        else:
            self.destroy()

    def _finish(self, name=None):
        """Editor complete: run the on_save callback, else close the view."""
        cb = self._on_save
        if callable(cb):
            try:
                cb(name)
            except Exception:
                pass
        else:
            self.close_view()

    def _attr_options(self):
        return ([f"{label}" for _, label in SKATER_ATTRIBUTES] +
                [f"{label} (G)" for _, label in GOALIE_ATTRIBUTES])

    def _label_to_key(self, label):
        label = label.replace(" (G)", "")
        for key, name in ALL_ATTRIBUTES.items():
            if name == label:
                return key
        return None

    def _key_to_label(self, key, goalie=False):
        name = ALL_ATTRIBUTES.get(key, key)
        if goalie and key in dict(GOALIE_ATTRIBUTES):
            return name + " (G)"
        return name

    def _add_row(self, key=None, minimum=38):
        row = tk.Frame(self._rows_frame, bg=self._bg)
        row.pack(fill="x", pady=2)
        attr_var = tk.StringVar(
            value=self._key_to_label(key) if key else "Strength")
        combo = ttk.Combobox(row, textvariable=attr_var, width=24,
                             values=self._attr_options(), state="readonly")
        combo.pack(side="left", padx=(0, 8))
        tk.Label(row, text="min:", bg=self._bg, fg=self._fg).pack(
            side="left")
        min_var = tk.StringVar(value=str(minimum))
        spin = tk.Spinbox(row, from_=1, to=99, width=5,
                          textvariable=min_var)
        spin.pack(side="left", padx=(4, 8))
        tk.Button(row, text="✕", command=lambda: self._remove_row(row),
                  bg=self._bg, fg="#e74c3c",
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        self._rows.append((attr_var, min_var, row))

    def _remove_row(self, row_frame):
        self._rows = [r for r in self._rows if r[2] is not row_frame]
        row_frame.destroy()

    def _save(self):
        name = self._name.get().strip()
        if not name:
            messagebox.showwarning("Missing Name",
                                   "Give your profile a name.",
                                   parent=self)
            return
        if get_profile(name) and get_profile(name).builtin:
            messagebox.showwarning(
                "Name Taken",
                f"'{name}' is a pre-built profile. Choose another name.",
                parent=self)
            return
        attrs = {}
        for attr_var, min_var, _ in self._rows:
            key = self._label_to_key(attr_var.get())
            if not key:
                continue
            try:
                minimum = max(1, min(99, int(min_var.get())))
            except ValueError:
                continue
            attrs[key] = minimum
        if not attrs:
            messagebox.showwarning("No Attributes",
                                   "Add at least one attribute minimum.",
                                   parent=self)
            return
        codes = dict(POSITION_GROUPS).get(self._pos_choice.get(), [])
        profile = ScoutingProfile(name=name,
                                  description=self._desc.get().strip(),
                                  attributes=attrs,
                                  positions=list(codes))
        save_custom_profile(profile)
        self._finish(name)


class ProfileEditorDialog(InGamePopup):
    """Popup wrapper around ProfileEditorView (backward compatibility)."""

    def __init__(self, parent, bg, fg, profile=None, on_save=None):
        super().__init__(parent, modal=True)
        self.title("Edit Profile" if profile else "New Scouting Profile")
        app = (getattr(parent, 'app', None)
               or getattr(parent, 'parent', None) or parent)
        self._view = ProfileEditorView(self, app=app, bg=bg, fg=fg,
                                       profile=profile, on_save=on_save)
        self._view._close_screen = self.destroy
        self._view.pack(fill="both", expand=True)

    def __getattr__(self, name):
        view = self.__dict__.get("_view")
        if view is not None:
            try:
                return getattr(view, name)
            except AttributeError:
                pass
        return InGamePopup.__getattr__(self, name)
