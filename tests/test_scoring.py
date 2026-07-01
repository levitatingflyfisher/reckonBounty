"""Spec §4 scoring formulas — normative: two clients given the same triples
must produce identical numbers. Every formula and edge rule gets its test."""

import math

import pytest

from reckonbounty import scoring

# --- Binary: Brier (p - o)^2, log ln(p_o) ------------------------------------


def test_brier_binary_miss():
    assert scoring.brier_binary(0.35, False) == pytest.approx(0.1225)


def test_brier_binary_hit():
    assert scoring.brier_binary(0.35, True) == pytest.approx(0.4225)


def test_brier_binary_perfect_and_worst():
    assert scoring.brier_binary(1.0, True) == 0.0
    assert scoring.brier_binary(1.0, False) == 1.0


def test_log_binary_uses_probability_of_realized_outcome():
    assert scoring.log_binary(0.35, False) == pytest.approx(math.log(0.65))
    assert scoring.log_binary(0.35, True) == pytest.approx(math.log(0.35))


def test_log_binary_clamps_absolute_zero_to_1e_minus_9():
    # A p=1 miss (p_o = 0) must be a huge but FINITE penalty (spec/how-to).
    assert scoring.log_binary(1.0, False) == pytest.approx(math.log(1e-9))
    assert scoring.log_binary(0.0, True) == pytest.approx(math.log(1e-9))


def test_log_binary_clamps_absolute_one():
    # p_o = 1 clamps to 1 - 1e-9: essentially zero, never exactly ln(1).
    assert scoring.log_binary(1.0, True) == pytest.approx(math.log(1 - 1e-9))
    assert scoring.log_binary(1.0, True) != 0.0


# --- Multi: multiclass Brier Σ(p_i - o_i)^2, log ln(p_winner) -----------------


def test_brier_multi_sums_over_all_options():
    dist = {"buy": 0.5, "rent": 0.3, "wait": 0.2}
    # (0.5-0)^2 + (0.3-1)^2 + (0.2-0)^2 = 0.25 + 0.49 + 0.04
    assert scoring.brier_multi(dist, ["buy", "rent", "wait"], "rent") == pytest.approx(0.78)


def test_brier_multi_perfect_forecast_scores_zero():
    dist = {"buy": 0.0, "rent": 1.0, "wait": 0.0}
    assert scoring.brier_multi(dist, ["buy", "rent", "wait"], "rent") == 0.0


def test_log_multi_is_ln_of_winner_probability():
    dist = {"buy": 0.5, "rent": 0.3, "wait": 0.2}
    assert scoring.log_multi(dist, "rent") == pytest.approx(math.log(0.3))


def test_log_multi_clamps_zero_winner():
    dist = {"buy": 1.0, "rent": 0.0}
    assert scoring.log_multi(dist, "rent") == pytest.approx(math.log(1e-9))


# --- Quantity: mean pinball loss over tau in {0.1, 0.5, 0.9} ------------------


def test_pinball_mean_worked_example():
    quantiles = {"p10": 5, "p50": 9, "p90": 20}
    # tau=0.1, y=10 >= 5:  0.1 * (10-5)  = 0.5
    # tau=0.5, y=10 >= 9:  0.5 * (10-9)  = 0.5
    # tau=0.9, y=10 < 20: -0.1 * (10-20) = 1.0
    assert scoring.pinball_mean(quantiles, 10) == pytest.approx(2.0 / 3.0)


def test_pinball_perfect_quantiles_score_zero():
    assert scoring.pinball_mean({"p10": 7, "p50": 7, "p90": 7}, 7) == 0.0


def test_pinball_uses_only_the_three_spec_taus():
    # Extra provided quantiles do not change the score: tau set is normative.
    base = scoring.pinball_mean({"p10": 5, "p50": 9, "p90": 20}, 10)
    extra = scoring.pinball_mean({"p10": 5, "p25": 6, "p50": 9, "p90": 20}, 10)
    assert base == pytest.approx(extra)


