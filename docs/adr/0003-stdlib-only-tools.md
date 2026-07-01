# ADR-0003: Reference tools are stdlib-only Python

- **Status:** Accepted
- **Date:** 2026-07-11 (founding decision, v0.1)

## Context

The repo ships reference tools (`rb ask/answer/resolve/score/validate`) whose job is
to make the spec *kickable*: prove the formats are implementable, give bot
operators a working start, and pin the scoring formulas to executable truth.
Reference code is read far more than it is run — by implementers porting the
protocol to Dart (Reckon), JS, or anything else. Every dependency in it is a
thing a reader must also understand, a supply chain the household must also
trust, and an install step that can fail.

## Decision

The `reckonbounty` package runs on **Python ≥ 3.11 with zero runtime
dependencies** — `argparse`, `json`, `urllib`, `uuid`, `datetime`, `math` and
friends. `pytest` is the only dev dependency. Concretely:

- Validation is hand-rolled per spec §3 — no `jsonschema`. Unknown fields
  pass (forward compatibility); missing or malformed mandatory fields fail
  with a precise message.
- The OpenAI-compatible backend speaks `/v1/chat/completions` over `urllib`;
  the `claude-cli` backend shells out to `claude -p`. No SDK either way.
- Scoring is a handful of arithmetic functions mirroring spec §4 exactly,
  TDD'd against the [cabin example](../../examples/cabin/).

## Consequences

- **Buys:** `pip install -e tools/` (or copying the files) always works,
  offline, forever-ish; the whole tool is auditable in one sitting; the
  scoring code reads like the spec it implements, so ports can be checked
  line-by-line.
- **Costs:** we re-implement small conveniences (schema checks, an HTTP POST,
  table printing) and forgo nicer CLI/UX libraries. Accepted — the tools are
  a reference, not a product.
- **Forecloses:** convenience deps creeping in via "just this one". A PR that
  adds a runtime dependency needs a new ADR superseding this one.

## Alternatives considered

- **`requests` + `jsonschema` + `click`** — friendlier code, but three supply
  chains for a tool whose value is that a stranger can trust it by reading it.
- **A published PyPI package with pins** — publication can come later; pinning
  doesn't remove the reading burden.
- **Go/Rust single binary** — great distribution, but the primary audience
  tonight is people who will port the logic, and Python is the workshop's
  lingua franca for reference implementations.
