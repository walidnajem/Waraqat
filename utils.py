import os
import re
from urllib.parse import urlparse

# Device names that Windows reserves regardless of extension.
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MAX_FILENAME_CHARS = 120
DEFAULT_MAX_PATH = 240


def get_site_name(url):
    """Returns a clean domain name for display, without the www. prefix."""
    try:
        domain = urlparse(str(url)).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or "Universal Scanner"
    except Exception:
        return "General Website"


def clean_filename(text):
    """
    Cleans and sanitizes a string to make it a valid Windows/Linux filename.
    Removes invalid characters, handles reserved device names, strips extra
    whitespace, and strips .pdf suffix.
    """
    if not text:
        return "unnamed_document"

    text = str(text).strip()

    # Remove invalid characters for Windows filenames
    invalid_chars = r'\/:*?"<>|'
    for char in invalid_chars:
        text = text.replace(char, "_")

    # Remove non-printable control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    # Normalize whitespace
    text = " ".join(text.split())

    # Remove trailing .pdf extension if already present (case-insensitive)
    if text.lower().endswith(".pdf"):
        text = text[:-4].strip()

    # Remove trailing dots or spaces which Windows forbids
    text = text.rstrip('. ')

    if not text:
        return "unnamed_document"

    # Windows reserves CON, PRN, AUX, NUL, COM1-9 and LPT1-9 (with or without
    # an extension). Prefixing with "_" makes the name safe.
    stem = text.split(".")[0].strip().upper()
    if stem in WINDOWS_RESERVED_NAMES:
        text = "_" + text

    return text[:MAX_FILENAME_CHARS].rstrip('. ')


def fit_filename(folder, filename, max_path=DEFAULT_MAX_PATH):
    """
    Shortens a filename so the full path stays below the Windows MAX_PATH
    limit (260 chars by default). Keeps the extension and the leading number.
    """
    if not filename:
        return filename

    try:
        folder_len = len(os.path.abspath(folder))
    except Exception:
        folder_len = len(str(folder))

    ext = os.path.splitext(filename)[1]
    stem = filename[:-len(ext)] if ext else filename
    available = max_path - folder_len - 1 - len(ext)

    if available < 16:
        available = 16

    if len(stem) <= available:
        return filename

    keep = max(1, available - 3)
    shortened = stem[:keep].rstrip('. ') + "..."
    return shortened + ext
