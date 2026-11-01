# Plain: unified language and UI specification

**Status: proposed design, not implemented.** This document specifies a new
function-based direction for Plain. It deliberately differs from the existing
indentation-based PL draft and Stage 1 prototype: in particular, it replaces
node-line, `look`, `page`, `to`, and implicit state syntax with ordinary
functions, values, and explicitly declared components and state. The programs
below are **design examples**, not programs accepted by today's `plain` CLI.
They are not a claim that Clear or a native compiler already implements this
design. Migration and parser changes need a separate decision and work plan.

## 1. Goals and design rules

Plain is one statically checked, compiled language for application logic and
interfaces. A UI is a value returned by a function; text, controls, layout,
style, animation, and handlers are ordinary library values and functions. There
are no markup tags, selector language, templates, embedded scripting language,
or special UI child syntax. The compiler and runtime may use platform APIs
internally; that is not source-language HTML, CSS, or JavaScript.

Rules for readable programs:

1. A `component` owns persistent state and returns a `View`; an ordinary `fn`
   computes a value. Component calls and ordinary calls use the same syntax.
2. `let` is immutable, `var` is a local mutable variable, and `state` is a
   persistent reactive cell. Mutation always uses `=`; reading or writing a
   state cell always uses `.value`.
3. Named arguments identify UI properties. Child views are ordinary lists.
   Function calls, not juxtaposed words, construct every node.
4. A modifier is a typed method call. Chains execute left to right; each call
   wraps the preceding view. There is no selector, hidden cascade, or implicit
   mutation of an existing view.
5. Conditions and matches must be exhaustive when used as expressions. No
   implicit truthiness, coercion between unrelated types, or silent failure.
6. Effects are explicit: rendering is pure; event handlers and async tasks may
   perform effects. State is changed only in an event or a task on the UI thread.

The design borrows Python's readable names, Rust's checked ownership, Swift's
value modifiers, Compose's composition, Flutter's view values, Elm's pure
rendering and algebraic data, Kotlin's structured tasks, Go's channels, and
TypeScript's structural shapes. These are inspirations, not claims of identical
semantics or proven performance.

## 2. Source, lexing, and grammar

### 2.1 Lexical rules

A source file is UTF-8; a UTF-8 BOM is permitted only at the start. Line endings
LF and CRLF are equivalent. Whitespace separates tokens but has no syntactic
significance; braces delimit blocks. `//` starts a line comment; `/* ... */` is
a nestable block comment. Comments are not recognized inside strings.
Identifiers are ASCII `[A-Za-z_][A-Za-z0-9_]*`, case-sensitive. Keywords below
cannot be identifiers. Types, components and enum variants use PascalCase;
functions, variables and fields use snake_case. These naming conventions are
formatter/linter rules, not different namespaces or parsing rules.

Keywords: `module import as public fn async component state let var return if
else match for in while break continue struct enum trait impl for type true false
and or not await spawn move ref mut where`. `for` is used both in loops and
`impl Trait for Type`. Names such as `Text`, `View`, `Some`, `None`, `Ok`, and
`Err` are prelude names, not keywords.

Integers are decimal digits with optional internal `_`; floats require digits
on both sides of `.` and may have an exponent (`1.0`, `2.0e3`). A leading
minus is an operator. Integer literals default to `Int` and decimal literals to
`Float` absent an expected numeric type. Overflow is a compile error for
constants and a checked runtime error otherwise. Strings use double quotes;
`\\`, `\"`, `\n`, `\r`, `\t`, and `\u{hex}` are the supported escapes.
Strings are Unicode scalar sequences. There is no interpolation: use
`"Count: " + count.to_text()`. Color is a typed constructor such as
`Color.hex("#2563EB")`, not a special token.

The following EBNF is normative for the surface forms used in this proposal.
`?`, `*`, and `+` mean optional, zero-or-more, and one-or-more; `|` separates
alternatives. Terminals are quoted. Comma-separated lists allow a trailing
comma. An implementation must reject syntax not described here. Library APIs
are not keywords and can be extended without changing the grammar.

