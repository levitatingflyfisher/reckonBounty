"""The `rb` command line: ask / answer / resolve / score / validate.

Exit codes, uniform across subcommands:
  0  success
  1  validation found problems (rb validate)
  2  bad input (unreadable file, malformed message, wrong flags)
  3  polite refusal (reserved bounty rail or privacy tier — spec §3.1/§5)
  4  backend failure (rb answer could not obtain a conforming forecast)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from . import __version__, backends, formats, scoring


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rb",
        description="Reference tools for the reckonBounty protocol "
        "(spec: docs/spec/PROTOCOL.md).",
    )
    parser.add_argument("--version", action="version", version=f"rb {__version__}")
    sub = parser.add_subparsers(dest="cmd", metavar="command")

    p_ask = sub.add_parser(
        "ask",
        help="build a BountyRequest from flags",
        description="Build a conforming BountyRequest. Redaction is YOUR job "
        "and happens before this tool: write the title/background already "
        "de-identified (that is what the default tier 'redacted' asserts), "
        "or pass --tier public.",
    )
    p_ask.add_argument("--title", required=True, help="the decision question")
    p_ask.add_argument("--background", default=None,
                       help="de-identified context for forecasters")
    p_ask.add_argument("--type", choices=formats.QUESTION_TYPES, default="binary",
                       dest="qtype")
    p_ask.add_argument("--option", action="append", dest="options", metavar="TEXT",
                       help="answer option (repeat 2-16 times; multi only)")
    p_ask.add_argument("--unit", default=None, help="unit of measure (quantity only)")
    p_ask.add_argument("--reply-by", default=None, dest="reply_by",
                       help="ISO-8601 deadline; omit for an open call")
    p_ask.add_argument("--criteria", default=None,
                       help="how the question will be resolved")
    p_ask.add_argument("--horizon", default=None,
                       help="when the question will be resolved (date)")
    p_ask.add_argument("--resolver", default="asker",
                       help="who resolves (default: asker — that is the point)")
    p_ask.add_argument("--tier", choices=("public", "redacted"), default="redacted",
                       help="privacy tier (attested/fhe are reserved, spec §5)")
    p_ask.add_argument("--out", default=None, metavar="FILE",
                       help="write here instead of stdout")
    p_ask.set_defaults(func=cmd_ask)

    p_answer = sub.add_parser(
        "answer",
        help="answer a BountyRequest (the reference bot)",
        description="Generate a conforming BountyResponse. Backends: echo "
        "(deterministic placeholder), claude-cli (shells out to `claude -p` "
        "in a neutral temp directory), openai:<base_url> (any OpenAI-"
        "compatible /v1/chat/completions — llamafile, Ollama). LLM output is "
        "validated with one retry; a malformed response is never emitted.",
    )
    p_answer.add_argument("request", metavar="request.json")
    p_answer.add_argument("--backend", default="echo",
                          help="echo | claude-cli | openai:<base_url> "
                          "(default: echo)")
    p_answer.add_argument("--name", default=backends.DEFAULT_BOT_NAME,
                          help="your bot's stable name — it IS its track record")
    p_answer.add_argument("--operator", default="anonymous")
    p_answer.add_argument("--model", default=None,
                          help="model hint passed to the backend")
    p_answer.add_argument("--timeout", type=float, default=backends.DEFAULT_TIMEOUT,
                          help="backend timeout in seconds")
    p_answer.add_argument("--out", default=None, metavar="FILE",
                          help="write here instead of stdout")
    p_answer.set_defaults(func=cmd_answer)

    p_resolve = sub.add_parser(
        "resolve",
        help="record a request's outcome as a BountyResolution",
        description="Build a conforming BountyResolution bound to the "
        "request's id — nobody should have to open a JSON file to copy a "
        "uuid. The outcome is checked against the request's question type: "
        "yes/no/true/false (binary), one of the request's options (multi), "
        "a number (quantity), or 'void' to cancel scoring (spec §3.3).",
    )
    p_resolve.add_argument("request", metavar="request.json")
    p_resolve.add_argument("--outcome", required=True,
                           help="yes|no|true|false (binary), an option "
                           "(multi), a number (quantity), or 'void'")
    p_resolve.add_argument("--note", default=None,
                           help="what actually happened, for the record")
    p_resolve.add_argument("--out", default=None, metavar="FILE",
                           help="write here instead of stdout")
    p_resolve.set_defaults(func=cmd_resolve)

    p_score = sub.add_parser(
        "score",
        help="score responses against a resolution",
        description="Score every eligible response with the spec §4 formulas: "
        "Brier + log score (binary/multi) or mean pinball loss (quantity). "
        "Late responses are excluded; duplicate bot names keep the latest "
        "response before the deadline; a 'void' resolution cancels scoring.",
    )
    p_score.add_argument("request", metavar="request.json")
    p_score.add_argument("resolution", metavar="resolution.json")
    p_score.add_argument("responses", nargs="+", metavar="response.json")
    p_score.add_argument("--json", action="store_true", dest="as_json",
                         help="machine-readable report on stdout")
    p_score.set_defaults(func=cmd_score)

    p_validate = sub.add_parser(
        "validate",
        help="check messages against the spec (§3)",
        description="Validate protocol messages: unknown fields pass "
        "(forward compatibility), missing/malformed mandatory fields fail "
        "with a precise message.",
    )
    p_validate.add_argument("files", nargs="+", metavar="file.json")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def _reject_json_constant(name: str) -> float:
    # Python's json module accepts NaN/Infinity by default; RFC 8259 (and
    # spec §3's "UTF-8 JSON") does not. Letting them through poisons scores
    # (a NaN Brier makes every track-record mean NaN) and makes our own
    # --json output unparseable to strict clients.
    raise ValueError(f"{name} is not a JSON value (spec §3: UTF-8 JSON)")


def load_message(path: str) -> tuple[dict | None, str | None]:
    """Read one message file → (message, error). Exactly one side is None."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read file: {exc}"
    try:
        # ValueError covers JSONDecodeError and the constant rejection.
        return json.loads(text, parse_constant=_reject_json_constant), None
    except ValueError as exc:
        return None, f"not valid JSON: {exc}"


