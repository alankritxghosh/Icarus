# History-failure reduction pilot — preregistration

Registered 2026-08-27 before task discovery or any agent session, per
`docs/experiments/PROTOCOL.md` §3. The task-selection rules, primary endpoint,
analysis, predictions, and invalidation rules above `## Result` are frozen.
Candidate and result records may only be appended below that line.

## Why this replaces raw fix rate as the percentage experiment

The preceding quality-delta run measured the named bug being fixed. Its control
arm reached 17/17, so the metric has no useful headroom. It also measures a
generic coding ability Icarus does not claim to provide. Icarus's stated Agent
Mode value is narrower: supplying recorded engineering history before a change
so an agent does not repeat a refused approach, act on a superseded decision,
or violate a recorded constraint.

This pilot measures that value directly. The old quality-delta record remains a
valid negative result about raw bug-fix pass rate; it is not extended or
reinterpreted into a different metric.

## Status and claim boundary

This is a **30-task paired pilot**, not a confirmatory benchmark. It exists to
estimate the baseline failure rate, the treatment/control discordance rate, and
the confirmatory sample size. No public "percent better" claim may be made from
this pilot, even if its point estimate is large.

A later confirmatory run may make a claim only if it uses the unchanged endpoint
and rubric, is sized from this pilot before launch, and its paired 95% confidence
interval excludes zero improvement.

## The causal question

> When the same coding agent receives Icarus's retrieved engineering-memory
> context before working on the same task, by what percentage does the rate of
> recorded-history mistakes fall?

This is **directed efficacy**, not unprompted product effectiveness. The harness
obtains the Icarus context before the treatment session and supplies it to the
agent. The control session receives the identical task without that context.
This removes tool-call choice from the causal comparison.

An unprompted availability experiment is separate owed work. Mixing the two
would confound "Icarus supplied useful information" with "the agent happened to
call the tool."

## Primary endpoint

One binary outcome per history-bearing task and arm: `history_failure`.

`history_failure = true` when the final plan, explanation, or patch does at
least one of the following against the task's pre-frozen gold record:

1. repeats an explicitly refused approach without acknowledging the refusal or
   presenting new evidence that answers it;
2. treats a superseded proposal or past state as current;
3. violates an explicit recorded constraint or maintainer decision;
4. claims no relevant prior attempt or decision exists when the gold record
   contains one;
5. asserts a rationale that the retrieved record does not support.

Merely failing to mention history is not a primary failure when the delivered
outcome is history-safe. `history_awareness` is recorded separately as a
secondary outcome so the primary metric measures avoided mistakes rather than
performative citation.

## Percentage reported

The headline effect, if the later confirmatory run supports one, is:

```text
relative history-failure reduction
    = (control failure rate - treatment failure rate)
      / control failure rate * 100
```

Every report also includes:

- absolute percentage-point reduction;
- paired 95% confidence intervals;
- exact paired discordance test;
- number of task pairs and repositories;
- both arm rates, so the percentage cannot hide its denominator.

"Percent better" is not used without naming the outcome. The permitted form is
"X% fewer recorded-history failures," never "X% better results."

## Secondary endpoints

- `technical_success`: the frozen reproduction/test passes.
- `history_safe_technical_success`: technical success with no history failure.
- `history_awareness`: the output identifies the relevant recorded attempt,
  decision, or honest absence.
- `unsupported_rationale`: any unsupported "why" claim.
- elapsed wall time, model/tool calls, and Icarus call outcome; descriptive
  only, never substituted for the primary endpoint.
- on null-history tasks: invented-history rate and honest-unknown rate.

The existing groundedness, bluff-rate, and abstention-recall gates remain
blocking. A treatment that improves the primary endpoint while weakening an
honesty gate is not a win.

## Task pool — 30 paired tasks, at least five repositories

The pool is stratified before discovery:

| Stratum | Target | Primary population? |
|---|---:|---|
| explicitly refused approach | 12 | yes |
| superseded/replaced proposal or past state | 6 | yes |
| explicit recorded constraint/maintainer decision | 6 | yes |
| no relevant recorded history | 6 | no; harm/honesty control |

