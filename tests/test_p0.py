"""Regression tests for the P0 backlog (TODO.md §2, milestone M0).

Each class maps to one P0 item. These are deliberately behavioral: they
exercise the same entry points a user does (`App`, `plain check`, the
preview server), not private helpers, so a future refactor can keep them.
"""
from __future__ import annotations

import contextlib
import http.client
import io
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from plainlang.checker import check_program, warnings_for
from plainlang.errors import PlainError, UnsupportedYet
from plainlang.fmt import format_source
from plainlang.parser import parse_program
from plainlang.render import App
from plainlang.server import _state_dump, make_handler

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "examples").glob("*.plain"))


def messages(src):
    try:
        return [e.render() for e in check_program(parse_program(src))]
    except PlainError as e:
        return [e.render()]


# ---------------------------------------------------------------- P0-01

SLOT_SRC = '''component Panel(title, children):
  column:
    text title
    children
page Home at "/":
  name = ""
  on = no
  count = 0
  column:
    Panel "Box":
      input bind name placeholder "n"
      toggle bind on
      button "Bump" on tap: count += 1
      seen is name
      text "{seen}"
'''


class TestP001SlotScope(unittest.TestCase):
    def test_slot_bind_and_derivation_use_caller_scope(self):
        app = App(SLOT_SRC)
        app.build(400, 600)
        inp = [n for n in app.scene.walk() if n.kind == "input"][0]
        self.assertEqual(inp.bind[0], "name")
        self.assertEqual(inp.bind[1], "page:Home")   # not ""
        app.set_field(inp.path, "Ada", submit=False)
        app.build(400, 600)
        self.assertEqual(app.runtime.scopes["page:Home"].state["name"], "Ada")
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Ada", texts)                  # scoped `seen is name`

    def test_slot_toggle_and_button_mutate_page_state(self):
        app = App(SLOT_SRC)
        app.build(400, 600)
        toggle = [n for n in app.scene.walk() if n.kind == "toggle"][0]
        app.tap(toggle.path)
        app.build(400, 600)
        self.assertTrue(app.runtime.scopes["page:Home"].state["on"])
        button = [n for n in app.scene.walk() if n.kind == "button"][0]
        app.tap(button.path)
        app.build(400, 600)
        self.assertEqual(app.runtime.scopes["page:Home"].state["count"], 1)

    def test_example_06_typing_reaches_page_state(self):
        app = App.for_file(ROOT / "examples/06-form-validation.plain")
        app.build(500, 800)
        for name, value in (("name", "Ada"), ("email", "ada@example.com"),
                            ("password", "hunter2!!")):
            app.build(500, 800)
            node = [n for n in app.scene.walk()
                    if n.kind == "input" and n.bind and n.bind[0] == name][0]
            app.set_field(node.path, value, submit=False)
        app.build(500, 800)
        state = app.runtime.scopes["page:SignUp"].state
        self.assertEqual(state["name"], "Ada")
        self.assertEqual(state["email"], "ada@example.com")
        self.assertEqual(state["password"], "hunter2!!")

    def test_example_06_submit_runs_and_reports_offline(self):
        # M1: the request seam runs. With no transport configured the failed
        # branch is taken honestly, and the form stops "sending".
        app = App.for_file(ROOT / "examples/06-form-validation.plain")
        app.build(500, 800)
        for name, value in (("name", "Ada"), ("email", "ada@example.com"),
                            ("password", "hunter2!!")):
            app.build(500, 800)
            node = [n for n in app.scene.walk()
                    if n.kind == "input" and n.bind and n.bind[0] == name][0]
            app.set_field(node.path, value, submit=False)
        app.build(500, 800)
        btn = [n for n in app.scene.walk()
               if n.kind == "button" and "Create account" in n.text][0]
        app.tap(btn.path)
        app.build(500, 800)
        state = app.runtime.scopes["page:SignUp"].state
        self.assertTrue(state["touched"])
        self.assertFalse(state["sending"])
        self.assertIn("offline", state["server-problem"])
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertTrue(any("offline" in t for t in texts))


# ---------------------------------------------------------------- P0-02

AVATAR_SRC = '''component Avatar(person, size = 40):
  text person size size
page Home at "/":
  column:
    CALL
'''


