# Experiment D, redone with directed Icarus consultation

Date: 2026-08-10
Repo: `simonw/llm` @ `94769b8b076c` (Icarus's currently connected corpus).
Two clean, independent clones — `experiment-d2-control`,
`experiment-d2-experiment` — so neither arm's edits could collide.

## Design

The original D efficiency half tested whether a model *volunteers* to use
Icarus. This run tests something different: two independent subagents, same
task, neither sees the other — but the experiment arm is **explicitly
directed** to call `get_change_context` with a specific question before
investigating further, mirroring Experiment C's task 5 finding that
unprompted consultation essentially never happens.

Task: issue #1340, "MIME type detection fails when puremagic returns empty
string." Chosen and verified the same way as every task today — checked
against the actual pinned-commit source (`git show 94769b8:llm/utils.py`),
not GitHub's live state: neither `mimetype_from_string` nor
`mimetype_from_path` guards against `puremagic` returning `''` instead of
raising `PureError`, confirmed live and unfixed.

Deliberately chosen despite a real limitation, disclosed up front: unlike D's
original uv tasks or C's task 5, the two closed-unmerged PRs found in an
earlier manual search (`#1358`, `#1387`) carry **zero review comments** —
no stated maintainer reason for either rejection. A prediction was
registered before launch (`docs/experiments/` scratch file, not committed)
that this weaker signal would produce a smaller correctness delta than the
sharper D/C-task-5 cases, since the fix is closer to self-diagnosable than
history-dependent.

## Result: the prediction was wrong, and instructively so

**On efficiency**, the actual metadata-reported tool counts (not either
agent's self-report — see below) were:

| | control | experiment |
|---|---|---|
| tool calls | 14 | **7** |
| wall clock | 123s | **47s** |

The directed arm was faster *and* cheaper. This contradicts the prediction,
which expected the pattern from Experiment D's original efficiency half
(Icarus arm slower) and C's task 5 (a directed call triggering a cascade of
extra verification). Here, Icarus's answer front-loaded information that
would otherwise require a large GitHub PR search to reconstruct — the
consultation collapsed work rather than adding it.

**A real self-report discrepancy, flagged rather than glossed over:** the
control arm reported `TOOL_CALLS: 6` in its own summary, but the harness's
own usage metadata for that same run shows `tool_uses: 14` — more than
double. The experiment arm's self-report (7) matched its metadata exactly.
The 14-vs-7 comparison above uses the metadata, not either self-report,
because this is now the second time in this session a self-reported tool
count has proven unreliable (see the original D efficiency half's own
caveat). Self-reports should be treated as indicative at best; metadata,
where available, is the number to trust.

## The decisive divergence

**Control did genuinely thorough, first-principles investigation.** It went
further than the experiment arm on pure code archaeology: it found and read
the actual installed `puremagic` library source
(`puremagic/main.py:229-230`) to trace the exact mechanism (`perform_magic()`
returning `info.mime_type` directly, which is empty for some magic-signature
entries), traced downstream through `Attachment.resolve_type()`
(`llm/models.py:86-99`) to the precise line producing the quoted error
string, and found a real precedent commit (`570a3ec`, "fixed a mimetype
detection bug") via plain `git log` showing the maintainer's own historical
pattern for this class of fix. This is *more* thorough root-causing on pure
code than the experiment arm produced.

**And it would still have shipped an eighth duplicate.** Its own conclusion:
`WOULD_WRITE_CODE: YES`. It had no way to know this fix already exists,
unreviewed, in five open pull requests, and was already submitted and closed
twice before — none of that is visible to `git log`/`git blame`, because
none of the seven merged.

**Experiment's directed Icarus call surfaced all seven in one response.**
Not the two the control-side manual search (mine, earlier today) had found —
**seven**: five open, two closed-unmerged. Its own words: this is what
changed the recommendation *"from 'write the obvious fix' to 'don't
duplicate 7 existing attempts.'"* `WOULD_WRITE_CODE: NO`.

**Both arms independently derived the identical fix content** (`if not
type_: return None`, in both wrapper functions). The prediction was right
about that much. What it got wrong was assuming convergent fix content would
mean no meaningful difference — it meant the entire difference in outcome:
whether to submit the fix at all, not what the fix should say.

## Cross-run pattern, now n=3 on the "directed" shape

| run | Icarus arm vs. control on efficiency | Icarus arm vs. control on correctness |
|---|---|---|
| Original D (uv, volunteered) | slower | right — control would have called a live bug fixed |
| C task 5 (llm, directed) | slower (extra archaeology triggered) | right — found a design 3 prior attempts missed |
| **This run (llm, directed)** | **faster** | **right — control would have duplicated 7 attempts** |

Efficiency is not consistent across these three — it depends on whether the
Icarus answer collapses a search that would otherwise be large (this run) or
opens a line of follow-up verification that wouldn't otherwise happen (C task
5). **Correctness is consistent: three for three, an agent working from code
and git history alone reached the materially worse conclusion every time.**

## Honest limits

- n=1 task for this specific redo; n=3 across the whole "directed
  consultation" pattern including C's task 5, one repo.
- The task's weak point (no stated rejection reason on either closed PR) did
  not weaken the result the way predicted — the sheer *volume* of duplicate
  attempts turned out to be signal enough on its own, which is itself worth
  registering as a finding: a rejected-attempt signal does not need a stated
  reason to be decision-relevant. Seven independent submissions of the same
  fix, none merged, is information a careful engineer would want regardless
  of whether anyone explained why.
- Both clones (`experiment-d2-control`, `experiment-d2-experiment`) are left
  in place, uncommitted, no changes made (both arms were investigation-only
  by instruction) — safe to delete.
