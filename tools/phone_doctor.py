#!/usr/bin/env python3
"""Read-only, credential-free phone diagnostics. Never roots or tunes Android."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

GIB = 1024 ** 3


def memory_info(text: str) -> dict:
    values = {}
    for line in text.splitlines():
        parts = line.replace(":", " ").split()
        if len(parts) >= 2 and parts[0] in ("MemTotal", "MemAvailable", "SwapTotal"):
            try:
                values[parts[0]] = int(parts[1]) * 1024
            except ValueError:
                pass
    return {"physicalBytes": values.get("MemTotal"), "availableBytes": values.get("MemAvailable"),
            "swapBytes": values.get("SwapTotal"),
            "note": "Expanded/virtual RAM uses storage; it is not additional physical RAM."}


def assess(*, is_termux: bool, architecture: str, free_bytes: int, physical_bytes, uid: int) -> dict:
    blockers, warnings = [], []
    if not is_termux:
        blockers.append("Not running in Termux on Android; this is not an on-device result.")
    if architecture not in ("aarch64", "arm64"):
        blockers.append("The phone trial targets ARM64, not this CPU architecture.")
    if free_bytes < 8 * GIB:
        blockers.append("Less than 8 GiB free in the private home filesystem (10 GiB recommended).")
    if uid == 0:
        blockers.append("Run the Android host installer as the normal Termux app UID, never root.")
    if physical_bytes is None:
        warnings.append("Android did not expose physical RAM through /proc/meminfo.")
    elif physical_bytes < 6 * GIB:
        warnings.append("Physical RAM is below the 8 GB target; concurrent agents/browser tasks need stricter limits.")
    warnings.extend([
        "PRoot is not Docker, a VM, or a security boundary between agents.",
        "Android/Realme battery management can stop Termux; this does not certify always-on operation.",
        "Provider calls, paid services, native libraries and phone screen control are not tested by this host diagnostic.",
    ])
    return {"hostPreflightPassed": not blockers, "androidParity": "NOT_CERTIFIED",
            "blockers": blockers, "warnings": warnings}


def android_properties() -> dict:
    binary = Path("/system/bin/getprop")
    if not binary.is_file():
        return {}
    output = {}
    # Deliberately do not collect serial numbers, accounts, installed apps or keys.
    for name, key in (("model", "ro.product.model"), ("manufacturer", "ro.product.manufacturer"),
                      ("androidVersion", "ro.build.version.release"), ("sdk", "ro.build.version.sdk"),
                      ("primaryAbi", "ro.product.cpu.abi")):
        try:
            result = subprocess.run([str(binary), key], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                output[name] = result.stdout.strip()[:120]
        except (OSError, subprocess.SubprocessError):
            pass
    return output


def collect() -> dict:
    prefix = os.environ.get("PREFIX", "")
    is_termux = prefix.startswith("/data/") and prefix.endswith("/files/usr") and Path("/system/bin/getprop").exists()
    try:
        memory = memory_info(Path("/proc/meminfo").read_text())
    except OSError:
        memory = memory_info("")
    disk = shutil.disk_usage(Path.home())
    architecture = platform.machine()
    report = {"schemaVersion": 1, "tool": "Terminator phone preflight",
              "device": android_properties(),
              "host": {"system": platform.system(), "architecture": architecture, "isTermux": is_termux},
              "memory": memory, "storage": {"freeBytes": disk.free, "totalBytes": disk.total},
              "tools": {name: shutil.which(name) is not None for name in ("proot-distro", "python3", "git")}}
    report.update(assess(is_termux=is_termux, architecture=architecture, free_bytes=disk.free,
                         physical_bytes=memory["physicalBytes"], uid=os.getuid() if hasattr(os, "getuid") else -1))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when the host preflight has blockers")
    args = parser.parse_args(argv)
    report = collect()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Terminator phone diagnostic — Android parity: NOT CERTIFIED")
        print(f"Architecture: {report['host']['architecture']}; Termux: {report['host']['isTermux']}")
        print(f"Free storage: {report['storage']['freeBytes'] / GIB:.1f} GiB")
        physical = report['memory']['physicalBytes']
        print(f"Physical RAM: {physical / GIB:.1f} GiB" if physical else "Physical RAM: unavailable")
        for kind in ("blockers", "warnings"):
            for message in report[kind]:
                print(f"{kind[:-1].upper()}: {message}")
    return 1 if args.strict and not report["hostPreflightPassed"] else 0


if __name__ == "__main__":
    sys.exit(main())
