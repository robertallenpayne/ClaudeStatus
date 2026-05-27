#!/usr/bin/env python3
"""Claude Code & API status widget."""

import json
import os
import subprocess
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

CACHE_FILE  = os.path.expanduser("~/.claude/statusline-data.json")
CONFIG_FILE = os.path.expanduser("~/.claude/status-widget.json")
BILLING_URL = "https://console.anthropic.com/settings/billing"
REFRESH_MS  = 30_000

# Hot-corner HUD behavior
POLL_MS       = 120     # how often the watcher samples the cursor position
HIDE_GRACE_MS = 400     # keep the HUD up this long after the cursor leaves it
PEEK_MS       = 2500    # show on launch this long so it's clear the app is running
MENU_PIN_MS   = 2500    # keep the HUD pinned this long after a menu opens
HOT_ZONE      = 6       # size of the top-right trigger square, in px
MENUBAR_H     = 28      # tuck the HUD this far below the top edge (under the menu bar)
EDGE_MARGIN   = 6       # gap from the right screen edge

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG     = "#0f0f1a"
CARD   = "#1a1a2e"
MUTED  = "#94a3b8"   # secondary text & icon buttons (lightened for readability)
LABEL  = "#cbd5e1"   # section captions & bar labels
TEXT   = "#e2e8f0"
PURPLE = "#a78bfa"
GREEN  = "#4ade80"
YELLOW = "#fbbf24"
RED    = "#f87171"

# Per-mode window sizing (width, height). Min sizes stop the window from
# being saved/restored at an unusably small size.
FULL_DEFAULT    = (310, 360)
FULL_MIN        = (300, 340)
COMPACT_DEFAULT = (430, 44)
COMPACT_MIN     = (400, 40)


def _bar_color(pct: float) -> str:
    if pct < 60:
        return GREEN
    if pct < 85:
        return YELLOW
    return RED


def _load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


