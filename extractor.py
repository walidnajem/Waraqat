import os
import re
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup

from utils import clean_filename

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ar,fr,en-US,en;q=0.9",
}

SOCIAL_DOMAINS = [
    "facebook.com", "whatsapp.com", "twitter.com", "x.com",
    "telegram.me", "t.me", "pinterest.com", "linkedin.com",
    "instagram.com", "youtube.com"
]

DOC_EXTENSIONS = (".pdf", ".docx", ".doc", ".pptx", ".ppt", ".epub", ".djvu")


def _extract_filename_from_cd(content_disposition):
    """Extracts filename from Content-Disposition header supporting RFC 6266 / UTF-8."""
    if not content_disposition:
        return ""
    match = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", content_disposition)
    if match:
        return urllib.parse.unquote(match.group(1).strip('"\' '))
    match = re.search(r'filename="?([^";]+)"?', content_disposition)
    if match:
        return urllib.parse.unquote(match.group(1).strip('"\' '))
    return ""


def _extract_name_from_url(url):
    """Extracts a clean filename from URL path or query params."""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    for key in ["name", "filename", "file", "title", "book"]:
        if key in qs and qs[key]:
            val = urllib.parse.unquote(qs[key][0]).strip()
            if val and len(val) >= 2:
                return val

    base = os.path.basename(urllib.parse.unquote(parsed.path))
    for ext in DOC_EXTENSIONS:
        if base.lower().endswith(ext):
            base = base[:-len(ext)]
            break
    return base


def _extract_text_around_element(element):
    """Finds descriptive text near a link."""
    prev = element.previous_sibling
    while prev:
        try:
            txt = prev.get_text(" ", strip=True) if hasattr(prev, "get_text") else str(prev).strip()
            if txt and len(txt) > 3:
                return txt
        except Exception:
            pass
        prev = getattr(prev, "previous_sibling", None)

    parent = element.find_parent(["li", "tr", "p", "div", "article", "section"])
    if parent:
        try:
            txt = parent.get_text(" ", strip=True)
            if txt and len(txt) > 3:
                return txt
        except Exception:
            pass
    return ""


def _clean_title(raw_text, fallback_name=""):
    """Cleans title text and strips generic download labels."""
    text = (raw_text or "").strip()

    cleaned = re.sub(
        r"(?i)\b(تحميل|تنزيل|رابط|ملف|مباشر|الكتاب|كتاب|download|telecharger|télécharger|pdf|file|link|book)\b",
        "",
        text
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.:")

    if cleaned and len(cleaned) >= 3 and not cleaned.isdigit():
        return clean_filename(cleaned)

    if fallback_name:
        fallback_cleaned = re.sub(
            r"(?i)\b(تحميل|تنزيل|رابط|ملف|مباشر|الكتاب|كتاب|download|telecharger|télécharger|pdf|file|link|book)\b",
            "",
            fallback_name
        ).strip(" -_.:")
        if fallback_cleaned and len(fallback_cleaned) >= 3:
            return clean_filename(fallback_cleaned)
        return clean_filename(fallback_name)

    if text and len(text) >= 3 and not text.isdigit():
        return clean_filename(text)

    return ""


def _extract_archive_org(url):
    """Extracts downloadable files (PDF, EPUB, DJVU, DOC, DOCX) from an Archive.org item."""
    parsed = urllib.parse.urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    # Convert /details/ID to /download/ID/
    if len(path_parts) >= 2 and path_parts[0] == "details":
        item_id = path_parts[1]
    elif len(path_parts) >= 2 and path_parts[0] == "download":
        item_id = path_parts[1]
    else:
        item_id = path_parts[-1] if path_parts else ""

    if not item_id:
        return []

    download_page_url = f"https://archive.org/download/{item_id}/"

    try:
        response = requests.get(download_page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    target_extensions = (".pdf", ".epub", ".djvu", ".doc", ".docx")
    files = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue

        href_lower = href.lower()
        matched_ext = None
        for ext in target_extensions:
            if href_lower.endswith(ext):
                matched_ext = ext
                break

        if not matched_ext:
            continue

        abs_url = urllib.parse.urljoin(download_page_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)

        filename = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(abs_url).path))
        title = filename
        for ext in target_extensions:
            if title.lower().endswith(ext):
                title = title[:-len(ext)]
                break
        title = clean_filename(title) or filename

        file_type = matched_ext.lstrip(".").upper()

        files.append({
            "type": file_type,
            "url": abs_url,
            "title": title
        })

    return files


