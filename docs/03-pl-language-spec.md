# PL — Plain Language Specification (v0.1 draft)

> **One sentence:** PL is the language where a program reads like a
> description of what you see — structure, style, and logic in one syntax,
> with state, data, and animation as primitives, and nothing to configure.
>
> This document is normative where it gives grammar/semantics, informative
> where it gives rationale. When it disagrees with `examples/*.plain`,
> the examples win (plainness is judged on real programs).

```
PL
├── 1. Philosophy & research basis
├── 2. Syntax overview (the whole language on one page)
├── 3. Structure (replaces HTML)
├── 4. Styling (replaces CSS)
├── 5. Layout in PL (Flow authoring)
├── 6. Logic (replaces JS): state, actions, data, control flow
├── 7. Type system
├── 8. Modules & stdlib
├── 9. Runtime model
├── 10. Developer experience
└── 11. The Plain Test (acceptance criteria for every feature)
```

---

## 1. Philosophy & research basis

| Principle | What it means | Evidence it works |
|---|---|---|
| **Unified** | One syntax for structure/style/logic (answers A5) | JSX proved devs prefer co-location despite initial controversy; Tailwind proved style co-location wins in practice; SwiftUI/Compose proved UI-as-code beats XML |
| **Plain to read** | Reads aloud like English describing a screen | Python's readability drove the largest adoption wave in history; Svelte's "disappearing" syntax wins satisfaction surveys by removing framework-visible code |
| **Plain to write** | Common patterns in 1–3 lines | Every library that shortens a pattern (jQuery→fetch wrappers→React Query) wins users; PL makes the short form the *language* |
| **Typed but inferred** | Types checked always, written rarely | TS demand (D2) + the ergonomics of Swift/Kotlin inference over Java/Obj-C verbosity |
| **Reactive by default** | Bindings are live; no subscriptions | Signals convergence (Solid/Svelte/Vue, D5); MobX showed "just mutate, UI follows" is the model devs wish for |
| **No build step** | `.plain` file → running app (answers D3) | The original web's view-source/run-anywhere immediacy built the modern world; bundlers broke it |
| **No ceremony** | No imports for basics, no boilerplate, no config | `create-*-app` generators exist only because defaults don't |

Non-goals: PL is not a systems language (no pointers/manual memory), not a
general backend language in v1 (though nothing forbids it later), and not
Turing-complete-by-accident in its style layer (styles are values, Doc 02 §1.2).

## 2. Syntax overview — the whole language on one page

```plain
# TodoApp.plain — a complete program. Run: plain run TodoApp.plain
needs storage                          # capabilities, plain words (§5 Doc 01)

kind Task:                             # a data shape (§7)
  title: Text
  done: Bool = no

page Home at "/":                      # a screen with an address (§6.6)
  tasks: List of Task = []             # state: just a variable (§6.1)
  keep tasks                           # persist it (offline, local-first)
  draft = ""
  remaining is tasks count where not done   # derived value, always fresh

  to add-task:                         # an action (§6.2)
    if draft trimmed is empty: return
    tasks add Task(title: draft trimmed)
    draft = ""

  column gap 16 padding 24 width fill max 560 center-self:
    text "My tasks" size 28 bold
    row gap 8:
      input bind draft placeholder "What needs doing?" grow
        on submit add-task
      button "Add" on tap add-task
    for task in tasks:                 # lists are a primitive (§6.4)
      row gap 12 align center padding 12 look card:
        toggle bind task.done
        text task.title grow strike if task.done
        button "Remove" plain on tap: tasks remove task
    if tasks is empty:
      text "Nothing here yet. Add your first task above." color muted
    text "{remaining} to go" color muted size 14

look card:                             # a reusable style (§4.3)
  background surface
  corners 12
  shadow soft
```

Grammar rules that generate everything above (and almost everything else):
1. **Indentation (2 spaces) = nesting.** A line ending in `:` opens a block.
   No braces, no closing tags, no semicolons, no `</div>` to mismatch.
2. **A line is one idea:** a node, a declaration, or a statement.
3. **Nodes:** `kind "content" prop value prop value flag` — properties are
   `name value` pairs; boolean properties are bare flags (`bold`, `grow`).
4. **`#` comments.** One canonical formatter (`plain fmt`, auto-applied);
   formatting debates are deleted, not configurable.
