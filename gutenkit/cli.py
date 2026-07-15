"""Command-line interface for gutenkit."""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

from . import __version__, epub, library, providers


# --- small output helpers --------------------------------------------------

def _tty():
    return sys.stdout.isatty()


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if _tty() else text


def bold(t):
    return c(t, "1")


def dim(t):
    return c(t, "2")


def err(msg):
    print(msg, file=sys.stderr)


# --- rendering -------------------------------------------------------------

def print_book_line(book):
    fmts = book.get("formats", [])
    fmt_str = dim(f"[{'/'.join(fmts) or 'no dl'}]")
    langs = ",".join(book.get("languages", []))
    extra = book.get("extra", {})
    tail = ""
    if "download_count" in extra:
        tail = dim(f"  ↓{extra['download_count']}")
    print(f"  {bold(book['uid'])}  {book['title']}")
    print(f"      {book['authors']}  {dim(langs)}{tail}  {fmt_str}")


def cmd_search(args):
    provs = providers.select(args.source)
    groups, everything = [], []
    for p in provs:
        try:
            data = p.search(
                args.query, topic=args.topic, languages=args.lang,
                sort=args.sort, page=args.page, limit=args.limit,
            )
        except providers.ProviderError as e:
            err(dim(f"! {p.label}: {e}"))
            continue
        groups.append((p, data))
        everything.extend(data["results"])

    if args.json:
        print(json.dumps(everything, indent=2))
        return 0

    shown_any = False
    for p, data in groups:
        results = data["results"]
        if not results:
            continue
        shown_any = True
        count = data.get("count")
        count_str = f"{count} match(es)" if count is not None else "matches"
        more = ", more available" if data.get("has_more") else ""
        print(bold(p.label) + dim(f" — {count_str}, showing {len(results)}{more}"))
        for book in results:
            print_book_line(book)
        print()

    if not shown_any:
        print("No matches.")
        return 0
    print(dim("Details:  gutenkit info <uid>     Download:  gutenkit get <uid>"))
    return 0


def cmd_info(args):
    source, local_id = providers.parse_uid(args.id)
    book = providers.get(source).by_id(local_id)
    if not book:
        err(f"No book with id {args.id}")
        return 1
    if args.json:
        print(json.dumps(book, indent=2))
        return 0
    extra = book.get("extra", {})
    print(bold(book["title"]))
    print(f"  by {book['authors']}")
    print(f"  uid:       {book['uid']}")
    print(f"  source:    {providers.get(source).label}")
    print(f"  languages: {', '.join(book.get('languages', [])) or '-'}")
    print(f"  formats:   {', '.join(book.get('formats', [])) or 'none'}")
    if "download_count" in extra:
        print(f"  downloads: {extra['download_count']}")
    editions = extra.get("editions")
    if editions:
        print("  editions:")
        for ed in editions:
            print(f"    - {ed['id']}  ({ed['lang']}, {ed['kind']})")
    subjects = extra.get("subjects", [])
    if subjects:
        print("  subjects:")
        for s in subjects[:12]:
            print(f"    - {s}")
    return 0


def cmd_get(args):
    source, local_id = providers.parse_uid(args.id)
    provider = providers.get(source)
    book = provider.by_id(local_id)
    if not book:
        err(f"No book with id {args.id}")
        return 1

    fmt = args.format or provider.default_format
    if fmt not in book["formats"]:
        avail = ", ".join(book["formats"]) or "none"
        err(f"No {fmt} format for '{book['title']}'. Available: {avail}")
        return 1

    ext = "epub" if fmt == "epub" else "txt"
    dest = os.path.join(
        library.BOOKS_DIR, library.filename_for(source, local_id, book["title"], ext)
    )
    print(f"Getting {bold(book['title'])} — {book['authors']} ({fmt})")
    provider.download(book, fmt, dest)

    # Fill in an unknown author from the EPUB's own metadata when we can
    # (Wikisource, in particular, only learns the author at this point).
    if ext == "epub" and book["authors"] in ("", "Unknown"):
        creator = epub.opf_metadata(dest).get("creator")
        if creator:
            book["authors"] = creator

    library.add(
        book["uid"],
        source=source,
        local_id=local_id,
        title=book["title"],
        authors=book["authors"],
        language=",".join(book.get("languages", [])),
        fmt=fmt,
        path=dest,
        downloaded_at=datetime.datetime.now().isoformat(timespec="seconds"),
    )
    print(f"Saved to {dest}")

    if args.read:
        return _read(dest, fmt)
    if _tty() and sys.stdin.isatty():
        ans = input("Open in txtread now? [y/N] ").strip().lower()
        if ans in ("y", "yes"):
            return _read(dest, fmt)
    return 0


def _txt_from_epub(epub_path):
    """Render an EPUB to a cached .txt (rebuilt if the EPUB is newer)."""
    os.makedirs(library.CACHE_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(epub_path))[0]
    cache = os.path.join(library.CACHE_DIR, base_name + ".txt")
    if not os.path.exists(cache) or os.path.getmtime(cache) < os.path.getmtime(epub_path):
        with open(cache, "w", encoding="utf-8") as f:
            f.write(epub.to_text(epub_path))
    return cache


def _read(path, fmt):
    """Open a downloaded book in txtread, converting EPUB to text first."""
    if fmt == "epub":
        try:
            path = _txt_from_epub(path)
        except epub.EpubError as e:
            err(f"gutenkit: could not read EPUB: {e}")
            return 1
    return _open_in_reader(path)


