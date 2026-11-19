# Android APK delivery status

The user requires an ordinary downloadable APK with the full original feature requirements. They declined a reduced-scope replacement. **The development build is progress toward that request, not acceptance of reduced scope and not a full-parity release.**

## What the development APK contains

- A native Android dashboard, automatic private Linux setup, foreground engine service and Stop notification.
- The original local OpenMausBot 0.1.169 UI/backend, ARM64 Node 24.22.1 and REA 6.9.0, not a remote-host-only website wrapper.
- Original upstream service-trust authentication and native-host-mediated single-use pairing; approvals and licensing are not bypassed.
- Android document-picker file import, attachment selection, explicit microphone consent, source export and a user-invoked REA MCP connection/test flow.
- An exportable archive of every verified original Git source blob and all five REA submodules. Git LFS **pointer** blobs are included; 892 external fixture payload objects remain absent. Do not call this a completely materialized LFS checkout.
- PRoot/talloc/XZ corresponding source and licenses, plus runtime provenance.

## Ordinary phone flow

1. Download/install the APK on an ARM64 Android 8+ phone. The app intentionally targets API 28 for private Linux executable compatibility; Android may show an older-app warning. Do not disable Play Protect or other phone security protections. If the OS blocks installation, stop and report the message rather than bypassing it.
2. Open **Terminator Test → Prepare & start bot**. The app explains and requests consent for an approximately 65 MB first-use Linux download. Keep at least **1.6 GB free** and keep the app open while it prepares. No Termux app or terminal commands are required.
3. Once the actual engine checks and owner pairing pass, tap **Open bot**. Configure the original provider settings with your own account/key; no paid key or subscription is included. Groq cloud inference needs internet.
4. **Connect REA tools** explicitly tests the original MCP endpoint before enabling the bundled integration. Review tool access and original approvals. External decompilers and runtime instrumentation still have separate prerequisites.
5. Stop from the dashboard or notification. Data persists in app-private storage; **uninstalling deletes it**. No boot receiver or silent autorun is provided.

## Remaining full-parity blockers

- Realme installation/boot, modern Android execution policy, native ARM64 modules under Android PRoot, WebView workflows and long-running behavior are not certified by Linux or compiler tests.
- No native Android Accessibility/MediaProjection self-control bridge is implemented. The APK does not request those permissions or claim phone takeover.
- PRoot is not Docker, a VM or a per-bot kernel security sandbox. Those original integrations need a supported execution host or substantial additional work, not a hidden feature flag.
- Optional CLI engines, Ghidra/JADX/JDK/Frida/browser binaries, third-party subscriptions and OAuth accounts are not all provisioned or tested. Retaining their code does not make them available.
- No on-device inference model is bundled; no offline-AI claim is made.
- Enterprise entitlements and trademark restrictions remain as upstream supplies them.

## Build evidence

`tools/build_apk.py` produces the APK, checksum, signing-certificate fingerprints and build manifest under ignored `artifacts/`. It must successfully compile the real application, build DEX, align the archive, sign it and verify its APK signatures before any artifact is presented. Java archive-extraction security tests and upstream authentication integration tests are separate gates. An APK signature pass is **not a device/feature acceptance pass**.

No desktop installer is renamed, converted or padded to obtain the APK size. Generated private signing material is excluded from source exports and Git.

## Private download handoff

An Arena file-viewer path is not a public HTTP download URL. The current sandbox preview also requires a traffic-access header; do not give an unauthenticated preview URL to the user as a working external download or expose sandbox credentials to make it work. The connected Drive workspace uploader has a 100 MB limit, smaller than this APK.

`.github/workflows/private-apk-download.yml` rebuilds the complete development bundle on a hosted runner and stores it **only in an owner-only draft release**, never a public release or public workflow artifact. It verifies uploaded sizes and an account-token-free, file-scoped download redirect. An authorised maintainer can issue a fresh, short-lived signed asset URL to the owner without sharing a GitHub or sandbox credential. Do not persist or publicly post the signed URL.

This is an internal evaluation handoff: the preserved `enterprise/` license explicitly prohibits redistribution without a partner agreement. Keeping entitlement checks intact does **not** grant permission for public binary/source redistribution. Do not publish this draft. The CI build generates a new development signing key; it is not an in-place update for a differently signed local APK. Never suggest uninstalling an existing app without warning that its private data will be deleted. A download check still does not certify phone boot or full feature parity.
