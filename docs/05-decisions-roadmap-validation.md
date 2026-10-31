# Phases 2, 4, 5 — Implementation Decisions, Roadmap, Validation

```
├── Phase 2: Architecture Decision Records (ADR-1 … ADR-8)
├── Phase 4: Proof-of-concept roadmap (Stages 1–5, with exit criteria)
└── Phase 5: Validation — 10 test apps, metrics, pass bars
```

---

# Phase 2 — Architecture Decision Records

## ADR-1: Implementation language for Clear + PL runtime → **Rust**
| Candidate | Strengths | Fatal/serious weaknesses for PLAIN |
|---|---|---|
| **Rust** ✅ | Memory safety without GC (engine hot paths), wgpu/Vello/Linebender ecosystem, Servo proved Rust browser-adjacent engineering, WASM target first-class, fearless concurrency for parallel layout | Steeper contributor curve (mitigated: contributors write engine Rust, *users* write PL — the audiences differ) |
| Zig | Simpler, great C interop, Bun precedent | Younger ecosystem; no wgpu/Vello-class graphics stack; memory safety is discipline+testing, not enforced — wrong trade for a sandbox host running untrusted code |
| C++ | Skia/Chromium surface area | ~70% of serious browser CVEs are memory-safety bugs; choosing C++ in 2026 for an untrusted-code platform needs a justification that doesn't exist; build/tooling complexity fights the <500k LOC budget (Doc 00 A11) |
| Mixed (Rust core + Zig etc.) | Best-of-both in theory | Two toolchains, FFI seams in hot paths, doubled hiring/CI story — complexity PLAIN exists to delete |

**Decision:** Rust everywhere for Clear, compiler, runtime, Looking Glass.
HarfBuzz via maintained bindings (Doc 02 §4). Revisit only if Stage 1–2
profiling shows a Rust-external bottleneck (none expected).

