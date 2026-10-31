"""`plain` — four verbs (Doc 03 §10): run, check, render, test (+ a11y)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import a11y as a11y_mod
from .checker import check_program
from .errors import PlainError
from .parser import parse_program
from .render import App


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PlainError(f"I can't find `{path}`. Check the name — PL files "
                         f"end in `.plain`.")


def cmd_check(args) -> int:
    bad = 0
    for path in args.files:
        try:
            prog = parse_program(_read(path))
            errors = check_program(prog)
        except PlainError as e:
            print(f"{path}:\n{e.render()}\n")
            bad += 1
            continue
        if errors:
            bad += 1
            for e in errors:
                print(f"{path}:\n{e.render()}\n")
        else:
            pages = ", ".join(prog.pages) or "no pages"
            comps = ", ".join(prog.components) or "no components"
            print(f"{path}: OK — pages: {pages}; components: {comps}; "
                  f"needs: {', '.join(prog.needs) or 'nothing'}")
    return 1 if bad else 0


def cmd_render(args) -> int:
    try:
        app = App(_read(args.file), name=args.file)
        svg = app.svg(args.width, args.height)
    except PlainError as e:
        print(e.render(), file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(svg, encoding="utf-8")
        print(f"wrote {args.out} ({len(svg)} bytes, {args.width}×{args.height})")
    else:
        print(svg)
    return 0


def cmd_a11y(args) -> int:
    try:
        app = App(_read(args.file), name=args.file)
        scene = app.build(args.width, args.height)
    except PlainError as e:
        print(e.render(), file=sys.stderr)
        return 1
    tree = a11y_mod.derive(scene)
    print(f"# Accessibility tree for {args.file} — derived, never written "
          f"(Doc 02 §1.4)\n")
    print(a11y_mod.render_text(tree) if tree else "(nothing on this page)")
    return 0


def cmd_run(args) -> int:
    from .server import serve
    try:
        _read(args.file)  # friendly error before binding a port
    except PlainError as e:
        print(e.render(), file=sys.stderr)
        return 1
    serve(args.file, port=args.port, width=args.width, height=args.height)
    return 0


def cmd_parse(args) -> int:
    """Debug: dump the classified AST (Looking Glass ancestor)."""
    import dataclasses
    import json

    def default(o):
        if dataclasses.is_dataclass(o):
            d = {k: v for k, v in dataclasses.asdict(o).items()}
            d["_type"] = type(o).__name__
            return d
        return str(o)

    try:
        prog = parse_program(_read(args.file))
    except PlainError as e:
        print(e.render(), file=sys.stderr)
        return 1
    print(json.dumps(dataclasses.asdict(prog), indent=2, default=default,
                     ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="plain",
        description="PLAIN — describe what you see. (Stage-1 reference "
                    "prototype; see docs/06-stage1-prototype.md)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="check .plain files for problems")
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("render", help="render a page to SVG")
    p.add_argument("file")
    p.add_argument("--out", default=None)
    p.add_argument("--width", type=float, default=800)
    p.add_argument("--height", type=float, default=600)
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("run", help="run with live preview (hot reload, state kept)")
    p.add_argument("file")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--width", type=float, default=800)
    p.add_argument("--height", type=float, default=600)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("a11y", help="print the derived accessibility tree")
    p.add_argument("file")
    p.add_argument("--width", type=float, default=800)
    p.add_argument("--height", type=float, default=600)
    p.set_defaults(fn=cmd_a11y)

    p = sub.add_parser("parse", help="dump the AST as JSON (debug)")
    p.add_argument("file")
    p.set_defaults(fn=cmd_parse)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
