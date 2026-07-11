#!/usr/bin/env python3
"""Interactive AGMSG local-LLM client with in-process chat context."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
AGMSG = Path(os.environ.get("AGMSG_SKILL_DIR", "~/.agents/skills/agmsg")).expanduser()
API = AGMSG / "scripts" / "api.sh"
SEND = AGMSG / "scripts" / "send.sh"
RUN_DIR = Path(os.environ.get("LLM_CLI_RUN_DIR", "~/.agents/llm_cli/run")).expanduser()
EVENT_RE = re.compile(
    r"^\[agmsg\] New message in team (?P<team>.+?) from (?P<sender>.+?) to (?P<recipient>.+?)\."
)

BASE_SYSTEM_PROMPT = """You are an interactive local LLM member in an AGMSG team.
Reply in concise Japanese. You are a conversation partner and a lightweight coding helper.
You cannot operate files, commands, or external services directly. Keep the current
conversation coherent, but do not claim long-term memory after this CLI session ends.
"""


def run_jsonl(args: list[str]) -> list[dict]:
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def run_text(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return proc.stdout.strip()


def persona_path() -> Path | None:
    raw = os.environ.get("LLM_PERSONA", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None


def system_prompt(team: str, agent: str, persona: Path | None) -> str:
    parts = [BASE_SYSTEM_PROMPT, f"\nTeam: {team}\nAGMSG name: {agent}\n"]
    if persona:
        parts.extend(["\n# Persona and Training Notes\n", persona.read_text(encoding="utf-8")])
    return "".join(parts)


def call_openai_compatible(base_url: str, model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=600) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def newest_message(team: str, agent: str, sender: str) -> dict | None:
    rows = run_jsonl([str(API), "get", "teams", team, "messages", "--agent", agent, "--limit", "80"])
    matches = [row for row in rows if row.get("to") == agent and row.get("from") == sender]
    return max(matches, key=lambda row: int(row["id"])) if matches else None


def marker_path(team: str, agent: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{team}-{agent}.active")
    return RUN_DIR / safe


def write_marker(team: str, agent: str) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    path = marker_path(team, agent)
    path.write_text(str(os.getpid()) + "\n", encoding="ascii")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive local LLM AGMSG client")
    parser.add_argument("boot_prompt", nargs="*", help=argparse.SUPPRESS)
    parser.add_argument("--team", default="")
    parser.add_argument("--agent", default=os.environ.get("LLM_AGENT", "LLM"))
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8081/v1"))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", "local-model"))
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()

    if not args.team:
        print(f"LLM CLI is ready. Send an AGMSG message to {args.agent} from the chat composer.")
    persona = persona_path()
    # One pane is one temporary conversation. It deliberately has no
    # per-sender, per-team, or on-disk memory, and ends when the pane closes.
    history: list[dict] = []
    handled_ids: set[int] = set()
    markers: list[Path] = []

    def clear_markers() -> None:
        for marker in markers:
            marker.unlink(missing_ok=True)

    atexit.register(clear_markers)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))

    if args.team:
        markers.append(write_marker(args.team, args.agent))

    def reply(team: str, sender: str, body: str, message_id: int | None = None) -> None:
        nonlocal history
        if body.strip() in {"/reset", "リセット"}:
            history = []
            response = "この会話の直近文脈をリセットしました。"
        else:
            messages = [
                {"role": "system", "content": system_prompt(team, args.agent, persona)},
                *history,
            ]
            messages.append({"role": "user", "content": body})
            response = call_openai_compatible(args.base_url, args.model, messages, args.temperature, args.max_tokens)
            history.extend(
                [
                    {"role": "user", "content": body},
                    {"role": "assistant", "content": response},
                ]
            )
        run_text([str(SEND), team, args.agent, sender, response])
        if message_id is not None:
            handled_ids.add(message_id)
        print(f"reply -> {team}:{sender}: {response}")

    def handle_event(raw: str) -> bool:
        match = EVENT_RE.match(raw.strip())
        if not match or match.group("recipient") != args.agent:
            return False
        team = match.group("team")
        sender = match.group("sender")
        message = newest_message(team, args.agent, sender)
        if message is None:
            print(f"No matching AGMSG message found for {team}:{sender}.")
            return True
        message_id = int(message["id"])
        if message_id not in handled_ids:
            reply(team, sender, message["body"], message_id)
        return True

    print(f"LLM CLI ready as {args.agent}. It keeps this conversation until the pane closes.")
    for raw in sys.stdin:
        line = raw.strip()
        if not line or line.startswith("$agmsg actas"):
            continue
        try:
            if handle_event(line):
                continue
            if args.team:
                reply(args.team, "ARS", line)
            else:
                print(f"Use the AGMSG chat composer to send a message to {args.agent}.")
        except Exception as exc:
            print(f"LLM CLI error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