```ebnf
file        = module_decl? import_decl* declaration* ;
module_decl = "module" path ";" ;
import_decl = "import" path ("as" ident)? ";" ;
path        = ident ("." ident)* ;
declaration = "public"? (function | component | struct | enum | trait | impl | alias) ;
function    = "async"? "fn" ident type_params? "(" params? ")" "->" type block ;
component   = "component" ident "(" params? ")" "->" "View" component_block ;
struct      = "struct" ident type_params? "{" fields? "}" ;
fields      = field ("," field)* ","? ;
field       = ident ":" type ;
enum        = "enum" ident type_params? "{" variants? "}" ;
variants    = variant ("," variant)* ","? ;
variant     = ident ("(" types? ")")? ;
trait       = "trait" ident "{" trait_method* "}" ;
trait_method = "fn" ident "(" params? ")" "->" type ";" ;
impl        = "impl" type_params? (type "for")? type "{" function* "}" ;
alias       = "type" ident type_params? "=" type ";" ;
type_params = "<" ident ("," ident)* ">" ;
params      = param ("," param)* ","? ;
param       = ident ":" type ;
types       = type ("," type)* ","? ;
type        = union_type ;
union_type  = intersection_type ("|" intersection_type)* ;
intersection_type = atomic_type ("&" atomic_type)* ;
atomic_type = path ("<" types ">")? | "(" types? ")"
            | "fn" "(" types? ")" "->" type
            | "{" fields? "}" ;
component_block = "{" state_decl* statement* "}" ;
state_decl  = "state" ident ":" type "=" expr ";" ;
block       = "{" statement* "}" ;
statement   = ("let" | "var") ident (":" type)? "=" expr ";"
            | "return" expr ";" | "if" expr block ("else" block)?
            | "for" ident "in" expr block | "while" expr block
            | "break" ";" | "continue" ";" | assignment ";"
            | expr ";" ;
assignment  = place "=" expr ;
place       = ident ("." ident)* ;
expr        = or_expr ;
or_expr     = and_expr ("or" and_expr)* ;
and_expr    = compare ("and" compare)* ;
compare     = additive (("==" | "!=" | "<" | "<=" | ">" | ">=") additive)? ;
additive    = multiply (("+" | "-") multiply)* ;
multiply    = unary (("*" | "/" | "%") unary)* ;
unary       = ("not" | "-" | "await" | "spawn") unary | postfix ;
postfix     = primary ("(" args? ")" | "." ident | "[" expr "]")* ;
args        = arg ("," arg)* ","? ;
arg         = (ident ":")? expr ;
primary     = literal | ident | path | "(" expr ")" | "(" ")" | tuple | list
            | record | lambda | if_expr | match_expr ;
tuple       = "(" expr "," (expr ("," expr)* ","?)? ")" ;
list        = "[" (expr ("," expr)* ","?)? "]" ;
record      = "{" (ident ":" expr ("," ident ":" expr)* ","?)? "}" ;
lambda      = "fn" "(" params? ")" "->" type block ;
if_expr     = "if" expr "{" expr "}" "else" "{" expr "}" ;
match_expr  = "match" expr "{" arm ("," arm)* ","? "}" ;
arm         = pattern "=>" expr ;
pattern     = "_" | literal | ident | path | path "(" patterns? ")" ;
patterns    = pattern ("," pattern)* ","? ;
literal     = integer | float | string | "true" | "false" ;
```

Lexing uses longest match, so `=>`, `==`, `<=`, `>=`, and `!=` are single
tokens. Calls can use positional arguments followed by named arguments; each
parameter must be supplied exactly once. Methods are calls whose receiver is the
first argument of the resolved method. Member access and indexing bind tighter
than unary operators; precedence then follows the EBNF. Arithmetic associates
left; comparisons cannot be chained. `and` and `or` short-circuit and require
`Bool`. `if` in statement position does not return a value; expression `if`
requires `else`. Expression branches contain one expression, not statements.
Statements end with semicolons except blocks. There is no implicit return.
A bare identifier pattern binds a new name; `_` discards; a payload-free enum
variant in a pattern is qualified (`Option.None`). Qualified expression paths
are resolved as module or type names before value member access. Patterns have no guards in
v1. Guard clauses use `if condition { return value; }`.

## 3. Types, values, and safety

* Every expression has a static type. Local `let`/`var` types and generic call
  arguments are inferred; public signatures, state, fields, and lambda
  parameters and return types are explicit. No dynamic `Any` or implicit casts.
* Prelude scalar types: `Bool`, signed 64-bit `Int`, IEEE-754 64-bit `Float`,
  Unicode `Text`, and `Unit` (the empty tuple `()`). Arithmetic operands must
  have the same numeric type. `Text` concatenation is `+`.
