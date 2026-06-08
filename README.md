# duplicate-file-finder

A fast Python CLI that scans directories for duplicate files using MD5 hashing and reports or deletes them.

## Features

- Recursive scan of one or more directories
- Three-pass hashing (size → 64 KB partial hash → full MD5) for minimal I/O
- Coloured table report: hash, file size, copy count, wasted space
- `--delete` to remove duplicates, `--dry-run` for a safe preview
- `--min-size` to skip files below a byte threshold
- Gracefully handles permission errors, symlinks, hard links, and empty files

## Requirements

- Python 3.9+
- [`rich`](https://github.com/Textualize/rich) ≥ 13.0

## Installation

```bash
git clone https://github.com/madnihamza1841/duplicate-file-finder.git
cd duplicate-file-finder
pip install .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

## Usage

```
dupfind [-h] [--delete] [--dry-run] [--min-size BYTES]
        [--output {table,paths}]
        DIR [DIR ...]
```

### Scan a directory and see a report

```
$ dupfind ~/Downloads

                            Duplicate Files
╭──────┬───────────────┬────────┬────────┬─────────┬───────────────────────────╮
│ #    │ MD5 (first 8) │   Size │ Copies │  Wasted │ Paths                     │
├──────┼───────────────┼────────┼────────┼─────────┼───────────────────────────┤
│ 1    │ a3f2c1b0      │ 4.2 MB │      2 │  4.2 MB │ /home/user/Downloads/     │
│      │               │        │        │         │   report_final.pdf        │
│      │               │        │        │         │   report_final_copy.pdf   │
├──────┼───────────────┼────────┼────────┼─────────┼───────────────────────────┤
│ 2    │ 9e1d04f7      │ 1.1 MB │      1 │  1.1 MB │ /home/user/Downloads/     │
│      │               │        │        │         │   photo.jpg               │
│      │               │        │        │         │   photo (1).jpg           │
╰──────┴───────────────┴────────┴────────┴─────────┴───────────────────────────╯

Found 2 duplicate group(s), 3 redundant file(s), 5.3 MB wasted.
```

### Preview what would be deleted (safe)

```bash
dupfind ~/Downloads --dry-run
```

### Delete duplicates (keeps the first copy found)

```bash
dupfind ~/Downloads --delete
```

### Skip files smaller than 1 MB

```bash
dupfind ~/Downloads --min-size 1048576
```

### Scan multiple directories

```bash
dupfind ~/Documents ~/Downloads ~/Desktop
```

### Output plain paths (for scripting)

```bash
dupfind ~/Downloads --output paths | xargs rm
```

## Running tests

```bash
pytest tests/ --cov=dupfinder
```

Expected: ≥80% coverage, all tests pass.
