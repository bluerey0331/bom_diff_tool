"""
tests/test_all.py - BOM Diff Tool の自動テスト

実行方法:
    pytest tests/
    pytest tests/ -v        # 詳細出力
    pytest tests/ --tb=short # 短縮エラー表示
"""

import os
import sys
import pytest
import pandas as pd

# プロジェクトルートを sys.path に追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.column_config import (
    load_column_config,
    save_column_config,
    reset_column_config,
    get_required_columns,
    get_index_column,
    get_sheet_names,
    DEFAULT_COLUMNS,
    DEFAULT_SHEET_NAMES,
)
from src.loader import load_bom, validate_columns
from src.comparator import (
    compare_bom,
    find_added,
    find_removed,
    find_quantity_changes,
    find_manufacturer_changes,
)
from src.preprocessor import load_excel_columns, keep_columns_and_save


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture(autouse=True)
def reset_config():
    """各テスト前後にカラム設定をデフォルトにリセットする"""
    reset_column_config()
    yield
    reset_column_config()


@pytest.fixture
def sample_old_df():
    """テスト用の旧BOM DataFrame"""
    return pd.DataFrame({
        "Manufacturer Part Number": ["PN-001", "PN-002", "PN-003", "PN-004"],
        "Manufacturer Name":        ["Murata",  "TDK",   "Panasonic", "Vishay"],
        "Requested Quantity 1":     ["10",      "5",     "100",       "20"],
        "Description":              ["Cap",     "Ind",   "Res",       "Diode"],
    }).set_index("Manufacturer Part Number")


@pytest.fixture
def sample_new_df():
    """テスト用の新BOM DataFrame（追加・削除・変更あり）"""
    return pd.DataFrame({
        "Manufacturer Part Number": ["PN-001", "PN-003", "PN-004", "PN-005"],
        "Manufacturer Name":        ["Murata", "Yageo",  "Vishay", "Samsung"],
        "Requested Quantity 1":     ["15",     "100",    "20",     "8"],
        "Description":              ["Cap",    "Res",    "Diode",  "LED"],
    }).set_index("Manufacturer Part Number")


@pytest.fixture
def excel_files(tmp_path, sample_old_df, sample_new_df):
    """テスト用の Excel ファイルを一時ディレクトリに作成する"""
    old_path = tmp_path / "old.xlsx"
    new_path = tmp_path / "new.xlsx"
    sample_old_df.reset_index().to_excel(old_path, index=False)
    sample_new_df.reset_index().to_excel(new_path, index=False)
    return str(old_path), str(new_path)


# ============================================================
# column_config のテスト
# ============================================================

class TestColumnConfig:

    def test_default_values(self):
        """デフォルト値が正しく読み込まれること"""
        cfg = load_column_config()
        assert cfg["columns"]["part_number"]  == "Manufacturer Part Number"
        assert cfg["columns"]["manufacturer"] == "Manufacturer Name"
        assert cfg["columns"]["quantity"]     == "Requested Quantity 1"
        assert cfg["columns"]["description"]  == "Description"
        assert cfg["sheet_names"]["added"]    == "追加部品"

    def test_save_and_load(self):
        """保存した設定が正しく読み込まれること"""
        custom = {
            "columns": {
                "part_number":  "Part No",
                "manufacturer": "Vendor",
                "quantity":     "Qty",
                "description":  "Item",
            },
            "sheet_names": {
                "added": "New", "removed": "Del", "qty": "Q", "mfr": "M",
            },
        }
        save_column_config(custom)
        loaded = load_column_config()
        assert loaded["columns"]["part_number"]  == "Part No"
        assert loaded["columns"]["manufacturer"] == "Vendor"
        assert loaded["sheet_names"]["added"]    == "New"

    def test_reset(self):
        """リセット後にデフォルト値に戻ること"""
        save_column_config({
            "columns":     {"part_number":"X","manufacturer":"Y","quantity":"Z","description":"W"},
            "sheet_names": {"added":"A","removed":"B","qty":"C","mfr":"D"},
        })
        reset_column_config()
        assert get_index_column() == "Manufacturer Part Number"
        assert get_required_columns() == [
            "Manufacturer Part Number", "Manufacturer Name",
            "Requested Quantity 1", "Description",
        ]

    def test_get_required_columns_returns_list(self):
        """get_required_columns() が4要素のリストを返すこと"""
        cols = get_required_columns()
        assert isinstance(cols, list)
        assert len(cols) == 4

    def test_custom_columns_reflected_in_required(self):
        """カスタム設定が get_required_columns() に反映されること"""
        save_column_config({
            "columns": {
                "part_number":"PN","manufacturer":"MFR","quantity":"QTY","description":"DESC"
            },
            "sheet_names": DEFAULT_SHEET_NAMES,
        })
        assert get_required_columns() == ["PN", "MFR", "QTY", "DESC"]


