# CBZ Page Replacer

A small macOS app for replacing existing pages in a CBZ archive.

## Build and use

From this directory, run:

```zsh
./build-app.sh
```

Open `CBZ Page Replacer.app`, then drag one `.cbz` plus one or more replacement image files into its window.

The filename must already appear exactly once in the archive. For example, dropping `001.jpg` together with `Venom - The Enemy Within (1994) - 001.cbz` replaces that archive's `001.jpg`. It refuses missing or ambiguous names and rebuilds the archive in a temporary file beside the original before atomically replacing it, so an error leaves the original archive untouched.