## ADR-2: The product is the language; the engine is boring
Clear adopts *proven* subsystems (wgpu, Vello-class paint, HarfBuzz,
Flutter's layout protocol) and spends its originality budget on integration
(one tree, bindings, budgets). PL receives the design risk and the Plain
Test iteration. Rationale: every failed "new platform" over-invested in
rendering novelty and under-invested in authoring feel (Doc 00 C3).

## ADR-3: Retained scene graph + compiled fine-grained bindings
(Not virtual-DOM diffing; not pure immediate mode.) Full rationale Doc 02
§1.3. Consequences: compiler must emit per-binding update code; runtime
keeps a dependency graph (which also powers "why did this update?" in
Looking Glass); list identity is runtime-tracked. Accepted cost: compiler
complexity — paid once, by us, instead of per-frame by every user (the
Svelte/Solid lesson).

## ADR-4: Execution — verified bytecode VM first, JIT second, AOT optional
Tree-walking interpreters are 10–50× too slow for data-heavy UI logic; a
from-scratch optimizing JIT (V8-class) is a decade project. Middle path:
register-based bytecode (Lua/Dart-VM class perf is ample: UI code is
binding- and IO-bound, not numeric-bound), bytecode verifier for sandboxing,
method JIT in Stage 4 only if profiles demand it, optional AOT-to-native at
publish for app-store contexts. GC: generational, incremental, off the
compositor thread (Doc 02 §6.1). Research anchors: LuaJIT (small+fast is
possible), Dart VM (UI-language runtime precedent), WASM (our export/plugin
target, not our primary IR — PL bytecode carries UI/binding semantics WASM
would erase).

## ADR-5: Graphics — wgpu + Vello-class compute paint, CPU fallback profile
Rationale Doc 02 §3.1. Risk register: Vello maturity → hedge by keeping
Clear's paint backend behind a narrow display-list interface; a Skia backend
remains buildable if compute path underperforms on target Mali/Adreno
low-end parts. Stage 1 exit criteria includes the fallback decision gate
(Phase 4 below).

## ADR-6: Threading — layout ∥ paint, programs in isolates, structured concurrency
Single-threaded rendering is rejected (Servo/Flutter evidence; A4's event
loop is the cautionary tale). PL exposes **no threads/locks/channels to
authors**; `together:` structured blocks + resources give parallelism
without races (Doc 03 §6.5). Compositor owns vsync; isolates can be killed
without losing the frame loop.

## ADR-7: Security — capabilities as unforgeable values, isolate sandboxing
Rationale Doc 01 §5. Explicitly rejected: origin-based policy (A6),
ambient stdlib authority (npm/Deno pre-flags lesson), in-process native
plugins for untrusted code. Formal target for Stage 5 audit: a machine-
checked proof sketch that safe-subset PL bytecode cannot invoke a
capability API without holding its handle (handle injection is the sole
introduction rule — small enough to actually verify).

## ADR-8: Distribution & identity — content-addressed, signed, HTTPS transport
Rationale Doc 01 §3.3. Rejected: inventing a wire protocol (QUIC exists),
location-only identity (spoofable, stale-cache-prone), app-store gating
(B3). Monetization hooks (Doc 00 §0.2.9) ride on signed authorship from
this ADR.

## ADR-9: Three-layer separation — PL Core, Clear Primitives, and Prelude UI (`std/ui`)
PL language fundamentals must not hardcode widget catalogs into the compiler
or engine. The stack separates cleanly into three layers while keeping PL's
single-syntax, zero-boilerplate authoring:
1. **PL Core (UI-agnostic language fundamentals):** kinds/variants, primitives,
   state (`=`), reactive derivations (`is`), two-way `bind` references,
   control flow (`if`/`for`/`when`), actions (`to`), modules (`use`),
   capabilities (`needs`), resources (`from`), persistence (`keep`), and
   generic block/element call syntax — runnable headless without Clear.
2. **Clear Engine Primitives (~8 irreducible atoms):** Flow layout (`row`,
   `column`, `stack`, `scroll`/`grid`), paint (`box`, `text`, `image`,
   `canvas`), OS text-editing/IME bridge (`text-input`), and intrinsic
   accessibility/interaction traits (`role`, `focusable`, `min-target`,
   pointer/key states) on primitives so Axiom A9 (derived accessibility)
   holds by construction.
3. **Standard UI Prelude (`std/ui.plain`):** controls (`button`, `toggle`,
   `slider`, `select`, `divider`, `spacer`, `spinner`, `table`/`header`/
   `cell`, etc.) authored in `.plain` on top of PL Core + Clear atoms and
   auto-loaded as prelude so both the Python oracle and Rust engine share
   one UI kit implementation and dogfood PL's own component model.

---

# Phase 4 — Proof-of-Concept Roadmap

> Sequencing principle: **language feel is tested from Stage 1** (examples
> are the spec). Each stage has *exit criteria*; a stage that misses its
> Plain-Test or budget criteria does not "pass with tech debt" — it iterates.

### Stage 1 — "Hello World" (Months 1–3)
- PL parser + formatter for the §2–§5 subset (nodes, props, looks/themes);
  bytecode VM skeleton; Clear: scene graph, Flow column/row, box/text/image
  nodes, wgpu window on Win/macOS/Linux; CPU paint fallback spike (ADR-5 gate).
- `plain run` CLI. Examples `00-hello`, `01-counter` (static half) parse+render.
- **Exit:** a new dev writes Hello World from the README in < 5 min in
  hallway testing; static scene renders pixel-identical on 3 desktop OSes;
  engine+VM < 60k LOC at this point (budget tracking starts now).

### Stage 2 — "Interactive" (Months 4–6)
- Fine-grained reactivity (`=`, `is`, bindings — ADR-3), events/gestures,
  input/toggle/button behavior, Flow grid/stack/scroll + container `when`,
  state-preserving hot reload, first Looking Glass (scene tree + click-to-source).
- **Exit:** `01-counter`, `02-todo` (core), `03-navbar` run as written in
  `examples/`; frame CPU < 4 ms for todo-with-1000-rows scroll on reference
  laptop; hallway users predict what `is`/`whenever` do before being told
  (Plain Test #1, measured, ≥ 80% correct).

### Stage 3 — "Useful" (Months 7–12)
- Components/children/kinds/`when`, resources (`from`, live streams, cache/
  retry/offline — Doc 01 §3.1), `keep` persistence + migrations, spring
  animation + page transitions, text engine hardening (IME, bidi, Ge'ez &
  Arabic test suites), forms+validation stdlib, Android shell (first mobile).
- **Exit:** examples `04–07` run as written; todo survives airplane-mode
  week; Amharic/Arabic/Chinese sample apps pass native-speaker review;
  a11y: todo fully operable via TalkBack/VoiceOver with zero a11y-specific
  code in its source (verify by grep — there is none to grep).

### Stage 4 — "Competitive" (Months 13–18)
- Full stdlib v1 (Doc 01 §6.1), Openly registry alpha (signed modules,
  scoring), Looking Glass profiler + time-travel, iOS shell, `scene3d`
  (example `08`), JIT if profiles demand, PL→web exporter (adoption bridge),
  LSP + editor plugins, docs site + 1-day tutorial (tested: juniors complete
  it in a day — Constraint 5, measured).
- **Exit:** Phase 5 apps 1–5 built by *external* pilot devs (not core team)
  within target dev-times; p95 frame budget held on the $100 reference phone.

### Stage 5 — "Ecosystem" (Months 19–24+)
- Production hardening, independent security audit + capability proof work
  (ADR-7), CRDT `shared sync` GA (whiteboard-scale, Phase 5 #9), spatial
  target beta, terminal renderer, governance/RFC process live (Doc 01 §6.4),
  micropayment/attribution design RFC (Doc 00 §0.2.9), benchmark suite
  published vs browser/Electron baselines.
- **Exit:** 3+ production apps by third parties; second-implementation
  feasibility study commissioned (Doc 00 §0.2.5); 1.0 spec freeze candidate.

Team shape (small on purpose): Stage 1–2 needs ~4–6 (compiler×2,
Clear×2, language-design/Docs×1, DX×1). PLAIN's LOC budget is also a
*coordination* budget.

---

# Phase 5 — Validation: 10 Test Apps

Each app is built in PL (core versions sketched in `examples/`) *and* in the
strongest incumbent for its category, then measured identically.
**Universal metrics:** LOC (source, excl. assets), cold start → interactive,
steady RAM, frame CPU (p95) during scripted interaction, on-wire/installed
size, dev-hours by a dev new to both stacks (after the 1-day PL tutorial),
and the **non-programmer read-aloud test** (% of PL source correctly
explained by a lay reader; no equivalent exists for incumbents — that's
the point). Pass bars reference Doc 02 §6.4 budgets.

| # | App | Stresses | Incumbent baseline | PL pass bar (beyond universal budgets) |
|---|---|---|---|---|
| 1 | Portfolio site | layout, type, responsive, motion | Next.js/Astro | ≤ 40% LOC; responsive with zero viewport queries |
| 2 | Todo + persistence | state, CRUD, storage | React+lib / Flutter | example `02` feature-complete; offline-first free via `keep` |
| 3 | Real-time chat | streams, lists, input | React+WS / native | `from live` only — zero socket code (example `04`) |
| 4 | Data dashboard | charts, dense layout, live data | React+chart lib | stdlib charts; 60 fps with 5 live-updating panels on $100 phone |
| 5 | Social feed, infinite scroll | perf, images, lazy load | React Native / web | 10k-item scroll, zero jank frames > 25 ms; image memory bounded |
| 6 | Code editor | text engine, highlighting, shortcuts | CodeMirror/Monaco (web) | IME+bidi correct; 100k-line file scrolls at 60 fps (shaped-run cache) |
| 7 | Video player | media, custom controls, fullscreen | web `<video>`+lib | controls are plain scene nodes; PiP/fullscreen = layout changes |
| 8 | 3D product configurator | 3D+2D state, gestures | three.js / Unity-lite | one state drives scene3d + price UI (example `08`); no engine seam |
| 9 | Collaborative whiteboard | P2P, canvas, CRDT | web + Yjs + WS server | `shared sync` only; LAN P2P with no server in path |
| 10 | Native-feel mobile app | navigation, gestures, platform fit | SwiftUI+Compose (×2 codebases) | ONE codebase; blind feel-test: users can't reliably tell from native |

**Falsification criteria (what would prove PLAIN wrong):** (a) external devs
consistently slower in PL after the tutorial day; (b) any app above needs an
escape hatch (FFI/webview) for its *core* feature; (c) $100-phone frame
budgets unachievable without per-app optimization folklore; (d) lay readers
can't explain examples better than chance. Any two ⇒ redesign the layer
responsible before Stage 5. A blueprint that can't fail is marketing;
these criteria make this one engineering.
