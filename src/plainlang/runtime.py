"""Stage-1 reactive runtime.

Semantics per Doc 03 §6.1 (`=` state, `is` derived), with one documented
prototype simplification: derivations recompute on every read instead of
using the fine-grained dependency graph of ADR-3. Observable behavior is
identical; performance is not the prototype's claim. The seam is exactly
here (`env_for`) so the Rust port can swap the strategy.

Instances: each page/component *instance* (identified by tree path) owns a
state dict, initialized from its StateDecls on first use.
"""
from __future__ import annotations

import re

from .ast_nodes import (
    ActionDecl, AssignStmt, DerivedDecl, IfNode, RawStmt, ResourceDecl,
    StateDecl,
)
from .errors import PlainError, UnsupportedYet
from .expr import evaluate_text, execute_assign, truthy


class _Return(Exception):
    pass


class Scope:
    """Bindings for one page/component instance."""

    def __init__(self, decl_owner):
        self.decl_owner = decl_owner          # Page or Component AST
        self.state: dict = {}
        self.derived: list[DerivedDecl] = []
        self.actions: dict[str, ActionDecl] = {}
        self.resources: dict[str, ResourceDecl] = {}
        self.initialized = False

    def declarations(self):
        return self.decl_owner.body if self.decl_owner else []


