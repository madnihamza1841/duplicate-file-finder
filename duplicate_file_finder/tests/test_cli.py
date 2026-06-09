"""Tests for dupfinder.cli — argument parsing, output, dry-run safety."""

from pathlib import Path

from dupfinder.cli import main


def _write(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_cli_no_duplicates(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "a.txt", b"aaa")
    _write(tmp_path / "b.txt", b"bbb")
    rc = main([str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No duplicates" in out


def test_cli_finds_duplicates(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "a.txt", b"same")
    _write(tmp_path / "b.txt", b"same")
    rc = main([str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 duplicate group" in out


def test_cli_dry_run_does_not_delete(tmp_path: Path) -> None:
    f1 = _write(tmp_path / "a.txt", b"same")
    f2 = _write(tmp_path / "b.txt", b"same")
    main([str(tmp_path), "--dry-run"])
    assert f1.exists()
    assert f2.exists()


def test_cli_delete_removes_duplicate(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", b"same")
    _write(tmp_path / "b.txt", b"same")
    main([str(tmp_path), "--delete"])
    remaining = list(tmp_path.iterdir())
    assert len(remaining) == 1


def test_cli_output_paths_format(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "a.txt", b"dup")
    _write(tmp_path / "b.txt", b"dup")
    main([str(tmp_path), "--output", "paths"])
    out = capsys.readouterr().out
    # Should print a plain file path, not a table border
    assert "╭" not in out
    assert str(tmp_path) in out


def test_cli_invalid_directory(tmp_path: Path, capsys) -> None:
    rc = main([str(tmp_path / "nonexistent")])
    assert rc == 2


def test_cli_min_size_filters_small_files(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "a.txt", b"hi")
    _write(tmp_path / "b.txt", b"hi")
    rc = main([str(tmp_path), "--min-size", "100"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No duplicates" in out