def _open_in_reader(path):
    reader = shutil.which("txtread")
    if not reader:
        err("txtread not found on PATH; open the file yourself:")
        print(path)
        return 1
    return subprocess.call([reader, path])


def cmd_library(args):
    lib = library.load()
    if args.json:
        print(json.dumps(list(lib.values()), indent=2))
        return 0
    if not lib:
        print("Library is empty. Try:  gutenkit search <query>")
        return 0
    for entry in sorted(lib.values(), key=lambda e: e["title"].lower()):
        missing = "" if os.path.exists(entry["path"]) else dim("  (file missing)")
        print(f"{bold(entry['uid'])}  {entry['title']}  "
              f"{dim('(' + entry['format'] + ')')}{missing}")
        print(f"      {entry['authors']}")
    print()
    print(dim("Read with:  gutenkit read <uid>"))
    return 0


def cmd_read(args):
    source, local_id = providers.parse_uid(args.id)
    uid = f"{source}:{local_id}"
    entry = library.get(uid)
    if not entry:
        err(f"{uid} is not in your library. Download it first:  gutenkit get {uid}")
        return 1
    if not os.path.exists(entry["path"]):
        err(f"File is missing: {entry['path']}\nRe-download with:  gutenkit get {uid}")
        return 1
    return _read(entry["path"], entry["format"])


def cmd_remove(args):
    source, local_id = providers.parse_uid(args.id)
    uid = f"{source}:{local_id}"
    entry = library.remove(uid)
    if not entry:
        err(f"{uid} is not in your library.")
        return 1
    print(f"Removed {uid} '{entry['title']}' from library.")
    if args.delete_file and os.path.exists(entry["path"]):
        os.remove(entry["path"])
        print(f"Deleted file {entry['path']}")
    return 0


def cmd_sources(args):
    if args.json:
        print(json.dumps(
            [{"name": p.name, "aliases": list(p.aliases), "label": p.label,
              "formats": p.formats_help} for p in providers.all_providers()],
            indent=2,
        ))
        return 0
    print(dim("Search a subset with:  gutenkit search <q> --source <name>[,<name>]"
              "  (or --source all)"))
    print()
    for p in providers.all_providers():
        aka = f"  (aka {', '.join(p.aliases)})" if p.aliases else ""
        print(f"{bold(p.name)}{dim(aka)}")
        print(f"      {p.label} — {p.formats_help}")
    return 0


def cmd_index(args):
    name = providers.get(args.provider).name
    if name != "perseus":
        err(f"'{name}' needs no index; only Perseus does.")
        return 1
    from .providers import perseus
    if perseus._load_catalog() is not None and not args.rebuild:
        print("Perseus index already present. Use --rebuild to refresh it.")
        return 0
    err("Building the Perseus catalogue — this streams ~130 MB of TEI metadata "
        "from GitHub once, then caches it.")
    perseus.build_index(log=lambda m: err(dim("  " + m)))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="gutenkit",
        description="Browse and download free books from several sources.",
    )
    p.add_argument("--version", action="version", version=f"gutenkit {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="search catalogues by title/author/topic")
    s.add_argument("query", nargs="?", help="free-text search of title and author")
    s.add_argument("--source", help="comma-separated sources, or 'all' "
                   "(default: gutenberg). See `gutenkit sources`.")
    s.add_argument("--topic", help="filter by subject/bookshelf keyword")
    s.add_argument("--lang", help="language code(s), comma-separated, e.g. en,la,grc")
    s.add_argument("--sort", choices=["popular", "ascending", "descending"],
                   help="sort order (Gutenberg only)")
    s.add_argument("--page", type=int, default=1, help="results page number")
    s.add_argument("--limit", type=int, default=15, help="max results per source")
    s.add_argument("--json", action="store_true", help="output raw JSON")
    s.set_defaults(func=cmd_search)

    i = sub.add_parser("info", help="show details for a book uid")
    i.add_argument("id", metavar="uid", help="e.g. 1342 or perseus:tlg0012.tlg001")
    i.add_argument("--json", action="store_true", help="output raw JSON")
    i.set_defaults(func=cmd_info)

    g = sub.add_parser("get", help="download a book by uid")
    g.add_argument("id", metavar="uid")
    g.add_argument("--format", choices=["txt", "epub"],
                   help="download format (default: the source's usual format)")
    g.add_argument("--read", action="store_true", help="open in txtread after download")
    g.set_defaults(func=cmd_get)

    ll = sub.add_parser("library", aliases=["list"], help="list downloaded books")
    ll.add_argument("--json", action="store_true", help="output raw JSON")
    ll.set_defaults(func=cmd_library)

    r = sub.add_parser("read", help="open a downloaded book in txtread")
    r.add_argument("id", metavar="uid")
    r.set_defaults(func=cmd_read)

    rm = sub.add_parser("remove", help="remove a book from the library")
    rm.add_argument("id", metavar="uid")
    rm.add_argument("--delete-file", action="store_true", help="also delete the file")
    rm.set_defaults(func=cmd_remove)

    so = sub.add_parser("sources", help="list available sources")
    so.add_argument("--json", action="store_true", help="output raw JSON")
    so.set_defaults(func=cmd_sources)

    ix = sub.add_parser("index", help="build a source's local catalogue (Perseus)")
    ix.add_argument("provider", nargs="?", default="perseus")
    ix.add_argument("--rebuild", action="store_true", help="rebuild even if present")
    ix.set_defaults(func=cmd_index)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except providers.ProviderError as e:
        err(f"gutenkit: {e}")
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
