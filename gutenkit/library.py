"""Local library: where downloaded books live and a JSON index of them.

Entries are keyed by *uid* ("gutenberg:1342", "perseus:tlg0012.tlg001", ...).
Older libraries keyed by bare integer Gutenberg ids are migrated on load."""

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
    text = text.replace("/", "-").replace(".", "-").replace(":", "-")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-") or "book"


def filename_for(source, local_id, title, ext):
    return f"{source}-{slugify(local_id)}-{slugify(title)}.{ext}"


def _read():
    try:
        with open(LIBRARY_JSON) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load():
    """Load the index, migrating any legacy integer-keyed entries to uids."""
    raw = _read()
    lib, changed = {}, False
    for key, entry in raw.items():
        uid = entry.get("uid")
        if not uid:
            uid = f"gutenberg:{key}"
            entry.update(uid=uid, source="gutenberg",
                         local_id=str(entry.get("id", key)))
            changed = True
        lib[uid] = entry
    if changed:
        save(lib)
    return lib


def save(lib):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = LIBRARY_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(lib, f, indent=2)
    os.replace(tmp, LIBRARY_JSON)


def get(uid):
    return load().get(uid)


def add(uid, *, source, local_id, title, authors, language, fmt, path,
        downloaded_at):
    lib = load()
    lib[uid] = {
        "uid": uid,
        "source": source,
        "local_id": local_id,
        "title": title,
        "authors": authors,
        "language": language,
        "format": fmt,
        "path": path,
        "downloaded_at": downloaded_at,
    }
    save(lib)


def remove(uid):
    lib = load()
    entry = lib.pop(uid, None)
    if entry is not None:
        save(lib)
    return entry
