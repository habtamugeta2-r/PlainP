# Phase 0 — Deep Research & Problem Analysis

> Purpose: prove, exhaustively and specifically, that the current platform
> stack is broken in ways that cannot be patched — and that a replacement can
> win. No design decision in later phases is allowed to exist without a
> failure documented here that it answers.

```
PHASE 0
├── 0.1 What current platforms get wrong
│   ├── A. Web browsers
│   ├── B. Mobile platforms
│   ├── C. Desktop platforms
│   ├── D. The language problem
│   └── E. What the current era demands (and doesn't get)
└── 0.2 What would make a new platform SUCCEED (10 concrete theses)
```

---

## 0.1 What current platforms get wrong

### A. Web browsers (Chrome, Firefox, Safari, Edge)

**A1. The rendering pipeline is an accident of history, not a design.**
DOM → CSSOM → render tree → layout → paint → composite exists because the web
started as *documents* (1993) and accreted app capabilities for 30 years. Each
stage is a separate tree, separately invalidated, separately traversed. A
single style change can force style recalculation over the whole document,
because CSS selectors can match *anywhere* (`.a .b > :nth-child(2)`), so the
engine can never prove a subtree is unaffected. This is why "layout thrash"
exists: reading `offsetHeight` after a write forces a synchronous full layout.
*Leaf — design demand:* PLAIN must have **one tree** and **local invalidation**
(a change's blast radius must be provable from the code, not discovered at
runtime). → Clear scene graph, Doc 02 §1.

**A2. The DOM is a second program you must keep in sync by hand.**
The DOM is neither your data nor your pixels; it is a retained, mutable,
stringly-typed tree in between. Every framework in existence is fundamentally
a DOM-synchronization strategy (virtual DOM diffing, Svelte's compiled
mutations, signals). Developers pay twice: once to describe UI, once to
reconcile it. The DOM API itself (`document.createElement`,
`appendChild`, classList string juggling) was designed for 1990s document
scripts like image rollovers, not applications.
*Leaf — design demand:* no DOM, no reconciliation tax. The scene graph **is**
the visual output; PL compiles descriptions *directly* to scene mutations.
→ Doc 02 §1.3, Doc 04 Feature 1.

**A3. CSS is a global, unscoped, cascade-resolved styling language bolted onto
structure.**
Specificity wars, `!important`, source-order dependence, inheritance surprises,
and "which file styles this element?" archaeology are not developer error —
they are the inevitable result of styles living in a *different language, in
different files, applied by pattern-matching over a global tree*. The industry
has spent 15 years inventing escapes: BEM naming conventions, CSS Modules,
CSS-in-JS, Tailwind, StyleX, shadow DOM. Each escape proves the base model is
wrong. Layout in CSS is five overlapping systems (block, inline, float,
flexbox, grid, absolute) with mutually surprising interactions — "how do I
center a div?" remained a genuine question for ~20 years.
*Leaf — design demand:* styles **co-located** on the node, **scoped by
construction** (there is no global namespace to leak into), **one layout
model**. No cascade because there is exactly one author of each property.
→ Doc 03 §4–5.

**A4. JavaScript was designed in 10 days (May 1995) for form validation, and
it shows in permanent ways.**
- `this` changes meaning by call site; arrow functions exist as a patch.
- Coercion: `[] + {}`, `==` transitivity failures, `typeof null === "object"`.
- Two nils (`null` *and* `undefined`) plus `NaN !== NaN`.
- Prototypal inheritance confused a generation; `class` is sugar that hides it
  without fixing it.
- Async evolved through three eras (callbacks → Promises → async/await) and
  still *colors* every function: an async function poisons its callers.
- The single-threaded event loop means one slow handler freezes input,
  rendering, and animation simultaneously.
- Module fragmentation: CommonJS vs ESM vs AMD/UMD — files still can't always
  tell which system they're in (`.mjs`/`.cjs` extensions exist as an apology).
- Numbers: one float type, so `0.1 + 0.2 !== 0.3` in money code, patched by
  bolting on BigInt that refuses to mix with Number.
  *Leaf — design demand:* no `this`, no coercion, no null, invisible async,
  one module system. A language designed *for UI* in one deliberate pass.
  → Doc 03 §6.

**A5. Three languages for one visual output is the root defect.**
HTML says what's there, CSS (elsewhere) says how it looks, JS (elsewhere
again) says what it does. A button's label, color, and click behavior — three
facts about *one thing* — live in three files, three syntaxes, three mental
models, joined by stringly-typed class names and ids that no compiler checks.
Rename a class in HTML and CSS silently stops applying. This is the single
largest source of accidental complexity in frontend development.
*Leaf — design demand:* **one syntax** where a thing, its look, and its
behavior are written in one place, checked as one program. → Doc 03 §2.

