"""Offline repair packaging and structural guards; not an Android runtime test."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools import build_apk

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'android/app'
JAVA = APP / 'src/main/java/dev/terminator/phone'
A = '{http://schemas.android.com/apk/res/android}'


class RepairApkSafetyTests(unittest.TestCase):
    def test_repair_installs_alongside_not_over_existing_data(self):
        old = ET.parse(APP / 'src/main/AndroidManifest.xml').getroot()
        repair = ET.parse(APP / 'src/repair/AndroidManifest.xml').getroot()
        self.assertEqual(repair.get('package'), 'dev.terminator.phone.repair')
        self.assertNotEqual(repair.get('package'), old.get('package'))
        self.assertEqual(repair.get(A + 'versionName'), '0.2.1-repair-test')
        self.assertEqual(repair.find('application/activity').get(A + 'name'), 'dev.terminator.phone.MainActivity')
        self.assertEqual(repair.find('application/service').get(A + 'exported'), 'false')
        self.assertEqual(repair.find('application').get(A + 'allowBackup'), 'false')
        self.assertEqual([x.get(A + 'name') for x in repair.findall('queries/package')], [old.get('package')])
        self.assertEqual({x.get(A + 'name') for x in repair.findall('uses-permission')}, {x.get(A + 'name') for x in old.findall('uses-permission')})
        self.assertEqual(repair.findall('.//receiver'), [])
        self.assertIsNone(repair.get(A + 'sharedUserId'))

    def test_import_pins_identify_exact_already_delivered_apk(self):
        source = json.loads((APP / 'repair-source.lock.json').read_text())
        self.assertEqual(source['sourcePackage'], 'dev.terminator.phone')
        self.assertEqual(source['sourceVersionCode'], 2)
        self.assertEqual(source['sourceApkBytes'], 325412043)
        self.assertEqual(source['sourceSignerSha256'], '2a462b1ce45587f753724250059ba3bcd91736febc83dce3f85d255180b80e9c')
        self.assertEqual(source['sourceApkSha256'], '8580191259d750fd0382eceb6780adb8a96fe777ed46cdc49e11a952f47803bf')
        lock = json.loads((APP / 'inputs.lock.json').read_text())
        self.assertEqual(source['rootfsSha256'], lock['rootfs']['sha256'])
        self.assertEqual(source['sourceArchive']['originalGitBlobs'], 22839)
        self.assertEqual(source['sourceArchive']['originalGitBytes'], 390825039)
        self.assertFalse(source['sourceArchive']['externalLfsAssetsIncluded'])
        self.assertEqual(sum(source[s]['bytes'] for s in ('runtime', 'sourceArchive', 'nativeSources')), 325189456)

    def test_old_public_apk_is_authenticated_before_resource_import(self):
        source = (JAVA / 'RuntimeAssets.java').read_text()
        self.assertIn('PackageManager.GET_SIGNING_CERTIFICATES', source)
        self.assertIn('PackageManager.GET_SIGNATURES', source)
        self.assertIn('signatures.length==1', source)
        self.assertIn('source.getString("signerSha256").equals(signer)', source)
        self.assertIn('installed.applicationInfo.sourceDir', source)
        self.assertIn('source.getString("apkSha256"),source.getLong("apkBytes")', source)
        self.assertLess(source.index('source.getString("apkSha256")'), source.index('context.createPackageContext(pkg,0)'))
        self.assertIn('original.getAssets().open(name)', source)
        self.assertNotIn('original.getFilesDir', source)
        self.assertNotIn('Context.CONTEXT_INCLUDE_CODE', source)
        self.assertNotIn('CONTEXT_IGNORE_SECURITY', source)
        self.assertIn('VerifiedFiles.importAsset', source)

    def test_engine_and_source_exports_use_verified_payload_access(self):
        installer = (JAVA / 'RuntimeInstaller.java').read_text()
        activity = (JAVA / 'MainActivity.java').read_text()
        self.assertIn('assets.prepare(status)', installer)
        self.assertIn('InputStream in=assets.open(asset)', installer)
        self.assertIn('new RuntimeAssets(this).open(asset)', activity)
        self.assertIn('private data/settings na access honge na delete', activity)
        self.assertIn('purane app ka in-place update nahi', activity)
        self.assertIn('Export repair app source', activity)

    def test_failure_diagnostics_retain_exception_type_causes_and_cleanup(self):
        service = (JAVA / 'RuntimeService.java').read_text()
        installer = (JAVA / 'RuntimeInstaller.java').read_text()
        self.assertIn('error.printStackTrace', service)
        self.assertIn('error.getClass().getSimpleName()', service)
        self.assertIn('safe(message)', service)
        self.assertIn('logs.length()>16000', service)
        self.assertIn('error.addSuppressed(cleanup)', installer)
        self.assertIn('extracted.copiedHardLinks', installer)

    def test_repair_prepare_preserves_all_three_complete_asset_descriptors(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            proot = base / 'proot.tar.gz'
            with tarfile.open(proot, 'w:gz') as archive:
                for name in ('root/bin/proot', 'root/libexec/proot/loader', 'root/libexec/proot/loader32'):
                    data = b'\x7fELFtest fixture, never executed';entry = tarfile.TarInfo(name);entry.size = len(data)
                    archive.addfile(entry, io.BytesIO(data))
            xz = base / 'xz.tar.gz'
            with tarfile.open(xz, 'w:gz') as archive:
                entry = tarfile.TarInfo('xz-java-fixture/src/org/tukaani/xz/XZInputStream.java');entry.size = 2
                archive.addfile(entry, io.BytesIO(b'//'))
            def download(spec, directory):
                return proot if spec['name'] == 'proot-android-aarch64.tar.gz' else xz
            cache, build = base / 'cache', base / 'build'
            with mock.patch.multiple(build_apk, CACHE=cache, BUILD=build), mock.patch.object(build_apk, 'download', side_effect=download):
                info = build_apk.prepare_repair()
            expected = json.loads((APP / 'repair-source.lock.json').read_text())
            for key in ('runtime', 'sourceArchive', 'nativeSources', 'upstreams'):
                self.assertEqual(info[key], expected[key])
            self.assertFalse(info['phoneTested'])
            self.assertEqual(info['parity'], 'NOT_CERTIFIED')
            self.assertEqual(info['deliveryMode'], 'installed-apk-import')
            self.assertFalse(info['importFromInstalled']['privateDataImported'])
            assets = build / 'assets'
            for key in ('runtime', 'sourceArchive', 'nativeSources'):
                self.assertFalse((assets / info[key]['asset']).exists(), 'Small download depends explicitly on already installed APK')
            port = assets / info['portSources']['asset']
            self.assertEqual(build_apk.sha(port), info['portSources']['sha256'])
            with tarfile.open(port) as archive:
                for name in ('SafeTar.java', 'RuntimeAssets.java', 'VerifiedFiles.java'):
                    self.assertEqual(archive.extractfile('android-port/' + (JAVA / name).relative_to(ROOT).as_posix()).read(), (JAVA / name).read_bytes())
                self.assertFalse(any('/signing/' in name or name.endswith('.jks') for name in archive.getnames()))

    def test_repair_dependency_and_phone_uncertainty_are_not_hidden(self):
        guide = (ROOT / 'docs/PHONE_REPAIR.md').read_text()
        self.assertIn('not a standalone', guide)
        self.assertIn('actual Android errno is **not established**', guide)
        self.assertIn('not Android engine-boot evidence', guide)
        self.assertIn('purane app ka update nahi', guide)
        self.assertIn('2 GB', guide)
        self.assertIn('has run for this repair yet', guide)


if __name__ == '__main__':
    unittest.main()
