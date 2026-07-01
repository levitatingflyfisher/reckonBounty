# Architecture Decision Records

Why the load-bearing choices went the way they did. Format: Context →
Decision → Consequences (buys / costs / forecloses) → Alternatives considered.
A decision changes by *superseding* its ADR with a new one, not by editing
history. Where an ADR and [the spec](../spec/PROTOCOL.md) disagree, the spec
wins.

| # | Decision |
|---|---|
| [0001](0001-bounty-not-market.md) | A bounty, not a market — the asker is the oracle, so nobody can ever win money |
| [0002](0002-files-before-http.md) | Files before HTTP — v0 transport is `.json` files; HTTPS is spec'd, optional |
| [0003](0003-stdlib-only-tools.md) | Reference tools are stdlib-only Python — zero runtime deps, pytest for dev |
| [0004](0004-payments-reserved-x402.md) | Payments reserved — `rail` shape settled now; x402 + no-admin-keys contract are future rails |
