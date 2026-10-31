"""`plain fmt` — the one canonical formatter (Doc 03 §2 rule 4).

v1 scope: normalize block indentation to 2-space levels from the parsed
block tree, trim trailing whitespace, collapse 2+ blank lines to 1.
Line *contents* are preserved verbatim (no rewrapping) — formatting must
never change what a program says.
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
    out: list[str] = []
    last_level = 0
    blank_run = 0
    for no, raw in enumerate(source.splitlines(), 1):
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
        elif stripped.startswith("#"):
            indent = last_level  # comment sits with the code above it
        else:
            indent = last_level + 1  # and/or continuation line
        out.append("  " * indent + stripped)
    return "\n".join(out).rstrip() + "\n"
