# Phase 3 — Syntax Showdown: 10 Features × 5 Stacks

> Method: for each feature, the *same behavior* in current-idiomatic React
> (TS), Svelte 5, SwiftUI, Flutter, and PL. Snippets are minimal but real
> (ceremony that production code can't omit is kept;imports noted where they
> matter). Verdicts cite concepts-to-learn and failure modes, not taste.
> PL semantics: Doc 03. Every PL snippet passes the Plain Test (Doc 03 §11).

---

## Feature 1 — Reactivity: a counter

**React**
```tsx
import { useState } from "react";
export function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>Count: {count}</button>;
}
```
**Svelte 5**
```svelte
<script> let count = $state(0); </script>
<button onclick={() => count++}>Count: {count}</button>
```
**SwiftUI**
```swift
struct Counter: View {
  @State private var count = 0
  var body: some View { Button("Count: \(count)") { count += 1 } }
}
```
**Flutter**
```dart
class Counter extends StatefulWidget { @override State<Counter> createState() => _S(); }
class _S extends State<Counter> {
  int count = 0;
  @override Widget build(BuildContext c) => ElevatedButton(
    onPressed: () => setState(() => count++), child: Text('Count: $count'));
}
```
**PL**
```plain
component Counter:
  count = 0
  button "Count: {count}" on tap: count += 1
```
**Verdict.** Svelte is closest (and PL openly learns from it), but still needs
a `<script>` split, `$state` rune, and HTML below. React adds a hook, a
setter ceremony, and re-render+diff semantics to learn; SwiftUI adds a
property-wrapper menagerie (`@State` vs `@Binding` vs `@StateObject`… B4);
Flutter needs two classes and `setState` to change one integer. PL has one
concept — *a variable* — because reactivity is the language (Doc 03 §6.1),
not an API. Fewer concepts isn't elegance points: it's bug classes
(stale closures, rules-of-hooks, setState-after-dispose) that cannot occur.

## Feature 2 — Component model: a reusable card with children

**React**
```tsx
type Props = { title: string; children: ReactNode };
export function Card({ title, children }: Props) {
  return <section className="card"><h2>{title}</h2>{children}</section>;
} // +.css file for .card
```
**Svelte 5**
```svelte
<script> let { title, children } = $props(); </script>
<section><h2>{title}</h2>{@render children()}</section>
<style> section { /* … */ } </style>
```
**SwiftUI**
```swift
struct Card<Content: View>: View {
  let title: String; @ViewBuilder var content: () -> Content
  var body: some View { VStack { Text(title); content() } }
}
```
**Flutter**
```dart
class Card extends StatelessWidget {
  final String title; final Widget child;
  const Card({super.key, required this.title, required this.child});
  @override Widget build(BuildContext c) => Column(children: [Text(title), child]);
}
```
**PL**
```plain
component Card(title, children):
  column gap 8 padding 16 look card:
    text title size 18 bold
    children
```
**Verdict.** Every incumbent makes "component" a special *kind of thing*
(function+props type, component file, `View` struct with generics+builders,
Widget class with const constructors and keys). PL: a component is a named
indented description; `children` is a parameter like any other. Usage is
identical in form to built-ins (`Card "Hi": …`), so the stdlib/userland
boundary is invisible — the property that makes ecosystems compose.

## Feature 3 — Styling: a primary button with pressed/disabled states

**React + CSS Modules**
```tsx
import s from "./btn.module.css";
<button className={s.primary} disabled={busy}>Save</button>
```
```css
/* btn.module.css */ .primary{background:#5B5BD6;color:#fff;border-radius:10px;padding:12px 20px;font-weight:600}
.primary:active{background:#4343B8} .primary:disabled{opacity:.5}
```
**Svelte** — same CSS, scoped in-file `<style>`, plus `class:primary`.
**SwiftUI**
```swift
Button("Save") { save() }
  .padding(.horizontal,20).padding(.vertical,12)
  .background(Color.accentColor).foregroundStyle(.white)
  .clipShape(RoundedRectangle(cornerRadius:10)).opacity(busy ? 0.5 : 1)
  .disabled(busy)   // pressed-state color: needs a custom ButtonStyle
```
**Flutter**
```dart
ElevatedButton(onPressed: busy ? null : save,
  style: ElevatedButton.styleFrom(backgroundColor: Colors.indigo,
    padding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
  child: Text('Save'))  // pressed color: MaterialStateProperty resolution
```
**PL**
```plain
button "Save" background accent color on-accent corners 10 padding 12 20 bold,
  background accent-deep when pressed, opacity 0.5 when disabled,
  disabled if busy, on tap save
```
**Verdict.** CSS solutions split one button's truth across two languages and
files (A3/A5), with unchecked string classnames. SwiftUI modifiers read
inside-out and still need a `ButtonStyle` type for pressed state; Flutter
nests three constructor types to say "rounded indigo." PL says the whole
visual truth on the node, in reading order, type-checked (Doc 03 §4). The
designer's sentence — "accent background, deeper when pressed" — *is* the code.

