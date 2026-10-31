"""Checker: plain-sentence diagnostics (Doc 03 §10).

Stage-1–3 checks:
  * unknown/misspelled node kinds (with did-you-mean), including inside actions
  * button/link with nothing to show (the spec's canonical error)
  * text with nothing to say
  * unknown property/flag on Stage-1-known nodes (with did-you-mean)
  * duplicate state names in one page/component
  * page missing its address
  * `needs` capability grammar + compile-time coverage for `keep` (`storage`)
    and literal `http(s)://` URLs (`network <host>`) (HAB-70 / CHK-08)
  * event-action and look names resolved; value names remain runtime-checked
    until full scope/type resolution lands (HAB-79).
"""
from __future__ import annotations

import difflib
import re
import urllib.parse

from .ast_nodes import (
    ActionDecl, AssignStmt, Capability, DerivedDecl, ForNode, IfNode, KeepDecl,
    Node, RawStmt, ResourceDecl, StateDecl, WhenNode,
)
from .errors import PlainError, PlainWarning
from .expr import parse_expr
from .parser import FLAGS, NODE_KINDS, SPECIAL_PROPS, VALUE_PROPS_1, VALUE_PROPS_EXPR

_KNOWN_PROPS = VALUE_PROPS_1 | VALUE_PROPS_EXPR | SPECIAL_PROPS | {
    "material", "part", "retry", "error",
}
_CHECKED_KINDS = {"column", "row", "text", "button", "box", "image", "input",
                  "toggle", "divider", "stack", "scroll", "grid", "spacer"}

_SCOPED_CAPS = {"network", "native"}
_UNSCOPED_CAPS = {
    "storage", "camera", "microphone", "location",
    "clipboard", "notifications", "gpu-compute",
}
_ALL_CAPS = _SCOPED_CAPS | _UNSCOPED_CAPS

_LITERAL_RES_URL_RE = re.compile(r'^(?:live\s+)?"(https?://[^"{]*)"\s*$')
_LITERAL_REQ_URL_RE = re.compile(r'^(?:post|fetch)\s+"(https?://[^"{]*)"(?:\s|$)')


def _check_capabilities(program, errors: list[PlainError]) -> None:
    for cap in getattr(program, "capabilities", []):
        if not cap.kind or cap.kind == "needs:":
            errors.append(PlainError(
                "`needs` must name at least one capability.",
                line_no=cap.line_no, line_text=cap.raw or None,
                hint="needs network api.example.com",
                col=cap.col, length=max(1, cap.length)))
            continue
        raw_kind = cap.kind.rstrip(":")
        if raw_kind not in _ALL_CAPS or cap.kind.endswith(":"):
            close = difflib.get_close_matches(raw_kind, sorted(_ALL_CAPS),
                                              n=1, cutoff=0.6)
            hint = (f"did you mean `needs {close[0]}`?" if close else
                    "capabilities include `network <host>`, `storage`, "
                    "`camera`, `clipboard`, `notifications`")
            errors.append(PlainError(
                f"`{cap.kind}` isn't a capability PL knows.",
                line_no=cap.line_no, line_text=cap.raw or None,
                hint=hint, col=cap.col, length=max(1, len(cap.kind))))
            continue
        if cap.kind in _SCOPED_CAPS:
            if not cap.target:
                example = ("needs network api.example.com"
                           if cap.kind == "network" else "needs native sqlite")
                what = ("the host it talks to (no blanket internet access)"
                        if cap.kind == "network" else "the library it loads")
                errors.append(PlainError(
                    f"`needs {cap.kind}` must name {what}.",
                    line_no=cap.line_no, line_text=cap.raw or None,
                    hint=example, col=cap.col, length=max(1, cap.length)))
                continue
            if cap.kind == "network":
                tgt = cap.target.strip()
                if "://" in tgt or "/" in tgt:
                    parsed = urllib.parse.urlsplit(
                        tgt if "://" in tgt else f"https://{tgt}")
                    clean_host = parsed.netloc or "api.example.com"
                    errors.append(PlainError(
                        f"`needs network` takes a host name, not a full URL "
                        f"(`{tgt}`).",
                        line_no=cap.line_no, line_text=cap.raw or None,
                        hint=f"needs network {clean_host}",
                        col=cap.col, length=max(1, cap.length)))
                elif "*" in tgt:
                    errors.append(PlainError(
                        f"`needs network` cannot use a wildcard (`{tgt}`) — "
                        f"name each host explicitly.",
                        line_no=cap.line_no, line_text=cap.raw or None,
                        hint="needs network api.example.com",
                        col=cap.col, length=max(1, cap.length)))
                elif any(ch.isspace() for ch in tgt):
                    errors.append(PlainError(
                        "Separate multiple capabilities with a comma in `needs`.",
                        line_no=cap.line_no, line_text=cap.raw or None,
                        hint="needs network api.example.com, storage",
                        col=cap.col, length=max(1, cap.length)))
        elif cap.target is not None:
            errors.append(PlainError(
                f"`needs {cap.kind}` doesn't take `{cap.target}` after it.",
                line_no=cap.line_no, line_text=cap.raw or None,
                hint=f"needs {cap.kind}",
                col=cap.col, length=max(1, cap.length)))


