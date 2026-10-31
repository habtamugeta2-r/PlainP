"""PL expression parser + evaluator (Stage-1 subset).

Grammar (lowest→highest precedence):
  conditional : or_expr [ 'if' or_expr 'otherwise' conditional ]
  or/and, comparison (is, >=, <=, >, <, contains, lacks, exists…),
  additive, multiplicative, unary (not, -), pipe/postfix, primary.

Postfix *pipeline* words (Doc 06 decision): `trimmed`, `count`, `length`,
`first`, `where <cond>`, `sorted by <key>`, `from <n> take <n>`,
`clamped a to b`, `at-least n`, `as <format>`. `where` filters apply to the
underlying list before terminal ops (`tasks count where not done`).
Per-item conditions see the item's fields as bare names (`done` = item.done).

Values: int/float, str, bool (yes/no), list, dict (kinds/records),
None = `nothing`.
"""
from __future__ import annotations

import math

from . import tokens as T
from .errors import PlainError, UnsupportedYet

# ---- AST --------------------------------------------------------------------

class E:  # tiny tuple-AST helpers keep this file compact
    pass


def parse_expr(src: str, line_no: int | None = None):
    toks = T.tokenize(src)
    p = _Parser(toks, src, line_no)
    node = p.conditional()
    if p.pos != len(toks):
        rest = T.detokenize(toks[p.pos:])
        raise PlainError(f"I couldn't make sense of the end of this: `{rest}`.",
                         line_no=line_no, line_text=src)
    return node


