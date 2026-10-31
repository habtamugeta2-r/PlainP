"""`plain run` preview server (prototype of the live runtime + Looking
Glass).

Trust model (Doc 06 / HAB-69):
  * Local / sandboxed developer preview bound to `0.0.0.0` (compatible with
    localhost and proxied preview iframes such as `*.e2b.app`).
  * One isolated `App` + random CSRF token per `plainsid` session cookie,
    guarded by an `RLock` and bounded at 32 sessions.
  * Every state mutation (`/tap/*`, `/field/*`, `/reset`, `/sync`) requires
    `POST` with a body <= 64 KiB, same-origin `Origin` (when sent), and a
    matching per-session CSRF token. `GET` is strictly read-only.
  * `secret` inputs never appear in URLs, HTML `value` attributes, SVG
    text, or Looking Glass state dumps.
"""
from __future__ import annotations

import html
import json
import secrets
import threading
import urllib.parse
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import a11y as a11y_mod
from .checker import warnings_for
from .errors import PlainError, UnsupportedYet
from .render import App

MAX_POST_BYTES = 65_536  # 64 KiB cap on preview form submissions

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    # Allow proxied preview iframes (no frame-ancestors lock-out) while
    # blocking external script/object injection.
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; img-src 'self' data:; object-src 'none'"
    ),
}

_PAGE_CSS = """
:root{color-scheme:light} body{margin:0;font-family:system-ui,-apple-system,
Segoe UI,sans-serif;background:#ECECF1;color:#16161A}
header{background:#16161A;color:#fff;padding:10px 16px;display:flex;gap:14px;
align-items:baseline;flex-wrap:wrap}
header b{font-size:18px;letter-spacing:.06em} header span{opacity:.75;font-size:13px}
header a,header button.linkbtn{color:#BDBDF5;font-size:13px;background:none;border:0;
padding:0;font-family:inherit;text-decoration:underline;cursor:pointer}
main{display:flex;gap:16px;padding:0 16px 16px;align-items:flex-start;flex-wrap:wrap}
.stage{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,20,40,.12);
overflow:hidden;position:relative;flex:none}
.stage form{margin:0}
.stage button.plain-tap{position:absolute;z-index:1;background:transparent;border:0;
padding:0;margin:0;cursor:pointer;border-radius:10px}
.stage button.plain-tap:focus-visible{outline:2px solid #5B5BD6;outline-offset:1px}
.stage input.plain-input{position:absolute;z-index:2;border:1px solid #D8D8E0;
border-radius:10px;padding:0 12px;font:16px system-ui;background:#fff;color:#16161A;
box-sizing:border-box}
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
.toast{position:absolute;z-index:3;left:50%;bottom:18px;transform:translateX(-50%);
background:#16161A;color:#fff;border-radius:999px;padding:9px 16px;
font-size:13.5px;box-shadow:0 8px 24px rgba(20,20,40,.25);max-width:90%;
pointer-events:none}
"""

# Progressive enhancement ONLY (preview chrome, not PL semantics): if the
# user typed into an input without pressing Enter, sync dirty input values via
# POST /sync before submitting the POST /tap/* form. Untouched secret inputs
# are skipped so stored passwords are never overwritten with empty strings.
_SYNC_JS = """
<script>
document.addEventListener('input', function(ev){
  if(ev.target && ev.target.classList && ev.target.classList.contains('plain-input')){
    ev.target.dataset.dirty = '1';
  }
});
document.addEventListener('submit', function(ev){
  var form = ev.target;
  if(!form || !form.action || form.dataset.synced === '1') return;
  var path = new URL(form.action, location.href).pathname;
  if(path.indexOf('/tap/') !== 0) return;
  var fields = document.querySelectorAll('input.plain-input');
  if(!fields.length) return;
  ev.preventDefault();
  var meta = document.querySelector('meta[name="plain-csrf"]');
  var csrf = meta ? meta.getAttribute('content') : '';
  var body = new URLSearchParams();
  body.set('_csrf', csrf);
  fields.forEach(function(f){
    if(f.dataset.secret === '1' && f.dataset.filled === '1' && f.dataset.dirty !== '1'){
      return;
    }
    body.set('f_' + f.dataset.path, f.value);
  });
  var size = new URLSearchParams(location.search).get('size') || 'desktop';
  fetch('/sync?size=' + encodeURIComponent(size), {
    method: 'POST',
    headers: {'X-Plain-CSRF': csrf},
    body: body
  }).then(function(){
    form.dataset.synced = '1';
    HTMLFormElement.prototype.submit.call(form);
  }).catch(function(){
    form.dataset.synced = '1';
    HTMLFormElement.prototype.submit.call(form);
  });
});
</script>"""