* `List<T>`, `Map<K, V>`, tuples such as `(Text, Int)`, and structural records
  such as `{name: Text, age: Int}` are values. Lists and maps are persistent,
  immutable collections; operations return new collections. `map.get(key)`
  returns `Option<V>`; `list[index]` returns `Option<T>`, never an unchecked
  value. Maps require keys implementing `Hash` and `Equal`. Empty list literals
  need an expected type. Record values are written `{name: "Ada", age: 37}`;
  fields can be projected by name. A record with extra fields can be used
  where a record with fewer matching fields is expected.
* `struct` is a nominal product type with immutable fields and a constructor
  named after its type, taking named field arguments. `enum` is a nominal sum;
  variants are qualified, e.g. `Load.Ready(value)`. Generics are monomorphized
  when practical; type checking is independent of specialization.
* `Option<T>` is `Option.Some(T) | Option.None`; `Result<T, E>` is
  `Result.Ok(T) | Result.Err(E)`. There is no null. `A | B` is a tagged union;
  `A & B` is an intersection of structural record types or trait bounds, not
  arbitrary incompatible concrete types. Matching a union requires patterns
  for each alternative; the compiler rejects overlapping indistinguishable
  alternatives. Trait bounds are part of API design, but v1's surface grammar
  does not support generic bounds declarations: use concrete types or trait
  values until bounds syntax is standardized. `trait` defines methods and
  `impl Trait for Type` supplies them; there is no implicit inheritance.
* Values are immutable by default. `var` permits local reassignment, not shared
  mutable aliases. Implementations use moves, immutable borrowing and reference
  counting as appropriate; a mutable borrow is exclusive and cannot escape its
  scope or cross `await`. Safe Plain has no raw pointers, data races, or
  use-after-free. Immutable heap graphs cannot directly contain strong cycles;
  runtime-managed handles use weak back-references. Exact representation is an
  implementation detail, not a promise of zero allocations.

```plain
struct Task { title: Text, done: Bool }
enum Load<T> { Waiting, Ready(T), Failed(Text) }

fn label(task: Task) -> Text {
  if task.done { return "Done: " + task.title; }
  return "Todo: " + task.title;
}

fn describe(load: Load<Text>) -> Text {
  return match load {
    Load.Waiting => "Loading",
    Load.Ready(text) => text,
    Load.Failed(message) => message,
  };
}
```

## 4. Functions, components, and rendering

`fn` declares an ordinary function. `component` declares a callable with an
instance identity and persistent local state; it must return exactly one
`View`. A `View` is an immutable, typed description, not an already-created
platform control. Built-in view constructors and modifier methods are normal
prelude APIs. A component call creates a deferred component view; the runtime evaluates its
body only after assigning its parent and key, so `.key(...)` on that view can
control its identity before state is initialized. A component may pass children
as `List<View>` or a single `View`,
just as it passes any other argument. It cannot mutate state, perform I/O, or
start tasks while constructing its result. The compiler checks these effects
transitively, including calls through function values. The compiler infers
effects from bodies; a function value with unknown effects is treated as
effectful, while APIs that evaluate callbacks during rendering require a known
pure callback. Passing an effectful callback to a deferred handler parameter
does not invoke it. Handler closures are created during rendering but execute
later in an effectful context.

```plain
component Hello() -> View {
  return Column(children: [
    Text("Hello, world.").font_size(32.0),
    Text("One language, one interface."),
  ]).gap(12.0).padding(24.0);
}
```

`Text` is overloaded by context: `Text` in type position is the prelude string
type; `Text(...)` in expression position is the UI text-view constructor. Type
and value names have separate namespaces. `Column` is a function, not a tag.
The prelude also provides `Row`, `Grid`, `Stack`, `Scroll`, `Button`, `Input`,
and `Empty`, all returning `View`. `Button` takes `label: Text`,
`on_click: fn() -> Unit`, and optional named `enabled: Bool` (default `true`);
`Input` takes `value: Text`, `on_change: fn(Text) -> Unit`, `label: Text`,
`kind: InputKind`, and `error: Option<Text>`. A semantic `Button` or `Input`
provides keyboard interaction and accessibility semantics, unlike a generic
painted rectangle. `Column`, `Row`, `Stack` accept `children: List<View>`;
`Grid` also requires `columns: Int`. `Scroll` accepts `child: View`. Function
parameter defaults are defined by library signatures, not user-function
syntax in v1. Duplicate named arguments are errors.