def _check_url_capability(url: str, line_no: int, raw: str | None,
                          col: int, length: int, program,
                          errors: list[PlainError]) -> None:
    allowed, host = program.allows_network_url(url)
    if allowed:
        return
    suggest_host = host.split(":")[0] if ":" in host and not host.startswith("scheme") else host
    errors.append(PlainError(
        f"This line connects to `{host}`, which isn't listed in `needs`.",
        line_no=line_no, line_text=raw,
        hint=f"add `needs network {suggest_host}` at the top of this file",
        col=col, length=max(1, length)))


def _check_request_text_capability(text: str, line_no: int, raw: str | None,
                                   col: int, program,
                                   errors: list[PlainError]) -> None:
    m = _LITERAL_REQ_URL_RE.match((text or "").strip())
    if m:
        url = m.group(1)
        _check_url_capability(url, line_no, raw, col, len(url) + 2,
                              program, errors)


def check_program(program) -> list[PlainError]:
    errors: list[PlainError] = []
    _check_capabilities(program, errors)

    for stmt in getattr(program, "shared_decls", []):
        if isinstance(stmt, ResourceDecl):
            m = _LITERAL_RES_URL_RE.match(stmt.source.strip())
            if m:
                _check_url_capability(m.group(1), stmt.line_no,
                                      stmt.raw or None, stmt.col,
                                      len(stmt.name), program, errors)
        elif isinstance(stmt, KeepDecl) and not program.has_capability("storage"):
            errors.append(PlainError(
                f"`keep {stmt.name}` saves data on this device, so this file "
                f"must declare `needs storage`.",
                line_no=stmt.line_no, line_text=stmt.raw or None,
                hint="add `needs storage` at the top of this file",
                col=stmt.col, length=max(1, len(f"keep {stmt.name}"))))

    for page in program.pages.values():
        if not page.path and not page.params:
            errors.append(PlainError(
                f"Page `{page.name}` has no address. Pages need one so "
                f"people (and links) can reach them.",
                line_no=page.line_no, line_text=page.raw or None,
                hint=f'page {page.name} at "/":',
                col=page.col, length=max(1, len("page " + page.name))))
    for owner in list(program.pages.values()) + list(program.components.values()):
        seen: dict[str, int] = {}
        for stmt in owner.body:
            if isinstance(stmt, (StateDecl, DerivedDecl)):
                if stmt.name in seen:
                    errors.append(PlainError(
                        f"`{stmt.name}` is already created on line "
                        f"{seen[stmt.name]}. One name, one value — pick a "
                        f"different name for the second one.",
                        line_no=stmt.line_no, line_text=stmt.raw or None,
                        col=stmt.col, length=max(1, len(stmt.name))))
                seen[stmt.name] = stmt.line_no
            elif isinstance(stmt, KeepDecl) and not program.has_capability("storage"):
                errors.append(PlainError(
                    f"`keep {stmt.name}` saves data on this device, so this "
                    f"file must declare `needs storage`.",
                    line_no=stmt.line_no, line_text=stmt.raw or None,
                    hint="add `needs storage` at the top of this file",
                    col=stmt.col, length=max(1, len(f"keep {stmt.name}"))))
            elif isinstance(stmt, ResourceDecl):
                m = _LITERAL_RES_URL_RE.match(stmt.source.strip())
                if m:
                    _check_url_capability(m.group(1), stmt.line_no,
                                          stmt.raw or None, stmt.col,
                                          len(stmt.name), program, errors)
        actions = {s.name for s in owner.body if isinstance(s, ActionDecl)}
        _check_block(owner.body, program, errors, visual=True, actions=actions,
                     owner_name=getattr(owner, "name", ""))
        # Action bodies are programs too: an unknown node or property inside
        # `to …:` must fail `plain check`, not the first tap.
        for stmt in owner.body:
            if isinstance(stmt, ActionDecl):
                _check_block(stmt.body, program, errors, visual=False,
                             actions=actions,
                             owner_name=getattr(owner, "name", ""))
    # Default parameter values are expressions too: catch a typo at
    # `plain check`, not on the first call that omits the argument.
    for comp in program.components.values():
        for name, src in getattr(comp, "defaults", {}).items():
            try:
                parse_expr(src, comp.line_no)
            except PlainError as e:
                errors.append(PlainError(
                    f"`{comp.name}`'s default for `{name}` isn't a valid "
                    f"expression: {e.message}",
                    line_no=comp.line_no, line_text=comp.raw or None,
                    col=comp.col, length=max(1, len(comp.name)),
                    hint="defaults are ordinary PL expressions, e.g. "
                         "`size = 40` or `label = \"Untitled\"`"))
    return errors


