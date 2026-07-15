"""Shared plumbing for source providers: the normalized book record, HTTP
helpers, and the Provider base class. Standard library only."""

import json
import os
import sys
import urllib.error
import urllib.request

from .. import __version__

USER_AGENT = f"gutenkit/{__version__} (+https://github.com/; headless CLI)"


class ProviderError(Exception):
    """Any failure talking to a source (network, parse, not-found)."""


# --- normalized record -----------------------------------------------------
#
# Every provider maps its own catalog onto this shape so the CLI never has to
# know which source a book came from:
#
#   uid        source-qualified id, e.g. "gutenberg:1342" or
#              "perseus:tlg0012.tlg001". This is what the user types.
#   source     provider name ("gutenberg", "standardebooks", "perseus")
#   local_id   id within the source (the part after the colon)
#   title      display title (str)
#   authors    display author(s) (str, already joined)
#   languages  list of language codes (["en"], ["grc"], ...)
#   formats    list of downloadable kinds available, e.g. ["txt", "epub"]
#   extra      provider-specific bag (subjects, urn, slug, edition, ...)

def make_record(source, local_id, *, title, authors, languages=None,
                formats=None, extra=None):
    local_id = str(local_id)
    return {
        "uid": f"{source}:{local_id}",
        "source": source,
        "local_id": local_id,
        "title": title or "(untitled)",
        "authors": authors or "Unknown",
        "languages": list(languages or []),
        "formats": list(formats or []),
        "extra": dict(extra or {}),
    }


# --- HTTP ------------------------------------------------------------------

def _open(url, *, headers=None, timeout=30):
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise ProviderError(f"HTTP {e.code} for {url}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProviderError(f"network error for {url}: {e}") from e


def http_json(url, *, headers=None, timeout=30):
    with _open(url, headers=headers, timeout=timeout) as resp:
        try:
            return json.load(resp)
        except json.JSONDecodeError as e:
            raise ProviderError(f"bad JSON from {url}: {e}") from e


def http_text(url, *, headers=None, timeout=30, encoding="utf-8"):
    with _open(url, headers=headers, timeout=timeout) as resp:
        return resp.read().decode(encoding, "replace")


def _tty():
    return sys.stderr.isatty()


def download_url(url, dest, *, timeout=120, headers=None):
    """Stream `url` to `dest` (atomically), with a progress line on a TTY."""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    tmp = dest + ".part"
    with _open(url, headers=headers, timeout=timeout) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        got = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            if _tty():
                if total:
                    sys.stderr.write(f"\r  downloading… {got * 100 // total:3d}%")
                else:
                    sys.stderr.write(f"\r  downloading… {got // 1024} KiB")
                sys.stderr.flush()
    os.replace(tmp, dest)
    if _tty():
        sys.stderr.write("\r" + " " * 40 + "\r")
        sys.stderr.flush()


# --- provider interface ----------------------------------------------------

class Provider:
    """A browsable source of free books.

    Subclasses set the class attributes and implement search/by_id/download.
    """

    name = "?"            # canonical id used in uids and --source
    label = "?"           # human-readable name for section headers
    aliases = ()          # extra --source spellings
    default_format = "txt"
    formats_help = ""     # short note shown by `sources`

    def search(self, query, *, topic=None, languages=None, sort=None,
               page=1, limit=15):
        """Return {"count": int|None, "results": [record], "has_more": bool}."""
        raise NotImplementedError

    def by_id(self, local_id):
        """Return a single record or None."""
        raise NotImplementedError

    def download(self, record, fmt, dest_path):
        """Fetch `fmt` of `record` and write it to `dest_path`."""
        raise NotImplementedError
