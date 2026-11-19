#!/usr/bin/env python3
"""Build a deterministic, checksummed bootstrap kit, not a padded APK."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('android', 'docs', 'tools', 'tests', 'upstream', 'licenses', '.github')
ROOT_FILES = ('README.md', 'LICENSE', 'NOTICE', 'Makefile', '.gitignore')
EXCLUDED = {'node_modules', '__pycache__', '.pytest_cache', '.cache', '.git', 'signing'}
EXTENSIONS = {'.sh', '.py', '.mjs', '.json', '.md', '.txt', '.csv', '.yml', '.yaml'}
MANIFEST = 'KIT-SHA256.json'


def selected_files(root: Path = ROOT) -> list[Path]:
    files = [root / name for name in ROOT_FILES]
    for directory in DIRECTORIES:
        folder = root / directory
        if not folder.is_dir():
            continue
        for path in folder.rglob('*'):
            relative = path.relative_to(root)
            if any(part in EXCLUDED for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f'Refusing to package symlink: {relative}')
            if path.is_file() and path.suffix in EXTENSIONS and not path.name.startswith('.env'):
                files.append(path)
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing/non-regular required kit file: {path}')
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def build(output: Path, root: Path = ROOT) -> dict:
    contents = {path.relative_to(root).as_posix(): path.read_bytes() for path in selected_files(root)}
    manifest = {'schemaVersion': 1, 'artifactKind': 'experimental-bootstrap-NOT-APK',
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}}
    contents[MANIFEST] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as target, gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for name, data in sorted(contents.items()):
                entry = tarfile.TarInfo('terminator-android-kit/' + name)
                entry.size = len(data)
                entry.mode = 0o755 if Path(name).suffix in ('.sh', '.py') else 0o644
                entry.mtime = 0
                entry.uid = entry.gid = 0
                entry.uname = entry.gname = ''
                archive.addfile(entry, io.BytesIO(data))
    return {'file': output.name, 'bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'files': len(contents),
            'kind': 'bootstrap kit; dependencies and full upstream source bytes are NOT embedded'}


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink():
        raise ValueError('Kit checksum manifest must not be a symlink')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schemaVersion') != 1 or not manifest.get('files'):
        raise ValueError('Unsupported or empty kit manifest')
    for name, expected in manifest['files'].items():
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or '..' in path.parts or str(path) != name or '\\' in name:
            raise ValueError('Unsafe kit manifest path')
        target = root
        for part in path.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError(f'Symlink in kit: {name}')
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Kit checksum mismatch: {name}')
    return {'ok': True, 'filesVerified': len(manifest['files']),
            'note': 'Checksums detect corruption; they are not a publisher signature or Android certification.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/terminator-android-kit.tar.gz')
    parser.add_argument('--verify', type=Path, metavar='EXTRACTED_KIT')
    args = parser.parse_args(argv)
    try:
        if args.verify:
            print(json.dumps(verify(args.verify.absolute()), indent=2))
        else:
            result = build(args.output)
            args.output.with_suffix(args.output.suffix + '.sha256').write_text(f"{result['sha256']}  {args.output.name}\n")
            print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f'Kit error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
