"""
scripts/show_tree.py

Print a tree of the repository (folders + files), with optional file sizes
and a summary. Cross-platform (Windows/macOS/Linux).

Usage:
    python scripts/show_tree.py
    python scripts/show_tree.py --root . --show-size --max-depth 4
    python scripts/show_tree.py --show-all            # don't skip noise
    python scripts/show_tree.py --only data          # restrict to a subpath
    python scripts/show_tree.py --save tree.txt      # write to file too
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

# Directories skipped by default (noise / vendor / caches / VCS).
SKIP_DIRS = {
    ".git",
    ".github",             # keep if you want to see CI; remove from set to show
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    ".next",
    ".nuxt",
    "dist",
    "build",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".eggs",
    "*.egg-info",
    ".cache",
    ".vite",
    ".turbo",
    ".parcel-cache",
}

# File patterns skipped by default (extensions we generally don't care about).
SKIP_FILE_EXTS = {
    ".pyc", ".pyo", ".pyd",
    ".lock",
    ".log",
    ".DS_Store",
}

SKIP_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".package-lock.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def human_size(n: int) -> str:
    """Format a byte count as B / KB / MB / GB."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{n} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def should_skip_dir(name: str, show_all: bool) -> bool:
    if show_all:
        return False
    return name in SKIP_DIRS or name.endswith(".egg-info")


def should_skip_file(name: str, show_all: bool) -> bool:
    if show_all:
        return False
    if name in SKIP_FILE_NAMES:
        return True
    ext = os.path.splitext(name)[1].lower()
    return ext in SKIP_FILE_EXTS


def dir_size(path: Path) -> int:
    """Recursive total byte size of a directory (skipping nothing here)."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


# ---------------------------------------------------------------------------
# Tree rendering
# ---------------------------------------------------------------------------

def walk(
    root: Path,
    out_lines: list[str],
    prefix: str = "",
    depth: int = 0,
    max_depth: int | None = None,
    show_size: bool = False,
    show_all: bool = False,
    stats: dict | None = None,
) -> None:
    """Recursively append tree lines to `out_lines`."""
    if max_depth is not None and depth > max_depth:
        return

    try:
        entries = sorted(
            root.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except OSError as exc:
        out_lines.append(f"{prefix}[error: {exc}]")
        return

    # Filter
    dirs, files = [], []
    for entry in entries:
        if entry.is_dir():
            if not should_skip_dir(entry.name, show_all):
                dirs.append(entry)
        else:
            if not should_skip_file(entry.name, show_all):
                files.append(entry)

    visible = dirs + files
    for i, entry in enumerate(visible):
        is_last = i == len(visible) - 1
        connector = "\\-- " if is_last else "|-- "

        if entry.is_dir():
            if show_size:
                sz = dir_size(entry)
                label = f"{entry.name}/  [{human_size(sz)}]"
            else:
                label = f"{entry.name}/"
            out_lines.append(f"{prefix}{connector}{label}")

            if stats is not None:
                stats["dirs"] += 1

            new_prefix = prefix + ("    " if is_last else "|   ")
            walk(
                entry,
                out_lines,
                prefix=new_prefix,
                depth=depth + 1,
                max_depth=max_depth,
                show_size=show_size,
                show_all=show_all,
                stats=stats,
            )
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0

            if stats is not None:
                stats["files"] += 1
                stats["bytes"] += size
                ext = os.path.splitext(entry.name)[1].lower() or "(no ext)"
                stats["exts"][ext] = stats["exts"].get(ext, 0) + 1

            if show_size:
                out_lines.append(
                    f"{prefix}{connector}{entry.name}  [{human_size(size)}]"
                )
            else:
                out_lines.append(f"{prefix}{connector}{entry.name}")


def build_tree(
    root: Path,
    max_depth: int | None,
    show_size: bool,
    show_all: bool,
) -> tuple[list[str], dict]:
    stats = {"dirs": 0, "files": 0, "bytes": 0, "exts": {}}

    root_label = str(root.resolve())
    lines: list[str] = [root_label]

    # Root-level entries (reuse walk with empty prefix at depth 0)
    walk(
        root,
        lines,
        prefix="",
        depth=0,
        max_depth=max_depth,
        show_size=show_size,
        show_all=show_all,
        stats=stats,
    )

    # Summary
    lines.append("")
    lines.append("=" * 72)
    lines.append("SUMMARY")
    lines.append("=" * 72)
    lines.append(f"Directories : {stats['dirs']}")
    lines.append(f"Files       : {stats['files']}")
    lines.append(f"Total size  : {human_size(stats['bytes'])}")

    if stats["exts"]:
        top = sorted(stats["exts"].items(), key=lambda kv: -kv[1])[:15]
        lines.append("")
        lines.append("Top file extensions:")
        for ext, count in top:
            lines.append(f"  {ext:<12} {count}")

    return lines, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Print the folder + file tree of this repository."
    )
    p.add_argument("--root", default=".", help="Directory to walk (default: .)")
    p.add_argument(
        "--only",
        default=None,
        help="Restrict to a subpath under --root (e.g. 'data' or 'models')",
    )
    p.add_argument(
        "--max-depth", type=int, default=None,
        help="Max recursion depth (default: unlimited)",
    )
    p.add_argument(
        "--show-size", action="store_true",
        help="Show file sizes (and recursive dir sizes)",
    )
    p.add_argument(
        "--show-all", action="store_true",
        help="Include noise dirs (node_modules, __pycache__, .git, ...)",
    )
    p.add_argument(
        "--save", default=None,
        help="Also write the output to this file (e.g. tree.txt)",
    )
    args = p.parse_args()

    root = Path(args.root).resolve()
    if args.only:
        root = (root / args.only).resolve()

    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    lines, _ = build_tree(
        root,
        max_depth=args.max_depth,
        show_size=args.show_size,
        show_all=args.show_all,
    )

    text = "\n".join(lines)
    print(text)

    if args.save:
        out_path = Path(args.save)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"\nSaved to: {out_path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())