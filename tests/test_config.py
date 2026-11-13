import json
import os

import config


def _isolate_settings(monkeypatch, tmp_path):
    store = tmp_path / "store"
    settings_file = store / "settings.json"
    legacy_file = tmp_path / "legacy-settings.json"
    monkeypatch.setattr(config, "APP_STORAGE_DIR", str(store))
    monkeypatch.setattr(config, "SETTINGS_FILE", str(settings_file))
    monkeypatch.setattr(config, "LEGACY_SETTINGS_FILE", str(legacy_file))
    return store, settings_file, legacy_file


def test_save_and_load_settings(monkeypatch, tmp_path):
    store, settings_file, _ = _isolate_settings(monkeypatch, tmp_path)

    config.save_settings({"save_path": "D:\\Docs", "timeout": 30, "max_workers": 8})
    loaded = config.load_settings()

    assert loaded["save_path"] == "D:\\Docs"
    assert loaded["timeout"] == 30
    assert loaded["max_workers"] == 8
    assert loaded["theme"] == "Dark"
    assert settings_file.exists()
    assert not os.path.exists(str(settings_file) + ".tmp")
    assert store.exists()


def test_legacy_settings_are_migrated(monkeypatch, tmp_path):
    store, settings_file, legacy_file = _isolate_settings(monkeypatch, tmp_path)
    store.mkdir(parents=True, exist_ok=True)

    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump({"timeout": 15, "theme": "Light"}, f)

    loaded = config.load_settings()

    assert loaded["timeout"] == 15
    assert loaded["theme"] == "Light"
    assert settings_file.exists()
    with open(settings_file, "r", encoding="utf-8") as f:
        persisted = json.load(f)
    assert persisted["timeout"] == 15


def test_invalid_settings_file_falls_back_to_defaults(monkeypatch, tmp_path):
    _, settings_file, _ = _isolate_settings(monkeypatch, tmp_path)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text("{not valid json", encoding="utf-8")

    loaded = config.load_settings()

    assert loaded["max_workers"] == config.DEFAULT_MAX_WORKERS
    assert loaded["timeout"] == config.TIMEOUT
