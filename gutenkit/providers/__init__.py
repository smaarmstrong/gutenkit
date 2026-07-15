"""Source providers and the registry the CLI talks to.

A *uid* is a source-qualified book id, e.g. ``gutenberg:1342`` or
``perseus:tlg0012.tlg001``. A bare id with no ``source:`` prefix is treated as
Project Gutenberg, so old-style ``gutenkit get 1342`` keeps working."""

from .base import Provider, ProviderError, make_record  # noqa: F401
from .gutenberg import Gutenberg
from .perseus import Perseus
from .standardebooks import StandardEbooks

DEFAULT_SOURCE = "gutenberg"

# Registration order = display order in aggregated search.
_PROVIDERS = [Gutenberg(), StandardEbooks(), Perseus()]

_BY_NAME = {}
for _p in _PROVIDERS:
    _BY_NAME[_p.name] = _p
    for _a in _p.aliases:
        _BY_NAME[_a] = _p


def all_providers():
    return list(_PROVIDERS)


def get(name):
    """Resolve a provider by canonical name or alias."""
    try:
        return _BY_NAME[name]
    except KeyError:
        known = ", ".join(p.name for p in _PROVIDERS)
        raise ProviderError(f"unknown source '{name}'. Known: {known}, all")


def parse_uid(raw, default=DEFAULT_SOURCE):
    """Split 'source:local_id' -> (source, local_id). Bare id -> default source.
    Only the first colon separates them (Perseus/edition ids contain none, but
    be safe)."""
    if ":" in raw:
        source, local_id = raw.split(":", 1)
        return source, local_id
    return default, raw


def select(spec):
    """Turn a --source spec into a list of providers.

    None            -> [default provider only] (fast, matches old behaviour)
    "all"           -> every registered provider
    "gb,se,perseus" -> the named ones, de-duplicated, in registration order
    """
    if spec is None:
        return [_BY_NAME[DEFAULT_SOURCE]]
    names = [n.strip() for n in spec.split(",") if n.strip()]
    if "all" in names:
        return list(_PROVIDERS)
    chosen = []
    for n in names:
        p = get(n)
        if p not in chosen:
            chosen.append(p)
    return chosen
