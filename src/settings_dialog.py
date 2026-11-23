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

from src.ui_language import tr
from src.column_config import (
    load_column_config,
    save_column_config,
    reset_column_config,
    DEFAULT_COLUMNS,
    DEFAULT_SHEET_NAMES,
)

from src.material_theme import PALETTE

FONT_TITLE = ("Segoe UI", 16)
FONT_HEAD  = ("Segoe UI", 10, "bold")
FONT_UI    = ("Segoe UI", 10)
FONT_LABEL = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 10)


class SettingsDialog(tk.Toplevel):
    """カラム名・シート名を設定するモーダルダイアログ"""

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title(tr("設定  —  カラム名 / シート名", "Column and sheet settings"))
        self.geometry("580x580")
        self.resizable(False, False)
        self.configure(bg=PALETTE["surface_low"])
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

        self._column_labels = {
            "part_number": tr("メーカー型番（照合キー）", "Manufacturer part number (key)"),
            "manufacturer": tr("メーカー名", "Manufacturer name"),
            "quantity": tr("数量", "Quantity"),
            "description": tr("説明", "Description"),
        }
        self._sheet_labels = {
            "added": tr("追加部品", "Added parts"),
            "removed": tr("削除部品", "Removed parts"),
            "qty": tr("数量変更", "Quantity changes"),
            "mfr": tr("メーカー変更", "Manufacturer changes"),
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
        header = tk.Frame(self, bg=PALETTE["surface"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=tr("列・シート設定", "Column and sheet settings"),
            bg=PALETTE["surface"], fg=PALETTE["on_surface"],
            font=FONT_TITLE).pack(side="left", padx=16, pady=10)
        tk.Frame(self, bg=PALETTE["outline_variant"], height=1).pack(fill="x")

        # ── フッター（先に配置して上部コンテンツが押し出されないようにする）──
        self._build_footer()

        # ── スクロール可能なコンテンツ ──
        canvas = tk.Canvas(self, bg=PALETTE["surface_low"],
            highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=PALETTE["surface_low"])
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
            body, tr("BOM カラム名", "BOM column names"),
            tr("Excel ファイル上の列ヘッダー名（BOMファイルの1行目）", "Excel column headers in the first row of the BOM file."),
            self._col_vars, self._column_labels, DEFAULT_COLUMNS,
        )
        tk.Frame(body, bg=PALETTE["outline_variant"], height=1).pack(
            fill="x", padx=16, pady=8)

        # ── セクション2: レポートシート名 ──
        self._build_section(
            body, tr("Excel レポートのシート名", "Excel report sheet names"),
            tr("保存する Excel レポートのシート見出し名", "Worksheet names in the exported Excel report."),
            self._sheet_vars, self._sheet_labels, DEFAULT_SHEET_NAMES,
        )
        tk.Frame(body, bg=PALETTE["surface_low"], height=12).pack()

    def _build_section(self, parent, title, subtitle,
                       vars_dict, labels, defaults):
        """設定項目のセクション（タイトル + 入力欄グループ）を構築する"""
        hdr = tk.Frame(parent, bg=PALETTE["surface_low"])
        hdr.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(hdr, text=title,
            bg=PALETTE["surface_low"], fg=PALETTE["on_surface"],
            font=FONT_HEAD).pack(anchor="w")
        tk.Label(hdr, text=subtitle,
            bg=PALETTE["surface_low"], fg=PALETTE["on_surface_variant"],
            font=FONT_SMALL).pack(anchor="w")

        card = tk.Frame(parent, bg=PALETTE["surface_container"])
        card.pack(fill="x", padx=16)

        for i, (key, var) in enumerate(vars_dict.items()):
            if i > 0:
                tk.Frame(card, bg=PALETTE["outline_variant"], height=1).pack(
                    fill="x", padx=8)

            row = tk.Frame(card, bg=PALETTE["surface_container"])
            row.pack(fill="x", padx=12, pady=7)

            # ラベル（固定幅で左揃え）
            tk.Label(row, text=labels.get(key, key),
                bg=PALETTE["surface_container"], fg=PALETTE["on_surface_variant"],
                font=FONT_LABEL, width=26, anchor="w"
                ).pack(side="left")

            # テキスト入力欄
            tk.Entry(row, textvariable=var,
                bg=PALETTE["surface_low"], fg=PALETTE["on_surface"],
                insertbackground=PALETTE["primary"],
                relief="flat", font=FONT_MONO, bd=5,
                highlightthickness=1, highlightbackground=PALETTE["outline"],
                highlightcolor=PALETTE["primary"]
                ).pack(side="left", fill="x", expand=True, padx=(8, 4))

            # ⟳ ボタン：この行だけデフォルトに戻す
            def _reset_one(k=key, v=var, d=defaults):
                v.set(d[k])
            tk.Button(row, text="⟳",
                bg=PALETTE["surface_container"], fg=PALETTE["on_surface_variant"],
                relief="flat", cursor="hand2",
                font=("Segoe UI", 11), padx=6,
                command=_reset_one
                ).pack(side="left")

    def _build_footer(self):
        """ダイアログ下部のボタン行を構築する"""
        tk.Frame(self, bg=PALETTE["outline_variant"], height=1).pack(
            fill="x", side="bottom")
        footer = tk.Frame(self, bg=PALETTE["surface"])
        footer.pack(fill="x", side="bottom")

        # 右側: キャンセル / 保存
        tk.Button(footer, text=tr("キャンセル", "Cancel"),
            bg=PALETTE["surface_container"], fg=PALETTE["on_surface_variant"],
            font=FONT_UI, relief="flat", cursor="hand2",
            padx=14, pady=8, command=self.destroy
            ).pack(side="right", padx=(4, 16), pady=10)

        tk.Button(footer, text=tr("✓  保存", "✓  Save"),
            bg=PALETTE["primary"], fg=PALETTE["on_primary"],
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=8, command=self._on_save
            ).pack(side="right", padx=4, pady=10)

        # 左側: すべてリセット
        tk.Button(footer, text=tr("↺  すべてリセット", "↺  Reset all"),
            bg=PALETTE["surface_container"], fg=PALETTE["changed"],
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
            [self._column_labels[k] for k, v in columns.items()     if not v] +
            [self._sheet_labels[k]  for k, v in sheet_names.items() if not v]
        )
        if empty:
            messagebox.showwarning(
                tr("入力エラー", "Invalid settings"),
                tr("以下の項目が空欄です:\n", "Fill in the following fields:\n") + "\n".join(f"  ・{n}" for n in empty),
                parent=self)
            return

        # カラム名の重複チェック
        vals = list(columns.values())
        if len(vals) != len(set(vals)):
            messagebox.showwarning(
                tr("入力エラー", "Invalid settings"),
                tr("カラム名が重複しています。\n各カラムに異なる名前を設定してください。", "Column names must be unique.\nEnter a different name for each column."),
                parent=self)
            return

        save_column_config({"columns": columns, "sheet_names": sheet_names})
        self.changed = True
        messagebox.showinfo(
            tr("保存完了", "Saved"),
            tr("設定を保存しました。\n次の比較実行から新しいカラム名が適用されます。", "Settings saved. The new column names apply to the next comparison."),
            parent=self)
        self.destroy()

    def _on_reset_all(self):
        """全設定をデフォルトに戻す"""
        if not messagebox.askyesno(
            tr("リセット確認", "Confirm reset"),
            tr("すべての設定をデフォルト値に戻しますか？", "Restore all default settings?"),
            parent=self):
            return
        cfg = reset_column_config()
        for k, v in self._col_vars.items():
            v.set(cfg["columns"][k])
        for k, v in self._sheet_vars.items():
            v.set(cfg["sheet_names"][k])
        messagebox.showinfo(tr("リセット完了", "Reset complete"), tr("デフォルト値に戻しました。", "Default values restored."), parent=self)


def open_settings(parent: tk.Tk) -> bool:
    """
    設定ダイアログを開いて閉じるまで待つ。

    Returns:
        bool: 設定が保存された場合 True
    """
    dialog = SettingsDialog(parent)
    parent.wait_window(dialog)
    return getattr(dialog, "changed", False)