def resolve_mediafire(url):
    """Resolves a MediaFire download page to its direct file link."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        btn = soup.find("a", id="downloadButton") or soup.find("a", attrs={"aria-label": re.compile(r"download", re.I)})
        if btn and btn.get("href"):
            return btn["href"]
    except Exception:
        pass
    return None


def extract_files(url):
    """
    Universally extracts downloadable documents (PDF, Word, PPT, EPUB) and cloud links
    from any web page or direct URL.
    """
    url = url.strip()
    parsed_input = urllib.parse.urlparse(url)
    path_input = parsed_input.path.lower()

    # -------------------------------------------------------------
    # CASE 1: The input URL ITSELF is a direct document
    # -------------------------------------------------------------
    for ext in DOC_EXTENSIONS:
        if path_input.endswith(ext) or re.search(re.escape(ext) + r"($|[?#])", url, re.IGNORECASE):
            title = _extract_name_from_url(url)
            file_type = ext.lstrip(".").upper()
            return [{
                "type": file_type,
                "url": url,
                "title": clean_filename(title) or "Document"
            }]

    # -------------------------------------------------------------
    # CASE 2: Input URL is a MediaFire link
    # -------------------------------------------------------------
    if "mediafire.com" in parsed_input.netloc.lower():
        direct_link = resolve_mediafire(url)
        if direct_link:
            title = _extract_name_from_url(direct_link)
            return [{
                "type": "MEDIAFIRE",
                "url": direct_link,
                "title": clean_filename(title) or "MediaFire_Document"
            }]

    # -------------------------------------------------------------
    # CASE 3: Input URL is a Google Drive link
    # -------------------------------------------------------------
    gdrive_match = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)([a-zA-Z0-9_-]+)", url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return [{
            "type": "GDRIVE",
            "id": file_id,
            "url": url,
            "title": "Google_Drive_Document"
        }]

    # -------------------------------------------------------------
    # CASE 4: Archive.org (Internet Archive)
    # -------------------------------------------------------------
    if "archive.org" in parsed_input.netloc.lower():
        return _extract_archive_org(url)

    # -------------------------------------------------------------
    # CASE 5: Mega.nz — encrypted links are not supported yet
    # -------------------------------------------------------------
    if "mega.nz" in parsed_input.netloc.lower() or "mega.co.nz" in parsed_input.netloc.lower():
        raise ValueError(
            "MEGA links are not supported yet. | روابط MEGA غير مدعومة حالياً."
        )

    # -------------------------------------------------------------
    # CASE 6: Universal web page — fetch and scan for document links
    # -------------------------------------------------------------
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True,
            verify=True
        )
    except requests.exceptions.SSLError:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True,
            verify=False
        )

    response.raise_for_status()

    # Check if final redirect is a binary file
    content_type = response.headers.get("Content-Type", "").lower()
    content_disposition = response.headers.get("Content-Disposition", "")
    for ext in DOC_EXTENSIONS:
        if ext in content_type or ext in content_disposition.lower():
            filename = _extract_filename_from_cd(content_disposition)
            if not filename:
                filename = _extract_name_from_url(response.url)
            return [{
                "type": ext.lstrip(".").upper(),
                "url": response.url,
                "title": clean_filename(filename) or "Document"
            }]

    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")

    page_title = ""
    h1 = soup.find(["h1", "h2"])
    if h1:
        page_title = h1.get_text(" ", strip=True)
    elif soup.title:
        page_title = soup.title.get_text(" ", strip=True)

    files = []
    seen_urls = set()
    seen_gdrive_ids = set()
    counter = 1

    # -------------------------------------------------------------
    # Search <a> anchor links
    # -------------------------------------------------------------
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        abs_url = urllib.parse.urljoin(url, href)
        parsed_url = urllib.parse.urlparse(abs_url)
        path_lower = parsed_url.path.lower()
        netloc_lower = parsed_url.netloc.lower()

        if any(s in netloc_lower for s in SOCIAL_DOMAINS):
            continue

        # Skip article/book browsing pages
        if re.search(r"/(?:ar/)?(?:book|books)/[^/]+-pdf/?$", path_lower) and not any(k in path_lower for k in ["download", "downloading", "/dl/"]):
            continue

        if path_lower.rstrip("/").endswith(("-ebooks", "/newest", "/category", "/archive", "/tags")):
            continue

        # --- A. Google Drive ---
        gdrive_match = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?id=)([a-zA-Z0-9_-]+)", abs_url)
        if gdrive_match:
            file_id = gdrive_match.group(1)
            if file_id in seen_gdrive_ids:
                continue
            seen_gdrive_ids.add(file_id)

            raw_text = a.get_text(" ", strip=True) or a.get("title") or a.get("aria-label") or _extract_text_around_element(a)
            fallback = page_title or f"Drive_File_{counter}"
            title = _clean_title(raw_text, fallback_name=fallback)

            files.append({
                "type": "GDRIVE",
                "id": file_id,
                "url": abs_url,
                "title": title or f"Drive_File_{counter}"
            })
            counter += 1
            continue

        # --- B. MediaFire ---
        if "mediafire.com" in netloc_lower and ("/file/" in path_lower or "/download/" in path_lower):
            if abs_url in seen_urls:
                continue
            seen_urls.add(abs_url)
            direct_mf = resolve_mediafire(abs_url)
            mf_target = direct_mf or abs_url
            raw_text = a.get_text(" ", strip=True) or _extract_name_from_url(mf_target)
            title = _clean_title(raw_text, fallback_name=page_title or f"MediaFire_File_{counter}")
            files.append({
                "type": "MEDIAFIRE",
                "url": mf_target,
                "title": title or f"MediaFire_File_{counter}"
            })
            counter += 1
            continue

        # --- C. Documents (PDF, Word, PPT, EPUB) ---
        link_text = a.get_text(" ", strip=True)
        link_title_attr = a.get("title", "") or ""
        link_aria = a.get("aria-label", "") or ""
        combined_text = f"{link_text} {link_title_attr} {link_aria}".lower()

        matched_ext = None
        for ext in DOC_EXTENSIONS:
            if (
                path_lower.endswith(ext) or
                re.search(re.escape(ext) + r"($|[?#])", abs_url, re.IGNORECASE) or
                str(a.get("download", "")).lower().endswith(ext)
            ):
                matched_ext = ext.lstrip(".").upper()
                break

        is_download_endpoint = False
        if not matched_ext:
            has_dl_path = (
                any(k in path_lower for k in ["/download", "/downloading", "/dl/", "get-file", "download_file"]) or
                any(k in parsed_url.query.lower() for k in ["download", "file_id", "b="])
            )
            has_dl_text = any(k in combined_text for k in ["تحميل", "تنزيل", "download", "telecharger", "télécharger"])
            has_pdf_kw = "pdf" in path_lower or "pdf" in combined_text

            if has_dl_path and (has_dl_text or has_pdf_kw):
                is_download_endpoint = True
                matched_ext = "PDF"

        if matched_ext or is_download_endpoint:
            canonical_url = abs_url.split("#")[0]
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)

            url_name = _extract_name_from_url(abs_url)
            fallback = page_title or url_name or f"Document_{counter}"

            is_generic_anchor = (
                not link_text or
                len(link_text) < 4 or
                link_text.strip().lower() in ["تحميل", "تنزيل", "download", "تحميل الكتاب", "تحميل pdf", "download pdf", "telecharger"]
            )
            raw_candidate = "" if is_generic_anchor else link_text
            title = _clean_title(raw_candidate, fallback_name=fallback)
            if not title:
                title = clean_filename(fallback) or f"Document_{counter}"

            files.append({
                "type": matched_ext or "PDF",
                "url": abs_url,
                "title": title
            })
            counter += 1

    # -------------------------------------------------------------
    # Embedded files in <embed>, <iframe>, <object>
    # -------------------------------------------------------------
    for tag in soup.find_all(["embed", "iframe", "object"]):
        src = tag.get("src") or tag.get("data")
        if not src:
            continue
        src = src.strip()
        abs_src = urllib.parse.urljoin(url, src)

        gdrive_match = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|preview\?id=)([a-zA-Z0-9_-]+)", abs_src)
        if gdrive_match:
            file_id = gdrive_match.group(1)
            if file_id not in seen_gdrive_ids:
                seen_gdrive_ids.add(file_id)
                files.append({
                    "type": "GDRIVE",
                    "id": file_id,
                    "url": abs_src,
                    "title": clean_filename(page_title or f"Drive_File_{counter}")
                })
                counter += 1
            continue

        for ext in DOC_EXTENSIONS:
            if ext in abs_src.lower():
                canonical_src = abs_src.split("#")[0]
                if canonical_src in seen_urls:
                    continue
                seen_urls.add(canonical_src)

                name = _extract_name_from_url(abs_src)
                title = clean_filename(name or page_title or f"Document_{counter}")
                files.append({
                    "type": ext.lstrip(".").upper(),
                    "url": abs_src,
                    "title": title
                })
                counter += 1
                break

    return files


def extract_files_batch(urls, log_callback=None):
    """
    Extracts files from a list of URLs and aggregates all results.
    """
    all_files = []
    seen = set()

    for i, u in enumerate(urls, start=1):
        u = u.strip()
        if not u:
            continue
        if log_callback:
            log_callback(f"[*] Scanning ({i}/{len(urls)}): {u}")
        try:
            items = extract_files(u)
            for item in items:
                key = item.get("id") or item.get("url")
                if key not in seen:
                    seen.add(key)
                    all_files.append(item)
            if log_callback:
                log_callback(f"[+] Found {len(items)} file(s) in: {u}")
        except Exception as e:
            if log_callback:
                log_callback(f"[ERROR] Failed to scan {u}: {str(e)}")

    return all_files
