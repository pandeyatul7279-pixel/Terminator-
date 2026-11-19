import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerSafetyTests(unittest.TestCase):
    def test_shell_syntax(self):
        for path in (ROOT / 'android').glob('*.sh'):
            with self.subTest(script=path.name):
                result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_has_no_install_side_effects(self):
        for script in ('install-termux.sh', 'start-termux.sh'):
            result = subprocess.run(['bash', str(ROOT / 'android' / script), '--help'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Usage:', result.stdout)

    def test_non_termux_host_is_refused_before_package_management(self):
        result = subprocess.run(['bash', str(ROOT / 'android/install-termux.sh'), '--install', '--yes'],
                                env={**os.environ, 'PREFIX': ''}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('inside the official Termux', result.stderr)

    def test_unknown_option_is_refused(self):
        result = subprocess.run(['bash', str(ROOT / 'android/install-termux.sh'), '--unknown'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Unknown argument', result.stderr)

    def test_auth_and_isolation_are_not_bypassed(self):
        startup = (ROOT / 'android/start-ubuntu.sh').read_text()
        host = (ROOT / 'android/start-termux.sh').read_text()
        self.assertIn('OMB_LOOPBACK_TRUST=service', startup)
        self.assertIn('--isolated --user terminator', host)
        self.assertNotIn('OMB_DEV_TRUST_LOCAL_BROWSER=1', startup)
        self.assertNotIn('--no-sandbox', startup)


if __name__ == '__main__':
    unittest.main()
