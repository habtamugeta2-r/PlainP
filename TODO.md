# TODO — PLAIN / PL, the complete work list

> Read of the entire repository on **2026-10-31** (all 7 docs, 17 Python
> modules, 7 Rust modules, 9 normative examples, 3 sidecar fixtures, the
> CI workflow, Makefile, README, launcher and tests), followed by running
> every command the project advertises. This is the exhaustive backlog:
> what is done, what is broken, what is missing, in what order, and how
> each item is judged finished.
>
> Nothing in this file changes the project's philosophy (Doc 03 §11).
> Every task is subject to the Plain Test: if the fix makes PL less plain,
> the fix is wrong.

---

## TL;DR — the six things that matter most

1. **The prototype is real.** All 9 examples parse, check, render and
   34 tests pass. The architecture claims are unusually well matched by
   running code. This backlog is about closing the gap between "renders"
   and "the docs are true", not about starting over.
2. **Interactivity inside component slots is broken** (`P0-01`). The Form
   example cannot be typed into, and any button inside a `children` slot
   is dead. This is the single highest-value fix in the repo.
3. **Valid PL is silently ignored** (`P0-03`): gestures, `theme:`, `use:`,
   `transition`, unsupported props. Silent no-ops are worse than errors —
   they make the spec untrustworthy.
4. **The type story is missing** (`EX-01…07`): units are discarded,
   `Money` is a float, `Result`/`Maybe` do not exist, and the checker does
   no name or type analysis. This is Stage 3's real content.
5. **Resources and actions cannot complete** (`P0-06`, `NET-01…07`):
   `post` is unimplemented and its error is misleading; chat send and form
   submit cannot run. Sidecar JSON is a good seam — finish behind it.
6. **The docs currently overstate the implementation** (`P0-11`,
   `P0-12`). Fix the counts, make `validate` fail, gate `fmt --check`,
   and keep the honest-deferred-list discipline that makes Doc 06 good.

**Recommended next move:** ship Milestone M0 (§21), then freeze the Stage-3
oracle semantics before starting Rust slice 3 (`RS-01`).

---

## 0. How to read this backlog

**Priority**

| Tag | Meaning |
|---|---|
| `P0` | Silent wrong behavior, a broken normative example, or a false claim. Fix before adding anything. |
| `P1` | Required to finish Stage 3 semantics already promised by Docs 03/05/06. |
| `P2` | Required for the Stage 4 "competitive" prototype (engine, tooling, tests). |
| `P3` | Stage 5 / ecosystem / platform targets. |

**Effort:** `S` ≤ ½ day · `M` 1–3 days · `L` 1–2 weeks · `XL` > 2 weeks.
**Status:** `☐ todo` · `◐ partial` · `⚠ bug` · `✅ verified done`.

**Definition of Done for every task** (the project's own rules, Doc 03 §10
and Doc 06 §1):

1. The behavior is implemented in the Python spec-oracle **and** at least one
   test asserts it (`tests/`), or the item explicitly says "Rust-only".
2. Every new semantic is written into `docs/03-pl-language-spec.md` (or
   recorded as an amendment in `docs/06-stage1-prototype.md` §5).
3. Errors are plain sentences: what, where (line + caret span), why, Try.
4. No new dependency in the oracle (Python stdlib only). Rust dependencies
   arrive only with the Clear slices and are recorded in an ADR.
5. `./plain check examples/*.plain`, `make test`, `./plain validate` and
   `./plain fmt --check examples/*.plain` all pass; CI enforces them.
6. Normative examples are never edited to make an implementation pass
   (Doc 03 preamble). If an example is wrong, the spec is amended first.

---

## 1. Verified baseline (2026-10-31)

Commands run from the repo root:

```text
$ PYTHONPATH=src python3 -m unittest discover -s tests
Ran 34 tests in 0.068s — OK

$ ./plain check examples/*.plain
9/9 OK (00–08)

$ ./plain validate
| Example | PL lines | Status | Nodes | SVG bytes | Build ms |
| 00 | 4 | renders ✓ | 4 | 535 | 0.7 |
| 01 | 12 | renders ✓ | 8 | 1154 | 1.2 |
| 02 | 54 | renders ✓ | 13 | 1633 | 4.1 |
| 03 | 23 | renders ✓ | 6 | 873 | 1.0 |
| 04 | 45 | renders ✓ | 22 | 2389 | 2.4 |
| 05 | 48 | renders ✓ | 47 | 7080 | 4.2 |
| 06 | 41 | renders ✓ | 14 | 1811 | 4.8 |
| 07 | 25 | renders ✓ | 7 | 1041 | 1.3 |
| 08 | 39 | renders ✓ | 20 | 2212 | 3.2 |

$ ./plain fmt --check examples/*.plain
FAILS on 02-todo, 06-form-validation, 07-page-transition (exit 1)

$ cargo --version
not installed in this sandbox; CI is the Rust compiler of record
```

**Code volume (actual):** Python package 4 002 LOC; Python tests 382 LOC;
Rust 2 414 LOC (15 `#[test]`s). `docs/06` still says "~3.1k LOC incl. tests"
and "22 tests" — both stale.

### 1.1 Honest capability matrix

| Area | Promised by docs | Actually working | Main gap |
|---|---|---|---|
| Lexer | Doc 03 §2, G-6 | ✅ hyphens, colors, units, ratios, continuations | no spans/columns |
| Parser | full corpus, G-1…G-10 | ◐ 9/9 parse, most constructs | defaults, variant kinds, `together`, `use`, themes, `whenever`, `every` |
| Checker | Doc 03 §10 | ◐ node/prop/look/action-name diagnostics, did-you-mean | no action bodies, no names in expressions, no types, no exhaustiveness |
| Runtime | Doc 03 §6, ADR-3 | ◐ state, `is`, actions, `keep`, nav stack, hot reload | recompute-on-read, no dep graph, no async/results |
| Resources | Doc 01 §3.1, §6.5 | ◐ sidecar JSON, `loading/ready/failed` matching | no HTTP, cache, retry, offline, streams, `refresh` |
| Scene | Doc 02 §1 | ◐ 19 of 31 declared node kinds, components, looks, `when` | slot interactions broken, only `ErrorBox` stdlib, no keyed identity |
| Layout | Doc 02 §2 (Flow) | ◐ column/row/stack/grid/scroll/table, grow/align/spread | container widths are viewport-derived; culling, logical axes, `at`, `spread around` missing |
| Paint | Doc 02 §3 | ◐ deterministic SVG | no shadows/gradients/borders/images/animation/3D |
| Text | Doc 02 §4 | ◐ fixed 0.52/0.56 metrics, greedy wrap | no shaping, bidi, ellipsis, IME |
| A11y | Doc 02 §1.4, Constraint 7 | ◐ derived roles/labels + CLI tree | no focus/keyboard/live regions/contrast/OS bridge |
| Dev server | Doc 03 §10 | ◐ taps, inputs (outside slots), sizes, hot reload, panels | no live push, one global session, slot inputs broken |
| CLI | Doc 03 §10 | ◐ check/render/run/a11y/parse/fmt/validate | `test`, `publish`, `add`, `lsp`, `--on phone` missing |
| Capabilities | Doc 01 §5, ADR-7 | ☐ `needs` only displayed | zero enforcement/sandboxing |
| Rust port | ADR-1, Doc 06 §8 | ◐ slices 1–2 (tokens/parser/checker) | expr/runtime/scene/layout/paint/window |
| Docs | 7 documents | ◐ rich and specific | drift in counts/status; spec amendments not folded in |

### 1.2 Things the docs claim that are not true today

Verified, with reproductions:

* **Form example 06 cannot be typed into.** Inputs inside a component
  `children` slot get `scope_path == ""`, so `App.set_field` raises
  `PlainError: That part of the page is gone (stale preview?)`.
  (`scene.py:444 call_scope_path` reads a `_path_hint` attribute that is
  never set.) The same bug kills every button/toggle/gesture placed inside
  any slot, not just forms.
* **Component default parameters are ignored.** `_params()` strips
  `size = 40` down to `size`, then `_expand_component` binds nothing for
  omitted args. Doc 03 §6.3's `Avatar(person, size = 40)` crashes with
  "`size` doesn't mean anything here yet" instead of using 40.
* **Unsupported gestures are silently accepted and never fire.**
  `on swipe-start`, `on long-press`, `on pinch`, `on drag-x`, `on hover`,
  `on key` are parsed into `node.events` and then ignored by `App.tap`;
  no warning, no `UnsupportedYet`. Example 02's swipe-to-delete and
  example 08's drag/scroll are decorative.
* **`theme:` and `use:` are silently swallowed.** Both become `RawStmt`s
  in `Program.themes` (a junk drawer that also receives `transition` and
  stray top-level lines). Example themes do nothing.
* **Units are discarded.** `300ms`, `2s`, `40deg`, `75%` all evaluate to
  bare `300`, `2`, `40`, `75` (`expr._number` multiplies by `1` and never
  records the suffix). Doc 03 §7.3's "units are types" is not implemented.
* **`post` and `then` produce misleading diagnostics.**
  `result = post "/api/signup" with …` fails inside the expression parser
  ("I couldn't make sense of the end of this"), not with the documented
  `UnsupportedYet("network calls (`post`)")`. `cart add x then show toast`
  is swallowed by the list-op regex before the toast branch is reached.
  Either way examples 04 and 06's actions cannot run.
