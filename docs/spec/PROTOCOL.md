# The reckonBounty Protocol — v0.1 (draft)

> **Put in your two cents. Get theirs.**
>
> An open, non-custodial protocol for buying probabilistic advice on personal
> decisions. An asker publishes a de-identified decision question with a
> (possibly zero) bounty. Independent bots answer with calibrated forecasts and
> rationales. The asker's client keeps longitudinal score of every advisor —
> human or bot. Reputation, not access, is the moat.
>
> **Status: v0.1 draft.** No payments. No custody. Transport is files. This
> document is a spec you can kick; every format below is implemented by the
> reference tools in this repository and by Reckon's bounty interface.

## 1. Why a bounty and not a market

Personal questions cannot be two-sided markets: the asker is the oracle, so
anyone betting against the asker must trust the asker's self-report. Every
real-money market on self-resolved questions is broken at the root. A bounty
is not: the asker pays for a *service* (advice), never stakes on an *outcome*,
and can never win money.

These are the invariants. Conforming implementations MUST preserve all six.

- **I1 — No market.** There are no positions and no counterparties. No
  participant other than the asker ever pays in. No participant can receive
  more than the asker chose to pay for the service.
- **I2 — The asker funds everything.** Because the pot is 100% asker-funded,
  a dishonest resolution can only misallocate the asker's own money. Nobody
  can be extracted from.
- **I3 — No custody.** The protocol defines no custodian and no operator who
  holds funds. When payments exist (future versions), they flow directly from
  asker to bot, or through an autonomous contract with no administrative keys.
- **I4 — The asker is the oracle.** Resolution is self-reported. Scoring
  therefore exists for *reputation*, never for wagering.
- **I5 — Privacy is a first-class field.** Every request declares a privacy
  tier; every bot declares which tiers it serves.
- **I6 — Local-first ledger.** Track records are computed client-side from
  stored request/response/resolution triples. No central server is required
  for the protocol to function correctly.

## 2. Terms

- **Asker** — the person (via a client such as Reckon) with a decision.
- **Bot** — any answering agent: an LLM pipeline, a human, a committee. The
  protocol does not care, only the track record does.
- **Client** — software acting for the asker: builds requests, collects
  responses, records resolutions, computes scores.
- **Directory** — a plain file listing bots. Anyone can host one.

## 3. Wire format

All messages are UTF-8 JSON objects with two mandatory envelope fields:
`"reckonbounty"` (spec version string, here `"0.1"`) and `"kind"`
(`request` | `response` | `resolution` | `directory`). Implementations MUST
ignore unknown fields (forward compatibility) and MUST reject messages whose
mandatory fields are missing or malformed.

### 3.1 BountyRequest

```json
{
  "reckonbounty": "0.1",
  "kind": "request",
  "id": "5f0a2b1c-9d4e-4f6a-8b3c-7e1d2a5b4c6d",
  "created_at": "2026-07-11T06:30:00Z",
  "reply_by": null,
  "privacy": { "tier": "redacted", "redaction": "local-llm" },
  "question": {
    "type": "binary",
    "title": "Buy the vacation cabin?",
    "background": "Family of five, single income, stable job. Cabin is 2.5h drive, asking price ~= 1.1x our annual gross income, 20% down available without touching retirement. Intended use: ~20 weekends/yr. Local rental comps would cover ~60% of carrying costs if rented 8 weeks/yr. Question: will we, one year after purchase, judge the purchase to have been the right call?",
    "resolution": {
      "criteria": "Asker records a yes/no judgment 12 months after purchase (or records 'did not buy').",
      "horizon": "2027-08-01",
      "resolver": "asker"
    }
  },
  "bounty": { "rail": "none", "terms": "per-answer", "amount": "0", "currency": "none" },
  "client": { "app": "reckon", "version": "0.9.0" }
}
```

Field rules:

- `question.type` is `binary` | `multi` | `quantity`.
  - `multi` adds `"options": ["...", "..."]` (2–16 entries, all distinct —
    a response's `distribution` is keyed by option text, so duplicate
    options cannot be told apart when scoring).
  - `quantity` adds `"unit": "..."`.
- `reply_by` MAY be null (open call). Responses after `reply_by` MUST be
  excluded from any scored comparison for that request.
- `bounty.rail` MUST be `"none"` in v0.x. The field exists so that the shape
  of a paid request is settled now: a future `"x402"` rail pays per-answer at
  the HTTP layer, and a future `"contract"` rail escrows a scored payout in an
  autonomous contract. Conforming v0 implementations MUST politely refuse
  requests with any other rail value.
- `privacy.tier` is defined in §5.

### 3.2 BountyResponse

```json
{
  "reckonbounty": "0.1",
  "kind": "response",
  "request_id": "5f0a2b1c-9d4e-4f6a-8b3c-7e1d2a5b4c6d",
  "id": "a1b2c3d4-1111-2222-3333-444455556666",
  "created_at": "2026-07-11T07:02:00Z",
  "bot": {
    "name": "hustlerBot80000",
    "operator": "anonymous",
    "model": "llamafile/Qwen2.5-7B-Instruct Q4_K_M, single pass + self-critique",
    "directory_url": null
  },
  "forecast": {
    "p": 0.35,
    "rationale": "Base rates for discretionary second-home satisfaction at >1x income are poor; usage projections of 20 weekends/yr typically realize at 8-12; the 60% rental offset assumes 8 rented weeks that compete with the 20 family weekends...",
    "base_rates": ["Second-home regret surveys", "Planned-vs-actual usage studies"],
    "key_uncertainties": ["Drive tolerance with three kids", "Rate environment at purchase"],
    "clarifying_questions": ["Is the 20-weekend estimate the parents' or the whole family's?"]
  }
}
```

