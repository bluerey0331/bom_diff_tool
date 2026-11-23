"""
loader.py - BOMデータの読み込みモジュール

カラム名は column_config.py から動的に取得します。
ハードコードされたカラム名はこのファイルには存在しません。
"""

import pandas as pd
from src.column_config import get_required_columns, get_index_column, get_column_names
from src.ui_language import tr


def load_bom(file_path: str) -> pd.DataFrame:
    """
    ExcelファイルからBOMデータを読み込む。

    使用するカラム名は config.ini の設定に従います。

    Args:
        file_path (str): 読み込むExcelファイルのパス

    Returns:
        pd.DataFrame: BOMデータを格納したDataFrame

    Raises:
        FileNotFoundError: 指定されたファイルが存在しない場合
        ValueError: 必要なカラムが不足している場合
    """
    df = pd.read_excel(file_path, dtype=str, keep_default_na=False)
    df.columns = df.columns.str.strip()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    validate_columns(df, file_path)

    df = df.loc[~df.eq("").all(axis=1)]
    part_column = get_index_column()
    part_numbers = df[part_column]
    quantity = pd.to_numeric(df[get_column_names()["quantity"]], errors="coerce")
    problems = (
        (part_numbers.eq(""), tr("型番が空欄", "Missing part number")),
        (part_numbers.ne("") & part_numbers.duplicated(keep=False),
         tr("型番が重複", "Duplicate part number")),
        (quantity.isna() | quantity.isin([float("inf"), float("-inf")]),
         tr("数量が有限の数値ではありません", "Quantity must be a finite number")),
    )
    errors = []
    for mask, message in problems:
        rows = df.index[mask]
        if len(rows):
            positions = ", ".join(str(row + 2) for row in rows[:20])
            if len(rows) > 20:
                positions += tr(f" ほか {len(rows) - 20} 行", f" and {len(rows) - 20} more")
            errors.append(tr(f"{message}（Excelの行 {positions}）",
                             f"{message} (Excel rows {positions})"))
    if errors:
        raise ValueError(f"{file_path}\n" + "\n".join(errors))
    return df.set_index(part_column)


def validate_columns(df: pd.DataFrame, file_path: str) -> None:
    """
    DataFrameに必要なカラムがすべて含まれているか検証する。

    Args:
        df (pd.DataFrame): 検証対象のDataFrame
        file_path (str): エラーメッセージ表示用のファイルパス

    Raises:
        ValueError: 必要なカラムが1つ以上不足している場合
    """
    required = get_required_columns()
    missing  = set(required) - set(df.columns)

    if missing:
        raise ValueError(
            tr(f"ファイル '{file_path}' に必要なカラムが不足しています。\n不足列: {sorted(missing)}",
               f"Required columns are missing from '{file_path}'.\nMissing: {sorted(missing)}")
        )