## Feature 4 — State management: a cart shared across screens

**React** (context+reducer *or* add Zustand/Redux): provider tree, action
types, selectors; ~60–120 lines before UI. **Svelte:** a `.svelte.ts` shared
`$state` module (good!) — but persistence/routing state still separate libs.
**SwiftUI:** `@Observable` class + `.environment(cart)` + `@Environment`
retrieval; lifetime owned by *someone's* `@State`. **Flutter:** pick your
religion (Provider/Riverpod/Bloc — B2); boilerplate varies, concepts don't.
**PL**
```plain
shared cart: List of Item = []
keep cart
# anywhere, any page/component:
text "Cart: {cart count} items"
button "Add" on tap: cart add item
```
**Verdict.** The incumbents differ in spelling but agree on structure:
shared state is a *framework/library* concern with providers, stores, or
injection. PL makes scope a prefix word (`shared`, Doc 03 §6.1) and
persistence another (`keep`). The five-states problem (local/shared/server/
URL/persisted) collapses into one mechanism — which is why PL needs no
Redux-shaped ecosystem to grow in the gap (D5).

## Feature 5 — Events & gestures: swipe-to-delete a row

**React/web:** pointerdown/move/up bookkeeping or a gesture library; touch
+ mouse + keyboard paths diverge. **Svelte:** same DOM reality, nicer
bindings. **SwiftUI:**
```swift
Row().swipeActions { Button("Delete", role: .destructive) { delete() } }
```
(Excellent — native recognizers win; PL agrees.) **Flutter:**
```dart
Dismissible(key: Key(id), onDismissed: (_) => delete(), child: Row())
```
Also declarative — good. **PL**
```plain
row on swipe-start: show button "Delete" on tap: tasks remove task
# plus, automatically: focus + Delete key + reader action (a11y derivation)
```
**Verdict.** Native stacks prove gesture *recognizers* beat raw pointer
events (Doc 03 §6.2); the web's pointer soup is the outlier. PL matches the
best incumbents and adds what none give free: the destructive action also
appears as keyboard/screen-reader operation because gestures map to *intents*
on semantic nodes (Doc 02 §1.4), not to pixels.

## Feature 6 — Conditional rendering: loading / error / empty / data

**React**
```tsx
{isPending ? <Spinner/> : error ? <ErrorBox e={error}/> :
 items.length === 0 ? <Empty/> : <List items={items}/>}
```
**Svelte** `{#if}/{:else if}/{/if}` + `{#await}` variants. **SwiftUI**
`switch` over an enum (good, exhaustive — if you modeled one). **Flutter**
`FutureBuilder` + `snapshot.hasError/hasData/ConnectionState` branching.
**PL**
```plain
when posts:
  is loading: spinner
  is failed why: ErrorBox why
  is ready items:
    if items is empty: text "No posts yet."
    otherwise: PostList items
```
**Verdict.** Ternary pyramids (React) and flag-soup (`isPending/isError/data?`)
make *forgetting a state* the default; the type system can't help because
three booleans allow impossible combinations. PL resources are variants and
`when` is exhaustive (Doc 03 §6.4): the compiler refuses to build a screen
with no error story. Swift enums get this right too — PL takes the idea and
makes it the *only* shape data arrives in.

## Feature 7 — Lists: keyed, filterable, animated, huge

**React**
```tsx
{tasks.filter(t => !t.done).map(t => <Row key={t.id} task={t}/>)}
{/* 10k rows? add react-window. Enter animations? add a lib. */}
```
**Svelte** `{#each tasks.filter(…) as task (task.id)}`. **SwiftUI**
`List(tasks.filter{!$0.done}) { Row(task: $0) }` (virtualized ✓). **Flutter**
`ListView.builder(itemCount:, itemBuilder:)` (virtualized ✓, index juggling).
**PL**
```plain
scroll:
  for task in tasks where not done:
    TaskRow task enter fade-up        # virtualized + animated by default
```
**Verdict.** Everyone converges on "map data to rows"; they diverge on the
taxes: manual keys (and the index-as-key bug class), external virtualization
on web, builder-callback indirection in Flutter. PL: identity is automatic
(the runtime tracks item identity, Doc 02 §1.3), filtering reads as English
(`where not done`), scroll containers virtualize always (Doc 02 §6.2), and
enter/exit animation is a property — four separate web libraries' jobs done
by the sentence you already wrote.

## Feature 8 — Derived data & effects: live search filtering

