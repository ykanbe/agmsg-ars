#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
STATE_DIR = Path(os.environ.get("LLM_BRIDGE_STATE_DIR", "~/.agents/agmsg_llm/state")).expanduser()
AGMSG = Path(os.environ.get("AGMSG_SKILL_DIR", "~/.agents/skills/agmsg")).expanduser()
API = AGMSG / "scripts" / "api.sh"
SEND = AGMSG / "scripts" / "send.sh"
DELEGATE_RE = re.compile(r"^\s*AGMSG_DELEGATE\s+([^:]+?)\s*:\s*(.+)\s*$", re.IGNORECASE | re.DOTALL)


BASE_SYSTEM_PROMPT = """あなたはAGMSGチームに参加しているローカルLLMサブエージェントです。
共通ルール:
- {delegate_agent} は総監督であり、あなたは補助的な相談相手です。
- 日本語で簡潔に返す。
- ファイル操作や外部操作はできないので、必要なら {delegate_agent} に依頼する。
- 自分で対応できない依頼は、ユーザーに「{delegate_agent}に頼んで」と言わず、
  `AGMSG_DELEGATE {delegate_agent}: <具体的な依頼>` だけを返す。
- 自分が受け取ったメッセージだけに反応する。
- 返信はそのまま相手に送られるので、前置きは短くする。
- 確信が低いことは断定せず、リスクや仮定として述べる。
"""


def run_jsonl(args):
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def run_text(args):
    proc = subprocess.run(args, text=True, capture_output=True, check=True)
    return proc.stdout.strip()


def state_path(team, agent):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{team}-{agent}.last_id"


def load_last_id(team, agent):
    path = state_path(team, agent)
    if not path.exists():
        return None
    value = path.read_text().strip()
    if not value:
        return None
    if not value.isdigit():
        print(f"Ignoring invalid state id in {path}: {value!r}", file=sys.stderr)
        return None
    return value


def save_last_id(team, agent, value):
    state_path(team, agent).write_text(str(value), encoding="utf-8")


def mark_seen(team, agent, msg):
    save_last_id(team, agent, msg["id"])
    return msg["id"]


def current_max_id(team, agent):
    rows = run_jsonl([str(API), "get", "teams", team, "messages", "--agent", agent, "--limit", "1"])
    return rows[-1]["id"] if rows else "0"


def list_all_teams():
    rows = run_jsonl([str(API), "get", "teams"])
    return [row["name"] for row in rows if row.get("name")]


def team_has_agent(team, agent):
    rows = run_jsonl([str(API), "get", "teams", team, "members"])
    return any(row.get("name") == agent for row in rows)


def discover_agent_teams(agent):
    teams = []
    for team in list_all_teams():
        if team_has_agent(team, agent):
            teams.append(team)
    return teams


def fetch_new_messages(team, agent, last_id, limit):
    rows = run_jsonl([str(API), "get", "teams", team, "messages", "--agent", agent, "--limit", str(limit)])
    if last_id is None:
        return rows
    return [m for m in rows if int(m["id"]) > int(last_id)]


