# ADR-0002: Files before HTTP

- **Status:** Accepted
- **Date:** 2026-07-11 (founding decision, v0.1)

## Context

A protocol needs a transport, and the reflex is to start with HTTP endpoints:
POST a request, get a response, done. But endpoints demand hosting, TLS,
availability, CORS, and an operator — and this project's values (local-first,
no accounts, no component that requires trusting an operator, spec §8) mean
the protocol must be *complete* without any of that. There is also a design
risk: formats developed alongside a live API tend to lean on the transport
(status codes, headers, sessions) and rot into incompleteness the moment they
travel any other way.

## Decision

**v0 transport is files.** Requests, responses, and resolutions move as
`.json` files or pasted text — share sheet, USB, chat, carrier pigeon
(spec §6). Every message is a self-contained UTF-8 JSON object with its own
envelope (`reckonbounty`, `kind`), correlation (`request_id`), timestamps, and
identity (`bot.name`) — nothing is delegated to a transport layer. HTTPS is
spec'd as an *optional* v0.1 transport (`POST <endpoint>`, or `202` + retrieval
URL for slow bots) so the shape is settled, but nothing in this repo requires
a server to exist.

## Consequences

- **Buys:** works offline; trivially auditable (a household can read every
  byte that left the device); testable with fixtures alone (the
  [cabin example](../../examples/cabin/) *is* the conformance suite); and the
  formats are forced to be complete, so any future transport is a pure
  carrier.
- **Costs:** no push, no discovery, no latency guarantee — answering is a
  human-speed loop until HTTP bots exist. The directory (§3.4) is just a file
  for the same reason.
- **Forecloses:** transport-dependent semantics. If a field's meaning would
  ever require knowing *how* the message arrived, the field is wrong.

## Alternatives considered

- **HTTP-first** — faster demos, but the protocol would silently depend on an
  operator being up, violating I6 and §8 on day one.
- **A relay/queue service** — even a "dumb" relay is a party to trust for
  availability, and it invites accounts. Reckon's separate blind-relay work
  shows what it costs to do this honestly; the *protocol* must not need it.
- **Email as transport** — genuinely decentralized, but MIME wrapping and
  quoting mangle JSON in practice; a file attachment is already "files."
