"""
gui.py - BOM比較ツールのGUIモジュール（DigiKey API + カラム名設定対応）

v2.1 変更点:
  - ヘッダーに ⚙ 設定ボタンを追加
  - 設定変更後、タブのカラム名表示を自動更新
  - loader / comparator / report のカラム名は column_config から動的取得
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


# ============================================================
# カラーパレット
# ============================================================
PALETTE = {
    "bg_dark":      "#0D1117",
    "bg_panel":     "#161B22",
    "bg_card":      "#1C2333",
    "border":       "#30363D",
    "accent":       "#58A6FF",
    "accent_dim":   "#1F4788",
    "text":         "#E6EDF3",
    "text_muted":   "#8B949E",
    "added":        "#238636",
    "added_bg":     "#0D2818",
    "removed":      "#DA3633",
    "removed_bg":   "#2D0F0F",
    "changed":      "#D29922",
    "changed_bg":   "#2D2006",
    "mono":         "#C9D1D9",
    "obsolete":     "#FF4444",
    "obsolete_bg":  "#3D0000",
    "nrnd":         "#FF8C00",
    "nrnd_bg":      "#3D2000",
    "active":       "#3FB950",
    "active_bg":    "#0D2818",
    "unknown_bg":   "#1C2333",
}

FONT_UI    = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 10)
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_HEAD  = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 8)


class BomApp(tk.Tk):
    """BOM比較ツールのメインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.title("BOM Diff Tool")
        self.geometry("1280x820")
        self.minsize(900, 600)
        self.configure(bg=PALETTE["bg_dark"])

        self._results          = None
        self._dk_results       = {}
        self._new_part_numbers = []

        self._build_ui()

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------

    def _build_ui(self):
        self._configure_styles()
        self._build_header()

        body = tk.Frame(self, bg=PALETTE["bg_dark"])
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        left = tk.Frame(body, bg=PALETTE["bg_dark"], width=290)
        left.pack(side="left", fill="y", padx=(0, 12))
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
            background=PALETTE["bg_dark"], borderwidth=0)
        style.configure("Dark.TNotebook.Tab",
            background=PALETTE["bg_card"], foreground=PALETTE["text_muted"],
            padding=[14, 6], font=FONT_LABEL, borderwidth=0)
        style.map("Dark.TNotebook.Tab",
            background=[("selected", PALETTE["bg_panel"])],
            foreground=[("selected", PALETTE["text"])])

        style.configure("Dark.Treeview",
            background=PALETTE["bg_panel"], foreground=PALETTE["text"],
            fieldbackground=PALETTE["bg_panel"], rowheight=28,
            font=FONT_MONO, borderwidth=0)
        style.configure("Dark.Treeview.Heading",
            background=PALETTE["bg_card"], foreground=PALETTE["text_muted"],
            font=FONT_HEAD, relief="flat")
        style.map("Dark.Treeview",
            background=[("selected", PALETTE["accent_dim"])],
            foreground=[("selected", PALETTE["text"])])

        style.configure("Dark.Vertical.TScrollbar",
            background=PALETTE["bg_card"], troughcolor=PALETTE["bg_dark"],
            arrowcolor=PALETTE["text_muted"], borderwidth=0)

        style.configure("BomTool.Horizontal.TProgressbar",
            troughcolor=PALETTE["bg_card"], background=PALETTE["accent"],
            borderwidth=0)

    def _build_header(self):
        header = tk.Frame(self, bg=PALETTE["bg_panel"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="⬡  BOM Diff Tool",
            bg=PALETTE["bg_panel"], fg=PALETTE["text"],
            font=FONT_TITLE).pack(side="left", padx=20, pady=14)

        # ── ⚙ 設定ボタン（右端） ──
        tk.Button(header, text="⚙  設定",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            padx=12, pady=6,
            command=self._open_settings
            ).pack(side="right", padx=16, pady=10)

        tk.Label(header, text="v2.1  +  DigiKey API",
            bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
            font=FONT_LABEL).pack(side="right", padx=4)

        tk.Frame(self, bg=PALETTE["border"], height=1).pack(fill="x")

    def _build_left_panel(self, parent):

        def section_label(text):
            tk.Label(parent, text=text, bg=PALETTE["bg_dark"],
                fg=PALETTE["text_muted"], font=FONT_SMALL,
                anchor="w").pack(fill="x", pady=(16, 4))

        section_label("OLD BOM FILE")
        self._old_path = tk.StringVar(value="old.xlsx")
        self._build_file_row(parent, self._old_path)

        section_label("NEW BOM FILE")
        self._new_path = tk.StringVar(value="new.xlsx")
        self._build_file_row(parent, self._new_path)

        tk.Frame(parent, bg=PALETTE["bg_dark"], height=12).pack()
        self._run_btn = tk.Button(parent, text="▶  Compare",
            bg=PALETTE["accent"], fg="#0D1117",
            font=("Segoe UI", 11, "bold"), relief="flat",
            cursor="hand2", pady=10, command=self._run_comparison)
        self._run_btn.pack(fill="x")

        self._progress = ttk.Progressbar(parent,
            style="BomTool.Horizontal.TProgressbar", mode="indeterminate")
        self._progress.pack(fill="x", pady=(8, 0))

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill="x", pady=16)

        section_label("DIGIKEY API")

        tk.Label(parent, text="Client ID", bg=PALETTE["bg_dark"],
            fg=PALETTE["text_muted"], font=FONT_SMALL, anchor="w").pack(fill="x")
        self._dk_client_id = tk.StringVar()
        self._build_entry(parent, self._dk_client_id, show="")

        tk.Label(parent, text="Client Secret", bg=PALETTE["bg_dark"],
            fg=PALETTE["text_muted"], font=FONT_SMALL, anchor="w").pack(fill="x", pady=(6, 0))
        self._dk_client_secret = tk.StringVar()
        self._build_entry(parent, self._dk_client_secret, show="•")

        tk.Frame(parent, bg=PALETTE["bg_dark"], height=8).pack()

        self._dk_btn = tk.Button(parent, text="⚡  Check Lifecycle",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            pady=8, state="disabled", command=self._run_digikey_check)
        self._dk_btn.pack(fill="x")

        self._dk_progress = ttk.Progressbar(parent,
            style="BomTool.Horizontal.TProgressbar", mode="determinate")
        self._dk_progress.pack(fill="x", pady=(6, 0))

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill="x", pady=16)

        section_label("SUMMARY")
        self._summary_cards = {}
        for key, label, color in [
            ("added",    "Added",    PALETTE["added"]),
            ("removed",  "Removed",  PALETTE["removed"]),
            ("qty",      "Qty Δ",    PALETTE["changed"]),
            ("mfr",      "Mfr Δ",    PALETTE["changed"]),
            ("obsolete", "Obsolete", PALETTE["obsolete"]),
            ("nrnd",     "NRND",     PALETTE["nrnd"]),
        ]:
            row = tk.Frame(parent, bg=PALETTE["bg_card"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=PALETTE["bg_card"],
                fg=PALETTE["text_muted"], font=FONT_LABEL,
                width=10, anchor="w").pack(side="left", padx=10, pady=5)
            lbl = tk.Label(row, text="—", bg=PALETTE["bg_card"],
                fg=color, font=("Consolas", 11, "bold"))
            lbl.pack(side="right", padx=10)
            self._summary_cards[key] = lbl

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill="x", pady=16)

        self._save_btn = tk.Button(parent, text="↓  Save Excel Report",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            pady=8, state="disabled", command=self._save_report)
        self._save_btn.pack(fill="x")

    def _build_file_row(self, parent, var: tk.StringVar):
        frame = tk.Frame(parent, bg=PALETTE["bg_card"])
        frame.pack(fill="x")
        tk.Entry(frame, textvariable=var, bg=PALETTE["bg_card"],
            fg=PALETTE["mono"], insertbackground=PALETTE["accent"],
            relief="flat", font=FONT_MONO, bd=0
            ).pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        tk.Button(frame, text="…", bg=PALETTE["bg_card"],
            fg=PALETTE["text_muted"], relief="flat", cursor="hand2",
            font=("Segoe UI", 11), padx=8,
            command=lambda v=var: self._browse_file(v)
            ).pack(side="right")

    def _build_entry(self, parent, var: tk.StringVar, show: str):
        frame = tk.Frame(parent, bg=PALETTE["bg_card"])
        frame.pack(fill="x")
        tk.Entry(frame, textvariable=var, bg=PALETTE["bg_card"],
            fg=PALETTE["mono"], insertbackground=PALETTE["accent"],
            relief="flat", font=FONT_MONO, bd=0, show=show
            ).pack(fill="x", padx=8, pady=6)

    def _build_result_panel(self, parent):
        self._notebook = ttk.Notebook(parent, style="Dark.TNotebook")
        self._notebook.pack(fill="both", expand=True)
        self._tabs = {}
        self._build_diff_tabs()

        # Lifecycle タブ
        dk_frame = tk.Frame(self._notebook, bg=PALETTE["bg_panel"])
        self._notebook.add(dk_frame, text="⚡  Lifecycle")
        self._build_lifecycle_tab(dk_frame)

    def _build_diff_tabs(self):
        """
        BOM差分の4タブを構築する。
        カラム名は column_config から取得するため、設定変更後に再構築できる。
        """
        cols = get_column_names()
        pn   = cols["part_number"]
        mfr  = cols["manufacturer"]
        qty  = cols["quantity"]
        desc = cols["description"]

        tab_defs = [
            ("added",   "＋  Added",
             [pn, mfr, qty, desc], PALETTE["added_bg"]),
            ("removed", "－  Removed",
             [pn, mfr, qty, desc], PALETTE["removed_bg"]),
            ("qty",     "△  Qty Changed",
             [pn, f"Old {qty}", f"New {qty}"], PALETTE["changed_bg"]),
            ("mfr",     "△  Mfr Changed",
             [pn, f"Old {mfr}", f"New {mfr}"], PALETTE["changed_bg"]),
        ]
        for key, label, columns, row_bg in tab_defs:
            frame = tk.Frame(self._notebook, bg=PALETTE["bg_panel"])
            self._notebook.add(frame, text=label)
            self._tabs[key] = self._build_treeview(frame, columns, row_bg)

    def _build_treeview(self, parent, columns: list, row_bg: str) -> ttk.Treeview:
        container = tk.Frame(parent, bg=PALETTE["bg_panel"])
        container.pack(fill="both", expand=True, padx=1, pady=1)

        vsb = ttk.Scrollbar(container, orient="vertical",
            style="Dark.Vertical.TScrollbar")
        vsb.pack(side="right", fill="y")

        tree = ttk.Treeview(container, columns=columns, show="headings",
            style="Dark.Treeview", yscrollcommand=vsb.set)
        vsb.configure(command=tree.yview)
        tree.pack(fill="both", expand=True)

        for col in columns:
            # 長いカラム名は広めに、短いものは狭めに
            w = max(100, min(len(col) * 11, 280))
            tree.column(col, width=w, minwidth=60, anchor="w")
            tree.heading(col, text=col, anchor="w")

        tree.tag_configure("colored",     background=row_bg)
        tree.tag_configure("colored_alt", background=PALETTE["bg_panel"])
        return tree

    def _build_lifecycle_tab(self, parent):
        tk.Label(parent,
            text="LIFECYCLE STATUS  (click row to view substitutes)",
            bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
            font=FONT_SMALL, anchor="w").pack(fill="x", padx=8, pady=(8, 2))

        lc_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        lc_frame.pack(fill="both", expand=True, padx=1, pady=1)

        vsb_lc = ttk.Scrollbar(lc_frame, orient="vertical",
            style="Dark.Vertical.TScrollbar")
        vsb_lc.pack(side="right", fill="y")

        cols   = get_column_names()
        lc_cols = [cols["part_number"], cols["manufacturer"], "Status", cols["description"]]
        self._lc_tree = ttk.Treeview(lc_frame, columns=lc_cols,
            show="headings", style="Dark.Treeview", yscrollcommand=vsb_lc.set)
        vsb_lc.configure(command=self._lc_tree.yview)
        self._lc_tree.pack(fill="both", expand=True)

        for col in lc_cols:
            w = 120 if col == "Status" else max(100, min(len(col) * 11, 280))
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

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill="x", pady=4)

        tk.Label(parent, text="DIGIKEY SUBSTITUTES  (for selected part)",
            bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
            font=FONT_SMALL, anchor="w").pack(fill="x", padx=8, pady=(4, 2))

        sub_frame = tk.Frame(parent, bg=PALETTE["bg_panel"], height=200)
        sub_frame.pack(fill="x", padx=1, pady=(0, 4))
        sub_frame.pack_propagate(False)

        vsb_sub = ttk.Scrollbar(sub_frame, orient="vertical",
            style="Dark.Vertical.TScrollbar")
        vsb_sub.pack(side="right", fill="y")

        sub_cols = ["Mfr Part Number", "DigiKey Part Number",
                    "Manufacturer Name", "Description"]
        self._sub_tree = ttk.Treeview(sub_frame, columns=sub_cols,
            show="headings", style="Dark.Treeview", yscrollcommand=vsb_sub.set)
        vsb_sub.configure(command=self._sub_tree.yview)
        self._sub_tree.pack(fill="both", expand=True)

        for col in sub_cols:
            self._sub_tree.column(col, width=160, minwidth=60, anchor="w")
            self._sub_tree.heading(col, text=col, anchor="w")

        self._sub_tree.tag_configure("sub_row", background=PALETTE["bg_card"])
        self._sub_tree.tag_configure("sub_alt", background=PALETTE["bg_panel"])

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PALETTE["bg_panel"], height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=PALETTE["border"], height=1).pack(fill="x")
        self._status_var = tk.StringVar(
            value="Ready  —  Select files and click Compare")
        tk.Label(bar, textvariable=self._status_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
            font=("Segoe UI", 9), anchor="w"
            ).pack(side="left", padx=12, pady=4)

    # ----------------------------------------------------------
    # 設定ダイアログ
    # ----------------------------------------------------------

    def _open_settings(self):
        """
        設定ダイアログを開く。
        設定が保存された場合、差分タブのカラム名表示を再構築する。
        """
        changed = open_settings(self)
        if changed:
            self._rebuild_diff_tabs()
            self._set_status(
                "設定を更新しました。次の Compare から新しいカラム名が適用されます。")

    def _rebuild_diff_tabs(self):
        """
        差分タブ（Added / Removed / Qty Changed / Mfr Changed）を
        現在の column_config に合わせて再構築する。
        既存データはクリアされます。
        """
        # 先頭4タブ（差分タブ）を削除
        for _ in range(4):
            if self._notebook.tabs():
                self._notebook.forget(0)
        self._tabs = {}

        # Lifecycle タブを一時退避（idx=0 になっているはずなので取得）
        lc_frame_id = self._notebook.tabs()[0] if self._notebook.tabs() else None

        # 差分タブを先頭に再挿入
        cols = get_column_names()
        pn   = cols["part_number"]
        mfr  = cols["manufacturer"]
        qty  = cols["quantity"]
        desc = cols["description"]

        tab_defs = [
            ("added",   "＋  Added",
             [pn, mfr, qty, desc], PALETTE["added_bg"]),
            ("removed", "－  Removed",
             [pn, mfr, qty, desc], PALETTE["removed_bg"]),
            ("qty",     "△  Qty Changed",
             [pn, f"Old {qty}", f"New {qty}"], PALETTE["changed_bg"]),
            ("mfr",     "△  Mfr Changed",
             [pn, f"Old {mfr}", f"New {mfr}"], PALETTE["changed_bg"]),
        ]
        for i, (key, label, columns, row_bg) in enumerate(tab_defs):
            frame = tk.Frame(self._notebook, bg=PALETTE["bg_panel"])
            self._notebook.insert(i, frame, text=label)
            self._tabs[key] = self._build_treeview(frame, columns, row_bg)

        # データをクリア（カラム構造が変わっているため再比較が必要）
        self._results = None
        self._set_status(
            "設定変更後は ▶ Compare を再実行してください")

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
        self._set_status("Comparing…")

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
        self._dk_btn.config(state="normal", fg=PALETTE["accent"])
        self._save_btn.config(state="normal", fg=PALETTE["accent"])

        total = (len(results["added"]) + len(results["removed"])
                 + len(results["qty_changed"]) + len(results["mfr_changed"]))
        self._set_status(
            f"Done  —  {total} difference(s)  ·  {len(new_pns)} parts in new BOM  ·  "
            "Click ⚡ Check Lifecycle to query DigiKey")

    def _on_comparison_error(self, error_msg: str):
        self._progress.stop()
        self._run_btn.config(state="normal", text="▶  Compare")
        self._set_status(f"Error: {error_msg}")
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
        self._set_status(f"DigiKey API: 0 / {len(self._new_part_numbers)} parts…")

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
            f"DigiKey API: {done} / {total}  —  {pn} → {lc.get('status_label','?')}")

    def _on_dk_done(self, results: dict):
        self._dk_results = results
        self._populate_lifecycle_tab(results)

        obsolete_n = sum(1 for r in results.values() if r.get("lifecycle") == LIFECYCLE_OBSOLETE)
        nrnd_n     = sum(1 for r in results.values() if r.get("lifecycle") == LIFECYCLE_NRND)

        self._summary_cards["obsolete"].config(text=str(obsolete_n))
        self._summary_cards["nrnd"].config(text=str(nrnd_n))
        self._dk_btn.config(state="normal", text="⚡  Check Lifecycle")
        self._set_status(f"DigiKey check done  —  Obsolete: {obsolete_n}  NRND: {nrnd_n}")
        self._notebook.select(4)

    def _on_dk_error(self, error_msg: str):
        self._dk_btn.config(state="normal", text="⚡  Check Lifecycle")
        self._set_status(f"DigiKey Error: {error_msg}")
        messagebox.showerror("DigiKey APIエラー", error_msg)

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

        pn          = selection[0]
        substitutes = self._dk_results.get(pn, {}).get("substitutes", [])

        for item in self._sub_tree.get_children():
            self._sub_tree.delete(item)

        if not substitutes:
            self._sub_tree.insert("", "end",
                values=["（代替品なし）", "", "", ""], tags=("sub_row",))
            return

        for i, sub in enumerate(substitutes):
            self._sub_tree.insert("", "end", values=[
                sub.get("mfr_part_number",     ""),
                sub.get("digikey_part_number", ""),
                sub.get("manufacturer",         ""),
                sub.get("description",          ""),
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
            self._set_status(f"Saved → {os.path.basename(path)}")
            messagebox.showinfo("保存完了", f"レポートを保存しました:\n{path}")
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))

    def _set_status(self, text: str):
        self._status_var.set(text)


def launch():
    app = BomApp()
    app.mainloop()