* **`plain fmt --check` fails on the normative corpus** (02, 06, 07).
  The formatter reindents continuation lines and attaches top-level
  comments to the previous block's indent. The test only checks
  idempotence, not conformance; CI never runs `fmt`.
* **Password fields are rendered and dumped in clear.** `paint_svg` draws
  `input.text` regardless of the `secret` flag, and the preview's
  "live state" panel prints bound values verbatim.
* **`needs` is a display string.** The preview header shows it; nothing
  is granted, denied, enforced or revocable.
* **The checker never looks inside actions.** `to go:` bodies are not
  checked, so an unknown node in an action is only discovered on tap.
* **`validate` always exits 0**, including when examples fail — so CI's
  "Phase-5 validate harness" step cannot fail.

---

## 2. P0 — fix before anything else

### P0-01 · Slot children must inherit the caller's scope
`P0` · `M` · **⚠ bug** · `scene.py:238–245`, `scene.py:444`, `render.py:107`

* **Now:** `_expand_component` builds slot children with
  `call_scope_path(caller_sc)`, which returns `""` because `_path_hint` is
  never assigned. Every `bind`/event inside a slot stores `""`; dispatch
  raises "That part of the page is gone".
* **Do:** pass the real `caller_scope_path` down; delete
  `call_scope_path` and use the string already in scope. Add tests for
  an `input bind`, a `toggle bind`, a `button on tap`, and a scoped
  derivation inside `children`. Add a regression test that types into
  example 06's three fields and submits successfully.
* **Done when:** `./plain run examples/06-form-validation.plain` accepts
  typing in Name/Email/Password and the submit flow navigates on valid
  input; a slot button mutates page state.

### P0-02 · Component default parameter values
`P0` · `M` · **⚠ bug** · `parser.py:129 _params`, `scene.py:214`

* **Now:** defaults are stripped at parse time; omitted args are unbound.
* **Do:** store params as `(name, default_expr | None)`. At call time bind
  positional args, then named props, then evaluate defaults in the caller
  environment; error plainly on missing required args, extra positional
  args, and duplicate binding. Type-check defaults in the checker.
* **Done when:** `component Avatar(person, size = 40)` used as
  `Avatar "Ada"` renders a 40-point avatar; `Avatar "Ada" 56` renders 56;
  missing required args produce a plain sentence with a Try line.

### P0-03 · Never silently ignore syntax
`P0` · `M` · **⚠ bug** · `scene.py:134`, `parser.py:179–187`, `render.py:113`

* **Now:** `transition`, `theme`, `use`, and every unsupported event name
  parse fine and do nothing.
* **Do:** decide implement-vs-reject per construct and make the outcome
  explicit:
  * `transition …` → keep parsing, but the renderer either implements it
    (P2 animation) or raises `UnsupportedYet("page transitions", "Stage 3")`.
  * `theme:` / `use:` → implement (FE-13/FE-12) or reject now.
  * event names → dispatch table of supported events; the checker warns
    "`on swipe-start` is valid PL but this prototype doesn't handle it yet"
    (warning, not error) and the runtime raises `UnsupportedYet` if fired.
* **Done when:** no valid construct can be silently inert; a grep of the
  codebase for `pass  #` and `continue` yields no "declared but ignored"
  paths.

### P0-04 · Stop leaking secrets in paint and preview
`P0` · `S` · **⚠ bug** · `paint_svg.py:131`, `server.py:72`

* **Do:** paint `input secret` as bullets of the same width (never the
  value); redact any state name declared `secret` or bound from a
  `secret` input in `_state_dump`; carry the `secret` bit into the export
  path. Add a test that the password string never appears in
  `App.svg()` or `_state_dump()`.
* **Done when:** typing into a `secret` field leaves no plaintext in the
  SVG, the state panel, or server logs.

### P0-05 · Make `fmt` trustworthy on the corpus
`P0` · `M` · **⚠ bug** · `fmt.py`, `tests/test_stage1.py:290`

* **Now:** `fmt --check` fails 02/06/07. Top-level comments are indented
  into the preceding block; continuation lines are reindented to one
  extra level regardless of author intent.
* **Do:** define the canonical continuation and comment rules in Doc 03
  §2; implement them; run `fmt --check` in CI and Makefile; add a test
  asserting `format_source(file) == file` for all 9 examples (or format
  the examples once and commit that, updating the spec).
* **Done when:** `./plain fmt --check examples/*.plain` exits 0; running
  `fmt --write` twice is a no-op; comment blocks stay with the declaration
  they describe.

### P0-06 · Make action statements dispatch honestly
`P0` · `M` · **⚠ bug** · `expr.py:517`, `runtime.py:303`

* **Now:** `post` never reaches its `UnsupportedYet` branch; `then` is
  captured by the list-add regex; errors are confusing and can leave
  partial mutations (chat clears `draft`, then explodes on `post`).
* **Do:** classify action statements in the parser or a single dispatch
  function, before evaluating: network calls, list ops, `go`, `return`,
  `refresh`, `show toast`, `then` chains, action calls. Each unimplemented
  construct raises `UnsupportedYet` with the stage and the exact line;
  nothing mutates before the check.
* **Done when:** `to send:` in example 04 raises a plain "network calls
  are Stage 3" message and leaves `draft` untouched; example 06's
  `submit` behaves the same.

### P0-07 · Fix/delete dead code paths that hide bugs
`P0` · `S` · **⚠ bug** · `layout.py:316`, `layout.py:372`, `paint_svg.py:71`,
`parser.py:236`, `parser.py:262`

* `_stretch_growers` is a `pass` no-op that is called as if it does work.
* `_place` contains `if "grow" in ch.flags and ch.kind in (…): pass`.
* `paint_svg` has `shadow = ' filter="url(#)" ' if False else ""`.
* `otherwise if` builds an unused `wrapper` `IfNode`.
* `_try_decl` constructs a throwaway `T.Tok(T.OP, ".")` inside a list
  comparison.
* **Do:** remove or implement each; add a lint rule/test that fails on
  unreachable branches in core modules. Dead code here is not cosmetic —
  it is where the next bug hides.
* **Done when:** `grep -rn "if False\|pass  #\|wrapper =" src/plainlang`
  returns nothing unexplained.

### P0-08 · Checker must visit action bodies
`P0` · `M` · **⚠ bug** · `checker.py:35–57`

* **Now:** `_check_block` is called on owner bodies but action bodies are
  never traversed, so invalid nodes/props/actions inside `to …:` pass
  `plain check` and fail at tap time.
* **Do:** recurse into `ActionDecl.body` with `visual=False` and an
  action-aware checker (statement grammar, defined names, arity). Keep
  the "lenient toward future syntax" rule: valid-but-unimplemented is a
  warning or `UnsupportedYet`, never a false error.
* **Done when:** an unknown node inside an action is reported by
  `./plain check`, and all 9 examples stay OK.

### P0-09 · Error spans and carets
`P0` · `M` · **⚠ bug/gap** · `errors.py`, `tokens.py`, `ast_nodes.py`

* **Now:** `PlainError` has `line_no` and `line_text` only; Doc 03 §10's
  canonical error shows a caret under the offending token.
* **Do:** give every token a start/end column; carry spans on `Node`,
  `Prop`, `Event`, `StateDecl`, `ActionDecl`, statements; render
  `^^^^^^^^` under the span; keep a plain `Try:` line. Use spans in the
  preview error page and the checker. Add snapshot tests for 10
  representative errors.
* **Done when:** every error printed by `plain check` points at the
  exact token, not just the line.

### P0-10 · Fix the preview session model
`P0` · `M` · **⚠ bug** · `server.py:102–147`

* **Now:** one module-level `session["app"]` shared by all clients; every
  request re-parses and mutates the same runtime; `/sync` hardcodes
  `load("desktop")` regardless of the selected viewport; no lock; errors
  return HTTP 200.
* **Do:** per-client session (signed cookie or connection id) with a
  lock or a single-threaded queue; pass the current `size` into `/sync`;
  return proper status codes while keeping the friendly HTML; keep
  `0.0.0.0` binding for proxied previews.
* **Done when:** two browser tabs can hold independent state; typing in
  a phone-size preview submits at phone size; concurrent requests cannot
  corrupt a scope.

### P0-11 · Correct the documentation drift
`P0` · `S` · **⚠ bug** · `README.md:74,86`, `docs/06:40,49`, `docs/06` TOC

* `README` says "22 tests" in the Try-it block while the line above says
  34; `docs/06` repeats 22 and "~3.1k LOC"; §5's TOC says G-1…G-8 while
  the body lists G-1…G-10; "Still deferred" omits the newly discovered
  gaps (slot scopes, defaults, silent gestures).
* **Do:** make the numbers generated or checked; add a docs test that
  greps counts from the code; update the module map with actual LOC and
  the honest deferred list.
* **Done when:** a reader can trust every number in the README.

### P0-12 · CI must be able to fail
`P0` · `S` · **⚠ bug** · `cli.py:108`, `.github/workflows/ci.yml`

* `cmd_validate` always returns 0. CI does not run `fmt --check`, does
  not assert the 9 examples' node/SVG counts, and does not test the
  server. The Rust job is fine.
* **Do:** `validate` returns nonzero if any example fails to render or
  drops below its recorded node count; add `fmt --check`, an example
  golden check, and a server smoke test to CI.
* **Done when:** breaking 00-hello-world turns CI red for the right
  reason.

---

## 3. Language front end (lexer · parser · AST)

