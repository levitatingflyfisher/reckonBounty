"""rb answer — the reference bot. Backends: echo (deterministic), claude-cli
(neutral cwd, strict JSON, one retry), openai:<base_url> (urllib only)."""

import json
import os
import tempfile
from types import SimpleNamespace

import pytest

from reckonbounty import backends, formats
from reckonbounty.cli import main

GOOD_JSON = json.dumps({
    "p": 0.42,
    "rationale": "A test rationale.",
    "base_rates": ["test base rate"],
    "key_uncertainties": ["test uncertainty"],
    "clarifying_questions": [],
})


# --- extract_json -------------------------------------------------------------


def test_extract_json_plain():
    assert backends.extract_json('{"p": 0.5}') == {"p": 0.5}


def test_extract_json_inside_code_fences():
    assert backends.extract_json('```json\n{"p": 0.5}\n```') == {"p": 0.5}


def test_extract_json_with_prose_around_it():
    text = 'Sure! Here is my forecast:\n{"p": 0.5}\nGood luck!'
    assert backends.extract_json(text) == {"p": 0.5}


def test_extract_json_garbage_raises():
    with pytest.raises(ValueError):
        backends.extract_json("I think it will probably happen.")


def test_extract_json_non_object_raises():
    with pytest.raises(ValueError):
        backends.extract_json("[0.5]")


# --- echo backend -------------------------------------------------------------


def test_echo_binary_is_deterministic(valid_request):
    first, _ = backends.generate(valid_request, "echo")
    second, _ = backends.generate(valid_request, "echo")
    assert first == second
    assert first["p"] == 0.5


def test_echo_multi_is_uniform(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["buy", "rent", "wait"]
    forecast, _ = backends.generate(valid_request, "echo")
    assert set(forecast["distribution"]) == {"buy", "rent", "wait"}
    assert sum(forecast["distribution"].values()) == pytest.approx(1.0)


def test_echo_quantity_has_the_three_quantiles(valid_request):
    valid_request["question"]["type"] = "quantity"
    valid_request["question"]["unit"] = "USD"
    forecast, _ = backends.generate(valid_request, "echo")
    assert list(forecast["quantiles"]) == ["p10", "p50", "p90"]


def test_echo_discloses_itself_as_not_a_model():
    _, disclosure = backends.generate(
        {"question": {"type": "binary", "title": "T?"}}, "echo"
    )
    assert "echo" in disclosure


# --- answer_request: the full BountyResponse ----------------------------------


def test_answer_request_emits_a_conforming_response(valid_request):
    response = backends.answer_request(valid_request, "echo")
    assert formats.validate_message(response) == []
    assert formats.forecast_shape_errors(response["forecast"],
                                         valid_request["question"]) == []
    assert response["request_id"] == valid_request["id"]
    assert response["bot"]["name"] == "rb-reference"
    assert "echo" in response["bot"]["model"]


def test_answer_request_custom_name_and_operator(valid_request):
    response = backends.answer_request(
        valid_request, "echo", name="myBot", operator="me"
    )
    assert response["bot"]["name"] == "myBot"
    assert response["bot"]["operator"] == "me"


def test_unknown_backend_is_a_usage_error(valid_request):
    with pytest.raises(ValueError, match="backend"):
        backends.generate(valid_request, "crystal-ball")


# --- prompt discipline ---------------------------------------------------------


def test_prompt_demands_strict_json_and_carries_the_question(valid_request):
    prompt = backends.build_prompt(valid_request)
    assert "JSON" in prompt
    assert valid_request["question"]["title"] in prompt
    assert '"p"' in prompt


def test_prompt_for_multi_lists_the_exact_options(valid_request):
    valid_request["question"]["type"] = "multi"
    valid_request["question"]["options"] = ["buy", "rent", "wait"]
    prompt = backends.build_prompt(valid_request)
    for option in ("buy", "rent", "wait"):
        assert option in prompt
    assert '"distribution"' in prompt


def test_prompt_forbids_reidentification(valid_request):
    # Spec §7 conduct travels with every LLM call.
    assert "re-identif" in backends.build_prompt(valid_request)


def test_retry_prompt_names_what_was_wrong(valid_request):
    prompt = backends.build_prompt(valid_request, retry_hint="not valid JSON")
    assert "not valid JSON" in prompt


# --- claude-cli backend --------------------------------------------------------


def test_claude_cli_runs_in_a_neutral_cwd(monkeypatch, valid_request):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout=GOOD_JSON, stderr="")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    forecast, disclosure = backends.generate(valid_request, "claude-cli")

    assert forecast["p"] == 0.42
    assert "claude" in disclosure
    assert seen["cmd"][0] == "claude"
    assert "-p" in seen["cmd"]
    # The neutral-cwd law: never the caller's project directory.
    assert seen["cwd"] is not None
    assert seen["cwd"] != os.getcwd()
    assert str(seen["cwd"]).startswith(tempfile.gettempdir())