The primary effect is calculated over the 24 history-bearing tasks. The six null
tasks test whether Icarus invents history or adds avoidable harm and are reported
separately. They are not diluted into the efficacy percentage.

### Inclusion rules — all mechanical before launch

Each history-bearing task must have:

1. a public repository and pinned commit;
2. a real, executable user-facing task at that commit;
3. a source-of-truth GitHub record predating the pin or describing the relevant
   historical attempt/decision;
4. an explicit gold statement of the landmine and what would count as repeating,
   contradicting, or respecting it;
5. a technical reproduction or deterministic acceptance check;
6. a successful directed Icarus probe that actually returns the gold-relevant
   record before the task enters the treatment pool.

A closed-unmerged PR alone is insufficient. The review, successor, maintainer
comment, or other primary record must establish whether it was refused,
superseded, or merely closed. The experiment may not translate "closed" into
"rejected."

Each null task must have a bounded search of the relevant issues, pull requests,
commits, and repository docs recorded before launch. "Nothing exists" is never
claimed universally; the gold label is "no relevant record found in the bounded
search."

Rejected candidates are logged with their reason. Discovery stops at 30 valid
tasks; it does not relax a rule to fill a stratum.

## Frozen task record

Before any agent session, each task is serialized with:

```json
{
  "task_id": "opaque identifier",
  "repo": "owner/name",
  "commit": "full SHA",
  "stratum": "refused|superseded|constraint|null",
  "prompt": "verbatim task",
  "technical_check": "exact command and expected result",
  "gold_refs": ["primary GitHub URLs or immutable refs"],
  "gold_landmine": "reviewer-only statement",
  "failure_conditions": ["observable condition"],
  "icarus_probe": "verbatim directed question",
  "icarus_probe_refs": ["refs actually returned"]
}
```

The task file's SHA-256 is recorded here before launch. Gold fields never enter
either agent's prompt.

## Arms and isolation

For every task:

- same pinned model/build, task prompt, limits, repository commit, network
  access, and clean checkout;
- one task per fresh session, no session reuse;
- no shared worktree, stash, transcript, cache, or prior arm output;
- control: Icarus tools absent and transcript proves absence;
- treatment: a verified directed Icarus response for the correct repository and
  commit is appended as read-only engineering-memory context;
- arm order is assigned from SHA-256 of `20260827-history-pilot:<task_id>`, so
  order is deterministic, balanced by parity, and unknowable before task IDs
  are frozen;
- arms are interleaved by task instead of running every control first, limiting
  model/provider time drift.

Any wrong-repository response, unavailable treatment, writable-session failure,
dirty starting tree, popped stash, mismatched commit, or missing transcript
voids the **pair**, not merely the inconvenient arm. The pair is rerun cleanly
under its original assignment and the invalid run remains logged.

## Scoring and blinding

Technical checks run mechanically. History outcomes are scored from an opaque
review packet that removes the arm label and randomizes presentation order.

Two reviewers independently apply the frozen task-specific failure conditions.
Disagreements are adjudicated against the primary record before arm labels are
revealed. Inter-reviewer agreement is reported. If Cohen's kappa is below 0.80,
the rubric is considered insufficiently reproducible: the pilot may revise the
rubric, but all affected outputs must then be rescored from scratch and cannot be
used as confirmatory evidence.

No agent self-report and no LLM judge determines the primary endpoint.

## Analysis

The task pair is the unit of analysis. Sessions and citations are not treated as
independent observations.

- arm rates and relative failure reduction are point estimates;
- absolute reduction receives a repository-clustered paired bootstrap 95% CI;
- relative reduction receives the same clustered bootstrap when the sampled
  control denominator is non-zero;
- the paired discordance table and exact two-sided McNemar p-value are reported;
- results are also shown by stratum and repository, without treating those
  underpowered slices as separate claims.

The confirmatory sample size is calculated from the pilot's discordant-pair rate
for 80% power, two-sided alpha 0.05, against a minimum worthwhile relative
failure reduction frozen after the pilot and before confirmatory launch.

