"""
settings_dialog.py - カラム名設定ダイアログ

メインウィンドウのボタンから呼び出すモーダルダイアログ。
変更できる設定:
  ・BOM の4カラム名（Excel 上の列ヘッダー）
  ・Excel レポートの4シート名
設定は「保存」ボタンで config.ini に自動保存されます。
"""

import tkinter as tk
from tkinter import ttk, messagebox

from src.column_config import (
    load_column_config,
    save_column_config,
    reset_column_config,
    COLUMN_LABELS,
    SHEET_LABELS,
    DEFAULT_COLUMNS,
    DEFAULT_SHEET_NAMES,
)

PALETTE = {
    "bg_dark":    "#0D1117",
    "bg_panel":   "#161B22",
    "bg_card":    "#1C2333",
    "border":     "#30363D",
    "accent":     "#58A6FF",
    "text":       "#E6EDF3",
    "text_muted": "#8B949E",
    "warn":       "#D29922",
    "mono":       "#C9D1D9",
}

FONT_TITLE = ("Segoe UI", 12, "bold")
FONT_HEAD  = ("Segoe UI", 10, "bold")
FONT_UI    = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 10)


class SettingsDialog(tk.Toplevel):
    """カラム名・シート名を設定するモーダルダイアログ"""

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title("設定  —  カラム名 / シート名")
        self.geometry("580x580")
        self.resizable(False, False)
        self.configure(bg=PALETTE["bg_dark"])
        self.transient(parent)
        self.grab_set()
        self.changed = False

        cfg = load_column_config()
        self._col_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value=val)
            for key, val in cfg["columns"].items()
        }
        self._sheet_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value=val)
            for key, val in cfg["sheet_names"].items()
        }

        self._build_ui()

        # 親ウィンドウの中央に配置
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------

    def _build_ui(self):
        # ── ヘッダー ──
        header = tk.Frame(self, bg=PALETTE["bg_panel"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⚙  カラム名 / シート名の設定",
            bg=PALETTE["bg_panel"], fg=PALETTE["text"],
            font=FONT_TITLE).pack(side="left", padx=16, pady=10)
        tk.Frame(self, bg=PALETTE["border"], height=1).pack(fill="x")

        # ── フッター（先に配置して上部コンテンツが押し出されないようにする）──
        self._build_footer()

        # ── スクロール可能なコンテンツ ──
        canvas = tk.Canvas(self, bg=PALETTE["bg_dark"],
            highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=PALETTE["bg_dark"])
        win  = canvas.create_window((0, 0), window=body, anchor="nw")

        body.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.bind("<Destroy>",
            lambda e: canvas.unbind_all("<MouseWheel>") if e.widget is self else None)

        # ── セクション1: BOM カラム名 ──
        self._build_section(
            body, "BOM カラム名",
            "Excel ファイル上の列ヘッダー名（BOMファイルの1行目）",
            self._col_vars, COLUMN_LABELS, DEFAULT_COLUMNS,
        )
        tk.Frame(body, bg=PALETTE["border"], height=1).pack(
            fill="x", padx=16, pady=8)

        # ── セクション2: レポートシート名 ──
        self._build_section(
            body, "Excel レポートのシート名",
            "保存する Excel レポートのシート見出し名",
            self._sheet_vars, SHEET_LABELS, DEFAULT_SHEET_NAMES,
        )
        tk.Frame(body, bg=PALETTE["bg_dark"], height=12).pack()

    def _build_section(self, parent, title, subtitle,
                       vars_dict, labels, defaults):
        """設定項目のセクション（タイトル + 入力欄グループ）を構築する"""
        hdr = tk.Frame(parent, bg=PALETTE["bg_dark"])
        hdr.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(hdr, text=title,
            bg=PALETTE["bg_dark"], fg=PALETTE["text"],
            font=FONT_HEAD).pack(anchor="w")
        tk.Label(hdr, text=subtitle,
            bg=PALETTE["bg_dark"], fg=PALETTE["text_muted"],
            font=FONT_SMALL).pack(anchor="w")

        card = tk.Frame(parent, bg=PALETTE["bg_card"])
        card.pack(fill="x", padx=16)

        for i, (key, var) in enumerate(vars_dict.items()):
            if i > 0:
                tk.Frame(card, bg=PALETTE["border"], height=1).pack(
                    fill="x", padx=8)

            row = tk.Frame(card, bg=PALETTE["bg_card"])
            row.pack(fill="x", padx=12, pady=7)

            # ラベル（固定幅で左揃え）
            tk.Label(row, text=labels.get(key, key),
                bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
                font=FONT_LABEL, width=26, anchor="w"
                ).pack(side="left")

            # テキスト入力欄
            tk.Entry(row, textvariable=var,
                bg=PALETTE["bg_dark"], fg=PALETTE["mono"],
                insertbackground=PALETTE["accent"],
                relief="flat", font=FONT_MONO, bd=0
                ).pack(side="left", fill="x", expand=True, padx=(8, 4))

            # ⟳ ボタン：この行だけデフォルトに戻す
            def _reset_one(k=key, v=var, d=defaults):
                v.set(d[k])
            tk.Button(row, text="⟳",
                bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
                relief="flat", cursor="hand2",
                font=("Segoe UI", 11), padx=6,
                command=_reset_one
                ).pack(side="left")

    def _build_footer(self):
        """ダイアログ下部のボタン行を構築する"""
        tk.Frame(self, bg=PALETTE["border"], height=1).pack(
            fill="x", side="bottom")
        footer = tk.Frame(self, bg=PALETTE["bg_panel"])
        footer.pack(fill="x", side="bottom")

        # 右側: キャンセル / 保存
        tk.Button(footer, text="キャンセル",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            padx=14, pady=8, command=self.destroy
            ).pack(side="right", padx=(4, 16), pady=10)

        tk.Button(footer, text="✓  保存",
            bg=PALETTE["accent"], fg="#0D1117",
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=8, command=self._on_save
            ).pack(side="right", padx=4, pady=10)

        # 左側: すべてリセット
        tk.Button(footer, text="↺  すべてリセット",
            bg=PALETTE["bg_card"], fg=PALETTE["warn"],
            font=FONT_UI, relief="flat", cursor="hand2",
            padx=12, pady=8, command=self._on_reset_all
            ).pack(side="left", padx=16, pady=10)

    # ----------------------------------------------------------
    # イベントハンドラー
    # ----------------------------------------------------------

    def _on_save(self):
        """入力値を検証して config.ini に保存する"""
        columns     = {k: v.get().strip() for k, v in self._col_vars.items()}
        sheet_names = {k: v.get().strip() for k, v in self._sheet_vars.items()}

        # 空欄チェック
        empty = (
            [COLUMN_LABELS[k] for k, v in columns.items()     if not v] +
            [SHEET_LABELS[k]  for k, v in sheet_names.items() if not v]
        )
        if empty:
            messagebox.showwarning(
                "入力エラー",
                "以下の項目が空欄です:\n" + "\n".join(f"  ・{n}" for n in empty),
                parent=self)
            return

        # カラム名の重複チェック
        vals = list(columns.values())
        if len(vals) != len(set(vals)):
            messagebox.showwarning(
                "入力エラー",
                "カラム名が重複しています。\n各カラムに異なる名前を設定してください。",
                parent=self)
            return

        save_column_config({"columns": columns, "sheet_names": sheet_names})
        self.changed = True
        messagebox.showinfo(
            "保存完了",
            "設定を保存しました。\n次の比較実行から新しいカラム名が適用されます。",
            parent=self)
        self.destroy()

    def _on_reset_all(self):
        """全設定をデフォルトに戻す"""
        if not messagebox.askyesno(
            "リセット確認",
            "すべての設定をデフォルト値に戻しますか？",
            parent=self):
            return
        cfg = reset_column_config()
        for k, v in self._col_vars.items():
            v.set(cfg["columns"][k])
        for k, v in self._sheet_vars.items():
            v.set(cfg["sheet_names"][k])
        messagebox.showinfo("リセット完了", "デフォルト値に戻しました。", parent=self)


def open_settings(parent: tk.Tk) -> bool:
    """
    設定ダイアログを開いて閉じるまで待つ。

    Returns:
        bool: 設定が保存された場合 True
    """
    dialog = SettingsDialog(parent)
    parent.wait_window(dialog)
    return getattr(dialog, "changed", False)
