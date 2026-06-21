"""
digikey_client.py - DigiKey API v4 クライアントモジュール

OAuth2 (2-legged / Client Credentials) でトークンを取得し、
Product Information V4 エンドポイントを使って以下を取得します。
  ・部品のライフサイクルステータス（Active / NRND / Obsolete 等）
  ・代替品 Substitutions
  ・推奨品 RecommendedProducts
  ・部品仕様 Parameters（AI のランキング判断に使用）

必要な認証情報:
    DIGIKEY_CLIENT_ID     : DigiKey Developer Portal で発行したクライアントID
    DIGIKEY_CLIENT_SECRET : 同クライアントシークレット
"""

import os
import time
import configparser
import requests


# ============================================================
# API エンドポイント定数
# ============================================================
TOKEN_URL              = "https://api.digikey.com/v1/oauth2/token"
PRODUCT_DETAILS_URL    = "https://api.digikey.com/products/v4/search/{pn}/productdetails"
SUBSTITUTIONS_URL      = "https://api.digikey.com/products/v4/search/{pn}/substitutions"
RECOMMENDED_URL        = "https://api.digikey.com/products/v4/search/{pn}/recommendedproducts"

# ライフサイクルステータスの分類セット
OBSOLETE_STATUSES = {"Obsolete", "Discontinued"}
NRND_STATUSES     = {"Not Recommended for New Designs", "NRND", "Last Time Buy"}

# ライフサイクル定数（GUI の色分けに使う）
LIFECYCLE_OBSOLETE = "obsolete"
LIFECYCLE_NRND     = "nrnd"
LIFECYCLE_ACTIVE   = "active"
LIFECYCLE_UNKNOWN  = "unknown"

# 候補プールの取得上限
#   DigiKey候補が多い場合でも AI に渡す件数が多すぎないよう上限を設ける
#   Substitutions 最大10件 + RecommendedProducts 最大10件 = 最大20件
MAX_SUBSTITUTES   = 10
MAX_RECOMMENDED   = 10


# ============================================================
# 認証情報の読み込み
# ============================================================

def load_credentials() -> tuple[str, str]:
    """
    DigiKey API のクライアントIDとシークレットを取得する。

    優先順位:
        1. 環境変数 DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET
        2. プロジェクトルートの config.ini ([digikey] セクション)

    Returns:
        tuple[str, str]: (client_id, client_secret)

    Raises:
        ValueError: 認証情報が見つからない場合
    """
    client_id     = os.environ.get("DIGIKEY_CLIENT_ID", "")
    client_secret = os.environ.get("DIGIKEY_CLIENT_SECRET", "")
    if client_id and client_secret:
        return client_id, client_secret

    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.ini")
    config.read(config_path, encoding="utf-8")
    if config.has_section("digikey"):
        client_id     = config.get("digikey", "client_id",     fallback="")
        client_secret = config.get("digikey", "client_secret", fallback="")
    if client_id and client_secret:
        return client_id, client_secret

    raise ValueError(
        "DigiKey APIの認証情報が見つかりません。\n"
        "環境変数 DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET を設定するか、\n"
        "config.ini に [digikey] セクションを追加してください。"
    )


# ============================================================
# DigiKeyClient クラス
# ============================================================

