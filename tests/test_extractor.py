import pytest

import extractor


@pytest.mark.parametrize(
    "header, expected",
    [
        ("", ""),
        ('attachment; filename="book.pdf"', "book.pdf"),
        ("attachment; filename=book%20one.pdf", "book one.pdf"),
        (
            "attachment; filename*=UTF-8''%D9%83%D8%AA%D8%A7%D8%A8.pdf",
            "كتاب.pdf",
        ),
    ],
)
def test_extract_filename_from_content_disposition(header, expected):
    assert extractor._extract_filename_from_cd(header) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.com/files/book.pdf", "book"),
        ("https://example.com/download?name=My%20Book", "My Book"),
        ("https://example.com/download?file=lesson.docx", "lesson.docx"),
        ("https://example.com/downloads/", ""),
    ],
)
def test_extract_name_from_url(url, expected):
    assert extractor._extract_name_from_url(url) == expected


def test_clean_title_strips_generic_labels():
    assert extractor._clean_title("تحميل كتاب الفيزياء PDF") == "الفيزياء"
    assert extractor._clean_title("Download", fallback_name="Algebra Book.pdf") == "Algebra"


def test_extract_files_direct_pdf_without_network():
    files = extractor.extract_files("https://example.com/files/lesson.pdf")
    assert len(files) == 1
    assert files[0]["type"] == "PDF"
    assert files[0]["url"] == "https://example.com/files/lesson.pdf"
    assert files[0]["title"] == "lesson"


def test_extract_files_gdrive_without_network():
    files = extractor.extract_files("https://drive.google.com/file/d/ABC123/view")
    assert len(files) == 1
    assert files[0]["type"] == "GDRIVE"
    assert files[0]["id"] == "ABC123"


def test_extract_files_rejects_unsupported_mega_links():
    with pytest.raises(ValueError, match="MEGA"):
        extractor.extract_files("https://mega.nz/file/abc123")


def test_extract_files_from_html_page(local_server):
    base, _ = local_server
    files = extractor.extract_files(base + "/html")
    types = {item["type"] for item in files}
    urls = {item.get("url") for item in files}

    assert "PDF" in types
    assert "GDRIVE" in types
    assert base + "/file" in urls
    gdrive = next(item for item in files if item["type"] == "GDRIVE")
    assert gdrive["id"] == "ABC123"


def test_extract_files_batch_deduplicates(local_server):
    base, _ = local_server
    files = extractor.extract_files_batch([base + "/html", base + "/html"])
    keys = [item.get("id") or item.get("url") for item in files]
    assert len(keys) == len(set(keys))
