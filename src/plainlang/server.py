"""`plain run` preview server (prototype of the live runtime + Looking
Glass). Holds ONE App session; re-reads the .plain file on every request
while preserving runtime state (hot reload with state — Doc 03 §10 — falls
out of declared state for free, even in the prototype).

Taps are plain links (`/tap/<scene-path>`) so the preview works with JS
disabled and in proxied sandboxes. Binds 0.0.0.0 for live-preview hosts.
"""
from __future__ import annotations

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import a11y as a11y_mod
from .errors import PlainError
from .render import App

_PAGE_CSS = """
:root{color-scheme:light} body{margin:0;font-family:system-ui,-apple-system,
Segoe UI,sans-serif;background:#ECECF1;color:#16161A}
header{background:#16161A;color:#fff;padding:10px 16px;display:flex;gap:14px;
align-items:baseline;flex-wrap:wrap}
header b{font-size:18px;letter-spacing:.06em} header span{opacity:.75;font-size:13px}
header a{color:#BDBDF5;font-size:13px}
main{display:flex;gap:16px;padding:16px;align-items:flex-start;flex-wrap:wrap}
.stage{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,20,40,.12);
overflow:hidden}
.panel{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,20,40,.08);
padding:14px 16px;max-width:460px;min-width:300px;flex:1}
.panel h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#6E6E7A;margin:0 0 8px}
pre{margin:0;font-size:12.5px;line-height:1.55;overflow:auto;white-space:pre-wrap}
.err{background:#FDECEC;color:#7A1F1F;border-radius:10px;padding:12px 14px;
white-space:pre-wrap;font-size:14px;max-width:640px}
.sizebar{display:flex;gap:8px;align-items:center;padding:0 16px 12px;flex-wrap:wrap}
.sizebar a{background:#fff;border:1px solid #D8D8E0;color:#16161A;border-radius:999px;
padding:5px 12px;font-size:12.5px;text-decoration:none}
.sizebar a.on{background:#5B5BD6;color:#fff;border-color:#5B5BD6}
"""

SIZES = {
    "desktop": (800, 600),
    "phone": (390, 700),
    "cheap-android": (360, 640),
    "small": (480, 360),
}


def _state_dump(app: App) -> str:
    dump = {}
    for path, sc in app.runtime.scopes.items():
        dump[path] = {k: v for k, v in sc.state.items()}
    if app.runtime.shared:
        dump["shared"] = app.runtime.shared
    try:
        return json.dumps(dump, indent=2, default=str)
    except TypeError:
        return str(dump)


def make_handler(app_path: Path, width: float, height: float):
    session: dict = {"app": None, "mtime": None}

    def load(size_key: str):
        w, h = SIZES.get(size_key, (width, height))
        source = app_path.read_text(encoding="utf-8")
        old = session["app"]
        app = App(source, name=app_path.name)
        if old is not None and not app.errors:
            # hot reload WITH state: carry the runtime over the reload
            app.runtime = old.runtime
            app.runtime.program = app.program
            from .scene import SceneBuilder
            app.builder = SceneBuilder(app.program, app.runtime)
        session["app"] = app
        return app, w, h

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, code, body: str, ctype="text/html; charset=utf-8",
                  extra_headers=None):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            size_key = (qs.get("size") or ["desktop"])[0]
            try:
                app, w, h = load(size_key)
            except PlainError as e:
                return self._error(e, size_key)
            except Exception as e:  # never white-screen the preview
                return self._error(PlainError(f"Prototype hiccup: {e}"), size_key)

            if parsed.path.startswith("/tap/"):
                target = urllib.parse.unquote(parsed.path[len("/tap/"):])
                try:
                    app.build(w, h)
                    app.tap(target)
                except PlainError as e:
                    return self._error(e, size_key)
                return self._send(302, "", extra_headers={
                    "Location": f"/?size={size_key}"})
            if parsed.path == "/reset":
                session["app"] = None
                return self._send(302, "", extra_headers={
                    "Location": f"/?size={size_key}"})
            if parsed.path == "/app.svg":
                try:
                    return self._send(200, app.svg(w, h, tap_prefix="/tap/"),
                                      "image/svg+xml")
                except PlainError as e:
                    return self._error(e, size_key)
            try:
                svg = app.svg(w, h, tap_prefix=f"/tap/")
                # keep size choice through taps
                svg = svg.replace('href="/tap/', f'href="/tap/')
                tree = a11y_mod.derive(app.scene)
                a11y_text = a11y_mod.render_text(tree) if tree else "(empty)"
            except PlainError as e:
                return self._error(e, size_key)
            size_links = "".join(
                f'<a class="{"on" if k == size_key else ""}" '
                f'href="/?size={k}">{k} {int(v[0])}×{int(v[1])}</a>'
                for k, v in SIZES.items())
            body = f"""<!doctype html><meta charset=utf-8>
<title>PLAIN — {html.escape(app_path.name)}</title><style>{_PAGE_CSS}</style>
<header><b>PLAIN</b><span>plain run · {html.escape(app_path.name)} ·
Stage-1 reference prototype</span>
<a href="/reset?size={size_key}">reset state</a>
<a href="/?size={size_key}">reload (state kept!)</a></header>
<div class="sizebar"><span>Viewport:</span>{size_links}
<span style="font-size:12.5px;color:#6E6E7A">edit the .plain file and reload —
state survives (Doc 03 §10)</span></div>
<main>
<div class="stage">{svg}</div>
<div style="display:flex;flex-direction:column;gap:16px;flex:1;min-width:300px">
<div class="panel"><h2>Source — this file is the whole app</h2>
<pre>{html.escape(app.source)}</pre></div>
<div class="panel"><h2>Looking Glass · accessibility (derived, Doc 02 §1.4)</h2>
<pre>{html.escape(a11y_text)}</pre></div>
<div class="panel"><h2>Looking Glass · live state</h2>
<pre>{html.escape(_state_dump(app))}</pre></div>
</div></main>"""
            self._send(200, body)

        def _error(self, e: PlainError, size_key="desktop"):
            body = f"""<!doctype html><meta charset=utf-8><title>PLAIN</title>
<style>{_PAGE_CSS}</style>
<header><b>PLAIN</b><span>{html.escape(app_path.name)}</span></header>
<main><div class="err">{html.escape(e.render())}</div></main>"""
            self._send(200, body)

    return Handler


def serve(app_path: str, port: int = 8000, width: float = 800, height: float = 600):
    path = Path(app_path)
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(path, width, height))
    print(f"PLAIN running {path} at http://0.0.0.0:{port}  (Ctrl-C to stop)",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