class _Parser:
    def __init__(self, toks, src, line_no):
        self.toks, self.src, self.line_no = toks, src, line_no
        self.pos = 0

    # -- helpers
    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def next(self):
        t = self.peek()
        self.pos += 1
        return t

    def at_name(self, *words):
        t = self.peek()
        return t is not None and t.kind == T.NAME and t.text in words

    def at_op(self, *ops):
        t = self.peek()
        return t is not None and t.kind == T.OP and t.text in ops

    def expect_name(self, word):
        if not self.at_name(word):
            raise PlainError(f"Expected `{word}` here.", self.line_no, self.src)
        return self.next()

    # -- grammar
    def conditional(self):
        node = self.or_expr()
        if self.at_name("if"):
            self.next()
            cond = self.or_expr()
            self.expect_name("otherwise")
            other = self.conditional()
            return ("cond", cond, node, other)
        return node

    def or_expr(self):
        node = self.and_expr()
        while self.at_name("or"):
            self.next()
            node = ("or", node, self.and_expr())
        return node

    def and_expr(self):
        node = self.comparison()
        while self.at_name("and"):
            self.next()
            node = ("and", node, self.comparison())
        return node

    _CMP_NAMES = ("contains", "lacks")

    def comparison(self):
        node = self.additive()
        while True:
            if self.at_op(">=", "<=", ">", "<", "==", "!="):
                op = self.next().text
                node = ("cmp", op, node, self.additive())
            elif self.at_name(*self._CMP_NAMES):
                op = self.next().text
                node = ("cmp", op, node, self.additive())
            elif self.at_name("is"):
                self.next()
                if self.at_name("empty"):
                    self.next()
                    node = ("cmp", "is empty", node, None)
                elif self.at_name("nothing"):
                    self.next()
                    node = ("cmp", "is nothing", node, None)
                else:
                    node = ("cmp", "is", node, self.additive())
            elif self.at_name("exists"):
                self.next()
                node = ("cmp", "exists", node, None)
            else:
                return node

    def additive(self):
        node = self.multiplicative()
        while self.at_op("+", "-"):
            op = self.next().text
            node = ("bin", op, node, self.multiplicative())
        return node

    def multiplicative(self):
        node = self.unary()
        while self.at_op("*", "/"):
            op = self.next().text
            node = ("bin", op, node, self.unary())
        return node

    def unary(self):
        if self.at_name("not"):
            self.next()
            return ("not", self.unary())
        if self.at_op("-"):
            self.next()
            return ("neg", self.unary())
        return self.pipeline()

    _PIPE_WORDS = ("trimmed", "count", "length", "first", "capitalized")

    def pipeline(self):
        node = self.primary()
        ops = []
        while True:
            t = self.peek()
            if t is None or t.kind != T.NAME:
                break
            w = t.text
            if w in self._PIPE_WORDS:
                self.next()
                ops.append((w,))
            elif w == "where":
                self.next()
                ops.append(("where", self._pipe_condition()))
            elif w == "sorted":
                self.next()
                self.expect_name("by")
                key = self.additive()
                rev = None
                if self.at_name("reversed"):
                    self.next()
                    if self.at_name("if"):
                        self.next()
                        rev = self.or_expr()
                    else:
                        rev = True
                ops.append(("sorted", key, rev))
            elif w == "from":
                self.next()
                start = self.additive()
                self.expect_name("take")
                ops.append(("slice", start, self.additive()))
            elif w == "ready-or":
                self.next()
                ops.append(("ready-or", self.additive()))
            elif w == "clamped":
                self.next()
                lo = self.additive()
                self.expect_name("to")
                ops.append(("clamp", lo, self.additive()))
            elif w == "at-least":
                self.next()
                ops.append(("at-least", self.additive()))
            elif w == "as":
                self.next()
                fmt = self.next()
                ops.append(("as", fmt.text if fmt else ""))
            else:
                break
        return ("pipe", node, ops) if ops else node

    def _pipe_condition(self):
        """A per-item condition. It is GREEDY: in `tasks where A or B` the
        whole `A or B` filters (examples/02, /05) — the condition runs to
        the end of the pipeline segment (stops at `if`, `)`, EOL)."""
        return self.or_expr()

    def primary(self):
        t = self.next()
        if t is None:
            raise PlainError("This line seems to end mid-thought.",
                             self.line_no, self.src)
        if t.kind == T.NUMBER:
            return ("lit", _number(t.text))
        if t.kind == T.COLOR:
            return ("lit", t.text)
        if t.kind == T.STRING:
            return ("str", t.text)
        if t.kind == T.LPAREN:
            node = self.conditional()
            if self.peek() and self.peek().kind == T.RPAREN:
                self.next()
            return self._postfix(node)
        if t.kind == T.LBRACKET:
            items = []
            while self.peek() and self.peek().kind != T.RBRACKET:
                items.append(self.conditional())
                if self.peek() and self.peek().kind == T.COMMA:
                    self.next()
            if self.peek():
                self.next()  # ]
            return self._postfix(("list", items))
        if t.kind == T.NAME:
            if t.text == "yes":
                return ("lit", True)
            if t.text == "no":
                return ("lit", False)
            if t.text == "nothing":
                return ("lit", None)
            # call?  Name(...)
            if self.peek() and self.peek().kind == T.LPAREN:
                self.next()
                args, kwargs = [], {}
                while self.peek() and self.peek().kind != T.RPAREN:
                    save = self.pos
                    if (self.peek().kind == T.NAME and self.pos + 1 < len(self.toks)
                            and self.toks[self.pos + 1].kind == T.COLON):
                        key = self.next().text
                        self.next()  # colon
                        kwargs[key] = self.conditional()
                    else:
                        self.pos = save
                        args.append(self.conditional())
                    if self.peek() and self.peek().kind == T.COMMA:
                        self.next()
                if self.peek():
                    self.next()  # )
                return self._postfix(("call", t.text, args, kwargs))
            return self._postfix(("name", t.text))
        raise PlainError(f"I didn't expect `{t.text}` here.",
                         self.line_no, self.src)

    def _postfix(self, node):
        # member access: .name  (also bare uppercase starts are names already)
        while self.peek() is not None and self.peek().kind == T.OP and self.peek().text == ".":
            self.next()
            member = self.next()
            if member is None:
                raise PlainError("Expected a name after `.`.", self.line_no, self.src)
            node = ("member", node, member.text)
        return node


