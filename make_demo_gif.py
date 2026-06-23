"""
make_demo_gif.py - BOMツールのデモGIFを生成するスクリプト

シーケンス:
  1. 起動 → ファイルパスがタイプライター式に入力される
  2. Compare ボタンがフラッシュ → 処理中アニメーション
  3. 結果が表示される（Added タブ）
  4. Removed → Qty Changed タブに切り替え
  5. 最後に Added へ戻りサマリー数字が見えるフレームで終了
"""

import sys
import time
import threading
import pathlib

BASE_DIR = pathlib.Path(__file__).parent
OLD_FILE = str(BASE_DIR / "sample_old.xlsx")
NEW_FILE = str(BASE_DIR / "sample_new.xlsx")
OUTPUT_GIF = str(BASE_DIR / "demo.gif")

frames = []
capturing = [True]
done_event = threading.Event()


# ============================================================
# キャプチャ
# ============================================================

def capture_loop(interval=0.06):
    import mss, win32gui
    from PIL import Image
    with mss.MSS() as sct:
        while capturing[0]:
            try:
                hwnd = win32gui.FindWindow(None, "BOM Diff Tool")
                if hwnd:
                    l, t, r, b = win32gui.GetWindowRect(hwnd)
                    w, h = r - l, b - t
                    if w > 50 and h > 50:
                        raw = sct.grab({"left": l, "top": t, "width": w, "height": h})
                        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                        ratio = 960 / img.width
                        img = img.resize((960, int(img.height * ratio)))
                        frames.append(img)
            except Exception:
                pass
            time.sleep(interval)


# ============================================================
# GIF 保存
# ============================================================

def save_gif():
    if not frames:
        print("フレームがありません")
        return

    print(f"\nフレーム数（生）: {len(frames)}")

    # フレームをグループで静止させる（重複削除せず、全フレーム保持）
    all_frames = (
        [frames[0]] * 8 +          # 起動状態を 0.5s 見せる
        frames +
        [frames[-1]] * 25          # 最終フレームを 1.5s 見せる
    )

    print(f"GIF生成中: {OUTPUT_GIF}  ({len(all_frames)} フレーム) ...")

    all_frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=all_frames[1:],
        duration=60,               # 60ms/frame ≈ 16fps
        loop=0,
        optimize=False,
    )
    size_kb = pathlib.Path(OUTPUT_GIF).stat().st_size // 1024
    print(f"完了: {OUTPUT_GIF}  ({size_kb} KB)")


# ============================================================
# 自動操作シーケンス
# ============================================================

def typewrite(var, text, app, delay=0.07):
    """テキストを1文字ずつ入力するタイプライター演出"""
    for i in range(len(text) + 1):
        app.after(0, var.set, text[:i])
        time.sleep(delay)


def run_demo():
    sys.path.insert(0, str(BASE_DIR))

    from src.column_config import save_column_config, load_column_config
    original_cfg = load_column_config()
    save_column_config({
        "columns": {
            "part_number":  "Manufacturer Part Number",
            "manufacturer": "Manufacturer Name",
            "quantity":     "Requested Quantity 1",
            "description":  "Description",
        },
        "sheet_names": original_cfg["sheet_names"],
    })

    from src.gui import BomApp, PALETTE
    app = BomApp()
    app.attributes("-topmost", True)
    app.state("zoomed")
    app.update()

    # 比較完了フック
    orig_done = app._on_comparison_done
    def done_hook(results, new_pns):
        orig_done(results, new_pns)
        done_event.set()
    app._on_comparison_done = done_hook

    # キャプチャ開始
    threading.Thread(target=capture_loop, daemon=True).start()

    def sequence():
        """デモシーケンス本体（バックグラウンドスレッドで実行）"""

        # --- フェーズ1: 起動状態を見せる (0.8s) ---
        time.sleep(0.8)

        # --- フェーズ2: OLD BOM パスをタイプライター入力 ---
        typewrite(app._old_path, "sample_old.xlsx", app, delay=0.06)
        time.sleep(0.3)

        # --- フェーズ3: NEW BOM パスをタイプライター入力 ---
        typewrite(app._new_path, "sample_new.xlsx", app, delay=0.06)
        time.sleep(0.4)

        # --- フェーズ4: Compare ボタンをフラッシュ ---
        def flash_btn():
            app._run_btn.config(state="disabled", text="▶  Compare")  # 一瞬 disabled 風に
            app.update()
        app.after(0, flash_btn)
        time.sleep(0.15)

        # --- フェーズ5: 比較実行 ---
        app.after(0, app._run_comparison)

        # --- フェーズ6: 処理中（完了まで待機）---
        done_event.wait(timeout=12)
        time.sleep(0.5)

        # --- フェーズ7: Added タブの結果を見せる (1.0s) ---
        app.after(0, lambda: app._notebook.select(0))
        time.sleep(1.0)

        # --- フェーズ8: Removed タブに切り替え (0.9s) ---
        app.after(0, lambda: app._notebook.select(1))
        time.sleep(0.9)

        # --- フェーズ9: Qty Changed タブ (0.9s) ---
        app.after(0, lambda: app._notebook.select(2))
        time.sleep(0.9)

        # --- フェーズ10: Added タブに戻る (最終フレーム) ---
        app.after(0, lambda: app._notebook.select(0))
        time.sleep(1.5)

        # --- 終了 ---
        capturing[0] = False
        time.sleep(0.2)

        save_gif()
        save_column_config(original_cfg)
        app.after(0, app.destroy)

    app.after(300, lambda: threading.Thread(target=sequence, daemon=True).start())
    app.mainloop()


if __name__ == "__main__":
    print(f"対象: {OLD_FILE}")
    print(f"      {NEW_FILE}")
    print(f"出力: {OUTPUT_GIF}\n")
    run_demo()
