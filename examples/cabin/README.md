# The cabin example

The worked example from [the spec](../../docs/spec/PROTOCOL.md) §9, as real
wire files: one `redacted` binary request, two bot responses, and the asker's
resolution (`false` — did not buy). These four files are the conformance
anchor for every implementation in this repo: `rb validate` must pass all
four, and `rb score` must reproduce this table (Brier to 4 decimals):

| Bot | p(yes) | Brier | Log score |
|---|---|---|---|
| hustlerBot80000 | 0.35 | 0.1225 | −0.431 |
| cautiousBot | 0.20 | 0.0400 | −0.223 |

(The spec's third row — the asker's own 0.60, Brier 0.3600 — lives in the
asker's client, not in a response file; askers don't answer their own bounty.)

Try it:

```sh
rb validate examples/cabin/*.json
rb score examples/cabin/request.json examples/cabin/resolution.json \
         examples/cabin/response-*.json
```
