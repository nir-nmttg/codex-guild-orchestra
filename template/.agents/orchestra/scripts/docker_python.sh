#!/usr/bin/env bash
# Docker 内の Python だけを実行基盤にする runtime runner。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATIC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GUILD_ROOT="$(cd "$STATIC_ROOT/../.." && pwd)"
HOST_CWD="$(pwd -P)"
IMAGE="${AGENT_GUILD_ORCHESTRA_DOCKER_IMAGE:-agent-guild-orchestra-runtime:local}"

if [ "$#" -eq 0 ]; then
  echo "使い方: docker_python.sh <python-args...>" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker_python: Docker が見つかりません。Docker をインストールして起動してください。" >&2
  exit 127
fi

if [ "${AGENT_GUILD_ORCHESTRA_DOCKER_SKIP_BUILD:-0}" != "1" ]; then
  docker build --quiet -t "$IMAGE" "$STATIC_ROOT/docker" >/dev/null
fi

mounts=()
mounted_paths=":"

add_mount() {
  local host_path="$1"
  local container_path="${2:-$1}"
  [ -n "$host_path" ] || return 0
  [ -n "$container_path" ] || return 0
  case ":$mounted_paths:" in
    *":$container_path:"*) return 0 ;;
  esac
  mounts+=("-v" "$host_path:$container_path")
  mounted_paths="${mounted_paths}${container_path}:"
}

nearest_existing_mount() {
  local input_path="$1"
  [ -n "$input_path" ] || return 0
  case "$input_path" in
    /*) ;;
    *) return 0 ;;
  esac

  local candidate="$input_path"
  if [ -e "$candidate" ] && [ ! -d "$candidate" ]; then
    candidate="$(dirname "$candidate")"
  fi
  while [ ! -e "$candidate" ] && [ "$candidate" != "/" ]; do
    candidate="$(dirname "$candidate")"
  done
  if [ "$candidate" = "/" ]; then
    echo "docker_python: mount 可能な親ディレクトリが見つかりません: $input_path" >&2
    exit 1
  fi
  add_mount "$(cd "$candidate" && pwd -P)" "$candidate"
}

scan_path_args() {
  local previous=""
  for arg in "$@"; do
    case "$previous" in
      --target|--source|--runtime-root|--static-root|--target-repo-root|--repo)
        nearest_existing_mount "$arg"
        previous=""
        continue
        ;;
    esac
    case "$arg" in
      --target=*|--source=*|--runtime-root=*|--static-root=*|--target-repo-root=*|--repo=*)
        nearest_existing_mount "${arg#*=}"
        ;;
      --target|--source|--runtime-root|--static-root|--target-repo-root|--repo)
        previous="$arg"
        ;;
      *)
        previous=""
        ;;
    esac
  done
}

add_mount "$GUILD_ROOT"
add_mount "$HOST_CWD"
scan_path_args "$@"
RUNTIME_ROOT_ENV="${AGENT_GUILD_ORCHESTRA_RUNTIME_ROOT:-}"
GUILD_ROOT_ENV="${AGENT_GUILD_ORCHESTRA_ROOT:-}"
if [ -n "$RUNTIME_ROOT_ENV" ]; then
  nearest_existing_mount "$RUNTIME_ROOT_ENV"
fi
if [ -n "$GUILD_ROOT_ENV" ]; then
  nearest_existing_mount "$GUILD_ROOT_ENV"
fi

env_args=("-e" "HOME=/tmp")
for env_name in CODEX_HOOK_PAYLOAD AGENT_GUILD_ORCHESTRA_STOP_QUALITY_STRICT AGENT_GUILD_ORCHESTRA_ROOT AGENT_GUILD_ORCHESTRA_RUNTIME_ROOT; do
  if [ -n "${!env_name+x}" ]; then
    env_args+=("-e" "$env_name")
  fi
done

exec docker run --rm -i \
  --user "$(id -u):$(id -g)" \
  "${env_args[@]}" \
  "${mounts[@]}" \
  -w "$HOST_CWD" \
  "$IMAGE" \
  python "$@"
