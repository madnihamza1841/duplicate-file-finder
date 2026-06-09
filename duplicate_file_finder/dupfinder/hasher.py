"""Core hashing and directory-walking logic.

This module implements the three-pass duplicate-detection strategy:

1. **Size filter** — files with unique sizes cannot be duplicates and are
   eliminated immediately without reading any file content.
2. **Partial hash** — for size-collision candidates, only the first 64 KB
   is hashed. This rules out the vast majority of false positives cheaply
   (e.g. two large files that differ early on).
3. **Full MD5 hash** — only files that survive both earlier filters receive
   a complete hash, minimising total I/O on large directory trees.

Logging uses the standard ``logging`` module at WARNING level for
recoverable problems (unreadable files, permission errors) so the caller
decides how and whether to surface them.
"""

import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from dupfinder.models import DuplicateGroup

logger = logging.getLogger(__name__)

CHUNK: int = 65_536
"""Read buffer size and partial-hash window: 64 KB."""

PRE_HASH_SIZE: int = CHUNK
"""Number of bytes read for the fast partial-hash pre-filter."""


def _md5_partial(path: Path, max_bytes: int = PRE_HASH_SIZE) -> str | None:
    """Return the MD5 digest of the first *max_bytes* of *path*.

    Used as a cheap pre-filter: if two files differ within the first 64 KB
    they cannot be identical, so a full hash is unnecessary.

    Args:
        path:      Path to the file to hash.
        max_bytes: Maximum number of bytes to read (default: 64 KB).

    Returns:
        Hex MD5 string on success, or ``None`` if the file cannot be read.
    """
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
    """Return the full MD5 digest of *path* by reading it in 64 KB chunks.

    Args:
        path: Path to the file to hash.

    Returns:
        32-character hex MD5 string on success, or ``None`` on any I/O error
        (permission denied, file disappeared mid-scan, etc.).
    """
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
    """Recursively collect all regular files across *directories*.

    The walk applies three filters before a file is added to the result:

    * **Symlinks** are skipped — following them could escape the intended
      scan scope and would report links as duplicates of their targets.
    * **Hard links** sharing the same ``(device, inode)`` pair are
      deduplicated so the same physical file is never counted twice.
    * **Small files** below *min_size* bytes are excluded (default 1 byte,
      which skips empty files).

    Directories that raise ``PermissionError`` are logged and skipped so
    the scan continues rather than crashing.

    Args:
        directories: List of root directories to scan recursively.
        min_size:    Minimum file size in bytes to include (default: 1).

    Returns:
        Deduplicated list of Path objects for qualifying files.
    """
    seen_inodes: set[tuple[int, int]] = set()
    result: list[Path] = []

    for base in directories:
        try:
            entries = list(base.rglob("*"))
        except PermissionError as exc:
            logger.warning("Cannot scan %s: %s", base, exc)
            continue

        for p in entries:
            if p.is_symlink():
                continue
            if not p.is_file():
                continue
            try:
                st = p.stat()
            except OSError as exc:
                logger.warning("Cannot stat %s: %s", p, exc)
                continue

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

    Runs the three-pass pipeline (size → partial hash → full MD5) to find
    every set of two or more files that share the same byte content.
    Results are sorted by wasted space descending so the most impactful
    groups appear first.

    Args:
        directories: One or more root directories to scan recursively.
        min_size:    Skip files strictly smaller than this many bytes.
                     Default is 1, which skips empty files. Pass 0 to
                     include empty files (all empty files share the same
                     hash and will form one group).

    Returns:
        List of :class:`~dupfinder.models.DuplicateGroup` objects, each
        containing the shared MD5, file size, and all duplicate paths.
        Returns an empty list when no duplicates are found.

    Example:
        >>> from pathlib import Path
        >>> groups = find_duplicates([Path("/home/user/Downloads")])
        >>> for g in groups:
        ...     print(g.md5, g.wasted_bytes, g.paths)
    """
    files = walk_files(directories, min_size=min_size)

    # Pass 1: group by file size — only files of the same size can be duplicates
    by_size: dict[int, list[Path]] = defaultdict(list)
    for p in files:
        try:
            by_size[p.stat().st_size].append(p)
        except OSError:
            continue

    # Pass 2: cheap partial hash to eliminate most false positives
    by_partial: dict[str, list[Path]] = defaultdict(list)
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        for p in candidates:
            digest = _md5_partial(p)
            if digest is not None:
                by_partial[f"{size}:{digest}"].append(p)

    # Pass 3: full hash only on survivors of the partial-hash filter
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for _key, candidates in by_partial.items():
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
