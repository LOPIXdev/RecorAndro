"""Foreground loopback feasibility UI. Media and canonical state stay in the core."""
import argparse
from contextlib import ExitStack
import copy
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
from urllib.parse import unquote

from .config import load_config
from .workflow import process_audio
from .recovery import recover_session
from .session_state import session_status, project_session, _folder
from .packages import _context
from .inspection import _verify
from .storage import OwnedDirectory, MIB

ID = re.compile(r'[0-9a-f]{32}\Z')
MAX_UPLOAD = 128 * MIB
ASSETS = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
          '/style.css': ('style.css', 'text/css')}


class Rejected(ValueError):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise Rejected('Use a 32-character session/job identifier.')
    return value


def matches(value, expected):
    return secrets.compare_digest(value.encode('utf-8'), expected.encode('utf-8'))


def error_status(exc):
    return exc.code if isinstance(exc, Rejected) else 409


class App:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.busy = False
        self.jobs = {}
        self.current = dict(state='select', session_id=None, parts=[])
        self.downloads = {}
        self.launch = secrets.token_urlsafe(32)
        self.cookie = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)

    def snapshot(self):
        with self.lock:
            return dict(copy.deepcopy(self.current), csrf=self.csrf)

    def idle(self):
        if self.busy:
            raise Rejected('A job is active. Wait; do not start another import.', 409)

    def reserve(self, job_id):
        identifier(job_id)
        with self.lock:
            if job_id in self.jobs:
                return False
            self.idle()
            if len(self.jobs) >= 64:
                raise Rejected('Launch job limit reached. Stop and restart.', 409)
            self.busy = True
            self.current = dict(state='uploading', job_id=job_id, session_id=None, parts=[])
            self.jobs[job_id] = self.current
            self.downloads.clear()
            return True

    def imported(self, sid):
        with self.lock:
            self.current.update(session_id=sid, state='processing',
                                message='Resuming verified pipeline; no live percentage is available.')
        # Survives browser/adapter loss in the owner's foreground terminal.
        print('Verified imported session:', sid, flush=True)

    def publish(self, status):
        self.downloads.clear()
        ready = status['current_state'] == 'packaged' and status['package_status']['status'] == 'verified'
        parts = []
        if ready:
            for aid, entry in sorted(status['artifacts'].items()):
                if entry['type'] == 'zip_package' and entry['status'] == 'verified':
                    token = secrets.token_hex(16)
                    self.downloads[token] = (status['session_id'], aid)
                    parts.append(dict(name=Path(entry['relative_path']).name,
                                      size_bytes=entry['size_bytes'], download='/download/' + token))
        self.current.update(state='packaged' if ready and parts else 'status',
                            session_id=status['session_id'], parts=parts,
                            milestone=status['last_successful_state'], recovery=status['recovery'],
                            warnings=status['warnings'], archive_status=status['archive_status'],
                            errors=status.get('errors', []))

    def fail(self, exc, release=True):
        with self.lock:
            self.current.update(state='failed', message=str(exc) or type(exc).__name__)
            if release:
                self.busy = False

    def run(self, path=None):
        try:
            if path is not None:
                result = process_audio(self.config, path, provision_seconds=self.current['budget'],
                                       on_import=self.imported)
                with self.lock:
                    self.current.update(session_id=result['session_id'],
                                        message=result.get('error', {}).get('message', ''),
                                        optional_issues=result['optional_issues'])
                sid = result['session_id']
            else:
                sid = self.current['session_id']
                result = recover_session(self.config, sid)
                with self.lock:
                    self.current['message'] = result.get('error_message') or ''
            if sid:
                status = session_status(self.config, sid)
                with self.lock:
                    self.publish(status)
            else:
                raise Rejected(self.current.get('message') or 'Import incomplete; reselect source.')
        except (Exception, KeyboardInterrupt) as exc:
            self.fail(exc, release=False)
        finally:
            with self.lock:
                self.busy = False

    def open_session(self, sid, resume=False):
        identifier(sid)
        with self.lock:
            self.idle()
            status = session_status(self.config, sid)
            self.current = dict(session_id=sid, parts=[], message='')
            self.publish(status)
            if resume:
                if status['recovery']['classification'] not in ('resumable', 'failed_retryable'):
                    raise Rejected('Recovery does not permit resume; inspect current status.', 409)
                self.busy = True
                self.current.update(state='processing', message='Resuming verified pipeline.')
                threading.Thread(target=self.run, daemon=True).start()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, config, port=8765):
        self.app = App(config)
        self.slots = threading.BoundedSemaphore(4)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)
        def expire():
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.deadline = threading.Timer(180, expire)
        self.deadline.daemon = True
        self.deadline.start()

    def finish(self):
        self.deadline.cancel()
        super().finish()

    def log_message(self, *args):
        pass  # No request paths, credentials or private names in logs.

    def reply(self, value, code=200, cookie=False):
        self.send_blob(json.dumps(value, ensure_ascii=True).encode(), 'application/json', code, cookie)

    def headers_out(self, kind, size, code=200, cookie=False):
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', 'recorandro=' + self.server.app.cookie + '; HttpOnly; SameSite=Strict; Path=/')

    def send_blob(self, blob, kind, code=200, cookie=False):
        self.headers_out(kind, len(blob), code, cookie)
        self.end_headers()
        self.wfile.write(blob)

    def guard(self, mutation=False):
        if (self.headers.get_all('Host') != [self.server.origin[7:]] or
                sum(len(k) + len(v) for k, v in self.headers.items()) > 16384):
            raise Rejected('Invalid Host or oversized headers.', 403)
        origin = self.headers.get('Origin')
        if (len(self.headers.get_all('Origin', [])) > 1 or
                (mutation and origin != self.server.origin) or (origin and origin != self.server.origin)):
            raise Rejected('Foreign or missing Origin.', 403)
        if self.path in ASSETS and not mutation:
            return
        if self.path == '/auth' and mutation:
            if not matches(self.headers.get('X-Launch-Token', ''), self.server.app.launch):
                raise Rejected('Open the private URL printed by this launch.', 403)
            return
        cookies = SimpleCookie(self.headers.get('Cookie', ''))
        value = cookies.get('recorandro')
        if not value or not matches(value.value, self.server.app.cookie):
            raise Rejected('Authentication required. Open the private launch URL.', 403)
        if mutation and not matches(self.headers.get('X-CSRF-Token', ''), self.server.app.csrf):
            raise Rejected('CSRF token required.', 403)

    def length(self, limit, allow_empty=False):
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not lengths[0].isdigit():
            raise Rejected('A single Content-Length is required.', 411)
        size = int(lengths[0])
        if size > limit or (not allow_empty and size == 0):
            raise Rejected('Empty or oversized request.', 413)
        return size

    def do_GET(self):
        try:
            self.guard()
            if self.path in ASSETS:
                name, kind = ASSETS[self.path]
                self.send_blob((Path(__file__).parent / 'mobile_web' / name).read_bytes(), kind)
            elif self.path == '/state':
                self.reply(self.server.app.snapshot())
            elif re.fullmatch(r'/download/[0-9a-f]{32}', self.path):
                self.download(self.path.rsplit('/', 1)[1])
            else:
                raise Rejected('Unknown route.', 404)
        except (ValueError, OSError, CookieError) as exc:
            self.reply({'error': str(exc)}, error_status(exc))

    def download(self, token):
        app = self.server.app
        with app.lock, ExitStack() as stack:
            app.idle()
            if token not in app.downloads:
                raise Rejected('Unknown or expired artifact.', 404)
            sid, aid = app.downloads[token]
            directory, record = _context(stack, app.config, sid, None)
            view = project_session(directory, record)
            entry = view['artifact_registry'].get(aid)
            if (view['current_state'] != 'packaged' or view['package_status']['status'] != 'verified'
                    or not entry or entry['type'] != 'zip_package' or entry['status'] != 'verified'):
                raise Rejected('Package no longer verifies; reopen session.', 409)
            folder, leaf = _folder(stack, directory, entry['relative_path'])
            stream = stack.enter_context(os.fdopen(folder.open(leaf, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)), 'rb'))
            _verify(stream, folder, leaf, entry)
            stream.seek(0)
            self.headers_out('application/zip', entry['size_bytes'])
            name = leaf if re.fullmatch(r'part_[0-9]+\.zip', leaf) else 'part.zip'
            self.send_header('Content-Disposition', 'attachment; filename="' + name + '"')
            self.end_headers()
            while True:
                block = stream.read(65536)
                if not block:
                    break
                self.wfile.write(block)

    def do_POST(self):
        try:
            self.guard(mutation=True)
            if self.path == '/auth':
                self.length(0, allow_empty=True)
                self.reply(self.server.app.snapshot(), cookie=True)
            elif self.path == '/start':
                self.upload()
            elif self.path in ('/open', '/resume'):
                if self.headers.get('Content-Type') != 'application/json':
                    raise Rejected('JSON required.')
                size = self.length(256)
                value = json.loads(self.rfile.read(size))
                if not isinstance(value, dict) or set(value) != {'session_id'}:
                    raise Rejected('Only a session_id is accepted.')
                self.server.app.open_session(value['session_id'], self.path == '/resume')
                self.reply(self.server.app.snapshot())
            elif self.path == '/stop':
                self.length(0, allow_empty=True)
                with self.server.app.lock:
                    self.server.app.idle()
                    self.reply({'state': 'stopped', 'message': 'Restart in Termux for a new private URL.'})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                raise Rejected('Unknown action.', 404)
        except (ValueError, OSError, CookieError) as exc:
            self.reply({'error': str(exc)}, error_status(exc))

    def upload(self):
        app = self.server.app
        size = self.length(MAX_UPLOAD)
        if self.headers.get('Content-Type') != 'application/octet-stream':
            raise Rejected('Upload one raw audio file.')
        name = unquote(self.headers.get('X-Filename', ''), errors='strict')
        if (not name or len(name.encode('utf-8')) > 240 or name.startswith('.') or
                any(c in name for c in '/\\:') or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or Path(name).suffix.lower() not in ('.m4a', '.mp3', '.wav', '.aac')):
            raise Rejected('Invalid audio filename or suffix.')
        budget = self.headers.get('X-Budget', '')
        if not budget.isascii() or not budget.isdigit() or not 1 <= int(budget) <= 604800:
            raise Rejected('Duration budget must be 1..604800 seconds, not a measurement.')
        job_id = self.headers.get('X-Job-ID', '')
        if not app.reserve(job_id):
            self.reply({'duplicate': True, 'job_id': job_id}, 200)
            return  # Close connection without consuming/replaying the duplicate body.
        try:
            with ExitStack() as stack:
                root = stack.enter_context(OwnedDirectory.root(app.config.data_root))
                parent = stack.enter_context(root.child('mobile-staging'))
                folder = stack.enter_context(parent.child(job_id, exclusive=True))
                if folder.free_bytes() < size + 256 * MIB:
                    raise Rejected('Insufficient staging space; no import started.', 409)
                try:
                    with os.fdopen(folder.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'wb') as target:
                        remaining = size
                        while remaining:
                            if folder.free_bytes() < min(remaining, 65536) + 256 * MIB:
                                raise Rejected('Staging storage exhausted; no import started.', 409)
                            block = self.rfile.read(min(remaining, 65536))
                            if not block:
                                raise Rejected('Upload cancelled/incomplete; no import started.')
                            target.write(block)
                            remaining -= len(block)
                        target.flush()
                        os.fsync(target.fileno())
                except BaseException:
                    folder.unlink(name)
                    raise
                with app.lock:
                    app.current.update(state='processing', budget=int(budget),
                                       message='Importing selected recording; no audio capture is performed.')
                threading.Thread(target=app.run, args=(folder.path / name,), daemon=True).start()
            self.reply({'accepted': True, 'job_id': job_id}, 202)
        except (Exception, KeyboardInterrupt) as exc:
            app.fail(exc)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    server = Server(load_config(args.config), args.port)
    print('Open privately on this phone:', server.origin + '/#' + server.app.launch, flush=True)
    print('Foreground only. Stop waits for an idle job. Keep session IDs to reopen after restart.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Adapter interrupted. Restart and reopen the retained session ID; do not repeat import.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