Field rules by question type: `binary` → `"p"` in [0,1]; `multi` →
`"distribution"` over exactly the request's options, summing to 1 ± 0.001;
`quantity` → `"quantiles"` with at least `p10`, `p50`, `p90`
(non-decreasing).

One response per bot per request: if a bot sends several with the same
`bot.name`, the latest `created_at` before `reply_by` wins. Ties on
`created_at` break by the lexicographically larger response `id`, so that
two clients given the same responses in any order select the same winner
(see §4's determinism requirement).

### 3.3 Resolution

Recorded client-side; MAY be shared back to bots as a courtesy (it is how
public bots build portable track records).

```json
{
  "reckonbounty": "0.1",
  "kind": "resolution",
  "request_id": "5f0a2b1c-9d4e-4f6a-8b3c-7e1d2a5b4c6d",
  "resolved_at": "2027-08-02T14:00:00Z",
  "outcome": false,
  "note": "Did not buy; used the down payment to clear the car loan instead. No regret."
}
```

`outcome` is `true|false` (binary), an option string (multi), or a number
(quantity). A resolution of `"void"` cancels scoring for that request.

### 3.4 Directory

A directory is just a file. The canonical one lives in this repository;
anyone may host their own.

```json
{
  "reckonbounty": "0.1",
  "kind": "directory",
  "bots": [
    {
      "name": "rb-reference",
      "endpoint": null,
      "transport": "file",
      "tiers": ["public", "redacted"],
      "pricing": null,
      "operator": "reckonBounty project",
      "model": "configurable (claude -p / any OpenAI-compatible endpoint)",
      "notes": "Reference implementation; run it yourself: rb answer"
    }
  ]
}
```

## 4. Scoring

Scoring is client-side and normative only in its formulas, so that two
clients given the same triples produce identical numbers.

- **Binary:** Brier `(p - o)^2` with `o ∈ {0,1}`; log score `ln(p_o)` where
  `p_o` is the probability assigned to the realized outcome.
- **Multi:** multiclass Brier `Σ_i (p_i - o_i)^2`; log score `ln(p_winner)`.
- **Quantity:** mean pinball loss over the provided quantiles
  `L_τ(y, q) = (τ - 1[y < q]) · (y - q)` for `τ ∈ {0.1, 0.5, 0.9}`.

**Log-score clamp (normative).** Before taking the logarithm, the probability
(`p_o` or `p_winner`) is clamped to `[1e-9, 1 - 1e-9]`. A bot that says an
absolute 0 or 1 and misses takes a huge but *finite* penalty
(`ln(1e-9) ≈ −20.7`); without the clamp, one client computing `ln(0) = −∞`
and another refusing to would break the identical-numbers requirement above
at exactly the inputs overconfident bots produce.

A **track record** is the per-bot (and per-asker!) mean of each score, grouped
by question category, with `n`. Clients SHOULD refuse to *display* comparative
claims below a minimum `n` and SHOULD show uncertainty intervals with any
comparison — small-sample verdicts are noise presented as judgment.

## 5. Privacy tiers

| Tier | Meaning | Status |
|---|---|---|
| `public` | Question may be shared anywhere, as-is. | v0 |
| `redacted` | Question was de-identified client-side (local model or manual edit) before leaving the device. Bots MUST NOT attempt re-identification. | v0 |
| `attested` | Request may only be sent to endpoints presenting a valid confidential-compute attestation. Attestation format reserved for v1. | reserved |
| `fhe` | Fully homomorphic evaluation. No conforming implementation exists; plaintext-scale LLM inference under FHE remains 3–4 orders of magnitude away. The tier is reserved so the enum never breaks. | reserved |

## 6. Transport

- **v0 — files.** Requests and responses move as `.json` files or pasted
  text: share sheet, USB, chat, carrier pigeon. Deliberate: it works offline,
  it is trivially auditable, and it forces the formats to be complete.
- **v0.1 — HTTPS (spec'd, optional).** `POST <endpoint>` with a BountyRequest
  body returns a BountyResponse (or `202` + a retrieval URL for slow bots).
- **Payments — reserved.** When `rail: "x402"` activates (future), payment is
  per-answer at the HTTP layer via the 402 flow, asker→bot directly, keeping
  I3 intact.

## 7. Bot conduct (normative)

A conforming bot: discloses its model/method in `bot.model`; never attempts
re-identification of a `redacted` question; forecasts with calibrated honesty
(no persuasion, no upselling in `rationale`); answers the question that was
asked or declines.

## 8. Non-goals

Custody. Matching engines. Order books. Two-sided wagering. Accounts.
Identity. Any component that requires trusting an operator — including us.

## 9. Worked example

The cabin question above, two bots, resolution `false`:

| Bot | p(yes) | Brier | Log score |
|---|---|---|---|
| hustlerBot80000 | 0.35 | (0.35−0)² = 0.1225 | ln(0.65) = −0.431 |
| cautiousBot | 0.20 | 0.0400 | ln(0.80) = −0.223 |
| the asker (recorded in Reckon) | 0.60 | 0.3600 | ln(0.40) = −0.916 |

cautiousBot earns the reputation. The asker's client quietly adjusts its
ensemble weights for housing-category questions — and says nothing unless
asked, because n=1 is noise.
