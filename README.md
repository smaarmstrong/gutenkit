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
```

## Reading

`gutenkit get` / `gutenkit read` open `.txt` books in `txtread`, which remembers your
place between sessions. EPUBs are downloaded but not opened by `txtread`.

## Where things live

- Downloaded files: `~/Books/gutenberg/` (override with `GUTENKIT_BOOKS_DIR`)
- Library index: `~/.local/share/gutenkit/library.json`

## License

MIT
