# gutenkit

A small, headless CLI for browsing and downloading [Project Gutenberg](https://www.gutenberg.org)
books, using the [Gutendex](https://gutendex.com) JSON API. Standard library only —
no third-party dependencies. Pairs with [`txtread`](#reading) for place-remembering reading.

## Install

```sh
pip install --user -e ~/armstrong/gutenkit
```

This puts a `gutenkit` command on your PATH (via `~/.local/bin`). You can also run it
without installing via `python -m gutenkit`.

## Usage

```sh
gutenkit search "pride and prejudice"      # search title/author
gutenkit search --topic detective --lang en
gutenkit search dickens --sort popular --limit 20 --page 2

gutenkit info 1342                          # details for a book id
gutenkit get 1342                           # download (txt by default)
gutenkit get 1342 --format epub
gutenkit get 1342 --read                    # download then open in txtread

gutenkit library                            # list what you've downloaded
gutenkit read 1342                          # open a downloaded book in txtread
gutenkit remove 1342 --delete-file

gutenkit search dickens --json              # machine-readable output
gutenkit info 1342 --json
gutenkit library --json
```

## Reading

`gutenkit get` / `gutenkit read` open books in `txtread`, which remembers your place
between sessions. `.txt` books open directly; EPUBs are rendered to plain text on the
fly (stdlib `zipfile` + `html.parser` — no dependencies) and cached, then opened in
`txtread` too.

## Headless / scripting

Standard library only, so it runs on a bare headless box (RHEL/Rocky, Python 3.8+) with
no `pip install` of dependencies. `--json` on `search`/`info`/`library` gives parseable
output for pipelines. Bash completion in [`completions/gutenkit.bash`](completions/gutenkit.bash):

```sh
cp completions/gutenkit.bash /etc/bash_completion.d/gutenkit   # or source it from ~/.bashrc
```

## Where things live

- Downloaded files: `~/Books/gutenberg/` (override with `GUTENKIT_BOOKS_DIR`)
- Library index: `~/.local/share/gutenkit/library.json`
- EPUB text cache: `~/.local/share/gutenkit/cache/`

## License

MIT
