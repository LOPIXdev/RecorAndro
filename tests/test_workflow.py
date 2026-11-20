"""Workflow boundaries plus one short real-core run; no historical suite rerun."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from recorandro.cli import main
from recorandro.config import Config
from recorandro.workflow import process_audio
from recorandro.recovery import recover_session
from recorandro.session_state import session_status
from recorandro.visuals import import_photos
from test_normalization import make_wav
from test_visuals import png


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = Config(self.base / 'data')
        self.sid = 'a' * 32
        self.view = dict(current_state='packaged', part_count=3,
            package_status={'status': 'verified'}, archive_status={'status': 'explicit_off'},
            artifacts={str(i): dict(type='zip_package', status='verified',
                relative_path=f'generated/packages/part_{i:02}.zip') for i in (3, 1, 2)})
        for name, kwargs in (
            ('import_audio', {'return_value': {'session_id': self.sid}}),
            ('recover_session', {'return_value': {'classification': 'complete'}}),
            ('session_status', {'side_effect': lambda *a: copy.deepcopy(self.view)}),
            ('import_photos', {'return_value': {'status': 'indexed'}})):
            mock = patch('recorandro.workflow.' + name, **kwargs)
            setattr(self, name, mock.start())
            self.addCleanup(mock.stop)

    def run_workflow(self, **kwargs):
        return process_audio(self.config, 'lecture.m4a', provision_seconds=7200, **kwargs)

    def test_zero_photos_default_off_multiple_paths_and_immediate_id(self):
        def imported(sid):
            self.assertEqual(sid, self.sid)
            self.recover_session.assert_not_called()
        result = self.run_workflow(on_import=imported)
        self.assertTrue(result['ok'])
        self.assertEqual([Path(p).name for p in result['part_zips']],
                         ['part_01.zip', 'part_02.zip', 'part_03.zip'])
        self.import_photos.assert_not_called()
        self.assertEqual(self.import_audio.call_args.kwargs['archive'], 'not_requested')
        self.assertEqual(self.import_audio.call_args.kwargs['provision_seconds'], 7200)

    def test_photo_selection_precedes_on_archive_inside_resume(self):
        self.view['archive_status'] = {'status': 'archived'}
        def resume(*args):
            self.import_photos.assert_called_once_with(self.config, self.sid, ['x.jpg'])
            return {'classification': 'complete'}
        self.recover_session.side_effect = resume
        self.assertTrue(self.run_workflow(photos=['x.jpg'], archive='on')['ok'])
        self.assertEqual(self.import_audio.call_args.kwargs['archive'], 'requested')

    def test_optional_failures_never_claim_archive_complete(self):
        self.import_photos.side_effect = OSError('unreadable photo')
        self.view['archive_status'] = {'status': 'failed_nonblocking'}
        result = self.run_workflow(photos=['missing.jpg'], archive='on')
        self.assertTrue(result['ok'])
        self.assertEqual([x['stage'] for x in result['optional_issues']], ['photos', 'archive'])
        self.assertEqual(len(result['recovery_actions']), 2)

    def test_failure_after_import_retains_id_and_resume(self):
        self.recover_session.side_effect = OSError('storage unavailable')
        result = self.run_workflow()
        self.assertFalse(result['ok'])
        self.assertEqual(result['stage'], 'resume')
        self.assertEqual(result['resume_args'], ['resume', self.sid])
        self.assertEqual(result['session_id'], self.sid)

    def test_no_false_success_on_failed_recovery_or_missing_package(self):
        self.recover_session.return_value = {'classification': 'failed_retryable',
                                            'error_code': 'export_failed'}
        self.assertFalse(self.run_workflow()['ok'])
        self.recover_session.return_value = {'classification': 'complete'}
        self.view['artifacts'].pop('2')
        self.assertFalse(self.run_workflow()['ok'])

    def test_interruption_and_cli_recovery_config(self):
        self.recover_session.side_effect = KeyboardInterrupt()
        config = self.base / 'config.json'
        config.write_text(json.dumps({'data_root': str(self.config.data_root)}))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(['--config', str(config), 'process-audio', 'x.wav',
                       '--provision-seconds', '60'])
        self.assertEqual(rc, 130)
        self.assertEqual(json.loads(err.getvalue())['session_id'], self.sid)
        self.assertEqual(json.loads(out.getvalue())['resume_args'][-4:],
                         ['--config', str(config), 'resume', self.sid])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Real tools required')
class RealWorkflowTests(unittest.TestCase):
    def test_zero_photo_failure_after_real_import_is_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Config(Path(tmp) / 'data')
            source = Path(tmp) / 'short.wav'
            make_wav(source, seconds=1, amplitude=0.1)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            with patch('recorandro.workflow.recover_session', side_effect=OSError('injected')):
                result = process_audio(config, source, provision_seconds=60)
            self.assertFalse(result['ok'])
            sid = result['session_id']
            self.assertEqual(session_status(config, sid)['audio']['sha256'], before)
            self.assertEqual(recover_session(config, sid)['classification'], 'complete')
            status = session_status(config, sid)
            self.assertEqual(status['current_state'], 'packaged')
            self.assertEqual(status['archive_status']['status'], 'explicit_off')
            self.assertEqual(status['visual_count'], 0)
            self.assertFalse((config.data_root / 'sessions' / sid / 'originals/photos').exists())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_short_audio_real_photos_archive_revision_and_original_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = Config(base / 'data')
            source = base / 'short.wav'
            make_wav(source, seconds=2, amplitude=0.1)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            photo = base / 'real-bytes.png'
            photo.write_bytes(png())
            result = process_audio(config, source, provision_seconds=60,
                                   photos=[photo], archive='on')
            self.assertTrue(result['ok'], result)
            self.assertEqual(len(result['part_zips']), 1)
            status = result['status']
            self.assertEqual(status['archive_status']['status'], 'archived')
            directory = config.data_root / 'sessions' / result['session_id']
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            self.assertEqual(hashlib.sha256((directory / status['audio']['managed_path']).read_bytes()).hexdigest(), before)
            with zipfile.ZipFile(result['part_zips'][0]) as part:
                self.assertEqual(len(part.namelist()), 3)
                self.assertFalse(any('photo' in n for n in part.namelist()))
            archive = next(e for e in status['artifacts'].values() if e['type'] == 'full_archive')
            with zipfile.ZipFile(directory / archive['relative_path']) as full:
                self.assertIsNone(full.testzip())
                self.assertTrue(any(n.startswith('originals/photos/') for n in full.namelist()))
            packaged_bytes = Path(result['part_zips'][0]).read_bytes()
            self.assertEqual(recover_session(config, result['session_id'])['performed_stages'], [])
            self.assertEqual(Path(result['part_zips'][0]).read_bytes(), packaged_bytes)
            self.assertEqual(session_status(config, result['session_id'])['current_state'], 'packaged')
            # Existing intake after packaging must retain every audio ZIP byte,
            # and the previously current archive must cease to claim completion.
            import_photos(config, result['session_id'], [photo])
            self.assertEqual(Path(result['part_zips'][0]).read_bytes(), packaged_bytes)
            self.assertEqual(session_status(config, result['session_id'])['archive_status']['status'],
                             'failed_nonblocking')
