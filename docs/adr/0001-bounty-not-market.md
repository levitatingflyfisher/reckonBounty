# ADR-0001: A bounty, not a market

- **Status:** Accepted
- **Date:** 2026-07-11 (founding decision, v0.1)

## Context

The obvious design for "get forecasts on my question" is a prediction market:
two-sided wagering, prices as probabilities, skin in the game. Markets have a
well-earned reputation for eliciting honest probabilities — *when the outcome
is externally verifiable*. Personal decisions are not. The asker is the only
party who can say how "will we judge the cabin purchase to have been the right
call?" resolved. Anyone betting *against* the asker must trust the asker's
self-report, so every real-money market on self-resolved questions is broken
at the root: the oracle holds a position.

There is also a regulatory and moral dimension. A market on personal outcomes
is gambling with extra steps; a household tool must be shareable in
communities where betting language alone is disqualifying.

## Decision

The protocol is a **bounty for a service**, never a market on an outcome.
This is carved into invariants I1–I4 of [the spec](../spec/PROTOCOL.md):
no positions or counterparties (I1); the asker funds everything (I2); no
custody (I3); the asker is the oracle, so scoring exists for *reputation*,
never for wagering (I4). No participant other than the asker ever pays in,
and nobody — including the asker — can ever *win* money.

## Consequences

- **Buys:** the oracle problem dissolves — a dishonest resolution can only
  misallocate the asker's own money, so there is nothing to extract and no
  incentive to corrupt the resolution. "Is this gambling?" has a clean answer:
  no; you can only buy advice. No order book, no matching engine, no operator.
- **Costs:** weaker elicitation pressure than a market. Honesty is enforced by
  the longitudinal track record (I6), not by stakes — bots that flatter or
  hedge get quietly down-weighted over time, which is slower than a price.
- **Forecloses:** any feature where a responder profits from an outcome:
  staking, side bets, "confidence deposits". Those reintroduce the oracle
  problem and are off-thesis permanently, not just for v0.

## Alternatives considered

- **Play-money market** — keeps market mechanics without gambling, but still
  needs an oracle everyone trusts, still needs accounts and a ledger operator,
  and play money makes the elicitation-pressure argument evaporate anyway.
- **Peer prediction / proper scoring against other responders** (Bayesian
  truth serum et al.) — clever, but rewards herding toward the responder pool
  rather than the truth of *this household's* outcome, and needs a large
  simultaneous pool that a personal question will never have.
- **Plain Q&A with no scoring** — that's a forum. Without a track record the
  asker cannot tell calibrated advisors from confident ones, which is the
  entire point.
