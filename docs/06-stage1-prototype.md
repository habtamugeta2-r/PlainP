# Stage 1 — Reference Prototype (what now actually runs)

> Status of Doc 05 Phase 4, Stage 1 ("Hello World", months 1–3) + the
> reactivity spike from Stage 2. Everything below is *executable*, not
> aspirational: `./plain run examples/01-counter.plain` really works.

```
Stage-1 prototype
├── 1. Why Python (and why that does NOT repeal ADR-1)
├── 2. Try it (60 seconds)
├── 3. Module map (code ↔ blueprint)
├── 4. Implemented vs deferred (honest table, exit criteria)
├── 5. Grammar decisions forced by implementation (G-1…G-8)
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
make test                                       # 22 tests, <0.1s
```

The `run` preview shows the app, its full source, the derived a11y tree and
live state side by side (a baby Looking Glass, Doc 01 §6.3), lets you tap
buttons (works with JS disabled — taps are scene-path links), switch
viewport sizes (incl. a 360×640 "cheap-android" preset, Constraint 6), and
**keeps state across reloads while applying your edits** (see §6.4).

## 3. Module map (~3.1k LOC incl. tests; well inside the 500k budget)

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

**Parse+check only (render raises `UnsupportedYet` naming its stage):**
resources (`from`, `when` — Stage 3), navigation (Stage 3), `scene3d/table`
(Stage 2/3+), transitions/gestures beyond tap, `keep` persistence (parsed;
Stage 2 task), themes as data (default palette built in), stdlib components
(`ErrorBox`…), name resolution in the checker (runtime reports unknown
names plainly today), text wrapping/shaping (approximate metrics), input
*editing* in the web preview (inputs render; two-way `bind` executes in
headless tests via state, HTML form wiring is first Stage-2 task).

**Stage-1 exit criteria (Doc 05) — scoreboard:** ✅ new-dev Hello World
from README in <5 min (only prerequisite: clone; zero install); ✅ static
scene byte-identical across OSes (deterministic SVG, golden test); ✅
engine+VM <60k LOC at Stage 1 (actual: ~2.9k — prototype LOC isn't the Rust
budget, but plainness is holding); ✅ examples 00/01 run as written
(Stage-2 criterion, met early, incl. interactivity). ⏳ wgpu window — replaced
this stage by SVG + web preview (§6.2); the CPU-fallback-first choice also
de-risks ADR-5's decision gate with real layout code to measure.

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

Still open (unchanged from examples/README): #2 resource conveniences
(`refresh x`, `ready-or []`) at the Stage-3 RFC; #4 shared-element `id`
retention (parsed; animation is Stage 3+).

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

**Stage 2 (in order):** (a) input `bind` end-to-end in the preview
(HTML forms → `on submit` — makes Todo fully usable, closing the Stage-2
"02 runs as written" criterion); (b) container `width` in scene env →
renders 03-navbar for real; (c) checker name resolution + `keep`
(file-backed persistence); (d) `plain fmt` (block-tree re-indent);
(e) text wrapping. **Rust port:** mirror this module map 1:1
(parser/tokens/expr first; they carry the semantics), port the test suite
unchanged as the conformance oracle, then swap paint to wgpu/Vello behind
the same scene. The Python tree stays as the reference for error wording.
