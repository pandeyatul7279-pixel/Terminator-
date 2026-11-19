from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from tools.apk_inventory import (ApkError, NO_STRING, inspect_apk, manifest_facts,
                                 manifest_elements, split_consistency)


def binary_manifest(utf8=True):
    strings = ['manifest', 'package', 'org.example.phone', 'versionCode', 'split', 'config.arm64_v8a']
    encoded, offsets = b'', []
    for value in strings:
        raw = value.encode('utf-8' if utf8 else 'utf-16-le')
        offsets.append(len(encoded))
        encoded += (bytes([len(value), len(raw)]) + raw + b'\0') if utf8 else (struct.pack('<H', len(value)) + raw + b'\0\0')
    start = 28 + len(strings) * 4
    padding = b'\0' * (-(start + len(encoded)) % 4)
    pool = struct.pack('<HHIIIIII', 1, 28, start + len(encoded) + len(padding), len(strings), 0, 0x100 if utf8 else 0, start, 0)
    pool += struct.pack('<' + 'I' * len(offsets), *offsets) + encoded + padding
    def attr(key, value, kind=3):
        return struct.pack('<IIIHBBI', NO_STRING, key, NO_STRING, 8, 0, kind, value)
    attributes = attr(1, 2) + attr(3, 17, 0x10) + attr(4, 5)
    tag = struct.pack('<HHIII', 0x102, 16, 36 + len(attributes), 1, NO_STRING)
    tag += struct.pack('<IIHHHHHH', NO_STRING, 0, 20, 20, 3, 0, 0, 0) + attributes
    return struct.pack('<HHI', 3, 8, 8 + len(pool) + len(tag)) + pool + tag


class ApkInventoryTests(unittest.TestCase):
    def test_compiled_android_manifest(self):
        report = manifest_facts(binary_manifest())
        self.assertEqual(report['package'], 'org.example.phone')
        self.assertEqual(report['versionCode'], '17')
        self.assertEqual(report['split'], 'config.arm64_v8a')

    def test_utf16_compiled_android_manifest(self):
        report = manifest_facts(binary_manifest(utf8=False))
        self.assertEqual(report['package'], 'org.example.phone')
        self.assertEqual(report['versionCode'], '17')

    def test_plain_manifest_facts(self):
        report = manifest_facts(b'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.example" android:versionCode="2"><uses-sdk android:minSdkVersion="26"/><uses-permission android:name="android.permission.INTERNET"/></manifest>')
        self.assertEqual(report['minSdk'], '26')
        self.assertEqual(report['permissions'], ['android.permission.INTERNET'])

    def test_xml_entities_are_refused(self):
        with self.assertRaises(ApkError):
            manifest_elements(b'<!DOCTYPE manifest [<!ENTITY x "boom">]><manifest package="&x;"/>')

    def test_truncated_binary_is_refused(self):
        for data in (b'', b'\x03\x00', binary_manifest()[:-1]):
            with self.subTest(length=len(data)), self.assertRaises(ApkError):
                manifest_elements(data)

    def test_zero_chunk_cannot_loop(self):
        data = struct.pack('<HHI', 3, 8, 16) + struct.pack('<HHI', 1, 0, 0)
        with self.assertRaises(ApkError):
            manifest_elements(data)

    def test_invalid_string_index_is_refused(self):
        data = bytearray(binary_manifest())
        # Last attribute's string value lies at the end of the last chunk.
        struct.pack_into('<I', data, len(data) - 4, 999999)
        with self.assertRaises(ApkError):
            manifest_facts(bytes(data))

    def test_apk_inventory_does_not_execute_or_extract(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'base.apk'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('AndroidManifest.xml', binary_manifest())
                archive.writestr('lib/arm64-v8a/libexample.so', b'not executed')
                archive.writestr('classes.dex', b'not executed')
            report = inspect_apk(path)
            self.assertEqual(report['nativeAbis'], ['arm64-v8a'])
            self.assertEqual(report['dexFiles'], 1)
            self.assertEqual(len(report['sha256']), 64)
            self.assertEqual(report['signatureVerification'], 'NOT_PERFORMED')
            self.assertEqual(len(list(Path(temporary).iterdir())), 1)

    def test_valid_split_metadata_is_not_install_certification(self):
        reports = [{'package': 'org.example', 'versionCode': '1', 'split': None},
                   {'package': 'org.example', 'versionCode': '1', 'split': 'config.en'}]
        result = split_consistency(reports)
        self.assertTrue(result['metadataConsistent'])
        self.assertIn('NOT_CERTIFIED', result['installability'])

    def test_mismatched_packages_fail_consistency(self):
        reports = [{'package': 'one', 'versionCode': '1', 'split': None},
                   {'package': 'two', 'versionCode': '2', 'split': 'config.en'}]
        self.assertFalse(split_consistency(reports)['metadataConsistent'])

    def test_no_base_and_duplicate_splits_fail(self):
        report = {'package': 'org.example', 'versionCode': '1', 'split': 'config.en'}
        self.assertEqual(len(split_consistency([report, report])['problems']), 2)


if __name__ == '__main__':
    unittest.main()
