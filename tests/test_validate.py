"""Spec §3 format rules: unknown fields PASS, malformed mandatory fields FAIL
with a precise message. One test per rule, straight from PROTOCOL.md."""

import json

import pytest

from reckonbounty import formats
from reckonbounty.cli import main


def errs(msg):
    return formats.validate_message(msg)


def assert_error_mentions(errors, *needles):
    """At least one error message contains every needle (precision check)."""
    assert errors, f"expected a validation error mentioning {needles!r}, got none"
    joined = "\n".join(errors)
    for needle in needles:
        assert needle in joined, f"{needle!r} not in errors:\n{joined}"


# --- Envelope (§3, all kinds) ------------------------------------------------


def test_valid_messages_pass(valid_request, valid_response, valid_resolution, valid_directory):
    for msg in (valid_request, valid_response, valid_resolution, valid_directory):
        assert errs(msg) == []


def test_top_level_must_be_an_object():
    assert_error_mentions(errs(["not", "an", "object"]), "JSON object")


def test_missing_spec_version_fails(valid_request):
    del valid_request["reckonbounty"]
    assert_error_mentions(errs(valid_request), "reckonbounty", "missing")


def test_non_string_spec_version_fails(valid_request):
    valid_request["reckonbounty"] = 0.1
    assert_error_mentions(errs(valid_request), "reckonbounty", "string")


def test_garbage_spec_version_fails(valid_request):
    valid_request["reckonbounty"] = "banana"
    assert_error_mentions(errs(valid_request), "reckonbounty", "banana")


def test_future_minor_version_is_tolerated(valid_request):
    valid_request["reckonbounty"] = "0.2"
    assert errs(valid_request) == []


def test_missing_kind_fails(valid_request):
    del valid_request["kind"]
    assert_error_mentions(errs(valid_request), "kind", "missing")


def test_unknown_kind_fails(valid_request):
    valid_request["kind"] = "party"
    assert_error_mentions(errs(valid_request), "kind", "party", "request")


def test_unknown_top_level_fields_pass(valid_request):
    valid_request["x_experimental"] = {"anything": [1, 2, 3]}
    assert errs(valid_request) == []


def test_unknown_nested_fields_pass(valid_response):
    valid_response["forecast"]["x_confidence_notes"] = "extra"
    valid_response["bot"]["x_homepage"] = "https://example.org"
    assert errs(valid_response) == []


# --- BountyRequest (§3.1) ----------------------------------------------------


def test_request_missing_id_fails(valid_request):
    del valid_request["id"]
    assert_error_mentions(errs(valid_request), "id", "missing")


def test_request_empty_id_fails(valid_request):
    valid_request["id"] = ""
    assert_error_mentions(errs(valid_request), "id", "empty")


def test_request_malformed_created_at_fails(valid_request):
    valid_request["created_at"] = "yesterday-ish"
    assert_error_mentions(errs(valid_request), "created_at", "yesterday-ish")


def test_request_reply_by_null_is_an_open_call(valid_request):
    valid_request["reply_by"] = None
    assert errs(valid_request) == []


def test_request_reply_by_absent_is_an_open_call(valid_request):
    del valid_request["reply_by"]
    assert errs(valid_request) == []


def test_request_malformed_reply_by_fails(valid_request):
    valid_request["reply_by"] = "next week"
    assert_error_mentions(errs(valid_request), "reply_by")


def test_request_missing_privacy_fails(valid_request):
    del valid_request["privacy"]
    assert_error_mentions(errs(valid_request), "privacy", "missing")


def test_request_unknown_privacy_tier_fails(valid_request):
    valid_request["privacy"]["tier"] = "pinky-swear"
    assert_error_mentions(errs(valid_request), "privacy.tier", "pinky-swear")


@pytest.mark.parametrize("tier", ["public", "redacted", "attested", "fhe"])
def test_all_four_spec_tiers_are_valid_wire_values(valid_request, tier):
    valid_request["privacy"]["tier"] = tier
    assert errs(valid_request) == []


def test_request_missing_question_fails(valid_request):
    del valid_request["question"]
    assert_error_mentions(errs(valid_request), "question", "missing")


def test_request_unknown_question_type_fails(valid_request):
    valid_request["question"]["type"] = "ternary"
    assert_error_mentions(errs(valid_request), "question.type", "ternary", "binary")


def test_request_missing_title_fails(valid_request):
    del valid_request["question"]["title"]
    assert_error_mentions(errs(valid_request), "question.title", "missing")


def test_request_non_object_resolution_fails(valid_request):
    valid_request["question"]["resolution"] = "soon"
    assert_error_mentions(errs(valid_request), "question.resolution", "object")


def test_multi_without_options_fails(valid_request):
    valid_request["question"]["type"] = "multi"
    assert_error_mentions(errs(valid_request), "question.options", "missing")


