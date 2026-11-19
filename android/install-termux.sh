#!/usr/bin/env bash
# Experimental, opt-in bootstrap. Run with bash inside ARM64 Termux, not Android's sh.
set -euo pipefail

usage() {
  cat <<'HELP'
Usage: bash android/install-termux.sh --check | --install [--yes]

--check    Read-only phone preflight; never installs packages.
--install  Install a dedicated 'terminator' Ubuntu PRoot and pinned upstream packages.
--yes      Confirm the documented installation without an interactive prompt.

This is NOT an APK or an all-features Android certification. Installation needs
internet and at least 8 GiB free (10 GiB recommended). It executes apt/npm vendor
installation scripts. It does not root the phone or configure paid providers.
HELP
}

mode=check
confirmed=0
for argument in "$@"; do
  case "$argument" in
    --check) mode=check ;;
    --install) mode=install ;;
    --yes) confirmed=1 ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$argument" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${PREFIX:-}" || "$PREFIX" != /data/*/files/usr || ! -x "${PREFIX}/bin/pkg" ]]; then
  printf 'Run this inside the official Termux app, from its private home directory.\n' >&2
  exit 2
fi
if [[ "$(id -u)" == 0 ]]; then
  printf 'Do not run Termux as root. The installer uses unprivileged PRoot.\n' >&2
  exit 2
fi
case "$(uname -m)" in
  aarch64|arm64) ;;
  *) printf 'This device trial targets ARM64 (aarch64) only.\n' >&2; exit 2 ;;
esac

android_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$android_dir/.." && pwd)"
case "$project_dir" in
  /sdcard/*|/storage/*) printf 'Copy/extract the kit into Termux $HOME, not shared storage.\n' >&2; exit 2 ;;
esac
free_mib="$(df -Pm "$HOME" | awk 'NR == 2 {print $4}')"
if [[ ! "$free_mib" =~ ^[0-9]+$ ]] || (( free_mib < 8192 )); then
  printf 'At least 8192 MiB free is required; detected: %s MiB. No install started.\n' "${free_mib:-unknown}" >&2
  exit 2
fi
printf 'ARM64 Termux preflight passed; free space: %s MiB.\n' "$free_mib"
printf 'Target: 8 GB physical RAM; start with one bot. Expanded RAM is not physical RAM.\n'
printf 'Full Android parity: NOT CERTIFIED. PRoot is not a security sandbox or a VM.\n'
if [[ "$mode" == check ]]; then
  printf 'No changes made. Review docs/ANDROID.md, then use --install if you agree.\n'
  exit 0
fi
if (( ! confirmed )); then
  printf '\nThis installs packages and runs upstream lifecycle scripts. Type INSTALL to continue: '
  read -r answer
  [[ "$answer" == INSTALL ]] || { printf 'Cancelled; no packages installed.\n'; exit 1; }
fi

# Package management happens only after --install and explicit confirmation.
pkg update -y
pkg install -y proot-distro python

runtime_base="$PREFIX/var/lib/proot-distro"
created=0
if [[ ! -d "$runtime_base/installed-rootfs/terminator" && ! -d "$runtime_base/containers/terminator" ]]; then
  help_text="$(proot-distro install --help 2>&1)"
  if [[ "$help_text" == *"--name"* ]]; then
    # PRoot-Distro 5+: OCI userland image, not a running Docker container.
    proot-distro install --name terminator ubuntu:24.04
  else
    # PRoot-Distro 4: its maintained Ubuntu alias, whose OS version may differ.
    proot-distro install --override-alias terminator ubuntu
  fi
  created=1
fi
if (( ! created )); then
  if ! proot-distro login terminator --isolated -- /usr/bin/test -f /opt/terminator/bootstrap/TERMINATOR_KIT; then
    printf 'A non-toolkit container named terminator exists. Refusing to modify it.\n' >&2
    exit 2
  fi
fi

stage="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/terminator-bootstrap.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/android/node" "$stage/android/runtime" "$stage/tools"
for file in install-ubuntu.sh start-ubuntu.sh runtime-smoke.mjs; do
  cp -- "$android_dir/$file" "$stage/android/$file"
done
for package in node runtime; do
  cp -- "$android_dir/$package/package.json" "$android_dir/$package/package-lock.json" "$stage/android/$package/"
done
cp -- "$project_dir/tools/phone_doctor.py" "$stage/tools/phone_doctor.py"
printf 'Terminator experimental upstream runtime toolkit\n' > "$stage/TERMINATOR_KIT"
proot-distro login terminator --isolated --bind "$stage:/mnt/terminator-bootstrap" -- \
  /bin/bash /mnt/terminator-bootstrap/android/install-ubuntu.sh
printf '\nInstallation completed, not Android-certified. To start:\n  bash %q/start-termux.sh\n' "$android_dir"
printf 'For a read-only diagnostic:\n  bash %q/start-termux.sh doctor\n' "$android_dir"
