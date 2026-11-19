import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.package_kit import ROOT, build, selected_files, verify


class PackageKitTests(unittest.TestCase):
    def test_selected_files_exclude_credentials_downloads_and_modules(self):
        files = [path.relative_to(ROOT).as_posix() for path in selected_files()]
        self.assertIn('android/runtime/package-lock.json', files)
        self.assertIn('upstream/lock.json', files)
        self.assertFalse(any('node_modules' in path or path.startswith('.git/') or path.startswith('.cache/') for path in files))
        self.assertFalse(any(path.endswith(('.apk', '.deb', '.exe', '.env')) for path in files))

    def test_archive_is_deterministic_and_checksummed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            first = directory / 'first.tgz'
            second = directory / 'second.tgz'
            a, b = build(first), build(second)
            self.assertEqual(a['sha256'], b['sha256'])
            with tarfile.open(first, 'r:gz') as archive:
                names = archive.getnames()
                self.assertTrue(all(name.startswith('terminator-android-kit/') for name in names))
                self.assertTrue(all(archive.getmember(name).isfile() for name in names))
                manifest = json.load(archive.extractfile('terminator-android-kit/KIT-SHA256.json'))
                for name, expected in manifest['files'].items():
                    actual = hashlib.sha256(archive.extractfile('terminator-android-kit/' + name).read()).hexdigest()
                    self.assertEqual(actual, expected)

    def test_extracted_kit_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'sample.txt').write_text('correct')
            manifest = {'schemaVersion': 1, 'files': {'sample.txt': hashlib.sha256(b'correct').hexdigest()}}
            (root / 'KIT-SHA256.json').write_text(json.dumps(manifest))
            self.assertTrue(verify(root)['ok'])
            (root / 'sample.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                verify(root)

    def test_checksum_parent_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / 'kit'
            outside = parent / 'outside'
            root.mkdir()
            outside.mkdir()
            (outside / 'sample.txt').write_text('correct')
            (root / 'subfolder').symlink_to(outside, target_is_directory=True)
            manifest = {'schemaVersion': 1, 'files': {'subfolder/sample.txt': hashlib.sha256(b'correct').hexdigest()}}
            (root / 'KIT-SHA256.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                verify(root)

    def test_checksum_path_traversal_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'KIT-SHA256.json').write_text(json.dumps({'schemaVersion': 1, 'files': {'../outside': 'abc'}}))
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                verify(root)


if __name__ == '__main__':
    unittest.main()
