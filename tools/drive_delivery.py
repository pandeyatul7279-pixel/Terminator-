#!/usr/bin/env python3
"""Privately transfer an existing verified APK to a pre-authorised Drive session.

Hosted-runner tool, not an Android component. No Drive account credential is
used. A file-scoped upload capability is consumed from an unpublished draft,
removed before network transfer, never committed or printed. No public sharing.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

CHUNK = 256 * 1024
HANDOFF = re.compile(r'<!-- terminator-drive-upload\n(.*?)\n-->', re.S)
RESULT = re.compile(r'<!-- terminator-drive-result\n(.*?)\n-->', re.S)


class DeliveryError(ValueError):
    """A deliberately credential-free diagnostic."""


class RetryUpload(Exception):
    pass


def validate_session(uri: str):
    try:
        url = urllib.parse.urlsplit(uri)
        valid = (url.scheme == 'https' and url.hostname == 'www.googleapis.com'
                 and url.port in (None, 443) and url.username is None and url.password is None
                 and url.path == '/upload/drive/v3/files' and not url.fragment
                 and len(uri) < 16384 and not any(c in uri for c in '\r\n\0')
                 and urllib.parse.parse_qs(url.query).get('uploadType') == ['resumable'])
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise DeliveryError('Expected the file-scoped HTTPS Drive resumable session')
    return url


def acknowledge(status: int, headers: dict, body: bytes, total: int, fallback=None):
    """Use upload active/final headers, not HTTP 200 as a completion signal.

    Also accept the original Drive v3 Content-Range protocol when that endpoint
    omits X-Goog headers. A classic final response must contain a file ID.
    """
    h = {k.lower(): v for k, v in headers.items()}
    if status == 429 or status >= 500:
        raise RetryUpload()
    if status >= 400:
        raise DeliveryError(f'Drive rejected the upload request (HTTP {status})')
    state = h.get('x-goog-upload-status', '').lower()
    try:
        data = json.loads(body) if body.strip() else {}
    except (ValueError, UnicodeError):
        data = {}
    if not isinstance(data, dict) or 'error' in data:
        raise DeliveryError('Drive returned an invalid upload receipt')
    if state == 'final':
        return 'final', total, data
    if state not in ('', 'active'):
        raise DeliveryError('Drive returned an unsupported upload state')
    if state == 'active' or status == 308:
        if 'x-goog-upload-size-received' in h:
            try:
                offset = int(h['x-goog-upload-size-received'])
            except ValueError:
                raise DeliveryError('Drive returned an invalid acknowledged length') from None
        elif 'range' in h:
            match = re.fullmatch(r'bytes=0-(\d+)', h['range'])
            if not match:
                raise DeliveryError('Drive returned an invalid acknowledged range')
            offset = int(match.group(1)) + 1
        elif state == 'active' and fallback is not None:
            offset = fallback
        elif status == 308:
            # Classic Drive explicitly omits Range when it has stored no bytes.
            offset = 0
        else:
            raise DeliveryError('Drive did not provide the resumable offset')
        if not 0 <= offset <= total or (offset != total and offset % CHUNK):
            raise DeliveryError('Drive returned an unsafe resumable offset')
        return 'active', offset, data
    if status in (200, 201) and data.get('id'):
        return 'final', total, data
    raise DeliveryError('Drive did not acknowledge or finalise the upload')


class ResumableUpload:
    def __init__(self, uri, total, *, connect=http.client.HTTPSConnection, sleep=time.sleep):
        url = validate_session(uri)
        self.host, self.target = url.hostname, url.path + '?' + url.query
        self.total, self.connect, self.sleep = total, connect, sleep
        self.connection = None

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def put(self, data, offset, *, query=False, finalise=False):
        if self.connection is None:
            self.connection = self.connect(self.host, timeout=120)
        if query:
            command, content_range = 'query', f'bytes */{self.total}'
        elif not data and finalise:
            command, content_range = 'finalize', f'bytes */{self.total}'
        else:
            command = 'upload, finalize' if finalise else 'upload'
            content_range = f'bytes {offset}-{offset + len(data) - 1}/{self.total}'
        headers = {'Content-Length': str(len(data)),
                   'Content-Type': 'application/vnd.android.package-archive',
                   'Content-Range': content_range,
                   'X-Goog-Upload-Offset': str(offset),
                   'X-Goog-Upload-Command': command,
                   'X-Goog-Upload-Total-Size': str(self.total)}
        self.connection.request('PUT', self.target, body=data, headers=headers)
        response = self.connection.getresponse()
        body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise DeliveryError('Drive upload receipt exceeded its safety limit')
        return response.status, dict(response.getheaders()), body

    def upload(self, path: Path):
        if path.stat().st_size != self.total or self.total <= 0:
            raise DeliveryError('Upload file size does not match the authorised session')
        offset, failures, stalled, query, last_progress = 0, 0, 0, True, 0
        try:
            with path.open('rb') as stream:
                while True:
                    stream.seek(offset)
                    data = b'' if query else stream.read(min(CHUNK, self.total - offset))
                    try:
                        reply = self.put(data, offset, query=query,
                                         finalise=not query and offset + len(data) == self.total)
                        state, received, receipt = acknowledge(*reply, self.total,
                                                               None if query else offset + len(data))
                    except (OSError, http.client.HTTPException, RetryUpload):
                        self.close()
                        failures += 1
                        if failures > 5:
                            raise DeliveryError('Upload interrupted repeatedly; session can be resumed') from None
                        self.sleep(min(2 ** (failures - 1), 8))
                        query = True
                        continue
                    failures = 0
                    if state == 'final':
                        return receipt
                    if received < offset:
                        raise DeliveryError('Refusing to rewind an acknowledged upload')
                    stalled = stalled + 1 if received == offset else 0
                    if stalled > 5:
                        raise DeliveryError('Drive upload stopped making progress')
                    offset, query = received, False
                    if offset - last_progress >= 32 * 1024 * 1024:
                        print(f'Transferred {offset // 1_000_000} / {self.total // 1_000_000} MB', flush=True)
                        last_progress = offset
        finally:
            self.close()


def gh_json(endpoint, *, method='GET', data=None):
    args = ['gh', 'api', '--method', method, endpoint]
    if data is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=None if data is None else json.dumps(data),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env={**os.environ, 'GH_DEBUG': ''}, timeout=90)
    if result.returncode:
        raise DeliveryError('Private GitHub metadata request failed')
    return json.loads(result.stdout)


def replace_private_body(repo, release_id, body):
    current = gh_json(f'repos/{repo}/releases/{release_id}')
    if current['draft'] is not True:
        raise DeliveryError('Refusing to store private handoff metadata on a public release')
    return gh_json(f'repos/{repo}/releases/{release_id}', method='PATCH', data={
        'draft': True, 'prerelease': True, 'name': current['name'],
        'tag_name': current['tag_name'], 'target_commitish': current['target_commitish'], 'body': body})


def download_asset(repo, asset_id, target: Path, expected_size, expected_sha):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    request = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/assets/{asset_id}',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/octet-stream', 'User-Agent': 'Terminator-private-Drive-delivery'})
    try:
        response = urllib.request.build_opener(NoRedirect).open(request, timeout=60)
    except urllib.error.HTTPError as response:
        if response.code not in (302, 303, 307):
            raise DeliveryError(f'Source asset request failed (HTTP {response.code})') from None
        url = response.headers['Location']
    else:
        response.close()
        raise DeliveryError('Expected a file-scoped source download redirect')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('release-assets.githubusercontent.com', 'objects.githubusercontent.com'):
        raise DeliveryError('Unexpected source asset download destination')
    sha, md5, count = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
    # This new request has no GitHub credential or Drive session header.
    with urllib.request.urlopen(url, timeout=120) as source, target.open('wb') as output:
        while chunk := source.read(1024 * 1024):
            count += len(chunk)
            if count > expected_size:
                raise DeliveryError('Source asset exceeded its expected length')
            output.write(chunk)
            sha.update(chunk); md5.update(chunk)
    if count != expected_size or sha.hexdigest() != expected_sha:
        raise DeliveryError('Source APK checksum or length mismatch; no bytes sent to Drive')
    return md5.hexdigest()


def main():
    repo, release_id = os.environ['GITHUB_REPOSITORY'], os.environ['EVALUATION_RELEASE_ID']
    release = gh_json(f'repos/{repo}/releases/{release_id}')
    if release['draft'] is not True:
        raise DeliveryError('Evaluation release must remain private')
    body = release.get('body') or ''
    matches = HANDOFF.findall(body)
    if len(matches) != 1:
        raise DeliveryError('Exactly one private Drive upload authorisation is required')
    payload = json.loads(matches[0])
    # Consume the one-file capability before a download or upload. It remains
    # only in process memory, never a workflow argument, public log or Git file.
    clean_body = HANDOFF.sub('', body).strip()
    replace_private_body(repo, release_id, clean_body)
    uri = payload['session_uri']
    validate_session(uri)
    print('::add-mask::' + uri, flush=True)
    for values in urllib.parse.parse_qs(urllib.parse.urlsplit(uri).query).values():
        for value in values:
            if len(value) > 20:
                print('::add-mask::' + value, flush=True)
    size, digest, name = payload['bytes'], payload['sha256'], payload['name']
    if not isinstance(size, int) or not 0 < size <= 2 * 1024 ** 3:
        raise DeliveryError('Invalid authorised APK length')
    if not re.fullmatch(r'[0-9a-f]{64}', digest) or not re.fullmatch(r'[A-Za-z0-9._-]+\.apk', name):
        raise DeliveryError('Invalid authorised APK identity')
    assets = [a for a in release['assets'] if a['id'] == payload['source_asset_id']]
    if (len(assets) != 1 or assets[0]['name'] != name or assets[0]['size'] != size
            or assets[0]['state'] != 'uploaded' or assets[0].get('digest') != 'sha256:' + digest):
        raise DeliveryError('Private source asset does not match the authorised APK')
    with tempfile.TemporaryDirectory(prefix='terminator-private-delivery-') as temporary:
        path = Path(temporary) / name
        md5 = download_asset(repo, payload['source_asset_id'], path, size, digest)
        print('Source APK SHA-256 and length verified; starting resumable Drive upload', flush=True)
        receipt = ResumableUpload(uri, size).upload(path)
    if receipt.get('size') is not None and int(receipt['size']) != size:
        raise DeliveryError('Drive final receipt length mismatch')
    if receipt.get('md5Checksum') is not None and receipt['md5Checksum'] != md5:
        raise DeliveryError('Drive final receipt checksum mismatch')
    result = {'completed': True, 'run_id': os.environ['GITHUB_RUN_ID'], 'name': name,
              'bytes': size, 'sha256': digest, 'md5': md5, 'drive_file_id': receipt.get('id')}
    current = gh_json(f'repos/{repo}/releases/{release_id}')
    latest_body = current.get('body') or ''
    if HANDOFF.search(latest_body):
        raise DeliveryError('Another delivery authorisation appeared; refusing to overwrite it')
    latest_body = RESULT.sub('', latest_body).strip()
    replace_private_body(repo, release_id, latest_body + '\n\n<!-- terminator-drive-result\n' + json.dumps(result) + '\n-->')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write('## Private Drive handoff completed\n\nThe existing signed APK was transferred without rebuilding or removing files. Source SHA-256 and length matched. Confirm the final file/checksum through the owner\'s Drive connector. No public sharing was enabled. Phone boot and full feature parity remain NOT_CERTIFIED.\n')
    print('Private single-file Drive transfer completed; verify using the connected Drive account', flush=True)


if __name__ == '__main__':
    try:
        main()
    except DeliveryError as error:
        print('Delivery failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Do not log exception representations that could contain scoped URLs.
        print('Delivery failed (' + type(error).__name__ + '); no private URL logged', file=sys.stderr)
        sys.exit(1)
