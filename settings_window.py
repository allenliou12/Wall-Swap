"""The WallSwap Settings window (CustomTkinter).

Never imports wallpaper_changer: when the app runs as __main__ that would load it a second time, with a second
Settings and lock guarding the same file. Everything it needs arrives in a WindowDeps. Every call here runs on the
Tk (main) thread.
"""
import dataclasses
import tkinter
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk

TAG_COLUMNS = 3            # chips per row in a search list
TOPMOST_PULSE_MS = 300     # how long the window stays on top when it opens, to get past Windows' foreground lock
ERROR_COLOR = ("#b3261e", "#ff8a80")  # (light, dark)
HINT_COLOR = ("gray40", "gray65")


@dataclasses.dataclass
class WindowDeps:
    """What the window needs from the app, passed in so this module never imports it."""
    snapshot: dict                                    # settings when the window opened; never changed here
    topic_labels: dict[str, str]
    mix_labels: dict[str, str]
    source_order: tuple
    interval_choices: list[int]
    shares: Callable[[dict], dict[str, int]]          # settings -> whole % of changes per source that has a share
    drop_reason: Callable[[dict, str], str | None]
    clean_search: Callable[[str, list[str]], str | None]
    patch: Callable[[dict, dict], dict]               # settings_patch(before, after)
    ask_folder: Callable[[Any], str | None]
    save: Callable[[dict, bool | None], str | None]   # (patch, start_with_windows or None) -> error message or None
    startup_on: bool
    icon_path: Path
    on_closed: Callable[[], None]
    game_name_max: int
    version: str = ""                                 # shown in the title bar
    resolution_labels: dict[str, str] = dataclasses.field(default_factory=dict)  # min_resolution value -> label
    # (search, done): counts Wallhaven's wallpapers off the Tk thread, then calls done(count or None) on it
    count_search: Callable[[str, Callable[[int | None], None]], None] | None = None


def search_check_message(count: int | None, is_game: bool) -> str:
    """What a search list says once Wallhaven has been asked about a newly added search (count None: no answer).
    Topic searches also need 30 favourites, so their count is only an upper bound; game searches don't."""
    if count is None:
        return "Added. Couldn't check Wallhaven right now."
    if count == 0:
        return "Added, but Wallhaven has nothing big enough for your screen for this search. Try a different spelling or a broader term."
    noun = "wallpaper" if count == 1 else "wallpapers"
    return f"Added. {count:,} {noun} on Wallhaven" if is_game else f"Added. About {count:,} {noun} on Wallhaven"


def _interval_label(minutes: int) -> str:
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} hour" + ("s" if minutes > 60 else "")