class TestP002ComponentDefaults(unittest.TestCase):
    def sizes(self, call):
        app = App(AVATAR_SRC.replace("CALL", call))
        app.build(400, 600)
        return [(n.text, n.props.get("size")) for n in app.scene.walk()
                if n.kind == "text"]

    def test_default_applies(self):
        self.assertEqual(self.sizes('Avatar "Ada"'), [("Ada", 40)])

    def test_positional_argument_overrides_default(self):
        self.assertEqual(self.sizes('Avatar "Ada" 56'), [("Ada", 56)])

    def test_named_argument_overrides_default(self):
        self.assertEqual(self.sizes('Avatar "Ada" size 56'), [("Ada", 56)])

    def test_missing_required_argument_is_a_plain_sentence(self):
        with self.assertRaises(PlainError) as caught:
            App(AVATAR_SRC.replace("CALL", "Avatar")).build(400, 600)
        rendered = caught.exception.render()
        self.assertIn("`Avatar` needs `person`.", rendered)
        self.assertIn("Try: pass a value", rendered)
        self.assertIn("^^^^^^", rendered)

    def test_extra_positional_argument_errors(self):
        with self.assertRaises(PlainError) as caught:
            App(AVATAR_SRC.replace("CALL", 'Avatar "Ada" 1 2')).build(400, 600)
        self.assertIn("takes 2 values, but got 3", caught.exception.message)

    def test_duplicate_binding_errors(self):
        with self.assertRaises(PlainError) as caught:
            App(AVATAR_SRC.replace("CALL", 'Avatar "Ada" 56 size 60')).build(400, 600)
        self.assertIn("given twice", caught.exception.message)

    def test_checker_validates_default_expressions(self):
        msgs = messages('component C(x = 1 +):\n  text "x"\n'
                        'page Home at "/":\n  C\n')
        self.assertTrue(any("default for `x`" in m for m in msgs), msgs)


# ---------------------------------------------------------------- P0-03

class TestP003NeverSilentlyInert(unittest.TestCase):
    SRC = '''theme:
  color ink #000000
use "./x.plain"
page Home at "/":
  transition slide
  column:
    image "x" on swipe-start: go back
'''

    def test_every_future_construct_has_a_visible_note(self):
        prog = parse_program(self.SRC)
        notes = "\n".join(w.render() for w in warnings_for(prog))
        self.assertIn("`theme` is valid PL", notes)
        self.assertIn("`use` is valid PL", notes)
        self.assertIn("`transition` is valid PL", notes)
        self.assertIn("`on swipe-start` is valid PL", notes)
        self.assertEqual(check_program(prog), [])  # warnings, not errors

    def test_firing_an_unsupported_gesture_fails_loudly(self):
        app = App.for_file(ROOT / "examples/07-page-transition.plain")
        app.build(412, 800)
        first = [n for n in app.scene.walk() if n.kind == "image"][0]
        app.tap(first.path)  # Gallery -> Detail, where pinch is declared
        app.build(412, 800)
        target = [n for n in app.scene.walk() if "pinch" in n.events][0]
        with self.assertRaises(UnsupportedYet) as caught:
            app.fire(target.path, "pinch")
        self.assertIn("on pinch", caught.exception.message)

    def test_check_cli_prints_notes_without_failing(self):
        from plainlang.cli import main
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "future.plain"
            f.write_text(self.SRC, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(["check", str(f)])
            self.assertEqual(code, 0)
            self.assertIn("note:", out.getvalue())
            self.assertIn("OK", out.getvalue())


# ---------------------------------------------------------------- P0-04

class TestP004Secrets(unittest.TestCase):
    SRC = '''page Home at "/":
  password = ""
  column:
    input bind password secret placeholder "pw"
'''

    def test_secret_never_reaches_svg_or_state_panel(self):
        app = App(self.SRC)
        app.build(400, 600)
        field = [n for n in app.scene.walk() if n.kind == "input"][0]
        app.set_field(field.path, "hunter2", submit=False)
        svg = app.svg(400, 600)
        dump = _state_dump(app)
        self.assertNotIn("hunter2", svg)
        self.assertNotIn("hunter2", dump)
        self.assertIn("••", svg)
        self.assertIn("••", dump)

    def test_plain_input_still_paints_its_value(self):
        app = App('page Home at "/":\n  name = ""\n  column:\n'
                  '    input bind name placeholder "name"\n')
        app.build(400, 600)
        field = [n for n in app.scene.walk() if n.kind == "input"][0]
        app.set_field(field.path, "Ada", submit=False)
        self.assertIn("Ada", app.svg(400, 600))


# ---------------------------------------------------------------- P0-05

class TestP005Formatter(unittest.TestCase):
    def test_corpus_is_already_canonical(self):
        for f in EXAMPLES:
            with self.subTest(file=f.name):
                text = f.read_text(encoding="utf-8")
                self.assertEqual(format_source(text), text)

    def test_twice_is_a_no_op(self):
        messy = ('page Home at "/":\n'
                 '  # about the column\n'
                 '  column width fill:\n'
                 '    text "hi"\n'
                 '\n\n\n'
                 '  text "x"\n')
        once = format_source(messy)
        self.assertEqual(format_source(once), once)
        self.assertIn('  # about the column\n  column', once)
        self.assertNotIn("\n\n\n", once)

    def test_continuation_alignment_is_preserved(self):
        src = 'page Home at "/":\n  column:\n    text "x" color accent\n' \
              '                or card\n'
        once = format_source(src)
        self.assertIn('    text "x" color accent\n', once)
        self.assertIn('                or card', once)
        self.assertEqual(format_source(once), once)

    def test_write_twice_is_a_no_op(self):
        from plainlang.cli import main
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "messy.plain"
            f.write_text('page Home at "/":\n  column:\n    text "x"\n\n\n',
                         encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["fmt", "--write", str(f)]), 0)
            once = f.read_text(encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["fmt", "--write", str(f)]), 0)
            self.assertEqual(f.read_text(encoding="utf-8"), once)

    def test_cli_fmt_check_on_corpus(self):
        from plainlang.cli import main
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["fmt", "--check", *map(str, EXAMPLES)])
        self.assertEqual(code, 0, out.getvalue() + err.getvalue())