def cmd_ask(args: argparse.Namespace) -> int:
    import uuid
    from datetime import datetime, timezone

    if not args.title.strip():
        print("rb ask: --title must not be empty", file=sys.stderr)
        return 2
    if args.options and args.qtype != "multi":
        print("rb ask: --option only makes sense with --type multi", file=sys.stderr)
        return 2
    if args.qtype == "multi" and not (args.options and 2 <= len(args.options) <= 16):
        print("rb ask: --type multi needs 2 to 16 --option flags", file=sys.stderr)
        return 2
    if args.options and any(not option for option in args.options):
        print("rb ask: --option values must not be empty", file=sys.stderr)
        return 2
    if args.options and len(set(args.options)) != len(args.options):
        print("rb ask: --option values must be distinct (a duplicate option "
              "cannot be told apart in the scored distribution)",
              file=sys.stderr)
        return 2
    if args.qtype == "quantity" and not args.unit:
        print("rb ask: --type quantity needs --unit", file=sys.stderr)
        return 2
    if args.reply_by is not None and formats.parse_timestamp(args.reply_by) is None:
        print(f"rb ask: --reply-by {args.reply_by!r} is not an ISO-8601 timestamp",
              file=sys.stderr)
        return 2

    question: dict = {"type": args.qtype, "title": args.title}
    if args.background:
        question["background"] = args.background
    if args.qtype == "multi":
        question["options"] = args.options
    if args.qtype == "quantity":
        question["unit"] = args.unit
    if args.criteria or args.horizon:
        resolution = {"resolver": args.resolver}
        if args.criteria:
            resolution["criteria"] = args.criteria
        if args.horizon:
            resolution["horizon"] = args.horizon
        question["resolution"] = resolution

    privacy: dict = {"tier": args.tier}
    if args.tier == "redacted":
        # The asker composed the flags themselves — manual redaction (§5).
        privacy["redaction"] = "manual"

    request = {
        "reckonbounty": "0.1",
        "kind": "request",
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reply_by": args.reply_by,
        "privacy": privacy,
        "question": question,
        "bounty": {"rail": "none", "terms": "per-answer", "amount": "0",
                   "currency": "none"},
        "client": {"app": "rb", "version": __version__},
    }

    errors = formats.validate_message(request)
    if errors:  # a bug in this builder, not in the user's flags — fail loudly
        for error in errors:
            print(f"rb ask: built an invalid request: {error}", file=sys.stderr)
        return 2

    return _emit(request, args.out)


