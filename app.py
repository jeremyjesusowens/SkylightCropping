#!/usr/bin/env python3
"""Skylight Cropping — desktop GUI (Darkroom · Aurora/Twilight theme).

Image-first redesign: a live 16:9 preview shows Claude's detected focal point
and crop box for each photo. Results persist per-image as a batch runs, so any
item in the queue can be clicked to review its crop during or after processing.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    import keyring
    import keyring.errors
    _KEYRING_AVAILABLE = True
except Exception:
    _KEYRING_AVAILABLE = False

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk


def _resource_path(*parts: str) -> Path:
    """Resolve a bundled resource, accounting for PyInstaller's extraction dir."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base.joinpath(*parts)


def _get_build_version() -> str:
    """Identify the exact commit/build this binary was produced from.

    Build scripts write build_info.txt (short commit SHA) next to app.py
    before invoking PyInstaller, and it gets bundled via --add-data so a
    packaged exe can report what it was built from. When running from
    source with no such file, fall back to asking git directly.
    """
    build_info = _resource_path("build_info.txt")
    if build_info.exists():
        return build_info.read_text(encoding="utf-8").strip()
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent, stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "dev"


APP_VERSION = _get_build_version()

from prompt_eval import DEFAULT_MODEL as PROMPT_EVAL_DEFAULT_MODEL
from prompt_eval import PROMPT_VARIANTS, run_prompt_eval
from smart_crop import (FALLBACK_MODELS, CropResult, collect_images,
                        compute_crop_box, list_models, recrop_image, run_crop,
                        run_send)

# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

_SETTINGS_DIR = (
    Path.home() / "Library" / "Application Support" / "SkylightCropping"
    if sys.platform == "darwin"
    else Path.home() / ".skylight_cropping"
)
SETTINGS_FILE = _SETTINGS_DIR / "settings.json"
DEFAULT_TO = ""  # set your Skylight frame's email address in the app Settings

_KEYRING_SERVICE = "SkylightCropping"
_KEYRING_KEYS = {"api_key", "smtp_password"}


def _kr_get(key: str) -> str:
    if not _KEYRING_AVAILABLE:
        return ""
    try:
        return keyring.get_password(_KEYRING_SERVICE, key) or ""
    except Exception:
        return ""


def _kr_set(key: str, value: str) -> bool:
    if not _KEYRING_AVAILABLE:
        return False
    try:
        if value:
            keyring.set_password(_KEYRING_SERVICE, key, value)
        else:
            try:
                keyring.delete_password(_KEYRING_SERVICE, key)
            except keyring.errors.PasswordDeleteError:
                pass
        return True
    except Exception:
        return False

# --- Aurora / Twilight palette ---------------------------------------------
BG        = "#0b0c14"   # window background
BAR       = "#12131f"   # top bar / footer
PANEL     = "#161827"   # raised panels / cards
PANEL2    = "#11121c"   # inset surfaces (entries, canvas)
STROKE    = "#25283a"   # borders
ACCENT    = "#A48CFF"   # primary violet
ACCENT_HV = "#b9a6ff"   # accent hover
ACCENT_INK = "#0e0822"  # text on accent
TXT       = "#e7e8f0"   # primary text
MUTED     = "#838aa3"   # secondary text
DIM       = "#5b6178"   # tertiary text
DONE      = "#5fd1b0"   # success
ERRC      = "#ff6b6b"   # failure
WARN      = "#e8a328"   # caution / crop warning
THUMB     = "#1b1d2e"   # thumbnail placeholder
SEL       = "#1d2030"   # selected row
HOVER     = "#191b2a"   # subtle hover

PREVIEW_MAX_PX = 1600    # cap for the in-app preview copy (display only)
THUMB_SIZE = (58, 34)    # queue-row thumbnail size

_SUBJECT_EMOJI: dict[str, str] = {
    "heron": "🦤", "egret": "🦤", "crane": "🦢", "eagle": "🦅", "hawk": "🦅",
    "osprey": "🦅", "falcon": "🦅", "owl": "🦉", "duck": "🦆", "goose": "🦆",
    "swan": "🦢", "pelican": "🐦", "bird": "🐦",
    "alligator": "🐊", "crocodile": "🐊",
    "deer": "🦌", "fox": "🦊", "bear": "🐻", "wolf": "🐺", "coyote": "🐺",
    "dog": "🐕", "cat": "🐈", "horse": "🐎", "rabbit": "🐇", "squirrel": "🐿️",
    "turtle": "🐢", "snake": "🐍", "lizard": "🦎", "frog": "🐸",
    "fish": "🐟", "dolphin": "🐬", "whale": "🐋", "seal": "🦭",
    "butterfly": "🦋", "dragonfly": "🪲", "bee": "🐝",
    "person": "🧍", "people": "👥", "child": "🧒",
    "flower": "🌸", "tree": "🌳", "landscape": "🏞️", "sunset": "🌅",
}


def subject_emoji(subject: str) -> str:
    s = subject.lower()
    for keyword, emoji in _SUBJECT_EMOJI.items():
        if keyword in s:
            return emoji
    return "📷"


def make_thumbnail(path: str, size: tuple[int, int] = THUMB_SIZE) -> Image.Image:
    """Load an image file and return a small, fully-decoded RGB thumbnail.

    Raises on unreadable/corrupt files — callers decide how to handle that.
    """
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im = ImageOps.fit(im, size, Image.LANCZOS)
        im.load()  # fully decode before the file handle closes
    return im


