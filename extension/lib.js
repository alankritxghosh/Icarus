// extension/lib.js
// Pure, DOM-free logic for the "explain a line on GitHub" content script --
// no chrome.* APIs, no fetch, no document access, so it's fully unit-testable
// offline (extension/lib.test.js, node --test, zero npm installs) and usable
// unchanged as a plain <script> in the extension (no bundler/build step).
//
// D0's live probe against the real GitHub blob view (see the plan doc,
// docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md, "D0 status")
// found: click+shift-click sets location.hash to "#L5" or "#L1-L4" -- GitHub's
// own line-link convention; drag-selection does NOT set the hash (so v1 only
// supports click+shift-click, matching real GitHub muscle memory); a PR-diff
// view's DOM is structurally different AND semantically ambiguous (old/new
// line numbers), explicitly out of scope for v1.

/**
 * Parse a GitHub blob-view URL hash into a 1-indexed, inclusive line range.
 * @param {string} hash - e.g. location.hash: "#L5", "#L1-L4", or "".
 * @returns {{start: number, end: number} | null} null when there's no valid
 *   selection (no hash, an unrelated hash, or -- defensively -- an inverted
 *   range GitHub's own UI never produces but a hand-crafted URL could).
 */
function parseLineHash(hash) {
  const m = /^#L(\d+)(?:-L(\d+))?$/.exec(hash || "");
  if (!m) return null;
  const start = parseInt(m[1], 10);
  const end = m[2] !== undefined ? parseInt(m[2], 10) : start;
  if (end < start) return null;
  return { start, end };
}

/**
 * Parse a GitHub blob-view pathname into its owner/repo/ref/path parts.
 * @param {string} pathname - e.g. location.pathname:
 *   "/simonw/llm/blob/94769b8.../llm/cli.py".
 * @returns {{owner: string, repo: string, ref: string, path: string} | null}
 *   null for any non-blob-view path (repo root, PR-diff view, etc.) --
 *   PR-diff view is explicitly out of scope for v1 (D0's finding: a
 *   structurally different, semantically ambiguous DOM).
 */
function parseBlobPath(pathname) {
  const m = /^\/([^/]+)\/([^/]+)\/blob\/([^/]+)\/(.+)$/.exec(pathname || "");
  if (!m) return null;
  return { owner: m[1], repo: m[2], ref: m[3], path: m[4] };
}

/**
 * Is the GitHub page's repo the one currently connected to Icarus? Case-
 * insensitive (GitHub repo names are). The extension only ever activates on
 * a connected repo -- it has an index there, so it has something to cite;
 * anywhere else it stays dormant rather than promising an answer it can't
 * ground (see the plan doc's "Scope guard").
 * @param {string} pageOwner
 * @param {string} pageRepo
 * @param {string | null | undefined} connectedRepo - "owner/repo" from /status,
 *   or falsy when nothing is connected.
 */
function isConnectedRepo(pageOwner, pageRepo, connectedRepo) {
  if (!connectedRepo) return false;
  return `${pageOwner}/${pageRepo}`.toLowerCase() === connectedRepo.toLowerCase();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseLineHash, parseBlobPath, isConnectedRepo };
}
