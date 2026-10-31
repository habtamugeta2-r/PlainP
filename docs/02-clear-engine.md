# Clear — Rendering Engine Design

> Clear's job: turn a PL scene description into pixels at 60–120 fps on a
> $100 phone, identically on every OS, spending **zero** energy when nothing
> changed. Clear is deliberately the boring half of PLAIN (C3): proven
> techniques, no research risks, strict budgets.

```
Clear
├── 1. Scene Graph
├── 2. Layout Engine ("Flow")
├── 3. Paint Engine
├── 4. Text Engine
├── 5. Animation Engine
└── 6. Compositor & Performance Model
```

---

## 1. Scene Graph — one tree to replace DOM + render tree + layer tree

### 1.1 Node types (closed, small set — extensibility via composition)
- **Layout:** `column, row, stack, grid, scroll, spacer` (structure only)
- **Visual:** `box` (rect/rounded/gradient/border/shadow — the one primitive
  behind cards/buttons via stdlib components), `divider`, `canvas`
- **Text:** `text` (rich runs inline), `input`, `textarea` (editing built in)
- **Media:** `image, video, audio` (decode off-thread, GPU textures)
- **Control:** `button, toggle, slider, select, link` (behavior + semantics
  intrinsic — a11y derivation, §1.4)
- **3D:** `scene3d, model3d, light, camera` (same tree, §3.4)
- **Custom:** `canvas shader "..."` (WGSL fragment hook) and WASM painters
  for charts/whiteboards — first-class, capability `needs gpu-compute` for
  heavy shaders.

Components do **not** add node types; they expand to these. A closed node set
is what lets layout/paint/a11y be *complete* and fast — the opposite of the
DOM's open-ended element/plugin surface (A11 budget logic).

### 1.2 Property system
Every property is: **typed** (`Length, Color, Angle, Duration, Easing…`
Doc 03 §7.3), **reactive** ( bound to PL values via the dependency graph),
**animatable by default** (any numeric/color property can spring; §5).
Properties live in flat, cache-friendly struct-of-arrays storage per node
kind — no per-node hashmaps, no string keys at runtime (the DOM's
stringly-typed style object is a known perf trap Clear simply lacks).

### 1.3 Updates: direct mutation, no diffing (answers D5/D6)
Research verdicts:
- *Virtual-DOM diffing (React):* O(tree) allocation per update to discover
  O(few) changes; exists only because the DOM is slow and untyped.
- *Retained manual mutation (classic native toolkits):* fast, but the
  programmer hand-syncs UI to data — the original bug farm.
- *Immediate mode (ImGui, Xilem research):* delightful programming model;
  pure IM re-runs everything per frame (battery-hostile, E) and struggles
  with retained services like accessibility focus and text editing.
- **Clear's synthesis (decision):** PL programs *read* like declarative
  immediate descriptions, but the compiler emits **fine-grained bindings**:
  each dynamic property/text/branch becomes a subscription from scene node →
  signal (Solid/Svelte-5-style graph, built into the language, Doc 03 §6.1).
  State change ⇒ exactly the subscribed properties update ⇒ only affected
  layout subtrees re-measure ⇒ only dirty regions repaint. No diff, no
  re-run of component bodies for property updates, O(change) everything.
  Structural changes (list insert) splice nodes directly with keyed identity.

### 1.4 Accessibility tree — derived, never authored (answers A9; Constraint 7)
Each node kind has intrinsic semantics: `button "Save"` ⇒ role=button,
label="Save", focusable, keyboard-activatable, ≥44pt hit target enforced
(engine warns + Looking Glass flags if a style shrinks it). Headings come
from text `level`, lists from `for` structure, live regions from `from live`
resources (`announce` property opt-in per stream). Authors may *refine*
(`label "Save document"`, `hide from reader` for decoration) but can never
forget the basics — there is no `<div onClick>` to forget them on. The a11y
tree is a *view* computed from the scene graph and kept in sync by the same
bindings, then bridged to UIAccessibility / Android Accessibility / AT-SPI /
UIA. Contrast: the engine checks theme token pairs at load and warns in
plain words ("`muted` text on `paper` is 3.1:1 — needs 4.5:1").

## 2. Layout Engine — "Flow": one model that subsumes the five (answers A3/A10)

Research synthesis:
- *CSS block/float:* document-era; floats as layout was a decade-long hack.
- *Flexbox:* good 1-D distribution; confusing defaults (`flex: 1` shorthand
  traps, min-content surprises).
