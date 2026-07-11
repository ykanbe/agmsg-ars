#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


AGMSG = Path(os.environ.get("AGMSG_SKILL_DIR", "~/.agents/skills/agmsg")).expanduser()
API = AGMSG / "scripts" / "api.sh"
SEND = AGMSG / "scripts" / "send.sh"
IDENTITIES = AGMSG / "scripts" / "identities.sh"
DEFAULT_CLI_RUN_DIR = Path(os.environ.get("LLM_CLI_RUN_DIR", "~/.agents/llm_cli/run")).expanduser()


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


def wait_for_reply(team, sender, recipient, after_id, timeout, poll):
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = run_jsonl([str(API), "get", "teams", team, "messages", "--agent", sender, "--limit", "100"])
        for msg in rows:
            if int(msg["id"]) <= after_id:
                continue
            if msg["from"] == recipient and msg["to"] == sender:
                return msg
        time.sleep(poll)
    return None


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
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--poll", type=float, default=1.0)
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

    before = newest_message_id(args.team, args.sender)
    run_text([str(SEND), args.team, args.sender, args.recipient, prompt])
    reply = wait_for_reply(args.team, args.sender, args.recipient, before, args.timeout, args.poll)
    if reply is None:
        print(f"Timed out waiting for {args.recipient}", file=sys.stderr)
        return 1
    print(reply["body"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