def _open_folder(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def load_settings() -> dict:
    defaults = {
        "api_key": "",
        "smtp_password": "",
        "from_email": "",
        "to_email": DEFAULT_TO,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": "587",
        "max_retries": "12",
        "retry_delay": "300",
        "model": "claude-opus-4-7",
        "output_suffix": "_16x9",
        # remembered between sessions
        "crop_files": [],
        "crop_output_dir": "",
        "send_dir": "",
        "model_list": list(FALLBACK_MODELS),
    }
    if SETTINGS_FILE.exists():
        try:
            defaults.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    # Keyring values take precedence over any plaintext remnants in the JSON file.
    for key in _KEYRING_KEYS:
        kr_val = _kr_get(key)
        if kr_val:
            defaults[key] = kr_val
    return defaults


def save_settings(settings: dict) -> None:
    to_save = dict(settings)
    for key in _KEYRING_KEYS:
        value = to_save.pop(key, "")
        if not _kr_set(key, value):
            to_save[key] = value  # keyring unavailable — keep in plaintext as fallback
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(to_save, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Skylight Cropping")
        self.geometry("1200x920")
        self.minsize(1040, 780)
        self.configure(fg_color=BG)

        _icon_png = _resource_path("assets", "icon.png")
        _icon_ico = _resource_path("assets", "icon.ico")
        if sys.platform == "win32" and _icon_ico.exists():
            self.iconbitmap(str(_icon_ico))
        elif _icon_png.exists():
            _icon_img = ImageTk.PhotoImage(Image.open(_icon_png).resize((256, 256), Image.LANCZOS))
            self.iconphoto(True, _icon_img)
            self._app_icon = _icon_img  # prevent GC

        self.settings = load_settings()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.progress_queue: queue.Queue[tuple[int, int]] = queue.Queue()
        self.result_queue: queue.Queue = queue.Queue()
        self._running = False

        # Queue model: ordered list of item dicts; lookup by path.
        self.items: list[dict] = []
        self.item_by_path: dict[str, dict] = {}
        self.current_path: str | None = None

        # Preview / thumbnail caches.
        self._preview_cache: dict[str, tuple[Image.Image, tuple[int, int]]] = {}
        self._tk_preview = None          # keep a ref so it isn't GC'd
        self._resize_after = None
        self.thumb_jobs: queue.Queue[str] = queue.Queue()
        self.thumb_ready: queue.Queue[tuple[str, Image.Image]] = queue.Queue()
        self._thumb_requested: set[str] = set()

        # Fonts — humanist sans; Courier New / Menlo for mono.
        # Trebuchet MS ships with Windows; Helvetica Neue is the macOS fallback.
        UI     = "Helvetica Neue" if sys.platform == "darwin" else "Trebuchet MS"
        MONO_F = "Menlo"          if sys.platform == "darwin" else "Courier New"
        # A color-emoji font, so subject icons render in their native colors
        # instead of being substituted by a fallback glyph tinted by the
        # surrounding label's text_color.
        EMOJI_F = ("Apple Color Emoji" if sys.platform == "darwin"
                   else "Segoe UI Emoji" if sys.platform == "win32"
                   else "Noto Color Emoji")
        self.f_word    = ctk.CTkFont(family=UI,     size=20, weight="bold")
        self.f_word_it = ctk.CTkFont(family=UI,     size=20, slant="italic")
        self.f_nav     = ctk.CTkFont(family=UI,     size=13, weight="bold")
        self.f_h1      = ctk.CTkFont(family=UI,     size=26, weight="bold")
        self.f_section = ctk.CTkFont(family=UI,     size=12, weight="bold")
        self.f_label   = ctk.CTkFont(family=UI,     size=13)
        self.f_small   = ctk.CTkFont(family=UI,     size=11)
        self.f_button  = ctk.CTkFont(family=UI,     size=13, weight="bold")
        self.f_mono    = ctk.CTkFont(family=MONO_F, size=12)
        self.f_emoji   = ctk.CTkFont(family=EMOJI_F, size=12)

        self._build_ui()

        # Restore remembered photos (that still exist) into the queue.
        for f in self.settings.get("crop_files", []):
            f = str(Path(f))
            if Path(f).exists():
                self._add_item(f)
        self._refresh_count()
        if self.items:
            self._select_item(self.items[0]["path"])
        else:
            self._render_preview(None)

        threading.Thread(target=self._thumb_worker, daemon=True).start()
        self._poll_queues()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.settings.get("api_key", "").strip():
            self._refresh_models(silent=True)

    # =======================================================================
    # Layout
    # =======================================================================

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_topbar()

        self.content = ctk.CTkFrame(self, fg_color=BG)
        self.content.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.frames = {
            "Crop": ctk.CTkFrame(self.content, fg_color=BG),
            "Send": ctk.CTkFrame(self.content, fg_color=BG),
            "Settings": ctk.CTkFrame(self.content, fg_color=BG),
        }
        for fr in self.frames.values():
            fr.grid(row=0, column=0, sticky="nsew")

        self._build_crop_tab(self.frames["Crop"])
        self._build_send_tab(self.frames["Send"])
        self._build_settings_tab(self.frames["Settings"])

        self._build_footer()
        self._select_tab("Crop")

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=60, fg_color=BAR, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)

        # Wordmark canvas — animated crop-bracket corners
        # On macOS, offset right to clear the traffic-light window buttons (~80px).
        wm_x = 90 if sys.platform == "darwin" else 18
        wm = tk.Canvas(bar, width=270, height=54, bg=BAR, highlightthickness=0)
        wm.place(x=wm_x, y=3)
        wm.create_text(18, 33, anchor="w", text="Skylight", fill=TXT,
                       font=self.f_word)
        wm.create_text(106, 33, anchor="w", text="Cropping", fill=ACCENT,
                       font=self.f_word_it)
        # bracket lines tagged so we can update coords each frame
        for _ in range(8):
            wm.create_line(0, 0, 0, 0, fill=ACCENT, width=1, tags="brk")
        self._wm_canvas = wm
        self._wm_draw_brackets(1.0)   # start expanded
        self._wm_schedule_idle()

        self.nav_btns: dict[str, ctk.CTkButton] = {}
        self.nav_bars: dict[str, ctk.CTkFrame] = {}
        self.nav_bar_x: dict[str, int] = {}
        x0 = 510 if sys.platform == "darwin" else 440
        for i, name in enumerate(("Crop", "Send", "Settings")):
            b = ctk.CTkButton(bar, text=name.upper(), font=self.f_nav, width=92,
                              fg_color="transparent", hover_color=HOVER,
                              text_color=MUTED,
                              command=lambda n=name: self._select_tab(n))
            b.place(x=x0 + i * 116, y=14)
            u = ctk.CTkFrame(bar, height=3, width=52, fg_color=ACCENT, corner_radius=2)
            self.nav_bar_x[name] = x0 + i * 116 + 20
            self.nav_btns[name] = b
            self.nav_bars[name] = u

    # ------------------------------------------------------------------
    # Wordmark bracket animation
    # Expanded box: bx=4,by=4,bw=262,bh=46  (loose frame around full canvas)
    # Tight box:    bx=8,by=21,bw=226,bh=20  (hugs text both H and V)
    # Easing: smoothstep  Duration: ~2 s in  Hold: 4 s  Idle: ~16 s
    # ------------------------------------------------------------------
    _WM_EXPANDED = (4, 4, 262, 46, 11)     # bx, by, bw, bh, leg
    _WM_TIGHT    = (8, 21, 188, 20, 8)
    _WM_FRAMES   = 80          # steps per transition
    _WM_STEP_MS  = 25          # ms per frame (~2 s total)
    _WM_HOLD_MS  = 4_000       # pause at expanded before returning to tight
    _WM_IDLE_MS  = 9_000       # wait (at tight) between animation cycles

    def _wm_lerp(self, t):
        """Smoothstep easing 0→1."""
        return t * t * (3 - 2 * t)

    def _wm_draw_brackets(self, t):
        """Draw brackets interpolated at progress t (0=tight, 1=expanded)."""
        e, g = self._WM_EXPANDED, self._WM_TIGHT
        bx = g[0] + (e[0] - g[0]) * t
        by = g[1] + (e[1] - g[1]) * t
        bw = g[2] + (e[2] - g[2]) * t
        bh = g[3] + (e[3] - g[3]) * t
        leg = g[4] + (e[4] - g[4]) * t
        corners = ((bx, by, 1, 1), (bx+bw, by, -1, 1),
                   (bx, by+bh, 1, -1), (bx+bw, by+bh, -1, -1))
        items = self._wm_canvas.find_withtag("brk")
        for idx, (cx, cy, dx, dy) in enumerate(corners):
            self._wm_canvas.coords(items[idx*2],
                                   cx, cy, cx + dx*leg, cy)
            self._wm_canvas.coords(items[idx*2+1],
                                   cx, cy, cx, cy + dy*leg)

    def _wm_schedule_idle(self):
        # rest at expanded, then occasionally crop in
        self.after(self._WM_IDLE_MS, lambda: self._wm_animate(0, expanding=False))

    def _wm_animate(self, frame, expanding):
        t_raw = frame / self._WM_FRAMES
        t = self._wm_lerp(t_raw)
        self._wm_draw_brackets(t if expanding else 1.0 - t)
        if frame < self._WM_FRAMES:
            self.after(self._WM_STEP_MS,
                       lambda: self._wm_animate(frame + 1, expanding))
        elif not expanding:
            # arrived at tight — hold, then expand back
            self.after(self._WM_HOLD_MS,
                       lambda: self._wm_animate(0, expanding=True))
        else:
            # back to expanded — idle before next cycle
            self._wm_schedule_idle()

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color=BAR, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        row = ctk.CTkFrame(footer, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 2))
        row.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(row, text="Ready", anchor="w",
                                         font=self.f_label, text_color=MUTED)
        self.status_label.grid(row=0, column=0, sticky="w")
        self.progress_count = ctk.CTkLabel(row, text="", anchor="e",
                                           font=self.f_button, text_color=ACCENT)
        self.progress_count.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(row, text=APP_VERSION, anchor="e",
                     font=self.f_small, text_color=MUTED).grid(row=0, column=2, sticky="e", padx=(12, 0))

        self.progress = ctk.CTkProgressBar(footer, height=8, corner_radius=4,
                                           progress_color=ACCENT, fg_color=PANEL2)
        self.progress.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.progress.set(0)

        head = ctk.CTkFrame(footer, fg_color="transparent")
        head.grid(row=2, column=0, sticky="ew", padx=18)
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="ACTIVITY LOG", anchor="w", font=self.f_section,
                     text_color=MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(head, text="Clear", width=58, height=24, font=self.f_small,
                      fg_color="transparent", border_width=1, border_color=STROKE,
                      text_color=MUTED, hover_color=HOVER,
                      command=self._clear_log).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(footer, height=104, state="disabled",
                                      font=self.f_mono, corner_radius=8,
                                      fg_color=PANEL2, text_color="#9aa0b8",
                                      border_width=1, border_color=STROKE)
        self.log_box.grid(row=3, column=0, sticky="ew", padx=18, pady=(4, 12))

    def _select_tab(self, name: str):
        self.frames[name].tkraise()
        for n, b in self.nav_btns.items():
            active = n == name
            b.configure(text_color=TXT if active else MUTED)
            if active:
                self.nav_bars[n].place(x=self.nav_bar_x[n], y=46)
            else:
                self.nav_bars[n].place_forget()

    # -- styled control helpers ----------------------------------------------

    def _entry(self, parent, textvariable=None, placeholder="", show="", width=None):
        kw = dict(fg_color=PANEL2, border_color=STROKE, border_width=1,
                  text_color=TXT, placeholder_text_color=DIM)
        if width:
            kw["width"] = width
        return ctk.CTkEntry(parent, textvariable=textvariable, show=show,
                            placeholder_text=placeholder, **kw)

    def _primary(self, parent, text, command, height=44, width=None):
        kw = dict(text=text, command=command, height=height, font=self.f_button,
                  fg_color=ACCENT, hover_color=ACCENT_HV, text_color=ACCENT_INK,
                  corner_radius=8)
        if width:
            kw["width"] = width
        return ctk.CTkButton(parent, **kw)

    def _ghost(self, parent, text, command, width=96, height=30):
        return ctk.CTkButton(parent, text=text, command=command, width=width,
                             height=height, font=self.f_button,
                             fg_color=PANEL2, hover_color=HOVER, text_color=TXT,
                             border_width=1, border_color=STROKE, corner_radius=7)

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=PANEL,
                            border_width=1, border_color=STROKE)
        card.pack(fill="x", pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title.upper(), font=self.f_section, anchor="w",
                     text_color=MUTED).grid(row=0, column=0, sticky="w",
                                            padx=18, pady=(14, 2))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=18, pady=(2, 16))
        body.grid_columnconfigure(1, weight=1)
        return body

    # =======================================================================
    # Crop tab
    # =======================================================================

    def _build_crop_tab(self, tab):
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=0)

        # --- left: preview + options + crop button --------------------------
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        pv = ctk.CTkFrame(left, fg_color="#0a0b12", corner_radius=10,
                          border_width=1, border_color=STROKE)
        pv.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(pv, bg="#0a0b12", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_preview_click)

        opt = ctk.CTkFrame(left, fg_color=PANEL, corner_radius=10,
                           border_width=1, border_color=STROKE)
        opt.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        opt.grid_columnconfigure(1, weight=1)
        opt.grid_columnconfigure(3, weight=0)

        ctk.CTkLabel(opt, text="Output", font=self.f_label, text_color=MUTED).grid(
            row=0, column=0, sticky="w", padx=(16, 8), pady=(14, 7))
        of = ctk.CTkFrame(opt, fg_color="transparent")
        of.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 16), pady=(14, 7))
        of.grid_columnconfigure(0, weight=1)
        self.output_dir_var = ctk.StringVar(value=self.settings.get("crop_output_dir", ""))
        self._entry(of, self.output_dir_var,
                    "Same folder as each source photo").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._ghost(of, "Browse", self._browse_output_dir, width=84).grid(row=0, column=1)

        ctk.CTkLabel(opt, text="Suffix", font=self.f_label, text_color=MUTED).grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=7)
        self.suffix_var = ctk.StringVar(value=self.settings.get("output_suffix", "_16x9"))
        self._entry(opt, self.suffix_var, width=120).grid(row=1, column=1, sticky="w", pady=7)

        self.dry_run_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(opt, text="Dry run (preview only)", variable=self.dry_run_var,
                      font=self.f_label, text_color=TXT, progress_color=ACCENT,
                      button_color=TXT, fg_color=STROKE).grid(
            row=1, column=2, columnspan=2, sticky="e", padx=(0, 16), pady=7)

        ctk.CTkLabel(opt, text="Model", font=self.f_label, text_color=MUTED).grid(
            row=2, column=0, sticky="w", padx=(16, 8), pady=(7, 14))
        mf = ctk.CTkFrame(opt, fg_color="transparent")
        mf.grid(row=2, column=1, columnspan=3, sticky="w", pady=(7, 14))
        self.model_var = ctk.StringVar(value=self.settings.get("model", "claude-opus-4-7"))
        model_values = self.settings.get("model_list") or list(FALLBACK_MODELS)
        if self.model_var.get() not in model_values:
            model_values = [self.model_var.get(), *model_values]
        self.model_menu = ctk.CTkOptionMenu(
            mf, values=model_values, variable=self.model_var, width=260,
            fg_color=PANEL2, button_color=STROKE, button_hover_color=ACCENT,
            text_color=TXT, dropdown_fg_color=PANEL, dropdown_text_color=TXT,
            dropdown_hover_color=HOVER)
        self.model_menu.pack(side="left", padx=(0, 8))
        ctk.CTkButton(mf, text="↻", width=34, font=self.f_button,
                      fg_color=PANEL2, hover_color=HOVER, text_color=TXT,
                      border_width=1, border_color=STROKE,
                      command=lambda: self._refresh_models(silent=False)).pack(side="left")

        self.crop_btn = self._primary(left, "Crop Photos", self._run_crop, height=46)
        self.crop_btn.grid(row=2, column=0, sticky="ew", pady=(12, 0))

        # --- right: queue panel --------------------------------------------
        right = ctk.CTkFrame(tab, fg_color=PANEL, corner_radius=10, width=360,
                             border_width=1, border_color=STROKE)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 6))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="QUEUE", font=self.f_section, text_color=MUTED).grid(
            row=0, column=0, sticky="w")
        self.queue_count = ctk.CTkLabel(hdr, text="0", font=self.f_button,
                                        text_color=ACCENT)
        self.queue_count.grid(row=0, column=1, sticky="e")

        btns = ctk.CTkFrame(right, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(0, 8))
        self._ghost(btns, "Add Files", self._add_crop_files, width=98).pack(side="left", padx=(0, 6))
        self._ghost(btns, "Add Folder", self._add_crop_folder, width=104).pack(side="left", padx=(0, 6))
        self._ghost(btns, "Clear", self._clear_crop_files, width=62).pack(side="left")

        self.queue_list = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.queue_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    # -- queue rows ----------------------------------------------------------

    def _add_item(self, path: str):
        if path in self.item_by_path:
            return
        row = ctk.CTkFrame(self.queue_list, fg_color="transparent", corner_radius=8,
                           height=72)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)
        thumb = ctk.CTkLabel(row, text="", width=58, height=34, fg_color=THUMB,
                             corner_radius=4)
        thumb.place(x=10, y=19)
        disp_name = Path(path).name
        if len(disp_name) > 28:
            disp_name = disp_name[:25] + "…"
        name = ctk.CTkLabel(row, text=disp_name, font=self.f_mono,
                            text_color=MUTED, anchor="w")
        name.place(x=80, y=5)
        status = ctk.CTkLabel(row, text="● queued", font=self.f_small,
                              text_color=DIM, anchor="w")
        status.place(x=80, y=26)
        subject_emoji_lbl = ctk.CTkLabel(row, text="", font=self.f_emoji, anchor="w")
        subject_emoji_lbl.place(x=80, y=48)
        subject_lbl = ctk.CTkLabel(row, text="", font=self.f_small,
                                   text_color=DIM, anchor="w")
        subject_lbl.place(x=98, y=48)
        size_lbl = ctk.CTkLabel(row, text="", font=self.f_small,
                                text_color=DIM, anchor="e")
        size_lbl.place(relx=1.0, x=-10, y=10, anchor="ne")

        item = {"path": path, "status": "queued", "result": None, "row": row,
                "thumb": thumb, "name": name, "status_lbl": status,
                "subject_emoji_lbl": subject_emoji_lbl, "subject_lbl": subject_lbl,
                "size_lbl": size_lbl, "thumb_img": None}
        for w in (row, thumb, name, status, subject_emoji_lbl, subject_lbl, size_lbl):
            w.bind("<Button-1>", lambda e, p=path: self._select_item(p))
            w.bind("<Enter>", lambda e, it=item: self._row_hover(it, True))
            w.bind("<Leave>", lambda e, it=item: self._row_hover(it, False))

        self.items.append(item)
        self.item_by_path[path] = item
        self._request_thumb(path)

    def _row_hover(self, item, on):
        if item["path"] == self.current_path:
            return
        item["row"].configure(fg_color=HOVER if on else "transparent")

    def _update_row(self, item):
        result = item.get("result")
        status_map = {
            "queued":    ("● queued", DIM),
            "now":       ("● analyzing…", ACCENT),
            "analyzing": ("● analyzing…", ACCENT),
            "cropped":   ("● cropped", DONE),
            "dry_run":   ("● preview ready", DONE),
            "failed":    ("● failed", ERRC),
        }
        text, color = status_map.get(item["status"], ("● queued", DIM))
        if result and result.crop_warning and item["status"] in ("cropped", "dry_run"):
            text = text.replace("●", "⚠", 1)
            color = WARN
        item["status_lbl"].configure(text=text, text_color=color)
        item["name"].configure(
            text_color=TXT if item["path"] == self.current_path else MUTED)

        # Subject label — shown once a crop result is available
        if result and result.subject and item["status"] in ("cropped", "dry_run"):
            item["subject_emoji_lbl"].configure(text=subject_emoji(result.subject))
            item["subject_lbl"].configure(text=result.subject, text_color=DIM)
        else:
            item["subject_emoji_lbl"].configure(text="")
            item["subject_lbl"].configure(text="")

        # File size badge with traffic-light colouring
        if result and result.output_size_bytes and item["status"] == "cropped":
            mb = result.output_size_bytes / 1024 / 1024
            q = result.compression_quality
            size_text = f"{mb:.1f} MB"
            if q is not None and q < 70:
                size_color = ERRC
            elif q is not None and q < 95:
                size_color = WARN
            else:
                size_color = DONE
            item["size_lbl"].configure(text=size_text, text_color=size_color)
        else:
            item["size_lbl"].configure(text="")

    def _select_item(self, path: str):
        self.current_path = path
        for it in self.items:
            sel = it["path"] == path
            it["row"].configure(fg_color=SEL if sel else "transparent")
            it["name"].configure(text_color=TXT if sel else MUTED)
        self._render_preview(self.item_by_path.get(path))

    def _refresh_count(self):
        self.queue_count.configure(text=str(len(self.items)))

    # -- thumbnails (generated off the UI thread) ----------------------------

    def _request_thumb(self, path: str):
        if path not in self._thumb_requested:
            self._thumb_requested.add(path)
            self.thumb_jobs.put(path)

    def _thumb_worker(self):
        while True:
            path = self.thumb_jobs.get()
            try:
                im = make_thumbnail(path)
                self.thumb_ready.put((path, im))
            except Exception:
                pass

    # =======================================================================
    # Preview rendering
    # =======================================================================

    def _on_canvas_resize(self, _event=None):
        if self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(
            60, lambda: self._render_preview(self.item_by_path.get(self.current_path)))

    def _get_preview_image(self, path: str):
        cached = self._preview_cache.get(path)
        if cached:
            return cached
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            orig = im.size
            if max(orig) > PREVIEW_MAX_PX:
                im = im.copy()
                im.thumbnail((PREVIEW_MAX_PX, PREVIEW_MAX_PX), Image.LANCZOS)
            else:
                im = im.copy()
        self._preview_cache[path] = (im, orig)
        return self._preview_cache[path]

    def _render_preview(self, item):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20 or h < 20:
            return
        c.delete("all")

        if not item:
            self._draw_placeholder(w, h, "Add photos to preview the 16:9 crop")
            return

        path = item["path"]
        try:
            pil, (ow, oh) = self._get_preview_image(path)
        except Exception as exc:
            self._draw_placeholder(w, h, f"Could not open image\n{exc}")
            return

        m = 12
        scale = min((w - 2 * m) / ow, (h - 2 * m) / oh)
        dw, dh = max(1, round(ow * scale)), max(1, round(oh * scale))
        ox, oy = (w - dw) / 2, (h - dh) / 2

        disp = pil.resize((dw, dh), Image.LANCZOS)
        self._tk_preview = ImageTk.PhotoImage(disp)
        c.create_image(ox, oy, anchor="nw", image=self._tk_preview)

        result = item.get("result")
        if result and result.box:
            l, u, r, b = result.box
            x1, y1 = ox + l * scale, oy + u * scale
            x2, y2 = ox + r * scale, oy + b * scale
            # rule of thirds — only shown once a crop result exists
            for i in (1, 2):
                c.create_line(ox + dw * i / 3, oy, ox + dw * i / 3, oy + dh,
                              fill="#ffffff", width=1, stipple="gray25")
                c.create_line(ox, oy + dh * i / 3, ox + dw, oy + dh * i / 3,
                              fill="#ffffff", width=1, stipple="gray25")
            # dim everything outside the crop
            for rx1, ry1, rx2, ry2 in (
                (ox, oy, ox + dw, y1), (ox, y2, ox + dw, oy + dh),
                (ox, y1, x1, y2), (x2, y1, ox + dw, y2),
            ):
                if rx2 - rx1 > 0.5 and ry2 - ry1 > 0.5:
                    c.create_rectangle(rx1, ry1, rx2, ry2, fill=BG, outline="",
                                       stipple="gray50")
            c.create_rectangle(x1, y1, x2, y2, outline=ACCENT, width=2)
            for hx in (x1, x2):
                for hy in (y1, y2):
                    c.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4,
                                       fill=ACCENT, outline="")
            if result.focal:
                fx, fy = result.focal
                fxp = ox + (fx / 100 * ow) * scale
                fyp = oy + (fy / 100 * oh) * scale
                # dark underlay so the marker reads over any photo
                c.create_line(fxp - 16, fyp, fxp + 16, fyp, fill="#000000", width=3)
                c.create_line(fxp, fyp - 16, fxp, fyp + 16, fill="#000000", width=3)
                c.create_oval(fxp - 9, fyp - 9, fxp + 9, fyp + 9, outline="#000000", width=4)
                c.create_line(fxp - 16, fyp, fxp + 16, fyp, fill=ACCENT, width=1)
                c.create_line(fxp, fyp - 16, fxp, fyp + 16, fill=ACCENT, width=1)
                c.create_oval(fxp - 9, fyp - 9, fxp + 9, fyp + 9, outline=ACCENT, width=2)
                label = f"target  {fx:.0f}%, {fy:.0f}%"
                label_x = fxp + 14
                if result.subject:
                    emoji = subject_emoji(result.subject)
                    label = f"{result.subject}  ·  {fx:.0f}%, {fy:.0f}%"
                    # Drawn separately, in its native colors instead of the
                    # accent tint, since Courier New has no emoji glyphs.
                    self._otext(label_x, fyp - 14, emoji, ACCENT, self.f_emoji, anchor="w")
                    label_x += self.f_emoji.measure(emoji) + 6
                self._otext(label_x, fyp - 14, label,
                            ACCENT, ("Courier New", 10), anchor="w")
                if result.crop_warning:
                    first_reason = result.crop_warning.split(";")[0].strip()
                    self._otext(x1 + 6, y1 + 14, f"⚠ {first_reason}",
                                WARN, ("Courier New", 9), anchor="w")
        elif item["status"] in ("now", "analyzing"):
            c.create_rectangle(ox + 10, oy + 10, ox + 132, oy + 36,
                               fill=PANEL, outline=ACCENT, width=1)
            c.create_text(ox + 20, oy + 23, anchor="w", fill=ACCENT,
                          font=("Courier New", 11, "bold"), text="ANALYZING…")
        elif item["status"] == "failed":
            c.create_rectangle(ox, oy, ox + dw, oy + dh, fill=BG, outline="",
                               stipple="gray50")
            err = (item.get("result").error if item.get("result") else "") or "could not crop"
            c.create_text(ox + dw / 2, oy + dh / 2, fill=ERRC,
                          font=("Courier New", 12, "bold"),
                          text=f"FAILED\n{err}", justify="center", width=dw - 40)

        # filename + dimensions overlay
        self._otext(ox + 8, oy + dh - 12, Path(path).name,
                    "#ffffff", ("Courier New", 11), anchor="w")
        self._otext(ox + dw - 8, oy + dh - 12, f"{ow} × {oh}  →  16:9",
                    "#cfd2e0", ("Courier New", 10), anchor="e")
        # click-to-move hint — only shown when a crop result exists
        if result and result.box:
            self._otext(ox + dw / 2, oy + 14, "click to move target",
                        DIM, ("Courier New", 9), anchor="center")

    def _otext(self, x, y, text, fill, font, anchor="w"):
        """Draw text with a 1px black halo so it stays legible over photos."""
        c = self.canvas
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
            c.create_text(x + dx, y + dy, anchor=anchor, fill="#000000",
                          font=font, text=text)
        c.create_text(x, y, anchor=anchor, fill=fill, font=font, text=text)

    def _on_preview_click(self, event):
        """Move the target point to the clicked position and re-crop."""
        item = self.item_by_path.get(self.current_path) if self.current_path else None
        if not item or not item.get("result") or not item["result"].box:
            return
        result = item["result"]
        # Convert canvas pixel → image percentage
        c = self.canvas
        cw, ch = c.winfo_width(), c.winfo_height()
        try:
            pil, (ow, oh) = self._get_preview_image(self.current_path)
        except Exception:
            return
        m = 12
        scale = min((cw - 2 * m) / ow, (ch - 2 * m) / oh)
        dw, dh = max(1, round(ow * scale)), max(1, round(oh * scale))
        ox, oy = (cw - dw) / 2, (ch - dh) / 2
        ix, iy = event.x - ox, event.y - oy
        if ix < 0 or iy < 0 or ix > dw or iy > dh:
            return  # click outside image
        fx = (ix / dw) * 100
        fy = (iy / dh) * 100
        # Update result immediately so preview redraws without API call
        new_box, _ = compute_crop_box(ow, oh, fx, fy)
        item["result"] = CropResult(
            path=result.path, status=result.status,
            width=ow, height=oh,
            focal=(fx, fy), box=new_box,
            output_path=result.output_path,
            subject=result.subject,
            confidence=result.confidence,
            focal_box=result.focal_box,
            crop_warning=result.crop_warning,
        )
        self._render_preview(item)
        # Re-save in background (skip if dry run or no output path)
        if result.output_path and result.status != "dry_run":
            self._log(f"Re-cropping with new target ({fx:.0f}%, {fy:.0f}%)…")
            def _worker(ip=result.path, op=result.output_path, sx=fx, sy=fy, sub=result.subject):
                try:
                    recrop_image(ip, op, sx, sy, subject=sub)
                    self.log_queue.put(f"  ✓ Re-saved {Path(op).name}")
                except Exception as exc:
                    self.log_queue.put(f"  ✗ Re-crop failed: {exc}")
            threading.Thread(target=_worker, daemon=True).start()
        elif result.status == "dry_run":
            self._log(f"Target moved to ({fx:.0f}%, {fy:.0f}%) — dry run, no file written")

    def _draw_placeholder(self, w, h, text):
        c = self.canvas
        bw = min(w - 80, (h - 80) * 16 / 9)
        bw = max(120, bw)
        bh = bw * 9 / 16
        x1, y1 = (w - bw) / 2, (h - bh) / 2
        c.create_rectangle(x1, y1, x1 + bw, y1 + bh, outline=STROKE, width=2,
                           dash=(6, 4))
        for i in (1, 2):
            c.create_line(x1 + bw * i / 3, y1, x1 + bw * i / 3, y1 + bh,
                          fill=STROKE, width=1)
            c.create_line(x1, y1 + bh * i / 3, x1 + bw, y1 + bh * i / 3,
                          fill=STROKE, width=1)
        c.create_text(w / 2, y1 + bh + 28, fill=MUTED, font=("Courier New", 12),
                      text=text, justify="center", width=w - 80)

    # =======================================================================
    # Send tab
    # =======================================================================

    def _build_send_tab(self, tab):
        body = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)

        c = self._card(body, "Photos to send")
        ctk.CTkLabel(c, text="Folder", font=self.f_label, text_color=MUTED,
                     anchor="w").grid(row=0, column=0, sticky="w", pady=7)
        ff = ctk.CTkFrame(c, fg_color="transparent")
        ff.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=7)
        ff.grid_columnconfigure(0, weight=1)
        self.send_dir_var = ctk.StringVar(value=self.settings.get("send_dir", ""))
        self._entry(ff, self.send_dir_var,
                    "Select a folder of photos to email").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._ghost(ff, "Browse", self._browse_send_dir, width=84).grid(row=0, column=1)

        d = self._card(body, "Delivery")
        ctk.CTkLabel(d, text="To", font=self.f_label, text_color=MUTED,
                     anchor="w").grid(row=0, column=0, sticky="w", pady=7)
        self.send_to_var = ctk.StringVar(value=self.settings.get("to_email", DEFAULT_TO))
        self._entry(d, self.send_to_var).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=7)

        ctk.CTkLabel(d, text="From", font=self.f_label, text_color=MUTED,
                     anchor="w").grid(row=1, column=0, sticky="w", pady=7)
        self.send_from_label = ctk.CTkLabel(
            d, text=self.settings.get("from_email") or "(set in Settings)",
            anchor="w", font=self.f_label, text_color=MUTED)
        self.send_from_label.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=7)
        ctk.CTkLabel(d, text="From address & app password live in the Settings tab.",
                     font=self.f_small, text_color=DIM, anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.send_btn = self._primary(body, "Send Photos", self._run_send, height=46)
        self.send_btn.pack(fill="x", pady=(2, 8))

    # =======================================================================
    # Settings tab
    # =======================================================================

    def _build_settings_tab(self, tab):
        body = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self.settings_vars: dict[str, ctk.StringVar] = {}

        def add_field(parent, row, label, key, hidden, hint):
            ctk.CTkLabel(parent, text=label, font=self.f_label, text_color=MUTED,
                         anchor="w").grid(row=row, column=0, sticky="w", pady=7)
            var = ctk.StringVar(value=self.settings.get(key, ""))
            self.settings_vars[key] = var
            ef = ctk.CTkFrame(parent, fg_color="transparent")
            ef.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=7)
            ef.grid_columnconfigure(0, weight=1)
            entry = self._entry(ef, var, show="●" if hidden else "")
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 8) if hidden else 0)
            if hidden:
                btn = self._ghost(ef, "Show", None, width=58, height=28)
                btn.configure(command=lambda e=entry, b=btn: self._toggle_show(e, b))
                btn.grid(row=0, column=1)
            if hint:
                ctk.CTkLabel(parent, text=hint, font=self.f_small, text_color=DIM,
                             anchor="w", wraplength=300, justify="left").grid(
                    row=row, column=2, sticky="w", padx=(12, 0), pady=7)

        cred = self._card(body, "Credentials")
        cred.grid_columnconfigure(1, weight=1)
        add_field(cred, 0, "Anthropic API Key", "api_key", True, "From console.anthropic.com")
        add_field(cred, 1, "Yahoo App Password", "smtp_password", True,
                  "myaccount.yahoo.com → Security → App passwords")

        email = self._card(body, "Email")
        email.grid_columnconfigure(1, weight=1)
        add_field(email, 0, "From Email", "from_email", False, "Your Yahoo address")
        add_field(email, 1, "To Email", "to_email", False, "")
        add_field(email, 2, "SMTP Host", "smtp_host", False, "")
        add_field(email, 3, "SMTP Port", "smtp_port", False, "")

        adv = self._card(body, "Sending behavior")
        adv.grid_columnconfigure(1, weight=1)
        add_field(adv, 0, "Retry Attempts", "max_retries", False, "Per photo on rate limit (default 12)")
        add_field(adv, 1, "Retry Delay (secs)", "retry_delay", False, "Wait between retries (default 300)")

        self._build_prompt_lab_card(body)

        self._primary(body, "Save Settings", self._save_settings, height=46).pack(
            fill="x", pady=(2, 6))
        ctk.CTkLabel(body, text=f"Saved to {SETTINGS_FILE}", font=self.f_small,
                     text_color=DIM, anchor="w").pack(fill="x")

    # =======================================================================
    # Prompt Lab — compares wording variants of the focal-point prompt
    # =======================================================================

    def _build_prompt_lab_card(self, body):
        lab = self._card(body, "Prompt Lab (experimental)")
        lab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(lab, text="Test photos", font=self.f_label, text_color=MUTED,
                     anchor="w").grid(row=0, column=0, sticky="w", pady=7)
        lf = ctk.CTkFrame(lab, fg_color="transparent")
        lf.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=7)
        lf.grid_columnconfigure(0, weight=1)
        default_test_dir = Path(__file__).parent / "test_photos"
        self.eval_folder_var = ctk.StringVar(
            value=str(default_test_dir) if default_test_dir.is_dir() else "")
        self._entry(lf, self.eval_folder_var,
                    "Folder of sample photos").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._ghost(lf, "Browse", self._browse_eval_folder, width=84).grid(row=0, column=1)

        ctk.CTkLabel(lab, text="Prompt variants", font=self.f_label, text_color=MUTED,
                     anchor="nw").grid(row=1, column=0, sticky="nw", pady=7)
        vf = ctk.CTkFrame(lab, fg_color="transparent")
        vf.grid(row=1, column=1, sticky="w", pady=7)
        self.eval_variant_vars: dict[str, ctk.BooleanVar] = {}
        for i, name in enumerate(PROMPT_VARIANTS):
            var = ctk.BooleanVar(value=True)
            self.eval_variant_vars[name] = var
            ctk.CTkCheckBox(vf, text=name, variable=var, font=self.f_label,
                            text_color=TXT, fg_color=ACCENT, hover_color=ACCENT_HV,
                            border_color=STROKE, checkmark_color=ACCENT_INK).grid(
                row=i, column=0, sticky="w", pady=2)

        ctk.CTkLabel(lab, text="Test model", font=self.f_label, text_color=MUTED,
                     anchor="w").grid(row=2, column=0, sticky="w", pady=7)
        model_list = self.settings.get("model_list") or list(FALLBACK_MODELS)
        default_eval_model = (
            PROMPT_EVAL_DEFAULT_MODEL if PROMPT_EVAL_DEFAULT_MODEL in model_list
            else model_list[-1]
        )
        self.eval_model_var = ctk.StringVar(value=default_eval_model)
        eval_model_values = model_list if default_eval_model in model_list else [default_eval_model, *model_list]
        self.eval_model_menu = ctk.CTkOptionMenu(
            lab, values=eval_model_values, variable=self.eval_model_var, width=260,
            fg_color=PANEL2, button_color=STROKE, button_hover_color=ACCENT,
            text_color=TXT, dropdown_fg_color=PANEL, dropdown_text_color=TXT,
            dropdown_hover_color=HOVER)
        self.eval_model_menu.grid(row=2, column=1, sticky="w", pady=7)

        ctk.CTkLabel(
            lab, text="Compares prompt wordings on a small photo set and saves one "
            "side-by-side comparison image per photo to eval_out/ so you can pick "
            "the best crop by eye. One API call per photo per variant checked above.",
            font=self.f_small, text_color=DIM, anchor="w", wraplength=460, justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 8))

        self.prompt_eval_btn = self._primary(
            lab, "Run Prompt Test", self._run_prompt_eval, height=40)
        self.prompt_eval_btn.grid(row=4, column=0, columnspan=2, sticky="ew")

    def _browse_eval_folder(self):
        folder = filedialog.askdirectory(title="Select folder of test photos")
        if folder:
            self.eval_folder_var.set(folder)

    def _run_prompt_eval(self):
        if self._running:
            return
        api_key = self.settings_vars["api_key"].get().strip()
        if not api_key:
            messagebox.showerror("Missing API Key", "Enter your Anthropic API key above first.")
            return

        folder = self.eval_folder_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showwarning("No Folder", "Select a folder of test photos first.")
            return
        images = collect_images([folder], log=lambda _: None)
        if not images:
            messagebox.showwarning("No Photos", "No supported images found in that folder.")
            return

        variant_names = [name for name, var in self.eval_variant_vars.items() if var.get()]
        if not variant_names:
            messagebox.showwarning("No Variants", "Check at least one prompt variant to test.")
            return

        model = self.eval_model_var.get()
        n_calls = len(images) * len(variant_names)
        if not messagebox.askyesno(
            "Run Prompt Test",
            f"This will make {n_calls} API call(s) on {model}\n"
            f"({len(images)} photo(s) × {len(variant_names)} variant(s)).\n\nProceed?",
        ):
            return

        out_dir = Path(__file__).parent / "eval_out"
        self.progress.set(0)
        self.progress_count.configure(text=f"0 / {len(images)}")
        self._set_busy(True, "Testing prompts…")
        self._log(f"\n═══ Prompt test: {len(images)} photo(s) × {variant_names} on {model} ═══")

        def worker():
            try:
                outputs = run_prompt_eval(
                    images=images, variant_names=variant_names, model=model,
                    api_key=api_key, out_dir=out_dir,
                    log_fn=self._log, progress_fn=self._post_progress,
                )
            except Exception as exc:
                self._log(f"\nUnexpected error: {exc}")
                self.after(0, lambda: self._set_busy(False, "Error"))
            else:
                self._log(f"\n═══ Finished: {len(outputs)} comparison image(s) in {out_dir} ═══")
                self.after(0, lambda: self._set_busy(False, "Prompt test complete"))
                self.after(0, lambda: _open_folder(out_dir))

        threading.Thread(target=worker, daemon=True).start()

    # =======================================================================
    # File / folder pickers
    # =======================================================================

    def _add_crop_files(self):
        files = filedialog.askopenfilenames(
            title="Select photos",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.gif *.JPG *.JPEG *.PNG *.WEBP *.GIF"),
                ("All files", "*.*"),
            ],
        )
        added = self._ingest(files)
        if added:
            self._after_queue_change(select_first=added[0])

    def _add_crop_folder(self):
        folder = filedialog.askdirectory(title="Select folder of photos")
        if not folder:
            return
        paths = [str(p) for p in collect_images([folder], log=lambda _: None)]
        added = self._ingest(paths)
        if added:
            self._after_queue_change(select_first=added[0])

    def _ingest(self, paths) -> list[str]:
        added = []
        for f in paths:
            f = str(Path(f))  # normalise separators so keys match result.path on Windows
            if f not in self.item_by_path:
                self._add_item(f)
                added.append(f)
        return added

    def _after_queue_change(self, select_first=None):
        self._refresh_count()
        self._persist_paths()
        if select_first and self.current_path is None:
            self._select_item(select_first)

    def _clear_crop_files(self):
        for it in self.items:
            it["row"].destroy()
        self.items.clear()
        self.item_by_path.clear()
        self.current_path = None
        self._refresh_count()
        self._persist_paths()
        self._render_preview(None)

    def _browse_output_dir(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_dir_var.set(folder)
            self._persist_paths()

    def _browse_send_dir(self):
        folder = filedialog.askdirectory(title="Select folder of photos to send")
        if folder:
            self.send_dir_var.set(folder)
            self._persist_paths()

    # =======================================================================
    # Settings persistence
    # =======================================================================

    def _toggle_show(self, entry: ctk.CTkEntry, btn: ctk.CTkButton):
        if entry.cget("show") == "●":
            entry.configure(show="")
            btn.configure(text="Hide")
        else:
            entry.configure(show="●")
            btn.configure(text="Show")

    def _persist_paths(self):
        self.settings["crop_files"] = [it["path"] for it in self.items]
        self.settings["crop_output_dir"] = self.output_dir_var.get().strip()
        self.settings["send_dir"] = self.send_dir_var.get().strip()
        save_settings(self.settings)

    def _save_settings(self):
        for key, var in self.settings_vars.items():
            self.settings[key] = var.get().strip()
        self.settings["output_suffix"] = self.suffix_var.get().strip()
        self.settings["model"] = self.model_var.get()
        self._persist_paths()
        self.send_from_label.configure(text=self.settings.get("from_email") or "(set in Settings)")
        messagebox.showinfo("Saved", "Settings saved.")
        if self.settings.get("api_key", "").strip():
            self._refresh_models(silent=True)

    def _on_close(self):
        self.settings["output_suffix"] = self.suffix_var.get().strip()
        self.settings["model"] = self.model_var.get()
        self.settings["to_email"] = self.send_to_var.get().strip()
        self._persist_paths()
        self.destroy()

    # =======================================================================
    # Dynamic models
    # =======================================================================

    def _refresh_models(self, silent: bool):
        api_key = self.settings.get("api_key", "").strip()
        if not api_key:
            if not silent:
                messagebox.showwarning("No API Key", "Add your Anthropic API key in Settings first.")
            return
        if not silent:
            self.status_label.configure(text="Fetching available models…")

        def worker():
            models = list_models(api_key)
            self.after(0, lambda: self._apply_models(models, silent))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_models(self, models: list[str], silent: bool):
        current = self.model_var.get()
        if current and current not in models:
            models = [current, *models]
        self.model_menu.configure(values=models)
        self.settings["model_list"] = models
        save_settings(self.settings)
        if not silent:
            self.status_label.configure(text=f"Loaded {len(models)} models")

    # =======================================================================
    # Log / progress / result polling
    # =======================================================================

    def _log(self, msg: str):
        self.log_queue.put(str(msg))

    def _post_progress(self, done: int, total: int):
        self.progress_queue.put((done, total))

    def _post_result(self, result):
        self.result_queue.put(result)

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _poll_queues(self):
        # A failure anywhere below must never stop this from being rescheduled —
        # otherwise every queued UI update (thumbnails, progress, results) would
        # silently stop forever for the rest of the session.
        try:
            self._poll_queues_once()
        finally:
            self.after(80, self._poll_queues)

    def _poll_queues_once(self):
        # logs
        wrote = False
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if not wrote:
                    self.log_box.configure(state="normal")
                    wrote = True
                self.log_box.insert("end", msg if msg.endswith("\n") else msg + "\n")
        except queue.Empty:
            pass
        if wrote:
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        # progress (latest wins)
        latest = None
        try:
            while True:
                latest = self.progress_queue.get_nowait()
        except queue.Empty:
            pass
        if latest is not None:
            done, total = latest
            self.progress.set(done / total if total else 0)
            self.progress_count.configure(text=f"{done} / {total}" if total else "")

        # crop results
        try:
            while True:
                self._apply_result(self.result_queue.get_nowait())
        except queue.Empty:
            pass

        # thumbnails — each one is isolated so a single bad/corrupt image can't
        # drop the rest of the batch or (via the wrapper above) the whole poll loop.
        try:
            while True:
                path, pil = self.thumb_ready.get_nowait()
                item = self.item_by_path.get(path)
                if item:
                    try:
                        img = ctk.CTkImage(light_image=pil, dark_image=pil, size=THUMB_SIZE)
                        item["thumb_img"] = img
                        item["thumb"].configure(image=img, text="")
                    except Exception:
                        pass
        except queue.Empty:
            pass

    # How long to linger on a finished photo's crop preview before jumping to
    # the next one that has started analyzing (ms).
    _LINGER_MS = 1_800

    def _apply_result(self, result):
        item = self.item_by_path.get(str(Path(result.path)))
        if not item:
            return
        item["status"] = result.status
        if result.status == "analyzing":
            item["status"] = "now"
            self._update_row(item)
            # If the current photo already has a crop result, linger on it
            # briefly so the user can see the focal point before we move on.
            current = self.item_by_path.get(self.current_path) if self.current_path else None
            if current and current.get("result") and current["result"].box:
                self.after(self._LINGER_MS,
                           lambda p=result.path: self._select_item(p))
            else:
                self._select_item(result.path)
        else:
            item["result"] = result
            self._update_row(item)
            if result.path == self.current_path:
                self._render_preview(item)

    def _set_busy(self, busy: bool, status: str = "Ready"):
        self._running = busy
        state = "disabled" if busy else "normal"
        self.crop_btn.configure(state=state)
        self.send_btn.configure(state=state)
        self.prompt_eval_btn.configure(state=state)
        self.status_label.configure(text=status, text_color=ACCENT if busy else MUTED)

    # =======================================================================
    # Crop operation
    # =======================================================================

    def _run_crop(self):
        if self._running:
            return
        if not self.items:
            messagebox.showwarning("No Photos", "Add some photos to crop first.")
            return
        api_key = self.settings.get("api_key", "").strip()
        if not api_key:
            messagebox.showerror("Missing API Key", "Enter your Anthropic API key in Settings.")
            self._select_tab("Settings")
            return

        output_dir = self.output_dir_var.get().strip() or None
        suffix = self.suffix_var.get().strip() or "_16x9"
        model = self.model_var.get()
        dry_run = self.dry_run_var.get()
        files = [it["path"] for it in self.items]

        # Reset queue state for a fresh run (results will repopulate live).
        for it in self.items:
            it["status"] = "queued"
            it["result"] = None
            self._update_row(it)

        self.progress.set(0)
        self.progress_count.configure(text=f"0 / {len(files)}")
        self._set_busy(True, "Cropping…")
        self._log(f"\n═══ Cropping {len(files)} photo(s) ═══")

        def worker():
            try:
                failures, total = run_crop(
                    inputs=files, output_dir=output_dir, suffix=suffix,
                    model=model, dry_run=dry_run, api_key=api_key,
                    log_fn=self._log, progress_fn=self._post_progress,
                    result_fn=self._post_result,
                )
                self._summarize(failures, total, "cropped")
            except Exception as exc:
                self._log(f"\nUnexpected error: {exc}")
                self.after(0, lambda: self._set_busy(False, "Error"))
            else:
                done = total - len(failures)
                self.after(0, lambda: self._set_busy(False, f"Done — {done}/{total} cropped"))

        threading.Thread(target=worker, daemon=True).start()

    # =======================================================================
    # Send operation
    # =======================================================================

    def _run_send(self):
        if self._running:
            return
        send_dir = self.send_dir_var.get().strip()
        if not send_dir:
            messagebox.showwarning("No Folder", "Select a folder of photos to send.")
            return

        from_addr   = self.settings.get("from_email", "").strip()
        password    = self.settings.get("smtp_password", "").strip()
        to_addr     = self.send_to_var.get().strip()
        smtp_host   = self.settings.get("smtp_host", "smtp.mail.yahoo.com").strip()
        smtp_port   = int(self.settings.get("smtp_port", "587") or "587")
        max_retries = int(self.settings.get("max_retries", "12") or "12")
        retry_delay = int(self.settings.get("retry_delay", "300") or "300")

        if not from_addr:
            messagebox.showerror("Missing Email", "Enter your From email address in Settings.")
            self._select_tab("Settings")
            return
        if not password:
            messagebox.showerror("Missing Password", "Enter your Yahoo App Password in Settings.")
            self._select_tab("Settings")
            return

        self.progress.set(0)
        self.progress_count.configure(text="")
        self._set_busy(True, "Sending…")
        self._log("\n═══ Sending photos ═══")

        def worker():
            try:
                failures, total = run_send(
                    directory=send_dir, from_addr=from_addr, to_addr=to_addr,
                    smtp_host=smtp_host, smtp_port=smtp_port, password=password,
                    log_fn=self._log, max_retries=max_retries, retry_delay=retry_delay,
                    progress_fn=self._post_progress,
                )
                self._summarize(failures, total, "sent")
            except Exception as exc:
                self._log(f"\nUnexpected error: {exc}")
                self.after(0, lambda: self._set_busy(False, "Error"))
            else:
                done = total - len(failures)
                self.after(0, lambda: self._set_busy(False, f"Done — {done}/{total} sent"))

        threading.Thread(target=worker, daemon=True).start()

    def _summarize(self, failures, total, verb):
        done = total - len(failures)
        if failures:
            self._log(f"\n{len(failures)} could not be {verb}:")
            for name, err in failures:
                self._log(f"  • {name}: {err}")
        self._log(f"\n═══ Finished: {done}/{total} {verb} ═══")

        if verb == "cropped" and done > 0:
            # Subject breakdown
            subjects = Counter(
                it["result"].subject for it in self.items
                if it.get("result") and it["result"].subject
                and it["result"].status in ("cropped", "dry_run")
            )
            if subjects:
                parts = [f"{cnt} {subj}" for subj, cnt in subjects.most_common()]
                self._log("  " + "  ·  ".join(parts))

            # Compression summary — only photos that needed quality reduction
            compressed = [
                it["result"] for it in self.items
                if it.get("result")
                and it["result"].compression_quality is not None
                and it["result"].compression_quality < 95
                and it["result"].output_size_bytes is not None
            ]
            if compressed:
                min_q = min(r.compression_quality for r in compressed)
                avg_mb = (
                    sum(r.output_size_bytes for r in compressed)
                    / len(compressed) / 1024 / 1024
                )
                self._log(
                    f"  {len(compressed)}/{done} compressed to fit 24 MB limit"
                    f" — avg {avg_mb:.1f} MB, lowest quality: {min_q}"
                )

            # Warning tally
            warned = [
                it for it in self.items
                if it.get("result") and it["result"].crop_warning
            ]
            if warned:
                self._log(f"  ⚠ {len(warned)} photo(s) flagged for review — click to inspect")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
