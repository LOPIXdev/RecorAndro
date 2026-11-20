"""Loopback HTTP boundaries and a disposable actual-core smoke run, not Android evidence."""
import hashlib
import http.client
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote
import zipfile

from recorandro.config import Config
from recorandro.mobile_ui import Server, MAX_UPLOAD
from recorandro.session_state import session_status
from test_normalization import make_wav
from test_visuals import png


class HTTPFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Config(Path(self.temp.name) / 'data')
        self.server = Server(self.config, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path='/state', method='GET', body=None, headers=None, auth=True):
        app = self.server.app
        h = {'Origin': self.server.origin}
        if auth:
            h.update(Cookie='recorandro=' + app.cookie)
            h['X-CSRF-Token'] = app.csrf
        h.update(headers or {})
        con = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=60)
        try:
            con.request(method, path, body=body, headers=h)
            r = con.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        finally:
            con.close()

    def start(self, data=b'RIFF', **headers):
        h = {'Content-Type': 'application/octet-stream', 'X-Job-ID': 'a' * 32,
             'X-Filename': 'short.wav', 'X-Budget': '60'}
        h.update(headers)
        return self.request('/start', 'POST', data, h)

    def wait_idle(self):
        until = time.monotonic() + 90
        while self.server.app.busy and time.monotonic() < until:
            time.sleep(.05)
        self.assertFalse(self.server.app.busy, 'worker did not finish')
        return json.loads(self.request()[2])


