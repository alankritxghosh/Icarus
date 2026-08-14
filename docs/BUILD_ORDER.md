# Icarus — Build Order

We build one honest brick at a time, and we **never build the talker before the
brain it speaks for.** Each phase ends in a thing you can actually demo. Voice
comes last on purpose — it's the most fun and the most dangerous, because it
tempts the system to guess.

The rule for every phase: it inherits "can't bluff" from the phase below it.

---

## Phase 1 — The brain, in text (no voice, no app)

**Build:** a plain command-line / web tool where you type a question about **one**
GitHub repo and get a written answer **with citations**, or an honest "no one
wrote this down."

**Why first:** if this works, you have a brain. If it doesn't, voice and overlays
are just lipstick on a confused pig. This is the only phase that proves the
defensible core.

**Includes:** GitHub ingest for one repo → fingerprints in a vector store → the
honesty gate → the AI writer producing answer + citations.

**Done when:** on a small set of real questions against a real public repo, Icarus
answers documented "why" questions with correct citations, and returns "I don't
know" for questions whose answer was never written down — measured by the
evaluation harness, not by vibes. See [EVALUATION.md](EVALUATION.md).

## Phase 1B — The coding-agent face (read-only)

**Build:** expose the proven text brain through a thin, read-only MCP adapter so
Claude Code, Codex, Cursor, and compatible tools can retrieve the recorded why
before planning a meaningful change. The adapter adds no answering logic and
cannot edit code or switch repositories.

**Why here:** coding agents are another consumer of the text brain, not a new
brain and not an autonomous Icarus. Brick 0 showed that retrieved context can
materially change a coding plan; it also showed that an honest unknown must carry
the bounded related evidence retrieval considered without promoting that
evidence into an asserted reason.

**Done when:** an agent call returns a self-identifying repo/commit, cited
answer or honest unknown, and bounded retrieved evidence; repo mismatches fail
closed. Private-repository evidence is allowed under the explicit transferred
risk recorded in `decisions/2026-08-07-mcp-private-repository-access.md`.

**Authentication bridge complete:** without a development override, the MCP
installed Mac app exchanges its Keychain-held GitHub bearer for a ten-minute,
in-memory, read-only Icarus session. The MCP client never receives the GitHub
credential. The server binds the session to one identity and active repository,
rate-limits issuance, and permits only `/status`, `/ask`, `/explain`, and
`/context`.

**Distribution complete:** the app binary is the stdio MCP server, production
is explicitly constrained to one warm replica, the installer wires Claude Code,
and Settings provides an explicit install/repair action. No user needs this
repository's Python module or virtualenv path. Measure
time-to-first-context and whether context reduces plan changes or review
corrections; do not infer those outcomes from tool availability.

## Phase 2 — The face (Mac app + overlay)

**Build:** wrap Phase 1 in a macOS app with the translucent on-screen overlay
that shows the citations. Still typed input.

**Why now:** now it *looks* like the vision. This is mostly packaging — the brain
already exists as a service the app talks to.

**Done when:** an engineer can type a question in the app and see the answer with
the proof rendered in the overlay, talking to the private-cloud brain.

## Phase 3 — The voice

**Build:** the hotkey (push-to-talk), speech-to-text in, text-to-speech out. The
full hold Right Option → speak → hear loop with the overlay showing proof.

**Why now (and not sooner):** voice only gets to speak once the brain underneath
physically cannot lie. This is the deliberate crossing where speed becomes
load-bearing.

**Done when:** holding the hotkey, asking out loud, and hearing a correct, cited
answer feels immediate — within the latency budget in [METRICS.md](METRICS.md).

**Implementation status:** the push-to-talk, streaming speech recognition,
grounded answer, honest spoken unknown, and system TTS loop are shipped. The app
now measures the controllable release → transcript → answer → speech-start path,
keeps only 50 duration-only samples in memory, and shows the latest breakdown
plus session p50/p95.

**Next smallest brick:** run at least 20 real voice asks on a Mac for each
available recognition path (on-device and Apple cloud fallback), record the
release → speech-start p50/p95, and compare them with the 3s/8s starting budget
in [METRICS.md](METRICS.md). Phase 3 is implemented but not latency-accepted
until those observed results exist.

## Phase 4 — Sellable (multi-company + trust)

**Build:** the per-company private-cloud isolation, the written guarantees
(never-train, delete-after-request), authentication, and the compliance work
(SOC 2 / ISO 27001) that companies will demand before they hand over their source.

**Why last:** you earn the right to sell once the product is real. Trust controls
are the floor for a company to let its code leave the laptop.

**Done when:** a second company can be onboarded into its own isolated brain, and
the data-never-leaves-the-boundary promise is something we can demonstrate, not
just claim.

---

## Guardrails that hold across all phases

- **Prove the gap with an eval before changing the brain.** No capability is
  "done" because it looks done — it's done when the evaluation harness says so.
- **Cite-or-unknown never degrades**, on any tier, in any phase.
- **Don't widen scope mid-phase.** New data sources (Slack, Linear, Notion),
  structural code understanding, and broader team surfaces are *post-Phase-4* —
  listed in [VISION.md](VISION.md) §4, deliberately not now. The Phase 1B
  read-only coding-agent face is the explicit narrow exception.
- **Rent the commodities, build the moat** — see the table in
  [ARCHITECTURE.md](ARCHITECTURE.md).
