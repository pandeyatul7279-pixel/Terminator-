#!/usr/bin/env python3
"""Build the real native ARM64 development APK without Gradle/network Maven.

Only hash-pinned inputs are accepted. Downloaded tools, dependencies, private
signing material and output APKs stay out of Git. This is not a parity certificate.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'android/app'
CACHE = ROOT / '.cache/apk-runtime'
TOOLS = ROOT / '.cache/apk-toolchain'
BUILD = ROOT / '.cache/apk-build'
ARTIFACTS = ROOT / 'artifacts'


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kwargs)


def download(spec: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / spec['name']
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and sha(path) == spec['sha256']:
        return path
    partial = path.with_name(path.name + '.part')
    try:
        with partial.open('wb') as out:
            if 'gitBlob' in spec:
                run(['gh', 'api', f"repos/{spec['repository']}/git/blobs/{spec['gitBlob']}",
                     '-H', 'Accept: application/vnd.github.raw+json'], stdout=out)
            else:
                with urllib.request.urlopen(spec['url'], timeout=90) as source:
                    shutil.copyfileobj(source, out)
        if sha(partial) != spec['sha256']:
            raise ValueError(f"Pinned checksum mismatch: {spec['name']}")
        if 'bytes' in spec and partial.stat().st_size != spec['bytes']:
            raise ValueError(f"Pinned size mismatch: {spec['name']}")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    print('Verified input:', spec['name'], path.stat().st_size, flush=True)
    return path


def tools() -> tuple[Path, dict]:
    lock = json.loads((APP / 'toolchain.lock.json').read_text())
    for component in lock['components']:
        path = download(component, TOOLS)
        if component['name'] in ('aapt2', 'zipalign'):
            path.chmod(0o755)
    jdk = lock['jdk']
    wheel = download({'name': jdk['filename'], 'url': jdk['url'],
                      'sha256': jdk['digests']['sha256']}, TOOLS)
    runtime = TOOLS / 'jdk-wheel/jdk4py/java-runtime'
    if not (runtime / 'bin/java').exists():
        with zipfile.ZipFile(wheel) as archive:
            for entry in archive.infolist():
                p = Path(entry.filename)
                if p.is_absolute() or '..' in p.parts:
                    raise ValueError('Unsafe Java runtime wheel')
            archive.extractall(TOOLS / 'jdk-wheel')
    for path in (runtime / 'bin').iterdir():
        path.chmod(0o755)
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(TOOLS / 'lib64')
    return runtime, env


def tar_add(archive: tarfile.TarFile, path: Path, name: str, mode: int | None = None):
    entry = archive.gettarinfo(str(path), arcname=name)
    entry.uid = entry.gid = entry.mtime = 0
    entry.uname = entry.gname = ''
    if mode is not None:
        entry.mode = mode
    if entry.isfile():
        with path.open('rb') as data:
            archive.addfile(entry, data)
    else:
        archive.addfile(entry)


def tar_bytes(archive, name, data):
    entry = tarfile.TarInfo(name)
    entry.size = len(data)
    entry.mode = 0o644
    archive.addfile(entry, io.BytesIO(data))


def gzip_tar(path: Path):
    """Caller owns both streams; deterministic tar + XZ (or gzip for native sources).

    XZ reduces download size without removing any original source or runtime file.
    Preset 4 uses a small dictionary suitable for the phone's decoder.
    """
    raw = path.open('wb')
    zipped = (lzma.LZMAFile(raw, mode='wb', format=lzma.FORMAT_XZ, preset=4)
              if path.suffix == '.xz' else
              gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6))
    return raw, zipped, tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT)


def describe(path, asset=None, **extra):
    return {'asset': asset or path.name, 'bytes': path.stat().st_size, 'sha256': sha(path), **extra}


def prepare() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    lock = json.loads((APP / 'inputs.lock.json').read_text())
    for spec in lock['sources']:
        download(spec, CACHE)
    proot = download(lock['proot'], CACHE)
    node = download(lock['node'], CACHE / 'packages')
    native = BUILD / 'native/arm64-v8a'
    native.mkdir(parents=True, exist_ok=True)
    with tarfile.open(proot) as archive:
        for source, name in [('root/bin/proot', 'libproot.so'),
                             ('root/libexec/proot/loader', 'libproot-loader.so'),
                             ('root/libexec/proot/loader32', 'libproot-loader32.so')]:
            data = archive.extractfile(source).read()
            if not data.startswith(b'\x7fELF'):
                raise ValueError('Expected actual PRoot ELF, not a placeholder')
            (native / name).write_bytes(data)
    xz = CACHE / 'xz-java'
    if not (xz / 'src/org/tukaani/xz/XZInputStream.java').is_file():
        xz.mkdir(exist_ok=True)
        with tarfile.open(CACHE / 'xz-java-source.tar.gz') as archive:
            for entry in archive:
                p = Path(entry.name)
                if p.is_absolute() or '..' in p.parts or entry.issym() or entry.islnk():
                    raise ValueError('Unsafe XZ source entry')
                relative = Path(*p.parts[1:])
                target = xz / relative
                if entry.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif entry.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(entry).read())
    package = CACHE / 'arm64-runtime'
    package.mkdir(exist_ok=True)
    for name in ('package.json', 'package-lock.json'):
        shutil.copyfile(ROOT / 'android/runtime' / name, package / name)
    npm_marker = package / '.pinned-install'
    npm_hash = sha(package / 'package-lock.json')
    if not npm_marker.is_file() or npm_marker.read_text() != npm_hash:
        run(['npm', 'ci', '--prefix', package, '--cpu=arm64', '--os=linux', '--libc=glibc',
             '--ignore-scripts', '--no-audit', '--no-fund'])
        npm_marker.write_text(npm_hash)
    payload = CACHE / 'runtime.tar.xz'
    fingerprint = npm_hash + lock['node']['sha256'] + sha(ROOT / 'android/runtime-smoke.mjs')
    marker = CACHE / 'runtime-payload.input'
    expanded = 0
    if not payload.is_file() or not marker.is_file() or marker.read_text() != fingerprint:
        raw, zipped, archive = gzip_tar(payload)
        try:
            with tarfile.open(node) as node_archive:
                for source, destination, mode in [('package/bin/node', 'node/bin/node', 0o755),
                                                   ('package/LICENSE', 'node/LICENSE', 0o644)]:
                    entry = node_archive.getmember(source)
                    member = tarfile.TarInfo(destination); member.size = entry.size; member.mode = mode
                    archive.addfile(member, node_archive.extractfile(entry)); expanded += entry.size
            for path in sorted((package / 'node_modules').rglob('*')):
                if path.is_file() or path.is_symlink():
                    tar_add(archive, path, 'runtime/' + path.relative_to(package).as_posix())
                    if not path.is_symlink(): expanded += path.stat().st_size
            for name in ('package.json', 'package-lock.json'):
                p = package / name; tar_add(archive, p, 'runtime/' + name); expanded += p.stat().st_size
            bootstrap = ROOT / 'android/runtime-smoke.mjs'
            tar_add(archive, bootstrap, 'bootstrap/runtime-smoke.mjs', 0o644); expanded += bootstrap.stat().st_size
        finally:
            archive.close(); zipped.close(); raw.close()
        marker.write_text(fingerprint)
        (CACHE / 'runtime-expanded.txt').write_text(str(expanded))
    else:
        expanded = int((CACHE / 'runtime-expanded.txt').read_text())
    print('Runtime archive:', payload.stat().st_size, 'bytes;', expanded, 'expanded', flush=True)
    ARTIFACTS.mkdir(exist_ok=True)
    with (CACHE / 'source-check.json').open('w') as output:
        run(['python3', 'tools/upstreams.py', 'verify', '--json'], stdout=output)
    originals = CACHE / 'original-sources.tar.xz'
    raw, zipped, archive = gzip_tar(originals)
    files = byte_count = 0
    try:
        original_lock = json.loads((ROOT / 'upstream/lock.json').read_text())
        for name, project in original_lock['projects'].items():
            manifest = json.loads((ROOT / 'upstream' / project['manifest']).read_text())
            for path, mode, blob, size in manifest['files']:
                if mode == '160000':
                    continue
                source = ROOT / '.cache/sources' / project['path'] / path
                # mode 120000 has deliberately inert link-target bytes. Never activate them.
                tar_add(archive, source, f'original/{name}/{path}', 0o755 if mode == '100755' else 0o644)
                files += 1; byte_count += size
            print('Included original source:', name, flush=True)
        port_files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).split(b'\0')
        for encoded in sorted(set(port_files)):
            if not encoded: continue
            path = ROOT / os.fsdecode(encoded)
            if path.is_file() and not path.is_symlink():
                tar_add(archive, path, 'android-port/' + path.relative_to(ROOT).as_posix())
        tar_bytes(archive, 'SOURCE-PRESERVATION-NOTICE.txt', b'All 22839 pinned original Git blobs are retained; symlink targets are inert files. Git LFS pointers are present, but 892 external payload objects are not fetched. This is source preservation, not Android feature parity. See android-port/upstream/lock.json and manifests.\n')
    finally:
        archive.close(); zipped.close(); raw.close()
    if files != 22839 or byte_count != 390825039:
        raise ValueError(f'Unexpected source inventory: {files}, {byte_count}')
    native_sources = CACHE / 'native-corresponding-sources.tar.gz'
    raw, zipped, archive = gzip_tar(native_sources)
    try:
        for spec in lock['sources']:
            tar_add(archive, CACHE / spec['name'], spec['name'], 0o644)
        tar_add(archive, APP / 'inputs.lock.json', 'provenance.json', 0o644)
        tar_add(archive, APP / 'README.md', 'README.md', 0o644)
    finally:
        archive.close(); zipped.close(); raw.close()
    meta = {
        'schemaVersion': 1, 'version': '0.2.0-test', 'package': 'dev.terminator.phone',
        'architecture': 'arm64-v8a', 'minSdk': 26, 'targetSdk': 28,
        'parity': 'NOT_CERTIFIED', 'phoneTested': False,
        'rootfs': lock['rootfs'], 'runtime': describe(payload, expandedBytes=expanded),
        'sourceArchive': describe(originals, originalGitBlobs=files, originalGitBytes=byte_count, externalLfsAssetsIncluded=False),
        'nativeSources': describe(native_sources),
        'upstreams': {'openmausbot': '0.1.169', 'rea-agents': '6.9.0', 'node': '24.22.1'},
    }
    assets = BUILD / 'assets'
    if assets.exists(): shutil.rmtree(assets)
    assets.mkdir()
    for path in (payload, originals, native_sources): shutil.copyfile(path, assets / path.name)
    (assets / 'build-info.json').write_text(json.dumps(meta, indent=2) + '\n')
    (assets / 'feature-status.txt').write_text((ROOT / 'docs/APK.md').read_text() + '\n\n' + (ROOT / 'docs/FEATURE_PARITY.md').read_text())
    (assets / 'license-notes.txt').write_text((ROOT / 'NOTICE').read_text() + '\n\n' + (ROOT / 'docs/SECURITY_AND_LICENSES.md').read_text() + '\n\nNative container: green-green-avk/proot v0.15_release (GPL-2.0-or-later); talloc 2.1.14 (LGPL); XZ for Java 1.9 (public domain). Corresponding complete source archives are included and exportable. Compiler/JRE tools are build inputs only, not shipped in the app. Ubuntu is downloaded directly from the separately identified distribution on the first explicit prepare action; its package copyright and source information remains in /usr/share/doc. Node, npm dependencies and original enterprise code retain their own licenses. No enterprise entitlement or trademark license is granted.\n\n' + json.dumps(lock, indent=2))
    (BUILD / 'build-info.json').write_text(json.dumps(meta, indent=2) + '\n')
    return meta


def build(java_home: Path, env: dict) -> Path:
    java = java_home / 'bin/java'
    for folder in ('generated', 'classes', 'dex'):
        path = BUILD / folder
        if path.exists(): shutil.rmtree(path)
        path.mkdir(parents=True)
    run([TOOLS / 'aapt2', 'compile', '--dir', APP / 'src/main/res', '-o', BUILD / 'resources.zip'], env=env)
    run([TOOLS / 'aapt2', 'link', '-o', BUILD / 'resources.ap_', '--manifest', APP / 'src/main/AndroidManifest.xml', '-I', TOOLS / 'android.jar', '--java', BUILD / 'generated', BUILD / 'resources.zip'], env=env)
    source_paths = sorted((APP / 'src/main/java').rglob('*.java')) + sorted((BUILD / 'generated').rglob('*.java')) + sorted((CACHE / 'xz-java/src').rglob('*.java'))
    sources = BUILD / 'java-sources.txt'; sources.write_text('\n'.join(str(p) for p in source_paths) + '\n')
    run([java, '-jar', TOOLS / 'ecj.jar', '-8', '-proc:none', '-nowarn', '-bootclasspath', str(TOOLS / 'android.jar') + ':' + str(TOOLS / 'core-lambda-stubs.jar'), '-d', BUILD / 'classes', '@' + str(sources)])
    with zipfile.ZipFile(BUILD / 'classes.jar', 'w') as archive:
        for p in sorted((BUILD / 'classes').rglob('*.class')): archive.write(p, p.relative_to(BUILD / 'classes').as_posix())
    run([java, '-cp', TOOLS / 'r8.jar', 'com.android.tools.r8.D8', '--min-api', '26', '--lib', TOOLS / 'android.jar', '--output', BUILD / 'dex', BUILD / 'classes.jar'])
    unsigned = BUILD / 'unsigned.apk'
    shutil.copyfile(BUILD / 'resources.ap_', unsigned)
    with zipfile.ZipFile(unsigned, 'a') as archive:
        archive.write(BUILD / 'dex/classes.dex', 'classes.dex', compress_type=zipfile.ZIP_DEFLATED)
        for path in sorted((BUILD / 'assets').iterdir()): archive.write(path, 'assets/' + path.name, compress_type=zipfile.ZIP_STORED)
        for path in sorted((BUILD / 'native').rglob('*.so')): archive.write(path, 'lib/' + path.relative_to(BUILD / 'native').as_posix(), compress_type=zipfile.ZIP_DEFLATED)
    aligned = BUILD / 'aligned.apk'
    run([TOOLS / 'zipalign', '-p', '-f', '4', unsigned, aligned], env=env)
    signing = ROOT / 'android/signing'; signing.mkdir(mode=0o700, exist_ok=True)
    password = signing / 'test-password.txt'; key = signing / 'terminator-test.jks'
    if not key.exists():
        password.write_text(secrets.token_urlsafe(32)); password.chmod(0o600)
        run([java_home / 'bin/keytool', '-genkeypair', '-keystore', key, '-storetype', 'JKS', '-alias', 'terminator-test', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000', '-dname', 'CN=Terminator Development,OU=Local Test,O=Terminator', '-storepass:file', password, '-keypass:file', password, '-noprompt'])
        key.chmod(0o600)
    if not password.exists(): raise ValueError('Existing signing key has no local password file; do not replace a release key')
    output = ARTIFACTS / 'Terminator-0.2.0-arm64-test.apk'
    run([java, '-jar', TOOLS / 'apksigner.jar', 'sign', '--ks', key, '--ks-key-alias', 'terminator-test', '--ks-pass', 'file:' + str(password), '--v1-signing-enabled', 'true', '--v2-signing-enabled', 'true', '--v3-signing-enabled', 'true', '--v4-signing-enabled', 'false', '--out', output, aligned])
    verification = subprocess.check_output([str(java), '-jar', str(TOOLS / 'apksigner.jar'), 'verify', '--verbose', '--print-certs', str(output)], cwd=ROOT, text=True)
    print(verification)
    (ARTIFACTS / (output.name + '.signature.txt')).write_text(verification)
    run([TOOLS / 'zipalign', '-c', '-p', '4', output], env=env)
    digest = sha(output)
    (ARTIFACTS / (output.name + '.sha256')).write_text(f'{digest}  {output.name}\n')
    meta = json.loads((BUILD / 'build-info.json').read_text())
    meta['apk'] = {'name': output.name, 'bytes': output.stat().st_size, 'sha256': digest, 'signaturesVerified': True}
    (ARTIFACTS / 'Terminator-0.2.0-build.json').write_text(json.dumps(meta, indent=2) + '\n')
    print('APK BUILT:', output, output.stat().st_size, 'bytes', digest, flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    if not (args.prepare or args.build): parser.error('Pass --prepare and/or --build')
    BUILD.mkdir(parents=True, exist_ok=True); ARTIFACTS.mkdir(exist_ok=True)
    java, env = tools()
    if args.prepare: prepare()
    if args.build:
        if not (BUILD / 'assets/build-info.json').exists(): parser.error('Run --prepare first')
        build(java, env)

if __name__ == '__main__': main()
