# Web Staging Link (Typed) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let engineers try Icarus from a browser at `https://icarus-brain.onrender.com/` — sign in with GitHub, connect a public or private repo, and ask — with no `.dmg` download.

**Architecture:** The brain already serves a web UI (`demo/index.html`) and already has the GitHub OAuth endpoints (`/auth/github/begin`, `/auth/github/callback`, `/auth/github/redeem`), per-user isolation, private routing, and the paid writer — all deployed and auth-gated. The **only** missing piece is browser sign-in: today's OAuth callback redirects to the Mac app's `icarus://` custom scheme, which a browser can't follow, and the web page never authenticates (so its `/ask`/`/connect` calls hit the auth-required brain and get `401`). This plan adds a **web login mode**: `/auth/github/begin` is tagged `mode=web`, the callback redirects a web login back to the page (`/?session=…`) instead of `icarus://`, and the page redeems the session for the token, holds it in **sessionStorage** (decided: Option A — trusted-engineer staging), and sends it as `Authorization: Bearer` on every call. Private repos then work automatically because the server already routes an authed private connect to the paid writer. **The Mac-app flow stays byte-for-byte unchanged** (default `mode=app` → `icarus://`).

**Decisions (locked):** token in **sessionStorage** (not an HttpOnly cookie); **any GitHub account** may sign in (no allowlist); **typed only** (no voice/overlay — those are browser-impossible and/or break the on-device-audio promise). The deterministic honesty gate (`evals/gate.py`) and per-user isolation are **not touched**.

**Tech Stack:** Python stdlib `http.server` (`demo/server.py`, `demo/github_oauth.py`), vanilla-JS single-page `demo/index.html`, `unittest`. No new dependencies.

**Run all brain tests from the repo root** (the `-t .` is required for package imports):
`python3 -m unittest discover -t . -s demo` and `... -s evals`.

**Security notes to preserve while implementing:**
- The GitHub token **never** appears in a redirect URL — only the opaque, single-use `session` id does (existing guarantee in `demo/github_oauth.py`; keep it).
- sessionStorage holds the token in the tab only; clears on tab close. Accepted XSS trade-off for a trusted-engineer staging link.
- No brain change touches `evals/gate.py`, the trust interlock (`evals/trust.py`), or the isolation in `demo/registry.py`.

---

## Task 1: `OAuthFlow` remembers the login surface (app vs web)

Teach the OAuth orchestrator to tag each pending login with a `mode` and hand it back at completion, so the callback knows where to send the user.

**Files:**
- Modify: `demo/github_oauth.py` (`begin`, `complete`, `_sweep`, the `_pending` type)
- Test: `demo/test_github_oauth.py`

**Step 1: Write the failing tests**

Add to `demo/test_github_oauth.py` inside `class OAuthFlowTests`:

```python
    def test_begin_defaults_to_app_mode(self):
        flow = self._flow()
        state, _ = flow.begin()
        session, mode = flow.complete(state, "CODE_A")
        self.assertEqual(mode, "app")
        self.assertEqual(flow.redeem(session), "token-for-CODE_A")

    def test_begin_web_mode_flows_through_complete(self):
        flow = self._flow()
        state, _ = flow.begin("web")
        session, mode = flow.complete(state, "CODE_W")
        self.assertEqual(mode, "web")
        self.assertEqual(flow.redeem(session), "token-for-CODE_W")
```

Also update the three existing tests that call `complete` (its return type changes from `str` to `tuple[str, str]`):

- `test_begin_complete_redeem_happy_path`:
```python
        session, mode = flow.complete(state, "CODE1")
        self.assertEqual(mode, "app")
        self.assertEqual(flow.redeem(session), "token-for-CODE1")
```
- `test_redeem_is_single_use`: change `session = flow.complete(state, "CODE2")` to `session, _ = flow.complete(state, "CODE2")`.
- `test_state_is_single_use`: `flow.complete(state, "CODE3")` still returns a tuple; leave the call as-is (return value unused) — it still works.

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest demo.test_github_oauth -v`
Expected: FAIL — `test_begin_web_mode_flows_through_complete` errors because `begin()` takes no `mode`, and the mode-unpacking tests fail because `complete` returns a `str`.

**Step 3: Write the minimal implementation**

In `demo/github_oauth.py`:

Change the `_pending` annotation in `__init__`:
```python
        self._pending: dict[str, tuple[float, str]] = {}   # state -> (created_at, mode)
