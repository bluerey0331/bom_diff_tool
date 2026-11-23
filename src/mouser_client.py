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
from src.ui_language import tr
from src.column_config import load_api_settings
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

    key = load_api_settings()["api_key"]
    if key:
        return key

    raise ValueError(tr("API設定でMouserの検索APIキーを入力してください。",
                        "Enter the Mouser Search API key in API settings."))


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

        search = data.get("SearchResults")
        parts = (search or {}).get("Parts") or []
        if parts:
            return parts
        errors = data.get("Errors") or []
        messages = [
            str(error.get("Message") or error.get("Code") or "").strip()
            for error in errors
        ]
        if any(message and not message.lower().startswith(
                ("no match", "no parts found", "no results found"))
                for message in messages):
            raise ValueError(tr("Mouser が検索リクエストを拒否しました。APIキーと品番を確認してください。", "Mouser rejected the request. Check your API key and the part number."))
        if search is None and not errors:
            raise ValueError(tr("Mouser の検索結果を読み取れませんでした。", "Could not read the Mouser search results."))
        return []

    # ----------------------------------------------------------
    # ライフサイクル判定（DigiKeyClient と同一インターフェース）
    # ----------------------------------------------------------

    def check_lifecycle(self, part_number: str, manufacturer: str = "") -> dict:
        """
        部品のライフサイクルステータスと代替品を一括取得する。

        DigiKeyClient.check_lifecycle() と同じ戻り値フォーマットを返す。
        これにより gui.py / report.py を変更せずに利用できる。

        Args:
            part_number (str): 検索する部品番号
            manufacturer (str): BOM上のメーカー名

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
            part = _find_best_match(parts, part_number, manufacturer)
            if part is None:
                exact = _find_best_match(parts, part_number)
                result["status_label"] = "Manufacturer mismatch" if manufacturer and exact else "Not Found"
                return result

            # ライフサイクル判定
            status_str = part.get("LifecycleStatus") or ""
            if not status_str and str(part.get("IsDiscontinued", "")).lower() in ("true", "yes", "1"):
                status_str = "Obsolete"
            lifecycle, label = _classify_lifecycle(status_str.strip())
            result["lifecycle"]    = lifecycle
            result["status_label"] = label

            result["source_specs"] = product_specs(part)
            result["description"] = part.get("Description") or ""

            # 代替品（SuggestedReplacement は文字列リストまたは単一文字列）
            suggested = part.get("SuggestedReplacement", "") or ""
            result["substitutes"] = _parse_substitutes(suggested)

        except requests.exceptions.Timeout:
            result["error"] = tr("タイムアウト（10秒）。再試行してください。", "The request timed out after 10 seconds. Try again.")
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            result["stop_check"] = code in (401, 403, 429)
            if code in (401, 403):
                result["error"] = tr("APIキーが無効です。設定を確認してください。", "The API key was rejected. Check your settings.")
            elif code == 429:
                result["error"] = tr("レート制限中（30回/分）。しばらく待ってから再試行してください。", "Rate limit reached. Wait and try again.")
            else:
                result["error"] = tr(f"Mouser APIのHTTPエラー ({code})", f"Mouser API HTTP error ({code})")
        except requests.exceptions.RequestException:
            result["error"] = tr("Mouser APIとの通信に失敗しました。", "Could not connect to the Mouser API.")
        except ValueError as e:
            result["error"] = str(e)
        except Exception:
            result["error"] = tr("Mouser の応答を処理できませんでした。", "Could not process the Mouser response.")

        return result


# ============================================================
# ヘルパー関数
# ============================================================

def product_specs(part: dict) -> list[dict]:
    specs = [
        {"name": item["AttributeName"], "value": item["AttributeValue"]}
        for item in part.get("ProductAttributes") or []
        if item.get("AttributeName") and item.get("AttributeValue")
    ]
    if part.get("Packaging"):
        specs.append({"name": "Packaging", "value": part["Packaging"]})
    return specs


def _find_best_match(parts: list[dict], query: str, manufacturer: str = "") -> dict | None:
    """Prefer an exact distributor SKU, then an exact manufacturer part."""
    query = query.casefold().strip()
    manufacturer = str(manufacturer or "").casefold().strip()
    if manufacturer:
        parts = [part for part in parts if manufacturer in {
            (part.get("Manufacturer") or "").casefold().strip(),
            (part.get("ActualMfrName") or "").casefold().strip(),
        }]
    for part in parts:
        if (part.get("MouserPartNumber") or "").casefold().strip() == query:
            return part
    matches = [part for part in parts
               if (part.get("ManufacturerPartNumber") or "").casefold().strip() == query]
    if not matches:
        return None
    return max(matches, key=lambda part: (bool(part.get("SuggestedReplacement")),
                                          bool(part.get("LifecycleStatus"))))


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
    if status_str in ("Active", "New Product"):
        return LIFECYCLE_ACTIVE, status_str
    return LIFECYCLE_UNKNOWN, status_str or "Unknown"


def _parse_substitutes(suggested: str | list[str]) -> list[dict]:
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

    values = suggested if isinstance(suggested, list) else [suggested]
    part_numbers = dict.fromkeys(
        part.strip() for value in values if isinstance(value, str)
        for part in value.replace(";", ",").split(",") if part.strip()
    )
    substitutes = [
        {"mfr_part_number": "", "mouser_part_number": pn,
         "manufacturer": "", "description": "", "source": "mouser"}
        for pn in part_numbers
    ]
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
