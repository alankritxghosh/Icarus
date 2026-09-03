---
status: DRAFT — not published
genre: A1 (working with an AI colleague you cannot trust)
sources: docs/experiments/2026-08-10-agent-mode-exp-d-efficiency.md:66,99
         scripts/agent_call_audit.py:6
         evals/test_writer_uses_evidence.py
         docs/experiments/2026-08-10-agent-mode-exp-d-directed.md:74-82
checked: every number read out of its source file, 2026-08-23
target: ~1,050 words
---

# Why you spend your day checking instead of building

An agent told me a bug was already fixed. It was right about the cause, right
about the commit, and wrong about the bug.

Here is what had happened. The agent read the code, found the function
responsible, found the commit that had repaired it, and closed the question. All
three steps were correct. The fix it found was real and it had landed. What it
could not see was that a second cause was still open, being argued about, not
yet merged, and living entirely in a discussion thread rather than in any line
of code.

So it produced a confident, correct-looking, completely wrong conclusion. And
the reason it was wrong is not that it reasoned badly. It reasoned well over
what it could see.

---

Everyone talks about this shift in terms of speed. You will write code faster.
You will ship faster. The demos are all about the gap between typing a sentence
and watching a feature appear.

That is not what happened to my week.

The work did not get faster so much as it moved. Writing the thing stopped being
the expensive part. Establishing whether the thing was true became the expensive
part. I did not get a faster version of my old job. I got a different job, and
nobody handed me a description of it.

I spend most of my day now doing something that has no good name. Not reviewing,
exactly, because reviewing implies the work is finished and I am checking it.
More like continuously asking a colleague who is faster than me and more
confident than the situation warrants: how do you know that?

---

Three things convinced me this is the actual job and not a phase.

**The first is that an agent's account of its own work is not a record of its
work.** I wanted to know how often a tool was being used during a task, so I did
the obvious thing and asked. It told me six.

I believed it. That is the part worth saying plainly. It was a specific number,
delivered without hedging, about events that had happened minutes earlier inside
the same conversation. There was no reason to doubt it and I did not.

The actual figure, sitting in a log the whole time, was fourteen.

Not a rounding difference. Not a disagreement about what counts. More than twice,
in the direction that made the story tidier. What I had been handed was not a
log. It was prose about a log, generated the same way everything else is
generated, and nothing had checked it against the log. I now read the log.

**The second is that fluent wrong answers cost more than confused ones.** A
system that sounds uncertain gets checked. A system that sounds certain gets
built on.

I once got an answer that began with the word "yes" and was accurate in every
clause after it. Every fact in the sentence was true. Every reference in it was
real. The problem was that the source it drew from was recommending against the
thing, and the answer's first word said the opposite.

Every clause true. The conclusion inverted. And the reader's eye takes the first
word and moves on, because that is what first words are for.

**The third is that being good at the visible part is not protection.** In one
comparison I ran, the agent that could not see a project's discussion history
did *better* first-principles code reading than the one that could. Cleaner
tracing, better structural understanding. It was the stronger engineer of the
two on the part I could watch.

It would also have written a patch that seven people had already written. Five
of those attempts were still open. Two had been closed without ever landing.
None of it exists in the code, because none of it became code, and reading the
code perfectly gets you no closer to knowing it happened.

Skill at the visible task does not compensate for an invisible one. It disguises
the gap.

---

I would like to tell you I spotted all of this from the outside, as a careful
observer. I did not.

I wrote myself a rule about exactly this class of mistake: never conclude a
thing is reachable from a description of it, go and execute it. I wrote the rule
down because I had broken it, and I wrote it in a document whose whole purpose
is that every rule in it cost something.

I broke it again the next day. In writing. I looked at a version number, decided
what that implied, and never ran anything. The implication was backwards, and I
was holding the document that said not to do that.

The agent caught it. It ran the actual cases, got identical results across all of
them, and the thing I had asserted turned out to be untrue of the version I was
asserting it about.

I mention this not as a confession but as a correction to how this is usually
framed. The problem is not that machines are careless and humans are careful.
Both of us reached for the convenient signal over the authoritative one, on
consecutive days, about the same class of question. The difference is that one of
us was faster.

---

What I have changed is smaller than it sounds.

I no longer accept a summary of work as evidence of work. If there is a record,
I read the record.

I no longer treat confidence as information. It correlates with nothing I care
about, and in a few measured cases it correlated backwards.

And I have stopped asking whether an answer is right, which is a question I
usually cannot settle, and started asking what it would have needed to see to be
right. That one is answerable. Often the answer is that the deciding fact was
never in the code at all, and no amount of reading the code was going to produce
it.

What I do not know is whether this ratio improves. It is possible that better
models shrink the verification burden until it is background noise again. It is
also possible that it grows, because the faster the generation, the more surface
there is to check, and checking has not got faster at all. I have been doing this
for months and I genuinely cannot tell which way it is going.

I would rather say that than pick the version that makes for a better ending.

If you are working this way too, I would like to know what you stopped
delegating. Not what failed once. What you tried, measured, and took back.
