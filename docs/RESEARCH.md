# Investigation: OpenMausBot, REA and the Android target

Recorded **19 November 2026**. This report distinguishes source inspection, metadata, Linux execution, and untested phone behavior.

## 1. What was found in Drive

Read-only Drive queries found the two files named in the request:

| Filename | Stored bytes | What the filename/metadata indicates |
|---|---:|---|
| `OpenMausBot-setup.exe` | 270,463,514 | Windows installer; about 257.9 MiB |
| `OpenMausBot-amd64.deb` | 276,585,448 | Debian/Ubuntu x86-64 package; about 263.8 MiB |

These byte counts match the corresponding assets in [upstream release v0.1.169](https://github.com/milind-soni/OpenMausBot/releases/tag/v0.1.169). **A size match does not authenticate the binary.** The Drive installers were not downloaded, executed, decompiled or signature-verified. Each exceeds the connector's 100 MiB binary-download limit.

The four recent split-APK uploads from the screenshot are also present:

| Filename | Stored bytes |
|---|---:|
| `base.apk` | 82,509,565 |
| `split_config.arm64_v8a.apk` | 47,922,659 |
| `split_config.en.apk` | 135,577 |
| `split_config.xhdpi.apk` | 340,448 |

Their APK contents have **not** been read, so their package ID, app identity, version, signer and relation to Grok/Groq remain unknown. No separately named Groq/Grok source project was found by the relevant filename search. This does not establish that no such project exists elsewhere in Drive. Private Drive IDs/links and unrelated files were not copied into the repository.

## 2. OpenMausBot architecture

Sources: [release README](https://github.com/milind-soni/OpenMausBot/blob/b832de78c43c8d76e92d6f50fb1a8d33be364480/README.md), [self-hosting](https://github.com/milind-soni/OpenMausBot/blob/b832de78c43c8d76e92d6f50fb1a8d33be364480/docs/self-hosting.md), [package build](https://github.com/milind-soni/OpenMausBot/blob/b832de78c43c8d76e92d6f50fb1a8d33be364480/scripts/build-npm-package.mjs).

- Desktop Electron is a shell around a substantial Node/TypeScript harness and React web UI. A supported headless/server distribution already exists; rebuilding a thin chat interface would unnecessarily discard existing systems.
- The published `openmausbot@0.1.169` package includes the compiled server, original web assets, skills and optional enterprise layer. Its compressed npm archive is **21,131,154 bytes**, not the Windows installer's 270 MB. Different packaging overhead does not imply different feature counts.
- The actual [Groq driver](https://github.com/milind-soni/OpenMausBot/blob/b832de78c43c8d76e92d6f50fb1a8d33be364480/server/drivers/groq.ts) is already present. It uses an OpenAI-compatible Groq cloud endpoint, discovers models, and retains the normal runtime/tool integration. Groq and xAI Grok are distinct.
- The [phone web-app guide](https://github.com/milind-soni/OpenMausBot/blob/b832de78c43c8d76e92d6f50fb1a8d33be364480/docs/phone-web-app.md) explicitly says installation does not add offline chat, push notifications or native phone computer control. A phone client connected to a PC is not a phone-hosted backend.
- Node 24+ is required. DuckDB, Resvg and the 1Password SDK are native dependencies in the npm server package. DuckDB publishes Linux ARM64 bindings but not a direct Android/Bionic binding in the inspected version; Resvg does publish an Android ARM64 package. Do not equate Linux ARM64/glibc with Android ARM64/Bionic.
- Ubuntu in PRoot is therefore a plausible compatibility route for the **original Linux ARM64** distribution, not proof that every feature is portable. It supplies no Docker daemon, VM kernel, Android accessibility service or certified per-bot sandbox.
- Upstream self-hosting separates server-capable features from desktop-only voice/host-control behavior. Its host doctor and runtime contracts include architecture and security-boundary assumptions. We did not disable those assumptions to claim parity.

Initial examination also saw main at `c444029f…` / version `0.1.170`. The kit deliberately uses **the released `0.1.169` source and package**, not a mixture of a moving main branch and the older Drive release.

## 3. What REA is and is not

Sources: [REA README](https://github.com/morluto/rea/blob/bd5c985b3fc8b3f26caaa94d88b66a0953dc66a8/README.md), [package](https://github.com/morluto/rea/blob/bd5c985b3fc8b3f26caaa94d88b66a0953dc66a8/package.json), [Termux workflow](https://github.com/morluto/rea/blob/bd5c985b3fc8b3f26caaa94d88b66a0953dc66a8/.github/workflows/real-termux.yml).

REA is an evidence-oriented CLI/MCP analysis toolkit, not a universal EXE-to-APK converter or an AI model by itself. The source is MIT, but externally supplied tools keep their licenses.

- Its package requires Node `^22.23.4 || ^24.22.1 || >=26.12.1`; **24.22.1** satisfies both projects and matches REA's `.nvmrc`.
- It has `build:termux`/`compile:termux` and an opt-in real-Termux browser workflow. That workflow uses an **x86-64 Android emulator**, not a Realme ARM64 device, so its existence is not certification of this phone or of all REA tools.
- Static JavaScript analysis does not need a native decompiler. JADX/JDK, Ghidra, adb, browser engines, Frida, and proprietary tools are separate requirements for their respective operations.
- The published package contains bundled runtime dependencies as well as separately resolved native/optional components. The entire original npm package is installed, not a hand-picked list of CLI commands.
- The Linux trial returned real Evidence for a small JavaScript fixture **without executing the fixture**. That does not establish full analysis coverage of the desktop installers or unknown APKs.
- Frida was an unmet optional dependency in the Linux install and is explicitly reported as missing. We do not call runtime instrumentation available merely because npm exited successfully.

Because OpenMausBot's source is already available, source inspection and license-preserving reuse are preferable to trying to recover its original source by decompiling an installer.

## 4. Exact source preservation

The complete source inventory is in [`upstream/lock.json`](../upstream/lock.json) and its seven manifests:

| Project | Revision (short; full ID in lock) | Tracked blobs | Original blob bytes |
|---|---|---:|---:|
| OpenMausBot release | `b832de78c43c` | 8,668 | 254,771,798 |
| REA | `bd5c985b3fc8` | 9,257 | 111,402,663 |
| REA / binwalk | `4fdab3d464d9` | 210 | 2,182,544 |
| REA / ghidra-nativeaot | `effeb734fc57` | 64 | 1,135,345 |
| REA / jadx-headless-mcp | `5844800a486d` | 50 | 270,622 |
| REA / unblob | `1fcc7a0a584a` | 3,086 | 2,147,588 |
| REA / wakaru | `8219bf5016a0` | 1,504 | 18,914,479 |
| **Total** | | **22,839** | **390,825,039** |

`tools/upstreams.py` reproduces each original root Git tree hash, fetches the precise public commit into a temporary bare object store, exports each raw Git blob, and checks every byte count/hash/executable bit. It does not switch this working repository's branch. All five gitlinks are followed using their separately pinned manifests. Existing modified source trees are refused, not overwritten or silently accepted.

Why raw objects instead of a naive ZIP/archive import? Export attributes can change working-tree line endings, and one unblob fixture contains a control-character filename whose API rendering does not round-trip unchanged. The inventory uses the original raw Git path/object bytes. No source lines are truncated for a token or package-size limit.

**214 tracked symlink target blobs** are retained byte-for-byte as inert regular text files, while their original Git mode `120000` remains in the manifest. This deliberately avoids activating hostile/absolute/dangling symlink fixtures. It is an audit representation, not an unchanged symlink-capable checkout for upstream fixture tests.

**External LFS assets are not materialized:** unblob contains **2,506 Git LFS pointer files** referring to **892 unique external fixture objects** totalling **222,010,238 payload bytes**. The raw pointer blobs are preserved and verified as Git stores them; the external binary contents were not fetched. The tool/lock explicitly report `gitLfsUniqueObjectsNotFetched` and related totals. Running all of unblob's fixture tests would require separately obtaining those objects through its official Git LFS workflow; a successful Git-blob verification does not certify a fully materialized fixture tree.

This is a Git-blob-level completeness/integrity result for those pinned repository trees. It is **not** a line-by-line semantic review, an exhaustive feature test, an assertion that all external assets/dependencies/services are included, or a license to copy closed-source software.

## 5. What can realistically come next on this phone

The current kit is an **experimental deployment path** for the preserved server/UI and REA packages. It has not run on the Realme yet. See [the phone guide](ANDROID.md) and [feature acceptance gates](FEATURE_PARITY.md).

A full native Android application requires decisions about background execution, Android-native control/audio/push permissions, local credential protection, supported ARM64 native libraries, engine binaries, isolation and externally hosted computers. Rooting alone would not automatically implement those features or provide appropriate kernel support.

A larger APK is not evidence of completeness. The Linux x64 test installation of the two upstream packages occupied about **447 MiB** before the separate Node runtime, Ubuntu userland and caches. The phone's installed footprint will differ. Package only the components actually needed, publish their checksums and measured behavior, and never add padding merely to reach 250–260 MB.