```

Replace `begin`:
```python
    def begin(self, mode: str = "app") -> tuple[str, str]:
        """Mint a CSRF state (tagged with the login surface) and return
        (state, authorize_url). `mode` is "app" (Mac app → icarus:// callback)
        or "web" (browser → same-origin page); the callback reads it back to
        decide where to send the user."""
        state = new_state()
        with self._lock:
            self._sweep()
            self._pending[state] = (time.time(), mode)
        return state, authorize_url(self._cid, self._redirect, state)
```

Replace `complete`:
```python
    def complete(self, state: str, code: str) -> tuple[str, str]:
        """Validate the state, exchange the code, store the token under a fresh
        session id, and return (session_id, mode). Raises ValueError on an
        unknown/expired state."""
        with self._lock:
            self._sweep()
            entry = self._pending.pop(state, None)
            if entry is None:
                raise ValueError("unknown or expired state")
        _created, mode = entry
        token = self._exchange(  # network happens outside the lock
            code, client_id=self._cid, client_secret=self._secret, redirect_uri=self._redirect)
        session_id = new_state()
        with self._lock:
            self._sessions[session_id] = (token, time.time())
        return session_id, mode
```

Replace the `_pending` line in `_sweep` (the tuple is now `(created_at, mode)`, so filter on `v[0]`):
```python
    def _sweep(self):
        now = time.time()
        self._pending = {s: v for s, v in self._pending.items() if now - v[0] < self._ttl}
        self._sessions = {s: v for s, v in self._sessions.items() if now - v[1] < self._ttl}
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m unittest demo.test_github_oauth -v`
Expected: PASS (all, including the two new mode tests).

**Step 5: Commit**

```bash
git add demo/github_oauth.py demo/test_github_oauth.py
git commit -m "feat(brain): OAuthFlow tags each login with an app/web mode"
```

---

## Task 2: `/auth/github/begin` accepts a mode; the callback redirects by mode

The web page must be able to ask for a web-mode login, and the callback must send a web login back to the page instead of `icarus://`.

**Files:**
- Modify: `demo/server.py` (the `/auth/github/begin` branch in `do_POST`; `_github_callback`)
- Test: `demo/test_server.py` (the `WebLogin…` fixture around line 439)

**Step 1: Write the failing tests**

In `demo/test_server.py`, in the web-login test class, add a mode-aware begin helper and two tests:

```python
    def _begin_mode(self, mode):
        req = urllib.request.Request(
            self.base + "/auth/github/begin",
            data=json.dumps({"mode": mode}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["authorize_url"]

    def test_web_mode_callback_redirects_to_page(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        state = parse_qs(urlparse(self._begin_mode("web")).query)["state"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODEW&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        self.assertEqual(r.status, 302)
        self.assertTrue(loc.startswith("/?session="),
                        f"web login must return to the page, got {loc!r}")

    def test_app_mode_callback_still_uses_custom_scheme(self):
        from urllib.parse import urlparse, parse_qs
        import http.client
        # Default begin (no mode / "{}") is the Mac app path — must stay icarus://
        state = parse_qs(urlparse(self._begin()).query)["state"][0]
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", f"/auth/github/callback?code=CODEA&state={state}")
        r = conn.getresponse()
        loc = r.getheader("Location")
        r.read(); conn.close()
        self.assertEqual(r.status, 302)
        self.assertTrue(loc.startswith("icarus://auth?session="),
                        f"app login must stay on the custom scheme, got {loc!r}")
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest demo.test_server -v -k WebLogin` (adjust `-k` to the actual class name shown by `grep -n "class .*Login" demo/test_server.py`).
Expected: FAIL — `test_web_mode_callback_redirects_to_page` gets an `icarus://…` Location (mode is ignored today).

**Step 3: Write the minimal implementation**

