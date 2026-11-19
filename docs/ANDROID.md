# Realme 15T: experimental phone-hosted installation

> **Developer reference, not the accepted user handoff.** The user requires an installable full-feature APK and has explicitly rejected technical setup and reduced-scope APK alternatives. These earlier trial instructions are retained for investigation only, not as a replacement for that APK.

## Before you start

This trial targets the phone you described: **Realme 15T, 8 GB physical RAM, 12 GB memory expansion**. Android version, actual ABI, root status and free storage have not yet been measured. We assume an ordinary **unrooted ARM64** phone; the preflight checks the architecture.

**This is a Termux/Ubuntu launcher, not an installable APK and not a finished Android port.** A successful dependency check does not mean all OpenMausBot/REA features work on Android.

The path is:

```text
Chrome on the phone
  → upstream pairing + web UI
  → original OpenMausBot server in Ubuntu PRoot on that same phone
  → Groq / another configured provider over the internet
  → optional REA MCP tools in the same Ubuntu userland
```

The backend is phone-hosted. **Groq model inference is not on-device or offline.** The kit contains no model weights. xAI **Grok** and the **Groq** inference provider are different products.

### Requirements and cautions

- Official Termux from its [upstream releases](https://github.com/termux/termux-app/releases), with a trusted/current package source. Do not install random repackaged APKs.
- **8 GiB free in Termux's private filesystem minimum; 10 GiB recommended.** Package caches, rootfs, model downloads and user work need additional room over time.
- A stable connection for Ubuntu, Node and npm packages. Do not start on a small mobile data allowance without reviewing the downloads.
- Keep Termux open during the trial. In Realme's app battery settings, allow Termux background activity if you choose, but this is **not** a guarantee of uninterrupted routines. Avoid disabling system-wide security or rooting the phone.
- Start with **one bot** and no automated browser. The 1 GiB Node heap default is not a total-process memory limit. The 12 GB memory expansion is not a substitute for physical RAM.
- PRoot provides a Linux userland, **not** Docker, a VM, privileged kernel features, or a trustworthy agent isolation boundary. Use a test workspace without sensitive files initially.

## 1. Put the kit in Termux's private home

Download `terminator-android-kit.tar.gz`. If you downloaded it through Chrome into Downloads, Termux needs your permission to copy that particular file:

```sh
termux-setup-storage
mkdir -p "$HOME/terminator-kit"
tar -xzf "$HOME/storage/downloads/terminator-android-kit.tar.gz" \
  -C "$HOME/terminator-kit" --strip-components=1
cd "$HOME/terminator-kit"
```

Grant storage access only if you want to copy the download. The runtime launcher uses PRoot's `--isolated` mode and does not automatically bind shared storage into the bot workspace. PRoot isolation is still **not a security boundary**.

If you already have the repository in Termux's private home, use its directory instead. Do not run the kit directly from `/sdcard` or `/storage`; Android shared storage does not provide a normal executable Linux filesystem.

For an archive integrity check before installation:

```sh
python3 tools/package_kit.py --verify .
```

If Python is not installed in Termux yet, install it explicitly with `pkg install python`. The embedded checksum manifest detects corruption; it is not an independent publisher signature.

## 2. Read-only preflight

```sh
bash android/install-termux.sh --check
```

This checks the Termux environment, non-root host UID, ARM64 and free space. It does not install packages or change Android settings. **Passing is not an Android compatibility certificate.**

## 3. Review and install

Read `android/install-termux.sh` and `android/install-ubuntu.sh`, then:

```sh
bash android/install-termux.sh --install
```

Type `INSTALL` when asked. For an already-reviewed unattended installation, add `--yes` explicitly.

The installer:

1. Updates Termux package indexes and installs `proot-distro` and Python.
2. Creates a container named **`terminator`**. With modern PRoot-Distro it requests the `ubuntu:24.04` userland image; legacy PRoot-Distro uses its Ubuntu alias. It does **not** run Docker. The OS image, apt packages and Termux tools are not fully reproducibly pinned.
3. Refuses to modify an existing, non-toolkit container with that name. An existing unrelated `ubuntu` container is left alone.
4. Installs Ubuntu's bootstrap Node/npm, Git, Python, build tools and procps. Then it installs **Node 24.22.1** in `/opt/terminator/node`.
5. Uses `npm ci` with the committed lockfile to install **OpenMausBot 0.1.169** and **REA 6.9.0** in `/opt/terminator/runtime`.
6. Runs credential-free native dependency/CLI probes. No optional dependencies are deliberately omitted; an optional package can nevertheless fail to install, and the report shows this (Frida was missing in our Linux test).
7. Creates guest user `terminator` and leaves the runtime stopped. Guest-root setup is PRoot emulation, not Android rooting.

This runs third-party apt/npm installation scripts and writes the dedicated rootfs. Only proceed if you trust those sources. An installation failure is a failure, not permission to disable platform safeguards. Do not use arbitrary `--no-sandbox` workarounds to call browser automation supported.

Re-running installs the same pinned app versions; **stop the server first**. It refreshes managed runtime dependencies, not the saved workspace. Do not use PRoot-Distro `reset`/`remove` unless you intend to erase the rootfs and have exported your data.

## 4. Start the original application

```sh
bash android/start-termux.sh
```

Keep that Termux session open. Use the browser pairing invitation the original CLI prints. Enter it in Chrome **on this same phone**. The local server address is:

```text
http://127.0.0.1:8799
```

Phone loopback is valid here because the server and browser are on the **same physical phone**. If the backend is on a PC/VPS, this address is wrong: use that server's HTTPS address and normal pairing.

The launcher deliberately uses upstream **service loopback trust**, so other local callers are not automatically treated as workspace owners. If the invitation is missing or refused, keep the terminal output, stop the process and report the failure; do not disable pairing. Do not share invitation links/tokens in public logs.

No LAN sharing, external tunnel, account connection or native phone permission is enabled by this kit. Ctrl+C stops the foreground server; it should not delete conversations. The guest workspace is `/home/terminator/.openmausbot`. Save a backup through upstream's export facilities before resetting or uninstalling the PRoot.

## 5. Enable Groq without rewriting the bot

In the **original UI**, open **Settings → AI → Providers**, select **Groq**, and save your key there. Choose a model currently offered to your Groq account and select it for one test bot.

Do not paste the key in chat, a command-line argument, an example JSON committed to Git, or a diagnostic. Groq support is already in the upstream driver; there is no reason to replace its conversation/permission system with a new thin client.

Try one short message first, then verify persistence after a clean restart. This project has not made a live paid-provider request or measured phone latency, cost, temperature, battery drain or concurrency.

## 6. Optional: connect REA as a tool provider

First verify the original CLI:

```sh
bash android/start-termux.sh rea --version
bash android/start-termux.sh rea doctor
bash android/start-termux.sh rea capabilities --json
```

Then use upstream **Plugins → MCP servers → Add server**, and review this standard MCP block:

```json
{
  "mcpServers": {
    "rea": {
      "command": "/opt/terminator/node/node_modules/node/bin/node",
      "args": [
        "/opt/terminator/runtime/node_modules/rea-agents/scripts/rea.mjs",
        "mcp"
      ]
    }
  }
}
```

Allow its connection/tool-list test to finish. Select which bots may use it; do not grant blanket permissions to an untrusted agent. This exact OpenMausBot↔REA handshake still needs on-device validation. REA tools can have consequential side effects; inspect only software/devices you own or are authorised to examine.

REA's package contains far more than a decompiler. Availability depends on tools such as JADX/JDK, Ghidra, adb, a browser or Frida. They are **not all installed or certified** by this bootstrap. A listed tool is not a working tool; check its availability and limitations.

## 7. Send a safe diagnostic before the next development phase

```sh
bash android/start-termux.sh doctor > "$HOME/terminator-doctor.txt" 2>&1
```

The host diagnostic collects model/Android version/ABI, RAM, free storage and tool presence—not serial numbers, accounts, keys, transcripts or installed-app inventories. Native probes run in the guest and explicitly mark Android parity `NOT_CERTIFIED`. Review the text before sharing it.

If installation fails before the guest runtime exists, run:

```sh
python3 tools/phone_doctor.py --json
```

The next acceptance gates are in [FEATURE_PARITY.md](FEATURE_PARITY.md). We need the actual phone results before describing this as a working phone installation, and substantially more work before claiming a native Android app or complete feature parity.

## The APK files in Drive

`base.apk` and three `split_config.*.apk` files were found, but their generic names do **not** identify an app. Their package/signature contents have not been inspected here. Do not rename an `.exe`/`.deb` to `.apk`, and do not treat a base APK alone as a complete split installation.

If those files are on your phone, this local read-only inspection identifies their package and split metadata without executing them:

```sh
python3 tools/apk_inventory.py \
  "$HOME/storage/downloads/base.apk" \
  "$HOME/storage/downloads/split_config.en.apk" \
  "$HOME/storage/downloads/split_config.xhdpi.apk" \
  "$HOME/storage/downloads/split_config.arm64_v8a.apk"
```

It does **not** verify signing certificates, promise installability, or recover original source. No content from an unidentified APK has been copied into this project.
