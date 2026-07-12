#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import urlopen


AGMSG = Path(os.environ.get("AGMSG_SKILL_DIR", "~/.agents/skills/agmsg")).expanduser()
API = AGMSG / "scripts" / "api.sh"
SEND = AGMSG / "scripts" / "send.sh"
IDENTITIES = AGMSG / "scripts" / "identities.sh"
DEFAULT_CLI_RUN_DIR = Path(os.environ.get("LLM_CLI_RUN_DIR", "~/.agents/llm_cli/run")).expanduser()
REQUEST_ID_RE = re.compile(r"<!--\s*agmsg-request-id:([0-9a-f]+)\s*-->", re.IGNORECASE)
APPROVAL_RE = re.compile(r"^(?:判定\s*[:：]\s*)?(?:注意して)?許可(?:してよい)?$|^問題なし$", re.IGNORECASE)
DENIAL_RE = re.compile(r"^(?:判定\s*[:：]\s*)?(?:拒否|不許可|禁止|中止)(?:してください)?$", re.IGNORECASE)


def add_request_id(text, request_id):
    return f"{text.rstrip()}\n\n<!-- agmsg-request-id:{request_id} -->"


def extract_request_id(text):
    match = REQUEST_ID_RE.search(text or "")
    return match.group(1).lower() if match else None


def strip_request_id(text):
    return REQUEST_ID_RE.sub("", text or "").strip()


def recipient_is_active(team, recipient, run_dir):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{team}-{recipient}.active")
    marker = run_dir / safe
    if not marker.exists():
        return False
    try:
        pid = int(marker.read_text(encoding="ascii").strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def run_jsonl(args):
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def run_text(args):
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return proc.stdout.strip()


def infer_team(project_path, sender):
    output = run_text([str(IDENTITIES), str(project_path), "codex"])
    teams = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2:
            continue
        team, agent = fields
        if agent == sender and team not in teams:
            teams.append(team)
    if len(teams) == 1:
        return teams[0]
    if not teams:
        raise ValueError(
            f"no AGMSG team found for sender {sender!r} in project {str(project_path)!r}; "
            "pass --team explicitly"
        )
    raise ValueError(
        f"multiple AGMSG teams found for sender {sender!r} in project {str(project_path)!r}: "
        f"{', '.join(teams)}; pass --team explicitly"
    )


def newest_message_id(team, agent):
    rows = run_jsonl([str(API), "get", "teams", team, "messages", "--agent", agent, "--limit", "1"])
    return int(rows[-1]["id"]) if rows else 0


def wait_for_reply(team, sender, recipient, after_id, request_id, timeout, poll):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = run_jsonl([str(API), "get", "teams", team, "messages", "--agent", sender, "--limit", "100"])
        for msg in rows:
            if int(msg["id"]) <= after_id:
                continue
            if (
                msg["from"] == recipient
                and msg["to"] == sender
                and extract_request_id(msg["body"]) == request_id
            ):
                return msg
        time.sleep(poll)
    return None


def bridge_is_running(path, max_age):
    try:
        return time.time() - path.stat().st_mtime <= max_age
    except FileNotFoundError:
        return False


def approval_result(body):
    lines = [line.strip() for line in strip_request_id(body).splitlines() if line.strip()]
    if not lines:
        return None
    decision_line = lines[0]
    if DENIAL_RE.search(decision_line):
        return False
    if APPROVAL_RE.search(decision_line):
        return True
    return None


def backend_is_running(url, timeout):
    if not url:
        return True
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def main(
    *,
    default_sender="Codex",
    default_recipient="LLM-review",
    allowed_recipients=None,
    active_recipient=None,
    active_marker_dir=None,
):
    parser = argparse.ArgumentParser(description="Ask an LLM agent through AGMSG and print the reply.")
    parser.add_argument("prompt", nargs="*", help="Prompt text. If omitted, stdin is used.")
    parser.add_argument("--team", default=os.environ.get("AGMSG_TEAM", ""))
    parser.add_argument("--from", dest="sender", default=os.environ.get("LLM_SENDER", default_sender))
    parser.add_argument("--to", dest="recipient", default=os.environ.get("LLM_RECIPIENT", default_recipient))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("LLM_REPLY_TIMEOUT", "300")))
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--approval", action="store_true", help="Fail closed unless the reviewer explicitly approves.")
    parser.add_argument(
        "--bridge-heartbeat",
        type=Path,
        default=Path(os.environ.get("LLM_BRIDGE_HEARTBEAT", "~/.agents/agmsg_llm/state/bridge.heartbeat")).expanduser(),
    )
    parser.add_argument("--bridge-max-age", type=float, default=float(os.environ.get("LLM_BRIDGE_MAX_AGE", "15")))
    parser.add_argument("--backend-health-url", default=os.environ.get("LLM_BACKEND_HEALTH_URL", ""))
    parser.add_argument("--backend-health-timeout", type=float, default=2.0)
    parser.add_argument(
        "--active-marker-dir",
        type=Path,
        default=active_marker_dir or DEFAULT_CLI_RUN_DIR,
        help="Directory containing <team>-<agent>.active markers for interactive agents.",
    )
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("ask_llm.py: prompt is empty", file=sys.stderr)
        return 2
    if allowed_recipients is not None and args.recipient not in allowed_recipients:
        allowed = ", ".join(sorted(allowed_recipients))
        print(
            f"ask_llm.py: unknown recipient {args.recipient!r}; use one of: {allowed}",
            file=sys.stderr,
        )
        return 2
    if not args.team:
        try:
            args.team = infer_team(Path.cwd(), args.sender)
        except (subprocess.CalledProcessError, ValueError) as exc:
            print(f"ask_llm.py: {exc}", file=sys.stderr)
            return 2
    if active_recipient and args.recipient == active_recipient and not recipient_is_active(
        args.team, args.recipient, args.active_marker_dir.expanduser()
    ):
        print(
            f"ask_llm.py: {args.recipient} is interactive. Start its pane in this team first, "
            f"or use {default_recipient}.",
            file=sys.stderr,
        )
        return 1
    if args.approval and not bridge_is_running(args.bridge_heartbeat, args.bridge_max_age):
        print(
            f"Approval denied: {args.recipient} bridge is not running "
            f"(heartbeat missing or older than {args.bridge_max_age:g}s)",
            file=sys.stderr,
        )
        return 3
    if args.approval and not backend_is_running(args.backend_health_url, args.backend_health_timeout):
        print(
            f"Approval denied: {args.recipient} model backend is not running "
            f"({args.backend_health_url})",
            file=sys.stderr,
        )
        return 3

    before = newest_message_id(args.team, args.sender)
    request_id = uuid.uuid4().hex
    run_text([str(SEND), args.team, args.sender, args.recipient, add_request_id(prompt, request_id)])
    reply = wait_for_reply(
        args.team,
        args.sender,
        args.recipient,
        before,
        request_id,
        args.timeout,
        args.poll,
    )
    if reply is None:
        label = "Approval denied" if args.approval else "Timed out"
        print(f"{label}: timed out waiting for {args.recipient}", file=sys.stderr)
        return 4 if args.approval else 1
    if args.approval:
        decision = approval_result(reply["body"])
        if decision is not True:
            reason = "reviewer rejected the action" if decision is False else "reviewer reply was not an explicit approval"
            print(f"Approval denied: {reason}", file=sys.stderr)
            print(strip_request_id(reply["body"]), file=sys.stderr)
            return 5
    print(strip_request_id(reply["body"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