5. **Names:** nodes/stdlib lowercase words; components/pages `PascalCase`;
   values/actions lowercase-with-hyphens (`add-task` is one name — PL allows
   hyphens in identifiers; subtraction requires spaces: `a - b`). Case and
   hyphens carry meaning a reader already understands.

## 3. Structure (replaces HTML)

Research considered: indentation (Pug/Haml/Python — nesting *visible*, zero
close-tag cost), S-expressions (Hiccup — elegant, parentheses repel
newcomers), function-call DSLs (Compose/Flutter — UI drowned in constructors,
commas, and closing-paren pyramids), SwiftUI result builders (nice, but
trailing-closure/modifier chains read backwards: `.padding().background()`
applies inside-out, a famous confusion).

**Decision: indentation-based node lines.** Better than HTML because there
are no closing tags (roughly 30% of HTML bytes are `</...>` noise) and
mismatched nesting is impossible to write and obvious to see. Better than
Flutter/Compose because there are no parentheses/commas between a reader
and the tree. Better than SwiftUI modifiers because properties read in the
order you'd describe them aloud, left to right.

- **Children** = indented block. **Text content** = first quoted string.
- **Components** (§6.3) are defined with `component Name(params):` and used
  exactly like built-in nodes — no distinction in spelling or power, so
  "extract a component" is cut-and-paste, not a refactor ceremony.
- **Slots:** a component may declare `children` — callers indent content
  under it, same as built-ins:
  ```plain
  Card "Profile":
    text "Ada"
  ```
- **No string-built UI:** there is no `innerHTML`, no markup parsing of
  values, ever (security A6/Doc 01 §5, correctness). Interpolated
  `"{name}"` is a *text value*, typed and escaped by construction.

## 4. Styling (replaces CSS)

### 4.1 The model (answers A3)
Styles are **properties on the node**, full stop. There are no selectors, no
cascade, no specificity, no `!important`, no global stylesheet to bleed —
each property has exactly one author: the line that creates the node. The
15 years of CSS escape hatches (BEM → Modules → CSS-in-JS → Tailwind →
StyleX) were all walking toward this point; PL starts there.

```plain
button "Save" background accent color on-accent corners 10 padding 12 20 bold
```

Research notes: Tailwind proved co-located utilities beat semantic classes
for most teams but kept cryptic abbreviations (`flex-col gap-4 px-2`) and
HTML-attribute string soup; Styled Components proved styles-want-to-be-values
but paid runtime CSS generation; StyleX proved compile-time atomic CSS works
but remains CSS underneath. PL keeps the lesson (co-located, value-based),
drops the substrate (no CSS at all — properties are typed scene values,
Doc 02 §1.2, so `corners "big"` is a *compile-time plain-English error*,
not a silently dropped declaration as in CSS).

### 4.2 Inheritance — small, explicit, documented
Only text-ish properties inherit (`size, color, font, weight, direction,
language`), down the tree, nearest wins — because that's how documents read.
Box properties (`background, padding…`) never inherit. That is the entire
"cascade": one rule, teachable in a minute, vs CSS's origin/importance/
specificity/source-order matrix.

### 4.3 Reuse: `look`, themes, tokens
```plain
look card:  background surface, corners 12, shadow soft   # named style
theme:                                                    # design tokens
  color ink #16161A        color paper #FFFFFF
  color accent #5B5BD6     color muted #6E6E7A
  space small 8   space medium 16   space large 24
  font body "Inter"
theme dark:                            # same names, dark values;
  color paper #131316      color ink #F2F2F5   # auto-follows the OS
```
Tokens are **typed language values**, not CSS variables (untyped strings
resolved at computed-value time). Referencing a missing token is a compile
error. Dark mode, brand themes, and per-user themes are the same mechanism.
Figma-token parity is a tooling feature (Doc 01 §6.3), not a language hack.

### 4.4 States & animation are styling
Interactive states are property suffixes, not pseudo-classes in another file:
```plain
button "Save" background accent, background accent-deep when pressed, opacity 0.5 when disabled
```
and `animate spring` (Doc 02 §5) animates changes. One place tells the whole
visual truth about a node — checkable by eye, by compiler, and by the a11y
contrast checker (Doc 02 §1.4).

## 5. Layout in PL (Flow authoring — model in Doc 02 §2)

