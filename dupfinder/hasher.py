"""Core hashing and directory-walking logic."""

import hashlib
from collections import defaultdict
from pathlib import Path

from dupfinder.models import DuplicateGroup

CHUNK = 65_536  # 64 KB read chunks


def md5_of_file(path: Path) -> str:
    """Return the hex MD5 digest of *path*."""
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(directories: list[Path], min_size: int = 0) -> list[Path]:
    """Recursively yield all regular files in *directories* that meet *min_size*."""
    seen: set[Path] = set()
    result: list[Path] = []
    for base in directories:
        for p in base.rglob("*"):
            if p.is_file() and not p.is_symlink():
                resolved = p.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                if p.stat().st_size >= min_size:
                    result.append(p)
    return result


def find_duplicates(
    directories: list[Path], min_size: int = 0
) -> list[DuplicateGroup]:
    """Scan *directories* and return groups of duplicate files."""
    files = walk_files(directories, min_size=min_size)

    # First pass: group by file size — files with unique sizes can't be duplicates
    by_size: dict[int, list[Path]] = defaultdict(list)
    for p in files:
        by_size[p.stat().st_size].append(p)

    # Second pass: hash only size-collision candidates
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        for p in candidates:
            digest = md5_of_file(p)
            by_hash[digest].append(p)

    groups: list[DuplicateGroup] = []
    for digest, paths in by_hash.items():
        if len(paths) < 2:
            continue
        size = paths[0].stat().st_size
        groups.append(DuplicateGroup(md5=digest, size=size, paths=paths))

    # Deterministic order: largest wasted space first
    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return groups
