"""Plain-sentence errors (Doc 03 §10: what, where, why, a concrete fix).

Every diagnostic can point at a token: `col` is 1-based within the raw
source line and `length` is the token width, so `render()` draws a caret
span under exactly the thing that is wrong.
"""
from __future__ import annotations


class PlainError(Exception):
    """An error a beginner can read and act on."""

    def __init__(self, message: str, line_no: int | None = None,
                 line_text: str | None = None, hint: str | None = None,
                 col: int | None = None, length: int = 1):
        super().__init__(message)
        self.message = message
        self.line_no = line_no
        self.line_text = line_text
        self.hint = hint
        self.col = col
        self.length = max(1, length)

    def render(self) -> str:
        out = []
        if self.line_no is not None:
            out.append(f"Line {self.line_no}: {self.message}")
        else:
            out.append(self.message)
        if self.line_text:
            raw = self.line_text
            shown = raw.strip()
            out.append(f"   {shown}")
            if self.col is not None:
                leading = len(raw) - len(raw.lstrip(" "))
                offset = max(0, self.col - 1 - leading)
                width = max(1, min(self.length, max(1, len(shown) - offset)))
                out.append("   " + " " * offset + "^" * width)
        if self.hint:
            out.append(f"Try: {self.hint}")
        return "\n".join(out)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.render()


class PlainWarning:
    """Valid PL that this prototype knows about but does not do yet.

    Warnings are *visible* (CLI + preview) and never fail a build. They exist
    so no valid construct is silently inert (Doc 06 §4 honesty rule).
    """

    def __init__(self, message: str, line_no: int | None = None,
                 line_text: str | None = None, hint: str | None = None,
                 col: int | None = None, length: int = 1):
        self.message = message
        self.line_no = line_no
        self.line_text = line_text
        self.hint = hint
        self.col = col
        self.length = max(1, length)

    def render(self) -> str:
        out = []
        if self.line_no is not None:
            out.append(f"Line {self.line_no}: note: {self.message}")
        else:
            out.append(f"note: {self.message}")
        if self.line_text:
            raw = self.line_text
            shown = raw.strip()
            out.append(f"   {shown}")
            if self.col is not None:
                leading = len(raw) - len(raw.lstrip(" "))
                offset = max(0, self.col - 1 - leading)
                width = max(1, min(self.length, max(1, len(shown) - offset)))
                out.append("   " + " " * offset + "^" * width)
        if self.hint:
            out.append(f"Try: {self.hint}")
        return "\n".join(out)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.render()


class UnsupportedYet(PlainError):
    """Valid PL that this Stage-1 prototype does not implement yet.

    Distinct from a user error: the program is right, the prototype is
    incomplete. Carries the roadmap stage that will implement it.
    """

    def __init__(self, feature: str, stage: str, line_no=None, line_text=None,
                 col=None, length: int = 1):
        super().__init__(
            f"{feature} is part of PL, but this Stage-1 prototype doesn't "
            f"do it yet (planned: {stage}). Your program is fine.",
            line_no=line_no, line_text=line_text, col=col, length=length)
        self.feature = feature
        self.stage = stage
