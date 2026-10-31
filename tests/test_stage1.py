"""Stage-1 prototype tests. Run:  make test
   (PYTHONPATH=src python3 -m unittest discover -s tests -v)
"""
import unittest
from pathlib import Path

from plainlang import a11y as a11y_mod
from plainlang.ast_nodes import IfNode, Node
from plainlang.checker import check_program
from plainlang.errors import PlainError, UnsupportedYet
from plainlang.expr import evaluate_text
from plainlang.parser import parse_program
from plainlang.render import App

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "examples").glob("*.plain"))


def src_of(name):
    return (ROOT / "examples" / name).read_text(encoding="utf-8")


class TestCorpus(unittest.TestCase):
    def test_all_examples_parse_and_check(self):
        self.assertGreaterEqual(len(EXAMPLES), 9)
        for f in EXAMPLES:
            with self.subTest(file=f.name):
                prog = parse_program(f.read_text(encoding="utf-8"))
                errors = check_program(prog)
                self.assertEqual([e.render() for e in errors], [])


class TestParser(unittest.TestCase):
    def test_hello_structure(self):
        prog = parse_program(src_of("00-hello-world.plain"))
        page = prog.pages["Home"]
        self.assertEqual(page.path, "/")
        col = page.body[-1]
        self.assertEqual(col.kind, "column")
        texts = [c for c in col.children if isinstance(c, Node)]
        self.assertEqual([t.content for t in texts],
                         ["Hello, world.", "This whole app is this file."])

    def test_hyphenated_names_are_single_names(self):
        self.assertEqual(evaluate_text("sort-by", {"sort-by": "name"}), "name")

    def test_hex_color_is_not_a_comment(self):
        v = evaluate_text('Finish("Oak", #B08968, 0)', {},
                          parse_program(src_of("08-viewer-3d.plain")).kinds)
        self.assertEqual(v["tint"], "#B08968")

    def test_button_line_is_not_an_assignment(self):
        # regression: `button "−1" on tap: count -= 1` classified as Assign
        prog = parse_program(src_of("01-counter.plain"))
        col = prog.components["Counter"].body[-1]
        row = [c for c in col.children if isinstance(c, Node) and c.kind == "row"][0]
        self.assertEqual([b.content for b in row.children], ["−1", "Reset", "+1"])

    def test_otherwise_pairs_inside_node_children(self):
        # regression: else branches silently dropped in node children
        prog = parse_program(src_of("02-todo.plain"))
        col = prog.pages["Home"].body[-1]

        def find_if(stmts):
            for s in stmts:
                if isinstance(s, IfNode):
                    return s
                for sub in getattr(s, "children", []):
                    if isinstance(sub, IfNode):
                        return sub
            return None

        ifn = find_if(col.children)
        self.assertIsNotNone(ifn)
        self.assertTrue(ifn.else_body, "otherwise branch must be attached")

    def test_bad_indent_is_plain_error(self):
        with self.assertRaises(PlainError) as cm:
            parse_program('page Home at "/":\n   column:\n    text "hi"\n')
        self.assertIn("indented 3 spaces", str(cm.exception))


class TestChecker(unittest.TestCase):
    def test_empty_button_matches_spec_error(self):
        prog = parse_program('page Home at "/":\n  column:\n    button on tap save\n')
        msgs = [e.render() for e in check_program(prog)]
        self.assertTrue(any("`button` needs something to show." in m
                            and 'Try: button "Save" on tap save' in m
                            for m in msgs), msgs)

    def test_misspelled_node_suggests(self):
        prog = parse_program('page Home at "/":\n  colunm:\n    text "hi"\n')
        msgs = [e.render() for e in check_program(prog)]
        self.assertTrue(any("did you mean `column`" in m for m in msgs), msgs)

    def test_misspelled_property_suggests_once(self):
        prog = parse_program('page Home at "/":\n  column:\n    text "hi" colour red\n')
        msgs = [e.render() for e in check_program(prog)]
        colour = [m for m in msgs if "colour" in m]
        self.assertEqual(len(colour), 1, msgs)
        self.assertIn("did you mean `color`", colour[0])

    def test_page_needs_address(self):
        prog = parse_program('page Home:\n  column:\n    text "hi"\n')
        msgs = [e.render() for e in check_program(prog)]
        self.assertTrue(any("no address" in m for m in msgs), msgs)


