#!/usr/bin/env python3
"""Skylight Cropping — desktop GUI."""

import json
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from smart_crop import collect_images, run_crop, run_send

# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

SETTINGS_FILE = Path.home() / ".skylight_cropping" / "settings.json"
DEFAULT_TO = "your-skylight-frame@example.com"
MODELS = ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]


def load_settings() -> dict:
    defaults = {
        "api_key": "",
        "smtp_password": "",
        "from_email": "",
        "to_email": DEFAULT_TO,
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": "587",
        "max_retries": "3",
        "retry_delay": "90",
        "model": "claude-opus-4-7",
        "output_suffix": "_16x9",
    }
    if SETTINGS_FILE.exists():
        try:
            stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            defaults.update(stored)
        except Exception:
            pass
    return defaults


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Skylight Cropping")
        self.geometry("940x740")
        self.minsize(780, 640)

        self.settings = load_settings()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.crop_files: list[str] = []
        self._running = False

        self._build_ui()
        self._poll_log()

    # -------------------------------------------------------------------------
    # Layout
    # -------------------------------------------------------------------------

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        for name in ("Crop", "Send", "Settings"):
            self.tabs.add(name)

        self._build_crop_tab(self.tabs.tab("Crop"))
        self._build_send_tab(self.tabs.tab("Send"))
        self._build_settings_tab(self.tabs.tab("Settings"))

        # Shared log + progress bar at the bottom
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bottom, text="Log", anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.log_box = ctk.CTkTextbox(
            bottom, height=165, state="disabled",
            font=ctk.CTkFont(family="Courier New", size=11),
        )
        self.log_box.grid(row=1, column=0, sticky="ew")

        self.progress = ctk.CTkProgressBar(bottom, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.progress.grid_remove()

    # -- Crop tab -------------------------------------------------------------

    def _build_crop_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        row = 0

        self.crop_count_label = ctk.CTkLabel(
            tab, text="Input Photos — 0 selected", anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.crop_count_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row += 1

        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ctk.CTkButton(btn_row, text="Add Files",   width=100, command=self._add_crop_files).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Add Folder",  width=100, command=self._add_crop_folder).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Clear",       width=80,  command=self._clear_crop_files,
                      fg_color="transparent", border_width=1).pack(side="left")
        row += 1

        self.crop_list = ctk.CTkTextbox(
            tab, height=110, state="disabled",
            font=ctk.CTkFont(family="Courier New", size=11),
        )
        self.crop_list.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        row += 1

        # Output folder
        ctk.CTkLabel(tab, text="Output Folder", anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        out_frame = ctk.CTkFrame(tab, fg_color="transparent")
        out_frame.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=5)
        out_frame.grid_columnconfigure(0, weight=1)
        self.output_dir_var = ctk.StringVar()
        ctk.CTkEntry(out_frame, textvariable=self.output_dir_var,
                     placeholder_text="Same folder as source files (default)").grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(out_frame, text="Browse", width=80, command=self._browse_output_dir).grid(row=0, column=1)
        row += 1

        # Suffix
        ctk.CTkLabel(tab, text="Output Suffix", anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        self.suffix_var = ctk.StringVar(value=self.settings.get("output_suffix", "_16x9"))
        ctk.CTkEntry(tab, textvariable=self.suffix_var, width=120).grid(
            row=row, column=1, sticky="w", padx=(8, 0), pady=5)
        row += 1

        # Model
        ctk.CTkLabel(tab, text="Model", anchor="w").grid(row=row, column=0, sticky="w", pady=5)
        self.model_var = ctk.StringVar(value=self.settings.get("model", "claude-opus-4-7"))
        ctk.CTkOptionMenu(tab, values=MODELS, variable=self.model_var, width=280).grid(
            row=row, column=1, sticky="w", padx=(8, 0), pady=5)
        row += 1

        # Dry run
        self.dry_run_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            tab, text="Dry run — preview crop boxes without writing files",
            variable=self.dry_run_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        row += 1

        self.crop_btn = ctk.CTkButton(tab, text="Crop Photos", height=42, command=self._run_crop)
        self.crop_btn.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(14, 0))

    # -- Send tab -------------------------------------------------------------

    def _build_send_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        row = 0

        # Photos folder
        ctk.CTkLabel(tab, text="Photos Folder", anchor="w").grid(row=row, column=0, sticky="w", pady=6)
        folder_frame = ctk.CTkFrame(tab, fg_color="transparent")
        folder_frame.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=6)
        folder_frame.grid_columnconfigure(0, weight=1)
        self.send_dir_var = ctk.StringVar()
        ctk.CTkEntry(folder_frame, textvariable=self.send_dir_var,
                     placeholder_text="Select folder of photos...").grid(
            row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(folder_frame, text="Browse", width=80, command=self._browse_send_dir).grid(row=0, column=1)
        row += 1

        # To
        ctk.CTkLabel(tab, text="To", anchor="w").grid(row=row, column=0, sticky="w", pady=6)
        self.send_to_var = ctk.StringVar(value=self.settings.get("to_email", DEFAULT_TO))
        ctk.CTkEntry(tab, textvariable=self.send_to_var).grid(
            row=row, column=1, sticky="ew", padx=(8, 0), pady=6)
        row += 1

        # From (read-only, sourced from Settings)
        ctk.CTkLabel(tab, text="From", anchor="w").grid(row=row, column=0, sticky="w", pady=6)
        self.send_from_label = ctk.CTkLabel(
            tab,
            text=self.settings.get("from_email") or "(configure in Settings)",
            anchor="w",
            text_color=("gray40", "gray60"),
        )
        self.send_from_label.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=6)
        row += 1

        ctk.CTkLabel(
            tab,
            text="From address and App Password are configured in the Settings tab.",
            anchor="w",
            text_color=("gray40", "gray60"),
            font=ctk.CTkFont(size=11),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 14))
        row += 1

        self.send_btn = ctk.CTkButton(tab, text="Send Photos", height=42, command=self._run_send)
        self.send_btn.grid(row=row, column=0, columnspan=2, sticky="ew")

    # -- Settings tab ---------------------------------------------------------

    def _build_settings_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)

        fields = [
            ("Anthropic API Key",  "api_key",       True,  "Get yours at console.anthropic.com"),
            ("Yahoo App Password", "smtp_password",  True,  "myaccount.yahoo.com → Security → App passwords"),
            ("From Email",         "from_email",     False, "Your Yahoo address"),
            ("To Email",           "to_email",       False, ""),
            ("SMTP Host",          "smtp_host",      False, ""),
            ("SMTP Port",          "smtp_port",      False, ""),
            ("Retry Attempts",     "max_retries",    False, "Per photo on rate limit error (default: 3)"),
            ("Retry Delay (secs)", "retry_delay",    False, "Wait between retries (default: 90)"),
        ]
        self.settings_vars: dict[str, ctk.StringVar] = {}

        for row, (label, key, hidden, hint) in enumerate(fields):
            ctk.CTkLabel(tab, text=label, anchor="w").grid(row=row, column=0, sticky="w", pady=6)
            var = ctk.StringVar(value=self.settings.get(key, ""))
            self.settings_vars[key] = var

            entry_frame = ctk.CTkFrame(tab, fg_color="transparent")
            entry_frame.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=6)
            entry_frame.grid_columnconfigure(0, weight=1)

            entry = ctk.CTkEntry(entry_frame, textvariable=var, show="●" if hidden else "")
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 6) if hidden else 0)

            if hidden:
                # Show / Hide toggle
                show_btn = ctk.CTkButton(
                    entry_frame, text="Show", width=60,
                    fg_color="transparent", border_width=1,
                    command=lambda e=entry, b=None: self._toggle_show(e),
                )
                show_btn.grid(row=0, column=1)
                # Store reference so toggle can flip the label
                show_btn.configure(command=lambda e=entry, b=show_btn: self._toggle_show(e, b))

            if hint:
                ctk.CTkLabel(
                    tab, text=hint, anchor="w",
                    text_color=("gray40", "gray60"), font=ctk.CTkFont(size=10),
                ).grid(row=row, column=2, sticky="w", padx=(6, 0), pady=6)

        save_row = len(fields)
        ctk.CTkButton(
            tab, text="Save Settings", height=42, command=self._save_settings
        ).grid(row=save_row, column=0, columnspan=2, sticky="ew", pady=(18, 4))

        ctk.CTkLabel(
            tab, text=f"Settings file: {SETTINGS_FILE}",
            anchor="w", text_color=("gray40", "gray60"), font=ctk.CTkFont(size=10),
        ).grid(row=save_row + 1, column=0, columnspan=3, sticky="w")

    # -------------------------------------------------------------------------
    # File / folder pickers
    # -------------------------------------------------------------------------

    def _add_crop_files(self):
        files = filedialog.askopenfilenames(
            title="Select photos",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.gif *.JPG *.JPEG *.PNG *.WEBP *.GIF"),
                ("All files", "*.*"),
            ],
        )
        added = sum(1 for f in files if f not in self.crop_files or not self.crop_files.append(f))
        # simpler:
        before = len(self.crop_files)
        for f in files:
            if f not in self.crop_files:
                self.crop_files.append(f)
        if len(self.crop_files) > before:
            self._refresh_crop_list()

    def _add_crop_folder(self):
        folder = filedialog.askdirectory(title="Select folder of photos")
        if not folder:
            return
        new_paths = collect_images([folder], log=lambda _: None)
        before = len(self.crop_files)
        for p in new_paths:
            if str(p) not in self.crop_files:
                self.crop_files.append(str(p))
        if len(self.crop_files) > before:
            self._refresh_crop_list()

    def _clear_crop_files(self):
        self.crop_files.clear()
        self._refresh_crop_list()

    def _refresh_crop_list(self):
        count = len(self.crop_files)
        self.crop_count_label.configure(text=f"Input Photos — {count} selected")
        self.crop_list.configure(state="normal")
        self.crop_list.delete("1.0", "end")
        for f in self.crop_files:
            self.crop_list.insert("end", Path(f).name + "\n")
        self.crop_list.configure(state="disabled")

    def _browse_output_dir(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_dir_var.set(folder)

    def _browse_send_dir(self):
        folder = filedialog.askdirectory(title="Select folder of photos to send")
        if folder:
            self.send_dir_var.set(folder)

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    def _toggle_show(self, entry: ctk.CTkEntry, btn: ctk.CTkButton):
        if entry.cget("show") == "●":
            entry.configure(show="")
            btn.configure(text="Hide")
        else:
            entry.configure(show="●")
            btn.configure(text="Show")

    def _save_settings(self):
        for key, var in self.settings_vars.items():
            self.settings[key] = var.get().strip()
        save_settings(self.settings)
        self.send_from_label.configure(
            text=self.settings.get("from_email") or "(configure in Settings)"
        )
        messagebox.showinfo("Saved", "Settings saved.")

    # -------------------------------------------------------------------------
    # Log + progress
    # -------------------------------------------------------------------------

    def _log(self, msg: str):
        self.log_queue.put(str(msg))

    def _poll_log(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.log_box.insert("end", msg if msg.endswith("\n") else msg + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _set_busy(self, busy: bool):
        self._running = busy
        state = "disabled" if busy else "normal"
        self.crop_btn.configure(state=state)
        self.send_btn.configure(state=state)
        if busy:
            self.progress.grid()
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.grid_remove()

    # -------------------------------------------------------------------------
    # Crop operation
    # -------------------------------------------------------------------------

    def _run_crop(self):
        if self._running:
            return
        if not self.crop_files:
            messagebox.showwarning("No Photos", "Please add photos to crop first.")
            return
        api_key = self.settings.get("api_key", "").strip()
        if not api_key:
            messagebox.showerror("Missing API Key",
                                 "Enter your Anthropic API key in the Settings tab.")
            self.tabs.set("Settings")
            return

        output_dir = self.output_dir_var.get().strip() or None
        suffix = self.suffix_var.get().strip() or "_16x9"
        model = self.model_var.get()
        dry_run = self.dry_run_var.get()
        files = list(self.crop_files)

        self._set_busy(True)
        self._log(f"\n── Crop started — {len(files)} photo(s) ──")

        def worker():
            try:
                failures, total = run_crop(
                    inputs=files,
                    output_dir=output_dir,
                    suffix=suffix,
                    model=model,
                    dry_run=dry_run,
                    api_key=api_key,
                    log_fn=self._log,
                )
                if failures:
                    self._log(f"\nFailed ({len(failures)}):")
                    for name, err in failures:
                        self._log(f"  {name}: {err}")
                self._log(f"\n── Finished: {total - len(failures)}/{total} cropped ──")
            except Exception as exc:
                self._log(f"\nUnexpected error: {exc}")
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------------------
    # Send operation
    # -------------------------------------------------------------------------

    def _run_send(self):
        if self._running:
            return
        send_dir = self.send_dir_var.get().strip()
        if not send_dir:
            messagebox.showwarning("No Folder", "Please select a folder of photos to send.")
            return

        from_addr   = self.settings.get("from_email", "").strip()
        password    = self.settings.get("smtp_password", "").strip()
        to_addr     = self.send_to_var.get().strip()
        smtp_host   = self.settings.get("smtp_host", "smtp.mail.yahoo.com").strip()
        smtp_port   = int(self.settings.get("smtp_port", "587") or "587")
        max_retries = int(self.settings.get("max_retries", "3") or "3")
        retry_delay = int(self.settings.get("retry_delay", "90") or "90")

        if not from_addr:
            messagebox.showerror("Missing Email",
                                 "Enter your From email address in the Settings tab.")
            self.tabs.set("Settings")
            return
        if not password:
            messagebox.showerror("Missing Password",
                                 "Enter your Yahoo App Password in the Settings tab.")
            self.tabs.set("Settings")
            return

        self._set_busy(True)
        self._log(f"\n── Send started ──")

        def worker():
            try:
                failures, total = run_send(
                    directory=send_dir,
                    from_addr=from_addr,
                    to_addr=to_addr,
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    password=password,
                    log_fn=self._log,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                )
                if failures:
                    self._log(f"\nFailed ({len(failures)}):")
                    for name, err in failures:
                        self._log(f"  {name}: {err}")
                self._log(f"\n── Finished: {total - len(failures)}/{total} sent ──")
            except Exception as exc:
                self._log(f"\nUnexpected error: {exc}")
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
