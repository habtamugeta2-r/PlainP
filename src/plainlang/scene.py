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

    def build_page(self, page, params: dict | None = None) -> SceneNode:
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
                local_derived[stmt.name] = stmt.expr  # scoped derivation
            elif isinstance(stmt, Node):
                env = self._env(sc, extra, local_derived)
                out.extend(self._build_node(stmt, sc, scope_path, env,
                                            child_path, slot_children,
                                            local_derived, extra))
            elif isinstance(stmt, IfNode):
                env = self._env(sc, extra, local_derived)
                try:
                    cond = truthy(evaluate_text(stmt.condition, env,
                                                self.program.kinds, stmt.line_no))
                except PlainError:
                    raise UnsupportedYet(
                        f"condition `{stmt.condition}` (needs container "
                        f"`width` or Stage-2+ values)", "Stage 2", stmt.line_no)
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
                raise UnsupportedYet("`when` over resources", "Stage 3",
                                     stmt.line_no)
            elif isinstance(stmt, RawStmt):
                raise UnsupportedYet(f"`{stmt.text.split()[0]}` in a visual "
                                     f"position", "Stage 2/3", stmt.line_no,
                                     stmt.text)
        return out

    def _env(self, sc, extra, local_derived):
        env = self.runtime.env_for(sc, extra)
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
        sn.children = self._build_block(_visual(node.children), sc, scope_path,
                                        extra, path, slot_children)
        return [sn]

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
        values += list(call.args)
        for name, v in zip(params, values):
            bound[name] = v
        for p in call.props:
            if p.name in params:
                if p.condition and not truthy(evaluate_text(
                        p.condition, caller_env, self.program.kinds, call.line_no)):
                    bound[p.name] = None
                else:
                    bound[p.name] = evaluate_text(p.value, caller_env,
                                                  self.program.kinds, call.line_no)
        inst_path = f"{path}#{comp.name}"
        inst_sc = self.runtime.scope(inst_path, comp)
        slot = self._build_block(_visual(call.children), caller_sc,
                                 call_scope_path(caller_sc), extra, path + "/slot",
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


def call_scope_path(sc) -> str:
    # SceneBuilder tracks scope by object identity in Runtime.scopes; this
    # helper is only used for slot children event binding metadata.
    return getattr(sc, "_path_hint", "")
