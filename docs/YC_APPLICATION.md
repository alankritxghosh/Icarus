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

**Who are your competitors, and what do you understand that they don't?**

Code-comprehension tools (Cursor, Greptile, Sourcegraph Cody, Unblocked) and
enterprise search (Glean). They are strong products, better resourced, and most
are aimed at *writing* code or *finding* code.

The understanding we're betting on: **for organizational memory, a confident
wrong answer is worse than no answer.** If a tool tells you why a timeout is 30
seconds and it's guessing, you've been handed a fact you will now repeat, and
you have no way to know. That makes "I don't know" a feature you must be able to
*trust*, which makes it an engineering problem — a deterministic gate, an eval
board, a published failure boundary — not a prompt. Tools optimized for
generation are structurally reluctant to build it, because the same machinery
that makes them feel magical is what makes them bluff.

**How will you make money?**

Per-developer subscription, the standard developer-tools shape. Rough starting
point $20–40/developer/month, with design partners discounted or free while they
prove the product. There is a real cost of goods — each question is a paid model
call — so pricing has a genuine floor. **[ALANKRIT]** — decide whether to state a
number or say "per-seat, priced above our per-query cost."

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