def test_claude_cli_retries_once_then_succeeds(monkeypatch, valid_request):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        stdout = "I cannot answer in JSON, sorry." if len(calls) == 1 else GOOD_JSON
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    forecast, _ = backends.generate(valid_request, "claude-cli")
    assert forecast["p"] == 0.42
    assert len(calls) == 2


def test_claude_cli_fails_loudly_after_the_single_retry(monkeypatch, valid_request):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="still prose", stderr="")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    with pytest.raises(backends.BackendError):
        backends.generate(valid_request, "claude-cli")
    assert len(calls) == 2  # exactly one retry, never a loop


def test_claude_cli_nonzero_exit_is_a_backend_error(monkeypatch, valid_request):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="not logged in")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    with pytest.raises(backends.BackendError, match="not logged in"):
        backends.generate(valid_request, "claude-cli")


def test_claude_cli_rejects_conforming_json_with_wrong_shape(monkeypatch, valid_request):
    # Valid JSON but a quantity forecast for a binary question: retry, then fail.
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"quantiles": {"p10": 1, "p50": 2, "p90": 3}}),
            stderr="",
        )

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    with pytest.raises(backends.BackendError, match="forecast.p"):
        backends.generate(valid_request, "claude-cli")


def test_claude_cli_passes_the_timeout_through(monkeypatch, valid_request):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return SimpleNamespace(returncode=0, stdout=GOOD_JSON, stderr="")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    backends.generate(valid_request, "claude-cli", timeout=7)
    assert seen["timeout"] == 7


# --- openai-compatible backend -------------------------------------------------


class FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def openai_payload(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_openai_backend_posts_to_chat_completions(monkeypatch, valid_request):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode("utf-8"))
        seen["content_type"] = req.get_header("Content-type")
        return FakeHTTPResponse(openai_payload(GOOD_JSON))

    monkeypatch.setattr(backends, "urlopen", fake_urlopen)
    forecast, disclosure = backends.generate(
        valid_request, "openai:http://localhost:8080"
    )
    assert forecast["p"] == 0.42
    assert seen["url"] == "http://localhost:8080/v1/chat/completions"
    assert seen["content_type"] == "application/json"
    assert valid_request["question"]["title"] in seen["body"]["messages"][0]["content"]
    assert "localhost:8080" in disclosure


def test_openai_backend_tolerates_trailing_slash(monkeypatch, valid_request):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return FakeHTTPResponse(openai_payload(GOOD_JSON))

    monkeypatch.setattr(backends, "urlopen", fake_urlopen)
    backends.generate(valid_request, "openai:http://localhost:8080/")
    assert seen["url"] == "http://localhost:8080/v1/chat/completions"


def test_openai_backend_retries_once(monkeypatch, valid_request):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        content = "prose" if len(calls) == 1 else GOOD_JSON
        return FakeHTTPResponse(openai_payload(content))

    monkeypatch.setattr(backends, "urlopen", fake_urlopen)
    forecast, _ = backends.generate(valid_request, "openai:http://localhost:8080")
    assert forecast["p"] == 0.42
    assert len(calls) == 2


