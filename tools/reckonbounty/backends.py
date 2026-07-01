"""The reference bot's three backends — echo, claude-cli, openai:<base_url>.

Shared discipline, regardless of backend:

  * the prompt demands ONE strict-JSON object in the §3.2 forecast shape and
    carries the §7 conduct rules (no re-identification, no persuasion);
  * the raw completion is parsed and validated; on failure there is exactly
    ONE retry with a hint naming what was wrong, then a loud BackendError —
    a malformed response is never emitted;
  * `claude -p` always runs with cwd set to a NEUTRAL temporary directory.
    The Claude CLI reads project context (CLAUDE.md, git state) from its
    working directory, and a forecast contaminated by whatever repo the
    asker happened to be sitting in is not a forecast.

Stdlib only: subprocess for the Claude CLI, urllib for HTTP (ADR-0003).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from . import SPEC_VERSION, formats

DEFAULT_TIMEOUT = 120.0
DEFAULT_BOT_NAME = "rb-reference"


class BackendError(RuntimeError):
    """The backend could not produce a conforming forecast."""


# --- Prompt -------------------------------------------------------------------

_SHAPES = {
    "binary": (
        '{"p": <number in [0,1]: probability the outcome resolves TRUE>,\n'
        ' "rationale": "<2-6 sentences of honest reasoning>",\n'
        ' "base_rates": ["<reference class you anchored on>", ...],\n'
        ' "key_uncertainties": ["<what could move this>", ...],\n'
        ' "clarifying_questions": ["<what you would ask the asker>", ...]}'
    ),
    "multi": (
        '{"distribution": {"<option>": <number in [0,1]>, ...},\n'
        ' "rationale": "<2-6 sentences of honest reasoning>",\n'
        ' "base_rates": [...], "key_uncertainties": [...],\n'
        ' "clarifying_questions": [...]}\n'
        "The distribution MUST contain exactly the listed options and sum to 1."
    ),
    "quantity": (
        '{"quantiles": {"p10": <number>, "p50": <number>, "p90": <number>},\n'
        ' "rationale": "<2-6 sentences of honest reasoning>",\n'
        ' "base_rates": [...], "key_uncertainties": [...],\n'
        ' "clarifying_questions": [...]}\n'
        "Quantiles MUST be non-decreasing: p10 <= p50 <= p90."
    ),
}


def build_prompt(request: dict, retry_hint: str | None = None) -> str:
    question = request["question"]
    qtype = question.get("type", "binary")

    lines = [
        "You are a forecasting bot answering a reckonBounty request — an open",
        "protocol for calibrated probabilistic advice on personal decisions.",
        "",
        f"Question type: {qtype}",
        f"Title: {question.get('title', '')}",
    ]
    if question.get("background"):
        lines.append(f"Background: {question['background']}")
    if qtype == "multi":
        lines.append(f"Options: {json.dumps(question.get('options', []))}")
    if qtype == "quantity":
        lines.append(f"Unit: {question.get('unit', '')}")
    resolution = question.get("resolution") or {}
    if resolution.get("criteria"):
        lines.append(f"Resolution criteria: {resolution['criteria']}")
    if resolution.get("horizon"):
        lines.append(f"Resolution horizon: {resolution['horizon']}")

    lines += [
        "",
        "Reply with ONE JSON object and NOTHING else — no prose before or",
        "after, no code fences. Required shape:",
        _SHAPES[qtype],
        "",
        "Conduct (normative, protocol §7): forecast with calibrated honesty;",
        "never attempt to re-identify the asker from a redacted question;",
        "no persuasion and no upselling in the rationale; answer the question",
        "that was asked.",
    ]
    if retry_hint:
        lines += [
            "",
            f"Your previous reply was rejected: {retry_hint}.",
            "Reply again with ONLY the JSON object.",
        ]
    return "\n".join(lines)


# --- Completion parsing --------------------------------------------------------


def extract_json(text: str) -> dict:
    """Pull one JSON object out of a completion; ValueError if there is none."""
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object found in backend output") from None
        try:
            parsed = json.loads(stripped[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"backend output is not valid JSON: {exc}") from None
    if not isinstance(parsed, dict):
        raise ValueError("backend output is not a JSON object")
    return parsed


# --- Backends ------------------------------------------------------------------


def _echo_forecast(request: dict) -> dict:
    """Deterministic maximum-entropy placeholder — plumbing, not advice."""
    question = request["question"]
    qtype = question.get("type", "binary")
    rationale = (
        "Deterministic echo backend: a fixed maximum-entropy placeholder "
        "forecast for tests and tutorials; not advice."
    )
    if qtype == "binary":
        return {"p": 0.5, "rationale": rationale}
    if qtype == "multi":
        options = question["options"]
        share = 1.0 / len(options)
        return {"distribution": {option: share for option in options},
                "rationale": rationale}
    return {"quantiles": {"p10": 0.0, "p50": 0.0, "p90": 0.0},
            "rationale": rationale}


def _invoke_claude(prompt: str, model: str | None, timeout: float) -> str:
    cmd = ["claude", "-p", prompt]
    if model:
        cmd += ["--model", model]
    # The neutral-cwd law — see the module docstring.
    with tempfile.TemporaryDirectory(prefix="rb-neutral-") as neutral_cwd:
        try:
            result = subprocess.run(
                cmd, cwd=neutral_cwd, capture_output=True, text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise BackendError(
                "claude CLI not found — install it or pick another backend"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise BackendError(f"claude -p timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise BackendError(
            f"claude -p failed (exit {result.returncode}): "
            f"{result.stderr.strip()[:500]}"
        )
    return result.stdout


def _invoke_openai(base_url: str, prompt: str, model: str | None,
                   timeout: float) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model or "default",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("RB_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if api_key:  # llamafile/Ollama need none; hosted endpoints might
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=json.dumps(payload).encode("utf-8"),
                      headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise BackendError(f"openai-compatible endpoint {url} failed: {exc}") from exc
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise BackendError(
            f"openai-compatible endpoint {url} returned an unexpected shape: "
            f"{str(body)[:300]}"
        ) from exc


def generate(request: dict, backend_spec: str, model: str | None = None,
             timeout: float = DEFAULT_TIMEOUT) -> tuple[dict, str]:
    """Produce (forecast, bot.model disclosure) for a request.

    Raises ValueError for an unknown backend spec (a usage error) and
    BackendError when a real backend cannot produce a conforming forecast.
    """
    if backend_spec == "echo":
        return _echo_forecast(request), "rb echo backend (deterministic placeholder)"

    if backend_spec == "claude-cli":
        def invoke(prompt: str) -> str:
            return _invoke_claude(prompt, model, timeout)
        disclosure = f"claude-cli (claude -p, model {model})" if model \
            else "claude-cli (claude -p, operator-default model)"
    elif backend_spec.startswith("openai:"):
        base_url = backend_spec[len("openai:"):]
        if not base_url:
            raise ValueError(
                "openai backend needs a base_url: --backend openai:<base_url>"
            )

        def invoke(prompt: str) -> str:
            return _invoke_openai(base_url, prompt, model, timeout)
        disclosure = f"openai-compatible endpoint {base_url}, model " \
            f"{model or 'endpoint default'}"
    else:
        raise ValueError(
            f"unknown backend {backend_spec!r} — use echo, claude-cli, "
            "or openai:<base_url>"
        )

    return _generate_llm(request, invoke), disclosure


def _generate_llm(request: dict, invoke) -> dict:
    """Call, parse, validate; exactly one retry with a hint; then fail loudly."""
    question = request["question"]
    prompt = build_prompt(request)
    last_error = ""
    for _attempt in range(2):
        raw = invoke(prompt)
        try:
            forecast = extract_json(raw)
        except ValueError as exc:
            last_error = str(exc)
        else:
            errors = formats.validate_forecast(forecast, question)
            if not errors:
                return forecast
            last_error = "; ".join(errors)
        prompt = build_prompt(request, retry_hint=last_error)
    raise BackendError(
        "backend did not produce a conforming forecast after one retry: "
        f"{last_error}"
    )


# --- Assembling the BountyResponse ----------------------------------------------


def answer_request(request: dict, backend_spec: str, *,
                   name: str = DEFAULT_BOT_NAME, operator: str = "anonymous",
                   model: str | None = None,
                   timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Answer a BountyRequest → a conforming BountyResponse (§3.2)."""
    forecast, disclosure = generate(request, backend_spec, model=model,
                                    timeout=timeout)
    response = {
        "reckonbounty": SPEC_VERSION,
        "kind": "response",
        "request_id": request["id"],
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bot": {
            "name": name,
            "operator": operator,
            "model": disclosure,  # §7: disclose the method, honestly
            "directory_url": None,
        },
        "forecast": forecast,
    }
    errors = formats.validate_message(response)
    if errors:  # a bug in this assembler — never ship a malformed response
        raise BackendError(
            "assembled an invalid response (bug): " + "; ".join(errors)
        )
    return response
