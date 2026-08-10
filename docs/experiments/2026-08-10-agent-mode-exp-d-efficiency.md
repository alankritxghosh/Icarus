# Experiment D, efficiency half — two uncontaminated agents, one task

Date: 2026-08-10
Repo: `astral-sh/uv`, local clone at HEAD `6253839`; Icarus corpus `a50af60f`
Task: issue **#20675** — "Clean up `~/.local/share/uv/python/.temp`" (bug).
Chosen fresh: none of the five earlier Agent Mode tasks touched it.

## Design

The paired within-task design used earlier could not produce efficiency
numbers, because the Icarus arm had already read the code. This run fixes that
with **two subagents, neither able to see the other's work**:

- **CONTROL** — local repository only, explicitly forbidden from every
  `mcp__icarus__*` tool.
- **EXPERIMENT** — same repository plus Icarus.

Identical prompts, identical task, identical clone, same model, same required
report fields. Both barred from `gh` and the web, so neither could read the
issue thread directly.

## Results

| | control | experiment |
|---|---|---|
| tool calls | **15** | 19 (2 Icarus) |
| distinct files opened | 12 | **10** |
| wall clock | **164s** | 300s |
| root cause | `.keep()` disowning the `TempDir`, already fixed | same, **plus a second, unfixed cause** |
| would write code? | **NO** | **YES** |
| confidence maintainers want it | HIGH ("already merged") | MEDIUM (honest) |

**Registered prediction, and it was wrong.** Before launching I wrote that the
Icarus arm would "reach a decision in fewer steps but not necessarily a
different one." The opposite happened on both counts: it took *more* calls and
nearly twice the wall clock, and it reached a *different* decision.

**On raw efficiency, Icarus lost.** That is the honest headline of this run and
it should not be softened: 4 extra tool calls and +136s. The one efficiency
metric it won — files opened, 10 vs 12 — is small and self-reported.

## The disagreement, which is the actual result

Both arms found the merged fix (commit `8d09b838`, PR #20752) and both
correctly reported that the `.keep()` leak is closed at HEAD.

The **control stopped there**: fix shipped, nothing to do. It classified the
abrupt-termination case as a "structural RAII limitation, not something this
issue's fix addressed or that I'd touch."

The **experiment kept going**, because Icarus surfaced something git history
does not contain: **PR #20754, a second attempt to fix this same issue via
`uv cache clean`, was tried and CLOSED without merging, while the issue itself
stayed open.** A merged fix, plus a rejected follow-up, plus a still-open
issue, is a signature that the reported problem was not fully solved.

It then established the residual cause from the code — `.temp` depends
entirely on `tempfile::TempDir`'s `Drop`, which never runs under SIGKILL or an
OOM kill; `find_all()` explicitly excludes `.temp` (managed.rs:227);
`uv cache clean` never references it; `uv python uninstall` only clears it as a
side effect of removing everything — and proposed sweeping `.temp` inside
`ManagedPythonInstallations::lock()`, where the exclusive lock proves anything
present is orphaned from a dead run. It explicitly avoided the `cache clean`
route **because that was the rejected one**.

So the control would have closed a live bug as "already fixed", and the
experiment found real remaining work while steering around a known-rejected
design.

## The design flaw, which is mine

I barred `gh` and the web but allowed `Bash` for git. The control therefore
reached **commit messages**, including `8d09b838`'s, which names issue #20675
outright. That is a genuine history channel.

So this is not "history vs. no history". It is **indexed PR/issue discussion vs.
what `git log` records**. And the divergence falls exactly on that boundary:
git recorded the *merge*; only Icarus recorded the *rejection*. A closed,
unmerged PR leaves no trace in the commit graph at all.

That makes the comparison narrower than I set it up to be, and more precise
about where the value actually sits: **not in knowing what happened, but in
knowing what was tried and refused.**

## Caveats

- Counts are self-reported by each agent; I received final reports, not raw
  tool logs. Indicative, not audited.
- n=1 task, one repository, whose index is truncated at 5,000 PRs/issues.
- The experiment arm verified Icarus's claims against the code and git history
  rather than trusting them, and rated maintainer-acceptance MEDIUM while
  flagging that it could not learn *why* #20754 was closed. That is the right
  posture and worth preserving in any Agent Mode prompt.

## What this adds to the session's running result

Six tasks now, and in **6 of 6 the unaided reading produced the wrong action**.
Five times by acting when it should not have; this time by the opposite error —
**stopping too early**, declaring a still-open bug already fixed.

The claim this supports is narrow and defensible: **Icarus does not make an
agent faster. It changes what the agent concludes.** Anyone selling it on
speed will be contradicted by this run's own numbers.