class SecurityTests(HTTPFixture):
    def test_batch_options_and_declared_boundaries(self):
        def setup(data):
            return {'X-Setup': quote(json.dumps(data))}
        for data in ({'archive': 'automatic'}, {'photos': [{'name': '../x.png', 'size': 1}]},
                     {'photos': [{'name': 'x.png', 'size': True}]},
                     {'photos': [{'name': 'x.png', 'size': 4}]}):
            self.assertIn(self.start(**setup(data))[0], (400, 413))
        self.assertFalse(self.server.app.jobs)
        with patch('recorandro.mobile_ui.process_audio') as process:
            def use_paths(config, path, **options):
                self.assertEqual(path.read_bytes(), b'RIFF')
                self.assertEqual([p.read_bytes() for p in options['photos']], [b'a', b'b'])
                self.assertEqual([p.name for p in options['photos']], ['x.png', 'x.png'])
                self.assertEqual((options['title'], options['course'], options['archive']), ('Title', 'Course', 'on'))
                return dict(session_id=None, optional_issues=[], error={'message': 'injected failure'})
            process.side_effect = use_paths
            data = {'archive': 'on', 'title': 'Title', 'course': 'Course',
                    'photos': [{'name': 'x.png', 'size': 1}] * 2}
            self.assertEqual(self.start(b'RIFFab', **setup(data))[0], 202)
            self.assertEqual(self.wait_idle()['message'], 'injected failure')
        self.assertFalse(list(self.config.data_root.rglob('x.png')))
        self.assertFalse(list(self.config.data_root.rglob('short.wav')))

    def test_lost_start_response_keeps_worker_reservation(self):
        from recorandro.mobile_ui import Handler
        entered, release = threading.Event(), threading.Event()
        reply = Handler.reply
        def lose_response(handler, value, code=200, cookie=False):
            if code == 202:
                raise BrokenPipeError()
            return reply(handler, value, code, cookie)
        def worker(*args, **kwargs):
            entered.set()
            release.wait(10)
            return dict(session_id=None, optional_issues=[], error={'message': 'injected failure'})
        with patch.object(Handler, 'reply', lose_response), \
                patch('recorandro.mobile_ui.process_audio', side_effect=worker) as process:
            try:
                with self.assertRaises(http.client.RemoteDisconnected):
                    self.start()
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.start(**{'X-Job-ID': 'b' * 32})[0], 409)
                process.assert_called_once()
            finally:
                release.set()
                self.wait_idle()
    def test_binding_auth_cookie_and_response_headers(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        self.assertEqual(self.request(auth=False)[0], 403)
        code, h, _ = self.request('/', auth=False)
        self.assertEqual(code, 200)
        self.assertNotIn('Access-Control-Allow-Origin', h)
        self.assertEqual(h['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", h['Content-Security-Policy'])
        self.assertEqual(self.request('/auth', 'POST', b'', auth=False)[0], 403)
        code, h, _ = self.request('/auth', 'POST', b'',
                                  {'X-Launch-Token': self.server.app.launch}, auth=False)
        self.assertEqual(code, 200)
        self.assertIn('HttpOnly; SameSite=Strict', h['Set-Cookie'])

    def test_foreign_origin_host_missing_origin_and_csrf(self):
        for headers in ({'Origin': 'https://foreign.invalid'}, {'Host': 'localhost:8765'},
                        {'Origin': 'null'}, {'X-CSRF-Token': 'bad'}, {'Origin': ''}):
            self.assertEqual(self.request('/stop', 'POST', b'', headers)[0], 403)
        self.assertEqual(self.request('/state', headers={'Origin': 'https://foreign.invalid'})[0], 403)

    def test_invalid_file_budget_and_upload_limit_no_job(self):
        for name in ('../x.wav', 'x%2fw.wav', '%00x.wav', 'x.flac', '.wav', 'x%5Cfoo.wav'):
            self.assertEqual(self.start(**{'X-Filename': name})[0], 400)
        for budget in ('0', '-1', 'NaN', '604801'):
            self.assertEqual(self.start(**{'X-Budget': budget})[0], 400)
        self.assertEqual(self.start(**{'Content-Length': str(MAX_UPLOAD + 1)})[0], 413)
        self.assertEqual(self.start(data=b'')[0], 413)
        self.assertEqual(self.start(**{'Transfer-Encoding': 'chunked'})[0], 411)
        self.assertFalse(self.server.app.jobs)

    def test_picker_cancellation_and_truncated_upload_never_import(self):
        with patch('recorandro.mobile_ui.process_audio') as process:
            self.request('/')  # Choosing/cancelling in the browser sends no start request.
            self.assertFalse(self.server.app.jobs)
            con = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
            con.putrequest('POST', '/start')
            for k, v in {'Origin': self.server.origin, 'Cookie': 'recorandro=' + self.server.app.cookie,
                         'X-CSRF-Token': self.server.app.csrf, 'Content-Length': '100',
                         'Content-Type': 'application/octet-stream', 'X-Job-ID': 'a' * 32,
                         'X-Filename': 'cancel.wav', 'X-Budget': '60'}.items():
                con.putheader(k, v)
            con.endheaders(b'RIFF')
            con.sock.shutdown(socket.SHUT_WR)
            response = con.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            con.close()
            self.assertEqual(self.wait_idle()['state'], 'failed')
            process.assert_not_called()
            self.assertFalse(list(self.config.data_root.rglob('cancel.wav')))

    def test_staging_space_denial(self):
        with patch('recorandro.mobile_ui.OwnedDirectory.free_bytes', return_value=1), \
                patch('recorandro.mobile_ui.process_audio') as process:
            self.assertEqual(self.start()[0], 409)
            process.assert_not_called()
            self.assertFalse(self.server.app.busy)

    def test_duplicate_start_single_worker_and_stop_busy(self):
        entered, release = threading.Event(), threading.Event()
        def process(*args, **kwargs):
            kwargs['on_import']('c' * 32)
            entered.set()
            release.wait(10)
            return dict(session_id=None, optional_issues=[], error={'message': 'injected failure'})
        with patch('recorandro.mobile_ui.process_audio', side_effect=process) as call:
            try:
                self.assertEqual(self.start()[0], 202)
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.start()[0], 200)
                self.assertEqual(self.start(**{'X-Job-ID': 'b' * 32})[0], 409)
                self.assertEqual(self.request('/stop', 'POST', b'')[0], 409)
                code, _, state = self.request()
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(state)['session_id'], 'c' * 32)
                self.assertEqual(call.call_count, 1)
            finally:
                release.set()
                self.wait_idle()

    def test_route_allowlist_and_safe_download_identifiers(self):
        for path in ('/download/../../secret', '/download/' + 'a' * 32,
                     '/state?file=secret', '/session.json'):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request('/exec', 'POST', b'')[0], 404)
        self.assertEqual(self.request('/open', 'POST', b'{"session_id":"../bad"}',
                                      {'Content-Type': 'application/json'})[0], 400)

    def test_reopen_resume_classification_and_worker(self):
        status = dict(session_id='a' * 32, current_state='imported', package_status={'status': 'not_generated'},
                      last_successful_state='imported', recovery={'classification': 'resumable'},
                      warnings=[], archive_status={'status': 'explicit_off'}, artifacts={})
        body = json.dumps({'session_id': 'a' * 32}).encode()
        with patch('recorandro.mobile_ui.session_status', return_value=status), \
                patch('recorandro.mobile_ui.recover_session', return_value={}) as resume:
            self.assertEqual(self.request('/open', 'POST', body, {'Content-Type': 'application/json'})[0], 200)
            resume.assert_not_called()
            self.assertEqual(self.request('/resume', 'POST', body, {'Content-Type': 'application/json'})[0], 200)
            self.wait_idle()
            resume.assert_called_once_with(self.config, 'a' * 32)
            status['recovery']['classification'] = 'failed_manual_attention'
            self.assertEqual(self.request('/resume', 'POST', body, {'Content-Type': 'application/json'})[0], 409)

    def test_optional_photo_failure_keeps_verified_parts_ready(self):
        sid = 'a' * 32
        status = dict(session_id=sid, current_state='packaged', package_status={'status': 'verified'},
                      last_successful_state='packaged', recovery={'classification': 'complete'},
                      warnings=[], archive_status={'status': 'explicit_off'},
                      artifacts={'part': dict(type='zip_package', status='verified',
                                              relative_path='part_01.zip', size_bytes=1)})
        result = dict(session_id=sid, optional_issues=[{'stage': 'photos', 'message': 'Photo intake failed'}])
        with patch('recorandro.mobile_ui.process_audio', return_value=result), \
                patch('recorandro.mobile_ui.session_status', return_value=status):
            self.assertEqual(self.start()[0], 202)
            state = self.wait_idle()
        self.assertEqual(state['state'], 'packaged')
        self.assertEqual(state['optional_issues'], result['optional_issues'])
        self.assertEqual(len(state['parts']), 1)

    def test_failed_lookup_preserves_verified_session_and_resume(self):
        sid = 'a' * 32
        status = dict(session_id=sid, current_state='imported', package_status={'status': 'not_generated'},
                      last_successful_state='imported', recovery={'classification': 'resumable'},
                      warnings=[], archive_status={'status': 'explicit_off'}, artifacts={})
        headers = {'Content-Type': 'application/json'}
        with patch('recorandro.mobile_ui.session_status', side_effect=[status, OSError('Session missing')]):
            self.assertEqual(self.request('/open', 'POST', json.dumps({'session_id': sid}), headers)[0], 200)
            self.assertEqual(self.request('/open', 'POST', json.dumps({'session_id': 'b' * 32}), headers)[0], 409)
        current = json.loads(self.request()[2])
        self.assertEqual(current['session_id'], sid)
        self.assertEqual(current['recovery']['classification'], 'resumable')

    def test_stop_idle(self):
        self.assertEqual(self.request('/stop', 'POST', b'')[0], 200)


