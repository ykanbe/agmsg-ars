# AGMSG local LLM examples

These examples connect AGMSG agents to an OpenAI-compatible local LLM endpoint.
They are provider-neutral and were tested with a local Qwen model served by
llama.cpp.

The ask helper waits up to 300 seconds by default and correlates each reply with
its request, so a delayed response cannot be mistaken for a later review. The
correlation marker is kept directly after the body on both request and reply,
so Markdown rendering does not add an extra blank line. Set `LLM_REPLY_TIMEOUT`
or pass `--timeout` to override the wait limit.

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
pane ends that conversation. Each turn includes its actual AGMSG sender in the
model input, so one shared pane can distinguish human and agent participants.
If the model cannot handle a request, it can return
`AGMSG_DELEGATE Codex: <具体的な依頼>`. The client forwards that request in the
same team with the original sender and message, then replies to the original
sender that it was forwarded. Use `--delegate-agent <name>` or
`LLM_DELEGATE_AGENT` to select another delegate; the default is `Codex`. A
marker received from the delegate itself is answered locally without forwarding
again, preventing a delegation loop.

The client also applies a fail-closed input route before calling the local LLM:

- ordinary conversation, inline translation/summarization, and bounded code
  drafts stay in the interactive local LLM
- non-X URLs, local machine/file/command operations, and explicitly difficult
  technical judgments are forwarded to the Codex delegate
- X.com, Twitter, and `t.co` URLs are sent to the Grok retrieval agent; the client keeps
  an in-process correlation record, receives Grok's retrieval-only result, and
  asks the local LLM to answer the original sender

The URL gate permits only a narrow set of explicit URL-string formatting
requests to stay local. Mixed X and non-X URLs go to Codex. Grok requests are
limited to post text, quoted-post text, and related URLs. Use `--x-agent <name>`
or `LLM_X_AGENT`; the default is `Grok`. Grok replies use a request id when
available. A reply without an id is accepted only when exactly one request is
pending in that team; ambiguous results stop instead of being sent to the wrong
requester. Pending X retrievals expire after 300 seconds by default and are not
retried automatically, preventing a delayed result from being attached to a new
request. Override this with `--x-reply-timeout` or `LLM_X_REPLY_TIMEOUT`.

To let the patched desktop app launch this client, create a trusted AGMSG type
plugin under `~/.agents/skills/agmsg/plugins/types/<type-name>/`. Its
`type.conf` should include:

```ini
name=local-llm-cli
template=template.md
cli=/absolute/path/to/interactive-llm-wrapper
spawnable=yes
team_agent_args=yes
monitor=no
delivery_modes=off
```

Then trust it with
`~/.agents/skills/agmsg/scripts/plugin.sh trust types/local-llm-cli`. The
desktop app passes `--team <selected-team> --agent <member-name>` when opening
the pane. Keep machine-specific paths and private personas outside this public
repository.

## Environment variables

- `AGMSG_SKILL_DIR`: AGMSG skill directory, default `~/.agents/skills/agmsg`
- `AGMSG_TEAM`: explicit team for `ask_llm.py` or `api_bridge.py`
- `LLM_AGENT`, `LLM_MODEL`, `LLM_BASE_URL`: bridge/client defaults
- `LLM_PERSONA`: optional Markdown persona file
- `LLM_DELEGATE_AGENT`: delegate target for `AGMSG_DELEGATE`, default `Codex`
- `LLM_X_AGENT`: X.com/Twitter retrieval target, default `Grok`
- `LLM_X_REPLY_TIMEOUT`: X retrieval correlation lifetime in seconds, default `300`
- `LLM_BRIDGE_STATE_DIR`: cursor state directory for `api_bridge.py`
- `LLM_BRIDGE_HEARTBEAT`: heartbeat file written by `api_bridge.py`
- `LLM_BACKEND_HEALTH_URL`: optional model-server health URL checked in approval mode
- `LLM_CLI_RUN_DIR`: active-pane marker directory for `interactive_cli.py`

## Fail-closed approval check

For an approval precheck, use `--approval`:

```bash
LLM_BRIDGE_HEARTBEAT=/path/to/bridge.heartbeat \
LLM_BACKEND_HEALTH_URL=http://127.0.0.1:8081/health \
python3 examples/agmsg_llm/ask_llm.py \
  --approval --from Codex --to LLM-review \
  "Review this higher-risk action."
```

Approval mode exits successfully only for an explicit `許可`, `注意して許可`,
or `問題なし` response. A missing/stale bridge heartbeat, unavailable model
backend, timeout, rejection, or ambiguous response exits nonzero. The caller
must treat every nonzero result as denial and must not run the protected action.

Do not commit API keys, AGMSG databases, team state, chat logs, or private
persona files.
