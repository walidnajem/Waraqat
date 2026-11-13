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
