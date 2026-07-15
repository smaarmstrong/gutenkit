"""Perseus Digital Library — the canonical Greek and Latin corpora, as TEI XML
hosted on GitHub. Original-language texts (and often English translations).

The Scaife CTS API is unreliable, so the searchable catalogue is built once from
the two canonical repos' tarballs (extracting only the small __cts__.xml
metadata files) and cached. Individual works are then fetched as raw TEI and
rendered to text on demand."""

import json
import os
import tarfile
import xml.etree.ElementTree as ET

from . import base
from .. import library, tei

REPOS = {
    "greekLit": "canonical-greekLit",
    "latinLit": "canonical-latinLit",
}
TARBALL = "https://codeload.github.com/PerseusDL/{repo}/tar.gz/refs/heads/master"
RAW = "https://raw.githubusercontent.com/PerseusDL/{repo}/master/{path}"

CATALOG_PATH = os.path.join(library.DATA_DIR, "perseus-catalog.json")

# Map gutenkit --lang codes onto Perseus's ISO-639-3-ish codes.
_LANG_ALIASES = {
    "la": "lat", "lat": "lat", "latin": "lat",
    "grc": "grc", "el": "grc", "gr": "grc", "greek": "grc",
    "en": "eng", "eng": "eng",
}


def _local(el):
    return el.tag.split("}")[-1].lower()


def _xml_lang(el):
    for k, v in el.attrib.items():
        if k.split("}")[-1] == "lang":
            return v
    return ""


def _pick_text(elems):
    """From several <title>/<groupname> variants, prefer an English label."""
    best = None
    for e in elems:
        txt = (e.text or "").strip()
        if not txt:
            continue
        if best is None:
            best = txt
        if _xml_lang(e).startswith("en"):
            return txt
    return best


def _urn_parts(urn):
    # urn:cts:greekLit:tlg0012.tlg001[.perseus-grc2]
    bits = urn.split(":")
    return bits[2], bits[3]  # namespace, id-tail


# --- catalogue building ----------------------------------------------------

