"""`plain` — four verbs (Doc 03 §10): run, check, render, test (+ a11y)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import a11y as a11y_mod
from .checker import check_program, warnings_for
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
            continue
        pages = ", ".join(prog.pages) or "no pages"
        comps = ", ".join(prog.components) or "no components"
        warns = warnings_for(prog)
        suffix = f" ({len(warns)} note{'s' if len(warns) != 1 else ''})" if warns else ""
        print(f"{path}: OK — pages: {pages}; components: {comps}; "
              f"needs: {', '.join(prog.needs) or 'nothing'}{suffix}")
        for w in warns:
            print("\n".join(f"{path}: {line}" for line in w.render().splitlines()))
            print()
    return 1 if bad else 0


def cmd_render(args) -> int:
    try:
        app = App.for_file(args.file)
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
        app = App.for_file(args.file)
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


def cmd_fmt(args) -> int:
    from .fmt import format_source
    bad = 0
    for path in args.files:
        try:
            source = _read(path)
            formatted = format_source(source)
        except PlainError as e:
            print(f"{path}:\n{e.render()}\n", file=sys.stderr)
            bad += 1
            continue
        if args.check:
            if formatted != source:
                print(f"{path}: not formatted (run `./plain fmt {path}`)")
                bad += 1
        elif args.write:
            Path(path).write_text(formatted, encoding="utf-8")
            print(f"{path}: formatted")
        else:
            print(formatted, end="")
    return 1 if bad else 0


def cmd_validate(args) -> int:
    """Phase-5 validation harness: build every example, report real metrics."""
    import glob as glob_mod
    import time
    from .errors import UnsupportedYet
    rows = []
    for path in sorted(glob_mod.glob(args.pattern)):
        lines = [l for l in Path(path).read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        started = time.perf_counter()
        status, nodes, svg_bytes = "renders ✓", 0, 0
        try:
            app = App.for_file(path)
            scene = app.build(args.width, args.height)
            nodes = sum(1 for _ in scene.walk())
            svg_bytes = len(app.svg(args.width, args.height))
        except UnsupportedYet as e:
            status = f"parse+check only ({e.stage})"
        except PlainError as e:
            status = f"ERROR: {e.message}"
        ms = (time.perf_counter() - started) * 1000
        rows.append((Path(path).name, len(lines), status, nodes, svg_bytes, ms))
    print(f"| Example | PL lines | Prototype status | Scene nodes | SVG bytes | Build ms |")
    print(f"|---|---|---|---|---|---|")
    for name, loc, status, nodes, b, ms in rows:
        print(f"| `{name}` | {loc} | {status} | {nodes or '—'} | {b or '—'} | {ms:.1f} |")
    failed = sum(1 for row in rows if row[2].startswith("ERROR"))
    if not rows:
        print("\nvalidate: no files matched.", file=sys.stderr)
        return 1
    if failed:
        print(f"\nvalidate: {failed} of {len(rows)} example(s) failed.",
              file=sys.stderr)
        return 1
    # Golden floor (P0-12): an example may grow, never silently shrink or
    # stop rendering. The baseline is committed and reviewed.
    import json
    base_path = Path(args.baseline)
    shortfalls = []
    if base_path.exists():
        baseline = json.loads(base_path.read_text(encoding="utf-8"))
        for name, _loc, status, nodes, b, _ms in rows:
            want = baseline.get(name)
            if not want:
                continue
            if status.startswith("ERROR"):
                shortfalls.append(f"{name}: {status}")
            elif nodes < want["nodes"]:
                shortfalls.append(
                    f"{name}: {nodes} nodes < baseline {want['nodes']}")
            elif b < want["svg_bytes"]:
                shortfalls.append(
                    f"{name}: {b} SVG bytes < baseline {want['svg_bytes']}")
    else:
        print(f"validate: baseline not found at {base_path} (skipped)",
              file=sys.stderr)
    if shortfalls:
        print("\nvalidate: below the committed baseline:\n  " +
              "\n  ".join(shortfalls), file=sys.stderr)
        return 1
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

    p = sub.add_parser("fmt", help="format .plain files canonically")
    p.add_argument("files", nargs="+")
    p.add_argument("--write", action="store_true", help="rewrite files in place")
    p.add_argument("--check", action="store_true", help="fail if unformatted")
    p.set_defaults(fn=cmd_fmt)

    p = sub.add_parser("validate", help="Phase-5 harness: build examples, report metrics")
    p.add_argument("pattern", nargs="?", default="examples/*.plain")
    p.add_argument("--width", type=float, default=412)
    p.add_argument("--height", type=float, default=800)
    p.add_argument("--baseline", default="tests/example_baseline.json")
    p.set_defaults(fn=cmd_validate)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