# ---------------------------------------------------------------- P0-06

class TestP006ActionPreflight(unittest.TestCase):
    def test_chat_send_fails_offline_and_restores_draft(self):
        app = App.for_file(ROOT / "examples/04-chat.plain")
        app.build(412, 800)
        field = [n for n in app.scene.walk()
                 if n.kind == "input" and n.bind and n.bind[0] == "draft"][0]
        app.set_field(field.path, "hello", submit=False)
        app.build(412, 800)
        btn = [n for n in app.scene.walk()
               if n.kind == "button" and n.text == "Send"][0]
        app.tap(btn.path)
        app.build(412, 800)
        state = app.runtime.scopes["page:RoomPage"].state
        self.assertEqual(state["draft"], "hello")       # restored by failure
        self.assertIn("offline", state["problem"].lower())
        self.assertIn("offline", app.runtime.last_request["result"][1])

    def test_show_toast_is_visible_to_the_app(self):
        app = App('page Home at "/":\n  column:\n'
                  '    button "b" on tap: show toast "hi"\n')
        app.build()
        btn = [n for n in app.scene.walk() if n.kind == "button"][0]
        app.tap(btn.path)
        self.assertEqual(app.runtime.toasts, ["hi"])

    def test_refresh_is_a_plain_stage_3_message(self):
        app = App('page Home at "/":\n  to r:\n    refresh x\n'
                  '  column:\n    button "b" on tap r\n')
        app.build()
        btn = [n for n in app.scene.walk() if n.kind == "button"][0]
        with self.assertRaises(UnsupportedYet) as caught:
            app.tap(btn.path)
        self.assertIn("refresh", caught.exception.message)


# ---------------------------------------------------------------- P0-07

class TestP007NoDeadCode(unittest.TestCase):
    def test_no_known_dead_code_patterns(self):
        bad = {"if False": [], "pass  #": [], "wrapper =": [],
               "_stretch_growers": []}
        for f in (ROOT / "src/plainlang").glob("*.py"):
            text = f.read_text(encoding="utf-8")
            for needle in bad:
                if needle in text:
                    bad[needle].append(f.name)
        self.assertEqual({k: v for k, v in bad.items() if v}, {})

    def test_grow_flag_was_a_no_op_and_is_gone(self):
        from plainlang import layout
        self.assertFalse(hasattr(layout, "_stretch_growers"))


# ---------------------------------------------------------------- P0-08

