"""
auto_updater.py — Waraqat Auto-Update System
Checks GitHub Releases for new versions and self-updates the exe.
"""
import os
import sys
import threading
import subprocess
import tempfile
import requests

from config import APP_VERSION, GITHUB_OWNER, GITHUB_REPO, UPDATE_CHECK_URL


def parse_version(v: str) -> tuple:
    """Converts '3.1' or 'v3.1' to (3, 1) for comparison."""
    v = v.lstrip("v").strip()
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def check_for_update(callback):
    """
    Runs in a background thread.
    Calls callback(latest_version, download_url, release_notes)
    - latest_version: str (e.g. 'v0.3.1')
    - download_url: str (url to .exe)
    - release_notes: str (release body / changelog)
    If up to date: calls callback(None, None, "up_to_date")
    If failed / no connection: calls callback(None, None, "error")
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
                callback(None, None, "error")
                return

            data = resp.json()
            latest_tag = data.get("tag_name", "")
            release_notes = data.get("body", "تحديثات وتحسينات جديدة للأداء.")
            latest_ver = parse_version(latest_tag)
            current_ver = parse_version(APP_VERSION)

            if latest_ver <= current_ver:
                callback(None, None, "up_to_date")
                return

            # Find the .exe asset
            assets = data.get("assets", [])
            exe_url = None
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".exe"):
                    exe_url = asset.get("browser_download_url")
                    break

            # Fallback: zipball
            if not exe_url:
                exe_url = data.get("zipball_url")

            callback(latest_tag, exe_url, release_notes)

        except Exception as e:
            callback(None, None, f"error: {str(e)}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def download_and_install(download_url, progress_callback=None, done_callback=None):
    """
    Downloads the new exe and installs it via a launcher bat script.
    progress_callback(percent: int) — called with 0-100
    done_callback(success: bool, message: str)
    """
    def _run():
        try:
            # Determine current exe path
            if getattr(sys, "frozen", False):
                current_exe = sys.executable
            else:
                current_exe = os.path.abspath(__file__)

            exe_dir = os.path.dirname(current_exe)
            new_exe_path = os.path.join(exe_dir, "Waraqat_update.exe")
            bat_path = os.path.join(tempfile.gettempdir(), "waraqat_update.bat")

            # Download new exe
            with requests.get(download_url, stream=True, timeout=60,
                              headers={"User-Agent": "Waraqat-App"}) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(new_exe_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total and progress_callback:
                                progress_callback(int(downloaded * 100 / total))

            if progress_callback:
                progress_callback(100)

            # Create bat script that replaces exe after app exits
            bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)

            # Launch bat and exit app
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True
            )

            if done_callback:
                done_callback(True, "")

        except Exception as e:
            if done_callback:
                done_callback(False, str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()
