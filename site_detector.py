from urllib.parse import urlparse


def detect_site(url):
    """
    Detects the domain / site name from any URL.
    All websites are supported universally.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Remove 'www.' prefix for cleaner display
        if domain.startswith("www."):
            domain = domain[4:]

        if not domain:
            domain = "Universal Scanner"

        return {
            "site": domain,
            "extractor": "universal"
        }
    except Exception:
        return {
            "site": "General Website",
            "extractor": "universal"
        }


def get_site_name(url):
    return detect_site(url)["site"]


def get_extractor(url):
    return "universal"
