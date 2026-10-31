"""SVG paint — Clear's CPU-fallback *profile* for the Stage-1 prototype.

Production Clear paints with GPU compute on wgpu (Doc 02 §3); SVG gives the
prototype deterministic, inspectable output and a browser-viewable preview
without a GPU toolchain. What is being validated is scene+layout semantics,
not this paint backend.
"""
from __future__ import annotations

import xml.sax.saxutils as xml

from .scene import DEFAULT_THEME


def _color(value, default=None):
    if value is None:
        return default
    if isinstance(value, str) and value in DEFAULT_THEME:
        return DEFAULT_THEME[value]
    return str(value)


def _f(v):
    return f"{v:.1f}"


def to_svg(root, width: float, height: float, tap_prefix: str | None = None,
           body_only: bool = False) -> str:
    parts: list[str] = []
    for child in root.children:
        _paint(child, parts, tap_prefix)
    body = "".join(parts)
    if body_only:
        return body
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(width)}" '
        f'height="{_f(height)}" viewBox="0 0 {_f(width)} {_f(height)}" '
        f'role="img" font-family="system-ui, -apple-system, Segoe UI, sans-serif">'
        f'<rect width="100%" height="100%" fill="{DEFAULT_THEME["paper"]}"/>'
        f"{body}</svg>"
    )


def _wrap_tap(node, svg_frag: str, tap_prefix) -> str:
    if tap_prefix and "tap" in node.events:
        return (f'<a href="{tap_prefix}{xml.escape(node.path)}">'
                f"<title>{xml.escape(node.text or node.kind)}</title>"
                f"{svg_frag}</a>")
    return svg_frag


