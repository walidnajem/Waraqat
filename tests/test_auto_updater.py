import os

import pytest

import auto_updater


@pytest.mark.parametrize(
    "version, expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v0.4.3", (0, 4, 3)),
        ("bad", (0,)),
        ("", (0,)),
    ],
)
def test_parse_version(version, expected):
    assert auto_updater.parse_version(version) == expected


def test_validate_downloaded_exe_rejects_small_files(tmp_path):
    path = tmp_path / "small.exe"
    path.write_bytes(b"MZ")

    with pytest.raises(RuntimeError, match="too small"):
        auto_updater._validate_downloaded_exe(str(path))


def test_validate_downloaded_exe_rejects_non_executable(tmp_path):
    path = tmp_path / "fake.exe"
    path.write_bytes(b"PK" + b"\0" * auto_updater.MIN_UPDATE_SIZE)

    with pytest.raises(RuntimeError, match="not a valid Windows executable"):
        auto_updater._validate_downloaded_exe(str(path))


def test_validate_downloaded_exe_accepts_mz_payload(tmp_path):
    path = tmp_path / "valid.exe"
    path.write_bytes(b"MZ" + b"\0" * auto_updater.MIN_UPDATE_SIZE)

    auto_updater._validate_downloaded_exe(str(path))
    assert os.path.getsize(path) > auto_updater.MIN_UPDATE_SIZE


import time
import types

import auto_updater


class _FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}

    def json(self):
        return self._data


def _wait_for(callback_result, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline and "value" not in callback_result:
        time.sleep(0.05)
    return callback_result.get("value")


def test_check_for_update_reports_up_to_date(monkeypatch):
    monkeypatch.setattr(auto_updater, "APP_VERSION", "0.4.3")
    monkeypatch.setattr(
        auto_updater.requests,
        "get",
        lambda *a, **k: _FakeResponse(200, {"tag_name": "v0.4.3", "assets": []}),
    )

    result = {}

    def cb(*args):
        result["value"] = args

    auto_updater.check_for_update(cb)
    args = _wait_for(result)
    assert args == (None, None, "up_to_date", None)


def test_check_for_update_finds_exe_asset(monkeypatch):
    monkeypatch.setattr(auto_updater, "APP_VERSION", "0.4.2")
    monkeypatch.setattr(
        auto_updater.requests,
        "get",
        lambda *a, **k: _FakeResponse(
            200,
            {
                "tag_name": "v0.4.3",
                "body": "notes",
                "assets": [
                    {"name": "source.zip", "browser_download_url": "https://x/source.zip"},
                    {
                        "name": "Waraqat.exe",
                        "browser_download_url": "https://x/Waraqat.exe",
                        "digest": "sha256:abc123",
                    },
                ],
            },
        ),
    )

    result = {}

    def cb(*args):
        result["value"] = args

    auto_updater.check_for_update(cb)
    args = _wait_for(result)
    assert args[0] == "v0.4.3"
    assert args[1] == "https://x/Waraqat.exe"
    assert args[2] == "notes"
    assert args[3] == "abc123"


def test_check_for_update_reports_no_asset(monkeypatch):
    monkeypatch.setattr(auto_updater, "APP_VERSION", "0.4.2")
    monkeypatch.setattr(
        auto_updater.requests,
        "get",
        lambda *a, **k: _FakeResponse(
            200, {"tag_name": "v0.4.3", "assets": [{"name": "source.zip"}]}
        ),
    )

    result = {}

    def cb(*args):
        result["value"] = args

    auto_updater.check_for_update(cb)
    args = _wait_for(result)
    assert args == (None, None, "no_asset", None)


def test_check_for_update_reports_rate_limit(monkeypatch):
    monkeypatch.setattr(auto_updater, "APP_VERSION", "0.4.2")
    monkeypatch.setattr(
        auto_updater.requests, "get", lambda *a, **k: _FakeResponse(403, {})
    )

    result = {}

    def cb(*args):
        result["value"] = args

    auto_updater.check_for_update(cb)
    args = _wait_for(result)
    assert args == (None, None, "rate_limit", None)


def test_check_for_update_respects_skipped_version(monkeypatch):
    monkeypatch.setattr(auto_updater, "APP_VERSION", "0.4.2")
    monkeypatch.setattr(
        auto_updater.requests,
        "get",
        lambda *a, **k: _FakeResponse(
            200,
            {
                "tag_name": "v0.4.3",
                "assets": [
                    {"name": "Waraqat.exe", "browser_download_url": "https://x/Waraqat.exe"}
                ],
            },
        ),
    )

    result = {}

    def cb(*args):
        result["value"] = args

    auto_updater.check_for_update(cb, allow_skipped=False, skipped_version="v0.4.3")
    args = _wait_for(result)
    assert args == (None, None, "skipped", None)


def test_validate_downloaded_exe_rejects_bad_sha(tmp_path):
    path = tmp_path / "valid.exe"
    path.write_bytes(b"MZ" + b"\\x00" * auto_updater.MIN_UPDATE_SIZE)

    with pytest.raises(RuntimeError, match="SHA-256"):
        auto_updater._validate_downloaded_exe(str(path), expected_sha256="deadbeef")
