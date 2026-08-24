# evals/test_context_stability.py
"""The stability gate for `get_task_context`: does the SAME task, asked twice,
return the same decisions?

WHY THIS EXISTS. Measured 2026-08-25 over four trials against a real repository
(`docs/experiments/2026-08-25-agent-mode-three-trial-variance.md`): same question,
same corpus, `indexing: false` throughout, nothing varying but the writer's
sampling.

    trial            decisions   FALSE decision present?
    08-24                    2   no
    08-25 T1                 2   YES
    08-25 T2                 3   YES
    08-25 T3                 3   YES

The unstable entry claimed retrieval consumers were "not currently" wired, at a
commit where they are. It carries support `explicit` -- the STRONGEST class --
and cites a pull request that resolves perfectly, so no gate can see it.

WHAT THAT COST. A one-lexical-trial vs one-semantic-trial comparison had been
written up as "retrieval fixed it", and a clean retrieval-defect vs writer-defect
split built on top. Three trials refuted it. **A difference observed once is a
draw, not a mechanism**, and this board exists so that mistake needs deliberate
effort to repeat.

WHAT IS MEASURED, and what deliberately is not:

  * MEASURED -- the `decisions` list, because it is what the tool's own
    description tells an agent to read before starting work, and it is
    model-produced end to end.
  * NOT measured -- `architecture` / `dependencies`. `demo.structure` is pure and
    deterministic, so it cannot vary, and importing `demo` from `evals` would
    invert the dependency direction the repo maintains. A fixed structure dict is
    passed instead.
  * NOT measured -- prose wording. Two runs may phrase one decision differently
    and mean the same thing; the gate keys on whether a decision is PRESENT.

IT IS GREEN ON THIS CORPUS, AND GREEN HERE IS NOT REASSURANCE. Measured
2026-08-25, first run: 3/3 trials returned IDENTICAL decisions, unknowns, risks
and citations on the committed `simonw/llm` board, lexical-only.

**So this gate does NOT reproduce the defect it was built for, and would not have
caught it.** Say that plainly rather than reading the green as "the loop is
stable". The recorded instability was a different corpus
(`SaravananJaichandar/world-model-mcp`), a different task, and hybrid retrieval;
this is the committed board, a plugin-registry task, and BM25 only.

Its remaining value is as a REGRESSION detector: if the loop becomes unstable on
this corpus, this fires. That is worth having and is not what was asked for.

The live hypothesis, recorded in [[Unknowns]] rather than acted on: the unstable
case sits on evidence describing SUCCESSIVE STATES of one feature -- a dense
CHANGELOG plus the stacked `#22`/`#23`/`#24` pull requests -- where several
mutually-inconsistent-over-time claims are all individually citable. The stable
case has no such layering. If that is right, stability is a property of the
EVIDENCE, not of the loop, and a board on the committed corpus can never show it.

It must never be made to look better by lowering `TRIALS`, by comparing counts
instead of membership, or by sampling one trial.

COST. Each trial is a full investigation -- several billed writer calls -- so
this needs BOTH `GEMINI_PAID_API_KEY` and an explicit `RUN_STABILITY_BOARD=1`,
matching the opt-in other expensive live boards use. It never fires by accident.
"""
import json
import os
import unittest
from pathlib import Path

from . import investigator
from .context_package import build_context_package
from .corpus import load_chunks
from .entities import build_entity_index
from .env_file import load_env_file
from .pipeline import GatedPipeline
from .provider import make_provider
from .query_normalize import build_vocabulary
from .retriever import (
    HybridRetriever, LexicalRetriever, NormalizingRetriever, SemanticRetriever,
)

_CORPUS = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"

TRIALS = 3

# A real task over the committed simonw/llm board -- the corpus every other eval
# uses, so this is reproducible by anyone with the paid key.
TASK = os.environ.get("STABILITY_TASK") or (
    "Add a new model provider plugin, wiring it through the plugin registry "
    "and the command line interface")

# demo.structure's output is pure and deterministic, so it cannot contribute
# variance. Fixed here rather than computed, which also keeps `evals` from
# importing `demo`.
_FIXED_STRUCTURE = {
    "file_edges": [], "file_edge_evidence": [], "package_edges": [],
    "components": [], "most_depended_on_files": [],
    "unresolved_import_count": 0, "unanalysed_languages": [],
}


def _decision_key(d):
    """Identity of a decision for comparison purposes.

    The CITATION SET, not the prose. Two runs may word one finding differently
    and mean the same thing; a finding resting on different evidence is a
    different finding. Falls back to the text when a decision cites nothing.
    """
    cites = tuple(sorted(d.get("citations") or ()))
    return cites if cites else ("text:" + (d.get("text") or "").strip().lower(),)


