# AGMSG local LLM examples

These examples connect AGMSG agents to an OpenAI-compatible local LLM endpoint.
They are provider-neutral and were tested with a local Qwen model served by
llama.cpp.

The ask helper waits up to 300 seconds by default and correlates each reply with
its request, so a delayed response cannot be mistaken for a later review. Set
`LLM_REPLY_TIMEOUT` or pass `--timeout` to override the wait limit.

Requirements:

- Python 3.10 or later; no third-party Python packages are required
- AGMSG installed with its scripts available under `~/.agents/skills/agmsg`
- an OpenAI-compatible `/chat/completions` endpoint

The examples do not read or send API keys. If your endpoint requires
authentication, add an appropriate local header mechanism without committing
credentials or `.env` files.

## Files

- `ask_llm.py`: sends a request through AGMSG, waits for the reply, and prints it.
- `api_bridge.py`: watches one or more teams and handles each request independently.
- `interactive_cli.py`: runs in an AGMSG terminal pane and keeps conversation
  context until the pane closes.

## API-style review agent

Register a review member in AGMSG, then run:

```bash
python3 examples/agmsg_llm/api_bridge.py \
  --all-teams \
  --agent LLM-review \
  --base-url http://127.0.0.1:8081/v1 \
  --model local-model
```

Ask it from a Codex project that has a single matching AGMSG team:

```bash
python3 examples/agmsg_llm/ask_llm.py \
  --from Codex \
  --to LLM-review \
  "Review this change briefly."
```

`ask_llm.py` infers the team from the current project and sender identity. Pass
`--team <name>` when the project is registered in more than one team. It refuses
to send when the team cannot be resolved uniquely.

## Interactive agent

Launch `interactive_cli.py` from an AGMSG pane with the team and agent name:

```bash
LLM_PERSONA=/path/to/persona.md \
python3 examples/agmsg_llm/interactive_cli.py \
  --team my-team \
  --agent LLM \
  --base-url http://127.0.0.1:8081/v1 \
  --model local-model
```

The interactive client keeps context only in the running process. Closing the
pane ends that conversation.

## Environment variables

- `AGMSG_SKILL_DIR`: AGMSG skill directory, default `~/.agents/skills/agmsg`
- `AGMSG_TEAM`: explicit team for `ask_llm.py` or `api_bridge.py`
- `LLM_AGENT`, `LLM_MODEL`, `LLM_BASE_URL`: bridge/client defaults
- `LLM_PERSONA`: optional Markdown persona file
- `LLM_BRIDGE_STATE_DIR`: cursor state directory for `api_bridge.py`
- `LLM_CLI_RUN_DIR`: active-pane marker directory for `interactive_cli.py`

Do not commit API keys, AGMSG databases, team state, chat logs, or private
persona files.
