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

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from .ast_nodes import (
    ActionDecl, AssignStmt, DerivedDecl, ForNode, IfNode, KeepDecl, RawStmt,
    ResourceDecl, StateDecl, WhenNode,
)
from .errors import PlainError, UnsupportedYet
from .expr import evaluate_text, execute_assign, truthy


def _has_top_level_word(text: str, word: str) -> bool:
    """True when `word` appears outside string literals.

    `msg = "first then second"` is data, not a `then` chain; scanning the
    raw text would have made preflight reject a correct program.
    """
    in_str = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if text.startswith(word, i) and (i == 0 or not (
                text[i - 1].isalnum() or text[i - 1] in "_-")) and (
                i + len(word) == len(text) or not (
                text[i + len(word)].isalnum() or text[i + len(word)] in "_-")):
            return True
        i += 1
    return False


class _Return(Exception):
    pass


class Navigate(Exception):
    """`go to Page(args)` / `go back` — unwinds to App, which owns the stack."""

    def __init__(self, page_name=None, args=None, back=False):
        super().__init__(page_name or "back")
        self.page_name = page_name
        self.args = args or []
        self.back = back


# Resource values are ("ready", data) | ("failed", reason) | ("loading", None)
def _provider_lookup(source: str, providers: dict):
    """Sidecar/fixture value for a resource address, or None.

    Matching is exact, then `{param}`-collapsed, then last path segment —
    the same rule the preview has always used for sidecars.
    """
    if not providers:
        return None
    exact = [source, re.sub(r"\{[^}]*\}", "*", source)]
    # Exact and `{param}`-collapsed keys win over the loose last-segment
    # fallback, so `/rooms/r2/messages` never picks r1's fixture.
    for cand in exact:
        for key, val in providers.items():
            if key == cand or re.sub(r"\{[^}]*\}", "*", str(key)) == cand:
                return val
    last = source.rstrip("/").rsplit("/", 1)[-1]
    for key, val in providers.items():
        if str(key).rstrip("/").rsplit("/", 1)[-1] == last:
            return val
    return None


def _resource_match(decl: ResourceDecl, providers: dict):
    """Resolve a sidecar resource; unmatched resources are an honest failure."""
    val = _provider_lookup(decl.source.strip().strip('"'), providers)
    if val is None:
        return ("failed",
                "no data source is connected in this prototype yet")
    if isinstance(val, dict) and val.get("_failed"):
        return ("failed", str(val["_failed"]))
    return ("ready", val)


class Scope:
    """Bindings for one page/component instance."""

    def __init__(self, decl_owner):
        self.decl_owner = decl_owner          # Page or Component AST
        self.path: str = ""
        self.state: dict = {}
        self.derived: list[DerivedDecl] = []
        self.actions: dict[str, ActionDecl] = {}
        self.resources: dict[str, ResourceDecl] = {}
        self.keeps: set[str] = set()
        self.initialized = False

    def declarations(self):
        return self.decl_owner.body if self.decl_owner else []


