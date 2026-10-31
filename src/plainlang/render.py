"""One-call pipeline: source → checked program → scene → laid-out SVG.

Used by the CLI, the preview server, and tests (one code path, per the
Doc 03 §10 "language server shares the real compiler" principle).
Owns the navigation stack and preview interactions (tap / field / submit).
"""
from __future__ import annotations

import json
from pathlib import Path

from .checker import check_program
from .errors import PlainError
from .layout import layout
from .paint_svg import to_svg
from .parser import parse_program
from .runtime import Navigate, Runtime
from .scene import SceneBuilder


class App:
    """A loaded .plain program with a live runtime."""

    def __init__(self, source: str, name: str = "<program>",
                 providers: dict | None = None,
                 page_params: dict | None = None,
                 persist_path: str | Path | None = None):
        self.name = name
        self.source = source
        self.program = parse_program(source)
        self.errors = check_program(self.program)
        self.providers = providers or {}
        self.initial_params = page_params or {}
        self.runtime = Runtime(self.program, providers=self.providers,
                               persist_path=persist_path)
        self.builder = SceneBuilder(self.program, self.runtime)
        self.scene = None
        first = self.program.first_page()
        self.stack: list[tuple[str, dict]] = [
            (first.name, dict(self.initial_params))] if first else []

    @classmethod
    def for_file(cls, path: str | Path, persist: bool = False) -> "App":
        """Load an app file plus its optional sidecar fixtures
        (`<name>.sample.json` — prototype data providers, Stage 3)."""
        p = Path(path)
        providers, params = {}, {}
        sidecar = p.with_suffix(".sample.json")
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            providers = data.get("resources", {})
            params = data.get("page_params", {})
        persist_path = None
        if persist:
            persist_path = Path(".plain") / (p.stem + ".json")
        return cls(p.read_text(encoding="utf-8"), name=p.name,
                   providers=providers, page_params=params,
                   persist_path=persist_path)

    def require_ok(self):
        if self.errors:
            raise self.errors[0]

    # -- navigation ---------------------------------------------------------
    def page(self):
        if not self.stack:
            raise PlainError(
                "This file has no page to show. Add one: "
                '`page Home at "/":` with what it looks like indented below.')
        name = self.stack[-1][0]
        page = self.program.pages.get(name)
        if page is None:
            raise PlainError(
                f"This file has no page called `{name}` to go to. "
                f"Pages here: {', '.join(self.program.pages) or 'none'}.")
        return page

    def _navigate(self, nav: Navigate):
        if nav.back:
            if len(self.stack) > 1:
                self.stack.pop()
            return
        page = self.program.pages.get(nav.page_name)
        if page is None:
            raise PlainError(
                f"There's no page called `{nav.page_name}` in this file "
                f"to go to.")
        params = {}
        for key, val in zip(page.params, nav.args):
            params[key] = val
        self.stack.append((nav.page_name, params))

    # -- building -----------------------------------------------------------
    def build(self, width: float = 800, height: float = 600):
        self.require_ok()
        self.scene = self.builder.build_page(self.page(), self.stack[-1][1],
                                             viewport=(width, height))
        layout(self.scene, width, height)
        return self.scene

    def svg(self, width: float = 800, height: float = 600,
            tap_prefix: str | None = None) -> str:
        scene = self.build(width, height)
        return to_svg(scene, width, height, tap_prefix=tap_prefix)

    # -- interaction ----------------------------------------------------------
    def _scope(self, scope_path: str):
        sc = self.runtime.scopes.get(scope_path)
        if sc is None:
            raise PlainError("That part of the page is gone (stale preview?).")
        return sc

    def tap(self, path: str):
        if self.scene is None:
            self.build()
        node = self.scene.find(path)
        if node is None:
            raise PlainError(f"Nothing at `{path}` to tap (stale preview?).")
        if "disabled" in node.flags:
            return  # disabled controls don't activate (Doc 02 §1.4)
        try:
            if node.kind == "toggle" and node.bind:
                target, scope_path, extra = node.bind
                sc = self._scope(scope_path)
                cur = self.runtime.get_value(sc, target, extra, node.source_line)
                self.runtime.set_value(sc, target, not cur, extra, node.source_line)
                return
            entry = node.events.get("tap")
            if entry is None:
                return
            event, scope_path, extra = entry
            self.runtime.run_event(self._scope(scope_path), event, extra)
        except Navigate as nav:
            self._navigate(nav)
        finally:
            self.runtime.save_kept()

    def set_field(self, path: str, value: str, submit: bool = False):
        """Type into an `input bind …` (and optionally fire `on submit`)."""
        if self.scene is None:
            self.build()
        node = self.scene.find(path)
        if node is None or not node.bind:
            raise PlainError(f"Nothing at `{path}` to type into (stale preview?).")
        target, scope_path, extra = node.bind
        sc = self._scope(scope_path)
        self.runtime.set_value(sc, target, value, extra, node.source_line)
        try:
            ev_name = "submit" if submit else "change"
            entry = node.events.get(ev_name) or (node.events.get("change")
                                                 if submit else None)
            if entry is not None:
                event, esc_path, eextra = entry
                eextra = dict(eextra)
                if event.param:
                    eextra[event.param] = value
                self.runtime.run_event(self._scope(esc_path), event, eextra)
        except Navigate as nav:
            self._navigate(nav)
        finally:
            self.runtime.save_kept()

    def reset(self):
        first = self.program.first_page()
        self.stack = [(first.name, dict(self.initial_params))] if first else []
        self.runtime.clear_persisted()
        self.runtime.reset()

    # -- hot reload carry-over (dev server) -----------------------------------
    def carry_from(self, old: "App"):
        """Adopt the previous App's runtime + nav stack after a re-parse."""
        self.runtime = old.runtime
        self.runtime.program = self.program
        self.runtime.providers = self.providers
        self.builder = SceneBuilder(self.program, self.runtime)
        self.stack = [(n, p) for n, p in old.stack if n in self.program.pages]
        if not self.stack:
            first = self.program.first_page()
            self.stack = [(first.name, dict(self.initial_params))] if first else []
