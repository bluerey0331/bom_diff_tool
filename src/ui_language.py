"""Language selection and shared display terms for the desktop UI."""

language = "ja"


def tr(japanese: str, english: str) -> str:
    return english if language == "en" else japanese


def lifecycle_label(status: str) -> str:
    japanese = {
        "Active": "現行品", "New Product": "新製品", "Obsolete": "廃止",
        "Discontinued": "廃止", "End of Life": "生産終了", "EOL": "生産終了",
        "NRND": "新規設計非推奨", "Last Time Buy": "最終購入",
        "Not For New Designs": "新規設計非推奨",
        "Not Recommended For New Designs": "新規設計非推奨",
        "Not Found": "該当なし", "Unknown": "不明",
        "Manufacturer mismatch": "メーカー不一致",
    }
    return tr(japanese.get(status, status), status)
