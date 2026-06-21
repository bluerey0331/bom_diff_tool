"""
column_config.py - カラム名設定の読み書きモジュール

4つの論理カラム（part_number / manufacturer / quantity / description）の
「実際のExcel上のカラム名」と「Excelレポートのシート名」を
config.ini の [columns] / [sheet_names] セクションに保存・読み込みします。

他のモジュールはすべてこのモジュールから設定を取得します。
ハードコードされたカラム名はこのファイルにしか存在しません。
"""

import configparser
import os

# config.ini のパス（プロジェクトルート）
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.ini")


# ============================================================
# デフォルト値（初回起動時 / リセット時に使用）
# ============================================================

DEFAULT_COLUMNS = {
    "part_number":  "Manufacturer Part Number",
    "manufacturer": "Manufacturer Name",
    "quantity":     "Requested Quantity 1",
    "description":  "Description",
}

DEFAULT_SHEET_NAMES = {
    "added":    "追加部品",
    "removed":  "削除部品",
    "qty":      "Qty変更",
    "mfr":      "Mfr変更",
}

# 設定ダイアログの表示ラベル
COLUMN_LABELS = {
    "part_number":  "Part Number（キー列・インデックス）",
    "manufacturer": "Manufacturer Name",
    "quantity":     "Quantity",
    "description":  "Description",
}

SHEET_LABELS = {
    "added":   "追加部品シート名",
    "removed": "削除部品シート名",
    "qty":     "Qty変更シート名",
    "mfr":     "Mfr変更シート名",
}


# ============================================================
# 読み込み
# ============================================================

def load_column_config() -> dict:
    """
    config.ini からカラム名・シート名設定を読み込む。
    セクションがなければデフォルト値を返す。

    Returns:
        dict: {
            "columns":     {"part_number": str, "manufacturer": str,
                            "quantity": str, "description": str},
            "sheet_names": {"added": str, "removed": str,
                            "qty": str, "mfr": str},
        }
    """
    config = _read_ini()

    columns = {
        key: config.get("columns", key, fallback=default).strip()
        for key, default in DEFAULT_COLUMNS.items()
    }
    sheet_names = {
        key: config.get("sheet_names", key, fallback=default).strip()
        for key, default in DEFAULT_SHEET_NAMES.items()
    }
    return {"columns": columns, "sheet_names": sheet_names}


# ============================================================
# 保存 / リセット
# ============================================================

def save_column_config(col_cfg: dict) -> None:
    """
    カラム名・シート名設定を config.ini に保存する。

    Args:
        col_cfg (dict): load_column_config() と同じ構造の辞書
    """
    config = _read_ini()

    if not config.has_section("columns"):
        config.add_section("columns")
    for key, value in col_cfg["columns"].items():
        config.set("columns", key, value)

    if not config.has_section("sheet_names"):
        config.add_section("sheet_names")
    for key, value in col_cfg["sheet_names"].items():
        config.set("sheet_names", key, value)

    _write_ini(config)


def reset_column_config() -> dict:
    """
    デフォルト値にリセットして config.ini に保存する。

    Returns:
        dict: リセット後の設定辞書
    """
    default_cfg = {
        "columns":     dict(DEFAULT_COLUMNS),
        "sheet_names": dict(DEFAULT_SHEET_NAMES),
    }
    save_column_config(default_cfg)
    return default_cfg


# ============================================================
# 便利アクセサ（各モジュールが直接使う）
# ============================================================

def get_column_names() -> dict[str, str]:
    """論理キー → Excelカラム名 の辞書を返す"""
    return load_column_config()["columns"]


def get_required_columns() -> list[str]:
    """loader.py が検証に使う必須カラム名リストを返す"""
    c = get_column_names()
    return [c["part_number"], c["manufacturer"], c["quantity"], c["description"]]


def get_index_column() -> str:
    """インデックス（キー列）に使うカラム名を返す"""
    return get_column_names()["part_number"]


def get_sheet_names() -> dict[str, str]:
    """Excelレポートのシート名辞書を返す"""
    return load_column_config()["sheet_names"]


# ============================================================
# 内部ユーティリティ
# ============================================================

def _read_ini() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if os.path.exists(_CONFIG_PATH):
        config.read(_CONFIG_PATH, encoding="utf-8")
    return config


def _write_ini(config: configparser.ConfigParser) -> None:
    out_dir = os.path.dirname(_CONFIG_PATH)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        config.write(f)
