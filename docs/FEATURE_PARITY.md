# Android feature ledger and acceptance gates

**Target:** Realme 15T, reported 8 GB physical RAM. **Current phone status: 0.2.0 APK installation/dashboard launch observed; Linux preparation fails on the Perl hard link before engine readiness.** A separate non-destructive 0.2.1 repair is implemented and host-regression-tested, but has not been verified on the phone. See [PHONE_REPAIR.md](PHONE_REPAIR.md).

**Delivery decision, 19 November 2026:** the required handoff is an ordinary installable APK, not technical Termux setup. The user explicitly selected **“Limited version nahi chahiye”** when offered an initial limited phone-only version, a server-assisted APK or retaining the full requirement. No reduced-scope app or server deployment is authorised by that selection. Full parity remains an unmet acceptance criterion. After the subsequent request to make the APK possible, a real native-hosted development APK was built, with the local engine bundled and automatic private Linux setup. This is not approval to reduce scope or claim a complete port. Do not present a wrapper, placeholder or bootstrap archive as completion.

The original packages are retained, but code presence ≠ dependency availability ≠ an end-to-end feature pass. This ledger groups product areas; it is **not an assertion that every upstream edge case has been enumerated or tested**. Exact full source manifests prevent source files from being silently discarded.

Legend:

- **Linux smoke passed:** only the specific test in VALIDATION.md ran on Linux x64.
- **Phone unverified:** no Realme ARM64 execution evidence yet.
- **Additional dependency:** needs an engine, provider, binary, service or permission not provisioned here.
- **Not provided:** this launcher does not implement that platform capability.

| Product area | What is preserved / required | Realme phone status |
|---|---|---|
| Original web interface and server | Published OpenMausBot package; root HTML, health, environment descriptor and PWA manifest served in Linux smoke | Phone unverified |
| Pairing, sessions, admin/client scopes | Upstream auth, service loopback trust, no development-owner bypass | Phone unverified; security regression gate required |
| Bots, profiles, pin/unread/duplicate/hide/delete | Original application/UI; no replacement data model | Phone unverified |
| Chats, channels/rooms, rosters, mentions, coordination | Original routing/runtime and event storage | Phone unverified |
| Groq model provider | Existing `server/drivers/groq.ts`; cloud key and currently available model required | Additional dependency; no paid request tested |
| Claude, Codex, Grok and custom CLI engines | Original drivers; each requires compatible ARM64 installation and sign-in | Additional dependency; not all engines installed |
| Generic OpenAI-compatible and custom ACP engines | Original multi-instance driver contracts retained | Additional dependency; phone unverified |
| Streaming, cancellation, reconnect, attachments | Original HTTP/event/file paths retained | Phone unverified |
| Shell/file tool approvals and questions | Original permission broker retained, not replaced with auto-allow | Phone unverified; never equate PRoot with isolation |
| Memory, recall, skills and shared skill library | Original stores, review switches and helper-model costs retained | Phone unverified |
| Routines, schedules, proactivity and incident handling | Original scheduler retained | Phone unverified; Android background killing is a blocker to an always-on guarantee |
| Team/playbook imports, bot sharing, templates | Original import/review/privacy code retained | Phone unverified; licensed org templates remain gated |
| Connected apps, OAuth, Composio, custom MCP | Original marketplace and permission paths retained | Additional dependency; no accounts connected |
| REA CLI and static JS inspection | Original REA 6.9.0; version + non-executing fixture analysis passed on Linux | Phone unverified |
| REA MCP in OpenMausBot | Documented explicit stdio configuration, not auto-enabled | Handshake and safe calls not tested on phone |
| REA APK/Flutter/signature/static metadata tools | Original full package retained | Per-tool platform/prerequisite checks required; signatures not inspected in this turn |
| REA native decompilers/JADX/JDK/Ghidra/IDA/Hopper/JEB | Integrations remain, external licensed tools not universally bundled | Additional dependency; some providers require a different OS/architecture |
| REA runtime capture/Frida/debuggers | Original interfaces retained | Frida optional package missing in Linux trial; Android attachment not authorised/tested |
| DuckDB-backed features | Native binding loaded, in-memory query passed on Linux | ARM64 glibc probe required on phone; no direct Bionic binding assumed |
| SVG/chart rendering | Resvg rendered a tiny SVG to PNG on Linux | ARM64 runtime probe required on phone |
| 1Password/Bitwarden/login integrations | Original integrations; 1Password module-import smoke only | No vault/auth operations tested |
| Browser for bots, profiles, live preview | Original engine integration; browser binaries/system libs not installed by this kit | Additional dependency; not certified in PRoot; do not silently disable sandboxing |
| Cloud Linux computers | Original provider integrations, account and external service required | Not phone-local; not provisioned/tested |
| Isolated Local VM/Docker/Podman desktops | Original code remains in upstream package | **Not provided by ordinary unrooted PRoot** |
| Secure per-bot kernel sandbox | Needs supported namespaces/seccomp/cgroups and original host certification | **Not provided/certified by this PRoot launcher** |
| Controlling the Android home screen/other apps | Desktop/adb code is not a native Android accessibility implementation | **Not provided**; needs explicit-consent Android work or a separately authorised device bridge |
| USB/adb phone takeover, scrcpy | Original desktop-to-device integration retained | Not equivalent to self-control; additional bridge/authorisation required |
| Voice calls, dictation, cloud TTS, platform voices | Server TTS differs from desktop microphone/voice capabilities | Cloud credentials/native audio work required; phone unverified |
| macOS saved steps and platform-only helpers | Preserved upstream source; platform guards untouched | **Not Android features**; new platform implementations would be required |
| Push notifications and mobile foreground lifecycle | APK has a visible, explicitly started foreground service/Stop notification; no boot autorun or native push transport | Phone lifecycle unverified; no always-on guarantee |
| Enterprise/team/admin/white-label capabilities | Source-available enterprise adapter and upstream entitlements unchanged | License/partner agreement may be required; no bypass implemented |
| Native installable Android APK | Signed native dashboard/service APK with original local engine/source archives; separate small repair imports those full archives from the original installed APK without touching its private data | **0.2.0 installed/launched; Linux extraction failed; repaired engine boot still unverified** |
| Fully offline AI inference | No model weights or on-device inference backend installed | **Not provided**; Groq inference requires internet |

