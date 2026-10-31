# Examples — the spec made concrete

These eight programs (plus Hello World) are **normative**: the Stage 1–3
parser must accept them as written (Doc 05, Phase 4 exit criteria). Each
answers one item from the original brief (§2.2.4) and maps to the Phase 5
validation suite (Doc 05).

| File | Brief item | PL lines* | Typical incumbent | Concepts exercised |
|---|---|---|---|---|
| `00-hello-world.plain` | Stage 1 smoke test | 4 | 3 files + tooling / ~25 (Flutter) | page, column, text |
| `01-counter.plain` | counter | 13 | React 6+ / Flutter ~12 (2 classes) | `=` `is` `on tap` |
| `02-todo.plain` | todo add/remove/filter | ~45 | React ~140 / Flutter ~160 | kinds, `keep`, `where`, looks |
| `03-navbar.plain` | responsive nav | ~30 | HTML+CSS+JS toggle ~90 | container `width`, `when` layouts |
| `04-chat.plain` | real-time chat | ~50 | web+WS stack 200+ | `from live`, `when` resource |
| `05-datatable.plain` | table sort+page | ~55 | React+table lib ~120 | derivations as pipelines |
| `06-form-validation.plain` | form validation | ~55 | RHF+Zod ~110 | error derivations, Result |
| `07-page-transition.plain` | animated transition | ~40 | VT API/framer ~60+dep | springs, shared `id`, gestures |
| `08-viewer-3d.plain` | 3D viewer | ~50 | three.js/R3F ~150 | `scene3d`, one-state 2D↔3D |

\* Excluding comments. Incumbent counts are honest minimal-production
equivalents (error/loading states included where PL includes them);
methodology + pass bars in Doc 05 Phase 5.

## The read-aloud test (try it)

Read `01-counter.plain` to a non-programmer, as sentences:

> "Component Counter. Count is zero. Mood is 'getting warm' if count is at
> least ten, otherwise 'just starting.' A column, gap sixteen, padding
> twenty-four, align center: text 'Count' and the count, size thirty-two,
> bold… button '+1', on tap count plus-equals one."

They will tell you what the app does. Now try the same with the React or
Flutter versions in `docs/04-syntax-showdown.md`. That gap — not lines of
code — is PLAIN's actual claim. LOC is just its shadow.

## Notes for implementers (known spec pressure points)

1. ✅ **Resolved (Stage 1, Doc 06 G-3):** inline conditional props
   (`look chip-selected if … otherwise look chip`, `strike if task.done`)
   are the one spelling — implemented and tested. The comma-suffixed form
   sketched in Doc 03 §4.4 is withdrawn.
2. `04` uses `refresh messages` as an action expression and `ready-or []`
   in `07` — resource conveniences to ratify or cut at Stage 3 RFC.
   Cutting is allowed; adding a second spelling is not.
3. ✅ **Resolved (Stage 1, Doc 06 G-4):** `is` derivations inside any block
   scope (`05`'s `when`-branch pipelines, `07`'s `columns is …`) parse and
   evaluate as scoped locals.
4. `07`'s shared-element `id "photo-{photo.id}"` requires Clear to retain
   outgoing-page geometry during transitions (Doc 02 §5 budget includes it).
   Parsed today; animation lands in Stage 3+.
