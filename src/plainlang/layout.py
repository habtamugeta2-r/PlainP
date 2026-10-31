"""Flow layout (Doc 02 §2): constraints go down, sizes go up, the parent
sets positions — one single-pass protocol (after Flutter's RenderBox,
with PL's authoring words on top).

Stage-1 scope: column/row/stack/grid/scroll containers; text/button/input/
toggle/image/box/divider/spacer leaves; `fill/fit/fixed + max` sizes,
padding (1/2/4), gap, align (cross axis), spread (main-axis distribution),
grow. Text metrics are deterministic approximations (production Clear uses
HarfBuzz — Doc 02 §4); they are the same on every machine, which is what
golden tests need.
"""
from __future__ import annotations

from dataclasses import dataclass

INF = float("inf")


@dataclass
class Constraints:
    max_w: float = INF
    max_h: float = INF


def layout(root, width: float, height: float):
    """Lay out a page scene into a width×height viewport (in place)."""
    for child in root.children:
        _measure(child, Constraints(width, height))
        # Stage-1 page semantics: the page is the viewport; its single root
        # child fills it unless it asks to be smaller (max width + center-self).
        if "center-self" in child.flags:
            child.x = max(0.0, (width - child.w) / 2)
        if child.props.get("width", {}).get("mode") in ("fill", None) and \
                child.kind in ("column", "row") and not _has_max(child, "width"):
            child.w = width
        if child.kind in ("column", "row") and child.props.get("height", {}).get("mode") != "fixed":
            child.h = max(child.h, height) if child.props.get("spread") else child.h
            if child.props.get("height", {}).get("mode") == "fill":
                child.h = height
        _place(child, child.x, child.y)
    root.w, root.h = width, height
    return root


# ---- helpers ------------------------------------------------------------------

def _pad(node) -> tuple[float, float, float, float]:
    p = node.props.get("padding")
    if not p:
        return (0, 0, 0, 0)
    if len(p) == 1:
        t = r = b = l = p[0]
    elif len(p) == 2:
        t = b = p[0]
        r = l = p[1]
    else:
        t, r, b, l = (p + [0, 0, 0, 0])[:4]
    return (t, r, b, l)


def _len_spec(v, extent: float):
    if v is None:
        return None
    s = str(v)
    if s.endswith("%"):
        base = extent if extent != INF else 0
        return float(s[:-1]) / 100.0 * base
    return float(s)


def _apply_size(node, axis: str, fit: float, extent: float) -> float:
    spec = node.props.get(axis)
    if not spec:
        return fit
    mode = spec.get("mode", "fit")
    if mode == "fill" and extent != INF:
        val = extent
    elif mode == "fixed":
        val = _len_spec(spec.get("value"), extent) or fit
    else:
        val = fit
    mx = _len_spec(spec.get("max"), extent)
    if mx is not None:
        val = min(val, mx)
    mn = _len_spec(spec.get("min"), extent)
    if mn is not None:
        val = max(val, mn)
    return val


def _has_max(node, axis):
    spec = node.props.get(axis)
    return bool(spec and spec.get("max") is not None)


def text_size(node, text: str) -> tuple[float, float]:
    size = float(node.props.get("size", _DEFAULT_TEXT))
    factor = 0.56 if "bold" in node.flags else 0.52
    return (len(text) * size * factor, size * 1.3)


_DEFAULT_TEXT = 16.0


# ---- measure ---------------------------------------------------------------------

