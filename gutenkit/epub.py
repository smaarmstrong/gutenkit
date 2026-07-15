"""Convert an EPUB to plain text using only the standard library.

An EPUB is a zip: META-INF/container.xml points at an OPF package file, whose
<spine> lists the reading order of (X)HTML documents in the <manifest>. We walk
the spine, strip each document's markup, and concatenate. No third-party deps."""

import posixpath
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote

# Tags whose boundaries imply a line break in plain text.
_BLOCK = {
    "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "blockquote", "section", "article", "hr", "pre",
}
# Tags whose contents should be dropped entirely.
_SKIP = {"script", "style", "head", "title"}


class EpubError(Exception):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        out, blanks = [], 0
        for line in raw.splitlines():
            line = line.rstrip()
            if not line.strip():
                blanks += 1
                if blanks <= 1:
                    out.append("")
            else:
                blanks = 0
                out.append(line)
        return "\n".join(out).strip()


def _localname(el):
    return el.tag.split("}")[-1]


def _opf_path(zf):
    try:
        with zf.open("META-INF/container.xml") as f:
            tree = ET.parse(f)
    except KeyError:
        raise EpubError("not a valid EPUB (no META-INF/container.xml)")
    for el in tree.getroot().iter():
        if _localname(el) == "rootfile" and el.get("full-path"):
            return el.get("full-path")
    raise EpubError("EPUB container declares no package document")


def _spine_hrefs(zf, opf_path):
    with zf.open(opf_path) as f:
        root = ET.parse(f).getroot()
    manifest, spine = {}, []
    for el in root.iter():
        name = _localname(el)
        if name == "item":
            manifest[el.get("id")] = el.get("href")
        elif name == "itemref":
            spine.append(el.get("idref"))
    base = posixpath.dirname(opf_path)
    hrefs = []
    for idref in spine:
        href = manifest.get(idref)
        if href:
            hrefs.append(posixpath.normpath(posixpath.join(base, unquote(href))))
    return hrefs


def opf_metadata(epub_path):
    """Return {"title", "creator"} from the EPUB's Dublin Core metadata, as
    available. Best-effort: returns {} if the file can't be read."""
    try:
        with zipfile.ZipFile(epub_path) as zf:
            with zf.open(_opf_path(zf)) as f:
                root = ET.parse(f).getroot()
    except (KeyError, zipfile.BadZipFile, ET.ParseError, EpubError):
        return {}
    meta = {}
    for el in root.iter():
        name = _localname(el)
        if name in ("title", "creator") and name not in meta and (el.text or "").strip():
            meta[name] = el.text.strip()
    return meta


def to_text(epub_path):
    """Return the full text of an EPUB in spine order."""
    try:
        with zipfile.ZipFile(epub_path) as zf:
            names = set(zf.namelist())
            hrefs = _spine_hrefs(zf, _opf_path(zf))
            chunks = []
            for href in hrefs:
                if href not in names:
                    continue
                with zf.open(href) as f:
                    doc = f.read().decode("utf-8", "replace")
                ex = _TextExtractor()
                ex.feed(doc)
                chunk = ex.text()
                if chunk.strip():
                    chunks.append(chunk)
    except zipfile.BadZipFile:
        raise EpubError("file is not a valid zip/EPUB")
    if not chunks:
        raise EpubError("no readable text found in EPUB")
    return "\n\n\n".join(chunks) + "\n"
