# gutenkit

A small, headless CLI for browsing and downloading free books from several sources:

- **[Project Gutenberg](https://www.gutenberg.org)** — ~75k mostly-English public-domain
  books, via the [Gutendex](https://gutendex.com) JSON API (`txt`, `epub`).
- **[Standard Ebooks](https://standardebooks.org)** — carefully typeset public-domain
  classics (`epub`, rendered to text for reading).
- **[Wikisource](https://wikisource.org)** — the free library, one wiki per language
  (English, Latin, Greek, …); works assembled to `epub` via ws-export.
- **[Perseus](https://www.perseus.tufts.edu)** — the canonical Greek & Latin corpora as
  TEI, rendered to plain text (original-language editions, often with translations).

Standard library only — no third-party dependencies. Pairs with [`txtread`](#reading)
for place-remembering reading.

## Install

```sh
pip install --user -e ~/armstrong/gutenkit    # or, from the repo:  make install
```

This puts a `gutenkit` command on your PATH (via `~/.local/bin`). You can also run it
without installing via `python -m gutenkit`. Run `make` (or `make help`) for the other
chores: `check` (byte-compile), `test` (offline smoke), `index`, `completions`, `clean`.

## Book ids (uids)

Every book has a source-qualified id, or **uid**: `source:local_id`.

```
gutenberg:1342
standardebooks:jane-austen/pride-and-prejudice
perseus:tlg0012.tlg001
```

A bare number with no prefix means Project Gutenberg, so `gutenkit get 1342` still works.

## Usage

```sh
gutenkit sources                            # list sources and their aliases

# search — Project Gutenberg only by default
gutenkit search "pride and prejudice"
gutenkit search --topic detective --lang en
gutenkit search dickens --sort popular --limit 20 --page 2

# search across sources (or a subset); aliases: gb, se, perseus, ...
gutenkit search "jane austen" --source gutenberg,standardebooks
gutenkit search homer --source perseus --lang grc
gutenkit search cicero --source perseus --lang la
gutenkit search "bello gallico" --source wikisource --lang la
gutenkit search austen --source all

# details / download / read — by uid
gutenkit info perseus:tlg0012.tlg001
gutenkit get 1342                           # Gutenberg, txt by default
gutenkit get standardebooks:jane-austen/pride-and-prejudice   # epub by default
gutenkit get perseus:tlg0012.tlg001 --read  # download then open in txtread

gutenkit library                            # list what you've downloaded
gutenkit read gutenberg:1342
gutenkit remove standardebooks:jane-austen/pride-and-prejudice --delete-file

gutenkit search dickens --json              # machine-readable output
```

## Perseus (Greek & Latin)

Perseus needs a one-time local catalogue, built from the two canonical corpora
(streams ~130 MB of TEI metadata from GitHub, then caches a small index):

```sh
gutenkit index perseus            # build once
gutenkit index perseus --rebuild  # refresh later
```

After that, `search --source perseus` and `get perseus:…` work offline against the
cached catalogue (individual texts are fetched as raw TEI on `get`). Language codes:
`grc` (Ancient Greek), `la`/`lat` (Latin), `en`/`eng` (translations). `get` downloads the
original-language edition by default; pass an edition uid (e.g.
`perseus:tlg0012.tlg001.perseus-eng3`) to fetch a specific translation.

## Wikisource

Wikisource is one wiki per language; `--lang` picks the subdomain(s): `en`, `la`
(Latin), `el`/`grc` (Greek), and others pass through. Search hits both whole works and
chapter subpages. Downloads go through the ws-export service, which assembles a work
(following its subpages) into an EPUB; the author is read back from that EPUB.

Note: ws-export can only assemble what the page transcludes or links as subpages. A
well-structured edition comes through complete; a portal/"versions" landing page whose
contents live on separate top-level pages may yield only a thin file — in that case pick
the specific edition or subpage from the search results.

## Reading

`gutenkit get` / `gutenkit read` open books in `txtread`, which remembers your place
between sessions. `.txt` books open directly; EPUBs are rendered to plain text on the
fly (stdlib `zipfile` + `html.parser`) and cached; Perseus TEI is rendered to text on
download. No dependencies.

## Headless / scripting

Standard library only, so it runs on a bare headless box (RHEL/Rocky, Python 3.8+) with
no `pip install` of dependencies. `--json` on `search`/`info`/`library`/`sources` gives
parseable output for pipelines. Bash completion in
[`completions/gutenkit.bash`](completions/gutenkit.bash):

```sh
cp completions/gutenkit.bash /etc/bash_completion.d/gutenkit   # or source it from ~/.bashrc
```

## Where things live

- Downloaded files: `~/Books/gutenberg/` (override with `GUTENKIT_BOOKS_DIR`)
- Library index: `~/.local/share/gutenkit/library.json`
- EPUB text cache: `~/.local/share/gutenkit/cache/`
- Perseus catalogue: `~/.local/share/gutenkit/perseus-catalog.json`

## Adding a source

Each source is a `Provider` subclass in [`gutenkit/providers/`](gutenkit/providers/) that
maps the source's catalogue onto a normalized record and implements `search`, `by_id`, and
`download`. Register it in [`gutenkit/providers/__init__.py`](gutenkit/providers/__init__.py).

## License

MIT
