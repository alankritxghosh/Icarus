# demo/onboarding.py
"""The guided onboarding tour: what Icarus says about a repository, unprompted.

A tour is a fixed short sequence of questions Icarus asks on the user's behalf
before they type anything. It is deliberately NOT a workflow engine and holds
NO per-user state: the plan is a constant, each step is fetched on its own, and
the client drives the order. That is what makes "interrupt with a question and
come back" free -- there is no session to lose, so resuming is just asking for
the next step. Build the engine only if a thin tour proves one is needed.

Every step goes through the ordinary `GatedPipeline` -- same retrieval, same
writer, same deterministic honesty gate -- so a step that has no evidence says
"no one wrote this down" exactly as any other answer would. There is no new
honesty path here, and there must never be one: a claim Icarus VOLUNTEERS gets
less scepticism from a reader than one they asked for, so it needs more proof,
not less.

**Which steps ship is a measurement, not a taste.** `evals/onboarding_probe.py`
asked seven candidate steps across ten real repositories (2026-07-29):

    purpose      10/10   (after addressing the README -- 2/10 when searched for)
    stack        10/10
    recent       10/10
    conventions   9/10
    decisions     8/10
    ----------------- shipped above, cut below -----------------
    debt          5/10
    architecture  2/10   (anchoring it to the README did NOT help: still 2/10,
                          and it cost spf13/cobra a real answer -- a README says
                          what a project is FOR, not how its code is arranged)

The two cut steps stay in the probe so we find out if they ever become viable;
they are not in the tour, because a tour that refuses a third of the time is a
worse first impression than a shorter tour that does not.
"""

from .repo_map import build_map

# `.explain()` takes a line range; a README is never this long. The corpus does
# not record real file lengths, so this stands in for "the whole file".
_WHOLE_FILE_END = 10 ** 6

# The steps that ship, in the order a person would want them. Question wording
# is load-bearing: these are the EXACT strings the probe measured, and
# demo/test_onboarding.py's drift guard fails if the two ever diverge --
# otherwise "10/10 on purpose" would quietly stop being evidence about the tour
# that actually ships.
STEPS = [
    ("purpose", "What is this project?",
     "What does this repository do, and what problem does it solve?"),
    ("stack", "What it is built with",
     "What programming languages, frameworks and major dependencies does this "
     "project use?"),
    ("decisions", "Decisions that shaped it",
     "What significant architectural or design decisions were made in this "
     "project, and why?"),
    ("conventions", "How the team works",
     "What conventions or practices does this project expect contributors to "
     "follow?"),
    ("recent", "What changed recently",
     "What has changed most recently in this project?"),
]

# Steps answered from a specific DOCUMENT ADDRESSED BY PATH instead of searched
# for, mapping step id -> the key in the repository map's
# `indexed_documentation` that names the file.
#
# Both entries were earned by measurement over ten real repos, and both fixed
# the SAME failure: the document that answers the question is indexed the whole
# time, and retrieval reaches history that merely MENTIONS it instead.
#
#   purpose      2/10 -> 10/10 answered. Searching found commit messages; the
#                README's own embedded window is dominated by badges, logo
#                markup and sponsor blocks (measured on sindresorhus/execa: the
#                answer is 30 characters at offset 300 of the ~2,000-character
#                window the embedder actually reads).
#   conventions  answered 9/10 but only 4/9 SUBSTANTIVELY -- every hollow one
#                cited a commit that mentioned a contributing guide ("added in
#                commit a6ed0f2") rather than the guide, which 7 of the 10
#                repos had indexed all along.
#
# A step with no such document falls back to an ordinary ask, and on that
# evidence is expected to abstain rather than paraphrase a commit. That is the
# correct outcome, not a gap.
ANCHOR_DOCUMENT = {"purpose": "readme", "conventions": "contributing"}

# Kept as the set of step ids for callers (and the probe) that only need to ask
# "is this step anchored?".
ANCHORED_STEPS = set(ANCHOR_DOCUMENT)

_BY_ID = {step_id: (title, question) for step_id, title, question in STEPS}