def test_multi_with_one_option_fails(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["only one"]
    assert_error_mentions(errs(valid_request), "question.options", "2")


def test_multi_with_seventeen_options_fails(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = [f"opt{i}" for i in range(17)]
    assert_error_mentions(errs(valid_request), "question.options", "16")


def test_multi_with_duplicate_options_fails(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["stay", "stay"]
    assert_error_mentions(errs(valid_request), "question.options", "duplicate")


def test_multi_with_non_string_option_fails(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["stay", 7]
    assert_error_mentions(errs(valid_request), "question.options")


def test_valid_multi_passes(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["buy", "rent", "wait"]
    assert errs(valid_request) == []


def test_quantity_without_unit_fails(valid_request):
    valid_request["question"]["type"] = "quantity"
    assert_error_mentions(errs(valid_request), "question.unit", "missing")


def test_valid_quantity_passes(valid_request):
    valid_request["question"]["type"] = "quantity"
    valid_request["question"]["unit"] = "USD"
    assert errs(valid_request) == []


def test_request_missing_bounty_fails(valid_request):
    del valid_request["bounty"]
    assert_error_mentions(errs(valid_request), "bounty", "missing")


def test_reserved_rail_is_politely_refused(valid_request):
    valid_request["bounty"]["rail"] = "x402"
    assert_error_mentions(errs(valid_request), "bounty.rail", "x402", "none")


# --- BountyResponse (§3.2) ---------------------------------------------------


def test_response_missing_request_id_fails(valid_response):
    del valid_response["request_id"]
    assert_error_mentions(errs(valid_response), "request_id", "missing")


def test_response_missing_bot_fails(valid_response):
    del valid_response["bot"]
    assert_error_mentions(errs(valid_response), "bot", "missing")


def test_response_empty_bot_name_fails(valid_response):
    valid_response["bot"]["name"] = ""
    assert_error_mentions(errs(valid_response), "bot.name", "empty")


def test_response_non_string_bot_model_fails(valid_response):
    valid_response["bot"]["model"] = 7
    assert_error_mentions(errs(valid_response), "bot.model", "string")


def test_response_missing_forecast_fails(valid_response):
    del valid_response["forecast"]
    assert_error_mentions(errs(valid_response), "forecast", "missing")


def test_forecast_with_no_known_shape_fails(valid_response):
    valid_response["forecast"] = {"vibes": "good"}
    assert_error_mentions(errs(valid_response), "forecast", "p", "distribution", "quantiles")


@pytest.mark.parametrize("p", [-0.1, 1.5, "0.5", None])
def test_out_of_range_or_non_numeric_p_fails(valid_response, p):
    valid_response["forecast"]["p"] = p
    assert_error_mentions(errs(valid_response), "forecast.p")


@pytest.mark.parametrize("p", [0, 1, 0.5])
def test_boundary_p_values_pass(valid_response, p):
    valid_response["forecast"]["p"] = p
    assert errs(valid_response) == []


def test_boolean_p_fails(valid_response):
    # In Python a bool is an int; the wire format still says number in [0,1].
    valid_response["forecast"]["p"] = True
    assert_error_mentions(errs(valid_response), "forecast.p", "number")


def test_distribution_summing_off_by_more_than_tolerance_fails(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["distribution"] = {"a": 0.5, "b": 0.4}
    assert_error_mentions(errs(valid_response), "forecast.distribution", "sum")


def test_distribution_within_spec_tolerance_passes(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["distribution"] = {"a": 0.5005, "b": 0.5}  # 1 ± 0.001
    assert errs(valid_response) == []


def test_negative_distribution_entry_fails(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["distribution"] = {"a": -0.2, "b": 1.2}
    assert_error_mentions(errs(valid_response), "forecast.distribution", "a")


def test_quantiles_missing_p50_fails(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["quantiles"] = {"p10": 1, "p90": 3}
    assert_error_mentions(errs(valid_response), "forecast.quantiles", "p50")


def test_decreasing_quantiles_fail(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["quantiles"] = {"p10": 5, "p50": 4, "p90": 6}
    assert_error_mentions(errs(valid_response), "forecast.quantiles", "non-decreasing")


def test_equal_quantiles_pass(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["quantiles"] = {"p10": 2, "p50": 2, "p90": 2}
    assert errs(valid_response) == []


def test_nonfinite_quantiles_fail(valid_response):
    # NaN/inf are not JSON numbers (RFC 8259); via the library API they must
    # not pass either — under NaN the non-decreasing check is vacuous and a
    # NaN score would poison every downstream mean forever.
    valid_response["forecast"]["quantiles"] = {
        "p10": float("nan"), "p50": float("inf"), "p90": float("inf")}
    assert_error_mentions(errs(valid_response), "forecast.quantiles")


def test_cli_rejects_nan_infinity_literals_as_invalid_json(tmp_path, capsys):
    # Python's lenient json.loads accepts NaN/Infinity literals, but spec §3
    # says messages are UTF-8 JSON — and RFC 8259 has no such literals. They
    # must fail at load (exit 2), or `rb score --json` would emit output no
    # strict parser (e.g. Reckon's Dart client) can read.
    poisoned = tmp_path / "response.json"
    poisoned.write_text(
        '{"reckonbounty": "0.1", "kind": "response", "request_id": "r",'
        ' "id": "x", "created_at": "2026-07-11T07:02:00Z",'
        ' "bot": {"name": "b"},'
        ' "forecast": {"quantiles": {"p10": NaN, "p50": Infinity,'
        ' "p90": Infinity}}}',
        encoding="utf-8",
    )
    assert main(["validate", str(poisoned)]) == 2
    err = capsys.readouterr().err
    assert "JSON" in err


def test_extra_quantiles_must_respect_the_ordering(valid_response):
    del valid_response["forecast"]["p"]
    valid_response["forecast"]["quantiles"] = {"p10": 1, "p25": 9, "p50": 2, "p90": 3}
    assert_error_mentions(errs(valid_response), "forecast.quantiles", "non-decreasing")


# --- Resolution (§3.3) -------------------------------------------------------


@pytest.mark.parametrize("outcome", [True, False, "took the job", 42, 3.5, "void"])
def test_all_spec_outcome_types_pass(valid_resolution, outcome):
    valid_resolution["outcome"] = outcome
    assert errs(valid_resolution) == []


@pytest.mark.parametrize("outcome", [None, {"won": True}, [1, 2]])
def test_malformed_outcomes_fail(valid_resolution, outcome):
    valid_resolution["outcome"] = outcome
    assert_error_mentions(errs(valid_resolution), "outcome")


def test_resolution_missing_outcome_fails(valid_resolution):
    del valid_resolution["outcome"]
    assert_error_mentions(errs(valid_resolution), "outcome", "missing")


def test_resolution_malformed_resolved_at_fails(valid_resolution):
    valid_resolution["resolved_at"] = 12345
    assert_error_mentions(errs(valid_resolution), "resolved_at")


# --- Directory (§3.4) --------------------------------------------------------


def test_directory_missing_bots_fails(valid_directory):
    del valid_directory["bots"]
    assert_error_mentions(errs(valid_directory), "bots", "missing")


def test_directory_bots_must_be_a_list(valid_directory):
    valid_directory["bots"] = {"rb-reference": {}}
    assert_error_mentions(errs(valid_directory), "bots", "list")


def test_directory_entry_without_name_fails(valid_directory):
    del valid_directory["bots"][0]["name"]
    assert_error_mentions(errs(valid_directory), "bots[0].name", "missing")


def test_directory_entry_with_unknown_tier_fails(valid_directory):
    valid_directory["bots"][0]["tiers"] = ["public", "trust-me"]
    assert_error_mentions(errs(valid_directory), "bots[0].tiers", "trust-me")


def test_the_canonical_directory_file_validates(cabin_dir):
    canonical = json.loads(
        (cabin_dir.parent.parent / "directory.json").read_text(encoding="utf-8")
    )
    assert errs(canonical) == []


# --- rb validate (CLI) -------------------------------------------------------


def test_cli_validates_the_cabin_example(cabin_dir, capsys):
    files = sorted(str(p) for p in cabin_dir.glob("*.json"))
    assert len(files) == 4
    assert main(["validate", *files]) == 0
    out = capsys.readouterr().out
    assert out.count("OK") == 4


def test_cli_reports_the_file_and_the_field(tmp_path, valid_request, capsys):
    del valid_request["kind"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(valid_request), encoding="utf-8")
    assert main(["validate", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "bad.json" in err
    assert "kind" in err


def test_cli_rejects_non_json_with_exit_2_bad_input(tmp_path, capsys):
    # Exit-code contract (cli.py header): 2 = bad input (unreadable file,
    # malformed message), 1 = the message parsed but violates the spec. A
    # truncated download must not read as "spec-nonconforming".
    junk = tmp_path / "junk.json"
    junk.write_text("{not json", encoding="utf-8")
    assert main(["validate", str(junk)]) == 2
    err = capsys.readouterr().err
    assert "junk.json" in err
    assert "JSON" in err


def test_cli_rejects_missing_file_with_exit_2_bad_input(tmp_path, capsys):
    assert main(["validate", str(tmp_path / "ghost.json")]) == 2
    assert "ghost.json" in capsys.readouterr().err


def test_cli_a_load_error_outranks_a_validation_failure(
        tmp_path, valid_request, capsys):
    # One unreadable input makes the whole batch a usage problem (2), even
    # when another file merely fails validation (1).
    del valid_request["kind"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(valid_request), encoding="utf-8")
    assert main(["validate", str(bad), str(tmp_path / "ghost.json")]) == 2


def test_cli_one_bad_file_fails_the_batch(tmp_path, valid_request, valid_response, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(valid_request), encoding="utf-8")
    del valid_response["forecast"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(valid_response), encoding="utf-8")
    assert main(["validate", str(good), str(bad)]) == 1
    captured = capsys.readouterr()
    assert "good.json" in captured.out and "OK" in captured.out
    assert "bad.json" in captured.err
