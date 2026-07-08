# Patch Stack

Base target at the time this stack was extracted:

```text
app-v0.1.4
```

The patches are applied in lexical order from `patches/agmsg-dev/`.

## Patches

- `0001-display-message-times-in-jst.patch`
  - Render desktop message times in Japan time.
- `0002-light-navy-theme.patch`
  - Replace the dark default look with a white/gray/navy theme.
- `0003-disable-dev-auto-updater.patch`
  - Prevent patched dev builds from auto-installing official updates over the
    local build.
- `0004-keep-composer-independent.patch`
  - Keep the composer usable when duplicate app-user history is hidden.
- `0005-use-type-command-prefix-for-spawn.patch`
  - Respect type-specific AGMSG command prefixes.
- `0006-timeout-delivery-mode-status.patch`
  - Avoid blocking pane startup on slow delivery-mode probes.
- `0007-hide-app-user-history-by-default.patch`
  - Hide duplicate app-user history by default.
- `0008-do-not-probe-delivery-mode-before-spawn.patch`
  - Treat app-spawned panes as app-delivered without a synchronous probe.
- `0009-japanese-composer-sender-label.patch`
  - Use `送信者` wording in the composer.
- `0010-inject-codex-actas-after-pty-start.patch`
  - Historical Codex startup experiment retained for patch-stack continuity.
- `0011-bypass-codex-monitor-shim-in-pty-pane.patch`
  - Launch the real Codex binary from app panes instead of a PATH shim.
- `0012-inject-codex-agmsg-command-on-message.patch`
  - Inject a compact AGMSG inbox/send instruction for Codex panes when messages
    arrive.
- `0013-do-not-inject-codex-actas-on-startup.patch`
  - Stop startup-time `actas` injection into Codex panes.
- `0014-split-team-and-chat-room-tabs.patch`
  - Add separate team-room and chat-room tabs, with bubble-style chat messages.
- `0015-show-dev-build-provenance.patch`
  - Embed and display upstream base and local patch provenance.
- `0016-match-official-codex-spawn-command.patch`
  - Keep Codex spawn behavior aligned with the official app command shape.
- `0017-scope-running-panes-by-team.patch`
  - Scope live panes by team and member name, not member name alone.
- `0018-start-codex-pane-without-actas.patch`
  - Start Codex panes without `actas`; use team-scoped AGMSG delivery
    instructions instead.

## Refreshing a Patch

When upstream changes conflict with a patch:

1. Check out the upstream base in a temporary worktree.
2. Apply patches up to the failing patch.
3. Recreate only the failing patch against the new upstream source.
4. Keep the filename number stable if the intent is unchanged.