In `demo/server.py`, replace the `/auth/github/begin` branch in `do_POST`:
```python
            if self.path == "/auth/github/begin":
                if oauth is None or not oauth.configured:
                    self._send_json(503, {"error": "github login not configured"})
                    return
                try:
                    mode = (self._body() or {}).get("mode", "app")
                except (ValueError, AttributeError):
                    mode = "app"
                if mode not in ("app", "web"):
                    mode = "app"
                _, url = oauth.begin(mode)
                self._send_json(200, {"authorize_url": url})
                return
```

In `_github_callback`, change the completion + redirect. Replace:
```python
            try:
                session_id = oauth.complete(state, code)
            except Exception as e:
```
with:
```python
            try:
                session_id, mode = oauth.complete(state, code)
            except Exception as e:
```
and replace the redirect block:
```python
            self.send_response(302)
            self.send_header("Location", f"icarus://auth?session={session_id}")
            self.send_header("Content-Length", "0")
            self.end_headers()
```
with:
```python
            # Web logins return to the same-origin page; the Mac app keeps its
            # icarus:// custom scheme (which closes its auth sheet). The token is
            # NOT in the URL — only the single-use session id is.
            location = f"/?session={session_id}" if mode == "web" else f"icarus://auth?session={session_id}"
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m unittest demo.test_server -v`
Expected: PASS (both new tests; the existing app-mode `test_full_flow_begin_callback_redeem` still passes).

**Step 5: Commit**

```bash
git add demo/server.py demo/test_server.py
git commit -m "feat(brain): web-mode OAuth callback returns to the page, app stays icarus://"
```

---

## Task 3: The web page signs in, holds the token, and sends it

Wire sign-in into `demo/index.html`: a "Sign in with GitHub" control, session redemption on return, sessionStorage token, `Authorization: Bearer` on every call, a public/private badge, and sign-out.

**Files:**
- Modify: `demo/index.html` (sidebar markup + the `<script>` block)
- Test: `demo/test_server.py` (extend the index.html smoke assertion)

**Step 1: Write the failing test**

Find the existing index.html smoke test (`grep -n "index" demo/test_server.py` — the `GET /` test asserting the page serves). Add an assertion that the auth affordance is present. In that test body, after fetching the page text `html`:
```python
        self.assertIn("Sign in with GitHub", html)
        self.assertIn("/auth/github/begin", html)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest demo.test_server -v -k index` (adjust `-k` to the real test name).
Expected: FAIL — the current page has no sign-in markup.

**Step 3: Implement the sign-in UI + JS**

In `demo/index.html`, **replace the sidebar auth/trust area**. Replace this block:
```html
    <div class="trust"><span class="dot"></span> 0 trained on your code</div>
```
with:
```html
    <div id="auth-area">
      <div id="signed-out">
        <button id="signin-btn" class="ghost" style="width:100%">Sign in with GitHub</button>
        <div class="repo-status muted" style="margin-top:8px">Sign in to connect a repo — public, or your own private one.</div>
      </div>
      <div id="signed-in" style="display:none">
        <div class="navlabel">signed in</div>
        <div id="tier-badge" class="trust"><span class="dot"></span> 0 trained on your code</div>
        <button id="signout-btn" class="ghost" style="width:100%;margin-top:8px">Sign out</button>
      </div>
    </div>
```

Then in the `<script>`, **add token handling at the top** (right after the existing `const result=...` lines):
```javascript
const TOKEN_KEY="icarus.token";
function getToken(){return sessionStorage.getItem(TOKEN_KEY)||"";}
function setToken(t){t?sessionStorage.setItem(TOKEN_KEY,t):sessionStorage.removeItem(TOKEN_KEY);}
function authHeaders(extra){
  const h=Object.assign({},extra||{});
  const t=getToken();
  if(t)h["Authorization"]="Bearer "+t;
  return h;
}
```

