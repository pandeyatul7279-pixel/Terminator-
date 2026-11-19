#!/usr/bin/env bash
set -euo pipefail
umask 077

app=/opt/terminator
export PATH="$app/node/node_modules/node/bin:$app/runtime/node_modules/.bin:/usr/local/bin:/usr/bin:/bin"
[[ "$(id -u)" != 0 ]] || { printf 'Start with proot-distro login --user terminator.\n' >&2; exit 2; }
[[ "$HOME" == /home/terminator ]] || { printf 'Unexpected guest home; refusing to change the workspace.\n' >&2; exit 2; }
export OMB_DATA_DIR="$HOME/.openmausbot"
# Other Android apps can reach phone loopback too. Use upstream's supported
# service-trust pairing flow, rather than treating every local caller as owner.
export OMB_LOOPBACK_TRUST=service
# Heap limit only, not a total-process/RAM guarantee. No CPU count or swap changes.
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1024}"

case "${1:-}" in
  doctor)
    shift
    exec node "$app/bootstrap/android/runtime-smoke.mjs" --runtime "$app/runtime" "$@"
    ;;
  rea)
    shift
    exec node "$app/runtime/node_modules/rea-agents/scripts/rea.mjs" "$@"
    ;;
  shell)
    shift
    exec /bin/bash "$@"
    ;;
esac
printf 'Experimental phone-hosted upstream server. Keep Termux open; Ctrl+C stops it.\n'
printf 'No Docker/VM boundary or native Android control is provided by this launcher.\n'
# Keep the upstream pairing, permission broker and licensing checks untouched.
# Loopback is intentional on the phone: Chrome and the backend are on that same
# phone. Do NOT use this address for a server on a different computer.
exec node "$app/runtime/node_modules/openmausbot/cli.js" serve --port 8799 \
  --data-dir "$OMB_DATA_DIR" "$@"