def test_openai_backend_network_error_is_a_backend_error(monkeypatch, valid_request):
    def fake_urlopen(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(backends, "urlopen", fake_urlopen)
    with pytest.raises(backends.BackendError, match="connection refused"):
        backends.generate(valid_request, "openai:http://localhost:8080")


def test_openai_backend_requires_a_base_url(valid_request):
    with pytest.raises(ValueError, match="base_url"):
        backends.generate(valid_request, "openai:")


# --- rb answer (CLI) -----------------------------------------------------------


def write_request(tmp_path, request):
    p = tmp_path / "request.json"
    p.write_text(json.dumps(request), encoding="utf-8")
    return str(p)


def test_cli_answer_echo_round_trips(tmp_path, valid_request, capsys):
    assert main(["answer", write_request(tmp_path, valid_request),
                 "--backend", "echo"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert formats.validate_message(response) == []
    assert response["request_id"] == valid_request["id"]


def test_cli_answer_writes_out_file(tmp_path, valid_request):
    target = tmp_path / "response.json"
    assert main(["answer", write_request(tmp_path, valid_request),
                 "--backend", "echo", "--out", str(target)]) == 0
    response = json.loads(target.read_text(encoding="utf-8"))
    assert formats.validate_message(response) == []


def test_cli_answer_politely_refuses_reserved_rails(tmp_path, valid_request, capsys):
    valid_request["bounty"]["rail"] = "x402"
    code = main(["answer", write_request(tmp_path, valid_request), "--backend", "echo"])
    assert code == 3
    err = capsys.readouterr().err
    assert "refus" in err  # refuse/refusing
    assert "x402" in err


def test_cli_answer_politely_refuses_reserved_tiers(tmp_path, valid_request, capsys):
    valid_request["privacy"]["tier"] = "attested"
    code = main(["answer", write_request(tmp_path, valid_request), "--backend", "echo"])
    assert code == 3
    assert "attested" in capsys.readouterr().err


def test_cli_answer_rejects_a_malformed_message_even_with_a_reserved_rail(
        tmp_path, capsys):
    # Spec §3: messages with missing mandatory fields MUST be rejected.
    # A polite refusal (exit 3) is for CONFORMING requests this v0 bot
    # chooses not to serve — garbage carrying bounty.rail 'x402' is not a
    # valid future-version request and must exit 2 like any other bad input.
    garbage = tmp_path / "garbage.json"
    garbage.write_text('{"bounty": {"rail": "x402"}}', encoding="utf-8")
    code = main(["answer", str(garbage), "--backend", "echo"])
    assert code == 2
    err = capsys.readouterr().err
    assert "refus" not in err
    assert "missing" in err  # names the missing mandatory fields


def test_cli_answer_rejects_invalid_request(tmp_path, valid_request, capsys):
    del valid_request["question"]
    code = main(["answer", write_request(tmp_path, valid_request), "--backend", "echo"])
    assert code == 2
    assert "question" in capsys.readouterr().err


def test_cli_answer_unknown_backend_is_a_usage_error(tmp_path, valid_request, capsys):
    code = main(["answer", write_request(tmp_path, valid_request),
                 "--backend", "crystal-ball"])
    assert code == 2
    assert "backend" in capsys.readouterr().err


def test_cli_answer_backend_failure_exits_4(tmp_path, valid_request, monkeypatch, capsys):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="never json", stderr="")

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    code = main(["answer", write_request(tmp_path, valid_request),
                 "--backend", "claude-cli"])
    assert code == 4
    assert "forecast" in capsys.readouterr().err.lower()


def test_cli_answer_custom_bot_name(tmp_path, valid_request, capsys):
    assert main(["answer", write_request(tmp_path, valid_request),
                 "--backend", "echo", "--name", "myBot"]) == 0
    assert json.loads(capsys.readouterr().out)["bot"]["name"] == "myBot"
