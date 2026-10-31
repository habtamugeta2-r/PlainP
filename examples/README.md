# Examples — The Spec Made Concrete

These nine programs (`00`–`08`) are **normative**: the parser, checker, formatter, Flow layout engine, SVG painter, and derived accessibility tree are continuously verified against them in CI (`./plain check`, `./plain fmt --check`, `./plain validate`). Each maps to one item from the Phase-5 validation suite ([`../docs/05-decisions-roadmap-validation.md`](../docs/05-decisions-roadmap-validation.md)).

| File | Brief item | PL lines* | Fixtures | Interactive status | Typical incumbent | Concepts exercised |
|---|---|---:|---|---|---|---|
| `00-hello-world.plain` | Stage-1 smoke test | 4 | — | Static (`Page`) | 3 files + tooling / ~25 (Flutter) | `page`, `column`, `text` |
| `01-counter.plain` | Counter | 12 | — | Full (`+`, `−`, `Reset`) | React 6+ / Flutter ~12 (2 classes) | `=`, `is`, `on tap` |
| `02-todo.plain` | Todo add/remove/filter | 54 | — | Full (add, filter, toggle, delete, `keep`) | React ~140 / Flutter ~160 | `kind`, `keep`, `where`, `look` |
| `03-navbar.plain` | Responsive nav | 23 | — | Drawer works; `Docs`/`About` routes open (`HAB-77`) | HTML+CSS+JS toggle ~90 | container `width`, `when` layouts |
| `04-chat.plain` | Real-time chat | 45 | `04-chat.sample.json` | `post` + `refresh` work; `from live` is one-shot (`HAB-82`) | web+WS stack 200+ | `from live`, `when` resource, `post` |
| `05-datatable.plain` | Dashboard sort + refresh | 48 | `05-datatable.sample.json` | Full (filter, sort, `refresh`) | React+table lib ~120 | derivations as pipelines, `table` |
| `06-form-validation.plain` | Form validation | 41 | — | Typing + submit `Result` work; target pages open (`HAB-77`) | RHF+Zod ~110 | slot inputs, live validation, `Result` |
| `07-page-transition.plain` | Gallery + pagination | 25 | `07-page-transition.sample.json` | Full (`Load more` slice + detail navigation) | VT API/framer ~60+dep | `ready-or`, `from … take`, shared `id` |
| `08-viewer-3d.plain` | 3D product viewer | 39 | — | Finish/cushion toggles work; `cart`/`Chair` open (`HAB-77`) | three.js/R3F ~150 | `scene3d`, one-state 2D↔3D, `then` |

\* Non-comment, non-blank PL lines reported directly by `./plain validate`. Incumbent counts are minimal-production equivalents (error/loading states included where PL includes them); methodology and pass bars live in [`../docs/05-decisions-roadmap-validation.md`](../docs/05-decisions-roadmap-validation.md) Phase 5.

---

## The Read-Aloud Test (Try It)

Read `01-counter.plain` to a non-programmer, as sentences:

> "Component Counter. Count is zero. Mood is 'getting warm' if count is at
> least ten, otherwise 'just starting.' A column, gap sixteen, padding
> twenty-four, align center: text 'Count' and the count, size thirty-two,
> bold… button '+1', on tap count plus-equals one."

They will tell you what the app does. Now try the same with the React or Flutter versions in `docs/04-syntax-showdown.md`. That gap — not lines of code — is PLAIN's actual claim. LOC is just its shadow.

---

## Notes for Implementers (Spec Pressure Points)

1. **Inline conditional props (`G-3`, settled):**
   `look chip-selected if … otherwise look chip` and `strike if task.done` are the single canonical spelling — implemented, formatted, and tested. The comma-suffixed form sketched in `docs/03-pl-language-spec.md` §4.4 is withdrawn (`HAB-78` folds `G-1…G-10` into Doc 03).
2. **`ready-or` & `refresh` (`G-10`, settled):**
   Both `ready-or []` (`07`) and `refresh metrics` / `refresh messages` (`04`, `05`) are ratified and implemented end-to-end (including conditional `If-None-Match` ETag revalidation and `ErrorBox … retry refresh x` in M1 Tranche 2).
3. **Scoped `is` derivations (`G-4`, settled):**
   `is` derivations inside any block scope (`05`'s `when`-branch pipelines, `07`'s `columns is …`) parse and evaluate as scoped locals.
4. **Shared-element transitions & 3D scene (`Stage 3+` / `M2–M3`):**
   `07`'s shared-element `id "photo-{photo.id}"` and `08`'s `scene3d` currently emit explicit `PlainWarning` notes / wireframe placeholders rather than failing silently (`P0-03`).
5. **Interactive target completeness (`HAB-77`):**
   Three examples (`03`, `06`, `08`) intentionally sketch cross-page links (`Docs-link`, `Welcome`, `SignIn`) or external state (`cart`, `Chair`) whose normative single-file resolution is tracked in Linear `HAB-77`.
