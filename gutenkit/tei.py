"""Render a TEI/EpiDoc XML document (as used by the Perseus canonical corpora)
to readable plain text, using only the standard library.

TEI wraps the work in <TEI><text><body>…; the body holds structural elements
(<div> books/sections, <l> verse lines, <p> prose, <lg> stanzas, <head>
headings, <sp>/<speaker> for drama). Editorial apparatus (<note>, variant
<rdg>, <bibl>) is dropped so the reading text comes through clean."""

import xml.etree.ElementTree as ET

# Subtrees to drop entirely (editorial/critical apparatus, not reading text).
_SKIP = {
    "teiheader", "note", "rdg", "bibl", "ref", "figure", "figdesc",
    "gap", "del", "milestone", "pb", "cb", "fw",
}
# Elements set off by a blank line (prose paragraphs, section/stanza groups).
_PARA = {"p", "head", "div", "lg", "sp", "stage", "table", "ab"}
# Elements that occupy their own line, single-spaced (verse lines, list items).
_LINE = {"l", "lb", "item", "label", "speaker", "row"}


class TeiError(Exception):
    pass


def _local(el):
    tag = el.tag
    return tag.split("}")[-1].lower() if isinstance(tag, str) else ""


def _emit(parts, text):
    """Append a text node, folding its own newlines/tabs to spaces so that only
    our structural separators create line breaks (TEI expresses structure with
    elements, not source whitespace)."""
    if text:
        parts.append(text.replace("\n", " ").replace("\r", " ").replace("\t", " "))


def _walk(el, parts):
    tag = _local(el)
    if tag in _SKIP:
        _emit(parts, el.tail)
        return
    # Paragraph-like elements get a blank line before them; line-like elements
    # get a single newline after. Keeping the breaks asymmetric stops adjacent
    # verse lines from ending up double-spaced.
    open_sep = "\n\n" if tag in _PARA else ""
    close_sep = "\n" if tag in _LINE else ""
    if open_sep:
        parts.append(open_sep)
    _emit(parts, el.text)
    for child in el:
        _walk(child, parts)
    if close_sep:
        parts.append(close_sep)
    _emit(parts, el.tail)


def _find_body(root):
    for el in root.iter():
        if _local(el) == "body":
            return el
    for el in root.iter():
        if _local(el) == "text":
            return el
    return root


def _collapse(raw):
    out, blanks = [], 0
    for line in raw.splitlines():
        line = " ".join(line.split())  # squeeze inner whitespace
        if not line:
            blanks += 1
            if blanks <= 1:
                out.append("")
        else:
            blanks = 0
            out.append(line)
    return "\n".join(out).strip()


def to_text(xml_source):
    """Render TEI given as a str or bytes. Returns plain text."""
    try:
        if isinstance(xml_source, bytes):
            root = ET.fromstring(xml_source)
        else:
            root = ET.fromstring(xml_source.encode("utf-8"))
    except ET.ParseError as e:
        raise TeiError(f"invalid TEI XML: {e}") from e
    parts = []
    _walk(_find_body(root), parts)
    text = _collapse("".join(parts))
    if not text:
        raise TeiError("no readable text found in TEI body")
    return text + "\n"
