"""Command-line interface for the duplicate file finder.

This module wires together the scanning engine (``dupfinder.hasher``) and
the terminal presentation layer (``rich``). It exposes a single ``main``
function that is registered as the ``dupfind`` console script entry point
in ``pyproject.toml``.

Typical usage::

    $ dupfind ~/Downloads ~/Documents
    $ dupfind ~/Downloads --dry-run
    $ dupfind ~/Downloads --delete --min-size 102400
    $ dupfind ~/Downloads --output paths | xargs rm
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from dupfinder.hasher import find_duplicates
from dupfinder.models import DuplicateGroup

console = Console()
err_console = Console(stderr=True)


def _human_size(num_bytes: int) -> str:
    """Convert a raw byte count into a compact human-readable string.

    Iterates through standard SI units (B, KB, MB, GB, TB) and returns the
    value formatted to one decimal place in the most appropriate unit.

    Args:
        num_bytes: Size in bytes (may be 0 or negative for display purposes).

    Returns:
        String such as ``"4.2 MB"`` or ``"512.0 B"``.

    Example:
        >>> _human_size(1_048_576)
        '1.0 MB'
        >>> _human_size(500)
        '500.0 B'
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024  # type: ignore[assignment]
    return f"{num_bytes:.1f} PB"


def _build_report(groups: list[DuplicateGroup]) -> Table:
    """Construct a Rich ``Table`` summarising all duplicate groups.

    Each row shows one duplicate group with its short hash, file size,
    redundant copy count, wasted space, and all file paths. The first path
    in each group is highlighted as the "keeper"; subsequent paths are
    shown in yellow as the ones that could be deleted.

    Args:
        groups: Non-empty list of :class:`~dupfinder.models.DuplicateGroup`
                objects as returned by :func:`~dupfinder.hasher.find_duplicates`.

    Returns:
        A configured ``rich.table.Table`` ready to be printed with
        ``console.print()``.
    """
    table = Table(
        title="[bold red]Duplicate Files[/bold red]",
        box=box.ROUNDED,
        show_lines=True,
        highlight=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("MD5 (first 8)", style="cyan", no_wrap=True)
    table.add_column("Size", style="green", justify="right")
    table.add_column("Copies", justify="center")
    table.add_column("Wasted", style="red", justify="right")
    table.add_column("Paths", overflow="fold")

    for idx, group in enumerate(groups, start=1):
        paths_text = Text()
        for i, p in enumerate(group.paths):
            if i == 0:
                paths_text.append(str(p), style="bold white")
            else:
                paths_text.append("\n" + str(p), style="yellow")
        table.add_row(
            str(idx),
            group.md5[:8],
            _human_size(group.size),
            str(group.copy_count),
            _human_size(group.wasted_bytes),
            paths_text,
        )
    return table


def _delete_duplicates(groups: list[DuplicateGroup], dry_run: bool) -> int:
    """Delete all but the first path in each duplicate group.

    In dry-run mode, prints what would be deleted without touching the
    filesystem. In delete mode, calls ``Path.unlink()`` on each redundant
    file and prints a confirmation. Any ``OSError`` (e.g. a file that
    disappeared between scan and deletion) is reported to stderr and
    skipped rather than causing the whole operation to abort.

    Args:
        groups:  Duplicate groups to process.
        dry_run: When ``True``, only print intended actions; do not delete.

    Returns:
        Number of files actually deleted (always 0 in dry-run mode).
    """
    deleted = 0
    for group in groups:
        for path in group.paths[1:]:
            if dry_run:
                console.print(f"[dim][DRY-RUN][/dim] would delete [yellow]{path}[/yellow]")
            else:
                try:
                    path.unlink()
                    console.print(f"[red]Deleted[/red] {path}")
                    deleted += 1
                except OSError as exc:
                    err_console.print(f"[bold red]Error[/bold red] deleting {path}: {exc}")
    return deleted


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build the argument parser and return parsed arguments.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when
              ``None`` (standard argparse behaviour).

    Returns:
        ``argparse.Namespace`` with attributes ``directories``, ``delete``,
        ``dry_run``, ``min_size``, and ``output``.
    """
    parser = argparse.ArgumentParser(
        prog="dupfind",
        description="Find (and optionally delete) duplicate files using MD5 hashing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  dupfind ~/Downloads\n"
            "  dupfind ~/Downloads --dry-run\n"
            "  dupfind ~/Downloads --delete --min-size 102400\n"
            "  dupfind ~/Downloads --output paths | xargs rm\n"
            "  dupfind ~/Documents ~/Downloads ~/Desktop"
        ),
    )
    parser.add_argument(
        "directories",
        nargs="+",
        metavar="DIR",
        help="One or more directories to scan recursively.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete duplicate files, keeping the first occurrence of each group.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without removing anything.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        metavar="BYTES",
        help="Skip files strictly smaller than BYTES (default: 1, skips empty files).",
    )
    parser.add_argument(
        "--output",
        choices=["table", "paths"],
        default="table",
        help=(
            "Output format. 'table' (default) renders a coloured summary table. "
            "'paths' prints one duplicate path per line for scripting."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the duplicate-file finder CLI and return an exit code.

    Orchestrates argument parsing, directory validation, scanning, report
    rendering, and optional deletion. Exit codes follow Unix convention:

    * ``0`` — success (including the case where no duplicates were found).
    * ``2`` — a supplied path is not a valid directory.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]`` when ``None``.
              Pass an explicit list to call programmatically, e.g. in tests.

    Returns:
        Integer exit code (0 or 2).
    """
    args = _parse_args(argv)

    dirs = [Path(d) for d in args.directories]
    for d in dirs:
        if not d.is_dir():
            err_console.print(f"[bold red]Error:[/bold red] {d} is not a directory.")
            return 2

    with console.status("[bold green]Scanning for duplicates…[/bold green]"):
        groups = find_duplicates(dirs, min_size=args.min_size)

    if not groups:
        console.print("[bold green]No duplicates found.[/bold green]")
        return 0

    total_wasted = sum(g.wasted_bytes for g in groups)
    total_copies = sum(g.copy_count for g in groups)

    if args.output == "table":
        console.print(_build_report(groups))
    else:
        for group in groups:
            for path in group.paths[1:]:
                console.print(str(path))

    console.print(
        f"\n[bold]Found {len(groups)} duplicate group(s)[/bold], "
        f"{total_copies} redundant file(s), "
        f"[red]{_human_size(total_wasted)}[/red] wasted."
    )

    if args.delete or args.dry_run:
        deleted = _delete_duplicates(groups, dry_run=args.dry_run)
        if not args.dry_run:
            console.print(f"[green]Deleted {deleted} file(s).[/green]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
