# YC Application — Icarus (draft)

**Status: DRAFT, 2026-07-22.** Everything factual here is verifiable against the
repo, the eval board, or the live deployment. Anything I could not verify is
marked **[ALANKRIT]** — those are yours to fill, and I have not guessed at them.

**The one rule for this document:** do not add a number, a user, or a claim that
isn't true. YC partners interview on the application. An inflated line becomes a
question you cannot answer in the room, and this is a company whose entire pitch
is that it doesn't bluff — getting caught embellishing the *application* would be
the most expensive irony available.

---

## Company

**Name:** Icarus

**What do you do? (50 characters max)**

> Answers why your codebase is the way it is.

*(48 chars. Alternatives: "The engineering brain that never bluffs" (39) ·
"Cited answers about why your code exists" (41).)*

**Company URL / demo:** **[ALANKRIT]** — no public URL yet. You have the live
brain and a DMG, not a landing page. Options: link a 90-second demo video
(recommended), or ship a one-page site. Do not link the raw Azure endpoint.

---

## What is your company going to make?

Icarus answers questions about a company's codebase — specifically the *why*,
not just the *what* — and shows the evidence for every answer.

An engineer holds a hotkey and asks "why do we retry three times here?" Icarus
searches the code, the pull requests, and the issue discussions, answers in a
sentence or two, and shows the exact lines it drew from. When the reason was
never written down, it says **"No one wrote this down"** instead of inventing a
plausible one.

The technical core is a deterministic honesty gate. The language model proposes
an answer; a separate, non-model piece of code verifies that every citation
resolves to evidence that was genuinely retrieved, with a valid line window, and
refuses the answer otherwise. Groundedness is enforced in code, not requested in
a prompt — so it cannot degrade with a model change, a prompt tweak, or a
jailbreak.

---

## Progress

**How far along are you?**

Working and deployed, no customers yet.

- **Shipped:** a macOS app (hotkey overlay + push-to-talk voice), a Chrome
  extension for GitHub, and a hosted brain running on Azure Container Apps.
