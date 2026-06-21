"""
preprocessor.py - BOM前処理ロジックモジュール

任意のExcelファイルを読み込み、
・不要なカラムを削除（カラム名はリネームしない）
・old.xlsx / new.xlsx として保存
する機能を提供します。

【設計方針】
カラム名のリネームは行いません。
入力ファイルのカラム名をそのまま出力します。
BOM比較ツール側の設定（⚙ 設定）で、
入力ファイルのカラム名に合わせてください。
"""

import os
import pandas as pd


# 保存先ファイル名の選択肢
OUTPUT_CHOICES = ["old.xlsx", "new.xlsx"]


def load_excel_columns(file_path: str) -> list[str]:
    """
    Excelファイルの先頭行だけ読み込んでカラム名一覧を返す。

    Args:
        file_path (str): 読み込むExcelファイルのパス

    Returns:
        list[str]: カラム名のリスト（空白をstrip済み）

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: シートが空でカラムが取得できない場合
    """
    df_header = pd.read_excel(file_path, nrows=0, dtype=str)
    columns   = [col.strip() for col in df_header.columns]
    if not columns:
        raise ValueError(f"ファイル '{file_path}' にカラムが見つかりません。")
    return columns


def keep_columns_and_save(
    file_path: str,
    keep_columns: list[str],
    output_path: str,
) -> dict:
    """
    Excelファイルを読み込み、指定した列だけを残して保存する。
    カラム名のリネームは行わない。

    Args:
        file_path (str): 入力Excelファイルのパス
        keep_columns (list[str]): 残すカラム名のリスト（元のカラム名のまま）
        output_path (str): 出力先のフルパス

    Returns:
        dict: {
            "output_path"     : str   保存先パス,
            "rows"            : int   データ行数,
            "kept_columns"    : list  保持したカラム,
            "dropped_columns" : list  削除したカラム,
        }

    Raises:
        ValueError: keep_columns が空の場合
    """
    if not keep_columns:
        raise ValueError("残すカラムが指定されていません。")

    df = pd.read_excel(file_path, dtype=str)
    df.columns = df.columns.str.strip()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # 削除されるカラム
    dropped_columns = [col for col in df.columns if col not in keep_columns]

    # 指定した列だけを残す（順番は keep_columns の順）
    existing_keeps = [col for col in keep_columns if col in df.columns]
    df = df[existing_keeps]

    # 完全空白行を除去
    df = df.dropna(how="all")

    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)

    df.to_excel(output_path, index=False)

    return {
        "output_path":     output_path,
        "rows":            len(df),
        "kept_columns":    existing_keeps,
        "dropped_columns": dropped_columns,
    }