def _number(s: str):
    mult = 1
    for suffix in ("ms", "deg", "s", "%"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    if "/" in s:  # ratio 4/3 -> keep as (num, den) marker string for aspect
        a, b = s.split("/")
        return ("ratio", float(a), float(b))
    v = float(s) * mult
    return int(v) if v.is_integer() else v


# ---- evaluation ---------------------------------------------------------------

class _Missing:
    def __repr__(self):
        return "<missing>"


MISSING = _Missing()


def truthy(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (list, str, dict)):
        return len(v) > 0
    if isinstance(v, (int, float)):
        return v != 0
    return True


def interpolate(text: str, env: dict, kinds: dict | None = None, line_no=None) -> str:
    """Expand {expr} segments in a string value."""
    out, i = [], 0
    while True:
        j = text.find("{", i)
        if j == -1:
            out.append(text[i:])
            break
        k = text.find("}", j)
        if k == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        val = evaluate_text(text[j + 1:k], env, kinds, line_no)
        out.append(display(val))
        i = k + 1
    return "".join(out)


def display(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, list):
        return ", ".join(display(x) for x in v)
    if isinstance(v, dict):
        return str(v.get("name") or v.get("title") or v)
    return str(v)


def evaluate_text(src: str, env: dict, kinds: dict | None = None, line_no=None):
    return evaluate(parse_expr(src, line_no), env, kinds or {}, line_no)


def evaluate(node, env: dict, kinds: dict, line_no=None):
    tag = node[0]
    if tag == "lit":
        return node[1]
    if tag == "str":
        return interpolate(node[1], env, kinds, line_no)
    if tag == "list":
        return [evaluate(x, env, kinds, line_no) for x in node[1]]
    if tag == "name":
        name = node[1]
        if name in env:
            return env[name]
        if name.endswith("-link"):
            # Page-link literal (Doc 06 G-9): `Home-link` is the link to the
            # Home page — {title, page}. Lets nav data be plain values.
            stem = name[: -len("-link")]
            return {"_kind": "Link", "title": stem.replace("-", " ").title(),
                    "page": stem[:1].upper() + stem[1:]}
        raise PlainError(
            f"`{name}` doesn't mean anything here yet. Did you forget to "
            f"create it above with `{name} = …`?", line_no=line_no)
    if tag == "member":
        obj = evaluate(node[1], env, kinds, line_no)
        key = node[2]
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            raise PlainError(f"This value has no `{key}`.", line_no=line_no)
        raise PlainError(f"Only records have parts like `.{key}`.",
                         line_no=line_no)
    if tag == "call":
        _, name, args, kwargs = node
        return _call(name, args, kwargs, env, kinds, line_no)
    if tag == "not":
        return not truthy(evaluate(node[1], env, kinds, line_no))
    if tag == "neg":
        return -evaluate(node[1], env, kinds, line_no)
    if tag == "and":
        return truthy(evaluate(node[1], env, kinds, line_no)) and \
            truthy(evaluate(node[2], env, kinds, line_no))
    if tag == "or":
        return truthy(evaluate(node[1], env, kinds, line_no)) or \
            truthy(evaluate(node[2], env, kinds, line_no))
    if tag == "bin":
        _, op, a, b = node
        av, bv = evaluate(a, env, kinds, line_no), evaluate(b, env, kinds, line_no)
        if op == "+":
            return av + bv
        if op == "-":
            return av - bv
        if op == "*":
            return av * bv
        if op == "/":
            return av / bv if bv else 0
    if tag == "cmp":
        _, op, a, b = node
        av = evaluate(a, env, kinds, line_no)
        if op == "exists":
            return av is not None
        if op == "is nothing":
            return av is None
        if op == "is empty":
            return av is None or (isinstance(av, (str, list, dict)) and len(av) == 0)
        bv = evaluate(b, env, kinds, line_no) if b is not None else None
        if op == "is" or op == "==":
            return av == bv
        if op == "!=":
            return av != bv
        if op == ">=":
            return av >= bv
        if op == "<=":
            return av <= bv
        if op == ">":
            return av > bv
        if op == "<":
            return av < bv
        if op == "contains":
            return str(bv) in str(av) if isinstance(av, str) else bv in av
        if op == "lacks":
            return str(bv) not in str(av)
    if tag == "cond":
        _, cond, yes_v, no_v = node
        branch = yes_v if truthy(evaluate(cond, env, kinds, line_no)) else no_v
        return evaluate(branch, env, kinds, line_no)
    if tag == "pipe":
        return _eval_pipe(node, env, kinds, line_no)
    raise PlainError(f"Internal: unknown expression `{tag}`.", line_no=line_no)


def _eval_pipe(node, env, kinds, line_no):
    _, base, ops = node
    val = evaluate(base, env, kinds, line_no)
    # `where` filters apply to the underlying list before terminal ops, so
    # `tasks count where not done` counts the filtered list (Doc 06).
    ordered = [o for o in ops if o[0] == "where"] + [o for o in ops if o[0] != "where"]
    for op in ordered:
        name = op[0]
        if name == "trimmed":
            val = str(val).strip() if val is not None else ""
        elif name == "capitalized":
            val = str(val).capitalize()
        elif name == "count":
            val = len(val) if isinstance(val, (list, str, dict)) else 0
        elif name == "length":
            val = len(val) if isinstance(val, (list, str)) else 0
        elif name == "first":
            val = val[0] if isinstance(val, list) and val else None
        elif name == "where":
            cond = op[1]
            if not isinstance(val, list):
                raise PlainError("`where` filters a list — this isn't one.",
                                 line_no=line_no)
            val = [it for it in val
                   if truthy(evaluate(cond, _item_env(env, it), kinds, line_no))]
        elif name == "sorted":
            _, key_node, rev_node = op
            key_name = _key_name(key_node, env, kinds, line_no)
            rev = rev_node if isinstance(rev_node, bool) else (
                truthy(evaluate(rev_node, env, kinds, line_no)) if rev_node else False)
            val = sorted(val or [],
                         key=lambda it: evaluate(key_node, _item_env(env, it, key_name), kinds, line_no)
                         if key_name is None else _item_key(it, key_name),
                         reverse=bool(rev))
        elif name == "slice":
            start = int(evaluate(op[1], env, kinds, line_no))
            n = int(evaluate(op[2], env, kinds, line_no))
            val = (val or [])[start:start + n]
        elif name == "ready-or":
            default = evaluate(op[1], env, kinds, line_no)
            if isinstance(val, tuple) and len(val) == 2 and val[0] in ("ready", "failed", "loading"):
                val = val[1] if val[0] == "ready" else default
            elif val is None:
                val = default
        elif name == "clamp":
            lo = evaluate(op[1], env, kinds, line_no)
            hi = evaluate(op[2], env, kinds, line_no)
            val = max(lo, min(hi, val))
        elif name == "at-least":
            val = max(val, evaluate(op[1], env, kinds, line_no))
        elif name == "as":
            val = _format_as(val, op[1])
        else:  # pragma: no cover
            raise PlainError(f"Internal: unknown pipe `{name}`.", line_no=line_no)
    return val


def _item_env(env, item):
    merged = dict(env)
    if isinstance(item, dict):
        merged.update(item)
    merged.setdefault("item", item)
    return merged


def _key_name(key_node, env, kinds, line_no):
    """`sorted by sort-by` — sort-by holds the FIELD NAME as text."""
    v = evaluate(key_node, env, kinds, line_no)
    return v if isinstance(v, str) else None


def _item_key(item, key_name):
    return item.get(key_name) if isinstance(item, dict) else item


def _format_as(val, fmt):
    if val is None:
        return ""
    if fmt == "money":
        try:
            return f"${float(val):,.0f}" if float(val) == int(float(val)) else f"${float(val):,.2f}"
        except (TypeError, ValueError):
            return display(val)
    if fmt in ("date", "time", "sentence"):
        return display(val)
    return display(val)


def _call(name, arg_nodes, kw_nodes, env, kinds, line_no):
    if name in kinds:  # record construction: Task(title: x) / Finish("Oak", …)
        kind = kinds[name]
        record = {"_kind": name}
        for f in kind.fields:
            record[f.name] = evaluate_text(f.default, env, kinds, line_no) \
                if f.default else None
        for f, a in zip(kind.fields, arg_nodes):
            record[f.name] = evaluate(a, env, kinds, line_no)
        for k, a in kw_nodes.items():
            record[k] = evaluate(a, env, kinds, line_no)
        return record
    args = [evaluate(a, env, kinds, line_no) for a in arg_nodes]
    if name == "ceil":
        return math.ceil(args[0])
    if name == "floor":
        return math.floor(args[0])
    if name in ("post", "fetch"):
        raise UnsupportedYet("network calls (`post`)", "Stage 3", line_no)
    if name in ("go",):
        raise UnsupportedYet("navigation calls", "Stage 3", line_no)
    raise PlainError(
        f"`{name}(…)` — I don't know a `{name}` to call here.", line_no=line_no)


# ---- statements ----------------------------------------------------------------

def execute_assign(target: str, op: str, expr_src: str, env: dict,
                   write: dict, kinds: dict, line_no=None):
    """Execute `name = expr` / `+=` / `-=`. Targets may be dotted
    (`task.done`). `env` is read-view, `write` is the state dict mutated."""
    value = evaluate_text(expr_src, env, kinds, line_no)
    parts = target.split(".")
    if len(parts) == 1:
        name = parts[0]
        if op == "=":
            write[name] = value
        elif op == "+=":
            write[name] = write.get(name, env.get(name, 0)) + value
        elif op == "-=":
            write[name] = write.get(name, env.get(name, 0)) - value
        return
    # dotted: mutate the record value in place (records are dicts)
    obj = write.get(parts[0], env.get(parts[0]))
    if not isinstance(obj, dict):
        raise PlainError(f"`{parts[0]}` isn't a record, so it has no parts "
                         f"to change.", line_no=line_no)
    obj[parts[-1]] = value if op == "=" else obj.get(parts[-1], 0) + (value if op == "+=" else -value)