def _emit(message: dict, out: str | None) -> int:
    text = json.dumps(message, indent=2, ensure_ascii=False) + "\n"
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    msg, load_error = load_message(args.request)
    if load_error:
        print(f"{args.request}: {load_error}", file=sys.stderr)
        return 2

    # Validation FIRST (spec §3: missing mandatory fields MUST be rejected),
    # refusals second. A polite refusal (3) is for CONFORMING messages this
    # v0 bot chooses not to serve — a reserved rail/tier on garbage must not
    # promote it past the malformed-input exit (2). The one validator error
    # a reserved rail itself produces is set aside so an otherwise
    # conforming future-rail request still lands on the refusal path.
    rail = None
    tier = None
    if isinstance(msg, dict):
        if isinstance(msg.get("bounty"), dict):
            rail = msg["bounty"].get("rail")
        if isinstance(msg.get("privacy"), dict):
            tier = msg["privacy"].get("tier")
    reserved_rail = isinstance(rail, str) and rail != "none"

    errors = formats.validate_message(msg)
    if reserved_rail:
        errors = [e for e in errors
                  if not (e.startswith("bounty.rail:") and "reserved" in e)]
    if errors:
        for error in errors:
            print(f"{args.request}: {error}", file=sys.stderr)
        return 2
    if msg.get("kind") != "request":
        print(
            f"{args.request}: expected a request, got kind={msg.get('kind')!r}",
            file=sys.stderr,
        )
        return 2

    if reserved_rail:
        print(
            f"rb answer: politely refusing — bounty.rail {rail!r} is "
            "reserved for a future version; this v0 bot serves only rail "
            "'none' (spec §3.1)",
            file=sys.stderr,
        )
        return 3
    if tier in ("attested", "fhe"):
        print(
            f"rb answer: politely refusing — privacy tier {tier!r} is "
            "reserved (spec §5); this reference bot serves 'public' and "
            "'redacted'",
            file=sys.stderr,
        )
        return 3

    request = msg
    try:
        response = backends.answer_request(
            request, args.backend, name=args.name, operator=args.operator,
            model=args.model, timeout=args.timeout,
        )
    except ValueError as exc:  # unknown backend spec — a usage error
        print(f"rb answer: {exc}", file=sys.stderr)
        return 2
    except backends.BackendError as exc:
        print(f"rb answer: {exc}", file=sys.stderr)
        return 4

    return _emit(response, args.out)


def _load_checked(path: str, expected_kind: str) -> tuple[dict | None, int]:
    """Load + validate one scoring input; returns (message, exit_code)."""
    msg, load_error = load_message(path)
    if load_error:
        print(f"{path}: {load_error}", file=sys.stderr)
        return None, 2
    errors = formats.validate_message(msg)
    if errors:
        for error in errors:
            print(f"{path}: {error}", file=sys.stderr)
        return None, 2
    if msg.get("kind") != expected_kind:
        print(
            f"{path}: expected a {expected_kind} in this position, got kind="
            f"{msg.get('kind')!r}",
            file=sys.stderr,
        )
        return None, 2
    return msg, 0


