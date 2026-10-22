"""Optional intake, zero-photo compatibility and archive revision integration."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile
import subprocess
import shutil

from recorandro.config import Config
from recorandro.sessions import import_audio
from recorandro.session_state import session_status
from recorandro.storage import OwnedDirectory, StorageError
from recorandro.visuals import import_photos, metadata
from recorandro.manifests import generate_manifests
from recorandro.packages import package_session, archive_session
from test_normalization import make_wav
from test_exports import ExportFixture


def png():
    import zlib
    def chunk(name, data):
        return struct.pack('>I', len(data)) + name + data + struct.pack('>I', zlib.crc32(name + data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\0\xff\0\0')) + chunk(b'IEND', b'')


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = Config(self.base / 'data')
        source = self.base / 'audio.wav'
        make_wav(source, seconds=1)
        with patch.object(OwnedDirectory, 'free_bytes', return_value=10**12):
            record = import_audio(self.config, source, provision_seconds=1, archive='not_requested')
        self.sid = record['session_id']
        self.directory = self.config.data_root / 'sessions' / self.sid
        self.photo = self.base / ('Şığ fotoğraf ' + 'ü' * 70 + '.PNG')
        self.photo.write_bytes(png())

    def ingest(self, paths):
        with patch.object(OwnedDirectory, 'free_bytes', return_value=10**12):
            return import_photos(self.config, self.sid, paths)

    def test_zero_noop_tree_and_metadata(self):
        before = {p.relative_to(self.directory).as_posix(): p.read_bytes() for p in self.directory.rglob('*') if p.is_file() and p.name != '.inspection.lock'}
        self.assertEqual(self.ingest([])['status'], 'not_present')
        after = {p.relative_to(self.directory).as_posix(): p.read_bytes() for p in self.directory.rglob('*') if p.is_file() and p.name != '.inspection.lock'}
        self.assertEqual(before, after)
        self.assertFalse((self.directory / 'originals/photos').exists())
        self.assertFalse(any('visual' in p.name for p in self.directory.rglob('*')))

    def test_multiple_unicode_long_bad_and_heif(self):
        bad = self.base / 'broken.jpg'
        bad.write_bytes(b'bad exif image')
        heif = self.base / 'camera.heic'
        heif.write_bytes(b'\0\0\0\x18ftypheic' + b'\0' * 12)
        result = self.ingest([self.photo, bad, heif])
        self.assertEqual(result['status'], 'partial_warning')
        self.assertEqual([p['visual_id'] for p in result['photos']], ['V001', 'V002', 'V003'])
        self.assertEqual(result['photos'][0]['original_filename'], self.photo.name)
        for p in result['photos']:
            blob = (self.directory / p['relative_path']).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(), p['sha256'])
            self.assertEqual(p['metadata']['timing_role'], 'hint_only')
        view = session_status(self.config, self.sid)
        self.assertEqual(view['current_state'], 'imported')
        self.assertEqual(len([e for e in view['artifacts'].values() if e['type'] == 'original_photo']), 3)

    def test_storage_denial_batch_failure_leave_audio_metadata_unchanged(self):
        before = (self.directory / 'session.json').read_bytes()
        with patch.object(OwnedDirectory, 'free_bytes', return_value=1), self.assertRaises(StorageError):
            import_photos(self.config, self.sid, [self.photo])
        self.assertEqual((self.directory / 'session.json').read_bytes(), before)
        self.assertFalse((self.directory / 'originals/photos').exists())
        with self.assertRaises(OSError):
            self.ingest([self.photo, self.base / 'absent.jpg'])
        self.assertEqual((self.directory / 'session.json').read_bytes(), before)
        self.assertEqual(session_status(self.config, self.sid)['visual_count'], 0)

    def test_publication_failure_never_registers_partial_batch(self):
        before = (self.directory / 'session.json').read_bytes()
        with patch.object(OwnedDirectory, 'publish', side_effect=OSError('injected')), self.assertRaises(OSError):
            self.ingest([self.photo])
        self.assertEqual((self.directory / 'session.json').read_bytes(), before)

    def test_protected_original_identity_and_corruption_nonblocking(self):
        result = self.ingest([self.photo])
        photo = result['photos'][0]
        (self.directory / photo['relative_path']).write_bytes(b'corrupt')
        view = session_status(self.config, self.sid)
        self.assertEqual(view['visual_status'], 'failed_nonblocking')
        self.assertEqual(view['current_state'], 'imported')
        self.assertNotIn('original_photo:V001', view['artifacts'])
        record = json.loads((self.directory / 'session.json').read_bytes())
        record['photos'][0]['sha256'] = '0' * 64
        with OwnedDirectory.root(self.directory) as directory, self.assertRaises(StorageError):
            directory.atomic_json(record)

    def test_bounded_malformed_metadata_and_exif_hints(self):
        for data in (b'', b'\xff\xd8\xff\xe1\0\x10Exif\0\0BADBAD', png(), b'random'):
            self.assertEqual(metadata(data, '.jpg')['timing_role'], 'hint_only')
        stamp = b'2026:10:22 10:20:30\0'
        tiff = b'II' + struct.pack('<HIH', 42, 8, 1) + struct.pack('<HHII', 0x9003, 2, len(stamp), 26) + b'\0' * 4 + stamp
        value = b'Exif\0\0' + tiff
        jpeg = b'\xff\xd8\xff\xe1' + struct.pack('>H', len(value) + 2) + value + b'\xff\xd9'
        result = metadata(jpeg, '.jpg')
        self.assertEqual(result['capture_time'], '2026:10:22 10:20:30')
        self.assertIsNone(result['timezone_offset'])

    def test_index_repair_and_append_keep_ids_originals_and_noop(self):
        original = self.ingest([self.photo])['photos'][0]
        before = (self.directory / 'session.json').read_bytes()
        self.assertTrue(self.ingest([])['reused'])
        self.assertEqual((self.directory / 'session.json').read_bytes(), before)
        record = json.loads(before)
        (self.directory / record['visual_index']['relative_path']).unlink()
        self.ingest([])
        self.assertEqual(session_status(self.config, self.sid)['visual_errors'], [])
        result = self.ingest([self.photo])
        self.assertEqual(result['photos'][0], original)
        self.assertEqual(result['photos'][1]['visual_id'], 'V002')

    @unittest.skipUnless(shutil.which('ffmpeg'), 'actual image encoder required')
    def test_real_jpeg_original_and_dimensions(self):
        path = self.base / 'kamera.jpg'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                        'color=red:size=16x16', '-frames:v', '1', '-threads', '1', str(path)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        photo = self.ingest([path])['photos'][0]
        self.assertEqual(photo['metadata']['format'], 'JPEG')
        self.assertEqual(photo['metadata']['dimensions'], dict(width=16, height=16))
        self.assertEqual((self.directory / photo['relative_path']).read_bytes(), path.read_bytes())

    def test_crash_after_one_photo_publish_never_commits_selection(self):
        second = self.base / 'second.png'
        second.write_bytes(png())
        original_publish = OwnedDirectory.publish
        before = (self.directory / 'session.json').read_bytes()
        def crash(owner, temporary, final, destination):
            original_publish(owner, temporary, final, destination)
            raise KeyboardInterrupt('simulated process death')
        with patch.object(OwnedDirectory, 'publish', crash), self.assertRaises(KeyboardInterrupt):
            self.ingest([self.photo, second])
        self.assertEqual((self.directory / 'session.json').read_bytes(), before)
        self.assertEqual(session_status(self.config, self.sid)['visual_count'], 0)
        result = self.ingest([self.photo, second])
        self.assertEqual(result['visual_count'], 2)


class VisualPipelineTests(ExportFixture):
    def test_zero_full_pipeline_and_attachment_archive_invalidation(self):
        legacy = self.record()
        legacy['visual_status'] = 'not_present'
        with OwnedDirectory.root(self.directory) as directory:
            directory.atomic_json(legacy)
        self.mocked_export()
        generate_manifests(self.config, self.sid)
        with patch.object(OwnedDirectory, 'free_bytes', return_value=10**12):
            package_session(self.config, self.sid)
            prior_archive = archive_session(self.config, self.sid, decision='on')
            before = session_status(self.config, self.sid)
            originals = {e['relative_path']: (self.directory / e['relative_path']).read_bytes()
                         for e in before['artifacts'].values() if e['status'] == 'verified'}
            metadata_before = (self.directory / 'session.json').read_bytes()
            import_photos(self.config, self.sid, [])
            self.assertEqual((self.directory / 'session.json').read_bytes(), metadata_before)
            self.assertFalse(any('visual' in w for w in before['warnings']))
            self.assertFalse((self.directory / 'originals/photos').exists())
            photo = self.directory.parent.parent / 'örnek.png'
            photo.write_bytes(png())
            import_photos(self.config, self.sid, [photo])
            view = session_status(self.config, self.sid)
            self.assertEqual(view['current_state'], 'packaged')
            self.assertEqual(view['archive_status']['status'], 'failed_nonblocking')
            for path, blob in originals.items():
                self.assertEqual((self.directory / path).read_bytes(), blob)
            archive_session(self.config, self.sid, decision='on')
            view = session_status(self.config, self.sid)
            self.assertEqual(view['archive_status']['status'], 'archived')
            entry = next(e for e in view['artifacts'].values() if e['type'] == 'full_archive' and e['status'] == 'verified')
            with zipfile.ZipFile(self.directory / entry['relative_path']) as archive:
                self.assertTrue(any(n.startswith('originals/photos/') for n in archive.namelist()))
                self.assertTrue(any(n.endswith('/visual_index.json') for n in archive.namelist()))
