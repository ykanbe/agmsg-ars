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

公式 fujibee/agmsg に agmsg-ars のパッチ列を当てて agmsg-dev をビルドします。

Options:
  --fetch            ビルド前に upstream main を fetch する
  --base <ref>       ビルド対象の base ref (default: origin/main)
  --install          生成した app を $HOME/Applications/agmsg-dev.app へコピーする
  --keep-worktree    デバッグ用に一時 worktree を残す
  -h, --help         このヘルプを表示する

Environment:
  AGMSG_REPO         upstream agmsg clone。存在しない場合は、このrepo配下の
                     .upstream/agmsg へ clone する
  AGMSG_PATCH_DIR    local *.patch files を置いたディレクトリ
  AGMSG_BUILD_PARENT 一時 worktree を作る親ディレクトリ
  AGMSG_ARTIFACT_PARENT
                     --install しない場合の生成 app 保存先
  AGMSG_NODE_MODULES_SOURCE
                     ビルド前に一時 worktree へコピーする任意の node_modules
  AGMSG_CORE_RESOURCE_SOURCE
                     upstream checkout が必要とする場合にコピーする任意の
                     agmsg-core resource directory
  AGMSG_APP_DEST     --install 使用時のインストール先
  AGMSG_CODESIGN_IDENTITY
                     生成 app の署名 identity。未指定の場合は
                     "agmsg-dev Local Code Signing" があれば使い、なければ
                     ad-hoc 署名 ("-") にフォールバックする。
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
      echo "不明なオプションです: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$PATCH_DIR" ]]; then
  echo "パッチディレクトリが見つかりません: $PATCH_DIR" >&2
  exit 1
fi

if [[ ! -d "$REPO/.git" ]]; then
  echo "upstream agmsg clone が見つかりません。cloneします: $REPO"
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
    echo "worktree を残しました: $BUILD_DIR"
  else
    git -C "$REPO" worktree remove --force "$BUILD_DIR" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

shopt -s nullglob
patches=("$PATCH_DIR"/*.patch)
if ((${#patches[@]} == 0)); then
  echo "パッチが見つかりません: $PATCH_DIR" >&2
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
  echo "パッチ適用: $patch_name"
  git -C "$BUILD_DIR" apply "$patch"
done

if [[ -n "$NODE_MODULES_SOURCE" && -d "$NODE_MODULES_SOURCE" && ! -e "$BUILD_DIR/app/node_modules" ]]; then
  ditto "$NODE_MODULES_SOURCE" "$BUILD_DIR/app/node_modules"
  echo "node_modules をコピーしました: $NODE_MODULES_SOURCE"
fi

if [[ -n "$CORE_RESOURCE_SOURCE" && -d "$CORE_RESOURCE_SOURCE" && ! -e "$BUILD_DIR/app/src-tauri/resources/agmsg-core" ]]; then
  mkdir -p "$BUILD_DIR/app/src-tauri/resources"
  ditto "$CORE_RESOURCE_SOURCE" "$BUILD_DIR/app/src-tauri/resources/agmsg-core"
  echo "agmsg-core resource を使用します: $CORE_RESOURCE_SOURCE"
elif [[ -x "$BUILD_DIR/app/scripts/bundle-core.sh" ]]; then
  echo "公式のbundle-core.shで固定coreを準備します"
  bash "$BUILD_DIR/app/scripts/bundle-core.sh"
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
echo "ビルド済み app: $BUILT_APP"
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
echo "app に署名します: $CODESIGN_IDENTITY"
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

  echo "起動中の app に終了を要求します: $app_path ($app_id)"
  osascript -e "tell application id \"$app_id\" to quit" >/dev/null 2>&1 || true

  while ((waited < timeout_seconds)); do
    if ! app_is_running "$app_id"; then
      echo "app が終了しました: $app_path ($app_id)"
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done

  echo "${timeout_seconds}秒後も app が起動中です: $app_path ($app_id)" >&2
  echo "agmsg-dev を手動で終了してから --install を再実行してください。既存 app は移動していません。" >&2
  return 1
}

if ((INSTALL)); then
  app_id=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$BUILT_APP/Contents/Info.plist")
  quit_running_app "$app_id" 30 "$APP_DEST"
  if app_is_running "$app_id"; then
    echo "install 継続前に app が再起動しました: $APP_DEST ($app_id)" >&2
    echo "agmsg-dev を手動で終了してから --install を再実行してください。既存 app は移動していません。" >&2
    exit 1
  fi
  if [[ -e "$APP_DEST" ]]; then
    backup="${APP_DEST%.app}.backup-$(date +%Y%m%d%H%M%S).app.disabled"
    if [[ -e "$backup" ]]; then
      backup="${backup%*.disabled}-$$.app.disabled"
    fi
    mv "$APP_DEST" "$backup"
    echo "既存 app をバックアップしました: $backup"
  fi
  mkdir -p "$(dirname "$APP_DEST")"
  ditto "$BUILT_APP" "$APP_DEST"
  strip_gatekeeper_xattrs "$APP_DEST"
  echo "app をインストールしました: $APP_DEST"
else
  mkdir -p "$ARTIFACT_PARENT"
  ARTIFACT_APP="$ARTIFACT_PARENT/agmsg-dev-$(date +%Y%m%d%H%M%S).app"
  ditto "$BUILT_APP" "$ARTIFACT_APP"
  strip_gatekeeper_xattrs "$ARTIFACT_APP"
  echo "app を保存しました: $ARTIFACT_APP"
  echo "インストールする場合:"
  echo "  ditto \"$ARTIFACT_APP\" \"$APP_DEST\""
fi