def test_pinball_penalizes_overconfident_intervals():
    narrow = scoring.pinball_mean({"p10": 9.9, "p50": 10.0, "p90": 10.1}, 50)
    wide = scoring.pinball_mean({"p10": 5, "p50": 10, "p90": 60}, 50)
    assert narrow > wide


# --- score_bounty: the §3/§4 edge rules ---------------------------------------


def make_response(valid_response, name, created_at, **forecast):
    import copy

    r = copy.deepcopy(valid_response)
    r["bot"]["name"] = name
    r["created_at"] = created_at
    r["forecast"] = {**forecast}
    return r


def test_score_bounty_cabin_numbers(cabin_request, cabin_resolution, cabin_responses):
    report = scoring.score_bounty(cabin_request, cabin_resolution, cabin_responses)
    assert not report.void
    rows = {row.bot: row for row in report.rows}
    assert round(rows["hustlerBot80000"].scores["brier"], 4) == 0.1225
    assert round(rows["hustlerBot80000"].scores["log_score"], 4) == -0.4308
    assert round(rows["cautiousBot"].scores["brier"], 4) == 0.0400
    assert round(rows["cautiousBot"].scores["log_score"], 4) == -0.2231


def test_rows_come_back_in_answer_order(cabin_request, cabin_resolution, cabin_responses):
    # Spec §9 lists bots chronologically; reversing input order must not matter.
    report = scoring.score_bounty(
        cabin_request, cabin_resolution, list(reversed(cabin_responses))
    )
    assert [row.bot for row in report.rows] == ["hustlerBot80000", "cautiousBot"]


def test_late_response_is_excluded(valid_request, valid_resolution, valid_response):
    late = make_response(valid_response, "lateBot", "2026-07-19T00:00:00Z", p=0.9)
    on_time = make_response(valid_response, "punctualBot", "2026-07-12T00:00:00Z", p=0.4)
    report = scoring.score_bounty(valid_request, valid_resolution, [late, on_time])
    assert [row.bot for row in report.rows] == ["punctualBot"]
    assert any(bot == "lateBot" and "late" in reason for bot, reason in report.excluded)


def test_response_exactly_at_reply_by_is_on_time(valid_request, valid_resolution, valid_response):
    at_deadline = make_response(
        valid_response, "buzzerBot", valid_request["reply_by"], p=0.4
    )
    report = scoring.score_bounty(valid_request, valid_resolution, [at_deadline])
    assert [row.bot for row in report.rows] == ["buzzerBot"]


def test_null_reply_by_means_nothing_is_late(valid_request, valid_resolution, valid_response):
    valid_request["reply_by"] = None
    slow = make_response(valid_response, "slowBot", "2030-01-01T00:00:00Z", p=0.4)
    report = scoring.score_bounty(valid_request, valid_resolution, [slow])
    assert [row.bot for row in report.rows] == ["slowBot"]


def test_duplicate_bot_name_latest_before_deadline_wins(
    valid_request, valid_resolution, valid_response
):
    first = make_response(valid_response, "flipFlopBot", "2026-07-12T00:00:00Z", p=0.9)
    second = make_response(valid_response, "flipFlopBot", "2026-07-13T00:00:00Z", p=0.1)
    report = scoring.score_bounty(valid_request, valid_resolution, [first, second])
    assert len(report.rows) == 1
    # outcome false, p=0.1 -> brier 0.01 (the later forecast)
    assert report.rows[0].scores["brier"] == pytest.approx(0.01)
    assert any("superseded" in reason for _, reason in report.excluded)


