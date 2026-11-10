"""
Windows Toast Notifications for Waraqat desktop app.

Provides notification functions for download completion, errors,
and update availability using plyer with winotify fallback.
"""

import os
import sys

# Resolve the base directory for assets
_BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_ICON = os.path.join(_BASE_DIR, "assets", "waraqat_icon.ico")


def _get_icon(icon_path=None):
    """Return icon path if it exists, else None."""
    path = icon_path or _DEFAULT_ICON
    if path and os.path.isfile(path):
        return path
    return None


def _notify_plyer(title, message, icon_path=None, timeout=10):
    """Show notification via plyer."""
    from plyer import notification
    kwargs = {
        "title": title,
        "message": message,
        "timeout": timeout,
        "app_name": "Waraqat | ورقات",
    }
    icon = _get_icon(icon_path)
    if icon:
        kwargs["app_icon"] = icon
    notification.notify(**kwargs)


def _notify_winotify(title, message, icon_path=None):
    """Show notification via winotify (Windows-only fallback)."""
    from winotify import Notification
    toast = Notification(
        app_id="Waraqat | ورقات",
        title=title,
        msg=message,
        duration="long",
    )
    icon = _get_icon(icon_path)
    if icon:
        toast.set_audio(None)
        toast.icon = icon
    toast.show()


def _send_notification(title, message, icon_path=None, timeout=10):
    """Try plyer first, then winotify. Silently pass if both fail."""
    try:
        _notify_plyer(title, message, icon_path, timeout)
        return
    except Exception:
        pass
    try:
        _notify_winotify(title, message, icon_path)
        return
    except Exception:
        pass


def notify_download_complete(title, message, icon_path=None):
    """
    Show a toast notification when downloads finish.

    Args:
        title: Notification title (e.g. "ورقات | Waraqat").
        message: Summary message (e.g. "Downloaded 15 files successfully to ...").
        icon_path: Optional path to .ico file. Defaults to assets/waraqat_icon.ico.
    """
    _send_notification(title, message, icon_path, timeout=10)


def notify_error(title, message, icon_path=None):
    """
    Show a toast notification for download errors.

    Args:
        title: Notification title.
        message: Error description.
        icon_path: Optional path to .ico file.
    """
    _send_notification(title, f"❌ {message}", icon_path, timeout=10)


def notify_update_available(version, icon_path=None):
    """
    Show a toast notification when a new version is available.

    Args:
        version: The new version string (e.g. "0.4.0").
        icon_path: Optional path to .ico file.
    """
    _send_notification(
        "ورقات | Waraqat — Update Available",
        f"إصدار جديد متوفر: {version}\nA new version is available: {version}",
        icon_path,
        timeout=10,
    )