### 5.1 Containers & sizing (plain words, no unit zoo)
`column / row / grid columns 3 / stack / scroll`; sizes: bare numbers are
density-independent points (the one unit authors type 95% of the time),
`%` of parent, `fill`, `fit`, `grow [n]`, clamps `width fill max 720`.
`gap`, `padding` (1, 2, or 4 values), `align start|center|end|stretch`,
`spread between|around`. CSS's px/em/rem/vw/ch/fr menagerie collapses to:
points, percent, and relationships — because tokens carry scales (§4.3).

### 5.2 Centering a child (the 20-year question, A3)
```plain
column align center spread center:   # done. (In a row it's the same words.)
  text "Centered both ways"
```

### 5.3 Responsive without media queries (answers A10)
```plain
grid gap 16:
  columns is 3 if width > 900 otherwise 2 if width > 560 otherwise 1
  for photo in photos: image photo.url aspect 4/3 corners 8
```
`width` here is *this node's* actual width — container-aware by birth.
For structural changes, `when narrow:` / `when width < 600:` blocks swap
subtrees (see `examples/03-navbar.plain`). One component, one place, every
size — including the same component at two sizes on one screen, which
viewport media queries cannot express at all.

## 6. Logic (replaces JavaScript)

### 6.1 State & reactivity (answers D5, B4) — *the* core decision
Research field (5+ models): React hooks (re-run + diff; rules-of-hooks
footguns; `useEffect` dependency-array bug class), Vue refs/reactivity
(sound core, `.value` noise, two APIs), Svelte `$:`/runes (compiler magic
moving toward explicit signals), Solid signals (fine-grained, correct,
getter-function syntax tax), MobX observables (mutate-and-it-works ergonomics,
action/observable annotation creep), Elm (Model-Update-View: predictable,
boilerplate-heavy, batched message plumbing for trivial state).

**Decision — language-level fine-grained reactivity with plain variables:**
```plain
count = 0                 # state (writable). Any assignment in a component
                          # or page is reactive state. Nothing to import,
                          # declare, or annotate. (Kills useState, @State,
                          # remember, ref — B4's annotation soup.)
double is count * 2       # derived (read-only). `is` = "always equals".
                          # Recomputes only when inputs change; the
                          # dependency graph is built by the compiler.
```
- Reading state inside a node property, `is` derivation, or `whenever` block
  subscribes exactly that consumer (Doc 02 §1.3). Writing state updates
  exactly its subscribers. No re-render, no diff, no dependency arrays.
- **Side effects** are one explicit construct (no `useEffect` swiss-army):
  ```plain
  whenever query changes: log "searched {query}"     # rare, visible
  when page appears: focus search-box                # lifecycle in words
  ```
  Derived data uses `is` (pure); effects use `whenever` (impure). The
  purity split React forces devs to simulate with hooks is syntactic here.
- **Shared state:** `shared cart = []` at file/app scope — readable/writable
  from any component, same reactivity (replaces context/providers/stores;
  prop-drilling and store libraries both deleted). **Persisted state:**
  `keep cart` (local-first storage, versioned/migrated by shape). **URL
  state:** page params (§6.6) are ordinary state bound to the address.
  Local/shared/server/persisted/URL state — the five kinds web apps juggle
  with five libraries — are one `=` with at most one prefix word.
- **Immutability stance:** values are immutable by default; state variables
  are the explicit mutation points; collection ops (`tasks add x`,
  `tasks remove t`) are persistent-structure updates under the hood, so old
  snapshots stay valid for time-travel debugging (Doc 01 §6.3) while the
  syntax stays plain. No `setState({...state, …})` spread rituals.

### 6.2 Actions & events (answers A4)
```plain
to checkout:                       # define: "to checkout:" reads like a manual
  if cart is empty: return
  order = place-order(cart)        # async invisible (§6.5)
  when order:
    is ok receipt: go to Thanks(receipt)
    is failed why: show toast "Couldn't check out: {why}"

button "Check out" on tap checkout           # wire: event + action name
button "+1" on tap: count += 1               # or inline one-liner
input bind email on submit checkout          # two-way bind + submit
```
Events are node properties (`on tap|change|submit|hover|focus|key …`),
gestures (`on swipe left`, `on long-press`, `on drag`) are engine
recognizers — not pointer-event state machines per app (research: DOM
pointer events vs iOS gesture recognizers; recognizers win for humans).
No `addEventListener`, no cleanup functions, no event-object archaeology;
handlers receive named values (`on change value:`) when they need them.

