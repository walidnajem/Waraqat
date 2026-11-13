"""
auto_updater.py — Waraqat Auto-Update System
Checks GitHub Releases for new versions and self-updates the exe.
"""
import os
import sys
import hashlib
import shutil
import threading
import subprocess
import tempfile
import requests

from config import APP_VERSION, UPDATE_CHECK_URL

# Minimum plausible size for the packaged Waraqat exe (guards against HTML/error pages).
MIN_UPDATE_SIZE = 1024 * 100
# Safety cap so a mislabelled asset cannot fill the disk.
MAX_UPDATE_SIZE = 500 * 1024 * 1024

# Windows batch script used to swap the running exe.
# Paths are passed as arguments so the script itself stays ASCII-only
# (safe for exe directories containing Arabic/Unicode characters).
UPDATE_BAT = r"""@echo off
setlocal
set "NEW=%~1"
set "CUR=%~2"
set "TRIES=0"

:waitloop
timeout /t 1 /nobreak >nul
move /y "%NEW%" "%CUR%" >nul 2>&1
if not exist "%NEW%" goto success
set /a TRIES+=1
if %TRIES% GEQ 60 goto failed
goto waitloop

:success
start "" "%CUR%"
del "%~f0"
exit /b 0

:failed
if exist "%NEW%" del /f /q "%NEW%" >nul 2>&1
start "" "%CUR%"
del "%~f0"
exit /b 1
"""


def parse_version(v: str) -> tuple:
    """Converts '3.1' or 'v3.1' to (3, 1) for comparison."""
    v = v.lstrip("v").strip()
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _status_for_http(status: int) -> str:
    if status == 403 or status == 429:
        return "rate_limit"
    if status == 404:
        return "not_found"
    return "error"


def check_for_update(callback, allow_skipped: bool = False, skipped_version: str = None):
    """
    Runs in a background thread.
    Calls callback(latest_version, download_url, release_notes, sha256)
    - latest_version: str (e.g. 'v0.3.1') or None
    - download_url: str (url to .exe) or None
    - release_notes: str (release body / changelog) or a status token
    - sha256: hex digest of the asset (or None)

    Status tokens passed as release_notes when there is no update:
      "up_to_date", "skipped", "no_asset", "rate_limit", "not_found",
      "error" or "error: <detail>".
    If up to date: calls callback(None, None, "up_to_date", None)
    If failed / no connection: calls callback(None, None, "error", None)
    If the release has no .exe asset: calls callback(None, None, "no_asset", None)
    """

    def _run():
        try:
            resp = requests.get(
                UPDATE_CHECK_URL,
                timeout=8,
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": "Waraqat-App"}
            )
            if resp.status_code != 200:
                callback(None, None, _status_for_http(resp.status_code), None)
                return

            data = resp.json()
            latest_tag = data.get("tag_name", "")
            release_notes = data.get("body", "تحديثات وتحسينات جديدة للأداء.")
            latest_ver = parse_version(latest_tag)
            current_ver = parse_version(APP_VERSION)

            if latest_ver <= current_ver:
                callback(None, None, "up_to_date", None)
                return

            if (not allow_skipped) and skipped_version and latest_tag == skipped_version:
                callback(None, None, "skipped", None)
                return

            # Find the .exe asset. Never fall back to a zipball: it would be
            # saved with an .exe name and corrupt the installation.
            assets = data.get("assets", [])
            exe_url = None
            exe_sha = None
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".exe"):
                    exe_url = asset.get("browser_download_url")
                    digest = asset.get("digest") or ""
                    if digest.lower().startswith("sha256:"):
                        exe_sha = digest.split(":", 1)[1].strip().lower()
                    break

            if not exe_url:
                callback(None, None, "no_asset", None)
                return

            callback(latest_tag, exe_url, release_notes, exe_sha)

        except Exception as e:
            callback(None, None, f"error: {str(e)}", None)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _validate_downloaded_exe(path, expected_sha256=None):
    """Ensures the downloaded payload is a plausible Windows executable."""
    if not os.path.exists(path):
        raise RuntimeError("Update file was not created.")

    size = os.path.getsize(path)
    if size < MIN_UPDATE_SIZE:
        raise RuntimeError(
            f"Downloaded update is too small ({size} bytes). "
            "The release asset may be invalid or an error page."
        )
    if size > MAX_UPDATE_SIZE:
        raise RuntimeError(
            f"Downloaded update is too large ({size} bytes). "
            "The release asset may be invalid."
        )

    with open(path, "rb") as f:
        if f.read(2) != b"MZ":
            raise RuntimeError(
                "Downloaded update is not a valid Windows executable. "
                "The release asset may be a ZIP archive or an HTML page."
            )

    if expected_sha256:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if h.hexdigest().lower() != expected_sha256.lower():
            raise RuntimeError(
                "SHA-256 verification failed for the downloaded update. "
                "The file may be corrupted or tampered with."
            )


