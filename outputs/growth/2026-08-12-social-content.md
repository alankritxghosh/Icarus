# Icarus social content, 2026-08-12

Drafts only. Nothing in this file has been posted or scheduled.

## Zero-awareness rule

Assume the reader has never heard the name Icarus. Every standalone post must
first explain, in plain language:

1. What it is: engineering memory for software teams and their coding agents.
2. What it does: reads a repository's GitHub record so people and agents can
   understand the system, investigate a question, and recover prior decisions
   and attempts before changing code.
3. How it stays trustworthy: it cites retrieved repository evidence or makes
   the missing record explicit instead of filling the gap from model memory.

Only then introduce the tagline, the demo result, or Agent Mode. "Git remembers
what changed. Icarus remembers why." is a differentiator, not a sufficient
introduction by itself.

Use this stable category sentence when space allows:

> Icarus is engineering memory for software teams and their coding agents. It
> reads a repository's GitHub record and returns cited context or an honest
> unknown before someone changes the code.

The first public demo shows one human workflow, not the whole product. Do not
let the overlay imply that Icarus is only a voice assistant or code explainer.

## Asset decision

Use `site/shots/demo_icarus.mov` for the X demo post. It is 60.06 seconds and
shows both load-bearing product states against `psf/requests`:

1. A cited answer to "Why does requests not support HTTP/2?", with receipts
   for issues 6856 and 6752.
2. An honest unknown for "Why is the redirect limit 30?", with the sources
   searched rather than an invented explanation.

Do not use `site/shots/icarus_product_demo_2026-07-24.mov` as the primary
demo. It is 6.56 seconds and shows repository connection plus the question
being entered, but not the answer or refusal. No third recording is needed for
this batch.

`site/shots/panel_cited.png` and `site/shots/panel_refusal.png` are the verified
still-image fallbacks. They were captured from the live product, not recreated
for marketing.

## X post 1: demo

### Recommended copy

> I built Icarus: engineering memory for people and coding agents.
>
> It reads a repository's code and GitHub history, then returns cited context
> or an honest unknown before someone changes the code.
>
> Here is one workflow on psf/requests.

Attach `site/shots/demo_icarus.mov`. Do not add a link to the body of the
first post. If someone asks to try it, send the current installation path in
the reply only after checking that the path is live.

### Alternate hook

> This is Icarus: engineering memory for the people and agents changing a
> codebase.

Keep the rest of the recommended copy from "It reads a repository...".

## X post 2: Agent Mode

### Recommended copy

> Icarus gives coding agents the repository memory they do not start with.
>
> Before changing code, they can retrieve prior decisions and attempts from
> GitHub, with citations or an honest unknown.
>
> In one test, that exposed 7 prior attempts and stopped an 8th
> duplicate.

Use `site/shots/panel_cited.png` or a real Agent Mode capture if one already
exists and is verified. Do not manufacture a coding-agent UI for this post.

### Alternate hook

> Icarus is not another coding agent. It is the repository memory underneath
> one.

Then continue from "Before an agent changes code...". Keep "In one test" in
the result sentence; this is evidence from one directed task, not a universal
performance claim.

## LinkedIn post 1: demo

### Recommended copy

> I have been building Icarus, an engineering-memory system for software teams
> and the coding agents working alongside them.
>
> It connects to GitHub and turns the repository record into usable context:
> a guided map for someone new, multi-step investigation for harder questions,
> prior decisions and attempts before a change, and cited answers when the
> evidence supports them.
>
> When the reason was never recorded, Icarus says so. That missing rationale
> becomes a visible engineering-memory gap instead of a confident guess.
>
> This demo shows one of those workflows on psf/requests. I ask two questions:
>
> 1. Why does Requests not support HTTP/2?
> 2. Why is the redirect limit 30?
>
> For the first, it finds the recorded discussion and shows the GitHub issues
> behind the answer.
>
> For the second, it finds the implementation but no recorded rationale. So it
> says: "No one wrote this down."
>
> That distinction is the trust boundary. The broader product is a shared
> engineering memory that people and coding agents can consult before they
> change a system.
>
> Git remembers what changed. Icarus remembers why.
>
> I am looking for engineering leaders willing to test this against a real
> repository and tell me where it breaks.

