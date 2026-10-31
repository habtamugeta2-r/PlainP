"""AST for PL (v0.1 spec, Doc 03). Expressions are kept as source text and
parsed on demand by expr.py — deliberate for Stage 1: the parser must accept
the whole normative corpus (examples 00-08) while the evaluator grows.

Every statement carries its 1-based column and raw line text (Doc 03 §10:
errors point at the token, not just the line). `line_no` stays the primary
location; `col`/`raw` exist for carets and future Looking Glass source maps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import urllib.parse


@dataclass
class Line:
    """One logical source line in the indentation block tree."""
    text: str                       # comment-stripped, trimmed
    no: int                         # 1-based source line number
    level: int                      # indent level (2 spaces each)
    col: int = 1                    # 1-based column of the first character
    children: list["Line"] = field(default_factory=list)


# ---- node-line pieces -------------------------------------------------------

@dataclass
class Prop:
    name: str
    value: str = ""                 # detokenized value expression/text
    condition: str | None = None    # `prop val if <condition>`
    otherwise: "Prop | None" = None  # `... otherwise prop val2`
    line_no: int | None = None
    col: int | None = None          # 1-based column of the prop name
    length: int = 1                 # token length (for carets)


@dataclass
class Flag:
    name: str
    condition: str | None = None
    line_no: int | None = None
    col: int | None = None
    length: int = 1


@dataclass
class Event:
    name: str                       # tap, submit, change, swipe-start, ...
    param: str | None = None        # binder name (`on change value:`)
    inline: str | None = None       # statement after `:` on same line
    action: str | None = None       # action call source (`add-task`, `save(x)`)
    block: list = field(default_factory=list)  # classified statements
    line_no: int | None = None
    col: int | None = None          # 1-based column of `on`
    length: int = 1
    raw: str = ""                   # the event line (child `on …` lines too)


@dataclass
class Node:
    kind: str
    line_no: int
    content: str | None = None      # quoted-string content (raw, uninterpolated)
    content_expr: str | None = None  # expression content (`text task.title`)
    props: list[Prop] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    children: list = field(default_factory=list)  # Node/If/For/When/Derived/Raw
    args: list = field(default_factory=list)      # component-call positional args
    col: int = 1
    raw: str = ""                   # the node line as written (for carets)
    length: int = 1                 # length of the node kind token

    def prop(self, name: str) -> Prop | None:
        for p in self.props:
            if p.name == name:
                return p
        return None

    def has_flag(self, name: str) -> bool:
        return any(f.name == name for f in self.flags)

    def event(self, name: str) -> Event | None:
        for e in self.events:
            if e.name == name:
                return e
        return None


# ---- statements / declarations ----------------------------------------------

@dataclass
class StateDecl:
    name: str
    expr: str
    line_no: int
    type_hint: str | None = None
    shared: bool = False
    col: int = 1
    raw: str = ""


@dataclass
class DerivedDecl:
    name: str
    expr: str
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class AssignStmt:
    target: str
    op: str                         # =, +=, -=
    expr: str
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class ActionDecl:
    name: str
    params: list[str]
    body: list
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class ResourceDecl:
    name: str
    source: str                     # everything after `from`
    line_no: int
    shared: bool = False
    col: int = 1
    raw: str = ""


@dataclass
class KeepDecl:
    name: str
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class RawStmt:
    """Anything the Stage-1 classifier doesn't own yet (go to, return,
    `tasks add …` at parse level, transition, …). Kept so parsing the full
    corpus never crashes; runtime/checker decide what they support."""
    text: str
    line_no: int
    children: list = field(default_factory=list)
    col: int = 1
    raw: str = ""


@dataclass
class IfNode:
    condition: str
    then_body: list
    else_body: list = field(default_factory=list)
    line_no: int = 0
    inline_then: str | None = None  # `if cond: return`
    col: int = 1
    raw: str = ""


@dataclass
class ForNode:
    var: str
    index_var: str | None
    iterable: str
    body: list
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class WhenBranch:
    pattern: str                    # `loading`, `failed why`, `ready items`
    body: list
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class WhenNode:
    subject: str
    branches: list[WhenBranch]
    line_no: int
    col: int = 1
    raw: str = ""


# ---- top level ---------------------------------------------------------------

@dataclass
class KindField:
    name: str
    type_hint: str | None = None
    default: str | None = None
    line_no: int | None = None
    col: int = 1


@dataclass
class KindDecl:
    name: str
    fields: list[KindField]
    line_no: int
    col: int = 1
    raw: str = ""


@dataclass
class LookDecl:
    name: str
    props: list[Prop] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    line_no: int = 0
    col: int = 1
    raw: str = ""


@dataclass
class Component:
    name: str
    params: list[str]
    body: list                      # decls + visual roots, classified
    line_no: int
    # `component Avatar(person, size = 40)` — defaults evaluated in the caller
    # environment at call time (Doc 03 §6.3).
    defaults: dict = field(default_factory=dict)
    col: int = 1
    raw: str = ""


@dataclass
class Page:
    name: str
    params: list[str]
    path: str | None
    body: list
    line_no: int
    defaults: dict = field(default_factory=dict)
    col: int = 1
    raw: str = ""


@dataclass(frozen=True)
class Capability:
    """A top-level `needs` capability grant (Doc 01 §5, Doc 03 §8)."""
    kind: str                       # e.g. "network", "storage", "camera"
    target: str | None = None       # host[:port] for `network`, lib for `native`
    line_no: int = 0
    col: int = 1
    raw: str = ""
    length: int = 1

    def label(self) -> str:
        return f"{self.kind} {self.target}" if self.target else self.kind


@dataclass
class Program:
    needs: list[str] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    kinds: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    looks: dict = field(default_factory=dict)
    shared_decls: list = field(default_factory=list)
    themes: list = field(default_factory=list)   # theme declarations (Stage 3)
    uses: list = field(default_factory=list)     # module imports (Stage 3+)
    deferred: list = field(default_factory=list)  # stray top-level lines

    def first_page(self) -> Page | None:
        return next(iter(self.pages.values()), None)

    def has_capability(self, kind: str) -> bool:
        return any(c.kind == kind for c in self.capabilities)

    def allows_network_url(self, url: str) -> tuple[bool, str]:
        """Return `(allowed, host_or_reason)` for an outgoing URL."""
        parsed = urllib.parse.urlsplit(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            return False, f"scheme `{scheme or 'unknown'}`"
        if not parsed.hostname:
            return False, url
        host = parsed.hostname.lower()
        try:
            port = parsed.port
        except ValueError:
            return False, host
        host_port = f"{host}:{port}" if port is not None else host
        for cap in self.capabilities:
            if cap.kind != "network" or not cap.target:
                continue
            tgt = cap.target.strip().lower()
            if ":" in tgt and not tgt.endswith("]"):
                if tgt == host_port:
                    return True, host_port
            elif tgt.strip("[]") == host:
                return True, host_port
        return False, host_port
