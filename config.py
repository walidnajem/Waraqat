import os
import sys
import json

APP_NAME = "Waraqat | ورقات"
APP_SUBTITLE = "المنظومة الذكية لسحب وتنزيل المستندات والكتب"
APP_VERSION = "0.4.7"

DEFAULT_MAX_WORKERS = 5
TIMEOUT = 60
DEFAULT_DOWNLOAD_FOLDER = "Downloads"

# Directory of the source file / packaged exe (used only to migrate old settings)
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LEGACY_SETTINGS_FILE = os.path.join(_BASE_DIR, "settings.json")

# Persistent settings live in %APPDATA%\Waraqat so the app keeps working
# when installed in a read-only folder such as Program Files.
_APPDATA = os.environ.get("APPDATA")
if _APPDATA:
    APP_STORAGE_DIR = os.path.join(_APPDATA, "Waraqat")
else:
    APP_STORAGE_DIR = os.path.join(os.path.expanduser("~"), ".waraqat")

SETTINGS_FILE = os.path.join(APP_STORAGE_DIR, "settings.json")
QUEUE_FILE = os.path.join(APP_STORAGE_DIR, "queue.json")


def load_settings():
    """Loads persistent settings or returns defaults, migrating legacy files."""
    default_dir = os.path.join(os.path.expanduser("~"), DEFAULT_DOWNLOAD_FOLDER)
    defaults = {
        "save_path": default_dir,
        "max_workers": DEFAULT_MAX_WORKERS,
        "theme": "Dark",
        "open_folder_on_finish": True,
        "auto_check_updates": True,
        "timeout": TIMEOUT,
        "notifications_enabled": True,
        "proxy": "",
        "restore_queue_on_start": True
    }

    source = None
    if os.path.exists(SETTINGS_FILE):
        source = SETTINGS_FILE
    elif os.path.exists(LEGACY_SETTINGS_FILE):
        source = LEGACY_SETTINGS_FILE

    if source:
        try:
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                defaults.update(data)
            # Move old settings from the exe/project folder to %APPDATA%.
            if source == LEGACY_SETTINGS_FILE:
                save_settings(defaults)
        except Exception:
            pass

    return defaults


def save_settings(settings):
    """Saves settings atomically to settings.json."""
    try:
        os.makedirs(APP_STORAGE_DIR, exist_ok=True)
        temp_file = SETTINGS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        os.replace(temp_file, SETTINGS_FILE)
    except Exception:
        pass

# ---------- GitHub Auto‑Update Settings ----------
GITHUB_OWNER = "walidnajem"
GITHUB_REPO  = "Waraqat"
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
