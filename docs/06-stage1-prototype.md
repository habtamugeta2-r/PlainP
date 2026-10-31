# Stage 1–3 — Reference Prototype (what now actually runs)

> Status of Doc 05 Phase 4: **Stage 1 + Stage 2 + Stage-3 core complete
> in the reference prototype.** All 9 normative examples render and the
> interactive ones are usable in the preview. Everything below is
> *executable*: `./plain run examples/02-todo.plain`, type, hit Enter.

```
Stage-1 prototype
├── 1. Why Python (and why that does NOT repeal ADR-1)
├── 2. Try it (60 seconds)
├── 3. Module map (code ↔ blueprint)
├── 4. Implemented vs deferred (honest table, exit criteria)
├── 5. Grammar decisions forced by implementation (G-1…G-10)
├── 6. Deliberate divergences from the blueprint
└── 7. Next: Stage 2 work list + Rust-port mapping
```

## 1. Why Python — the spec-oracle

ADR-1 chose **Rust** for production Clear/runtime (Doc 05). That decision
stands. This prototype is a **reference implementation in zero-dependency
Python** (stdlib only) because Stage 1's risks are *language* risks —
grammar ambiguities, layout semantics, error-message quality — not
throughput risks. A readable oracle that pins semantics down (and that the
future Rust port must match test-for-test) is the cheapest way to retire
those risks; this is the CPython/reference-interpreter pattern. The sandbox
used for this work also has no Rust toolchain and no route to install one —
recorded here so the choice isn't misread as an ADR-1 reversal. Rule:
**no semantic may exist only in this prototype** — each one lands either in
Doc 03 (spec amendment) or in §5 below.

## 2. Try it (60 seconds)

```bash
./plain check examples/*.plain                  # all 9 normative examples pass
./plain render examples/00-hello-world.plain --out hello.svg
./plain run    examples/01-counter.plain        # http://localhost:8000 — click +1
./plain a11y   examples/01-counter.plain        # derived accessibility tree
make test                                       # 92 tests, <2s
```

The `run` preview shows the app, its full source, the derived a11y tree and
live state side by side (a baby Looking Glass, Doc 01 §6.3), lets you tap
buttons (works with JS disabled — taps are scene-path links), switch
viewport sizes (incl. a 360×640 "cheap-android" preset, Constraint 6), and
**keeps state across reloads while applying your edits** (see §6.4).

## 3. Module map (~6.2k LOC incl. tests; well inside the 500k budget)

| File | Blueprint home | What it does |
|---|---|---|
| `tokens.py` | Doc 03 §2 | Line tokenizer; hyphen-names; `#` comment vs `#RRGGBB` color |
| `parser.py` | Doc 03 §3–6 | Indentation block tree → classified AST; table-driven property loop |
| `ast_nodes.py` | Doc 03 | The AST (expressions kept as source, parsed on demand) |
| `expr.py` | Doc 03 §6–7 | Expression parser/evaluator: pipelines (`where/count/…`), records, interpolation |
| `checker.py` | Doc 03 §10 | Plain-sentence diagnostics + did-you-mean |
| `runtime.py` | Doc 03 §6.1/§9 | State scopes (=), derivations (is), actions, hot-reload preservation |
| `scene.py` | Doc 02 §1 | Page → ONE scene tree; component expansion; looks; source spans |
| `layout.py` | Doc 02 §2 | **Flow**: constraints down, sizes up; align/spread/grow |
| `paint_svg.py` | Doc 02 §3 (CPU profile) | Deterministic SVG paint |
| `a11y.py` | Doc 02 §1.4 | Derived accessibility tree — never authored |
| `server.py`/`cli.py` | Doc 03 §10 | `plain run/check/render/a11y/parse` |

One pipeline (`render.py: App`) is shared by CLI, server, and tests — the
Doc 03 §10 "one compiler" rule from day one.

## 4. Implemented vs deferred

**Works today (with tests):** full-corpus parse+check (all 9 examples);
pages/components/params/`children` slot; `=`, `is`, `to` actions, inline
`on tap:` statements, action calls; records with defaults (`Task(title:…)`);
list ops `add/remove`; `if/otherwise`, `for` (incl. index), scoped
derivations; looks + conditional looks; Flow column/row/stack/grid/scroll,
text/button/input/toggle/box/image/divider/spacer/spinner; grow, align,
spread, `fill/fixed/fit + max`, padding 1/2/4; interpolation; derived a11y;
hot reload with state; spec-exact error messages ("`` `button` needs
something to show… Try: button "Save" on tap save`` — Doc 03 §10, verbatim).

