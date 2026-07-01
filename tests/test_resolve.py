"""rb resolve: bind an outcome to a request as a conforming BountyResolution.

The quickstart's third act. `rb ask` exists so nobody hand-writes a request;
`rb resolve` exists for the same reason — the resolution must carry the
request's exact id, and a stranger should never have to open a JSON file to
copy a uuid. Like rb ask, it must never emit a message rb validate rejects.
"""

import json

from reckonbounty import formats
from reckonbounty.cli import main


def resolve(capsys, *argv):
    code = main(["resolve", *argv])
    out = capsys.readouterr().out
    return code, out


def make_request(tmp_path, capsys, *extra):
    path = tmp_path / "request.json"
    code = main(["ask", "--title", "Buy the vacation cabin?", *extra,
                 "--out", str(path)])
    assert code == 0
    capsys.readouterr()
    return path


def test_resolve_emits_a_conforming_resolution_bound_to_the_request(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    request = json.loads(request_path.read_text(encoding="utf-8"))

    code, out = resolve(capsys, str(request_path), "--outcome", "no")
    assert code == 0
    resolution = json.loads(out)
    assert formats.validate_message(resolution) == []
    assert resolution["kind"] == "resolution"
    assert resolution["request_id"] == request["id"]
    assert resolution["outcome"] is False


def test_resolve_binary_accepts_yes_no_true_false(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    for word, expected in (("yes", True), ("TRUE", True),
                           ("no", False), ("False", False)):
        code, out = resolve(capsys, str(request_path), "--outcome", word)
        assert code == 0
        assert json.loads(out)["outcome"] is expected


def test_resolve_binary_garbage_outcome_is_refused(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    code = main(["resolve", str(request_path), "--outcome", "maybe"])
    assert code == 2
    assert "outcome" in capsys.readouterr().err


def test_resolve_void_works_for_any_question_type(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    code, out = resolve(capsys, str(request_path), "--outcome", "void")
    assert code == 0
    assert json.loads(out)["outcome"] == "void"


def test_resolve_multi_takes_the_winning_option(tmp_path, capsys):
    request_path = make_request(
        tmp_path, capsys, "--type", "multi",
        "--option", "buy", "--option", "rent",
    )
    code, out = resolve(capsys, str(request_path), "--outcome", "rent")
    assert code == 0
    resolution = json.loads(out)
    assert formats.validate_message(resolution) == []
    assert resolution["outcome"] == "rent"


def test_resolve_multi_unknown_option_is_refused(tmp_path, capsys):
    request_path = make_request(
        tmp_path, capsys, "--type", "multi",
        "--option", "buy", "--option", "rent",
    )
    code = main(["resolve", str(request_path), "--outcome", "sublet"])
    assert code == 2
    err = capsys.readouterr().err
    assert "outcome" in err and "option" in err


def test_resolve_quantity_takes_a_number(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys, "--type", "quantity",
                                "--unit", "USD")
    code, out = resolve(capsys, str(request_path), "--outcome", "412.5")
    assert code == 0
    resolution = json.loads(out)
    assert formats.validate_message(resolution) == []
    assert resolution["outcome"] == 412.5


def test_resolve_quantity_non_number_is_refused(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys, "--type", "quantity",
                                "--unit", "USD")
    code = main(["resolve", str(request_path), "--outcome", "lots"])
    assert code == 2
    assert "outcome" in capsys.readouterr().err


def test_resolve_quantity_non_finite_is_refused(tmp_path, capsys):
    # float() happily parses 'nan' and 'inf', but neither is valid JSON —
    # a builder that cannot emit a bad wire file must refuse them.
    # (--outcome=-inf: the '=' form is how argparse takes dash-leading words.)
    request_path = make_request(tmp_path, capsys, "--type", "quantity",
                                "--unit", "USD")
    for raw in ("--outcome=nan", "--outcome=inf", "--outcome=-inf"):
        code = main(["resolve", str(request_path), raw])
        assert code == 2
        assert "outcome" in capsys.readouterr().err


def test_resolve_quantity_negative_number_works(tmp_path, capsys):
    # Plain `--outcome -3.2` must work: argparse's negative-number matcher
    # keeps real-world quantities (temperatures, deltas) usable.
    request_path = make_request(tmp_path, capsys, "--type", "quantity",
                                "--unit", "degC")
    code, out = resolve(capsys, str(request_path), "--outcome", "-3.2")
    assert code == 0
    assert json.loads(out)["outcome"] == -3.2


def test_resolve_note_is_kept(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    code, out = resolve(capsys, str(request_path), "--outcome", "no",
                        "--note", "No regrets.")
    assert code == 0
    assert json.loads(out)["note"] == "No regrets."


def test_resolve_resolved_at_is_utc_iso(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    _, out = resolve(capsys, str(request_path), "--outcome", "no")
    resolved_at = json.loads(out)["resolved_at"]
    assert resolved_at.endswith("Z")
    assert formats.parse_timestamp(resolved_at) is not None


def test_resolve_out_writes_a_file(tmp_path, capsys):
    request_path = make_request(tmp_path, capsys)
    target = tmp_path / "resolution.json"
    code = main(["resolve", str(request_path), "--outcome", "no",
                 "--out", str(target)])
    assert code == 0
    resolution = json.loads(target.read_text(encoding="utf-8"))
    assert formats.validate_message(resolution) == []


def test_resolve_unreadable_request_is_refused(tmp_path, capsys):
    code = main(["resolve", str(tmp_path / "nope.json"), "--outcome", "no"])
    assert code == 2
    assert "cannot read file" in capsys.readouterr().err


def test_readme_quickstart_pipeline_end_to_end(tmp_path, capsys):
    """The README's ask -> answer -> resolve -> score, exactly as printed
    (modulo shell redirection, which --out stands in for)."""
    request = tmp_path / "request.json"
    response = tmp_path / "response.json"
    resolution = tmp_path / "resolution.json"

    assert main(["ask", "--title", "Buy the vacation cabin?",
                 "--out", str(request)]) == 0
    assert main(["answer", str(request), "--backend", "echo",
                 "--out", str(response)]) == 0
    assert main(["resolve", str(request), "--outcome", "no",
                 "--out", str(resolution)]) == 0
    capsys.readouterr()

    assert main(["score", str(request), str(resolution), str(response)]) == 0
    table = capsys.readouterr().out
    assert "Brier" in table
