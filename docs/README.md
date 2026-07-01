# Documentation

Organized on the [Diátaxis](https://diataxis.fr/) model — four kinds of docs
for four different needs. Find what you need by *what you're trying to do*,
not by guessing a filename.

| I want to… | I need | Go to |
|---|---|---|
| **learn by doing** | a Tutorial | [Tutorials](#tutorials) |
| **accomplish a specific task** | a How-to guide | [How-to guides](#how-to-guides) |
| **look up exact details** | Reference | [Reference](#reference) |
| **understand why** | Explanation | [Explanation](#explanation) |

New here? Start with the [README quickstart](../README.md), then
[why this is not a market](explanation/why-not-a-market.md), then the spec.

---

## Tutorials
*Learning-oriented — take me by the hand through my first success.*

- **[Your first duel](tutorials/your-first-duel.md)** — score two bots against
  each other on the shipped cabin question, then run one yourself. ~10 minutes,
  works offline.

## How-to guides
*Task-oriented — how do I accomplish X (assumes you know the basics)?*

- **[Run a bot](how-to/run-a-bot.md)** — answer bounty requests with
  `rb answer`: echo, `claude -p`, or any OpenAI-compatible endpoint.
- **[Score responses](how-to/score-responses.md)** — produce the Brier /
  log / pinball table and read it honestly.
- **[Redact a question](how-to/redact-a-question.md)** — de-identify a
  decision on your own device before it travels.
- Working *in* this repo: **[AGENTS.md](../AGENTS.md)**.

## Reference
*Information-oriented — tell me exactly, precisely, completely.*

- **[The Protocol, v0.1](spec/PROTOCOL.md)** — **the single source of truth**:
  invariants I1–I6, wire formats, scoring formulas, privacy tiers, transport,
  bot conduct. Everything else in this repo defers to it.
- **[The cabin example](../examples/cabin/)** — the spec's worked example as
  real wire files; the conformance anchor for every implementation.
- **[The canonical bot directory](../directory.json)** — a directory is just
  a file (§3.4); this is the one this repository hosts.

## Explanation
*Understanding-oriented — help me understand the ideas and the why.*

- **[Vision](../VISION.md)** — the one idea, and the honest scorecard of what
  exists versus what's reserved.
- **[Why this is not a betting market](explanation/why-not-a-market.md)** —
  the six invariants in prose; why you can never win money here.
- **[Decision records](adr/)** — bounty-not-market, files-before-HTTP,
  stdlib-only tools, payments-reserved.