def _measure(node, c: Constraints) -> tuple[float, float]:
    k = node.kind
    t, r, b, l = _pad(node)
    inner = Constraints(max(0.0, c.max_w - l - r) if c.max_w != INF else INF,
                        max(0.0, c.max_h - t - b) if c.max_h != INF else INF)

    if k == "text":
        w, h = text_size(node, node.text)
        node.w = _apply_size(node, "width", w + l + r, c.max_w)
        node.h = _apply_size(node, "height", h + t + b, c.max_h)
        return node.w, node.h

    if k == "button":
        w, h = text_size(node, node.text)
        bt, br, bb, bl = (t, r, b, l) if node.props.get("padding") else (12, 20, 12, 20)
        node.props.setdefault("padding", [bt, br])
        node.w = _apply_size(node, "width", w + bl + br, c.max_w)
        node.h = _apply_size(node, "height", max(44.0, h + bt + bb), c.max_h)
        return node.w, node.h

    if k == "input":
        label = node.text or node.props.get("placeholder", "")
        tw, th = text_size(node, label or " ")
        node.w = _apply_size(node, "width", tw + 28, c.max_w)
        node.h = _apply_size(node, "height", max(44.0, th + 20), c.max_h)
        node.w = max(node.w, 140.0)
        return node.w, node.h

    if k == "toggle":
        node.w, node.h = 52.0, 30.0
        return node.w, node.h

    if k == "divider":
        node.w = c.max_w if c.max_w != INF else 100.0
        node.h = 1.0
        return node.w, node.h

    if k == "spacer":
        s = float(node.props.get("size", 0) or 0)
        node.w, node.h = s, s
        return node.w, node.h

    if k == "spinner":
        node.w = node.h = 28.0
        return node.w, node.h

    if k == "image":
        aspect = float(node.props.get("aspect", 4 / 3))
        w = _apply_size(node, "width", 200.0, c.max_w)
        if node.props.get("size"):
            w = float(node.props["size"])
            node.w = node.h = w
            return node.w, node.h
        node.w = w
        node.h = _apply_size(node, "height", w / aspect, c.max_h)
        return node.w, node.h

    if k == "box":
        if node.props.get("size"):
            s = float(node.props["size"])
            node.w, node.h = s, s
            for ch in node.children:
                _measure(ch, Constraints(s, s))
            return node.w, node.h
        cw = ch_max = 0.0
        for ch in node.children:
            _measure(ch, inner)
            cw = max(cw, ch.w)
            ch_max = max(ch_max, ch.h)
        node.w = _apply_size(node, "width", cw + l + r, c.max_w)
        node.h = _apply_size(node, "height", ch_max + t + b, c.max_h)
        return node.w, node.h

    if k in ("column", "scroll"):
        gap = float(node.props.get("gap", 0) or 0)
        for ch in node.children:
            _measure(ch, inner)
        content_w = max([ch.w for ch in node.children], default=0.0)
        content_h = sum(ch.h for ch in node.children) \
            + gap * max(0, len(node.children) - 1)
        node.w = _apply_size(node, "width", content_w + l + r, c.max_w)
        node.h = _apply_size(node, "height", content_h + t + b, c.max_h)
        if node.w == c.max_w and c.max_w != INF:
            _stretch_growers(node, horizontal=False)
        return node.w, node.h

    if k == "row":
        gap = float(node.props.get("gap", 0) or 0)
        for ch in node.children:
            _measure(ch, inner)
        content_w = sum(ch.w for ch in node.children) \
            + gap * max(0, len(node.children) - 1)
        content_h = max([ch.h for ch in node.children], default=0.0)
        node.w = _apply_size(node, "width", content_w + l + r, c.max_w)
        node.h = _apply_size(node, "height", content_h + t + b, c.max_h)
        return node.w, node.h

    if k == "grid":
        gap = float(node.props.get("gap", 0) or 0)
        cols = int(node.props.get("columns", 2) or 2)
        cell_w = (inner.max_w - gap * (cols - 1)) / cols if inner.max_w != INF else 150
        for ch in node.children:
            _measure(ch, Constraints(cell_w, INF))
            ch.w = cell_w
            if ch.kind == "image":
                ch.h = cell_w / float(ch.props.get("aspect", 4 / 3))
        rows = (len(node.children) + cols - 1) // cols or 1
        row_h = max([ch.h for ch in node.children], default=0.0)
        node.w = _apply_size(node, "width", inner.max_w if inner.max_w != INF else cols * cell_w, c.max_w)
        node.h = _apply_size(node, "height", rows * row_h + gap * (rows - 1) + t + b, c.max_h)
        node.props["_cols"] = cols
        node.props["_cell_w"] = cell_w
        node.props["_row_h"] = row_h
        return node.w, node.h

    if k == "stack":
        w = h = 0.0
        for ch in node.children:
            _measure(ch, inner)
            w = max(w, ch.w)
            h = max(h, ch.h)
        node.w = _apply_size(node, "width", w + l + r, c.max_w)
        node.h = _apply_size(node, "height", h + t + b, c.max_h)
        return node.w, node.h

    # unknown leaf: zero-size (checker/engine warnings live elsewhere)
    node.w, node.h = 0.0, 0.0
    return node.w, node.h


