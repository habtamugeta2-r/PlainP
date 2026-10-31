"""Scene graph construction (Doc 02 §1): expand a page into ONE visual tree.

Components expand to built-in nodes; `if`/`for` are resolved against the
runtime; looks are merged (explicit props win); every scene node carries
its source line (Doc 01 invariant 4 — powers Looking Glass later) and a
stable path id (used by the preview server for tap dispatch).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ast_nodes import (
    DerivedDecl, Event, ForNode, IfNode, Node, RawStmt, WhenNode,
)
from .errors import PlainError, UnsupportedYet
from .expr import evaluate_text, interpolate, truthy

SUPPORTED_NODES = {
    "column", "row", "stack", "grid", "scroll", "box", "text", "image",
    "button", "input", "toggle", "divider", "spacer", "spinner", "children",
    "table", "header", "cell", "scene3d",
}

DEFAULT_THEME = {
    "ink": "#16161A", "paper": "#FFFFFF", "surface": "#F4F4F6",
    "accent": "#5B5BD6", "accent-deep": "#4343B8", "accent-soft": "#E6E6FA",
    "on-accent": "#FFFFFF", "muted": "#6E6E7A", "danger": "#D64545",
    "danger-soft": "#FDECEC", "paper-muted": "#C9C9D1",
}


@dataclass
class SceneNode:
    kind: str
    source_line: int
    path: str
    text: str = ""
    props: dict = field(default_factory=dict)    # resolved, typed-ish values
    flags: set = field(default_factory=set)
    children: list = field(default_factory=list)
    events: dict = field(default_factory=dict)  # name -> (Event, scope_path, extra)
    scope_path: str = ""
    bind: tuple | None = None  # (target, scope_path, extra) for input/toggle
    # layout results
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def find(self, path: str):
        for n in self.walk():
            if n.path == path:
                return n
        return None


class SceneBuilder:
    def __init__(self, program, runtime):
        self.program = program
        self.runtime = runtime
        self._counter = 0
        self._sizes: list[tuple[float, float]] = [(800.0, 600.0)]

    def build_page(self, page, params: dict | None = None,
                   viewport: tuple[float, float] = (800.0, 600.0)) -> SceneNode:
        self._sizes = [viewport]
        scope_path = f"page:{page.name}"
        sc = self.runtime.scope(scope_path, page)
        extra = dict(params or {})
        root = SceneNode(kind="page", source_line=page.line_no,
                         path="root", scope_path=scope_path)
        root.children = self._build_block(
            _visual(page.body), sc, scope_path, extra, "root", None)
        return root

    # -- blocks -----------------------------------------------------------
    def _build_block(self, stmts, sc, scope_path, extra, path, slot_children):
        out: list[SceneNode] = []
        local_derived: dict[str, str] = {}
        for stmt in stmts:
            idx = len(out)
            child_path = f"{path}/{idx}"
            if isinstance(stmt, DerivedDecl):
                # Scoped derivation: evaluate now and bind for every
                # following sibling (and their subtrees) via `extra`.
                env = self._env(sc, extra, local_derived)
                extra = {**extra,
                         stmt.name: evaluate_text(stmt.expr, env,
                                                  self.program.kinds,
                                                  stmt.line_no)}
                local_derived[stmt.name] = stmt.expr
            elif isinstance(stmt, Node):
                env = self._env(sc, extra, local_derived)
                out.extend(self._build_node(stmt, sc, scope_path, env,
                                            child_path, slot_children,
                                            local_derived, extra))
            elif isinstance(stmt, IfNode):
                env = self._env(sc, extra, local_derived)
                cond = truthy(evaluate_text(stmt.condition, env,
                                            self.program.kinds, stmt.line_no))
                body = stmt.then_body if cond else stmt.else_body
                out.extend(self._build_block(body, sc, scope_path,
                                             extra, child_path, slot_children))
            elif isinstance(stmt, ForNode):
                env = self._env(sc, extra, local_derived)
                items = evaluate_text(stmt.iterable, env, self.program.kinds,
                                      stmt.line_no)
                if items is None:
                    items = []
                for n, item in enumerate(items):
                    item_extra = dict(extra)
                    item_extra[stmt.var] = item
                    if stmt.index_var:
                        item_extra[stmt.index_var] = n
                    out.extend(self._build_block(stmt.body, sc, scope_path,
                                                 item_extra, f"{child_path}:{n}",
                                                 slot_children))
            elif isinstance(stmt, WhenNode):
                env = self._env(sc, extra, local_derived)
                subject = evaluate_text(stmt.subject, env, self.program.kinds,
                                        stmt.line_no)
                branch, payload_name, payload = _match_branch(subject, stmt)
                if branch is not None:
                    bout = dict(extra)
                    if payload_name:
                        bout[payload_name] = payload
                    out.extend(self._build_block(branch.body, sc, scope_path,
                                                 bout, child_path, slot_children))
            elif isinstance(stmt, RawStmt):
                if stmt.text.startswith("transition"):
                    continue  # motion metadata; animation lands in Stage 3+
                raise UnsupportedYet(f"`{stmt.text.split()[0]}` in a visual "
                                     f"position", "Stage 2/3", stmt.line_no,
                                     stmt.text)
        return out

    def _env(self, sc, extra, local_derived):
        env = self.runtime.env_for(sc, extra)
        w, h = self._sizes[-1]
        env.setdefault("width", w)       # container size builtins (Doc 03
        env.setdefault("height", h)     # §5.3) — program state may shadow
        env.setdefault("narrow", w < 600)
        for name, expr in local_derived.items():
            env[name] = evaluate_text(expr, env, self.program.kinds)
        return env

    # -- nodes --------------------------------------------------------------
    def _build_node(self, node: Node, sc, scope_path, env, path,
                    slot_children, local_derived, extra) -> list[SceneNode]:
        comp = self.program.components.get(node.kind)
        if comp is not None:
            return self._expand_component(node, comp, sc, scope_path, env, path, extra)
        if node.kind == "children":
            return list(slot_children or [])
        if node.kind[:1].isupper():
            if node.kind in STDLIB_COMPONENTS:
                return STDLIB_COMPONENTS[node.kind](self, node, env, path, scope_path)
            raise UnsupportedYet(f"component `{node.kind}` (not defined in "
                                 f"this file — stdlib/Openly)", "Stage 3/4",
                                 node.line_no)
        if node.kind not in SUPPORTED_NODES:
            raise UnsupportedYet(f"node `{node.kind}`", "Stage 2/3", node.line_no)

        sn = SceneNode(kind=node.kind, source_line=node.line_no, path=path,
                       scope_path=scope_path)
        sn.text = self._node_text(node, env)
        self._resolve_props(node, sn, env)
        for ev in node.events:
            sn.events[ev.name] = (ev, scope_path, dict(extra))
        self._bind_value(node, sn, env, scope_path, extra)

        if node.kind == "scene3d":
            # Prototype: a labeled 3D viewport placeholder. Its AST children
            # (camera/light/model3d/parts) are engine data, not 2D scenes.
            for ch in node.children:
                if isinstance(ch, Node) and ch.kind == "model3d":
                    sn.text = ch.content or sn.text
            return [sn]

        # Scoped derivations that ARE layout inputs (grid `columns is …`)
        for ch in node.children:
            if isinstance(ch, DerivedDecl):
                sn.props.setdefault(ch.name, evaluate_text(
                    ch.expr, env, self.program.kinds, ch.line_no))

        self._sizes.append(_child_size(sn, self._sizes[-1]))
        try:
            sn.children = self._build_block(_visual(node.children), sc, scope_path,
                                            extra, path, slot_children)
        finally:
            self._sizes.pop()
        return [sn]

    def _bind_value(self, node, sn, env, scope_path, extra):
        bind = node.prop("bind")
        if bind is None:
            return
        target = bind.value.strip()
        sn.bind = (target, scope_path, dict(extra))
        try:
            val = evaluate_text(target, env, self.program.kinds, node.line_no)
        except PlainError:
            val = None
        if node.kind == "input":
            from .expr import display
            sn.text = display(val) if val is not None else ""
        elif node.kind == "toggle":
            sn.props["_on"] = bool(val)

    def _expand_component(self, call: Node, comp, caller_sc, caller_scope_path,
                          caller_env, path, extra):
        # bind params: positional content first, then named props
        bound: dict = {}
        params = [p for p in comp.params if p != "children"]
        values = []
        if call.content is not None:
            values.append(interpolate(call.content, caller_env,
                                      self.program.kinds, call.line_no))
        elif call.content_expr is not None:
            values.append(evaluate_text(call.content_expr, caller_env,
                                        self.program.kinds, call.line_no))
        values += [evaluate_text(arg, caller_env, self.program.kinds,
                                 call.line_no) for arg in call.args]
        if len(values) > len(params):
            extra = len(values) - len(params)
            raise PlainError(
                f"`{comp.name}` takes {len(params)} value"
                f"{'s' if len(params) != 1 else ''}, but got {len(values)}.",
                line_no=call.line_no, line_text=call.raw or None,
                col=call.col, length=max(1, len(comp.name)),
                hint="check the component's parameter list, or pass the "
                     "extra value as a named property")
        for name, v in zip(params, values):
            bound[name] = v
        for p in call.props:
            if p.name in params:
                if p.name in bound:
                    raise PlainError(
                        f"`{p.name}` is given twice to `{comp.name}`.",
                        line_no=call.line_no, line_text=call.raw or None,
                        col=p.col, length=p.length,
                        hint="pass it once — positionally or by name")
                if p.condition and not truthy(evaluate_text(
                        p.condition, caller_env, self.program.kinds, call.line_no)):
                    # Conditioning a param out binds `nothing`, unless a
                    # default exists (then the default applies below).
                    if p.name not in getattr(comp, "defaults", {}):
                        bound[p.name] = None
                    continue
                bound[p.name] = evaluate_text(p.value, caller_env,
                                              self.program.kinds, call.line_no)
        missing = [p for p in params
                   if p not in bound and p not in getattr(comp, "defaults", {})]
        if missing:
            raise PlainError(
                f"`{comp.name}` needs `{missing[0]}`.",
                line_no=call.line_no, line_text=call.raw or None,
                col=call.col, length=max(1, len(comp.name)),
                hint=f'pass a value, e.g. `{comp.name} "Ada"`')
        # Defaults are evaluated in the caller's environment, after explicit
        # args, so `size = 40` (Doc 03 §6.3) actually applies.
        for pname in params:
            if pname in bound:
                continue
            default_src = getattr(comp, "defaults", {}).get(pname)
            if default_src is not None:
                denv = dict(caller_env)
                denv.update(bound)
                bound[pname] = evaluate_text(default_src, denv,
                                             self.program.kinds, call.line_no)
        inst_path = f"{path}#{comp.name}"
        inst_sc = self.runtime.scope(inst_path, comp)
        slot = self._build_block(_visual(call.children), caller_sc,
                                 caller_scope_path, extra, path + "/slot",
                                 None) if call.children else []
        merged_extra = dict(bound)
        return self._build_block(_visual(comp.body), inst_sc, inst_path,
                                 merged_extra, path, slot)

    # -- text & props ---------------------------------------------------------
    def _node_text(self, node: Node, env) -> str:
        if node.content is not None:
            txt = interpolate(node.content, env, self.program.kinds, node.line_no)
        elif node.content_expr is not None:
            from .expr import display
            txt = display(evaluate_text(node.content_expr, env,
                                        self.program.kinds, node.line_no))
        else:
            return ""
        if node.has_flag("capitalize"):
            txt = txt.capitalize()
        return txt

    def _resolve_props(self, node: Node, sn: SceneNode, env):
        # looks first (explicit wins)
        raw_props = []
        for p in node.props:
            if p.name == "look":
                chosen = self._choose_look(p, env, node)
                if chosen:
                    raw_props = list(chosen.props) + raw_props
                    for f in chosen.flags:
                        sn.flags.add(f.name)
        raw_props += [p for p in node.props if p.name != "look"]

        for p in raw_props:
            self._apply_prop(sn, p, env, node)
        for f in node.flags:
            if f.condition:
                if truthy(evaluate_text(f.condition, env, self.program.kinds,
                                        node.line_no)):
                    sn.flags.add(f.name)
            else:
                sn.flags.add(f.name)

    def _choose_look(self, prop, env, node):
        name = prop.value.strip()
        if prop.condition:
            cond = truthy(evaluate_text(prop.condition, env,
                                        self.program.kinds, node.line_no))
            if not cond:
                if prop.otherwise:
                    name = prop.otherwise.value.strip()
                else:
                    return None
        look = self.program.looks.get(name)
        if look is None:
            raise PlainError(
                f"There's no look called `{name}`. Looks are written as "
                f"`look {name}:` in this file.", line_no=node.line_no)
        return look

    def _apply_prop(self, sn: SceneNode, p, env, node):
        if p.condition:
            cond = truthy(evaluate_text(p.condition, env, self.program.kinds,
                                        node.line_no))
            if not cond:
                if p.otherwise is not None:
                    p = p.otherwise
                else:
                    return
        sn.props[p.name] = resolve_value(p.name, p.value, env,
                                         self.program.kinds, node.line_no)


_NUMERIC_PROPS = {"gap", "size", "corners", "opacity", "weight", "columns"}


def resolve_value(name: str, raw: str, env, kinds, line_no):
    raw = (raw or "").strip()
    if name == "padding":
        nums = [float(x) for x in raw.split()] or [0]
        return nums
    if name in ("width", "height"):
        return parse_size_spec(raw)
    if name in _NUMERIC_PROPS:
        try:
            return float(raw.rstrip("%"))
        except ValueError:
            return evaluate_text(raw, env, kinds, line_no)
    if name in ("color", "background"):
        if raw in DEFAULT_THEME or raw.startswith("#"):
            return raw
        try:  # expression like finish.tint
            v = evaluate_text(raw, env, kinds, line_no)
            return v if isinstance(v, str) else raw
        except PlainError:
            return raw
    if name in ("placeholder", "label"):
        if raw.startswith('"') and raw.endswith('"'):
            return interpolate(raw[1:-1], env, kinds, line_no)
        try:
            from .expr import display
            return display(evaluate_text(raw, env, kinds, line_no))
        except PlainError:
            return raw
    if name == "bind":
        return raw
    if name == "id":
        if raw.startswith('"') and raw.endswith('"'):
            return interpolate(raw[1:-1], env, kinds, line_no)
        return raw
    if name == "aspect":
        if "/" in raw:
            a, b = raw.split("/")
            return float(a) / float(b)
        return float(raw)
    # align/spread/shape/fit/enter/exit/animate/shadow/autocomplete/kind/error…
    return raw


def parse_size_spec(raw: str) -> dict:
    """`fill`, `fill max 560`, `280`, `max 75%`, `fit` → spec dict."""
    parts = raw.split()
    spec = {"mode": "fit", "value": None, "max": None, "min": None}
    i = 0
    while i < len(parts):
        w = parts[i]
        if w in ("fill", "fit"):
            spec["mode"] = w
        elif w in ("max", "min") and i + 1 < len(parts):
            spec[w] = parts[i + 1]
            i += 1
        else:
            spec["mode"] = "fixed"
            spec["value"] = w
        i += 1
    return spec


def _visual(stmts):
    """Filter a classified block to visual + scoped-derivation statements."""
    return [s for s in stmts
            if isinstance(s, (Node, IfNode, ForNode, WhenNode, RawStmt,
                              DerivedDecl))]


def _match_branch(subject, when_node):
    """Match a resource/result tuple against `is` branches.
    Returns (branch, payload_name|None, payload)."""
    if isinstance(subject, tuple) and len(subject) == 2:
        tag, payload = subject
    else:
        tag, payload = "ready", subject
    for br in when_node.branches:
        parts = br.pattern.split()
        if parts and parts[0] == tag:
            return br, (parts[1] if len(parts) > 1 else None), payload
    return None, None, None


def _child_size(sn, avail):
    """Available size for a node's children: own size spec + padding."""
    w, h = avail
    spec = sn.props.get("width") or {}
    if isinstance(spec, dict):
        if spec.get("mode") == "fixed":
            try:
                w = float(str(spec.get("value")).rstrip("%")) * (w / 100 if str(spec.get("value")).endswith("%") else 1)
            except ValueError:
                pass
        if spec.get("max"):
            try:
                mx = str(spec["max"])
                w = min(w, float(mx.rstrip("%")) * (w / 100 if mx.endswith("%") else 1))
            except ValueError:
                pass
    pad = sn.props.get("padding") or []
    if len(pad) == 1:
        w, h = w - 2 * pad[0], h - 2 * pad[0]
    elif len(pad) >= 2:
        w, h = w - 2 * pad[1], h - 2 * pad[0]
    return (max(w, 0.0), max(h, 0.0))


def _stdlib_error_box(builder, node, env, path, scope_path):
    msg = builder._node_text(node, env)
    box = SceneNode(kind="box", source_line=node.line_no, path=path,
                    scope_path=scope_path,
                    props={"background": "danger-soft", "corners": 10.0,
                           "padding": [14.0, 16.0]})
    txt = SceneNode(kind="text", source_line=node.line_no, path=path + "/0",
                    scope_path=scope_path, text=f"⚠ {msg}",
                    props={"color": "danger", "size": 15.0})
    box.children = [txt]
    return [box]


# Tiny stdlib surface that ships with the runtime (Doc 01 §6.1) — grows
# toward the full control set; each entry is implemented against the same
# scene primitives user components get.
STDLIB_COMPONENTS = {
    "ErrorBox": _stdlib_error_box,
}
