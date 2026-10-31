"""`plain run` preview server (prototype of the live runtime + Looking
Glass). One App session, re-parsed per request with runtime + navigation
carried over (hot reload with state — Doc 03 §10). Taps are scene-path
links; inputs are HTML overlays in per-field forms, so everything works
with JS disabled — a 15-line progressive-enhancement script also syncs
typed values before button taps. Binds 0.0.0.0 for proxied previews.
State marked `keep …` persists to `.plain/<app>.json`.
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
main{display:flex;gap:16px;padding:0 16px 16px;align-items:flex-start;flex-wrap:wrap}
.stage{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,20,40,.12);
overflow:hidden;position:relative;flex:none}
.stage form{margin:0}
.stage input.plain-input{position:absolute;border:1px solid #D8D8E0;border-radius:10px;
padding:0 12px;font:16px system-ui;background:#fff;color:#16161A;box-sizing:border-box}
.stage input.plain-input:focus{outline:2px solid #5B5BD6;outline-offset:-1px}
.panel{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,20,40,.08);
padding:14px 16px;max-width:460px;min-width:300px;flex:1}
.panel h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#6E6E7A;margin:0 0 8px}
pre{margin:0;font-size:12.5px;line-height:1.55;overflow:auto;white-space:pre-wrap}
.err{background:#FDECEC;color:#7A1F1F;border-radius:10px;padding:12px 14px;
white-space:pre-wrap;font-size:14px;max-width:640px}
.sizebar{display:flex;gap:8px;align-items:center;padding:12px 16px;flex-wrap:wrap}
.sizebar a{background:#fff;border:1px solid #D8D8E0;color:#16161A;border-radius:999px;
padding:5px 12px;font-size:12.5px;text-decoration:none}
.sizebar a.on{background:#5B5BD6;color:#fff;border-color:#5B5BD6}
"""

# Progressive enhancement ONLY (preview chrome, not PL semantics): if the
# user typed but didn't press Enter, push field values before following a
# tap link, so "type → click Add" works like the real runtime would.
_SYNC_JS = """
<script>
document.addEventListener('click', function(ev){
  var a = ev.target.closest('a[href^="/tap/"]'); if(!a) return;
  var fields = document.querySelectorAll('input.plain-input'); if(!fields.length) return;
  ev.preventDefault();
  var body = new URLSearchParams();
  fields.forEach(function(f){ body.set('f_' + f.dataset.path, f.value); });
  fetch('/sync', {method:'POST', body: body})
    .then(function(){ location.href = a.href; })
    .catch(function(){ location.href = a.href; });
});
</script>"""

SIZES = {
    "desktop": (800, 600),
    "phone": (390, 700),
    "cheap-android": (360, 640),
    "small": (480, 360),
}


def _state_dump(app: App) -> str:
    dump = {p: dict(sc.state) for p, sc in app.runtime.scopes.items()}
    if app.runtime.shared:
        dump["shared"] = {k: ("(resource)" if isinstance(v, tuple) else v)
                          for k, v in app.runtime.shared.items()}
    try:
        return json.dumps(dump, indent=2, default=str)
    except TypeError:
        return str(dump)


def _input_overlays(app: App, size_key: str) -> str:
    out = []
    for n in app.scene.walk():
        if n.kind != "input" or not n.bind:
            continue
        typ = "password" if "secret" in n.flags else (
            "email" if n.props.get("kind") == "email" else "text")
        val = html.escape(n.text or "", quote=True)
        ph = html.escape(str(n.props.get("placeholder", "")), quote=True)
        out.append(
            f'<form method="get" action="/field/{html.escape(n.path)}">'
            f'<input type="hidden" name="size" value="{size_key}">'
            f'<input class="plain-input" type="{typ}" name="v" value="{val}" '
            f'placeholder="{ph}" data-path="{html.escape(n.path)}" autocomplete="off" '
            f'style="left:{n.x:.0f}px;top:{n.y:.0f}px;width:{n.w:.0f}px;height:{n.h:.0f}px">'
            f'</form>')
    return "".join(out)


