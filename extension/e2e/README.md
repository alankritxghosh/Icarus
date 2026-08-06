# Browser harness for the Icarus extension

`node --test extension/*.test.js` (41 tests, zero install) covers pure
functions: string parsing and HTML-string building. **Every bug this extension
has actually shipped lived outside them** and was found by loading it in a
browser:

- the stylesheet was injected lazily inside `showPanel`, so the first trigger a
  user ever saw was completely unstyled;
- an inline `style.position = "relative"` silently overrode the CSS class's
  `position: fixed`, putting the panel off-screen at `left:-24px`;
- a content script's own `fetch()` is bound by the GitHub page's CORS and
  Private Network Access rules, so every brain call failed with a bare
  "Failed to fetch" until they were relayed through the service worker.

This harness runs the **real unpacked extension** in real Chromium against real
github.com, with only the brain stubbed.

## Running it

```
cd extension/e2e
npm run setup     # once: npm install + playwright install chromium
npm test
```

The dependency is deliberately confined to this directory. `extension/` itself
stays installable by copying files, and the fast stdlib tests keep running with
no install at all.

## Why it needs a token and a stub

`content.js` returns immediately when `chrome.storage.local` has no token, and
only shows its trigger when `/status` reports a connected repo **matching the
page**. An unseeded run would therefore pass every test by doing nothing.
`fixtures.js` seeds a token through the service worker and stubs the brain, so
these tests never touch the live brain or a paid writer.

## These tests were verified by breaking the code

A harness nobody has seen fail is not evidence. Each test was checked against a
throwaway copy of the extension (`ICARUS_EXT_DIR=/path/to/copy`) with a bug
that really shipped reintroduced:

| reintroduced bug | test that caught it |
|---|---|
| `content.js` fetches the brain directly instead of via the service worker (the CORS bug) | cited answer |
| stylesheet injected lazily in `showPanel` only (the unstyled first trigger) | styled and on-screen |
| inline `position:relative` overriding the CSS class (the off-screen panel) | styled and on-screen |
| connected-repo gate removed | a repo that is not the connected one shows nothing |
| index citation rendered as a raw `index:overview` ref | cited answer |

One of these mutations exposed a mistake in the harness rather than the product:
an early attempt removed a style-injection call from inside `showTrigger`, the
test stayed green, and the reason was that injection happens once at module load
— which *is* the fix. The test only became meaningful once the mutation matched
the real bug.

An earlier assertion was also wrong rather than the code: it required a
background colour on `.icarus-trigger-bar`, which is a transparent flex
container by design. It now asserts on properties the stylesheet genuinely sets.

## `live.spec.js` — the real thing, on request

`npm test` never touches the network beyond loading github.com; the brain is
always stubbed. `npm run test:live` (or `ICARUS_LIVE=1 npx playwright test
live.spec.js`) runs the same extension against the **real** github.com and the
**real deployed Azure brain** — no stub, real writer call, real citations
checked to actually resolve on GitHub. It uses `gh auth token` for sign-in
(this machine's own identity; never written to disk or passed as a CLI arg) and
targets whichever repo that account currently has connected.

Skipped by default because it costs a real writer call and needs both `gh` auth
and a live deployment. First run of this file found a real bug in the harness,
not the product: it asserted the panel `toBeVisible`, which is true the instant
it renders its "thinking…" state, and read the text right then. Fixed to poll
until the panel actually resolves to evidence or an honest unknown.

## What is still not covered

- the GitHub OAuth flow (`chrome.identity.launchWebAuthFlow`) itself — needs a
  real consent screen, not just a token dropped into storage;
- the popup.