- [ ] **FE-01 · Token spans & source map** — `P1 · M` · `tokens.py`.
      Add `line`, `col_start`, `col_end`, `offset` to `Tok`; thread spans
      through `Line` and AST nodes; use for P0-09, LSP, and Looking Glass
      click-to-source.
- [ ] **FE-02 · Grammar conformance suite** — `P1 · M` · `tests/`.
      One test per Doc 03 clause and per G-1…G-10 amendment: valid form
      parses, invalid form produces the documented sentence. Table-driven.
- [ ] **FE-03 · Variant kinds** — `P1 · M` · `parser.py:154`.
      Doc 03 §7.5 `kind Payment: card number, expiry | cash | …` currently
      parses as one field line. Parse variants, model them in `KindDecl`,
      construct and match them; checker enforces exhaustiveness.
- [ ] **FE-04 · Typed declarations** — `P1 · M`.
      `name: Type = value`, `kind` field types, `component` param types,
      action param types. Keep types optional; preserve defaults.
- [ ] **FE-05 · Component/default/prop binding rules** — `P1 · M`.
      Specify and implement: positional args, named props, `children`,
      defaults, extra args, shadowing, and when a prop name collides with
      a component param.
- [ ] **FE-06 · `together:` blocks** — `P1 · M`.
      Parse and execute structured concurrency (RT-13); reject today
      with a precise message if not implemented in the same change.
- [ ] **FE-07 · `whenever` and lifecycle** — `P1 · M`.
      `whenever query changes:` and `when page appears/leaves:`; parse into
      a distinct `EffectDecl` (today they fall through to `RawStmt`).
- [ ] **FE-08 · `every 30s:` timers** — `P1 · S`. Parse and route to the
      runtime timer resource; never a hidden `setInterval`.
- [ ] **FE-09 · `refresh x` statement** — `P1 · S`. Resolve G-10's open
      spelling once, implement it, record it in Doc 03, keep
      `ready-or` as the only unwrap form.
- [ ] **FE-10 · Page routes with params** — `P1 · M`. Parse and retain
      `/photos/{photo.id}` as a route pattern (not just a display string);
      validate duplicate/ambiguous routes; feed the router (RT-23).
- [ ] **FE-11 · Strings** — `P1 · S`. Escapes (`\"`, `\n`, `\{`), nested
      braces in interpolation, multi-line strings if the spec adopts them.
      Today `\"` is not handled; an unterminated quote silently eats the
      rest of the line.
- [ ] **FE-12 · `use` and module AST** — `P1 · M`. `use "openly:…"` and
      `use "./x.plain"` become a real `UseDecl`; local module loading,
      cycles, namespacing, and `needs` union.
- [ ] **FE-13 · `theme` AST** — `P1 · M`. Typed token declarations and
      variants (`theme dark:`), resolved at compile time; missing token is
      an error (Doc 03 §4.3).
- [ ] **FE-14 · Statement/expression boundary** — `P1 · S`. `x = post …`,
      bare calls, `return value`, `go to` in expressions vs statements;
      one classifier, shared by parser/runtime/checker.
- [ ] **FE-15 · Indentation & continuation policy** — `P1 · S`. Document
      and test: 2-space levels, tabs rejected, continuation lines, prop
      continuation vs child node, comments inside/after blocks. Fix P0-05
      with the same rules.
- [ ] **FE-16 · Unicode & identifiers** — `P2 · M`. Decide whether
      Amharic/Ge'ez identifiers are allowed (the platform's audience says
      yes); tokenizer, formatter, error messages, and LSP must agree.
      Hyphens stay word-joining; subtraction keeps spaces.
- [ ] **FE-17 · Parser error recovery** — `P2 · L`. Collect multiple
      diagnostics per file instead of raising on the first; keep the
      plain-sentence guarantee. Needed for LSP and for large files.
- [ ] **FE-18 · AST round-trip** — `P2 · M`. `parse → format → parse`
      must be stable for every corpus file; formatter and parser share
      the same source model.
- [ ] **FE-19 · Performance** — `P2 · S`. Parse+check 9 examples in one
      pass; target < 5 ms for the corpus on this sandbox (currently
      ~0.5 s including process start); add a microbenchmark.

---

## 4. Expressions & type system

- [ ] **EX-01 · Unit-carrying values** — `P1 · L` · `expr._number`.
      Introduce `Duration` (`300ms`, `2s`), `Angle` (`40deg`), `Percent`
      (`75%`), `Length` (points), and make arithmetic unit-aware:
      `300ms + 12` must be an error, `2s + 300ms` must work, `50% + 10`
      must be an error unless the spec defines it. Replace the current
      "strip suffix, return a float" behavior (P0 finding).
- [ ] **EX-02 · Money** — `P1 · M`. Decimal-correct `Money`, arithmetic
      with `Number`, formatting (`$334`, no float drift), and boundary
      parsing from JSON. `as money` must use it, not `float()`.
- [ ] **EX-03 · Time** — `P1 · M`. `Moment`, `Duration`, `Calendar-day`;
      `now`, arithmetic, comparison, `as date/time`, timezone policy.
      Until then, `as date` must not pretend to work.
- [ ] **EX-04 · Maybe / nothing** — `P1 · M`. One absence concept; make
      `exists`, `is nothing`, `x or default` total; field access on
      `nothing` should short-circuit or error plainly, never crash Python.
- [ ] **EX-05 · Result and `ok`/`failed`** — `P1 · M`. Constructors,
      matching (`when r: is ok v / is failed why`), propagation from
      actions, human-readable `Reason` values (`offline`, `denied`,
      `invalid field "email"`, `server 500`).
- [ ] **EX-06 · Type annotations & inference** — `P1 · L`. Structural
      types; infer component bodies; check annotations at boundaries;
      validate JSON against `kind` at resource boundaries (EX-01…05
      depend on this).
- [ ] **EX-07 · Exhaustive `when`** — `P1 · M`. For `Resource`,
      `Result`, `Maybe`, and variant kinds, the checker rejects a `when`
      missing a case, with the missing branch named in the message.
- [ ] **EX-08 · Comparison safety** — `P1 · S`. `>=` on `Text` vs
      `Number`, `contains` on a non-list, division by zero: all must be
      plain errors, not Python `TypeError`/silent `0`.
- [ ] **EX-09 · Operator set** — `P1 · S`. Decide and implement `%`, `in`,
      ranges, string concatenation, `**`; document precedence in one table
      (current precedence is implicit in `_Parser`).
- [ ] **EX-10 · Pipeline completeness** — `P1 · M`. Add `last`, `sum`,
      `min`, `max`, `join`, `map`, `unique`, `reversed`; keep `where`
      greedy (G-2) and terminal ops after filters. Every pipeline word
      gets a spec sentence + test.
- [ ] **EX-11 · Sort semantics** — `P1 · S`. `sorted by key reversed if c`
      works; define stability, missing keys, mixed types, case sensitivity.
- [ ] **EX-12 · Slicing bounds** — `P1 · S`. `from/take` with negatives,
      zero, past-end, non-integers; `clamped a to b`, `at-least n`.
- [ ] **EX-13 · Interpolation** — `P1 · M`. `{expr}` with formats
      (`{price as money}`), escaped braces, unknown names producing the
      standard error; no HTML/string-built UI ever (Doc 01 §5).
- [ ] **EX-14 · Builtin scope** — `P1 · S`. `width`, `height`, `narrow`
      are currently filled from a static viewport stack in `scene._env`;
      they must reflect the node's actual constraints (see LAY-01) or be
      documented as viewport facts. Also define which builtins exist in
      actions (where `width` is meaningless).
- [ ] **EX-15 · Standard functions** — `P2 · M`. `ceil/floor` exist only.
      Add the stdlib function surface (string, list, number, time) with
      consistent names and errors; no user-defined value functions until
      the spec decides.
- [ ] **EX-16 · Cycles & shadowing** — `P1 · S`. Detect `a is b; b is a`;
      define shadowing between params, state, shared, loop vars, and
      scoped derivations; test every pair.
- [ ] **EX-17 · Number lexing** — `P2 · S`. `-3`, `.5`, exponents,
      `1/2` vs division, thousands separators; `4/3` currently becomes a
      tuple `("ratio", 4, 3)` inside a "literal", which is a leaky model.
- [ ] **EX-18 · Display/formatting** — `P2 · S`. Stable `display()` for
      records, lists, booleans, nothing; no Python repr leakage.

---

## 5. Runtime · state · reactivity · persistence

- [ ] **RT-01 · Fine-grained dependency graph** — `P1 · L` · ADR-3.
      Replace recompute-on-read (`runtime.env_for`) with tracked signals:
      each derived/binding subscribes to the state it reads; writes mark
      exactly those subscribers dirty. Keep the observable semantics and
      `env_for` as the seam; add a test proving unrelated derivations do
      not recompute.
- [ ] **RT-02 · Incremental scene updates** — `P1 · L`. Bindings mutate
      scene nodes in place; no full rebuild per interaction. Today every
      tap calls `app.build()`. Target: O(changed nodes) per state write.
- [ ] **RT-03 · Keyed list identity** — `P1 · L`. `for` rows keep identity
      by item key, not index; removing/reordering preserves per-row state
      and drives `enter/exit`; fix the index-as-key bug class (Doc 04 F7).
- [ ] **RT-04 · Persist `shared` state** — `P1 · S`. `keep` only works
      inside page/component scopes; `keep cart` at file scope is parsed as
      a stray line. Add file-level keeps, persist under a reserved key,
      and test.
