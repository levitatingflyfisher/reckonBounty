# How to score responses

Once a request has a resolution, every response to it can be scored. Scoring
is client-side and **normative only in its formulas** (spec §4): two clients
given the same triples must produce identical numbers — that's what makes a
track record portable and arguing about it pointless.

## The command

```sh
rb score <request.json> <resolution.json> <response.json...>
```

The resolution comes from `rb resolve <request.json> --outcome …`, which
binds the request's exact id so the triple lines up (outcome word by
question type: `yes/no/true/false`, an option string, a number, or `void`).

Prints one row per bot: Brier and log score (binary/multi) or mean pinball
loss (quantity). Sanity check against the shipped example — this must
reproduce [the spec's §9 table](../spec/PROTOCOL.md) to 4 decimals:

```sh
rb score examples/cabin/request.json examples/cabin/resolution.json \
         examples/cabin/response-*.json
```

## What the numbers mean

| Question type | Scores | Reading |
|---|---|---|
| `binary` | Brier `(p − o)²`, log `ln(p_o)` | Lower Brier is better; log closer to 0 is better. `p_o` is the probability given to what actually happened. |
| `multi` | multiclass Brier `Σ(p_i − o_i)²`, log `ln(p_winner)` | Same reading, over the whole distribution. |
| `quantity` | mean pinball loss over `p10/p50/p90` | Lower is better; punishes both bias and overconfident intervals. |

Brier rewards being *close*; log score savagely punishes confident wrongness
(a p = 0.99 miss costs ln(0.01) ≈ −4.6). Implementation note: the reference
tool clamps the log-score input to `[1e-9, 1 − 1e-9]`, so a bot that says an
absolute 0 or 1 and misses gets a huge—but finite—penalty.

## Edge rules (all from the spec)

- **Late responses** — `created_at` after the request's `reply_by` → excluded
  from any scored comparison for that request.
- **Duplicate bot names** — one response per bot per request; the latest
  `created_at` before `reply_by` wins (ties break by the lexicographically
  larger response `id`, never by file order).
- **Void resolutions** — `outcome: "void"` cancels scoring for that request
  entirely. Nothing is scored, nothing enters a track record.

## From scores to a track record — honestly

A track record is the per-bot (and per-asker!) mean of each score, grouped by
question category, with `n` attached (spec §4). Two display rules keep it
honest, and clients SHOULD enforce both:

- **Refuse comparative claims below a minimum n.** "cautiousBot beats
  hustlerBot" after one question is noise presented as judgment.
- **Show uncertainty intervals with any comparison.**

Note the "per-asker" — score yourself with the same formulas. The asker in
the cabin example ran a Brier of 0.36 against cautiousBot's 0.04; knowing
*who to defer to, and when* is the entire payoff of keeping score.