**Replace the three `fetch` calls** so they carry the bearer:
- In the ask handler, replace the `fetch("/ask",…)` line:
```javascript
    const resp=await fetch("/ask",{method:"POST",headers:authHeaders({"Content-Type":"application/json"}),body:JSON.stringify({question})});
    if(resp.status===401){setToken("");renderAuthState();ask.disabled=false;return;}
```
- In `refreshStatus`, replace the fetch:
```javascript
    const s=await (await fetch("/status",{headers:authHeaders()})).json();
```
- In the connect handler, replace the `fetch("/connect",…)` line:
```javascript
    const r=await fetch("/connect",{method:"POST",headers:authHeaders({"Content-Type":"application/json"}),body:JSON.stringify({repo})});
    if(r.status===401){setStatus("sign in first","error");connectBtn.disabled=false;ask.disabled=false;return;}
```

**Add the auth flow + badge functions** (before the final `refreshStatus();` call):
```javascript
const signedOut=document.getElementById("signed-out");
const signedIn=document.getElementById("signed-in");
const tierBadge=document.getElementById("tier-badge");

function renderAuthState(){
  const on=!!getToken();
  signedOut.style.display=on?"none":"block";
  signedIn.style.display=on?"block":"none";
  if(!on){activeRepo.textContent="—";setStatus("");}
}

document.getElementById("signin-btn").addEventListener("click",async()=>{
  try{
    const r=await fetch("/auth/github/begin",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:"web"})});
    const {authorize_url}=await r.json();
    window.location.assign(authorize_url);
  }catch(e){setStatus("couldn't start sign-in","error");}
});

document.getElementById("signout-btn").addEventListener("click",()=>{
  setToken(""); renderAuthState(); window.location.assign("/");
});

// On return from GitHub the brain redirects to /?session=... — redeem it once,
// keep the token in sessionStorage, and scrub it from the visible URL.
async function redeemFromUrl(){
  const p=new URLSearchParams(window.location.search);
  const session=p.get("session");
  if(!session)return;
  try{
    const r=await fetch("/auth/github/redeem",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session})});
    if(r.ok){const {token}=await r.json();setToken(token);}
  }catch(e){/* fall through to signed-out */}
  history.replaceState({},document.title,"/");
}

// Reflect the writer tier honestly from /status (never inferred).
async function refreshBadge(){
  if(!getToken())return;
  try{
    const s=await (await fetch("/status",{headers:authHeaders()})).json();
    if(s&&s.state==="ready"&&s.repo){
      tierBadge.innerHTML='<span class="dot"></span> '+(s.private?"private · paid writer":"public · free writer")+" — 0 trained on your code";
    }
  }catch(e){}
}

(async()=>{ await redeemFromUrl(); renderAuthState(); await refreshStatus(); await refreshBadge(); })();
```

Finally, **remove the now-duplicated bare `refreshStatus();`** at the very end of the script (the IIFE above replaces it).

**Step 4: Run the test to verify it passes**

Run: `python3 -m unittest demo.test_server -v`
Expected: PASS (the index smoke now finds "Sign in with GitHub").

**Step 5: Commit**

```bash
git add demo/index.html demo/test_server.py
git commit -m "feat(web): browser GitHub sign-in on the demo page (sessionStorage bearer)"
```

---

## Task 4: Local end-to-end verification (auth mode)

