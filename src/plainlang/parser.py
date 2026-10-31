"""PL parser: source → indentation block tree → classified AST.

Stages:
  1. logical lines: strip comments, join `and`/`or` continuations,
     validate indentation (2 spaces, no tabs) with plain errors.
  2. block tree: children = following lines one level deeper.
  3. classification: declarations vs nodes vs control flow. Unknown lines
     become RawStmt — parsing the full normative corpus (examples 00–08,
     incl. Stage-2/3 features) must never crash; the checker/renderer
     decide what they support.

Node-line property parsing is table-driven (VALUE_PROPS/FLAGS below are the
single source of truth shared with checker.py). Inline conditional props
(`strike if done`, `look a if c otherwise look b`) are THE one spelling
(resolves examples/README pressure point 1 — see docs/06).
"""
from __future__ import annotations

import re

from . import tokens as T
from .ast_nodes import (
    ActionDecl, AssignStmt, Capability, Component, DerivedDecl, Event, Flag,
    ForNode, IfNode, KeepDecl, KindDecl, KindField, Line, LookDecl, Node, Page,
    Program, Prop, RawStmt, ResourceDecl, StateDecl, WhenBranch, WhenNode,
)
from .errors import PlainError

# Built-in node kinds known to the language (renderer supports a Stage-1
# subset — see scene.py SUPPORTED_NODES).
NODE_KINDS = {
    "column", "row", "stack", "grid", "scroll", "box", "text", "image",
    "video", "audio", "canvas", "button", "input", "textarea", "toggle",
    "slider", "select", "link", "divider", "spacer", "spinner", "table",
    "header", "cell", "scene3d", "model3d", "camera", "light", "children",
    "material", "part",
}

# props taking one value token (value captured with member/call chaining)
VALUE_PROPS_1 = {
    "gap", "size", "color", "background", "corners", "align", "spread",
    "label", "placeholder", "aspect", "id", "shape", "fit", "weight",
    "font", "opacity", "enter", "exit", "shadow", "bind", "autocomplete",
    "kind", "columns", "level", "lines", "ring",
}
# props whose value is a free expression up to `if`/next-prop/EOL
VALUE_PROPS_EXPR = {"error", "value", "scale", "rotate-y", "rotate", "retry"}
# props taking a name then expression args (kept raw)
SPECIAL_PROPS = {"width", "height", "padding", "animate", "look", "at",
                 "look-at", "angle", "stagger"}

FLAGS = {
    "bold", "plain", "primary", "grow", "center", "center-self", "strike",
    "secret", "capitalize", "disabled", "visible", "stick-to-bottom",
    "soft-shadows", "italic", "wrap",
}

ANY_PROP_START = VALUE_PROPS_1 | VALUE_PROPS_EXPR | SPECIAL_PROPS | FLAGS | {"on", "if", "otherwise"}

CONTENT_KINDS = {"text", "button", "cell", "image", "link", "video", "model3d"}


# ---- stage 1+2: lines & block tree -------------------------------------------

def logical_lines(source: str) -> list[tuple[int, int, str]]:
    """(line_no, indent_spaces, text) with continuations joined."""
    raw: list[tuple[int, int, str]] = []
    for no, rawline in enumerate(source.splitlines(), 1):
        if "\t" in rawline[: len(rawline) - len(rawline.lstrip())]:
            raise PlainError(
                "Tabs for indentation get confusing fast — PL uses 2 spaces "
                "per level.", line_no=no, line_text=rawline,
                hint="replace each tab with 2 spaces",
                col=rawline.index("\t") + 1, length=1)
        code = T.strip_comment(rawline)
        if not code.strip():
            continue
        indent = len(code) - len(code.lstrip(" "))
        text = code.strip()
        if raw and (text.startswith("or ") or text.startswith("and ")):
            pno, pind, ptext = raw[-1]
            raw[-1] = (pno, pind, ptext + " " + text)
            continue
        raw.append((no, indent, text))
    for no, indent, text in raw:
        if indent % 2 != 0:
            raise PlainError(
                f"This line is indented {indent} spaces. PL indents 2 spaces "
                f"at a time, so this one's halfway between levels.",
                line_no=no, line_text=text,
                hint=f"indent it {indent - 1} or {indent + 1} spaces",
                col=1, length=max(1, len(text.strip())))
    return raw


