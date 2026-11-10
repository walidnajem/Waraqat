import re
import arabic_reshaper
from bidi.algorithm import get_display


def ar(text):
    """Reshapes Arabic text for proper display in RTL contexts."""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def clean_filename(text):
    """
    Cleans and sanitizes a string to make it a valid Windows/Linux filename.
    Removes invalid characters, strips extra whitespace, and strips .pdf suffix.
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

    return text[:120]


def safe_print(text):
    """Safely prints text with Arabic reshaping if possible."""
    try:
        print(ar(text))
    except Exception:
        print(text)