- **Ingests** public and private GitHub repositories — 22 source-file types
  spanning ~17 languages (Python, JS/TS, Go, Rust, Java, Kotlin, Swift,
  Objective-C, C/C++, C#, Ruby, PHP, Scala, shell), plus pull requests, issues
  and their comment threads.
- **Test suite:** 457 brain tests, 199 server tests, 80 macOS tests, all green.
- **Eval board** (frozen labelled set, paid model): honesty gates 100% /100%,
  citation correctness 100%, answer correctness 100%.
- **Live pressure test across 10 large open-source repositories:** groundedness
  held on 30 of 31 questions, and 8 of 9 deliberately fabricated-premise
  questions were correctly refused.

**How long have you been working on this?** The repo's first commit is
**2026-06-27**, and it is literally titled *"Archive: JARVIS Engineering v0
(pre-Icarus reset)"* — so roughly four weeks on Icarus itself, on top of an
earlier version you reset from. **[ALANKRIT]** — decide how to frame the
pre-reset work. "I built a version, decided it could bluff, and threw it away"
is a genuinely strong answer if that is what happened; check that it is before
using it.

**Users / revenue:** None. A small number of engineers have tested builds and
sent feedback, which drove real fixes. No design partners signed, no revenue.
**Do not soften this.** "Built it, hardened it against ten real codebases, now
putting it in engineers' hands" is a credible stage; "early users" is not true.

---

## Idea

**Why did you pick this idea?** **[ALANKRIT]** — this must be your story, in your
words, and it is one of the most-read answers on the form. The honest raw
material is in the repo if you want it: you started from an assistant that could
answer questions about code, and the thing you refused to ship was one that
sounded confident when it didn't know. If there is a specific moment — a codebase
where the person who knew had left, an answer that was confidently wrong — lead
with that. A concrete moment beats a market thesis here.

**What's new about what you're making?**

Two things, and the second is the defensible one.

1. **It answers "why", not "what".** Code search and code-writing copilots
   operate on the code as it exists. The reasoning behind it lives in pull
   request discussions, issue threads and commit messages — and mostly in the
   heads of people who leave. Icarus indexes the argument, not just the artifact.

2. **It is provably unable to cite evidence it didn't retrieve.** Every
   competitor's honesty is a prompt and a hope. Ours is a deterministic gate with
   its own test suite, and we are precise about its limits: no fabricated
   citations, ever, provable in code; abstention-when-unrecorded is code-enforced
   for the clear cases and writer-reliant beyond them. We publish that boundary
   rather than claiming perfection.

**Who are your competitors? What do you understand that they don't?**
*(Final answer, 2026-07-22.)*

Competitors: code-comprehension and code-gen tools — Cursor, Greptile,
Sourcegraph Cody, Unblocked, GitHub Copilot — and enterprise search like Glean.
All better resourced than us, and most are genuinely good at what they're aimed
at, which is *writing* code or *finding* code. The real incumbent, though, is the
status quo: asking the one person who's been there five years, or `git blame`
and a guess.

What we understand that they don't:

1. **The reason isn't in the code, so indexing the code can't find it.**
   Competitors index the artifact. The *why* lives in the argument that produced
   it — pull request discussions, issue threads, commit messages — and then it
   walks out the door when the author leaves. That's a different corpus, and it
   changes what you retrieve and what counts as evidence.

2. **Abstention is the product, and it is commercially hard for them to ship.**
   Not technically hard — commercially. A coding assistant is judged on how often
   it produces something useful; every "I don't know" is a failed interaction by
   that metric, so the whole system is tuned toward always answering. We're
   judged on whether the answer can be trusted, which makes "no one wrote this
   down" a success. Same capability, opposite incentive. That gap is why we think
   this doesn't get closed by a competitor adding a feature.

3. **Honesty has to be enforced outside the model, and that means throwing away
   work.** Ours is deterministic code between the model and the user, and it
   regularly rejects answers the model was happy with. A real example from this
   week: the model produced a fluent answer *and labelled it valid*, but its own
   prose said "the evidence does not state a specific reason." Our gate caught the
   contradiction and converted it to a refusal. A team optimizing for engagement
   doesn't build the thing that deletes its own output.

Where they're ahead, and we know it: they have users, revenue, and distribution;
we have neither users nor revenue yet. They're far better at code generation — we
don't write code at all, deliberately. If a company only wants faster code, we're
the wrong product.

**How do or will you make money? How much could you make?**
*(Final answer, 2026-07-22.)*

Per-developer subscription, billed monthly or annually — the standard shape for
dev tools, and the one an engineering lead can approve without procurement.
Planned starting price **$30/developer/month**; design partners free or heavily
discounted while they prove it with us. Per-seat over per-query on purpose: if
asking costs money, people stop asking, and a tool nobody asks isn't
organizational memory.

The cost constraint, stated honestly: every question is a paid model call, so our
marginal cost isn't ~zero. The prompt is bounded in code (≤10 evidence chunks,
code capped at 10k chars each) — a worst-case question is ~25k input tokens on a
cheap model, typically far less. **We have not instrumented cost-per-question
yet** and would measure it before quoting a gross margin. Structural answer: price
the seat above realistic monthly usage, plus a fair-use ceiling.

How much: at $30/dev/mo = $360/dev/year.

| developers | ≈ companies (avg 30 devs) | ARR |
|---|---|---|
| 1,000 | ~33 | $360K |
| 10,000 | ~333 | $3.6M |
| 100,000 | ~3,300 | $36M |

A venture-scale outcome needs ~3,000 mid-sized engineering orgs — a small
fraction of companies with 10+ engineers, a legacy codebase, and turnover.
Expansion, both already in the architecture: an enterprise tier for
single-tenant / in-customer-cloud (security-conscious buyers pay a multiple),
and sources beyond GitHub (Slack, Linear, Notion), which raises per-seat value
because more of the "why" gets captured. The real bet, unproven: that teams pay
for *understanding* code, not only for writing it. The first thing we test with
design partners isn't answer quality — it's whether anyone opens it twice in a
week.

**What tech stack are you using? (incl. AI models and AI coding tools)**
*(Final answer, 2026-07-22 — verified against the repo, not memory.)*

Brain: Python 3.12, almost entirely standard library (BM25 retrieval, the honesty
gate, the eval harness, a stdlib `http.server` — no web framework). Three deps:
`fastembed` for local ONNX embeddings (`BAAI/bge-small-en-v1.5`, no PyTorch), and
`tree-sitter` + `tree-sitter-language-pack` for AST-aware code chunking.
Embeddings run locally, so customer code is never sent out to be indexed.
Retrieval is hybrid — BM25 fused with semantic, weighted from a measured sweep.

