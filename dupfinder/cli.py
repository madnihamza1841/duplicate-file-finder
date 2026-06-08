"""CLI entry point for the duplicate file finder."""

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
    """Return a human-readable byte count."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024  # type: ignore[assignment]
    return f"{num_bytes:.1f} PB"


def _build_report(groups: list[DuplicateGroup]) -> Table:
    """Render duplicate groups into a rich Table."""
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
    """Delete all but the first path in each group. Returns number of files removed."""
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
    parser = argparse.ArgumentParser(
        prog="dupfind",
        description="Find (and optionally delete) duplicate files using MD5 hashing.",
    )
    parser.add_argument(
        "directories",
        nargs="+",
        metavar="DIR",
        help="One or more directories to scan.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete duplicate files, keeping the first occurrence.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        metavar="BYTES",
        help="Skip files smaller than BYTES (default: 1, i.e. skip empty files).",
    )
    parser.add_argument(
        "--output",
        choices=["table", "paths"],
        default="table",
        help="Output format: 'table' (default) or plain 'paths'.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
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
