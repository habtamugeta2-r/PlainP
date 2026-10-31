# PlainP — Active Roadmap & Engineering Triage

> **Single Source of Truth Policy**
> - **Active sprint queue, owners, dependencies, and status updates** are tracked in **Linear** under project **PlainP — PLAIN Platform & PL** (`HAB-69`..`HAB-84`).
> - **This file (`TODO.md`)** is the concise, repo-resident priority board kept in lockstep with Linear.
> - **Granular subsystem checklists (all 272 items across Stages 1–5)** live in [`docs/07-workstream-backlog.md`](docs/07-workstream-backlog.md).

---

## 1. Project Pulse (2026-10-31)

| Surface | Verified State on Branch | Verification Command |
|---|---|---|
| **Blueprint & Spec (`docs/00`–`07`)** | 8 architectural & spec docs + [`docs/README.md`](docs/README.md) index | — |
| **Normative Corpus (`examples/`)** | All **9** `.plain` apps parse, check, format canonically, and render deterministic SVG + derived a11y | `./plain validate` & `./plain fmt --check examples/*.plain` |
| **Python Spec-Oracle (`src/plainlang/`)** | 17 stdlib-only modules (~5.3k LOC), 8 CLI subcommands, 102 tests, zero runtime dependencies (`pyproject.toml`) | `make ci` |
| **Rust Engine (`rust/`)** | `plain-rs` Slices 1–2 (`tokens`, `ast`, `parser`, `checker`, 17 tests incl. structured `needs` & action-body walk) | GitHub Actions `engine-rust` job |
| **Completed Milestones** | **M0** (`HAB-73`) + **M1 Tranches 1–2** (`HAB-74`) + **DX/Linear Reorganization** (`HAB-75`) + **Wave 1A Security** (`HAB-69`, `HAB-70`) | All CI gates green |

---

## 2. Active Priority Queue (`Todo` — Milestone M1 Wave 1)

Ordered by severity and dependency chain. Every item maps 1:1 to an open Linear issue in **PlainP — PLAIN Platform & PL**.

### Wave 1B · Architectural Separation (`ADR-9`) & Python–Rust Lockstep Gate
- [ ] **`HAB-85` · [P2 High] Separate PL Core language fundamentals from Clear atoms (~8 primitives) and `std/ui.plain` prelude** (`ADR-9`, `docs/05`)
  - Decouple parser/checker from hardcoded widget lists via two-phase signature resolution, promote two-way `bind` references + typed boolean flags to PL Core, expose interaction/semantic a11y traits on `box`/`text-input`, and author controls (`button`, `toggle`, `divider`, `spacer`, `spinner`, `table`) in `std/ui.plain` shared by Python & Rust.
- [ ] **`HAB-76` · [P2 High] Bring Rust front-end (`plain-rs` Slice 1–2) up to M0 parity with Python oracle** (`RS-08`, `P0-02/03/08/09`)
  - Add 1-based column spans & carets (`tokens.rs`, `ast.rs`, `errors.rs`), preserve component/page parameter `defaults` (`parser.rs:146`), and emit `PlainWarning` notes (action-body walk & capability checks landed in `HAB-70`).
- [ ] **`HAB-71` · [P2 High] Establish Python–Rust differential parity harness** (`RS-09`, `TST-11`) *(blocked by `HAB-76`)*
  - Add `--dump-ast --json` and `--json` diagnostics to both Python `plain` and Rust `plain-rs`, plus a CI gate diffing ASTs, warnings, and errors across `examples/*.plain` and negative fixtures.

### Wave 1C · Spec Consolidation, Core Types & Corpus Completeness
- [ ] **`HAB-77` · [P2 High] Resolve broken action & navigation targets in normative examples `03`, `06`, and `08`** (`DOC-04`, `UI-13`)
  - Resolve undeclared `cart` / `Chair(...)` on `08-viewer-3d.plain:55`, missing `Welcome` / `SignIn` targets in `06-form-validation.plain:31,51`, and `Docs-link` / `About-link` targets in `03-navbar.plain:32`.
