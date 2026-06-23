"""
capture_demo.py - BOMツールのワークフローをスクリーンショットで保存するスクリプト
"""

import os
import sys
import time
import threading
import pathlib
import tkinter as tk

BASE_DIR = pathlib.Path(__file__).parent
SAVE_DIR = BASE_DIR / "screenshots"
SAVE_DIR.mkdir(exist_ok=True)

OLD_FILE = str(BASE_DIR / "sample_old.xlsx")
NEW_FILE = str(BASE_DIR / "sample_new.xlsx")


def take_screenshot(window: tk.Tk, filename: str):
    """ウィンドウのスクリーンショットを取得して保存する"""
    try:
        from PIL import ImageGrab
        window.update()
        time.sleep(0.3)
        x = window.winfo_rootx()
        y = window.winfo_rooty()
        w = window.winfo_width()
        h = window.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        path = SAVE_DIR / filename
        img.save(str(path))
        print(f"  保存: {path}")
    except Exception as e:
        print(f"  スクリーンショット失敗: {e}")


def run_demo():
    """GUIを起動してデモシナリオを実行する"""
    sys.path.insert(0, str(BASE_DIR))
    from src.gui import BomApp

    # サンプルファイルに合わせた列名を一時設定
    from src.column_config import save_column_config, load_column_config
    original_cfg = load_column_config()
    sample_cfg = {
        "columns": {
            "part_number":  "Manufacturer Part Number",
            "manufacturer": "Manufacturer Name",
            "quantity":     "Requested Quantity 1",
            "description":  "Description",
        },
        "sheet_names": original_cfg["sheet_names"],
    }
    save_column_config(sample_cfg)

    app = BomApp()

    def automate():
        time.sleep(1.2)

        # --- Step 1: 初期状態 ---
        app._old_path.set(OLD_FILE)
        app._new_path.set(NEW_FILE)
        app.update()
        time.sleep(0.5)
        take_screenshot(app, "01_files_loaded.png")
        print("Step 1: ファイル選択状態を保存しました")

        # --- Step 2: Compare 実行 ---
        app._run_comparison()
        # 比較完了を待機（最大10秒）
        for _ in range(100):
            time.sleep(0.1)
            if app._results is not None:
                break
        time.sleep(0.5)
        take_screenshot(app, "02_compare_result.png")
        print("Step 2: 比較結果を保存しました")

        # --- Step 3: レポート保存 ---
        output_path = str(BASE_DIR / "bom_diff_report.xlsx")
        from src.report import save_report
        if app._results:
            save_report(app._results, output_path)
            print(f"Step 3: レポート保存 → {output_path}")
        time.sleep(0.5)
        take_screenshot(app, "03_report_saved.png")

        print("\n完了！ screenshots/ フォルダを確認してください。")
        # 元の列名設定に戻す
        save_column_config(original_cfg)
        time.sleep(2)
        app.destroy()

    thread = threading.Thread(target=automate, daemon=True)
    thread.start()
    app.mainloop()


if __name__ == "__main__":
    print(f"対象ファイル:")
    print(f"  OLD: {OLD_FILE}")
    print(f"  NEW: {NEW_FILE}")
    print(f"保存先: {SAVE_DIR}\n")
    run_demo()