def _check_block(stmts, program, errors, visual, actions=frozenset(), owner_name=""):
    for stmt in stmts:
        if isinstance(stmt, Node):
            _check_node(stmt, program, errors, actions, owner_name)
        elif isinstance(stmt, AssignStmt):
            _check_request_text_capability(stmt.expr, stmt.line_no,
                                           stmt.raw or None, stmt.col,
                                           program, errors)
        elif isinstance(stmt, IfNode):
            if stmt.inline_then:
                _check_request_text_capability(stmt.inline_then, stmt.line_no,
                                               stmt.raw or None, stmt.col,
                                               program, errors)
            _check_block(stmt.then_body, program, errors, visual, actions, owner_name)
            _check_block(stmt.else_body, program, errors, visual, actions, owner_name)
        elif isinstance(stmt, ForNode):
            _check_block(stmt.body, program, errors, visual, actions, owner_name)
        elif isinstance(stmt, WhenNode):
            for br in stmt.branches:
                _check_block(br.body, program, errors, visual, actions, owner_name)
        elif isinstance(stmt, RawStmt):
            _check_request_text_capability(stmt.text, stmt.line_no,
                                           stmt.raw or stmt.text, stmt.col,
                                           program, errors)
            for child in stmt.children or []:
                _check_block([child], program, errors, visual, actions, owner_name)
            head = stmt.text.split()[0].rstrip(":") if stmt.text.split() else ""
            if visual:
                if head not in ("go", "return", "transition", "refresh"):
                    close = difflib.get_close_matches(head, NODE_KINDS, n=1,
                                                      cutoff=0.65)
                    if close:
                        errors.append(PlainError(
                            f"`{head}` isn't a thing PL knows how to draw.",
                            line_no=stmt.line_no, line_text=stmt.raw or stmt.text,
                            hint=f"did you mean `{close[0]}`?",
                            col=stmt.col,
                            length=max(1, len(head))))
            else:
                # Inside an action: statements may be action-only verbs, but
                # a misspelled node kind is still a plain error now — not at
                # the first tap (Doc 03 §10).
                allowed = {"go", "return", "transition", "refresh", "show",
                           "post", "fetch", "then", "together", "wait"}
                words = stmt.text.split()
                is_list_op = len(words) > 1 and words[1] in ("add", "remove")
                if (head and head not in allowed and not is_list_op
                        and not head.startswith(("add", "remove"))):
                    close = difflib.get_close_matches(head, NODE_KINDS, n=1,
                                                      cutoff=0.65)
                    if close:
                        errors.append(PlainError(
                            f"`{head}` isn't a thing PL knows how to draw.",
                            line_no=stmt.line_no, line_text=stmt.raw or stmt.text,
                            hint=f"did you mean `{close[0]}`?",
                            col=stmt.col,
                            length=max(1, len(head))))


