"""Scouting profile manager dialog for Puck Dynasty.

Browse the pre-built archetype profiles, and create / edit / delete your own
custom profiles (attribute minimums + position scope). Pure Tkinter UI over
the scouting_profiles logic module.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from modern_widgets import RoundedButton

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


class ScoutingProfileDialog(tk.Toplevel):
    """Browse, create, edit and delete scouting profiles."""

    def __init__(self, parent, on_apply=None):
        super().__init__(parent)
        self._parent = parent
        self._on_apply = on_apply  # callback(profile_name) after Apply/close
        self.title("Scouting Profiles")
        self.geometry("760x620")
        self.minsize(680, 540)
        self.transient(parent)
        self.grab_set()

        bg = getattr(parent, "CONTENT_BG", "#1e2430")
        fg = getattr(parent, "TEXT_COLOR", "#e8ecf4")
        self.configure(bg=bg)
        self._bg, self._fg = bg, fg

        main = tk.Frame(self, bg=bg)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # -- left: profile list -------------------------------------------
        left = tk.LabelFrame(main, text="Profiles", bg=bg, fg=fg,
                             font=("Helvetica", 10, "bold"))
        left.pack(side="left", fill="y", padx=(0, 10))
        self._list = tk.Listbox(left, width=26, height=24, bg="#141a24", fg=fg,
                                selectbackground="#2f6fed",
                                font=("Helvetica", 10))
        self._list.pack(fill="y", expand=True, padx=6, pady=6)
        self._list.bind("<<ListboxSelect>>", self._on_select)

        # -- right: details -------------------------------------------------
        right = tk.Frame(main, bg=bg)
        right.pack(side="left", fill="both", expand=True)

        self._name_var = tk.StringVar()
        tk.Label(right, textvariable=self._name_var, bg=bg, fg=fg,
                 font=("Helvetica", 14, "bold")).pack(anchor="w")
        self._desc_var = tk.StringVar()
        tk.Label(right, textvariable=self._desc_var, bg=bg, fg="#9aa4b5",
                 font=("Helvetica", 10), wraplength=440,
                 justify="left").pack(anchor="w", pady=(0, 8))

        cols = ("Attribute", "Minimum")
        self._attrs = ttk.Treeview(right, columns=cols, show="headings",
                                   height=12)
        self._attrs.heading("Attribute", text="Attribute")
        self._attrs.heading("Minimum", text="Minimum")
        self._attrs.column("Attribute", width=220)
        self._attrs.column("Minimum", width=90, anchor="center")
        self._attrs.pack(fill="x", pady=(0, 8))

        self._pos_var = tk.StringVar()
        tk.Label(right, textvariable=self._pos_var, bg=bg, fg="#9aa4b5",
                 font=("Helvetica", 10)).pack(anchor="w", pady=(0, 10))

        # -- buttons --------------------------------------------------------
        btn = tk.Frame(right, bg=bg)
        btn.pack(fill="x", pady=(4, 0))
        self._new_btn = RoundedButton(btn, text="New Profile", command=self._new,
                                      bg="#2f6fed", fg="white",
                                      font=("Helvetica", 10, "bold"),
                                      radius=9, padx=14, pady=7)
        self._new_btn.pack(side="left", padx=(0, 6))
        self._edit_btn = RoundedButton(btn, text="Edit", command=self._edit,
                                       bg="#242F42", fg=fg,
                                       font=("Helvetica", 10),
                                       radius=9, padx=14, pady=7)
        self._edit_btn.pack(side="left", padx=(0, 6))
        self._del_btn = RoundedButton(btn, text="Delete", command=self._delete,
                                      bg="#242F42", fg=fg,
                                      font=("Helvetica", 10),
                                      radius=9, padx=14, pady=7)
        self._del_btn.pack(side="left", padx=(0, 6))
        self._apply_btn = RoundedButton(btn, text="Apply & Close",
                                        command=self._apply_close,
                                        bg="#1f9d55", fg="white",
                                        font=("Helvetica", 10, "bold"),
                                        radius=9, padx=16, pady=8)
        self._apply_btn.pack(side="right")

        self._refresh_list()

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
        ProfileEditorDialog(self, self._bg, self._fg,
                            on_save=self._after_save)

    def _edit(self):
        p = self._selected()
        if p and not p.builtin:
            ProfileEditorDialog(self, self._bg, self._fg,
                                profile=p, on_save=self._after_save)

    def _after_save(self, name):
        self._refresh_list(select=name)

    def _delete(self):
        p = self._selected()
        if not p or p.builtin:
            return
        if messagebox.askyesno("Delete Profile",
                                f"Delete your custom profile '{p.name}'?",
                                parent=self):
            delete_custom_profile(p.name)
            self._refresh_list()

    def _apply_close(self):
        p = self._selected()
        if self._on_apply and p:
            self._on_apply(p.name)
        self.destroy()


class ProfileEditorDialog(tk.Toplevel):
    """Create or edit a single custom scouting profile."""

    def __init__(self, parent, bg, fg, profile=None, on_save=None):
        super().__init__(parent)
        self._on_save = on_save
        self._editing_name = profile.name if profile else None
        self.title("Edit Profile" if profile else "New Scouting Profile")
        self.geometry("560x640")
        self.minsize(520, 560)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=bg)
        self._bg, self._fg = bg, fg

        main = tk.Frame(self, bg=bg)
        main.pack(fill="both", expand=True, padx=14, pady=14)

        # name + description
        tk.Label(main, text="Profile name:", bg=bg, fg=fg,
                 font=("Helvetica", 10, "bold")).pack(anchor="w")
        self._name = tk.StringVar(value=profile.name if profile else "")
        tk.Entry(main, textvariable=self._name, width=40,
                 font=("Helvetica", 11)).pack(anchor="w", pady=(2, 8))

        tk.Label(main, text="Description:", bg=bg, fg=fg,
                 font=("Helvetica", 10, "bold")).pack(anchor="w")
        self._desc = tk.StringVar(
            value=profile.description if profile else "")
        tk.Entry(main, textvariable=self._desc, width=60,
                 font=("Helvetica", 10)).pack(anchor="w", fill="x",
                                              pady=(2, 10))

        # position scope
        tk.Label(main, text="Position scope:", bg=bg, fg=fg,
                 font=("Helvetica", 10, "bold")).pack(anchor="w")
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
                 font=("Helvetica", 10, "bold")).pack(anchor="w")
        self._rows_frame = tk.Frame(main, bg=bg)
        self._rows_frame.pack(fill="both", expand=True, pady=(4, 8))
        self._rows = []  # (attr_var, min_var, row_frame)

        add_btn = RoundedButton(main, text="+ Add Attribute",
                                command=self._add_row, bg="#242F42", fg=fg,
                                font=("Helvetica", 10),
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
                      font=("Helvetica", 10, "bold"),
                      radius=9, padx=14, pady=7).pack(side="left",
                                                     padx=(0, 8))
        RoundedButton(btn, text="Cancel", command=self.destroy,
                      bg="#242F42", fg=fg, font=("Helvetica", 10),
                      radius=9, padx=14, pady=7).pack(side="left")

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
                  font=("Helvetica", 10, "bold")).pack(side="left")
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
        if self._on_save:
            self._on_save(name)
        self.destroy()