SIZES = {
    "desktop": (800, 600),
    "phone": (390, 700),
    "cheap-android": (360, 640),
    "small": (480, 360),
}


def _secret_roots(app: App) -> set[str]:
    """State names bound to `input … secret` — never print their values."""
    roots: set[str] = set()
    if app.scene is None:
        return roots
    for n in app.scene.walk():
        if n.kind == "input" and "secret" in n.flags and n.bind:
            roots.add(n.bind[0].split(".")[0])
    return roots


def _state_dump(app: App) -> str:
    redact = _secret_roots(app)
    dump = {}
    for p, sc in app.runtime.scopes.items():
        dump[p] = {k: ("••••••" if k in redact else v)
                   for k, v in sc.state.items()}
    if app.runtime.shared:
        dump["shared"] = {k: ("(resource)" if isinstance(v, tuple)
                              else ("••••••" if k in redact else v))
                          for k, v in app.runtime.shared.items()}
    try:
        return json.dumps(dump, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        return str(dump)


def _tap_overlays(app: App, size_key: str, csrf: str) -> str:
    """POST form overlays for tappable controls — works with JS disabled."""
    out = []
    esc_size = html.escape(size_key, quote=True)
    esc_csrf = html.escape(csrf, quote=True)
    for n in app.scene.walk():
        if "disabled" in n.flags:
            continue
        tappable = "tap" in n.events or (n.kind == "toggle" and bool(n.bind))
        if not tappable:
            continue
        action_path = "/tap/" + urllib.parse.quote(n.path, safe="/:")
        label = html.escape(str(n.text or n.props.get("label") or n.kind),
                            quote=True)
        out.append(
            f'<form method="post" action="{html.escape(action_path, quote=True)}">'
            f'<input type="hidden" name="_csrf" value="{esc_csrf}">'
            f'<input type="hidden" name="size" value="{esc_size}">'
            f'<button class="plain-tap" type="submit" title="{label}" '
            f'aria-label="{label}" '
            f'style="left:{n.x:.0f}px;top:{n.y:.0f}px;width:{n.w:.0f}px;height:{n.h:.0f}px">'
            f'</button></form>'
        )
    return "".join(out)


def _input_overlays(app: App, size_key: str, csrf: str) -> str:
    """POST form overlays for bound inputs; never echoes `secret` values."""
    out = []
    esc_size = html.escape(size_key, quote=True)
    esc_csrf = html.escape(csrf, quote=True)
    for n in app.scene.walk():
        if n.kind != "input" or not n.bind:
            continue
        is_secret = "secret" in n.flags
        typ = "password" if is_secret else (
            "email" if n.props.get("kind") == "email" else "text")
        filled = "1" if (is_secret and bool(n.text)) else "0"
        val = "" if is_secret else html.escape(n.text or "", quote=True)
        raw_ph = ("••••••" if (is_secret and n.text)
                  else str(n.props.get("placeholder", "")))
        ph = html.escape(raw_ph, quote=True)
        action_path = "/field/" + urllib.parse.quote(n.path, safe="/:")
        out.append(
            f'<form method="post" action="{html.escape(action_path, quote=True)}">'
            f'<input type="hidden" name="_csrf" value="{esc_csrf}">'
            f'<input type="hidden" name="size" value="{esc_size}">'
            f'<input class="plain-input" type="{typ}" name="v" value="{val}" '
            f'placeholder="{ph}" data-path="{html.escape(n.path, quote=True)}" '
            f'data-secret="{"1" if is_secret else "0"}" data-filled="{filled}" '
            f'autocomplete="off" '
            f'style="left:{n.x:.0f}px;top:{n.y:.0f}px;width:{n.w:.0f}px;height:{n.h:.0f}px">'
            f'</form>')
    return "".join(out)


def _same_origin(headers) -> bool:
    """Reject foreign-origin POSTs while supporting localhost & proxy hosts."""
    fetch_site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if fetch_site == "cross-site":
        return False
    origin = headers.get("Origin")
    if origin is None:
        return True
    origin = origin.strip()
    if not origin or origin.lower() == "null":
        return False
    origin_host = (urllib.parse.urlsplit(origin).netloc or "").strip().lower()
    if not origin_host:
        return False
    allowed_hosts: set[str] = set()
    for hdr in ("Host", "X-Forwarded-Host"):
        raw = headers.get(hdr)
        if raw:
            for part in raw.split(","):
                part = part.strip().lower()
                if part:
                    allowed_hosts.add(part)
    return origin_host in allowed_hosts


def make_handler(app_path: Path, width: float, height: float):
    # One app/runtime + CSRF secret per browser session. All access is
    # serialized by `lock` so ThreadingHTTPServer never races on state.
    sessions: dict[str, dict] = {}
    lock = threading.RLock()
    max_sessions = 32

    def ensure_session(sid: str) -> dict:
        with lock:
            session = sessions.get(sid)
            if session is None:
                session = {"app": None, "csrf": secrets.token_hex(16)}
                sessions[sid] = session
                if len(sessions) > max_sessions:
                    oldest = next((k for k in sessions if k != sid), None)
                    if oldest is not None:
                        sessions.pop(oldest, None)
            return session

    def load(sid: str, size_key: str):
        w, h = SIZES.get(size_key, (width, height))
        with lock:
            session = ensure_session(sid)
            app = App.for_file(app_path, persist=True)
            old = session.get("app")
            if old is not None and not app.errors:
                app.carry_from(old)
            session["app"] = app
            return app, w, h, session["csrf"]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _sid(self) -> str:
            if getattr(self, "_sid_value", None):
                return self._sid_value
            sid = None
            raw = self.headers.get("Cookie")
            if raw:
                jar = SimpleCookie()
                try:
                    jar.load(raw)
                    if "plainsid" in jar:
                        cand = jar["plainsid"].value
                        if cand and len(cand) <= 128:
                            sid = cand
                except Exception:  # malformed cookie -> new session
                    sid = None
            if not sid:
                sid = uuid.uuid4().hex
                self._new_sid = True
            self._sid_value = sid
            return sid

        def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in _SECURITY_HEADERS.items():
                self.send_header(k, v)
            if getattr(self, "_new_sid", False):
                self.send_header(
                    "Set-Cookie",
                    f"plainsid={self._sid_value}; Path=/; HttpOnly; SameSite=Lax")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, size_key: str):
            safe_size = size_key if size_key in SIZES else "desktop"
            self._send(303, "", extra={"Location": f"/?size={safe_size}"})

        def _read_post_form(self) -> tuple[int | None, dict[str, list[str]] | str]:
            raw_len = self.headers.get("Content-Length")
            if raw_len is None:
                length = 0
            else:
                try:
                    length = int(raw_len)
                except ValueError:
                    self.close_connection = True
                    return 400, "Invalid Content-Length header."
            if length < 0:
                self.close_connection = True
                return 400, "Negative Content-Length header."
            if length > MAX_POST_BYTES:
                self.close_connection = True
                return 413, (f"Request body too large ({length} bytes; "
                             f"limit is {MAX_POST_BYTES} bytes).")
            raw = self.rfile.read(length) if length else b""
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                return 400, "Form body must be valid UTF-8."
            return None, urllib.parse.parse_qs(decoded, keep_blank_values=True)

        def _check_csrf(self, sid: str, form: dict[str, list[str]]) -> bool:
            if getattr(self, "_new_sid", False):
                return False
            with lock:
                session = sessions.get(sid)
                if session is None:
                    return False
                expected = session["csrf"]
            token = ((form.get("_csrf") or [""])[0]
                     or self.headers.get("X-Plain-CSRF")
                     or "")
            return bool(token) and secrets.compare_digest(token, expected)

        def do_POST(self):
            sid = self._sid()
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            known_post = (
                path == "/sync"
                or path == "/reset"
                or path.startswith("/tap/")
                or path.startswith("/field/")
            )
            if not known_post:
                return self._send(404, "not found", "text/plain; charset=utf-8")

            if not _same_origin(self.headers):
                return self._send(
                    403, "Forbidden: cross-origin state mutation blocked.",
                    "text/plain; charset=utf-8")

            err_code, payload = self._read_post_form()
            if err_code is not None:
                return self._send(err_code, str(payload),
                                  "text/plain; charset=utf-8")
            form = payload
            assert isinstance(form, dict)

            if not self._check_csrf(sid, form):
                return self._send(
                    403, "Forbidden: missing or invalid preview session token.",
                    "text/plain; charset=utf-8")

            qs = urllib.parse.parse_qs(parsed.query)
            size_key = (qs.get("size") or form.get("size") or ["desktop"])[0]
            if size_key not in SIZES:
                size_key = "desktop"

            if path == "/sync":
                try:
                    with lock:
                        app, w, h, _csrf = load(sid, size_key)
                        app.build(w, h)
                        for key, vals in form.items():
                            if key.startswith("f_"):
                                app.set_field(key[2:], vals[0], submit=False)
                    return self._send(204, "", "text/plain; charset=utf-8")
                except PlainError as e:
                    return self._send(
                        501 if isinstance(e, UnsupportedYet) else 400,
                        e.render(), "text/plain; charset=utf-8")
                except Exception as e:
                    return self._send(
                        500, f"Prototype hiccup: {e}",
                        "text/plain; charset=utf-8")

            try:
                with lock:
                    app, w, h, _csrf = load(sid, size_key)
                    if path.startswith("/tap/"):
                        app.build(w, h)
                        app.tap(urllib.parse.unquote(path[len("/tap/"):]))
                        return self._redirect(size_key)
                    if path.startswith("/field/"):
                        # Read `v` strictly from POST body so secrets never
                        # travel via query string.
                        val = (form.get("v") or [""])[0]
                        app.build(w, h)
                        app.set_field(
                            urllib.parse.unquote(path[len("/field/"):]),
                            val, submit=True)
                        return self._redirect(size_key)
                    if path == "/reset":
                        app.reset()
                        return self._redirect(size_key)
            except PlainError as e:
                return self._error(
                    e, code=501 if isinstance(e, UnsupportedYet) else 400)
            except Exception as e:
                return self._error(PlainError(f"Prototype hiccup: {e}"), code=500)

        def do_GET(self):
            sid = self._sid()
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            size_key = (qs.get("size") or ["desktop"])[0]
            if size_key not in SIZES:
                size_key = "desktop"

            # State-mutating endpoints never execute on GET (HAB-69).
            if (parsed.path == "/reset"
                    or parsed.path.startswith("/tap/")
                    or parsed.path.startswith("/field/")):
                return self._send(
                    405,
                    "State changes require POST (GET is read-only in PLAIN preview).",
                    "text/plain; charset=utf-8",
                    extra={"Allow": "POST"},
                )

            try:
                with lock:
                    app, w, h, csrf = load(sid, size_key)
                    if parsed.path == "/app.svg":
                        return self._send(200, app.svg(w, h), "image/svg+xml")
                    if parsed.path != "/":
                        return self._send(404, "not found",
                                          "text/plain; charset=utf-8")
                    svg = app.svg(w, h)
                    taps = _tap_overlays(app, size_key, csrf)
                    overlays = _input_overlays(app, size_key, csrf)
                    tree = a11y_mod.derive(app.scene)
                    a11y_text = a11y_mod.render_text(tree) if tree else "(empty)"
                    warns = warnings_for(app.program)
                    warn_text = "\n\n".join(w.render() for w in warns) or "(none)"
                    toast_text = app.runtime.toasts[-1] if app.runtime.toasts else ""
                    toast_html = (f'<div class="toast">{html.escape(toast_text)}</div>'
                                  if toast_text else "")
                    page_name = app.stack[-1][0] if app.stack else "?"
            except PlainError as e:
                return self._error(
                    e, code=501 if isinstance(e, UnsupportedYet) else 400)
            except Exception as e:
                return self._error(PlainError(f"Prototype hiccup: {e}"), code=500)

            size_links = "".join(
                f'<a class="{"on" if k == size_key else ""}" href="/?size={k}">'
                f'{k} {int(v[0])}×{int(v[1])}</a>' for k, v in SIZES.items())
            needs = ", ".join(app.program.needs) or "nothing"
            esc_csrf = html.escape(csrf, quote=True)
            esc_size = html.escape(size_key, quote=True)
            body = f"""<!doctype html><meta charset=utf-8>
<meta name="plain-csrf" content="{esc_csrf}">
<title>PLAIN — {html.escape(app_path.name)}</title><style>{_PAGE_CSS}</style>
<header><b>PLAIN</b><span>plain run · {html.escape(app_path.name)} · page {html.escape(page_name)}</span>
<span>capabilities needed: {html.escape(needs)}</span>
<span>{len(warns)} note{'s' if len(warns) != 1 else ''}</span>
<form method="post" action="/reset" style="display:inline;margin:0">
<input type="hidden" name="_csrf" value="{esc_csrf}">
<input type="hidden" name="size" value="{esc_size}">
<button type="submit" class="linkbtn">reset (clears kept state)</button></form>
<a href="/?size={esc_size}">reload (state kept)</a></header>
<div class="sizebar"><span>Viewport:</span>{size_links}
<span style="font-size:12.5px;color:#6E6E7A">type + Enter to submit · edit the file, reload, state survives</span></div>
<main>
<div class="stage">{svg}{taps}{overlays}{toast_html}</div>
<div style="display:flex;flex-direction:column;gap:16px;flex:1;min-width:300px">
<div class="panel"><h2>Source — this file is the whole app</h2>
<pre>{html.escape(app.source)}</pre></div>
<div class="panel"><h2>Looking Glass · accessibility (derived, Doc 02 §1.4)</h2>
<pre>{html.escape(a11y_text)}</pre></div>
<div class="panel"><h2>Looking Glass · live state</h2>
<pre>{html.escape(_state_dump(app))}</pre></div>
<div class="panel"><h2>Valid PL this prototype does not do yet</h2>
<pre>{html.escape(warn_text)}</pre></div>
</div></main>{_SYNC_JS}"""
            self._send(200, body)

        def _error(self, e: PlainError, code: int = 400):
            body = f"""<!doctype html><meta charset=utf-8><title>PLAIN</title>
<style>{_PAGE_CSS}</style>
<header><b>PLAIN</b><span>{html.escape(app_path.name)}</span></header>
<main style="padding-top:16px"><div class="err">{html.escape(e.render())}</div></main>"""
            self._send(code, body)

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
