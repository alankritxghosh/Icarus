# evals/onboarding_probe.py
"""Measure how often a guided onboarding tour would have to say "I don't know".

The thin onboarding tour is a fixed sequence of questions asked on the user's
behalf, before they type anything. Every one of them goes through the ordinary
`GatedPipeline` -- same retrieval, same writer, same honesty gate -- so every
one of them can honestly abstain. That is correct behaviour and it is also a
product risk: a tour where most steps refuse is a bad first experience, and
nobody knows the real rate.

This measures it, per step and per repository, BEFORE any tour UI is designed,
so the sequence is built around the rate that exists rather than the one we
hoped for.

Deliberately NOT a unittest: it needs the network, `gh`, a paid writer key and
tens of minutes. Run it directly:

    .venv/bin/python3 -m evals.onboarding_probe --repos owner/a,owner/b
    .venv/bin/python3 -m evals.onboarding_probe            # the default set

Notes on method, so the number can be trusted:
- It connects each repo through the REAL serving path (`demo.library.Library`),
  not the eval harness, because that is what a user would hit.
- `background_upgrade=False`, so every question is asked AFTER the semantic
  index is installed. Asking during the lexical-only window measurably turns
  correct answers into abstentions (docs/HANDOFF.md, 2026-07-28) and would
  measure the wrong thing.
- Corpora are cached under `--storage`, so a re-run is cheap and a crash
  resumes.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# The tour's steps come from the PRODUCT (demo/onboarding.py), never a copy:
# this probe is the evidence that "purpose 10/10" is true of the tour that
# actually ships, and a second set of question strings here would silently
# invalidate that the first time someone reworded one.
#
# CANDIDATE_STEPS are the ones measurement CUT from the tour. They stay here on
# purpose -- if `architecture` or `debt` ever become viable, this probe is what
# should tell us, and dropping them would guarantee we never find out.
#
# Steps in ANCHORED_STEPS address the repo's README by path instead of
# searching for it; see demo/onboarding.py for the measurement behind that.
from .substance import is_substantive  # noqa: E402
from demo.onboarding import (  # noqa: E402
    ANCHORED_STEPS, STEPS as _SHIPPED_STEPS, answer_step,
)

CANDIDATE_STEPS = [
    ("architecture", "How is this codebase structured, and what are its main "
                     "components?"),
    ("debt", "What known limitations, technical debt or open problems does this "
             "project have?"),
]

ONBOARDING_STEPS = [(step_id, question) for step_id, _title, question in _SHIPPED_STEPS] \
    + CANDIDATE_STEPS

# Ten real public repositories, chosen for range rather than for flattering
# results: four languages, a documentation-heavy project and a sparse one, a
# framework and a small library, plus one whose primary language this ingest
# does NOT index at all (shellcheck is Haskell) so the honest failure mode is
# in the sample rather than excluded from it.
#
# The bias that remains, and it is real: these are all SMALL-to-medium repos,
# picked so ten of them can be ingested and embedded in one sitting. A
# monorepo's tour may behave differently, and this does not measure that.
DEFAULT_REPOS = [
    "simonw/sqlite-utils",      # Python, exceptionally well documented
    "pallets/click",            # Python, mature library, heavy docs
    "psf/requests",             # Python, huge history, medium docs
    "spf13/cobra",              # Go, framework
    "charmbracelet/glow",       # Go, small app
    "sindresorhus/execa",       # JS, small library
    "tj/commander.js",          # JS, mature library
    "rust-lang/mdBook",         # Rust, app + book
    "koalaman/shellcheck",      # Haskell -- NOT an indexed language
    "jesseduffield/lazygit",    # Go, large app, sparse formal docs
]


def probe_repo(lib, repo, anchor=True, judge=None):
    """Connect `repo` and ask every onboarding step. Returns a result dict."""
    started = time.monotonic()
    status = lib.connect_sync(repo, background_upgrade=False)
    if status.get("state") != "ready":
        return {"repo": repo, "error": status.get("error") or status.get("state"),
                "steps": []}
    connect_seconds = round(time.monotonic() - started, 1)
    pipeline = lib.current_pipeline()

    # The repository map already knows the README's REAL indexed path (casing
    # and directory included), so no filename guessing is needed here.
    from demo.repo_map import build_map
    readme = None
    if anchor:
        readme = build_map(pipeline.indexed_chunks(), status)["indexed_documentation"]["readme"]

    shipped = {step_id for step_id, _t, _q in _SHIPPED_STEPS}
    steps = []
    for step_id, question in ONBOARDING_STEPS:
        anchored = anchor and bool(readme) and step_id in ANCHORED_STEPS
        try:
            if anchor and step_id in shipped:
                # Exercise the PRODUCT's own code path, so this measures the
                # tour that ships rather than a re-implementation of it.
                result = answer_step(pipeline, status, step_id)
            else:
                # Candidate steps the tour cut, and the --no-anchor baseline.
                result = pipeline.answer(question)
        except Exception as e:                    # a writer outage is not an abstention
            steps.append({"step": step_id, "verdict": "error",
                          "reason": type(e).__name__, "citations": [], "anchored": anchored})
            continue
        # Substantiveness is a QUALITY DIAL and is judged by a DIFFERENT
        # provider than the writer -- grading your own homework with the same
        # model is not a measurement. None when no judge was wired.
        substantive = None
        if judge is not None and result.verdict == "answer":
            substantive = is_substantive(judge, question, result.answer)
        steps.append({"step": step_id, "verdict": result.verdict,
                      "reason": result.abstention_reason,
                      "citations": result.citations,
                      "anchored": anchored,
                      "substantive": substantive,
                      "answer": result.answer[:400]})
    return {"repo": repo, "commit": status.get("commit"),
            "counts": status.get("counts"), "truncated": status.get("truncated"),
            "readme": readme, "connect_seconds": connect_seconds, "steps": steps}


def summarize(results):
    """Abstention rate overall, per step, and per repo -- plus the reasons,
    because "nobody wrote this down" and "that isn't in this repo" are
    different findings and only one of them is about the tour."""
    by_step, reasons = {}, {}
    answered = abstained = errored = substantive = judged = 0
    for r in results:
        for s in r["steps"]:
            if s.get("substantive") is not None:
                judged += 1
                substantive += 1 if s["substantive"] else 0
            bucket = by_step.setdefault(s["step"], {"answer": 0, "unknown": 0,
                                                    "error": 0, "substantive": 0})
            if s.get("substantive"):
                bucket["substantive"] += 1
            bucket[s["verdict"]] = bucket.get(s["verdict"], 0) + 1
            if s["verdict"] == "answer":
                answered += 1
            elif s["verdict"] == "unknown":
                abstained += 1
                reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
            else:
                errored += 1
    return {"answered": answered, "abstained": abstained, "errored": errored,
            "substantive": substantive, "judged": judged,
            "by_step": by_step, "reasons": reasons}


def _print_report(results, summary):
    total = summary["answered"] + summary["abstained"] + summary["errored"]
    print("\n" + "=" * 64)
    print("Onboarding abstention probe")
    print("=" * 64)
    for r in results:
        if r.get("error"):
            print(f"\n{r['repo']}: CONNECT FAILED ({r['error']})")
            continue
        line = " ".join(
            f"{s['step']}={'Y' if s['verdict'] == 'answer' else ('-' if s['verdict'] == 'unknown' else '!')}"
            for s in r["steps"])
        n_unknown = sum(1 for s in r["steps"] if s["verdict"] == "unknown")
        print(f"\n{r['repo']}  ({r['connect_seconds']}s connect, "
              f"{sum((r['counts'] or {}).values())} chunks"
              f"{', TRUNCATED' if r.get('truncated') else ''})")
        print(f"  {line}    {len(r['steps']) - n_unknown}/{len(r['steps'])} answered")
    print("\n" + "-" * 64)
    if total:
        print(f"ANSWERED {summary['answered']}/{total} "
              f"({100 * summary['answered'] / total:.0f}%)   "
              f"ABSTAINED {summary['abstained']}/{total} "
              f"({100 * summary['abstained'] / total:.0f}%)   "
              f"ERRORS {summary['errored']}")
    print("\nper step:")
    for step, _q in ONBOARDING_STEPS:
        b = summary["by_step"].get(step)
        if b:
            line = (f"  {step:<14} answered {b.get('answer', 0):>2}  "
                    f"abstained {b.get('unknown', 0):>2}  errors {b.get('error', 0):>2}")
            if summary.get("judged"):
                line += f"   substantive {b.get('substantive', 0):>2}"
            print(line)
    if summary.get("judged"):
        sub, jud = summary["substantive"], summary["judged"]
        print(f"\nSUBSTANTIVE {sub}/{jud} of the answers "
              f"({100 * sub / jud:.0f}%) -- the rest answered a question, but not"
              f" the one asked")
    print("\nabstention reasons:")
    for reason, n in sorted(summary["reasons"].items(), key=lambda kv: -kv[1]):
        print(f"  {str(reason):<22} {n}")
    print("=" * 64)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repos", default=None, help="comma-separated owner/name list")
    p.add_argument("--storage", default="/tmp/icarus-onboarding-probe",
                   help="corpus cache root (reused across runs)")
    p.add_argument("--out", default=None, help="write the full results as JSON here")
    p.add_argument("--judge", default=None,
                   help="provider that grades whether answers are SUBSTANTIVE "
                        "(e.g. groq). Must differ from the writer: grading your "
                        "own homework with the same model is not a measurement.")
    p.add_argument("--no-anchor", action="store_true",
                   help="reproduce the pre-fix baseline: search for every step "
                        "instead of addressing the README for ANCHORED_STEPS")
    args = p.parse_args(argv)

    from .env_file import load_env_file
    load_env_file(Path(__file__).resolve().parent.parent / ".env")
    from demo.library import Library

    repos = [r.strip() for r in args.repos.split(",")] if args.repos else DEFAULT_REPOS
    storage = Path(args.storage)
    storage.mkdir(parents=True, exist_ok=True)
    default_dir = Path(__file__).resolve().parent / "corpus"

    judge = None
    if args.judge:
        from .provider import make_provider
        judge = make_provider(args.judge)
        print(f"substantiveness judge: {args.judge} "
              f"(writer is gemini-paid -- cross-provider)", file=sys.stderr)

    lib = Library(default_dir, storage, "simonw/llm")
    results = []
    for i, repo in enumerate(repos, 1):
        print(f"[{i}/{len(repos)}] {repo} …", file=sys.stderr, flush=True)
        try:
            results.append(probe_repo(lib, repo, anchor=not args.no_anchor, judge=judge))
        except Exception as e:
            print(f"  {repo} failed: {type(e).__name__}: {e}", file=sys.stderr)
            results.append({"repo": repo, "error": f"{type(e).__name__}", "steps": []})
        if args.out:  # write as we go, so a crash keeps what already ran
            Path(args.out).write_text(json.dumps(results, indent=2) + "\n")

    summary = summarize(results)
    _print_report(results, summary)
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"results": results, "summary": summary}, indent=2) + "\n")
        print(f"\nfull results -> {args.out}")


if __name__ == "__main__":
    main()
