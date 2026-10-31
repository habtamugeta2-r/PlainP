"""Checker: plain-sentence diagnostics (Doc 03 §10).

Stage-1 checks (lenient toward Stage-2/3 syntax — a program using future
features is *not* an error here; it only fails when rendered):
  * unknown/misspelled node kinds (with did-you-mean)
  * button/link with nothing to show (the spec's canonical error)
  * text with nothing to say
  * unknown property/flag on Stage-1-known nodes (with did-you-mean)
  * duplicate state names in one page/component
  * page missing its address
  * `otherwise` is parser-caught; name resolution is deferred to Stage 2
    (needs full scope/type info) — runtime reports unknown names plainly.
"""
from __future__ import annotations

import difflib

from .ast_nodes import (
    DerivedDecl, ForNode, IfNode, Node, RawStmt, StateDecl, WhenNode,
)
from .errors import PlainError
from .parser import FLAGS, NODE_KINDS, SPECIAL_PROPS, VALUE_PROPS_1, VALUE_PROPS_EXPR

_KNOWN_PROPS = VALUE_PROPS_1 | VALUE_PROPS_EXPR | SPECIAL_PROPS | {
    "material", "part", "retry", "error",
}
# Nodes whose prop/flag vocabulary we check strictly. Future nodes
# (scene3d, table…) are left alone until their stages implement them.
_CHECKED_KINDS = {"column", "row", "text", "button", "box", "image", "input",
                  "toggle", "divider", "stack", "scroll", "grid", "spacer"}


def check_program(program) -> list[PlainError]:
    errors: list[PlainError] = []
    for page in program.pages.values():
        if not page.path and not page.params:
            errors.append(PlainError(
                f"Page `{page.name}` has no address. Pages need one so "
                f"people (and links) can reach them.",
                line_no=page.line_no, hint=f'page {page.name} at "/":'))
    for owner in list(program.pages.values()) + list(program.components.values()):
        seen: dict[str, int] = {}
        for stmt in owner.body:
            if isinstance(stmt, (StateDecl, DerivedDecl)):
                if stmt.name in seen:
                    errors.append(PlainError(
                        f"`{stmt.name}` is already created on line "
                        f"{seen[stmt.name]}. One name, one value — pick a "
                        f"different name for the second one.",
                        line_no=stmt.line_no))
                seen[stmt.name] = stmt.line_no
        _check_block(owner.body, program, errors, visual=True)
    return errors


def _check_block(stmts, program, errors, visual):
    for stmt in stmts:
        if isinstance(stmt, Node):
            _check_node(stmt, program, errors)
        elif isinstance(stmt, IfNode):
            _check_block(stmt.then_body, program, errors, visual)
            _check_block(stmt.else_body, program, errors, visual)
        elif isinstance(stmt, ForNode):
            _check_block(stmt.body, program, errors, visual)
        elif isinstance(stmt, WhenNode):
            for br in stmt.branches:
                _check_block(br.body, program, errors, visual)
        elif isinstance(stmt, RawStmt) and visual:
            for child in stmt.children or []:
                _check_block([child], program, errors, visual)
            head = stmt.text.split()[0].rstrip(":") if stmt.text.split() else ""
            if head not in ("go", "return", "transition", "refresh"):
                close = difflib.get_close_matches(head, NODE_KINDS, n=1, cutoff=0.65)
                if close:
                    errors.append(PlainError(
                        f"`{head}` isn't a thing PL knows how to draw.",
                        line_no=stmt.line_no, line_text=stmt.text,
                        hint=f"did you mean `{close[0]}`?"))


def _check_node(node: Node, program, errors):
    if node.kind == "button" or node.kind == "link":
        if node.content is None and node.content_expr is None \
                and node.prop("label") is None and not node.children:
            ev = node.events[0] if node.events else None
            action_src = ""
            if ev:
                bits = f"on {ev.name}"
                if ev.action:
                    bits += f" {ev.action}"
                action_src = bits
            errors.append(PlainError(
                f"`{node.kind}` needs something to show.",
                line_no=node.line_no,
                line_text=f"{node.kind} {action_src}".strip(),
                hint=f'{node.kind} "Save" {action_src}'.strip()))
    if node.kind == "text":
        if node.content is None and node.content_expr is None:
            errors.append(PlainError(
                "`text` needs something to say.", line_no=node.line_no,
                hint='text "Hello"'))
    if node.kind in _CHECKED_KINDS:
        for p in node.props:
            if p.name not in _KNOWN_PROPS and p.name not in program.components:
                close = difflib.get_close_matches(p.name, _KNOWN_PROPS, n=1, cutoff=0.6)
                hint = f"did you mean `{close[0]}`?" if close else \
                    "see docs/03-pl-language-spec.md §4-5 for the property list"
                errors.append(PlainError(
                    f"`{node.kind}` has no property called `{p.name}`.",
                    line_no=node.line_no, hint=hint))
        for f in node.flags:
            if f.name not in FLAGS and not f.name[:1].isupper():
                close = difflib.get_close_matches(f.name, FLAGS, n=1, cutoff=0.6)
                if close or len(f.name) > 2:
                    hint = f"did you mean `{close[0]}`?" if close else None
                    errors.append(PlainError(
                        f"`{f.name}` isn't a style word PL knows.",
                        line_no=node.line_no, hint=hint))
    for ch in node.children:
        if isinstance(ch, Node):
            _check_node(ch, program, errors)
        elif isinstance(ch, (IfNode, ForNode, WhenNode)):
            _check_block([ch], program, errors, visual=True)
