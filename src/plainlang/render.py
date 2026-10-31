"""One-call pipeline: source → checked program → scene → laid-out SVG.

Used by the CLI, the preview server, and tests (one code path, per the
Doc 03 §10 "language server shares the real compiler" principle).
"""
from __future__ import annotations

from .checker import check_program
from .errors import PlainError
from .layout import layout
from .paint_svg import to_svg
from .parser import parse_program
from .runtime import Runtime
from .scene import SceneBuilder


class App:
    """A loaded .plain program with a live runtime."""

    def __init__(self, source: str, name: str = "<program>"):
        self.name = name
        self.source = source
        self.program = parse_program(source)
        self.errors = check_program(self.program)
        self.runtime = Runtime(self.program)
        self.builder = SceneBuilder(self.program, self.runtime)
        self.scene = None

    def require_ok(self):
        if self.errors:
            raise self.errors[0]

    def page(self):
        page = self.program.first_page()
        if page is None:
            raise PlainError(
                "This file has no page to show. Add one: "
                '`page Home at "/":` with what it looks like indented below.')
        return page

    def build(self, width: float = 800, height: float = 600):
        self.require_ok()
        self.scene = self.builder.build_page(self.page())
        layout(self.scene, width, height)
        return self.scene

    def svg(self, width: float = 800, height: float = 600,
            tap_prefix: str | None = None) -> str:
        scene = self.build(width, height)
        return to_svg(scene, width, height, tap_prefix=tap_prefix)

    def tap(self, path: str):
        if self.scene is None:
            self.build()
        node = self.scene.find(path)
        if node is None:
            raise PlainError(f"Nothing at `{path}` to tap (stale preview?).")
        entry = node.events.get("tap")
        if entry is None:
            return
        event, scope_path, extra = entry
        sc = self.runtime.scopes.get(scope_path)
        if sc is None:
            raise PlainError("That part of the page is gone (stale preview?).")
        self.runtime.run_event(sc, event, extra)
