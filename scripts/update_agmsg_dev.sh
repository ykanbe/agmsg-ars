#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

REPO="${AGMSG_REPO:-$PROJECT_ROOT/.upstream/agmsg}"
PATCH_DIR="${AGMSG_PATCH_DIR:-$PROJECT_ROOT/patches/agmsg-dev}"
BUILD_PARENT="${AGMSG_BUILD_PARENT:-/private/tmp}"
ARTIFACT_PARENT="${AGMSG_ARTIFACT_PARENT:-$PROJECT_ROOT/dist}"
NODE_MODULES_SOURCE="${AGMSG_NODE_MODULES_SOURCE:-}"
CORE_RESOURCE_SOURCE="${AGMSG_CORE_RESOURCE_SOURCE:-}"
APP_DEST="${AGMSG_APP_DEST:-$HOME/Applications/agmsg-dev.app}"
DEFAULT_CODESIGN_IDENTITY="agmsg-dev Local Code Signing"
BASE_REF="origin/main"
FETCH=0
INSTALL=0
KEEP=0

usage() {
  cat <<'USAGE'
Usage: scripts/update_agmsg_dev.sh [options]

Build agmsg-dev from official fujibee/agmsg plus the agmsg-ars patch stack.

Options:
  --fetch            fetch upstream main before building
  --base <ref>       base ref to build from (default: origin/main)
  --install          copy the built app to $HOME/Applications/agmsg-dev.app
  --keep-worktree    keep the temporary worktree for debugging
  -h, --help         show this help

Environment:
  AGMSG_REPO         upstream agmsg clone. If missing, it is cloned into
                     .upstream/agmsg under this repository.
  AGMSG_PATCH_DIR    directory containing local *.patch files
  AGMSG_BUILD_PARENT parent directory for temporary worktrees
  AGMSG_ARTIFACT_PARENT
                     destination for built app artifacts when not installing
  AGMSG_NODE_MODULES_SOURCE
                     optional node_modules directory to copy into the temporary
                     worktree before building
  AGMSG_CORE_RESOURCE_SOURCE
                     optional agmsg-core resource directory to copy into the
                     temporary worktree when the upstream checkout needs it
  AGMSG_APP_DEST     install destination when --install is used
  AGMSG_CODESIGN_IDENTITY
                     signing identity for the built app. If unset, the script
                     uses "agmsg-dev Local Code Signing" when present, otherwise
                     falls back to ad-hoc signing ("-").
USAGE
}

while (($#)); do
  case "$1" in
    --fetch)
      FETCH=1
      shift
      ;;
    --base)
      BASE_REF="${2:?--base requires a ref}"
      shift 2
      ;;
    --install)
      INSTALL=1
      shift
      ;;
    --keep-worktree)
      KEEP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$PATCH_DIR" ]]; then
  echo "patch directory not found: $PATCH_DIR" >&2
  exit 1
fi

if [[ ! -d "$REPO/.git" ]]; then
  echo "Upstream agmsg clone not found; cloning into: $REPO"
  mkdir -p "$(dirname "$REPO")"
  git clone https://github.com/fujibee/agmsg.git "$REPO"
fi

if ((FETCH)); then
  git -C "$REPO" fetch origin main --tags
fi

BUILD_DIR="$BUILD_PARENT/agmsg-ars-build-$(date +%Y%m%d%H%M%S)"
git -C "$REPO" worktree add --detach "$BUILD_DIR" "$BASE_REF"
BASE_COMMIT="$(git -C "$BUILD_DIR" rev-parse HEAD)"
BASE_DESCRIBE="$(git -C "$BUILD_DIR" describe --tags --always --dirty)"
BUILD_TIME_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

if [[ -n "${AGMSG_CODESIGN_IDENTITY:-}" ]]; then
  CODESIGN_IDENTITY="$AGMSG_CODESIGN_IDENTITY"
else
  CODESIGN_IDENTITY="$(
    security find-identity -p codesigning -v 2>/dev/null |
      awk -v name="\"$DEFAULT_CODESIGN_IDENTITY\"" '$0 ~ name { print $2; exit }'
  )"
  if [[ -z "$CODESIGN_IDENTITY" ]]; then
    CODESIGN_IDENTITY="-"
  fi
fi

