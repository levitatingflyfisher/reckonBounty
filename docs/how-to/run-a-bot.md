# How to run a bot

`rb answer` is the reference bot: it takes a BountyRequest file and emits a
conforming BountyResponse. A "bot" in this protocol is anything that answers —
an LLM pipeline, a committee, you (spec §2). This guide covers the three
built-in backends and the conduct rules that make a bot conforming.

## Pick a backend

```sh
rb answer <request.json> --backend <backend> [--name <botname>] > response.json
```

| Backend | What it does | Needs |
|---|---|---|
| `echo` | Deterministic fixed forecast — for tests, tutorials, plumbing checks. | Nothing |
| `claude-cli` | Shells out to `claude -p` with a strict-JSON forecasting prompt. | The `claude` CLI, logged in |
| `openai:<base_url>` | POSTs to any OpenAI-compatible `/v1/chat/completions` — llamafile, Ollama, etc. | A local (or remote) endpoint |

Examples:

```sh
# Fully local, via a llamafile listening on 8080:
rb answer request.json --backend openai:http://localhost:8080 > response.json

# Via the Claude CLI:
rb answer request.json --backend claude-cli > response.json
```

The backend prompt instructs the model to return **strict JSON** matching the
forecast shape for the question type (`p` for binary, `distribution` for
multi, `quantiles` for quantity — spec §3.2). The tool validates the model's
output and retries once on a parse failure; if it still can't get conforming
JSON, it fails loudly rather than emit a malformed response.

## Answering as a service (file transport)

v0 transport is files (spec §6), so "running a bot" is a loop you own:

1. Receive a `request.json` however people reach you — chat, email, share sheet.
2. Check you serve its `privacy.tier` (and its `bounty.rail` is `"none"` —
   politely refuse anything else, spec §3.1).
3. `rb answer` it; send the response file back before `reply_by` — late
   responses are excluded from scored comparisons.
4. Keep your `bot.name` stable. Your name *is* your track record; one response
   per bot per request (latest before `reply_by` wins).
5. If askers share resolutions back with you, keep the triples — they are your
   portable track record.

To be findable, add your bot to a directory file (spec §3.4) — the canonical
one is [`directory.json`](../../directory.json) at the repo root; PRs welcome,
or host your own.

## Conduct (normative, spec §7)

- **Disclose your method** in `bot.model` — backend and model string, honestly
  (`rb answer` fills this in for you).
- **Never attempt re-identification** of a `redacted` question.
- **Forecast with calibrated honesty** — no persuasion, no upselling in the
  rationale. The rationale is for the asker's understanding, not your
  marketing.
- **Answer what was asked, or decline.**

A bot that games any of these wins nothing: there is no money to win (v0),
and the asker's client is keeping score.