class Runtime:
    def __init__(self, program, providers: dict | None = None,
                 persist_path: str | Path | None = None):
        self.program = program
        self.scopes: dict[str, Scope] = {}
        self.shared: dict = {}
        self._shared_ready = False
        self.providers = providers or {}
        self.persist_path = Path(persist_path) if persist_path else None
        self._store: dict | None = None
        self.toasts: list[str] = []
        self.last_request: dict | None = None
        self.resource_cache: dict[str, tuple] = {}
        self.resource_meta: dict[str, dict] = {}

    # -- persistence (`keep`) ---------------------------------------------
    @property
    def store(self) -> dict:
        if self._store is None:
            self._store = {}
            if self.persist_path and self.persist_path.exists():
                try:
                    self._store = json.loads(
                        self.persist_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    self._store = {}
        return self._store

    def save_kept(self):
        if not self.persist_path:
            return
        for sc in self.scopes.values():
            for name in sc.keeps:
                if name in sc.state:
                    self.store.setdefault(sc.path, {})[name] = sc.state[name]
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.persist_path.write_text(
            json.dumps(self.store, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8")

    def clear_persisted(self):
        self._store = {}
        if self.persist_path and self.persist_path.exists():
            self.persist_path.unlink()

    # -- scopes ---------------------------------------------------------
    def scope(self, path: str, decl_owner) -> Scope:
        sc = self.scopes.get(path)
        if sc is None:
            sc = Scope(decl_owner)
            sc.path = path
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
            elif isinstance(stmt, KeepDecl):
                sc.keeps.add(stmt.name)
        if not preserve and self.persist_path:
            saved = self.store.get(sc.path, {})
            for name in sc.keeps:
                if name in saved:
                    sc.state[name] = saved[name]
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
            elif isinstance(stmt, ResourceDecl):
                self.shared[stmt.name] = _resource_match(stmt, self.providers)

    def env_for(self, sc: Scope, extra: dict | None = None,
                resources: bool = True) -> dict:
        """Read-view: shared + state + derived (recomputed) + locals."""
        env = dict(self.shared)
        env.update(sc.state)
        if resources:
            for name, decl in sc.resources.items():
                env[name] = self._resource_value(sc, decl, extra)
        if extra:
            env.update(extra)
        for d in sc.derived:  # decl order: later may use earlier
            env[d.name] = evaluate_text(d.expr, env, self.program.kinds, d.line_no)
        return env

    # -- execution ---------------------------------------------------------
    def run_event(self, sc: Scope, event, extra: dict | None = None):
        # Refuse unsupported statements BEFORE running any of them: a chat
        # action must not clear `draft` and then discover `post` is missing.
        self.preflight(event.block)
        if event.inline and not event.block:
            self._preflight_text(event.inline, None)
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
        self.preflight(act.body)
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

    # -- preflight: no partial mutation before an honest failure ------------
    def preflight(self, stmts):
        for stmt in stmts or []:
            self._preflight_stmt(stmt)

    def _preflight_text(self, text: str, line_no, col=None):
        text = (text or "").strip()
        self._preflight_src(text, line_no, col, text)

    def _preflight_src(self, text: str, line_no, col=None, raw=""):
        # Every action statement has an implementation as of M1. Keep this
        # hook: a future statement must fail before earlier ones mutate state.
        return

    def _preflight_stmt(self, stmt):
        if isinstance(stmt, AssignStmt):
            self._preflight_src(stmt.expr.strip(), stmt.line_no, stmt.col,
                                stmt.raw or f"{stmt.target} {stmt.op} {stmt.expr}")
        elif isinstance(stmt, RawStmt):
            text = stmt.text.strip()
            self._preflight_src(text, stmt.line_no, stmt.col, stmt.raw or text)
            self.preflight(stmt.children)
        elif isinstance(stmt, IfNode):
            if stmt.inline_then:
                self._preflight_text(stmt.inline_then, stmt.line_no, stmt.col)
            self.preflight(stmt.then_body)
            self.preflight(stmt.else_body)
        elif isinstance(stmt, (ForNode, WhenNode)):
            body = stmt.body if isinstance(stmt, ForNode) else [
                s for br in stmt.branches for s in br.body]
            self.preflight(body)

    # -- resources: cache + refresh (NET-01/02/05/06 subset) ----------------
    def _resource_key(self, sc: Scope, decl: ResourceDecl, extra) -> str:
        # The address is part of the key: one page scope may render different
        # params (`/rooms/r1` vs `/rooms/r2`) without sharing stale data.
        return f"{sc.path}:{decl.name}:{self._resource_address(sc, decl, extra)}"

    def _resource_address(self, sc: Scope, decl: ResourceDecl, extra) -> str:
        src = decl.source.strip()
        if src.startswith("live "):
            src = src[len("live "):].strip()
        env = self.env_for(sc, extra, resources=False)
        try:
            val = evaluate_text(src, env, self.program.kinds, decl.line_no)
            return str(val)
        except PlainError:
            return src.strip('"')

    def _resource_value(self, sc: Scope, decl: ResourceDecl, extra=None,
                        force: bool = False) -> tuple:
        key = self._resource_key(sc, decl, extra)
        if not force and key in self.resource_cache:
            return self.resource_cache[key]
        value = self._load_resource(sc, decl, extra)
        self.resource_cache[key] = value
        meta = self.resource_meta.setdefault(key, {"attempts": 0})
        meta["attempts"] += 1
        meta["value"] = value[0]
        return value

    def _load_resource(self, sc: Scope, decl: ResourceDecl, extra=None) -> tuple:
        address = self._resource_address(sc, decl, extra)
        fixture = _provider_lookup(address, self.providers)
        if fixture is not None:
            if isinstance(fixture, dict) and fixture.get("_failed"):
                return ("failed", str(fixture["_failed"]))
            return ("ready", fixture)
        if address.startswith(("http://", "https://")):
            tag, value = _http_request("GET", address, None, "empty",
                                       decl.line_no)
            # Resources carry `ready`, request Results carry `ok`.
            return ("ready" if tag == "ok" else tag, value)
        return ("failed",
                f"no data source is connected for {address} in this prototype")

    def refresh(self, sc: Scope, name: str, extra=None, line_no=None):
        """`refresh messages` — drop the cached value and fetch once."""
        decl = sc.resources.get(name)
        if decl is None:
            raise PlainError(
                f"There's no resource called `{name}` to refresh.",
                line_no=line_no,
                hint=f"resources are declared as `{name} from \"/path\"`")
        return self._resource_value(sc, decl, extra, force=True)

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

    # -- network / request results (M1) ------------------------------------
    @staticmethod
    def _is_request(src: str) -> bool:
        return bool(re.match(r"^(post|fetch)\b", (src or "").strip()))

    def _write_value(self, sc, target: str, value, extra):
        parts = target.split(".")
        if len(parts) == 1:
            root = parts[0]
            if root in self.shared and root not in sc.state:
                self.shared[root] = value
            else:
                sc.state[root] = value
            return
        env = self.env_for(sc, extra)
        obj = env.get(parts[0])
        if not isinstance(obj, dict):
            raise PlainError(f"`{parts[0]}` isn't a record, so it has no "
                             f"parts to change.")
        obj[parts[-1]] = value

    def _request(self, src: str, sc: Scope, extra, line_no):
        """Evaluate `post URL [with … | body …]` / `fetch URL`.

        Result shape is Doc 03 §7.4: `("ok", value)` or
        `("failed", sentence)`. Relative URLs use sidecar fixtures keyed
        `"POST /path"` / `"FETCH /path"`; without one the prototype reports
        an honest offline failure instead of pretending. Absolute http(s)
        URLs use the stdlib transport (timeout, JSON when announced).
        """
        text = (src or "").strip()
        m = re.match(r"^(post|fetch)\s+(.+)$", text)
        if not m:
            raise PlainError(f"I couldn't read this request: `{text}`.",
                             line_no=line_no)
        method = m.group(1).lower()
        rest = m.group(2).strip()
        url_src, rest = _take_url_source(rest, line_no)
        env = self.env_for(sc, extra)
        url = evaluate_text(url_src, env, self.program.kinds, line_no)
        if not isinstance(url, str) or not url:
            raise PlainError("A request needs an address (a string).",
                             line_no=line_no, line_text=text,
                             hint='post "/api/signup"')
        body = None
        body_kind = "empty"
        rest = rest.strip()
        if rest.startswith("with "):
            arg_srcs = _split_args(rest[len("with "):])
            values = [evaluate_text(a.strip(), env, self.program.kinds, line_no)
                      for a in arg_srcs]
            if all(re.match(r"^[A-Za-z_][\w-]*(?:\.[\w-]+)*$", a.strip())
                   for a in arg_srcs):
                body = {a.strip().split(".")[-1]: v
                        for a, v in zip(arg_srcs, values)}
            else:
                body = values
            body_kind = "json"
        elif rest.startswith("body "):
            body = evaluate_text(rest[len("body "):], env,
                                 self.program.kinds, line_no)
            body_kind = "raw" if isinstance(body, (str, bytes)) else "json"
        elif rest:
            raise PlainError(
                f"I don't know how to send `{rest}` with a request.",
                line_no=line_no, line_text=text,
                hint="use `with value, value` or `body text`")

        method_upper = "POST" if method == "post" else "GET"
        fixture_method = "POST" if method == "post" else "FETCH"
        fixture = self._fixture_response(fixture_method, url)
        if fixture is not None:
            result = fixture
        elif url.startswith(("http://", "https://")):
            result = _http_request(method_upper, url, body, body_kind, line_no)
        else:
            result = ("failed", f"offline: no transport for {url} "
                                f"in this prototype yet")
        self.last_request = {"method": method_upper, "url": url,
                             "body": body, "result": result,
                             "line": line_no}
        return result

    def _fixture_response(self, method: str, url: str):
        prefix = method + " "
        for key, val in self.providers.items():
            if not isinstance(key, str) or not key.upper().startswith(prefix):
                continue
            pattern = key[len(prefix):]
            if not _url_matches(pattern, url):
                continue
            if isinstance(val, dict) and val.get("_failed"):
                return ("failed", str(val["_failed"]))
            if isinstance(val, dict) and "_ok" in val:
                return ("ok", val["_ok"])
            return ("ok", val)
        return None

    def _assign(self, sc, target, op, expr_src, extra, line_no):
        if op == "=" and self._is_request(expr_src):
            value = self._request(expr_src, sc, extra, line_no)
            root = target.split(".")[0]
            if root not in sc.state and root not in self.shared and extra is not None:
                extra[target] = value
            else:
                self._write_value(sc, target, value, extra)
            self.save_kept()
            return
        env = self.env_for(sc, extra)
        root = target.split(".")[0]
        # Write to shared if this name lives there, else instance state.
        write = self.shared if root in self.shared and root not in sc.state else sc.state
        execute_assign(target, op, expr_src, env, write,
                       self.program.kinds, line_no)

    def set_value(self, sc: Scope, target: str, value, extra=None, line_no=None):
        """Write a Python value to a bound target (`draft`, `task.done`)."""
        parts = target.split(".")
        if len(parts) == 1:
            root = parts[0]
            if root in self.shared and root not in sc.state:
                self.shared[root] = value
            else:
                sc.state[root] = value
            self.save_kept()
            return
        env = self.env_for(sc, extra)
        obj = env.get(parts[0])
        if not isinstance(obj, dict):
            raise PlainError(f"`{parts[0]}` isn't a record, so it has no "
                             f"parts to change.", line_no=line_no)
        obj[parts[-1]] = value
        self.save_kept()

    def get_value(self, sc: Scope, target: str, extra=None, line_no=None):
        env = self.env_for(sc, extra)
        return evaluate_text(target, env, self.program.kinds, line_no)

    def exec_stmt(self, sc: Scope, stmt, extra: dict | None = None):
        if isinstance(stmt, AssignStmt):
            # new names inside actions are locals unless known state/shared
            root = stmt.target.split(".")[0]
            if (stmt.op == "=" and root not in sc.state
                    and root not in self.shared and extra is not None
                    and not self._is_request(stmt.expr)):
                env = self.env_for(sc, extra)
                from .expr import evaluate_text as ev
                extra[stmt.target] = ev(stmt.expr, env, self.program.kinds, stmt.line_no)
                return
            self._assign(sc, stmt.target, stmt.op, stmt.expr, extra, stmt.line_no)
            return
        if isinstance(stmt, WhenNode):
            env = self.env_for(sc, extra)
            subject = evaluate_text(stmt.subject, env, self.program.kinds,
                                    stmt.line_no)
            branch, payload_name, payload = _match_when(subject, stmt)
            if branch is None:
                return
            bout = dict(extra or {})
            if payload_name:
                bout[payload_name] = payload
            for s in branch.body:
                self.exec_stmt(sc, s, bout)
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
        parts = _split_top_level_word(text, "then")
        if len(parts) > 1:
            for part in parts:
                self.exec_text(sc, part, extra, stmt.line_no)
            return
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
        if text == "go back":
            raise Navigate(back=True)
        m = re.match(r"^go to\s+(.+)$", text)
        if m:
            dest = m.group(1).strip()
            call = re.match(r"^([A-Z][\w-]*)(?:\((.*)\))?$", dest)
            env = self.env_for(sc, extra)
            if call:
                args = []
                if call.group(2):
                    args = [evaluate_text(a.strip(), env, self.program.kinds,
                                          stmt.line_no)
                            for a in _split_args(call.group(2))]
                raise Navigate(call.group(1), args)
            # `go to link.page` — destination is a value naming the page
            name = evaluate_text(dest, env, self.program.kinds, stmt.line_no)
            if isinstance(name, dict):
                name = name.get("page") or name.get("title")
            raise Navigate(str(name), [])
        if text.startswith("refresh "):
            self.refresh(sc, text[len("refresh "):].strip(), extra,
                         stmt.line_no)
            return
        if text.startswith("show toast"):
            msg = evaluate_text(text[len("show toast"):].strip(),
                                self.env_for(sc, extra), self.program.kinds,
                                stmt.line_no)
            self.toasts.append(str(msg))
            return
        if self._is_request(text):
            self._request(text, sc, extra, stmt.line_no)
            return
        if re.match(r"^[\w-]+(\(.*\))?$", text):
            self.call_action(sc, text, extra, stmt.line_no)
            return
        raise UnsupportedYet(f"action line `{text.split()[0]} …`", "Stage 2/3",
                             stmt.line_no, text)

    def reset(self):
        self.scopes.clear()
        self.shared.clear()
        self._shared_ready = False
        self.toasts.clear()
        self.last_request = None
        self.resource_cache.clear()
        self.resource_meta.clear()


def _take_url_source(rest: str, line_no=None) -> tuple[str, str]:
    """First request argument: a quoted string or one bare token."""
    if not rest:
        raise PlainError("A request needs an address.", line_no=line_no)
    if rest[0] == '"':
        out, i, escaped = ['"'], 1, False
        while i < len(rest):
            ch = rest[i]
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                return "".join(out), rest[i + 1:]
            i += 1
        raise PlainError("This string never closes.", line_no=line_no,
                         line_text=rest)
    parts = rest.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _url_matches(pattern: str, url: str) -> bool:
    collapse = lambda s: re.sub(r"\{[^}]*\}", "*", str(s))
    return (pattern == url or collapse(pattern) == collapse(url)
            or pattern.rstrip("/").rsplit("/", 1)[-1]
            == url.rstrip("/").rsplit("/", 1)[-1])


def _http_request(method: str, url: str, body, body_kind: str,
                  line_no=None):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        if body_kind == "json":
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            data = (body if isinstance(body, bytes)
                    else str(body).encode("utf-8"))
            headers["Content-Type"] = "text/plain; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" in ctype:
                return ("ok", json.loads(raw.decode("utf-8")))
            return ("ok", raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return ("failed", f"server {e.code}")
    except urllib.error.URLError as e:
        return ("failed", f"offline: {getattr(e, 'reason', e)}")
    except (TimeoutError, OSError) as e:
        return ("failed", f"offline: {e}")
    except ValueError as e:  # invalid JSON from the server
        return ("failed", f"bad response: {e}")


def _match_when(subject, when_node):
    """Match a result/resource tuple against `is` branches."""
    if isinstance(subject, tuple) and len(subject) == 2:
        tag, payload = subject
    else:
        tag, payload = "ready", subject
    for br in when_node.branches:
        parts = br.pattern.split()
        if parts and parts[0] == tag:
            return br, (parts[1] if len(parts) > 1 else None), payload
    return None, None, None


def _split_top_level_word(text: str, word: str) -> list[str]:
    """Split `a then b` outside strings/brackets. `then` in data is safe."""
    parts, cur = [], []
    depth = 0
    in_str = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            cur.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            cur.append(ch)
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if (depth == 0 and text.startswith(word, i)
                and (i == 0 or text[i - 1] in " \t")
                and (i + len(word) == len(text)
                     or text[i + len(word)] in " \t")):
            parts.append("".join(cur).strip())
            cur = []
            i += len(word)
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


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