- [ ] **RT-05 · `keep` versioning/migration** — `P1 · M`. Store a schema
      version, migrate by shape on load, tolerate corrupt/partial JSON,
      write atomically (temp + rename), debounce writes, and never crash
      on a stale file.
- [ ] **RT-06 · Persistence semantics** — `P1 · S`. Decide what is kept
      (`keep` only), when (on write vs on interval), where (`.plain/<app>.json`),
      and how `reset` clears it. Test renames, removals, and page changes.
- [ ] **RT-07 · Action locals vs state** — `P1 · S`. The current rule
      ("`=` inside an action is local if the name is unknown elsewhere")
      is subtle; document it and test shadowing, mutation of records,
      and returning early.
- [ ] **RT-08 · Action calls & arity** — `P1 · S`. Parse args without
      regex, check arity/types at compile time, support defaults, and
      produce plain messages for unknown actions.
- [ ] **RT-09 · Event dispatch table** — `P1 · M`. One registry of
      supported events per node kind (`tap`, `change`, `submit`, `focus`,
      `hover`, `key`, `swipe-*`, `drag-*`, `pinch`, `scroll`,
      `double-tap`, `long-press`). Unsupported → checker warning +
      runtime `UnsupportedYet` (P0-03).
- [ ] **RT-10 · Event parameters** — `P1 · S`. `on change value:`,
      `on key key:`, gesture values with typed payloads; currently the
      param is bound only for `change`/`submit` paths.
- [ ] **RT-11 · `when page appears/leaves`** — `P1 · S`. Lifecycle in
      words (Doc 03 §6.1); no hooks, no cleanup zoo.
- [ ] **RT-12 · `whenever` effects** — `P1 · M`. Dependency-tracked,
      cancellable, never blocking the UI (EX-07/FE-07).
- [ ] **RT-13 · `together:` concurrency** — `P1 · M`. Run steps
      concurrently, join, cancel siblings on failure; no threads/locks
      exposed to authors.
- [ ] **RT-14 · Async I/O without coloring** — `P1 · L`. Resource and
      action I/O suspend the isolate fiber, not the UI; implement the
      scheduling skeleton even before real HTTP.
- [ ] **RT-15 · Timers** — `P1 · M`. `every 30s:` coalesced by the
      runtime; pause when the page is hidden; no hidden polling.
- [ ] **RT-16 · Deterministic replay** — `P2 · M`. Seeded clock/random,
      recorded events, replay for tests and time travel.
- [ ] **RT-17 · State transition log** — `P2 · M`. Every write logged for
      Looking Glass time travel; persistent structures for old snapshots.
- [ ] **RT-18 · Error boundary** — `P1 · M`. Isolate faults route to
      `page Fallback(error)`; never a white screen. Add a test that a
      runtime error on one page can be dismissed/retried.
- [ ] **RT-19 · Quotas & watchdog** — `P2 · M`. CPU/memory limits per
      program; kill runaway isolates without touching the compositor.
- [ ] **RT-20 · Hot reload in place** — `P1 · M`. Today the server
      re-parses per request and re-homes state by path. Production
      semantics: rewire bindings, preserve state by name/shape, update
      only changed nodes, keep focus/scroll. Match the oracle behavior
      first, then optimize.
- [ ] **RT-21 · Scope key stability** — `P1 · S`. Instance paths like
      `root/0#Card/slot/0` are fragile; define stable keys so state
      survives insertion/reordering and two instances of the same
      component do not collide.
- [ ] **RT-22 · Navigation stack** — `P1 · M`. Typed page params,
      duplicate-push policy, back stack depth, restoration across reload,
      and `go back` when the stack has one entry.
- [ ] **RT-23 · Deep links & URL routing** — `P1 · M`. `page X at "/people/{id}"`
      is currently display-only; the first page always wins. Implement a
      router, URL ↔ stack mapping, 404/fallback page, and browser
      back/forward in the preview.
- [ ] **RT-24 · Shared state details** — `P1 · M`. Declarations in pages
      vs file scope, writes from any component, read-after-write
      consistency, and interaction with `keep` (RT-04).

---

## 6. Resources, networking, async

- [ ] **NET-01 · Real HTTP resources** — `P1 · L`. Replace sidecar
      providers with `GET` via stdlib `http.client`/`urllib` behind a
      capability handle; JSON decode; content-type handling; timeouts.
      Keep sidecars as offline fixtures.
- [ ] **NET-02 · Cache** — `P1 · L`. Key by (capability, address, accept);
      dedupe concurrent fetches; stale-while-revalidate; ETag/If-None-Match;
      memory + disk bounds with eviction.
- [ ] **NET-03 · Retry & backoff** — `P1 · M`. Bounded exponential
      backoff; cancel on navigation; surface the final `Reason` plainly.
- [ ] **NET-04 · Offline queue & optimistic mutations** — `P1 · L`. Queue
      `post` while offline, replay on reconnect, reconcile responses;
      `on tap: posts add draft, sync` semantics.
- [ ] **NET-05 · `loading/ready/failed` lifecycle** — `P1 · M`. States are
      real values; `when` sees `loading` immediately; a failed fetch never
      masquerades as "no data source is connected in this prototype".
- [ ] **NET-06 · `refresh x` and `retry`** — `P1 · S`. Wire `retry refresh
      messages` (currently an inert prop) and the G-10 spelling.
- [ ] **NET-07 · Streaming `from live`** — `P1 · L`. SSE/WebSocket
      transport, reconnect, ordered append, backpressure; `loading` until
      the first frame; `stick-to-bottom` honored.
- [ ] **NET-08 · Request builder** — `P1 · M`. `post` with body, headers,
      method, query; Result return; no ambient credentials.
- [ ] **NET-09 · Boundary validation** — `P1 · M`. Validate JSON against
      the declared `kind`; a mismatch is a `failed` resource with a plain
      sentence naming the field, never a crash. Fixes TS's erased-types
      hole (Doc 04 F10).
- [ ] **NET-10 · Fixtures & tests** — `P1 · M`. Local HTTP server in
      tests, no external network in CI, sample mode for the preview.
- [ ] **NET-11 · Network inspector** — `P2 · M`. Looking Glass panel for
      each resource: state, cache age, retries, bytes, last error.
- [ ] **NET-12 · Auth as capability** — `P2 · M`. Token handles the program
      cannot leak to code it does not have; no cookies/CSRF.
- [ ] **NET-13 · Cancellation** — `P2 · M`. Navigating away or changing a
      query cancels in-flight work, with no unhandled errors.
- [ ] **NET-14 · Resource sharing** — `P2 · S`. `shared x from …` is one
      fetch across components; test both readers see the same state.

---

## 7. Scene graph, components, stdlib

- [ ] **UI-01 · Node coverage** — `P1 · L`. Implement the nodes already in
      `NODE_KINDS` but rejected by `SUPPORTED_NODES`: `link`, `slider`,
      `select`, `textarea`, `video`, `audio`, `canvas`, `model3d`,
      `light`, `camera`, `material`, `part`, plus `window`, `menu`,
      `tray` (desktop), `webview` (legacy, fenced). Each gets semantics,
      paint, layout, a11y, and tests.
- [ ] **UI-02 · `children` slot semantics** — `P1 · M`. Beyond P0-01:
      slot naming, multiple slots, default content, scope rules, and
      events inside slots.
- [ ] **UI-03 · Component recursion & depth** — `P1 · S`. Detect infinite
      components with a plain error; cap depth.
- [ ] **UI-04 · `when` matching** — `P1 · M`. Payload binding, nested
      patterns, `is ok`/`is failed`, `is nothing`, variant kinds; an
      unmatched subject is a checker error once exhaustiveness lands.
- [ ] **UI-05 · Conditional props/flags** — `P1 · S`. `strike if done`,
      `look a if c otherwise look b`, `width 3 if selected` are the one
      spelling (G-3); add the missing `otherwise <flag>` form if the spec
      allows it.
- [ ] **UI-06 · Scoped derivations** — `P1 · M`. `name is …` anywhere
      statements are (G-4); ordering, visibility, recomputation at
      dispatch (currently snapshotted into event extras), and shadowing.
- [ ] **UI-07 · Stdlib components** — `P1 · L`. Only `ErrorBox` ships.
      Add the Doc 01 §6.1 set as PL components over the same primitives:
      `Field`, `Card`, `Button` variants, `Dialog`, `Toast`, `Menu`,
      `Tabs`, `DataTable`, `EmptyState`, `ErrorState`, `Avatar`,
      `Spinner`, `List`, `Chart` basics.
- [ ] **UI-08 · Stdlib needs `use`-free prelude** — `P1 · S`. Stdlib
      components resolve without imports; user modules come from `use`.
- [ ] **UI-09 · Prop coverage** — `P1 · L`. Every visual prop either
      renders or is rejected: `shadow`, `ring`, `border`, `gradient`,
      `opacity`, `rotate`, `scale`, `clip`, `z`, `align-self`, `lines`,
      `ellipsis`, `fit`, `level`.
- [ ] **UI-10 · Source spans on scene nodes** — `✅ mostly`; keep
      `source_line`, add columns and the originating AST id for
      click-to-source.
- [ ] **UI-11 · Retained identity for transitions** — `P1 · M`. `id "photo-{id}"`
      is parsed but unused; retain geometry across page swaps (Doc 02 §5).
