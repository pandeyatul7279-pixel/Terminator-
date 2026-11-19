#!/usr/bin/env python3
"""Identify APK/split metadata without installing, executing or extracting an app.

Reports identity, permissions, ABIs, DEX counts and SHA-256. Does NOT verify APK
signatures, recover original source, bypass protections, or certify installability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

MAX_MANIFEST = 8 * 1024 * 1024
NO_STRING = 0xFFFFFFFF


class ApkError(ValueError):
    pass


def unpack(fmt, data, offset):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise ApkError("Truncated binary Android manifest")
    return struct.unpack_from(fmt, data, offset)


def length_at(data, offset, utf8):
    if utf8:
        first, = unpack('<B', data, offset)
        if first & 0x80:
            second, = unpack('<B', data, offset + 1)
            return ((first & 0x7F) << 8) | second, offset + 2
        return first, offset + 1
    first, = unpack('<H', data, offset)
    if first & 0x8000:
        second, = unpack('<H', data, offset + 2)
        return ((first & 0x7FFF) << 16) | second, offset + 4
    return first, offset + 2


def string_pool(chunk):
    _, header_size, chunk_size = unpack('<HHI', chunk, 0)
    if header_size < 28 or chunk_size != len(chunk):
        raise ApkError("Invalid Android string pool header")
    count, styles, flags, start, _ = unpack('<IIIII', chunk, 8)
    if count > 1000000 or header_size + (count + styles) * 4 > len(chunk) or start < header_size + (count + styles) * 4:
        raise ApkError("Invalid Android string pool bounds")
    utf8 = bool(flags & 0x100)
    strings = []
    for index in range(count):
        relative, = unpack('<I', chunk, header_size + index * 4)
        offset = start + relative
        if utf8:
            _, offset = length_at(chunk, offset, True)  # UTF-16 character count.
        length, offset = length_at(chunk, offset, utf8)
        byte_count = length if utf8 else length * 2
        terminator = b'\0' if utf8 else b'\0\0'
        end = offset + byte_count
        if end + len(terminator) > len(chunk) or chunk[end:end + len(terminator)] != terminator:
            raise ApkError("Truncated/unterminated Android string")
        try:
            strings.append(chunk[offset:end].decode('utf-8' if utf8 else 'utf-16-le'))
        except UnicodeError as error:
            raise ApkError("Invalid Android manifest string encoding") from error
    return strings


def manifest_elements(data: bytes):
    if len(data) > MAX_MANIFEST:
        raise ApkError("Manifest exceeds safe inspection limit")
    if data.lstrip().startswith(b'<'):
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ApkError("XML declarations/entities are not allowed")
        try:
            root = ET.fromstring(data)
        except ET.ParseError as error:
            raise ApkError("Invalid XML manifest") from error
        return [(element.tag.rsplit('}', 1)[-1], {key.rsplit('}', 1)[-1]: value for key, value in element.attrib.items()})
                for element in root.iter()]
    kind, header_size, size = unpack('<HHI', data, 0)
    if kind != 3 or header_size < 8 or size != len(data):
        raise ApkError("Not a complete Android binary XML document")
    strings = []
    elements = []
    offset = header_size

    def string(index):
        if not 0 <= index < len(strings):
            raise ApkError("Invalid Android manifest string reference")
        return strings[index]

    while offset < size:
        kind, header, length = unpack('<HHI', data, offset)
        if header < 8 or length < header or offset + length > size:
            raise ApkError("Invalid Android XML chunk bounds")
        chunk = data[offset:offset + length]
        if kind == 1:
            strings = string_pool(chunk)
        elif kind == 0x0102:
            if header != 16 or length < 36:
                raise ApkError("Invalid Android start-element header")
            _, name, attribute_start, attribute_size, count, _, _, _ = unpack('<IIHHHHHH', chunk, 16)
            first = 16 + attribute_start
            if attribute_size < 20 or first < 36 or first + count * attribute_size > length:
                raise ApkError("Invalid Android attribute bounds")
            attributes = {}
            for index in range(count):
                position = first + index * attribute_size
                _, key, raw, value_size, zero, value_type, value = unpack('<IIIHBBI', chunk, position)
                if value_size != 8 or zero != 0:
                    raise ApkError("Invalid typed Android attribute")
                if raw != NO_STRING:
                    decoded = string(raw)
                elif value_type == 3:
                    decoded = string(value)
                elif value_type == 0x12:
                    decoded = bool(value)
                elif value_type in (0x10, 0x11):
                    decoded = value
                else:
                    decoded = f'@0x{value:08x}'
                attributes[string(key)] = decoded
            elements.append((string(name), attributes))
        offset += length
    if offset != size:
        raise ApkError("Incomplete Android XML document")
    return elements


def manifest_facts(data: bytes) -> dict:
    elements = manifest_elements(data)
    manifests = [attrs for name, attrs in elements if name == 'manifest']
    if len(manifests) != 1 or not isinstance(manifests[0].get('package'), str):
        raise ApkError("Manifest has no unique package identity")
    root = manifests[0]
    sdk = next((attrs for name, attrs in elements if name == 'uses-sdk'), {})
    return {'package': root['package'], 'versionCode': str(root.get('versionCode', '')),
            'versionName': root.get('versionName'), 'split': root.get('split'),
            'minSdk': sdk.get('minSdkVersion'), 'targetSdk': sdk.get('targetSdkVersion'),
            'permissions': sorted({attrs['name'] for name, attrs in elements
                                   if name.startswith('uses-permission') and isinstance(attrs.get('name'), str)})}


def inspect_apk(path: Path) -> dict:
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 200000:
            raise ApkError("APK has too many entries for bounded inspection")
        manifests = [entry for entry in entries if entry.filename == 'AndroidManifest.xml']
        if len(manifests) != 1 or manifests[0].file_size > MAX_MANIFEST:
            raise ApkError("Missing, duplicate, or oversized AndroidManifest.xml")
        if manifests[0].compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ApkError("Unexpected APK manifest compression method")
        with archive.open(manifests[0]) as stream:
            data = stream.read(MAX_MANIFEST + 1)
        if len(data) > MAX_MANIFEST or len(data) != manifests[0].file_size:
            raise ApkError("Manifest decompression exceeded declared inspection bounds")
        facts = manifest_facts(data)
        abis = sorted({parts[1] for entry in entries if len(parts := entry.filename.split('/')) >= 3
                       and parts[0] == 'lib' and entry.filename.endswith('.so')})
        dex_count = sum(bool(re.fullmatch(r'classes(?:[0-9]+)?\.dex', entry.filename)) for entry in entries)
    return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': hasher.hexdigest(),
            **facts, 'nativeAbis': abis, 'dexFiles': dex_count, 'signatureVerification': 'NOT_PERFORMED'}


def split_consistency(reports: list[dict]) -> dict:
    problems = []
    if len({report['package'] for report in reports}) != 1:
        problems.append('Package IDs differ')
    if len({report['versionCode'] for report in reports}) != 1:
        problems.append('Version codes differ')
    if sum(not report['split'] for report in reports) != 1:
        problems.append('Expected exactly one base APK')
    splits = [report['split'] for report in reports if report['split']]
    if len(splits) != len(set(splits)):
        problems.append('Duplicate split identities')
    return {'metadataConsistent': not problems, 'problems': problems,
            'installability': 'NOT_CERTIFIED: signatures, required splits and device compatibility are not verified'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apks', type=Path, nargs='+')
    args = parser.parse_args(argv)
    try:
        reports = [inspect_apk(path) for path in args.apks]
        print(json.dumps({'apks': reports, 'splitSet': split_consistency(reports)}, indent=2))
        return 0
    except (ApkError, OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        print(f'APK inspection failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
