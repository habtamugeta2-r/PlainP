# PLAIN Documentation Index

Welcome to the architectural, language, engine, and backlog documentation for **PLAIN** (`PlainP`).

If you are new to the project, read in the order below—each document builds directly on the decisions established in the previous one.

---

## Reading Order & Specification Map

| # | Document | Role | What It Covers |
|---:|---|---|---|
| **00** | [`00-phase0-research.md`](00-phase0-research.md) | **First Principles** | Audit of HTML/CSS/JS, Flutter, SwiftUI, Elm, and Immediate-Mode UIs; 12 root pain points; 12 non-negotiable axioms (`A1`–`A12`). |
| **01** | [`01-architecture.md`](01-architecture.md) | **System Architecture** | The 4-layer stack (**PL** language → **Clear** engine → **Capabilities** → **Looking Glass** inspector) and the 5-rule **Plain Test**. |
| **02** | [`02-clear-engine.md`](02-clear-engine.md) | **Engine Specification** | **Flow** single-protocol constraint layout (`row`, `column`, `grid`, `stack`, `scroll`), retained scene graph, text/i18n budgets, 2D/3D canvas, and **derived accessibility**. |
| **03** | [`03-pl-language-spec.md`](03-pl-language-spec.md) | **Language Spec (v0.1)** | Normative syntax and semantics for `kind`, `look`, `theme`, `component`, `page`, `=`, `is`, `from`, `when`, `to`, `needs`, and plain-English diagnostics. *(Read alongside §5 of Doc 06 until `HAB-78` folds `G-1…G-10` directly into Doc 03.)* |
| **04** | [`04-syntax-showdown.md`](04-syntax-showdown.md) | **Design Rationale** | Side-by-side comparison of 3 candidate syntaxes across 6 real-world interfaces and why indentation-based English-keyword PL won. |
| **05** | [`05-decisions-roadmap-validation.md`](05-decisions-roadmap-validation.md) | **ADRs & Master Plan** | Architecture Decision Records (`ADR-1` Python oracle + Rust engine through `ADR-8`), risk register, open RFCs, and the 5-stage validation roadmap. |
| **06** | [`06-stage1-prototype.md`](06-stage1-prototype.md) | **Implementation Reality** | Exact guide to what runs today in `src/plainlang/` and `rust/`, settled grammar amendments **`G-1…G-10`**, M0 & M1 Tranches 1–2 notes, and the slice-by-slice Rust port plan. |
| **07** | [`07-workstream-backlog.md`](07-workstream-backlog.md) | **272-Item Reference** | Complete subsystem checklist (`P0-*` through `PLAT-*`) across Stages 1–5 with shipped checkboxes and Linear `HAB-*` cross-references. |
| **08** | [`08-plain-unified-language.md`](08-plain-unified-language.md) | **Proposed function-based Plain** | Unified core language and UI design, complete illustrative programs, runtime model, and explicit prototype compatibility caveats. |

---

## Companion Guides in the Repository

- **Active Roadmap & Priority Queue:** [`../TODO.md`](../TODO.md)
- **Normative Example Corpus (`00`–`08`):** [`../examples/README.md`](../examples/README.md)
- **Contributor Workflow & Guardrails:** [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- **Issue Tracker & Project Handbook:** Linear project **PlainP — PLAIN Platform & PL** (`HAB` team)
