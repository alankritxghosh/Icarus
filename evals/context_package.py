"""Reshape an investigation's already-gated findings into structured context
an agent can read BEFORE writing code -- Experiment B's `icarus.context(task)`
(docs/HANDOFF.md's Agent Mode entry, and see docs/experiments/2026-08-10-*).

Every field here is drawn from something ALREADY proven safe elsewhere:
architecture/dependencies/files from demo/structure.py (pure, deterministic,
no writer, cannot bluff); decisions/unknowns/citations from
evals/investigator.py through the SAME honesty gate /ask and /investigate go
through; risks from evals/attempts.py (deterministic, no model).

This module adds NO new retrieval, NO new model call, and NO new honesty
logic -- it is a pure reshaping/grouping function over outputs that are
already gated or already deterministic. That is deliberate: the six Agent
Mode tasks measured this session (docs/experiments/2026-08-10-agent-mode-exp-
a-run*.md, exp-d*.md) found Icarus's real value is telling an agent whether to
act and what was already tried, not speed -- so the safest and smallest
version of a structured "get me up to speed" interface is one that can only
ever say LESS than what /investigate already proved, never more.

Deliberately DROPPED from the original brief's schema: "symbols". Nothing in
the codebase extracts symbol-level information cheaply and honestly today --
a permanently-empty field would be worse than a documented omission. Add it
only when there is a real, gated source for it.
"""
from typing import Dict


def build_context_package(investigation, result, structure: Dict, texts: Dict[str, str]) -> Dict:
    """
    `investigation` is the evals.investigation.Investigation a task's
    investigate() run produced. `result` is what conclude() returned for it --
    the gate-checked answer, whose `.citations` are what the package's own
    `citations` field reports (narrower than everything gathered).
    `structure` is demo.structure.build_structure(chunks) over the SAME
    corpus. `texts` is the caller-owned ref->text map investigate() filled
    (see investigator.py's docstring on why this cannot be rebuilt from the
    index afterwards -- a live-fetched PR/commit/diff would go missing).
    """
    from .attempts import rejected_attempts

    summary = investigation.summary()

    # decisions: verified findings backed by something more than code alone.
    # A WEAK claim (code alone, or one uncorroborated source) proves WHAT,
    # never WHY -- see evals/investigation.py's own SUPPORT_HEADLINES -- so it
    # does not belong in a package a caller reads for "why is it built this
    # way". summary()["claims"] already excludes unverified claims.
    decisions = [
        {"text": c["text"], "support": c["support"], "citations": list(c["citations"])}
        for c in summary["claims"]
        if c["support"] in ("explicit", "strong")
    ]

    # Every ref this task's investigation actually gathered, in absorption
    # order -- NOT just what made it into the final cited answer. A rejected-
    # attempt PR is exactly as valuable whether or not the conclusion happened
    # to cite it (evals/attempts.py's own docstring: "set on the abstention
    # path too").
    prs, issues, files = [], [], []
    for ref, ev in investigation.evidence.items():
        if ev.source == "pr":
            prs.append(ref)
        elif ev.source == "issue":
            issues.append(ref)
        elif ev.source == "code":
            path = ref.split(":", 1)[1].split("#", 1)[0] if ":" in ref else ref
            if path not in files:
                files.append(path)

    risks = rejected_attempts({ref: texts.get(ref, "") for ref in investigation.evidence})

    constraints = []
    if summary["budget_note"]:
        constraints.append(summary["budget_note"])
    for lang in structure.get("unanalysed_languages", []):
        constraints.append(f"{lang} files are not structurally analysed")
    unresolved = structure.get("unresolved_import_count")
    if unresolved:
        constraints.append(
            f"{unresolved} imports could not be resolved to an indexed file")

    return {
        "task": investigation.objective,
        "architecture": structure.get("components", []),
        "dependencies": {
            "file_edges": structure.get("file_edges", []),
            "package_edges": structure.get("package_edges", []),
        },
        "files": files,
        "decisions": decisions,
        "prs": prs,
        "issues": issues,
        "risks": risks,
        "constraints": constraints,
        "unknowns": summary["unknowns"],
        "citations": list(result.citations),
    }