## 5. Style, layout, interaction, and animation

All styling is expressed through typed values and `View` methods. Lengths below
are `Float` logical pixels, scaled by the platform for device density; negative
padding, gaps, sizes and radii are rejected, as are non-finite values. The
layout algorithm measures children under min/max constraints, chooses a size
within them, then places them. `Column` stacks on the vertical axis and `Row`
on the horizontal axis; `gap` is between adjacent children. `Grid` arranges
children in row-major order into equal-width columns; `columns` must be positive.
`Stack` overlays children in list order. `Scroll` clips its child and scrolls
along the chosen axis. Finite parent constraints are required for `fill_width`;
an unconstrained width is a layout diagnostic, not infinity in the scene.

`padding` adds space around the previous view; `background` paints its current
bounds; therefore `v.padding(8.0).background(c)` paints the padded bounds,
while `v.background(c).padding(8.0)` leaves the padding unpainted. Other
prelude modifiers include `width`, `max_width`, `fill_width`, `align`,
`foreground`, `font_size`, `font_weight`, `border`, `corner_radius`, and
`shadow`. `Color`, `Border`, `Shadow`, `Insets`, and `FontWeight` are typed
values. Text color and font are inherited from the closest ancestor that
explicitly sets them; other properties do not inherit. There are no selectors,
stylesheets, global cascade, or specificity. Theme tokens are ordinary
immutable values passed as parameters; a component that reads a reactive theme
rebuilds when it changes.

`interaction_style` is a Button modifier taking a pure `fn(Interaction) ->
ButtonStyle`. `Interaction` has independent `hovered`, `pressed`, `focused`,
and `disabled` Bool fields. The function computes one complete style; if
several flags are true, its explicit code determines precedence. `ButtonStyle`
has `background: Color` and `foreground: Color`. `animate(duration_ms: Int)`
on a view interpolates changes to supported numeric, color, and geometry
properties of that view over the specified nonnegative duration; unsupported
properties change immediately. The platform's reduce-motion preference makes
the duration zero. Animations do not change the source state.

```plain
fn button_style(i: Interaction) -> ButtonStyle {
  let bg = if i.disabled { Color.hex("#6B7280") }
    else { if i.pressed { Color.hex("#1E3A8A") }
    else { if i.hovered { Color.hex("#1D4ED8") }
    else { Color.hex("#2563EB") } } };
  return ButtonStyle(background: bg, foreground: Color.hex("#FFFFFF"));
}

component SaveButton(on_save: fn() -> Unit) -> View {
  return Button(label: "Save", on_click: on_save)
    .padding(12.0)
    .corner_radius(8.0)
    .interaction_style(button_style)
    .animate(duration_ms: 120);
}
```

Style modifiers on a semantic control configure that control's visual box;
padding remains a wrapper as specified above. Focus rings are supplied by the
control unless explicitly replaced with an accessible equivalent. `on_key`,
`on_gesture`, `on_mount`, and `on_unmount` are typed view modifiers accepting
handlers; unmount handlers cannot write to state of the unmounted component.
A click is a semantic activation from pointer, keyboard, or accessibility API,
not only a mouse event.

### Responsive layout

`viewport()` is a pure reactive read of the window's logical size. It subscribes
the current component to changes. For reusable components, pass available
constraints explicitly rather than assuming window width. Breakpoints are normal
comparisons, with no separate media-query syntax.

```plain
struct CardData { id: Int, title: Text }

component CardGrid(cards: List<CardData>) -> View {
  let columns = if viewport().width < 600.0 { 1 }
    else { if viewport().width < 1000.0 { 2 } else { 3 } };
  let views = cards.map(fn(card: CardData) -> View {
    return Text(card.title).padding(16.0)
      .background(Color.hex("#F3F4F6"))
      .corner_radius(8.0).key(card.id);
  });
  return Grid(columns: columns, children: views).gap(16.0).padding(24.0);
}
```

Keys are unique among siblings and stable across reorderings. `key` accepts
`Int` or `Text`. Duplicate keys are a runtime diagnostic; keyed identity
includes the component type, so replacing its type resets its state.

## 6. State, events, and lifecycle