class TagList(ctk.CTkFrame):
    """Editable list of searches: click a chip to remove it, type and press Add or Enter to add one."""

    def __init__(self, master, searches: list[str], clean, on_change=lambda: None, count_search=None,
                 is_game: bool = False):
        super().__init__(master, fg_color="transparent")
        self._clean = clean
        self._on_change = on_change
        self._count_search = count_search
        self._is_game = is_game
        self._check_id = 0  # bumped whenever the message line changes, so a late answer can't overwrite a newer one
        self._message_chip = None  # the chip the message line is about (being checked, or its count shown)
        self._chips: list[tuple[str, ctk.CTkButton]] = []
        self._chip_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._chip_frame.pack(fill="x")
        for search in searches:
            self._add_chip(search)
        self._layout()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(4, 0))
        self._entry = ctk.CTkEntry(row, placeholder_text="Add a search")
        self._entry.pack(side="left", fill="x", expand=True)
        self._entry.bind("<Return>", lambda _e: self._add())
        ctk.CTkButton(row, text="Add", width=60, command=self._add).pack(side="left", padx=(6, 0))
        self._message = ctk.CTkLabel(self, text="", text_color=ERROR_COLOR, anchor="w", justify="left",
                                     wraplength=460)
        self._message.pack(fill="x")

    def values(self) -> list[str]:
        return [search for search, _chip in self._chips]

    def _add_chip(self, search: str):
        chip = ctk.CTkButton(self._chip_frame, text=f"{search}  ×", height=24, corner_radius=12,
                             fg_color=("gray80", "gray28"), hover_color=("gray70", "gray36"),
                             text_color=("gray10", "gray90"))
        chip.configure(command=lambda: self._remove(chip))
        self._chips.append((search, chip))

    def _layout(self):
        for i, (_search, chip) in enumerate(self._chips):
            chip.grid(row=i // TAG_COLUMNS, column=i % TAG_COLUMNS, padx=2, pady=2, sticky="w")

    def _remove(self, chip):
        self._chips = [(s, c) for s, c in self._chips if c is not chip]
        chip.destroy()
        self._layout()
        if chip is self._message_chip:
            self._say("")  # its "Checking…" or count goes with it; another tag's message stays
        self._on_change()

    def _add(self):
        text = self._entry.get()
        cleaned = self._clean(text, self.values())
        if cleaned is None:
            # clean_search says only "no"; asking it again without the existing searches tells why
            if not text.split():
                reason = "Empty"
            elif self._clean(text, []) is None:
                reason = "Too long"
            else:
                reason = "Already there"
            self._say(reason, ERROR_COLOR)
            self._message_chip = None
            return
        self._entry.delete(0, "end")
        self._add_chip(cleaned)
        self._layout()
        self._on_change()
        chip = self._chips[-1][1]
        if self._count_search is None:
            self._say("")
            self._message_chip = None
            return
        check_id = self._say("Checking…")
        self._message_chip = chip
        self._count_search(cleaned, lambda count: self._checked(check_id, chip, count))

    def _say(self, text: str, color=HINT_COLOR) -> int:
        self._check_id += 1
        self._message.configure(text=text, text_color=color)
        return self._check_id

    def _checked(self, check_id: int, chip, count: int | None):
        """Tk thread: show Wallhaven's answer, unless the window, the tag or the message has moved on."""
        try:
            if not self.winfo_exists():
                return
        except tkinter.TclError:
            return  # Tk itself is gone
        if check_id != self._check_id or all(c is not chip for _s, c in self._chips):
            return
        self._say(search_check_message(count, self._is_game), ERROR_COLOR if count == 0 else HINT_COLOR)


class FolderList(ctk.CTkFrame):
    """My folders and the favourite game's folders in one list. Only the lists change; folders are never touched."""

    def __init__(self, master, local: list[str], game: list[str], game_tag: str, ask_folder, on_change=lambda: None):
        super().__init__(master, fg_color="transparent")
        self._local, self._game = list(local), list(game)
        self._game_tag = game_tag
        self._ask_folder = ask_folder
        self._on_change = on_change
        self._rows = ctk.CTkFrame(self, fg_color="transparent")
        self._rows.pack(fill="x")
        ctk.CTkButton(self, text="Add folder…", width=120, command=self._add).pack(anchor="w", pady=(6, 0))
        self._message = ctk.CTkLabel(self, text="", text_color=HINT_COLOR, anchor="w")
        self._message.pack(fill="x")
        self._show()

    def values(self) -> tuple[list[str], list[str]]:
        return list(self._local), list(self._game)

    def _show(self):
        for child in self._rows.winfo_children():
            child.destroy()
        folders = list(dict.fromkeys(self._local + self._game))
        if not folders:
            ctk.CTkLabel(self._rows, text="No folders yet.", text_color=HINT_COLOR, anchor="w").pack(fill="x")
        for folder in folders:
            row = ctk.CTkFrame(self._rows, fg_color="transparent")
            row.pack(fill="x", pady=1)
            tag = f"  {self._game_tag}" if folder in self._game else ""
            # The button is packed first so a long path wraps instead of pushing it out of the window
            ctk.CTkButton(row, text="Remove", width=70,
                          command=lambda f=folder: self._remove(f)).pack(side="right", anchor="n")
            ctk.CTkLabel(row, text=folder + tag, anchor="w", justify="left", wraplength=480).pack(
                side="left", fill="x", expand=True)

    def _remove(self, folder: str):
        # Out of both lists, as removing it from the tray does
        self._local = [f for f in self._local if f != folder]
        self._game = [f for f in self._game if f != folder]
        self._message.configure(text="")
        self._show()
        self._on_change()

    def _add(self):
        folder = self._ask_folder(self.winfo_toplevel())
        if not folder:
            return
        if folder in self._local or folder in self._game:
            self._message.configure(text="Already in the list")
            return
        self._message.configure(text="")
        self._local.append(folder)
        self._show()
        self._on_change()


class _TopicRow(ctk.CTkFrame):
    """One topic: tick box, search count and an arrow that opens its searches (built on first open)."""

    def __init__(self, master, label: str, entry: dict, clean, on_change, count_search=None):
        super().__init__(master, fg_color="transparent")
        self._searches = list(entry["searches"])
        self._clean = clean
        self._count_search = count_search
        self._on_change = on_change
        self.tags: TagList | None = None
        self._open = False
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x")
        self.check = ctk.CTkCheckBox(head, text=label, command=on_change)
        if entry["enabled"]:
            self.check.select()
        self.check.pack(side="left")
        self._arrow = ctk.CTkButton(head, text="▸", width=28, height=24, fg_color="transparent",
                                    text_color=("gray10", "gray90"), hover_color=("gray80", "gray28"),
                                    command=self.toggle)
        self._arrow.pack(side="right")
        self._count = ctk.CTkLabel(head, text="", text_color=HINT_COLOR)
        self._count.pack(side="right", padx=6)
        self._update_count()

    def searches(self) -> list[str]:
        return self.tags.values() if self.tags else list(self._searches)

    def toggle(self):
        if self.tags is None:
            # Built only now: all topics' chips at once (about 141 for an upgraded file) would slow the opening
            self.tags = TagList(self, self._searches, self._clean, on_change=self._tags_changed,
                                count_search=self._count_search)
        self._open = not self._open
        if self._open:
            self.tags.pack(fill="x", padx=(28, 0), pady=(2, 6))
        else:
            self.tags.pack_forget()
        self._arrow.configure(text="▾" if self._open else "▸")

    def _tags_changed(self):
        self._update_count()
        self._on_change()

    def _update_count(self):
        n = len(self.searches())
        self._count.configure(text=f"{n} search" + ("" if n == 1 else "es"))


class SettingsWindow(ctk.CTkToplevel):
    """Edits a snapshot of the settings; Save hands only what changed to deps.save."""

    def __init__(self, master, deps: WindowDeps):
        super().__init__(master)
        self.deps = deps
        self._snapshot = deps.snapshot
        self._closed = False
        self.title(f"WallSwap {deps.version} Settings" if deps.version else "WallSwap Settings")
        self.geometry("640x720")
        self.minsize(520, 480)
        self._set_icon()
        self.after(250, self._set_icon)  # CTkToplevel can set its own icon shortly after opening
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._body = body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        self._build_topics(body)
        self._build_game(body)
        self._build_folders(body)
        self._build_mix(body)
        self._build_interval(body)
        self._build_resolution(body)
        self._build_startup(body)
        self._build_footer()
        self._refresh_shares()
        self.bring_to_front()

    # ── Building ──
    def _heading(self, master, text: str):
        ctk.CTkLabel(master, text=text, font=ctk.CTkFont(size=16, weight="bold"),
                     anchor="w").pack(fill="x", pady=(14, 4))

    def _build_topics(self, body):
        self._heading(body, "Topics")
        self._topics: dict[str, _TopicRow] = {}
        for topic, label in self.deps.topic_labels.items():
            if topic in self._snapshot["topics"]:
                row = _TopicRow(body, label, self._snapshot["topics"][topic], self.deps.clean_search,
                                self._refresh_shares, count_search=self.deps.count_search)
                row.pack(fill="x", pady=1)
                self._topics[topic] = row

    def _build_game(self, body):
        self._heading(body, "Favourite game")
        limit = self.deps.game_name_max
        self._game_name = ctk.CTkEntry(
            body, placeholder_text="Game name", validate="key",
            validatecommand=(self.register(lambda text: len(text) <= limit), "%P"))
        if self._snapshot["game_name"]:
            self._game_name.insert(0, self._snapshot["game_name"][:limit])
        self._game_name.pack(fill="x")
        ctk.CTkLabel(body, text="Leave empty if you don't want one.", text_color=HINT_COLOR,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(body, text="Wallhaven searches for it", anchor="w").pack(fill="x", pady=(6, 0))
        self._game_tags = TagList(body, self._snapshot["game_queries"], self.deps.clean_search,
                                  on_change=self._refresh_shares, count_search=self.deps.count_search, is_game=True)
        self._game_tags.pack(fill="x")

    def _build_folders(self, body):
        self._heading(body, "My folders")
        name = self._snapshot["game_name"]
        self._folders = FolderList(body, self._snapshot["local_folders"], self._snapshot["game_folders"],
                                   f"({name or 'game'})", self.deps.ask_folder, on_change=self._refresh_shares)
        self._folders.pack(fill="x")

    def _build_mix(self, body):
        self._heading(body, "Source mix")
        self._sliders: dict[str, ctk.CTkSlider] = {}
        self._moved: set[str] = set()
        self._share_labels: dict[str, ctk.CTkLabel] = {}
        grid = ctk.CTkFrame(body, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure(1, weight=1)
        for i, source in enumerate(self.deps.source_order):
            ctk.CTkLabel(grid, text=self.deps.mix_labels[source], anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 10), pady=4)
            slider = ctk.CTkSlider(grid, from_=0, to=100, number_of_steps=100,
                                   command=lambda _v, s=source: self._slider_moved(s))
            slider.set(min(100, round(self._snapshot["chances"][source] * 100)))
            slider.grid(row=i, column=1, sticky="ew", pady=4)
            share = ctk.CTkLabel(grid, text="", anchor="w", width=220)
            share.grid(row=i, column=2, sticky="w", padx=(10, 0), pady=4)
            self._sliders[source] = slider
            self._share_labels[source] = share
        self._mix_warning = ctk.CTkLabel(body, text="", text_color=ERROR_COLOR, anchor="w", justify="left")
        self._mix_warning.pack(fill="x")

    def _build_interval(self, body):
        self._heading(body, "Change every")
        self._interval_by_label = {_interval_label(m): m for m in self.deps.interval_choices}
        self._interval = ctk.CTkSegmentedButton(body, values=list(self._interval_by_label))
        stored = self._snapshot["interval_minutes"]
        # A hand-set value that isn't one of the choices shows none selected and is kept
        self._interval.set(_interval_label(stored) if stored in self.deps.interval_choices else "")
        self._interval.pack(anchor="w")

    def _build_resolution(self, body):
        self._heading(body, "Smallest image to use")
        self._resolution_by_label = {label: value for value, label in self.deps.resolution_labels.items()}
        self._resolution = ctk.CTkSegmentedButton(body, values=list(self._resolution_by_label))
        stored = self._snapshot["min_resolution"]
        # A hand-set value that isn't one of the choices behaves as the first one (match the screen) and is kept
        self._resolution.set(self.deps.resolution_labels.get(stored) or next(iter(self._resolution_by_label), ""))
        self._resolution.pack(anchor="w")
        ctk.CTkLabel(body, text="Smaller images are skipped, in your own folders too. Match my screen never asks "
                                "for more than 1440p.", text_color=HINT_COLOR, anchor="w").pack(fill="x")

    def _build_startup(self, body):
        self._heading(body, "Start with Windows")
        self._startup = ctk.CTkSwitch(body, text="Start WallSwap when I sign in")
        if self.deps.startup_on:
            self._startup.select()
        self._startup.pack(anchor="w", pady=(0, 12))

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=12)
        if self.deps.version:
            ctk.CTkLabel(footer, text=f"WallSwap {self.deps.version}", text_color=HINT_COLOR).pack(side="left", padx=(0, 12))
        self._banner =ctk.CTkLabel(footer, text="", text_color=ERROR_COLOR, anchor="w", justify="left",
                                    wraplength=380)
        self._banner.pack(side="left", fill="x", expand=True)
        self._save_button = ctk.CTkButton(footer, text="Save", width=90, command=self._on_save)
        self._save_button.pack(side="right")
        self._cancel_button = ctk.CTkButton(footer, text="Cancel", width=90, fg_color="transparent", border_width=1,
                                            text_color=("gray10", "gray90"), command=self._on_cancel)
        self._cancel_button.pack(side="right", padx=(0, 8))

    def _set_icon(self):
        try:
            self.iconbitmap(str(self.deps.icon_path))
        except tkinter.TclError:
            pass  # missing or unreadable icon file: the window keeps Tk's default icon

    # ── State ──
    def form(self) -> dict:
        """The settings as the window shows them, shaped like settings.json (only the keys it edits)."""
        snap = self._snapshot
        local, game = self._folders.values()
        chances = dict(snap["chances"])
        for source in self._moved:
            chances[source] = round(self._sliders[source].get() / 100, 2)
        topics = {t: {"enabled": row.check.get() == 1, "searches": row.searches()}
                  for t, row in self._topics.items()}
        resolution = self._resolution_by_label.get(self._resolution.get(), snap["min_resolution"])
        if snap["min_resolution"] not in self.deps.resolution_labels and resolution == next(
                iter(self.deps.resolution_labels), None):
            resolution = snap["min_resolution"]  # the hand-set value was only shown as the first choice
        return {
            "interval_minutes": self._interval_by_label.get(self._interval.get(), snap["interval_minutes"]),
            "min_resolution": resolution,
            "game_name": self._game_name.get().strip()[:self.deps.game_name_max],
            "game_queries": self._game_tags.values(),
            "chances": chances,
            "topics": {**snap["topics"], **topics},
            "local_folders": local,
            "game_folders": game,
        }

    def _slider_moved(self, source: str):
        self._moved.add(source)  # an untouched slider keeps the stored value, even one it can't show (like 1.5)
        self._refresh_shares()

    def _refresh_shares(self):
        data = {**self._snapshot, **self.form()}
        shares = self.deps.shares(data)
        for source, label in self._share_labels.items():
            if source in shares:
                label.configure(text=f"{shares[source]}% of changes")
            else:
                label.configure(text=f"0% · {self.deps.drop_reason(data, source) or 'not used'}")
        self._mix_warning.configure(
            text="" if shares else "No source can be used, so the wallpaper won't change until one can.")

    def _startup_choice(self) -> bool | None:
        on = self._startup.get() == 1
        return on if on != self.deps.startup_on else None

    # ── Buttons ──
    def _on_save(self):
        patch = self.deps.patch(self._snapshot, self.form())
        startup = self._startup_choice()
        self._save_button.configure(state="disabled")
        self._cancel_button.configure(state="disabled")
        self._banner.configure(text="Saving…", text_color=HINT_COLOR)
        self.update_idletasks()
        error = self.deps.save(patch, startup)
        if error:
            self._banner.configure(text=error, text_color=ERROR_COLOR)
            self._save_button.configure(state="normal")
            self._cancel_button.configure(state="normal")
            return
        self.destroy()

    def _on_cancel(self):
        changed = any(self.deps.patch(self._snapshot, self.form()).values()) or self._startup_choice() is not None
        if changed and not messagebox.askyesno("WallSwap", "Discard your changes?", parent=self):
            return
        self.destroy()

    def bring_to_front(self):
        """Raise and focus the window; a short topmost pulse gets past Windows' foreground lock."""
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(TOPMOST_PULSE_MS, self._end_topmost)

    def _end_topmost(self):
        try:
            self.attributes("-topmost", False)
        except tkinter.TclError:
            pass  # the window closed during the pulse; nothing left to lower

    def destroy(self):
        # Every way the window goes away (Save, Cancel, close button, Quit) ends here; tell the app once
        if not self._closed:
            self._closed = True
            self.deps.on_closed()
        super().destroy()