Prove the whole browser flow against a local auth-required brain before deploying. This is a **manual** task (a real GitHub `code` can't be faked end-to-end); the unit tests above cover the redirect logic.

**Files:** none (verification only)

**Step 1: Start the brain in auth mode**
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"
ICARUS_REQUIRE_GITHUB_AUTH=1 python3 -m demo.server
```
Requires `.env` with `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` whose OAuth app has `http://127.0.0.1:8000/auth/github/callback` registered, plus `GEMINI_PAID_API_KEY` for private repos.

**Step 2: Confirm web-mode begin returns a GitHub URL**
```bash
curl -s -X POST http://127.0.0.1:8000/auth/github/begin \
  -H 'Content-Type: application/json' -d '{"mode":"web"}' | python3 -m json.tool
```
Expected: an `authorize_url` on `github.com` with `state=` and `scope=repo`.

**Step 3: Drive the browser flow**
Open `http://127.0.0.1:8000/`, click **Sign in with GitHub**, authorize; the browser returns to `/?session=…`, the page redeems it, the URL scrubs to `/`, and the sidebar shows **signed in**. Connect a repo (public like `simonw/llm`, or a private one you own), watch it index, ask a question, confirm a cited answer or an honest unknown, and that the badge reads **public · free writer** or **private · paid writer** correctly.

**Step 4: Run the full brain suites (nothing regressed)**
```bash
python3 -m unittest discover -t . -s demo
python3 -m unittest discover -t . -s evals
```
Expected: OK (skips allowed for the self-skipping live tests).

**Step 5: Commit** — nothing to commit (verification only). If you tweaked copy/markup while verifying, commit those under `demo/index.html`.

---

## Task 5: Docs + deploy

**Files:**
- Modify: `general_index.md` (the `demo/index.html` and `demo/github_oauth.py`/`demo/server.py` entries)
- Modify: `docs/HANDOFF.md` (note the web staging link exists)

**Step 1:** Update `general_index.md`:
- `demo/index.html` — note it now has **browser GitHub sign-in** (web-mode OAuth, sessionStorage bearer) so private repos work from the browser.
- `demo/github_oauth.py` — `begin(mode)`/`complete → (session_id, mode)` distinguishing app (`icarus://`) vs web (`/?session=`) logins.
- `demo/server.py` — `/auth/github/begin` reads `mode`; `_github_callback` redirects by mode.

**Step 2:** Add a short note to `docs/HANDOFF.md` (§3/§6): the hosted brain now doubles as a **typed web staging link** — engineers sign in with GitHub in the browser and connect their own repo; no DMG needed. Same infra/bill/no-training caveats as the DMG path (the link is easier to pass around — don't post it publicly).

**Step 3: Commit**
```bash
git add general_index.md docs/HANDOFF.md
git commit -m "docs: record the typed web staging link"
```

**Step 4: Deploy** — this is a **brain change**, so it needs a Render redeploy (the app-only fixes didn't):
```bash
git push origin main
```
Then trigger/confirm the Render deploy. After it's live, verify:
```bash
curl -s -X POST https://icarus-brain.onrender.com/auth/github/begin \
  -H 'Content-Type: application/json' -d '{"mode":"web"}' | python3 -m json.tool
```
Expected: a github.com authorize URL. Then open `https://icarus-brain.onrender.com/` in a browser and run the full sign-in → connect → ask flow. The GitHub OAuth app's callback URL is unchanged (`…onrender.com/auth/github/callback`), so **no GitHub settings change is needed**.

---

## Known gaps (accepted for a trusted-engineer staging link)
- **Sign-out is client-only.** The web "Sign out" clears the sessionStorage token
  and reloads; it does **not** `POST /disconnect`, so the caller's server-side
  library and any indexed private corpus persist under the storage root until LRU
  eviction. A reader might expect sign-out to also drop the server-side private
  corpus — wire sign-out to `/disconnect`, or leave as-is for staging (documented
  here so it isn't a surprise).
- **OAuth `state`/`session` are in-memory.** A Render restart or the free-tier
  idle sleep mid-sign-in invalidates all pending states/unredeemed sessions →
  the user sees "Sign-in failed or expired." Retry once the instance is warm.
- **sessionStorage XSS exposure.** Any script injected into the page can read the
  bearer. Accepted for a trusted staging link — which is exactly why the page must
  keep escaping any model/user content it renders (`esc()` is used in the render
  paths; never `innerHTML` un-escaped model output). The tier badge's `innerHTML`
  is a fixed literal ternary, not model data — keep it that way.

## Out of scope (do not build here)
- HttpOnly session cookies / CSRF tokens (Option B) — revisit when this goes past trusted-engineer staging.
- A GitHub-username allowlist — decided: any GitHub account.
- Voice in/out and the floating overlay — browser-impossible or breaks the on-device-audio promise; the native app owns these.
- Any change to `evals/gate.py`, `evals/trust.py`, or the per-user isolation in `demo/registry.py`.
- Persisting OAuth `state` across restarts — a free-tier Render sleep can still expire an in-flight sign-in ("try again"); accepted for staging.
