"""Tests for dupfinder.hasher — grouping, edge cases, optimisation paths."""

from pathlib import Path

import pytest

from dupfinder.hasher import find_duplicates, md5_of_file, walk_files
from dupfinder.models import DuplicateGroup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# md5_of_file
# ---------------------------------------------------------------------------

def test_md5_of_file_known_hash(tmp_path: Path) -> None:
    import hashlib

    data = b"hello world"
    f = _write(tmp_path / "f.bin", data)
    expected = hashlib.md5(data).hexdigest()
    assert md5_of_file(f) == expected


def test_md5_of_file_missing_returns_none(tmp_path: Path) -> None:
    assert md5_of_file(tmp_path / "nonexistent.bin") is None


# ---------------------------------------------------------------------------
# walk_files
# ---------------------------------------------------------------------------

def test_walk_files_basic(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", b"aaa")
    _write(tmp_path / "b.txt", b"bbb")
    result = walk_files([tmp_path])
    assert len(result) == 2


def test_walk_files_skips_symlinks(tmp_path: Path) -> None:
    real = _write(tmp_path / "real.txt", b"data")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    result = walk_files([tmp_path])
    assert link not in result
    assert real in result


def test_walk_files_min_size(tmp_path: Path) -> None:
    _write(tmp_path / "small.txt", b"hi")   # 2 bytes
    _write(tmp_path / "big.txt", b"hello world")  # 11 bytes
    result = walk_files([tmp_path], min_size=5)
    names = {p.name for p in result}
    assert "big.txt" in names
    assert "small.txt" not in names


def test_walk_files_skips_empty_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "empty.txt", b"")
    _write(tmp_path / "non_empty.txt", b"x")
    result = walk_files([tmp_path])  # default min_size=1
    names = {p.name for p in result}
    assert "empty.txt" not in names
    assert "non_empty.txt" in names


def test_walk_files_hard_link_dedup(tmp_path: Path) -> None:
    real = _write(tmp_path / "real.txt", b"data")
    link = tmp_path / "hardlink.txt"
    link.hardlink_to(real)
    result = walk_files([tmp_path])
    # Only one of the two hard-linked paths should appear
    assert len(result) == 1


def test_walk_files_recursive(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(sub / "nested.txt", b"nested")
    result = walk_files([tmp_path])
    assert any(p.name == "nested.txt" for p in result)


# ---------------------------------------------------------------------------
# find_duplicates — core grouping
# ---------------------------------------------------------------------------

def test_find_duplicates_detects_identical_files(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", b"same content")
    _write(tmp_path / "b.txt", b"same content")
    groups = find_duplicates([tmp_path])
    assert len(groups) == 1
    assert groups[0].copy_count == 1
    assert groups[0].wasted_bytes == len(b"same content")


def test_find_duplicates_no_duplicates(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", b"aaa")
    _write(tmp_path / "b.txt", b"bbb")
    assert find_duplicates([tmp_path]) == []


def test_find_duplicates_single_file(tmp_path: Path) -> None:
    _write(tmp_path / "only.txt", b"solo")
    assert find_duplicates([tmp_path]) == []


def test_find_duplicates_empty_directory(tmp_path: Path) -> None:
    assert find_duplicates([tmp_path]) == []


def test_find_duplicates_same_name_different_content(tmp_path: Path) -> None:
    d1 = (tmp_path / "d1")
    d2 = (tmp_path / "d2")
    d1.mkdir()
    d2.mkdir()
    _write(d1 / "file.txt", b"content A")
    _write(d2 / "file.txt", b"content B")
    assert find_duplicates([tmp_path]) == []


def test_find_duplicates_multiple_groups(tmp_path: Path) -> None:
    _write(tmp_path / "a1.txt", b"group_one")
    _write(tmp_path / "a2.txt", b"group_one")
    _write(tmp_path / "b1.txt", b"group_two!!")
    _write(tmp_path / "b2.txt", b"group_two!!")
    groups = find_duplicates([tmp_path])
    assert len(groups) == 2


def test_find_duplicates_sorted_by_wasted_space(tmp_path: Path) -> None:
    # Group A: 1-byte files, wastes 1 byte
    _write(tmp_path / "a1.txt", b"x")
    _write(tmp_path / "a2.txt", b"x")
    # Group B: 100-byte files, wastes 100 bytes
    big = b"y" * 100
    _write(tmp_path / "b1.txt", big)
    _write(tmp_path / "b2.txt", big)
    groups = find_duplicates([tmp_path])
    assert groups[0].wasted_bytes > groups[1].wasted_bytes


def test_find_duplicates_skips_empty_files_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "e1.txt", b"")
    _write(tmp_path / "e2.txt", b"")
    assert find_duplicates([tmp_path]) == []


def test_find_duplicates_includes_empty_files_with_min_size_zero(tmp_path: Path) -> None:
    _write(tmp_path / "e1.txt", b"")
    _write(tmp_path / "e2.txt", b"")
    groups = find_duplicates([tmp_path], min_size=0)
    assert len(groups) == 1


def test_find_duplicates_multi_directory(tmp_path: Path) -> None:
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    _write(d1 / "file.txt", b"dupe")
    _write(d2 / "file.txt", b"dupe")
    groups = find_duplicates([d1, d2])
    assert len(groups) == 1
