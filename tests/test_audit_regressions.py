import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from src.column_config import get_column_names
from src.comparator import compare_bom
from src.gui import merge_lifecycle_results
from src.loader import load_bom
from src.mouser_client import MouserClient
from src.report import save_report


def write_bom(path, rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(list(get_column_names().values()))
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def test_loader_preserves_literal_na_and_reports_blank_duplicate_and_invalid_rows(tmp_path):
    path = tmp_path / "bom.xlsx"
    write_bom(path, [("NA", "Maker", 1, "Part")])
    assert list(load_bom(path).index) == ["NA"]

    write_bom(path, [
        ("P1", "Maker", 1, "Part"),
        (None, None, None, None),
        ("P1", "Maker", "pending", "Part"),
        (None, "Maker", 2, "Part"),
    ])
    with pytest.raises(ValueError) as error:
        load_bom(path)
    assert "型番が空欄（Excelの行 5）" in str(error.value)
    assert "型番が重複（Excelの行 2, 4）" in str(error.value)
    assert "数量が有限の数値ではありません（Excelの行 4）" in str(error.value)


def test_report_preserves_text_instead_of_creating_formulas(tmp_path):
    fields = get_column_names()
    new_bom = pd.DataFrame([["Maker", "1", "=1+1"]],
                           columns=[fields["manufacturer"], fields["quantity"], fields["description"]],
                           index=pd.Index(["P1"], name=fields["part_number"]))
    output = tmp_path / "report.xlsx"
    save_report(compare_bom(new_bom.iloc[:0], new_bom), output,
                mouser_results={"P1": {"lifecycle": "obsolete",
                                       "substitutes": [{"description": "=1+1"}]}})
    workbook = load_workbook(output)
    for cell in (workbook.worksheets[0]["D2"], workbook.worksheets[-1]["E2"]):
        assert cell.data_type == "s"
        assert cell.value == "=1+1"
    workbook.close()


def test_mouser_rejects_different_manufacturer_and_preserves_unknown(monkeypatch):
    client = MouserClient("test")
    data = {"ManufacturerPartNumber": "P100", "Manufacturer": "Maker",
            "LifecycleStatus": None, "SuggestedReplacement": "OTHER-100"}
    monkeypatch.setattr(client, "search_part", lambda pn: [data])
    rejected = client.check_lifecycle("P100", "Different")
    assert rejected["status_label"] == "Manufacturer mismatch"
    assert rejected["substitutes"] == []
    assert client.check_lifecycle("P100", "maker")["lifecycle"] == "unknown"


def test_lifecycle_summary_uses_most_severe_status_regardless_of_order():
    dk = {"P1": {"lifecycle": "active"}, "P2": {"lifecycle": "unknown"}}
    mouser = {"P1": {"lifecycle": "obsolete"}, "P2": {"lifecycle": "nrnd"}}
    assert merge_lifecycle_results(dk, mouser) == mouser
    assert merge_lifecycle_results(mouser, dk) == mouser