class TestP008CheckerVisitsActions(unittest.TestCase):
    def test_unknown_node_inside_action_is_reported(self):
        msgs = messages('page Home at "/":\n  to go:\n'
                        '    buton "x" on tap go\n  column:\n'
                        '    button "x" on tap go\n')
        self.assertTrue(any("did you mean `button`" in m for m in msgs), msgs)

    def test_unknown_property_inside_action_node_is_reported(self):
        msgs = messages('page Home at "/":\n  to go:\n'
                        '    text "x" colour red\n  column:\n'
                        '    button "x" on tap go\n')
        self.assertTrue(any("no property called `colour`" in m for m in msgs), msgs)

    def test_all_examples_stay_ok(self):
        for f in EXAMPLES:
            with self.subTest(file=f.name):
                self.assertEqual(
                    [e.render() for e in check_program(
                        parse_program(f.read_text(encoding="utf-8")))], [])


# ---------------------------------------------------------------- P0-09

class TestP009ErrorSpans(unittest.TestCase):
    SNAPSHOTS = {
        "missing_action": (
            'page Home at "/":\n  column:\n    button "x" on tap nope\n',
            'Line 3: There\'s no action called `nope` here for `on tap` to run.\n'
            '   button "x" on tap nope\n'
            '              ^^^^^^\n'
            'Try: write it as `to nope:` in this page/component'),
        "unknown_prop": (
            'page Home at "/":\n  column:\n    text "hi" colour red\n',
            'Line 3: `text` has no property called `colour`.\n'
            '   text "hi" colour red\n'
            '             ^^^^^^\n'
            'Try: did you mean `color`?'),
        "empty_button": (
            'page Home at "/":\n  column:\n    button\n',
            'Line 3: `button` needs something to show.\n'
            '   button\n'
            '   ^^^^^^\n'
            'Try: button "Save"'),
        "no_address": (
            'page Home:\n  column:\n    text "x"\n',
            'Line 1: Page `Home` has no address. Pages need one so people '
            '(and links) can reach them.\n'
            '   page Home:\n'
            '   ^^^^^^^^^\n'
            'Try: page Home at "/":'),
        "duplicate_state": (
            'page Home at "/":\n  x = 1\n  x = 2\n  column:\n    text "x"\n',
            'Line 3: `x` is already created on line 2. One name, one value — '
            'pick a different name for the second one.\n'
            '   x = 2\n'
            '   ^'),
        "bad_indent": (
            'page Home at "/":\n   column:\n      text "x"\n',
            'Line 2: This line is indented 3 spaces. PL indents 2 spaces at '
            "a time, so this one's halfway between levels.\n"
            '   column:\n'
            '   ^^^^^^^\n'
            'Try: indent it 2 or 4 spaces'),
        "action_typo": (
            'page Home at "/":\n  to go:\n    buton "x" on tap go\n'
            '  column:\n    button "x" on tap go\n',
            'Line 3: `buton` isn\'t a thing PL knows how to draw.\n'
            '   buton "x" on tap go\n'
            '   ^^^^^\n'
            'Try: did you mean `button`?'),
    }

    def test_exact_caret_snapshots(self):
        for name, (src, expected) in self.SNAPSHOTS.items():
            with self.subTest(case=name):
                got = messages(src)
                self.assertIn(expected, got)

    def test_component_error_points_at_the_call(self):
        with self.assertRaises(PlainError) as caught:
            App(AVATAR_SRC.replace("CALL", "Avatar")).build(400, 600)
        self.assertEqual(
            caught.exception.render(),
            'Line 5: `Avatar` needs `person`.\n'
            '   Avatar\n'
            '   ^^^^^^\n'
            'Try: pass a value, e.g. `Avatar "Ada"`')

    def test_warning_also_has_a_caret(self):
        notes = warnings_for(parse_program(
            'page Home at "/":\n  transition slide\n  column:\n'
            '    text "x"\n'))
        self.assertEqual(
            notes[0].render(),
            'Line 2: note: `transition` is valid PL, but page transitions '
            'are not animated yet (planned: Stage 3).\n'
            '   transition slide\n'
            '   ^^^^^^^^^^\n'
            'Try: the page still swaps instantly; motion lands with the '
            'animation engine')

    def test_spans_are_on_the_ast(self):
        prog = parse_program(
            'page Home at "/":\n  column:\n'
            '    button "x" colour red on tap go\n')
        node = prog.pages["Home"].body[0].children[0]
        self.assertEqual((node.col, node.length), (1, 6))
        self.assertEqual(node.raw, 'button "x" colour red on tap go')
        prop = [p for p in node.props if p.name == "colour"][0]
        self.assertEqual((prop.col, prop.length), (12, 6))
        event = node.events[0]
        self.assertEqual((event.col, event.length), (23, 6))


