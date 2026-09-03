---
name: icarus-outreach
description: Write cold emails for Icarus design-partner outreach, built on a real answer Icarus gave about the prospect's own codebase. Use when Alankrit asks to write a cold email, qualify a prospect, build a prospect page, or run an outreach batch for Icarus. Not for agency or client work — that is what cold-outreach-engine is for.
---

# Icarus outreach

Write one cold email at a time, each built on a fact about the recipient's own
code that did not exist until we generated it.

**Do not use `cold-outreach-engine` for Icarus.** Its second beat is "reference
a pain point they *likely* have," and speculation is the defect this skill
exists to remove. See *Why this replaced the generic skill* at the bottom.

## The one rule

**No specific, checkable, non-obvious answer about their code → no email.**

Everything below serves that. A prospect who fails qualification is skipped,
not written to. A weak set of answers means the company is dropped, not
dressed up. Roughly one in three prospects will die at one of these gates;
that is the skill working, not failing.

---

## 1. Qualify — before writing a word

Disqualify on **any** of these:

| Check | Threshold | Why |
|---|---|---|
| Public repo **is the product** | ≥ ~5MB of code | An SDK/client repo means "I read your codebase" = their 300KB wrapper. Kills fal, ElevenLabs, Rive, Cartesia. |
| TypeScript-dominant | TS+JS ≥ ~50% of bytes, or a large TS frontend | Measured strength: `ts_chunk` took tsx recall 66.7% → 100%. |
| Actively developed | pushed within ~60 days | Theatre.js last shipped 2024-08. |
| Not too famous | ≲ 50k stars | Excalidraw (129k), ComfyUI (124k) — the email drowns in inbound. |
| **A named human** | a real person, real address | Non-negotiable. See below. |

### The address rule

**Never a role inbox.** No `founders@`, `info@`, `hello@`, `hi@`, `support@`,
`sales@`, `hiring@`. If the person cannot be found, **skip the company**.

Batch 1 sent 20 of 23 to role inboxes while opening "Hey {FirstName}". A
first name arriving at `support@` does not read as personal, it reads as
proof you could not find them. One address was guessed and hard-bounced.

Find the human on GitHub — many publish an address on their own profile:

```bash
gh api "repos/OWNER/REPO/contributors?per_page=4" --jq '.[].login'
gh api "users/LOGIN" --jq '{name, company, blog, email}'
```

A profile-published address is fair use. Do not mine commit history in bulk
to assemble addresses.

### When they have deliberately hidden it

Many maintainers enable GitHub's private-email setting, so every commit reads
`NNNN+user@users.noreply.github.com`. That address **does not receive mail**,
and it is an explicit opt-out. Respect it:

- **Do not** dig through pre-privacy commits looking for the address that
  leaked before they turned the setting on.
- **Do not** fall back to the company's `hello@`/`info@` inbox. A role inbox
  is banned no matter how the search went — that is batch 1's exact failure.
- **Do** switch channel. If they are publicly reachable elsewhere (X bio
  inviting contact, a personal site), send the same content there, cut to
  three or four lines. For X specifically, follow `x-variant.md` — it is the
  fallback channel, not a replacement for email. A DM that lands beats an email that goes to support
  triage.

Measured: Richie McIlroy (Cap) uses the noreply address on every commit, and
cap.so publishes only `hello@cap.so`. Cap is unreachable **by email** and
reachable by X — even though it is otherwise the best-qualified prospect.
Prospects whose maintainers publish a real address (Steve Sewell
`steve@builder.io`, Steve Ruiz `steve@tldraw.com`) should go first, because
nothing about them is blocked.

### Verify, never assume

```bash
gh api repos/OWNER/REPO --jq '[.language,(.stargazers_count|tostring),.pushed_at]|@tsv'
gh api repos/OWNER/REPO/languages
```

---

## 2. Research — index their repo and ask real questions

Index the whole repo into a scratch dir. **Never** point `evals.ingest`'s CLI
at a prospect — it overwrites the committed `simonw/llm` eval board.

```bash
ICARUS_AST_CHUNKING=1 python3 -c "
from evals.ingest import ingest_repo
print(ingest_repo('OWNER/REPO', '<scratch>/NAME_corpus', code_dir='.'))"
```

Then **derive the questions from their own history** — never invent them.
Search the corpus for PRs that actually record a reason:

```bash
python3 -c "
import json,re
for l in open('<scratch>/NAME_corpus/chunks.jsonl'):
    d=json.loads(l or '{}')
    if d.get('source')!='pr' or len(d['text'])<400: continue
    if re.search(r'\b(because|instead of|root cause|turned out|regression)\b',d['text'],re.I):
        print(d['text'].split(chr(10))[0][:90])"
```