**A6. The browser security model is complex *and* leaky.**
Same-origin policy + CORS + CSP + cookies/SameSite + XSS + CSRF form a
layered defense around a fundamentally ambient-authority runtime: any script
on the page can `fetch` anywhere, read all page storage, and exfiltrate.
CORS is so misunderstood that "CORS error" is a rite of passage; CSP is so
painful most sites ship weak policies. XSS remains endemic after 25 years
because HTML conflates code and data in one string stream.
*Leaf — design demand:* capability-based security, no ambient authority, and
a language where user data can never be parsed as code (no string-built UI).
→ Doc 01 §5, Doc 05 ADR-7.

**A7. Web apps feel slow on hardware 1000× faster than 1995's because the
stack eats the gains.**
Median web page weight is ~2.5 MB; typical SPA ships megabytes of JS that must
be parsed on the main thread before first interaction. Framework + router +
state + date + HTTP libraries are re-downloaded for *every site* (no shared
standard library). Hydration re-runs the app on the client to reconstruct what
the server already rendered. Meanwhile the engine underneath must stay
compatible with every page ever written, so hot paths carry decades of
spec-compliance branches.
*Leaf — design demand:* fat standard library shipped *with the runtime*
(downloaded once, ever), no hydration (server sends scene state, not markup
to re-execute), small programs. → Doc 01 §3, §6.

**A8. Text — the web's original job — is still inconsistent.**
Font loading causes FOUT/FOIT; `font-display` is a patch. Line-breaking,
hyphenation, sub-pixel rendering, and emoji metrics differ per engine.
Variable fonts, complex-script shaping (Arabic, Devanagari, Ethiopic), and
bidi text work *mostly*, via HarfBuzz under the hood, but developers get
almost no control and inconsistent results. A $100 phone in Addis Ababa
rendering Amharic (Ge'ez script) is an afterthought in a Western-centric
pipeline. *Leaf — design demand:* one text engine, HarfBuzz-class shaping,
identical metrics on every platform, fonts subsetted/streamed by the runtime.
→ Doc 02 §4.

**A9. Accessibility is a parallel universe (ARIA) instead of a property of the
UI.** A `<div onClick>` is invisible to a screen reader until a developer
manually adds role, tabindex, aria-label, and key handlers — so most don't.
WebAIM's annual survey consistently finds ~95%+ of home pages have detectable
WCAG failures. The information needed (this is a button, this is its label,
this is its state) *already exists in the code*; the platform just throws it
away and asks developers to re-state it. *Leaf — design demand:* the
accessibility tree is **derived from the scene graph automatically**; a
`button "Save"` is accessible on the day it's written, with zero extra code.
→ Doc 02 §1.4. (Constraint 7.)

**A10. Responsive design is a declarative patch (media queries) on a rigid
model.** Media queries ask about the *viewport*, when components actually care
about *their own container* (container queries arrived in 2023 — 28 years in —
and still require duplicated rule blocks). Breakpoints scatter one component's
layout logic across multiple distant rule sets. *Leaf — design demand:*
container-aware layout as the default; a node adapts to the space it is
*given*, expressed inline where the node is defined. → Doc 03 §5.3.

**A11. The weight: Chromium is ~35M+ lines of code.** Commonly reported
figures for the full Chromium tree (including third_party) run 25–36M LOC;
even conservative counts of first-party code exceed 10M. Why? It must
implement 30 years of web specs (HTML, CSS, JS, WebGL, WebGPU, WebRTC,
WebUSB…), three+ rendering paths, a multi-process sandbox, an extension
platform, a media stack, and bug-for-bug compatibility with the entire
existing web. That mass is *mostly not* "rendering UI well" — it is the cost
of never being allowed to say no. **Lesson for PLAIN:** a tight, opinionated
surface ("one way to do each thing") is a performance and security feature.
PLAIN's core budget: **< 500k LOC for engine + runtime**, enforced as an
architectural constraint (Doc 05 ADR-1). If a feature can't fit the budget,
it doesn't ship.

### B. Mobile platforms (iOS/Android)

**B1. Write-twice is the default.** Swift/SwiftUI and Kotlin/Compose are both
*good* — and mutually unusable. Businesses pay 2× engineering, then pay again
to keep features and bugs in parity. This is a platform-vendor outcome
(lock-in is profitable for Apple/Google), not a technical necessity.

**B2. Every cross-platform answer compromises somewhere.**
- *React Native:* JS↔native bridge (largely fixed by the new architecture/JSI,
  after a decade), still two mental models (JS + native modules), still
  JS's language flaws, still npm.
- *Flutter:* the closest existing proof that PLAIN's thesis works — own
  renderer (Skia, now Impeller), one language, consistent pixels everywhere.
  What it gets **right**: retained widget tree, hot reload, "constraints go
  down, sizes go up" layout, no OEM widget roulette. What it gets **wrong**:
  Dart is a general-purpose language with UI bolted on, so UI code is deeply
  nested constructor calls with trailing commas and `Widget` ceremony;
  state management was left to the community (Provider, Riverpod, Bloc,
  GetX — an entire sub-industry proving the core model is incomplete);
  widget/element/render-object is *three* trees; platform feel (scroll
  physics, text selection, accessibility) must be re-created per platform
  and periodically drifts.
- *.NET MAUI / Xamarin lineage:* abstraction over native widgets = lowest
  common denominator + per-platform quirks leaking through.
  *Leaf — design demand:* keep Flutter's "own the pixels" insight, fix the
  language (UI-first syntax, not constructor nesting) and make state a
  language feature so no state-library ecosystem is ever needed.

**B3. App stores are gatekept distribution.** 15–30% tax, opaque review,
days-long update latency, regional censorship leverage. The web's one true
victory — *a link is an app* — must be preserved by any successor.
*Leaf — design demand:* PLAIN programs distribute by **address** (URL-style
links, QR codes, messages) and run instantly in the sandbox; installation is
optional caching, not permission. → Doc 01 §3.3, §6.2.

**B4. Mobile state management is still unsolved in the small.** SwiftUI's
`@State/@StateObject/@ObservedObject/@EnvironmentObject` (four spellings of
related ideas, with famous footguns like `@StateObject` in a conditional) and
Compose's `remember/mutableStateOf/derivedStateOf` (positional memoization
that breaks intuitions when control flow moves) both prove: bolting reactivity
onto a non-reactive language produces annotation soup. *Leaf — design demand:*
reactivity is what variables *are* in PL; there is no annotation because
there is nothing to opt into. → Doc 03 §6.1, Doc 04 Feature 1/4.

