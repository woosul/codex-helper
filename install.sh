#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv is required: https://docs.astral.sh/uv/" >&2
  exit 2
}
command -v codex >/dev/null 2>&1 || {
  echo "ERROR: codex CLI is required" >&2
  exit 2
}

"$ROOT/bin/codex-harness" "$@" bootstrap
"$ROOT/bin/codex-harness" "$@" plan
printf "Apply the planned Codex harness changes? [y/N] "
read -r answer
case "$answer" in
  y|Y|yes|YES) "$ROOT/bin/codex-harness" "$@" apply --yes ;;
  *) echo "No changes applied."; exit 0 ;;
esac
"$ROOT/bin/codex-harness" "$@" doctor
