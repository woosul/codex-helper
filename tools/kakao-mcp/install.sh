#!/usr/bin/env bash
# Install the pinned community MCP and its local reader patch on a new Mac.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HOME/.local/share/kakao-mcp"
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

[[ "$(uname -s)" == Darwin ]] || { echo 'macOS is required.' >&2; exit 1; }
for command in git brew uv swift python3; do
  command -v "$command" >/dev/null || { echo "Missing prerequisite: $command" >&2; exit 1; }
done
if [[ -e "$ROOT/server" ]]; then
  echo "Existing installation at $ROOT/server; preserve it and follow README.md for maintenance." >&2
  exit 1
fi

brew list sqlcipher >/dev/null 2>&1 || HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install sqlcipher
mkdir -p "$ROOT/src" "$ROOT/bin" "$ROOT/patches"
git clone https://github.com/Jaeha0526/kakao-mcp.git "$ROOT/server"
git -C "$ROOT/server" -c advice.detachedHead=false checkout 028588f447536ae4f9b06f54dbf2c876246292cc

# The upstream script pins kakaocli and the optional kmsg sender.
bash "$ROOT/server/scripts/install-deps.sh"
git -C "$ROOT/src/kakaocli" apply --check "$HERE/kakaocli-account-recovery.patch"
git -C "$ROOT/src/kakaocli" apply "$HERE/kakaocli-account-recovery.patch"
(
  cd "$ROOT/src/kakaocli"
  swift test -c release --disable-sandbox
  install -m 0755 .build/release/kakaocli "$ROOT/bin/kakaocli"
)
(
  cd "$ROOT/server"
  uv sync --frozen --python 3.11
  .venv/bin/python -m pytest -q
)
cp "$HERE/kakaocli-account-recovery.patch" "$ROOT/patches/"
cp "$HERE/README.md" "$ROOT/patches/README.md"

"$ROOT/server/.venv/bin/python" - <<'PY'
import json
import os
from pathlib import Path

home = Path.home()
config = home / '.config/kakao-mcp/config.json'
config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
if not config.exists():
    data = {
        'user_id': None,
        'kakaocli_path': str(home / '.local/share/kakao-mcp/bin/kakaocli'),
        'kmsg_path': str(home / '.local/share/kakao-mcp/bin/kmsg'),
        'read': {'exclude_chat_ids': [], 'default_messages': 100, 'max_messages': 1000},
        'media': {'max_download_mb': 200},
        'send': {'enabled': False, 'allowed_chats': {}, 'max_length': 1000, 'confirm_ttl_seconds': 300},
    }
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    print('Created private config with sending disabled.')
else:
    print('Existing config preserved; review its send settings before use.')
PY

echo "Installed $ROOT/server/.venv/bin/kakao-mcp"
echo 'Register clients and verify local DB access as documented in README.md.'