# ============================================================
# loader のテスト
# ============================================================

class TestLoader:

    def test_load_bom_basic(self, excel_files):
        """Excel を正しく読み込み、インデックスが設定されること"""
        old_path, _ = excel_files
        df = load_bom(old_path)
        assert df.index.name == "Manufacturer Part Number"
        assert "Manufacturer Name" in df.columns
        assert len(df) == 4

    def test_load_bom_strips_whitespace(self, tmp_path):
        """カラム名・値の前後空白が除去されること"""
        path = tmp_path / "ws.xlsx"
        pd.DataFrame({
            "Manufacturer Part Number": [" PN-001 "],
            "Manufacturer Name":        [" Murata "],
            "Requested Quantity 1":     [" 10 "],
            "Description":              [" Cap "],
        }).to_excel(path, index=False)
        df = load_bom(str(path))
        assert df.index[0] == "PN-001"
        assert df.loc["PN-001", "Manufacturer Name"] == "Murata"

    def test_load_bom_missing_column_raises(self, tmp_path):
        """必須カラムが欠けている場合に ValueError が発生すること"""
        path = tmp_path / "bad.xlsx"
        pd.DataFrame({"Col A": [1], "Col B": [2]}).to_excel(path, index=False)
        with pytest.raises(ValueError, match="必要なカラムが不足"):
            load_bom(str(path))

    def test_load_bom_custom_columns(self, tmp_path):
        """カスタムカラム名でも正しく読み込めること"""
        save_column_config({
            "columns": {
                "part_number":"PN","manufacturer":"MFR","quantity":"QTY","description":"DESC"
            },
            "sheet_names": DEFAULT_SHEET_NAMES,
        })
        path = tmp_path / "custom.xlsx"
        pd.DataFrame({
            "PN":   ["P1", "P2"],
            "MFR":  ["A",  "B"],
            "QTY":  ["1",  "2"],
            "DESC": ["X",  "Y"],
        }).to_excel(path, index=False)
        df = load_bom(str(path))
        assert df.index.name == "PN"
        assert "MFR" in df.columns


# ============================================================
# comparator のテスト
# ============================================================