class DigiKeyClient:
    """DigiKey Product Information API v4 クライアント"""

    def __init__(self, client_id: str, client_secret: str):
        self._client_id     = client_id
        self._client_secret = client_secret
        self._access_token  = ""
        self._token_expires = 0.0

    # ----------------------------------------------------------
    # OAuth2 トークン管理
    # ----------------------------------------------------------

    def _ensure_token(self) -> None:
        """アクセストークンが期限切れなら再取得する（30秒前に先行更新）"""
        if time.time() < self._token_expires - 30:
            return
        resp = requests.post(TOKEN_URL, data={
            "grant_type":    "client_credentials",
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._access_token  = data["access_token"]
        self._token_expires = time.time() + int(data.get("expires_in", 3600))

    def _headers(self) -> dict:
        self._ensure_token()
        return {
            "Authorization":      f"Bearer {self._access_token}",
            "X-DIGIKEY-Client-Id": self._client_id,
            "Content-Type":       "application/json",
        }

    # ----------------------------------------------------------
    # 個別エンドポイント
    # ----------------------------------------------------------

    def get_product_details(self, part_number: str) -> dict | None:
        """
        部品詳細を取得する。見つからない場合は None を返す。

        取得内容:
          - ライフサイクルステータス (ProductStatus.Status)
          - スペック一覧 (Parameters)
          - 在庫数・価格など

        Args:
            part_number (str): メーカー品番 または DigiKey 品番

        Returns:
            dict | None: API レスポンス全体、404 の場合は None
        """
        url  = PRODUCT_DETAILS_URL.format(pn=requests.utils.quote(part_number))
        resp = requests.get(url, headers=self._headers(), timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def get_substitutions(self, part_number: str) -> list[dict]:
        """
        DigiKey の Substitutions エンドポイントから代替品を取得する。

        DigiKey が公式に登録している直接代替品（ドロップイン互換品）。
        Substitutions は通常 RecommendedProducts より互換性が高い。

        Args:
            part_number (str): 代替品を調べたい部品番号

        Returns:
            list[dict]: 生の API レスポンス配列（SubstituteProducts）
        """
        url  = SUBSTITUTIONS_URL.format(pn=requests.utils.quote(part_number))
        resp = requests.get(url, headers=self._headers(), timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("SubstituteProducts", [])

    def get_recommended_products(self, part_number: str) -> list[dict]:
        """
        DigiKey の RecommendedProducts エンドポイントから推奨品を取得する。

        Substitutions より広い範囲の候補が含まれる。
        スペックが近い・同カテゴリの部品が返ってくることが多い。

        Args:
            part_number (str): 推奨品を調べたい部品番号

        Returns:
            list[dict]: 生の API レスポンス配列（RecommendedProducts）
        """
        url  = RECOMMENDED_URL.format(pn=requests.utils.quote(part_number))
        resp = requests.get(url, headers=self._headers(), timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("RecommendedProducts", [])

    # ----------------------------------------------------------
    # ライフサイクル + 候補プール 一括取得
    # ----------------------------------------------------------

    def check_lifecycle(self, part_number: str) -> dict:
        """
        ライフサイクルステータスと DigiKey 候補プールを一括取得する。

        取得フロー:
          1. ProductDetails でライフサイクルと元部品スペックを取得
          2. 廃品・NRND の場合のみ Substitutions + RecommendedProducts を取得
          3. 重複を排除して候補プールを作成

        Returns:
            dict: {
                "part_number"    : str,
                "lifecycle"      : str,       # LIFECYCLE_* 定数
                "status_label"   : str,       # 表示用ラベル
                "source_specs"   : list[dict],# 元部品のスペック（AI 判断用）
                "candidates"     : list[dict],# 候補プール（Subs + Recommended）
                "substitutes"    : list[dict],# Substitutions のみ（GUI表示用）
                "error"          : str,
            }
        """
        result = {
            "part_number":  part_number,
            "lifecycle":    LIFECYCLE_UNKNOWN,
            "status_label": "Unknown",
            "source_specs": [],
            "candidates":   [],   # Subs + Recommended をマージした全候補
            "substitutes":  [],   # GUI の DigiKey テーブル用（Subs のみ）
            "error":        "",
        }

        try:
            details = self.get_product_details(part_number)
            if details is None:
                result["error"] = "Part not found in DigiKey"
                return result

            product    = details.get("Product", {})
            status_str = product.get("ProductStatus", {}).get("Status", "")

            lifecycle, label = _classify_lifecycle(status_str)
            result["lifecycle"]    = lifecycle
            result["status_label"] = label

            # 元部品のスペックを抽出（AI のランキング判断材料）
            result["source_specs"] = _extract_specs(product)

            # 廃品・NRND のみ候補を取得
            if lifecycle in (LIFECYCLE_OBSOLETE, LIFECYCLE_NRND):

                # Substitutions（直接代替品・互換性が高い）
                subs_raw  = self.get_substitutions(part_number)
                subs_list = _parse_candidates(subs_raw[:MAX_SUBSTITUTES],
                                              source="substitution")
                result["substitutes"] = subs_list  # GUI 表示用

                # RecommendedProducts（推奨品・候補が広め）
                rec_raw  = self.get_recommended_products(part_number)
                rec_list = _parse_candidates(rec_raw[:MAX_RECOMMENDED],
                                             source="recommended")

                # 重複排除してマージ（Substitutions を優先・先頭に）
                result["candidates"] = _merge_candidates(subs_list, rec_list)

        except requests.exceptions.HTTPError as e:
            result["error"] = f"HTTP {e.response.status_code}: {e.response.text[:120]}"
        except requests.exceptions.RequestException as e:
            result["error"] = f"通信エラー: {e}"
        except Exception as e:
            result["error"] = f"予期しないエラー: {e}"

        return result


# ============================================================
# ヘルパー関数
# ============================================================

def _classify_lifecycle(status_str: str) -> tuple[str, str]:
    """
    DigiKey の Status 文字列を内部ライフサイクル定数とラベルに変換する。

    Args:
        status_str (str): API レスポンスの Status フィールド値

    Returns:
        tuple[str, str]: (lifecycle定数, 表示ラベル)
    """
    if status_str in OBSOLETE_STATUSES:
        return LIFECYCLE_OBSOLETE, "Obsolete"
    if status_str in NRND_STATUSES:
        return LIFECYCLE_NRND, "NRND"
    if status_str == "Active":
        return LIFECYCLE_ACTIVE, "Active"
    if status_str:
        return LIFECYCLE_NRND, status_str
    return LIFECYCLE_UNKNOWN, "Unknown"


def _extract_specs(product: dict) -> list[dict]:
    """
    ProductDetails レスポンスの Parameters（スペック）を抽出する。

    AI が元部品との仕様一致度を判断するための材料として使用する。
    例: [{"name": "Resistance", "value": "1 kOhms"}, ...]

    Args:
        product (dict): API レスポンスの Product オブジェクト

    Returns:
        list[dict]: [{"name": str, "value": str}, ...]
    """
    specs = []
    for param in product.get("Parameters", []):
        name  = param.get("ParameterText", "")
        value = param.get("ValueText", "")
        if name and value:
            specs.append({"name": name, "value": value})
    return specs


def _parse_candidates(raw_list: list[dict], source: str) -> list[dict]:
    """
    API レスポンスの部品リストを共通フォーマットに正規化する。

    Args:
        raw_list (list[dict]): API レスポンス配列
            (SubstituteProducts または RecommendedProducts)
        source (str): 候補の出所 "substitution" または "recommended"

    Returns:
        list[dict]: 正規化した候補リスト
            各要素は以下のキーを持つ:
            - mfr_part_number   : str  メーカー品番
            - digikey_part_number: str  DigiKey 品番
            - manufacturer      : str  メーカー名
            - description       : str  説明
            - specs             : list[dict]  スペック一覧（AI判断用）
            - source            : str  "substitution" / "recommended"
    """
    result = []
    for item in raw_list:
        mfr_pn = item.get("ManufacturerProductNumber", "")
        mfr    = item.get("Manufacturer", {}).get("Name", "")
        desc   = item.get("Description", {}).get("ProductDescription", "")
        dk_pn  = ""
        variations = item.get("ProductVariations", [])
        if variations:
            dk_pn = variations[0].get("DigiKeyProductNumber", "")
        specs = _extract_specs(item)

        if mfr_pn:  # 品番がないものは除外
            result.append({
                "mfr_part_number":    mfr_pn,
                "digikey_part_number": dk_pn,
                "manufacturer":       mfr,
                "description":        desc,
                "specs":              specs,
                "source":             source,
            })
    return result


def _merge_candidates(
    subs: list[dict],
    recommended: list[dict],
) -> list[dict]:
    """
    Substitutions と RecommendedProducts を重複排除してマージする。

    重複判定はメーカー品番（大文字小文字・スペース無視）で行う。
    Substitutions を先頭に配置し、RecommendedProducts で補完する。

    Args:
        subs (list[dict]): Substitutions の正規化済みリスト
        recommended (list[dict]): RecommendedProducts の正規化済みリスト

    Returns:
        list[dict]: 重複排除後のマージリスト
    """
    seen   = set()
    merged = []

    for cand in subs + recommended:
        key = cand["mfr_part_number"].lower().replace(" ", "")
        if key and key not in seen:
            seen.add(key)
            merged.append(cand)

    return merged


# ============================================================
# ファクトリ関数
# ============================================================

def create_client() -> "DigiKeyClient":
    """認証情報を自動読み込みして DigiKeyClient を生成する"""
    client_id, client_secret = load_credentials()
    return DigiKeyClient(client_id, client_secret)