class TestExpressions(unittest.TestCase):
    def test_where_is_greedy_and_per_item(self):
        tasks = [{"title": "a", "done": False}, {"title": "b", "done": True}]
        got = evaluate_text('tasks where show is "all" or (show is "x" and not done)',
                            {"tasks": tasks, "show": "x"})
        self.assertEqual([t["title"] for t in got], ["a"])

    def test_count_where(self):
        tasks = [{"done": False}, {"done": True}, {"done": False}]
        self.assertEqual(
            evaluate_text("tasks count where not done", {"tasks": tasks}), 2)

    def test_conditional_and_interpolation(self):
        env = {"count": 10}
        self.assertEqual(
            evaluate_text('"getting warm" if count >= 10 otherwise "just starting"', env),
            "getting warm")
        from plainlang.expr import interpolate
        self.assertEqual(interpolate("Count: {count}", env), "Count: 10")

    def test_trimmed_is_empty(self):
        self.assertTrue(evaluate_text("draft trimmed is empty", {"draft": "  "}))

    def test_record_defaults(self):
        kinds = parse_program(src_of("02-todo.plain")).kinds
        task = evaluate_text('Task(title: "Buy milk")', {}, kinds)
        self.assertEqual(task["title"], "Buy milk")
        self.assertEqual(task["done"], False)


class TestRuntimeAndScene(unittest.TestCase):
    def _buttons(self, app):
        return {n.text: n.path for n in app.scene.walk() if n.kind == "button"}

    def test_counter_full_interaction(self):
        app = App(src_of("01-counter.plain"))
        app.build()
        ui = self._buttons(app)
        self.assertEqual(set(ui), {"−1", "Reset", "+1"})
        for _ in range(10):
            app.tap(ui["+1"])
            app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Count: 10", texts)
        self.assertIn("getting warm", texts)  # derived `mood is …`
        app.tap(self._buttons(app)["Reset"])
        app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Count: 0", texts)
        self.assertIn("just starting", texts)

    def test_todo_empty_then_add_via_action(self):
        app = App(src_of("02-todo.plain"))
        app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Nothing here yet. Add your first task above.", texts)
        self.assertTrue({"All", "Open", "Done"} <= set(texts))  # capitalize flag
        sc = app.runtime.scopes["page:Home"]
        sc.state["draft"] = "  Buy milk  "
        app.runtime.call_action(sc, "add-task")
        app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Buy milk", texts)
        self.assertIn("1 to go", texts)  # otherwise-branch + derivation
        self.assertEqual(sc.state["tasks"][0]["done"], False)

    def test_hello_layout_centers_content(self):
        app = App(src_of("00-hello-world.plain"))
        scene = app.build(800, 600)
        hello = [n for n in scene.walk() if n.text == "Hello, world."][0]
        self.assertAlmostEqual(hello.x + hello.w / 2, 400, delta=2)
        self.assertTrue(200 < hello.y < 400, f"y={hello.y} (spread center)")

    def test_a11y_is_derived_not_written(self):
        source = src_of("01-counter.plain")
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#"))
        import re as _re
        for word in ("aria", "role", "accessibility", "tabindex", "semantics"):
            self.assertIsNone(_re.search(rf"\b{word}\b", code.lower()),
                              f"a11y term {word!r} must not be needed in source")
        app = App(source)
        scene = app.build()
        tree = a11y_mod.derive(scene)
        flat = []

        def walk(t):
            flat.append((t["role"], t["label"]))
            for c in t["children"]:
                walk(c)

        walk(tree)
        self.assertIn(("button", "+1"), flat)
        self.assertIn(("heading", "Count: 0"), flat)

    def test_hot_reload_preserves_state(self):
        # Re-parsing (as the dev server does per request) must NOT reset
        # state; renaming a state variable re-initializes only that one.
        from plainlang.parser import parse_program as pp
        from plainlang.runtime import Runtime
        from plainlang.scene import SceneBuilder
        src = src_of("01-counter.plain")
        rt = Runtime(pp(src))
        app1 = App(src)
        app1.runtime = rt
        app1.builder = SceneBuilder(app1.program, rt)
        app1.build()
        plus = {n.text: n.path for n in app1.scene.walk() if n.kind == "button"}["+1"]
        for _ in range(3):
            app1.tap(plus)
            app1.build()
        # simulate reload: brand-new App (new AST), same Runtime object
        prog2 = pp(src.replace("just starting", "warming up"))
        rt.program = prog2
        scene = SceneBuilder(prog2, rt).build_page(prog2.first_page())
        texts = [n.text for n in scene.walk() if n.text]
        self.assertIn("Count: 3", texts)       # state survived the edit
        self.assertIn("warming up", texts)      # ...while the edit applied

    def test_svg_golden_sanity(self):
        svg = App(src_of("00-hello-world.plain")).svg(800, 600)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Hello, world.", svg)
        # deterministic: same input → same bytes
        self.assertEqual(svg, App(src_of("00-hello-world.plain")).svg(800, 600))