Attach the same 60.06-second demo natively. Do not paste the X post or place an
external link in the opening paragraph.

### Alternate hook

> I am building Icarus: engineering memory for the people and coding agents
> changing a codebase.

Then continue from "It connects to GitHub...".

## LinkedIn post 2: Agent Mode

### Recommended copy

> Icarus is engineering memory for software teams and their coding agents. It
> reads a repository's GitHub record so both can recover prior decisions and
> attempts before changing code, with cited evidence or an honest unknown.
>
> Here is why I think coding agents need it.
>
> An agent can read today's code. It usually cannot know:
>
> - why a team chose one approach over another
> - what earlier pull requests attempted and how the discussion ended
> - whether a strange constraint is intentional or accidental
> - when no rationale was recorded at all
>
> That missing history is where teams repeat old debates and agents
> confidently propose work the organization already explored.
>
> Icarus is not another coding agent, and it does not edit code. Through its
> read-only Agent Mode, the agent can retrieve change context, explain a
> specific code range, or build structured task context before it acts.
>
> In one directed test, an agent working from code alone found the local issue
> but was still prepared to submit another implementation. With Icarus, it saw
> seven previous attempts and stopped an eighth duplicate. That is one task,
> not a general benchmark result, but it makes the product hypothesis concrete.
>
> For engineering leaders rolling out agents across a team, the question is no
> longer only "Can it write code?" It is "Does it understand what this
> organization already learned?"

### Alternate hook

> Coding agents start with the task and today's code. Icarus gives them the
> repository memory they are missing.

Then continue from "An agent can read today's code...".

## Supporting post: the human product

Use after the introduction, not before it.

### X draft

> Icarus is more than the question box in the demo.
>
> It gives a new teammate a guided repository tour, briefs returning engineers
> on what changed, and runs multi-step investigations with an evidence trail.
>
> Same engineering memory, different moments of work.

### LinkedIn angle

Show the five current Mac surfaces together: Home, Start here, Investigate,
Decision History, and Engineering Memory. Frame them as a path from orientation
to investigation to durable capture, not as five disconnected features.

## Supporting post: closing the memory gap

Use only after the audience understands the cite-or-unknown boundary.

### X draft

> Sometimes Icarus finds the code but no recorded reason.
>
> That is not a failed answer. It is a visible engineering-memory gap.
>
> A person can record the missing rationale through a reviewed GitHub PR, then
> Icarus can cite it after merge and re-indexing.

Do not imply Icarus autonomously decides or writes the rationale. A human
supplies it, GitHub review remains the control point, and Icarus does not merge
the record.

## Claim guardrails

- Say that citations are deterministically constrained to retrieved evidence.
  Do not claim arbitrary semantic faithfulness is mathematically guaranteed.
- Say "recorded why" or "recorded context". Never imply Icarus can retrieve a
  reason that nobody documented.
- A closed-unmerged pull request is evidence of an attempted path, not proof
  that the team rejected the idea. The cited discussion determines meaning.
- Do not claim the Agent Mode result generalizes beyond the measured
  experiments. The strongest measured trigger result is four unprompted calls
  in four tasks on one repository; the seven-attempt duplicate result is one
  directed task.
- Icarus complements coding agents. It does not implement changes for them.
- Do not describe the demo overlay as the whole product. It is one client and
  one workflow over the shared brain.
- Do not claim that every semantically unsupported sentence is caught by code.
  Citation containment and explicit covered refusals are deterministic;
  arbitrary entailment still depends on the writer.
- Do not say customer code is discarded after every request while the product
  intentionally maintains a repository index. Any provider-retention claim
  needs separately verified, precise wording.
