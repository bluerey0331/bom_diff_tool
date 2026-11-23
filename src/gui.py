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

import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from src.ui_language import tr, lifecycle_label
from src.loader import load_bom
from src.comparator import compare_bom
from src.report import save_report
from src.column_config import get_column_names, get_sheet_names, migrate_api_settings, save_api_settings
from src.material_theme import PALETTE
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


FONT_UI    = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 10)
FONT_TITLE = ("Segoe UI", 18)
FONT_HEAD  = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 8)
FONT_CAP   = ("Segoe UI", 9)
FONT_NUM   = ("Segoe UI", 23)


# ============================================================
# ヘルパー
# ============================================================

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
        self._disabled_bg = disabled_bg or PALETTE["surface_container"]
        self._fg         = fg
        self._text       = text
        self._command    = command
        self._radius     = radius
        self._font       = font or ("Segoe UI", 11, "bold")
        self._disabled   = False
        self._current_bg = bg

        self.bind("<Configure>", lambda _: self._draw(self._current_bg))
        super().configure(takefocus=True, cursor="hand2", highlightthickness=2,
                          highlightcolor=PALETTE["primary"],
                          highlightbackground=parent.cget("bg"))
        self.bind("<Button-1>", self._on_click)
        self.bind("<Return>", self._on_click)
        self.bind("<space>", self._on_click)
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
        inset = 2
        radius = min(self._radius, (h - inset * 2) / 2, (w - inset * 2) / 2)
        if radius > 0:
            self._rounded_rect(inset, inset, w - inset, h - inset, radius, color)
        fg = PALETTE["disabled_text"] if self._disabled else self._fg
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
            super().configure(takefocus=not self._disabled,
                              cursor="" if self._disabled else "hand2")
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

def merge_lifecycle_results(*providers):
    """For each part, use the most severe reported status for the summary and row color."""
    severity = {"unknown": 0, "active": 1, "nrnd": 2, "obsolete": 3}
    merged = {}
    for results in providers:
        for part, result in results.items():
            current = merged.get(part)
            if current is None or severity.get(result.get("lifecycle"), 0) > severity.get(current.get("lifecycle"), 0):
                merged[part] = result
    return merged


