# Native phone runtime APK (development)

This is an actual Android Activity + foreground Service hosting the original OpenMausBot/REA Node packages in a private ARM64 Linux/PRoot environment. It is **not** a remote-server-only WebView wrapper. There is no dependency on the Termux app and no terminal commands in the phone setup flow.

It is also **not full Android feature parity or a production release**. The user's full-feature requirement remains open. All original pinned Git source blobs are included in an exportable source archive; executable dependencies are separately versioned. Android self-control, Docker/VM isolation, offline inference and optional third-party engines are not magically provided by retaining their integrations.

## Architecture / security decisions

- Android API 26 minimum; target API **28 intentionally**, as current private writable Linux executables need legacy execution policy. Modern Android may display an older-app warning. This is a development constraint, not a Play Store-ready release or a recommendation to disable Play Protect.
- A visible, explicitly started foreground service prepares the environment, launches the engine, and offers Stop in its notification. It does not start on boot. Android can still terminate it.
- First preparation downloads a pinned Ubuntu 24.04 distribution (65,051,348 bytes) **directly from its existing third-party distribution repository**, verifies SHA-256, and extracts it into app-private storage. No unverified installer script is run. Its package copyright/source information remains in the downloaded distribution.
- Node 24.22.1, OpenMausBot 0.1.169 and REA 6.9.0 are bundled. Original upstream feature, approval, licensing and provider code is not replaced.
- The server binds phone loopback only, with `OMB_LOOPBACK_TRUST=service`. A per-launch random owner capability is delivered on private process stdin using upstream's `OMB_CLI_OWNER_STDIN` contract. The native host uses it only for upstream's single-use pairing exchange, then installs the returned HttpOnly cookie into its own WebView. No owner-secret JavaScript bridge or anonymous-owner bypass exists.
- External HTTPS pages open in the user's browser, not the privileged local WebView. File selection uses Android's document picker; there is no broad storage permission. Microphone access needs an explicit OS grant and an origin check.
- PRoot and a common Android UID are **not a bot isolation boundary**. Only use trusted tasks and the original approval controls. No Accessibility, screen-capture, root, device-admin or boot permissions are requested.
- Source export uses the document picker. No secrets, runtime workspace or generated signing private key belong in Git or the APK source archive.

## Reproduce (Linux developer environment)

`python3 tools/build_apk.py --prepare --build` fetches hash-pinned compiler components via the GitHub API/PyPI, assembles the ARM64 npm runtime using its lockfile, verifies the complete upstream blob inventory, compiles Java/XZ to DEX, aligns and signs a test APK. Build artifacts, downloaded OS images, toolchains, dependencies and private signing material are ignored.

See `docs/APK.md` and `docs/FEATURE_PARITY.md` for the exact validation boundary. A verified APK signature does not establish Android runtime success or full feature parity.
