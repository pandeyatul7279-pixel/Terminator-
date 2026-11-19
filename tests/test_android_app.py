"""Structural regression gates; these are NOT Android device tests."""
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from tools import package_kit

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'android/app'
ANDROID='{http://schemas.android.com/apk/res/android}'

class NativeAppSafetyTests(unittest.TestCase):
    def test_real_launcher_and_private_service(self):
        manifest=ET.parse(APP/'src/main/AndroidManifest.xml').getroot()
        app=manifest.find('application');service=app.find('service');activity=app.find('activity')
        self.assertEqual(service.get(ANDROID+'exported'),'false')
        self.assertEqual(activity.get(ANDROID+'name'),'.MainActivity')
        self.assertEqual(app.get(ANDROID+'allowBackup'),'false')
        self.assertEqual(app.get(ANDROID+'extractNativeLibs'),'true')
    def test_legacy_target_is_explicitly_documented(self):
        sdk=ET.parse(APP/'src/main/AndroidManifest.xml').getroot().find('uses-sdk')
        self.assertEqual(sdk.get(ANDROID+'minSdkVersion'),'26');self.assertEqual(sdk.get(ANDROID+'targetSdkVersion'),'28')
        self.assertRegex((ROOT/'docs/APK.md').read_text(),r'targets? API 28')
    def test_no_broad_storage_root_or_silent_boot_permissions(self):
        manifest=ET.parse(APP/'src/main/AndroidManifest.xml').getroot()
        actual={x.get(ANDROID+'name') for x in manifest.findall('uses-permission')}
        self.assertEqual(actual,{'android.permission.INTERNET','android.permission.ACCESS_NETWORK_STATE','android.permission.FOREGROUND_SERVICE','android.permission.WAKE_LOCK','android.permission.RECORD_AUDIO'})
        self.assertEqual(manifest.findall('.//receiver'),[])
    def test_cleartext_is_only_for_phone_loopback(self):
        policy=ET.parse(APP/'src/main/res/xml/network_security_config.xml').getroot()
        self.assertEqual(policy.find('base-config').get('cleartextTrafficPermitted'),'false')
        permitted={x.text for config in policy.findall('domain-config') if config.get('cleartextTrafficPermitted')=='true' for x in config.findall('domain')}
        self.assertEqual(permitted,{'localhost','127.0.0.1'})
    def test_no_unscoped_javascript_owner_bridge(self):
        source=(APP/'src/main/java/dev/terminator/phone/MainActivity.java').read_text()
        self.assertNotIn('addJavascriptInterface',source)
        self.assertIn('setAllowUniversalAccessFromFileURLs(false)',source)
        self.assertIn('sameOrigin(request.getOrigin(),local)',source)
        service=(APP/'src/main/java/dev/terminator/phone/RuntimeService.java').read_text()
        self.assertIn('"OMB_LOOPBACK_TRUST","service"',service)
        self.assertIn('"OMB_CLI_OWNER_STDIN","1"',service)
        self.assertIn('process.getOutputStream()',service)
    def test_distribution_is_pinned_and_not_an_installer_script(self):
        lock=json.loads((APP/'inputs.lock.json').read_text());os=lock['rootfs']
        self.assertEqual(os['bytes'],65051348)
        self.assertEqual(os['gitBlob'],'2daa70bda0d05310898b3ca1074179544b154663')
        self.assertEqual(os['url'],'https://api.github.com/repos/EXALAB/AnLinux-Resources/git/blobs/'+os['gitBlob'])
        self.assertRegex(os['sha256'],r'^[0-9a-f]{64}$')
        self.assertGreater(lock['proot']['bytes'],100000)
        self.assertEqual(len(lock['sources']),3)
    def test_private_signing_text_is_excluded_from_legacy_kit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in package_kit.ROOT_FILES:(root/name).write_text('fixture')
            secret=root/'android/signing';secret.mkdir(parents=True);(secret/'test-password.txt').write_text('do-not-package')
            public=root/'android/app';public.mkdir(parents=True);(public/'README.md').write_text('public')
            files=[x.relative_to(root).as_posix() for x in package_kit.selected_files(root)]
            self.assertNotIn('android/signing/test-password.txt',files)
            self.assertIn('android/app/README.md',files)
    def test_full_parity_is_not_claimed(self):
        guide=(ROOT/'docs/APK.md').read_text()
        self.assertIn('not a full-parity release',guide)
        java=(APP/'src/main/java/dev/terminator/phone/MainActivity.java').read_text()
        self.assertIn('NOT FULL-PARITY CERTIFIED',java)
        self.assertIn('Full parity: NOT CERTIFIED',java)

if __name__=='__main__':unittest.main()