def _stretch_growers(node, horizontal: bool):
    pass  # grow distribution happens in _place; measuring stays fit-based


# ---- place -----------------------------------------------------------------------

def _place(node, x: float, y: float):
    node.x, node.y = x, y
    k = node.kind
    t, r, b, l = _pad(node)
    cx, cy = x + l, y + t
    inner_w, inner_h = node.w - l - r, node.h - t - b
    gap = float(node.props.get("gap", 0) or 0)
    align = node.props.get("align", "start")
    if "center" in node.flags and k in ("text",):
        align = "center"

    if k in ("column", "scroll"):
        content_h = sum(ch.h for ch in node.children) + gap * max(0, len(node.children) - 1)
        free = max(0.0, inner_h - content_h)
        growers = [c for c in node.children if "grow" in c.flags]
        extra_gap = 0.0
        offset = 0.0
        spread = node.props.get("spread")
        if growers and free > 0:
            share = free / len(growers)
            for g in growers:
                g.h += share
            free = 0.0
        elif spread == "center":
            offset = free / 2
        elif spread == "end":
            offset = free
        elif spread == "between" and len(node.children) > 1:
            extra_gap = free / (len(node.children) - 1)
        cur = cy + offset
        for ch in node.children:
            chx = cx
            if align == "center":
                chx = cx + (inner_w - ch.w) / 2
            elif align == "end":
                chx = cx + inner_w - ch.w
            elif align == "stretch":
                ch.w = inner_w
                _remeasure_stretched(ch)
            if "grow" in ch.flags and ch.kind in ("input", "scroll", "column", "row"):
                pass
            if "center-self" in ch.flags:
                chx = cx + (inner_w - ch.w) / 2
            _place(ch, chx, cur)
            cur += ch.h + gap + extra_gap

    elif k == "row":
        content_w = sum(ch.w for ch in node.children) + gap * max(0, len(node.children) - 1)
        free = max(0.0, inner_w - content_w)
        growers = [c for c in node.children if "grow" in c.flags]
        extra_gap = 0.0
        offset = 0.0
        spread = node.props.get("spread")
        if growers and free > 0:
            share = free / len(growers)
            for g in growers:
                g.w += share
                _remeasure_stretched(g)
        elif spread == "center":
            offset = free / 2
        elif spread == "end":
            offset = free
        elif spread == "between" and len(node.children) > 1:
            extra_gap = free / (len(node.children) - 1)
        cur = cx + offset
        for ch in node.children:
            chy = cy
            if align == "center":
                chy = cy + (inner_h - ch.h) / 2
            elif align == "end":
                chy = cy + inner_h - ch.h
            elif align == "stretch":
                ch.h = inner_h
            _place(ch, cur, chy)
            cur += ch.w + gap + extra_gap

    elif k == "grid":
        cols = int(node.props.get("_cols", 2))
        cell_w = float(node.props.get("_cell_w", 0))
        row_h = float(node.props.get("_row_h", 0))
        for n, ch in enumerate(node.children):
            _place(ch, cx + (n % cols) * (cell_w + gap), cy + (n // cols) * (row_h + gap))

    elif k in ("stack", "box"):
        for ch in node.children:
            chx, chy = cx, cy
            if k == "box" or align == "center":
                chx = cx + (inner_w - ch.w) / 2
                chy = cy + (inner_h - ch.h) / 2
            _place(ch, chx, chy)


def _remeasure_stretched(node):
    """After a grow/stretch resize, re-place descendants against new size."""
    if node.children:
        _measure_children_only(node)


def _measure_children_only(node):
    t, r, b, l = _pad(node)
    inner = Constraints(max(0.0, node.w - l - r), max(0.0, node.h - t - b))
    for ch in node.children:
        _measure(ch, inner)
