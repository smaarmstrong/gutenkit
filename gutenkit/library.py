"""Local library: where downloaded books live and a JSON index of them."""

import json
import os
import re

DATA_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
    "gutenkit",
)
LIBRARY_JSON = os.path.join(DATA_DIR, "library.json")

# Plain-text renders of EPUBs, so txtread can read them.
CACHE_DIR = os.path.join(DATA_DIR, "cache")

# Where the actual book files are stored. Override with GUTENKIT_BOOKS_DIR.
BOOKS_DIR = os.environ.get(
    "GUTENKIT_BOOKS_DIR", os.path.expanduser("~/Books/gutenberg")
)


def slugify(text, maxlen=60):
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-") or "book"


def filename_for(book_id, title, ext):
    return f"{book_id}-{slugify(title)}.{ext}"


def load():
    try:
        with open(LIBRARY_JSON) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(lib):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = LIBRARY_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(lib, f, indent=2)
    os.replace(tmp, LIBRARY_JSON)


def get(book_id):
    return load().get(str(book_id))


def add(book_id, *, title, authors, language, fmt, path, downloaded_at):
    lib = load()
    lib[str(book_id)] = {
        "id": int(book_id),
        "title": title,
        "authors": authors,
        "language": language,
        "format": fmt,
        "path": path,
        "downloaded_at": downloaded_at,
    }
    save(lib)


def remove(book_id):
    lib = load()
    entry = lib.pop(str(book_id), None)
    if entry is not None:
        save(lib)
    return entry
