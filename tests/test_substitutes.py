from unittest.mock import Mock

from src.digikey_client import DigiKeyClient
from src.mouser_client import MouserClient


def test_digikey_reads_v4_substitutes_and_uses_distributor_part_number(monkeypatch):
    client = DigiKeyClient("test", "test")
    monkeypatch.setattr(client, "_headers", lambda: {})
    monkeypatch.setattr(client, "get_product_details", lambda pn: {
        "Product": {
            "ProductStatus": {"Status": "Obsolete"},
            "ProductVariations": [{"DigiKeyProductNumber": "296-OLD-ND"}],
        },
    })
    monkeypatch.setattr(client, "get_recommended_products", lambda pn: [])

    def get(url, **kwargs):
        assert url.endswith("/296-OLD-ND/substitutions")
        return Mock(status_code=200, json=lambda: {
            "ProductSubstitutes": [{
                "ManufacturerProductNumber": "LM358DR",
                "DigiKeyProductNumber": "296-NEW-ND",
                "Description": "Dual operational amplifier",
            }],
        })

    monkeypatch.setattr("src.digikey_client.requests.get", get)
    result = client.check_lifecycle("LM358D")
    assert not result["error"]
    candidate, = result["substitutes"]
    assert candidate["mfr_part_number"] == "LM358DR"
    assert candidate["digikey_part_number"] == "296-NEW-ND"
    assert candidate["description"] == "Dual operational amplifier"


def test_mouser_uses_the_exact_manufacturer_result_with_a_replacement(monkeypatch):
    client = MouserClient("test")
    common = {"ManufacturerPartNumber": "LM358D", "Manufacturer": "Texas Instruments"}
    monkeypatch.setattr(client, "search_part", lambda pn: [
        {**common, "Manufacturer": "Other", "SuggestedReplacement": "OTHER-REPLACEMENT"},
        {**common, "SuggestedReplacement": ""},
        {**common, "SuggestedReplacement": "595-LM358DR", "LifecycleStatus": "Obsolete"},
    ])
    result = client.check_lifecycle("LM358D", "Texas Instruments")
    assert result["lifecycle"] == "obsolete"
    candidate, = result["substitutes"]
    assert candidate["mouser_part_number"] == "595-LM358DR"
    assert candidate["mfr_part_number"] == ""