- [ ] **`HAB-72` · [P2 High] Specify and implement core expression types and units** (`EX-01`..`EX-04`, `EX-08`)
  - Replace `_Unit(float)` (`expr.py:258`) with unit-safe `Duration`, `Angle`, `Percent`, and `Length` (`300ms + 12` errors; `2s + 300ms == 2300ms`), integer-minor-unit `Money`, validated `Date`/`Time`, and safe `Maybe` propagation.
- [ ] **`HAB-78` · [P3 Medium] Fold grammar amendments `G-1…G-10` into Doc 03 spec and resolve open RFCs** (`DOC-03`, `DOC-04`, `FE-02`)
  - Fold `docs/06` §5 into `docs/03-pl-language-spec.md` (removing withdrawn comma-suffixed `when` prop styling in §4.4) and settle remaining RFCs (`theme dark` OS behavior, Ge'ez/Unicode identifiers, multi-error recovery, v1 prelude stdlib list).

---

## 3. Planned Backlog (`Backlog` — Milestone M1 Wave 2 & Milestone M2)

### Milestone M1 Wave 2 · Full Stage-3 Oracle Completeness
- [ ] **`HAB-79` · [P2] Implement compile-time name resolution (`CHK-02`) and exhaustive `when` checking (`CHK-04`)** *(blocked by `HAB-72`, `HAB-77`)*
- [ ] **`HAB-80` · [P3] Implement typed `theme` tokens, local `use` modules, and core stdlib controls** (`FE-12`, `FE-13`, `CHK-06`, `UI-07..08`) *(blocked by `HAB-78`)*
- [ ] **`HAB-81` · [P3] Complete Flow container constraints (`LAY-01..05`) and derived accessibility checks (`A11Y-01..06`)** *(related to `HAB-80`)*
- [ ] **`HAB-82` · [P3] Add async `loading` lifecycle, `from live` streaming, keyed list identity & signal graph** (`RT-01..05`, `NET-05`, `NET-07`, `SRV-01`) *(blocked by `HAB-69`)*
- [ ] **`HAB-84` · [P4] Modularize Python test suite by subsystem, add coverage/lint CI gates & implement `plain test`** (`TST-01`, `TST-09..10`, `CLI-01`)

### Milestone M2 · Competitive Rust Engine (`ADR-1`)
- [ ] **`HAB-83` · [P3] Port Slice 3 (`expr` + `runtime`) and Slice 4 (`scene` + Flow `layout` + `a11y` + `paint_svg`) to Rust** (`RS-01..05`, `RS-07`, `RS-10`) *(blocked by `HAB-71`, `HAB-72`)*

---

## 4. Recently Completed Milestones (`Done`)

- [x] **`HAB-69` & `HAB-70` · Wave 1A Preview Server Hardening & Default-Deny Capability Boundaries** *(2026-10-31)*
  - Moved `/tap/*`, `/field/*`, and `/reset` to `POST` (`405` on `GET`), enforced per-session CSRF + `Origin`/`Sec-Fetch-Site` checks, capped `POST` bodies at 64 KiB (`413`), added proxy-compatible security headers, and eliminated `secret` input plaintext from URLs, HTML `value`, SVG, `a11y`, and Looking Glass (`HAB-69`).
  - Added structured `Capability` AST + comma-separated `needs` parsing in Python & Rust, `plain check` diagnostics (`keep` requires `needs storage`, literal `http(s)://` requires `needs network <host>`, no wildcards/blanket `needs network`), and runtime default-deny host + redirect hop checks (`HAB-70`).
- [x] **`HAB-75` · Repository Audit, TODO Split, Packaging & Linear Documentation Hub** *(2026-10-31)*
  - Audited all 17 Python modules, 7 Rust modules, 9 examples, and 7 blueprint docs; created Linear handbook, labels, dependency graph, and issues `HAB-69`..`HAB-84`; split 1,392-line `TODO.md` into `TODO.md` + `docs/07-workstream-backlog.md`; added `pyproject.toml`, `docs/README.md`, `CONTRIBUTING.md`, and fixed `examples/README.md` + duplicate `parser.py` branch.
- [x] **`HAB-74` · M1 Tranches 1–2: Request Actions, `when`/`then`, Toasts, LRU Resource Cache, ETag & Safe-GET Retries** *(PR #3, 2026-10-31)*
  - Shipped `post`/`put`/`patch`/`delete`/`fetch` Result actions, `when` payload matching, `then` chains, `show toast`, 128-entry LRU resource cache, `If-None-Match` `304` revalidation on `refresh`, and 3-attempt safe-GET retries.
- [x] **`HAB-73` · M0 Trustworthy Baseline: Blueprint v0.1, Python Spec-Oracle, Rust Slices 1–2 & P0 Fixes** *(PR #1 & PR #2, 2026-10-31)*
  - Shipped `docs/00`–`06`, `examples/00`–`08`, `src/plainlang/`, `rust/` Slice 1–2, and all 12 `P0-01`..`P0-12` fixes (slot scopes, defaults, explicit `UnsupportedYet`/notes, secret masking, `plain fmt`, caret spans, isolated `plainsid` sessions, golden CI gates).

---

## 5. Subsystem Reference Map (`docs/07-workstream-backlog.md`)

| Section in `docs/07` | ID Prefix | Scope | Primary Linear Issues |
|---|---|---|---|
| §2 P0 Baseline | `P0-01..12` | Stop-the-line honesty, spans, sessions, formatter, CI | `HAB-73` (12/12 Done) |
| §3 Language Front End | `FE-01..19` | Lexer, indentation, AST, variants, `theme`, `use` | `HAB-78`, `HAB-80` |
| §4 Expressions & Types | `EX-01..18` | Units, Money, Time, Maybe, Result, pipelines | `HAB-72`, `HAB-74`, `HAB-79` |
| §5 Runtime & Reactivity | `RT-01..24` | Signal graph, keyed `for`, `keep`, lifecycle, routing | `HAB-74`, `HAB-82` |
| §6 Resources & Net | `NET-01..14` | HTTP, LRU cache, retries, `from live`, capabilities | `HAB-70`, `HAB-74`, `HAB-82` |
| §7 Scene & Stdlib | `UI-01..16` | Nodes, slots, `when`, prelude stdlib controls | `HAB-77`, `HAB-80` |
| §8 Flow Layout | `LAY-01..14` | True container constraints, weights, grid, scroll, RTL | `HAB-81` |
| §9 Paint, Text & 3D | `H-01..14` | SVG completeness, springs, gestures, shaping, wgpu | `HAB-83` (M2/M3) |
| §10 Accessibility | `A11Y-01..14` | Derived roles, labels, 44pt targets, contrast, `--json` | `HAB-81` |
| §11 Dev Server & Preview | `SRV-01..14` | Hardening, SSE live reload, Looking Glass panels | `HAB-69`, `HAB-82` |
| §12 CLI & Packaging | `CLI-01..14` | `pyproject.toml`, `plain test`, `fmt`, LSP, templates | `HAB-75`, `HAB-84` |
| §13 Checker & Formatter | `CHK-01..13` | Static name resolution, typechecking, exhaustiveness | `HAB-73`, `HAB-79` |
| §14 Security | `SEC-01..10` | `needs` handles, default-deny, preview CSRF, sandboxing | `HAB-69`, `HAB-70` |
| §15 Rust Port | `RS-01..14` | Slice 1–2 catch-up, diff harness, Slice 3–5 port | `HAB-76`, `HAB-71`, `HAB-83` |
| §16 Tests & CI | `TST-01..15` | Subsystem split, golden snapshots, coverage, fuzzing | `HAB-71`, `HAB-84` |
| §17–§20 Docs, Perf, Eco, Plat | `DOC`/`PERF`/`ECO`/`PLAT` | Spec consolidation, benchmarks, i18n, native shells | `HAB-75`, `HAB-78`, M3–M4 |