- *Grid:* good 2-D; separate mental model from flex, verbose track syntax.
- *Cassowary/constraint solvers (Auto Layout):* maximally general, maximally
  undebuggable ("unsatisfiable constraints" logs are famously unreadable).
- *Flutter RenderBox ("constraints go down, sizes go up, parent sets
  position"):* the cleanest core protocol in production today; single-pass,
  composable, predictable. **Flow adopts this protocol** and fixes its
  authoring ergonomics in the language layer.

**Flow rules (the whole model — fits here, unlike CSS):**
1. Parent passes **constraints** (min/max width/height) down; child returns
   a **size** within them; parent sets child **position**. Single pass,
   no solver, no second guess.
2. `column`/`row` distribute along one axis: children take `fit` (natural),
   fixed lengths, or `grow [n]` shares of free space; `gap`, `align`,
   `spread` (`start|center|end|between|around`) are the only knobs.
3. `grid columns n|auto` is Flow in 2-D (rows are columns of rows under the
   hood) — one model, two spellings, no Grid-vs-Flex choice paralysis.
4. `stack` overlays (z-order = source order); `scroll` gives infinite
   constraint on one axis + viewport culling (§6.2). Absolute positioning
   exists only inside `stack` (`at x y`, `pin edges`) — contained, never
   a global escape hatch.
5. **Responsive is inherent:** sizes like `width fill max 720`, `columns`
   driven by an `is` derivation from container width, and `when width < 600:`
   blocks *at the node* (Doc 03 §5.3). No viewport media queries; a component
   in a sidebar and the same component full-screen each adapt to the space
   *they* receive (what container queries belatedly bolted onto CSS).
6. **Writing modes first-class:** all Flow axes are logical
   (`start/end`, inline/block internally); RTL (Arabic/Hebrew) and vertical
   (CJK) flip by `direction` inherited from locale or set per subtree —
   physical `left/right` properties don't exist in PL, so RTL bugs are
   unrepresentable in the common case.
7. Text participates natively: intrinsic sizing from the text engine (§4),
   `lines max 2 ellipsis`, baseline alignment in rows — no line-height
   voodoo, no inline-block mysteries.

## 3. Paint Engine — GPU-compute 2D, unified vector/raster

### 3.1 Research verdicts
- *Skia (Chrome/Flutter-legacy):* battle-tested, but C++, large, CPU-heavy
  path processing; raster pipeline predates GPU compute.
- *Impeller (Flutter):* right idea (pre-compiled shaders, no runtime jank),
  Metal/Vulkan-only, Flutter-coupled.
- *WebRender (Servo→Firefox):* retained display lists + aggressive GPU
  batching proved document rendering can be game-engine-shaped [1](https://news.ycombinator.com/item?id=10294373);
  CSS-shaped, not reusable as-is.
- *Vello (Linebender, Rust):* GPU-compute path rendering (parallel prefix
  sums) via wgpu — reported ~177 fps on the paris-30k scene (M1 Max) and
  strong scaling with path complexity where CPU pipelines degrade
  [1](https://converter.brightcoding.dev/blog/stop-using-cpu-bound-renderers-vello-is-the-2d-gpu-secret).
  Rust (memory-safe), WebGPU-portable, embeddable. Pathfinder lineage
  similarly validated GPU text/path rendering.
- **Decision:** Clear paints via a **Vello-class GPU-compute renderer on
  wgpu** (Vulkan/Metal/DX12/WebGPU from one codebase), with an
  **analytic CPU rasterizer fallback** (tiny-skia-class) for devices whose
  GPUs/drivers fail conformance — degraded speed, identical pixels within
  tolerance. This beats "Skia because everyone does" on size, safety, and
  low-end scaling, at the cost of younger tech — mitigated by the CPU
  fallback being a fully supported profile, not an afterthought.

### 3.2 Pipeline properties
Retained display lists per layer; opaque-first Z-batching and occlusion
culling (WebRender lessons); sub-pixel AA for text, analytic AA for paths;
wide-gamut/HDR color (Color type carries space; default Display-P3-aware,
sRGB-safe fallbacks); images decoded/scaled off-thread into a GPU texture
atlas with memory-pressure eviction.

### 3.3 Shaders as citizens
`canvas shader` nodes run sandboxed WGSL (no IO, bounded loops verified) —
custom effects (blur-behind, gradients, generative art) without leaving the
scene model or breaking batching for everything else.

### 3.4 2D/3D unified
`scene3d` renders into its layer via the same wgpu device; 2D overlays
(HUD, labels) are ordinary scene siblings. No separate engine, no canvas
island (answers E-spatial). Model format: glTF (the one sane standard).

## 4. Text Engine — the make-or-break subsystem (answers A8)

- **Shaping:** HarfBuzz (the industry's one true shaping library; reusing it
  is the plain choice — shaping Arabic/Devanagari/Ge'ez correctly is not a
  place for originality) + ICU-class line breaking/bidi (Unicode UAX #9/#14).
- **One metrics truth:** fonts are bundled/subsetted by the runtime (only
  used glyphs ship/stream), so layout is *pixel-identical across OSes* —
  ending the web's per-engine text drift. Variable fonts native (`weight`
  is a continuous animatable property).
- **Rich text as data:** styled runs are values (`text` accepts parts with
  per-run props), not markup strings — no HTML parsing, no injection class.
- **Editing built in:** selection, caret, IME composition (critical for CJK
  and Ethiopic input methods), spellcheck hooks, undo — implemented once in
  Clear, inherited by every `input`/`textarea`/code editor built on them.
  (Every web code-editor re-implementing this over `contenteditable` is a
  monument to its absence as a platform primitive.)
- **Performance:** shaped-run cache keyed by (text-runs, font, size, width);
  text layout is the most expensive common op, so it is memoized hardest.

## 5. Animation Engine — physics first (answers CSS transitions/keyframes split)

- **Default motion is spring physics** (stiffness/damping presets:
  `spring gentle|snappy|bouncy`, or raw params) — springs are interruptible
  and velocity-continuous, so gesture-interrupted animations never pop
  (the CSS model restarts easing curves; physics just continues).
- **Declaration site = the property:** `animate spring` on a node animates
  *any* property change (state-, gesture-, or layout-driven) — FLIP-style
  layout animation included, free. No keyframes, no transition property
  lists, no class toggling.
- **Enter/exit** are node properties (`enter fade-up`, `exit scale 0.9 fade`),
  orchestrated by stagger on `for` lists (`stagger 30ms`).
- **Frame budgeting:** the compositor owns a per-frame budget (e.g. 8 ms of
  the 16.6 ms frame on low tier); animation system sheds non-essential work
  (blur radius, shadow quality) before dropping frames, and Looking Glass
  shows exactly what was shed. `prefers-reduced-motion` is read from the OS
  and *enforced by the engine* (springs→fades), not left to authors (A9
  logic applied to motion).

## 6. Compositor & performance model

### 6.1 Threads (program code can never jank the UI — answers A4)
- **Program isolate(s):** run PL; emit binding updates. Never block others.
- **Layout thread:** Flow passes for dirty subtrees (parallel across
  independent subtrees; layout is pure over constraints so it parallelizes
  safely — Servo's core lesson, without Servo's DOM-shaped obstacles).
- **Paint/compositor thread (the only one on the vsync critical path):**
  builds display lists for dirty layers, submits GPU work; scroll and
  gesture transforms are compositor-only (no layout/paint round-trip), so
  scrolling stays 60/120 fps even while program code churns.
- **IO/decode workers:** network, image/video decode, font subsetting.

### 6.2 Culling & memory
Occlusion culling + viewport culling in `scroll` (off-screen list items cost
nothing — virtualized lists are the *only* kind; no `react-window` library
needed); layer promotion is automatic and introspectable; hard texture/atlas
budgets with LRU eviction keep the $100-phone profile inside ~80 MB.

### 6.3 Energy (answers E)
Idle = literally no frames scheduled (vsync callback disarmed until a
binding fires, animation starts, or input arrives). Dirty-region repaint
means a one-digit clock update repaints one digit's rect. Timers in PL are
declared resources (`every 1s`), coalesced by the runtime — no hidden
`setInterval` battery leaks.

### 6.4 Performance budgets (enforced in CI on a reference $100 device)
| Metric | Budget | Typical web/Electron today |
|---|---|---|
| Cold start → interactive (cached runtime) | < 500 ms | 2–5 s |
| Frame CPU (layout+paint, typical app scene) | < 4 ms | 8–20 ms with GC/diff spikes |
| Idle CPU / wakeups | 0 | nonzero (timers, GC, extensions) |
| Per-app RAM (typical) | < 80 MB | 200–400 MB (Electron/WebView) |
| Program size on wire (typical app) | 10–200 KB | 0.5–3 MB JS + assets |
| Runtime install (once, shared) | < 25 MB | 150–300 MB *per Electron app* |
