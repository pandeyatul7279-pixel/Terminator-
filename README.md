# Terminator — native Android runtime port

Targets a **Realme 15T with 8 GB physical RAM**. The additional 12 GB of memory expansion is storage-backed, not another 12 GB of physical RAM.

> **A signed development APK is now built. It is not a completed all-features Android port, an offline AI model, or a phone-certified release.** No physical Realme or Android system emulator was available. Full feature parity remains an unmet acceptance criterion, not a requirement the user agreed to drop.

## APK — actual native host, not a remote-only wrapper

`artifacts/Terminator-0.2.0-arm64-test.apk` contains a native dashboard and foreground service, ARM64 Node 24.22.1, the original OpenMausBot 0.1.169/REA 6.9.0 runtime, an exportable archive of **all 22,839 verified original Git source blobs**, and PRoot/talloc/XZ corresponding source. The app automatically downloads/verifies/prepares its private Linux distribution on first explicit Start; **no Termux app or phone terminal commands are needed**. Source archives are large and are not padding.

The native host retains service-trust authentication, uses upstream's private-stdin owner bootstrap and single-use cookie pairing, supports document-picker file import/attachments and explicit microphone permission, and offers an opt-in original REA MCP connection test. No provider key, subscription, model weights, root/Accessibility takeover or Docker/VM sandbox is bundled.

**Phone flow and exact limits: [APK guide](docs/APK.md).** First setup downloads approximately 65 MB and needs at least 1.6 GB free space. The intentionally legacy target API 28 execution policy may cause an older-app warning; do not disable phone security protections. Realme installation/boot, workflows and background reliability remain untested.

The user explicitly declined a reduced-scope substitute and then asked to make the APK possible. This development artifact is concrete porting progress, **not a declaration that the full request is complete**. See the [feature ledger and acceptance gates](docs/FEATURE_PARITY.md) and [test record](docs/VALIDATION.md).

## Earlier developer runtime investigation

- Installs a dedicated, unprivileged **Ubuntu PRoot inside Termux**, without modifying an existing Ubuntu container.
- Pins the **unmodified OpenMausBot 0.1.169 server/web UI**, **REA 6.9.0**, and **Node 24.22.1**. The OpenMausBot version matches the release whose installer sizes were seen in Drive.
- Uses upstream's pairing/approval/licensing mechanisms, including service-mode loopback trust. It does not silently grant local callers ownership, connect accounts, or save keys.
- Preserves **22,839 original tracked Git blobs** across both repositories and all five REA submodules using a separately downloadable, byte-verified source inventory.
- Provides read-only phone diagnostics, native runtime probes, a bounded APK identity/split inspector, tests, and a clearly marked feature-gap ledger.

**Developer reference only:** [experimental Realme/Termux installation](docs/ANDROID.md). This is not the user-requested APK handoff.

Other documentation:

- [Investigation and exact source provenance](docs/RESEARCH.md)
- [Feature parity and acceptance gates](docs/FEATURE_PARITY.md)
- [Security and licensing boundaries](docs/SECURITY_AND_LICENSES.md)
- [What was actually tested](docs/VALIDATION.md)

## Phone trial

After reviewing the guide, inside ARM64 Termux, from this extracted kit:

```sh
bash android/install-termux.sh --check
bash android/install-termux.sh --install
bash android/start-termux.sh
```

Installation is opt-in, needs internet and at least **8 GiB free storage** (10 GiB recommended), and runs apt/npm installation scripts. Android root is not required. The runtime downloads are intentionally **not padded to a particular installer size**.

Open the pairing link printed **on that same phone**. The server listens at `http://127.0.0.1:8799` on the phone, not on another computer. Groq is already an upstream provider: enter your key only into the app's provider settings, **never into chat or Git**. Groq inference still uses the internet.

```sh
bash android/start-termux.sh doctor
bash android/start-termux.sh rea --version
```

## Reproduce the source-preservation check

Python 3.10+ and Git are sufficient. These commands never execute downloaded source:

```sh
python3 tools/upstreams.py list
python3 tools/upstreams.py fetch
python3 tools/upstreams.py verify
```

Downloads live under ignored `.cache/sources`, not in the tracked repository. Every blob, byte count and executable bit is checked; the manifests reproduce all seven original root Git tree hashes. REA's 214 tracked symlink target blobs are preserved as **inert text**, not activated symlinks. The source audit tree is consequently not a drop-in checkout for symlink-dependent upstream fixture tests.

The unblob submodule also tracks **2,506 Git LFS pointer files** referring to **892 external fixture objects** (222,010,238 payload bytes). Their original pointer blobs are verified, but those external payloads are **not downloaded/materialized**. The verifier reports this explicitly; this is not a complete upstream test-fixture checkout.

This preserves the specified Git source revisions. It does **not** assert that every line was manually reviewed, that every feature runs on Android, that external assets/dependencies are vendored, or that a proprietary APK's original source can be recovered.

## Developer checks

The runtime commands below are for Linux/glibc, not native Termux/Bionic. The native APK build is `python3 tools/build_apk.py --prepare --build`; Java extractor checks are `python3 tools/test_apk_java.py -v`. Phone users should follow the [APK guide](docs/APK.md), not these developer commands.

```sh
make test
make runtime-install   # Node 24.22.1 required; downloads upstream code
make runtime-test
make kit               # artifacts/terminator-android-kit.tar.gz
```

The archive contains the launcher, documentation, checksums and full source **manifests**, not a prebuilt Android app or all downloaded dependencies. Its installer retrieves the actual runtime; full upstream sources are fetched separately with the commands above.

New toolkit code is Apache-2.0. Upstreams and dependencies keep their own licenses. OpenMausBot's `enterprise/` is **not** Apache-2.0; commercial features and trademarks are not granted by this kit. See [the licensing notes](docs/SECURITY_AND_LICENSES.md).