### 6.3 Components (research: Doc 04 Feature 2)
```plain
component Avatar(person, size = 40):
  if person.photo exists:
    image person.photo size size shape circle
  otherwise:
    box size size shape circle background accent-soft:
      text person.initials center bold
```
A component is a named, reusable description with its own state — nothing
more (no classes, no lifecycle method zoo, no `Widget`/`View` protocol
conformance lists). Used as `Avatar ada size 56`. Stateful vs stateless is
not a taxonomy: if it has `=` lines, it has state.

### 6.4 Control flow: `if`, `for`, `when` (pattern matching primary)
```plain
for task, i in tasks: …                 # repetition primitive, keyed by
                                        # identity automatically (§1.3 Doc 02)
for task in tasks where not task.done: …    # filtered, plainly
when notifications:                     # exhaustive matching — compiler
  is loading: spinner                     # errors if a case is missing
  is failed why: ErrorBox why
  is ready items: NotificationList items
```
`if/otherwise` for binary choice; `when/is` for everything richer (kinds,
results, resources). No ternaries, no `&&`-rendering (`{cond && <X/>}` and
its infamous `0 &&` bug), no switch fallthrough. Exhaustiveness turns
"forgot the error state" from a runtime embarrassment into a compile error —
for UI, this single feature deletes a whole bug category.

### 6.5 Data & async — invisible async (answers A4, D-libraries)
Research: async/await (function coloring), Promises (chain noise), Go
goroutines (cheap concurrency, still manual channels), algebraic effects
(elegant, research-grade), React Suspense/`use` (exceptions-as-control-flow
for loading), resource primitives (Solid `createResource`, SvelteKit `load`).
**Decision: all I/O returns values that may not be ready yet; the language
handles it.** No `async`, no `await`, no Promise type in user code.

```plain
posts from "/api/posts"                          # a Resource (§3.1 Doc 01)
messages from live "/rooms/{room.id}/messages"   # a streaming Resource
photo from camera                                # hardware, same shape
every 30s: refresh posts                         # time, same spirit
```
A resource is matched with `when` (§6.4) on `loading/failed/ready` — loading
and error UI are therefore *unavoidable to consider* (exhaustiveness) and
trivial to write. Inside actions, calls like `place-order(cart)` simply
produce `ok/failed` results (§7.4); the runtime suspends the isolate fiber,
never the UI (Doc 02 §6.1). Concurrency is structured: `together:` blocks
run steps concurrently and join; there are no user threads, locks, or races
on state (state writes are serialized per component by the runtime).

### 6.6 Navigation (answers router libraries)
```plain
page Profile(user) at "/people/{user.id}": …
go to Profile(ada)        # typed: wrong arg = compile error, not a 404
go back
```
Pages declare addresses; navigation is state change; deep links, back stack,
and state restoration are runtime behaviors. Stringly-typed route tables
(`/people/:id` parsed by regex at runtime) are deleted.

### 6.7 Errors: values, not exceptions across UI code (§7.4)
Fallible ops return `ok value | failed reason`, consumed by `when`. Truly
exceptional faults (engine bugs, OOM) crash the *isolate* into an error
boundary page (`page Fallback(error)`) — never a white screen, never a
try/catch thicket. `nothing` (absence, §7.2) is handled by matching or by
`x or default`; there is no null-dereference crash class.

## 7. Type system

- **7.1 Structural + inference-first:** types are shapes; Hindley-Milner-
  style inference covers component bodies; annotations appear at boundaries
  (component params, `kind` fields, resources) — where they double as
  network validation (D2). `x: Type = value` when you want to say it;
  the compiler usually already knows.
- **7.2 No null/undefined:** absence is `Maybe T` = a value or `nothing`
  (`person.photo` above). One absence concept (JS has two + NaN, A4).
- **7.3 UI-native types:** `Text, Number, Integer, Bool (yes/no), List,
  Map, Color, Length, Angle, Duration (300ms, 2s), Percent, Gradient,
  Easing, Moment, Resource T, Stream T`. `width "wide"` fails with:
  *"`width` needs a length like `240` or `fill` — you wrote text."*
  Units are types, so `300ms + 12` is an error, not a NaN.
