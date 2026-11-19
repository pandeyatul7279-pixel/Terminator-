# Security and licensing boundaries

## Runtime security

- This kit runs original upstream code; it has not performed a comprehensive security review of that code. It does not make the agents safe merely by using PRoot.
- PRoot processes share the Termux application's real Android UID and kernel. Guest root and guest users are compatibility mechanisms, **not Android root or strong separation between bots**. `--isolated` reduces automatic mounts; it does not create container-grade isolation.
- The launcher uses upstream `OMB_LOOPBACK_TRUST=service`, preserving explicit pairing rather than granting anonymous phone-loopback callers owner rights. Phone loopback can be reached by other local apps. Do not disable pairing or set development browser-trust flags to work around errors.
- Upstream's permission broker and license gates are not modified. No account is connected and no provider key is requested by installation. Add a key only to upstream's own provider settings after reviewing its storage/security behavior.
- Nothing here grants Accessibility, screen capture, microphone, adb, root or device-admin permissions. Browser automation is not silently run with sandbox protection disabled.
- Installation explicitly executes apt/npm vendor lifecycle scripts in the dedicated PRoot. Versions/integrities of the app dependency graph are in `android/runtime/package-lock.json`; OS images, apt packages, Termux tools and the platform binary selected by the pinned npm Node installer are not a fully hermetic build.
- The kit download's embedded checksums detect damage. They are not an independently signed attestation and do not replace trust in the download source.
- Source downloads use pinned public GitHub repositories as **data**, without checking out branches or running hooks, submodule scripts, build scripts or downloaded instructions. Every original Git blob is checked. Audit-tree symlink targets are inert text, preventing hostile fixture links from being activated.
- Keep a test workspace at first. Do not expose the server to the internet or shared LAN without upstream's authenticated HTTPS configuration and a separate review.

## License scope

New Terminator toolkit code in this repository is under the root Apache-2.0 `LICENSE`. This does **not** relicense downloaded applications, third-party code, trademarks or proprietary providers.

### OpenMausBot

The open-source core is Apache-2.0; preserve the upstream [LICENSE](../licenses/OpenMausBot-LICENSE.txt), [NOTICE](../licenses/OpenMausBot-NOTICE.txt), per-file notices and relevant third-party material when distributing a derivative.

The pinned upstream [LICENSING.md](https://github.com/milind-soni/OpenMausBot/blob/b832de78c43c8d76e92d6f50fb1a8d33be364480/LICENSING.md) states that **`enterprise/` is source-available under a separate Enterprise License**, not Apache-2.0. Production enterprise features require an appropriate license; third-party hosting/white-labelling may need a partner agreement. This kit leaves those restrictions and entitlement checks intact. It does not grant rights to use the OpenMausBot/MausBot trademarks or mascot as the branding for a new product.

The npm package includes the original enterprise license and code. Its presence is not a license entitlement. Do not remove gating or claim that all commercial services are included because their code can be downloaded.

### REA and external tools

REA-authored code is MIT; see [REA's license](../licenses/REA-LICENSE.txt). Its integrations and dependencies retain their own licenses, including submodules and optional/externally supplied analysis tools. MIT does not grant Hopper/IDA/JEB or other third-party tool licenses. Preserve REA's full distributed notices when redistributing it, not only the short MIT text.

The kit fetches the original packages rather than redistributing repackaged binaries. Any future self-contained APK/bundle needs an actual component/license inventory, notices/source offers as applicable, signing policy and distribution review.

## APK and binary inspection

Inspect only software/devices you own or are authorised to analyse. The local APK helper reports bounded static metadata without installing or executing an APK. It does not verify signatures or circumvent protections. A decompiled APK does not recover original comments, variable names, server-side source, private APIs or proprietary entitlements. No code from the unidentified Drive APKs was incorporated here.

Private Drive file IDs, access tokens, keys, downloaded installers, user workspaces and transcripts are deliberately not committed. Read-only diagnostics avoid serial numbers, account lists and provider credentials. Review any log before sharing it; upstream pairing links are credentials.
