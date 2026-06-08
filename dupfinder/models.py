"""Data models for the duplicate file finder.

This module defines the core data structures used to represent groups of
files that share identical content, as determined by MD5 hashing.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DuplicateGroup:
    """A set of files that share the same MD5 content hash.

    All files in a group have identical byte-for-byte content, regardless
    of their names, locations, or timestamps. The first path in `paths` is
    treated as the "keeper" when duplicates are deleted.

    Attributes:
        md5:   Full 32-character hex MD5 digest shared by all files in the group.
        size:  File size in bytes (identical for all members of the group).
        paths: List of absolute Path objects pointing to each duplicate file.
               Must contain at least two entries to form a valid group.

    Example:
        >>> group = DuplicateGroup(md5="abc123", size=1024, paths=[Path("a.jpg"), Path("b.jpg")])
        >>> group.copy_count
        1
        >>> group.wasted_bytes
        1024
    """

    md5: str
    size: int
    paths: list[Path] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        """Return the number of bytes consumed by redundant copies.

        Calculated as ``size * (number_of_paths - 1)`` because one copy
        must be kept while the rest are redundant.

        Returns:
            Wasted disk space in bytes, or 0 if only one path is present.
        """
        return self.size * (len(self.paths) - 1)

    @property
    def copy_count(self) -> int:
        """Return the number of redundant copies (all paths minus the keeper).

        Returns:
            Number of duplicate copies that could safely be deleted.
        """
        return len(self.paths) - 1
