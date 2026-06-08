"""Data models for the duplicate file finder."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DuplicateGroup:
    """Holds a set of files that share the same MD5 hash."""

    md5: str
    size: int  # bytes — all files in the group are the same size
    paths: list[Path] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        """Bytes consumed by redundant copies (total minus one keeper)."""
        return self.size * (len(self.paths) - 1)

    @property
    def copy_count(self) -> int:
        """Number of duplicate copies (excluding the keeper)."""
        return len(self.paths) - 1