class TestStage2(unittest.TestCase):
    """Doc 05 Stage-2 scope: interactive inputs, responsive width,
    persistence, name resolution, formatter."""

    def test_todo_by_typing_end_to_end(self):
        app = App.for_file(ROOT / "examples/02-todo.plain")
        app.build()
        box = [n for n in app.scene.walk() if n.kind == "input"][0]
        app.set_field(box.path, "Write tests", submit=True)  # type + Enter
        app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Write tests", texts)
        self.assertIn("1 to go", texts)
        # flip the task's toggle → done → "0 to go"
        tog = [n for n in app.scene.walk() if n.kind == "toggle"][0]
        app.tap(tog.path)
        app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("0 to go", texts)

    def test_navbar_is_container_responsive(self):
        wide = App.for_file(ROOT / "examples/03-navbar.plain")
        wide.build(800, 600)
        wide_texts = {n.text for n in wide.scene.walk() if n.text}
        self.assertIn("Docs", wide_texts)
        self.assertNotIn("Menu", wide_texts)
        narrow = App.for_file(ROOT / "examples/03-navbar.plain")
        narrow.build(390, 700)
        narrow_texts = {n.text for n in narrow.scene.walk() if n.text}
        self.assertIn("Menu", narrow_texts)
        self.assertNotIn("Docs", narrow_texts)

    def test_keep_persists_across_apps(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / "state.json"
            src = src_of("02-todo.plain")
            app = App(src, persist_path=store)
            app.build()
            box = [n for n in app.scene.walk() if n.kind == "input"][0]
            app.set_field(box.path, "Kept task", submit=True)
            fresh = App(src, persist_path=store)  # new runtime, same file
            fresh.build()
            texts = [n.text for n in fresh.scene.walk() if n.text]
            self.assertIn("Kept task", texts)

    def test_checker_unknown_action_and_look(self):
        prog = parse_program(
            'page Home at "/":\n  column:\n'
            '    button "Go" on tap fly\n    text "x" look fancy\n')
        msgs = [e.render() for e in check_program(prog)]
        self.assertTrue(any("no action called `fly`" in m for m in msgs), msgs)
        self.assertTrue(any("no look called `fancy`" in m for m in msgs), msgs)

    def test_fmt_idempotent_and_still_checks(self):
        from plainlang.fmt import format_source
        for f in EXAMPLES:
            with self.subTest(file=f.name):
                once = format_source(f.read_text(encoding="utf-8"))
                self.assertEqual(format_source(once), once)
                self.assertEqual(check_program(parse_program(once)), [])

    def test_long_text_wraps(self):
        app = App('page Home at "/":\n  column width 200 padding 10:\n'
                  '    text "one two three four five six seven eight nine ten"\n')
        scene = app.build(800, 600)
        t = [n for n in scene.walk() if n.kind == "text"][0]
        self.assertGreater(len(t.props["_lines"]), 1)
        self.assertGreater(t.h, 16 * 1.3 * 1.5)


class TestStage3(unittest.TestCase):
    """Doc 05 Stage-3 core: resources + when, navigation, tables, forms."""

    def test_chat_resource_renders_messages(self):
        app = App.for_file(ROOT / "examples/04-chat.plain")
        app.build(412, 800)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("General", texts)               # page param (sidecar)
        self.assertIn("Selam! Welcome to General 👋", texts)

    def test_datatable_search_sort_paginate(self):
        app = App.for_file(ROOT / "examples/05-datatable.plain")
        app.build(1000, 700)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Tigist Worku", texts)
        box = [n for n in app.scene.walk() if n.kind == "input"][0]
        app.set_field(box.path, "Design", submit=False)
        app.build(1000, 700)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Selam Tesfaye", texts)
        self.assertNotIn("Tigist Worku", texts)
        self.assertIn("2 people · page 1 of 1", texts)

    def test_gallery_navigation_push_and_back(self):
        app = App.for_file(ROOT / "examples/07-page-transition.plain")
        app.build(412, 800)
        img = [n for n in app.scene.walk() if n.kind == "image"][0]
        app.tap(img.path)
        self.assertEqual(app.stack[-1][0], "Detail")
        app.build(412, 800)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Rock churches of Lalibela", texts)
        back = [n for n in app.scene.walk()
                if n.kind == "button" and n.text == "Back"][0]
        app.tap(back.path)
        self.assertEqual(app.stack[-1][0], "Gallery")

    def test_form_validation_flow(self):
        # Derivations are always correct; the UI stays quiet until `touched`.
        app = App.for_file(ROOT / "examples/06-form-validation.plain")
        app.build(500, 800)
        scope = app.runtime.scopes["page:SignUp"]
        # Submitting is honestly blocked: the fixture's next step is a real
        # network call, which is Stage 3 (P0-06). Nothing mutates first.
        btn = [n for n in app.scene.walk()
               if n.kind == "button" and "Create account" in n.text][0]
        with self.assertRaises(UnsupportedYet):
            app.tap(btn.path)
        self.assertFalse(scope.state["touched"])
        # Derivations are ready; the UI shows them once `touched` is set.
        scope.state["touched"] = True
        app.build(500, 800)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Please enter your name.", texts)
        self.assertIn("Use at least 8 characters.", texts)

    def test_configurator_one_state_drives_2d_and_3d(self):
        app = App.for_file(ROOT / "examples/08-viewer-3d.plain")
        app.build(900, 600)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("$334", texts)  # 299 + 0 (Oak) + 35 cushion
        self.assertIn("3D · /models/chair.glb", app.svg(900, 600))
        swatches = [n for n in app.scene.walk()
                    if n.kind == "box" and "tap" in n.events]
        self.assertEqual(len(swatches), 3)
        app.tap(swatches[1].path)  # Walnut (+40)
        app.build(900, 600)
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("$374", texts)

    def test_disabled_button_does_not_fire(self):
        app = App('component C:\n  n = 0\n  column:\n'
                  '    button "B" disabled if yes on tap: n += 1\n'
                  '    text "{n}"\npage Home at "/":\n  C\n')
        app.build()
        btn = [n for n in app.scene.walk() if n.kind == "button"][0]
        app.tap(btn.path)
        app.build()
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("0", texts)


if __name__ == "__main__":
    unittest.main()