class Runtime:
    def __init__(self, program):
        self.program = program
        self.scopes: dict[str, Scope] = {}
        self.shared: dict = {}
        self._shared_ready = False

    # -- scopes ---------------------------------------------------------
    def scope(self, path: str, decl_owner) -> Scope:
        sc = self.scopes.get(path)
        if sc is None:
            sc = Scope(decl_owner)
            self.scopes[path] = sc
            self._init_scope(sc)
        elif sc.decl_owner is not decl_owner:
            # Hot reload: same instance path, fresh AST. Keep state values
            # whose names still exist; initialize new names; drop removed
            # ones; refresh derivations/actions. (Doc 03 §10: "hot reload
            # that preserves state" — possible because state is declared.)
            sc.decl_owner = decl_owner
            self._init_scope(sc, preserve=True)
        return sc

    def _init_scope(self, sc: Scope, preserve: bool = False):
        self._init_shared()
        sc.derived = []
        declared = set()
        for stmt in sc.declarations():
            if isinstance(stmt, StateDecl):
                declared.add(stmt.name)
                if preserve and stmt.name in sc.state:
                    continue
                env = dict(self.shared)
                env.update(sc.state)
                sc.state[stmt.name] = evaluate_text(
                    stmt.expr, env, self.program.kinds, stmt.line_no)
            elif isinstance(stmt, DerivedDecl):
                sc.derived.append(stmt)
            elif isinstance(stmt, ActionDecl):
                sc.actions[stmt.name] = stmt
            elif isinstance(stmt, ResourceDecl):
                sc.resources[stmt.name] = stmt
        if preserve:
            for name in list(sc.state):
                if name not in declared:
                    del sc.state[name]
        sc.initialized = True

    def _init_shared(self):
        if self._shared_ready:
            return
        self._shared_ready = True
        for stmt in self.program.shared_decls:
            if isinstance(stmt, StateDecl):
                self.shared[stmt.name] = evaluate_text(
                    stmt.expr, dict(self.shared), self.program.kinds, stmt.line_no)

    def env_for(self, sc: Scope, extra: dict | None = None) -> dict:
        """Read-view: shared + state + derived (recomputed) + locals."""
        env = dict(self.shared)
        env.update(sc.state)
        if extra:
            env.update(extra)
        for d in sc.derived:  # decl order: later may use earlier
            env[d.name] = evaluate_text(d.expr, env, self.program.kinds, d.line_no)
        return env

    # -- execution ---------------------------------------------------------
    def run_event(self, sc: Scope, event, extra: dict | None = None):
        try:
            if event.action:
                self.call_action(sc, event.action, extra)
            for stmt in event.block:
                self.exec_stmt(sc, stmt, extra)
            if event.inline and not event.block:
                self.exec_text(sc, event.inline, extra, line_no=None)
        except _Return:
            pass

    def call_action(self, sc: Scope, call_src: str, extra: dict | None = None,
                    line_no=None):
        m = re.match(r"^([\w-]+)(?:\((.*)\))?$", call_src.strip())
        if not m:
            raise PlainError(f"I can't tell what action `{call_src}` is.",
                             line_no=line_no)
        name, arg_src = m.group(1), m.group(2)
        act = sc.actions.get(name)
        if act is None:
            raise PlainError(
                f"There's no action called `{name}` here. Actions are "
                f"written as `to {name}:` in this page/component.",
                line_no=line_no)
        locals_ = dict(extra or {})
        if arg_src:
            env = self.env_for(sc, locals_)
            values = [evaluate_text(a.strip(), env, self.program.kinds, line_no)
                      for a in _split_args(arg_src)]
            for p, v in zip(act.params, values):
                locals_[p] = v
        try:
            for stmt in act.body:
                self.exec_stmt(sc, stmt, locals_)
        except _Return:
            pass
        # action-local `name = …` for NEW names stay local; names that are
        # existing state were written through by exec (see below).

    def exec_text(self, sc: Scope, text: str, extra, line_no):
        """Execute an inline one-liner like `count += 1` / `add-task`."""
        text = text.strip()
        m = re.match(r"^([\w-]+(?:\.[\w-]+)*)\s*(\+=|-=|=)\s*(.+)$", text)
        if m:
            self._assign(sc, m.group(1), m.group(2), m.group(3), extra, line_no)
            return
        if re.match(r"^[\w-]+(\(.*\))?$", text) and text.split("(")[0] in sc.actions:
            self.call_action(sc, text, extra, line_no)
            return
        self.exec_stmt(sc, RawStmt(text, line_no or 0), extra)

    def _assign(self, sc, target, op, expr_src, extra, line_no):
        env = self.env_for(sc, extra)
        root = target.split(".")[0]
        # Write to shared if this name lives there, else instance state.
        write = self.shared if root in self.shared and root not in sc.state else sc.state
        execute_assign(target, op, expr_src, env, write,
                       self.program.kinds, line_no)

    def exec_stmt(self, sc: Scope, stmt, extra: dict | None = None):
        if isinstance(stmt, AssignStmt):
            # new names inside actions are locals unless known state/shared
            root = stmt.target.split(".")[0]
            if stmt.op == "=" and root not in sc.state and root not in self.shared \
                    and extra is not None:
                env = self.env_for(sc, extra)
                from .expr import evaluate_text as ev
                extra[stmt.target] = ev(stmt.expr, env, self.program.kinds, stmt.line_no)
                return
            self._assign(sc, stmt.target, stmt.op, stmt.expr, extra, stmt.line_no)
            return
        if isinstance(stmt, IfNode):
            env = self.env_for(sc, extra)
            if truthy(evaluate_text(stmt.condition, env, self.program.kinds, stmt.line_no)):
                if stmt.inline_then:
                    self.exec_text(sc, stmt.inline_then, extra, stmt.line_no)
                for s in stmt.then_body:
                    self.exec_stmt(sc, s, extra)
            else:
                for s in stmt.else_body:
                    self.exec_stmt(sc, s, extra)
            return
        if isinstance(stmt, RawStmt):
            self._exec_raw(sc, stmt, extra)
            return
        raise UnsupportedYet(f"statement `{type(stmt).__name__}` in actions",
                             "Stage 2", getattr(stmt, "line_no", None))

    def _exec_raw(self, sc: Scope, stmt: RawStmt, extra):
        text = stmt.text.strip()
        if text == "return":
            raise _Return()
        # list ops: `tasks add X` / `tasks remove X`
        m = re.match(r"^([\w-]+)\s+(add|remove)\s+(.+)$", text)
        if m:
            name, op, expr_src = m.groups()
            env = self.env_for(sc, extra)
            value = evaluate_text(expr_src, env, self.program.kinds, stmt.line_no)
            target = self.shared if name in self.shared else sc.state
            lst = target.get(name)
            if not isinstance(lst, list):
                raise PlainError(f"`{name}` isn't a list, so nothing can be "
                                 f"added to it.", line_no=stmt.line_no)
            if op == "add":
                lst.append(value)
            else:
                target[name] = [x for x in lst if x is not value and x != value]
            return
        if text.startswith("go to") or text == "go back":
            raise UnsupportedYet("navigation", "Stage 3", stmt.line_no, text)
        if text.startswith("show toast") or " then " in text:
            raise UnsupportedYet("toasts / `then` chains", "Stage 3", stmt.line_no, text)
        if re.match(r"^[\w-]+(\(.*\))?$", text):
            self.call_action(sc, text, extra, stmt.line_no)
            return
        raise UnsupportedYet(f"action line `{text.split()[0]} …`", "Stage 2/3",
                             stmt.line_no, text)

    def reset(self):
        self.scopes.clear()
        self.shared.clear()
        self._shared_ready = False


def _split_args(src: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in src:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts
