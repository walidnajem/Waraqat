import os
import re
import time
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import DEFAULT_MAX_WORKERS, TIMEOUT
from utils import clean_filename, fit_filename

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    # Keep byte ranges aligned with the real file bytes (no transparent gzip).
    "Accept-Encoding": "identity",
}

CONNECT_TIMEOUT = 10
MAX_READ_TIMEOUT = 20
CHUNK_SIZE = 65536

print_lock = Lock()


def _build_timeout(timeout):
    """
    Builds a (connect, read) timeout tuple. The read timeout is capped so a
    stalled server cannot block cancellation for the full user timeout.
    """
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = TIMEOUT
    timeout = max(5, timeout)
    return (min(CONNECT_TIMEOUT, timeout), min(timeout, MAX_READ_TIMEOUT))


def _looks_like_html(chunk):
    """Heuristic check for an HTML/error page served instead of a document."""
    peek = chunk[:512].lower()
    return b"<!doctype" in peek or b"<html" in peek or b"<head" in peek


def _remove_file(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass


def _existing_part_size(filepath):
    """Returns the size of a resumable partial file, or 0 if it is unusable."""
    if not os.path.exists(filepath):
        return 0
    try:
        size = os.path.getsize(filepath)
        if size <= 0:
            _remove_file(filepath)
            return 0
        with open(filepath, "rb") as f:
            if _looks_like_html(f.read(512)):
                _remove_file(filepath)
                return 0
        return size
    except OSError:
        _remove_file(filepath)
        return 0


def _download_headers(resume_from=0):
    headers = dict(HEADERS)
    if resume_from > 0:
        headers["Range"] = f"bytes={resume_from}-"
    return headers


def _parse_unsatisfied_total(content_range):
    """Parses 'bytes */12345' from a 416 response."""
    match = re.match(r"bytes\s+\*/(\d+)", content_range or "")
    return int(match.group(1)) if match else None


def _range_matches(response, resume_from):
    """Checks that a 206 response really starts at the requested byte."""
    if resume_from <= 0:
        return True
    if response.status_code != 206:
        return False
    match = re.match(r"bytes\s+(\d+)-", response.headers.get("Content-Range", "") or "")
    return bool(match) and int(match.group(1)) == resume_from


def download_gdrive(file_id, filepath, cancel_event=None, item_progress_callback=None,
                    timeout=TIMEOUT, resume=True):
    """
    Downloads a Google Drive file, handling large file confirmation warnings
    and streaming chunks to avoid high RAM consumption. Supports resuming.
    """
    session = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    timeout = _build_timeout(timeout)

    resume_from = _existing_part_size(filepath) if resume else 0
    if not resume:
        _remove_file(filepath)

    def _request(target_url, use_range):
        return session.get(
            target_url,
            headers=_download_headers(resume_from if use_range else 0),
            timeout=timeout,
            stream=True,
            allow_redirects=True
        )

    response = _request(url, True)

    # A 416 on the initial request may mean the partial file is already complete.
    if resume_from > 0 and response.status_code == 416:
        total = _parse_unsatisfied_total(response.headers.get("Content-Range", ""))
        try:
            response.close()
        except Exception:
            pass
        if total == resume_from:
            return
        _remove_file(filepath)
        resume_from = 0
        response = _request(url, False)

    response.raise_for_status()

    # Check for large file warning token
    confirm_token = None
    for key, value in session.cookies.items():
        if key.startswith("download_warning"):
            confirm_token = value
            break

    content_type = response.headers.get("Content-Type", "").lower()
    if not confirm_token and "text/html" in content_type:
        match = re.search(r"confirm=([0-9A-Za-z_]+)", response.text)
        if match:
            confirm_token = match.group(1)

    target_url = url
    if confirm_token:
        try:
            response.close()
        except Exception:
            pass
        target_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
        response = _request(target_url, True)

    # If the server ignored our Range header (or the partial file is already
    # complete), restart cleanly or finish without re-downloading.
    if resume_from > 0:
        if response.status_code == 416:
            total = _parse_unsatisfied_total(response.headers.get("Content-Range", ""))
            try:
                response.close()
            except Exception:
                pass
            if total == resume_from:
                return
            _remove_file(filepath)
            resume_from = 0
            response = _request(target_url, False)
        elif not _range_matches(response, resume_from):
            try:
                response.close()
            except Exception:
                pass
            resume_from = 0
            response = _request(target_url, False)

    response.raise_for_status()

    # A Drive "access denied / quota exceeded" page must never be saved as a document.
    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        try:
            response.close()
        except Exception:
            pass
        raise Exception(
            "Google Drive returned an HTML page instead of the document "
            "(file restricted, removed, or quota exceeded)"
        )

    total_bytes = int(response.headers.get("content-length", 0)) + resume_from
    downloaded_bytes = resume_from
    first_chunk = resume_from == 0
    mode = "ab" if resume_from > 0 else "wb"

    with open(filepath, mode) as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if cancel_event and cancel_event.is_set():
                f.close()
                if downloaded_bytes == 0:
                    _remove_file(filepath)
                raise Exception("Download cancelled by user")
            if chunk:
                if first_chunk:
                    first_chunk = False
                    if _looks_like_html(chunk):
                        f.close()
                        _remove_file(filepath)
                        raise Exception(
                            "Google Drive returned an HTML page instead of the document "
                            "(file restricted, removed, or quota exceeded)"
                        )
                f.write(chunk)
                downloaded_bytes += len(chunk)
                if item_progress_callback and total_bytes > 0:
                    pct = min(100.0, (downloaded_bytes / total_bytes) * 100.0)
                    item_progress_callback(pct, downloaded_bytes, total_bytes)

    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        _remove_file(filepath)
        raise Exception("Downloaded file is empty (0 bytes)")


def download_stream_file(url, filepath, cancel_event=None, item_progress_callback=None,
                         timeout=TIMEOUT, resume=True):
    """Downloads any document (PDF, Word, etc.) using chunk streaming."""
    timeout = _build_timeout(timeout)
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    resume_from = _existing_part_size(filepath) if resume else 0
    if not resume:
        _remove_file(filepath)

    response = requests.get(
        url,
        headers=_download_headers(resume_from),
        timeout=timeout,
        stream=True,
        allow_redirects=True
    )

    if resume_from > 0:
        if response.status_code == 416:
            total = _parse_unsatisfied_total(response.headers.get("Content-Range", ""))
            try:
                response.close()
            except Exception:
                pass
            if total == resume_from:
                return
            _remove_file(filepath)
            resume_from = 0
            response = requests.get(
                url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True
            )
        elif not _range_matches(response, resume_from):
            try:
                response.close()
            except Exception:
                pass
            resume_from = 0
            response = requests.get(
                url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True
            )

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        try:
            response.close()
        except Exception:
            pass
        raise Exception("Server returned an HTML webpage instead of a document file.")

    total_bytes = int(response.headers.get("content-length", 0)) + resume_from
    downloaded_bytes = resume_from
    first_chunk = resume_from == 0
    mode = "ab" if resume_from > 0 else "wb"

    with open(filepath, mode) as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if cancel_event and cancel_event.is_set():
                f.close()
                if downloaded_bytes == 0:
                    _remove_file(filepath)
                raise Exception("Download cancelled by user")

            if chunk:
                if first_chunk:
                    first_chunk = False
                    if _looks_like_html(chunk):
                        f.close()
                        _remove_file(filepath)
                        raise Exception("Server returned an HTML webpage instead of a document file.")
                f.write(chunk)
                downloaded_bytes += len(chunk)
                if item_progress_callback and total_bytes > 0:
                    pct = min(100.0, (downloaded_bytes / total_bytes) * 100.0)
                    item_progress_callback(pct, downloaded_bytes, total_bytes)

    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        _remove_file(filepath)
        raise Exception("Downloaded file is empty (0 bytes)")


def download_file(index, total, item, folder, log_callback=None, cancel_event=None,
                  item_callback=None, timeout=TIMEOUT):
    """
    Downloads a single file item with automatic retry mechanism (3 attempts),
    resumable .part files, and duplicate skipping.
    """
    try:
        file_idx = int(item.get("orig_index", index))
    except (TypeError, ValueError):
        file_idx = index
    if cancel_event and cancel_event.is_set():
        if item_callback:
            item_callback(file_idx, "cancelled", 0.0)
        return "cancelled"

    raw_type = item.get("type", "PDF").upper()
    ext = raw_type.lower()
    if ext in ["gdrive", "mediafire"]:
        ext = "pdf"

    title = clean_filename(item.get("title", f"Document_{index}"))
    # Keep the number shown in the checklist, even when only a subset is
    # selected/filtered. Using the batch position here would renumber files
    # and could skip or duplicate existing downloads.
    filename = fit_filename(folder, f"{file_idx:02d}_{title}.{ext}")
    filepath = os.path.join(folder, filename)
    part_path = filepath + ".part"

    # Skip if file already exists and is not empty
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        _remove_file(part_path)
        if log_callback:
            log_callback(f"[SKIP] (Already exists) -> {filename}")
        if item_callback:
            item_callback(file_idx, "skip", 100.0)
        return "skip"

    if log_callback:
        log_callback(f"[DOWNLOAD] [{index}/{total}] -> {filename}")
    if item_callback:
        item_callback(file_idx, "downloading", 0.0)

    def _chunk_cb(pct, downloaded, total_b):
        if item_callback:
            item_callback(file_idx, "progress", pct)

    for attempt in range(3):
        if cancel_event and cancel_event.is_set():
            if item_callback:
                item_callback(file_idx, "cancelled", 0.0)
            return "cancelled"

        try:
            start_time = time.time()
            if raw_type == "GDRIVE":
                download_gdrive(
                    item["id"], part_path, cancel_event,
                    item_progress_callback=_chunk_cb, timeout=timeout
                )
            else:
                download_stream_file(
                    item["url"], part_path, cancel_event,
                    item_progress_callback=_chunk_cb, timeout=timeout
                )

            os.replace(part_path, filepath)

            elapsed = max(time.time() - start_time, 0.1)
            size_mb = round(os.path.getsize(filepath) / 1024 / 1024, 2)
            speed_mb = round(size_mb / elapsed, 2)

            if log_callback:
                log_callback(f"[OK] {filename} ({size_mb} MB at {speed_mb} MB/s)")
            if item_callback:
                item_callback(file_idx, "success", 100.0)
            return "success"

        except Exception as e:
            if "cancelled" in str(e).lower():
                if item_callback:
                    item_callback(file_idx, "cancelled", 0.0)
                return "cancelled"

            # Keep non-empty .part files so the next attempt can resume.
            if os.path.exists(part_path) and os.path.getsize(part_path) == 0:
                _remove_file(part_path)

            if attempt < 2 and (not cancel_event or not cancel_event.is_set()):
                if log_callback:
                    log_callback(f"[RETRY] ({attempt + 1}/3) -> {filename}")
                if item_callback:
                    item_callback(file_idx, "retry", 0.0)
                time.sleep(2)
            else:
                if log_callback:
                    log_callback(f"[FAILED] {filename} ({str(e)})")
                    if os.path.exists(part_path):
                        log_callback(f"[PART] Partial download kept for resume: {filename}.part")
                if item_callback:
                    item_callback(file_idx, "failed", 0.0)

    return "failed"


def download_parallel(files, folder, progress_callback=None, log_callback=None,
                      cancel_event=None, max_workers=DEFAULT_MAX_WORKERS,
                      item_callback=None, timeout=TIMEOUT):
    """
    Manages parallel downloads using ThreadPoolExecutor.
    Supports real-time per-file progress callback, cancellation, resumable
    partial files, and configurable thread count / timeout.
    """
    total = len(files)
    success = 0
    failed = 0
    skipped = 0
    cancelled = 0
    completed = 0

    if log_callback:
        log_callback(f"[*] Starting download ({max_workers} threads)...")

    # Don't use tqdm if stdout/stderr is None (GUI windowed mode)
    import sys
    use_tqdm = sys.stderr is not None and sys.stdout is not None
    progress = None
    if use_tqdm:
        try:
            progress = tqdm(
                total=total,
                desc="Downloading",
                unit="file",
                dynamic_ncols=True,
                colour="green"
            )
        except Exception:
            progress = None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                download_file,
                index,
                total,
                item,
                folder,
                log_callback,
                cancel_event,
                item_callback,
                timeout
            ): index
            for index, item in enumerate(files, start=1)
        }

        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                result = "failed"

            completed += 1

            if result == "success":
                success += 1
            elif result == "skip":
                skipped += 1
            elif result == "cancelled":
                cancelled += 1
            else:
                failed += 1

            if progress:
                try:
                    progress.update(1)
                except Exception:
                    pass

            if progress_callback:
                try:
                    progress_callback(completed, total)
                except Exception:
                    pass

    if progress:
        try:
            progress.close()
        except Exception:
            pass

    result = {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "cancelled": cancelled
    }

    if log_callback:
        log_callback("")
        log_callback("==================== SUMMARY ====================")
        log_callback(f"Total files  : {total}")
        log_callback(f"Successful   : {success}")
        log_callback(f"Skipped      : {skipped}")
        log_callback(f"Failed       : {failed}")
        if cancelled > 0:
            log_callback(f"Cancelled    : {cancelled}")
        log_callback(f"Folder       : {folder}")
        log_callback("=================================================")

    return result
