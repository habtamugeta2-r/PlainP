"""Plain-sentence errors (Doc 03 §10: what, where, why, a concrete fix)."""
from __future__ import annotations


class PlainError(Exception):
    """An error a beginner can read and act on."""

    def __init__(self, message: str, line_no: int | None = None,
                 line_text: str | None = None, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.line_no = line_no
        self.line_text = line_text
        self.hint = hint

    def render(self) -> str:
        out = []
        if self.line_no is not None:
            out.append(f"Line {self.line_no}: {self.message}")
        else:
            out.append(self.message)
        if self.line_text:
            out.append(f"   {self.line_text.strip()}")
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

    def __init__(self, feature: str, stage: str, line_no=None, line_text=None):
        super().__init__(
            f"`{feature}` is part of PL, but this Stage-1 prototype doesn't "
            f"do it yet (planned: {stage}). Your program is fine.",
            line_no=line_no, line_text=line_text)
        self.feature = feature
        self.stage = stage