def default_persona_path():
    raw = os.environ.get("LLM_PERSONA", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None


def load_system_prompt(team, agent, persona_path, delegate_agent):
    parts = [
        BASE_SYSTEM_PROMPT.format(delegate_agent=delegate_agent),
        f"\n現在のAGMSGチーム: {team}\n現在のあなたのAGMSG名: {agent}\n",
    ]
    if persona_path:
        path = Path(persona_path).expanduser()
        if path.exists():
            parts.append("\n# Persona and Training Notes\n")
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def call_openai_compatible(base_url, model, system_prompt, prompt, temperature, max_tokens):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=600) as res:
        data = json.loads(res.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def delegation_request(reply, delegate_agent):
    match = DELEGATE_RE.match(reply.strip())
    if not match or match.group(1).strip().casefold() != delegate_agent.casefold():
        return None
    request = match.group(2).strip()
    return request or None


def send_or_delegate(team, agent, msg, reply, delegate_agent):
    request = delegation_request(reply, delegate_agent)
    if not request:
        print(f"reply -> {team}:{msg['from']}: {reply}")
        run_text([str(SEND), team, agent, msg["from"], reply])
        return

    if msg["from"] != delegate_agent:
        body = (
            f"{agent}から{delegate_agent}への委譲です。\n"
            f"元の依頼者: {msg['from']}\n"
            f"依頼: {request}\n\n"
            f"元メッセージ:\n{msg['body']}"
        )
        print(f"delegate -> {team}:{delegate_agent}: {request}")
        run_text([str(SEND), team, agent, delegate_agent, body])

    ack = f"この件は{agent}では直接対応できないため、{delegate_agent}へ依頼しました。"
    print(f"reply -> {team}:{msg['from']}: {ack}")
    run_text([str(SEND), team, agent, msg["from"], ack])


def parse_teams(raw):
    teams = []
    for item in raw.split(","):
        team = item.strip()
        if team and team != "all" and team not in teams:
            teams.append(team)
    return teams


def configured_teams(args):
    if args.all_teams or args.teams.strip() == "all":
        return discover_agent_teams(args.agent)
    return parse_teams(args.teams or args.team)


def add_team_state(last_ids, team, agent, reply_existing, limit):
    if team in last_ids:
        return
    last_id = load_last_id(team, agent)
    if last_id is None and not reply_existing:
        last_id = current_max_id(team, agent)
        save_last_id(team, agent, last_id)
        print(f"Starting {team} from message id {last_id}. Use --reply-existing to process old messages.")
    elif last_id is None:
        print(f"Starting {team} with existing messages enabled.")
    else:
        print(f"Resuming {team} from message id {last_id}.")
    last_ids[team] = last_id


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--team", default=os.environ.get("AGMSG_TEAM", ""), help="Single AGMSG team to monitor.")
    parser.add_argument("--teams", default=os.environ.get("AGMSG_TEAMS", ""), help="Comma-separated AGMSG teams to monitor, or 'all'.")
    parser.add_argument("--all-teams", action="store_true", default=os.environ.get("AGMSG_ALL_TEAMS", "").lower() in {"1", "true", "yes"}, help="Monitor every AGMSG team where this agent is registered.")
    parser.add_argument("--team-refresh", type=float, default=float(os.environ.get("AGMSG_TEAM_REFRESH", "15")), help="Seconds between all-team rediscovery checks.")
    parser.add_argument("--agent", default=os.environ.get("LLM_AGENT", "LLM-review"))
    parser.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8081/v1"))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", "local-model"))
    parser.add_argument("--delegate-agent", default=os.environ.get("LLM_DELEGATE_AGENT", "Codex"))
    parser.add_argument("--poll", type=float, default=2.0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--persona", default=None, help="Optional Markdown persona/training file.")
    parser.add_argument("--reply-existing", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    teams = configured_teams(args)
    if not teams:
        print("No AGMSG teams configured", file=sys.stderr)
        return 2

    last_ids = {}
    for team in teams:
        add_team_state(last_ids, team, args.agent, args.reply_existing, args.limit)

    persona_path = args.persona or default_persona_path()
    print(f"llm api bridge listening: teams={','.join(last_ids.keys())} agent={args.agent} model={args.model} persona={persona_path or 'none'} all_teams={args.all_teams or args.teams.strip() == 'all'}")
    next_refresh = time.time() + max(args.team_refresh, 1.0)
    while True:
        try:
            if args.all_teams or args.teams.strip() == "all":
                now = time.time()
                if now >= next_refresh:
                    try:
                        desired = configured_teams(args)
                    except Exception as exc:
                        print(f"team rediscovery failed; keeping existing teams: {exc}", file=sys.stderr)
                    else:
                        for team in desired:
                            add_team_state(last_ids, team, args.agent, True, args.limit)
                        for team in list(last_ids):
                            if team not in desired:
                                print(f"Stopping monitor for {team}: agent {args.agent} is no longer registered there.")
                                del last_ids[team]
                    next_refresh = now + max(args.team_refresh, 1.0)

            for team in list(last_ids):
                messages = fetch_new_messages(team, args.agent, last_ids[team], args.limit)
                for msg in messages:
                    if msg["from"] == args.agent or msg["to"] != args.agent:
                        last_ids[team] = mark_seen(team, args.agent, msg)
                        continue
                    print(f"[{team}:{msg['id']}] {msg['from']} -> {msg['to']}: {msg['body']}")
                    prompt = f"From: {msg['from']}\nMessage:\n{msg['body']}\n\nReply to {msg['from']}."
                    system_prompt = load_system_prompt(team, args.agent, persona_path, args.delegate_agent)
                    reply = call_openai_compatible(args.base_url, args.model, system_prompt, prompt, args.temperature, args.max_tokens)
                    send_or_delegate(team, args.agent, msg, reply, args.delegate_agent)
                    last_ids[team] = mark_seen(team, args.agent, msg)
            if args.once:
                break
            time.sleep(args.poll)
        except KeyboardInterrupt:
            print("stopped")
            return
        except Exception as exc:
            print(f"bridge error: {exc}", file=sys.stderr)
            if args.once:
                raise
            time.sleep(max(args.poll, 5.0))


if __name__ == "__main__":
    raise SystemExit(main())
