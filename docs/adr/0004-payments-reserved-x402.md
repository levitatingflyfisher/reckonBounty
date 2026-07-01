# ADR-0004: Payments are reserved (x402 rail spec'd, not built)

- **Status:** Accepted
- **Date:** 2026-07-11 (founding decision, v0.1)

## Context

"Pay pennies for calibrated advice" eventually needs actual pennies. But
every premature payment design either adds custody (an operator holding a
pot — violating I3 and making someone a money transmitter) or welds the
protocol to one payment fashion. Meanwhile, leaving money out of the *shape*
of the messages would mean a breaking format change the day payments arrive.
The bounty works at amount 0 today: the scarce thing bots compete for in v0
is track record, not cash.

## Decision

**No payments in v0.x — but the shape is settled now.** Every request carries
a `bounty` object (`rail`, `terms`, `amount`, `currency`); `rail` MUST be
`"none"` in v0.x, and conforming implementations MUST politely refuse any
other value (spec §3.1). Two future rails are named and reserved:

- **`x402`** — per-answer payment at the HTTP layer via the HTTP 402 flow,
  asker→bot directly. Pairs with the optional HTTPS transport (§6).
- **`contract`** — a scored payout escrowed in an autonomous contract with
  **no administrative keys**, for pay-for-accuracy terms.

Both keep I3 intact: funds flow asker→bot directly or through code nobody
operates. The protocol never defines a custodian.

## Consequences

- **Buys:** v0 is unambiguously not gambling and not money transmission —
  shareable anywhere; the wire format won't break when money arrives; the
  refuse-unknown-rails rule means old clients fail safe, not silently unpaid.
- **Costs:** no economic pull for bot operators yet; the reserved fields are
  dead weight every implementation must carry and validate.
- **Forecloses:** any rail requiring an operator with keys over user funds —
  a hosted escrow, a platform balance, a tipping pool we administer. Those
  need I3 repealed, which is a different project.

## Alternatives considered

- **Build x402 now** — real wallets and real demand don't exist yet for this
  use; shipping payment code before a single external bot exists is risk
  without users. (Roadmap: "the payment problem" stays open, undated.)
- **Omit the `bounty` field until needed** — cheapest today, but retrofitting
  money into a settled ecosystem forces a version break exactly when
  compatibility starts to matter.
- **Lightning / plain invoices in v0** — direct and custody-free, but wires
  payment semantics into a files-only transport where nothing can enforce
  them; per-answer rails belong on the HTTP layer they'll actually ride.