Models we rent: answer-writing is Google **Gemini 3.1 Flash Lite** on a
billing-enabled key — one model for every repo. Evaluation uses *different*
providers so the judge is never the writer (Groq / Llama 3.3 70B, and Gemini),
cross-provider. Speech in/out is Apple's on-device framework.

Deliberately NOT a model: the honesty gate — deterministic Python that verifies
every citation resolves to genuinely-retrieved evidence within a valid line
range, and refuses otherwise. No prompt talks it out of that; it doesn't change
when we swap models.

Clients: macOS app in Swift 6 (SwiftUI + AppKit, SwiftPM); Chrome extension in
vanilla JS (MV3, no build step). Infra: Docker on Azure Container Apps, Azure
Files for per-tenant isolated storage, GitHub OAuth, GitHub Actions CI. ~740
automated tests across brain, server, app.

AI coding tools: Claude Code writes most of the code, against a checked-in
engineering constitution (`AGENTS.md`) that requires a failing test before any
brain change. We also run adversarial review with a *different* model (GPT-5.6)
aimed at breaking the honesty gate — that's how we found the verdict-trust bug
above and fixed it deterministically.

**Other ideas you considered.** **[ALANKRIT — do not let anyone fill this for
you.]** YC sometimes funds the idea listed HERE, so a fabricated one is a real
liability: you could be interviewed on something you never thought about. Real
candidates surfaced from your own environment (confirm/correct/discard each,
2026-07-22): (1) a **personal AI memory system** — your `CLAUDE.md` walls off a
personal memory under `../brain/`; Icarus is that idea pointed at a company
instead of a person; (2) a **productized design-to-build pipeline** (brief →
style guide → Figma → WordPress) you already automated as a skill; (3)
**Pantheon**, a multi-agent critique/synthesis system wired as its own MCP.
Framing rules: 2–3 not 10; say why you didn't pick it (shows judgement); never
list one you'd resent building; prefer ideas you've already made something for.

---

## Founders

**[ALANKRIT — this whole section is yours.]** Do not let me write your
background. What the form wants: who you are, what you have built before, who
writes the code, and why you specifically will not quit. If you are a solo
founder, YC will ask about it directly — have a real answer about how you plan to
address it rather than deflecting.

---

## Legal / equity

**[ALANKRIT]** — incorporation status, ownership split, any prior fundraising.
Per the handoff, the entity conversation was identified as a decision and not yet
made. Answer truthfully; "not yet incorporated" is normal at application.

---

## Things they will probe — prepare these, don't put them in the form

Written down so the interview isn't the first time you meet them.

1. **"You have no users."** True. Best answer: the specific plan and its first
   name — a Morphic Labs engineer was already identified as the first target.
   Have a date.
2. **"What stops Cursor or GitHub from doing this in a weekend?"** The honest
   answer isn't "they can't" — it's that the gate, the eval board, and the
   published failure boundary are a *product posture*, not a feature, and it
   conflicts with an assistant optimized to always produce something.
3. **"Your OAuth scope asks for a user's entire private-repo account."** True
   today, and a security-minded partner may spot it. The fix is a GitHub App with
   per-repo read-only access; it is scoped and next. Say so plainly.
4. **"Isn't this just RAG?"** Retrieval is the commodity and we rent it. The
   product is what happens *after* retrieval: the refusal.
5. **"Show me it failing."** Have this ready as a demo beat, not a defence. Ask
   it something the repo never recorded and let it say "No one wrote this down."
   That moment is the pitch.

---

## Demo video — 90 seconds

Order matters; lead with the refusal, because it is the only thing on this list a
competitor's demo cannot show.

1. **0:00–0:15** — Hotkey, ask a real "why" about a well-known open-source repo.
   Cited answer appears with quoted proof on screen.
2. **0:15–0:35** — Click a receipt; it opens the exact lines on GitHub. Point out
   the answer could not have been emitted without that citation resolving.
3. **0:35–0:55** — Ask something the repo never wrote down. **"No one wrote this
   down."** Say the sentence out loud: most tools would have guessed here.
4. **0:55–1:15** — Ask about a symbol that does not exist in that codebase. It
   refuses instead of describing the nearest real thing. (This is a real bug we
   found in live testing and fixed with a deterministic guard — worth one line.)
5. **1:15–1:30** — One sentence on what this is for: the reason behind the code
   outlives the person who wrote it.

Record on a repo you do not maintain. Answering questions about someone else's
unfamiliar code is far more convincing than answering about your own.