Write 8–9 questions from those PRs, plus 1–2 deliberate long shots
(architecture choice, the project's name) to exercise the abstention path.
Ask them:

```bash
.venv/bin/python <scratch>/ask_repo.py <scratch>/NAME_corpus \
    <scratch>/NAME_q.json <scratch>/NAME_answers.json
```

**Use `.venv/bin/python`.** System Python has no `fastembed`, and the pipeline
degrades silently to lexical-only — the log line is `local embedder
unavailable`. Measured cost on Cap: "PostHog was causing the editor to hang"
(lexical) versus "first-party proxying, ad-blocker resistant, server-side
delivery moved off the response path" (hybrid).

Embedding is the slow step, roughly 25 min per 14k chunks on CPU, cached to
disk afterwards. Index the batch before you need it.

### What to expect

**"Why does this behave this way" almost always answers. "Why did we choose
this architecture" usually does not.** Across Cap, Builder.io and tldraw,
every unknown was an architectural choice — why Rust, why Mitosis, why one
monorepo, why Zero, why HTML elements instead of a canvas.

It is a tendency, not a law: tldraw *had* written down why its editor uses a
reactive signals store, and Icarus answered it. So ask the architecture
questions — some teams document them, and an answered one is the strongest
line you can put in an email.

This shapes the promise. Icarus explains **why their code behaves as it does**,
and admits when a reason was never recorded. It does not recover unwritten
architectural intent. Never imply it does.

---

## 3. The output gate

Before writing, read the answers and kill the email if:

- No answer names a concrete symbol, file or mechanism
- The best answer only restates the PR title
- Everything came back unknown (a page of nine abstentions sells nothing)

**Grade every answer by what it cites.** An answer citing `pr:`, `commit:` or
`issue:` was reconstructed from history — that is the product working. An
answer citing only `doc:` was read out of a file the recipient probably wrote,
which is the batch-1 failure in a new costume: telling them what they already
published.

Never lead an email with a doc-only answer. tldraw's "why a signals store"
came back cited to `doc:packages/state/README.md` — a correct answer, useless
as proof, because Steve Ruiz wrote that README. The email led with the
reactions-query answer instead (`pr:9840` + a commit), which no document
states.

```bash
python3 -c "
import json,sys
for r in json.load(open(sys.argv[1])):
    if r['verdict']!='answer' or not r['citations']: continue
    s={c.split(':')[0] for c in r['citations']}
    print('HISTORY' if s&{'pr','commit','issue'} else 'doc-only', r['question'][:64])" ANSWERS.json
```

**One retrieval configuration only.** Never re-run with different settings and
keep whichever flatters the page. If a question flips from answered to unknown
under the shipping config, it is unknown. Cap went 7/9 → 6/9 that way and the
6/9 is the honest number.

Build the page:

```bash
python3 site/for/build_page.py <scratch>/NAME_answers.json \
    <scratch>/NAME_corpus/meta.json site/for/NAME.html
```

---

## 4. The email

Four beats. **Under 120 words.** Plain text.

```
Subject: {lowercase, describes the artifact, no tease}

{Name} —

{WHAT I DID} — one sentence, literal. No compliment about their product.

{THE ANSWER} — 2-3 lines, verbatim from Icarus, with its citation.

{THE UNKNOWN} — what it refused to answer. This is the differentiator.

{STAGE + LINK} — built it on my own, you're one of the first seeing it.
                 Their page.

{CLOSE} — ask them to check your work.
```

### Subject lines

Lowercase, specific, no sales register. Lead with a failure or a question,
never a benefit. Working examples: `asked your repo why the recorder is Rust —
it said no one wrote that down`, `why did we make this RTL decision?`,
`10m students and a small engineering team`.

Avoid abstract-noun subjects — `context across SIS, LMS and CRM data` promises
nothing. Eleven of batch 1's 23 were that shape.

### The close

Ask them to **check your work**, not to take a meeting:

> If any of it is wrong, I'd genuinely like to know — you're one of about
> three people who can tell me.

An engineer will reply to correct you. That is the cheapest reply available,
and starting a conversation is the whole job of email #1.

### Voice — Alankrit's own, extracted from his real sends

**Never invent typos.** The email's whole claim is that everything in it is
true and checkable; manufacturing errors to simulate authenticity is the one
dishonest thing in it, and a misspelled `SCShareableContent` makes a correct
answer look wrong. There is no need to fake it — his real typing already
reads as human. Copy *that* instead:

| Habit | Evidence from batch 1 |
|---|---|
| **No em dashes. Ever.** Commas and full stops instead. | Not one em dash in 23 emails. An em dash is the single loudest AI tell. |
| Drops apostrophes in contractions, **inconsistently** | `isnt`, `youre`, `shouldnt`, `Its`, `Thats` — but `I'm` keeps its apostrophe. Mixed, never systematic. |
| Lowercase sentence starts, usually the last line | "happy to send it over if youre curious." |
| Plain words | `kinda`, `a lot of`, `pretty strange` |
| Short paragraphs, one idea, blank line between | Every one of the 23. |
| Sign-off is the bare first name | `Alankrit`. No "Best", no "Cheers", no title. |

Applying these is not sloppiness, it is his actual register. Do not make it
uniform — real typing is uneven, so leave some contractions correct and some
not. If a sentence reads like it was proofread by a machine, loosen it.

Drop: every hedge. Batch 1 ran on `feels like`, `probably`, `I imagine`,
`I'm guessing`, `sounds like`, `must`.

**Never soften a technical term to sound casual.** Symbol names, PR numbers
and the answer text stay exactly as Icarus produced them.

---

## 5. Banned — every item traceable to batch 1

- **Speculation verbs**: `feels like`, `probably`, `I imagine`, `I'm guessing`,
  `sounds like`, `must be`, `likely`. If a sentence guesses at their pain,
  delete it. The answer replaces it.
- **Restating their marketing page.** Paraphrasing their About page back at
  them is the texture of AI personalization. Nothing in the email should be
  something they published about themselves.
- **Permission asks**: `happy to send it over if you're curious`,
  `let me know if you'd like`. Never ask permission to send proof that costs
  nothing to include.
- **Implied traction.** No "teams are using", no "we". You built it alone;
  say so. It is checkable and better.
- **Openers**: `hope this finds you well`, `quick question`, `just reaching
  out`, `I came across your profile`.
- **A first name to a role inbox.**
- **Tracking pixels.** Placement risk outweighs an open rate you can't act on.

---

## 6. Sending

- **≤ 8/day**, spread out. Batch 1 sent 16 in one afternoon at 6–8 minute
  intervals — a sequencer's signature from a personal Gmail.
- **≤ 1 link** (their page). Zero others.
- **Placement test before every batch**: send one to accounts on Gmail,
  Outlook and Fastmail and confirm the inbox. Batch 1 cannot distinguish
  "ignored" from "never delivered", which makes every copy change unfalsifiable.
- Plain text. No HTML signature, no images.

### The follow-up rule — exactly one

One follow-up, **5–7 days** after, **three lines maximum**, on the same thread.

It must **add new information** — another answer Icarus gave about their repo,
or something that changed since. If there is nothing new to say, send nothing.

Never: "just bumping this", "did you see my last email", "following up".
A second email that only repeats the first tells them the first was not worth
answering.

After the follow-up, stop. No third touch.

---

## 7. Log every send

Append one row per send to `site/for/outreach_log.jsonl`:

```json
{"date":"2026-08-05","company":"CapSoftware/Cap","person":"Richie McIlroy",
 "email":"...","repo":"CapSoftware/Cap","chunks":13819,"answered":6,"unknown":3,
 "subject":"...","lead_answer":"pr:2064","variable":"repo-proof opener",
 "sent_at":"09:12","followed_up":null,"outcome":null}
```

Fill `outcome` later: `reply` / `bounce` / `silence` / `unsubscribe`, plus the
reply text if any. **A bounce, a "no thanks" and silence are three different
diagnoses** — a bounce is a list problem, a "what is this?" is a clarity
problem, silence is relevance or placement.

Hold everything constant except one `variable` per batch.

### Reading the results honestly

At ~20 per batch you are looking for a **qualitative jump (0 → 3)**, not
significance. At a 5% reply rate, 20 sends returns an expected 1 reply, and
**P(zero replies) ≈ 0.36** — so zero does not prove the email is bad, and one
does not prove it is good. Batch 1's 0/23 was diagnosed by *reading the copy*,
not by the zero.

---

## Why this replaced the generic skill

Batch 1: **23 emails, 2026-08-03/04, 0 replies, 1 hard bounce.**

`cold-outreach-engine`'s structure is Hook → "a pain point they likely have"
→ Value prop → Low-friction CTA. Every one of the 23 executes it faithfully:
paraphrase their product, speculate about their pain, one line on Icarus,
"happy to send it over if youre curious."

The emails were not written badly. They were written to a framework whose
second step is a guess. This skill's second step is a fact instead.

**Prospect list and per-company research live in the conversation that built
them, not here.** This file is the method.