def cmd_resolve(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    request, rc = _load_checked(args.request, "request")
    if rc:
        return rc

    outcome, outcome_error = _parse_outcome(args.outcome, request["question"])
    if outcome_error:
        print(f"rb resolve: {outcome_error}", file=sys.stderr)
        return 2

    resolution: dict = {
        "reckonbounty": "0.1",
        "kind": "resolution",
        "request_id": request["id"],
        "resolved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome,
    }
    if args.note:
        resolution["note"] = args.note

    errors = formats.validate_message(resolution)
    if errors:  # a bug in this builder, not in the user's flags — fail loudly
        for error in errors:
            print(f"rb resolve: built an invalid resolution: {error}",
                  file=sys.stderr)
        return 2

    return _emit(resolution, args.out)


def _parse_outcome(raw: str, question: dict) -> tuple[object, str | None]:
    """CLI word → typed outcome for this question. Exactly one side is None."""
    if raw == "void":
        return "void", None
    qtype = question.get("type")
    if qtype == "binary":
        word = raw.lower()
        if word in ("yes", "true"):
            return True, None
        if word in ("no", "false"):
            return False, None
        return None, (f"--outcome {raw!r}: binary questions resolve to "
                      "yes/no/true/false (or 'void')")
    if qtype == "multi":
        options = question.get("options", [])
        if raw in options:
            return raw, None
        return None, (f"--outcome {raw!r}: must be one of the request's "
                      f"options {options} (or 'void')")
    # quantity
    try:
        number = float(raw)
    except ValueError:
        return None, (f"--outcome {raw!r}: quantity questions resolve to a "
                      "number (or 'void')")
    if not math.isfinite(number):
        return None, (f"--outcome {raw!r}: quantity outcomes must be finite "
                      "— nan/inf are not JSON numbers")
    return int(number) if number.is_integer() else number, None


def cmd_score(args: argparse.Namespace) -> int:
    request, rc = _load_checked(args.request, "request")
    if rc:
        return rc
    resolution, rc = _load_checked(args.resolution, "resolution")
    if rc:
        return rc
    responses = []
    for path in args.responses:
        response, rc = _load_checked(path, "response")
        if rc:
            return rc
        responses.append(response)

    try:
        report = scoring.score_bounty(request, resolution, responses)
    except scoring.ScoringError as exc:
        print(f"rb score: {exc}", file=sys.stderr)
        return 2

    for bot, reason in report.excluded:
        print(f"excluded {bot}: {reason}", file=sys.stderr)

    if args.as_json:
        print(json.dumps({
            "request_id": report.request_id,
            "question_type": report.question_type,
            "void": report.void,
            "rows": [
                {"bot": row.bot, "created_at": row.created_at,
                 "headline": row.headline, **row.scores}
                for row in report.rows
            ],
            "excluded": [{"bot": bot, "reason": reason}
                         for bot, reason in report.excluded],
        }, indent=2))
        return 0

    if report.void:
        print("Resolution is void — scoring cancelled for this request (spec §3.3).")
        return 0

    print(_format_table(report))
    return 0


def _format_table(report: scoring.ScoreReport) -> str:
    if report.question_type == "quantity":
        header = ["Bot", "p50", "Pinball"]
        lines = [[row.bot, f"{row.headline:g}", f"{row.scores['pinball']:.4f}"]
                 for row in report.rows]
    else:
        label = "p(yes)" if report.question_type == "binary" else "p(winner)"
        header = ["Bot", label, "Brier", "Log score"]
        lines = [[row.bot, f"{row.headline:.2f}", f"{row.scores['brier']:.4f}",
                  f"{row.scores['log_score']:.4f}"]
                 for row in report.rows]
    widths = [max(len(cell) for cell in column) for column in zip(header, *lines)]
    rendered = ["  ".join(cell.ljust(w) for cell, w in zip(line, widths)).rstrip()
                for line in [header, *lines]]
    return "\n".join(rendered)


def cmd_validate(args: argparse.Namespace) -> int:
    # Exit codes follow the module contract: an unreadable or non-JSON file
    # is BAD INPUT (2) — the same condition every other subcommand reports
    # as 2 — while 1 is reserved for messages that parsed but violate the
    # spec. A load error anywhere outranks validation failures.
    load_failures = 0
    spec_failures = 0
    for path in args.files:
        msg, load_error = load_message(path)
        if load_error:
            load_failures += 1
            print(f"{path}: {load_error}", file=sys.stderr)
            continue
        errors = formats.validate_message(msg)
        if errors:
            spec_failures += 1
            for error in errors:
                print(f"{path}: {error}", file=sys.stderr)
        else:
            print(f"{path}: OK ({msg.get('kind')})")
    if load_failures:
        return 2
    return 1 if spec_failures else 0


def _not_implemented(args: argparse.Namespace) -> int:  # pragma: no cover
    print(f"rb {args.cmd}: not implemented yet", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "cmd", None) is None:
        parser.print_usage(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