def _paint(node, out: list[str], tap_prefix):
    k = node.kind
    bg = _color(node.props.get("background"))
    corners = float(node.props.get("corners", 0) or 0)

    if k in ("column", "row", "stack", "grid", "scroll", "table", "header"):
        if bg:
            out.append(f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                       f'height="{_f(node.h)}" rx="{_f(corners)}" fill="{bg}"/>')
        for ch in node.children:
            _paint(ch, out, tap_prefix)
        return

    if k == "box":
        shape = node.props.get("shape")
        if shape == "circle":
            out.append(f'<circle cx="{_f(node.x + node.w/2)}" cy="{_f(node.y + node.h/2)}" '
                       f'r="{_f(min(node.w, node.h)/2)}" fill="{bg or "none"}"/>')
        else:
            shadow = ' filter="url(#)" ' if False else ""
            out.append(f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                       f'height="{_f(node.h)}" rx="{_f(corners)}" fill="{bg or "none"}"/>')
        frags = out[-1:]
        del out[-1:]
        inner: list[str] = []
        for ch in node.children:
            _paint(ch, inner, tap_prefix)
        out.append(_wrap_tap(node, frags[0] + "".join(inner), tap_prefix))
        return

    if k in ("text", "cell"):
        size = float(node.props.get("size", 16))
        fill = _color(node.props.get("color"), DEFAULT_THEME["ink"])
        weight = ' font-weight="700"' if "bold" in node.flags else ""
        deco = ' text-decoration="line-through"' if "strike" in node.flags else ""
        align_end = node.props.get("align") == "end"
        tx = node.x + node.w - 10 if (k == "cell" and align_end) else \
            node.x + (10 if k == "cell" else 0)
        anchor = "end" if (k == "cell" and align_end) else "start"
        lines = node.props.get("_lines") or [node.text]
        tspans = "".join(
            f'<tspan x="{_f(tx)}" y="{_f(node.y + (8 if k == "cell" else 0) + i * size * 1.3)}">'
            f'{xml.escape(ln)}</tspan>' for i, ln in enumerate(lines))
        frag = (f'<text font-size="{_f(size)}" '
                f'fill="{fill}"{weight}{deco} text-anchor="{anchor}" '
                f'dominant-baseline="hanging">{tspans}</text>')
        if k == "cell":
            frag = (f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                    f'height="{_f(node.h)}" fill="none" stroke="#E8E8EF"/>') + frag
            out.append(_wrap_tap(node, frag, tap_prefix))
            return
        if bg:
            frag = (f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                    f'height="{_f(node.h)}" rx="{_f(corners)}" fill="{bg}"/>') + frag
        out.append(_wrap_tap(node, frag, tap_prefix))
        return

    if k == "button":
        is_plain = "plain" in node.flags
        b = bg or ("none" if is_plain else DEFAULT_THEME["accent"])
        fill = _color(node.props.get("color"),
                      DEFAULT_THEME["accent"] if is_plain else DEFAULT_THEME["on-accent"])
        r = corners if corners else 10.0
        size = float(node.props.get("size", 16))
        weight = ' font-weight="600"'  # buttons read as actions
        if "bold" in node.flags:
            weight = ' font-weight="700"'
        frag = (
            f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
            f'height="{_f(node.h)}" rx="{_f(r)}" fill="{b}"/>'
            f'<text x="{_f(node.x + node.w/2)}" y="{_f(node.y + node.h/2)}" '
            f'font-size="{_f(size)}" fill="{fill}"{weight} text-anchor="middle" '
            f'dominant-baseline="central">{xml.escape(node.text)}</text>'
        )
        if "disabled" in node.flags:
            frag = f'<g opacity="0.5">{frag}</g>'
        out.append(_wrap_tap(node, frag, tap_prefix))
        return

    if k == "input":
        ph = node.props.get("placeholder", "")
        val = node.text
        shown = val if val else ph
        fill = DEFAULT_THEME["ink"] if val else DEFAULT_THEME["muted"]
        frag = (
            f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
            f'height="{_f(node.h)}" rx="10" fill="{bg or "#FFFFFF"}" '
            f'stroke="#D8D8E0"/>'
            f'<text x="{_f(node.x + 14)}" y="{_f(node.y + node.h/2)}" '
            f'font-size="16" fill="{fill}" dominant-baseline="central">'
            f'{xml.escape(shown)}</text>'
        )
        out.append(frag)
        return

    if k == "toggle":
        on = node.props.get("_on", False)
        track = DEFAULT_THEME["accent"] if on else "#D8D8E0"
        knob_x = node.x + node.w - 15 if on else node.x + 15
        frag = (f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                f'height="{_f(node.h)}" rx="{_f(node.h/2)}" fill="{track}"/>'
                f'<circle cx="{_f(knob_x)}" cy="{_f(node.y + node.h/2)}" r="11" fill="#fff"/>')
        out.append(_wrap_tap(node, frag, tap_prefix))
        return

    if k == "divider":
        out.append(f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                   f'height="1" fill="#E2E2E8"/>')
        return

    if k == "image":
        frag = (f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                f'height="{_f(node.h)}" rx="{_f(corners)}" fill="#E8E8F2"/>'
                f'<text x="{_f(node.x + node.w/2)}" y="{_f(node.y + node.h/2)}" '
                f'font-size="12" fill="{DEFAULT_THEME["muted"]}" text-anchor="middle" '
                f'dominant-baseline="central">🖼 {xml.escape(node.text or "image")}</text>')
        out.append(_wrap_tap(node, frag, tap_prefix))
        return

    if k == "scene3d":
        frag = (f'<rect x="{_f(node.x)}" y="{_f(node.y)}" width="{_f(node.w)}" '
                f'height="{_f(node.h)}" fill="#20202A"/>'
                f'<text x="{_f(node.x + node.w/2)}" y="{_f(node.y + node.h/2 - 8)}" '
                f'font-size="28" text-anchor="middle" fill="#BDBDF5">◆</text>'
                f'<text x="{_f(node.x + node.w/2)}" y="{_f(node.y + node.h/2 + 22)}" '
                f'font-size="13" fill="#C9C9D1" text-anchor="middle">'
                f'3D · {xml.escape(node.text or "scene")}</text>')
        out.append(_wrap_tap(node, frag, tap_prefix))
        return

    if k == "spinner":
        out.append(f'<circle cx="{_f(node.x + node.w/2)}" cy="{_f(node.y + node.h/2)}" '
                   f'r="11" fill="none" stroke="{DEFAULT_THEME["accent"]}" '
                   f'stroke-width="3" stroke-dasharray="40 30">'
                   f'<animateTransform attributeName="transform" type="rotate" '
                   f'from="0 {node.x + node.w/2:.0f} {node.y + node.h/2:.0f}" '
                   f'to="360 {node.x + node.w/2:.0f} {node.y + node.h/2:.0f}" '
                   f'dur="0.9s" repeatCount="indefinite"/></circle>')
        return

    for ch in node.children:  # fallback: paint children (children slot)
        _paint(ch, out, tap_prefix)
