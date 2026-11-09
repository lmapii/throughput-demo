#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
vsix_dir="${script_dir}/../_vsix"

# Lifecycle commands don't get `VSCODE_IPC_HOOK_CLI`, so `bin/remote-cli/code`
# fails with "Command is only available in WSL or inside a Visual Studio Code
# terminal". The server's own `code-server` binary doesn't need that socket.
code_server="$(ls -dt "$HOME"/.vscode-server/bin/*/bin/code-server 2>/dev/null | head -n1 || true)"

if [[ ! -x "$code_server" ]]; then
    echo "code-server not found; cannot install extensions." >&2
    exit 1
fi

extensions_json="$HOME/.vscode-server/extensions/extensions.json"
stamp_dir="$HOME/.vscode-server/.vsix-installed"
wait_timeout_s=300

# `customizations.vscode.extensions` from `devcontainer.json`, without comments
mapfile -t batch_ids < <(
    sed -n '/"extensions": \[/,/\]/p' "${script_dir}/devcontainer.json" |
        grep -v '^[[:space:]]*//' |
        grep -oE '"[A-Za-z0-9-]+\.[A-Za-z0-9-]+"' |
        tr -d '"'
)

batch_installed() {
    local id
    for id in "${batch_ids[@]}"; do
        grep -qiF "\"id\":\"${id}\"" "$extensions_json" 2>/dev/null || return 1
    done
}

# The server installs `customizations.vscode.extensions` while this script runs.
# Installing at the same time breaks in two ways:
# - `extensions.json` is shared between processes without a lock
# - a VSIX added before its dependency is hot-loaded by the running window and
#   fails with "Cannot activate ... depends on ..."
# The server doesn't log when it's done at the log level it's started with, so
# look for the result instead.
waited_s=0
until batch_installed; do
    if ((waited_s >= wait_timeout_s)); then
        echo "Extensions still missing after ${wait_timeout_s}s; installing VSIX files anyway." >&2
        break
    fi
    sleep 1
    waited_s=$((waited_s + 1))
done

mkdir -p "$stamp_dir"

shopt -s nullglob
for vsix_path in "$vsix_dir"/*.vsix; do
    [[ -f "$vsix_path" ]] || continue

    # This script runs on each attach, and reinstalling an extension that's
    # running makes the window reload it. Only install what changed.
    stamp="${stamp_dir}/$(sha256sum "$vsix_path" | cut -d' ' -f1)"
    [[ -e "$stamp" ]] && continue

    # `--force` since QA builds can differ while keeping the same version
    "$code_server" --install-extension "$vsix_path" --force
    touch "$stamp"
done