## Registered predictions

1. Directed Icarus context will reduce recorded-history failures by at least
   25% relatively on the 24 history-bearing tasks. Confidence: low-to-medium;
   this is a pilot estimate, not a claim.
2. The largest effect will be on refused and superseded strata, where working
   tree and ordinary `git log` evidence is structurally incomplete.
3. Raw technical success will remain high and differ little, reproducing the
   negative fix-rate result rather than reversing it.
4. At least one treatment run will still fail because Icarus retrieves the wrong
   evidence, fails to convey decisive evidence, or states a stale rationale.
   The product's measured defects make a clean sweep implausible.
5. Null tasks will show no treatment advantage. Any invented-history increase is
   reported as harm, not averaged away.

## Result

In progress. No agent sessions have started and no outcome data exist.

Candidate screening on 2026-08-27 and 2026-08-28 has rejected nineteen tasks before the manifest was
frozen:

- two superseded-history tasks because live Icarus probes missed the decisive
  earlier or successor pull request;
- one constraint task because the reviewer's suggested workaround failed the
  mechanical reproduction; and
- one constraint task because its motivating behavior belonged to another
  repository and could not be scored deterministically at the pinned commit;
- one refused task because its review thread was mixed and did not establish a
  refusal; and
- one constraint task because its Python 2-only failure cannot be reproduced
  in the frozen environment; and
- one null-history task because its failure requires a real Jupyter/ipywidgets
  lifecycle that the frozen environment cannot reproduce deterministically;
- one refused candidate because its pull request was ultimately merged and is
  visible in ordinary Git history; and
- one refused candidate because it closed for inactivity after actionable
  review rather than because maintainers refused the approach; and
- one null-history candidate because its external Dify failure had no payload
  or local reproduction and would require credentials to exercise;
- one null-history candidate because reproducing an inaccessible macOS keyring
  requires a real graphical-session boundary and the pinned auth API discards
  the error before a deterministic test can observe it; and
- one null-history candidate because adding a top-level signal context alone
  cannot prove the named cleanup outcome across blocking pager and raw-I/O
  paths; and
- one constraint candidate because the repository had no deterministic browser
  check covering its combined rendered-visibility, clipboard, and syntax-token
  contract, so any source assertion would prescribe an unregistered mechanism;
  and
- one constraint candidate because reproducing its resolver-setting mismatch
  requires a pinned uv build plus a controlled multi-version package index, while
  a source-only check would silently decide the disputed compatibility policy;
  and
- one refused candidate because both proposals reproduced the symptom only by
  using the same declined raw-string mechanism, leaving no accepted structural
  behavior to freeze as a passing check;
- one refused candidate because its site-specific nested-code-block selector
  had no accepted generic contract that could be frozen without prescribing a
  new mechanism;
- one refused candidate because its apparent refusal was actually superseded
  by merged pull requests, placing it in the wrong stratum;
- one refused candidate because the claimed CommonJS/ESM build failure was
  absent at the pinned commit; and
- one refused candidate because a later merged issue-closing pull request made
  the proposed refusal narrative incomplete.

The reviewer-only candidate ledger retains those failures and the proposed
replacements. Deterministic validation is complete for all 30 survivors.
Pinned-commit Icarus probes, the frozen manifest hash, and all experimental
sessions remain outstanding.

Screening also exposed a registered secondary-endpoint tension before launch:
on an explicitly refused task, a history-safe agent may correctly decline the
requested implementation or propose a narrower alternative, while the frozen
reproduction for the requested behavior remains red. The primary
`history_failure` endpoint still measures the registered causal question, but
prediction 3 and `technical_success` cannot be interpreted as independent
evidence of benefit in that stratum. This limitation was recorded before any
agent session and does not change the frozen endpoint or rubric.

### Amendment 1 — 2026-08-28: probe results, pool reduced to 23, manifest frozen

Appended after the pinned Icarus probes ran and before any agent session. The
text above this `## Result` heading is unchanged.

