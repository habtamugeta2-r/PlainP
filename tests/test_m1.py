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
        if self.path == "/data":
            return self._json({"name": "Ada", "role": "engineer"})
        return self._json({"_error": "not found"}, 404)

    def do_POST(self):
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