### C. Desktop platforms (Electron, Tauri, Qt, GTK, WPF…)

**C1. Electron bundles a browser per app** (~150–300 MB installed per app,
hundreds of MB RAM at idle) because the *real* product developers want is
"one codebase, decent UI, ships everywhere" and the web stack is the only
practical way to get it. Ten Electron apps = ten Chromium instances. Users
pay in disk, RAM, and battery for a distribution failure.
*Leaf — design demand:* the PLAIN runtime is a **single shared system
runtime** (target < 25 MB installed); apps are kilobytes of `.plain` source
(or compiled bytecode). One engine on the device, like a JVM that actually
won. → Doc 01 §4.2.

**C2. Native desktop UI is fragmented** across WinUI/WPF, AppKit/SwiftUI, GTK,
Qt — five incompatible answers, so serious cross-platform products (VS Code,
Slack, Discord, Spotify, Figma) all embed web tech. The market has already
voted: *write-once UI wins; the web is just the worst possible implementation
of it that happens to exist.* *Leaf:* PLAIN doesn't need to convince anyone
write-once is good — only that it can be done without the browser tax.

**C3. Why has no unified native-performance engine won yet?** Because previous
attempts kept one foot in the old world: JavaFX/Swing (looked alien, slow
start), Qt (licensing + C++ barrier), Flutter desktop (mobile-first idioms),
WebViews (see A1–A11). The missing piece was never rendering — GPUs solved
that — it was a *language* pleasant enough to displace HTML/CSS/JS habits.
That is why PL, not Clear, is PLAIN's actual product. Clear just has to be
fast and boring. → Doc 05 ADR-2.

### D. The language problem

**D1. Every platform having its own language is vendor economics, not
engineering.** JS (web), Swift (Apple), Kotlin (Google/Android), C#/C++
(desktop) partition the developer population into non-transferable skill
silos. A developer's *UI knowledge* — layout, state, interaction — is
universal; only syntax and APIs differ. PLAIN captures the universal part once.

**D2. TypeScript's existence proves** developers will adopt an entire extra
compile step, type-language-within-a-language (itself Turing-complete), and
`any`-leakage — purely to get the safety JS should have had. But TS types are
erased at runtime, so the safety is advisory at exactly the boundary (network
JSON) where bugs live. *Leaf:* PL is typed *in the runtime*, inferred almost
everywhere, and validates at boundaries automatically. → Doc 03 §7.

