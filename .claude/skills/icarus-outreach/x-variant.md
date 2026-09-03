# The X variant

Same method, different envelope. Read `SKILL.md` first — qualification, the
research pass and the output gate are unchanged. This file only covers what
differs when the message goes over X instead of email.

## When to use it

**X is the fallback channel, not the default.** Use it when:

- The maintainer is email-blocked (noreply commits, only a role inbox
  published) — the Cap case, and the reason this file exists.
- The maintainer publishes an X handle on their GitHub profile *and* email
  has already been tried and gone silent.

Do not use it because email feels slow. Measured on the 2026-08-08 board:
of 7 qualified prospects, only 4 publish an X handle, and the three with the
most recorded reasoning (ontime, rx-player, opentogethertube — 3,802 merged
PRs between them) publish none. Choosing X as the primary channel
systematically drops the best prospects.

## DM, not a public reply

Always the DM. The message says a reason for something in their code was
never written down. In a DM that is an observation; in a public reply it is a
critique of their team's documentation, posted where their users can read it.

The one exception is a maintainer whose bio explicitly invites public contact
and who has no DMs open. Then send it as a reply to a post of theirs about
that repo, and cut the unknown entirely — leave only the answer and the link.

## Your profile is the envelope

On email the from-address does the credibility work. On X the recipient opens
your profile before they read a word. A zero-post account with an empty bio
reads as a bot no matter how good the message is, and the DM lands in
Requests where it may never be seen at all.

Before the first send, the account needs a bio naming what Icarus is and a
link. This is a precondition, not a nicety. If the account is empty, fix that
first or use email.

## The message

**Four lines. 60–75 words. One message, never a follow-up before they reply.**

```
{Name}, {WHAT I DID} — one sentence, literal.

{THE ANSWER} — 1-2 lines, verbatim from Icarus, with its citation.

{LINK} — their page.

{CLOSE} — ask them to check your work.
```

No sign-off. Email closes with the bare first name; a DM does not, and adding
one reads as a pasted email.

### What changes from the email, and why

| Email beat | In the DM |
|---|---|
| Subject line | **Gone.** X has none, so line 1 does the subject's job — it must carry the specificity the subject carried. |
| WHAT I DID | Kept, compressed to one clause. |
| THE ANSWER | **Kept verbatim, with its citation.** This is the whole message. Never paraphrase it to save characters. |
| THE UNKNOWN | **Cut from the prose, carried by the page.** It is the differentiator, but it is the one beat the link can deliver in full. |
| STAGE + LINK | Link kept. "Built it on my own, you're one of the first" is cut — it reads as filler at DM length. |
| CLOSE | Kept, unchanged. It is the cheapest reply available and works identically here. |

Cutting the unknown from the prose is the real cost of this channel. The
email's strongest line is the refusal, and a DM cannot afford it. That is a
reason to prefer email when email is open, not a reason to pretend the DM is
equivalent.

## Voice

Identical to `SKILL.md` — no em dashes, inconsistently dropped apostrophes,
plain words, short lines, no hedges, never a fabricated typo. Two additions:

- **No sign-off**, per above.
- **Comma after the name, never a dash.** The email template opens `{Name} —`;
  that is the one place SKILL.md's own no-em-dash rule gets bent, and at DM
  length a leading dash is conspicuous. Use `Boris,`.
- **No link preview bait.** Do not write "link below" or "take a look" — X
  renders the card, the sentence is wasted.

## The gate is unchanged

**No specific, checkable, non-obvious answer about their code → no message.**
A shorter format is not a lower bar. If the answers came back doc-only, or
every one was an abstention, the prospect is dropped, not downgraded to a DM
because a DM is cheaper to write.

## Logging

Same `site/for/outreach_log.jsonl`, one row per send, plus:

```json
{"channel":"x","handle":"@whyboris","dm_open":true}
```

`dm_open` records whether their DMs accepted the message at all — a closed DM
is a delivery failure, the X equivalent of a bounce, and must not be filed as
silence. Three outcomes, three diagnoses: `blocked` (DMs closed),
`request_unread` (landed in Requests), `silence` (delivered, ignored).