class TestComparator:

    def test_find_added(self, sample_old_df, sample_new_df):
        """追加部品が正しく検出されること"""
        added = find_added(sample_old_df, sample_new_df)
        assert list(added.index) == ["PN-005"]

    def test_find_removed(self, sample_old_df, sample_new_df):
        """削除部品が正しく検出されること"""
        removed = find_removed(sample_old_df, sample_new_df)
        assert list(removed.index) == ["PN-002"]

    def test_find_quantity_changes(self, sample_old_df, sample_new_df):
        """Quantity変更が正しく検出されること"""
        qty = find_quantity_changes(sample_old_df, sample_new_df)
        assert "PN-001" in qty.index
        assert qty.loc["PN-001", "Old Requested Quantity 1"] == "10"
        assert qty.loc["PN-001", "New Requested Quantity 1"] == "15"

    def test_find_manufacturer_changes(self, sample_old_df, sample_new_df):
        """Manufacturer変更が正しく検出されること"""
        mfr = find_manufacturer_changes(sample_old_df, sample_new_df)
        assert "PN-003" in mfr.index
        assert mfr.loc["PN-003", "Old Manufacturer Name"] == "Panasonic"
        assert mfr.loc["PN-003", "New Manufacturer Name"] == "Yageo"

    def test_compare_bom_returns_all_keys(self, sample_old_df, sample_new_df):
        """compare_bom() が4つのキーを持つ辞書を返すこと"""
        results = compare_bom(sample_old_df, sample_new_df)
        assert set(results.keys()) == {"added", "removed", "qty_changed", "mfr_changed"}

    def test_no_changes_when_identical(self, sample_old_df):
        """同一BOMを比較したとき差分がゼロになること"""
        results = compare_bom(sample_old_df, sample_old_df)
        assert results["added"].empty
        assert results["removed"].empty
        assert results["qty_changed"].empty
        assert results["mfr_changed"].empty

    def test_quantity_change_case_insensitive_manufacturer(self, sample_old_df, sample_new_df):
        """Manufacturer の大文字小文字の違いは変更として検出されないこと"""
        # sample_old_df の Murata を MURATA にしても Manufacturer変更にならないことを確認
        new_df2 = sample_new_df.copy()
        new_df2.loc["PN-001", "Manufacturer Name"] = "MURATA"
        mfr = find_manufacturer_changes(sample_old_df, new_df2)
        assert "PN-001" not in mfr.index

    def test_compare_bom_custom_columns(self, tmp_path):
        """カスタムカラム名でも比較が正しく動作すること"""
        save_column_config({
            "columns": {
                "part_number":"PN","manufacturer":"MFR","quantity":"QTY","description":"DESC"
            },
            "sheet_names": DEFAULT_SHEET_NAMES,
        })
        old = pd.DataFrame({
            "PN":["A","B"],"MFR":["X","Y"],"QTY":["1","2"],"DESC":["a","b"]
        }).set_index("PN")
        new = pd.DataFrame({
            "PN":["A","C"],"MFR":["X","Z"],"QTY":["5","3"],"DESC":["a","c"]
        }).set_index("PN")
        results = compare_bom(old, new)
        assert list(results["added"].index)   == ["C"]
        assert list(results["removed"].index) == ["B"]
        assert "A" in results["qty_changed"].index


# ============================================================
# preprocessor のテスト
# ============================================================

class TestPreprocessor:

    def test_load_excel_columns(self, tmp_path):
        """Excel のカラム名一覧が正しく取得できること"""
        path = tmp_path / "test.xlsx"
        pd.DataFrame({"A": [1], "B": [2], "C": [3]}).to_excel(path, index=False)
        cols = load_excel_columns(str(path))
        assert cols == ["A", "B", "C"]

    def test_load_excel_columns_strips_whitespace(self, tmp_path):
        """カラム名の前後空白が除去されること"""
        path = tmp_path / "ws.xlsx"
        df = pd.DataFrame([[1, 2]])
        df.columns = [" Col A ", " Col B "]
        df.to_excel(path, index=False)
        cols = load_excel_columns(str(path))
        assert cols == ["Col A", "Col B"]

    def test_keep_columns_and_save(self, tmp_path):
        """指定した列だけ残してリネームなしで保存されること"""
        src = tmp_path / "src.xlsx"
        out = tmp_path / "out.xlsx"
        pd.DataFrame({
            "Part No": ["P1"], "Vendor": ["M1"],
            "Qty": ["10"],     "Item": ["A"],
            "Price": ["0.5"],  "Stock": ["100"],
        }).to_excel(src, index=False)

        result = keep_columns_and_save(
            str(src), ["Part No", "Vendor", "Qty", "Item"], str(out)
        )
        df = pd.read_excel(out, dtype=str)

        # カラム名がリネームされていないこと
        assert list(df.columns) == ["Part No", "Vendor", "Qty", "Item"]
        # 不要列が削除されていること
        assert "Price" not in df.columns
        assert "Stock" not in df.columns
        assert set(result["dropped_columns"]) == {"Price", "Stock"}

    def test_keep_columns_empty_raises(self, tmp_path):
        """keep_columns が空のとき ValueError が発生すること"""
        src = tmp_path / "src.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(src, index=False)
        with pytest.raises(ValueError, match="残すカラムが指定されていません"):
            keep_columns_and_save(str(src), [], str(tmp_path / "out.xlsx"))

    def test_keep_columns_drops_empty_rows(self, tmp_path):
        """完全空白行が除去されること"""
        src = tmp_path / "src.xlsx"
        out = tmp_path / "out.xlsx"
        pd.DataFrame({
            "A": ["val1", None, "val3"],
            "B": ["x",    None, "z"],
        }).to_excel(src, index=False)
        result = keep_columns_and_save(str(src), ["A", "B"], str(out))
        df = pd.read_excel(out)
        assert result["rows"] == 2


