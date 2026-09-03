# Reply targets — batch 2, found live 2026-08-22 ~06:10 IST

**Batch 1 status: all four sent, verbatim, unedited.** Account moved 69 → 73
posts and **13 → 14 followers**. One follow inside an hour of the first reply is
not a result yet, but it is the first movement on the metric E5 actually
measures.

**Recurring defect to fix at the keyboard, not in the draft:** reply #1 shipped
as one block with the line breaks stripped and a missing space at
`20%.Repository`. The composer eats hard line breaks on paste. Type the breaks
in manually after pasting, or the structure - which is the voice - is lost every
time.

Drafts below are ship-ready and written to be sent unchanged. **Every one has
been run through `lint.py`.** The first versions of 1 and 2 had no number in
them and were rewritten from the inventory, not rephrased. See `style-lock.md`.

---

## 1. @omarsar0 — elvis, DAIR.AI

**Link:** https://x.com/omarsar0/status/2091199978014458081
**Post:** 1h old · 40 likes · 3.2K views · very large AI-research audience · **best target in this batch**

Parent:
> A long post on a new paper: "A lot of the issues we see with AI agents today revolve around wrong assumptions the LLMs make. This leads to problems like hallucination, cost inefficiencies, unreliable tool calls... The problem is that context acquisition is treated as afterthought... Users tend to leave out constraints when prompting. So the agent needs to guess the default." (arXiv:2608.19202)

**Draft reply (249 chars):**

> Where the missing constraint lives is measurable.
>
> I ran 7 questions across 10 real repos. The citations that actually answered: 58 from commits, 17 from pull requests, 14 from issues.
>
> 2 from docs. 1 from code.

**Why:** He is describing guessing as a cost problem. You are adding the part the paper's framing misses: the guess is indistinguishable from the answer at the interface, so no downstream check catches it. That is your entity-presence finding stated as a general fact, not as our changelog.

---

## 2. @JaredKubin — Jared Kubin, LIQN.ai

**Link:** https://x.com/JaredKubin/status/2091142975610818621
**Post:** 4h old · 49 likes · 11K views · quote-posting Austen Allred · long, serious, technical

Parent:
> "if there is ANY daylight or open seam in your planning... SPEC workflow... verification... grading criteria... review... the frontier models will find it, fill 'something' in... and it will 100% of the time be wrong and subtle... but catastrophic down the pipeline."

**Draft reply (237 chars):**

> Watched this exact thing once across 4 tasks.
>
> The model invented a rule that did not exist, over-generalised from 2 real sources. Every citation resolved, so nothing downstream flagged it.
>
> The pieces were real. The assembly was invented.

**Why:** He has named the symptom precisely and stopped one step short of the mechanism. You have the mechanism, measured. Also the highest-reach post in this batch and he replies in his own threads.

---

## 3. @matthias_mrc — Matt

**Link:** https://x.com/matthias_mrc/status/2091163986322682215
**Post:** 3h old · 74 likes · **50 replies** · 3.4K views · the most conversational post here

Parent:
> "VIBE CODING MADE EVERYONE A BUILDER. It made nobody a marketer."

**Draft reply (219 chars):**

> Building has a compile step. It tells you when you're wrong, immediately.
>
> Marketing has no compile step. The signal is slow and mostly absent.
>
> Same person, same effort. One loop is measurable and the other isn't.

**Why:** You already hold this position - your own post 20h ago said marketing 'can seem stagnating' because your productivity in building is measurable. This is that thought, sharpened into a contrast, said to 3.4K people who are arguing about it right now. **No product angle. Don't add one.**

---

## 4. @xlr8harder

**Link:** https://x.com/xlr8harder/status/2091135883319689256
**Post:** 5h old · 42 likes · 829 views · a joke post, well-known account · OPTIONAL

Parent:
> "vibefish (v.), to deceive someone into believing you understand something by confidently repeating vocabulary you picked up from a vibe coding session but never actually understood. cf. catfish."

**Draft reply (109 chars):**

> The tell is fluency with no boundary. Someone who actually understood it can tell you where it stops working.

**Why:** Short, dry, matches the register of a joke post rather than answering it with a statistic. **Do not put a number in this one** - a measurement under a joke reads as missing the joke. Lowest reach here; send it only if you have a slot left.

---

## Four, not five, again

I looked at the vibe-coding trend (519 posts and climbing), the hallucination
searches, and the agent-memory feed. What is left over is crypto-shill accounts
using AI vocabulary, recycled Karpathy copy, and one-line posts with nothing to
add to. Four is what cleared the bar.

**The batch-1 targets are still live and none of them are stale enough to
ignore** - if @dillon_mulroy or @fmontes reply to you, answering them is worth
more than any new cold reply here. A conversation with one principal engineer
beats five more first replies.

## Log

`experiments.md` E1 - parent handle, reach at send, payload, time offset from
the parent post, and any follow. Batch 1 rows are in; add these when sent.
