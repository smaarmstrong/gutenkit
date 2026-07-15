"""Standard Ebooks (https://standardebooks.org) — carefully typeset public-domain
ebooks. Their OPDS feed is now patron-gated, so we use the public HTML search
and the stable download-URL pattern. Only EPUB is offered; gutenkit renders it
to text with the built-in EPUB reader.

Search listings show slug-derived titles (cheap); exact title/author are fetched
from the book page on `info`/`get`."""

import re
import urllib.parse
from html.parser import HTMLParser

from . import base

ROOT = "https://standardebooks.org"
_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of",
          "on", "or", "the", "to", "with"}


def _titleize(slug):
    words = slug.split("-")
    out = []
    for i, w in enumerate(words):
        if i and w in _SMALL:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


class _LinkGrabber(HTMLParser):
    """Collect unique /ebooks/<author>/<work> paths in document order."""

    def __init__(self):
        super().__init__()
        self.paths = []
        self._seen = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        m = re.match(r"^/ebooks/([a-z0-9-]+)/([a-z0-9-]+)/?$", href)
        if m:
            path = f"{m.group(1)}/{m.group(2)}"
            if path not in self._seen:
                self._seen.add(path)
                self.paths.append(path)


def _record_from_path(path, *, title=None, authors=None):
    author_slug, work_slug = path.split("/", 1)
    return base.make_record(
        StandardEbooks.name, path,
        title=title or _titleize(work_slug),
        authors=authors or _titleize(author_slug),
        languages=["en"],
        formats=["epub"],
        extra={"path": path},
    )


class StandardEbooks(base.Provider):
    name = "standardebooks"
    label = "Standard Ebooks"
    aliases = ("se", "std")
    default_format = "epub"
    formats_help = "epub only (read via built-in EPUB->text); English classics"

    def search(self, query, *, topic=None, languages=None, sort=None,
               page=1, limit=15):
        if languages and not any(l.startswith("en") for l in languages.split(",")):
            return {"count": 0, "results": [], "has_more": False}
        q = query or topic or ""
        url = ROOT + "/ebooks?" + urllib.parse.urlencode({"query": q})
        html = base.http_text(url)
        grab = _LinkGrabber()
        grab.feed(html)
        paths = grab.paths[:limit]
        return {
            "count": len(grab.paths),
            "results": [_record_from_path(p) for p in paths],
            "has_more": len(grab.paths) > limit,
        }

    def by_id(self, local_id):
        if "/" not in local_id:
            return None
        url = f"{ROOT}/ebooks/{local_id}"
        try:
            html = base.http_text(url)
        except base.ProviderError:
            return None
        title = authors = None
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            head = re.sub(r"\s+", " ", m.group(1)).strip()
            # "Pride and Prejudice, by Jane Austen - Free ebook download - ..."
            head = head.split(" - ")[0]
            if ", by " in head:
                title, authors = head.split(", by ", 1)
        return _record_from_path(local_id, title=title, authors=authors)

    def download(self, record, fmt, dest_path):
        if fmt != "epub":
            raise base.ProviderError(
                "Standard Ebooks only offers epub; try:  --format epub"
            )
        author, work = record["local_id"].split("/", 1)
        # The bare .epub URL serves a "download has started" interstitial that
        # meta-refreshes to the same path with ?source=download; that query is
        # what actually returns the file.
        url = (f"{ROOT}/ebooks/{author}/{work}/downloads/"
               f"{author}_{work}.epub?source=download")
        base.download_url(url, dest_path)
