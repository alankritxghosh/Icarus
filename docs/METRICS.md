# Icarus — Metrics

The numbers that tell us we're winning. Grouped by what they protect: **honesty**
first (the moat), then **retrieval quality**, then **experience**, then **trust &
business**. If a metric ever fights the honesty group, honesty wins.

---

## North-star metric

**Trusted, cited answers per engineer per week.**

Not "answers." *Trusted, cited* answers — ones the engineer believed because they
could see the receipt. This single number captures the whole product: it only
goes up if Icarus is correct, grounded, fast enough to bother using, and honest
enough to be believed the second time.

## 1. Honesty (the non-negotiables — must hold at 100%)

| Metric | Target | Notes |
|--------|--------|-------|
| **Groundedness** — every spoken claim traces to a citation | 100% | A single ungrounded claim is a product failure, not a bug. |
| **Bluff rate** — answers given when evidence didn't support one | 0% | The catastrophic failure. Never trade away. |
| **Abstention recall** — correctly says "I don't know" when unrecorded | 100% | The behavior that earns trust on the second hard question. |

These come from the [evaluation harness](EVALUATION.md). They are pass/fail gates,
not dials.

## 2. Retrieval quality (the dials we turn up over time)

| Metric | Direction | Notes |
|--------|-----------|-------|
| **Retrieval recall@k** | ↑ | Is the right evidence in the top *k* pieces? |
| **Citation correctness** | ↑ | Cites the actual source, not a lookalike. |
| **Answer correctness** (answerable Qs) | ↑ | Right answer, not just a grounded one. |
| **Under-find rate** | ↓ | Documented answers wrongly returned as "I don't know." |

These improve continuously and are never improved by weakening Group 1.

## 3. Experience (load-bearing once Phase 3 exists)

| Metric | Target (starting guess) | Notes |
|--------|-------------------------|-------|
| **Hotkey → spoken answer, p50** | feels immediate (~ a couple seconds) | The magic dies if it's slow. |
| **Hotkey → spoken answer, p95** | bounded, no long tails | Tail latency breaks trust in the loop. |
| **Speech-to-text accuracy** | high | Errors here poison everything downstream. |
| **Time-to-first-word** | low | Start speaking the answer before it's fully formed where safe. |

Latency budget is split across speech-in → retrieval → synthesis → speech-out;
each leg gets a sub-budget once Phase 3 starts. This is a primary reason heavy
inference runs in the cloud.

## 4. Trust & business

| Metric | Notes |
|--------|-------|
| **Data-never-leaves-boundary** | Demonstrable, not just claimed — the core sales guarantee. |
| **Onboarding time for a new company** | How fast a new private brain learns a codebase. |
| **New-hire ramp** | Are new engineers talking to the codebase instead of interrupting seniors? |
| **"Write it down" rate** | Is the org recording more decisions because Icarus makes that pay off? |
| **Repeat-trust** | Does an engineer come back after the *second* "I don't know"? |

---

## How these map to the build

- **Phase 1** reports Groups 1 and 2 (honesty + retrieval) from the harness.
- **Phase 3** adds Group 3 (experience / latency).
- **Phase 4** adds Group 4 (trust & business).

A metric we can't yet measure is listed but explicitly marked "starts in Phase X"
— we don't pretend to track what doesn't exist yet. That honesty about our own
numbers is the same discipline we sell to customers.
