"""
prepare.py - BOM前処理ツール（独立GUIウィンドウ）

任意のExcelファイルを読み込み、
・不要な列をチェックを外すだけで削除
・カラム名はリネームしない（元のまま保持）
・old.xlsx / new.xlsx として保存
する前処理GUIツールです。

【使い方】
    python prepare.py

【カラム名について】
カラム名はリネームしません。
BOM比較ツール（main.py）の ⚙ 設定 で、
入力ファイルのカラム名に合わせて設定してください。
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading

from src.preprocessor import (
    OUTPUT_CHOICES,
    load_excel_columns,
    keep_columns_and_save,
)
from src.settings_dialog import open_settings


# ============================================================
# カラーパレット（BOM Diff Tool と統一）
# ============================================================
PALETTE = {
    "bg_dark":    "#0D1117",
    "bg_panel":   "#161B22",
    "bg_card":    "#1C2333",
    "border":     "#30363D",
    "accent":     "#58A6FF",
    "accent_dim": "#1F4788",
    "text":       "#E6EDF3",
    "text_muted": "#8B949E",
    "ok":         "#238636",
    "warn":       "#D29922",
    "error":      "#DA3633",
    "mono":       "#C9D1D9",
    "check_on":   "#238636",   # チェックON：緑
    "check_off":  "#DA3633",   # チェックOFF（削除予定）：赤
}

FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_UI    = ("Segoe UI", 10)
FONT_HEAD  = ("Segoe UI", 10, "bold")
FONT_LABEL = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_MONO  = ("Consolas", 10)


class PrepareApp(tk.Tk):
    """BOM前処理ツールのメインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.title("BOM Prepare Tool  —  前処理")
        self.geometry("680x620")
        self.resizable(True, True)
        self.configure(bg=PALETTE["bg_dark"])

        self._source_path   = tk.StringVar()
        self._output_choice = tk.StringVar(value="old.xlsx")
        self._output_dir    = tk.StringVar()

        # カラム名 → チェック状態（True=残す / False=削除）の辞書
        self._col_vars: dict[str, tk.BooleanVar] = {}

        self._configure_styles()
        self._build_ui()

    # ----------------------------------------------------------
    # スタイル設定
    # ----------------------------------------------------------

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Dark.TRadiobutton",
            background=PALETTE["bg_dark"],
            foreground=PALETTE["text"],
            font=FONT_UI)
        style.map("Dark.TRadiobutton",
            background=[("active", PALETTE["bg_dark"])])

        style.configure("BomTool.Horizontal.TProgressbar",
            troughcolor=PALETTE["bg_card"],
            background=PALETTE["accent"],
            borderwidth=0)

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------

    def _build_ui(self):
        self._build_header()

        # ── スクロール可能なメインエリア ──
        canvas    = tk.Canvas(self, bg=PALETTE["bg_dark"],
            highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._scroll_frame  = tk.Frame(canvas, bg=PALETTE["bg_dark"])
        self._scroll_window = canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw")

        self._scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._scroll_window, width=e.width))
        self.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        body = self._scroll_frame
        pad  = {"padx": 20}

        # STEP 1: ファイル選択
        self._build_step_label(body, "STEP 1", "入力ファイルを選択")
        self._build_file_section(body, pad)

        # STEP 2: 残すカラムを選択（ファイル読込後に動的生成）
        self._build_step_label(body, "STEP 2", "残すカラムを選択（チェックを外すと削除）")
        self._col_container = tk.Frame(body, bg=PALETTE["bg_dark"])
        self._col_container.pack(fill="x", padx=20, pady=(0, 8))
        self._col_placeholder()

        # STEP 3: 出力設定
        self._build_step_label(body, "STEP 3", "出力先を設定")
        self._build_output_section(body, pad)

        # 実行ボタン
        tk.Frame(body, bg=PALETTE["bg_dark"], height=8).pack()
        self._run_btn = tk.Button(body, text="▶  削除して保存",
            bg=PALETTE["accent"], fg="#0D1117",
            font=("Segoe UI", 11, "bold"), relief="flat",
            cursor="hand2", pady=10, state="disabled",
            command=self._run_conversion)
        self._run_btn.pack(fill="x", padx=20, pady=(4, 4))

        self._progress = ttk.Progressbar(body,
            style="BomTool.Horizontal.TProgressbar", mode="indeterminate")
        self._progress.pack(fill="x", padx=20, pady=(0, 4))

        self._build_statusbar()

    def _build_header(self):
        """ヘッダー（タイトル + ⚙設定ボタン）"""
        header = tk.Frame(self, bg=PALETTE["bg_panel"], height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="⚙  BOM Prepare Tool",
            bg=PALETTE["bg_panel"], fg=PALETTE["text"],
            font=FONT_TITLE).pack(side="left", padx=20, pady=12)

        # ⚙ 設定ボタン（BOM比較側のカラム名を変更するため）
        tk.Button(header, text="⚙  設定",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_UI, relief="flat", cursor="hand2",
            padx=12, pady=6, command=self._open_settings
            ).pack(side="right", padx=16, pady=10)

        tk.Label(header, text="不要カラム削除（リネームなし）",
            bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
            font=FONT_LABEL).pack(side="right", padx=4)

        tk.Frame(self, bg=PALETTE["border"], height=1).pack(fill="x")

    def _build_step_label(self, parent, step: str, title: str):
        frame = tk.Frame(parent, bg=PALETTE["bg_dark"])
        frame.pack(fill="x", padx=20, pady=(18, 6))
        tk.Label(frame, text=step,
            bg=PALETTE["accent_dim"], fg=PALETTE["accent"],
            font=("Segoe UI", 8, "bold"), padx=6, pady=2).pack(side="left")
        tk.Label(frame, text=f"  {title}",
            bg=PALETTE["bg_dark"], fg=PALETTE["text"],
            font=FONT_HEAD).pack(side="left")

    def _build_file_section(self, parent, pad):
        """STEP 1: 入力ファイル選択"""
        card  = tk.Frame(parent, bg=PALETTE["bg_card"])
        card.pack(fill="x", **pad, pady=(0, 4))
        inner = tk.Frame(card, bg=PALETTE["bg_card"])
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="Excel ファイル",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_SMALL, anchor="w").pack(fill="x")

        row = tk.Frame(inner, bg=PALETTE["bg_card"])
        row.pack(fill="x", pady=(4, 0))
        tk.Entry(row, textvariable=self._source_path,
            bg=PALETTE["bg_card"], fg=PALETTE["mono"],
            insertbackground=PALETTE["accent"],
            relief="flat", font=FONT_MONO, bd=0
            ).pack(side="left", fill="both", expand=True)
        tk.Button(row, text="…", bg=PALETTE["bg_card"],
            fg=PALETTE["text_muted"], relief="flat",
            cursor="hand2", font=("Segoe UI", 11), padx=8,
            command=self._browse_source
            ).pack(side="right")

    def _col_placeholder(self):
        """カラム未読込み時のプレースホルダー"""
        tk.Label(self._col_container,
            text="ファイルを選択すると、カラム一覧が表示されます",
            bg=PALETTE["bg_dark"], fg=PALETTE["text_muted"],
            font=FONT_LABEL, anchor="w").pack(fill="x", pady=4)

    def _build_output_section(self, parent, pad):
        """STEP 3: 出力先設定"""
        card  = tk.Frame(parent, bg=PALETTE["bg_card"])
        card.pack(fill="x", **pad, pady=(0, 4))
        inner = tk.Frame(card, bg=PALETTE["bg_card"])
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="出力ファイル名",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_SMALL, anchor="w").pack(fill="x")

        btn_row = tk.Frame(inner, bg=PALETTE["bg_card"])
        btn_row.pack(fill="x", pady=(4, 8))
        for choice in OUTPUT_CHOICES:
            ttk.Radiobutton(btn_row, text=choice,
                variable=self._output_choice, value=choice,
                style="Dark.TRadiobutton"
                ).pack(side="left", padx=(0, 24))

        tk.Label(inner, text="保存先フォルダ",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_SMALL, anchor="w").pack(fill="x")

        dir_row = tk.Frame(inner, bg=PALETTE["bg_card"])
        dir_row.pack(fill="x", pady=(4, 0))
        tk.Entry(dir_row, textvariable=self._output_dir,
            bg=PALETTE["bg_card"], fg=PALETTE["mono"],
            insertbackground=PALETTE["accent"],
            relief="flat", font=FONT_MONO, bd=0
            ).pack(side="left", fill="both", expand=True)
        tk.Button(dir_row, text="…", bg=PALETTE["bg_card"],
            fg=PALETTE["text_muted"], relief="flat",
            cursor="hand2", font=("Segoe UI", 11), padx=8,
            command=self._browse_output_dir
            ).pack(side="right")

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PALETTE["bg_panel"], height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=PALETTE["border"], height=1).pack(fill="x")
        self._status_var = tk.StringVar(value="Ready  —  入力ファイルを選択してください")
        tk.Label(bar, textvariable=self._status_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["text_muted"],
            font=("Segoe UI", 9), anchor="w"
            ).pack(side="left", padx=12, pady=4)

    # ----------------------------------------------------------
    # カラム選択 UI（動的生成）
    # ----------------------------------------------------------

    def _build_col_checkboxes(self, columns: list[str]):
        """
        読み込んだカラム名をチェックボックスで一覧表示する。

        デフォルト状態:
          ✓ ON（残す）: 設定ダイアログで定義した4列
          ✗ OFF（削除）: それ以外の列

        設定ダイアログでカラム名を変更した後に再呼び出しすると
        チェック状態も更新される。

        Args:
            columns (list[str]): 元Excelのカラム名リスト
        """
        # 設定済みの4列名を取得（ONにするカラムの判定に使う）
        from src.column_config import get_required_columns
        required_set = set(get_required_columns())

        # 既存ウィジェットをクリア
        for w in self._col_container.winfo_children():
            w.destroy()
        self._col_vars.clear()

        card = tk.Frame(self._col_container, bg=PALETTE["bg_card"])
        card.pack(fill="x")

        # ── ヘッダー行 ──
        hdr = tk.Frame(card, bg=PALETTE["bg_card"])
        hdr.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(hdr, text=f"検出されたカラム  {len(columns)} 列",
            bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_SMALL).pack(side="left")

        # 凡例
        tk.Label(hdr, text="● 残す",
            bg=PALETTE["bg_card"], fg=PALETTE["check_on"],
            font=FONT_SMALL).pack(side="left", padx=(12, 0))
        tk.Label(hdr, text="● 削除",
            bg=PALETTE["bg_card"], fg=PALETTE["check_off"],
            font=FONT_SMALL).pack(side="left", padx=(6, 0))

        # 全解除・全選択ボタン
        tk.Button(hdr, text="全て削除",
            bg=PALETTE["bg_card"], fg=PALETTE["error"],
            font=FONT_SMALL, relief="flat", cursor="hand2", padx=6,
            command=lambda: self._set_all_checks(False)
            ).pack(side="right", padx=(4, 0))
        tk.Button(hdr, text="全て残す",
            bg=PALETTE["bg_card"], fg=PALETTE["ok"],
            font=FONT_SMALL, relief="flat", cursor="hand2", padx=6,
            command=lambda: self._set_all_checks(True)
            ).pack(side="right", padx=(4, 0))

        tk.Frame(card, bg=PALETTE["border"], height=1).pack(fill="x", padx=8)

        # ── カラムごとのチェックボックス行 ──
        for col in columns:
            # 設定済み4列 → ON（残す）、それ以外 → OFF（削除）
            is_required = col in required_set
            var = tk.BooleanVar(value=is_required)
            self._col_vars[col] = var

            row = tk.Frame(card, bg=PALETTE["bg_card"])
            row.pack(fill="x", padx=12, pady=1)

            # 状態インジケーター（●）
            indicator = tk.Label(row, text="●",
                bg=PALETTE["bg_card"],
                fg=PALETTE["check_on"] if is_required else PALETTE["check_off"],
                font=FONT_LABEL)
            indicator.pack(side="left", padx=(0, 6))

            # チェックボックス（設定4列は太字で強調）
            cb = tk.Checkbutton(row, text=col,
                variable=var,
                bg=PALETTE["bg_card"],
                fg=PALETTE["text"] if is_required else PALETTE["text_muted"],
                selectcolor=PALETTE["bg_card"],
                activebackground=PALETTE["bg_card"],
                activeforeground=PALETTE["text"],
                font=(FONT_MONO[0], FONT_MONO[1], "bold") if is_required else FONT_MONO,
                anchor="w", relief="flat", bd=0)
            cb.pack(side="left", fill="x", expand=True)

            # チェック変更時にインジケーター色を更新
            def _on_toggle(v=var, ind=indicator):
                ind.config(
                    fg=PALETTE["check_on"] if v.get() else PALETTE["check_off"])
                self._update_delete_preview()
            var.trace_add("write", lambda *_, fn=_on_toggle: fn())

        # ── 削除予定プレビューラベル ──
        tk.Frame(card, bg=PALETTE["border"], height=1).pack(
            fill="x", padx=8, pady=(6, 0))
        self._delete_preview = tk.Label(card,
            text="", bg=PALETTE["bg_card"], fg=PALETTE["text_muted"],
            font=FONT_SMALL, anchor="w", wraplength=600, justify="left")
        self._delete_preview.pack(fill="x", padx=12, pady=(4, 8))

        self._update_delete_preview()
        self._run_btn.config(state="normal")

        matched = [c for c in columns if c in required_set]
        self._set_status(
            f"{len(columns)} 列を検出  —  "
            f"設定カラム {len(matched)}/{len(required_set)} 列が一致  "
            f"（設定カラム=残す、その他=削除）"
        )

    def _set_all_checks(self, state: bool):
        """全カラムのチェック状態を一括変更する"""
        for var in self._col_vars.values():
            var.set(state)

    def _update_delete_preview(self):
        """削除予定カラムのリストをリアルタイムでプレビュー表示する"""
        if not hasattr(self, "_delete_preview"):
            return
        deleted = [col for col, var in self._col_vars.items() if not var.get()]
        if deleted:
            self._delete_preview.config(
                text=f"削除予定 ({len(deleted)} 列):  " + "  /  ".join(deleted),
                fg=PALETTE["check_off"])
        else:
            self._delete_preview.config(
                text="削除予定のカラムはありません（全列を保持）",
                fg=PALETTE["text_muted"])

    # ----------------------------------------------------------
    # 設定ダイアログ
    # ----------------------------------------------------------

    def _open_settings(self):
        """
        ⚙ 設定ダイアログを開く。
        保存後は「設定4列 → ON / その他 → OFF」の状態にチェックを更新する。
        """
        changed = open_settings(self)
        if changed and self._col_vars:
            # 設定が変わったので、新しい4列定義でチェック状態を再適用する
            self._refresh_checks()
            self._set_status(
                "設定を更新しました  —  "
                "新しい設定カラムがONになりました。内容を確認して保存してください。"
            )
        elif not changed:
            pass  # キャンセルされた場合は何もしない

    def _refresh_checks(self):
        """
        現在の column_config の4列定義に合わせてチェック状態を更新する。
        設定変更後・ファイル再読み込み時に呼ぶ。
        ファイルが未読み込みの場合は何もしない。
        """
        if not self._col_vars:
            return

        from src.column_config import get_required_columns
        required_set = set(get_required_columns())

        for col, var in self._col_vars.items():
            var.set(col in required_set)

    # ----------------------------------------------------------
    # イベントハンドラー
    # ----------------------------------------------------------

    def _browse_source(self):
        path = filedialog.askopenfilename(
            title="変換するExcelファイルを選択",
            filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"),
                       ("All files", "*.*")])
        if not path:
            return

        self._source_path.set(path)
        if not self._output_dir.get():
            self._output_dir.set(os.path.dirname(path))

        self._set_status("カラム情報を読み込み中…")
        threading.Thread(
            target=self._load_columns_worker,
            args=(path,), daemon=True).start()

    def _load_columns_worker(self, path: str):
        try:
            columns = load_excel_columns(path)
            self.after(0, self._on_columns_loaded, columns)
        except Exception as e:
            self.after(0, self._on_load_error, str(e))

    def _on_columns_loaded(self, columns: list[str]):
        self._build_col_checkboxes(columns)

    def _on_load_error(self, error_msg: str):
        self._set_status(f"Error: {error_msg}")
        messagebox.showerror("読み込みエラー", error_msg)

    def _browse_output_dir(self):
        directory = filedialog.askdirectory(title="保存先フォルダを選択")
        if directory:
            self._output_dir.set(directory)

    def _run_conversion(self):
        """削除処理の確認 → 実行"""
        source  = self._source_path.get().strip()
        out_dir = self._output_dir.get().strip()

        if not source:
            messagebox.showwarning("入力エラー", "入力ファイルを選択してください。")
            return
        if not out_dir:
            messagebox.showwarning("入力エラー", "保存先フォルダを選択してください。")
            return

        # 残すカラム・削除するカラムを確定
        keep    = [col for col, var in self._col_vars.items() if var.get()]
        deleted = [col for col, var in self._col_vars.items() if not var.get()]

        if not keep:
            messagebox.showwarning("選択エラー", "残すカラムを1つ以上選択してください。")
            return

        output_path = os.path.join(out_dir, self._output_choice.get())

        if os.path.exists(output_path):
            if not messagebox.askyesno("上書き確認",
                f"'{output_path}' は既に存在します。\n上書きしますか？"):
                return

        # 確認ダイアログ
        confirm_msg = (
            f"以下の内容で保存します。\n\n"
            f"【保存先】\n  {output_path}\n\n"
            f"【保持するカラム ({len(keep)} 列)】\n"
            + "\n".join(f"  ✓  {c}" for c in keep)
            + f"\n\n【削除するカラム ({len(deleted)} 列)】\n"
            + ("\n".join(f"  ✗  {c}" for c in deleted) if deleted else "  なし")
        )
        if not messagebox.askyesno("実行確認", confirm_msg):
            return

        self._run_btn.config(state="disabled", text="処理中…")
        self._progress.start(12)
        self._set_status("処理中…")

        threading.Thread(
            target=self._conversion_worker,
            args=(source, keep, output_path),
            daemon=True).start()

    def _conversion_worker(self, source: str, keep: list[str], output_path: str):
        try:
            result = keep_columns_and_save(source, keep, output_path)
            self.after(0, self._on_conversion_done, result)
        except Exception as e:
            self.after(0, self._on_conversion_error, str(e))

    def _on_conversion_done(self, result: dict):
        self._progress.stop()
        self._run_btn.config(state="normal", text="▶  削除して保存")

        out_path = result["output_path"]
        self._set_status(
            f"完了  —  {os.path.basename(out_path)}  "
            f"({result['rows']} 行 / "
            f"{len(result['kept_columns'])} 列保持 / "
            f"{len(result['dropped_columns'])} 列削除)")

        messagebox.showinfo("完了",
            f"保存しました:\n{out_path}\n\n"
            f"  データ行数 : {result['rows']} 行\n"
            f"  保持カラム : {', '.join(result['kept_columns'])}\n"
            f"  削除カラム : {len(result['dropped_columns'])} 列")

    def _on_conversion_error(self, error_msg: str):
        self._progress.stop()
        self._run_btn.config(state="normal", text="▶  削除して保存")
        self._set_status(f"Error: {error_msg}")
        messagebox.showerror("エラー", error_msg)

    def _set_status(self, text: str):
        self._status_var.set(text)


if __name__ == "__main__":
    app = PrepareApp()
    app.mainloop()