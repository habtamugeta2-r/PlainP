"""AST for PL (v0.1 spec, Doc 03). Expressions are kept as source text and
parsed on demand by expr.py — deliberate for Stage 1: the parser must accept
the whole normative corpus (examples 00-08) while the evaluator grows.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Line:
    """One logical source line in the indentation block tree."""
    text: str                       # comment-stripped, trimmed
    no: int                         # 1-based source line number
    level: int                      # indent level (2 spaces each)
    children: list["Line"] = field(default_factory=list)


# ---- node-line pieces -------------------------------------------------------

@dataclass
class Prop:
    name: str
    value: str = ""                 # detokenized value expression/text
    condition: str | None = None    # `prop val if <condition>`
    otherwise: "Prop | None" = None  # `... otherwise prop val2`


@dataclass
class Flag:
    name: str
    condition: str | None = None


@dataclass
class Event:
    name: str                       # tap, submit, change, swipe-start, ...
    param: str | None = None        # binder name (`on change value:`)
    inline: str | None = None       # statement after `:` on same line
    action: str | None = None       # action call source (`add-task`, `save(x)`)
    block: list = field(default_factory=list)  # classified statements


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


@dataclass
class DerivedDecl:
    name: str
    expr: str
    line_no: int


@dataclass
class AssignStmt:
    target: str
    op: str                         # =, +=, -=
    expr: str
    line_no: int


@dataclass
class ActionDecl:
    name: str
    params: list[str]
    body: list
    line_no: int


@dataclass
class ResourceDecl:
    name: str
    source: str                     # everything after `from`
    line_no: int
    shared: bool = False


@dataclass
class KeepDecl:
    name: str
    line_no: int


@dataclass
class RawStmt:
    """Anything the Stage-1 classifier doesn't own yet (go to, return,
    `tasks add …` at parse level, transition, …). Kept so parsing the full
    corpus never crashes; runtime/checker decide what they support."""
    text: str
    line_no: int
    children: list = field(default_factory=list)


@dataclass
class IfNode:
    condition: str
    then_body: list
    else_body: list = field(default_factory=list)
    line_no: int = 0
    inline_then: str | None = None  # `if cond: return`


@dataclass
class ForNode:
    var: str
    index_var: str | None
    iterable: str
    body: list
    line_no: int


@dataclass
class WhenBranch:
    pattern: str                    # `loading`, `failed why`, `ready items`
    body: list
    line_no: int


@dataclass
class WhenNode:
    subject: str
    branches: list[WhenBranch]
    line_no: int


# ---- top level ---------------------------------------------------------------

@dataclass
class KindField:
    name: str
    type_hint: str | None = None
    default: str | None = None


@dataclass
class KindDecl:
    name: str
    fields: list[KindField]
    line_no: int


@dataclass
class LookDecl:
    name: str
    props: list[Prop] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    line_no: int = 0


@dataclass
class Component:
    name: str
    params: list[str]
    body: list                      # decls + visual roots, classified
    line_no: int


@dataclass
class Page:
    name: str
    params: list[str]
    path: str | None
    body: list
    line_no: int


@dataclass
class Program:
    needs: list[str] = field(default_factory=list)
    kinds: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    looks: dict = field(default_factory=dict)
    shared_decls: list = field(default_factory=list)
    themes: list = field(default_factory=list)  # RawStmt placeholders Stage 1

    def first_page(self) -> Page | None:
        return next(iter(self.pages.values()), None)
