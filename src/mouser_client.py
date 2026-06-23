"""
mouser_client.py - Mouser Search API v2 クライアントモジュール

Mouser Search API v2（JSON形式）を使って以下を取得します。
  ・部品のライフサイクルステータス（LifecycleStatus フィールド）
  ・代替品（SuggestedReplacement フィールド）

DigiKey と異なり OAuth2 は不要。APIキー1つで動作します。

必要な認証情報:
    MOUSER_API_KEY : Mouser Developer Portal で発行したAPIキー
                     https://www.mouser.com/api-hub/ から申請

レート制限:
    30 リクエスト / 分
    1,000 リクエスト / 日
"""

import os
import configparser
import requests


# ============================================================
# API エンドポイント定数
# ============================================================
SEARCH_URL = "https://api.mouser.com/api/v2/search/partnumber"

# Mouser が返す LifecycleStatus 文字列 → 内部定数 のマッピング
# （DigiKey と共通の定数を使うことでGUI/Reportを共有できる）
OBSOLETE_STATUSES = {
    "Obsolete",
    "Not For New Design",      # NFD: 新規設計不可
    "End of Life",
    "Discontinued",
}
NRND_STATUSES = {
    "Not Recommended For New Designs",
    "NRND",
    "Last Time Buy",
    "Last Time Ship",
}

# DigiKey クライアントと共通のライフサイクル定数
LIFECYCLE_OBSOLETE = "obsolete"
LIFECYCLE_NRND     = "nrnd"
LIFECYCLE_ACTIVE   = "active"
LIFECYCLE_UNKNOWN  = "unknown"


# ============================================================
# 認証情報の読み込み
# ============================================================

def load_api_key() -> str:
    """
    Mouser Search API キーを取得する。

    優先順位:
        1. 環境変数 MOUSER_API_KEY
        2. プロジェクトルートの config.ini ([mouser] セクション)

    Returns:
        str: APIキー文字列

    Raises:
        ValueError: APIキーが見つからない場合
    """
    # 1. 環境変数
    key = os.environ.get("MOUSER_API_KEY", "")
    if key:
        return key

    # 2. config.ini
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.ini")
    config.read(config_path, encoding="utf-8")
    key = config.get("mouser", "api_key", fallback="")
    if key and not key.startswith("YOUR_"):
        return key

    raise ValueError(
        "Mouser APIキーが見つかりません。\n"
        "環境変数 MOUSER_API_KEY を設定するか、\n"
        "config.ini の [mouser] セクションに api_key を追加してください。\n"
        "APIキーは https://www.mouser.com/api-hub/ から申請できます。"
    )


# ============================================================
# MouserClient クラス
# ============================================================