**D3. Build tools prove the platform can't run its own language.** Webpack,
Vite, Babel, SWC, esbuild, PostCSS, Sass (D4) exist because: browsers lag the
JS spec (transpile), CSS lacks variables/nesting for a decade (preprocess),
modules don't load efficiently (bundle), TS must be erased (compile). A new
developer runs `create-react-app`/Vite and inherits ~200 MB of `node_modules`
and 6 config files before writing line one. Every layer is a confession.
*Leaf — design demand:* **no build step, ever.** `plain run app.plain`. The
runtime is the only tool. (Production AOT is an optional, invisible
optimization by the runtime itself, not a user-run pipeline.) → Doc 03 §9–10.

**D5. State libraries (Redux, MobX, Zustand, Pinia, signals…) prove the
rendering model has no theory of change.** React re-renders whole component
functions and diffs virtual trees because the platform gives it no fine-grained
notion of "this value changed." Fine-grained signals (Solid, Svelte 5 runes,
Vue refs) converge on the right answer from three directions: *track values,
not trees.* *Leaf:* PL builds signal-style fine-grained reactivity into the
language semantics — no library, no virtual tree, no diff. → Doc 03 §6.1.

**D6. Virtual DOMs and compile-away frameworks prove the real DOM is the
problem** (slow, untyped, string-based). React diffs to avoid touching it;
Svelte/Solid compile to surgical DOM ops to avoid diffing. Both are
workarounds for a target PLAIN simply doesn't have. When your render target
is your own scene graph, designed with the language, both workarounds
evaporate. → Doc 02 §1.3.

### E. What the current era demands (and current platforms don't give)

| Demand | Today's answer | PLAIN's answer (where designed) |
|---|---|---|
| AI-native / generative, streaming UI | Streamed tokens → markdown → DOM hackery; "generative UI" re-invented per app | Streams are a data primitive (`from live`); UI is data-driven scene description a model can emit/partially update safely (capability-sandboxed). Doc 03 §6.5 |
| Real-time collaboration | WebSocket + hand-rolled OT/CRDT library per app | Local-first sync as a stdlib/behavior (`shared` + `sync`), CRDT-backed. Doc 01 §3.2 |
| 3D / spatial | Separate engine (Unity/WebGL canvas island) | `scene3d` is a node in the same tree; 2D↔3D share layout/state. Doc 02 §3.4 |
| Offline-first / edge | Service workers (notorious), manual cache surgery | Programs + data cached by runtime; `keep`/resources work offline by default. Doc 01 §3.1 |
| Accessibility | Compliance checkbox (A9) | Automatic from scene graph. Doc 02 §1.4 |
| Low-end devices ("next billion") | 2.5 MB pages on 2 GB-RAM phones | KB-sized programs, shared runtime, frame budgeting, GPU-compute 2D with CPU fallback. Constraint 6, Doc 02 §6 |
| Energy | Browser = #1 battery consumer; JS parse + layout storms | No diff, dirty-region repaint only, idle = zero work (no timers unless declared). Doc 02 §6.3 |

---

## 0.2 What would make PLAIN succeed — the concrete case

**1. Developer adoption curve / the exodus trigger.** Developers don't switch
for purity; they switch when the *first hour* is dramatically better
(Tailwind, Vite, Flutter all won on first-hour feel). PLAIN's trigger:
`plain run` on a file you wrote in 10 minutes that would have been a
3-file, 400-dependency Vite project — and it runs on your phone from a QR
code. Target metric: **time-to-first-interactive-app < 15 minutes from
zero** (install included). Every design choice that adds a concept must
justify itself against this metric.

**2. Performance thesis (quantified).** Removing (a) HTML/CSS parsing,
(b) style recalculation over global selectors, (c) virtual-DOM allocation +
diffing, (d) JS parse of megabyte bundles, and (e) layout thrash leaves a
pipeline where a state change touches O(changed nodes), not O(tree).
Realistic targets vs a React SPA on a $100 Android (Mediatek Helio-class,
3 GB RAM): **cold start to interactive < 500 ms** (vs 2–5 s), **steady-state
frame cost < 4 ms CPU** for typical app scenes, **idle RAM < 80 MB per app**
(vs 200–400 MB per Electron/WebView app). What becomes possible: 60 fps
apps on devices the modern web has effectively abandoned — which is most of
the world's phones.