class Widget(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._cfg = _load_config()
        self._compact = self._cfg.get("compact", False)

        self.title("Claude Status")
        self.configure(fg_color=BG)

        self._job = None
        self._watch_job = None
        self._visible = False
        self._peeking = False           # forces the HUD to stay up during the launch peek
        self._pin = 0                   # >0 keeps the HUD up while a menu/dialog is open
        self._leave_count = 0
        self._grace_ticks = max(1, HIDE_GRACE_MS // POLL_MS)

        self._build()
        self._refresh()
        self.update_idletasks()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._enter_mode()

    def _mode_sizes(self):
        if self._compact:
            return COMPACT_DEFAULT, COMPACT_MIN
        return FULL_DEFAULT, FULL_MIN

    def _layout_window(self):
        """Size the window for the current mode and place it: tucked under the
        top-right corner in strip mode, or at its remembered/default spot as a
        normal window in full-card mode."""
        (w, h), (minw, minh) = self._mode_sizes()
        self.minsize(minw, minh)
        sw = self.winfo_screenwidth()
        if self._compact:
            self.geometry(f"{w}x{h}+{sw - w - EDGE_MARGIN}+{MENUBAR_H}")
        elif geo := self._cfg.get("geometry"):
            self.geometry(geo)
        else:
            self.geometry(f"{w}x{h}+{sw - w - 40}+60")

    # ── Window mode ─────────────────────────────────────────────────────────────

    def _enter_mode(self):
        """Apply the window chrome, placement, and watcher for the current mode.
        Strip mode is a borderless, always-on-top hot-corner HUD; full-card mode
        is an ordinary draggable window."""
        self._stop_watch()
        self.withdraw()                 # re-map cleanly so overrideredirect redraws

        if self._compact:
            self.resizable(False, False)
            self.overrideredirect(True)
            self.attributes("-topmost", True)
            self._layout_window()
            # Peek on launch/switch so it's clear it's there, then watch the corner.
            self._visible = False
            self._peeking = True
            self._show()
            self.after(PEEK_MS, self._end_peek)
            self._start_watch()
        else:
            self.overrideredirect(False)
            self.attributes("-topmost", False)
            self.resizable(True, True)
            self._layout_window()
            self.deiconify()
            self.lift()
            self._visible = True

    def _save_geometry_if_full(self):
        if not self._compact:
            self._cfg["geometry"] = self.geometry()

    # ── Show / hide (hot corner, strip mode only) ────────────────────────────────

    def _in_hot_corner(self, px, py):
        return px >= self.winfo_screenwidth() - HOT_ZONE and py <= HOT_ZONE

    def _pointer_over_window(self, px, py):
        x, y = self.winfo_rootx(), self.winfo_rooty()
        return x <= px <= x + self.winfo_width() and y <= py <= y + self.winfo_height()

    def _should_stay(self, px, py):
        """True while anything wants the HUD to remain visible."""
        return (self._peeking or self._pin > 0
                or self._in_hot_corner(px, py)
                or self._pointer_over_window(px, py))

    def _show(self):
        self._layout_window()
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self._visible = True
        self._leave_count = 0
        self._refresh()

    def _hide(self):
        self.withdraw()
        self._visible = False

    def _start_watch(self):
        if self._watch_job is None:
            self._watch_corner()

    def _stop_watch(self):
        if self._watch_job is not None:
            self.after_cancel(self._watch_job)
            self._watch_job = None

    def _watch_corner(self):
        if not self._compact:           # full-card mode never auto-hides
            self._watch_job = None
            return
        try:
            px, py = self.winfo_pointerxy()
        except tk.TclError:
            self._watch_job = None
            return
        if self._visible:
            if self._should_stay(px, py):
                self._leave_count = 0
            else:
                self._leave_count += 1
                if self._leave_count >= self._grace_ticks:
                    self._hide()
        elif self._in_hot_corner(px, py):
            self._show()
        self._watch_job = self.after(POLL_MS, self._watch_corner)

    def _end_peek(self):
        self._peeking = False
        px, py = self.winfo_pointerxy()
        if self._compact and self._visible and not self._should_stay(px, py):
            self._hide()

    def _pin_for(self, ms):
        """Pin the HUD open for a stretch (used while menus are posted)."""
        self._pin += 1
        self.after(ms, self._unpin)

    def _unpin(self):
        self._pin = max(0, self._pin - 1)

    def _on_close(self):
        self._save_geometry_if_full()
        for job in (self._job, self._watch_job):
            if job:
                self.after_cancel(job)
        _save_config(self._cfg)
        self.destroy()

    def _quit(self):
        self._on_close()

    # ── Toggle ────────────────────────────────────────────────────────────────

    def _toggle_mode(self):
        self._save_geometry_if_full()   # remember where the full card was sitting
        self._compact = not self._compact
        self._cfg["compact"] = self._compact
        _save_config(self._cfg)

        for w in self.winfo_children():
            w.destroy()

        self._build()
        self._enter_mode()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        if self._compact:
            self._build_compact()
        else:
            self._build_full()

    def _build_full(self):
        pad = {"padx": 8}

        # Header
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10)
        hdr.pack(fill="x", **pad, pady=(8, 4))

        ctk.CTkLabel(hdr, text="◆  Claude Status",
                     font=("SF Pro Display", 12, "bold"), text_color=PURPLE,
                     ).pack(side="left", padx=10, pady=7)

        ctk.CTkButton(hdr, text="↻", width=28, height=24,
                      fg_color="transparent", hover_color="#1a2d3e",
                      text_color=MUTED, font=("SF Pro", 14),
                      command=self._refresh).pack(side="right", padx=6)

        ctk.CTkButton(hdr, text="⊟", width=28, height=24,
                      fg_color="transparent", hover_color="#1a2d3e",
                      text_color=MUTED, font=("SF Pro", 13),
                      command=self._toggle_mode).pack(side="right", padx=0)

        self._menu_btn = ctk.CTkButton(hdr, text="⋮", width=28, height=24,
                                        fg_color="transparent", hover_color="#1a2d3e",
                                        text_color=MUTED, font=("SF Pro", 14),
                                        command=self._show_menu)
        self._menu_btn.pack(side="right", padx=0)

        # Claude Code card
        cc = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10)
        cc.pack(fill="x", **pad, pady=4)

        ctk.CTkLabel(cc, text="CLAUDE CODE", font=("SF Mono", 8, "bold"),
                     text_color=LABEL).pack(anchor="w", padx=10, pady=(7, 1))

        self.model_lbl = ctk.CTkLabel(cc, text="—",
                                       font=("SF Mono", 11, "bold"), text_color=PURPLE)
        self.model_lbl.pack(anchor="w", padx=10, pady=(0, 6))

        self.ctx_bar, self.ctx_lbl = self._bar_row(cc, "ctx")
        self.fh_bar,  self.fh_lbl  = self._bar_row(cc, "5h ")

        self.reset_lbl = ctk.CTkLabel(cc, text="", font=("SF Mono", 9), text_color=MUTED)
        self.reset_lbl.pack(anchor="e", padx=14)

        self.sd_bar, self.sd_lbl = self._bar_row(cc, "7d ")

        self.dir_lbl = ctk.CTkLabel(cc, text="", font=("SF Mono", 9), text_color=MUTED)
        self.dir_lbl.pack(anchor="w", padx=10, pady=(6, 8))

        # API card
        api = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10)
        api.pack(fill="x", **pad, pady=4)

        api_top = ctk.CTkFrame(api, fg_color="transparent")
        api_top.pack(fill="x", padx=10, pady=(7, 4))

        ctk.CTkLabel(api_top, text="ANTHROPIC API",
                     font=("SF Mono", 8, "bold"), text_color=LABEL).pack(side="left")
        self.api_dot = ctk.CTkLabel(api_top, text="●",
                                     font=("SF Mono", 12), text_color=MUTED)
        self.api_dot.pack(side="right")

        btn_row = ctk.CTkFrame(api, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 7))

        ctk.CTkButton(btn_row, text="Set API Key",
                      font=("SF Pro", 10), height=26,
                      fg_color="#1e1e3a", hover_color="#2d2d52", text_color="#818cf8",
                      command=self._set_api_key,
                      ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(btn_row, text="Billing ↗",
                      font=("SF Pro", 10), height=26,
                      fg_color="#1e1e3a", hover_color="#2d2d52", text_color="#818cf8",
                      command=lambda: subprocess.run(["open", BILLING_URL]),
                      ).pack(side="right")

        # Footer
        self.footer_lbl = ctk.CTkLabel(self, text="", font=("SF Mono", 8), text_color=MUTED)
        self.footer_lbl.pack(pady=(2, 6))

    def _build_compact(self):
        self.footer_lbl = None

        row = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        row.pack(fill="both", expand=True, padx=5, pady=4)

        # Expand button
        ctk.CTkButton(row, text="⊞", width=26, height=24,
                      fg_color="transparent", hover_color="#1a2d3e",
                      text_color=MUTED, font=("SF Pro", 13),
                      command=self._toggle_mode).pack(side="left", padx=(4, 2), pady=2)

        # Model name (truncated)
        self.model_lbl = ctk.CTkLabel(row, text="—",
                                       font=("SF Mono", 10, "bold"), text_color=PURPLE,
                                       width=110, anchor="w")
        self.model_lbl.pack(side="left", padx=(2, 6))

        _sep = lambda: ctk.CTkLabel(row, text="│", font=("SF Mono", 10),
                                     text_color=MUTED, width=6).pack(side="left")
        _sep()

        # ctx %
        self.ctx_lbl = ctk.CTkLabel(row, text="ctx —",
                                     font=("SF Mono", 10), text_color=TEXT, width=54)
        self.ctx_lbl.pack(side="left", padx=4)
        _sep()

        # 5h %
        self.fh_lbl = ctk.CTkLabel(row, text="5h —",
                                    font=("SF Mono", 10), text_color=TEXT, width=48)
        self.fh_lbl.pack(side="left", padx=4)
        _sep()

        # 7d %
        self.sd_lbl = ctk.CTkLabel(row, text="7d —",
                                    font=("SF Mono", 10), text_color=TEXT, width=48)
        self.sd_lbl.pack(side="left", padx=4)
        _sep()

        # API dot
        self.api_dot = ctk.CTkLabel(row, text="●", font=("SF Mono", 12), text_color=MUTED)
        self.api_dot.pack(side="left", padx=4)

        # Refresh + menu on the right
        ctk.CTkButton(row, text="↻", width=26, height=24,
                      fg_color="transparent", hover_color="#1a2d3e",
                      text_color=MUTED, font=("SF Pro", 14),
                      command=self._refresh).pack(side="right", padx=(2, 4))

        self._menu_btn = ctk.CTkButton(row, text="⋮", width=26, height=24,
                                        fg_color="transparent", hover_color="#1a2d3e",
                                        text_color=MUTED, font=("SF Pro", 14),
                                        command=self._show_menu)
        self._menu_btn.pack(side="right", padx=2)

        # These aren't used in compact mode
        self.ctx_bar = self.fh_bar = self.sd_bar = None
        self.reset_lbl = self.dir_lbl = None

    def _bar_row(self, parent, label: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)

        lbl = ctk.CTkLabel(row, text="—", font=("SF Mono", 10), text_color=TEXT, width=42)
        lbl.pack(side="right")

        ctk.CTkLabel(row, text=label, font=("SF Mono", 10),
                     text_color=LABEL, width=28).pack(side="left")

        bar = ctk.CTkProgressBar(row, height=6, corner_radius=3)
        bar.pack(side="left", fill="x", expand=True, padx=6)
        bar.set(0)

        return bar, lbl

    # ── Menu (compact mode) ───────────────────────────────────────────────────

    def _show_menu(self):
        # Keep the HUD up while the menu is posted, even if the cursor wanders
        # onto the (separate) menu window.
        self._pin_for(MENU_PIN_MS)

        menu = tk.Menu(self, tearoff=0,
                       bg="#1e1e3a", fg="#818cf8",
                       activebackground="#2d2d52", activeforeground="#c4b5fd",
                       font=("SF Pro", 11), bd=0)
        menu.add_command(
            label="Expand to full card" if self._compact else "Collapse to strip",
            command=self._toggle_mode)
        menu.add_separator()
        menu.add_command(label="Set API Key", command=self._set_api_key)
        menu.add_command(label="Billing ↗",
                         command=lambda: subprocess.run(["open", BILLING_URL]))
        menu.add_separator()
        menu.add_command(label="Quit Claude Status", command=self._quit)

        btn = self._menu_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 2
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ── Data ──────────────────────────────────────────────────────────────────

    def _refresh(self):
        if self._job:
            self.after_cancel(self._job)

        if not os.path.exists(CACHE_FILE):
            self.model_lbl.configure(text="no session yet")
            if self.footer_lbl:
                self.footer_lbl.configure(text="waiting for Claude Code…")
        else:
            try:
                with open(CACHE_FILE) as f:
                    data = json.load(f)
                self._apply(data)
                mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
                if self.footer_lbl:
                    self.footer_lbl.configure(
                        text=f"updated {mtime.strftime('%-I:%M:%S %p').lower()}"
                    )
            except Exception as exc:
                if self.footer_lbl:
                    self.footer_lbl.configure(text=f"error: {exc}")

        key = os.environ.get("ANTHROPIC_API_KEY") or self._cfg.get("api_key", "")
        if self._compact:
            self.api_dot.configure(
                text="●",
                text_color=GREEN if key else RED,
            )
        else:
            self.api_dot.configure(
                text="● active" if key else "● no key",
                text_color=GREEN if key else RED,
            )

        self._job = self.after(REFRESH_MS, self._refresh)

    def _apply(self, d: dict):
        name = d.get("model", {}).get("display_name", "—")

        if self._compact:
            if len(name) > 18:
                name = name[:17] + "…"
            self.model_lbl.configure(text=name)

            ctx = d.get("context_window", {})
            if (u := ctx.get("used_percentage")) is not None:
                self.ctx_lbl.configure(text=f"ctx {int(round(u))}%",
                                        text_color=_bar_color(u))

            fh = d.get("rate_limits", {}).get("five_hour", {})
            if (p := fh.get("used_percentage")) is not None:
                self.fh_lbl.configure(text=f"5h {int(round(p))}%",
                                       text_color=_bar_color(p))

            sd = d.get("rate_limits", {}).get("seven_day", {})
            if (p := sd.get("used_percentage")) is not None:
                self.sd_lbl.configure(text=f"7d {int(round(p))}%",
                                       text_color=_bar_color(p))
        else:
            self.model_lbl.configure(text=name)

            ctx = d.get("context_window", {})
            if (u := ctx.get("used_percentage")) is not None:
                self._set_bar(self.ctx_bar, self.ctx_lbl, u)

            fh = d.get("rate_limits", {}).get("five_hour", {})
            if (p := fh.get("used_percentage")) is not None:
                self._set_bar(self.fh_bar, self.fh_lbl, p)

            if reset_ts := fh.get("resets_at"):
                t = datetime.fromtimestamp(reset_ts)
                self.reset_lbl.configure(text=f"resets {t.strftime('%-I:%M %p').lower()}")
            else:
                self.reset_lbl.configure(text="")

            sd = d.get("rate_limits", {}).get("seven_day", {})
            if (p := sd.get("used_percentage")) is not None:
                self._set_bar(self.sd_bar, self.sd_lbl, p)

            cwd = d.get("workspace", {}).get("current_dir") or d.get("cwd", "")
            cwd = cwd.replace(os.path.expanduser("~"), "~")
            if len(cwd) > 34:
                cwd = "…" + cwd[-32:]
            self.dir_lbl.configure(text=cwd)

    def _set_bar(self, bar, lbl, pct: float):
        color = _bar_color(pct)
        bar.set(pct / 100)
        bar.configure(progress_color=color)
        lbl.configure(text=f"{int(round(pct))}%", text_color=color)

    def _set_api_key(self):
        # Keep the HUD up and drop topmost so the dialog isn't hidden behind it.
        self._pin += 1
        self.attributes("-topmost", False)
        try:
            dialog = ctk.CTkInputDialog(
                text="Paste your Anthropic API key\n(saved locally to ~/.claude/status-widget.json):",
                title="Set API Key",
            )
            key = dialog.get_input()
        finally:
            self.attributes("-topmost", True)
            self._pin -= 1
        if key and key.strip():
            self._cfg["api_key"] = key.strip()
            _save_config(self._cfg)
            self._refresh()


if __name__ == "__main__":
    Widget().mainloop()
