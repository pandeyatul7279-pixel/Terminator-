"""No-network tests of the private one-file delivery protocol, not phone tests."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('drive_delivery', ROOT / 'tools/drive_delivery.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
# Non-secret fixture; no request in this test suite reaches any network.
SESSION = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=unit-test-session'


def active(offset):
    return 200, {'X-Goog-Upload-Status': 'active', 'X-Goog-Upload-Size-Received': str(offset)}, b''


def final():
    return 200, {'X-Goog-Upload-Status': 'final'}, b'{"id":"fixture-file"}'


class DriveDeliveryTests(unittest.TestCase):
    def test_only_scoped_https_drive_upload_destination_is_allowed(self):
        self.assertEqual(d.validate_session(SESSION).hostname, 'www.googleapis.com')
        for uri in [SESSION.replace('https:', 'http:'), SESSION.replace('www.googleapis.com', 'example.com'),
                    SESSION.replace('/upload/drive/v3/files', '/other'),
                    SESSION.replace('www.googleapis.com', 'user@www.googleapis.com'),
                    SESSION.replace('www.googleapis.com', 'www.googleapis.com:8443'),
                    SESSION.replace('resumable', 'media'), SESSION + '#fragment', SESSION + '\n']:
            with self.subTest(uri=uri), self.assertRaises(d.DeliveryError):
                d.validate_session(uri)

    def test_http_200_active_is_not_mistaken_for_completion(self):
        state, offset, _ = d.acknowledge(*active(d.CHUNK), d.CHUNK + 7)
        self.assertEqual((state, offset), ('active', d.CHUNK))

    def test_http_200_final_uses_the_upload_status_header(self):
        state, offset, receipt = d.acknowledge(*final(), d.CHUNK + 7)
        self.assertEqual((state, offset, receipt['id']), ('final', d.CHUNK + 7, 'fixture-file'))

    def test_classic_drive_range_is_supported(self):
        reply = (308, {'Range': f'bytes=0-{d.CHUNK - 1}'}, b'')
        self.assertEqual(d.acknowledge(*reply, 2 * d.CHUNK)[:2], ('active', d.CHUNK))

    def test_classic_missing_range_does_not_skip_unreceived_bytes(self):
        self.assertEqual(d.acknowledge(308, {}, b'', d.CHUNK, d.CHUNK)[:2], ('active', 0))

    def test_classic_completion_needs_a_file_receipt(self):
        self.assertEqual(d.acknowledge(200, {}, b'{"id":"fixture-file"}', 7)[0], 'final')
        with self.assertRaises(d.DeliveryError):
            d.acknowledge(200, {}, b'{}', 7)

    def test_invalid_or_unaligned_offsets_are_refused(self):
        for offset in (-1, 4, 3 * d.CHUNK):
            with self.subTest(offset=offset), self.assertRaises(d.DeliveryError):
                d.acknowledge(*active(offset), 2 * d.CHUNK)
        with self.assertRaises(d.DeliveryError):
            d.acknowledge(308, {'Range': 'invalid'}, b'', d.CHUNK)

    def test_server_and_quota_errors_are_retryable_not_completion(self):
        for status in (429, 500, 503):
            with self.subTest(status=status), self.assertRaises(d.RetryUpload):
                d.acknowledge(status, {'X-Goog-Upload-Status': 'active'}, b'', d.CHUNK)
        with self.assertRaises(d.DeliveryError):
            d.acknowledge(400, {}, b'{"error":{}}', d.CHUNK)

    def make_file(self, directory, size):
        path = Path(directory) / 'fixture.apk'
        path.write_bytes(b'a' * size)
        return path

    def test_chunks_are_256_kib_except_the_final_chunk(self):
        with tempfile.TemporaryDirectory() as folder:
            size = d.CHUNK + 7
            path = self.make_file(folder, size)
            uploader = d.ResumableUpload(SESSION, size)
            uploader.put = Mock(side_effect=[active(0), active(d.CHUNK), final()])
            receipt = uploader.upload(path)
            self.assertEqual(receipt['id'], 'fixture-file')
            calls = uploader.put.call_args_list
            self.assertTrue(calls[0].kwargs['query'])
            self.assertEqual([len(c.args[0]) for c in calls[1:]], [d.CHUNK, 7])
            self.assertEqual([c.args[1] for c in calls[1:]], [0, d.CHUNK])
            self.assertTrue(calls[-1].kwargs['finalise'])

    def test_disconnect_after_acknowledged_chunk_queries_before_resending(self):
        with tempfile.TemporaryDirectory() as folder:
            size = d.CHUNK + 7
            path = self.make_file(folder, size)
            sleep = Mock()
            uploader = d.ResumableUpload(SESSION, size, sleep=sleep)
            uploader.put = Mock(side_effect=[active(0), OSError('fixture disconnect'), active(d.CHUNK), final()])
            uploader.upload(path)
            calls = uploader.put.call_args_list
            self.assertTrue(calls[2].kwargs['query'])
            self.assertEqual(calls[3].args[1], d.CHUNK)
            self.assertEqual(len(calls[3].args[0]), 7)
            sleep.assert_called_once_with(1)

    def test_completed_session_is_not_uploaded_again(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder, 7)
            uploader = d.ResumableUpload(SESSION, 7)
            uploader.put = Mock(return_value=final())
            uploader.upload(path)
            self.assertEqual(uploader.put.call_count, 1)
            self.assertTrue(uploader.put.call_args.kwargs['query'])

    def test_upload_cannot_stall_forever(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_file(folder, d.CHUNK)
            uploader = d.ResumableUpload(SESSION, d.CHUNK)
            uploader.put = Mock(return_value=active(0))
            with self.assertRaisesRegex(d.DeliveryError, 'progress'):
                uploader.upload(path)
            self.assertLess(uploader.put.call_count, 10)

    def test_content_range_and_google_headers_do_not_forward_github_credentials(self):
        response = Mock(status=200)
        response.read.return_value = b''
        response.getheaders.return_value = [('X-Goog-Upload-Status', 'active')]
        connection = Mock()
        connection.getresponse.return_value = response
        factory = Mock(return_value=connection)
        uploader = d.ResumableUpload(SESSION, d.CHUNK + 7, connect=factory)
        uploader.put(b'a' * d.CHUNK, 0)
        method, target = connection.request.call_args.args
        headers = connection.request.call_args.kwargs['headers']
        self.assertEqual(method, 'PUT')
        self.assertIn('uploadType=resumable', target)
        self.assertEqual(headers['Content-Range'], f'bytes 0-{d.CHUNK - 1}/{d.CHUNK + 7}')
        self.assertEqual(headers['X-Goog-Upload-Command'], 'upload')
        self.assertEqual(headers['X-Goog-Upload-Offset'], '0')
        self.assertNotIn('Authorization', headers)
        uploader.put(b'a' * 7, d.CHUNK, finalise=True)
        self.assertEqual(connection.request.call_args.kwargs['headers']['X-Goog-Upload-Command'], 'upload, finalize')
        uploader.close()
        connection.close.assert_called_once()

    def test_delivery_does_not_rebuild_or_publicly_share_the_apk(self):
        workflow = (ROOT / '.github/workflows/deliver-apk-to-drive.yml').read_text()
        source = (ROOT / 'tools/drive_delivery.py').read_text()
        self.assertNotIn('build_apk.py', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('tools/drive_delivery.py', workflow)
        self.assertNotIn('make_public', source)
        self.assertIn("current['draft'] is not True", source)
        self.assertIn("HANDOFF.sub('', body)", source)
        self.assertIn("gh_json(f'repos/{repo}/releases/{release_id}'", source)
        self.assertIn('Source APK checksum or length mismatch; no bytes sent to Drive', source)


if __name__ == '__main__':
    unittest.main()