**3. Simplicity thesis.** HTML+CSS+JS+React+TS+tooling is realistically
3–6 months to junior competence. PL's surface (Doc 03) is deliberately
~30 node kinds, ~40 properties, ~15 keywords — learnable in a day because
it *removes* categories (selectors, cascade, hooks rules, bundler config,
`this`, module systems) rather than adding a new spelling for them.
Economic impact: the addressable developer pool expands to designers,
domain experts, and the Global South developers for whom a 6-month runway
is not affordable. (PL's examples must pass the read-aloud test, Doc 03 §11.)

**4. Unification thesis — what disappears.** One PL file replaces:
`.html`, `.css`, `.js/.tsx`, framework, router, state lib, CSS solution,
`package.json`, bundler config, transpiler config, tsconfig, ESLint/Prettier
(one canonical formatter built in). Rough count for a typical Vite+React+TS
template: **7–10 config files and 30+ direct dependencies before app code.**
PLAIN: **0 config files, 0 required dependencies.** Tooling doesn't get
better; it *evaporates*.

**5. Platform economics.** Chrome's ~65–70% share means one vendor
(Google, an ads company) effectively vetoes web evolution (cf. JPEG XL
removal, FLoC/Topics, Web Environment Integrity proposal). PLAIN's counter
is structural, not rhetorical: an open spec (Doc 03) + open runtime +
foundation governance (Doc 01 §6.4) so no single vendor can capture it.
The engine is intentionally small enough (A11 budget) that a second
implementation is *feasible* — the property the web lost around 2017 when
only 3 engines remained and one funds the others' ecosystems.

**6. Distribution without stores or browser chrome.** A PLAIN program is
addressed (`plain://` link / https URL / QR), fetched (KBs), verified
(signed, hash-checked), and run in the sandbox — the web's distribution
with native's performance. "Installing" = pinning to the home surface; it's
caching, not a gate. Updates are instant and atomic (content-addressed
versions), killing the store-review bottleneck *and* the web's
stale-cache problem. → Doc 01 §3.3.

**7. Backward compatibility — deliberately *not* rendering the web.**
Research analogies: WINE (API reimplementation — decades, still partial),
WSL (Microsoft gave up on translation, shipped a real kernel), Rosetta 2
(binary translation worked because Apple controlled the hardware transition
and time-boxed it). Conclusion: embedding a web engine makes PLAIN *into*
the thing it replaces (size, security surface, complexity). PLAIN's bridge
is one-directional and time-boxed: (a) an *optional, sandboxed* `webview`
node provided by the host OS for legacy content, clearly fenced; (b) a
PLAIN-to-web **exporter** (compile PL → HTML/CSS/WASM) so PLAIN components
can live inside today's web during transition — PLAIN invades the web,
not vice versa. → Doc 01 §4.3.

**8. Simpler *and* stronger security.** Replace origin-based ambient
authority with **capabilities**: a program declares needs in plain words
(`needs network api.example.com, camera`) in its header; the runtime grants
exactly those, revocably; default is *nothing* (render + local state only).
No CORS (requests are pre-authorized by declared capability, not retro-
permitted by server headers), no XSS class (UI is never built from strings;
interpolated values are text values, typed), no cookie CSRF (no ambient
credentials; auth tokens are capability handles the program can't leak to
scripts it doesn't have). → Doc 01 §5.

**9. Creator monetization the web never built.** Because programs are
signed and content is addressable, attribution and payment can be runtime
services: `pay creator 0.02 for article` as a stdlib call settling over
whatever rails the user configured (the runtime is rail-agnostic).
Micropayments failed on the web due to per-site friction (accounts, cards);
a platform-level wallet removes exactly that friction. (Design sketch only
in v0.1; flagged Stage 5, Doc 05.)

**10. The "iPhone moment" — why a *user* opens PLAIN.** Not ideology:
(a) an app from a QR code on a café table opens **instantly**, full-screen,
offline-capable, and weighs less than one photo; (b) on a cheap phone it is
*visibly* smoother than the same service's website; (c) permissions are
readable sentences, so trust is possible. The killer demo is a side-by-side
on a $100 phone: the web version janks through 3 s of spinners; the PLAIN
version is simply *there*. Speed on cheap hardware is the feature no
incumbent can copy without abandoning their stack.

> **Phase 0 conclusion.** The failures above are not bugs; they are
> load-bearing consequences of three historical accidents: documents-first
> rendering (A1–A3), a scripting language never designed for UI (A4–A5),
> and vendor-partitioned platforms (B–D). Patching has had 30 years and
> produced preprocessors, transpilers, virtual DOMs, and ARIA — an entire
> economy of workarounds. A clean-slate, language-first platform is not
> a luxury; it is the only move left that removes categories of problems
> instead of managing them.