A `state` declaration appears only at the start of a component body. Its
initializer runs once per mounted instance; it must be pure and cannot read
another state cell. The declaration binds a stable `State<T>` handle, not a
plain `T`. `.value` reads the current immutable value and tracks a dependency
when executed during rendering; `.value = new_value` replaces it. No automatic
binding or implicit two-way mutation exists. Derived values are ordinary pure
expressions, recomputed on render. An optional `memo` API may cache expensive
pure computations but does not change semantics.

Events run serially on the UI thread. All synchronous writes in one handler
form a transaction: after it returns, affected components are scheduled once;
reads inside that handler see earlier writes. Runtime batches invalidations and
renders a consistent snapshot before the next frame. Dependencies are tracked
per component and replaced on each successful render, including conditional
reads. Updating an equal value causes no invalidation for types implementing
`Equal`. Rendering must not write state, even indirectly. An async suspension
ends the current transaction; writes after resumption form a new one.

Instance identity is its parent identity, component type, and sibling key, or
its position if unkeyed. A keyed reorder preserves state; removing an instance
cancels its owned tasks and drops its state. Unkeyed reorder can move state to a
different item, so use keys for changing lists. A closure captures state handles,
not snapshots; it reads current `.value` on invocation. Captures keep a weak
owner reference, and invocation after unmount is ignored. The runtime invokes
mount once after insertion and unmount once on removal, on the UI thread.

```plain
component Counter() -> View {
  state count: Int = 0;
  return Column(children: [
    Text("Count: " + count.value.to_text()),
    Button(label: "Add", on_click: fn() -> Unit {
      count.value = count.value + 1;
    }),
  ]).gap(8.0);
}
```

### Stateful form with validation

```plain
fn email_error(email: Text) -> Option<Text> {
  if not email.contains("@") { return Option.Some("Enter an email address."); }
  return Option.None;
}

component SignUp() -> View {
  state email: Text = "";
  state attempted: Bool = false;
  state submitted: Bool = false;
  let error = email_error(email.value);
  let shown_error = if attempted.value { error } else { Option.None };
  return Column(children: [
    Input(value: email.value, label: "Email", kind: InputKind.Email,
      error: shown_error, on_change: fn(value: Text) -> Unit {
        email.value = value;
        submitted.value = false;
      }),
    Button(label: "Create account", on_click: fn() -> Unit {
      attempted.value = true;
      if email_error(email.value) == Option.None { submitted.value = true; }
    }),
    if submitted.value { Text("Ready to submit.") } else { Empty() },
  ]).gap(12.0).padding(24.0).max_width(420.0);
}
```

This example validates only a minimal client-side rule and does not send data;
real applications must also validate on the server. `Input.error` is associated
with the input in the accessibility tree, and changing it is announced according
to platform accessibility settings.

## 7. Errors, async, and concurrency

Expected failures use `Result<T, E>` and exhaustive `match`; absence uses
`Option<T>`. There are no catchable exceptions in v1. Checked arithmetic,
invalid layout values and violated runtime invariants are programmer errors:
they terminate the current task with a diagnostic; they are not substitutes
for input validation. Cancellation is a distinct task outcome, not an `Err`
from an unrelated operation. No implicit error propagation operator is defined.

`async fn` returns `Task<T>` when called and does not start until awaited or
spawned. `await` is legal only inside an `async fn` or async lambda; async
lambdas are a future extension, so v1 handlers call named async functions.
`spawn` is legal only in an effectful context and starts an owned child task;
the expression returns a task handle. Tasks spawned by a handler belong to its
component and are cancelled on unmount. `await` yields without blocking the UI
thread; a UI-owned task resumes on the UI thread. Cancellation propagates to
children, is observed at suspension points, and runs cleanup owned by the
runtime. Task handles cannot outlive their owner. No blocking I/O is permitted
on the UI thread. Host I/O APIs declare their capabilities and return typed
results. Workers can run pure or explicitly isolated work; only `Send` values
may cross worker boundaries, and UI state handles are not `Send`.

```plain
async fn load_message() -> Result<Text, NetworkError> {
  return await network.get_text("https://example.com/message");
}

component Message() -> View {
  state message: Text = "Not loaded";
  return Button(label: message.value, on_click: fn() -> Unit {
    spawn update_message(message);
  });
}

async fn update_message(message: State<Text>) -> Unit {
  let result = await load_message();
  message.value = match result {
    Result.Ok(text) => text,
    Result.Err(error) => error.to_text(),
  };
}
```

