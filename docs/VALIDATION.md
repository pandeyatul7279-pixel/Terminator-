# Validation record

Recorded 19 November 2026. **Execution environment: Linux x64 sandbox, with additional ARM64 Linux user-mode emulation, not the Realme 15T.** No Android system emulator or physical phone was available for installation tests. A real native Activity/foreground Service application has now been compiled to DEX and packaged, aligned, signed and signature-verified as an APK. These build and Linux tests are not evidence of successful Android installation or full feature parity.

**Delivery status:** the user explicitly declined reduced-scope replacements, then requested an APK implementation. The signed development APK is porting progress; **the complete full-feature requirement remains unmet**. The earlier `terminator-android-kit.tar.gz` remains a separate developer experiment, not the accepted handoff.

## Native APK build and additional checks

- `python3 tools/build_apk.py --prepare --build`: real Java sources and XZ decoder compiled with Eclipse ECJ; Android API 35 resource linking, D8 DEX compilation, zip alignment, RSA-3072 test signing. **APK Signature Schemes v2 and v3 verified**. Exact artifact size/hash/certificate are in `artifacts/Terminator-0.2.0-build.json` and `.signature.txt`; no private signing material is included in exports or Git.
- **19 Java extractor tests passed** via `python3 tools/test_apk_java.py -v`: traversal, link-parent writes, escaping links, hard-link targets, checksum tampering, truncation, duplicate/fresh-directory refusal, PAX long names, execute/setuid permissions and legitimate POSIX colon/backslash filenames.
- The **exact shipped Java extractor** also extracted the real Ubuntu archive (**7,507 files /353,013,771 payload bytes /1,132 links**) and the real bundled engine archive (**13,824 files /551,347,697 payload bytes /19 links**) successfully in Linux with UTF-8 paths. Setuid/device ownership is not restored; symlinks are deferred and confined. This is not an Android storage test.
- ARM64 **Node 24.22.1**, a DuckDB `SELECT 42` query, resvg PNG rendering and 1Password module import passed under QEMU 7.2.22 with the downloaded Ubuntu libraries. Node/OpenMausBot CLI versions also responded. This uses ARM64 Linux emulation, **not Android/Bionic, an Android system emulator or successful Android PRoot validation**.
- **Six APK auth/MCP integration checks passed** via `node tools/apk-auth-integration.mjs android/runtime`: reject anonymous/forged-owner requests; native-private-stdin owner bootstrap; single-use code → HttpOnly cookie with no token in JSON; authenticated config access; original OpenMausBot→REA MCP initialize/tools-list probe; explicit connect/enable flow with foreign-origin mutation refusal; logout revocation. These groups ran on **Linux x64**, with no paid model request or analysis-target execution.
- The old host-only PRoot 5.1 binary failed a full ARM64 guest file-access probe (modern syscall compatibility); it is **not included in the APK**. The APK ships the separately pinned Android PRoot fork with statx support. No full guest/server Android boot pass is inferred from the isolated ARM64 native tests.
- The APK's source archive was scanned for signing paths, password files, `.git/config` and `node_modules`: none included. It contains all 22,839 original Git blobs, plus the new port source, with inert source symlinks and explicit LFS exclusions.

Reports are under ignored `reports/local/apk-*`. The APK's native dashboard and guide visibly state `NOT_CERTIFIED`; the user has not accepted missing features as completion.

## Source integrity — passed

```sh
python3 tools/upstreams.py list
python3 tools/upstreams.py fetch
python3 tools/upstreams.py verify
```

All **22,839** original Git blobs across seven pinned trees were fetched and verified, including all five REA submodules. Original blob bytes total **390,825,039**. Root tree reproduction, per-blob hashes, sizes and executable bits pass. The **214** symlink target blobs are inert text; their original modes remain in the manifest. Downloaded source bytes live in ignored `.cache/sources`, not as large vendored files in Git.

