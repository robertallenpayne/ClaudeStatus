#!/usr/bin/env python3
"""Claude Code & API status widget."""

import json
import os
import re
import subprocess
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

CACHE_FILE  = os.path.expanduser("~/.claude/statusline-data.json")
CONFIG_FILE = os.path.expanduser("~/.claude/status-widget.json")
BILLING_URL = "https://console.anthropic.com/settings/billing"
REFRESH_MS  = 30_000

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
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.configure(fg_color=BG)

        self._restore_geometry()
        self._job = None
        self._build()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _geo_key(self):
        return "geometry_compact" if self._compact else "geometry"

    def _mode_sizes(self):
        if self._compact:
            return COMPACT_DEFAULT, COMPACT_MIN
        return FULL_DEFAULT, FULL_MIN

    def _default_geometry(self):
        (w, h), _ = self._mode_sizes()
        sw = self.winfo_screenwidth()
        return f"{w}x{h}+{sw - w - 20}+20"

    @staticmethod
    def _sanitize_geometry(geo, minw, minh):
        """Return a valid 'WxH+X+Y' string with size clamped up to the
        minimum, or None if the saved value is missing/unparseable."""
        if not geo:
            return None
        m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geo.strip())
        if not m:
            return None
        w, h, x, y = int(m[1]), int(m[2]), m[3], m[4]
        return f"{max(w, minw)}x{max(h, minh)}{x}{y}"

    def _restore_geometry(self):
        _, (minw, minh) = self._mode_sizes()
        self.minsize(minw, minh)          # set before geometry so it can shrink between modes
        geo = self._sanitize_geometry(self._cfg.get(self._geo_key()), minw, minh)
        self.geometry(geo or self._default_geometry())

    def _on_close(self):
        self._cfg[self._geo_key()] = self.geometry()
        _save_config(self._cfg)
        self.destroy()

    # ── Toggle ────────────────────────────────────────────────────────────────

    def _toggle_mode(self):
        self._cfg[self._geo_key()] = self.geometry()
        self._compact = not self._compact
        self._cfg["compact"] = self._compact
        _save_config(self._cfg)

        for w in self.winfo_children():
            w.destroy()

        self._restore_geometry()
        self._build()
        self._refresh()

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
        menu = tk.Menu(self, tearoff=0,
                       bg="#1e1e3a", fg="#818cf8",
                       activebackground="#2d2d52", activeforeground="#c4b5fd",
                       font=("SF Pro", 11), bd=0)
        menu.add_command(label="Expand to full card", command=self._toggle_mode)
        menu.add_separator()
        menu.add_command(label="Set API Key", command=self._set_api_key)
        menu.add_command(label="Billing ↗",
                         command=lambda: subprocess.run(["open", BILLING_URL]))

        btn = self._menu_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 2
        menu.post(x, y)

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
        dialog = ctk.CTkInputDialog(
            text="Paste your Anthropic API key\n(saved locally to ~/.claude/status-widget.json):",
            title="Set API Key",
        )
        key = dialog.get_input()
        if key and key.strip():
            self._cfg["api_key"] = key.strip()
            _save_config(self._cfg)
            self._refresh()


if __name__ == "__main__":
    Widget().mainloop()