The network capability must be granted by the host; denial is a `NetworkError`.
The state handle above is valid only in its UI-owned task; cancellation on
unmount prevents the subsequent write. `Channel<T>` is a bounded, FIFO async
queue: `send` waits for capacity, `receive` waits for an item, and closing
wakes waiters with a typed closed result. Channels require `Send` for cross-worker
use. No ordering is promised between independent tasks beyond each channel's
FIFO order. Ownership, effect and `Send` checking are required compiler work,
not features provided by the current prototype.

## 8. Modules, packages, and entry point

Each file begins with its module path. `import a.b;` binds the last path segment
(`b`) as a namespace; `import a.b as c;` binds `c`. Access exports as
`b.name`; there are no wildcard imports. Declarations are module-private
unless marked `public`. Prelude names are available without imports. A package
manifest identifies a name, version, entry module, capabilities, and pinned
dependencies; the exact manifest format, version resolver, registry, and ABI
are deliberately **not standardized here**. A third-party UI library is a
normal package exporting functions, components, types and immutable tokens.
There is no separate component-file format.

```plain
// package: ui_kit; file: ui_kit/buttons.plain
module ui_kit.buttons;

public struct Palette { accent: Color, on_accent: Color }

public component PrimaryButton(label: Text, palette: Palette,
                               on_click: fn() -> Unit) -> View {
  return Button(label: label, on_click: on_click)
    .padding(12.0).background(palette.accent)
    .foreground(palette.on_accent).corner_radius(8.0);
}
```

```plain
// application module
module app.main;
import ui_kit.buttons as buttons;

component App() -> View {
  let palette = buttons.Palette(accent: Color.hex("#1D4ED8"),
                                on_accent: Color.hex("#FFFFFF"));
  return buttons.PrimaryButton(label: "Continue", palette: palette,
    on_click: fn() -> Unit { log("Continue"); });
}

public fn main() -> Unit {
  run_app(App());
}
```

`run_app` mounts the root view and starts the platform event loop. The package
entry module must export `main: fn() -> Unit`. `log` and `run_app` are effectful
prelude functions and are forbidden during component rendering.

## 9. Compilation, runtime, and performance

The intended production path is ahead-of-time compilation to native machine
code, with a portable Wasm target where the host provides the required window,
rendering, input and accessibility APIs. Wasm alone cannot create a UI: a host
bridge is required. A browser host may use browser APIs internally, but cannot
promise the same no-HTML/CSS/JS implementation substrate; the language source
itself remains Plain. Native rendering is the primary no-browser target.

The compiler parses and type/effect/ownership-checks source, lowers calls and
views to an intermediate representation, specializes where profitable, and
emits optimized code. At runtime components build immutable descriptions;
dependency changes schedule reevaluation, the runtime reconciles by identity,
then Clear measures, lays out, paints, and updates the accessibility tree.
Input events are routed to handlers. Layout and paint can be skipped for
unchanged subtrees; correctness must not depend on this optimization.

Fast startup, frame pacing, bounded allocations, and small binaries are goals,
not guarantees. Native compilation does not by itself make UI code fast: shaping
text, GPU work, large lists, allocations and I/O still matter. Benchmark release
builds on representative low-end hardware using startup time, p50/p95 frame
time, memory, and binary size; publish workloads and results before claiming a
speed advantage. Hot reload is a development goal; state can be preserved only
when component identity and state types remain compatible, otherwise it resets
with a diagnostic.

## 10. Scope and conformance

This document fixes the core syntax and intended semantics above, but is not a
complete standard library, ABI, platform API, or executable implementation.
In particular, trait-object dispatch and generic bound syntax, comprehensive
Unicode identifiers, package manifest/resolution, exact event payload APIs,
full modifier signatures, serialization, networking, accessibility policy,
worker APIs, and detailed cancellation cleanup remain to be specified before a
production implementation can claim conformance. User-defined functions have no
default parameters or overloads in v1; the prelude's type/value `Text` names
and optional `Button.enabled` are explicitly defined conveniences.

A conforming implementation must at minimum parse and type-check the examples
in this document, reject state writes during rendering, preserve keyed identity,
batch synchronous event writes, follow modifier order, report invalid sizes and
duplicate keys, and provide semantic controls and the stated cancellation
behavior. Conformance tests should cover each of those guarantees and negative
cases, plus formatter round trips. Until such tests and the compiler exist,
this document is a proposal rather than evidence that those guarantees ship.