## Feature switches are not portability fixes

The pinned upstream switch documentation and `server/config.ts` are retained. This includes `skillAuthoring`, `skillReview`, `showToolCalls`, `browser`, `sharedComputers`, `claudeUserMcp`, `claudeUserSkills`, `smartSetupChoices`, `autoRecall`, `skillsLibrary`, `roomMemoryCapture`, `parallelRoomJobs`, `acpPlanLines`, `agentsToolBridge`, `savedSteps`, `usbPhoneTakeover`, `skillReviewSteps` and `shareLearnedSkills`.

This bootstrap does not flip those switches to manufacture a passing capability list. A switch cannot create kernel features, a microphone bridge, a model subscription or a license entitlement.

## Required next gates

1. **Device boot:** record actual Android version/ABI, free space, Node/SDK native probes, logs, clean start/stop, thermal/memory behavior. No phone claim until this passes.
2. **Security:** pairing as owner/client, wrong/expired/revoked token denial, cross-origin denial, no local anonymous ownership, approval Allow/Deny/cancel, safe file boundaries. PRoot remains a documented non-boundary.
3. **Core workflow:** one Groq message with user-owned credentials, streaming/cancel, restart persistence, attachments, bot CRUD, rooms, model switches and a routine while foregrounded. Establish measured resource limits.
4. **Tools and integrations:** REA MCP handshake and safe static fixture; record each operation's actual availability. Validate every requested OAuth/MCP integration separately. Never attach to another app without authorisation.
5. **Android-native bridge:** design a foreground service and explicitly consented Accessibility/MediaProjection/audio/notification integration as needed. Preserve the existing approval broker. Separate phone UI from process-hosting architecture; a web wrapper is not the missing backend.
6. **Long-running reliability:** foreground/background/reboot/battery-saver/network-loss tests on Realme, with visible state and recovery, not a promise Android cannot enforce.
7. **Computers and isolation:** either retain these as clearly external services, or select a genuinely supported privileged/virtualised environment after explicit review. Do not label PRoot as Docker or a VM.
8. **Production release packaging:** the signed development APK may be used for an explicitly labelled trial; a complete/production release still requires the feature/security/device tests above, installed-behavior verification and a full license/dependency inventory. Publish the actual size/checksum. Do not pad it to resemble a desktop installer.

A complete phone-only, feature-for-feature replacement is a substantial porting project, not a file-format conversion. Some platform-only or externally hosted features require changed architecture, not merely a larger APK.