def block_tree(source: str) -> list[Line]:
    roots: list[Line] = []
    stack: list[Line] = []
    for no, indent, text in logical_lines(source):
        level = indent // 2
        node = Line(text=text, no=no, level=level, col=indent + 1)
        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            if level > stack[-1].level + 1:
                raise PlainError(
                    "This line jumps in more than one level. Indent one "
                    "step (2 spaces) at a time so nesting stays obvious.",
                    line_no=no, line_text=text,
                    col=indent + 1, length=max(1, len(text)))
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


# ---- stage 3: classification ---------------------------------------------------

_DECL_RE = {
    "needs": re.compile(r"^needs(?:\s+(.*))?$"),
    "kind": re.compile(r"^kind\s+([A-Z][\w-]*)\s*:$"),
    "component": re.compile(r"^component\s+([A-Z][\w-]*)(?:\(([^)]*)\))?\s*:$"),
    "page": re.compile(r"^page\s+([A-Z][\w-]*)(?:\(([^)]*)\))?(?:\s+at\s+\"([^\"]*)\")?\s*:$"),
    "look": re.compile(r"^look\s+([\w-]+)\s*:$"),
    "theme": re.compile(r"^theme(?:\s+([\w-]+))?\s*:$"),
    "action": re.compile(r"^to\s+([\w-]+)(?:\(([^)]*)\))?\s*:$"),
    "keep": re.compile(r"^keep\s+([\w-]+)$"),
}


def _param_specs(s: str | None) -> list[tuple[str, str | None]]:
    """`(name, default_expr)` pairs from a parameter list.

    Defaults are preserved, not discarded: Doc 03 §6.3's
    `Avatar(person, size = 40)` must actually default size to 40.
    """
    if not s:
        return []
    out: list[tuple[str, str | None]] = []
    for raw in s.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if "=" in raw:
            name, default = raw.split("=", 1)
            out.append((name.split(":")[0].strip(), default.strip()))
        else:
            out.append((raw.split(":")[0].strip(), None))
    return out


def _params(s: str | None) -> list[str]:
    return [name for name, _ in _param_specs(s)]


def _defaults(s: str | None) -> dict[str, str]:
    return {name: default for name, default in _param_specs(s)
            if default is not None}


def _parse_capabilities(rest: str | None, ln: Line) -> list[Capability]:
    """Parse `needs network api.example.com, storage` into structured items."""
    raw = (rest or "").strip()
    if not raw:
        return [Capability("", None, ln.no, 1, ln.text, len(ln.text))]
    out: list[Capability] = []
    search_from = ln.text.find(raw)
    if search_from < 0:
        search_from = 0
    for part in raw.split(","):
        clause = part.strip()
        if not clause:
            continue
        pos = ln.text.find(clause, search_from)
        if pos >= 0:
            col = pos + 1
            search_from = pos + len(clause)
        else:
            col = 1
        if clause == "nothing":
            continue
        words = clause.split()
        kind = words[0]
        target = " ".join(words[1:]) if len(words) > 1 else None
        out.append(Capability(kind, target, ln.no, col, ln.text, len(clause)))
    return out