class ContextDecisionsAreStable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        load_env_file(".env")
        if not os.environ.get("RUN_STABILITY_BOARD"):
            raise unittest.SkipTest(
                "RUN_STABILITY_BOARD=1 not set; this board runs "
                f"{TRIALS} full investigations and costs money")
        if not os.environ.get("GEMINI_PAID_API_KEY"):
            raise unittest.SkipTest("GEMINI_PAID_API_KEY not set; live board")
        if not _CORPUS.exists():                        # pragma: no cover
            raise unittest.SkipTest("committed corpus missing")
        chunks = load_chunks(_CORPUS)
        # Hybrid when the embedder is available, lexical otherwise -- the SAME
        # fallback demo/library.py makes in production, so neither regime is
        # unrepresentative. The regime is printed with the results because it
        # bounds what the numbers describe: the recorded 2026-08-25 case was
        # measured on hybrid.
        try:
            import fastembed  # noqa: F401
            from .provider import make_embedding_provider
            inner = HybridRetriever(LexicalRetriever(chunks),
                                    SemanticRetriever(chunks, make_embedding_provider("local")))
            cls.regime = "hybrid (BM25 + local semantic)"
        except ImportError:
            inner = LexicalRetriever(chunks)
            cls.regime = "LEXICAL ONLY (fastembed unavailable)"
        retriever = NormalizingRetriever(inner, build_vocabulary(chunks))
        provider = make_provider("gemini-paid")
        pipeline = GatedPipeline(retriever, chunks, provider)
        entities = build_entity_index(chunks)

        cls.trials = []
        for _ in range(TRIALS):
            texts = {}
            inv = investigator.investigate(TASK, pipeline, entities, provider, texts=texts)
            result = investigator.conclude(inv, provider, texts=texts)
            pkg = build_context_package(inv, result, _FIXED_STRUCTURE, texts)
            cls.trials.append(pkg)

        print(f"\n  === get_task_context stability, {TRIALS} trials ===")
        print(f"  retrieval: {cls.regime}")
        for i, pkg in enumerate(cls.trials, 1):
            print(f"  trial {i}: {len(pkg['decisions']):>2} decisions  "
                  f"{len(pkg['unknowns']):>2} unknowns  "
                  f"{len(pkg['risks']):>2} risks  "
                  f"{len(pkg['citations']):>2} citations")
            for d in pkg["decisions"]:
                print(f"      [{d['support']}] {d['text'][:88]}")

    def test_the_same_decisions_appear_in_every_trial(self):
        """THE GATE. A decision that appears in some trials and not others means
        an agent asking the same question twice is told different things about
        the same repository, and has no way to know which draw it got.

        Do NOT make this pass by comparing counts, by sampling one trial, or by
        lowering TRIALS. If the loop is made stable, this goes green on its own.
        """
        sets = [{_decision_key(d) for d in t["decisions"]} for t in self.trials]
        shared = set.intersection(*sets) if sets else set()
        unstable = set.union(*sets) - shared if sets else set()
        if unstable:
            detail = []
            for key in sorted(unstable, key=str):
                seen = [i + 1 for i, s in enumerate(sets) if key in s]
                text = next((d["text"] for t in self.trials for d in t["decisions"]
                             if _decision_key(d) == key), "?")
                detail.append(f"    trials {seen} only: {text[:100]}")
            self.fail(
                f"{len(unstable)} of {len(set.union(*sets))} decisions are not "
                f"stable across {TRIALS} identical calls:\n" + "\n".join(detail))

    def test_the_same_decision_TEXTS_appear_in_every_trial(self):
        """THE SECOND GATE, added after the first one gave a FALSE GREEN.

        `_decision_key` compares CITATION SETS, justified on the grounds that two
        runs may word one finding differently and mean the same thing. On the
        layered arm (2026-08-25) that justification broke: trial 1 said the
        schema "uses a `conversation_tools` table or JSON column", trials 2-3
        said it "uses a `ToolCall` data class with a `tool_call_id`". Same
        citations, materially different claims, and the citation-keyed gate
        passed it.

        So text is compared too. The disclosed cost is the opposite error: a
        trivial rewording fails this. That is the cheaper mistake — a false green
        on a substantive divergence is exactly what this board exists to prevent,
        and it already happened once."""
        norm = lambda t: " ".join((t or "").lower().split())
        sets = [{norm(d["text"]) for d in t["decisions"]} for t in self.trials]
        shared = set.intersection(*sets) if sets else set()
        unstable = (set.union(*sets) - shared) if sets else set()
        if unstable:
            detail = []
            for text in sorted(unstable):
                seen = [i + 1 for i, st in enumerate(sets) if text in st]
                detail.append(f"    trials {seen} only: {text[:110]}")
            self.fail(
                f"{len(unstable)} decision texts are not stable across {TRIALS} "
                f"identical calls:\n" + "\n".join(detail))

    def test_the_unknowns_count_is_stable(self):
        """Reported separately because it moves independently: on the layered arm
        the counts were 6 / 11 / 11 while the citation-keyed decision gate stayed
        green. An unknowns list that nearly doubles between identical calls is
        the same instability wearing a different field."""
        counts = [len(t["unknowns"]) for t in self.trials]
        self.assertEqual(len(set(counts)), 1, f"unknowns count varied: {counts}")

    def test_every_trial_reaches_a_verdict_and_cites_something(self):
        """Diagnostic, kept separate: if this fails, the board above is measuring
        a broken run rather than instability."""
        for i, pkg in enumerate(self.trials, 1):
            self.assertTrue(pkg["citations"], f"trial {i} cited nothing at all")

    def test_the_deterministic_fields_never_vary(self):
        """The half that MUST stay stable, and the reason the honest claim about
        this feature is the deterministic one. `risks` comes from
        `evals.attempts.rejected_attempts` over whatever the investigation
        gathered -- so it can vary if the GATHERING varies, and that is itself
        worth seeing. Reported, then asserted, so a regression here is loud."""
        risk_sets = [tuple(sorted(r["ref"] for r in t["risks"])) for t in self.trials]
        self.assertEqual(len(set(risk_sets)), 1,
                         f"risks varied across trials: {risk_sets}")