**Added in Stage 2 (all tested):** typing end-to-end — HTML form overlays
bound to scene inputs, `type → Enter` fires `on submit`, a JS-optional
`/sync` path makes `type → click Add` work too; toggle taps flip `bind`
targets; disabled buttons don't fire. Container `width/height/narrow`
builtins during scene build (navbar switches inline-links ↔ Menu by real
viewport); `keep` persistence (`.plain/<app>.json`, survives restarts,
`/reset` clears); checker name resolution for event actions + looks;
`./plain fmt` (idempotent on the whole corpus); greedy text wrapping with
fixed-width parents constraining children (Flow, constraints-down).

**Added in Stage-3 core (all tested):** resources with sidecar data
providers (`<app>.sample.json`) as `("ready"|"failed", payload)` values;
`when` matching over resources with payload binding; `ready-or` pipe;
navigation stack (`go to Page(x)`, `go back`, page params); `table/header/
cell` with shared column widths; stdlib `ErrorBox`; `scene3d` as a labeled
viewport placeholder whose sibling 2D UI works fully (configurator price
updates from swatches/cushion — the one-tree claim holds); form validation
flow runs (submit-empty → errors appear); page-link literals (G-9).

**Phase-5 harness:** `./plain validate` builds every example and reports
PL lines / scene nodes / SVG bytes / build ms — currently **9/9 render,
0.7–6 ms builds** on this sandbox (Python! — the point is headroom, not
the number).

**Still deferred (render raises `UnsupportedYet` naming its stage):**
a configurable retry policy, streaming `from live`, request headers/query
builders, cache dedupe/stale-while-revalidate/disk, animation/springs +
page transitions (declared, ignored), gestures beyond tap, themes as author
data (built-in palette), `shared sync` CRDTs, scroll viewport culling,
HarfBuzz shaping/wrapping polish, non-`ErrorBox` stdlib components, the
Rust/GPU production engine (ADR-1/5 — §7).

**Exit-criteria scoreboard (Doc 05):** Stage 1 ✅ (Hello World <5 min;
byte-identical SVG; ~4.9k LOC ≪ 60k budget). Stage 2 ✅ in prototype
(00/01/02/03 run as written; todo usable by typing; frame costs are
CPython numbers, not the Rust budget — noted honestly). Stage 3 ✅ core
(04–08 render + interact as tested above). Stage 4/5 partially (stdlib
seed, Looking-Glass panels, validate harness; Openly/JIT/iOS shell are
production-engine work, not oracle work). ⏳ wgpu window — SVG + web
preview stands in (§6.2), de-risking ADR-5's gate with measurable layout.

## 5. Grammar decisions forced by implementation (spec amendments)

Each was ambiguous in Doc 03 v0.1; each now has ONE spelling, a test, and
belongs in Doc 03 at the next spec rev:

- **G-1 Content-first:** built-in content kinds (`text`, `button`, …) always
  take their content as the first token, even when it spells a property
  name (`text label …`, `text error …` in ex. 06). Components keep
  named-arg reading for their own params.
- **G-2 `where` is greedy:** in `tasks where A or B`, the whole `A or B`
  is the per-item filter (ex. 02/05). `tasks count where not done` counts
  the filtered list (terminal ops apply after filters). Item fields are
  bare names inside the condition.
