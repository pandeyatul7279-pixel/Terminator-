#!/usr/bin/env python3
"""Preserve every pinned upstream Git blob without executing upstream code.

Uses raw Git objects, not working-tree/archive exports (which can change line
endings). All five REA submodules are pinned and fetched too. Tracked symbolic
link targets are kept as inert text blobs, never activated on this machine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "upstream/lock.json"
CHUNK = 1024 * 1024
SHA1 = re.compile(r"[0-9a-f]{40}\Z")


class SourceError(ValueError):
    pass


def safe_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise SourceError(f"Unsafe source path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in (".", "..", ".git") for part in value.split("/")):
        raise SourceError(f"Unsafe source path: {value!r}")
    if str(path) != value:
        raise SourceError(f"Noncanonical source path: {value!r}")
    return value


def git_hash(kind: str, data: bytes) -> str:
    return hashlib.sha1(f"{kind} {len(data)}\0".encode() + data).hexdigest()


def tree_hash(files: list, gitlinks: list) -> str:
    tree: dict = {}
    for path, mode, digest, *_ in files + gitlinks:
        safe_path(path)
        if mode not in ("100644", "100755", "120000", "160000") or not SHA1.fullmatch(digest):
            raise SourceError(f"Invalid mode or Git object ID: {path}")
        cursor = tree
        parts = path.split("/")
        for part in parts[:-1]:
            if part in cursor and not isinstance(cursor[part], dict):
                raise SourceError(f"File/directory collision: {path}")
            cursor = cursor.setdefault(part, {})
        if parts[-1] in cursor:
            raise SourceError(f"Duplicate source entry: {path}")
        cursor[parts[-1]] = (mode, digest)

    def digest_tree(node: dict) -> str:
        records = []
        for name, value in node.items():
            directory = isinstance(value, dict)
            mode, digest = ("40000", digest_tree(value)) if directory else value
            encoded = name.encode("utf-8", "surrogateescape")
            records.append((encoded + (b"/" if directory else b""),
                            mode.encode() + b" " + encoded + b"\0" + bytes.fromhex(digest)))
        return git_hash("tree", b"".join(record for _, record in sorted(records)))

    return digest_tree(tree)


def read_lock(lock_path: Path = LOCK) -> dict:
    lock = json.loads(lock_path.read_text())
    if lock.get("schemaVersion") != 1 or not lock.get("projects"):
        raise SourceError("Unsupported or empty upstream lock")
    destinations = set()
    for name, project in lock["projects"].items():
        safe_path(project["path"])
        if project["path"] in destinations:
            raise SourceError("Duplicate source destination")
        destinations.add(project["path"])
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", project["repository"]):
            raise SourceError(f"Invalid repository: {name}")
        if not SHA1.fullmatch(project["commit"]) or not SHA1.fullmatch(project["tree"]):
            raise SourceError(f"Invalid source revision: {name}")
        manifest_path = lock_path.parent / safe_path(project["manifest"])
        raw = manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != project["manifestSha256"]:
            raise SourceError(f"Manifest checksum mismatch: {name}")
        manifest = json.loads(raw)
        files, links = manifest["files"], manifest.get("gitlinks", [])
        if any(len(file) != 4 or not isinstance(file[3], int) or file[3] < 0 or
               file[1] not in ("100644", "100755", "120000") for file in files):
            raise SourceError(f"Malformed file manifest: {name}")
        if len(files) != project["fileCount"] or sum(file[3] for file in files) != project["blobBytes"]:
            raise SourceError(f"Manifest totals mismatch: {name}")
        if tree_hash(files, links) != project["tree"]:
            raise SourceError(f"Root Git tree mismatch: {name}")
        project["_manifest"] = manifest
    for name, project in lock["projects"].items():
        for path, mode, commit, child in project["_manifest"].get("gitlinks", []):
            target = lock["projects"].get(child)
            if mode != "160000" or not target or target["commit"] != commit:
                raise SourceError(f"Unpinned submodule: {name}/{path}")
            if target["path"] != project["path"] + "/" + path:
                raise SourceError(f"Submodule destination mismatch: {name}/{path}")
    return lock


def blob_hash(path: Path, size: int) -> str:
    hasher = hashlib.sha1(f"blob {size}\0".encode())
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_tree(directory: Path, manifest: dict) -> dict:
    if directory.is_symlink() or not directory.is_dir():
        raise SourceError(f"Missing source directory or symlink: {directory}")
    expected = {file[0]: file for file in manifest["files"]}
    links = {link[0] for link in manifest.get("gitlinks", [])}
    observed = set()
    lfs_pointers = 0
    lfs_objects = {}
    for folder, dirs, files in os.walk(directory, followlinks=False):
        relative = Path(folder).relative_to(directory)
        for name in list(dirs):
            child = Path(folder) / name
            if child.is_symlink():
                raise SourceError(f"Unexpected source symlink: {child}")
            if (relative / name).as_posix() in links:
                dirs.remove(name)  # Verified separately using the child's manifest.
        for name in files:
            path = Path(folder) / name
            relative_path = path.relative_to(directory).as_posix()
            if path.is_symlink() or not path.is_file() or relative_path not in expected:
                raise SourceError(f"Unexpected source entry: {relative_path}")
            _, mode, digest, size = expected[relative_path]
            stat = path.stat()
            if stat.st_size != size or blob_hash(path, size) != digest:
                raise SourceError(f"Changed source file: {relative_path}")
            if os.name == "posix" and bool(stat.st_mode & 0o111) != (mode == "100755"):
                raise SourceError(f"Changed executable bit: {relative_path}")
            if size < 1024:
                raw = path.read_bytes()
                if raw.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                    oid = re.search(rb"\noid sha256:([0-9a-f]{64})(?:\n|$)", raw)
                    payload_size = re.search(rb"\nsize ([0-9]+)(?:\n|$)", raw)
                    if oid and payload_size:
                        lfs_pointers += 1
                        lfs_objects[oid.group(1)] = int(payload_size.group(1))
            observed.add(relative_path)
    missing = set(expected) - observed
    if missing:
        raise SourceError(f"Missing {len(missing)} source files; first: {min(missing)}")
    return {"filesVerified": len(observed), "blobBytes": sum(file[3] for file in expected.values()),
            "symlinkBlobsAsText": sum(file[1] == "120000" for file in expected.values()),
            "gitLfsPointerFiles": lfs_pointers, "gitLfsUniqueObjectsNotFetched": len(lfs_objects),
            "gitLfsUniquePayloadBytesNotFetched": sum(lfs_objects.values())}


def git_command(*args, cwd=None) -> bytes:
    command = ["git", "-c", "core.hooksPath=/dev/null", "-c", "maintenance.auto=false",
               "-c", "protocol.file.allow=never", "-c", "fetch.recurseSubmodules=false", *args]
    result = subprocess.run(command, cwd=cwd, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        raise SourceError(f"Git failed: {result.stderr.decode(errors='replace')[-3000:]}")
    return result.stdout


def export_blobs(repository: Path, destination: Path, manifest: dict) -> None:
    process = subprocess.Popen(["git", "-C", str(repository), "cat-file", "--batch"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for relative, mode, digest, size in manifest["files"]:
            process.stdin.write(digest.encode() + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256).strip().split()
            if header != [digest.encode(), b"blob", str(size).encode()]:
                raise SourceError(f"Missing or unexpected Git object: {relative}")
            path = destination / safe_path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            hasher = hashlib.sha1(f"blob {size}\0".encode())
            with path.open("xb") as output:
                remaining = size
                while remaining:
                    chunk = process.stdout.read(min(CHUNK, remaining))
                    if not chunk:
                        raise SourceError(f"Truncated Git blob: {relative}")
                    output.write(chunk)
                    hasher.update(chunk)
                    remaining -= len(chunk)
            if process.stdout.read(1) != b"\n" or hasher.hexdigest() != digest:
                raise SourceError(f"Git blob checksum mismatch: {relative}")
            # Includes symlink Git objects: retain their exact target bytes as inert text.
            path.chmod(0o755 if mode == "100755" else 0o644)
        process.stdin.close()
        if process.wait(timeout=30):
            raise SourceError("git cat-file failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        if not process.stdin.closed:
            process.stdin.close()


def fetch_project(project: dict, base: Path) -> dict:
    destination = base / safe_path(project["path"])
    for parent in (destination, *destination.parents):
        if parent.is_symlink():
            raise SourceError(f"Source destination contains a symlink: {parent}")
        if parent == base:
            break
    if destination.exists():
        return {"state": "already-verified", **verify_tree(destination, project["_manifest"])}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".terminator-source-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        repository = stage / "objects.git"
        git_command("init", "--bare", "--quiet", str(repository))
        git_command("-C", str(repository), "fetch", "--depth=1", "--no-tags",
                    f"https://github.com/{project['repository']}.git", project["commit"])
        if git_command("-C", str(repository), "rev-parse", "FETCH_HEAD").decode().strip() != project["commit"]:
            raise SourceError("Downloaded commit mismatch")
        if git_command("-C", str(repository), "rev-parse", "FETCH_HEAD^{tree}").decode().strip() != project["tree"]:
            raise SourceError("Downloaded Git tree mismatch")
        source = stage / "tree"
        source.mkdir()
        export_blobs(repository, source, project["_manifest"])
        result = verify_tree(source, project["_manifest"])
        if destination.exists():
            raise SourceError("Destination appeared during download; refusing to replace it")
        source.rename(destination)
    return {"state": "downloaded-and-verified", **result}


def select_projects(lock: dict, names: list[str]) -> list[str]:
    selected = []

    def include(name):
        if name not in lock["projects"]:
            raise SourceError(f"Unknown project: {name}")
        if name in selected:
            return
        selected.append(name)
        for link in lock["projects"][name]["_manifest"].get("gitlinks", []):
            include(link[3])

    for name in names or lock["projects"]:
        include(name)
    return selected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "fetch", "verify"))
    parser.add_argument("projects", nargs="*", help="Default: both projects and every pinned REA submodule")
    parser.add_argument("--dest", type=Path, default=ROOT / ".cache/sources")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        lock = read_lock()
        results = []
        for name in select_projects(lock, args.projects):
            project = lock["projects"][name]
            result = {"project": name, "repository": project["repository"], "commit": project["commit"]}
            if args.command == "list":
                result.update(files=project["fileCount"], blobBytes=project["blobBytes"],
                              **project.get("externalAssetAudit", {}))
            elif args.command == "fetch":
                print(f"Fetching/verifying {name} at {project['commit']}...", file=sys.stderr)
                result.update(fetch_project(project, args.dest.absolute()))
            else:
                result.update(state="verified", **verify_tree(args.dest / project["path"], project["_manifest"]))
            results.append(result)
        if args.json:
            print(json.dumps({"ok": True, "verificationScope": "Pinned Git blobs, not external Git LFS payloads",
                              "externalLfsAssetsIncluded": not any(r.get("gitLfsPointerFiles", 0) for r in results),
                              "projects": results}, indent=2))
        else:
            for result in results:
                print(f"{result['project']}: {result.get('state', 'pinned')}; "
                      f"{result.get('filesVerified', result.get('files'))} files; {result['commit']}")
                if result.get("gitLfsPointerFiles"):
                    print(f"  NOTE: {result['gitLfsPointerFiles']} Git LFS pointers verified; "
                          "their external payloads are NOT fetched/materialized.")
        return 0
    except (SourceError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}) if args.json else f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