def make_handler(app_path: Path, width: float, height: float):
    session: dict = {"app": None}

    def load(size_key: str):
        w, h = SIZES.get(size_key, (width, height))
        app = App.for_file(app_path, persist=True)
        old = session["app"]
        if old is not None and not app.errors:
            app.carry_from(old)
        session["app"] = app
        return app, w, h

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, size_key):
            self._send(302, "", extra={"Location": f"/?size={size_key}"})

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/sync":
                return self._send(404, "not found")
            length = int(self.headers.get("Content-Length", 0))
            form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            try:
                app, w, h = load("desktop")
                app.build(w, h)  # paths are size-stable for inputs
                for key, vals in form.items():
                    if key.startswith("f_"):
                        app.set_field(key[2:], vals[0], submit=False)
                self._send(204, "")
            except PlainError as e:
                self._send(400, e.render(), "text/plain")

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            size_key = (qs.get("size") or ["desktop"])[0]
            try:
                app, w, h = load(size_key)
            except PlainError as e:
                return self._error(e)
            except Exception as e:  # never white-screen the preview
                return self._error(PlainError(f"Prototype hiccup: {e}"))

            try:
                if parsed.path.startswith("/tap/"):
                    app.build(w, h)
                    app.tap(urllib.parse.unquote(parsed.path[len("/tap/"):]))
                    return self._redirect(size_key)
                if parsed.path.startswith("/field/"):
                    app.build(w, h)
                    app.set_field(urllib.parse.unquote(parsed.path[len("/field/"):]),
                                  (qs.get("v") or [""])[0], submit=True)
                    return self._redirect(size_key)
                if parsed.path == "/reset":
                    app.reset()
                    return self._redirect(size_key)
                if parsed.path == "/app.svg":
                    return self._send(200, app.svg(w, h, tap_prefix="/tap/"),
                                      "image/svg+xml")
            except PlainError as e:
                return self._error(e)

            try:
                svg = app.svg(w, h, tap_prefix="/tap/")
                overlays = _input_overlays(app, size_key)
                tree = a11y_mod.derive(app.scene)
                a11y_text = a11y_mod.render_text(tree) if tree else "(empty)"
                page_name = app.stack[-1][0] if app.stack else "?"
            except PlainError as e:
                return self._error(e)
            size_links = "".join(
                f'<a class="{"on" if k == size_key else ""}" href="/?size={k}">'
                f'{k} {int(v[0])}×{int(v[1])}</a>' for k, v in SIZES.items())
            needs = ", ".join(app.program.needs) or "nothing"
            body = f"""<!doctype html><meta charset=utf-8>
<title>PLAIN — {html.escape(app_path.name)}</title><style>{_PAGE_CSS}</style>
<header><b>PLAIN</b><span>plain run · {html.escape(app_path.name)} · page {html.escape(page_name)}</span>
<span>capabilities needed: {html.escape(needs)}</span>
<a href="/reset?size={size_key}">reset (clears kept state)</a>
<a href="/?size={size_key}">reload (state kept)</a></header>
<div class="sizebar"><span>Viewport:</span>{size_links}
<span style="font-size:12.5px;color:#6E6E7A">type + Enter to submit · edit the file, reload, state survives</span></div>
<main>
<div class="stage">{svg}{overlays}</div>
<div style="display:flex;flex-direction:column;gap:16px;flex:1;min-width:300px">
<div class="panel"><h2>Source — this file is the whole app</h2>
<pre>{html.escape(app.source)}</pre></div>
<div class="panel"><h2>Looking Glass · accessibility (derived, Doc 02 §1.4)</h2>
<pre>{html.escape(a11y_text)}</pre></div>
<div class="panel"><h2>Looking Glass · live state</h2>
<pre>{html.escape(_state_dump(app))}</pre></div>
</div></main>{_SYNC_JS}"""
            self._send(200, body)

        def _error(self, e: PlainError):
            body = f"""<!doctype html><meta charset=utf-8><title>PLAIN</title>
<style>{_PAGE_CSS}</style>
<header><b>PLAIN</b><span>{html.escape(app_path.name)}</span></header>
<main style="padding-top:16px"><div class="err">{html.escape(e.render())}</div></main>"""
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
