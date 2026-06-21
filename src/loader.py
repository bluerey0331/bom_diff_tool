"""
loader.py - BOMデータの読み込みモジュール

カラム名は column_config.py から動的に取得します。
ハードコードされたカラム名はこのファイルには存在しません。
"""

import pandas as pd
from src.column_config import get_required_columns, get_index_column


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
    df = pd.read_excel(file_path, dtype=str)
    df.columns = df.columns.str.strip()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    validate_columns(df, file_path)

    df = df.set_index(get_index_column())
    return df


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
            f"ファイル '{file_path}' に必要なカラムが不足しています: {missing}\n"
            f"必須カラム: {required}\n"
            f"設定を変更するには GUI の ⚙ 設定ボタンを使用してください。"
        )
