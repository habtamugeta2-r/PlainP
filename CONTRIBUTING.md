# Contributing to PlainP (PLAIN Platform & PL)

Thank you for working on **PlainP**. This guide captures the architectural rules, daily commands, and automated CI invariants that keep the spec, Python oracle, Rust engine, and Linear tracker aligned.

---

## 1. Core Engineering Rules

1. **Zero External Runtime Dependencies**
   - **Python (`src/plainlang/`, `pyproject.toml`):** Python 3.11+ standard library only (`dependencies = []`).
   - **Rust (`rust/Cargo.toml`):** Standard library only until rendering/GPU slices (`wgpu`, `cosmic-text`, `accesskit`) explicitly open in Milestone M3.
2. **Dual-Track Lockstep (`ADR-1`)**
   - `src/plainlang/` is the executable **spec-oracle**.
   - `rust/` (`plain-rs`) is the **production engine**.
   - Never invent divergent grammar or diagnostic rules in one implementation. When behavior changes, record the spec rule (`docs/03` or `docs/06`), implement + test in Python, and keep `plain-rs` in parity (`HAB-76`, `HAB-71`).
3. **No Silent Stubs (`P0-03`)**
   - Every valid PL construct must either **execute cleanly** or surface an explicit `PlainWarning` note / `UnsupportedYet` message naming the stage where it lands. Never swallow parsed syntax silently.
4. **Normative Corpus Discipline (`examples/00`–`08`)**
   - The 9 files in `examples/` are normative tests of the language, not scratchpads.
   - Never weaken an example to work around an engine limitation. Any intentional corpus change requires updating `tests/example_baseline.json` and verifying `./plain fmt --check examples/*.plain`.
5. **The Plain Test (`docs/01-architecture.md` §2)**
   - Before adding syntax, flags, or error messages, check: *Can a 14-year-old read it aloud? Is there only one way to write it? Does the error point at the exact column span with a human `Try:` hint?*

---

## 2. Local Setup & Verification

No virtual environment or package install is required to run from a checkout (though `pip install --no-build-isolation -e .` is supported via `pyproject.toml`):

```bash
# Run the full local CI gate (tests + check + fmt-check + validate)
make ci

# Or run individual commands:
PYTHONPATH=src python3 -m unittest discover -s tests -v
./plain check examples/*.plain
./plain fmt --check examples/*.plain
./plain validate

# Launch the interactive preview + Looking Glass inspector (binds 0.0.0.0)
./plain run examples/02-todo.plain --port 8000
```

If you have a Rust toolchain installed locally (`cargo` 1.75+):

```bash
cd rust && cargo test --verbose
```

---

## 3. Automated Invariants Checked by `tests/test_p0.py`

Before committing, keep these enforced test invariants in mind:

- **Canonical Formatting (`TestP005Formatter`):** `./plain fmt --check examples/*.plain` must exit `0`, and `fmt(fmt(src)) == fmt(src)` must hold.
- **No Dead Placeholder Patterns (`TestP007NoDeadCode`):** `src/plainlang/*.py` is scanned to ensure dead-code smells (`if False`, `pass  #`, `wrapper =`, `_stretch_growers`) never return.
- **Docs-Match-Reality (`TestP011DocsMatchReality`):** Whenever you add or remove `def test_*` methods in `tests/test_*.py`, update the exact test count string in **both** `README.md` (`"<N> spec-oracle tests"`) and `docs/06-stage1-prototype.md` (`"<N> tests"`).
- **Golden Scene & SVG Baselines (`TestP012CI`):** `./plain validate` compares every example's scene node count and SVG byte size against `tests/example_baseline.json`.
- **Backlog Alignment:** Keep high-level active work in `TODO.md` synced with Linear (`HAB-*` issues) and check off completed granular items in `docs/07-workstream-backlog.md`.
