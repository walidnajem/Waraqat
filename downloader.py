import os
import re
import time
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import DEFAULT_MAX_WORKERS, TIMEOUT
from utils import clean_filename

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*"
}

print_lock = Lock()


def download_gdrive(file_id, filepath, cancel_event=None):
    """
    Downloads a Google Drive file, handling large file confirmation warnings
    and streaming chunks to avoid high RAM consumption.
    """
    session = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}"

    response = session.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        stream=True,
        allow_redirects=True
    )
    response.raise_for_status()

    # Check for large file warning token
    confirm_token = None
    for key, value in session.cookies.items():
        if key.startswith("download_warning"):
            confirm_token = value
            break

    if not confirm_token and "text/html" in response.headers.get("Content-Type", ""):
        match = re.search(r"confirm=([0-9A-Za-z_]+)", response.text)
        if match:
            confirm_token = match.group(1)

    if confirm_token:
        confirm_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
        response = session.get(
            confirm_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=True
        )
        response.raise_for_status()

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if cancel_event and cancel_event.is_set():
                f.close()
                if os.path.exists(filepath):
                    os.remove(filepath)
                raise Exception("Download cancelled by user")
            if chunk:
                f.write(chunk)

    if os.path.getsize(filepath) < 1000:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "<html" in content.lower():
                os.remove(filepath)
                raise Exception("Google Drive returned HTML instead of document (Access denied or file restricted)")


def download_stream_file(url, filepath, cancel_event=None):
    """
    Downloads any document (PDF, Word, etc.) using chunk streaming.
    Checks for HTML error responses.
    """
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        stream=True,
        allow_redirects=True
    )
    response.raise_for_status()

    first_chunk = True
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if cancel_event and cancel_event.is_set():
                f.close()
                if os.path.exists(filepath):
                    os.remove(filepath)
                raise Exception("Download cancelled by user")

            if chunk:
                if first_chunk:
                    first_chunk = False
                    peek = chunk[:250].lower()
                    if b"<!doctype" in peek or b"<html" in peek or b"<head" in peek:
                        f.close()
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        raise Exception("Server returned an HTML webpage instead of a document file.")
                f.write(chunk)

    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise Exception("Downloaded file is empty (0 bytes)")


def download_file(index, total, item, folder, log_callback=None, cancel_event=None):
    """
    Downloads a single file item with automatic retry mechanism (3 attempts)
    and duplicate skipping.
    """
    if cancel_event and cancel_event.is_set():
        return "cancelled"

    raw_type = item.get("type", "PDF").upper()
    ext = raw_type.lower()
    if ext in ["gdrive", "mediafire"]:
        ext = "pdf"

    title = clean_filename(item.get("title", f"Document_{index}"))
    filename = f"{index:02d}_{title}.{ext}"
    filepath = os.path.join(folder, filename)

    # Skip if file already exists and is not empty
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        if log_callback:
            log_callback(f"[SKIP] (Already exists) -> {filename}")
        return "skip"

    if log_callback:
        log_callback(f"[DOWNLOAD] [{index}/{total}] -> {filename}")

    for attempt in range(3):
        if cancel_event and cancel_event.is_set():
            if os.path.exists(filepath):
                os.remove(filepath)
            return "cancelled"

        try:
            start_time = time.time()
            if raw_type == "GDRIVE":
                download_gdrive(item["id"], filepath, cancel_event)
            else:
                download_stream_file(item["url"], filepath, cancel_event)

            elapsed = max(time.time() - start_time, 0.1)
            size_mb = round(os.path.getsize(filepath) / 1024 / 1024, 2)
            speed_mb = round(size_mb / elapsed, 2)

            if log_callback:
                log_callback(f"[OK] {filename} ({size_mb} MB at {speed_mb} MB/s)")
            return "success"

        except Exception as e:
            if "cancelled" in str(e).lower():
                return "cancelled"

            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

            if attempt < 2 and (not cancel_event or not cancel_event.is_set()):
                if log_callback:
                    log_callback(f"[RETRY] ({attempt + 1}/3) -> {filename}")
                time.sleep(2)
            else:
                if log_callback:
                    log_callback(f"[FAILED] {filename} ({str(e)})")

    return "failed"


def download_parallel(files, folder, progress_callback=None, log_callback=None, cancel_event=None, max_workers=DEFAULT_MAX_WORKERS):
    """
    Manages parallel downloads using ThreadPoolExecutor.
    Supports real-time cancellation and configurable thread count.
    """
    total = len(files)
    success = 0
    failed = 0
    skipped = 0
    cancelled = 0
    completed = 0

    if log_callback:
        log_callback(f"[*] Starting download ({max_workers} threads)...")

    progress = tqdm(
        total=total,
        desc="Downloading",
        unit="file",
        dynamic_ncols=True,
        colour="green"
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                download_file,
                index,
                total,
                item,
                folder,
                log_callback,
                cancel_event
            ): index
            for index, item in enumerate(files, start=1)
        }

        for future in as_completed(futures):
            if cancel_event and cancel_event.is_set():
                cancelled += 1
                completed += 1
                continue

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

            progress.update(1)

            if progress_callback:
                try:
                    progress_callback(completed, total)
                except Exception:
                    pass

    progress.close()

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
