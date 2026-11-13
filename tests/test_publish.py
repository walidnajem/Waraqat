import pytest

import config
import publish


@pytest.mark.parametrize(
    "version, expected",
    [
        ("0.4.3", "0.4.4"),
        ("1.0.0", "1.0.1"),
        ("0.4", "0.4.1"),
        ("bad", "0.3.1"),
    ],
)
def test_bump_patch_version(version, expected):
    assert publish.bump_patch_version(version) == expected


@pytest.mark.parametrize(
    "version, expected",
    [
        ("0.4.3", (0, 4, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("bad", (0,)),
    ],
)
def test_parse_version(version, expected):
    assert publish.parse_version(version) == expected


def test_current_version_matches_config():
    assert publish.get_current_version() == config.APP_VERSION


def test_build_command_is_a_safe_argument_list():
    cmd = publish.build_command()

    assert cmd[0] == publish.sys.executable
    assert cmd[1:3] == ["-m", "PyInstaller"]
    assert "--onefile" in cmd
    assert "--windowed" in cmd
    assert "main.py" == cmd[-1]
    assert all(isinstance(part, str) for part in cmd)
