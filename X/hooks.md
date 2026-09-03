# Hooks — the library, and the mechanism under each

A hook's job is one thing: **make continuing cheaper than leaving.** Not to
trick. On a technical feed, the cheapest way to do that is to be visibly
expensive to fake.

`voice.md` covers the five devices this account already uses and why. This file
is the wider working library — patterns, the mechanism, and whether they are
usable here.

---

## The mechanisms (there are only about six)

| Mechanism | What it does to the reader | Cost if abused |
|---|---|---|
| **Information gap** | Opens a question they now want closed | Clickbait: gap opened, never closed |
| **Costly signal** | Proves work happened before any claim is evaluated | None — this is the account's core asset |
| **Belief violation** | "I thought X. X is false." Forces re-evaluation | Contrarianism with nothing behind it |
| **Stakes** | Something was at risk | Manufactured drama |
| **Scene** | Places the reader somewhere, not at a pitch | None |
| **Authority transfer** | Cites a source stronger than you | Fabricated citations — the one unrecoverable sin here |

Everything below is one of those six wearing clothes.

---

## Pattern library

### 1. The contrast pair — *belief violation*
> Code shows what exists. Not why it exists.
> A merged PR leaves a commit. A refused one leaves nothing.

Clause one is something the reader already believes. Clause two removes it.
**Generator:** take any finding in `content-pillars.md`, write the belief it
overturned as line one. Account's signature. Highest performer.

### 2. The bare number opener — *costly signal*
> 17,810 agent skills in one library.
> One repo showed 1,283 pull requests closed without merging.

`1,283` cannot be guessed. Rounding destroys the signal at zero benefit.

### 3. The scene opener — *scene*
> Watched a coding agent about to write a patch two people had already had rejected.

"I built X" requires the reader to already care about you. "Watched an agent
about to…" requires only that they care about agents. On a small account that
difference is the entire game.

### 4. The named self-limit — *costly signal, inverted*
> Icarus can prove a citation is real. It cannot prove it's true.

Publishing your own boundary is uncopyable by anyone who does not have one. In a
market where everything overclaims, this is positioning, not a caveat.

### 5. The wrong prediction — *belief violation, first-person*
> The registered prediction was wrong.

Requires having registered one. Almost nobody has. **Check against the
no-failure-disclosure rule each time:** a wrong prediction about *how agents
behave* is a finding; a wrong prediction about *our own effectiveness* is not.

### 6. The unit correction — *belief violation, quantitative*
> 1,283 closed pull requests. Filter out bots: 62.
> 41% of contributors could not merge anything.

Reader accepted a number, then watches it collapse. Teaches a reusable habit —
which is what converts the primary segment (`audience.md`).

### 7. The two-things-that-look-like-one — *information gap*
> Sounds like one guarantee. It's two.
> Refused and abandoned are not the same event.

A distinction the reader has been eliding. They cannot tell if they were making
the mistake without reading on.

### 8. The negative result — *belief violation + costly signal*
> Built it, measured it, it was anti-correlated with truth, deleted it.

Rare on X, near-impossible to fake, and the strongest currency with the
dev-tool-builder segment.

### 9. The flat close — *not an opener, a closer*
> Live today.

No lesson supplied, no explanation of why it matters. Trusting the reader to
draw the conclusion is what makes this read as an engineer's account.
**The most common fix in review is deleting the last sentence.**

---

## Anti-patterns (present in the record or in the drafted files)

| Anti-pattern | Example from the record | Why it fails |
|---|---|---|
| Aphorism with no number | "A maintainer decides in about five seconds" | Could have been written by someone who did nothing |
| Product first | "Icarus now supports X" | Ad. Move product to beat three |
| Institutional cadence | "It reads a repository's code and GitHub history, then returns cited context" | Accurate; sounds like a different person |
| Conclusion supplied | "…which shows why context matters" | Delete the clause |
| Ask with no reason to care | "Reply if you're interested" (13 views) | The ask was fine; it needed a reason first |
| Rounded quantity | "hundreds of PRs" | Use the count or cut the sentence |

---

## The three tests before a draft ships

1. **The anyone test.** Could someone who did not do the work have written this
   sentence? If yes, the specifics were stripped somewhere.
2. **The first-line test.** Read line one alone. Does it open a gap, or announce
   a topic? Announcing a topic is not a hook.
3. **The character count.** 280 hard. The composer strips line breaks on long
   pastes, and the line breaks *are* the voice. Count every time.
