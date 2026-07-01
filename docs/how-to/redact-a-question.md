# How to redact a question

Privacy is a first-class field (invariant I5): every request declares a tier,
and redaction — when you choose it — happens **on your device, before the
question travels**. No service ever sees the un-redacted text; there is no
service.

## Choose a tier (spec §5)

| Tier | Choose it when | Status |
|---|---|---|
| `public` | The question as-is could sit on a forum with your name off it. | v0 |
| `redacted` | The decision is real but identifying — de-identify first (this guide). | v0 |
| `attested` | You'd only send it to a bot running in attested confidential compute. | reserved |
| `fhe` | You'd only send it fully encrypted. Aspirational; the tier is reserved so the enum never breaks. | reserved |

Declare it in the request: `"privacy": { "tier": "redacted", "redaction": "manual" }`
(or `"local-llm"` if a local model did the rewrite).

## What redaction means here

The forecast only needs the *decision-relevant structure* — base-rate hooks,
constraints, magnitudes. It never needs your identity. The shipped
[cabin request](../../examples/cabin/request.json) is the worked example:

| Instead of… | It says… |
|---|---|
| a town / listing | "2.5h drive" |
| a price and a salary | "asking price ~= 1.1x our annual gross income" |
| names, employer | "family of five, single income, stable job" |
| account balances | "20% down available without touching retirement" |

**Ratios instead of amounts. Durations instead of places. Roles instead of
names.** The forecasting signal survives; the identification handles don't.

## Manual redaction checklist

Rewrite, then scan for what's left:

- [ ] Names (people, employers, schools, congregations), usernames, handles
- [ ] Places more specific than a region — swap for distances/drive times
- [ ] Exact money amounts — convert to ratios of income/net worth
- [ ] Exact dates that pin an event — prefer "12 months after purchase"
- [ ] Rare combinations (job title + city + family size can be unique alone)
- [ ] Re-read as a stranger: could you find yourself from this text?

A local LLM makes a decent first-pass rewriter — ask it to de-identify per
the table above, then **verify by hand**; you hold the redaction
responsibility, and you're the only one who can recognize handle number six.

## What the other side owes you

Bots MUST NOT attempt re-identification of a `redacted` question (spec §5
and §7). That's a conduct rule, not cryptography — which is exactly why the
tier table is honest that `attested` and `fhe` are *reserved*, not shipped.
Until they ship, redact as if the bot were curious, because you can't audit
that it isn't.
