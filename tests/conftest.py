"""Shared fixtures. Adds tools/ to sys.path so tests run without an install."""

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

CABIN = REPO_ROOT / "examples" / "cabin"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def cabin_dir() -> Path:
    return CABIN


@pytest.fixture
def cabin_request() -> dict:
    return load(CABIN / "request.json")


@pytest.fixture
def cabin_resolution() -> dict:
    return load(CABIN / "resolution.json")


@pytest.fixture
def cabin_responses() -> list[dict]:
    return [
        load(CABIN / "response-hustlerbot.json"),
        load(CABIN / "response-cautiousbot.json"),
    ]


# --- Minimal valid messages (deep-copied per test so mutation is safe) ------

_REQUEST = {
    "reckonbounty": "0.1",
    "kind": "request",
    "id": "11111111-2222-4333-8444-555566667777",
    "created_at": "2026-07-11T06:30:00Z",
    "reply_by": "2026-07-18T00:00:00Z",
    "privacy": {"tier": "redacted", "redaction": "manual"},
    "question": {
        "type": "binary",
        "title": "Buy the vacation cabin?",
        "background": "A de-identified background.",
        "resolution": {
            "criteria": "Asker records a yes/no judgment after 12 months.",
            "horizon": "2027-08-01",
            "resolver": "asker",
        },
    },
    "bounty": {"rail": "none", "terms": "per-answer", "amount": "0", "currency": "none"},
    "client": {"app": "rb", "version": "0.1.0"},
}

_RESPONSE = {
    "reckonbounty": "0.1",
    "kind": "response",
    "request_id": "11111111-2222-4333-8444-555566667777",
    "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeffff0000",
    "created_at": "2026-07-12T07:02:00Z",
    "bot": {
        "name": "testBot",
        "operator": "anonymous",
        "model": "test fixture",
        "directory_url": None,
    },
    "forecast": {"p": 0.35, "rationale": "Fixture rationale."},
}

_RESOLUTION = {
    "reckonbounty": "0.1",
    "kind": "resolution",
    "request_id": "11111111-2222-4333-8444-555566667777",
    "resolved_at": "2027-08-02T14:00:00Z",
    "outcome": False,
    "note": "Fixture note.",
}

_DIRECTORY = {
    "reckonbounty": "0.1",
    "kind": "directory",
    "bots": [
        {
            "name": "rb-reference",
            "endpoint": None,
            "transport": "file",
            "tiers": ["public", "redacted"],
            "pricing": None,
            "operator": "reckonBounty project",
            "model": "configurable",
            "notes": "Reference implementation.",
        }
    ],
}


@pytest.fixture
def valid_request() -> dict:
    return copy.deepcopy(_REQUEST)


@pytest.fixture
def valid_response() -> dict:
    return copy.deepcopy(_RESPONSE)


@pytest.fixture
def valid_resolution() -> dict:
    return copy.deepcopy(_RESOLUTION)


@pytest.fixture
def valid_directory() -> dict:
    return copy.deepcopy(_DIRECTORY)
