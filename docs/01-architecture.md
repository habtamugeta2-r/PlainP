# Phase 1 — PLAIN Architecture (In-to-Out Decomposition)

> One root concept: **a program is a description of what you see; the
> platform keeps pixels, behavior, accessibility, and sync true to that
> description, on every device.** Everything below exists because that
> sentence requires it. Every leaf states: research finding → design
> decision → implementation approach. Detail lives in Doc 02 (Clear),
> Doc 03 (PL), Doc 05 (ADRs/roadmap).

```
PLAIN (The Platform)
├── 1. Clear — Rendering Engine .................. deep design: Doc 02
├── 2. PL — Plain Language ....................... spec: Doc 03
├── 3. Networking Layer .......................... §3 below
├── 4. Platform Integration ...................... §4 below
├── 5. Security Model ............................ §5 below
└── 6. Ecosystem ................................. §6 below
```

---

## 1. Clear — Rendering Engine (summary; full design in Doc 02)

```
1. Clear
├── 1.1 Scene Graph (ONE unified visual tree — no DOM)
│   ├── 1.1.1 Node types: Visual, Layout, Text, Media, 3D, Custom(shader)
│   ├── 1.1.2 Properties: typed, reactive, animatable by default
│   ├── 1.1.3 Updates: DIRECT fine-grained mutation (no diffing — D5/D6)
│   └── 1.1.4 Accessibility tree DERIVED from scene graph (A9)
├── 1.2 Layout Engine — one model: FLOW (constraints down, sizes up)
├── 1.3 Paint Engine — GPU-compute 2D (Vello-class) on wgpu; CPU fallback
├── 1.4 Text Engine — HarfBuzz shaping, one metrics truth everywhere
├── 1.5 Animation Engine — springs by default, frame-budgeted, interruptible
└── 1.6 Compositor — multi-threaded, dirty-region, zero-work idle
```