def parse_program(source: str) -> Program:
    roots = block_tree(source)
    # Pre-scan component signatures so call sites bind named args correctly.
    sigs: dict[str, list[str]] = {}
    for ln in roots:
        m = _DECL_RE["component"].match(ln.text)
        if m:
            sigs[m.group(1)] = _params(m.group(2))
    par = _Parser(sigs)
    prog = Program()
    for ln in roots:
        t = ln.text
        if m := _DECL_RE["needs"].match(t):
            caps = _parse_capabilities(m.group(1), ln)
            prog.capabilities.extend(caps)
            prog.needs.extend(c.label() for c in caps if c.kind)
        elif m := _DECL_RE["kind"].match(t):
            fields = []
            for ch in ln.children:
                fm = re.match(r"^([\w-]+)(?:\s*:\s*([^=]+?))?(?:\s*=\s*(.*))?$", ch.text)
                if fm:
                    fields.append(KindField(
                        fm.group(1),
                        fm.group(2).strip() if fm.group(2) else None,
                        fm.group(3).strip() if fm.group(3) else None,
                        ch.no, ch.col))
            prog.kinds[m.group(1)] = KindDecl(m.group(1), fields, ln.no,
                                              ln.col, ln.text)
        elif m := _DECL_RE["component"].match(t):
            prog.components[m.group(1)] = Component(
                m.group(1), _params(m.group(2)),
                par.classify_block(ln.children, context="decls"), ln.no,
                _defaults(m.group(2)), ln.col, ln.text)
        elif m := _DECL_RE["page"].match(t):
            prog.pages[m.group(1)] = Page(
                m.group(1), _params(m.group(2)), m.group(3),
                par.classify_block(ln.children, context="decls"), ln.no,
                _defaults(m.group(2)), ln.col, ln.text)
        elif m := _DECL_RE["look"].match(t):
            look = LookDecl(m.group(1), line_no=ln.no, col=ln.col, raw=ln.text)
            for ch in ln.children:
                holder = Node(kind="box", line_no=ch.no, col=ch.col, raw=ch.text)
                par._prop_loop(T.tokenize(ch.text), holder, ch)
                look.props += holder.props
                look.flags += holder.flags
            prog.looks[m.group(1)] = look
        elif _DECL_RE["theme"].match(t):
            prog.themes.append(RawStmt(t, ln.no, ln.children, ln.col, ln.text))
        elif t.startswith("shared "):
            prog.shared_decls.append(par.classify_stmt(ln, context="decls"))
        elif t.startswith("use "):
            prog.uses.append(RawStmt(t, ln.no, [], ln.col, ln.text))
        else:
            # stray top-level line: keep for checker to complain about
            prog.deferred.append(RawStmt(t, ln.no, ln.children, ln.col, ln.text))
    return prog


