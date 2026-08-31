<!-- icarus-agent-mode-decision:v1 id=5e486a1d1c4ae61ed05be61ff36f5c292156289cbecfdf421c5c5e35af1133ef -->

# Keep the Chrome extension's content-script match narrow (https://github.com/*/*/blob/*) and ship a defensive try/catch on the Navigation API listener; do NOT broaden the match pattern. Defer the soft-navigation injection gap to a post-launch webNavigation+scripting fix.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Keep the Chrome extension's content-script match narrow (https://github.com/*/*/blob/*) and ship a defensive try/catch on the Navigation API listener; do NOT broaden the match pattern. Defer the soft-navigation injection gap to a post-launch webNavigation+scripting fix.

## Confirmed rationale

The narrow match is a deliberate, test-enforced privacy guarantee (extension/manifest.test.js pins the exact pattern; public site + store copy claim it acts only on file pages). Broadening it would inject the extension on every GitHub page and falsify that claim. The genuine gap — the content script not injecting when GitHub soft-navigates from a repo root into a /blob/ page — must be fixed the privacy-preserving way: webNavigation.onHistoryStateUpdated filtered to blob URLs + scripting.executeScript on demand, so the script still only runs on blob pages. That adds 2 permissions and re-triggers Web Store review, so it is not a day-before-launch change. The navigate-listener try/catch (applied, 55/55 tests green) is safe now.

## Alternatives considered

- Broaden matches to https://github.com/*
- Do the webNavigation+scripting injection fix now

## Affected paths

No affected paths were recorded.

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