Key decisions (rationale in Doc 02 / Doc 05): retained scene graph with
*immediate-mode-style authoring* (PL re-describes cheaply; runtime applies
surgical mutations — synthesis of WebRender's retained batching and
ImGui/Xilem's simple programming model); layout separate thread from paint;
wgpu backends (Vulkan/Metal/DX12/WebGPU) with a high-quality CPU raster
fallback for bottom-tier GPUs (Constraint 6).

## 2. PL — Plain Language (summary; full spec in Doc 03)

```
2. PL
├── 2.1 Philosophy: unified, readable-aloud, typed-but-inferred,
│       reactive-by-default, no build step, no ceremony
├── 2.2 Syntax: indentation structure + co-located style + plain logic
├── 2.3 Type system: structural, gradual-at-edges, UI-native types
├── 2.4 Modules: URL/Openly imports, fat stdlib, no node_modules
├── 2.5 Runtime: bytecode VM → JIT/AOT tiers, GC tuned for UI, sandboxed
└── 2.6 DX: zero-config `plain run`, hot state reload, Elm-class errors, LSP
```

## 3. Networking Layer

```
3. Networking
├── 3.1 Content & data loading
│   ├── Research: fetch+React-Query/SWR (cache/retry/dedupe as a library
│   │   *because* the platform lacks a data model), GraphQL (client-shaped
│   │   queries; heavy toolchain), tRPC (type sharing; TS-only), gRPC
│   │   (efficient; unfriendly tooling)
│   ├── Decision: data is a LANGUAGE primitive: `posts from "/api/posts"`
│   │   yields a Resource with loading/ready/failed states; the RUNTIME
│   │   owns caching, dedupe, retry-with-backoff, revalidation, offline
│   │   queue, optimistic mutation (`on tap: posts add draft, sync`)
│   └── Implementation: runtime cache keyed by (capability, address, accept);
│       responses validated against inferred/declared PL types at the
│       boundary (fixes TS's erased-types hole, D2); stale-while-revalidate
│       default; mutations are queued ops, replayed when online.
├── 3.2 Real-time & peer-to-peer
│   ├── Research: WebSockets (raw pipe; every app reinvents protocol),
│   │   WebRTC (powerful, notoriously complex), libp2p/IPFS (decentralized,
│   │   heavy), Yjs/Automerge CRDTs (proven local-first sync algorithms)
│   ├── Decision: two primitives cover 95%: `from live <address>` (streaming
│   │   resource: chat, feeds, AI token streams, sensors) and `shared` state
│   │   with `sync` (CRDT-backed multi-writer docs: whiteboards, docs).
│   │   Direct P2P (WebRTC-class transport) is the default data path for
│   │   `shared` when peers are co-located; relay fallback otherwise.
│   └── Implementation: CRDT types in stdlib (`SharedList`, `SharedText`,
│       `SharedMap`) with the same PL syntax as local ones; presence as a
│       stdlib value (`peers here`); all sync E2E-encrypted by capability keys.
└── 3.3 Protocol & distribution
    ├── Research: HTTP/3+QUIC (ubiquitous, multiplexed, encrypted), custom
    │   binary protocols (marginal gains, ecosystem cost), content addressing
    │   (IPFS: integrity for free, availability challenges)
    ├── Decision: ride HTTPS/QUIC for transport (don't fight the network),
    │   but address PROGRAMS by content: `plain://name@version` resolves to
    │   a signed manifest + content hash. Location can move; identity can't
    │   be spoofed. Updates = new hash, atomically swapped (0.2 §6).
    └── Implementation: manifest (needs, entry, hash, signature) fetched
        first; bytecode/source streamed + cached forever by hash; mirrors/CDNs
        are untrusted caches because hashes verify content.
```

## 4. Platform Integration

```
4. Platform Integration
├── 4.1 OS integration (all capability-gated — §5)
│   ├── Files: per-app sandbox dir + user-picked files via system picker
│   │   (the picker IS the permission — no broad fs access by default)
│   ├── Notifications, clipboard, share sheet, drag-and-drop: stdlib calls,
│   │   each a declared capability; clipboard read requires user gesture
│   ├── Windows/tray/menus: `window`, `menu`, `tray` nodes in the same
│   │   scene model (desktop is not a second-class target)
│   └── Hardware: camera/mic as `from live camera` streams; sensors as
│       resources; GPU compute via `canvas shader` for custom effects
│       (research base: Electron APIs' breadth, Tauri's allowlist proof
│       that capability lists work, Project Fugu's web-capability backlog)
├── 4.2 Cross-platform rendering targets
│   ├── Desktop (Win/macOS/Linux): native windows, wgpu; ONE shared runtime
│   │   install (<25 MB), apps are KBs — the anti-Electron (C1)
│   ├── Mobile (iOS/Android): same Clear engine in a native shell; NOT a
│   │   WebView; platform text-editing/IME + accessibility services bridged
│   │   (learn from Flutter's drift: text input & a11y use OS services,
│   │   pixels & layout are ours)
│   ├── Embedded/IoT/automotive: Clear CPU-fallback profile, fixed-heap mode
│   ├── Spatial/AR/VR: `scene3d` subtree presented stereoscopically; 2D
│   │   panels are scene nodes in space (E: 3D as extension, not island)
│   └── Terminal: degraded renderer maps scene → TUI (text/buttons/lists
│       survive; media degrades to placeholders) — same program, honest floor
└── 4.3 Interop
    ├── PLAIN-in-web (adoption bridge, 0.2 §7): PL → WASM+WebGPU exporter;
    │   a PLAIN component embeds in an existing page as one custom element
    ├── Web-in-PLAIN (legacy bridge): host-OS `webview` node, sandboxed,
    │   no scene-graph access; clearly marked deprecated path
    ├── FFI: Rust/C libraries via signed native modules (capability:
    │   `needs native libname`), kept out-of-process where feasible
    └── WASM: both a compile target (export) and the plugin format for
        untrusted extensions (WASI-style capability imports mirror §5)
```

## 5. Security Model

```
5. Security (default-deny; capabilities, not origins — 0.2 §8)
├── 5.1 Capabilities
│   ├── Research: Deno flags (proof devs accept explicit grants), iOS
│   │   permissions (proof users understand per-capability prompts),
│   │   Android install-time bundles (anti-pattern: all-or-nothing fatigue)
│   ├── Decision: program header declares `needs` in plain words; runtime
│   │   shows them verbatim before first run; grant = per-capability,
│   │   revocable anytime, narrowable (network to ONE host, files to ONE
│   │   picked folder). No declaration → capability doesn't exist in the
│   │   program's world (no global fetch/storage to abuse — A6)
│   └── Implementation: capabilities are unforgeable handle values injected
│       by the runtime; stdlib network/fs APIs REQUIRE a handle parameter
│       in their (internal) signatures, so ambient authority is
│       unrepresentable, not merely discouraged.
├── 5.2 Sandboxing
│   ├── Decision: PL is memory-safe by construction (no pointers, no FFI in
│   │   the safe subset); each program runs in its own isolate (V8-isolate /
│   │   Workers-class density) inside a per-program process on desktop;
│   │   native modules out-of-process. Chrome's multi-process lesson kept,
│   │   its per-process browser-stack weight dropped.
│   └── Implementation: bytecode verifier (typed, bounded) before execution;
│       CPU/memory quotas per program; watchdog kills runaway isolates
│       without touching the compositor (UI thread can never be blocked
│       by program code — A4 event-loop failure designed out).
└── 5.3 Content trust & supply chain
    ├── All programs/modules signed; hashes pinned in `use` lines
    │   automatically on first fetch (trust-on-first-use made visible);
    │   no install scripts (the npm left-pad/postinstall class is
    │   unrepresentable: modules are pure PL/WASM with declared needs)
    └── Reproducible bytecode builds; Openly (§6.2) rebuilds from source
        and refuses mismatches.
```

## 6. Ecosystem

```
6. Ecosystem
├── 6.1 Standard library ("batteries" — the anti-node_modules, D3/D4)
│   ├── UI: full control set (button/input/select/slider/toggle/table/
│   │   tabs/dialog/toast/menu/chart basics) as PL components in stdlib,
│   │   themeable via tokens, accessible by derivation (A9)
│   ├── Data: List/Map/Set + persistent collections, Shared* CRDT set (§3.2)
│   ├── Time: one `Moment`/`Duration`/`Calendar` API (research: JS Date's
│   │   failures → Moment → Temporal; ship Temporal-class correctness first)
│   ├── I18n as primitive: `text "Hello" in user-language` with message
│   │   catalogs as PL data; plural/gender rules (ICU-class) in runtime;
│   │   RTL/vertical handled by layout (Doc 02 §2.4), incl. Ge'ez/Amharic
│   ├── Crypto: hashes, signatures, secure random, key storage (OS keychain)
│   └── Testing built in: `check "adds": ...` blocks run by `plain test`;
│       scene snapshots + interaction simulation, no test-runner ecosystem
├── 6.2 Openly — registry
│   ├── Research: npm (scale, but flat namespace + install scripts + typosquat
│   │   disasters), crates.io (immutable versions, good hygiene), pub.dev
│   │   (scoring works), Go modules (minimal version selection sanity)
│   ├── Decision: centralized index, decentralized (mirrorable) storage;
│   │   scoped names (`openly:@author/name`), immutable versions, semver
│   │   enforced by API-diff at publish, quality score (tests? docs? needs
│   │   minimal?) shown in `plain add` output; modules are components first
│   └── Anti-goal: stdlib is so complete that the median app has 0–3 deps
├── 6.3 Looking Glass — dev tools (built into runtime, not extensions)
│   ├── Scene inspector: click a pixel → the PL line that made it (impossible
│   │   in browser DevTools' DOM↔source guessing game; trivial when the
│   │   scene graph carries source spans — designed in from Stage 1)
│   ├── Profiler: per-frame layout/paint/composite budget view; "why did
│   │   this repaint?" answered by the reactive dependency graph
│   ├── State time-travel: every state change is a logged transition
│   │   (free from the reactive runtime); scrub history, UI follows
│   ├── Network/resource inspector: every `from` resource's cache/state
│   └── Design bridge: import Figma/Penpot frames → PL skeleton (tokens +
│       layout), export PL theme → design tokens (both are PL data)
└── 6.4 Governance
    ├── Open spec + reference implementation (this repo's trajectory);
    │   foundation stewardship (Rust Foundation / Linux Foundation model);
    │   RFC process with the Plain Test (Doc 03 §11) as a formal gate
    └── Funding without capture: grants + hosted-Openly/enterprise support;
        no single sponsor >20% of budget; spec changes require two
        independent implementations' sign-off once a second exists (0.2 §5)
```

## Cross-cutting invariants (apply at every level of the tree)

1. **One tree** (scene), **one language** (PL), **one layout model** (Flow),
   **one module system**, **one way** to do each common thing.
2. **Locality:** any change's effect is bounded by its reactive dependencies;
   nothing global is ever recomputed "just in case."
3. **Zero-work idle:** no timers, no polling, no re-render without a
   state/resource event (battery, E).
4. **Source spans everywhere:** every scene node knows the PL line that
   created it (makes Looking Glass, errors, and AI tooling trivially good).
5. **Budgets as architecture:** engine+runtime < 500k LOC (A11), runtime
   install < 25 MB (C1), frame CPU < 4 ms typical (0.2 §2). Budgets are
   reviewed like APIs.
