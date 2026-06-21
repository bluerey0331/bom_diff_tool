"""
comparator.py - BOMデータの比較モジュール

カラム名は column_config.py から動的に取得します。
"""

import pandas as pd
from src.column_config import get_column_names


def compare_bom(old_df: pd.DataFrame, new_df: pd.DataFrame) -> dict:
    """
    2つのBOM DataFrameを比較し、差分をまとめた辞書を返す。

    Args:
        old_df (pd.DataFrame): 旧BOMデータ
        new_df (pd.DataFrame): 新BOMデータ

    Returns:
        dict: {
            "added"       : 追加された部品のDataFrame,
            "removed"     : 削除された部品のDataFrame,
            "qty_changed" : Quantity変更のDataFrame,
            "mfr_changed" : Manufacturer変更のDataFrame,
        }
    """
    return {
        "added":       find_added(old_df, new_df),
        "removed":     find_removed(old_df, new_df),
        "qty_changed": find_quantity_changes(old_df, new_df),
        "mfr_changed": find_manufacturer_changes(old_df, new_df),
    }


def find_added(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """新BOMに存在し、旧BOMには存在しない部品（追加部品）を取得する"""
    return new_df.loc[new_df.index.difference(old_df.index)].copy()


def find_removed(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """旧BOMに存在し、新BOMには存在しない部品（削除部品）を取得する"""
    return old_df.loc[old_df.index.difference(new_df.index)].copy()


def find_quantity_changes(
    old_df: pd.DataFrame, new_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Quantity カラムの変更を検出する。
    カラム名は column_config.get_column_names()["quantity"] を使用する。
    """
    col          = get_column_names()["quantity"]
    common_index = old_df.index.intersection(new_df.index)

    old_qty = pd.to_numeric(old_df.loc[common_index, col], errors="coerce")
    new_qty = pd.to_numeric(new_df.loc[common_index, col], errors="coerce")

    changed_index = common_index[old_qty != new_qty]
    return pd.DataFrame({
        f"Old {col}": old_df.loc[changed_index, col],
        f"New {col}": new_df.loc[changed_index, col],
    })


def find_manufacturer_changes(
    old_df: pd.DataFrame, new_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Manufacturer カラムの変更を検出する。
    カラム名は column_config.get_column_names()["manufacturer"] を使用する。
    """
    col          = get_column_names()["manufacturer"]
    common_index = old_df.index.intersection(new_df.index)

    old_mfr = old_df.loc[common_index, col]
    new_mfr = new_df.loc[common_index, col]

    changed_index = common_index[
        old_mfr.str.lower() != new_mfr.str.lower()
    ]
    return pd.DataFrame({
        f"Old {col}": old_df.loc[changed_index, col],
        f"New {col}": new_df.loc[changed_index, col],
    })