- **G-3 Inline conditional props are THE spelling** (`strike if done`,
  `look a if c otherwise look b`, `width 3 if selected`) — resolves
  examples/README pressure point 1: the comma-suffixed form in Doc 03 §4.4
  is **withdrawn** (one way only, Plain Test #4).
- **G-4 Scoped derivations are real** (`columns is 3 if …` inside `grid`,
  ex. 07; derivations inside `when` branches, ex. 05) — resolves pressure
  point 3: `name is …` is legal wherever statements are.
- **G-5 Declaration LHS:** `name [: Type] = …` only if the left side is
  names/colons/dots — so node lines containing `+=`/`-=` in handlers never
  mis-parse. (Bug found by implementation; now a regression test.)
- **G-6 `#` disambiguation:** `#` + 3/6/8 hex digits + delimiter is a color;
  otherwise it's a comment. Both appear in real programs (ex. 08).
- **G-7 Continuations & prop wrapping:** a line starting with `and`/`or`
  continues the previous logical line (ex. 02); indented lines under a node
  that begin with a property word are prop continuations of that node
  (ex. 04/06/08) — except `name is …` (G-4).
- **G-8 Page = viewport:** the page's root child fills the viewport unless
  it sizes itself otherwise (`width fill max 560 center-self`, ex. 02).
- **G-9 Page-link literals:** `Home-link` evaluates to the link record
  `{title, page}` for `page Home` (ex. 03) — navigation data stays plain
  values; `go to link.page` navigates by the record's page.
- **G-10 `ready-or` ratified** (pressure point 2): `photos ready-or []`
  is the resource-unwrap spelling. `refresh x` is now executable: it drops
  the cached value and fetches once, and an unknown `x` is a plain error.

Still open: #4 shared-element `id` retention (parsed; animation pending).

**Newly known gaps (now visible as `plain check` notes, never silent):**
`theme` / `use` are parsed and preserved but not applied; `transition` swaps
instantly; only `tap`, `change`, and `submit` are dispatched (other valid
gestures raise `UnsupportedYet` if fired); `refresh x` forces one refetch
(no polling yet); `ErrorBox … retry refresh x` dispatches that same refresh
on tap. Safe GETs (`fetch` and resources) retry transient failures three
times with 50→100 ms backoff; `POST` never auto-retries, so a write cannot
be silently duplicated. Text metrics remain the deterministic approximation.
Resources are cached in memory per `(scope, name, resolved address)`, bounded
at 128 entries with LRU eviction; a resource over real http(s) is fetched on
first use and reused until `refresh`. A refresh sends `If-None-Match` when an
ETag was seen, and a `304` keeps the cached value. `post` / `fetch` execute
through a request seam: sidecar keys `"POST /path"` / `"FETCH /path"` or real
http(s), returning `ok`/`failed` results consumed by `when`; `then` and
`show toast` work in actions. Without a fixture/transport a request returns a plain offline
sentence — never a crash and never a fake success.
**Known example defect:** example 08's Add-to-cart line references an
undeclared `cart` list and a `Chair(…)` kind that the file never defines.
The parser accepts it; the runtime reports a plain error at tap time. The
examples are normative, so this needs a spec/example decision rather than a
silent runtime fallback.

## 6. Deliberate divergences (prototype simplifications, seams marked)

1. **Reactivity:** derivations recompute on read instead of ADR-3's
   fine-grained graph. Same observable semantics; seam = `runtime.env_for`.
2. **Paint:** SVG (Clear's *CPU-fallback profile* in spirit), not wgpu GPU
   compute (ADR-5). Seam = `paint_svg.to_svg(scene)`; scene/layout above
   it are backend-agnostic already.
3. **Text metrics:** deterministic approximation (0.52/0.56 × size per char),
   no wrapping/shaping yet — HarfBuzz arrives with the Rust engine
   (Doc 02 §4). Layout *protocol* (constraints→sizes) is the real one.
4. **Hot reload:** the Python server re-parses per request and re-homes
   state by instance path (new names init, removed names dropped) — Doc 03
   §10's semantics, accidentally also the simplest implementation. The
   production version rewires bindings instead; behavior must match this.
5. **Errors for future syntax:** `UnsupportedYet` ("Your program is fine")
   is a distinct class from user `PlainError` — the corpus can stay ahead
   of the renderer without anyone thinking correct programs are wrong.

## 7. Next

**Remaining oracle work:** configurable retry policy + streaming behind the
existing resource seam (NET-03/07); animation timing/springs in the preview;
`shared sync` sketch; themes as data; scroll culling; LSP.

## 8. Rust port status (production path, ADR-1)

Lives in `rust/` (zero-dependency crate `plainlang` + `plain-rs` CLI),
mirroring the oracle module-for-module. This sandbox cannot install Rust
(`static.rust-lang.org` is egress-blocked), so **CI is the compiler of
record**: `.github/workflows/ci.yml` runs the Python oracle suite and the
Rust parity tests on every push/PR.

| Slice | Contents | Status |
|---|---|---|
| 1 | `tokens`, block tree, `ast`, `parser` (full classification parity incl. G-1…G-10), `plain-rs check` parse stage | ✅ CI green (9 tests) |
| 2 | `checker` (all diagnostics + did-you-mean via normalized Levenshtein), `plain-rs check` = parse+check | ✅ CI green (15 tests) |
| 3 | `expr` parser/evaluator + `runtime` (state/derived/actions/`keep`) | next |
| 4 | `scene` + `layout` (Flow) + `a11y` derivation | planned |
| 5 | Clear paint: wgpu/Vello per ADR-5 (SVG writer first for parity), HarfBuzz text, native window | planned |

Rule of the port: no semantic may diverge silently — each Rust slice ships
with tests translated from `tests/test_stage1.py`, and error wording is
asserted by substring in *both* suites. When they disagree, the oracle
(and before it, the examples) wins until a spec amendment says otherwise.