def _check_node(node: Node, program, errors, actions=frozenset(), owner_name=""):
    # event targets must be actions declared in this page/component
    for ev in node.events:
        if ev.action:
            name = ev.action.split("(")[0].strip()
            if name not in actions:
                close = difflib.get_close_matches(name, sorted(actions), n=1,
                                                  cutoff=0.6)
                hint = (f"did you mean `to {close[0]}`?" if close else
                        f"write it as `to {name}:` in this page/component")
                errors.append(PlainError(
                    f"There's no action called `{name}` here for "
                    f"`on {ev.name}` to run.", line_no=node.line_no,
                    line_text=ev.raw or node.raw or None, hint=hint,
                    col=ev.col, length=ev.length))
        if ev.inline:
            inline_rhs = ev.inline.split("=", 1)[1].strip() if "=" in ev.inline else ev.inline
            _check_request_text_capability(inline_rhs, ev.line_no or node.line_no,
                                           ev.raw or node.raw or None,
                                           ev.col or node.col, program, errors)
        if ev.block:
            _check_block(ev.block, program, errors, visual=False,
                         actions=actions, owner_name=owner_name)
    # looks must exist
    for p in node.props:
        if p.name == "look":
            for cand in (p, p.otherwise):
                if cand is not None and cand.value.strip() not in program.looks:
                    errors.append(PlainError(
                        f"There's no look called `{cand.value.strip()}`.",
                        line_no=node.line_no, line_text=node.raw or None,
                        hint=f"write it as `look {cand.value.strip()}:` in this file",
                        col=cand.col, length=cand.length))
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
                line_text=node.raw or f"{node.kind} {action_src}".strip(),
                hint=f'{node.kind} "Save" {action_src}'.strip(),
                col=node.col, length=max(1, len(node.kind))))
    if node.kind == "text":
        if node.content is None and node.content_expr is None:
            errors.append(PlainError(
                "`text` needs something to say.", line_no=node.line_no,
                line_text=node.raw or None, hint='text "Hello"',
                col=node.col, length=max(1, len(node.kind))))
    if node.kind in _CHECKED_KINDS:
        for p in node.props:
            if p.name not in _KNOWN_PROPS and p.name not in program.components:
                close = difflib.get_close_matches(p.name, _KNOWN_PROPS, n=1, cutoff=0.6)
                hint = f"did you mean `{close[0]}`?" if close else \
                    "see docs/03-pl-language-spec.md §4-5 for the property list"
                errors.append(PlainError(
                    f"`{node.kind}` has no property called `{p.name}`.",
                    line_no=node.line_no, line_text=node.raw or None,
                    hint=hint, col=p.col, length=p.length))
        for f in node.flags:
            if f.name not in FLAGS and not f.name[:1].isupper():
                close = difflib.get_close_matches(f.name, FLAGS, n=1, cutoff=0.6)
                if close or len(f.name) > 2:
                    hint = f"did you mean `{close[0]}`?" if close else None
                    errors.append(PlainError(
                        f"`{f.name}` isn't a style word PL knows.",
                        line_no=node.line_no, line_text=node.raw or None,
                        hint=hint, col=f.col, length=f.length))
    for ch in node.children:
        if isinstance(ch, Node):
            _check_node(ch, program, errors, actions, owner_name)
        elif isinstance(ch, (IfNode, ForNode, WhenNode)):
            _check_block([ch], program, errors, visual=True,
                         actions=actions, owner_name=owner_name)


# ---- honest "valid but not yet implemented" warnings -------------------------
# Doc 06 §4: the corpus may stay ahead of the renderer, but nothing may be
# silently inert. These are shown by `plain check` and in the preview; they
# never fail a build.

SUPPORTED_EVENTS = {"tap", "change", "submit"}


def warnings_for(program) -> list[PlainWarning]:
    warns: list[PlainWarning] = []
    for stmt in program.themes:
        warns.append(PlainWarning(
            "`theme` is valid PL, but this prototype does not apply theme "
            "tokens yet (planned: Stage 3).",
            line_no=stmt.line_no, line_text=stmt.raw or stmt.text,
            col=stmt.col, length=len("theme"),
            hint="themes are parsed and kept; pixels use the built-in palette"))
    for stmt in program.uses:
        warns.append(PlainWarning(
            "`use` is valid PL, but this prototype does not load modules yet "
            "(planned: Stage 3+).",
            line_no=stmt.line_no, line_text=stmt.raw or stmt.text,
            col=stmt.col, length=len("use")))
    for stmt in program.deferred:
        warns.append(PlainWarning(
            "this line is outside a page or component, so nothing uses it.",
            line_no=stmt.line_no, line_text=stmt.raw or stmt.text,
            col=stmt.col, length=max(1, len(stmt.text.split()[0]))
            if stmt.text.split() else 1))
    for owner in list(program.pages.values()) + list(program.components.values()):
        _warn_block(owner.body, warns)
    return warns


def _warn_block(stmts, warns: list[PlainWarning]) -> None:
    for stmt in stmts:
        if isinstance(stmt, Node):
            for ev in stmt.events:
                if ev.name not in SUPPORTED_EVENTS:
                    warns.append(PlainWarning(
                        f"`on {ev.name}` is valid PL, but this prototype's "
                        f"preview only dispatches tap, change and submit "
                        f"(planned: Stage 3).",
                        line_no=ev.line_no or stmt.line_no,
                        line_text=ev.raw or stmt.raw or None,
                        col=ev.col, length=ev.length,
                        hint="the handler is parsed and kept; no gesture "
                             "recognizer runs yet"))
            _warn_block(stmt.children, warns)
        elif isinstance(stmt, IfNode):
            _warn_block(stmt.then_body, warns)
            _warn_block(stmt.else_body, warns)
        elif isinstance(stmt, ForNode):
            _warn_block(stmt.body, warns)
        elif isinstance(stmt, WhenNode):
            for br in stmt.branches:
                _warn_block(br.body, warns)
        elif isinstance(stmt, RawStmt):
            if stmt.text.strip().startswith("transition"):
                warns.append(PlainWarning(
                    "`transition` is valid PL, but page transitions are not "
                    "animated yet (planned: Stage 3).",
                    line_no=stmt.line_no, line_text=stmt.raw or stmt.text,
                    col=stmt.col, length=len("transition"),
                    hint="the page still swaps instantly; motion lands with "
                         "the animation engine"))
            _warn_block(stmt.children or [], warns)
