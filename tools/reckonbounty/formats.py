"""Wire-format validation — PROTOCOL.md §3, hand-rolled, stdlib only.

The two laws of §3, encoded here and tested in tests/test_validate.py:

  * unknown fields PASS (forward compatibility) — we never enumerate-and-reject;
  * missing or malformed MANDATORY fields FAIL with a precise message
    (``<json.path>: <what is wrong>``).

Validators return a list of error strings; an empty list means the message
conforms. Nothing in here raises on bad input — callers decide what a
failure costs.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

KINDS = ("request", "response", "resolution", "directory")
QUESTION_TYPES = ("binary", "multi", "quantity")
PRIVACY_TIERS = ("public", "redacted", "attested", "fhe")
DISTRIBUTION_TOLERANCE = 0.001  # §3.2: summing to 1 ± 0.001
MANDATORY_QUANTILES = ("p10", "p50", "p90")

_VERSION_RE = re.compile(r"^\d+(\.\d+)+$")
_QUANTILE_KEY_RE = re.compile(r"^p(\d{1,2})$")


def _is_number(value: object) -> bool:
    """JSON number — excludes bool (Python counts it as int) and NaN/inf
    (RFC 8259 has no such values; under NaN every comparison is vacuously
    false, so e.g. the quantile ordering check would silently pass)."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def parse_timestamp(value: object) -> datetime | None:
    """ISO-8601 → aware datetime (naive assumed UTC), or None if malformed."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# --- Field-level helpers (append precise errors, never raise) ----------------


def _require_nonempty_string(obj: dict, key: str, errors: list[str], path: str = "") -> None:
    label = f"{path}{key}"
    if key not in obj:
        errors.append(f"{label}: missing mandatory field")
    elif not isinstance(obj[key], str):
        errors.append(f"{label}: must be a string (got {type(obj[key]).__name__})")
    elif not obj[key]:
        errors.append(f"{label}: must not be empty")


def _check_string_if_present(obj: dict, key: str, errors: list[str], path: str = "") -> None:
    if key in obj and obj[key] is not None and not isinstance(obj[key], str):
        errors.append(f"{path}{key}: must be a string (got {type(obj[key]).__name__})")


def _require_timestamp(obj: dict, key: str, errors: list[str], path: str = "") -> None:
    label = f"{path}{key}"
    if key not in obj:
        errors.append(f"{label}: missing mandatory field")
    elif not isinstance(obj[key], str):
        errors.append(f"{label}: must be an ISO-8601 timestamp string "
                      f"(got {type(obj[key]).__name__})")
    elif parse_timestamp(obj[key]) is None:
        errors.append(f"{label}: {obj[key]!r} is not an ISO-8601 timestamp")


def _require_object(obj: dict, key: str, errors: list[str], path: str = "") -> bool:
    """True iff obj[key] exists and is a dict; records the error otherwise."""
    label = f"{path}{key}"
    if key not in obj:
        errors.append(f"{label}: missing mandatory field")
        return False
    if not isinstance(obj[key], dict):
        errors.append(f"{label}: must be an object (got {type(obj[key]).__name__})")
        return False
    return True


# --- Message validators -------------------------------------------------------


def validate_message(msg: object) -> list[str]:
    """Validate any protocol message. Empty list == conforming (§3)."""
    if not isinstance(msg, dict):
        return ["message: must be a JSON object"]

    errors: list[str] = []

    version = msg.get("reckonbounty")
    if "reckonbounty" not in msg:
        errors.append("reckonbounty: missing mandatory field (the spec version string)")
    elif not isinstance(version, str):
        errors.append(f"reckonbounty: must be a string (got {type(version).__name__})")
    elif not _VERSION_RE.match(version):
        errors.append(f"reckonbounty: {version!r} is not a version string like '0.1'")
    # Any well-formed version passes: §3 forward compatibility means a v0.1
    # validator must not reject a message merely for being newer.

    kind = msg.get("kind")
    if "kind" not in msg:
        errors.append("kind: missing mandatory field")
        return errors
    if kind not in KINDS:
        errors.append(f"kind: {kind!r} is not one of {', '.join(KINDS)}")
        return errors

    validator = {
        "request": _validate_request,
        "response": _validate_response,
        "resolution": _validate_resolution,
        "directory": _validate_directory,
    }[kind]
    validator(msg, errors)
    return errors


def _validate_request(msg: dict, errors: list[str]) -> None:
    _require_nonempty_string(msg, "id", errors)
    _require_timestamp(msg, "created_at", errors)

    # reply_by MAY be null or absent — an open call (§3.1).
    if msg.get("reply_by") is not None and parse_timestamp(msg["reply_by"]) is None:
        errors.append(f"reply_by: {msg['reply_by']!r} is not an ISO-8601 timestamp or null")

    if _require_object(msg, "privacy", errors):
        privacy = msg["privacy"]
        tier = privacy.get("tier")
        if "tier" not in privacy:
            errors.append("privacy.tier: missing mandatory field")
        elif tier not in PRIVACY_TIERS:
            errors.append(
                f"privacy.tier: {tier!r} is not one of {', '.join(PRIVACY_TIERS)}"
            )
        _check_string_if_present(privacy, "redaction", errors, "privacy.")

    if _require_object(msg, "question", errors):
        _validate_question(msg["question"], errors)

    if _require_object(msg, "bounty", errors):
        bounty = msg["bounty"]
        rail = bounty.get("rail")
        if "rail" not in bounty:
            errors.append("bounty.rail: missing mandatory field")
        elif rail != "none":
            # §3.1: politely refuse — the rail namespace is reserved on purpose.
            errors.append(
                f"bounty.rail: {rail!r} is reserved for a future version; "
                "v0 implementations accept only 'none' (politely refusing)"
            )
        for key in ("terms", "amount", "currency"):
            _check_string_if_present(bounty, key, errors, "bounty.")


def _validate_question(question: dict, errors: list[str]) -> None:
    qtype = question.get("type")
    if "type" not in question:
        errors.append("question.type: missing mandatory field")
    elif qtype not in QUESTION_TYPES:
        errors.append(
            f"question.type: {qtype!r} is not one of {', '.join(QUESTION_TYPES)}"
        )
    _require_nonempty_string(question, "title", errors, "question.")
    _check_string_if_present(question, "background", errors, "question.")

    if "resolution" in question:
        if not isinstance(question["resolution"], dict):
            errors.append(
                "question.resolution: must be an object "
                f"(got {type(question['resolution']).__name__})"
            )
        else:
            for key in ("criteria", "horizon", "resolver"):
                _check_string_if_present(question["resolution"], key, errors,
                                         "question.resolution.")

    if qtype == "multi":
        options = question.get("options")
        if "options" not in question:
            errors.append("question.options: missing mandatory field for type 'multi'")
        elif not isinstance(options, list):
            errors.append(f"question.options: must be a list "
                          f"(got {type(options).__name__})")
        else:
            if not all(isinstance(o, str) and o for o in options):
                errors.append("question.options: entries must be non-empty strings")
            if not 2 <= len(options) <= 16:
                errors.append(
                    f"question.options: must have 2 to 16 entries (got {len(options)})"
                )
            if len(set(options)) != len(options):
                errors.append("question.options: duplicate entries are not allowed")

    if qtype == "quantity" and "unit" not in question:
        errors.append("question.unit: missing mandatory field for type 'quantity'")
    elif qtype == "quantity":
        _check_string_if_present(question, "unit", errors, "question.")


def _validate_response(msg: dict, errors: list[str]) -> None:
    _require_nonempty_string(msg, "request_id", errors)
    _require_nonempty_string(msg, "id", errors)
    _require_timestamp(msg, "created_at", errors)

    if _require_object(msg, "bot", errors):
        bot = msg["bot"]
        _require_nonempty_string(bot, "name", errors, "bot.")
        for key in ("operator", "model", "directory_url"):
            _check_string_if_present(bot, key, errors, "bot.")

    if _require_object(msg, "forecast", errors):
        _validate_forecast(msg["forecast"], errors)


def _validate_forecast(forecast: dict, errors: list[str]) -> None:
    shapes = [k for k in ("p", "distribution", "quantiles") if k in forecast]
    if not shapes:
        errors.append(
            "forecast: must contain at least one of p, distribution, quantiles"
        )
        return

    if "p" in forecast:
        p = forecast["p"]
        if not _is_number(p) or not 0 <= p <= 1:
            errors.append(f"forecast.p: must be a number in [0, 1] (got {p!r})")

    if "distribution" in forecast:
        _validate_distribution(forecast["distribution"], errors)

    if "quantiles" in forecast:
        _validate_quantiles(forecast["quantiles"], errors)

    _check_string_if_present(forecast, "rationale", errors, "forecast.")
    for key in ("base_rates", "key_uncertainties", "clarifying_questions"):
        value = forecast.get(key)
        if value is not None and key in forecast:
            if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
                errors.append(f"forecast.{key}: must be a list of strings")


def _validate_distribution(distribution: object, errors: list[str]) -> None:
    if not isinstance(distribution, dict) or not distribution:
        errors.append("forecast.distribution: must be a non-empty object of "
                      "option -> probability")
        return
    ok = True
    for option, value in distribution.items():
        if not isinstance(option, str) or not _is_number(value) or not 0 <= value <= 1:
            errors.append(
                f"forecast.distribution: entry {option!r} must be a number in [0, 1] "
                f"(got {value!r})"
            )
            ok = False
    if ok:
        total = sum(distribution.values())
        if abs(total - 1) > DISTRIBUTION_TOLERANCE:
            errors.append(
                f"forecast.distribution: values must sum to 1 ± "
                f"{DISTRIBUTION_TOLERANCE} (got {total:.6g})"
            )


def _validate_quantiles(quantiles: object, errors: list[str]) -> None:
    if not isinstance(quantiles, dict):
        errors.append("forecast.quantiles: must be an object of pNN -> number")
        return
    for key in MANDATORY_QUANTILES:
        if key not in quantiles:
            errors.append(f"forecast.quantiles: missing mandatory quantile {key}")
        elif not _is_number(quantiles[key]):
            errors.append(
                f"forecast.quantiles: {key} must be a number (got {quantiles[key]!r})"
            )
    # Non-decreasing across ALL recognized percentile keys, spec'd for
    # p10/p50/p90 and extended naturally to any extras the bot provided.
    ordered = sorted(
        (int(m.group(1)), key)
        for key in quantiles
        if (m := _QUANTILE_KEY_RE.match(key)) and _is_number(quantiles[key])
    )
    values = [quantiles[key] for _, key in ordered]
    if any(a > b for a, b in zip(values, values[1:])):
        errors.append(
            "forecast.quantiles: values must be non-decreasing in percentile order"
        )


def _validate_resolution(msg: dict, errors: list[str]) -> None:
    _require_nonempty_string(msg, "request_id", errors)
    _require_timestamp(msg, "resolved_at", errors)
    if "outcome" not in msg:
        errors.append("outcome: missing mandatory field")
    elif not (isinstance(msg["outcome"], bool)
              or isinstance(msg["outcome"], str)
              or _is_number(msg["outcome"])):
        errors.append(
            "outcome: must be true/false (binary), an option string (multi), "
            f"a number (quantity), or 'void' — got {msg['outcome']!r}"
        )
    _check_string_if_present(msg, "note", errors)


def _validate_directory(msg: dict, errors: list[str]) -> None:
    if "bots" not in msg:
        errors.append("bots: missing mandatory field")
        return
    if not isinstance(msg["bots"], list):
        errors.append(f"bots: must be a list (got {type(msg['bots']).__name__})")
        return
    for i, bot in enumerate(msg["bots"]):
        path = f"bots[{i}]"
        if not isinstance(bot, dict):
            errors.append(f"{path}: must be an object (got {type(bot).__name__})")
            continue
        _require_nonempty_string(bot, "name", errors, f"{path}.")
        for key in ("endpoint", "transport", "operator", "model", "notes"):
            _check_string_if_present(bot, key, errors, f"{path}.")
        tiers = bot.get("tiers")
        if tiers is not None and "tiers" in bot:
            if not isinstance(tiers, list):
                errors.append(f"{path}.tiers: must be a list of privacy tiers")
            else:
                for tier in tiers:
                    if tier not in PRIVACY_TIERS:
                        errors.append(
                            f"{path}.tiers: {tier!r} is not one of "
                            f"{', '.join(PRIVACY_TIERS)}"
                        )


# --- Cross-checks used by rb score / rb answer --------------------------------


def validate_forecast(forecast: object, question: dict | None = None) -> list[str]:
    """Standalone §3.2 forecast checks, plus the per-question-type rules
    when the request's question is in hand."""
    if not isinstance(forecast, dict):
        return ["forecast: must be a JSON object"]
    errors: list[str] = []
    _validate_forecast(forecast, errors)
    if question is not None:
        errors.extend(forecast_shape_errors(forecast, question))
    return errors


def forecast_shape_errors(forecast: dict, question: dict) -> list[str]:
    """The per-question-type rules of §3.2 that need the request in hand."""
    errors: list[str] = []
    qtype = question.get("type")
    if qtype == "binary" and "p" not in forecast:
        errors.append("forecast.p: missing — binary questions require p (spec §3.2)")
    elif qtype == "multi":
        if "distribution" not in forecast:
            errors.append(
                "forecast.distribution: missing — multi questions require a "
                "distribution (spec §3.2)"
            )
        elif isinstance(forecast["distribution"], dict):
            wanted = set(question.get("options", []))
            got = set(forecast["distribution"])
            if wanted != got:
                missing = sorted(wanted - got)
                extra = sorted(got - wanted)
                errors.append(
                    "forecast.distribution: must cover exactly the request's "
                    f"options (missing {missing}, unexpected {extra})"
                )
    elif qtype == "quantity" and "quantiles" not in forecast:
        errors.append(
            "forecast.quantiles: missing — quantity questions require quantiles "
            "(spec §3.2)"
        )
    return errors