class _Parser:
    def __init__(self, component_sigs: dict[str, list[str]]):
        self.sigs = component_sigs

    # -- blocks ---------------------------------------------------------
    def classify_block(self, lines: list[Line], context: str) -> list:
        out: list = []
        for ln in lines:
            stmt = self.classify_stmt(ln, context)
            if isinstance(stmt, _Otherwise):
                if out and isinstance(out[-1], IfNode):
                    if isinstance(stmt, _OtherwiseBody):
                        out[-1].else_body = stmt.body
                    else:
                        out[-1].else_body = self.classify_block(ln.children, context)
                else:
                    raise PlainError(
                        "`otherwise` needs an `if` right above it.",
                        line_no=ln.no, line_text=ln.text)
                continue
            out.append(stmt)
        return out

    def classify_stmt(self, ln: Line, context: str):
        t = ln.text
        toks = T.tokenize(t)
        head = toks[0].text if toks else ""

        if head == "to" and (m := _DECL_RE["action"].match(t)):
            return ActionDecl(m.group(1), _params(m.group(2)),
                              self.classify_block(ln.children, "actions"), ln.no,
                              1, ln.text)
        if head == "keep" and (m := _DECL_RE["keep"].match(t)):
            return KeepDecl(m.group(1), ln.no, 1, ln.text)
        if head == "if":
            cond, inline = self._split_colon(t[2:].strip())
            node = IfNode(condition=cond, then_body=self.classify_block(ln.children, context),
                          line_no=ln.no, inline_then=inline, col=1, raw=ln.text)
            return node
        if head == "otherwise":
            rest = t[len("otherwise"):].strip()
            if rest.startswith("if "):  # otherwise if …  → else containing an If
                sub = Line(text=rest, no=ln.no, level=ln.level,
                           col=ln.col, children=ln.children)
                node = self.classify_stmt(sub, context)
                if isinstance(node, IfNode):
                    return _OtherwiseBody([node])
            if rest in (":", ""):
                return _OTHERWISE
        if isinstance(_r := self._try_for(ln, context), ForNode):
            return _r
        if head == "when":
            subject, _ = self._split_colon(t[4:].strip())
            branches = []
            for ch in ln.children:
                pat, inline = self._split_colon(ch.text[2:].strip()) \
                    if ch.text.startswith("is ") else (ch.text, None)
                body = self.classify_block(ch.children, context)
                if inline:
                    sub = Line(text=inline, no=ch.no, level=ch.level)
                    body = [self.classify_stmt(sub, context)] + body
                branches.append(WhenBranch(pat.strip(), body, ch.no,
                                           1, ch.text))
            return WhenNode(subject.strip(), branches, ln.no, 1, ln.text)

        # declarations / assignments
        decl = self._try_decl(ln, toks, context)
        if decl is not None:
            return decl

        # node line?
        if head in NODE_KINDS or (head[:1].isupper() and toks[0].kind == T.NAME) \
                or head in self.sigs:
            return self.parse_node(ln, context)

        return RawStmt(t, ln.no, self.classify_block(ln.children, context)
                       if ln.children else [], 1, ln.text)

    def _try_for(self, ln: Line, context: str):
        m = re.match(r"^for\s+([\w-]+)(?:\s*,\s*([\w-]+))?\s+in\s+(.+?):?$", ln.text)
        if not m:
            return None
        iterable = m.group(3).strip()
        if iterable.endswith(":"):
            iterable = iterable[:-1].strip()
        return ForNode(m.group(1), m.group(2), iterable,
                       self.classify_block(ln.children, context), ln.no,
                       1, ln.text)

    def _split_colon(self, text: str) -> tuple[str, str | None]:
        """Split `head: inline` at a colon token outside quotes/brackets."""
        toks = T.tokenize(text)
        depth = 0
        for i, tok in enumerate(toks):
            if tok.kind in (T.LPAREN, T.LBRACKET):
                depth += 1
            elif tok.kind in (T.RPAREN, T.RBRACKET):
                depth -= 1
            elif tok.kind == T.COLON and depth == 0:
                left = T.detokenize(toks[:i])
                right = T.detokenize(toks[i + 1:])
                return left, (right or None)
        return text, None

    def _try_decl(self, ln: Line, toks, context: str):
        # shared …
        shared = toks and toks[0].kind == T.NAME and toks[0].text == "shared"
        work = toks[1:] if shared else toks
        if not work or work[0].kind != T.NAME:
            return None
        name = work[0].text
        # name from "…"  (resource)
        if len(work) > 1 and work[1].kind == T.NAME and work[1].text == "from":
            return ResourceDecl(name, T.detokenize(work[2:]), ln.no, shared,
                                1, ln.text)
        # name [: Type] = expr   /   name += expr …
        # The left side may only be names/colons/dots — so a node line like
        # `button "−1" on tap: count -= 1` is never mistaken for a declaration.
        for i, tok in enumerate(work[:8]):
            if i > 0 and not (tok.kind in (T.NAME, T.COLON)
                              or (tok.kind == T.OP and tok.text in (".", "=", "+=", "-="))):
                break
            if tok.kind == T.OP and tok.text in ("=", "+=", "-="):
                type_hint = None
                lhs = work[1:i]
                if lhs and lhs[0].kind == T.COLON:
                    type_hint = T.detokenize(lhs[1:])
                expr = T.detokenize(work[i + 1:])
                # A declaration's left side is a bare name or `name: Type`.
                # `task.done = yes` is an assignment, never a new state name.
                is_plain_decl = (not lhs) or lhs[0].kind == T.COLON
                if context == "decls" and tok.text == "=" and is_plain_decl:
                    return StateDecl(name, expr, ln.no, type_hint, shared,
                                     1, ln.text)
                return AssignStmt(T.detokenize(work[:i]).split(":")[0].strip(),
                                  tok.text, expr, ln.no, 1, ln.text)
            if tok.kind == T.NAME and tok.text == "." :
                break
        # name is expr  (derived) — LHS must be a single name
        if len(work) > 2 and work[1].kind == T.NAME and work[1].text == "is" \
                and context == "decls":
            return DerivedDecl(name, T.detokenize(work[2:]), ln.no,
                               1, ln.text)
        # name add/remove …  (list ops, kept raw for runtime)
        if len(work) > 1 and work[1].kind == T.NAME and work[1].text in ("add", "remove"):
            return RawStmt(ln.text, ln.no, [], 1, ln.text)
        return None

    # -- node lines -------------------------------------------------------
    def parse_node(self, ln: Line, context: str) -> Node:
        toks = T.tokenize(ln.text)
        # trailing block colon
        if toks and toks[-1].kind == T.COLON:
            toks = toks[:-1]
        kind = toks[0].text
        node = Node(kind=kind, line_no=ln.no, col=toks[0].col, raw=ln.text,
                    length=len(kind))
        rest = toks[1:]

        # inline child after colon: `column ... : spinner`
        inline_child = None
        depth = 0
        for i, tok in enumerate(rest):
            if tok.kind in (T.LPAREN, T.LBRACKET):
                depth += 1
            elif tok.kind in (T.RPAREN, T.RBRACKET):
                depth -= 1
            elif tok.kind == T.COLON and depth == 0:
                # a colon only introduces an inline child when what follows
                # can't belong to an `on …:` event (handled in prop loop).
                before = rest[:i]
                if not any(x.kind == T.NAME and x.text == "on" for x in before):
                    inline_child = T.detokenize(rest[i + 1:])
                    rest = before
                break

        rest = self._content_and_args(node, rest)
        self._prop_loop(rest, node, ln)

        # children: prop-continuations & events merge into this node,
        # everything else is a visual child — classified AS A BLOCK so
        # `otherwise` pairs with its `if` (classify_block owns pairing).
        visual_lines: list[Line] = []
        if inline_child:
            visual_lines.append(Line(text=inline_child, no=ln.no,
                                     level=ln.level + 1))
        for ch in ln.children:
            ctoks = T.tokenize(ch.text)
            chead = ctoks[0].text if ctoks else ""
            if chead == "on":
                node.events.append(self._event_from_line(ch, context))
            elif len(ctoks) > 1 and ctoks[1].kind == T.NAME and ctoks[1].text == "is":
                # `columns is 3 if …` — a scoped derivation, NOT a prop line
                visual_lines.append(ch)
            elif chead in (VALUE_PROPS_1 | VALUE_PROPS_EXPR | SPECIAL_PROPS | FLAGS) \
                    and chead not in NODE_KINDS:
                self._prop_loop(ctoks, node, ch)
            else:
                visual_lines.append(ch)
        node.children = self.classify_block(visual_lines, context)
        return node

    def _content_and_args(self, node: Node, toks) -> list:
        """Consume positional content / component args. Returns remaining."""
        if not toks:
            return toks
        is_component = node.kind[:1].isupper() or node.kind in self.sigs
        wants_content = node.kind in CONTENT_KINDS or is_component
        if not wants_content:
            return toks
        t0 = toks[0]
        if t0.kind == T.NAME and t0.text == "on":
            return toks  # no content — checker reports the empty button etc.
        if t0.kind == T.STRING:
            # conditional string content: "A" if cond otherwise "B" [props…]
            if len(toks) > 1 and toks[1].kind == T.NAME and toks[1].text == "if":
                end = self._conditional_string_end(toks)
                node.content_expr = T.detokenize(toks[:end])
                return toks[end:]
            node.content = t0.text
            return toks[1:]
        if t0.kind == T.NAME and (not is_component
                                  or (t0.text not in ANY_PROP_START
                                      and t0.text not in self.sigs.get(node.kind, []))):
            # expression content: name(.name)* with optional `as fmt`,
            # or NUMBER
            i = 1
            while i + 1 < len(toks) and toks[i].text == "." and toks[i + 1].kind == T.NAME:
                i += 2
            if i + 1 < len(toks) and toks[i].kind == T.NAME and toks[i].text == "as":
                i += 2
            node.content_expr = T.detokenize(toks[:i])
            return toks[i:]
        if t0.kind == T.NUMBER:
            node.content_expr = t0.text
            return toks[1:]
        return toks

    def _conditional_string_end(self, toks) -> int:
        """Index just past `"A" if cond otherwise "B"`."""
        i = 2  # past STRING, if
        while i < len(toks) and not (toks[i].kind == T.NAME and toks[i].text == "otherwise"):
            i += 1
        # past `otherwise` + the B primary (STRING or dotted name)
        i += 1
        if i < len(toks):
            i += 1
            while i + 1 < len(toks) and toks[i].text == "." :
                i += 2
        return i

    # -- property loop -------------------------------------------------------
    @staticmethod
    def _p(word: str, value: str, toks, i: int, ln: Line) -> Prop:
        tok = toks[i] if i < len(toks) else None
        return Prop(word, value, line_no=ln.no,
                    col=tok.col if tok else None,
                    length=tok.length if tok else len(word))

    @staticmethod
    def _f(word: str, tok, ln: Line) -> Flag:
        return Flag(word, line_no=ln.no, col=tok.col if tok else None,
                    length=tok.length if tok else len(word))

    def _prop_loop(self, toks, node: Node, ln: Line):
        i = 0
        n = len(toks)
        params = self.sigs.get(node.kind, [])
        while i < n:
            t = toks[i]
            if t.kind == T.COMMA or t.kind == T.COLON:
                i += 1
                continue
            if t.kind == T.NAME and t.text == "on":
                ev, i = self._event_from_tokens(toks, i, ln)
                node.events.append(ev)
                continue
            if t.kind != T.NAME:
                # stray value (e.g. component positional arg) — keep as an
                # expression source so strings stay quoted and numbers stay
                # numbers when the call is expanded.
                node.args.append(T.detokenize([t]))
                i += 1
                continue
            word = t.text
            if word == "if" and (node.props or node.flags):
                # condition for the preceding special prop (`width 3 if …`)
                cond, i = self._capture_condition(toks, i + 1, params)
                last = node.props[-1] if node.props else node.flags[-1]
                last.condition = cond
                if i < n and toks[i].kind == T.NAME and toks[i].text == "otherwise":
                    i += 1
                    if i < n and toks[i].kind == T.NAME and node.props:
                        o_name = toks[i].text
                        o_val, i = self._value_tokens(toks, i + 1, False, params)
                        node.props[-1].otherwise = Prop(o_name, o_val)
                continue
            if word in SPECIAL_PROPS:
                i = self._special_prop(word, toks, i, node, ln)
                continue
            if word in VALUE_PROPS_1 or word in VALUE_PROPS_EXPR or word in params:
                i = self._value_prop(word, toks, i, node, ln,
                                     free_expr=word in VALUE_PROPS_EXPR or word in params)
                continue
            if word in FLAGS:
                i += 1
                flag = self._f(word, t, ln)
                if i < n and toks[i].kind == T.NAME and toks[i].text == "if":
                    cond, i = self._capture_condition(toks, i + 1, params)
                    flag.condition = cond
                node.flags.append(flag)
                continue
            # unknown word: value-prop if followed by an obvious value,
            # else flag. Checker will judge it (with suggestions).
            nxt = toks[i + 1] if i + 1 < n else None
            if nxt is not None and (nxt.kind in (T.STRING, T.NUMBER, T.COLOR, T.LBRACKET)
                                    or (nxt.kind == T.NAME
                                        and nxt.text not in ANY_PROP_START
                                        and nxt.text not in params)):
                i = self._value_prop(word, toks, i, node, ln, free_expr=False)
            else:
                node.flags.append(self._f(word, t, ln))
                i += 1

    def _capture_condition(self, toks, i, params=()) -> tuple[str, int]:
        """Condition tokens: up to next prop/flag/event start, `otherwise`, EOL."""
        start = i
        depth = 0
        while i < len(toks):
            t = toks[i]
            if t.kind in (T.LPAREN, T.LBRACKET):
                depth += 1
            elif t.kind in (T.RPAREN, T.RBRACKET):
                depth -= 1
            elif depth == 0 and t.kind == T.NAME and t.text == "otherwise":
                break
            elif depth == 0 and t.kind == T.NAME and i > start \
                    and (t.text in (VALUE_PROPS_1 | VALUE_PROPS_EXPR | SPECIAL_PROPS | FLAGS | {"on"})
                         or t.text in params):
                break
            elif depth == 0 and t.kind == T.COMMA:
                break
            i += 1
        return T.detokenize(toks[start:i]), i

    def _value_tokens(self, toks, i, free_expr: bool, params=()) -> tuple[str, int]:
        """Capture a prop value starting at toks[i]."""
        if i >= len(toks):
            return "", i
        if free_expr:
            start = i
            depth = 0
            while i < len(toks):
                t = toks[i]
                if t.kind in (T.LPAREN, T.LBRACKET):
                    depth += 1
                elif t.kind in (T.RPAREN, T.RBRACKET):
                    depth -= 1
                elif depth == 0 and t.kind == T.NAME and t.text in ("if", "otherwise"):
                    break
                elif depth == 0 and i > start and t.kind == T.NAME \
                        and (t.text in ANY_PROP_START or t.text in params):
                    break
                elif depth == 0 and t.kind in (T.COMMA, T.COLON):
                    break
                i += 1
            return T.detokenize(toks[start:i]), i
        # single primary: STRING/NUMBER/COLOR/NAME(.NAME)*/bracketed list/call
        t = toks[i]
        if t.kind in (T.STRING, T.NUMBER, T.COLOR):
            return (f'"{t.text}"' if t.kind == T.STRING else t.text), i + 1
        if t.kind == T.LBRACKET:
            depth = 0
            j = i
            while j < len(toks):
                if toks[j].kind == T.LBRACKET:
                    depth += 1
                elif toks[j].kind == T.RBRACKET:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            return T.detokenize(toks[i:j + 1]), j + 1
        j = i + 1
        while j + 1 < len(toks) and toks[j].text == "." and toks[j + 1].kind == T.NAME:
            j += 2
        if j < len(toks) and toks[j].kind == T.LPAREN:
            depth = 0
            while j < len(toks):
                if toks[j].kind == T.LPAREN:
                    depth += 1
                elif toks[j].kind == T.RPAREN:
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
        return T.detokenize(toks[i:j]), j

    def _value_prop(self, word, toks, i, node: Node, ln: Line, free_expr: bool) -> int:
        params = self.sigs.get(node.kind, [])
        value, j = self._value_tokens(toks, i + 1, free_expr, params)
        prop = self._p(word, value, toks, i, ln)
        if j < len(toks) and toks[j].kind == T.NAME and toks[j].text == "if":
            cond, j = self._capture_condition(toks, j + 1, params)
            prop.condition = cond
            if j < len(toks) and toks[j].kind == T.NAME and toks[j].text == "otherwise":
                # `... otherwise <propname> <value>`
                j += 1
                if j < len(toks) and toks[j].kind == T.NAME:
                    o_name = toks[j].text
                    o_val, j = self._value_tokens(toks, j + 1, False, params)
                    prop.otherwise = Prop(o_name, o_val)
        node.props.append(prop)
        return j

    def _special_prop(self, word, toks, i, node: Node, ln: Line) -> int:
        n = len(toks)
        if word == "padding":
            vals, j = [], i + 1
            while j < n and toks[j].kind == T.NUMBER and len(vals) < 4:
                vals.append(toks[j].text)
                j += 1
            node.props.append(self._p(word, " ".join(vals), toks, i, ln))
            return j
        if word in ("width", "height"):
            j = i + 1
            got = []
            # fill|fit|NUMBER|NUMBER% [max N|%] [min N]
            while j < n and (toks[j].kind == T.NUMBER
                             or (toks[j].kind == T.NAME and toks[j].text in
                                 ("fill", "fit", "max", "min"))):
                got.append(toks[j].text)
                j += 1
            node.props.append(self._p(word, " ".join(got), toks, i, ln))
            return j
        if word == "look":
            params = self.sigs.get(node.kind, [])
            value, j = self._value_tokens(toks, i + 1, False)
            prop = self._p("look", value, toks, i, ln)
            if j < n and toks[j].kind == T.NAME and toks[j].text == "if":
                cond, j = self._capture_condition(toks, j + 1, params)
                prop.condition = cond
                if j < n and toks[j].kind == T.NAME and toks[j].text == "otherwise":
                    j += 1
                    if j < n and toks[j].kind == T.NAME and toks[j].text == "look":
                        o_val, j = self._value_tokens(toks, j + 1, False)
                        prop.otherwise = Prop("look", o_val)
            node.props.append(prop)
            return j
        if word == "animate":
            j = i + 1
            got = []
            while j < n and toks[j].kind == T.NAME and toks[j].text not in ANY_PROP_START:
                got.append(toks[j].text)
                j += 1
                if len(got) >= 2:
                    break
            node.props.append(self._p(word, " ".join(got), toks, i, ln))
            return j
        if word in ("at", "look-at"):
            j = i + 1
            got = []
            while j < n and (toks[j].kind in (T.NUMBER, T.COMMA)
                             or toks[j].text == "-"):
                got.append(toks[j].text)
                j += 1
            node.props.append(self._p(word, " ".join(got), toks, i, ln))
            return j
        # angle, stagger: single value
        value, j = self._value_tokens(toks, i + 1, False)
        node.props.append(self._p(word, value, toks, i, ln))
        return j

    # -- events ---------------------------------------------------------------
    def _event_from_tokens(self, toks, i, ln: Line) -> tuple[Event, int]:
        # toks[i] == 'on'; toks[i+1] == event name
        n = len(toks)
        name = toks[i + 1].text if i + 1 < n else ""
        j = i + 2
        param = None
        if j < n and toks[j].kind == T.NAME and j + 1 < n and toks[j + 1].kind == T.COLON:
            param = toks[j].text
            j += 1
        start_tok = toks[i] if i < len(toks) else None
        ev_col = start_tok.col if start_tok else None
        ev_len = (len(name) + 3) if name else 2
        if j < n and toks[j].kind == T.COLON:
            inline = T.detokenize(toks[j + 1:])
            return Event(name, param=param, inline=inline or None,
                         line_no=ln.no, col=ev_col, length=ev_len,
                         raw=ln.text), n
        if j < n and toks[j].kind == T.NAME:
            # action call: name [(args)]  — then more props may follow
            k = j + 1
            if k < n and toks[k].kind == T.LPAREN:
                depth = 0
                while k < n:
                    if toks[k].kind == T.LPAREN:
                        depth += 1
                    elif toks[k].kind == T.RPAREN:
                        depth -= 1
                        if depth == 0:
                            k += 1
                            break
                    k += 1
            return Event(name, param=param,
                         action=T.detokenize(toks[j:k]),
                         line_no=ln.no, col=ev_col, length=ev_len,
                         raw=ln.text), k
        return Event(name, param=param, line_no=ln.no, col=ev_col,
                     length=ev_len, raw=ln.text), j

    def _event_from_line(self, ln: Line, context: str) -> Event:
        toks = T.tokenize(ln.text)
        if toks and toks[-1].kind == T.COLON and ln.children:
            toks = toks[:-1]
        ev, _ = self._event_from_tokens(toks, 0, ln)
        if ln.children:
            ev.block = self.classify_block(ln.children, "actions")
        elif ev.inline:
            ev.block = [self.classify_stmt(
                Line(text=ev.inline, no=ln.no, level=ln.level + 1,
                     col=ln.col), "actions")]
        return ev


# sentinels for `otherwise` handling inside classify_block
class _Otherwise:
    pass


_OTHERWISE = _Otherwise()


class _OtherwiseBody(_Otherwise):
    def __init__(self, body):
        self.body = body
