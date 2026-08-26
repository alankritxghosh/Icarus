"""Precompute web/public/graph.json: the REAL evidence graph of the committed corpus.

Lives in scripts/ rather than beside the site because the repo root .gitignore
carries a bare `build/` rule, which silently swallowed the previous home at
site/build/. The generated graph.json was committed and its generator was not,
which is the worst version of that mistake: the artifact looks maintained and
cannot be reproduced.

Build-time only. Never run in a request. Nothing here invents an edge -- every
edge comes from evals/entities.py, which carries the indexed chunk that proves
it. `subsequent_prs` is deliberately EXCLUDED: it is co-occurrence in time, not
a causal link (entities.py says so itself), and 2,372 such edges would turn the
render into the ornament the decision record forbids.

Layout is computed HERE, not in the browser, for three reasons: the page ships
no simulation, the result is deterministic, and `prefers-reduced-motion` gets a
final-position frame for free rather than a softened animation.
"""
import json, math, random, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.corpus import load_chunks                      # noqa: E402
from evals.entities import build_entity_index             # noqa: E402
from demo.structure import build_structure                # noqa: E402

# Co-occurrence, not causation. See entities.py limitations.
KINDS = ["linked_issues", "changed_files", "commits", "dependencies"]
SEED = 20260826


def path_of(ref):
    """`code:llm/utils.py#L149-L153` -> `code:llm/utils.py`.

    Citations name a WINDOW; entity edges name the FILE. Without this the
    highlight silently misses every code citation, which looks like the graph
    working and the answer citing nothing.
    """
    return ref.split("#", 1)[0]


_SOURCES = ("pr:", "issue:", "commit:", "code:", "doc:", "config:", "diff:", "index:")


def as_node(target):
    """Entity edges name a FILE by bare path (`llm/models.py`); nodes are
    prefixed (`code:llm/models.py`). Prefix bare paths so the two agree.

    Returns the node id, or None for a target the corpus never indexed --
    `changed_files` lists paths outside the ingested subtree (tests/, docs/),
    and drawing a node for one would depict evidence Icarus did not retrieve.
    """
    if not target:
        return None
    return target if target.startswith(_SOURCES) else "code:" + target


def build():
    chunks = load_chunks(str(ROOT / "evals/corpus/chunks.jsonl"))
    idx = build_entity_index(chunks, structure=build_structure(chunks))

    # Every ref gets a node, including edgeless ones: any chunk can be cited,
    # and a citation with no node to light is indistinguishable from a bug.
    ids = sorted({path_of(c.ref) for c in chunks})
    pos = {r: i for i, r in enumerate(ids)}

    seen, edges = set(), []
    for c in chunks:
        r = c.ref
        for k in KINDS:
            try:
                es = idx.edges(r, k)
            except Exception:
                continue
            for e in es:
                a = path_of(r)
                b = as_node(path_of(getattr(e, "target", "") or ""))
                if not b or a == b or a not in pos or b not in pos:
                    continue
                key = (min(a, b), max(a, b))
                if key in seen:
                    continue
                seen.add(key)
                edges.append((pos[a], pos[b], k))

    xyz = layout(len(ids), edges, ids)
    kinds = [r.split(":", 1)[0] for r in ids]

    out = {
        "repo": "simonw/llm",
        "commit": "94769b8",
        "note": ("Real evidence graph of the indexed corpus. Edges are stated by "
                 "indexed text, never inferred. Co-occurrence edges are excluded."),
        "kinds": sorted(set(kinds)),
        "ids": ids,
        "node_kind": [sorted(set(kinds)).index(k) for k in kinds],
        # quantised to int16: 3 decimal places of a unit cube is far past what
        # a screen can show, and it halves the payload
        "pos": [int(round(v * 1000)) for p in xyz for v in p],
        "edges": [v for (a, b, _k) in edges for v in (a, b)],
    }
    dst = ROOT / "web/public/graph.json"
    dst.write_text(json.dumps(out, separators=(",", ":")))
    print(f"nodes={len(ids)} edges={len(edges)} bytes={dst.stat().st_size}")
    from collections import Counter
    print("by kind:", dict(Counter(kinds)))
    print("edges by kind:", dict(Counter(k for _a, _b, k in edges)))


def layout(n, edges, ids, iters=180, sample=24):
    """Force-directed layout with sampled repulsion.

    Full O(n^2) repulsion on 3,000 nodes in pure Python is minutes; repelling
    each node against `sample` random others per iteration is the standard
    cheap approximation and is visually indistinguishable here. Seeded, so the
    published graph is reproducible.
    """
    rnd = random.Random(SEED)
    # seed by kind so the four evidence types start apart and the edges,
    # not the initial jitter, decide the final shape
    ks = sorted({r.split(":", 1)[0] for r in ids})
    p = []
    for r in ids:
        a = ks.index(r.split(":", 1)[0]) / max(1, len(ks)) * math.tau
        p.append([math.cos(a) * 0.6 + rnd.uniform(-.35, .35),
                  rnd.uniform(-.5, .5),
                  math.sin(a) * 0.6 + rnd.uniform(-.35, .35)])

    deg = [1] * n
    for a, b, _ in edges:
        deg[a] += 1
        deg[b] += 1

    for it in range(iters):
        t = 1.0 - it / iters
        disp = [[0.0, 0.0, 0.0] for _ in range(n)]
        for i in range(n):
            for _ in range(sample):
                j = rnd.randrange(n)
                if j == i:
                    continue
                dx = p[i][0]-p[j][0]; dy = p[i][1]-p[j][1]; dz = p[i][2]-p[j][2]
                d2 = dx*dx + dy*dy + dz*dz + 1e-4
                f = 0.0016 / d2
                disp[i][0] += dx*f; disp[i][1] += dy*f; disp[i][2] += dz*f
        for a, b, _ in edges:
            dx = p[a][0]-p[b][0]; dy = p[a][1]-p[b][1]; dz = p[a][2]-p[b][2]
            d = math.sqrt(dx*dx + dy*dy + dz*dz) + 1e-6
            f = d * 0.010
            ux, uy, uz = dx/d*f, dy/d*f, dz/d*f
            disp[a][0] -= ux; disp[a][1] -= uy; disp[a][2] -= uz
            disp[b][0] += ux; disp[b][1] += uy; disp[b][2] += uz
        for i in range(n):
            dx, dy, dz = disp[i]
            m = math.sqrt(dx*dx + dy*dy + dz*dz) + 1e-9
            cap = 0.05 * t
            s = min(m, cap) / m
            p[i][0] += dx*s; p[i][1] += dy*s; p[i][2] += dz*s

    # normalise into a unit-ish ball so the camera framing is fixed
    cx = sum(q[0] for q in p)/n; cy = sum(q[1] for q in p)/n; cz = sum(q[2] for q in p)/n
    p = [[q[0]-cx, q[1]-cy, q[2]-cz] for q in p]
    r = max(math.sqrt(q[0]**2+q[1]**2+q[2]**2) for q in p) or 1.0
    return [[q[0]/r, q[1]/r, q[2]/r] for q in p]


if __name__ == "__main__":
    build()
