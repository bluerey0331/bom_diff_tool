"""
gui.py - BOM比較ツールのGUIモジュール（DigiKey / Mouser API + カラム名設定対応）

v3.0 変更点:
  - UIをフルリデザイン（モダンダークテーマ、ヴァイオレットアクセント）
  - 角丸 Compare ボタン（Canvas ベース）
  - ホバーエフェクトをすべてのボタンに追加
  - サマリーを大数字バッジ型に変更
  - セクションをカード枠でグルーピング
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from src.loader import load_bom
from src.comparator import compare_bom
from src.report import save_report
from src.column_config import get_column_names, get_sheet_names
from src.settings_dialog import open_settings

try:
    from src.digikey_client import (
        LIFECYCLE_OBSOLETE, LIFECYCLE_NRND,
        LIFECYCLE_ACTIVE,   LIFECYCLE_UNKNOWN,
    )
    DIGIKEY_AVAILABLE = True
except ImportError:
    DIGIKEY_AVAILABLE = False

try:
    from src.mouser_client import MouserClient, load_api_key as mouser_load_api_key
    MOUSER_AVAILABLE = True
except ImportError:
    MOUSER_AVAILABLE = False


# ============================================================
# カラーパレット（v3.0 モダンリデザイン）
# ============================================================
PALETTE = {
    # ── 背景 ──
    "bg_dark":      "#0C0E17",
    "bg_panel":     "#13161F",
    "bg_card":      "#1C2030",
    "bg_hover":     "#252A3E",

    # ── ボーダー ──
    "border":       "#2A2F47",
    "border2":      "#3A4060",

    # ── アクセント（ヴァイオレット） ──
    "accent":       "#7C3AED",
    "accent_hover": "#8B5CF6",
    "accent_dim":   "#2D1F5E",
    "accent_light": "#C4B5FD",

    # ── テキスト ──
    "text":         "#EEF0FB",
    "text_muted":   "#6B7080",
    "mono":         "#C9D1D9",

    # ── 差分ステータス ──
    "added":        "#10B981",
    "added_bg":     "#052E1D",
    "removed":      "#EF4444",
    "removed_bg":   "#2D0A0A",
    "changed":      "#F59E0B",
    "changed_bg":   "#2D1A00",

    # ── ライフサイクル ──
    "obsolete":     "#FCA5A5",
    "obsolete_bg":  "#4C0519",
    "nrnd":         "#FCD34D",
    "nrnd_bg":      "#422006",
    "active":       "#6EE7B7",
    "active_bg":    "#052E1D",
    "unknown_bg":   "#1C2030",
}

FONT_UI    = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 10)
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_HEAD  = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 8)
FONT_CAP   = ("Segoe UI", 7)
FONT_NUM   = ("Segoe UI", 20, "bold")


# ============================================================
# ヘルパー
# ============================================================

def _bind_hover(widget, normal_bg, hover_bg, normal_fg=None, hover_fg=None):
    """tk.Button / Label にホバーエフェクトを付与する"""
    def on_enter(_):
        kw = {"bg": hover_bg}
        if hover_fg:
            kw["fg"] = hover_fg
        widget.config(**kw)
    def on_leave(_):
        kw = {"bg": normal_bg}
        if normal_fg:
            kw["fg"] = normal_fg
        widget.config(**kw)
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


class RoundedButton(tk.Canvas):
    """Canvas ベースの角丸ボタン（ホバー対応）"""

    def __init__(self, parent, text, command,
                 bg, fg, hover_bg, disabled_bg=None,
                 radius=10, font=None, height=44, **kw):
        super().__init__(parent, height=height, bd=0,
                         highlightthickness=0,
                         bg=parent.cget("bg"), **kw)
        self._bg         = bg
        self._hover_bg   = hover_bg
        self._disabled_bg = disabled_bg or PALETTE["bg_card"]
        self._fg         = fg
        self._text       = text
        self._command    = command
        self._radius     = radius
        self._font       = font or ("Segoe UI", 11, "bold")
        self._disabled   = False
        self._current_bg = bg

        self.bind("<Configure>", lambda _: self._draw(self._current_bg))
        self.bind("<Button-1>",  self._on_click)
        self.bind("<Enter>",     self._on_enter)
        self.bind("<Leave>",     self._on_leave)

    def _rounded_rect(self, x1, y1, x2, y2, r, color):
        self.create_arc(x1, y1, x1+2*r, y1+2*r, start=90,  extent=90,  fill=color, outline=color)
        self.create_arc(x2-2*r, y1, x2, y1+2*r, start=0,   extent=90,  fill=color, outline=color)
        self.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90,  fill=color, outline=color)
        self.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90,  fill=color, outline=color)
        self.create_rectangle(x1+r, y1, x2-r, y2, fill=color, outline=color)
        self.create_rectangle(x1, y1+r, x2, y2-r, fill=color, outline=color)

    def _draw(self, bg=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        color = bg if bg else self._bg
        self._rounded_rect(0, 0, w, h, self._radius, color)
        fg = PALETTE["text_muted"] if self._disabled else self._fg
        self.create_text(w // 2, h // 2, text=self._text,
                         fill=fg, font=self._font, anchor="center")

    def _on_click(self, _):
        if not self._disabled and self._command:
            self._command()

    def _on_enter(self, _):
        if not self._disabled:
            self._current_bg = self._hover_bg
            self._draw(self._hover_bg)

    def _on_leave(self, _):
        if not self._disabled:
            self._current_bg = self._bg
            self._draw(self._bg)

    def config(self, **kw):
        if "text" in kw:
            self._text = kw.pop("text")
        if "state" in kw:
            st = kw.pop("state")
            self._disabled = (st == "disabled")
            self._current_bg = self._disabled_bg if self._disabled else self._bg
        if "fg" in kw:
            self._fg = kw.pop("fg")
        self.after_idle(lambda: self._draw(self._current_bg))

    configure = config

    def cget(self, key):
        if key == "state":
            return "disabled" if self._disabled else "normal"
        return super().cget(key)


# ============================================================
# メインウィンドウ
# ============================================================

class BomApp(tk.Tk):
    """BOM比較ツールのメインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.title("BOM Diff Tool")
        self.geometry("1300x840")
        self.minsize(900, 600)
        self.configure(bg=PALETTE["bg_dark"])

        self._results          = None
        self._dk_results       = {}
        self._ms_results       = {}
        self._new_part_numbers = []

        self._build_ui()

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------

    def _build_ui(self):
        self._configure_styles()
        self._build_header()

        body = tk.Frame(self, bg=PALETTE["bg_dark"])
        body.pack(fill="both", expand=True, padx=16, pady=(12, 12))

        left = tk.Frame(body, bg=PALETTE["bg_dark"], width=300)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        self._build_left_panel(left)

        right = tk.Frame(body, bg=PALETTE["bg_dark"])
        right.pack(side="left", fill="both", expand=True)
        self._build_result_panel(right)

        self._build_statusbar()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Dark.TNotebook",
            background=PALETTE["bg_dark"], borderwidth=0, tabmargins=0)
        style.configure("Dark.TNotebook.Tab",
            background=PALETTE["bg_dark"], foreground=PALETTE["text_muted"],
            padding=[16, 8], font=FONT_LABEL, borderwidth=0)
        style.map("Dark.TNotebook.Tab",
            background=[("selected", PALETTE["bg_dark"])],
            foreground=[("selected", PALETTE["text"])])

        style.configure("Dark.Treeview",
            background=PALETTE["bg_panel"], foreground=PALETTE["text"],
            fieldbackground=PALETTE["bg_panel"], rowheight=30,
            font=FONT_MONO, borderwidth=0)
        style.configure("Dark.Treeview.Heading",
            background=PALETTE["bg_card"], foreground=PALETTE["text_muted"],
            font=FONT_HEAD, relief="flat", borderwidth=0)
        style.map("Dark.Treeview",
            background=[("selected", PALETTE["accent_dim"])],
            foreground=[("selected", PALETTE["accent_light"])])

        style.configure("Dark.Vertical.TScrollbar",
            background=PALETTE["bg_card"], troughcolor=PALETTE["bg_dark"],
            arrowcolor=PALETTE["border2"], borderwidth=0, relief="flat")

        style.configure("Accent.Horizontal.TProgressbar",
            troughcolor=PALETTE["bg_card"], background=PALETTE["accent"],
            borderwidth=0, relief="flat")

    def _build_header(self):
        header = tk.Frame(self, bg=PALETTE["bg_panel"], height=58)
        header.pack(fill="x")
        header.pack_propagate(False)

        # アイコン＋タイトル
        left = tk.Frame(header, bg=PALETTE["bg_panel"])
        left.pack(side="left", padx=20, pady=10)
        tk.Label(left, text="◈", bg=PALETTE["bg_panel"], fg=PALETTE["accent"],
                 font=("Segoe UI", 17)).pack(side="left", padx=(0, 8))
        tk.Label(left, text="BOM Diff Tool", bg=PALETTE["bg_panel"], fg=PALETTE["text"],
                 font=FONT_TITLE).pack(side="left")

        # 右側: API バッジ + 設定ボタン
        right = tk.Frame(header, bg=PALETTE["bg_panel"])
        right.pack(side="right", padx=16)

        settings_btn = tk.Button(right, text="⚙  Settings",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            padx=12, pady=5, bd=0,
            command=self._open_settings)
        settings_btn.pack(side="right", padx=(8, 0))
        _bind_hover(settings_btn, PALETTE["bg_card"], PALETTE["bg_hover"],
                    PALETTE["text_muted"], PALETTE["text"])

        for label, color in [("Mouser", "#60A5FA"), ("DigiKey", "#F59E0B")]:
            badge = tk.Label(right, text=label,
                             bg=PALETTE["bg_card"], fg=color,
                             font=FONT_CAP, padx=8, pady=4)
            badge.pack(side="right", padx=3)

        tk.Label(right, text="v2.2", bg=PALETTE["bg_panel"],
                 fg=PALETTE["text_muted"], font=FONT_LABEL).pack(side="right", padx=8)

        # アクセントライン
        tk.Frame(self, bg=PALETTE["accent"], height=2).pack(fill="x")

    # ----------------------------------------------------------
    # 左パネル
    # ----------------------------------------------------------

    def _build_left_panel(self, parent):
        # ── BOM FILES カード ──
        self._build_card_header(parent, "BOM FILES")
        file_card = tk.Frame(parent, bg=PALETTE["bg_card"],
                             highlightbackground=PALETTE["border"],
                             highlightthickness=1)
        file_card.pack(fill="x", pady=(4, 0))

        tk.Label(file_card, text="OLD BOM", bg=PALETTE["bg_card"],
                 fg=PALETTE["text_muted"], font=FONT_CAP,
                 anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        self._old_path = tk.StringVar(value="old.xlsx")
        self._build_file_row(file_card, self._old_path)

        tk.Frame(file_card, bg=PALETTE["border"], height=1).pack(fill="x", padx=8)

        tk.Label(file_card, text="NEW BOM", bg=PALETTE["bg_card"],
                 fg=PALETTE["text_muted"], font=FONT_CAP,
                 anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        self._new_path = tk.StringVar(value="new.xlsx")
        self._build_file_row(file_card, self._new_path)
        tk.Frame(file_card, bg=PALETTE["bg_card"], height=4).pack()

        # ── Compare ボタン ──
        tk.Frame(parent, bg=PALETTE["bg_dark"], height=10).pack()
        self._run_btn = RoundedButton(
            parent, text="▶  Compare", command=self._run_comparison,
            bg=PALETTE["accent"], fg="#FFFFFF",
            hover_bg=PALETTE["accent_hover"],
            disabled_bg=PALETTE["bg_card"],
            radius=10, height=44,
            font=("Segoe UI", 11, "bold"))
        self._run_btn.pack(fill="x")

        self._progress = ttk.Progressbar(parent,
            style="Accent.Horizontal.TProgressbar", mode="indeterminate")
        self._progress.pack(fill="x", pady=(6, 0))

        # ── DIGIKEY API カード ──
        tk.Frame(parent, bg=PALETTE["bg_dark"], height=14).pack()
        self._build_card_header(parent, "DIGIKEY API")
        dk_card = tk.Frame(parent, bg=PALETTE["bg_card"],
                           highlightbackground=PALETTE["border"],
                           highlightthickness=1)
        dk_card.pack(fill="x", pady=(4, 0))

        tk.Label(dk_card, text="Client ID", bg=PALETTE["bg_card"],
                 fg=PALETTE["text_muted"], font=FONT_CAP,
                 anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        self._dk_client_id = tk.StringVar()
        self._build_entry(dk_card, self._dk_client_id, show="")

        tk.Label(dk_card, text="Client Secret", bg=PALETTE["bg_card"],
                 fg=PALETTE["text_muted"], font=FONT_CAP,
                 anchor="w").pack(fill="x", padx=10, pady=(6, 2))
        self._dk_client_secret = tk.StringVar()
        self._build_entry(dk_card, self._dk_client_secret, show="•")
        tk.Frame(dk_card, bg=PALETTE["bg_card"], height=8).pack()

        self._dk_btn = tk.Button(dk_card, text="⚡  Check DigiKey",
            bg=PALETTE["bg_hover"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            pady=7, state="disabled", bd=0,
            command=self._run_digikey_check)
        self._dk_btn.pack(fill="x", padx=8, pady=(0, 6))

        self._dk_progress = ttk.Progressbar(dk_card,
            style="Accent.Horizontal.TProgressbar", mode="determinate")
        self._dk_progress.pack(fill="x", padx=8, pady=(0, 8))

        # ── MOUSER API カード ──
        tk.Frame(parent, bg=PALETTE["bg_dark"], height=14).pack()
        self._build_card_header(parent, "MOUSER API")
        ms_card = tk.Frame(parent, bg=PALETTE["bg_card"],
                           highlightbackground=PALETTE["border"],
                           highlightthickness=1)
        ms_card.pack(fill="x", pady=(4, 0))

        tk.Label(ms_card, text="API Key", bg=PALETTE["bg_card"],
                 fg=PALETTE["text_muted"], font=FONT_CAP,
                 anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        self._ms_api_key = tk.StringVar()
        self._build_entry(ms_card, self._ms_api_key, show="•")
        tk.Frame(ms_card, bg=PALETTE["bg_card"], height=8).pack()

        self._ms_btn = tk.Button(ms_card, text="⚡  Check Mouser",
            bg=PALETTE["bg_hover"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            pady=7, state="disabled", bd=0,
            command=self._run_mouser_check)
        self._ms_btn.pack(fill="x", padx=8, pady=(0, 6))

        self._ms_progress = ttk.Progressbar(ms_card,
            style="Accent.Horizontal.TProgressbar", mode="determinate")
        self._ms_progress.pack(fill="x", padx=8, pady=(0, 8))

        # ── SUMMARY ──
        tk.Frame(parent, bg=PALETTE["bg_dark"], height=14).pack()
        self._build_card_header(parent, "SUMMARY")
        summary_card = tk.Frame(parent, bg=PALETTE["bg_card"],
                                highlightbackground=PALETTE["border"],
                                highlightthickness=1)
        summary_card.pack(fill="x", pady=(4, 0))

        self._summary_cards = {}
        badge_defs = [
            ("added",    "Added",    PALETTE["added"]),
            ("removed",  "Removed",  PALETTE["removed"]),
            ("qty",      "Qty Δ",    PALETTE["changed"]),
            ("mfr",      "Mfr Δ",    PALETTE["changed"]),
            ("obsolete", "Obsolete", PALETTE["obsolete"]),
            ("nrnd",     "NRND",     PALETTE["nrnd"]),
        ]
        grid = tk.Frame(summary_card, bg=PALETTE["bg_card"])
        grid.pack(fill="x", padx=8, pady=8)
        for i, (key, label, color) in enumerate(badge_defs):
            cell = tk.Frame(grid, bg=PALETTE["bg_hover"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            cell.grid(row=i // 2, column=i % 2,
                      padx=3, pady=3, sticky="nsew")
            grid.columnconfigure(i % 2, weight=1)
            num_lbl = tk.Label(cell, text="—", bg=PALETTE["bg_hover"],
                               fg=color, font=FONT_NUM, pady=4)
            num_lbl.pack()
            tk.Label(cell, text=label.upper(), bg=PALETTE["bg_hover"],
                     fg=PALETTE["text_muted"], font=FONT_CAP).pack(pady=(0, 6))
            self._summary_cards[key] = num_lbl

        # ── Save ボタン ──
        tk.Frame(parent, bg=PALETTE["bg_dark"], height=14).pack()
        self._save_btn = tk.Button(parent, text="↓  Save Excel Report",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            pady=9, state="disabled", bd=0,
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
            command=self._save_report)
        self._save_btn.pack(fill="x")
        _bind_hover(self._save_btn, PALETTE["bg_card"], PALETTE["bg_hover"])

    def _build_card_header(self, parent, text):
        tk.Label(parent, text=text, bg=PALETTE["bg_dark"],
                 fg=PALETTE["text_muted"], font=FONT_CAP,
                 anchor="w").pack(fill="x")

    def _build_file_row(self, parent, var: tk.StringVar):
        row = tk.Frame(parent, bg=PALETTE["bg_card"])
        row.pack(fill="x")
        tk.Entry(row, textvariable=var,
                 bg=PALETTE["bg_card"], fg=PALETTE["mono"],
                 insertbackground=PALETTE["accent"],
                 relief="flat", font=FONT_MONO, bd=0
                 ).pack(side="left", fill="both", expand=True, padx=(10, 0), pady=6)
        btn = tk.Button(row, text="…",
                        bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
                        relief="flat", cursor="hand2",
                        font=("Segoe UI", 12), padx=10, bd=0,
                        command=lambda v=var: self._browse_file(v))
        btn.pack(side="right", padx=(0, 4))
        _bind_hover(btn, PALETTE["bg_card"], PALETTE["bg_hover"],
                    PALETTE["text_muted"], PALETTE["text"])

    def _build_entry(self, parent, var: tk.StringVar, show: str):
        frame = tk.Frame(parent, bg=PALETTE["bg_hover"],
                         highlightbackground=PALETTE["border"],
                         highlightthickness=1)
        frame.pack(fill="x", padx=10, pady=(0, 4))
        tk.Entry(frame, textvariable=var,
                 bg=PALETTE["bg_hover"], fg=PALETTE["mono"],
                 insertbackground=PALETTE["accent"],
                 relief="flat", font=FONT_MONO, bd=0, show=show
                 ).pack(fill="x", padx=8, pady=5)

    # ----------------------------------------------------------
    # 右パネル（タブ）
    # ----------------------------------------------------------

    def _build_result_panel(self, parent):
        # タブ下線インジケーター用のラッパー
        wrapper = tk.Frame(parent, bg=PALETTE["bg_dark"])
        wrapper.pack(fill="both", expand=True)

        self._notebook = ttk.Notebook(wrapper, style="Dark.TNotebook")
        self._notebook.pack(fill="both", expand=True)

        self._tabs = {}
        self._build_diff_tabs()

        lc_frame = tk.Frame(self._notebook, bg=PALETTE["bg_panel"])
        self._notebook.add(lc_frame, text="⚡  Lifecycle")
        self._build_lifecycle_tab(lc_frame)

        # タブ選択時に下線バーを動かす（アクセント強調）
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, _):
        pass  # 将来の拡張用

    def _build_diff_tabs(self):
        cols = get_column_names()
        pn   = cols["part_number"]
        mfr  = cols["manufacturer"]
        qty  = cols["quantity"]
        desc = cols["description"]

        tab_defs = [
            ("added",   "+ Added",
             [pn, mfr, qty, desc], PALETTE["added_bg"]),
            ("removed", "− Removed",
             [pn, mfr, qty, desc], PALETTE["removed_bg"]),
            ("qty",     "△ Qty Changed",
             [pn, f"Old {qty}", f"New {qty}"], PALETTE["changed_bg"]),
            ("mfr",     "△ Mfr Changed",
             [pn, f"Old {mfr}", f"New {mfr}"], PALETTE["changed_bg"]),
        ]
        for key, label, columns, row_bg in tab_defs:
            frame = tk.Frame(self._notebook, bg=PALETTE["bg_panel"])
            self._notebook.add(frame, text=f"  {label}  ")
            self._tabs[key] = self._build_treeview(frame, columns, row_bg)

    def _build_treeview(self, parent, columns: list, row_bg: str) -> ttk.Treeview:
        container = tk.Frame(parent, bg=PALETTE["bg_panel"])
        container.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical",
                             style="Dark.Vertical.TScrollbar")
        vsb.pack(side="right", fill="y")

        tree = ttk.Treeview(container, columns=columns, show="headings",
                            style="Dark.Treeview", yscrollcommand=vsb.set)
        vsb.configure(command=tree.yview)
        tree.pack(fill="both", expand=True)

        for col in columns:
            w = max(110, min(len(col) * 11, 300))
            tree.column(col, width=w, minwidth=60, anchor="w")
            tree.heading(col, text=col, anchor="w")

        tree.tag_configure("colored",     background=row_bg)
        tree.tag_configure("colored_alt", background=PALETTE["bg_panel"])
        return tree

    def _build_lifecycle_tab(self, parent):
        tk.Label(parent,
                 text="LIFECYCLE STATUS  —  click a row to view substitutes",
                 bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
                 font=FONT_SMALL, anchor="w").pack(fill="x", padx=10, pady=(10, 4))

        lc_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        lc_frame.pack(fill="both", expand=True)

        vsb_lc = ttk.Scrollbar(lc_frame, orient="vertical",
                                style="Dark.Vertical.TScrollbar")
        vsb_lc.pack(side="right", fill="y")

        cols    = get_column_names()
        lc_cols = [cols["part_number"], cols["manufacturer"], "Status", cols["description"]]
        self._lc_tree = ttk.Treeview(lc_frame, columns=lc_cols,
                                     show="headings", style="Dark.Treeview",
                                     yscrollcommand=vsb_lc.set)
        vsb_lc.configure(command=self._lc_tree.yview)
        self._lc_tree.pack(fill="both", expand=True)

        for col in lc_cols:
            w = 120 if col == "Status" else max(110, min(len(col) * 11, 300))
            self._lc_tree.column(col, width=w, minwidth=60, anchor="w")
            self._lc_tree.heading(col, text=col, anchor="w")

        for tag, bg, fg in [
            ("obsolete", PALETTE["obsolete_bg"], PALETTE["obsolete"]),
            ("nrnd",     PALETTE["nrnd_bg"],     PALETTE["nrnd"]),
            ("active",   PALETTE["active_bg"],   PALETTE["active"]),
            ("unknown",  PALETTE["unknown_bg"],  PALETTE["text_muted"]),
        ]:
            self._lc_tree.tag_configure(tag, background=bg, foreground=fg)

        self._lc_tree.bind("<<TreeviewSelect>>", self._on_lifecycle_select)

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill="x", pady=6)

        tk.Label(parent, text="SUBSTITUTES  —  for selected part",
                 bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
                 font=FONT_SMALL, anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        sub_frame = tk.Frame(parent, bg=PALETTE["bg_panel"], height=200)
        sub_frame.pack(fill="x", pady=(0, 4))
        sub_frame.pack_propagate(False)

        vsb_sub = ttk.Scrollbar(sub_frame, orient="vertical",
                                 style="Dark.Vertical.TScrollbar")
        vsb_sub.pack(side="right", fill="y")

        sub_cols = ["Mfr Part Number", "DigiKey / Mouser P/N",
                    "Manufacturer Name", "Description", "Source"]
        self._sub_tree = ttk.Treeview(sub_frame, columns=sub_cols,
                                      show="headings", style="Dark.Treeview",
                                      yscrollcommand=vsb_sub.set)
        vsb_sub.configure(command=self._sub_tree.yview)
        self._sub_tree.pack(fill="both", expand=True)

        sub_widths = {
            "Mfr Part Number":      150,
            "DigiKey / Mouser P/N": 150,
            "Manufacturer Name":    140,
            "Description":          220,
            "Source":                80,
        }
        for col in sub_cols:
            self._sub_tree.column(col, width=sub_widths.get(col, 120),
                                  minwidth=50, anchor="w")
            self._sub_tree.heading(col, text=col, anchor="w")

        self._sub_tree.tag_configure("sub_row", background=PALETTE["bg_card"])
        self._sub_tree.tag_configure("sub_alt", background=PALETTE["bg_panel"])

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PALETTE["bg_panel"], height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=PALETTE["border"], height=1).pack(fill="x")

        inner = tk.Frame(bar, bg=PALETTE["bg_panel"])
        inner.pack(fill="x", padx=12, pady=4)

        self._status_dot = tk.Label(inner, text="●", bg=PALETTE["bg_panel"],
                                    fg=PALETTE["text_muted"], font=("Segoe UI", 8))
        self._status_dot.pack(side="left", padx=(0, 6))

        self._status_var = tk.StringVar(value="Ready  —  Select files and click Compare")
        tk.Label(inner, textvariable=self._status_var,
                 bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
                 font=FONT_LABEL, anchor="w").pack(side="left")

    def _set_status(self, text: str, color: str = None):
        self._status_var.set(text)
        if color:
            self._status_dot.config(fg=color)

    # ----------------------------------------------------------
    # 設定ダイアログ
    # ----------------------------------------------------------

    def _open_settings(self):
        changed = open_settings(self)
        if changed:
            self._rebuild_diff_tabs()
            self._set_status(
                "設定を更新しました。次の Compare から新しいカラム名が適用されます。")

    def _rebuild_diff_tabs(self):
        for _ in range(4):
            if self._notebook.tabs():
                self._notebook.forget(0)
        self._tabs = {}

        cols = get_column_names()
        pn   = cols["part_number"]
        mfr  = cols["manufacturer"]
        qty  = cols["quantity"]
        desc = cols["description"]

        tab_defs = [
            ("added",   "+ Added",
             [pn, mfr, qty, desc], PALETTE["added_bg"]),
            ("removed", "− Removed",
             [pn, mfr, qty, desc], PALETTE["removed_bg"]),
            ("qty",     "△ Qty Changed",
             [pn, f"Old {qty}", f"New {qty}"], PALETTE["changed_bg"]),
            ("mfr",     "△ Mfr Changed",
             [pn, f"Old {mfr}", f"New {mfr}"], PALETTE["changed_bg"]),
        ]
        for i, (key, label, columns, row_bg) in enumerate(tab_defs):
            frame = tk.Frame(self._notebook, bg=PALETTE["bg_panel"])
            self._notebook.insert(i, frame, text=f"  {label}  ")
            self._tabs[key] = self._build_treeview(frame, columns, row_bg)

        self._results = None
        self._set_status("設定変更後は ▶ Compare を再実行してください")

    # ----------------------------------------------------------
    # BOM 比較
    # ----------------------------------------------------------

    def _browse_file(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="Excelファイルを選択",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if path:
            var.set(path)

    def _run_comparison(self):
        old_path = self._old_path.get().strip()
        new_path = self._new_path.get().strip()
        if not old_path or not new_path:
            messagebox.showwarning("Input Required", "両方のファイルを指定してください。")
            return

        self._run_btn.config(state="disabled", text="Comparing…")
        self._progress.start(12)
        self._set_status("Comparing…", PALETTE["accent_light"])

        threading.Thread(
            target=self._comparison_worker,
            args=(old_path, new_path), daemon=True).start()

    def _comparison_worker(self, old_path: str, new_path: str):
        try:
            old_df = load_bom(old_path)
            new_df = load_bom(new_path)
            results = compare_bom(old_df, new_df)
            new_pns = list(new_df.index)
            self.after(0, self._on_comparison_done, results, new_pns)
        except Exception as e:
            self.after(0, self._on_comparison_error, str(e))

    def _on_comparison_done(self, results: dict, new_pns: list):
        self._results          = results
        self._new_part_numbers = new_pns
        self._dk_results       = {}
        self._ms_results       = {}

        cols = get_column_names()
        mfr  = cols["manufacturer"]
        qty  = cols["quantity"]
        desc = cols["description"]

        self._populate_tab("added",   results["added"],       [mfr, qty, desc])
        self._populate_tab("removed", results["removed"],     [mfr, qty, desc])
        self._populate_tab("qty",     results["qty_changed"], [f"Old {qty}", f"New {qty}"])
        self._populate_tab("mfr",     results["mfr_changed"], [f"Old {mfr}", f"New {mfr}"])

        self._clear_lifecycle_tab()

        self._summary_cards["added"].config(text=str(len(results["added"])))
        self._summary_cards["removed"].config(text=str(len(results["removed"])))
        self._summary_cards["qty"].config(text=str(len(results["qty_changed"])))
        self._summary_cards["mfr"].config(text=str(len(results["mfr_changed"])))
        self._summary_cards["obsolete"].config(text="—")
        self._summary_cards["nrnd"].config(text="—")

        self._progress.stop()
        self._run_btn.config(state="normal", text="▶  Compare")
        self._dk_btn.config(state="normal", fg=PALETTE["accent_light"])
        self._ms_btn.config(state="normal", fg=PALETTE["accent_light"])
        self._save_btn.config(state="normal", fg=PALETTE["accent_light"])
        _bind_hover(self._dk_btn, PALETTE["bg_hover"], PALETTE["accent_dim"],
                    PALETTE["accent_light"], PALETTE["accent_light"])
        _bind_hover(self._ms_btn, PALETTE["bg_hover"], PALETTE["accent_dim"],
                    PALETTE["accent_light"], PALETTE["accent_light"])

        total = (len(results["added"]) + len(results["removed"])
                 + len(results["qty_changed"]) + len(results["mfr_changed"]))
        self._set_status(
            f"Done  —  {total} difference(s)  ·  {len(new_pns)} parts in new BOM  ·  "
            "Click ⚡ Check DigiKey or ⚡ Check Mouser",
            PALETTE["added"])

    def _on_comparison_error(self, error_msg: str):
        self._progress.stop()
        self._run_btn.config(state="normal", text="▶  Compare")
        self._set_status(f"Error: {error_msg}", PALETTE["removed"])
        messagebox.showerror("比較エラー", error_msg)

    def _populate_tab(self, key: str, df, value_columns: list):
        tree = self._tabs[key]
        for item in tree.get_children():
            tree.delete(item)
        for i, (part_number, row) in enumerate(df.iterrows()):
            values = [part_number] + [row.get(col, "") for col in value_columns]
            tree.insert("", "end", values=values,
                        tags=("colored" if i % 2 == 0 else "colored_alt",))

    # ----------------------------------------------------------
    # DigiKey ライフサイクルチェック
    # ----------------------------------------------------------

    def _run_digikey_check(self):
        if not self._new_part_numbers:
            messagebox.showwarning("No Data", "先に Compare を実行してください。")
            return
        if not DIGIKEY_AVAILABLE:
            messagebox.showerror("Module Error",
                "requests ライブラリが見つかりません。\npip install requests を実行してください。")
            return

        self._dk_btn.config(state="disabled", text="Checking…")
        self._dk_progress.config(value=0, maximum=len(self._new_part_numbers))
        self._set_status(f"DigiKey API: 0 / {len(self._new_part_numbers)} parts…",
                         PALETTE["changed"])

        threading.Thread(
            target=self._digikey_worker,
            args=(self._dk_client_id.get().strip(),
                  self._dk_client_secret.get().strip()),
            daemon=True).start()

    def _digikey_worker(self, client_id: str, client_secret: str):
        try:
            from src.digikey_client import DigiKeyClient, load_credentials
            client = (DigiKeyClient(client_id, client_secret) if client_id and client_secret
                      else DigiKeyClient(*load_credentials()))
        except ValueError as e:
            self.after(0, self._on_dk_error, str(e))
            return

        results = {}
        total   = len(self._new_part_numbers)
        for i, pn in enumerate(self._new_part_numbers):
            lc = client.check_lifecycle(pn)
            results[pn] = lc
            self.after(0, self._on_dk_progress, i + 1, total, pn, lc)
        self.after(0, self._on_dk_done, results)

    def _on_dk_progress(self, done, total, pn, lc):
        self._dk_progress.config(value=done)
        self._set_status(
            f"DigiKey API: {done} / {total}  —  {pn} → {lc.get('status_label','?')}",
            PALETTE["changed"])

    def _on_dk_done(self, results: dict):
        self._dk_results = results
        self._populate_lifecycle_tab({**self._ms_results, **results})

        obsolete_n = sum(1 for r in results.values() if r.get("lifecycle") == LIFECYCLE_OBSOLETE)
        nrnd_n     = sum(1 for r in results.values() if r.get("lifecycle") == LIFECYCLE_NRND)

        self._summary_cards["obsolete"].config(text=str(obsolete_n))
        self._summary_cards["nrnd"].config(text=str(nrnd_n))
        self._dk_btn.config(state="normal", text="⚡  Check DigiKey")
        self._set_status(
            f"DigiKey check done  —  Obsolete: {obsolete_n}  NRND: {nrnd_n}",
            PALETTE["active"])
        self._notebook.select(4)

    def _on_dk_error(self, error_msg: str):
        self._dk_btn.config(state="normal", text="⚡  Check DigiKey")
        self._set_status(f"DigiKey Error: {error_msg}", PALETTE["removed"])
        messagebox.showerror("DigiKey APIエラー", error_msg)

    # ----------------------------------------------------------
    # Mouser ライフサイクルチェック
    # ----------------------------------------------------------

    def _run_mouser_check(self):
        if not self._new_part_numbers:
            messagebox.showwarning("No Data", "先に Compare を実行してください。")
            return
        if not MOUSER_AVAILABLE:
            messagebox.showerror("Module Error",
                "requests ライブラリが見つかりません。\npip install requests を実行してください。")
            return

        self._ms_btn.config(state="disabled", text="Checking…")
        self._ms_progress.config(value=0, maximum=len(self._new_part_numbers))
        self._set_status(f"Mouser API: 0 / {len(self._new_part_numbers)} parts…",
                         PALETTE["changed"])

        threading.Thread(
            target=self._mouser_worker,
            args=(self._ms_api_key.get().strip(),),
            daemon=True).start()

    def _mouser_worker(self, api_key: str):
        try:
            if api_key:
                client = MouserClient(api_key)
            else:
                client = MouserClient(mouser_load_api_key())
        except ValueError as e:
            self.after(0, self._on_ms_error, str(e))
            return

        results = {}
        total   = len(self._new_part_numbers)
        for i, pn in enumerate(self._new_part_numbers):
            lc = client.check_lifecycle(pn)
            results[pn] = lc
            self.after(0, self._on_ms_progress, i + 1, total, pn, lc)
        self.after(0, self._on_ms_done, results)

    def _on_ms_progress(self, done: int, total: int, pn: str, lc: dict):
        self._ms_progress.config(value=done)
        self._set_status(
            f"Mouser API: {done} / {total}  —  {pn} → {lc.get('status_label','?')}",
            PALETTE["changed"])

    def _on_ms_done(self, results: dict):
        self._ms_results = results
        merged = {**results, **self._dk_results}
        self._populate_lifecycle_tab(merged)

        obsolete_n = sum(1 for r in results.values() if r.get("lifecycle") == LIFECYCLE_OBSOLETE)
        nrnd_n     = sum(1 for r in results.values() if r.get("lifecycle") == LIFECYCLE_NRND)

        self._summary_cards["obsolete"].config(text=str(obsolete_n))
        self._summary_cards["nrnd"].config(text=str(nrnd_n))
        self._ms_btn.config(state="normal", text="⚡  Check Mouser")
        self._set_status(
            f"Mouser check done  —  Obsolete: {obsolete_n}  NRND: {nrnd_n}",
            PALETTE["active"])
        self._notebook.select(4)

    def _on_ms_error(self, error_msg: str):
        self._ms_btn.config(state="normal", text="⚡  Check Mouser")
        self._set_status(f"Mouser Error: {error_msg}", PALETTE["removed"])
        messagebox.showerror("Mouser APIエラー", error_msg)

    def _clear_lifecycle_tab(self):
        for item in self._lc_tree.get_children():
            self._lc_tree.delete(item)
        for item in self._sub_tree.get_children():
            self._sub_tree.delete(item)

    def _populate_lifecycle_tab(self, results: dict):
        self._clear_lifecycle_tab()
        cols = get_column_names()

        order = {LIFECYCLE_OBSOLETE: 0, LIFECYCLE_NRND: 1,
                 LIFECYCLE_ACTIVE: 2, LIFECYCLE_UNKNOWN: 3}
        sorted_items = sorted(results.items(),
            key=lambda kv: order.get(kv[1].get("lifecycle", "unknown"), 99))

        for pn, lc in sorted_items:
            lifecycle = lc.get("lifecycle", LIFECYCLE_UNKNOWN)
            error     = lc.get("error", "")
            status    = f"⚠ {error[:30]}" if error else lc.get("status_label", "Unknown")

            mfr = desc = ""
            if self._results is not None:
                added = self._results.get("added")
                if added is not None and pn in added.index:
                    mfr  = added.loc[pn, cols["manufacturer"]]
                    desc = added.loc[pn, cols["description"]]

            self._lc_tree.insert("", "end",
                values=[pn, mfr, status, desc],
                iid=pn, tags=(lifecycle,))

    def _on_lifecycle_select(self, event):
        selection = self._lc_tree.selection()
        if not selection:
            return

        pn = selection[0]

        all_subs = []
        dk_lc = self._dk_results.get(pn, {})
        for sub in dk_lc.get("substitutes", []):
            all_subs.append({**sub, "source": "DigiKey"})

        ms_lc = self._ms_results.get(pn, {})
        for sub in ms_lc.get("substitutes", []):
            all_subs.append({**sub, "source": "Mouser"})

        for item in self._sub_tree.get_children():
            self._sub_tree.delete(item)

        if not all_subs:
            self._sub_tree.insert("", "end",
                values=["（代替品なし）", "", "", "", ""], tags=("sub_row",))
            return

        for i, sub in enumerate(all_subs):
            dist_pn = sub.get("digikey_part_number", "") or sub.get("mouser_part_number", "")
            self._sub_tree.insert("", "end", values=[
                sub.get("mfr_part_number", ""),
                dist_pn,
                sub.get("manufacturer",   ""),
                sub.get("description",    ""),
                sub.get("source",         ""),
            ], tags=("sub_row" if i % 2 == 0 else "sub_alt",))

    # ----------------------------------------------------------
    # レポート保存
    # ----------------------------------------------------------

    def _save_report(self):
        if self._results is None:
            return
        path = filedialog.asksaveasfilename(
            title="レポートの保存先",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="bom_diff_report.xlsx")
        if not path:
            return
        try:
            save_report(self._results, path, self._dk_results or None)
            self._set_status(f"Saved → {os.path.basename(path)}", PALETTE["active"])
            messagebox.showinfo("保存完了", f"レポートを保存しました:\n{path}")
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))


def launch():
    app = BomApp()
    app.mainloop()