cleanup() {
  if ((KEEP)); then
    echo "Kept worktree: $BUILD_DIR"
  else
    git -C "$REPO" worktree remove --force "$BUILD_DIR" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

shopt -s nullglob
patches=("$PATCH_DIR"/*.patch)
if ((${#patches[@]} == 0)); then
  echo "No patches found in $PATCH_DIR" >&2
  exit 1
fi
PATCH_COUNT="${#patches[@]}"
PATCH_STACK=""

for patch in "${patches[@]}"; do
  patch_name="$(basename "$patch")"
  if [[ -n "$PATCH_STACK" ]]; then
    PATCH_STACK+=","
  fi
  PATCH_STACK+="$patch_name"
  echo "Applying $patch_name"
  git -C "$BUILD_DIR" apply "$patch"
done

if [[ -n "$NODE_MODULES_SOURCE" && -d "$NODE_MODULES_SOURCE" && ! -e "$BUILD_DIR/app/node_modules" ]]; then
  ditto "$NODE_MODULES_SOURCE" "$BUILD_DIR/app/node_modules"
  echo "Copied node_modules from: $NODE_MODULES_SOURCE"
fi

if [[ -n "$CORE_RESOURCE_SOURCE" && -d "$CORE_RESOURCE_SOURCE" && ! -e "$BUILD_DIR/app/src-tauri/resources/agmsg-core" ]]; then
  mkdir -p "$BUILD_DIR/app/src-tauri/resources"
  ditto "$CORE_RESOURCE_SOURCE" "$BUILD_DIR/app/src-tauri/resources/agmsg-core"
  echo "Using agmsg-core resource: $CORE_RESOURCE_SOURCE"
fi

(
  cd "$BUILD_DIR/app"
  AGMSG_DEV_BUILD=1 \
    AGMSG_DEV_BASE_REF="$BASE_DESCRIBE" \
    AGMSG_DEV_BASE_COMMIT="$BASE_COMMIT" \
    AGMSG_DEV_PATCH_COUNT="$PATCH_COUNT" \
    AGMSG_DEV_BUILD_TIME="$BUILD_TIME_UTC" \
    CI=true \
    PNPM_CONFIG_DANGEROUSLY_ALLOW_ALL_BUILDS=true \
    pnpm tauri build --bundles app --config '{"productName":"agmsg-dev","identifier":"cc.agmsg.dev","bundle":{"createUpdaterArtifacts":false,"macOS":{"signingIdentity":null}},"plugins":{"updater":{"active":false}}}'
)

BUILT_APP="$BUILD_DIR/app/src-tauri/target/release/bundle/macos/agmsg-dev.app"
echo "Built app: $BUILT_APP"
BUILT_PLIST="$BUILT_APP/Contents/Info.plist"

plist_set_string() {
  local key="$1"
  local value="$2"
  /usr/libexec/PlistBuddy -c "Delete :$key" "$BUILT_PLIST" >/dev/null 2>&1 || true
  /usr/libexec/PlistBuddy -c "Add :$key string $value" "$BUILT_PLIST"
}

plist_set_string AGMSGDevBaseRef "$BASE_DESCRIBE"
plist_set_string AGMSGDevBaseCommit "$BASE_COMMIT"
plist_set_string AGMSGDevPatchCount "$PATCH_COUNT"
plist_set_string AGMSGDevPatchStack "$PATCH_STACK"
plist_set_string AGMSGDevBuildTime "$BUILD_TIME_UTC"
plist_set_string AGMSGDevBuildScript "agmsg-ars/scripts/update_agmsg_dev.sh"

echo "Dev provenance: base=$BASE_DESCRIBE commit=${BASE_COMMIT:0:12} patches=$PATCH_COUNT built=$BUILD_TIME_UTC"
echo "Signing app with identity: $CODESIGN_IDENTITY"
codesign --force --deep --sign "$CODESIGN_IDENTITY" "$BUILT_APP" >/dev/null
codesign --verify --deep --strict --verbose=2 "$BUILT_APP"

strip_gatekeeper_xattrs() {
  local app_path="$1"
  xattr -dr com.apple.quarantine "$app_path" >/dev/null 2>&1 || true
  xattr -dr com.apple.provenance "$app_path" >/dev/null 2>&1 || true
}

app_is_running() {
  local app_id="$1"
  local state
  state="$(osascript -e "application id \"$app_id\" is running" 2>/dev/null || printf 'false')"
  [[ "$state" == "true" ]]
}

quit_running_app() {
  local app_id="$1"
  local timeout_seconds="${2:-30}"
  local app_path="${3:-unknown app path}"
  local waited=0

  if ! app_is_running "$app_id"; then
    return 0
  fi

  echo "Requesting running app to quit: $app_path ($app_id)"
  osascript -e "tell application id \"$app_id\" to quit" >/dev/null 2>&1 || true

  while ((waited < timeout_seconds)); do
    if ! app_is_running "$app_id"; then
      echo "App exited: $app_path ($app_id)"
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done

  echo "App is still running after ${timeout_seconds}s: $app_path ($app_id)" >&2
  echo "Quit agmsg-dev manually, then rerun with --install. Existing app was not moved." >&2
  return 1
}

if ((INSTALL)); then
  app_id=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$BUILT_APP/Contents/Info.plist")
  quit_running_app "$app_id" 30 "$APP_DEST"
  if app_is_running "$app_id"; then
    echo "App restarted before install could continue: $APP_DEST ($app_id)" >&2
    echo "Quit agmsg-dev manually, then rerun with --install. Existing app was not moved." >&2
    exit 1
  fi
  if [[ -e "$APP_DEST" ]]; then
    backup="${APP_DEST%.app}.backup-$(date +%Y%m%d%H%M%S).app.disabled"
    if [[ -e "$backup" ]]; then
      backup="${backup%*.disabled}-$$.app.disabled"
    fi
    mv "$APP_DEST" "$backup"
    echo "Backed up existing app: $backup"
  fi
  mkdir -p "$(dirname "$APP_DEST")"
  ditto "$BUILT_APP" "$APP_DEST"
  strip_gatekeeper_xattrs "$APP_DEST"
  echo "Installed app: $APP_DEST"
else
  mkdir -p "$ARTIFACT_PARENT"
  ARTIFACT_APP="$ARTIFACT_PARENT/agmsg-dev-$(date +%Y%m%d%H%M%S).app"
  ditto "$BUILT_APP" "$ARTIFACT_APP"
  strip_gatekeeper_xattrs "$ARTIFACT_APP"
  echo "Saved app: $ARTIFACT_APP"
  echo "Install with:"
  echo "  ditto \"$ARTIFACT_APP\" \"$APP_DEST\""
fi