def _parse_cts(data):
    """Parse one __cts__.xml blob -> ("textgroup", ns, tgid, name)
    or ("work", entry-dict) or None."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    kind = _local(root)
    if kind == "textgroup":
        ns, tgid = _urn_parts(root.get("urn", "::"))
        names = [e for e in root if _local(e) == "groupname"]
        return ("textgroup", ns, tgid, _pick_text(names) or tgid)
    if kind == "work":
        ns, workid = _urn_parts(root.get("urn", "::"))
        titles = [e for e in root if _local(e) == "title"]
        editions = []
        for e in root:
            k = _local(e)
            if k in ("edition", "translation"):
                _, eid = _urn_parts(e.get("urn", "::"))
                editions.append({
                    "id": eid,
                    "lang": _xml_lang(e) or eid.split("-")[-1][:3],
                    "kind": k,
                })
        entry = {
            "urn": workid,
            "namespace": ns,
            "lang": _xml_lang(root) or (editions[0]["lang"] if editions else ""),
            "title": _pick_text(titles) or workid,
            "editions": editions,
        }
        return ("work", entry)
    return None


def build_index(*, log=lambda m: None):
    """Stream both canonical tarballs, extract __cts__.xml, write the catalogue."""
    textgroups = {}   # "ns:tgid" -> author name
    works = {}        # workid -> entry
    for ns, repo in REPOS.items():
        log(f"Indexing {repo} (streaming tarball, this is the slow part)…")
        url = TARBALL.format(repo=repo)
        with base._open(url, timeout=300) as resp:
            with tarfile.open(fileobj=resp, mode="r|gz") as tar:
                for member in tar:
                    if not member.isfile() or not member.name.endswith("__cts__.xml"):
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    parsed = _parse_cts(f.read())
                    if not parsed:
                        continue
                    if parsed[0] == "textgroup":
                        _, tg_ns, tgid, name = parsed
                        textgroups[f"{tg_ns}:{tgid}"] = name
                        continue
                    entry = parsed[1]
                    works[entry["urn"]] = entry
    # Attach author names.
    for workid, entry in works.items():
        tgid = workid.split(".")[0]
        entry["author"] = textgroups.get(f"{entry['namespace']}:{tgid}", tgid)
    os.makedirs(library.DATA_DIR, exist_ok=True)
    tmp = CATALOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(works, fh)
    os.replace(tmp, CATALOG_PATH)
    log(f"Perseus index built: {len(works)} works.")
    return works


def _load_catalog():
    try:
        with open(CATALOG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return None


def _to_record(entry, *, prefer_edition=None):
    langs = sorted({entry.get("lang", "")} | {e["lang"] for e in entry["editions"]})
    return base.make_record(
        Perseus.name, entry["urn"],
        title=entry["title"],
        authors=entry.get("author", "Unknown"),
        languages=[l for l in langs if l],
        formats=["txt"],
        extra={
            "namespace": entry["namespace"],
            "editions": entry["editions"],
            "work_lang": entry.get("lang", ""),
            "prefer_edition": prefer_edition,
        },
    )


class Perseus(base.Provider):
    name = "perseus"
    label = "Perseus (Greek & Latin)"
    aliases = ("pdl", "classics")
    default_format = "txt"
    formats_help = "txt (rendered from TEI); needs one-time `gutenkit index perseus`"

    def _catalog_or_die(self):
        cat = _load_catalog()
        if cat is None:
            raise base.ProviderError(
                "Perseus index not built yet. Run once:  gutenkit index perseus"
            )
        return cat

    def search(self, query, *, topic=None, languages=None, sort=None,
               page=1, limit=15):
        cat = self._catalog_or_die()
        wanted_langs = None
        if languages:
            wanted_langs = {_LANG_ALIASES.get(l.strip(), l.strip())
                            for l in languages.split(",")}
        q = (query or topic or "").lower()
        hits = []
        for entry in cat.values():
            if wanted_langs:
                entry_langs = {entry.get("lang", "")} | {e["lang"] for e in entry["editions"]}
                if not (wanted_langs & entry_langs):
                    continue
            if q:
                hay = f"{entry['title']} {entry.get('author', '')} {entry['urn']}".lower()
                if q not in hay:
                    continue
            hits.append(entry)
        hits.sort(key=lambda e: (e.get("author", ""), e["title"]))
        results = [_to_record(e) for e in hits[:limit]]
        return {"count": len(hits), "results": results, "has_more": len(hits) > limit}

    def by_id(self, local_id):
        cat = self._catalog_or_die()
        prefer = None
        workid = local_id
        parts = local_id.split(".")
        if len(parts) >= 3:  # an edition urn was given
            workid = ".".join(parts[:2])
            prefer = local_id
        entry = cat.get(workid)
        return _to_record(entry, prefer_edition=prefer) if entry else None

    def _choose_edition(self, record):
        eds = record["extra"]["editions"]
        prefer = record["extra"].get("prefer_edition")
        if prefer:
            for e in eds:
                if e["id"] == prefer:
                    return e
        work_lang = record["extra"].get("work_lang")
        # Prefer an original-language critical edition over a translation.
        for e in eds:
            if e["kind"] == "edition" and e["lang"] == work_lang:
                return e
        for e in eds:
            if e["kind"] == "edition":
                return e
        return eds[0] if eds else None

    def download(self, record, fmt, dest_path):
        if fmt != "txt":
            raise base.ProviderError("Perseus provides plain text only: --format txt")
        ed = self._choose_edition(record)
        if not ed:
            raise base.ProviderError(f"no TEI edition listed for {record['uid']}")
        ns = record["extra"]["namespace"]
        tgid, work = record["local_id"].split(".")[:2]
        path = f"data/{tgid}/{work}/{ed['id']}.xml"
        url = RAW.format(repo=REPOS.get(ns, f"canonical-{ns}"), path=path)
        xml = base.http_text(url, timeout=60)
        try:
            text = tei.to_text(xml)
        except tei.TeiError as e:
            raise base.ProviderError(f"could not render TEI: {e}") from e
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        header = f"{record['title']} — {record['authors']}  [{ed['id']}]\n\n\n"
        with open(dest_path, "w", encoding="utf-8") as fh:
            fh.write(header + text)
