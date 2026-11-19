#!/usr/bin/env bash
# Called by install-termux.sh inside the dedicated Ubuntu PRoot only.
set -euo pipefail
umask 022

[[ "$(id -u)" == 0 ]] || { printf 'Ubuntu setup needs PRoot guest root (not Android root).\n' >&2; exit 2; }
case "$(uname -m)" in
  aarch64|arm64) ;;
  *) printf 'Expected ARM64 Ubuntu userland.\n' >&2; exit 2 ;;
esac
[[ -f /etc/os-release ]] && . /etc/os-release
[[ "${ID:-}" == ubuntu ]] || { printf 'This setup is for Ubuntu PRoot only.\n' >&2; exit 2; }
[[ -f /mnt/terminator-bootstrap/TERMINATOR_KIT ]] || { printf 'Missing reviewed bootstrap files.\n' >&2; exit 2; }

app=/opt/terminator
mkdir -p "$app/bootstrap" "$app/node" "$app/runtime"
cp -R /mnt/terminator-bootstrap/. "$app/bootstrap/"
chmod -R u+rwX,go+rX "$app/bootstrap"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates git nodejs npm python3 build-essential procps passwd

if ! id terminator >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash terminator
fi
# Never replace a user that was supplied by an unexpected existing image.
[[ "$(getent passwd terminator | cut -d: -f6)" == /home/terminator ]] || {
  printf 'Unexpected terminator home directory; refusing to continue.\n' >&2; exit 2;
}
install -d -m 700 -o terminator -g terminator /home/terminator/.openmausbot

cp "$app/bootstrap/android/node/package.json" "$app/bootstrap/android/node/package-lock.json" "$app/node/"
# Bootstrap Node is Ubuntu's nodejs; the npm-distributed Node then supplies the
# exact glibc ARM64 runtime required by both upstream packages.
npm ci --prefix "$app/node" --no-audit --no-fund
export PATH="$app/node/node_modules/node/bin:$PATH"
node -e 'if (process.versions.node !== "24.22.1" || process.platform !== "linux" || process.arch !== "arm64") throw Error("Incorrect Node runtime")'
cp "$app/bootstrap/android/runtime/package.json" "$app/bootstrap/android/runtime/package-lock.json" "$app/runtime/"
# Do not omit optional deps: DuckDB's platform binding is packaged as optional.
# npm may still be unable to install REA's optional Frida; the report exposes it.
npm ci --prefix "$app/runtime" --no-audit --no-fund
node "$app/bootstrap/android/runtime-smoke.mjs" --runtime "$app/runtime" > "$app/install-report.json"
cat "$app/install-report.json"
printf '\nOriginal upstream packages installed. No AI credentials were requested or saved.\n'
printf 'Browser automation, Android screen control and full feature parity remain unverified.\n'
