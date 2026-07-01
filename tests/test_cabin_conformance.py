"""The conformance anchor: examples/cabin/ IS spec §9 as real wire files.

This suite round-trips them through the CLI end to end. If it fails, either
the tools or the examples drifted from PROTOCOL.md — fix the drift, never
the assertion (AGENTS.md: the spec wins)."""

import json
import math
import shutil

from reckonbounty.cli import main

CABIN_FILES = (
    "request.json",
    "resolution.json",
    "response-hustlerbot.json",
    "response-cautiousbot.json",
)


def test_the_cabin_request_is_an_open_call(cabin_request):
    # The tutorial has strangers `rb answer` this request TODAY and score
    # the result ("Three rows now"). A hardcoded reply_by would silently
    # exclude every fresh response as late once the date passed — the
    # example must stay reproducible forever, so it is an open call.
    assert cabin_request["reply_by"] is None


def test_all_four_wire_files_validate(cabin_dir, capsys):
    argv = [str(cabin_dir / name) for name in CABIN_FILES]
    assert main(["validate", *argv]) == 0
    assert capsys.readouterr().out.count("OK") == 4


def test_score_reproduces_spec_section_9_to_4_decimals(cabin_dir, capsys):
    assert main([
        "score", "--json",
        str(cabin_dir / "request.json"),
        str(cabin_dir / "resolution.json"),
        str(cabin_dir / "response-hustlerbot.json"),
        str(cabin_dir / "response-cautiousbot.json"),
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    rows = {row["bot"]: row for row in report["rows"]}

    # The literal table: | hustlerBot80000 | 0.35 | 0.1225 | ln(0.65) |
    assert round(rows["hustlerBot80000"]["headline"], 4) == 0.35
    assert round(rows["hustlerBot80000"]["brier"], 4) == 0.1225
    assert round(rows["hustlerBot80000"]["log_score"], 4) == round(math.log(0.65), 4)
    assert round(rows["hustlerBot80000"]["log_score"], 4) == -0.4308

    # | cautiousBot | 0.20 | 0.0400 | ln(0.80) |
    assert round(rows["cautiousBot"]["headline"], 4) == 0.20
    assert round(rows["cautiousBot"]["brier"], 4) == 0.0400
    assert round(rows["cautiousBot"]["log_score"], 4) == round(math.log(0.80), 4)
    assert round(rows["cautiousBot"]["log_score"], 4) == -0.2231


def test_the_askers_row_from_spec_section_9(cabin_dir, tmp_path, capsys):
    # | the asker (recorded in Reckon) | 0.60 | 0.3600 | ln(0.40) | —
    # per-asker scoring uses the same formulas (§4), so a response carrying
    # the asker's own p must land exactly on the spec's third row.
    request = json.loads((cabin_dir / "request.json").read_text(encoding="utf-8"))
    asker = json.loads(
        (cabin_dir / "response-hustlerbot.json").read_text(encoding="utf-8")
    )
    asker["id"] = "0e0e0e0e-1111-4222-8333-444444444444"
    asker["bot"] = {"name": "the asker", "operator": "asker",
                    "model": "recorded in Reckon", "directory_url": None}
    asker["forecast"] = {"p": 0.60, "rationale": "The asker's own estimate."}
    asker_path = tmp_path / "response-asker.json"
    asker_path.write_text(json.dumps(asker), encoding="utf-8")

    assert main([
        "score", "--json",
        str(cabin_dir / "request.json"),
        str(cabin_dir / "resolution.json"),
        str(asker_path),
    ]) == 0
    row = json.loads(capsys.readouterr().out)["rows"][0]
    assert round(row["brier"], 4) == 0.3600
    assert round(row["log_score"], 4) == round(math.log(0.40), 4) == -0.9163


def test_full_protocol_loop_offline(cabin_dir, tmp_path, capsys):
    """The tutorial's arc: validate → answer (echo) → validate → score.
    No server, no account, no network — the whole v0 protocol."""
    workdir = tmp_path / "cabin"
    workdir.mkdir()
    for name in CABIN_FILES:
        shutil.copy(cabin_dir / name, workdir / name)

    mine = workdir / "my-response.json"
    assert main(["answer", str(workdir / "request.json"),
                 "--backend", "echo", "--out", str(mine)]) == 0
    assert main(["validate", str(mine)]) == 0
    capsys.readouterr()  # drain

    assert main([
        "score", "--json",
        str(workdir / "request.json"),
        str(workdir / "resolution.json"),
        str(workdir / "response-hustlerbot.json"),
        str(workdir / "response-cautiousbot.json"),
        str(mine),
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["excluded"] == []  # a fresh answer must never be "late"
    assert len(report["rows"]) == 3
    rows = {row["bot"]: row for row in report["rows"]}
    # echo says p=0.5; outcome false -> brier 0.25, log ln(0.5)
    assert round(rows["rb-reference"]["brier"], 4) == 0.25
    assert round(rows["rb-reference"]["log_score"], 4) == round(math.log(0.5), 4)
