"""rb ask: flag-driven BountyRequest builder. It must never emit a message
that rb validate would reject — validated before it leaves the tool."""

import json

from reckonbounty import formats
from reckonbounty.cli import main


def ask(capsys, *argv):
    code = main(["ask", *argv])
    out = capsys.readouterr().out
    return code, out


def test_minimal_ask_emits_a_conforming_request(capsys):
    code, out = ask(capsys, "--title", "Buy the vacation cabin?")
    assert code == 0
    request = json.loads(out)
    assert formats.validate_message(request) == []
    assert request["kind"] == "request"
    assert request["question"]["type"] == "binary"
    assert request["question"]["title"] == "Buy the vacation cabin?"
    assert request["bounty"]["rail"] == "none"


def test_ask_defaults_to_an_open_call(capsys):
    _, out = ask(capsys, "--title", "T?")
    assert json.loads(out)["reply_by"] is None


def test_ask_defaults_to_redacted_manual(capsys):
    # The asker composes the flags themselves — that IS manual redaction (§5).
    _, out = ask(capsys, "--title", "T?")
    privacy = json.loads(out)["privacy"]
    assert privacy["tier"] == "redacted"
    assert privacy["redaction"] == "manual"


def test_ask_public_tier_carries_no_redaction_claim(capsys):
    _, out = ask(capsys, "--title", "T?", "--tier", "public")
    privacy = json.loads(out)["privacy"]
    assert privacy["tier"] == "public"
    assert "redaction" not in privacy


def test_ask_generates_unique_ids(capsys):
    _, first = ask(capsys, "--title", "T?")
    _, second = ask(capsys, "--title", "T?")
    assert json.loads(first)["id"] != json.loads(second)["id"]


def test_ask_background_and_resolution_flags(capsys):
    _, out = ask(
        capsys,
        "--title", "T?",
        "--background", "De-identified background.",
        "--criteria", "Asker judges in 12 months.",
        "--horizon", "2027-08-01",
    )
    question = json.loads(out)["question"]
    assert question["background"] == "De-identified background."
    assert question["resolution"]["criteria"] == "Asker judges in 12 months."
    assert question["resolution"]["horizon"] == "2027-08-01"
    assert question["resolution"]["resolver"] == "asker"


def test_ask_multi_takes_repeated_options(capsys):
    _, out = ask(
        capsys, "--title", "T?", "--type", "multi",
        "--option", "buy", "--option", "rent", "--option", "wait",
    )
    request = json.loads(out)
    assert formats.validate_message(request) == []
    assert request["question"]["options"] == ["buy", "rent", "wait"]


def test_ask_multi_with_too_few_options_is_refused(capsys):
    code = main(["ask", "--title", "T?", "--type", "multi", "--option", "only"])
    assert code == 2
    assert "option" in capsys.readouterr().err


def test_ask_quantity_requires_a_unit(capsys):
    code = main(["ask", "--title", "T?", "--type", "quantity"])
    assert code == 2
    assert "unit" in capsys.readouterr().err


def test_ask_quantity_with_unit(capsys):
    _, out = ask(capsys, "--title", "How much?", "--type", "quantity", "--unit", "USD")
    request = json.loads(out)
    assert formats.validate_message(request) == []
    assert request["question"]["unit"] == "USD"


def test_ask_valid_reply_by_is_kept(capsys):
    _, out = ask(capsys, "--title", "T?", "--reply-by", "2026-08-01T00:00:00Z")
    assert json.loads(out)["reply_by"] == "2026-08-01T00:00:00Z"


def test_ask_garbage_reply_by_is_refused(capsys):
    code = main(["ask", "--title", "T?", "--reply-by", "next tuesday"])
    assert code == 2
    assert "reply-by" in capsys.readouterr().err


def test_ask_duplicate_options_are_a_flag_error_not_a_builder_bug(capsys):
    code = main(["ask", "--title", "pick", "--type", "multi",
                 "--option", "A", "--option", "A"])
    err = capsys.readouterr().err
    assert code == 2
    assert "--option" in err
    assert "distinct" in err
    # The wording must blame the flags, not the tool.
    assert "invalid request" not in err


def test_ask_empty_option_is_a_flag_error(capsys):
    code = main(["ask", "--title", "pick", "--type", "multi",
                 "--option", "A", "--option", ""])
    err = capsys.readouterr().err
    assert code == 2
    assert "--option" in err
    assert "invalid request" not in err


def test_ask_empty_title_is_a_flag_error(capsys):
    code = main(["ask", "--title", ""])
    err = capsys.readouterr().err
    assert code == 2
    assert "--title" in err
    assert "invalid request" not in err


def test_ask_options_on_binary_are_refused(capsys):
    code = main(["ask", "--title", "T?", "--option", "stray"])
    assert code == 2
    assert "multi" in capsys.readouterr().err


def test_ask_out_writes_a_file(tmp_path, capsys):
    target = tmp_path / "request.json"
    code = main(["ask", "--title", "T?", "--out", str(target)])
    assert code == 0
    request = json.loads(target.read_text(encoding="utf-8"))
    assert formats.validate_message(request) == []


def test_ask_created_at_is_utc_iso(capsys):
    _, out = ask(capsys, "--title", "T?")
    created = json.loads(out)["created_at"]
    assert created.endswith("Z")
    assert formats.parse_timestamp(created) is not None