@unittest.skipUnless(shutil.which('node'), 'Node required for client-controller check')
class BrowserControllerTests(unittest.TestCase):
    def test_selection_cancel_validation_and_error_remains_visible(self):
        script = (Path(__file__).parents[1] / 'recorandro/mobile_web/app.js').read_text()
        harness = r'''
const assert = require('node:assert/strict');
const nodes = {};
const node = () => ({files: [], value: '60', textContent: '', disabled: true, dataset: {},
  children: [], replaceChildren(...children) {this.children = children;},
  append(...children) {this.children.push(...children);}, setAttribute() {}, focus() {},
  click() {this.clicked = true;}});
global.document = {getElementById: id => nodes[id] ||= node(), createElement: node};
global.location = {hash: ''}; global.history = {replaceState() {}};
global.sessionStorage = {getItem() {return null;}, setItem() {}};
global.setInterval = () => {};
const calls = [];
const requests = [];
global.fetch = async (path, options) => {
  calls.push(path);
  requests.push(options);
  return {ok: path !== '/start', json: async () => path === '/start' ?
    {error: 'Provider read denied'} : {state: 'select', parts: [], csrf: 'token'}};
};
'''
        checks = r'''
(async () => {
  await new Promise(setImmediate);
  el('choose-audio').onclick(); el('choose-photos').onclick();
  assert.equal(el('audio').clicked, true);
  assert.equal(el('photos').clicked, true);
  await el('start').onclick();
  assert.match(el('notice').textContent, /Select one/);
  assert.equal(calls.filter(x => x === '/start').length, 0);
  el('audio').files = [{name: 'sample.wav', size: 20}];
  el('audio').onchange();
  assert.equal(el('audio-name').textContent, 'sample.wav');
  el('budget').value = '0'; await el('start').onclick();
  assert.match(el('notice').textContent, /1..604800/);
  el('budget').value = '60'; await el('start').onclick();
  assert.equal(calls.filter(x => x === '/start').length, 1);
  assert.equal(JSON.parse(decodeURIComponent(requests[calls.lastIndexOf('/start')].headers['X-Setup'])).archive, 'off');
  await poll();
  assert.match(el('notice').textContent, /Provider read denied/);
  assert.equal(el('setup').hidden, false);
  render({state: 'processing', busy: true, session_id: 'a'.repeat(32), milestone: 'imported'});
  assert.equal(el('status').hidden, false);
  assert.equal(el('milestone').textContent, 'imported');
  assert.equal(el('ready').hidden, true);
  el('photos').files = [{name: 'image.jpg', size: 9}];
  el('photos').onchange();
  assert.match(el('photo-names').textContent, /image.jpg/);
  el('archive').checked = true;
  el('archive').onchange();
  assert.match(el('settings-summary').textContent, /Archive on/);
  render({state: 'select'});
  await el('start').onclick();
  const setup = JSON.parse(decodeURIComponent(requests[calls.lastIndexOf('/start')].headers['X-Setup']));
  assert.equal(setup.archive, 'on');
  assert.deepEqual(setup.photos, [{name: 'image.jpg', size: 9}]);
  render({state: 'failed', recovery: {classification: 'failed_retryable', next_stage: 'package_generation'},
          session_id: 'a'.repeat(32)});
  assert.equal(el('resume').hidden, false);
  assert.match(el('activity').textContent, /Retry available/);
  await el('resume').onclick();
  assert.equal(JSON.parse(requests[calls.lastIndexOf('/resume')].body).session_id, 'a'.repeat(32));
  render({state: 'packaged', parts: [{number: 1, name: 'part_01.zip', size_bytes: 20,
    duration_seconds: 5, range_seconds: [8, 13], download: '/download/part'}],
    archive: {name: 'full_archive.zip', size_bytes: 30, download: '/download/archive'}});
  assert.equal(el('ready').hidden, false);
  assert.equal(el('status').hidden, true);
  assert.equal(el('parts').children[0].children[0].children[2].textContent, 'Source 0:08–0:13');
  assert.equal(el('parts').children[0].children[1].href, '/download/part');
  assert.equal(el('archive-download').children[0].children[1].href, '/download/archive');
  assert.equal(el('archive-output').hidden, false);
  connected = false;
  render();
  assert.equal(el('ready').hidden, true);
  assert.equal(el('archive-output').hidden, true);
  assert.equal(calls.filter(x => x === '/start').length, 2);
})().catch(e => { console.error(e); process.exitCode = 1; });
'''
        run = subprocess.run(['node', '-e', harness + script + checks], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Real media tools required')
class ActualMediaTests(HTTPFixture):
    def test_photos_and_explicit_archive_are_verified(self):
        source = Path(self.temp.name) / 'short.wav'
        make_wav(source, seconds=1, amplitude=.1)
        photo = png()
        setup = quote(json.dumps({'archive': 'on', 'photos': [{'name': 'slide.png', 'size': len(photo)}],
                                  'title': 'Disposable sample', 'course': 'Test'}))
        self.assertEqual(self.start(source.read_bytes() + photo, **{'X-Setup': setup})[0], 202)
        state = self.wait_idle()
        self.assertEqual(state['state'], 'packaged', state)
        self.assertEqual(state['visual_count'], 1)
        self.assertEqual(state['archive_status'], 'archived')
        self.assertEqual(state['parts'][0]['number'], 1)
        self.assertGreater(state['parts'][0]['duration_seconds'], 0)
        self.assertEqual(state['parts'][0]['range_seconds'], [0, 1])
        self.assertEqual(self.request(state['archive']['download'], auth=False)[0], 403)
        archive_code, _, archive = self.request(state['archive']['download'])
        self.assertEqual(archive_code, 200)
        with zipfile.ZipFile(io.BytesIO(archive)) as full:
            self.assertIsNone(full.testzip())
            names = [n for n in full.namelist() if n.startswith('originals/photos/')]
            self.assertEqual(len(names), 1)
            self.assertEqual(full.read(names[0]), photo)
        with zipfile.ZipFile(io.BytesIO(self.request(state['parts'][0]['download'])[2])) as part:
            self.assertEqual(len(part.namelist()), 3)
            self.assertFalse(any('photo' in name for name in part.namelist()))
        status = session_status(self.config, state['session_id'])
        archive_entry = next(e for e in status['artifacts'].values() if e['type'] == 'full_archive')
        path = self.config.data_root / 'sessions' / state['session_id'] / archive_entry['relative_path']
        path.write_bytes(b'corrupt')
        self.assertEqual(self.request(state['archive']['download'])[0], 409)
        current = json.loads(self.request()[2])
        self.assertEqual(current['state'], 'packaged')
        self.assertIsNone(current['archive'])
        self.assertEqual(self.request(current['parts'][0]['download'])[0], 200)

    def test_upload_process_download_corruption_resume(self):
        source = Path(self.temp.name) / 'short.wav'
        make_wav(source, seconds=1, amplitude=.1)
        original = source.read_bytes()
        self.assertEqual(self.start(original)[0], 202)
        state = self.wait_idle()
        self.assertEqual(state['state'], 'packaged', state)
        self.assertEqual(len(state['parts']), 1)
        self.assertEqual(state['archive_status'], 'explicit_off')
        self.assertIsNone(state['archive'])
        sid = state['session_id']
        status = session_status(self.config, sid)
        self.assertEqual(status['audio']['sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(status['visual_count'], 0)
        url = state['parts'][0]['download']
        self.assertEqual(self.request(url, auth=False)[0], 403)
        code, headers, blob = self.request(url)
        self.assertEqual(code, 200)
        self.assertEqual(headers['Content-Type'], 'application/zip')
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), 3)
        part = next(e for e in status['artifacts'].values() if e['type'] == 'zip_package')
        target = self.config.data_root / 'sessions' / sid / part['relative_path']
        self.assertEqual(blob, target.read_bytes())
        target.write_bytes(b'corrupted')
        self.assertEqual(self.request(url)[0], 409)  # Existence alone never permits delivery.
        current = json.loads(self.request()[2])
        self.assertEqual(current['session_id'], sid)
        self.assertNotEqual(current['state'], 'packaged')
        self.assertEqual(current['parts'], [])
        self.assertEqual(current['recovery']['classification'], 'failed_retryable')
        body = json.dumps({'session_id': sid}).encode()
        self.assertEqual(self.request('/open', 'POST', body, {'Content-Type': 'application/json'})[0], 200)
        self.assertEqual(json.loads(self.request()[2])['parts'], [])
        self.assertEqual(self.request('/resume', 'POST', body, {'Content-Type': 'application/json'})[0], 200)
        final = self.wait_idle()
        self.assertEqual(final['state'], 'packaged', final)
        self.assertEqual(self.request(final['parts'][0]['download'])[2], blob)
