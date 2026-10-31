"""`plain fmt` — the one canonical formatter (Doc 03 §2 rule 4).

v1 scope: normalize block indentation to 2-space levels from the parsed
block tree, keep continuation lines where the author aligned them, attach
comment blocks to the declaration they describe, trim trailing whitespace,
and collapse 2+ blank lines to 1. Line *contents* are preserved verbatim
(no rewrapping) — formatting must never change what a program says.

This is deliberately conservative: a formatter that silently moves a
comment into the previous block is a bug, not a style choice.
"""
from __future__ import annotations

from .parser import block_tree


def format_source(source: str) -> str:
    levels: dict[int, int] = {}

    def collect(lines):
        for ln in lines:
            levels[ln.no] = ln.level
            collect(ln.children)

    collect(block_tree(source))
    raw_lines = source.splitlines()

    # Continuation lines are joined by the parser (`and` / `or`); keep the
    # author's alignment so the formatted file stays the file they wrote.
    continuation = {
        no for no, raw in enumerate(raw_lines, 1)
        if raw.strip().startswith(("or ", "and "))
    }

    # A comment attaches to the NEXT declaration, not the previous block.
    next_level: dict[int, int] = {}
    upcoming: int | None = None
    for no in range(len(raw_lines), 0, -1):
        if no in levels:
            upcoming = levels[no]
        next_level[no] = upcoming if upcoming is not None else 0

    out: list[str] = []
    last_level = 0
    blank_run = 0
    for no, raw in enumerate(raw_lines, 1):
        stripped = raw.strip()
        if not stripped:
            blank_run += 1
            if blank_run <= 1 and out:
                out.append("")
            continue
        blank_run = 0
        if no in levels:
            last_level = levels[no]
            indent = last_level
        elif no in continuation:
            # Preserve exactly as written (canonical wrapping lands in fmt v2).
            out.append(raw.rstrip())
            continue
        elif stripped.startswith("#"):
            indent = next_level.get(no, last_level)
        else:
            indent = last_level + 1  # defensive: unknown continuation-ish line
        out.append("  " * indent + stripped)
    return "\n".join(out).rstrip() + "\n"