# The tour opens with the map and entry points. They need no retrieval at all,
# so they are solid during the lexical-only window right after a connect --
# which is exactly when a first-time user takes the tour, and exactly when the
# writer-backed steps are measurably at their worst.
_OVERVIEW = {"id": "overview", "kind": "map",
             "title": "What Icarus has read",
             "detail": "Served by GET /map -- indexed files, languages, "
                       "documentation and entry points. No writer, no retrieval."}

# The second writer-free step: how the code is ARRANGED, read off its own
# imports (`demo/structure.py`), served from the same GET /map response.
#
# This is deliberately NOT the `architecture` step measurement cut. That one
# asked the writer "how is this codebase structured?" and answered 2 of 10 real
# repositories -- the worst of any candidate -- and anchoring it to the README
# the way `purpose` and `conventions` were anchored did not move it at all,
# because a README says what a project is FOR, not how its code is laid out.
# The arrangement is written down in exactly one place, the imports, so this
# step reads it there instead of asking a model to recall it. It cannot
# abstain and it cannot bluff; where a repository genuinely has no resolvable
# internal imports it reports none, which is the true answer rather than a
# failure. `architecture` stays cut, and stays measured by the probe.
_STRUCTURE = {"id": "structure", "kind": "structure",
              "title": "How the code is arranged",
              "detail": "Served by GET /map as indexed_structure -- components, "
                        "what depends on what, and the indexed chunk proving "
                        "each edge. No writer, no retrieval."}

_INDEXING_NOTE = (
    "Icarus is still building semantic search for this repository. The tour "
    "works now, but answers are keyword-only until it finishes, so a step that "
    "says it doesn't know may mean Icarus hasn't finished reading -- not that "
    "nobody wrote it down."
)


def plan(status):
    """The ordered tour for the caller's connected repo. Pure and instant --
    no writer, no retrieval, so a client can render the whole shape before any
    step is answered."""
    indexing = bool(status.get("indexing", False))
    return {
        "repo": status.get("repo"),
        "commit": status.get("commit"),
        "semantic_indexing_in_progress": indexing,
        "note": _INDEXING_NOTE if indexing else "",
        "steps": [_OVERVIEW, _STRUCTURE] + [
            {"id": step_id, "kind": "question", "title": title, "question": question}
            for step_id, title, question in STEPS
        ],
    }


def answer_step(pipeline, status, step_id, token=None):
    """Answer ONE tour step. Returns a `Result`, untouched -- an abstention is
    passed straight through, never softened into something that reads like an
    answer.

    An ANCHORED step addresses one specific document -- `purpose` the README,
    `conventions` the contributing guide -- with the path resolved from the
    repository map, so `readme.md`, `docs/contributing.rst` or
    `.github/CONTRIBUTING.md` all work without guessing. It goes through
    `.explain()`, which resolves evidence by location using the identical
    writer and gate. Everything else is an ordinary `.answer()`.

    The honest cost of that, stated rather than buried: `.explain()` runs with
    the gate's (b) why->what guard OFF, because someone selecting code wants
    its "what". `purpose` is a what-question so that is the intended semantics,
    but it does mean this one step is held to groundedness alone rather than
    also to the rationale heuristic.

    No README indexed -> fall back to an ordinary ask. A repo without one still
    gets a tour; the step just performs as it did before the fix.
    """
    entry = _BY_ID.get(step_id)
    if entry is None:
        raise ValueError(f"unknown onboarding step: {step_id!r}")
    _title, question = entry

    doc_key = ANCHOR_DOCUMENT.get(step_id)
    if doc_key:
        docs = build_map(pipeline.indexed_chunks(), status)["indexed_documentation"]
        path = docs.get(doc_key)
        if path:
            # neighbors=False: answer from THIS document, nothing else. With
            # neighbours on, the anchor resolved and ranked first and the
            # writer still cited a commit message that merely discussed the
            # topic -- reporting another project's conventions as this one's
            # (found live 2026-07-30 on alankritxghosh/Icarus). Addressing a
            # document guarantees it is present, not that it is used.
            return pipeline.explain(path, 1, _WHOLE_FILE_END, question=question,
                                    neighbors=False)
    return pipeline.answer(question, token=token)


def title_for(step_id):
    entry = _BY_ID.get(step_id)
    return entry[0] if entry else None
