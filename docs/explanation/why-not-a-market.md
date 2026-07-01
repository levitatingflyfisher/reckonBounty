# Why this is not a betting market

**You can never win money here; you can only buy advice.** Everything else in
this document unpacks that sentence.

## The oracle problem

Prediction markets earn their reputation on questions with *external*
resolution — an election, a launch date, a printed statistic. Personal
decisions have none: only the family that bought (or didn't buy) the cabin
can say whether, a year on, it was the right call. Whoever resolves a
question is its **oracle**, and in a personal question the oracle is the
asker.

Put a market on that and you've built a machine for extraction: anyone
betting against the asker is betting against the referee. The asker can lie —
or just remember generously — and take the other side's money. Every
real-money market on self-resolved questions is broken at this root, which is
why serious markets ban them and gray ones rot. No amount of engineering
fixes it, because it isn't an engineering problem; it's who holds the truth.

## The bounty inversion

reckonBounty doesn't patch the oracle problem — it removes the thing the
oracle could corrupt. The asker pays (possibly zero, in v0 always zero) for a
*service*: calibrated forecasts with rationales. Not for being right, not as
a stake, and never with the possibility of getting more back.

The spec carves this into six invariants (§1). In prose:

- **I1 — No market.** No positions, no counterparties, no order book. Nobody
  other than the asker ever pays in, and nobody can receive more than the
  asker chose to pay for the service. There is no bet to win.
- **I2 — The asker funds everything.** Follow the incentive through a
  dishonest resolution: the pot is 100% the asker's own money, so lying about
  the outcome only misallocates *their* spend among advisors. Nobody can be
  extracted from — the attack pays nothing.
- **I3 — No custody.** No custodian, no operator holding funds, no platform
  balance. When payments exist (they don't in v0), they flow asker→bot
  directly, or through an autonomous contract with no administrative keys.
  There is no pot to freeze, skim, or subpoena.
- **I4 — The asker is the oracle — so scoring is reputation, never wagering.**
  Self-reported resolution is a *feature* once nothing rides on it but track
  record. A bot's incentive to be right is longitudinal: calibrated bots get
  weighted up in the asker's client; flattering ones quietly decay.
- **I5 — Privacy is a first-class field.** Every request declares a tier
  (`public`/`redacted`/`attested`/`fhe`); redaction happens on the asker's
  device. A market needs verifiable, therefore public, questions — a bounty
  can serve a question only the asker can resolve *because* it never asks
  anyone to bet on it.
- **I6 — Local-first ledger.** Track records are computed client-side from
  stored request/response/resolution triples. No central server, no accounts,
  no operator to trust — including us. (Non-goals, §8, says this outright.)

## "So is this gambling?"

No, and not as a technicality. Gambling requires staking something of value
on an uncertain outcome for a chance of gain. Here the only party who pays is
the asker; the payment buys a service at a chosen price; and *no* outcome can
return money to the asker. There is no chance of gain to anyone from the
outcome — bots are paid (in v0, reputationally) for answering, whichever way
the world goes. Remove the win and you've removed the wager.

## What the trade-off costs

Honesty requires naming what the market had that we gave up: **elicitation
pressure**. A trader with money at risk sharpens their probability; a bounty
bot has only its track record at risk. We accept slower, reputational
pressure — with `n` attached and small-sample verdicts refused — because the
alternative wasn't a sharper number, it was a broken game. The longer the
record runs, the smaller the gap gets; meanwhile the whole thing stays legal
to run, moral to share, and safe to point at your own family's decisions.

The decision in full: [ADR-0001 — a bounty, not a market](../adr/0001-bounty-not-market.md).
