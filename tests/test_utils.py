import os

import pytest

from utils import clean_filename, fit_filename, get_site_name


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", "unnamed_document"),
        (None, "unnamed_document"),
        ("a/b:c", "a_b_c"),
        ('bad<>:"/\\|?*name', "bad_________name"),
        ("  spaced   name  ", "spaced name"),
        ("book.pdf", "book"),
        ("book.PDF", "book"),
        ("name. ", "name"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("COM1.txt", "_COM1.txt"),
        ("LPT9", "_LPT9"),
        ("normal-name", "normal-name"),
    ],
)
def test_clean_filename(raw, expected):
    assert clean_filename(raw) == expected


def test_clean_filename_caps_length():
    result = clean_filename("x" * 500)
    assert len(result) == 120


def test_fit_filename_keeps_short_names():
    assert fit_filename("C:\\Docs", "07_My Document.pdf") == "07_My Document.pdf"


def test_fit_filename_shortens_long_paths(tmp_path):
    folder = str(tmp_path)
    filename = "a" * 300 + ".pdf"
    max_path = len(os.path.abspath(folder)) + 40
    fitted = fit_filename(folder, filename, max_path=max_path)

    assert fitted.endswith(".pdf")
    assert "..." in fitted
    assert len(os.path.abspath(folder)) + 1 + len(fitted) <= max_path


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.example.com/books/file.pdf", "example.com"),
        ("https://sub.example.com/a", "sub.example.com"),
        ("http://example.com:8080/a", "example.com:8080"),
        ("", "Universal Scanner"),
        ("not a url", "Universal Scanner"),
    ],
)
def test_get_site_name(url, expected):
    assert get_site_name(url) == expected