- [ ] **UI-12 · Slot event extras** — `P1 · S`. Stop snapshotting derived
      values into `extra` (they can go stale); keep only loop vars/params
      and recompute the rest at dispatch.
- [ ] **UI-13 · Component call validation** — `P1 · S`. Unknown named
      args, duplicate args, wrong types, missing required args — all in
      the checker, all with Did-you-mean.
- [ ] **UI-14 · Nesting limits & layout of unknown nodes** — `P2 · S`.
      Unknown leaf measured 0×0 silently today; make it a checker error
      or a visible placeholder in strict mode.
- [ ] **UI-15 · Scene serialization** — `P2 · M`. Stable JSON dump of the
      scene for tests, Looking Glass, AI tooling, and golden files.
- [ ] **UI-16 · Scene diff API** — `P2 · M`. Compute minimal mutations
      between two scenes; the basis for RT-02 and transitions.

---

## 8. Layout — Flow

- [ ] **LAY-01 · Real constraints down** — `P1 · L` · Doc 02 §2.
      `Constraints` has only `max_w/max_h`. Add min+max on both axes,
      pass actual parent constraints (including row shares and grid
      cells) into children, and make `width`/`height`/`narrow` in PL
      reflect **this node's** space. Today `scene._sizes` uses a static
      viewport stack, so "container queries" are viewport queries with a
      different name (Doc 00 A10 claim not yet true).
- [ ] **LAY-02 · `grow [n]` weights** — `P1 · M`. Currently equal share;
      support weights, minimums, and grow in both axes.
- [ ] **LAY-03 · `spread around`** — `P1 · S`. Missing; add it and test
      against `between/center/end/start`.
- [ ] **LAY-04 · Sizing algebra** — `P1 · M`. `fill|fit|fixed`, `%`,
      `max`, `min`, both axes; percent of what (parent content box);
      nested clamps; predictable precedence.
- [ ] **LAY-05 · Text in Flow** — `P1 · L`. Baseline alignment in rows,
      line-height, `lines max 2 ellipsis`, long-word breaking, intrinsic
      sizing from the real text engine (H-06), and a deterministic
      metric fallback for goldens.
- [ ] **LAY-06 · Grid completeness** — `P1 · M`. `columns auto`,
      responsive `columns is …` from LAY-01, row heights, sparse cells,
      header rows spanning columns.
- [ ] **LAY-07 · Stack/absolute** — `P1 · M`. `at x y`, `pin edges`,
      z-order by source order, contained absolute positioning only
      (Doc 02 §2.4). The parser accepts `at`; layout ignores it.
- [ ] **LAY-08 · Scroll** — `P1 · L`. Viewport, content size, scroll
      position, `stick-to-bottom`, culling (offscreen items cost nothing),
      nested scrolling, and compositor-only scrolling.
- [ ] **LAY-09 · Table** — `P1 · M`. Column sizing/alignment, header
      semantics, sorting affordances, virtualization, and responsive
      collapse.
- [ ] **LAY-10 · Logical axes / RTL / vertical** — `P2 · L`. Replace
      physical left/right with start/end; `direction` inherited from
      locale; vertical writing for CJK; bidi at the text layer. This is a
      core "plainness" claim (Doc 02 §2.6) and must not stay aspirational.
- [ ] **LAY-11 · Invalidation** — `P2 · L`. Only dirty subtrees
      re-measure; parallel layout of independent subtrees; constraint
      caches.
- [ ] **LAY-12 · Hit targets** — `P1 · S`. Enforce 44pt for interactive
      nodes (button enforces height today; toggle is 52×30), warn in the
      engine and Looking Glass, never silently shrink.
- [ ] **LAY-13 · Layout test suite** — `P1 · M`. Golden cases modelled on
      Flexbox's own tests plus PL-specific properties: no overlap, inside
      parent, padding respected, deterministic across runs.
- [ ] **LAY-14 · Percent & unit integration** — `P1 · S`. LAY-04 must use
      EX-01's typed lengths, not string suffix parsing.

---

## 9. Paint, text, media, animation

- [ ] **H-01 · SVG paint completeness** — `P1 · L`. Shadows, borders,
      gradients, rings, opacity, transforms, clipping, images (real
      files/data URIs), video posters, canvas placeholders.
- [ ] **H-02 · Hit regions** — `P1 · S`. Every interactive node gets a
      tap region (not only box/text/button/toggle/image); inputs are not
      currently wrapped, and overlapping children can steal taps.
- [ ] **H-03 · Animation engine** — `P1 · L`. Springs by default,
      interruptible, `animate spring gentle|snappy|bouncy`, enter/exit,
      `stagger`, frame budgeting, reduced-motion enforcement (Doc 02 §5).
      Everything here is currently parsed and ignored.
- [ ] **H-04 · Page transitions** — `P1 · L`. `transition slide spring snappy`,
      shared-element `id` (UI-11), outgoing geometry retention,
      interruption by gesture.
- [ ] **H-05 · Gesture recognizers** — `P1 · L`. tap, long-press, swipe
      directions, drag-x/y, pinch, scroll, double-tap, hover, focus, key.
      Map gestures to intents on semantic nodes so a11y/keyboard
      equivalents come free (Doc 04 F5).