**The probes were never credential-blocked.** `GEMINI_PAID_API_KEY` was present
in the gitignored `.env` throughout; `scripts/history_pilot_probe.py` simply did
not load `.env` the way `evals/run.py` does, so a present key read as absent and
this experiment was reported as blocked for a day. Fixed by loading `.env` in
the probe entry point; the interlock is unchanged and the free `GEMINI_API_KEY`
was never accepted as the paid attestation. This is `PROTOCOL.md` §5 — read the
state that produced the error, not the error string.

**All 30 pinned probes ran on the production paid writer** (`gemini-paid`,
`private_safe=True`) against the exact-commit corpora. Result:

| | pass | miss |
|---|---:|---:|
| refused | 10 | 2 |
| superseded | 4 | 2 |
| constraint | 3 | 3 |
| null | 6 | 0 |
| **total** | **23** | **7** |

Seven tasks — C05, C07, C08, R04, R20, S04, S05 — returned verdict `unknown`
with **zero citations**: the decisive record never reached the writer.
Inclusion rule 6 requires a successful directed probe that actually returns the
gold-relevant record, so those seven are rejected into the candidate ledger with
their reason. **No rule was relaxed to fill a stratum**, and no replacement was
substituted under time pressure.

Two further tasks missed the mechanical gate but were approved on review:
`N08` (null stratum) answered with correct bounded absence — "there are no
indexed records… while issue #6109 notes…" — which is precisely the behaviour
that stratum tests, and for which retrieving a gold ref is not the criterion;
`R13` answered substantively about the maintainer position from `issue:501`
without retrieving `pr:347`.

**This 7/30 probe-miss rate is itself a result and is reported as one.** On a
task pool constructed specifically because its history was known to exist and be
recorded, Icarus's production retrieval failed to surface the decisive record
for 23% of tasks (30% including the two soft misses). That is a measurement of
the product's retrieval ceiling, not a screening artefact, and it is recorded
here rather than in a footnote per `PROTOCOL.md` §4.

**Amended pool: n = 23** — refused 10, superseded 4, constraint 3, null 6. The
primary effect is therefore calculated over **17 history-bearing tasks**, not
24. This materially reduces power; the pilot's purpose (estimating the baseline
rate, the discordance rate, and the confirmatory sample size) survives, but the
constraint stratum at n=3 cannot support even a descriptive per-stratum reading
and will be reported as such. The no-public-claim boundary is unchanged and now
binds harder.

**Frozen artefacts** (built by `scripts/history_pilot_freeze.py`, which imports
`derive_arm_order` from the session runner so the two cannot disagree, and
copies no reviewer-only field):

```text
manifest.json          SHA-256 6b084f285643e1cb0a6d0dfe4c443cfc63cd41860191de5cf42d93fe91cc27f3
context-packet.json    SHA-256 06d09b3a1a6b89e162e3748fb426b8092c640f1bd09702e0fab1e9860c64b9ef
```

Verified through `scripts/history_pilot_sessions.py`: 23 tasks → 46 isolated arm
plans, unique output paths, treatment prompt equal to control plus one delimited
read-only Icarus block, and **zero** of the 56 reviewer-only landmine/failure
strings present in any assembled prompt.

**Corpus-completeness limitation.** Two of six repositories carry partial issue
coverage: `astral-sh/uv` (PRs and issues both at the 5,000 cap) and `cli/cli`
(PRs complete at 4,551; issues at the cap). rich, requests, firecrawl and
world-model-mcp are complete. A treatment context drawn from a truncated corpus
is a weaker treatment than one drawn from a complete corpus.

**Technical-check environment.** Frozen and verified in
`docs/experiments/2026-08-27-history-pilot-check-env.md`: all 30 checks behave
as registered (20 assertion-red at pin, 7 exception-red where the post-fix API is
absent, 3 green guardrails by design — C01, C05, R05). Scoring must treat a
non-zero exit at the pin as the reproduction regardless of exception type, and
must not expect the three guardrails to be red.

**Still outstanding:** the 46 agent sessions, arm verification, blinded packet
assembly, the two independent human reviews, and the statistical analysis. No
session has run and no outcome has been scored.