# ============================================================
# 統合テスト
# ============================================================

class TestIntegration:

    def test_full_pipeline(self, tmp_path):
        """Prepare → BOM比較 のフル統合テスト"""
        # 1. 余分な列を含む元ファイル
        raw_old = tmp_path / "raw_old.xlsx"
        raw_new = tmp_path / "raw_new.xlsx"
        pd.DataFrame({
            "Manufacturer Part Number": ["PN-001","PN-002"],
            "Manufacturer Name":        ["Murata","TDK"],
            "Requested Quantity 1":     ["10","5"],
            "Description":              ["Cap","Ind"],
            "Unit Price":               ["0.5","1.2"],   # 不要列
        }).to_excel(raw_old, index=False)
        pd.DataFrame({
            "Manufacturer Part Number": ["PN-001","PN-003"],
            "Manufacturer Name":        ["Murata","Yageo"],
            "Requested Quantity 1":     ["20","100"],
            "Description":              ["Cap","Res"],
            "Unit Price":               ["0.5","0.04"],   # 不要列
        }).to_excel(raw_new, index=False)

        # 2. Prepare: 不要列を削除して保存
        keep = ["Manufacturer Part Number","Manufacturer Name",
                "Requested Quantity 1","Description"]
        out_old = tmp_path / "old.xlsx"
        out_new = tmp_path / "new.xlsx"
        keep_columns_and_save(str(raw_old), keep, str(out_old))
        keep_columns_and_save(str(raw_new), keep, str(out_new))

        # 3. BOM比較
        old_df = load_bom(str(out_old))
        new_df = load_bom(str(out_new))
        results = compare_bom(old_df, new_df)

        assert list(results["added"].index)       == ["PN-003"]
        assert list(results["removed"].index)     == ["PN-002"]
        assert "PN-001" in results["qty_changed"].index
        assert results["mfr_changed"].empty

    def test_full_pipeline_custom_columns(self, tmp_path):
        """カスタムカラム名でのフル統合テスト"""
        save_column_config({
            "columns": {
                "part_number":"PN","manufacturer":"MFR","quantity":"QTY","description":"DESC"
            },
            "sheet_names": DEFAULT_SHEET_NAMES,
        })
        raw = tmp_path / "raw.xlsx"
        pd.DataFrame({
            "PN":   ["A","B"], "MFR": ["X","Y"],
            "QTY":  ["1","2"], "DESC":["a","b"],
            "EXTRA":["e","f"],
        }).to_excel(raw, index=False)

        out = tmp_path / "out.xlsx"
        keep_columns_and_save(str(raw), ["PN","MFR","QTY","DESC"], str(out))
        df = load_bom(str(out))

        assert df.index.name == "PN"
        assert "EXTRA" not in df.columns
