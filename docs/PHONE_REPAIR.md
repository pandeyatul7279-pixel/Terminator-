# Realme Linux-installer repair (0.2.1 development trial)

## Phone evidence, 19 November 2026

The owner installed and launched `dev.terminator.phone` version `0.2.0-test` / code 2. The dashboard failed during Linux preparation, before any native-engine readiness check, and displayed:

```
.../linux-7480ebcf0169.installing/usr/bin/perl -> .../linux-7480ebcf0169.installing/usr/bin/perl5.38.2
```

This is not a failed APK download or installation. The two absolute paths identify the extractor's hard-link operation. The old UI omitted the exception class/cause, so the actual Android errno is **not established**. Android/filesystem hard-link denial is the leading diagnosis, not a remotely observed errno.

## Extractor change

`SafeTar` still prefers real hard links on filesystems that support them. If the provider rejects the operation, it copies the complete, already-extracted regular target into a new private file. Executable permission is retained as private `0700`; other files use `0600`. The archive path, link-target, fresh-root, no-symlink-parent, no-overwrite, entry-count, per-file and total-expanded-byte limits remain in force. Additional copy bytes count toward the same total limit. Copies do not retain shared-inode mutation semantics; no original executable/source bytes are removed or patched.

The exact pinned Ubuntu archive contains two hard links: `usr/bin/perl` and `usr/bin/uncompress`. A host-JVM extraction with **every hard-link operation deliberately failing** successfully produced 7,507 regular files, 1,132 archive links and two fallback copies (356,958,357 written bytes, including 3,944,586 additional copy bytes). The Perl and gunzip alias bytes match the original archive. This is an extraction regression result, **not Android engine-boot evidence**.

Failure diagnostics now retain the exception class, causes/errno where supplied, stack and suppressed errors in bounded, credential-redacted, app-private logs. A failed installation never receives a completion marker; staging cleanup no longer hides the original exception. The failed rootfs cache can be retried without clearing app data.

## Why a separate, small repair APK

The already installed hosted build was signed with certificate SHA-256:

`2a462b1ce45587f753724250059ba3bcd91736febc83dce3f85d255180b80e9c`

Its ephemeral CI private signing key was not retained and is not available for an in-place update. A differently signed APK cannot replace it. **Never ask the owner to uninstall or clear storage to work around this.**

The repair profile uses package **`dev.terminator.phone.repair`**, label **Terminator Repair**, version **0.2.1-repair-test** / code **1**. It installs alongside the original and creates its own workspace. It does not migrate or open the old app's private chats, keys, settings, rootfs cache or data. The original stays unchanged.

The small APK is explicitly **not a standalone 325 MB replacement**: on the first user-approved prepare action it obtains *public APK assets* from the already installed original app using Android's package/resource APIs. It never loads that package's code. It verifies the original package/version, signing certificate, complete APK byte length/SHA-256, then imports all three full payload archives from `repair-source.lock.json`:

- `runtime.tar.xz`: 107,109,048 bytes, unchanged original OpenMausBot/REA/Node engine.
- `original-sources.tar.xz`: 181,875,240 bytes, all 22,839 preserved original Git blobs, including the original LFS pointers (not the missing external LFS payloads).
- `native-corresponding-sources.tar.gz`: 36,205,168 bytes, complete previously delivered PRoot/talloc/XZ source archives.

Each import uses bounded streaming, exact length and SHA-256 verification, private files, a temporary file and an atomic final rename. An incomplete/corrupt/cancelled import never replaces a final archive and can retry. Original archives are copied in full, not trimmed. After the archives have been copied successfully they are stored inside the repair app; subsequent starts do not depend on reading the old APK. The owner should nonetheless keep the original app installed until successful phone verification and a deliberate data/backup decision.

The complete current port/repair source is bundled separately and exportable under **Sources & licenses → Export repair app source**. Existing original source/native-source exports are retained and use the verified full imported archives. The pinned PRoot native library and loaders are bundled in the repair APK. All execution remains on the phone; this is not a remote-server substitute. Feature limits/approvals/entitlements remain unchanged; full parity is still **NOT_CERTIFIED**.

## Simple phone flow (Hinglish)

1. **Purana Terminator Test uninstall ya clear mat karein.**
2. Nayi **Terminator Repair** APK normal tarah install karke kholein. Yeh alag app hai, purane app ka update nahi.
3. Phone mein **2 GB khaali jagah** rakhein. **Prepare & start bot** dabayein aur consent padhein. App ko khula rakhein. Engine/source files purane installed APK se copy hongi; lagbhag 65 MB Ubuntu download phir bhi hoga, kyunki purane app ka private cache access nahi hota.
4. Sirf actual native probes, original server and authentication pass hone par **Open bot** enable hoga. Zaroorat par apni AI key/settings is naye workspace mein dobara configure karni hogi.
5. Agar error aaye to **Diagnostics** kholkar uska screenshot/text bhejein. Storage clear, uninstall, Play Protect disable ya Termux commands ki zaroorat nahi.

## Reproduction / acceptance boundary

Maintainer-only commands, not a phone-user handoff:

```
python3 tools/build_apk.py --repair --prepare --build
python3 tools/test_apk_java.py -v
# Already downloaded and verified archive; no unpinned network input:
APK_TEST_ROOTFS=.cache/apk-runtime/ubuntu-rootfs-arm64.tar.xz python3 tools/test_apk_java.py -v
```

The build compiles the real Android classes and DEX, aligns the APK, signs it and verifies v2/v3 signatures. The original small-APK dependency, package identity, source pins and safety invariants have separate regression guards. Local development signing material stays under ignored `android/signing/`; never commit, export or print it. Keep that key securely for any later repair-package update; generating another fresh signer would repeat the update problem.

No emulator/adb/Realme runtime test has run for this repair yet. Source-asset import through Android, the repaired extraction on the actual device, native PRoot/Node probes, server/auth readiness and all original feature workflows still require device evidence. A successful host extraction does not certify the rest of the port.
