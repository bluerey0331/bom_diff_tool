"""
main.py - BOM比較ツールのエントリーポイント

使い方:
    python main.py           # GUIモードで起動（デフォルト）
    python main.py --cli     # CLIモードで実行
    python main.py --cli --old old.xlsx --new new.xlsx --output report.xlsx
"""

import argparse
import sys


def parse_args() -> argparse.Namespace:
    """
    コマンドライン引数を解析する。

    --cli フラグがある場合は従来のCLIモード、
    ない場合はGUIモードで起動する。

    Returns:
        argparse.Namespace: 解析された引数オブジェクト
    """
    parser = argparse.ArgumentParser(
        description="BOM（部品表）比較ツール - 2つのExcelファイルを比較します"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="GUIを使わずCLIモードで実行する",
    )
    parser.add_argument(
        "--old",
        default="old.xlsx",
        help="旧BOMファイルのパス（CLIモード用、デフォルト: old.xlsx）",
    )
    parser.add_argument(
        "--new",
        default="new.xlsx",
        help="新BOMファイルのパス（CLIモード用、デフォルト: new.xlsx）",
    )
    parser.add_argument(
        "--output",
        default="bom_diff_report.xlsx",
        help="出力レポートのパス（CLIモード用、デフォルト: bom_diff_report.xlsx）",
    )
    return parser.parse_args()


def run_cli(args: argparse.Namespace) -> None:
    """
    CLIモードでBOM比較を実行する。

    Args:
        args: コマンドライン引数オブジェクト
    """
    from src.loader import load_bom
    from src.comparator import compare_bom
    from src.report import print_summary, save_report

    print(f"旧BOM読み込み中: {args.old}")
    print(f"新BOM読み込み中: {args.new}")

    try:
        old_df = load_bom(args.old)
        new_df = load_bom(args.new)
    except FileNotFoundError as e:
        print(f"\n[エラー] ファイルが見つかりません: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n[エラー] ファイル形式の問題: {e}")
        sys.exit(1)

    print(f"  旧BOM: {len(old_df)} 部品")
    print(f"  新BOM: {len(new_df)} 部品")

    results = compare_bom(old_df, new_df)
    print_summary(results)
    save_report(results, args.output)


def run_gui() -> None:
    """GUIモードでアプリを起動する"""
    from src.gui import launch
    launch()


if __name__ == "__main__":
    args = parse_args()

    if args.cli:
        # --cli フラグがあればCLIモード
        run_cli(args)
    else:
        # デフォルトはGUIモード
        run_gui()
