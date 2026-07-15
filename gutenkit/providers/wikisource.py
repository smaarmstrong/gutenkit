"""Wikisource — the free library of source texts, one MediaWiki per language
(en, la for Latin, el for Greek, ...).

Search uses the MediaWiki API. Whole works are often split across chapter
subpages, so downloading goes through the ws-export service, which assembles the
complete work (following subpages) into an EPUB that gutenkit then renders to
text. The author is read back from that EPUB's metadata, since the API doesn't
expose it cleanly."""

import urllib.parse

from . import base
from .. import epub

API = "https://{lang}.wikisource.org/w/api.php?{query}"
WS_EXPORT = "https://ws-export.wmcloud.org/?{query}"

DEFAULT_LANG = "en"
# gutenkit --lang code -> Wikisource subdomain. Unknown codes pass through, so
# any wikisource subdomain works even if not listed here.
_SUBDOMAIN = {
    "en": "en", "la": "la", "lat": "la",
    "el": "el", "grc": "el", "gr": "el",
    "fr": "fr", "de": "de", "es": "es", "it": "it",
}


def _subdomains(languages):
    if not languages:
        return [DEFAULT_LANG]
    out = []
    for code in languages.split(","):
        code = code.strip().lower()
        sub = _SUBDOMAIN.get(code, code)
        if sub and sub not in out:
            out.append(sub)
    return out


def _record(lang, title, *, authors="Unknown"):
    # local_id is "lang/Title"; the title keeps its own slashes (subpages) and
    # uses underscores for spaces, matching MediaWiki's canonical page form.
    local_id = f"{lang}/{title.replace(' ', '_')}"
    return base.make_record(
        Wikisource.name, local_id,
        title=title.replace("_", " "),
        authors=authors,
        languages=[lang],
        formats=["epub"],
        extra={"lang": lang, "page": title.replace("_", " ")},
    )


class Wikisource(base.Provider):
    name = "wikisource"
    label = "Wikisource"
    aliases = ("ws", "wikis")
    default_format = "epub"
    formats_help = "epub (read via EPUB->text); per-language: en, la, el, ..."

    def search(self, query, *, topic=None, languages=None, sort=None,
               page=1, limit=15):
        q = query or topic or ""
        subs = _subdomains(languages)
        results, count = [], 0
        for lang in subs:
            params = urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": q,
                "srnamespace": "0", "srlimit": str(limit),
                "format": "json", "formatversion": "2",
            })
            data = base.http_json(API.format(lang=lang, query=params))
            info = data.get("query", {})
            count += info.get("searchinfo", {}).get("totalhits", 0)
            for hit in info.get("search", []):
                results.append(_record(lang, hit["title"]))
        return {"count": count, "results": results[:limit],
                "has_more": len(results) > limit}

    def by_id(self, local_id):
        if "/" not in local_id:
            return None
        lang, title = local_id.split("/", 1)
        title = title.replace("_", " ")
        params = urllib.parse.urlencode({
            "action": "query", "titles": title, "prop": "info",
            "redirects": "1", "format": "json", "formatversion": "2",
        })
        data = base.http_json(API.format(lang=lang, query=params))
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return None
        return _record(lang, pages[0]["title"])

    def download(self, record, fmt, dest_path):
        if fmt != "epub":
            raise base.ProviderError("Wikisource is served as epub: --format epub")
        query = urllib.parse.urlencode({
            "lang": record["extra"]["lang"],
            "format": "epub-3",
            "page": record["extra"]["page"],
        })
        base.download_url(WS_EXPORT.format(query=query), dest_path, timeout=180)
        # ws-export sometimes returns an HTML error page on a bad title.
        if not epub.opf_metadata(dest_path):
            raise base.ProviderError(
                f"ws-export did not return a valid EPUB for '{record['title']}'"
            )
