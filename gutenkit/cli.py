"""Command-line interface for gutenkit."""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import urllib.request

from . import __version__, api, library


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

def print_book_line(book, index=None):
    fmts = api.available_formats(book)
    fmt_str = dim(f"[{'/'.join(fmts) or 'no dl'}]")
    langs = ",".join(book.get("languages", []))
    downloads = book.get("download_count", 0)
    prefix = f"{index:>2}. " if index is not None else ""
    print(
        f"{prefix}{bold('#' + str(book['id']))}  {book['title']}"
    )
    print(
        f"      {api.authors_str(book)}  "
        f"{dim(langs)}  {dim('↓' + str(downloads))}  {fmt_str}"
    )


def cmd_search(args):
    data = api.search(
        query=args.query,
        topic=args.topic,
        languages=args.lang,
        sort=args.sort,
        page=args.page,
    )
    count = data.get("count", 0)
    results = data.get("results", [])
    if not results:
        print("No matches.")
        return 0
    shown = min(len(results), args.limit)
    print(dim(f"{count} match(es); showing {shown} (page {args.page})"))
    print()
    for i, book in enumerate(results[: args.limit], 1):
        print_book_line(book, i)
    print()
    print(dim("Download with:  gutenkit get <id>"))
    if data.get("next"):
        print(dim(f"More results:   gutenkit search ... --page {args.page + 1}"))
    return 0


def cmd_info(args):
    book = api.by_id(args.id)
    if not book:
        err(f"No book with id {args.id}")
        return 1
    print(bold(book["title"]))
    print(f"  by {api.authors_str(book)}")
    print(f"  id:        {book['id']}")
    print(f"  languages: {', '.join(book.get('languages', []))}")
    print(f"  downloads: {book.get('download_count', 0)}")
    print(f"  formats:   {', '.join(api.available_formats(book)) or 'none'}")
    subjects = book.get("subjects", [])
    if subjects:
        print("  subjects:")
        for s in subjects[:12]:
            print(f"    - {s}")
    return 0


def _download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": api.USER_AGENT})
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
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
                    pct = got * 100 // total
                    sys.stdout.write(f"\r  downloading… {pct:3d}%")
                else:
                    sys.stdout.write(f"\r  downloading… {got // 1024} KiB")
                sys.stdout.flush()
    os.replace(tmp, dest)
    if _tty():
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()


def cmd_get(args):
    book = api.by_id(args.id)
    if not book:
        err(f"No book with id {args.id}")
        return 1
    fmt = args.format
    url = api.pick_format(book, fmt)
    if not url:
        avail = api.available_formats(book)
        err(f"No {fmt} format for '{book['title']}'. Available: {', '.join(avail) or 'none'}")
        return 1

    ext = "txt" if fmt == "txt" else "epub"
    dest = os.path.join(library.BOOKS_DIR, library.filename_for(book["id"], book["title"], ext))
    print(f"Getting {bold(book['title'])} — {api.authors_str(book)} ({fmt})")
    _download(url, dest)

    library.add(
        book["id"],
        title=book["title"],
        authors=api.authors_str(book),
        language=",".join(book.get("languages", [])),
        fmt=fmt,
        path=dest,
        downloaded_at=datetime.datetime.now().isoformat(timespec="seconds"),
    )
    print(f"Saved to {dest}")

    if fmt == "txt":
        if args.read:
            return _open_in_reader(dest)
        if _tty() and sys.stdin.isatty():
            ans = input("Open in txtread now? [y/N] ").strip().lower()
            if ans in ("y", "yes"):
                return _open_in_reader(dest)
    return 0


def _open_in_reader(path):
    reader = shutil.which("txtread")
    if not reader:
        err("txtread not found on PATH; open the file yourself:")
        print(path)
        return 1
    return subprocess.call([reader, path])


def cmd_library(args):
    lib = library.load()
    if not lib:
        print("Library is empty. Try:  gutenkit search <query>")
        return 0
    for entry in sorted(lib.values(), key=lambda e: e["title"].lower()):
        missing = "" if os.path.exists(entry["path"]) else dim("  (file missing)")
        print(f"{bold('#' + str(entry['id']))}  {entry['title']}  {dim('(' + entry['format'] + ')')}{missing}")
        print(f"      {entry['authors']}")
    print()
    print(dim("Read with:  gutenkit read <id>"))
    return 0


def cmd_read(args):
    entry = library.get(args.id)
    if not entry:
        err(f"#{args.id} is not in your library. Download it first:  gutenkit get {args.id}")
        return 1
    if not os.path.exists(entry["path"]):
        err(f"File is missing: {entry['path']}\nRe-download with:  gutenkit get {args.id}")
        return 1
    if entry["format"] != "txt":
        err(f"#{args.id} is {entry['format']}, which txtread can't display. File is at:")
        print(entry["path"])
        return 1
    return _open_in_reader(entry["path"])


def cmd_remove(args):
    entry = library.remove(args.id)
    if not entry:
        err(f"#{args.id} is not in your library.")
        return 1
    print(f"Removed #{args.id} '{entry['title']}' from library.")
    if args.delete_file and os.path.exists(entry["path"]):
        os.remove(entry["path"])
        print(f"Deleted file {entry['path']}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="gutenkit",
        description="Browse and download Project Gutenberg books from the terminal.",
    )
    p.add_argument("--version", action="version", version=f"gutenkit {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="search the catalog by title/author/topic")
    s.add_argument("query", nargs="?", help="free-text search of title and author")
    s.add_argument("--topic", help="filter by subject/bookshelf keyword")
    s.add_argument("--lang", help="language code(s), comma-separated, e.g. en,fr")
    s.add_argument("--sort", choices=["popular", "ascending", "descending"],
                   help="sort order (default: popular)")
    s.add_argument("--page", type=int, default=1, help="results page number")
    s.add_argument("--limit", type=int, default=15, help="max results to show")
    s.set_defaults(func=cmd_search)

    i = sub.add_parser("info", help="show details for a book id")
    i.add_argument("id", type=int)
    i.set_defaults(func=cmd_info)

    g = sub.add_parser("get", help="download a book by id")
    g.add_argument("id", type=int)
    g.add_argument("--format", choices=["txt", "epub"], default="txt")
    g.add_argument("--read", action="store_true", help="open in txtread after download")
    g.set_defaults(func=cmd_get)

    ll = sub.add_parser("library", aliases=["list"], help="list downloaded books")
    ll.set_defaults(func=cmd_library)

    r = sub.add_parser("read", help="open a downloaded book in txtread")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_read)

    rm = sub.add_parser("remove", help="remove a book from the library")
    rm.add_argument("id", type=int)
    rm.add_argument("--delete-file", action="store_true", help="also delete the file")
    rm.set_defaults(func=cmd_remove)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except api.ApiError as e:
        err(f"gutenkit: {e}")
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