### Amendment 2 — 2026-08-28: arm blinding is partial by construction

Found while building `scripts/history_pilot_blind.py`, before any session ran,
by that script's own leak audit run against a deliberately prompt-echoing fake
agent.

A coding agent routinely restates or quotes its own prompt in its final
response. The treatment prompt carries the delimited Icarus context block, so an
unredacted response hands the reviewer the arm label outright. The packet
builder now strips every verbatim reproduction of that block (and any lone
delimiter) from all reviewer-visible text, and refuses to emit a packet whose
audit still finds one.

**The residual cannot be removed and is registered here rather than discovered
during scoring.** An agent that actually used the supplied history will
paraphrase it — "PR #18604 was refused because…" — which no redaction can
strip, and which is precisely what the `history_awareness` secondary endpoint
measures. Blinding therefore conceals the *mechanical* tell, not the *semantic*
one; a reviewer may still infer the arm from an output that demonstrates
knowledge of unrecorded-in-code history.

Consequences accepted:

- reviewer independence and the frozen failure conditions remain the safeguard
  against arm-guessing biasing the primary endpoint, but they do not make the
  arm unguessable;
- inter-reviewer agreement (Cohen's kappa, reported) measures rubric
  reproducibility, not blinding integrity, and must not be cited as evidence of
  the latter;
- any confirmatory run inherits this limitation. A design that removes it would
  need the treatment's advantage to be invisible in the output, which is
  incompatible with measuring whether the treatment was used at all.

### Amendment 3 — 2026-08-28: single-reviewer scoring, registered before any outcome exists

Registered **before the first agent session ran and before any outcome was
observed**. Nothing in this amendment was chosen with knowledge of the results,
which is the only reason it is legitimate rather than a rationalisation
(`PROTOCOL.md` §3).

The registered design requires **two independent reviewers**, disagreements
adjudicated against the primary record before unblinding, and Cohen's kappa
reported, with the rubric considered insufficiently reproducible below κ = 0.80.
A second independent human reviewer is not available in the time this run has.

**This run will therefore be scored by a single human reviewer.** The
consequences are accepted in full and stated here rather than discovered later:

1. **No inter-reviewer agreement can be computed.** κ is undefined for one
   reviewer. The κ ≥ 0.80 rubric-reproducibility gate is therefore **not met —
   not passed, not failed, unevaluated.** No statement may be made about the
   rubric's reproducibility on the basis of this run.
2. **This run is not confirmatory-eligible and can never be promoted.** It
   cannot become the confirmatory run by later adding a second reviewer to the
   same outputs, because that reviewer would not be independent of a rubric
   already applied once. A confirmatory run needs fresh sessions and two
   reviewers from the start.
3. **The existing no-public-claim boundary is unchanged and now binds on a
   second ground.** No "X% fewer recorded-history failures" statement may be
   made publicly from this run, regardless of the point estimate.
4. Single-reviewer scoring compounds Amendment 2: with arm blinding partial by
   construction, reviewer independence was the main safeguard against
   arm-guessing biasing the primary endpoint, and one reviewer removes it. The
   frozen per-task failure conditions remain the only structural safeguard.
5. The reviewer scores from the blinded packet with arm labels withheld, and the
   unblind key is opened only after every verdict is submitted, exactly as the
   two-reviewer flow would have. `scripts/history_pilot_blind.py` refuses a
   single verdict file, so unblinding this run requires deliberately passing the
   same reviewer's file twice — the refusal is left in place as friction rather
   than removed, and the duplication is recorded in the result.

**Supersession:** if a second independent reviewer is secured **before scoring
begins**, this amendment is void, the two-reviewer flow applies unchanged, and κ
is reported as originally registered. It cannot be voided after scoring starts.

What this run still produces honestly: both arm rates, the absolute and relative
reduction, the paired discordance table, the exact McNemar p-value, the
repository-clustered bootstrap intervals, and a discordance rate from which a
confirmatory sample size can be calculated. Those are the pilot's actual stated
purposes. What it does not produce is evidence.
