"""M1: actions actually run — Result values, requests, `when`, `then`, toasts.

Tests use a local HTTP server only (NET-10: no external network in CI).
"""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from plainlang.render import App

class _Handler(BaseHTTPRequestHandler):
    requests = 0
    flaky_hits = 0
    post_flaky_hits = 0

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        type(self).requests += 1
        if self.path == "/data":
            return self._json({"name": "Ada", "role": "engineer"})
        if self.path == "/flaky":
            type(self).flaky_hits += 1
            if type(self).flaky_hits < 3:
                return self._json({"_error": "try later"}, 503)
            return self._json({"name": "Ada"})
        return self._json({"_error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/flaky-post":
            type(self).post_flaky_hits += 1
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            return self._json({"_error": "try later"}, 503)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            payload = raw.decode("utf-8")
        return self._json({"echo": payload, "saved": True})


class TestM1Requests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def tap_button(self, app, label=None):
        app.build(400, 600)
        buttons = [n for n in app.scene.walk() if n.kind == "button"]
        btn = next((b for b in buttons if label and b.text == label), buttons[0])
        app.tap(btn.path)
        app.build(400, 600)
        return app

    def test_fetch_result_and_when_ok(self):
        app = App(f'''page Home at "/":
  got = "loading"
  to load:
    result = fetch "{self.base}/data"
    when result:
      is ok value: got = value.name
      is failed why: got = why as sentence
  column:
    button "Load" on tap load
    text "{{got}}"
''')
        self.tap_button(app)
        self.assertEqual(app.runtime.scopes["page:Home"].state["got"], "Ada")
        self.assertEqual(app.runtime.last_request["method"], "GET")

    def test_post_with_body_returns_result(self):
        app = App(f'''page Home at "/":
  name = "Ada"
  got = "none"
  to save:
    result = post "{self.base}/save" with name
    when result:
      is ok saved: got = saved.echo.name
      is failed why: got = why as sentence
  column:
    button "Save" on tap save
''')
        self.tap_button(app)
        self.assertEqual(app.runtime.scopes["page:Home"].state["got"], "Ada")
        self.assertEqual(app.runtime.last_request["method"], "POST")
        self.assertEqual(app.runtime.last_request["body"], {"name": "Ada"})

    def test_get_retries_transient_failures(self):
        _Handler.flaky_hits = 0
        app = App(f'''page Home at "/":
  got = "loading"
  to load:
    result = fetch "{self.base}/flaky"
    when result:
      is ok value: got = value.name
      is failed why: got = why as sentence
  column:
    button "Load" on tap load
    text "{{got}}"
''')
        self.tap_button(app)
        self.assertEqual(app.runtime.scopes["page:Home"].state["got"], "Ada")
        self.assertEqual(_Handler.flaky_hits, 3)

    def test_post_is_not_retried(self):
        # A blind POST replay can duplicate a write; offline queueing is NET-04.
        _Handler.post_flaky_hits = 0
        app = App(f'''page Home at "/":
  got = "loading"
  to save:
    result = post "{self.base}/flaky-post" body "x"
    when result:
      is ok value: got = "saved"
      is failed why: got = why as sentence
  column:
    button "Save" on tap save
''')
        self.tap_button(app)
        self.assertEqual(app.runtime.scopes["page:Home"].state["got"],
                         "server 503")
        self.assertEqual(_Handler.post_flaky_hits, 1)

    def test_fixture_success_can_navigate(self):
        src = '''page Home at "/":
  name = "Ada"
  problem = nothing
  to save:
    result = post "/api/save" with name
    when result:
      is ok saved: go to Done(saved)
      is failed why: problem = why as sentence
  column:
    button "Save" on tap save
page Done(account) at "/done":
  column:
    text "Saved {account.id}"
'''
        app = App(src, providers={"POST /api/save": {"_ok": {"id": 7}}})
        self.tap_button(app, "Save")
        self.assertEqual(app.stack[-1][0], "Done")
        texts = [n.text for n in app.scene.walk() if n.text]
        self.assertIn("Saved 7", texts)

    def test_offline_failure_is_a_sentence_not_a_crash(self):
        app = App('''page Home at "/":
  name = "Ada"
  problem = nothing
  to save:
    result = post "/api/save" with name
    when result:
      is ok saved: problem = "saved"
      is failed why: problem = why as sentence
  column:
    button "Save" on tap save
''')
        self.tap_button(app, "Save")
        problem = app.runtime.scopes["page:Home"].state["problem"]
        self.assertIn("offline", problem)
        self.assertIn("/api/save", problem)

    def test_fixture_failure_uses_why(self):
        app = App('''page Home at "/":
  problem = nothing
  to load:
    result = fetch "/api/data"
    when result:
      is ok value: problem = "ok"
      is failed why: problem = why as sentence
  column:
    button "Load" on tap load
''', providers={"FETCH /api/data": {"_failed": "denied"}})
        self.tap_button(app, "Load")
        self.assertEqual(app.runtime.scopes["page:Home"].state["problem"],
                         "denied")

    def test_then_chain_and_toast_run_in_order(self):
        app = App('''page Home at "/":
  cart = []
  to add:
    cart add "x" then show toast "Added ✓"
  column:
    button "Add" on tap add
''')
        self.tap_button(app, "Add")
        self.assertEqual(app.runtime.scopes["page:Home"].state["cart"], ["x"])
        self.assertEqual(app.runtime.toasts, ["Added ✓"])

    def test_http_resource_caches_until_refresh(self):
        _Handler.requests = 0
        app = App(f'''page Home at "/":
  data from "{self.base}/data"
  to reload:
    refresh data
  column:
    when data:
      is ready value: text "{{value.name}}"
      is failed why: text why
    button "Reload" on tap reload
''')
        app.build(400, 600)
        self.assertIn("Ada", [n.text for n in app.scene.walk() if n.text])
        self.assertEqual(_Handler.requests, 1)
        key = next(k for k in app.runtime.resource_cache
                   if k.startswith("page:Home:data:"))
        cached = app.runtime.resource_cache[key]
        app.build(400, 600)                    # cache hit: same tuple, no GET
        self.assertEqual(_Handler.requests, 1)
        self.assertIs(app.runtime.resource_cache[key], cached)
        btn = [n for n in app.scene.walk() if n.kind == "button"][0]
        app.tap(btn.path)
        self.assertEqual(_Handler.requests, 2)
        self.assertEqual(app.runtime.resource_meta[key]["attempts"], 2)

    def test_resource_cache_keys_by_address(self):
        # Two params of the same page must not share one cached resource.
        app = App('''page RoomPage(room) at "/rooms/{room.id}":
  messages from "/rooms/{room.id}/messages"
  column:
    when messages:
      is ready value: text "count {value.n}"
''', providers={"/rooms/r1/messages": {"n": 1},
                   "/rooms/r2/messages": {"n": 2}})
        page = app.program.pages["RoomPage"]
        one = app.builder.build_page(page, {"room": {"id": "r1"}})
        two = app.builder.build_page(page, {"room": {"id": "r2"}})
        self.assertIn("count 1", [n.text for n in one.walk()])
        self.assertIn("count 2", [n.text for n in two.walk()])

    def test_error_box_retry_refreshes(self):
        app = App('''page Home at "/":
  data from "/api/data"
  column:
    when data:
      is ready value: text "ok {value.v}"
      is failed why: ErrorBox why retry refresh data
''', providers={"/api/data": {"_failed": "nope"}})
        app.build(400, 600)
        self.assertIn("⚠ nope", [n.text for n in app.scene.walk() if n.text])
        box = [n for n in app.scene.walk() if n.kind == "box"][0]
        app.providers["/api/data"] = {"v": 9}
        app.tap(box.path)
        app.build(400, 600)
        self.assertIn("ok 9", [n.text for n in app.scene.walk() if n.text])

    def test_error_box_retry_keeps_page_params(self):
        app = App('''page RoomPage(room) at "/rooms/{room.id}":
  messages from "/rooms/{room.id}/messages"
  column:
    when messages:
      is ready value: text "ok {value.n}"
      is failed why: ErrorBox why retry refresh messages
''', providers={"/rooms/r1/messages": {"_failed": "nope"}},
            page_params={"room": {"id": "r1"}})
        app.build(400, 600)
        box = [n for n in app.scene.walk() if n.kind == "box"][0]
        app.providers["/rooms/r1/messages"] = {"n": 3}
        app.tap(box.path)
        app.build(400, 600)
        self.assertIn("ok 3", [n.text for n in app.scene.walk() if n.text])
        self.assertTrue(any(k.endswith(":/rooms/r1/messages")
                            for k in app.runtime.resource_cache))

    def test_refresh_unknown_resource_is_plain(self):
        from plainlang.errors import PlainError
        app = App('''page Home at "/":
  to reload:
    refresh nope
  column:
    button "Reload" on tap reload
''')
        app.build(400, 600)
        with self.assertRaises(PlainError) as caught:
            app.tap([n for n in app.scene.walk() if n.kind == "button"][0].path)
        self.assertIn("no resource called `nope`", caught.exception.message)

    def test_http_error_becomes_failed(self):
        app = App(f'''page Home at "/":
  problem = nothing
  to load:
    result = fetch "{self.base}/missing"
    when result:
      is ok value: problem = "ok"
      is failed why: problem = why as sentence
  column:
    button "Load" on tap load
''')
        self.tap_button(app, "Load")
        self.assertEqual(app.runtime.scopes["page:Home"].state["problem"],
                         "server 404")


if __name__ == "__main__":
    unittest.main()
