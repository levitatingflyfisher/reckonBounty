# reckonBounty

> **Put in your two cents. Get theirs.**

An open, non-custodial protocol for buying probabilistic advice on personal
decisions. You publish a de-identified decision question with a (possibly
zero) bounty; independent bots answer with calibrated forecasts and
rationales; you decide; time scores everyone. Your client keeps the
longitudinal track record of every advisor — human or bot. **Reputation, not
access, is the moat.**

**Status: protocol v0.1 draft — file transport, no payments, spec open for
kicking.** Every format in [the spec](docs/spec/PROTOCOL.md) is implemented
by the reference tools here and by [Reckon](https://github.com/levitatingflyfisher/Reckon)'s
bounty interface.

## Why this is not a betting market

Personal questions can't be markets: **the asker is the oracle** (only you
can say whether buying the cabin turned out to be the right call), so anyone
betting against you must trust your self-report. reckonBounty inverts it —
the asker pays for a *service* (advice), never stakes on an *outcome*, and
**can never win money**. Nobody holds funds, nobody can be extracted from,
and the whole ledger lives on your device. The six invariants that make this
true are the heart of the spec; the prose version is
[why-not-a-market](docs/explanation/why-not-a-market.md).

## Quickstart (5 minutes, offline)

Python ≥ 3.11, zero runtime dependencies:

```sh
pip install -e tools/
```

**Ask → answer → resolve → score**, the whole protocol:

```sh
# 1. Ask — build a validated, de-identified BountyRequest
#    (flag-driven; `rb ask --help` lists every field):
rb ask --title "Buy the vacation cabin?" > request.json

# 2. Answer — the reference bot. `echo` is the deterministic offline
#    backend; swap in `claude-cli` or `openai:<base_url>` (llamafile,
#    Ollama) when you want a real model:
rb answer request.json --backend echo > response.json

# 3. Decide. Live it out. Record what actually happened (here: didn't
#    buy) — the resolution binds to the request's id so the triple
#    lines up — then time scores everyone:
rb resolve request.json --outcome no > resolution.json
rb score request.json resolution.json response.json
```

Or settle the shipped duel right now — two bots, one cabin, one resolution:

```sh
rb validate examples/cabin/*.json
rb score examples/cabin/request.json examples/cabin/resolution.json \
         examples/cabin/response-*.json
```

| Bot | p(yes) | Brier | Log score |
|---|---|---|---|
| hustlerBot80000 | 0.35 | 0.1225 | −0.431 |
| cautiousBot | 0.20 | 0.0400 | −0.223 |

cautiousBot earns the reputation. The hand-held version of this walk is
[your first duel](docs/tutorials/your-first-duel.md).

## The protocol in thirty seconds

Four message kinds, all self-contained UTF-8 JSON files: **request**
(question + privacy tier + bounty terms), **response** (forecast + rationale
+ disclosed method), **resolution** (self-reported outcome), **directory**
(a list of bots — just a file; [the canonical one](directory.json) lives
here). Scoring formulas (Brier / log / pinball) are normative so any two
clients agree to the digit. Transport is files in v0; HTTPS is spec'd and
optional; payments are **reserved** (`bounty.rail: "none"` — the x402
per-answer rail and a no-admin-keys escrow contract are named for later, not
built). The law lives in **[docs/spec/PROTOCOL.md](docs/spec/PROTOCOL.md)**;
where anything else disagrees with it, the spec wins.

## Reckon — the first client

reckonBounty is the open protocol; **[Reckon](https://github.com/levitatingflyfisher/Reckon)**
— the local-first decision journal — is the first client: it builds requests,
imports responses as scored forecasters, and keeps the track record on your
device. Any other client that speaks the formats is equally welcome; that's
the point of a spec.

## Docs

Reading order: this file → [VISION.md](VISION.md) (the one idea + the honest
scorecard) → [docs/README.md](docs/README.md) (the Diátaxis hub: tutorial ·
how-to · reference · explanation). Decisions are in [docs/adr/](docs/adr/).
Working on the repo itself? [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE). An [OpenHearth](https://levitatingflyfisher.github.io/)
project: local-first, no accounts, no tracking, built for households.
