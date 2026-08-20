# sales/

Lead pipeline for Icarus outreach. **Not part of the product.** `screen_leads.py`
imports nothing from Icarus at all; `ask_repo.py` uses it read-only as a library
and writes only into `outputs/leads/corpora/`. Nothing here touches
`evals/corpus/`.

## Unattended

`launchd` runs `run_nightly.sh` at 06:12. A run missed because the Mac was
asleep fires shortly after it wakes, so the briefing is waiting when the lid
opens.

    cp sales/com.icarus.leads.nightly.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.icarus.leads.nightly.plist

Stop it:

    launchctl unload ~/Library/LaunchAgents/com.icarus.leads.nightly.plist

**Prerequisite, and it is currently unmet:** headless `claude -p` needs its own
credential. As of 2026-08-05 it fails with `OAuth session expired and could not
be refreshed`. Fix once with `claude setup-token` (or export `ANTHROPIC_API_KEY`
in `run_nightly.sh`), then confirm:

    claude -p "Reply with exactly: HEADLESS OK" --allowedTools ""

Until that prints, the nightly job will produce an empty log every morning.

## The pieces

| file | what it does | judgement? |
|---|---|---|
| `screen_leads.py` | GitHub search + hard gates + finds a named human **with proven commit rights** | none — pure numbers |
| `ask_repo.py` | index a prospect, dump reason-bearing history, ask + grade | none |
| `queries.txt` | the search rotation | — |
| `nightly.md` | the standing instruction for the nightly Claude pass | all of it |
| `roll_up.py` | rebuilds `ALL_LEADS.md` + `VERIFIED_OWNERS.md` from everything on disk | none |
| `send_log.py` | append-only record of what was sent and what came back | none |
| `run_nightly.sh` | one headless `claude -p` | — |

Judgement lives in `nightly.md` where you can read and edit it. Mechanics live
in the scripts, where they cannot hallucinate.

## Who counts as a contact (changed 2026-08-17)

A contact must have **proven write access**, not a high contribution count.
`write_access()` asks GitHub (one GraphQL call) who has **merged** pull
requests here; merging requires write access, so it is a fact about permission
rather than an inference from activity. A personal repo's owner counts without
merging anything, since they always have it. An organisation never counts — it
is not a person to email.

**Why it changed.** Contacts used to come from `/contributors`, which ranks by
patches accepted — exactly what a contributor with no rights also has. Campaign
3 emailed a `marp-team/marp-cli` contributor who replied *"I'm just a
contributor so not for me"*. Verified live on that repo: the old path ranked
`chrisns` **third** of thirty, the new path returns only `yhatt`, who merged
all 100 sampled pull requests.

The cost is deliberate: repos where nobody with write access publishes an
address now fail with `nobody with proven commit rights publishes a usable
address` instead of yielding a contributor. A smaller list of real owners is
the point — see the outreach rules in the vault's `Outreach.md`.

## By hand

    python3 sales/screen_leads.py "language:TypeScript stars:1000..15000 topic:video" --limit 25
    .venv/bin/python sales/ask_repo.py index OWNER/REPO
    .venv/bin/python sales/ask_repo.py digest OWNER/REPO
    .venv/bin/python sales/ask_repo.py ask OWNER/REPO questions.json answers.json

`.venv/bin/python` for `ask_repo.py`, always — system Python has no fastembed
and retrieval degrades silently to lexical-only.

Self-checks: `python3 sales/screen_leads.py --self-check`,
`python3 sales/ask_repo.py self-check`.

## The send log (added 2026-08-17)

    python3 sales/send_log.py send --person "..." --email x@y.io \
        --repo owner/name --campaign 2026-08-batchN --subject "..."
    python3 sales/send_log.py observe --email x@y.io --campaign ... --kind reply
    python3 sales/send_log.py checked --campaign ... --channel email
    python3 sales/send_log.py report  --campaign ...

Three campaigns and ~104 sends produced the conclusion "0 replies", which
**cannot be told apart from "0 delivered"**. `site/for/outreach_log.jsonl` is a
hand-written diary: its first row compresses 23 sends into one line, and the
71-send campaign is absent. A diary records what someone concluded; this
records what happened.

**Delivery is three-valued and starts at UNKNOWN, per channel.** "No bounce
seen" is evidence only if somebody looked, so a send counts as `delivered` only
after a `checked` event for *its own channel*. Reconciling Gmail says nothing
about an X DM — which is exactly how one positive reply stayed invisible while
its batch was written up as a total failure (see the vault's `Outreach.md`).

Gmail already holds the ground truth for bounces and replies, so this does not
poll it; `observe`/`checked` are how a mailbox read gets written down.

**Backfill honesty:** only 16 of ~104 historical sends had a recoverable
recipient. The rest were never recorded per-person and were NOT invented. Reply
rates over that backfill are therefore computed on a biased subset — the rows
someone bothered to write down skew toward the ones that got a reply. Treat any
pre-2026-08-17 rate as illustrative, never as a measurement.

## Output

    outputs/leads/ALL_LEADS.md             <- one table, every lead, read this first
    outputs/leads/briefing-YYYY-MM-DD.md   <- detail behind tonight's top row
    outputs/leads/fit.json                 <- measured stage-2 signals per repo
    outputs/leads/candidates-YYYY-MM-DD.json
    outputs/leads/<slug>-answers.json
    outputs/leads/corpora/<owner>__<repo>/ <- indexed prospect corpora (large)
    outputs/leads/logs/YYYY-MM-DD.log
