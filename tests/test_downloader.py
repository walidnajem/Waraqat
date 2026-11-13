import os

import pytest

import downloader


def test_build_timeout_caps_read_timeout():
    assert downloader._build_timeout(60) == (10, 20)
    assert downloader._build_timeout(120) == (10, 20)
    assert downloader._build_timeout(5) == (5, 5)
    assert downloader._build_timeout("bad") == (10, 20)
    assert downloader._build_timeout(None) == (10, 20)


def test_parse_unsatisfied_total():
    assert downloader._parse_unsatisfied_total("bytes */12000") == 12000
    assert downloader._parse_unsatisfied_total("bytes */0") == 0
    assert downloader._parse_unsatisfied_total("") is None
    assert downloader._parse_unsatisfied_total("garbage") is None


def test_download_headers_are_range_and_encoding_safe():
    headers = downloader._download_headers(5000)
    assert headers["Range"] == "bytes=5000-"
    assert headers["Accept-Encoding"] == "identity"
    assert "Range" not in downloader._download_headers(0)


class _Response:
    def __init__(self, status, headers):
        self.status_code = status
        self.headers = headers


def test_range_matches():
    assert downloader._range_matches(_Response(200, {}), 0) is True
    assert downloader._range_matches(
        _Response(206, {"Content-Range": "bytes 5000-11999/12000"}), 5000
    ) is True
    assert downloader._range_matches(
        _Response(206, {"Content-Range": "bytes 0-11999/12000"}), 5000
    ) is False
    assert downloader._range_matches(_Response(200, {}), 5000) is False


def test_looks_like_html():
    assert downloader._looks_like_html(b"<!doctype html><html>")
    assert downloader._looks_like_html(b"  <html><body>")
    assert not downloader._looks_like_html(b"%PDF-1.4 binary")


def test_existing_part_size_handles_empty_and_html(tmp_path):
    empty = tmp_path / "empty.part"
    empty.write_bytes(b"")
    assert downloader._existing_part_size(str(empty)) == 0
    assert not empty.exists()

    html = tmp_path / "error.part"
    html.write_bytes(b"<html><body>quota exceeded</body></html>")
    assert downloader._existing_part_size(str(html)) == 0
    assert not html.exists()

    good = tmp_path / "good.part"
    good.write_bytes(b"%PDF-1.4 partial")
    assert downloader._existing_part_size(str(good)) == len(b"%PDF-1.4 partial")


def test_stream_download_resumes_with_range(local_server, tmp_path, body):
    base, server = local_server
    part = tmp_path / "book.pdf.part"
    part.write_bytes(body[:5000])

    downloader.download_stream_file(base + "/file", str(part))

    assert part.read_bytes() == body
    assert ("/file", "bytes=5000-") in server.seen_ranges


def test_stream_download_restarts_when_range_is_ignored(local_server, tmp_path, body):
    base, _ = local_server
    part = tmp_path / "ignored.pdf.part"
    part.write_bytes(body[:5000])

    downloader.download_stream_file(base + "/norange", str(part))

    assert part.read_bytes() == body


def test_stream_download_accepts_416_when_part_is_complete(local_server, tmp_path, body):
    base, _ = local_server
    part = tmp_path / "complete.pdf.part"
    part.write_bytes(body)

    downloader.download_stream_file(base + "/complete", str(part))

    assert part.read_bytes() == body


def test_stream_download_rejects_html_and_empty(local_server, tmp_path):
    base, _ = local_server

    with pytest.raises(Exception, match="HTML webpage"):
        downloader.download_stream_file(base + "/html_file", str(tmp_path / "bad.pdf"))

    with pytest.raises(Exception, match="empty"):
        downloader.download_stream_file(base + "/empty", str(tmp_path / "empty.pdf"))


def test_download_file_uses_orig_index_and_resumes(local_server, tmp_path, body):
    base, _ = local_server
    part = tmp_path / "07_My Doc.pdf.part"
    part.write_bytes(body[:5000])

    item = {"type": "PDF", "url": base + "/file", "title": "My Doc", "orig_index": 7}
    result = downloader.download_file(1, 1, item, str(tmp_path))

    final = tmp_path / "07_My Doc.pdf"
    assert result == "success"
    assert final.read_bytes() == body
    assert not part.exists()


def test_download_file_skips_existing_file(local_server, tmp_path, body):
    base, _ = local_server
    final = tmp_path / "01_Existing.pdf"
    final.write_bytes(body)

    item = {"type": "PDF", "url": base + "/file", "title": "Existing", "orig_index": 1}
    assert downloader.download_file(1, 1, item, str(tmp_path)) == "skip"
    assert final.read_bytes() == body


def test_download_file_honours_cancel_event(tmp_path):
    import threading

    cancel_event = threading.Event()
    cancel_event.set()
    item = {"type": "PDF", "url": "https://example.com/file.pdf", "title": "Cancelled", "orig_index": 1}

    assert downloader.download_file(1, 1, item, str(tmp_path), cancel_event=cancel_event) == "cancelled"
    assert not (tmp_path / "01_Cancelled.pdf").exists()


def test_download_parallel_keeps_original_numbers(local_server, tmp_path, body):
    base, _ = local_server
    files = [
        {"type": "PDF", "url": base + "/file", "title": "Alpha", "orig_index": 3},
        {"type": "PDF", "url": base + "/file", "title": "Beta", "orig_index": 9},
    ]

    result = downloader.download_parallel(files, str(tmp_path), max_workers=2, timeout=30)

    assert result["success"] == 2
    assert result["failed"] == 0
    assert (tmp_path / "03_Alpha.pdf").read_bytes() == body
    assert (tmp_path / "09_Beta.pdf").read_bytes() == body
