"""Core hashing and directory-walking logic."""

import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from dupfinder.models import DuplicateGroup

logger = logging.getLogger(__name__)

CHUNK = 65_536       # 64 KB — read chunk and pre-hash window size
PRE_HASH_SIZE = CHUNK


def _md5_partial(path: Path, max_bytes: int = PRE_HASH_SIZE) -> str | None:
    """Return MD5 of the first *max_bytes* of *path*, or None on error."""
    h = hashlib.md5()
    try:
        with path.open("rb") as fh:
            data = fh.read(max_bytes)
            h.update(data)
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None
    return h.hexdigest()


def md5_of_file(path: Path) -> str | None:
    """Return the full hex MD5 digest of *path*, or None on I/O error."""
    h = hashlib.md5()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(CHUNK), b""):
                h.update(chunk)
    except OSError as exc:
        logger.warning("Cannot hash %s: %s", path, exc)
        return None
    return h.hexdigest()


def walk_files(directories: list[Path], min_size: int = 1) -> list[Path]:
    """Recursively collect regular, non-symlink files that meet *min_size*.

    Skips unreadable directories gracefully and deduplicates inodes so
    hard-linked files are not double-counted.
    """
    seen_inodes: set[int] = set()
    result: list[Path] = []

    for base in directories:
        try:
            entries = list(base.rglob("*"))
        except PermissionError as exc:
            logger.warning("Cannot scan %s: %s", base, exc)
            continue

        for p in entries:
            # Skip symlinks — they are not true duplicates
            if p.is_symlink():
                continue
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError as exc:
                logger.warning("Cannot stat %s: %s", p, exc)
                continue

            # Deduplicate hard links by inode
            inode = (st.st_dev, st.st_ino)
            if inode in seen_inodes:
                continue
            seen_inodes.add(inode)

            if st.st_size < min_size:
                continue

            result.append(p)

    return result


def find_duplicates(
    directories: list[Path], min_size: int = 1
) -> list[DuplicateGroup]:
    """Scan *directories* and return groups of files with identical content.

    Uses a three-pass strategy to minimise I/O:
      1. Group by file size — unique sizes cannot be duplicates.
      2. Group by 64 KB partial hash — filters out most non-matches cheaply.
      3. Full MD5 hash only on remaining candidates.
    """
    files = walk_files(directories, min_size=min_size)

    # Pass 1: group by size
    by_size: dict[int, list[Path]] = defaultdict(list)
    for p in files:
        try:
            by_size[p.stat().st_size].append(p)
        except OSError:
            continue

    # Pass 2: partial hash to rule out non-duplicates cheaply
    by_partial: dict[str, list[Path]] = defaultdict(list)
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        for p in candidates:
            digest = _md5_partial(p)
            if digest is not None:
                by_partial[f"{size}:{digest}"].append(p)

    # Pass 3: full hash only on partial-hash matches
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for key, candidates in by_partial.items():
        if len(candidates) < 2:
            continue
        for p in candidates:
            digest = md5_of_file(p)
            if digest is not None:
                by_hash[digest].append(p)

    groups: list[DuplicateGroup] = []
    for digest, paths in by_hash.items():
        if len(paths) < 2:
            continue
        try:
            size = paths[0].stat().st_size
        except OSError:
            continue
        groups.append(DuplicateGroup(md5=digest, size=size, paths=paths))

    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return groups
