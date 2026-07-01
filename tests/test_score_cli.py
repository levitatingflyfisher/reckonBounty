"""rb score at the CLI seam: the tutorial's exact table, --json for machines,
and precise failures on contract violations."""

import json

from reckonbounty.cli import main


def write(tmp_path, name, msg):
    p = tmp_path / name
    p.write_text(json.dumps(msg), encoding="utf-8")
    return str(p)


def cabin_argv(cabin_dir):
    return [
        str(cabin_dir / "request.json"),
        str(cabin_dir / "resolution.json"),
        str(cabin_dir / "response-hustlerbot.json"),
        str(cabin_dir / "response-cautiousbot.json"),
    ]


def test_score_reproduces_the_spec_table_to_4_decimals(cabin_dir, capsys):
    assert main(["score", *cabin_argv(cabin_dir)]) == 0
    out = capsys.readouterr().out
    for needle in ("hustlerBot80000", "0.35", "0.1225", "-0.4308",
                   "cautiousBot", "0.20", "0.0400", "-0.2231"):
        assert needle in out, f"{needle!r} missing from table:\n{out}"


def test_score_json_output_for_machines(cabin_dir, capsys):
    assert main(["score", "--json", *cabin_argv(cabin_dir)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["question_type"] == "binary"
    assert report["void"] is False
    rows = {row["bot"]: row for row in report["rows"]}
    assert round(rows["hustlerBot80000"]["brier"], 4) == 0.1225
    assert round(rows["cautiousBot"]["log_score"], 4) == -0.2231


def test_score_void_resolution_prints_cancellation(
    tmp_path, valid_request, valid_resolution, valid_response, capsys
):
    valid_resolution["outcome"] = "void"
    argv = [
        write(tmp_path, "request.json", valid_request),
        write(tmp_path, "resolution.json", valid_resolution),
        write(tmp_path, "response.json", valid_response),
    ]
    assert main(["score", *argv]) == 0
    assert "void" in capsys.readouterr().out.lower()


def test_score_notes_excluded_late_responses_on_stderr(
    tmp_path, valid_request, valid_resolution, valid_response, capsys
):
    valid_response["created_at"] = "2026-07-19T00:00:00Z"  # after reply_by
    valid_response["bot"]["name"] = "lateBot"
    argv = [
        write(tmp_path, "request.json", valid_request),
        write(tmp_path, "resolution.json", valid_resolution),
        write(tmp_path, "response.json", valid_response),
    ]
    assert main(["score", *argv]) == 0
    captured = capsys.readouterr()
    assert "lateBot" in captured.err
    assert "late" in captured.err


def test_score_rejects_wrong_kind_in_position(
    tmp_path, valid_request, valid_resolution, capsys
):
    request = write(tmp_path, "request.json", valid_request)
    resolution = write(tmp_path, "resolution.json", valid_resolution)
    # resolution where a response should be
    assert main(["score", request, resolution, resolution]) == 2
    assert "response" in capsys.readouterr().err


def test_score_rejects_invalid_message_files(
    tmp_path, valid_request, valid_resolution, valid_response, capsys
):
    del valid_response["forecast"]
    argv = [
        write(tmp_path, "request.json", valid_request),
        write(tmp_path, "resolution.json", valid_resolution),
        write(tmp_path, "response.json", valid_response),
    ]
    assert main(["score", *argv]) == 2
    assert "forecast" in capsys.readouterr().err


def test_score_rejects_foreign_response(
    tmp_path, valid_request, valid_resolution, valid_response, capsys
):
    valid_response["request_id"] = "some-other-question"
    argv = [
        write(tmp_path, "request.json", valid_request),
        write(tmp_path, "resolution.json", valid_resolution),
        write(tmp_path, "response.json", valid_response),
    ]
    assert main(["score", *argv]) == 2
    assert "request_id" in capsys.readouterr().err
