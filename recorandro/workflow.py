"""Thin user workflow; canonical processing and locking belong to existing APIs."""
from .sessions import import_audio, ImportFailure
from .visuals import import_photos
from .recovery import recover_session
from .session_state import session_status


def process_audio(config, path, *, provision_seconds, photos=(), archive='off',
                  title=None, course=None, on_import=None):
    if archive not in ('on', 'off'):
        raise ValueError('Archive must be on or off')
    result = dict(ok=False, session_id=None, stage='import', part_zips=[],
                  optional_issues=[], recovery_actions=[])
    try:
        record = import_audio(config, path, provision_seconds=provision_seconds,
                              archive='requested' if archive == 'on' else 'not_requested',
                              title=title, course=course)
        sid = result['session_id'] = record['session_id']
        result['resume_args'] = ['resume', sid]
        result['stage'] = 'imported'
        if on_import is not None:
            on_import(sid)
        # Intake before resume: ON retains its original preflight reservation,
        # and resume cannot publish an archive preceding selected photos.
        result['stage'] = 'photos'
        if photos:
            try:
                result['photos'] = import_photos(config, sid, photos)
            except (ValueError, OSError) as exc:
                result['optional_issues'].append(dict(stage='photos', message=str(exc)))
                result['recovery_actions'].append(['import-photos', sid, *map(str, photos)])
        result['stage'] = 'resume'
        recovery = result['recovery'] = recover_session(config, sid)
        result['stage'] = 'status'
        status = result['status'] = session_status(config, sid)
        entries = sorted((e for e in status['artifacts'].values()
                          if e['type'] == 'zip_package' and e['status'] == 'verified'),
                         key=lambda e: e['relative_path'])
        base = config.data_root / 'sessions' / sid
        result['part_zips'] = [str(base / e['relative_path']) for e in entries]
        if (recovery['classification'] != 'complete' or status['current_state'] != 'packaged'
                or status['package_status']['status'] != 'verified'
                or not entries or len(entries) != status['part_count']):
            result.update(stage='resume', error=dict(
                code=recovery.get('error_code') or 'packages_not_verified',
                message=recovery.get('error_message') or 'Required package frontier did not verify.'))
            return result
        if archive == 'on' and status['archive_status']['status'] != 'archived':
            result['optional_issues'].append(dict(stage='archive',
                status=status['archive_status'], attempt=recovery.get('archive_status')))
            result['recovery_actions'].append(['archive-session', sid, '--decision', 'on'])
        result.update(ok=True, stage='packaged')
        return result
    except (ValueError, OSError, KeyboardInterrupt) as exc:
        if isinstance(exc, ImportFailure) and exc.record is not None:
            result['session_id'] = exc.record['session_id']
        result['error'] = dict(code=getattr(exc, 'code', 'interrupted' if isinstance(exc, KeyboardInterrupt)
                                          else 'workflow_failed'), message=str(exc) or type(exc).__name__)
        if result['stage'] == 'import':
            result['recovery_note'] = 'Import incomplete: inspect retained session if present; explicitly reselect source. Do not resume an unverified import.'
        else:
            result['recovery_note'] = 'Use resume_args with the same config/data root; optional photo selection may need explicit import-photos again.'
        return result