class BomApp(tk.Tk):
    """BOM比較ツールのメインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.title("BOM Diff Tool")
        self.geometry("1180x720")
        self.minsize(int(tr("980", "1120")), 600)
        self.configure(bg=PALETTE["surface_low"])

        self._results          = None
        self._dk_results       = {}
        self._ms_results       = {}
        self._new_part_numbers = []
        self._new_manufacturers = {}

        self._build_ui()

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------

    def _build_ui(self):
        self._configure_styles()
        self._build_header()

        body = tk.Frame(self, bg=PALETTE["surface_low"])
        body.pack(fill="both", expand=True, padx=24, pady=20)

        left = tk.Frame(body, bg=PALETTE["surface_low"], width=288)
        left.pack(side="left", fill="y", padx=(0, 20))
        left.pack_propagate(False)
        self._build_file_panel(left)

        right = tk.Frame(body, bg=PALETTE["surface_low"])
        right.pack(side="left", fill="both", expand=True)
        self._build_summary(right)
        self._build_result_panel(right)

        self._build_statusbar()
        for field in (self._old_path, self._new_path):
            field.trace_add("write", self._invalidate_results)

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Material.TNotebook",
            background=PALETTE["surface_low"], borderwidth=0, tabmargins=0)
        style.configure("Material.TNotebook.Tab",
            background=PALETTE["surface_low"], foreground=PALETTE["on_surface_variant"],
            padding=[12, 10], font=FONT_HEAD, borderwidth=0)
        style.map("Material.TNotebook.Tab",
            background=[("active", "!selected", PALETTE["surface_high"]),
                        ("selected", PALETTE["surface_low"])],
            foreground=[("selected", PALETTE["primary"])])
        self._tab_indicator = tk.PhotoImage(width=1, height=3)
        self._tab_indicator.put(PALETTE["primary"], to=(0, 0, 1, 3))
        self._tab_track = tk.PhotoImage(width=1, height=3)
        self._tab_track.put(PALETTE["surface_low"], to=(0, 0, 1, 3))
        style.element_create("Material.indicator", "image", self._tab_track,
                             ("selected", self._tab_indicator), sticky="ew")
        tab_layout = style.layout("TNotebook.Tab")
        tab_layout[0][1]["children"].insert(
            0, ("Material.indicator", {"side": "bottom", "sticky": "ew"}))
        style.layout("Material.TNotebook.Tab", tab_layout)

        style.configure("Material.TButton", font=FONT_HEAD, padding=(14, 8),
                        relief="flat", borderwidth=0,
                        background=PALETTE["surface_container"],
                        foreground=PALETTE["primary"])
        style.map("Material.TButton",
                  background=[("disabled", PALETTE["disabled_surface"]),
                              ("pressed", PALETTE["primary_container"]),
                              ("active", PALETTE["surface_high"])],
                  foreground=[("disabled", PALETTE["disabled_text"])])
        style.configure("Tonal.Material.TButton",
                        background=PALETTE["primary_container"],
                        foreground=PALETTE["on_primary_container"])
        style.map("Tonal.Material.TButton",
                  background=[("disabled", PALETTE["disabled_surface"]),
                              ("pressed", "#CCB7ED"), ("active", "#DDCCFA")],
                  foreground=[("disabled", PALETTE["disabled_text"])])

        style.configure("Material.Treeview",
            background=PALETTE["surface"], foreground=PALETTE["on_surface"],
            fieldbackground=PALETTE["surface"], rowheight=34,
            font=FONT_MONO, borderwidth=0)
        style.configure("Material.Treeview.Heading",
            background=PALETTE["surface_container"], foreground=PALETTE["on_surface_variant"],
            font=FONT_HEAD, relief="flat", borderwidth=0)
        style.map("Material.Treeview",
            background=[("selected", PALETTE["primary_container"])],
            foreground=[("selected", PALETTE["on_primary_container"])])

        for orientation in ("Vertical", "Horizontal"):
            style.configure(f"Material.{orientation}.TScrollbar",
                background=PALETTE["surface_container"], troughcolor=PALETTE["surface_low"],
                arrowcolor=PALETTE["outline"], borderwidth=0, relief="flat")

        style.configure("Accent.Horizontal.TProgressbar",
            troughcolor=PALETTE["surface_container"], background=PALETTE["primary"],
            borderwidth=0, relief="flat")

    def _build_header(self):
        header = tk.Frame(self, bg=PALETTE["surface"])
        header.pack(fill="x")
        tk.Label(header, text="BOM Diff Tool", bg=PALETTE["surface"],
                 fg=PALETTE["on_surface"], font=FONT_TITLE).pack(
                     side="left", padx=24, pady=16)

        self._save_btn = ttk.Button(
            header, text=tr("Excelレポートを保存", "Save Excel report"), style="Tonal.Material.TButton",
            state="disabled", command=self._save_report)
        self._save_btn.pack(side="right", padx=(8, 24), pady=12)
        self._settings_btn = ttk.Button(
            header, text=tr("列・シート設定", "Column and sheet settings"), style="Material.TButton",
            command=self._open_settings)
        self._settings_btn.pack(side="right")
        tk.Frame(self, bg=PALETTE["outline_variant"], height=1).pack(fill="x")

    def _build_file_panel(self, parent):
        card = tk.Frame(parent, bg=PALETTE["surface_container"])
        card.pack(fill="x")
        tk.Label(card, text=tr("比較するファイル", "BOM files"), bg=PALETTE["surface_container"],
                 fg=PALETTE["on_surface"], font=FONT_HEAD).pack(
                     anchor="w", padx=16, pady=(16, 4))

        self._old_path = tk.StringVar(value="old.xlsx")
        self._new_path = tk.StringVar(value="new.xlsx")
        self._file_controls = []
        for label, variable in ((tr("旧BOM", "Old BOM"), self._old_path), (tr("新BOM", "New BOM"), self._new_path)):
            tk.Label(card, text=label, bg=PALETTE["surface_container"],
                     fg=PALETTE["on_surface_variant"], font=FONT_LABEL).pack(
                         anchor="w", padx=16, pady=(12, 4))
            self._file_controls.extend(self._build_file_row(card, variable))

        self._swap_btn = ttk.Button(card, text=tr("旧BOMと新BOMを入れ替え", "Swap old and new BOMs"),
                                    style="Material.TButton", command=self._swap_files)
        self._swap_btn.pack(anchor="w", padx=8, pady=(8, 4))
        self._run_btn = RoundedButton(
            card, text=tr("BOMを比較", "Compare BOMs"), command=self._run_comparison,
            bg=PALETTE["primary"], fg=PALETTE["on_primary"],
            hover_bg=PALETTE["primary_hover"], disabled_bg=PALETTE["disabled_surface"],
            radius=24, height=44, font=FONT_HEAD)
        self._run_btn.pack(fill="x", padx=14, pady=(0, 16))

        self._demo_btn = ttk.Button(card, text=tr("デモを開く", "Open demo"),
                                    style="Material.TButton", command=self._open_demo)
        self._demo_btn.pack(fill="x", padx=16, pady=(0, 12))

        self._progress = ttk.Progressbar(parent,
            style="Accent.Horizontal.TProgressbar", mode="indeterminate")
        self._progress.pack(fill="x", pady=(8, 0))

    def _build_summary(self, parent):
        self._summary_cards = {}
        badge_defs = [
            ("added",    tr("追加", "Added"),    PALETTE["added"]),
            ("removed",  tr("削除", "Removed"),  PALETTE["removed"]),
            ("qty",      tr("数量変更", "Quantity changes"),    PALETTE["changed"]),
            ("mfr",      tr("メーカー変更", "Manufacturer changes"),    PALETTE["changed"]),
            ("obsolete", tr("廃止", "Obsolete"), PALETTE["obsolete"]),
            ("nrnd",     tr("新規設計非推奨", "NRND"),     PALETTE["nrnd"]),
        ]
        grid = tk.Frame(parent, bg=PALETTE["surface_low"])
        grid.pack(fill="x", pady=(0, 12))
        last = len(badge_defs) - 1
        for index, (key, label, color) in enumerate(badge_defs):
            cell = tk.Frame(grid, bg=PALETTE["surface_container"])
            cell.grid(row=0, column=index, padx=(0, 8) if index < last else 0, sticky="nsew")
            grid.columnconfigure(index, weight=1, uniform="summary")
            tk.Label(cell, text=label, bg=PALETTE["surface_container"],
                     fg=PALETTE["on_surface_variant"], font=FONT_CAP).pack(pady=(10, 0))
            count = tk.Label(cell, text="—", bg=PALETTE["surface_container"],
                             fg=color, font=FONT_NUM)
            count.pack(pady=(0, 10))
            self._summary_cards[key] = count

    def _build_api_panel(self, parent):
        try:
            saved = migrate_api_settings()
        except (OSError, ValueError, ImportError):
            saved = dict.fromkeys(("client_id", "client_secret", "api_key"), "")
            self.after_idle(messagebox.showerror,
                            tr("認証情報のエラー", "Credential storage error"),
                            tr("Windows資格情報マネージャーを読み込めませんでした。",
                               "Could not read Windows Credential Manager."))
        self._dk_client_id = tk.StringVar(value=saved["client_id"])
        self._dk_client_secret = tk.StringVar(value=saved["client_secret"])
        self._ms_api_key = tk.StringVar(value=saved["api_key"])
        self._api_entries = []
        providers = (
            ("DigiKey", ((tr("クライアントID", "Client ID"), self._dk_client_id, ""),
                         (tr("クライアントシークレット", "Client Secret"), self._dk_client_secret, "•")),
             self._run_digikey_check),
            ("Mouser", ((tr("APIキー", "API key"), self._ms_api_key, "•"),), self._run_mouser_check),
        )
        controls = []
        self._connection_buttons = {}
        for index, (name, fields, command) in enumerate(providers):
            parent.columnconfigure(index, weight=1, uniform="providers")
            card = tk.Frame(parent, bg=PALETTE["surface_container"])
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 12) if index == 0 else 0)
            tk.Label(card, text=name, bg=PALETTE["surface_container"],
                     fg=PALETTE["on_surface"], font=FONT_HEAD).pack(
                         anchor="w", padx=16, pady=(16, 4))
            for label, variable, mask in fields:
                tk.Label(card, text=label, bg=PALETTE["surface_container"],
                         fg=PALETTE["on_surface_variant"], font=FONT_LABEL).pack(
                             anchor="w", padx=16, pady=(8, 4))
                entry = self._build_entry(card, variable, show=mask)
                entry.pack(fill="x", padx=16)
                self._api_entries.append(entry)
            progress = ttk.Progressbar(card, style="Accent.Horizontal.TProgressbar",
                                        mode="determinate")
            progress.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
            button = ttk.Button(card, text=tr(f"{name}で確認", f"Check {name}"), style="Tonal.Material.TButton",
                                command=command, state="disabled")
            button.pack(side="bottom", anchor="w", padx=16, pady=(4, 12))
            probe = ttk.Button(card, text=tr("接続テスト", "Test connection"),
                               style="Material.TButton",
                               command=lambda provider=name: self._test_api_connection(provider))
            probe.pack(side="bottom", anchor="w", padx=16, pady=(8, 0))
            self._connection_buttons[name] = probe
            controls.append((button, progress))
        (self._dk_btn, self._dk_progress), (self._ms_btn, self._ms_progress) = controls

        self._save_api_btn = ttk.Button(
            parent, text=tr("認証情報を保存", "Save credentials"),
            style="Material.TButton", command=self._save_credentials)
        self._save_api_btn.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _save_credentials(self, provider=None):
        if sys.platform != "win32" and provider is not None:
            return True
        digikey = (self._dk_client_id.get().strip(), self._dk_client_secret.get().strip())
        mouser = self._ms_api_key.get().strip()
        save_digikey = provider in (None, "DigiKey")
        save_mouser = provider in (None, "Mouser")
        if save_digikey and bool(digikey[0]) != bool(digikey[1]):
            messagebox.showwarning(
                tr("認証情報が不足しています", "Incomplete credentials"),
                tr("DigiKeyのクライアントIDとシークレットを両方入力してください。",
                   "Enter both the DigiKey Client ID and Client Secret."))
            return False

        digikey_value = digikey if save_digikey and (provider is None or all(digikey)) else None
        mouser_value = mouser if save_mouser and (provider is None or mouser) else None
        try:
            if digikey_value is not None or mouser_value is not None:
                save_api_settings(digikey=digikey_value, mouser=mouser_value)
        except (OSError, ValueError, ImportError) as error:
            messagebox.showerror(tr("認証情報を保存できません", "Could not save credentials"),
                                 str(error))
            return False
        if provider is None:
            self._set_status(tr("API認証情報を保存しました。", "API credentials saved."),
                             PALETTE["active"])
        return True

    def _open_demo(self):
        root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        old = root / "samples" / "demo_old_bom.xlsx"
        new = root / "samples" / "demo_new_bom.xlsx"
        if not old.is_file() or not new.is_file():
            messagebox.showerror(tr("デモを開けません", "Could not open demo"),
                                 tr("デモ用Excelが見つかりません。", "The demo workbooks are missing."))
            return
        self._old_path.set(str(old))
        self._new_path.set(str(new))
        self._run_comparison()

    def _test_api_connection(self, provider):
        credentials = ((self._dk_client_id.get().strip(), self._dk_client_secret.get().strip())
                       if provider == "DigiKey" else (self._ms_api_key.get().strip(),))
        button = self._connection_buttons[provider]
        button.state(["disabled"])
        self._set_status(tr(f"{provider} の接続を確認中…", f"Testing {provider} connection…"))

        def worker():
            try:
                from src.api_connection import test_connection
                message = test_connection(provider, credentials)
            except ValueError as error:
                self.after(0, done, str(error), False)
            except Exception:
                self.after(0, done, tr("接続テストに失敗しました。", "Connection test failed."), False)
            else:
                self.after(0, done, message, True)

        def done(message, succeeded):
            button.state(["!disabled"])
            self._set_status(f"{provider} · {message}",
                             PALETTE["active" if succeeded else "removed"])
            alert = messagebox.showinfo if succeeded else messagebox.showerror
            alert(provider, message, parent=self)

        threading.Thread(target=worker, daemon=True).start()

    def _build_file_row(self, parent, variable):
        row = tk.Frame(parent, bg=PALETTE["surface_container"])
        row.pack(fill="x", padx=16)
        button = ttk.Button(row, text=tr("参照", "Browse"), style="Material.TButton",
                            command=lambda: self._browse_file(variable))
        button.pack(side="right", padx=(4, 0))
        entry = self._build_entry(row, variable)
        entry.pack(side="left", fill="both", expand=True)
        return entry, button

    def _build_entry(self, parent, variable, show=""):
        return tk.Entry(
            parent, textvariable=variable, show=show, width=12,
            bg=PALETTE["surface"], fg=PALETTE["on_surface"],
            disabledbackground=PALETTE["disabled_surface"],
            disabledforeground=PALETTE["disabled_text"],
            insertbackground=PALETTE["primary"], selectbackground=PALETTE["primary_container"],
            selectforeground=PALETTE["on_primary_container"], font=FONT_UI,
            relief="flat", bd=7, highlightthickness=1,
            highlightbackground=PALETTE["outline"], highlightcolor=PALETTE["primary"],
        )

    # ----------------------------------------------------------
    # 右パネル（タブ）
    # ----------------------------------------------------------

    def _build_result_panel(self, parent):
        # タブ下線インジケーター用のラッパー
        wrapper = tk.Frame(parent, bg=PALETTE["surface_low"])
        wrapper.pack(fill="both", expand=True)

        self._notebook = ttk.Notebook(wrapper, style="Material.TNotebook")
        self._notebook.pack(fill="both", expand=True)

        self._tabs = {}
        self._build_diff_tabs()

        self._lifecycle_frame = lc_frame = tk.Frame(self._notebook, bg=PALETTE["surface"])
        self._notebook.add(lc_frame, text=tr("ライフサイクル", "Lifecycle"))
        self._build_lifecycle_tab(lc_frame)

        api_frame = tk.Frame(self._notebook, bg=PALETTE["surface_low"])
        self._notebook.add(api_frame, text=tr("API設定", "API settings"))
        api_panel = tk.Frame(api_frame, bg=PALETTE["surface_low"])
        api_panel.pack(fill="x", padx=16, pady=16)
        tk.Label(api_panel, text=tr("BOMを比較してから、新BOMの品番を照会します。", "Compare the BOMs first to look up the parts in the new BOM."),
                 bg=PALETTE["surface_low"], fg=PALETTE["on_surface_variant"],
                 font=FONT_LABEL).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self._build_api_panel(api_panel)
        self._notebook.enable_traversal()

    def _build_diff_tabs(self):
        self._tab_labels = {}
        cols = get_column_names()
        pn   = cols["part_number"]
        mfr  = cols["manufacturer"]
        qty  = cols["quantity"]
        desc = cols["description"]

        tab_defs = [
            ("added",   tr("追加", "Added"),
             [pn, mfr, qty, desc], PALETTE["added_bg"]),
            ("removed", tr("削除", "Removed"),
             [pn, mfr, qty, desc], PALETTE["removed_bg"]),
            ("qty",     tr("数量変更", "Quantity changes"),
             [pn, f"Old {qty}", f"New {qty}"], PALETTE["changed_bg"]),
            ("mfr",     tr("メーカー変更", "Manufacturer changes"),
             [pn, f"Old {mfr}", f"New {mfr}"], PALETTE["changed_bg"]),
        ]
        for index, (key, label, columns, row_bg) in enumerate(tab_defs):
            frame = tk.Frame(self._notebook, bg=PALETTE["surface"])
            position = index if index < len(self._notebook.tabs()) else "end"
            self._notebook.insert(position, frame, text=label)
            self._tab_labels[key] = label
            self._tabs[key] = self._build_treeview(frame, columns, row_bg)

    def _build_treeview(self, parent, columns: list, row_bg: str) -> ttk.Treeview:
        container = tk.Frame(parent, bg=PALETTE["surface"])
        container.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical",
                             style="Material.Vertical.TScrollbar")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(container, orient="horizontal",
                            style="Material.Horizontal.TScrollbar")
        hsb.grid(row=1, column=0, sticky="ew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        tree = ttk.Treeview(container, columns=columns, show="headings",
                            style="Material.Treeview", yscrollcommand=vsb.set,
                            xscrollcommand=hsb.set)
        vsb.configure(command=tree.yview)
        hsb.configure(command=tree.xview)
        tree.grid(row=0, column=0, sticky="nsew")

        fields = get_column_names()
        labels = {
            fields["part_number"]: tr("メーカー型番", "Manufacturer part number"),
            fields["manufacturer"]: tr("メーカー", "Manufacturer"),
            fields["quantity"]: tr("数量", "Quantity"),
            fields["description"]: tr("説明", "Description"),
            f'Old {fields["quantity"]}': tr("旧数量", "Old quantity"),
            f'New {fields["quantity"]}': tr("新数量", "New quantity"),
            f'Old {fields["manufacturer"]}': tr("旧メーカー", "Old manufacturer"),
            f'New {fields["manufacturer"]}': tr("新メーカー", "New manufacturer"),
        }
        for col in columns:
            w = max(110, min(len(col) * 11, 300))
            tree.column(col, width=w, minwidth=w, anchor="w")
            tree.heading(col, text=labels[col], anchor="w")

        tree.tag_configure("colored",     background=row_bg)
        tree.tag_configure("colored_alt", background=PALETTE["surface"])
        return tree

    def _build_lifecycle_tab(self, parent):
        tk.Label(parent,
                 text=tr("部品を選択すると代替品候補が表示されます", "Select a part to view its replacements"),
                 bg=PALETTE["surface"], fg=PALETTE["on_surface_variant"],
                 font=FONT_SMALL, anchor="w").pack(fill="x", padx=10, pady=(10, 4))

        lc_frame = tk.Frame(parent, bg=PALETTE["surface"])
        lc_frame.pack(fill="both", expand=True)

        vsb_lc = ttk.Scrollbar(lc_frame, orient="vertical",
                                style="Material.Vertical.TScrollbar")
        vsb_lc.pack(side="right", fill="y")

        cols    = get_column_names()
        lc_cols = [cols["part_number"], cols["manufacturer"], "DigiKey", "Mouser", cols["description"]]
        self._lc_tree = ttk.Treeview(lc_frame, columns=lc_cols,
                                     show="headings", style="Material.Treeview",
                                     yscrollcommand=vsb_lc.set)
        vsb_lc.configure(command=self._lc_tree.yview)
        self._lc_tree.pack(fill="both", expand=True)

        headings = [tr("メーカー型番", "Manufacturer part number"), tr("メーカー", "Manufacturer"),
                    "DigiKey", "Mouser", tr("説明", "Description")]
        for col, heading in zip(lc_cols, headings):
            w = 135 if col in ("DigiKey", "Mouser") else max(110, min(len(col) * 11, 300))
            self._lc_tree.column(col, width=w, minwidth=60, anchor="w")
            self._lc_tree.heading(col, text=heading, anchor="w")

        for tag, bg, fg in [
            ("obsolete", PALETTE["obsolete_bg"], PALETTE["obsolete"]),
            ("nrnd",     PALETTE["nrnd_bg"],     PALETTE["nrnd"]),
            ("active",   PALETTE["active_bg"],   PALETTE["active"]),
            ("unknown",  PALETTE["unknown_bg"],  PALETTE["on_surface_variant"]),
        ]:
            self._lc_tree.tag_configure(tag, background=bg, foreground=fg)

        self._lc_tree.bind("<<TreeviewSelect>>", self._on_lifecycle_select)
        self._lc_detail = tk.StringVar()
        tk.Label(parent, textvariable=self._lc_detail, bg=PALETTE["surface"],
                 fg=PALETTE["on_surface_variant"], font=FONT_LABEL,
                 wraplength=520, justify="left").pack(anchor="w", padx=10, pady=4)

        tk.Frame(parent, bg=PALETTE["outline_variant"], height=1).pack(fill="x", pady=6)

        tk.Label(parent, text=tr("選択した部品の代替品候補", "Replacement candidates for the selected part"),
                 bg=PALETTE["surface"], fg=PALETTE["on_surface_variant"],
                 font=FONT_SMALL, anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        actions = tk.Frame(parent, bg=PALETTE["surface"])
        actions.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self._candidate_actions = []
        for label, command in (
            (tr("商品ページを開く", "Open product page"), self._open_candidate_page),
            (tr("仕様を比較", "Compare specifications"), self._compare_candidate),
        ):
            button = ttk.Button(actions, text=label, command=command,
                                style="Material.TButton", state="disabled")
            button.pack(side="left", padx=(0, 8))
            self._candidate_actions.append(button)
        self._candidates_by_row = {}

        sub_frame = tk.Frame(parent, bg=PALETTE["surface"], height=160)
        sub_frame.pack(fill="x", pady=(0, 4))
        sub_frame.pack_propagate(False)

        vsb_sub = ttk.Scrollbar(sub_frame, orient="vertical",
                                 style="Material.Vertical.TScrollbar")
        vsb_sub.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(sub_frame, orient="horizontal",
                                   style="Material.Horizontal.TScrollbar")
        horizontal.grid(row=1, column=0, sticky="ew")
        sub_frame.rowconfigure(0, weight=1)
        sub_frame.columnconfigure(0, weight=1)
        sub_frame.grid_propagate(False)

        sub_cols = ["Mfr Part Number", "DigiKey / Mouser P/N",
                    "Manufacturer Name", "Description", "Source"]
        self._sub_tree = ttk.Treeview(sub_frame, columns=sub_cols,
                                      show="headings", style="Material.Treeview",
                                      yscrollcommand=vsb_sub.set, xscrollcommand=horizontal.set)
        vsb_sub.configure(command=self._sub_tree.yview)
        horizontal.configure(command=self._sub_tree.xview)
        self._sub_tree.grid(row=0, column=0, sticky="nsew")

        sub_widths = {
            "Mfr Part Number":      190,
            "DigiKey / Mouser P/N": 160,
            "Manufacturer Name":    140,
            "Description":          220,
            "Source":                80,
        }
        headings = [tr("メーカー型番", "Manufacturer part number"),
                    tr("販売店型番", "Distributor part number"),
                    tr("メーカー", "Manufacturer"), tr("説明", "Description"), tr("出典", "Source")]
        for col, heading in zip(sub_cols, headings):
            self._sub_tree.column(col, width=sub_widths.get(col, 120),
                                  minwidth=sub_widths.get(col, 120), anchor="w")
            self._sub_tree.heading(col, text=heading, anchor="w")

        self._sub_tree.bind("<<TreeviewSelect>>", self._on_candidate_select)
        self._sub_tree.bind("<Double-Button-1>", self._open_candidate_page)
        self._sub_tree.tag_configure("sub_row", background=PALETTE["surface_container"])
        self._sub_tree.tag_configure("sub_alt", background=PALETTE["surface"])

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PALETTE["surface"], height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=PALETTE["outline_variant"], height=1).pack(fill="x")

        inner = tk.Frame(bar, bg=PALETTE["surface"])
        inner.pack(fill="x", padx=12, pady=4)

        self._status_dot = tk.Label(inner, text="●", bg=PALETTE["surface"],
                                    fg=PALETTE["on_surface_variant"], font=("Segoe UI", 8))
        self._status_dot.pack(side="left", padx=(0, 6))

        self._status_var = tk.StringVar(value=tr("旧BOMと新BOMを指定して比較してください。", "Select the old and new BOM files, then run the comparison."))
        tk.Label(inner, textvariable=self._status_var,
                 bg=PALETTE["surface"], fg=PALETTE["on_surface_variant"],
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
                tr("設定を更新しました。BOMを再比較してください。", "Settings updated. Compare the BOMs again."))

    def _rebuild_diff_tabs(self):
        for tree in self._tabs.values():
            tree.master.master.destroy()
        self._tabs.clear()
        self._build_diff_tabs()
        self._notebook.select(0)
        self._invalidate_results()

    def _invalidate_results(self, *_):
        self._results = None
        self._new_part_numbers = []
        self._new_manufacturers = {}
        self._dk_results = {}
        self._ms_results = {}
        for key, tree in self._tabs.items():
            tree.delete(*tree.get_children())
            self._notebook.tab(tree.master.master, text=self._tab_labels[key])
        self._clear_lifecycle_tab()
        self._dk_progress.config(value=0)
        self._ms_progress.config(value=0)
        for label in self._summary_cards.values():
            label.config(text="—")
        for button in (self._save_btn, self._dk_btn, self._ms_btn):
            button.config(state="disabled")
        self._set_status(tr("旧BOMと新BOMを指定して比較してください。", "Select the old and new BOM files, then run the comparison."))

    # ----------------------------------------------------------
    # BOM 比較
    # ----------------------------------------------------------

    def _set_inputs_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (*self._file_controls, self._swap_btn, self._demo_btn, self._settings_btn,
                       *self._api_entries, self._save_api_btn):
            widget.config(state=state)

    def _swap_files(self):
        old_path, new_path = self._old_path.get(), self._new_path.get()
        self._old_path.set(new_path)
        self._new_path.set(old_path)

    def _browse_file(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title=tr("Excelファイルを選択", "Select an Excel file"),
            filetypes=[(tr("Excelファイル", "Excel files"), "*.xlsx *.xlsm"), (tr("すべてのファイル", "All files"), "*.*")])
        if path:
            var.set(path)

    def _run_comparison(self):
        old_path = self._old_path.get().strip()
        new_path = self._new_path.get().strip()
        if not old_path or not new_path:
            messagebox.showwarning(tr("入力が必要です", "Input required"), tr("両方のファイルを指定してください。", "Select both BOM files."))
            return

        self._invalidate_results()
        self._set_inputs_enabled(False)
        self._run_btn.config(state="disabled", text=tr("比較中…", "Comparing…"))
        self._progress.start(12)
        self._set_status(tr("比較中…", "Comparing…"), PALETTE["primary"])

        threading.Thread(
            target=self._comparison_worker,
            args=(old_path, new_path), daemon=True).start()

    def _comparison_worker(self, old_path: str, new_path: str):
        try:
            old_df = load_bom(old_path)
            new_df = load_bom(new_path)
            results = compare_bom(old_df, new_df)
            new_pns = list(new_df.index)
            manufacturers = new_df[get_column_names()["manufacturer"]].fillna("").to_dict()
            self.after(0, self._on_comparison_done, results, new_pns, manufacturers)
        except Exception as e:
            self.after(0, self._on_comparison_error, str(e))

    def _on_comparison_done(self, results: dict, new_pns: list, manufacturers: dict):
        self._results          = results
        self._new_part_numbers = new_pns
        self._new_manufacturers = manufacturers
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
        self._set_inputs_enabled(True)
        self._run_btn.config(state="normal", text=tr("BOMを比較", "Compare BOMs"))
        api_state = "normal" if new_pns else "disabled"
        self._dk_btn.config(state=api_state)
        self._ms_btn.config(state=api_state)
        self._save_btn.config(state="normal")

        first_changed = next((key for key, tree in self._tabs.items()
                              if tree.get_children()), "added")
        self._notebook.select(self._tabs[first_changed].master.master)

        total = (len(results["added"]) + len(results["removed"])
                 + len(results["qty_changed"]) + len(results["mfr_changed"]))
        self._set_status(
            tr(f"比較完了　差分 {total} 件　新BOM {len(new_pns)} 部品",
               f"Comparison complete · {total} changes · {len(new_pns)} parts in new BOM"),
            PALETTE["added"])

    def _on_comparison_error(self, error_msg: str):
        self._progress.stop()
        self._set_inputs_enabled(True)
        self._run_btn.config(state="normal", text=tr("BOMを比較", "Compare BOMs"))
        self._set_status(tr(f"エラー: {error_msg}", f"Error: {error_msg}"), PALETTE["removed"])
        messagebox.showerror(tr("比較エラー", "Comparison error"), error_msg)

    def _populate_tab(self, key: str, df, value_columns: list):
        tree = self._tabs[key]
        self._notebook.tab(tree.master.master, text=f"{self._tab_labels[key]} ({len(df)})")
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
            messagebox.showwarning(tr("比較結果なし", "No comparison results"), tr("先にBOMを比較してください。", "Compare the BOMs first."))
            return
        if not DIGIKEY_AVAILABLE:
            messagebox.showerror(tr("依存パッケージのエラー", "Missing dependency"),
                tr("requestsライブラリが見つかりません。pip install requests を実行してください。",
                   "The requests library is missing. Run pip install requests."))
            return

        if not self._save_credentials("DigiKey"):
            return

        self._set_inputs_enabled(False)
        self._run_btn.config(state="disabled")
        self._dk_btn.config(state="disabled")
        self._ms_btn.config(state="disabled")
        self._dk_btn.config(state="disabled", text=tr("照会中…", "Checking…"))
        self._dk_progress.config(value=0, maximum=len(self._new_part_numbers))
        self._set_status(tr(f"DigiKey API: 0 / {len(self._new_part_numbers)} 件…",
                            f"DigiKey API: 0 / {len(self._new_part_numbers)} parts…"),
                         PALETTE["changed"])

        threading.Thread(
            target=self._digikey_worker,
            args=(self._dk_client_id.get().strip(),
                  self._dk_client_secret.get().strip()),
            daemon=True).start()

    def _digikey_worker(self, client_id: str, client_secret: str):
        try:
            from src.digikey_client import DigiKeyClient, load_credentials, load_locale_config
            if bool(client_id) != bool(client_secret):
                raise ValueError(tr("Client ID と Client Secret の両方を入力してください。", "Enter both the Client ID and Client Secret."))
            credentials = (client_id, client_secret) if client_id else load_credentials()
            client = DigiKeyClient(*credentials, *load_locale_config())
            results = {}
            total   = len(self._new_part_numbers)
            for i, pn in enumerate(self._new_part_numbers):
                lc = client.check_lifecycle(pn)
                results[pn] = lc
                self.after(0, self._on_dk_progress, i + 1, total, pn, lc)
                if lc.get("stop_check"):
                    break
            self.after(0, self._on_dk_done, results)
        except Exception as e:
            self.after(0, self._on_dk_error, str(e))

    def _on_dk_progress(self, done, total, pn, lc):
        self._dk_progress.config(value=done)
        self._set_status(
            f"DigiKey API: {done} / {total}  —  {pn} → {lifecycle_label(lc.get('status_label', 'Unknown'))}",
            PALETTE["changed"])

    def _on_dk_done(self, results: dict):
        self._dk_results = results
        self._refresh_lifecycle_results()
        self._finish_lifecycle_check()
        self._dk_btn.config(state="normal", text=tr("DigiKeyで確認", "Check DigiKey"))
        self._show_lifecycle_completion("DigiKey", results)

    def _on_dk_error(self, error_msg: str):
        self._finish_lifecycle_check()
        self._dk_btn.config(state="normal", text=tr("DigiKeyで確認", "Check DigiKey"))
        self._set_status(tr(f"DigiKey エラー: {error_msg}", f"DigiKey error: {error_msg}"), PALETTE["removed"])
        messagebox.showerror(tr("DigiKey APIエラー", "DigiKey API error"), error_msg)

    # ----------------------------------------------------------
    # Mouser ライフサイクルチェック
    # ----------------------------------------------------------

    def _run_mouser_check(self):
        if not self._new_part_numbers:
            messagebox.showwarning(tr("比較結果なし", "No comparison results"), tr("先にBOMを比較してください。", "Compare the BOMs first."))
            return
        if not MOUSER_AVAILABLE:
            messagebox.showerror(tr("依存パッケージのエラー", "Missing dependency"),
                tr("requestsライブラリが見つかりません。pip install requests を実行してください。",
                   "The requests library is missing. Run pip install requests."))
            return

        if not self._save_credentials("Mouser"):
            return

        self._set_inputs_enabled(False)
        self._run_btn.config(state="disabled")
        self._dk_btn.config(state="disabled")
        self._ms_btn.config(state="disabled")
        self._ms_btn.config(state="disabled", text=tr("照会中…", "Checking…"))
        self._ms_progress.config(value=0, maximum=len(self._new_part_numbers))
        self._set_status(tr(f"Mouser API: 0 / {len(self._new_part_numbers)} 件…",
                            f"Mouser API: 0 / {len(self._new_part_numbers)} parts…"),
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
            results = {}
            total   = len(self._new_part_numbers)
            for i, pn in enumerate(self._new_part_numbers):
                lc = client.check_lifecycle(pn, self._new_manufacturers.get(pn, ""))
                results[pn] = lc
                self.after(0, self._on_ms_progress, i + 1, total, pn, lc)
                if lc.get("stop_check"):
                    break
            self.after(0, self._on_ms_done, results)
        except Exception as e:
            self.after(0, self._on_ms_error, str(e))

    def _on_ms_progress(self, done: int, total: int, pn: str, lc: dict):
        self._ms_progress.config(value=done)
        self._set_status(
            f"Mouser API: {done} / {total}  —  {pn} → {lifecycle_label(lc.get('status_label', 'Unknown'))}",
            PALETTE["changed"])

    def _on_ms_done(self, results: dict):
        self._ms_results = results
        self._refresh_lifecycle_results()
        self._finish_lifecycle_check()
        self._ms_btn.config(state="normal", text=tr("Mouserで確認", "Check Mouser"))
        self._show_lifecycle_completion("Mouser", results)

    def _on_ms_error(self, error_msg: str):
        self._finish_lifecycle_check()
        self._ms_btn.config(state="normal", text=tr("Mouserで確認", "Check Mouser"))
        self._set_status(tr(f"Mouser エラー: {error_msg}", f"Mouser error: {error_msg}"), PALETTE["removed"])
        messagebox.showerror(tr("Mouser APIエラー", "Mouser API error"), error_msg)

    def _finish_lifecycle_check(self):
        self._set_inputs_enabled(True)
        self._run_btn.config(state="normal")
        self._dk_btn.config(state="normal")
        self._ms_btn.config(state="normal")

    def _show_lifecycle_completion(self, provider, results):
        errors = [entry["error"] for entry in results.values() if entry.get("error")]
        not_found = sum(entry.get("status_label") == "Not Found" for entry in results.values())
        total = len(self._new_part_numbers)
        self._set_status(
            tr(f"{provider}　照会 {len(results)}/{total} 件　該当なし {not_found} 件　エラー {len(errors)} 件",
               f"{provider} · {len(results)}/{total} checked · {not_found} not found · {len(errors)} errors"),
            PALETTE["removed"] if errors else PALETTE["active"])
        self._notebook.select(self._lifecycle_frame)
        if errors:
            if len(errors) == len(results):
                messagebox.showerror(tr(f"{provider} APIエラー", f"{provider} API error"), errors[0])
            self._lc_detail.set(f"{provider}: {errors[0]}")

    def _refresh_lifecycle_results(self):
        merged = merge_lifecycle_results(self._dk_results, self._ms_results)
        self._populate_lifecycle_tab(merged)
        for key in ("obsolete", "nrnd"):
            count = sum(result.get("lifecycle") == key for result in merged.values())
            self._summary_cards[key].config(text=str(count))

    def _clear_lifecycle_tab(self):
        self._lc_detail.set("")
        for item in self._lc_tree.get_children():
            self._lc_tree.delete(item)
        self._candidates_by_row.clear()
        self._sub_tree.delete(*self._sub_tree.get_children())
        self._on_candidate_select()

    def _populate_lifecycle_tab(self, results: dict):
        self._clear_lifecycle_tab()
        cols = get_column_names()

        order = {LIFECYCLE_OBSOLETE: 0, LIFECYCLE_NRND: 1,
                 LIFECYCLE_ACTIVE: 2, LIFECYCLE_UNKNOWN: 3}
        sorted_items = sorted(results.items(),
            key=lambda kv: order.get(kv[1].get("lifecycle", "unknown"), 99))

        for pn, lc in sorted_items:
            lifecycle = lc.get("lifecycle", LIFECYCLE_UNKNOWN)
            statuses = []
            for provider_results in (self._dk_results, self._ms_results):
                response = provider_results.get(pn)
                if response is None:
                    statuses.append("—")
                elif response.get("error") and response["lifecycle"] == LIFECYCLE_UNKNOWN:
                    statuses.append(tr("エラー", "Error"))
                else:
                    statuses.append(lifecycle_label(response.get("status_label", "Unknown")))

            mfr = desc = ""
            if self._results is not None:
                added = self._results.get("added")
                if added is not None and pn in added.index:
                    mfr  = added.loc[pn, cols["manufacturer"]]
                    desc = added.loc[pn, cols["description"]]

            self._lc_tree.insert("", "end",
                values=[pn, mfr, *statuses, desc],
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
        errors = [f"{provider}: {result['error']}"
                  for provider, result in (("DigiKey", dk_lc), ("Mouser", ms_lc))
                  if result.get("error")]
        self._lc_detail.set("\n".join(errors))
        for sub in ms_lc.get("substitutes", []):
            all_subs.append({**sub, "source": "Mouser"})

        self._candidates_by_row.clear()
        self._sub_tree.delete(*self._sub_tree.get_children())
        self._on_candidate_select()

        if not all_subs:
            if errors:
                message = tr("代替品を確認できませんでした", "Replacement lookup failed")
            else:
                message = tr("API応答に代替品候補なし", "No replacements returned")
            self._sub_tree.insert("", "end",
                values=[message, "", "", "", ""], tags=("sub_row",))
            return

        for i, sub in enumerate(all_subs):
            dist_pn = sub.get("digikey_part_number", "") or sub.get("mouser_part_number", "")
            row = self._sub_tree.insert("", "end", values=[
                sub.get("mfr_part_number", ""),
                dist_pn,
                sub.get("manufacturer",   ""),
                sub.get("description",    ""),
                sub.get("source",         ""),
            ], tags=("sub_row" if i % 2 == 0 else "sub_alt",))
            self._candidates_by_row[row] = (pn, sub)

    def _selected_candidate(self):
        selection = self._sub_tree.selection()
        return self._candidates_by_row.get(selection[0]) if selection else None

    def _on_candidate_select(self, event=None):
        state = "normal" if self._selected_candidate() else "disabled"
        for button in self._candidate_actions:
            button.config(state=state)

    def _open_candidate_page(self, event=None):
        selected = self._selected_candidate()
        if selected is None:
            return
        _, candidate = selected
        link = candidate.get("product_url") or ""
        host = "digikey.com" if candidate["source"] == "DigiKey" else "mouser.com"
        parsed = urlsplit(link)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" or not (hostname == host or hostname.endswith("." + host)):
            part = (candidate.get("digikey_part_number") or candidate.get("mouser_part_number")
                    or candidate.get("mfr_part_number"))
            if not part:
                return
            if host == "digikey.com":
                link = "https://www.digikey.com/en/products/result?" + urlencode({"keywords": part})
            else:
                link = "https://www.mouser.com/c/?" + urlencode({"q": part})
        if candidate["source"] == "Mouser" and not candidate.get("product_url"):
            def resolve():
                try:
                    from src.mouser_client import create_client, _find_best_match
                    part = candidate.get("mouser_part_number") or candidate.get("mfr_part_number")
                    data = _find_best_match(create_client().search_part(part), part) or {}
                    product_url = data.get("ProductDetailUrl") or ""
                    parsed = urlsplit(product_url)
                    host = parsed.hostname or ""
                    if parsed.scheme == "https" and (host == "mouser.com" or host.endswith(".mouser.com")):
                        self.after(0, webbrowser.open, product_url)
                        return
                except Exception:
                    pass
                self.after(0, webbrowser.open, link)
            threading.Thread(target=resolve, daemon=True).start()
        else:
            webbrowser.open(link)

    def _compare_candidate(self):
        selected = self._selected_candidate()
        if selected is None:
            return
        part, candidate = selected
        provider = candidate["source"]
        result = (self._dk_results if provider == "DigiKey" else self._ms_results).get(part, {})
        dialog = tk.Toplevel(self)
        dialog.title(tr("代替品との仕様比較", "Replacement specifications"))
        dialog.geometry("740x430")
        dialog.transient(self)
        candidate_number = (candidate.get("mfr_part_number") or candidate.get("digikey_part_number")
                            or candidate.get("mouser_part_number") or "—")
        table = ttk.Treeview(dialog, columns=("field", "original", "candidate"),
                             show="headings", style="Material.Treeview")
        table.heading("field", text=tr("仕様", "Specification"))
        table.heading("original", text=f'{tr("元の部品", "Original")} · {part}')
        table.heading("candidate", text=f'{tr("代替品候補", "Replacement")} · {candidate_number}')
        for column, width in (("field", 180), ("original", 275), ("candidate", 275)):
            table.column(column, width=width, anchor="w")
        status = ttk.Label(dialog, text=tr("候補の仕様を照会中…", "Looking up replacement specifications…"))
        status.pack(side="bottom", anchor="w", padx=8, pady=8)
        scrollbar = ttk.Scrollbar(dialog, command=table.yview)
        scrollbar.pack(side="right", fill="y")
        table.configure(yscrollcommand=scrollbar.set)
        table.pack(fill="both", expand=True)

        def display(specifications, description, message=""):
            if not dialog.winfo_exists():
                return
            status.config(text=message)
            table.delete(*table.get_children())
            table.insert("", "end", values=(tr("説明", "Description"),
                         result.get("description") or "—", description or "—"))
            left = {item["name"]: item["value"] for item in result.get("source_specs", [])}
            right = {item["name"]: item["value"] for item in specifications}
            for name in dict.fromkeys((*left, *right)):
                table.insert("", "end", values=(name, left.get(name, "—"), right.get(name, "—")))

        def worker():
            try:
                if provider == "DigiKey":
                    from src.digikey_client import create_client, _extract_specs
                    lookup = candidate.get("digikey_part_number") or candidate_number
                    details = create_client().get_product_details(lookup) or {}
                    product = details.get("Product") or {}
                    specs = _extract_specs(product)
                    description = (product.get("Description") or {}).get("ProductDescription", "")
                else:
                    from src.mouser_client import create_client, _find_best_match, product_specs
                    data = _find_best_match(create_client().search_part(candidate_number), candidate_number) or {}
                    specs = product_specs(data)
                    description = data.get("Description", "")
                message = "" if specs else tr("候補の仕様データはありません。", "No replacement specifications returned.")
            except Exception:
                specs, description = candidate.get("specs", []), candidate.get("description", "")
                message = tr("候補の詳細を取得できませんでした。", "Could not retrieve replacement details.")
            self.after(0, display, specs, description, message)

        display(candidate.get("specs", []), candidate.get("description", ""), status.cget("text"))
        threading.Thread(target=worker, daemon=True).start()

    # ----------------------------------------------------------
    # レポート保存
    # ----------------------------------------------------------

    def _save_report(self):
        if self._results is None:
            return
        path = filedialog.asksaveasfilename(
            title=tr("レポートの保存先", "Save report as"),
            defaultextension=".xlsx",
            filetypes=[(tr("Excelファイル", "Excel files"), "*.xlsx"), (tr("すべてのファイル", "All files"), "*.*")],
            initialfile="bom_diff_report.xlsx")
        if not path:
            return
        try:
            save_report(self._results, path, self._dk_results or None,
                        mouser_results=self._ms_results or None)
            self._set_status(tr(f"保存しました → {os.path.basename(path)}", f"Saved → {os.path.basename(path)}"), PALETTE["active"])
            messagebox.showinfo(tr("保存完了", "Saved"), tr(f"レポートを保存しました:\n{path}", f"Report saved to:\n{path}"))
        except Exception as e:
            messagebox.showerror(tr("保存エラー", "Save error"), str(e))


def launch():
    app = BomApp()
    app.mainloop()
