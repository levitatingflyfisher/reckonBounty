# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo.

**Read these three, in order, before non-trivial work:**
1. [VISION.md](VISION.md) — the one idea, what must stay true, the honest scorecard.
2. [docs/spec/PROTOCOL.md](docs/spec/PROTOCOL.md) — **the law.** Formats,
   invariants I1–I6, scoring formulas. Everything else defers to it.
3. [docs/adr/](docs/adr/) — why the four founding decisions went the way they did.

## Take the code as current-state, not gospel

Every line of source and every comment here was written by an AI assistant.
Treat it as **an accurate record of what currently exists, offered with
gratitude and a grain of salt** — not a specification and not guaranteed
correct. If a comment and the tests disagree, the tests win; if the tests and
the spec disagree, the spec wins; if the spec and reality disagree, that's a
spec bug — raise it, don't route around it.

## What this is

An **open, non-custodial protocol for buying probabilistic advice on personal
decisions**, plus its reference tooling: the spec (`docs/spec/PROTOCOL.md`),
stdlib-only Python tools (`tools/` — the `rb` CLI: ask/answer/resolve/score/validate),
a conformance example (`examples/cabin/`), a Diátaxis doc spine (`docs/`),
and a single-file static site (`site/`).
[Reckon](https://github.com/levitatingflyfisher/Reckon) is the first
client; this repo is the protocol's home.

## The map

```
docs/spec/PROTOCOL.md   THE spec — single source of truth; changes here are protocol changes
docs/adr/               0001 bounty-not-market · 0002 files-before-http
                        0003 stdlib-only-tools · 0004 payments-reserved-x402
docs/                   Diátaxis hub: tutorials/ how-to/ explanation/
examples/cabin/         spec §9 as real wire files — the conformance anchor
directory.json          the canonical bot directory (§3.4) — just a file
tools/reckonbounty/     the rb CLI (cli, formats, scoring, backends) — stdlib only
tests/                  pytest — every spec formula and format rule has a test
site/                   single-file static site → gh-pages
```

## Non-negotiables (breaking one is a regression, not a feature)

- **The six invariants (spec §1).** No market, asker funds everything, no
  custody, asker-is-oracle, privacy tier on every request, local-first
  ledger. No feature may let any participant win money, and no component may
  require trusting an operator — including us (spec §8).
- **The spec wins, and spec changes are deliberate.** Don't "fix" the spec
  from the tools' side. A wire-format or formula change means: change
  PROTOCOL.md (with version bump reasoning), the tests, the tools, and the
  cabin example together, in one honest commit.
- **Scoring is normative.** Two clients given the same triples must produce
  identical numbers. `rb score` must reproduce the [cabin table](examples/cabin/README.md)
  (spec §9) to 4 decimal places at all times — it is the cross-implementation
  handshake with Reckon.
- **Forward-compat validation, exactly as spec'd (§3):** unknown fields PASS,
  missing/malformed mandatory fields FAIL with a precise message. Never
  tighten validation to reject unknown fields; never loosen it to accept
  malformed mandatory ones.
- **stdlib-only tools** ([ADR-0003](docs/adr/0003-stdlib-only-tools.md)).
  Zero runtime dependencies; `pytest` is the only dev dependency. Adding a
  runtime dep requires a superseding ADR, not a lockfile entry.
- **`bounty.rail` stays `"none"` in v0.x** and other rails are politely
  refused. Don't build payment code ([ADR-0004](docs/adr/0004-payments-reserved-x402.md)).
- **Privacy tier honesty.** `attested`/`fhe` are reserved; nothing may claim
  or imply they work. Redaction is client-side, always.

## How to work here

- **TDD, always.** Failing test → make it pass → refactor. Every formula and
  format rule in PROTOCOL.md gets its test written *first*; bug fixes start
  with a reproducing test. Run from the repo root:
  ```sh
  pip install -e tools/ && python -m pytest tests/ -q
  ```
- **Edge cases are spec'd — test them:** p = 0/1 log clamp to
  `[1e-9, 1 − 1e-9]`, `void` resolutions, late responses (after `reply_by`),
  duplicate `bot.name` (latest-before-deadline wins), multi distributions
  summing to 1 ± 0.001, non-decreasing quantiles.
- **`claude-cli` backend hygiene:** always shell out to `claude -p` with cwd
  set to a **neutral directory** (tempdir), never the repo — project context
  contaminates the forecast. Strict-JSON prompt; validate; one retry; then
  fail loudly.
- **Commits:** atomic, message states the *why*. Persona is the repo-local
  git config (`OpenHearth Development`) — no personal identities, **no AI
  attribution of any kind** (no `Co-Authored-By`, no "Generated with").
  Fetch before push.
- **Never commit:** `CLAUDE.md`, `docs/superpowers/` (both git-ignored),
  or anything naming a real person, place, or community.
- **Docs are part of done.** A behavior change lands with its doc change —
  spec, how-to, or scorecard row, whichever it touched.
