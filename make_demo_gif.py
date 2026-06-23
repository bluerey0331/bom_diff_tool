"""
make_demo_gif.py - BOMツールのデモGIFを生成するスクリプト
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


def capture_loop(interval=0.1):
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
                        ratio = 900 / img.width
                        img = img.resize((900, int(img.height * ratio)))
                        frames.append(img)
            except Exception:
                pass
            time.sleep(interval)


def save_gif():
    if not frames:
        print("フレームがありません")
        return
    from PIL import Image

    print(f"\nフレーム数: {len(frames)}")
    print(f"GIF生成中: {OUTPUT_GIF} ...")

    all_frames = [frames[0]] * 10 + frames + [frames[-1]] * 20

    # 各フレームを個別に量子化（ローカルカラーテーブル）
    palette_frames = [f.quantize(colors=256) for f in all_frames]

    palette_frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=palette_frames[1:],
        duration=100,
        loop=0,
    )
    size_kb = pathlib.Path(OUTPUT_GIF).stat().st_size // 1024
    print(f"完了: {OUTPUT_GIF}  ({size_kb} KB)")


def run_demo():
    sys.path.insert(0, str(BASE_DIR))

    # サンプルファイル用の列名を一時設定
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

    from src.gui import BomApp
    app = BomApp()
    app.attributes("-topmost", True)
    app.state("zoomed")
    app._old_path.set(OLD_FILE)
    app._new_path.set(NEW_FILE)
    app.update()

    # 比較完了フックをセット
    orig_done = app._on_comparison_done
    def done_hook(results, new_pns):
        orig_done(results, new_pns)
        done_event.set()
    app._on_comparison_done = done_hook

    # キャプチャスレッド起動
    threading.Thread(target=capture_loop, daemon=True).start()

    def schedule():
        # 1.5秒後に Compare 実行
        app.after(1500, app._run_comparison)

        def waiter():
            done_event.wait(timeout=15)   # 比較完了まで待機
            time.sleep(2.0)               # 結果を見せる
            capturing[0] = False
            time.sleep(0.2)
            save_gif()
            save_column_config(original_cfg)
            app.after(0, app.destroy)

        threading.Thread(target=waiter, daemon=True).start()

    app.after(500, schedule)
    app.mainloop()


if __name__ == "__main__":
    print(f"対象ファイル:")
    print(f"  OLD: {OLD_FILE}")
    print(f"  NEW: {NEW_FILE}")
    print(f"出力: {OUTPUT_GIF}\n")
    run_demo()
