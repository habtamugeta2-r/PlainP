# PLAIN

> **PLAIN is a platform where you describe what you see, and it renders everywhere — plainly.**

PLAIN is a from-scratch, unified rendering platform and its native language **PL
(Plain Language)**. It is not a browser. It is not a framework. It replaces the
HTML + CSS + JavaScript + framework + bundler stack — and the write-twice
Swift/Kotlin stack, and the bundle-a-browser-per-app Electron stack — with
**one language, one runtime, one scene graph, on every device.**

Technology should be plain: plain to read, plain to write, plain to understand,
plain to run. If something in this design isn't plain, it's wrong, and it gets
simplified until it is.

---

## The 30-second pitch

```plain
component Counter:
  count = 0

  column gap 16 padding 24 align center:
    text "Count: {count}" size 32 bold
    button "Add one" on tap: count += 1
```

That is a complete, interactive, styled, accessible component. No imports. No
build step. No separate style file. No state library. A non-programmer can read
it aloud and understand it. That property — *code that reads like a description
of what you see* — is the entire design constraint of this platform.

## Names

| Name | Short | Meaning |
|---|---|---|
| **PLAIN** | — | The platform. "Technology should be plain." |
| **PL** (Plain Language) | `.plain` | The unified language: structure + style + logic. |
| **Clear** | — | The rendering engine. "Clear rendering, clear performance." |
| **Openly** | — | The package registry. "Share openly." |
| **Looking Glass** | `glass` | The dev tools / inspector. "See through your app." |

## Read the blueprint (In-to-Out order)

This repository is the architecture blueprint, organized by the **In-to-Out
principle**: one root concept, recursively decomposed until every leaf is an
actionable research answer, design decision, or implementation task.

```
PLAIN
├── docs/00-phase0-research.md ........ Phase 0 — what current platforms get
│                                        wrong, and the concrete case for PLAIN
├── docs/01-architecture.md ........... Phase 1 — the full decomposition tree:
│                                        Clear, PL, Networking, Platform,
│                                        Security, Ecosystem
├── docs/02-clear-engine.md ........... Clear rendering engine deep design
├── docs/03-pl-language-spec.md ....... PL language specification (v0.1 draft)
├── docs/04-syntax-showdown.md ........ Phase 3 — 10 core features × 5 stacks
│                                        (React / Svelte / SwiftUI / Flutter / PL)
├── docs/05-decisions-roadmap-validation.md
│   ................................... Phase 2 implementation decisions (ADRs),
│                                        Phase 4 proof-of-concept roadmap,
│                                        Phase 5 validation: 10 test apps + metrics
├── docs/06-stage1-prototype.md ....... Stage 1: the RUNNING reference
│                                        prototype — what's implemented,
│                                        grammar decisions, honest gaps
├── examples/ ......................... Canonical .plain programs (the spec
│                                        made concrete) + LOC comparisons
├── src/plainlang/ .................... Reference implementation / spec-oracle
│                                        (zero-dep Python — semantics' home)
├── rust/ ............................. Production engine port (ADR-1):
│                                        slices 1–2 (tokens/parser/checker)
│                                        green in CI — status: Doc 06 §8
├── tests/ ............................ 92 spec-oracle tests (`make test`)
│                                        + Rust parity tests in rust/tests/
└── plain ............................. The CLI: `./plain run|check|render|a11y|fmt|validate`
```

## Try it (Stage-1 prototype — actually runs)

```bash
./plain check examples/*.plain                  # all 9 examples: OK
./plain run examples/01-counter.plain           # → http://localhost:8000
./plain render examples/00-hello-world.plain --out hello.svg
./plain a11y examples/01-counter.plain          # a11y tree, derived free
make test                                       # 92 tests
```

No install, no dependencies, no build step (Doc 03 §10 honored by the
prototype itself). Edit a `.plain` file while it runs: reload applies your
edit **and keeps the app's state**.

## Design constraints (non-negotiable)

1. Not "a better browser" — make browsers obsolete for app delivery.
2. Not another JS framework — a language that makes frameworks unnecessary.
3. Synthesize the best of *all* existing systems; copy none of them.
4. Every decision justified: "better than X because Y" (concrete reason).
5. PL is learnable by a junior developer in **one day**.
6. Runs acceptably on a **$100 Android phone**.
7. **Accessibility is automatic**, never opt-in.
8. **Security is the default**, never a configuration.
9. Everything that *can* be a language primitive *is* one (near-zero deps).
10. Explainable in one sentence (see top of this file).
11. If it isn't plain, it's wrong. Simplify until it is.

## Status

Blueprint v0.1 **plus a working Stage 1–3 reference prototype** (Doc 06):
all 9 examples render and interact in the preview (type into Todo, resize
past the navbar breakpoint, search/sort the data table, navigate
Gallery→Detail→Back, configure the chair), state marked `keep` survives
restarts, and 10 grammar ambiguities the blueprint left open have been
resolved by implementation and recorded as spec amendments (Doc 06 §5).
Actions now run too: `post` / `fetch` return `ok`/`failed` results, `when`
matches them, and `then` / `show toast` execute. Requests use sidecar
fixtures or real http(s); with neither, the program gets an honest offline
sentence. Resources cache in memory (LRU) and `refresh` revalidates with
ETags; safe GETs retry transient failures with bounded backoff. Streaming
and non-tap gestures remain Stage 2–3.
The examples remain normative — every disagreement found so far was fixed
in the *implementation/spec*, never by editing an example. Plainness is
tested by reading (and now, running) real programs.

## License

See [LICENSE](LICENSE).
