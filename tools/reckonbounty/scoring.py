"""Scoring — PROTOCOL.md §4, normative in its formulas.

Two clients given the same request/response/resolution triples MUST produce
identical numbers; that is what makes a track record portable and arguing
about it pointless. So: the formulas below are transcribed from the spec,
each with its own test, and nothing here is configurable.

Edge rules implemented (all from §3):
  * a resolution outcome of "void" cancels scoring entirely (§3.3);
  * responses with created_at after reply_by are excluded (§3.1);
  * one response per bot per request — latest created_at before the
    deadline wins (§3.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import formats

# Log-score input clamp: a bot that says an absolute 0 or 1 and misses gets
# a huge but FINITE penalty (ln(1e-9) ~= -20.7), and ln(1) never masks the
# clamp on the other side.
LOG_CLAMP_LO = 1e-9
LOG_CLAMP_HI = 1 - 1e-9

PINBALL_TAUS = ((0.1, "p10"), (0.5, "p50"), (0.9, "p90"))


class ScoringError(ValueError):
    """A scoring input violates the protocol contract (not a formula issue)."""


def _clamp(p: float) -> float:
    return min(max(p, LOG_CLAMP_LO), LOG_CLAMP_HI)


# --- The §4 formulas ----------------------------------------------------------


def brier_binary(p: float, outcome: bool) -> float:
    """Brier (p - o)^2 with o in {0, 1}."""
    return (p - (1.0 if outcome else 0.0)) ** 2


def log_binary(p: float, outcome: bool) -> float:
    """Log score ln(p_o): probability assigned to the realized outcome."""
    p_o = p if outcome else 1.0 - p
    return math.log(_clamp(p_o))


def brier_multi(distribution: dict[str, float], options: list[str], winner: str) -> float:
    """Multiclass Brier Σ_i (p_i - o_i)^2 over the request's options."""
    return sum(
        (distribution[option] - (1.0 if option == winner else 0.0)) ** 2
        for option in options
    )


def log_multi(distribution: dict[str, float], winner: str) -> float:
    """Log score ln(p_winner)."""
    return math.log(_clamp(distribution[winner]))


def pinball_mean(quantiles: dict[str, float], y: float) -> float:
    """Mean pinball loss L_tau(y, q) = (tau - 1[y < q]) * (y - q)
    over tau in {0.1, 0.5, 0.9}. The tau set is normative: extra provided
    quantiles are welcome on the wire but do not enter the score."""
    losses = []
    for tau, key in PINBALL_TAUS:
        q = quantiles[key]
        indicator = 1.0 if y < q else 0.0
        losses.append((tau - indicator) * (y - q))
    return sum(losses) / len(losses)


# --- Scoring a whole bounty ----------------------------------------------------


@dataclass
class ScoredRow:
    bot: str
    created_at: str
    headline: float  # p (binary), p_winner (multi), p50 (quantity)
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ScoreReport:
    request_id: str
    question_type: str
    void: bool = False
    rows: list[ScoredRow] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (bot, reason)


def score_bounty(request: dict, resolution: dict, responses: list[dict]) -> ScoreReport:
    """Score every eligible response. Raises ScoringError on contract
    violations; protocol exclusions (late, superseded) are reported, not raised."""
    question = request["question"]
    qtype = question["type"]
    outcome = resolution["outcome"]
    report = ScoreReport(request_id=request["id"], question_type=qtype)

    if resolution["request_id"] != request["id"]:
        raise ScoringError(
            f"resolution.request_id {resolution['request_id']!r} does not match "
            f"request.id {request['id']!r}"
        )

    if outcome == "void":
        report.void = True
        return report

    _check_outcome_type(qtype, outcome, question)

    eligible = _eligible_responses(request, responses, report)

    for response in eligible:
        forecast = response["forecast"]
        shape_errors = formats.forecast_shape_errors(forecast, question)
        if shape_errors:
            raise ScoringError(
                f"response from {response['bot']['name']!r}: " + "; ".join(shape_errors)
            )
        report.rows.append(_score_one(qtype, question, outcome, response))

    report.rows.sort(key=lambda row: formats.parse_timestamp(row.created_at))
    return report


def _check_outcome_type(qtype: str, outcome: object, question: dict) -> None:
    if qtype == "binary" and not isinstance(outcome, bool):
        raise ScoringError(
            f"outcome: binary questions resolve to true/false, got {outcome!r}"
        )
    if qtype == "multi" and outcome not in question.get("options", []):
        raise ScoringError(
            f"outcome: {outcome!r} is not one of the request's options"
        )
    if qtype == "quantity" and not (
        isinstance(outcome, (int, float)) and not isinstance(outcome, bool)
    ):
        raise ScoringError(
            f"outcome: quantity questions resolve to a number, got {outcome!r}"
        )


def _eligible_responses(
    request: dict, responses: list[dict], report: ScoreReport
) -> list[dict]:
    """Apply the two §3 exclusion rules; record every exclusion with a reason."""
    reply_by = formats.parse_timestamp(request.get("reply_by"))

    for response in responses:
        if response["request_id"] != request["id"]:
            raise ScoringError(
                f"response {response['id']!r}: request_id "
                f"{response['request_id']!r} does not match request.id "
                f"{request['id']!r}"
            )

    on_time = []
    for response in responses:
        created = formats.parse_timestamp(response["created_at"])
        if reply_by is not None and created > reply_by:
            report.excluded.append((
                response["bot"]["name"],
                f"late: created_at {response['created_at']} is after "
                f"reply_by {request['reply_by']}",
            ))
        else:
            on_time.append(response)

    # One response per bot: latest created_at before the deadline wins.
    # Ties on created_at break by the lexicographically larger response id
    # (§3.2) — never by argument order, or two clients fed the same triples
    # in different file order would disagree, violating §4 determinism.
    def rank(response: dict) -> tuple:
        return (formats.parse_timestamp(response["created_at"]),
                response["id"])

    winners: dict[str, dict] = {}
    for response in on_time:
        name = response["bot"]["name"]
        current = winners.get(name)
        if current is None or rank(response) > rank(current):
            if current is not None:
                report.excluded.append(
                    (name, "superseded by a later response from the same bot")
                )
            winners[name] = response
        else:
            report.excluded.append(
                (name, "superseded by a later response from the same bot")
            )
    return list(winners.values())


def _score_one(qtype: str, question: dict, outcome: object, response: dict) -> ScoredRow:
    forecast = response["forecast"]
    row = ScoredRow(
        bot=response["bot"]["name"],
        created_at=response["created_at"],
        headline=0.0,
    )
    if qtype == "binary":
        p = forecast["p"]
        row.headline = p
        row.scores = {"brier": brier_binary(p, outcome), "log_score": log_binary(p, outcome)}
    elif qtype == "multi":
        dist = forecast["distribution"]
        row.headline = dist[outcome]
        row.scores = {
            "brier": brier_multi(dist, question["options"], outcome),
            "log_score": log_multi(dist, outcome),
        }
    else:  # quantity
        quantiles = forecast["quantiles"]
        row.headline = quantiles["p50"]
        row.scores = {"pinball": pinball_mean(quantiles, outcome)}
    return row