- **7.4 Results:** `Result T = ok T | failed Reason`; `Reason` is structured
  (`offline`, `denied`, `invalid field "email"`, `server 500`) and
  human-readable by default — error values print as sentences.
- **7.5 Kinds:** `kind Task:` (records with defaults) and variant kinds:
  ```plain
  kind Payment:  card number, expiry | cash | mobile-money phone
  ```
  matched exhaustively by `when`. Money is `Money` (decimal-correct;
  A4's float lesson), dates are `Moment/Duration/Calendar-day` (D/§6.1 Doc 01).
- **7.6 Gradual only at the FFI/JSON edge:** inside PL, types are sound
  (Dart-sound-null-safety lesson); `Any` exists solely for untyped external
  data and must be matched/narrowed before use — the unsafe perimeter is
  visible in code review.

## 8. Modules & standard library (answers D3/D4)

```plain
use "openly:@acme/charts@2"      # pinned + hashed automatically after
use "./receipt-card.plain"       # first verified fetch (Doc 01 §5.3)
```
- No `package.json`, no `node_modules`, no bundler (research: Deno URL
  imports proved the model; Go modules proved minimal-version-selection;
  cargo proved registry hygiene). The `use` line *is* the manifest.
- **Stdlib needs no `use`** (prelude): controls, charts-basics, collections,
  time, i18n, crypto, http-resources, storage, test (`check`) — sized so the
  median app needs 0–3 external modules (Doc 01 §6.1). `lodash/axios/moment`-
  class deps are stdlib-shaped holes; PLAIN fills them at the platform layer.
- Modules export components/kinds/actions; namespaces prevent collisions;
  module `needs` union into the program's capability list and are displayed
  to the user (a chart lib asking for `camera` is caught by a human).

## 9. Runtime model (detail: Doc 05 ADR-3/4)

- **Tiers:** parse → typed AST → bytecode (verified) → interpreter with
  inline-cached bindings for dev/instant start; hot paths JIT (and
  optionally AOT per-platform at publish) behind the scenes. The developer
  runs one command in every tier: `plain run`.
- **Memory:** generational GC tuned for UI allocation shapes (short-lived
  style/layout values arena-allocated in Clear; program heap GC'd).
  Ownership/ARC rejected for PL itself (programmer burden violates
  plainness; GC pauses are bounded off the compositor path, Doc 02 §6.1).
- **Sandbox:** isolates + capability handles (Doc 01 §5). Deterministic
  replay mode (seeded time/random) powers tests + time-travel.

## 10. Developer experience

- `plain run file.plain` — window opens. `plain run file.plain --on phone`
  (QR) for devices. `plain test`, `plain fmt`, `plain publish`. Four verbs.
- **Hot reload with state:** edit → scene updates in-place, state preserved
  (bindings rewire; state vars survive by name/shape) — stronger than hot
  *refresh* because state is declared, not hidden in hook order.
- **Errors in plain sentences** (Elm/Rust-compiler class is the bar):
  ```
  Line 12: `button` needs something to show.
     button on tap save
            ^^^^^^^^^^^
  Try:  button "Save" on tap save
  ```
  Every error: what, where (span), why in one sentence, a concrete fix.
- **LSP + Looking Glass from day one** (Doc 01 §6.3); the language server
  shares the real compiler (no divergent TS-server-vs-Babel truths).
- **AI-native tooling:** because PL is small, typed, and source-spanned,
  models generate/edit it reliably; `glass` exposes scene+state as
  structured data for agents. (A small language is an AI-ergonomics feature.)

## 11. The Plain Test — gate for every syntax decision (incl. future RFCs)

A feature ships only if all five pass:
1. A non-programmer reading it aloud roughly understands it.
2. A junior developer learns the pattern in < 5 minutes.
3. It reads as a *description of a UI*, not as code about code.
4. No character/keyword can be removed without losing meaning.
5. You'd show it to a designer without embarrassment.

Worked example — two-way binding candidates: `bind:value={draft}` (Svelte-ish:
fails 1, 4), `value={draft} onInput={e => setDraft(e.target.value)}` (React:
fails 1–5), `@Binding var draft` + `TextField("…", text: $draft)` (SwiftUI:
fails 1, 4 — the `$` is unexplained punctuation), **`input bind draft`
(passes all five; shipped §6.2).** The test is applied per-example in
`examples/README.md`.
