"""Structural delivery guards; these are not Android or live hosting tests."""
from pathlib import Path
import re
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/private-apk-download.yml'


class PrivateDownloadWorkflowTests(unittest.TestCase):
    def test_embedded_delivery_python_compiles(self):
        content = WORKFLOW.read_text()
        program = content.split("python3 - <<'PY'\n", 1)[1].rsplit('\n          PY', 1)[0]
        compile(textwrap.dedent(program), str(WORKFLOW), 'exec')

    def test_only_draft_release_uploads_are_allowed(self):
        content = WORKFLOW.read_text()
        self.assertIn("'--draft', '--prerelease'", content)
        self.assertIn("if release['draft'] is not True:", content)
        self.assertIn("if result['draft'] is not True:", content)
        self.assertNotIn('upload-artifact@', content)
        self.assertNotIn('--draft=false', content)
        self.assertIn('tools/upstreams.py fetch', content)
        self.assertIn('tools/build_apk.py --prepare --build', content)
        self.assertIn("meta['parity'] != 'NOT_CERTIFIED'", content)
        self.assertIn("meta['phoneTested'] is not False", content)

    def test_actions_are_pinned_and_keys_are_not_persisted(self):
        content = WORKFLOW.read_text()
        actions = re.findall(r'uses:\s+(\S+)', content)
        self.assertEqual(len(actions), 2)
        for action in actions:
            self.assertRegex(action, r'^[\w-]+/[\w-]+@[0-9a-f]{40}$')
        self.assertIn('persist-credentials: false', content)
        self.assertNotIn('actions/cache@', content)
        self.assertIn("'Accept': 'application/octet-stream'", content)
        self.assertIn('NoRedirect', content)
        self.assertIn("urllib.request.Request(scoped_url, method='HEAD')", content)
        self.assertNotIn('print(scoped_url)', content)

    def test_documented_distribution_and_download_boundaries(self):
        guide = (ROOT / 'docs/APK.md').read_text()
        self.assertIn('100 MB limit', guide)
        self.assertIn('traffic-access header', guide)
        self.assertIn('prohibits redistribution', guide)
        self.assertIn('Do not publish this draft', guide)
        self.assertIn('not an in-place update', guide)


if __name__ == '__main__':
    unittest.main()
