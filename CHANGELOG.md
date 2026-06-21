# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-06-21

### Added

- **BOM 差分比較**
  - 追加・削除・Quantity変更・Manufacturer変更の4種類を自動検出
  - old.xlsx / new.xlsx を読み込んで比較
  - Excel レポート出力（追加部品・削除部品・Qty変更・Mfr変更の4シート）

- **GUI**（`src/gui.py`）
  - tkinter 製ダークテーマデスクトップアプリ
  - タブ形式の結果表示（Added / Removed / Qty Changed / Mfr Changed / Lifecycle）
  - 比較結果のサマリーカード

- **カラム名カスタマイズ**（`src/column_config.py`, `src/settings_dialog.py`）
  - ⚙ 設定ボタンから BOM カラム名・Excel シート名を変更可能
  - 設定は `config.ini` に自動保存され次回起動時も維持
  - Prepare / BOM比較の両ツールで設定を共有

- **DigiKey API 連携**（`src/digikey_client.py`）
  - ライフサイクルステータス（Active / NRND / Obsolete）の自動チェック
  - Substitutions・RecommendedProducts エンドポイントで代替品取得
  - Lifecycle タブで廃品・NRND を色分け表示、行クリックで代替品一覧

- **Prepare ツール**（`prepare.py`, `src/preprocessor.py`）
  - 任意の Excel から不要列をチェックボックスで選択して削除
  - 設定カラム4列はデフォルトON、その他はデフォルトOFF
  - カラム名はリネームせず元のまま保存

- **CLI モード**
  - `python main.py --cli` で GUI なし実行
  - `--old` / `--new` / `--output` オプション対応

- **テスト**（`tests/test_all.py`）
  - pytest 形式、24テストケース
  - column_config / loader / comparator / preprocessor / 統合テストをカバー

- **GitHub Actions**（`.github/workflows/test.yml`）
  - Python 3.11 / 3.12 での自動テスト

- **サンプルデータ**（`sample_old.xlsx`, `sample_new.xlsx`）
  - 実際の部品型番を使ったダミーデータ
  - 追加・削除・Qty変更・Mfr変更の全パターンを含む
