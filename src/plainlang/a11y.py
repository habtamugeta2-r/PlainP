"""Derived accessibility tree (Doc 02 §1.4, Constraint 7).

Never authored — computed from the scene graph. A `button "Save"` is a
button-with-label-Save on the day it's written. This module is the Stage-1
proof: same scene in → semantic tree out, with no a11y-specific strings
anywhere in the source program.
"""
from __future__ import annotations

_ROLES = {
    "button": "button",
    "toggle": "switch",
    "input": "textbox",
    "image": "image",
    "divider": "separator",
    "link": "link",
    "slider": "slider",
    "select": "combobox",
    "spinner": "progressbar",
}


def derive(node) -> dict | None:
    k = node.kind
    children = [c for c in (derive(ch) for ch in node.children) if c]
    if k == "text":
        size = float(node.props.get("size", 16) or 16)
        role = "heading" if size >= 24 or node.props.get("level") else "text"
        return {"role": role, "label": node.text, "line": node.source_line,
                "children": children}
    if k in _ROLES:
        shown_text = (""
                      if k == "input" and "secret" in getattr(node, "flags", ())
                      else node.text)
        label = (node.props.get("label") or shown_text
                 or node.props.get("placeholder") or "")
        entry = {"role": _ROLES[k], "label": label, "line": node.source_line,
                 "children": children}
        if k == "button":
            entry["activatable"] = True
            entry["min-target-ok"] = node.h >= 44 if node.h else None
        return entry
    if k in ("page", "column", "row", "grid"):
        role = "main" if k == "page" else ("list" if k == "grid" else "group")
        return {"role": role, "label": "", "line": node.source_line,
                "children": children}
    if k == "scroll":
        return {"role": "region (scrollable)", "label": "",
                "line": node.source_line, "children": children}
    if k == "box":
        label = node.props.get("label") or ""
        if "tap" in node.events:
            return {"role": "button", "label": label, "line": node.source_line,
                    "children": children}
        return {"role": "group", "label": label, "line": node.source_line,
                "children": children}
    if children:
        return {"role": "group", "label": "", "line": node.source_line,
                "children": children}
    return None


def render_text(tree: dict, indent: int = 0) -> str:
    pad = "  " * indent
    label = f' "{tree["label"]}"' if tree.get("label") else ""
    lines = [f"{pad}{tree['role']}{label}  (line {tree['line']})"]
    for ch in tree.get("children", []):
        lines.append(render_text(ch, indent + 1))
    return "\n".join(lines)
