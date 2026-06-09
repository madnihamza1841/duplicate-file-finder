# duplicate-file-finder

A fast command-line tool for finding and optionally removing duplicate files.
It scans one or more directories recursively, identifies files with identical
content using MD5 hashing, and presents a clear summary of every duplicate
group — including how much disk space is being wasted.

---

## How it works

Duplicate detection runs in three passes to keep disk I/O as low as possible:

1. **Size filter** — files with a unique size are immediately ruled out. Two
   files cannot be identical if they differ in length.
2. **64 KB partial hash** — for files that share a size, only the first 64 KB
   is hashed. This eliminates most false positives (e.g. two large log files
   that diverge early) without reading each file in full.
3. **Full MD5 hash** — only the survivors of pass 2 receive a complete hash,
   confirming byte-for-byte identity.

---

## Requirements

- Python 3.9 or later
- [`rich`](https://github.com/Textualize/rich) ≥ 13.0 (installed automatically)

---

## Installation

Clone the repository and install with pip:

```bash
git clone https://github.com/madnihamza1841/duplicate-file-finder.git
cd duplicate-file-finder
pip install .
```

For development (adds pytest and coverage):

```bash
pip install -e ".[dev]"
```

After installation the `dupfind` command is available on your PATH.

---

## Usage

```
dupfind [-h] [--delete] [--dry-run] [--min-size BYTES]
        [--output {table,paths}]
        DIR [DIR ...]
```

| Flag | Description |
|---|---|
| `DIR [DIR …]` | One or more directories to scan (required) |
| `--delete` | Delete duplicates, keeping the first copy found |
| `--dry-run` | Show what *would* be deleted — does not touch any file |
| `--min-size BYTES` | Skip files smaller than BYTES (default: 1, skips empty files) |
| `--output table` | Coloured summary table (default) |
| `--output paths` | Plain file paths, one per line — suitable for scripting |

---

## Scenarios

### 1. Scan a single directory

```bash
dupfind ~/Downloads
```

Scans `~/Downloads` recursively and prints a table of every duplicate group.

---

### 2. Scan multiple directories at once

```bash
dupfind ~/Documents ~/Downloads ~/Desktop
```

Files are deduplicated across all supplied directories. A file in `~/Documents`
that is identical to one in `~/Downloads` will appear in the same group.

---

### 3. Preview deletions safely with --dry-run

```bash
dupfind ~/Downloads --dry-run
```

Prints exactly which files *would* be removed (all paths except the first in
each group) without deleting anything. Use this before `--delete`.

---

### 4. Delete duplicates, keeping one copy

```bash
dupfind ~/Downloads --delete
```

Removes all but the first path listed in each group. The tool prints a
confirmation line for every file it deletes.

---

### 5. Skip small files with --min-size

```bash
# Ignore files smaller than 1 MB
dupfind ~/Downloads --min-size 1048576

# Include empty files (default skips them)
dupfind ~/Downloads --min-size 0
```

Useful for ignoring lock files, thumbnails, or other tiny artefacts that are
intentionally identical across many locations.

---

### 6. Pipe duplicate paths to another command

```bash
# Print bare paths and delete them with xargs
dupfind ~/Downloads --output paths | xargs rm

# Move duplicates to a trash folder instead of deleting
dupfind ~/Downloads --output paths | xargs -I{} mv {} ~/.Trash/
```

`--output paths` suppresses the table and prints one redundant path per line,
making it easy to compose with standard Unix tools.

---

### 7. Redirect output to a report file

```bash
dupfind ~/Downloads --output paths > duplicate_report.txt
```

---

### 8. Combine flags: skip tiny files and do a dry run

```bash
dupfind ~/Documents ~/Downloads --min-size 4096 --dry-run
```

Only consider files ≥ 4 KB and show what would be deleted.

---

## Sample run on the included test data

The `sample_data/` folder in this repository contains a small tree of text
files and PNG images — several of which are intentional duplicates — to let
you try the tool right away.

### Directory layout

```
sample_data/
  photos/
    red_square.png       (122 B)  ← unique colour
    blue_square.png      (123 B)  ← duplicated in archive/ and backups/
    green_rect.png       (153 B)  ← unique
    yellow_square.png    (104 B)  ← unique
    description.txt      (238 B)  ← unique
  documents/
    project_notes.txt    (558 B)  ← duplicated in archive/ and backups/
    meeting_notes.txt    (380 B)  ← duplicated in archive/
    readme_draft.txt     (199 B)  ← unique
  backups/
    red_square_backup.png         ← duplicate of photos/red_square.png
    blue_backup.png               ← duplicate of photos/blue_square.png
    project_notes_backup.txt      ← duplicate of documents/project_notes.txt
  archive/
    blue_copy.png                 ← duplicate of photos/blue_square.png
    project_notes_old.txt         ← duplicate of documents/project_notes.txt
    meeting_notes_copy.txt        ← duplicate of documents/meeting_notes.txt
```

### Running the scan

```bash
dupfind sample_data
```

**Output:**

```
                            Duplicate Files
╭──────┬───────────────┬─────────┬────────┬─────────┬──────────────────────────╮
│ #    │ MD5 (first 8) │    Size │ Copies │  Wasted │ Paths                    │
├──────┼───────────────┼─────────┼────────┼─────────┼──────────────────────────┤
│ 1    │ 868b9988      │ 558.0 B │      2 │  1.1 KB │ sample_data/archive/     │
│      │               │         │        │         │   project_notes_old.txt  │
│      │               │         │        │         │ sample_data/documents/   │
│      │               │         │        │         │   project_notes.txt      │
│      │               │         │        │         │ sample_data/backups/     │
│      │               │         │        │         │   project_notes_backup.. │
├──────┼───────────────┼─────────┼────────┼─────────┼──────────────────────────┤
│ 2    │ 133e1ec0      │ 380.0 B │      1 │ 380.0 B │ sample_data/archive/     │
│      │               │         │        │         │   meeting_notes_copy.txt │
│      │               │         │        │         │ sample_data/documents/   │
│      │               │         │        │         │   meeting_notes.txt      │
├──────┼───────────────┼─────────┼────────┼─────────┼──────────────────────────┤
│ 3    │ 64d2310d      │ 123.0 B │      2 │ 246.0 B │ sample_data/archive/     │
│      │               │         │        │         │   blue_copy.png          │
│      │               │         │        │         │ sample_data/photos/      │
│      │               │         │        │         │   blue_square.png        │
│      │               │         │        │         │ sample_data/backups/     │
│      │               │         │        │         │   blue_backup.png        │
├──────┼───────────────┼─────────┼────────┼─────────┼──────────────────────────┤
│ 4    │ a173ed68      │ 122.0 B │      1 │ 122.0 B │ sample_data/photos/      │
│      │               │         │        │         │   red_square.png         │
│      │               │         │        │         │ sample_data/backups/     │
│      │               │         │        │         │   red_square_backup.png  │
╰──────┴───────────────┴─────────┴────────┴─────────┴──────────────────────────╯

Found 4 duplicate group(s), 6 redundant file(s), 1.8 KB wasted.
```

### Dry-run preview

```bash
dupfind sample_data --dry-run
```

```
[DRY-RUN] would delete sample_data/documents/project_notes.txt
[DRY-RUN] would delete sample_data/backups/project_notes_backup.txt
[DRY-RUN] would delete sample_data/documents/meeting_notes.txt
[DRY-RUN] would delete sample_data/photos/blue_square.png
[DRY-RUN] would delete sample_data/backups/blue_backup.png
[DRY-RUN] would delete sample_data/backups/red_square_backup.png
```

### Skip small files (--min-size 200)

```bash
dupfind sample_data --min-size 200
```

Only the two text-file groups (≥ 380 B) are reported; the small PNG duplicates
(122–123 B) are filtered out:

```
Found 2 duplicate group(s), 3 redundant file(s), 1.5 KB wasted.
```

### Plain-path output for scripting

```bash
dupfind sample_data --output paths
```

```
sample_data/documents/project_notes.txt
sample_data/backups/project_notes_backup.txt
sample_data/documents/meeting_notes.txt
sample_data/photos/blue_square.png
sample_data/backups/blue_backup.png
sample_data/backups/red_square_backup.png
```

---

## Running the tests

```bash
pytest tests/ -v --cov=dupfinder --cov-report=term-missing
```

The suite uses real temporary files (pytest `tmp_path` fixture) — no mocking.
Expected result: 25 tests pass, ≥ 80% coverage.

---

## Project structure

```
duplicate-file-finder/
├── dupfinder/
│   ├── __init__.py      Package marker
│   ├── models.py        DuplicateGroup dataclass
│   ├── hasher.py        File walker + three-pass MD5 engine
│   └── cli.py           argparse entry point + rich table renderer
├── tests/
│   ├── test_hasher.py   Unit tests for the hashing and walking logic
│   └── test_cli.py      Integration tests for the CLI layer
├── sample_data/         Ready-to-use test tree with intentional duplicates
├── pyproject.toml
├── README.md
└── CONTRIBUTING.md
```
