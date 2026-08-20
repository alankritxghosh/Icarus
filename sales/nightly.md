You are running the Icarus sales lead pipeline unattended. Alankrit is asleep.
He will read only one thing when he opens his laptop: the briefing you write.

Work from the repo root. Everything you need is in `sales/`. Do NOT modify any
file outside `sales/` and `outputs/leads/`. Do not touch `evals/corpus/`.

## 1. Screen

Pick ONE query from `sales/queries.txt` — the one least recently used according
to `outputs/leads/query_log.txt` (if that file is missing, use the first line).
Append the query and today's date to `outputs/leads/query_log.txt`.

    python3 sales/screen_leads.py "<query>" --limit 25 \
        --out outputs/leads/candidates-$(date +%F).json

## 2. Judge fit

Read the passed candidates. For each, gather with `gh api` (sleep 2 between
calls, GitHub secondary-rate-limits a tight loop):

- human-authored merged PRs: `search/issues?q=repo:R+is:pr+is:merged+-author:app/dependabot+-author:app/renovate`
- issue count, contributor count, `created_at`

Fit for Icarus means: **enough recorded reasoning to reconstruct, and a team
big enough to have forgotten it.** Rough floor: 100+ human merged PRs, 5+
contributors, 1+ year old. A repo below that produces a demo of abstentions.

Merge what you measured into `outputs/leads/fit.json` (keyed by repo:
`{"human_prs": N, "issues": N, "contributors": N, "since": "YYYY-MM"}`). Keep
existing entries; omit any key you could not measure rather than writing a
guess. This is what makes the consolidated table complete.

Rank them. Say why in one sentence each, in plain English, no engineering
jargon. If fewer than two clear the floor, say so and stop — do not pad.

## 3. Index the top one (two if the first indexes fast)

    .venv/bin/python sales/ask_repo.py index OWNER/REPO
    .venv/bin/python sales/ask_repo.py digest OWNER/REPO

`.venv/bin/python`, always. System Python has no fastembed and the pipeline
degrades silently to lexical-only. Indexing a large repo takes ~25 min; that
is expected, let it run.

## 4. Write 20 questions, ask them, keep 15

Derive every question from the digest — from PRs and issues that actually
record a reason. **Never invent a question from the README.** Include 3-4
deliberate long shots about architecture choice; those usually come back
unknown, and the honest unknown is what the recording is for.

    .venv/bin/python sales/ask_repo.py ask OWNER/REPO <questions.json> \
        outputs/leads/<slug>-answers.json

One pass. Never re-run with different settings and keep the better result.

## 5. Briefing, then the consolidated table

Write `outputs/leads/briefing-$(date +%F).md` — the detail for tonight's repo —
then regenerate the one table covering every lead ever found:

    python3 sales/roll_up.py

`outputs/leads/ALL_LEADS.md` is what Alankrit opens first; the briefing is the
detail behind tonight's top row. Structure of the briefing:

    # Briefing <date>

    ## Record Icarus on
    <repo> — <one plain sentence: why this company, no jargon>
    Contact: <name> <email>  (from stage 1; never a role inbox)

    ## Five reasons this repo works
    1-5, plain language, each tied to something measured (PR count, an actual
    answer Icarus gave). No adjectives you cannot back.

    ## The 15 questions, in recording order
    Each line: the question, then [ANSWERED, cites pr:123] or [HONEST UNKNOWN].
    Order them so the recording builds: 2-3 easy wins, then the deep ones,
    then close on an honest unknown.

    ## Why these and not the others
    The repos you rejected and the number that killed each.

    ## What I could not verify
    Anything you did not measure. Be explicit. An empty section is a lie.

Rules that override anything above: never invent a repo, a person, an email,
a PR number, or an answer. If a step fails, write the briefing anyway with the
failure in it. A short honest briefing beats a full invented one.