class MouserClient:
    """
    Mouser Search API v2 クライアント。

    DigiKeyClient と同じ check_lifecycle() インターフェースを持つため、
    GUI / Report 側のコードをほぼ変更せず利用できます。
    """

    def __init__(self, api_key: str):
        """
        Args:
            api_key (str): Mouser Search APIキー
        """
        self._api_key = api_key

    # ----------------------------------------------------------
    # 部品検索
    # ----------------------------------------------------------

    def search_part(self, part_number: str) -> list[dict]:
        """
        部品番号で検索して最大50件のマッチ結果を返す。

        Args:
            part_number (str): メーカー品番またはMouser品番

        Returns:
            list[dict]: マッチした部品情報のリスト（空の場合は []）

        Note:
            Mouser API v2 は POST リクエスト。
            APIキーは URL クエリパラメータで渡す。
        """
        resp = requests.post(
            SEARCH_URL,
            params={"apiKey": self._api_key},
            headers={
                "Content-Type": "application/json",
                "Accept":       "application/json",
            },
            json={
                "SearchByPartRequest": {
                    "mouserPartNumber":  part_number,
                    "partSearchOptions": "Exact",   # 完全一致を優先
                }
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        # Errors フィールドは「件数0」などの情報メッセージも含むため、
        # HTTPエラー（401/429 等）は raise_for_status() で処理済みとして
        # Parts リストのみを参照する。
        return data.get("SearchResults", {}).get("Parts", []) or []

    # ----------------------------------------------------------
    # ライフサイクル判定（DigiKeyClient と同一インターフェース）
    # ----------------------------------------------------------

    def check_lifecycle(self, part_number: str) -> dict:
        """
        部品のライフサイクルステータスと代替品を一括取得する。

        DigiKeyClient.check_lifecycle() と同じ戻り値フォーマットを返す。
        これにより gui.py / report.py を変更せずに利用できる。

        Args:
            part_number (str): 検索する部品番号

        Returns:
            dict: {
                "part_number"  : str,
                "lifecycle"    : str,        # LIFECYCLE_* 定数
                "status_label" : str,        # 表示用ラベル
                "substitutes"  : list[dict], # 代替品リスト
                "source"       : str,        # "mouser"（どのAPIで取得したか）
                "error"        : str,        # エラー時のメッセージ
            }
        """
        result = {
            "part_number":  part_number,
            "lifecycle":    LIFECYCLE_UNKNOWN,
            "status_label": "Unknown",
            "substitutes":  [],
            "source":       "mouser",
            "error":        "",
        }

        try:
            parts = self.search_part(part_number)

            if not parts:
                result["status_label"] = "Not Found"
                return result

            # 完全一致を優先（メーカー品番 or Mouser品番が一致するもの）
            part = _find_best_match(parts, part_number)

            # ライフサイクル判定
            status_str = part.get("LifecycleStatus", "") or ""
            lifecycle, label = _classify_lifecycle(status_str.strip())
            result["lifecycle"]    = lifecycle
            result["status_label"] = label

            # 代替品（SuggestedReplacement は文字列リストまたは単一文字列）
            suggested = part.get("SuggestedReplacement", "") or ""
            result["substitutes"] = _parse_substitutes(suggested)

        except requests.exceptions.Timeout:
            result["error"] = "タイムアウト（10秒）。再試行してください。"
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401:
                result["error"] = "APIキーが無効です。設定を確認してください。"
            elif code == 429:
                result["error"] = "レート制限中（30回/分）。しばらく待ってから再試行してください。"
            else:
                result["error"] = f"HTTP エラー {code}: {e.response.text[:120]}"
        except ValueError as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"予期しないエラー: {e}"

        return result


# ============================================================
# ヘルパー関数
# ============================================================

def _find_best_match(parts: list[dict], query: str) -> dict:
    """
    検索結果から最も一致する部品を選択する。

    優先順位:
      1. メーカー品番の完全一致（大文字小文字無視）
      2. Mouser品番の完全一致
      3. 最初の結果

    Args:
        parts (list[dict]): search_part() の戻り値
        query (str): 検索した部品番号

    Returns:
        dict: 最もマッチした部品情報
    """
    q = query.lower().strip()

    # 1. メーカー品番の完全一致
    for p in parts:
        if p.get("ManufacturerPartNumber", "").lower().strip() == q:
            return p

    # 2. Mouser品番の完全一致
    for p in parts:
        if p.get("MouserPartNumber", "").lower().strip() == q:
            return p

    # 3. 最初の結果
    return parts[0]


def _classify_lifecycle(status_str: str) -> tuple[str, str]:
    """
    Mouser の LifecycleStatus 文字列を内部定数とラベルに変換する。

    Args:
        status_str (str): API レスポンスの LifecycleStatus 値

    Returns:
        tuple[str, str]: (lifecycle定数, 表示ラベル)
    """
    if status_str in OBSOLETE_STATUSES:
        return LIFECYCLE_OBSOLETE, status_str or "Obsolete"
    if status_str in NRND_STATUSES:
        return LIFECYCLE_NRND, status_str or "NRND"
    if status_str in ("Active", "New Product", ""):
        # 空文字は在庫ありの現行品として扱う
        label = status_str if status_str else "Active"
        return LIFECYCLE_ACTIVE, label
    # 未知のステータスは NRND 相当として扱う
    return LIFECYCLE_NRND, status_str


def _parse_substitutes(suggested: str) -> list[dict]:
    """
    Mouser の SuggestedReplacement フィールドを代替品リストに変換する。

    Mouser は代替品をカンマ区切りの文字列で返す（品番のみ）。
    DigiKeyClient の substitutes フォーマットに合わせて返す。

    Args:
        suggested (str): "PN-001, PN-002" 形式の文字列、または空文字

    Returns:
        list[dict]: DigiKeyClient と互換の代替品辞書リスト
    """
    if not suggested:
        return []

    substitutes = []
    for pn in suggested.split(","):
        pn = pn.strip()
        if pn:
            substitutes.append({
                "mfr_part_number":     pn,
                "digikey_part_number": "",   # Mouserには DigiKey品番なし
                "manufacturer":        "",   # 品番のみなのでメーカー名は不明
                "description":         "",
                "source":              "mouser",
            })
    return substitutes


# ============================================================
# ファクトリ関数
# ============================================================

def create_client() -> "MouserClient":
    """
    APIキーを自動読み込みして MouserClient を生成する。

    Returns:
        MouserClient: 初期化済みクライアントインスタンス

    Raises:
        ValueError: APIキーが設定されていない場合
    """
    api_key = load_api_key()
    return MouserClient(api_key)