**External fixture limitation:** 2,506 Git LFS pointer files in unblob were verified as raw Git blobs; their 892 unique external objects (222,010,238 payload bytes) were not fetched. The source tool reports this explicitly. Its pass is not a fully materialized LFS fixture-tree pass.

## Toolkit tests

```sh
make test
```

**Result: 51 Python tests passed** (the original 43 plus eight native-app structural/security regression gates), followed by shell/JavaScript syntax checks and all seven source manifest/root-tree checks. The separate 19 Java tests above execute the actual archive-extraction implementation, not Android UI/device code.

The tests cover:

- Git hash/root-tree reproduction, missing/changed/extra files, executable bits, unsafe paths, symlink handling, duplicate entries and complete submodule selection;
- physical versus virtual RAM, architecture, storage and non-root preflight behavior;
- binary Android XML identity parsing, invalid/truncated inputs, XML-entity refusal, APK inventory without execution, and limited split-metadata consistency;
- shell syntax, safe help/argument behavior, non-Termux refusal before package installation and retention of service-trust/isolation settings;
- deterministic kit packaging, per-file checksums, tamper/path-traversal refusal and exclusion of secrets/downloaded modules.

The APK parser tests use **synthetic test fixtures**, not the unidentified user APKs. Metadata parsing is not signature verification.

## Original runtime — Linux x64 probes passed, optional capability missing

The trial used pinned **Node 24.22.1**, **OpenMausBot 0.1.169**, **REA 6.9.0** and `npm ci` using the committed runtime lockfile. No upstream feature code was replaced.

```sh
node android/runtime-smoke.mjs --runtime <runtime-directory>
node tools/runtime-integration.mjs <runtime-directory>
```

Probes:

- Both original CLI versions respond correctly.
- DuckDB native binding opens an in-memory database and completes a query.
- Resvg's native binding renders a tiny SVG to a valid PNG.
- 1Password SDK imports; **no authentication/vault operation was tested**.
- A procps-compatible `ps` responds; process details are not retained.
- **Frida was absent** as an unmet optional dependency. This is reported as a missing capability, not hidden by a successful npm exit.

Original server boot/HTTP checks exercise its web HTML, health/version/static flag, environment descriptor and standalone PWA manifest. The service-trust regression check requires anonymous, forged-local-CLI and foreign-origin requests for private configuration to be rejected. REA's static fixture analysis must return Evidence while leaving a sentinel file absent, demonstrating that the target was not executed.

The one-shot integration runner gives the server a fresh temporary home/workspace and no provider credentials, binds the test server to `0.0.0.0`, and stops its child in `finally`. The earlier manually inspected preview server was also stopped; no always-running public demo is required.

## Not tested / not delivered

- **Termux installation on the physical Realme, Ubuntu ARM64 installation, and native ARM64 module execution.** Shell syntax and x64 tests cannot substitute for these.
- Exact Android version/ABI, real free space, temperature, battery drain, concurrency or Android background/reboot survival.
- Live Groq/Claude/Codex/Grok calls, streaming/approvals with a real engine, OAuth connections, paid services, full routine/memory/team workflows, or every engine's ARM64 binary.
- Full OpenMausBot↔REA MCP handshake on the phone, native decompiler integrations, Frida instrumentation or adb control.
- Working Docker/Podman/VMs, per-bot kernel isolation, native Android Accessibility/MediaProjection/audio/push control.
- Contents/signers/app identity of the Drive APKs, or cryptographic verification of the Drive desktop installers.
- Successful installation/boot of the native development APK on Android, a fully offline model, a feature-for-feature Android clone, or comprehensive upstream security/semantic review.

GitHub Actions checks have been **added**, not claimed to have run on GitHub in this session. The workflow explicitly labels its upstream runtime job **Linux x64 only**. Physical Android acceptance remains open in [FEATURE_PARITY.md](FEATURE_PARITY.md).
