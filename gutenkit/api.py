"""Thin client for the Gutendex API (https://gutendex.com), which indexes
Project Gutenberg's catalog as JSON. Standard library only."""

import json
import urllib.parse
import urllib.request

from . import __version__

BASE = "https://gutendex.com/books/"
USER_AGENT = f"gutenkit/{__version__} (+https://gutendex.com)"


class ApiError(Exception):
    pass


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ApiError(f"HTTP {e.code} for {url}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ApiError(f"network error: {e}") from e
    except json.JSONDecodeError as e:
        raise ApiError(f"bad response from server: {e}") from e


def search(query=None, *, topic=None, languages=None, author=None, sort=None, page=1):
    """Query the catalog. Returns the parsed Gutendex page dict
    ({count, next, previous, results})."""
    params = {}
    if query:
        params["search"] = query
    if topic:
        params["topic"] = topic
    if languages:
        params["languages"] = languages
    if sort:
        params["sort"] = sort  # "popular" (default), "ascending", "descending"
    if page and page > 1:
        params["page"] = page
    url = BASE + "?" + urllib.parse.urlencode(params) if params else BASE
    return _get_json(url)


def by_id(book_id):
    """Fetch a single book's metadata by Gutenberg id, or None if not found."""
    data = _get_json(BASE + "?" + urllib.parse.urlencode({"ids": book_id}))
    results = data.get("results", [])
    return results[0] if results else None


# --- helpers for working with a book record -------------------------------

def authors_str(book):
    names = [a.get("name", "?") for a in book.get("authors", [])]
    return "; ".join(names) if names else "Unknown"


def pick_format(book, kind):
    """Return the best download URL for `kind` ('txt' or 'epub'), or None.

    Gutendex `formats` is a dict of mime-type -> url. Compressed and cover
    entries are skipped for text."""
    formats = book.get("formats", {})
    if kind == "epub":
        for mime, url in formats.items():
            if mime.startswith("application/epub+zip"):
                return url
        return None
    # txt: prefer utf-8 plain text, avoid zip archives
    candidates = [
        (mime, url)
        for mime, url in formats.items()
        if mime.startswith("text/plain") and "zip" not in mime
    ]
    if not candidates:
        return None
    for mime, url in candidates:
        if "utf-8" in mime.lower():
            return url
    return candidates[0][1]


def available_formats(book):
    fmts = []
    if pick_format(book, "txt"):
        fmts.append("txt")
    if pick_format(book, "epub"):
        fmts.append("epub")
    return fmts
