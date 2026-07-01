# Vision

> The north star for reckonBounty. If you (person or agent) are about to
> change something load-bearing, read this first — it says what must stay
> true and why. The wire-level law is [docs/spec/PROTOCOL.md](docs/spec/PROTOCOL.md);
> the why of each decision is in [docs/adr/](docs/adr/).

## The one idea

**Pay pennies for calibrated advice on YOUR decisions — from bots that keep
score, on a protocol that can't hold your money.**

Forecasting talent is real, measurable, and cheap to rent — but every venue
for it assumes questions with public resolutions and platforms that hold the
pot. Your actual decisions (buy the cabin? take the job? switch schools?) are
private, self-resolved, and worth more to you than any election. reckonBounty
is the missing wire format: a de-identified question goes out, calibrated
forecasts with rationales come back, and your own client keeps the
longitudinal book on who's actually good. Advisors compete on track record —
**reputation, not access, is the moat** — and the protocol is structurally
incapable of custody, so there is no operator to trust, pay, or fear.

## What must stay true

The six invariants of the spec (§1), forever: **no market** (I1), **the asker
funds everything** (I2), **no custody** (I3), **the asker is the oracle — so
scoring is reputation, never wagering** (I4), **privacy is a first-class
field** (I5), **local-first ledger** (I6). A change that bends any of these
is not a feature; it is a different project. Two derived commitments:

- **You can never win money here; you can only buy advice.** Every surface —
  spec, site, tools — must keep this sentence true and say it plainly.
- **The spec wins.** The formats and formulas are the product; tools, docs,
  and clients defer to PROTOCOL.md, and two conforming clients must produce
  identical scores from identical triples.

## Honest scorecard — built vs. reserved

A vision has to tell the truth about where the light reaches. This repo's
code and comments were written by an AI assistant; treat them as an accurate
record of what currently exists, offered with gratitude and a grain of salt —
verify before you rely. As of v0.1:

| Area | Status | Honest state |
|---|---|---|
| Protocol spec (formats, invariants, scoring) | ✅ | v0.1 draft complete, with a worked example ([cabin](examples/cabin/)) that doubles as the conformance fixture. Draft means draft: open for kicking. |
| File transport | ✅ | The v0 transport. Deliberate, not a stopgap ([ADR-0002](docs/adr/0002-files-before-http.md)). |
| Reference tools (`rb`) | 🟡 | stdlib-only ask/answer/resolve/score/validate with echo / claude-cli / OpenAI-compatible backends, TDD'd against the spec. |
| HTTP transport | 🟡 | Spec'd (§6), not implemented. No bot endpoint exists yet, including ours. |
| Reference bot quality | 🟡 | Single-pass prompt + strict-JSON validation + one retry. No ensembling, no self-critique loop, no calibration tuning — it demonstrates the format, it does not chase the leaderboard. |
| Reckon integration | 🟡 | The exchange contract is defined (import ignores unknown fields; `bot.name` → forecaster of kind bot; same §4 formulas). Reckon's bounty interface ships in the Reckon repo. |
| Track-record portability | 🟡 | Resolution-sharing is defined (§3.3) so bots can accumulate portable records; signed/verifiable track records are an open problem, not a format. |
| Payments | ❌ | **Reserved, on purpose.** `bounty.rail` MUST be `"none"` in v0.x; x402 and the no-admin-keys contract rail are named so the shape is settled ([ADR-0004](docs/adr/0004-payments-reserved-x402.md)). No wallet code exists. |
| `attested` / `fhe` privacy tiers | ❌ | Reserved enum values with honest status labels. No attestation format, no FHE anything. |
| Bot directory ecosystem | ❌ | [directory.json](directory.json) lists exactly one bot: the reference implementation. An ecosystem of one is a spec, not a network — that's what v0.1 *is*. |

## Horizons (problems, not dates)

- **The payment problem** — per-answer x402 needs real wallets and real
  demand; the escrow rail needs a target chain and an audit. Neither blocks
  usefulness at bounty = 0.
- **The directory problem** — who lists bots, who vouches, and how
  reputations travel: portable signed track records vs. client-local ledgers.
- **The privacy ceiling** — an `attested` tier worth standardizing; `fhe`
  stays a named aspiration until the overhead collapses.
- **The transport problem** — HTTPS endpoints, slow-bot retrieval, and
  discovery, without ever making the file path second-class.
