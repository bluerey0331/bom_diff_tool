"""Small catalog probes used independently of BOM comparison."""

import requests

from src.digikey_client import DigiKeyClient, load_credentials, load_locale_config
from src.mouser_client import MouserClient, load_api_key
from src.ui_language import tr


def test_connection(provider: str, credentials: tuple[str, ...]) -> str:
    try:
        if provider == "DigiKey":
            if any(credentials) and not all(credentials):
                raise ValueError(tr("DigiKeyのIDとシークレットを両方入力してください。",
                                    "Enter both DigiKey credentials."))
            client = DigiKeyClient(*(credentials if all(credentials) else load_credentials()),
                                   *load_locale_config())
            if client.get_product_details("LM358DR") is None:
                return tr("APIに接続しましたが、テスト品番が見つかりませんでした。",
                          "The API responded, but the test part was not found.")
        else:
            client = MouserClient(credentials[0] or load_api_key())
            if not client.search_part("LM358DR"):
                return tr("APIに接続しましたが、テスト品番が見つかりませんでした。",
                          "The API responded, but the test part was not found.")
    except requests.HTTPError as error:
        status = error.response.status_code
        messages = {
            401: tr("認証に失敗しました。", "Authentication failed."),
            403: tr("APIの利用権限が拒否されました。", "API access was denied."),
            429: tr("APIの利用回数制限に達しました。", "The API rate limit was reached."),
        }
        raise ValueError(f"{messages.get(status, tr('APIエラー', 'API error'))} (HTTP {status})") from None
    except requests.RequestException:
        raise ValueError(tr("APIとの通信に失敗しました。", "Could not communicate with the API.")) from None
    return tr("接続テストに成功しました。", "Connection test succeeded.")
