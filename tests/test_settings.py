from dctq_auto.config.settings import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("ADB_SERIAL", raising=False)
    monkeypatch.delenv("LOG_DIR", raising=False)
    monkeypatch.delenv("SCREENSHOT_DIR", raising=False)
    settings = Settings.from_env()
    assert settings.adb_serial is None
    assert settings.log_dir == __import__("pathlib").Path("logs")
    assert settings.screenshot_dir == __import__("pathlib").Path("artifacts/screenshots")
