"""Foreground loopback UI. Media and canonical state stay in the core."""
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
from .sessions import AUDIO_SUFFIXES
from .visuals import SUFFIXES as PHOTO_SUFFIXES

ID = re.compile(r'[0-9a-f]{32}\Z')
MAX_UPLOAD = 128 * MIB
MAX_PHOTOS = 8
MAX_PHOTO = 16 * MIB
MAX_BATCH = 192 * MIB
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


def file_name(name, suffixes):
    if (not isinstance(name, str) or not name or len(name.encode('utf-8')) > 240
            or name.startswith('.') or any(c in name for c in '/\\:<>"|?*')
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or Path(name).suffix.lower() not in suffixes):
        raise Rejected('Invalid file name or suffix.')
    return name


def upload_setup(header, total):
    setup = json.loads(unquote(header, errors='strict')) if header else {}
    if not isinstance(setup, dict) or set(setup) - {'photos', 'archive', 'title', 'course'}:
        raise Rejected('Invalid recording setup.')
    photos = setup.get('photos', [])
    if not isinstance(photos, list) or len(photos) > MAX_PHOTOS:
        raise Rejected('Select up to eight photos.')
    files = []
    for photo in photos:
        if not isinstance(photo, dict) or set(photo) != {'name', 'size'}:
            raise Rejected('Invalid photo selection.')
        size = photo['size']
        if type(size) is not int or not 0 < size <= MAX_PHOTO:
            raise Rejected('Photos must be nonempty and at most 16 MiB each.', 413)
        files.append((file_name(photo['name'], PHOTO_SUFFIXES), size))
    audio_size = total - sum(size for _, size in files)
    if not 0 < audio_size <= MAX_UPLOAD:
        raise Rejected('Audio must be nonempty and at most 128 MiB.', 413)
    archive = setup.get('archive', 'off')
    if archive not in ('on', 'off'):
        raise Rejected('Choose Full Archive ON or OFF.')
    options = {'archive': archive}
    for key in ('title', 'course'):
        value = setup.get(key, '')
        if (not isinstance(value, str) or len(value) > 120 or
                any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
            raise Rejected('Title and course must be at most 120 characters of text.')
        options[key] = value.strip() or None
    return audio_size, files, options


class App:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.busy = False
        self.stopping = False
        self.jobs = set()
        self.current = dict(state='select', session_id=None, parts=[])
        self.downloads = {}
        self.launch = secrets.token_urlsafe(32)
        self.cookie = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)

    def snapshot(self):
        with self.lock:
            return dict(copy.deepcopy(self.current), csrf=self.csrf, busy=self.busy)

    def idle(self):
        if self.stopping:
            raise Rejected('Adapter is stopping.', 409)
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
            self.jobs.add(job_id)
            self.downloads.clear()
            return True

    def imported(self, sid):
        with self.lock:
            self.current.update(session_id=sid, state='processing',
                                milestone='imported', message='Running the processing workflow.')
        # Survives browser/adapter loss in the owner's foreground terminal.
        print('Verified imported session:', sid, flush=True)

    def publish(self, status, outcome=None):
        self.downloads.clear()
        ready = status['current_state'] == 'packaged' and status['package_status']['status'] == 'verified'
        parts, archive = [], None
        if ready:
            durations = {int(aid.rsplit(':', 1)[-1]): (entry.get('media') or {}).get('duration_seconds')
                         for aid, entry in status['artifacts'].items()
                         if entry['type'] == 'audio_part' and entry['status'] == 'verified'}
            for aid, entry in sorted(status['artifacts'].items()):
                if entry['status'] != 'verified':
                    continue
                name = Path(entry['relative_path']).name
                part = re.fullmatch(r'part_([0-9]+)\.zip', name)
                kind = entry['type']
                is_part = kind == 'zip_package' and part
                is_archive = kind == 'full_archive' and status['archive_status']['status'] == 'archived'
                if is_part or is_archive:
                    token = secrets.token_hex(16)
                    self.downloads[token] = (status['session_id'], aid, kind)
                    item = dict(name=name, size_bytes=entry['size_bytes'], download='/download/' + token)
                    if is_part:
                        number = int(part[1])
                        parts.append(dict(item, number=number, duration_seconds=durations.get(number)))
                    else:
                        archive = item
        recovery = status['recovery']
        state = 'status'
        if ready and parts and outcome is None:
            state = 'packaged'
        elif outcome:
            state = outcome
        elif status['current_state'] == 'failed' or recovery['classification'].startswith('failed_'):
            state = 'failed'
        elif status.get('active_stage'):
            state = 'interrupted'
        if state != 'packaged':
            self.downloads.clear()
            parts, archive = [], None
        self.current.update(state=state,
                            session_id=status['session_id'], parts=parts,
                            milestone=status['last_successful_state'], recovery=recovery,
                            warnings=status['warnings'], archive=archive,
                            archive_status=status['archive_status']['status'],
                            visual_count=status.get('visual_count', 0), visual_status=status.get('visual_status'),
                            errors=status.get('errors', []))

    def fail(self, exc, release=True):
        with self.lock:
            state = 'busy' if getattr(exc, 'code', None) == 'inspection_busy' else 'failed'
            if isinstance(exc, KeyboardInterrupt):
                state = 'interrupted'
            self.current.update(state=state, message=str(exc) or type(exc).__name__)
            if release:
                self.busy = False

    def run(self, path=None, options=None, staging=None):
        try:
            outcome = None
            if path is not None:
                result = process_audio(self.config, path, provision_seconds=self.current['budget'],
                                       on_import=self.imported, **options)
                error = result.get('error', {})
                if error:
                    outcome = {'interrupted': 'interrupted', 'inspection_busy': 'busy'}.get(error.get('code'), 'failed')
                with self.lock:
                    self.current.update(session_id=result['session_id'] or self.current['session_id'],
                                        message=error.get('message', ''),
                                        optional_issues=result['optional_issues'])
                sid = self.current['session_id']
            else:
                sid = self.current['session_id']
                result = recover_session(self.config, sid)
                with self.lock:
                    self.current['message'] = result.get('error_message') or ''
            if sid:
                status = session_status(self.config, sid)
                with self.lock:
                    self.publish(status, outcome)
            else:
                raise Rejected(self.current.get('message') or 'Import incomplete; reselect source.')
        except (Exception, KeyboardInterrupt) as exc:
            self.fail(exc, release=False)
        finally:
            try:
                if staging is not None:
                    staging.close()
            except OSError:
                with self.lock:
                    self.current['cleanup_warning'] = 'A temporary upload copy could not be removed.'
            finally:
                with self.lock:
                    self.busy = False

    def open_session(self, sid, resume=False):
        identifier(sid)
        with self.lock:
            self.idle()
            # A mistyped or temporarily busy lookup must preserve the open session.
            try:
                status = session_status(self.config, sid)
            except (ValueError, OSError) as exc:
                raise Rejected(str(exc) or 'Cannot open that session.', 409) from exc
            self.current = dict(session_id=sid, parts=[], message='')
            self.publish(status)
            if resume:
                if status['recovery']['classification'] not in ('resumable', 'failed_retryable'):
                    raise Rejected('Recovery does not permit resume; inspect current status.', 409)
                self.busy = True
                self.current.update(state='processing', message='Resuming verified pipeline.')
                threading.Thread(target=self.run, daemon=True).start()

    def refresh_download_status(self, sid):
        """Withdraw links after a download detects evidence that changed."""
        try:
            status = session_status(self.config, sid)
        except (ValueError, OSError) as exc:
            self.downloads.clear()
            self.current.update(parts=[], archive=None)
            self.fail(exc)
        else:
            self.current['message'] = 'Package evidence changed. Review the current session status.'
            self.publish(status)


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
        if (self.headers.get('Transfer-Encoding') or len(lengths) != 1 or
                not re.fullmatch(r'[0-9]{1,10}', lengths[0])):
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
        with app.lock:
            app.idle()
            if token not in app.downloads:
                raise Rejected('Unknown or expired artifact.', 404)
            sid, aid, kind = app.downloads[token]
            try:
                self.verified_download(sid, aid, kind)
            except (ValueError, OSError) as exc:
                if getattr(exc, 'code', None) != 'inspection_busy':
                    app.refresh_download_status(sid)
                raise

    def verified_download(self, sid, aid, kind):
        with ExitStack() as stack:
            app = self.server.app
            directory, record = _context(stack, app.config, sid, None)
            view = project_session(directory, record)
            entry = view['artifact_registry'].get(aid)
            if (view['current_state'] != 'packaged' or view['package_status']['status'] != 'verified'
                    or not entry or entry['type'] != kind or entry['status'] != 'verified'
                    or (kind == 'full_archive' and view['archive_status']['status'] != 'archived')):
                raise Rejected('Package no longer verifies; reopen session.', 409)
            folder, leaf = _folder(stack, directory, entry['relative_path'])
            stream = stack.enter_context(os.fdopen(folder.open(leaf, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)), 'rb'))
            _verify(stream, folder, leaf, entry)
            stream.seek(0)
            self.headers_out('application/zip', entry['size_bytes'])
            name = leaf if re.fullmatch(r'(part_[0-9]+|full_archive)\.zip', leaf) else 'package.zip'
            self.send_header('Content-Disposition', 'attachment; filename="' + name + '"')
            try:
                self.end_headers()
                while block := stream.read(65536):
                    self.wfile.write(block)
            except OSError:
                self.close_connection = True

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
                body = self.rfile.read(size)
                if len(body) != size:
                    raise Rejected('Incomplete session request.')
                value = json.loads(body)
                if not isinstance(value, dict) or set(value) != {'session_id'}:
                    raise Rejected('Only a session_id is accepted.')
                self.server.app.open_session(value['session_id'], self.path == '/resume')
                self.reply(self.server.app.snapshot())
            elif self.path == '/stop':
                self.length(0, allow_empty=True)
                with self.server.app.lock:
                    self.server.app.idle()
                    self.server.app.stopping = True
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    self.reply({'state': 'stopped', 'message': 'Restart in Termux for a new private URL.'})
            else:
                raise Rejected('Unknown action.', 404)
        except (ValueError, OSError, CookieError) as exc:
            self.reply({'error': str(exc)}, error_status(exc))

    def upload(self):
        app = self.server.app
        size = self.length(MAX_BATCH)
        if self.headers.get('Content-Type') != 'application/octet-stream':
            raise Rejected('Upload one raw audio file.')
        name = file_name(unquote(self.headers.get('X-Filename', ''), errors='strict'), AUDIO_SUFFIXES)
        audio_size, photos, options = upload_setup(self.headers.get('X-Setup', ''), size)
        budget = self.headers.get('X-Budget', '')
        if not re.fullmatch(r'[0-9]{1,6}', budget) or not 1 <= int(budget) <= 604800:
            raise Rejected('Duration budget must be 1..604800 seconds, not a measurement.')
        job_id = self.headers.get('X-Job-ID', '')
        if not app.reserve(job_id):
            self.reply({'duplicate': True, 'job_id': job_id}, 200)
            return  # Close connection without consuming/replaying the duplicate body.
        try:
            with ExitStack() as stack:
                root = stack.enter_context(OwnedDirectory.root(app.config.data_root))
                parent = stack.enter_context(root.child('mobile-staging'))
                folder = stack.enter_context(parent.child(secrets.token_hex(16), exclusive=True))
                if folder.free_bytes() < size + 256 * MIB:
                    raise Rejected('Insufficient staging space; no import started.', 409)
                paths = []
                for index, (leaf, remaining) in enumerate([(name, audio_size), *photos]):
                    item = stack.enter_context(folder.child(str(index), exclusive=True))
                    fd = item.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                    stack.callback(item.unlink, leaf)
                    with os.fdopen(fd, 'wb') as target:
                        while remaining:
                            if item.free_bytes() < min(remaining, 65536) + 256 * MIB:
                                raise Rejected('Staging storage exhausted; no import started.', 409)
                            block = self.rfile.read(min(remaining, 65536))
                            if not block:
                                raise Rejected('Upload cancelled/incomplete; no import started.')
                            target.write(block)
                            remaining -= len(block)
                        target.flush()
                        os.fsync(target.fileno())
                    paths.append(item.path / leaf)
                with app.lock:
                    app.current.update(state='processing', budget=int(budget),
                                       message='Importing selected recording; no audio capture is performed.')
                staging = stack.pop_all()
                try:
                    options['photos'] = paths[1:]
                    threading.Thread(target=app.run, args=(paths[0], options, staging), daemon=True).start()
                except Exception:
                    staging.close()
                    raise
        except (Exception, KeyboardInterrupt) as exc:
            app.fail(exc)
            raise
        # If the browser has gone away, the worker still owns this reservation.
        try:
            self.reply({'accepted': True, 'job_id': job_id}, 202)
        except OSError:
            self.close_connection = True


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
