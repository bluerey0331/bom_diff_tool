from src import column_config


def test_api_credentials_preserve_other_settings_and_can_be_cleared(tmp_path, monkeypatch):
    vault = {}
    monkeypatch.setattr(column_config.credential_store, "read_credentials",
                        lambda: dict(vault) if vault else None)
    monkeypatch.setattr(column_config.credential_store, "write_credentials", vault.update)
    config_file = tmp_path / "config.ini"
    config_file.write_text("[columns]\nquantity = Custom quantity\n[digikey]\nclient_secret = old-secret\n", encoding="utf-8")
    monkeypatch.setattr(column_config, "_CONFIG_PATH", str(config_file))
    monkeypatch.setattr(column_config, "_USER_CONFIG_PATH", str(config_file))

    column_config.save_api_settings(digikey=("test-id", "test%secret"), mouser="test-key")
    column_config.save_api_settings(mouser="new-key")

    assert column_config.load_api_settings() == {
        "client_id": "test-id",
        "client_secret": "test%secret",
        "api_key": "new-key",
    }
    assert "old-secret" not in config_file.read_text(encoding="utf-8")
    assert "test%secret" not in config_file.read_text(encoding="utf-8")
    assert column_config.get_column_names()["quantity"] == "Custom quantity"

    column_config.save_api_settings(digikey=("", ""))
    assert column_config.load_api_settings() == {
        "client_id": "",
        "client_secret": "",
        "api_key": "new-key",
    }
