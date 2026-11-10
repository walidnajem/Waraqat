import os
import sys
import json

APP_NAME = "Waraqat | ورقات"
APP_SUBTITLE = "المنظومة الذكية لسحب وتنزيل المستندات والكتب"
APP_VERSION = "3.0"

DEFAULT_MAX_WORKERS = 5
TIMEOUT = 60
DEFAULT_DOWNLOAD_FOLDER = "Downloads"

# Determine directory for persistent settings
if getattr(sys, "frozen", False):
    APP_STORAGE_DIR = os.path.dirname(sys.executable)
else:
    APP_STORAGE_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(APP_STORAGE_DIR, "settings.json")


def load_settings():
    """Loads persistent settings or returns defaults."""
    default_dir = os.path.join(os.path.expanduser("~"), DEFAULT_DOWNLOAD_FOLDER)
    defaults = {
        "save_path": default_dir,
        "max_workers": DEFAULT_MAX_WORKERS,
        "include_docs": True
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    """Saves settings to settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
