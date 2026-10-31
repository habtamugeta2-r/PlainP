"""Shared line tokenizer for PL.

PL is line-oriented (Doc 03 §2): the parser works on one logical line at a
time. This tokenizer is deliberately small and total — it never fails on
odd input; classification is the parser's job.

Lexical decisions (Stage-1, see docs/06):
* Names may contain hyphens (`add-task`, `sort-by`); subtraction requires
  spaces (`a - b`), so `a-b` is ONE name. This is in the spec (§2.5).
* `#` starts a comment EXCEPT when it is a hex color literal:
  `#` + 3/6/8 hex digits followed by a delimiter.
* Numbers may carry a unit suffix (`300ms`, `2s`, `40deg`, `75%`) or be a
  ratio (`4/3`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

STRING = "STRING"
NUMBER = "NUMBER"
COLOR = "COLOR"
NAME = "NAME"
OP = "OP"
COMMA = "COMMA"
COLON = "COLON"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
LBRACKET = "LBRACKET"
RBRACKET = "RBRACKET"


@dataclass
class Tok:
    kind: str
    text: str

    def __repr__(self):  # pragma: no cover - debug aid
        return f"{self.kind}({self.text!r})"


_COLOR_RE = re.compile(r"#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?=[\s,)\]:]|$)")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:/\d+)?(?:ms|deg|s|%)?")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*")
_OPS2 = (">=", "<=", "+=", "-=", "==", "!=")
_OPS1 = "+-*/<>=."


def strip_comment(raw: str) -> str:
    """Remove a trailing `#` comment, respecting strings and hex colors."""
    in_str = False
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == '"':
            in_str = not in_str
        elif c == "#" and not in_str:
            if _COLOR_RE.match(raw, i):
                i += 1
                continue
            return raw[:i].rstrip()
        i += 1
    return raw.rstrip()


def tokenize(text: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == '"':
            j = text.find('"', i + 1)
            if j == -1:  # unterminated: take the rest (checker reports)
                toks.append(Tok(STRING, text[i + 1:]))
                break
            toks.append(Tok(STRING, text[i + 1:j]))
            i = j + 1
            continue
        m = _COLOR_RE.match(text, i)
        if m:
            toks.append(Tok(COLOR, m.group(0)))
            i = m.end()
            continue
        m = _NUMBER_RE.match(text, i)
        if m and c.isdigit():
            toks.append(Tok(NUMBER, m.group(0)))
            i = m.end()
            continue
        m = _NAME_RE.match(text, i)
        if m:
            toks.append(Tok(NAME, m.group(0)))
            i = m.end()
            continue
        if text[i:i + 2] in _OPS2:
            toks.append(Tok(OP, text[i:i + 2]))
            i += 2
            continue
        if c in _OPS1:
            toks.append(Tok(OP, c))
            i += 1
            continue
        if c == ",":
            toks.append(Tok(COMMA, c))
        elif c == ":":
            toks.append(Tok(COLON, c))
        elif c == "(":
            toks.append(Tok(LPAREN, c))
        elif c == ")":
            toks.append(Tok(RPAREN, c))
        elif c == "[":
            toks.append(Tok(LBRACKET, c))
        elif c == "]":
            toks.append(Tok(RBRACKET, c))
        else:
            # Any other single char (unicode symbols etc.) becomes a NAME-ish
            # token so nothing downstream crashes on it.
            toks.append(Tok(NAME, c))
        i += 1
    return toks


def detokenize(toks: list[Tok]) -> str:
    """Rebuild readable source text from tokens (for expression strings)."""
    out: list[str] = []
    prev: Tok | None = None
    for t in toks:
        s = f'"{t.text}"' if t.kind == STRING else t.text
        if prev is None:
            out.append(s)
        elif t.kind in (COMMA, RPAREN, RBRACKET) or t.text == ".":
            out.append(s)
        elif prev.kind in (LPAREN, LBRACKET) or prev.text == ".":
            out.append(s)
        elif t.kind == LPAREN and prev.kind == NAME:
            out.append(s)  # call: name(
        elif t.kind == COLON:
            out.append(":")
        else:
            out.append(" " + s)
        prev = t
    return "".join(out).strip()