def _download_headers(start: int = 0):
    headers = {"User-Agent": "Waraqat-App", "Accept-Encoding": "identity"}
    if start > 0:
        headers["Range"] = f"bytes={start}-"
    return headers


def download_and_install(download_url, progress_callback=None, done_callback=None,
                        expected_sha256=None):
    """
    Downloads the new exe and installs it via a launcher bat script.
    progress_callback(percent: int) — called with 0-100
    done_callback(success: bool, message: str)

    After a successful download the helper script waits for this process to
    exit, replaces the exe (retrying for up to 60 seconds) and relaunches it.
    The caller MUST close the application once done_callback(True) fires.
    """
    if not getattr(sys, "frozen", False):
        if done_callback:
            done_callback(
                False,
                "التحديث الذاتي متاح فقط لنسخة Waraqat.exe المجمّعة. "
                "Auto-update is only available in the packaged Waraqat.exe build."
            )
        return

    def _run():
        new_exe_path = None
        launched = False
        try:
            current_exe = sys.executable
            exe_dir = os.path.dirname(current_exe)
            # Download into %TEMP% so a read-only install folder (Program Files)
            # never blocks the update.
            new_exe_path = os.path.join(tempfile.gettempdir(), "Waraqat_update.exe")
            bat_path = os.path.join(tempfile.gettempdir(), "waraqat_update.bat")

            # Resume a previous partial download when possible.
            start = 0
            if os.path.exists(new_exe_path):
                try:
                    size = os.path.getsize(new_exe_path)
                    if size > 0:
                        with open(new_exe_path, "rb") as f:
                            if not _looks_like_html_bytes(f.read(512)):
                                start = size
                    if start == 0:
                        os.remove(new_exe_path)
                except OSError:
                    try:
                        os.remove(new_exe_path)
                    except OSError:
                        pass
                    start = 0

            # Check free disk space using the asset size (if known).
            # We learn the total from the first response below; pre-check with a
            # generous lower bound is done after headers are received.

            # Download new exe (with resume support).
            with requests.get(download_url, stream=True, timeout=60,
                              headers=_download_headers(start)) as r:
                if start > 0 and r.status_code == 416:
                    # Partial file is already complete.
                    pass
                else:
                    r.raise_for_status()

                    content_type = r.headers.get("Content-Type", "").lower()
                    if "text/html" in content_type:
                        raise RuntimeError(
                            "GitHub returned an HTML page instead of the update file."
                        )

                    if start > 0 and r.status_code == 200:
                        # Server ignored Range; restart from scratch.
                        start = 0
                        try:
                            if os.path.exists(new_exe_path):
                                os.remove(new_exe_path)
                        except OSError:
                            pass

                    if r.status_code not in (200, 206, 416):
                        raise RuntimeError(
                            f"Unexpected HTTP status {r.status_code} while downloading."
                        )

                    total = int(r.headers.get("content-length", 0))
                    if r.status_code == 206:
                        total = start + total
                    if total and total > MAX_UPDATE_SIZE:
                        raise RuntimeError(
                            f"Update is too large ({total} bytes)."
                        )

                    # Disk space check.
                    try:
                        free = shutil.disk_usage(tempfile.gettempdir()).free
                        if total and free < total + (5 * 1024 * 1024):
                            raise RuntimeError(
                                "Not enough free disk space to download the update."
                            )
                    except Exception:
                        pass

                    mode = "ab" if (start > 0 and r.status_code == 206) else "wb"
                    downloaded = start
                    with open(new_exe_path, mode) as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total and progress_callback:
                                    progress_callback(int(downloaded * 100 / total))

            _validate_downloaded_exe(new_exe_path, expected_sha256)

            if progress_callback:
                progress_callback(100)

            # Create bat script that replaces exe after app exits.
            # The paths are passed as command-line arguments (see Popen below).
            with open(bat_path, "w", encoding="ascii", newline="\r\n") as f:
                f.write(UPDATE_BAT)

            # Launch bat and let the caller exit the app.
            subprocess.Popen(
                ["cmd", "/c", bat_path, new_exe_path, current_exe],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True
            )
            launched = True

            if done_callback:
                done_callback(True, "")

        except Exception as e:
            if not launched and new_exe_path and os.path.exists(new_exe_path):
                # Keep partial files for resume on the next attempt.
                pass
            if done_callback:
                done_callback(False, str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _looks_like_html_bytes(data: bytes) -> bool:
    stripped = data.lstrip()
    return stripped.startswith(b"<!doctype html") or stripped.startswith(b"<html")
