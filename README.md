# Icarus — the engineering brain a company can buy

> Ask your codebase a question out loud, and get a straight, spoken answer —
> with the receipts on screen, and an honest "no one wrote this down" when the
> reason was never recorded.

Icarus is a privacy-first **engineering brain**. A company buys it, points it at
their code on GitHub, and every engineer can hold a hotkey and ask *why* a
decision was made, *what* something does, or *how* a part of the system works —
and get a colleague-style answer with the exact pull request, review comment, or
line it came from shown in a translucent overlay.

## The one rule (this is the whole product)

**Icarus only says what it can prove.** It answers from evidence it actually
retrieved from your code and its history — never from a model's memory. When the
answer was never written down, it says so, out loud. A brain that talks
beautifully but can't tell when it's wrong is a liability with a great voice. We
build the opposite.

## Version 1, in one breath

- **Source:** GitHub (code + pull requests + reviews).
- **Interface:** a macOS app — hold a hotkey, speak, hear the answer.
- **Proof:** a translucent on-screen overlay showing the citations.
- **Where it runs:** the app is the *face*; the heavy thinking runs in a cloud
  space rented **privately per company** — never trained on, deleted after each
  answer.

## Status

**Pre-build.** This repository currently holds the planning foundation only —
vision, architecture, build order, evaluation, and metrics. Building starts next.
The previous product (JARVIS Engineering Intelligence) is archived in git: tag
`jarvis-v0`, branch `archive/jarvis-v0`.

## Read next

| Doc | What it answers |
|-----|-----------------|
| [docs/VISION.md](docs/VISION.md) | What we're building and why it's trustworthy |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it's built — the face, the brain, and the cloud |
| [docs/BUILD_ORDER.md](docs/BUILD_ORDER.md) | What we build first, second, third |
| [docs/EVALUATION.md](docs/EVALUATION.md) | How we prove Icarus isn't bluffing |
| [docs/METRICS.md](docs/METRICS.md) | The numbers that tell us we're winning |
| [docs/WORKFLOWS.md](docs/WORKFLOWS.md) | How we work — one honest brick at a time |
