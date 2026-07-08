# agmsg-ars

Unofficial ARS patch kit for the [AGMSG](https://github.com/fujibee/agmsg)
desktop app.

This repository does not fork or vendor AGMSG itself. It keeps a small patch
stack and a build script that apply local UI/agent-workflow changes on top of
the official AGMSG source.

## Status

This is an unofficial patch kit. It is provided as-is, for people who want to
study or reproduce the ARS desktop workflow. Review the patch files before
building, keep backups of any existing AGMSG app, and expect patches to require
refreshing when upstream AGMSG changes.

## What This Changes

The current patch stack focuses on the desktop app:

- JST message time display
- Light theme using white, gray, and navy
- Dev-build updater guard, so patched builds do not overwrite themselves with
  official releases
- Composer stays visible while duplicate app-user history can stay hidden
- Japanese composer wording uses `送信者 {appUser}`
- Separate `# チームルーム` and `# チャットルーム` views
- Bubble-style chat room messages
- Codex pane startup avoids ambiguous `/agmsg actas codex` when the same
  project path has a `codex` member in several teams
- Running terminal panes are scoped by team and member name
- Patched builds embed base commit, patch count, patch stack, and build time in
  the app `Info.plist`

See [docs/patch-stack.md](docs/patch-stack.md) for the full patch list.

## Requirements

- macOS
- Git
- Node / pnpm dependencies required by upstream AGMSG
- Rust / Tauri build toolchain required by upstream AGMSG

The script clones upstream AGMSG into `.upstream/agmsg` by default. To use an
existing clone, set `AGMSG_REPO`.

## Build

```bash
scripts/update_agmsg_dev.sh --fetch
```

The built app is saved under `dist/` by default.

To install it as `agmsg-dev.app`:

```bash
scripts/update_agmsg_dev.sh --fetch --install
```

The default install destination is:

```text
$HOME/Applications/agmsg-dev.app
```

Override paths with environment variables:

```bash
AGMSG_REPO=/path/to/agmsg \
AGMSG_APP_DEST="$HOME/Applications/agmsg-dev.app" \
scripts/update_agmsg_dev.sh --base app-v0.1.4 --install
```

## Updating Against New AGMSG Releases

1. Fetch or clone the new upstream source.
2. Run the build script against the new base ref:

   ```bash
   scripts/update_agmsg_dev.sh --fetch --base origin/main
   ```

3. If a patch no longer applies, refresh only that patch instead of carrying a
   full fork.
4. Keep the patch stack small and numbered.

## Privacy

This repository is intended to be public. It should not contain:

- AGMSG DB files or team state
- API keys
- persona/training files
- LaunchAgents
- local bridge runtimes
- user chat logs
- machine-specific absolute paths

## License

MIT. AGMSG itself is also MIT-licensed; this repository contains only an
overlay patch kit and documentation.
