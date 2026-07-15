"""Project Gutenberg, via the Gutendex JSON API (https://gutendex.com)."""

import urllib.parse

from . import base

BASE = "https://gutendex.com/books/"


def _authors_str(raw):
    names = [a.get("name", "?") for a in raw.get("authors", [])]
    return "; ".join(names) if names else "Unknown"


def _format_urls(raw):
    """Map Gutendex's mime->url dict onto {"txt": url, "epub": url}."""
    formats = raw.get("formats", {})
    out = {}

    epub = next(
        (u for m, u in formats.items() if m.startswith("application/epub+zip")),
        None,
    )
    if epub:
        out["epub"] = epub

    txt_candidates = [
        (m, u) for m, u in formats.items()
        if m.startswith("text/plain") and "zip" not in m
    ]
    if txt_candidates:
        utf8 = next((u for m, u in txt_candidates if "utf-8" in m.lower()), None)
        out["txt"] = utf8 or txt_candidates[0][1]

    return out


def _to_record(raw):
    urls = _format_urls(raw)
    return base.make_record(
        Gutenberg.name, raw["id"],
        title=raw.get("title", ""),
        authors=_authors_str(raw),
        languages=raw.get("languages", []),
        formats=list(urls),
        extra={
            "format_urls": urls,
            "download_count": raw.get("download_count", 0),
            "subjects": raw.get("subjects", []),
        },
    )


class Gutenberg(base.Provider):
    name = "gutenberg"
    label = "Project Gutenberg"
    aliases = ("gb", "pg", "gutendex")
    default_format = "txt"
    formats_help = "txt, epub — ~75k mostly-English public-domain books"

    def search(self, query, *, topic=None, languages=None, sort=None,
               page=1, limit=15):
        params = {}
        if query:
            params["search"] = query
        if topic:
            params["topic"] = topic
        if languages:
            params["languages"] = languages
        if sort:
            params["sort"] = sort
        if page and page > 1:
            params["page"] = page
        url = BASE + ("?" + urllib.parse.urlencode(params) if params else "")
        data = base.http_json(url)
        results = [_to_record(r) for r in data.get("results", [])[:limit]]
        return {
            "count": data.get("count"),
            "results": results,
            "has_more": bool(data.get("next")),
        }

    def by_id(self, local_id):
        data = base.http_json(BASE + "?" + urllib.parse.urlencode({"ids": local_id}))
        results = data.get("results", [])
        return _to_record(results[0]) if results else None

    def download(self, record, fmt, dest_path):
        url = record["extra"].get("format_urls", {}).get(fmt)
        if not url:
            raise base.ProviderError(
                f"no {fmt} format for '{record['title']}' "
                f"(have: {', '.join(record['formats']) or 'none'})"
            )
        base.download_url(url, dest_path)
