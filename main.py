import os
import sys
import traceback
from datetime import datetime


def _get_writable_log_path():
    """Returns a writable path for the crash log, trying safe locations in order."""
    filename = "waraqat_error.log"
    candidates = []

    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), filename))

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(os.path.join(local_appdata, "Waraqat", "logs", filename))

    import tempfile
    candidates.append(os.path.join(tempfile.gettempdir(), filename))

    for path in candidates:
        try:
            log_dir = os.path.dirname(path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(path, "a", encoding="utf-8"):
                pass
            return path
        except Exception:
            continue

    return None


def _write_crash_log(details):
    """Persists the traceback to disk and returns the log path (or None)."""
    path = _get_writable_log_path()
    if not path:
        return None

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"{datetime.now().isoformat(timespec='seconds')}\n")
            f.write(details)
            f.write("=" * 60 + "\n")
        return path
    except Exception:
        return None


def _show_fatal_error(message):
    """Shows a native Windows message box without depending on Tkinter."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "Waraqat | ورقات", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from gui import App
        app = App()
        app.mainloop()
    except Exception:
        details = traceback.format_exc()
        log_path = _write_crash_log(details)

        print("\n" + "=" * 50)
        print("Error starting Waraqat | ورقات:")
        print(details)
        print("=" * 50)
        if log_path:
            print(f"Crash log saved to: {log_path}")

        if getattr(sys, "frozen", False):
            message = "تعذر تشغيل ورقات بسبب خطأ غير متوقع.\n"
            message += "Waraqat could not start due to an unexpected error.\n\n"
            if log_path:
                message += f"Log file / ملف السجل:\n{log_path}"
            _show_fatal_error(message)
        else:
            try:
                input("\nPress Enter to exit...")
            except Exception:
                pass

        sys.exit(1)