# ---------------------------------------------------------------- P0-10

class TestP010PreviewSessions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.plain = Path(self.temp.name) / "app.plain"
        self.plain.write_text(
            'page Home at "/":\n  name = ""\n  column:\n'
            '    input bind name\n    text "{name}"\n', encoding="utf-8")
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.plain, 800, 600))
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, body=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        out = (resp.status, resp.getheader("Set-Cookie"), data)
        conn.close()
        return out

    def test_each_client_gets_its_own_session(self):
        status_a, cookie_a, page = self.request("GET", "/")
        status_b, cookie_b, _ = self.request("GET", "/")
        self.assertEqual((status_a, status_b), (200, 200))
        self.assertIn("plainsid=", cookie_a)
        self.assertIn("plainsid=", cookie_b)
        self.assertNotEqual(cookie_a, cookie_b)

        path = re.search(rb'data-path="([^"]+)"', page).group(1).decode()
        sc, _, _ = self.request(
            "POST", "/sync?size=desktop",
            body=f"f_{path}=hello".encode(),
            cookie=cookie_a.split(";")[0])
        self.assertEqual(sc, 204)
        _, _, svg_a = self.request("GET", "/app.svg",
                                   cookie=cookie_a.split(";")[0])
        _, _, svg_b = self.request("GET", "/app.svg",
                                   cookie=cookie_b.split(";")[0])
        self.assertIn(b"hello", svg_a)
        self.assertNotIn(b"hello", svg_b)

    def test_viewport_and_error_statuses(self):
        status, _, svg = self.request("GET", "/app.svg?size=small")
        self.assertEqual(status, 200)
        self.assertIn(b'width="480.0"', svg)
        status, _, body = self.request("GET", "/tap/root/does-not-exist")
        self.assertEqual(status, 400)
        self.assertIn(b"Nothing at", body)


# ---------------------------------------------------------------- P0-11

class TestP011DocsMatchReality(unittest.TestCase):
    def test_readme_test_count_is_true(self):
        count = sum(len(re.findall(r"^    def test_", f.read_text(encoding="utf-8"),
                                   re.M))
                    for f in (ROOT / "tests").glob("test_*.py"))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs/06-stage1-prototype.md").read_text(encoding="utf-8")
        self.assertIn(f"{count} spec-oracle tests", readme)
        self.assertIn(f"{count} tests", docs)
        self.assertNotIn("22 tests", readme)
        self.assertNotIn("22 tests", docs)

    def test_example_count_is_true(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(len(EXAMPLES), 9)
        self.assertIn("all 9 examples", readme)
        docs = (ROOT / "docs/06-stage1-prototype.md").read_text(encoding="utf-8")
        self.assertIn("all 9 normative examples", docs)

    def test_docs_06_toc_matches_body(self):
        docs = (ROOT / "docs/06-stage1-prototype.md").read_text(encoding="utf-8")
        self.assertIn("G-1…G-10", docs)
        self.assertIn("G-10", docs)


# ---------------------------------------------------------------- P0-12

class TestP012CI(unittest.TestCase):
    def test_validate_fails_when_nothing_matches(self):
        from plainlang.cli import main
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["validate", "examples/nope*.plain"]), 1)

    def test_validate_enforces_golden_floors(self):
        from plainlang.cli import main
        with tempfile.TemporaryDirectory() as td:
            baseline = Path(td) / "baseline.json"
            baseline.write_text(json.dumps({
                "00-hello-world.plain": {"nodes": 999, "svg_bytes": 1}
            }), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                code = main(["validate", "examples/00-hello-world.plain",
                             "--baseline", str(baseline)])
            self.assertEqual(code, 1)

    def test_committed_baseline_covers_all_examples(self):
        baseline = json.loads(
            (ROOT / "tests/example_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(set(baseline), {f.name for f in EXAMPLES})
        from plainlang.cli import main
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["validate"]), 0)

    def test_ci_runs_fmt_and_golden_validate(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("fmt --check", ci)
        self.assertIn("./plain validate", ci)
        make = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("fmt-check", make)


if __name__ == "__main__":
    unittest.main()