def test_same_created_at_ties_break_by_response_id_not_argument_order(
    valid_request, valid_resolution, valid_response
):
    # §4: two clients given the same triples MUST produce identical numbers.
    # With identical created_at, the winner must not depend on file/glob
    # order — the tiebreak is the lexicographically larger response id.
    r1 = make_response(valid_response, "hustlerBot80000",
                       "2026-06-30T12:00:00Z", p=0.35)
    r1["id"] = "aaaa-1111"
    r2 = make_response(valid_response, "hustlerBot80000",
                       "2026-06-30T12:00:00Z", p=0.90)
    r2["id"] = "bbbb-2222"

    forward = scoring.score_bounty(valid_request, valid_resolution, [r1, r2])
    reverse = scoring.score_bounty(valid_request, valid_resolution, [r2, r1])

    assert forward.rows[0].scores["brier"] == reverse.rows[0].scores["brier"]
    # outcome false, the larger-id response (p=0.90) wins: brier 0.81.
    assert forward.rows[0].scores["brier"] == pytest.approx(0.81)


def test_void_resolution_cancels_scoring(valid_request, valid_resolution, valid_response):
    valid_resolution["outcome"] = "void"
    report = scoring.score_bounty(valid_request, valid_resolution, [valid_response])
    assert report.void
    assert report.rows == []


def test_mismatched_request_id_is_a_contract_violation(
    valid_request, valid_resolution, valid_response
):
    valid_response["request_id"] = "someone-elses-question"
    with pytest.raises(scoring.ScoringError, match="request_id"):
        scoring.score_bounty(valid_request, valid_resolution, [valid_response])


def test_mismatched_resolution_is_a_contract_violation(
    valid_request, valid_resolution, valid_response
):
    valid_resolution["request_id"] = "someone-elses-question"
    with pytest.raises(scoring.ScoringError, match="request_id"):
        scoring.score_bounty(valid_request, valid_resolution, [valid_response])


def test_wrong_forecast_shape_for_question_type_is_a_contract_violation(
    valid_request, valid_resolution, valid_response
):
    valid_response["forecast"] = {"quantiles": {"p10": 1, "p50": 2, "p90": 3}}
    with pytest.raises(scoring.ScoringError, match="forecast.p"):
        scoring.score_bounty(valid_request, valid_resolution, [valid_response])


def test_multi_distribution_must_cover_exactly_the_options(
    valid_request, valid_resolution, valid_response
):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["buy", "rent", "wait"]
    valid_resolution["outcome"] = "rent"
    valid_response["forecast"] = {"distribution": {"buy": 0.5, "rent": 0.5}}
    with pytest.raises(scoring.ScoringError, match="options"):
        scoring.score_bounty(valid_request, valid_resolution, [valid_response])


def test_multi_end_to_end(valid_request, valid_resolution, valid_response):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["buy", "rent", "wait"]
    valid_resolution["outcome"] = "rent"
    valid_response["forecast"] = {"distribution": {"buy": 0.5, "rent": 0.3, "wait": 0.2}}
    report = scoring.score_bounty(valid_request, valid_resolution, [valid_response])
    assert report.rows[0].scores["brier"] == pytest.approx(0.78)
    assert report.rows[0].scores["log_score"] == pytest.approx(math.log(0.3))


def test_multi_outcome_not_in_options_is_a_contract_violation(
    valid_request, valid_resolution, valid_response
):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["buy", "rent"]
    valid_resolution["outcome"] = "emigrate"
    valid_response["forecast"] = {"distribution": {"buy": 0.5, "rent": 0.5}}
    with pytest.raises(scoring.ScoringError, match="outcome"):
        scoring.score_bounty(valid_request, valid_resolution, [valid_response])


def test_quantity_end_to_end(valid_request, valid_resolution, valid_response):
    valid_request["question"]["type"] = "quantity"
    valid_request["question"]["unit"] = "USD"
    valid_resolution["outcome"] = 10
    valid_response["forecast"] = {"quantiles": {"p10": 5, "p50": 9, "p90": 20}}
    report = scoring.score_bounty(valid_request, valid_resolution, [valid_response])
    assert report.rows[0].scores["pinball"] == pytest.approx(2.0 / 3.0)


def test_binary_outcome_must_be_boolean(valid_request, valid_resolution, valid_response):
    valid_resolution["outcome"] = "false"  # a string is NOT a binary outcome
    with pytest.raises(scoring.ScoringError, match="outcome"):
        scoring.score_bounty(valid_request, valid_resolution, [valid_response])
