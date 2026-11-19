#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  printf 'Usage: bash android/start-termux.sh [serve options | doctor | rea COMMAND... | shell]\n'
  printf 'Starts the existing dedicated PRoot; never installs or resets it.\n'
  exit 0
fi
if ! command -v proot-distro >/dev/null 2>&1; then
  printf 'Run the reviewed android/install-termux.sh --install inside Termux first.\n' >&2
  exit 2
fi
# --isolated avoids automatic shared-storage and Termux-home mounts. This is
# data minimisation, not a security boundary: all PRoot processes share an UID.
if [[ "${1:-}" == doctor ]]; then
  printf '%s\n' '--- Android host (read-only) ---'
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  python3 "$script_dir/../tools/phone_doctor.py" --json
  printf '%s\n' '--- Ubuntu runtime (read-only module probes) ---'
fi
exec proot-distro login terminator --isolated --user terminator -- \
  /bin/bash /opt/terminator/bootstrap/android/start-ubuntu.sh "$@"