- [ ] **H-06 · Text engine** — `P2 · XL`. HarfBuzz shaping, ICU-class
      bidi (UAX #9) and line breaking (UAX #14), Emoji, selection/caret,
      IME composition, undo, spellcheck hooks. Amharic/Ge'ez, Arabic,
      CJK test suites are acceptance criteria (Doc 05 Stage 3).
- [ ] **H-07 · Fonts** — `P2 · L`. Bundling/subsetting by used glyphs,
      variable fonts, fallback chains, identical metrics across OSes.
- [ ] **H-08 · Images/media** — `P2 · L`. Off-thread decode, texture
      atlas, `fit contain/cover`, aspect, memory-pressure eviction;
      video/audio playback and controls.
- [ ] **H-09 · 3D** — `P2 · XL`. `scene3d` via wgpu + glTF; camera,
      light, material, part; 2D overlays as siblings; gestures drive
      camera/model. Today `scene3d` is a labeled placeholder.
- [ ] **H-10 · Paint backends** — `P2 · XL`. Vello-class GPU compute on
      wgpu with a tiny-skia-class CPU fallback behind one display-list
      interface; AA, wide gamut/HDR (ADR-5).
- [ ] **H-11 · Compositor** — `P2 · XL`. Layers, dirty regions,
      occlusion/viewport culling, idle = no frames, vsync budget,
      compositor-only scroll/gesture transforms.
- [ ] **H-12 · Shaders** — `P3 · L`. Sandboxed WGSL fragment hooks with
      bounded loops and `needs gpu-compute`.
- [ ] **H-13 · Paint determinism** — `P1 · S`. Same scene → byte-identical
      SVG; golden files for all 9 examples at 4 viewport sizes; pixel
      tolerance defined for the GPU path.
- [ ] **H-14 · Unsupported style words** — `P1 · S`. Any prop that paint
      cannot honor must be reported (strict mode) rather than ignored —
      the visual equivalent of P0-03.

---

## 10. Accessibility

- [ ] **A11Y-01 · Complete role mapping** — `P1 · M`. Every implemented
      node kind maps to a role; headings use `level` (not only size ≥ 24);
      lists come from `for`; tables/grids expose row/column semantics;
      dialogs get focus traps.
- [ ] **A11Y-02 · Labels** — `P1 · S`. Buttons from text, inputs from
      label/placeholder, images from alt, icon-only buttons warn;
      `label "…"` refines, never replaces the derived basics.
- [ ] **A11Y-03 · Keyboard operation** — `P1 · M`. Tab order follows
      scene order, Enter/Space activation, visible focus ring,
      focus restoration after navigation/dialog, shortcut declarations.
- [ ] **A11Y-04 · Screen-reader bridge** — `P2 · XL`. VoiceOver (iOS/macOS),
      TalkBack (Android), AT-SPI (Linux), UIA (Windows); announce errors,
      toasts, and live-region updates.
- [ ] **A11Y-05 · Contrast checker** — `P1 · M`. Evaluate theme token
      pairs at load; warn in plain words ("`muted` on `paper` is 3.1:1 —
      needs 4.5:1"); flag in Looking Glass; never silently pass.
- [ ] **A11Y-06 · 44pt enforcement** — `P1 · S`. Warn + flag when a style
      shrinks an interactive target (wired to LAY-12).
- [ ] **A11Y-07 · Reduced motion** — `P1 · S`. Read the OS preference and
      enforce springs→fades in the engine, not per app.
- [ ] **A11Y-08 · Decoration control** — `P1 · S`. `hide from reader`,
      decorative images, and a rule that hiding never removes focusable
      semantics silently.
- [ ] **A11Y-09 · Live regions** — `P1 · M`. Resources with `announce`,
      form errors, toasts; dedupe repeated announcements.
- [ ] **A11Y-10 · A11y tree sync** — `P1 · M`. The tree is derived from
      the scene and updated by the same bindings; focus and selection
      survive property updates (a reason retained scene graph beats pure
      immediate mode).
- [ ] **A11Y-11 · CLI/JSON output** — `P1 · S`. `plain a11y --json` for
      tooling and tests; keep the human tree.
- [ ] **A11Y-12 · Tests** — `P1 · M`. Automated tree assertions for all
      examples; scripted VoiceOver/TalkBack walkthroughs; keep the
      grep test proving no a11y words exist in source.
- [ ] **A11Y-13 · Forms** — `P1 · M`. `invalid`, described-by, error
      announcements, label association for the `Field` stdlib component.
- [ ] **A11Y-14 · A11y of the preview** — `P2 · S`. The Looking Glass
      panels and preview chrome themselves pass basic keyboard/contrast
      checks.

---

## 11. Dev server, preview, Looking Glass

- [ ] **SRV-01 · Live reload push** — `P1 · M`. Watch the file, rebuild,
      push via SSE/WebSocket; no manual reload; preserve state and scroll.
- [ ] **SRV-02 · Session isolation** — `P1 · M`. Per-client state, lock
      or queue around the runtime, no module-level app (P0-10).
- [ ] **SRV-03 · URL routing** — `P1 · M`. Serve each `page … at "…"`
      route; deep links; browser back/forward; `/` maps to the first page
      only as a fallback.
- [ ] **SRV-04 · Input fidelity** — `P1 · M`. `change` vs `submit` vs
      blur, password/email types, IME, autocomplete, focus retention;
      no GET form that submits on every keystroke path.
- [ ] **SRV-05 · `/sync` correctness** — `P1 · S`. Current viewport, race
      handling, 204/4xx semantics, CSRF/origin check for the preview.
- [ ] **SRV-06 · Error page with carets** — `P1 · S`. Use P0-09 spans;
      keep "your program is fine" for `UnsupportedYet`; never a stack
      trace in the page.
- [ ] **SRV-07 · Scene inspector** — `P2 · L`. Click a pixel → see the PL
      line; hover highlights; source map from spans.
- [ ] **SRV-08 · Profiler** — `P2 · L`. Per-frame layout/paint budget,
      "why did this repaint?" answered from the dependency graph.
- [ ] **SRV-09 · Time travel** — `P2 · L`. Scrub state transitions,
      replay, restore.
- [ ] **SRV-10 · Resource panel** — `P2 · M`. Cache/state/retry/bytes for
      every `from` resource (NET-11).
- [ ] **SRV-11 · Device presets & QR** — `P2 · M`. Keep 4 sizes; add
      `plain run --on phone` with QR and LAN address.
- [ ] **SRV-12 · Security headers** — `P1 · S`. CSP, frame-ancestors
      (must still allow the Arena preview proxy), no MIME sniffing,
      no state mutation from foreign origins.
- [ ] **SRV-13 · Server tests** — `P1 · M`. Integration tests for GET,
      tap, field, reset, sync, errors, two concurrent clients.
- [ ] **SRV-14 · Golden screenshots** — `P2 · M`. 9 examples × 4 sizes,
      compared on CI with a tolerance for font differences.

---

## 12. CLI, packaging, tooling

- [ ] **CLI-01 · `plain test`** — `P1 · L`. Run `check "name": …` blocks
      in a program, scene snapshots, and interaction simulation; no
      test-runner ecosystem (Doc 01 §6.1).
- [ ] **CLI-02 · `plain fmt` completion** — `P1 · M`. Stdin, `--check`,
      `--diff`, `--write`, safe refusal on parse errors (P0-05).
- [ ] **CLI-03 · `plain run` flags** — `P1 · S`. `--open`, `--host`,
      `--watch/--no-watch`, `--on phone`, `--size`.
- [ ] **CLI-04 · `plain render`** — `P1 · S`. `--page`, `--size`,
      multiple outputs, PNG/PDF later, deterministic SVG.
- [ ] **CLI-05 · `plain check`** — `P1 · S`. `--json`, `--quiet`,
      `--strict` (warnings as errors), directories/globs, stdin.
- [ ] **CLI-06 · `plain validate`** — `P1 · S`. Fail on regressions,
      emit Markdown/JSON, record baselines, compare to previous run.
- [ ] **CLI-07 · Packaging** — `P1 · M`. `pyproject.toml`, console script
      `plain`, `pipx`/`uv` install, `python -m plainlang` without
      `PYTHONPATH`, Python 3.11–3.13 support, no runtime deps.
- [ ] **CLI-08 · Cross-platform launcher** — `P1 · S`. Windows `.cmd`,
      `#!/usr/bin/env python3` portability, path handling, no reliance on
      CWD.
- [ ] **CLI-09 · `plain add` / `plain publish`** — `P3 · L`. Openly
      registry verbs (ECO-07…09).
- [ ] **CLI-10 · LSP** — `P2 · L`. Diagnostics, completion, hover,
      go-to-definition, rename, format-on-save; shares the real compiler.
- [ ] **CLI-11 · Editor support** — `P2 · M`. VS Code grammar/snippets,
      tree-sitter grammar, syntax highlighting for `<file>.plain`.
- [ ] **CLI-12 · `plain init` / templates** — `P2 · S`. One-command hello
      world; aligns with the < 15-minute metric (Doc 00 §0.2.1).
- [ ] **CLI-13 · Version & help** — `P2 · S`. `plain --version`, real
      help text, exit-code table.
- [ ] **CLI-14 · Error UX** — `P2 · M`. Colors, code frames with carets,
      docs links, "did you mean", no tracebacks for user errors.

---

## 13. Checker & formatter

- [ ] **CHK-01 · Action-body checking** — `P0-08`.
- [ ] **CHK-02 · Name resolution** — `P1 · L`. Resolve every expression
      name at compile time: params, state, shared, derived, loop vars,
      locals, builtins, page-link literals. Undefined → plain error with
      suggestions. Today it is runtime-only.
- [ ] **CHK-03 · Type checking** — `P1 · XL`. Inference + annotations
      (EX-06); prop value types (`corners "big"` is the spec's example
      error); component/action arity; resource boundary types.
- [ ] **CHK-04 · Exhaustiveness** — `P1 · M`. `when` over Resource,
      Result, Maybe, variant kinds (EX-07).
- [ ] **CHK-05 · Property vocabulary per kind** — `P1 · M`. Today only 13
      kinds are checked; future nodes are unchecked. Define the matrix
      in one table shared by parser/checker/docs.
- [ ] **CHK-06 · Look/theme/token resolution** — `P1 · M`. Missing look
      is checked; missing theme token is not (themes are ignored).
- [ ] **CHK-07 · Duplicates & collisions** — `P1 · S`. Duplicate kinds,
      components, pages, looks, shared names; duplicate page routes;
      component names colliding with built-in node kinds.
- [ ] **CHK-08 · Capability coverage** — `P1 · S`. `from "https://…"`
      without `needs network host`; a module's needs union; warn before
      run, never at first fetch.
- [ ] **CHK-09 · Warnings vs errors** — `P1 · M`. A warning channel with
      codes; valid-but-unimplemented syntax warns; unknown syntax errors.
      `--strict` promotes warnings.
- [ ] **CHK-10 · Multi-error recovery** — `P2 · L`. Report all
      independent errors in a file, with spans (FE-17).
- [ ] **CHK-11 · Message quality** — `P1 · S`. Every diagnostic has what,
      where, why, Try; snapshot tests for wording; no Python exception
      text ever reaches a user.
- [ ] **CHK-12 · Formatter v2** — `P1 · M`. Canonical spacing, comma and
      prop ordering policy, line wrapping for long node lines,
      continuation rules, comment attachment, idempotence, corpus
      conformance (P0-05).
- [ ] **CHK-13 · Formatter safety** — `P1 · S`. Refuse to write when the
      file does not parse; `--check` in CI; never reorder props in a way
      that changes conditional meaning.

---

## 14. Security & capabilities

- [ ] **SEC-01 · Parse `needs` properly** — `P1 · M`. Structured
      capabilities (`network api.example.com`, `storage`, `camera`,
      `clipboard`, `notifications`, `gpu-compute`, `native lib`), not a
      word list; display verbatim before first run.
- [ ] **SEC-02 · Enforcement** — `P1 · L`. Default deny. No network/fs
      call without a handle; deny produces `failed denied` a program can
      match, plus a plain UI explanation.
- [ ] **SEC-03 · Unforgeable handles** — `P1 · L`. Capabilities are values
      injected by the runtime; stdlib signatures require the handle, so
      ambient authority is unrepresentable (ADR-7).
- [ ] **SEC-04 · Grant/revoke UX** — `P2 · M`. Per-capability, revocable,
      narrowable (one host, one picked folder); the preview shows what
      would be asked.
- [ ] **SEC-05 · Sandbox** — `P2 · XL`. Isolate per program, bytecode
      verifier, quotas, watchdog, native modules out-of-process.
- [ ] **SEC-06 · Injection audit** — `P1 · S`. Every sink traced: SVG
      text escapes, HTML preview escapes, state dump escapes, no
      string-built UI, no `innerHTML`-equivalent anywhere.
- [ ] **SEC-07 · Preview hardening** — `P1 · S`. Origin/CSRF on `/sync`,
      headers, no arbitrary file reads, secrets redacted (P0-04).
- [ ] **SEC-08 · Content trust** — `P2 · L`. Signed programs/modules,
      hash pinning, TOFU made visible, no install scripts.
- [ ] **SEC-09 · Crypto stdlib** — `P3 · M`. Hashes, signatures, secure
      random, OS keychain storage.
- [ ] **SEC-10 · Threat model doc** — `P2 · M`. Assets, attackers,
      mitigations, non-goals; audit checklist for Stage 5.

---

## 15. Rust production port (ADR-1)

> Rule from Doc 06 §8: no semantic may diverge silently; each slice ships
> with tests translated from `tests/test_stage1.py`; when they disagree,
> the oracle (and before it, the examples) wins until a spec amendment.

- [ ] **RS-01 · Slice 3 — expressions** — `P1 · L`. Port `expr.py`:
      tokenizer-driven parser, evaluation, pipelines, interpolation,
      records, errors. Differential tests against Python on a corpus of
      expressions.
- [ ] **RS-02 · Slice 3 — runtime** — `P1 · L`. State/derived/actions/
      `keep`/scopes/navigation; the same observable behavior including
      hot reload and state preservation.
- [ ] **RS-03 · Slice 4 — scene** — `P2 · L`. Scene builder, component
      expansion, slots, looks, `when`, source spans, stable ids.
- [ ] **RS-04 · Slice 4 — Flow layout** — `P2 · L`. Port the layout
      protocol and the golden layout tests; byte-identical geometry.
- [ ] **RS-05 · Slice 4 — a11y** — `P2 · M`. Same derived tree as the
      oracle; snapshot parity.
- [ ] **RS-06 · Slice 5 — Clear paint** — `P2 · XL`. wgpu/Vello backend;
      SVG writer first for parity; CPU fallback; display lists; fonts
      (HarfBuzz); native window; the < 500k LOC budget tracked from day
      one.
- [ ] **RS-07 · CLI parity** — `P2 · M`. `plain-rs run/render/a11y/fmt/
      validate` matching the oracle's flags and messages.
- [ ] **RS-08 · Error parity** — `P1 · S`. Shared substring assertions
      for every diagnostic; a generated table of (input → exact output).
- [ ] **RS-09 · Differential harness** — `P1 · M`. Run both
      implementations over the examples and a fuzz corpus; diff ASTs,
      errors, scene JSON, and SVG; fail on any difference.
- [ ] **RS-10 · Quality gates** — `P2 · S`. `cargo fmt --check`,
      `clippy -D warnings`, MSRV, Cargo.lock committed once deps exist.
- [ ] **RS-11 · Cross-platform CI** — `P2 · M`. Linux/macOS/Windows
      matrix; wasm32 build check; caching.
- [ ] **RS-12 · Fuzzing** — `P2 · M`. `cargo-fuzz` targets for
      tokens/parser/expr; no panics on arbitrary input.
- [ ] **RS-13 · Benchmarks** — `P2 · M`. criterion benches for parse,
      scene, layout, paint; budgets in CI.
- [ ] **RS-14 · Crates & docs** — `P3 · S`. Publish `plainlang`, docs.rs,
      README for engine contributors.

---

## 16. Tests, quality, CI

- [ ] **TST-01 · Split the test monolith** — `P1 · S`. `test_stage1.py`
      (382 lines, everything) → `test_tokens.py`, `test_parser.py`,
      `test_expr.py`, `test_runtime.py`, `test_scene.py`,
      `test_layout.py`, `test_a11y.py`, `test_server.py`,
      `test_cli.py`, `test_corpus.py`.
- [ ] **TST-02 · Golden SVG snapshots** — `P1 · M`. All examples × sizes;
      deterministic bytes; update workflow documented.
- [ ] **TST-03 · Layout property tests** — `P1 · M`. No overlap, inside
      parent, padding/gap invariants, deterministic output, fuzzed trees.
- [ ] **TST-04 · Runtime semantics tests** — `P1 · M`. One test per
      G-1…G-10; state/derived/action/keep/hot-reload; scoped derivations;
      component defaults; slot interaction.
- [ ] **TST-05 · Fuzz the front end** — `P2 · M`. Hypothesis (dev-only,
      not a runtime dep) for tokens/parser/expr: never crash, never hang,
      errors always plain.
- [ ] **TST-06 · Server tests** — `P1 · M`. HTTP integration, two
      clients, sync, reset, error page, hot reload with state.
- [ ] **TST-07 · A11y tests** — `P1 · M`. Snapshot trees, keyboard
      scripts, no-a11y-words grep.
- [ ] **TST-08 · Performance tests** — `P2 · M`. Build ms/node count/SVG
      bytes/memory with thresholds; fail on regressions.
- [ ] **TST-09 · Coverage** — `P2 · S`. `coverage.py`, threshold (start
      85% core modules), published artifact.
- [ ] **TST-10 · Lint/type** — `P2 · M`. Ruff + mypy/pyright on
      `src/plainlang`; zero-dependency runtime preserved (dev deps only).
- [ ] **TST-11 · CI matrix & gates** — `P1 · S`. Python 3.11/3.12/3.13 ×
      Linux/macOS; tests, check, fmt --check, validate, Rust, coverage.
- [ ] **TST-12 · No-network tests** — `P1 · S`. Local fixtures only.
- [ ] **TST-13 · Security tests** — `P2 · M`. Escaping, secret redaction,
      capability denial, path traversal.
- [ ] **TST-14 · Pre-commit** — `P2 · S`. fmt/check/test on changed
      `.plain` and `.py` files.
- [ ] **TST-15 · Mutation testing** — `P3 · L`. Optional, for the runtime
      and checker.

---

## 17. Documentation & spec

- [ ] **DOC-01 · README truth pass** — `P0 · S`. Test counts, commands,
      status, architecture tree; every number verified (P0-11).
- [ ] **DOC-02 · Doc 06 truth pass** — `P0 · S`. LOC, test count, G-list,
      deferred list, Rust table, "Stage 3 core complete" nuance.
- [ ] **DOC-03 · Fold G-1…G-10 into Doc 03** — `P1 · M`. The spec must be
      normative again: defaults, content-first, greedy `where`, inline
      conditional props, scoped derivations, LHS rule, `#` handling,
      continuations, page=viewport, page-link literals, `ready-or`.
- [ ] **DOC-04 · Resolve open pressure points** — `P1 · S`. Shared-element
      `id` (pressure point 4 in examples/README), `refresh` spelling, `together`,
      `whenever`, themes; each gets one spelling and a spec sentence.
- [ ] **DOC-05 · Feature status matrix** — `P1 · S`. Generated from tests:
      spec clause → implementation → test. One table, always current.
- [ ] **DOC-06 · Examples README accuracy** — `P1 · S`. PL line counts,
      "eight plus hello", Phase-5 mapping, pressure-point status.
- [ ] **DOC-07 · Add missing examples** — `P1 · M`. Themes, shared state +
      persistence, a form that actually types, a real resource fetch,
      animation/transition, i18n/Amharic, terminal target, a component
      library. Each must pass `check` and render.
- [ ] **DOC-08 · Contributor docs** — `P2 · S`. CONTRIBUTING, code layout,
      how to add a node/property, how to run the oracle and Rust suites,
      how to amend the spec.
- [ ] **DOC-09 · Security docs** — `P2 · S`. SECURITY.md, capability
      model, threat model (SEC-10).
- [ ] **DOC-10 · Roadmap & changelog** — `P2 · S`. ROADMAP.md mirrored to
      Doc 05 stages, CHANGELOG.md, spec version history.
- [ ] **DOC-11 · 1-day tutorial + hallway protocol** — `P2 · M`. The
      Constraint-5 metric is only real if it is measured and recorded.
- [ ] **DOC-12 · Glossary** — `P2 · S`. PLAIN, PL, Clear, Openly,
      Looking Glass, Flow, look, kind, resource, capability, shared.
- [ ] **DOC-13 · Docs lint** — `P2 · S`. Link check, TOC generation,
      markdownlint, spelling (Amharic terms consistent).
- [ ] **DOC-14 · ADR traceability** — `P2 · S`. Each ADR marked
      proposed/accepted/implemented, with code and test links.

---

## 18. Performance & validation

- [ ] **PERF-01 · Benchmark harness** — `P1 · M`. Build time, node count,
      SVG bytes, memory, per example and size; commit baselines.
- [ ] **PERF-02 · Reference-device profile** — `P2 · L`. $100 Android
      class, cold start < 500 ms, frame CPU < 4 ms, idle 0, RAM < 80 MB,
      program 10–200 KB (Doc 02 §6.4).
- [ ] **PERF-03 · Reactivity cost** — `P2 · M`. Measure updates per state
      write; prove O(changed) after RT-01/RT-02.
- [ ] **PERF-04 · Text cache** — `P2 · M`. Shaped-run cache keyed by
      (runs, font, size, width); hit-rate instrumentation.
- [ ] **PERF-05 · Energy** — `P2 · L`. Idle wakeups, timers, animation
      budgets; publish numbers.
- [ ] **PERF-06 · Phase-5 comparison harness** — `P3 · XL`. Build all 10
      apps in PL and the strongest incumbent; measure LOC, dev-hours,
      cold start, RAM, frame p95, wire size, read-aloud comprehension
      (Doc 05 Phase 5). Publish, including failures.
- [ ] **PERF-07 · Regression dashboard** — `P3 · M`. Track budgets over
      commits; link from CI.

---

## 19. Ecosystem & stdlib breadth

- [ ] **ECO-01 · Stdlib control set** — `P2 · L`. The Doc 01 §6.1 list as
      PL components (UI-07), themed by tokens, accessible by derivation.
- [ ] **ECO-02 · Collections** — `P2 · M`. List/Map/Set and persistent
      variants; `SharedList/SharedText/SharedMap` CRDT types with the same
      syntax (Doc 01 §3.2).
- [ ] **ECO-03 · Time API** — `P2 · M`. `Moment/Duration/Calendar` with
      Temporal-class correctness, not JS Date's mistakes.
- [ ] **ECO-04 · i18n** — `P2 · L`. `text "Hello" in user-language`;
      message catalogs as PL data; ICU-class plural/gender; RTL and
      vertical layout; Amharic/Ge'ez first-class test apps (Doc 05 Stage 3
      exit). This is a headline differentiator — do not let it slip.
- [ ] **ECO-05 · Crypto** — `P3 · M`. SEC-09.
- [ ] **ECO-06 · Built-in testing** — `P1 · L`. `check` blocks, scene
      snapshots, interaction simulation; `plain test` (CLI-01).
- [ ] **ECO-07 · Openly registry spec** — `P3 · L`. Scoped names,
      immutable versions, semver API-diff at publish, quality score,
      mirrorable storage, no install scripts.
- [ ] **ECO-08 · Registry alpha** — `P3 · XL`. Index + storage + signing
      + `plain add`/`publish`.
- [ ] **ECO-09 · Modules** — `P3 · L`. `use` local and registry; namespace
      collisions; needs union displayed to the user.
- [ ] **ECO-10 · Charts** — `P3 · L`. Stdlib chart basics on `canvas`.
- [ ] **ECO-11 · Design bridge** — `P3 · L`. Figma/Penpot frames → PL
      skeleton; PL theme → design tokens.
- [ ] **ECO-12 · Playground & docs site** — `P3 · M`. Browser playground
      running the oracle/exporter; searchable spec.

---

## 20. Platform targets & distribution (Stage 4–5)

- [ ] **PLAT-01 · Desktop shell** — `P3 · XL`. Native windows on
      Win/macOS/Linux, wgpu, tray/menu/window nodes, < 25 MB runtime.
- [ ] **PLAT-02 · Android shell** — `P3 · XL`. Native shell, not WebView;
      IME and a11y bridges; first mobile target (Doc 05 Stage 3/4).
- [ ] **PLAT-03 · iOS shell** — `P3 · XL`. Same Clear engine; VoiceOver
      bridge; store constraints if any.
- [ ] **PLAT-04 · Embedded/fixed-heap profile** — `P3 · L`. CPU fallback,
      bounded memory, no-GC mode.
- [ ] **PLAT-05 · Spatial/AR/VR** — `P3 · XL`. `scene3d` subtree
      stereoscopic; 2D panels as scene nodes in space.
- [ ] **PLAT-06 · Terminal renderer** — `P3 · L`. Degraded renderer:
      text/buttons/lists survive; media placeholders; same program.
- [ ] **PLAT-07 · PL → web exporter** — `P3 · XL`. WASM+WebGPU, a custom
      element per component; the adoption bridge (Doc 00 §0.2.7).
- [ ] **PLAT-08 · Legacy webview node** — `P3 · M`. Sandboxed, no scene
      access, clearly deprecated.
- [ ] **PLAT-09 · FFI** — `P3 · L`. Signed native modules, capability
      `needs native`, out-of-process where feasible.
- [ ] **PLAT-10 · WASM plugin format** — `P3 · L`. WASI-style capability
      imports mirroring SEC-03.
- [ ] **PLAT-11 · Distribution** — `P3 · XL`. `plain://`, signed
      manifests, content hashes, QR, atomic updates, offline cache.
- [ ] **PLAT-12 · Monetization RFC** — `P3 · M`. `pay creator …` design
      only, rail-agnostic.
- [ ] **PLAT-13 · Governance** — `P3 · M`. Open spec, RFC process, Plain
      Test as formal gate, no sponsor > 20%, second-implementation
      sign-off rule.
- [ ] **PLAT-14 · Second implementation** — `P3 · XL`. Feasibility study
      once Rust is stable; the strongest proof the spec is real.

---

## 21. Suggested execution order

**Milestone M0 — "trustworthy prototype" (1–2 weeks).**
`P0-01` → `P0-02` → `P0-03` → `P0-06` → `P0-08` → `P0-09` → `P0-10` →
`P0-05` → `P0-12` → `P0-11`.
Exit: example 06 is typeable end-to-end; nothing is silently ignored;
`fmt --check` and CI mean something; docs tell the truth.

**Milestone M1 — "Stage 3 semantics complete" (4–6 weeks).**
Units/types (`EX-01…07`), component binding (`FE-05`), themes (`FE-13`),
`use` (`FE-12`), scoped derivations (`UI-06`), real resources
(`NET-01…07`), results/`post` (`EX-05`, `NET-08`), keyed lists (`RT-03`),
navigation/router (`RT-22/23`), event dispatch (`RT-09`), checker name
resolution (`CHK-02`), a11y basics (`A11Y-01…03,05`), layout constraints
(`LAY-01…05`), stdlib seed (`UI-07`).
Exit: all 9 examples run their *actions*, including chat send and form
submit; themes change pixels; `keep` migrates; a11y tree is complete;
`plain check` catches action errors.

**Milestone M2 — "competitive engine" (2–3 months).**
Rust slices 3–4 (`RS-01…05,09`), Flow completion (`LAY-06…14`),
text (`H-06`), paint completeness (`H-01`), animation/gestures
(`H-03…05`), Looking Glass (`SRV-07…10`), LSP (`CLI-10`), tests/CI
(`TST-*`, `CHK-*`), benchmarks (`PERF-01`).
Exit: Rust renderer and oracle agree on scene/layout/SVG; examples 07/08
actually animate/gesture; a dev can edit and see live updates with state.

**Milestone M3 — "platform" (6–12 months).**
Clear wgpu/Vello + HarfBuzz (`H-09/10/11`, `RS-06`), capabilities
(`SEC-01…05`), desktop/Android shells (`PLAT-01/02`), Openly alpha
(`ECO-07/08`), i18n (`ECO-04`), Phase-5 measurements (`PERF-06`).
Exit: Doc 05 Stage 4 exit criteria; p95 budgets on the reference phone.

**Milestone M4 — "ecosystem" (12–24 months).**
iOS, spatial, terminal, web exporter, distribution, governance,
second implementation, security audit (Doc 05 Stage 5).

**Parallelization:** parser/checker/diagnostics (one person), runtime +
resources (one), scene/layout (one), server/CLI/tooling (one), Rust port
(one), docs/examples/i18n (one). This matches Doc 05's 4–6 person Stage-2
team; do not add people to the language core without adding spec review.

---

## 22. Open decisions that block work

Each needs a written answer in Doc 03 before implementation; they are
listed here so the backlog does not silently choose for us.

1. **Component defaults syntax and semantics** — `size = 40` in the
   signature, evaluated in the caller or callee scope? (P0-02 depends.)
2. **`refresh` spelling** — examples/README pressure point 2 explicitly
   leaves it open; `ready-or` is settled.
3. **`then` chains + `show toast`** — are they statements, expressions, or
   sugar for a sequence? Doc 03 §6.5 uses both.
4. **Themes** — author-declared tokens only, or also library themes and
   per-user themes? How does `theme dark:` follow the OS?
5. **Units as types** — exact arithmetic rules for `Length/Percent/
   Duration/Angle`; what does `fill` mean in expressions?
6. **Identifiers in Amharic/Ge'ez** — allowed or ASCII-only? A platform
   for the next billion should answer deliberately, not by accident.
7. **Stdlib size for v1** — which of the Doc 01 §6.1 list ships before
   the registry exists?
8. **Error recovery policy** — how many errors per file, and does the
   preview show all or the first?
9. **Preview trust model** — is `plain run` a dev-only localhost tool, or
   a hosted playground? That decides SEC-07/SRV-12.
10. **Rust sequencing** — port slice 3 now (parity risk grows with every
    Python change) or freeze oracle semantics first? Recommendation:
    freeze M1 semantics, then port, with the differential harness running
    from day one.

---

## 23. Explicit non-goals for this backlog

- Rendering existing HTML/CSS/JS (Doc 00 §0.2.7). The bridge is one-way:
  an exporter, plus a fenced `webview` node.
- A CSS-like cascade, selectors, or global styles (Doc 03 §4.1).
- User-visible threads, locks, channels, or async/await coloring
  (Doc 03 §6.5).
- A package manager that runs install scripts (Doc 01 §6.2).
- A general-purpose systems language (Doc 03 §1).
- Bug-for-bug web compatibility. Saying no is a budget feature
  (Doc 00 A11).

---

## 24. Final definition of done for the project (Stage-3 oracle)

The Python oracle is "Stage 3 complete" when all of the following are
demonstrably true:

- [ ] All 9 examples pass `check`, render, and their **actions** execute:
      todo add/remove/filter, chat send with an error path, table
      sort/search/page, form validation submit, gallery navigation.
- [ ] No valid construct is silently ignored: every parsed statement,
      event, prop, theme, and module either works or names the stage that
      will implement it.
- [ ] Every example is interactable in the preview, including inputs and
      buttons inside `children` slots.
- [ ] `plain check` catches the canonical errors (including inside
      actions) with caret spans and Try lines.
- [ ] `plain fmt --check` passes on the corpus and is CI-gated.
- [ ] `plain validate` fails CI on regressions and reports real numbers.
- [ ] Accessibility is derived, keyboard-operable, and contrast-checked
      for every example, with zero a11y-specific words in their source.
- [ ] State survives reload and restart via `keep`, with a migration
      story; `shared` state is coherent across components.
- [ ] Every semantic has a home in Doc 03 (no oracle-only behavior).
- [ ] The Rust port has matching parser/checker/expr/runtime/scene/layout
      tests, and the differential harness is green.
- [ ] The README, Doc 06, and the code agree about what exists — verified
      by tests, not by editing prose.