**React**
```tsx
const shown = useMemo(() => items.filter(i => i.name.includes(q)), [items, q]);
useEffect(() => { analytics.log(q); }, [q]);   // forgot a dep? stale bug.
```
**Svelte 5** `let shown = $derived(items.filter(…)); $effect(() => log(q));`
**SwiftUI** computed property + `.onChange(of: q)`. **Flutter** `ValueNotifier`
+ listeners / provider `select` / recompute-in-build folklore.
**PL**
```plain
shown is items where name contains query
whenever query changes: log "search {query}"
```
**Verdict.** React's dependency arrays are manually-maintained compiler
output — the single most bug-dense idiom in mainstream UI (hence lint rules
to police them). Svelte 5's runes and PL agree on the fix (tracked
derivations); PL drops the `$`/parens and separates pure derivation (`is`)
from effects (`whenever`) syntactically, so "is this a calculation or a
side effect?" is answered by the first word of the line (Doc 03 §6.1).

## Feature 9 — Navigation: profile screen with a typed parameter

**React** route table `"/people/:id"` + `useParams()` (stringly; bad id =
runtime surprise) + a router library. **SvelteKit** file routes
`people/[id]/+page` (convention-strong, still string params + `load`).
**SwiftUI** `NavigationStack` + `.navigationDestination(for: Person.self)`
(typed ✓, registration ceremony). **Flutter** `Navigator.push(MaterialPageRoute
(builder: …))` or go_router tables (strings again).
**PL**
```plain
page Profile(user) at "/people/{user.id}": …
go to Profile(ada)
```
**Verdict.** Two camps: string routes (web, go_router: flexible, unchecked —
renames break links silently) vs typed navigation (SwiftUI: safe, verbose
registration separate from the destination). PL puts the address *on the
page declaration* and navigates by calling it: deep-linkable like the web,
type-checked like Swift, one line either way (Doc 03 §6.6).

## Feature 10 — Data fetching: posts with cache, retry, offline

**React**
```tsx
const { data, isPending, error } = useQuery({
  queryKey: ["posts"], queryFn: () => fetch("/api/posts").then(r => r.json()),
}); // needs TanStack Query installed+provider; types erased at r.json()
```
**SvelteKit** `+page.ts load()` + invalidation rules. **SwiftUI**
`.task { … URLSession … }` + manual cache/error state per screen.
**Flutter** `FutureBuilder(future: http.get(…))` (+ rebuild-refetch footgun)
or Riverpod `FutureProvider`.
**PL**
```plain
posts: List of Post from "/api/posts"
when posts:  is loading: …   is failed why: …   is ready items: …
```
**Verdict.** React Query/SWR are excellent libraries *confessing* a platform
hole (Doc 00 D, Doc 01 §3.1): cache keys, dedupe, retry, revalidation,
offline queue are *infrastructure*, identical in every app. PL moves them
into the runtime; the declaration also carries the expected type, so the
response is validated at the boundary (fixing `r.json()` erasure, D2). What
remains in user code is the only app-specific part: what the three states
look like — which exhaustiveness (Feature 6) guarantees you write.

---

## Summary table — concepts a newcomer must learn (lower = plainer)

| Feature | React | Svelte | SwiftUI | Flutter | **PL** |
|---|---|---|---|---|---|
| 1 Reactivity | hooks, setters, render model (3+) | `$state` rune (1) | `@State` family (4 variants) | StatefulWidget+setState (3) | **variable (0 new)** |
| 2 Components | fn+props+JSX rules | file+`$props`+slots | View+generics+builders | Widget classes+keys | **named block** |
| 3 Styling | CSS+modules (whole language) | CSS scoped | modifier order+styles | style objects (3 types deep) | **properties on the line** |
| 4 Shared state | context/store lib | shared module | environment+ownership | pick-a-library | **`shared`** |
| 5 Gestures | pointer events/lib | DOM events | recognizers ✓ | Dismissible ✓ | **`on swipe-start`** |
| 6 Conditionals | ternaries/flags | `{#if}` blocks | enum switch ✓ | snapshot flags | **exhaustive `when`** |
| 7 Lists | map+keys+virt lib | each+key | List ✓ | builder ✓ | **`for … where`** |
| 8 Derived/fx | useMemo/useEffect+deps | `$derived/$effect` | computed+onChange | notifiers | **`is` / `whenever`** |
| 9 Navigation | router+strings | file routes | destination registry | router tables | **`go to Page(x)`** |
| 10 Data | query lib+keys | load fns | manual per screen | FutureBuilder/providers | **`x from "…"`** |

**Pattern across all ten:** Svelte and SwiftUI each win a few rounds —
PLAIN's claim is not inventing every idea, but *completing* the set: the
best answer to all ten, in one language, with no seams (styles know types,
types know the network boundary, resources know the matcher, gestures know
accessibility). Seams are where the bug classes live; PL has dramatically
fewer seams.
