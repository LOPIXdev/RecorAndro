"""Optional immutable attachments. No audio timing or processing dependencies."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import uuid

from .storage import OwnedDirectory, StorageError, MIB, _is_redirect
from .sessions import _fingerprint, copy_stream, hash_stream
from .packages import _context
from .session_state import _check_file, artifact_entry, project_session
from .manifests import json_bytes

SUFFIXES = {'.jpg', '.jpeg', '.png', '.heic', '.heif'}
HEADER_LIMIT = 1024 * 1024


def metadata(blob, suffix):
    result = dict(format=None, dimensions=None, capture_time=None, timezone_offset=None,
                  timezone_uncertainty='unknown', timing_role='hint_only',
                  metadata_source='bounded_header_reader_v1', metadata_status='unavailable')
    try:
        if blob.startswith(b'\x89PNG\r\n\x1a\n') and blob[12:16] == b'IHDR':
            width, height = struct.unpack('>II', blob[16:24])
            result.update(format='PNG', dimensions=dict(width=width, height=height), metadata_status='partial')
        elif blob.startswith(b'\xff\xd8'):
            result.update(format='JPEG', metadata_status='partial')
            position = 2
            while position + 4 <= len(blob):
                if blob[position] != 255:
                    break
                marker = blob[position + 1]
                position += 2
                if marker in (0xd9, 0xda):
                    break
                if marker == 0xff:
                    position -= 1
                    continue
                length = int.from_bytes(blob[position:position + 2], 'big')
                if length < 2 or position + length > len(blob):
                    break
                value = blob[position + 2:position + length]
                position += length
                if marker in (0xc0, 0xc1, 0xc2) and len(value) >= 5:
                    height, width = struct.unpack('>HH', value[1:5])
                    result['dimensions'] = dict(width=width, height=height)
                if marker == 0xe1 and value.startswith(b'Exif\0\0'):
                    exif(value[6:], result)
        elif len(blob) >= 12 and blob[4:8] == b'ftyp' and suffix in ('.heic', '.heif'):
            result['format'] = 'HEIF'
    except (ValueError, KeyError, IndexError, struct.error, UnicodeError, OverflowError):
        result['metadata_status'] = 'partial'
    return result


def exif(data, result):
    endian = {'II': '<', 'MM': '>'}[data[:2].decode('ascii')]
    def number(offset, code):
        return struct.unpack_from(endian + code, data, offset)[0]
    if number(2, 'H') != 42:
        return
    def directory(offset):
        count = number(offset, 'H')
        if count > 256:
            raise ValueError('Bounded EXIF directory')
        return {number(p, 'H'): p for p in range(offset + 2, offset + 2 + count * 12, 12)}
    tags = directory(number(4, 'I'))
    if 0x8769 in tags:
        tags = directory(number(tags[0x8769] + 8, 'I'))
    for tag, key in ((0x9003, 'capture_time'), (0x9011, 'timezone_offset')):
        if tag in tags:
            p = tags[tag]
            length = number(p + 4, 'I')
            if number(p + 2, 'H') != 2 or not 1 <= length <= 64:
                continue
            start = p + 8 if length <= 4 else number(p + 8, 'I')
            value = data[start:start + length]
            if len(value) != length:
                raise ValueError('Truncated EXIF')
            result[key] = value.rstrip(b'\0').decode('ascii')
    if result['timezone_offset']:
        result['timezone_uncertainty'] = 'unvalidated_camera_claim'


def entries(directory, record, *, strict=False, check_index=True):
    """Verify optional evidence independently; never advance/regress audio state."""
    verified, bad = {}, []
    photos = record.get('photos', [])
    for photo in photos:
        try:
            with ExitStack() as stack:
                _check_file(stack, directory, photo)
            key = 'original_photo:' + photo['visual_id']
            verified[key] = artifact_entry(key, 'original_photo', photo['relative_path'], status='verified',
                size=photo['size_bytes'], sha256=photo['sha256'], created_at=photo['created_at'],
                verified_at=photo['verified_at'], media=photo['metadata'])
        except (ValueError, OSError, KeyError, TypeError):
            bad.append(photo.get('visual_id', 'unknown'))
    index = record.get('visual_index')
    if photos and index and check_index:
        try:
            with ExitStack() as stack:
                _check_file(stack, directory, index)
            key = 'visual_index'
            verified[key] = artifact_entry(key, 'report', index['relative_path'], status='verified',
                size=index['size_bytes'], sha256=index['sha256'], created_at=index['created_at'],
                verified_at=index['verified_at'], revision=index['sha256'])
        except (ValueError, OSError, KeyError, TypeError):
            bad.append('visual_index')
    elif photos and check_index:
        bad.append('visual_index')
    if strict and bad:
        raise StorageError('Optional visual originals/index require attention: ' + ', '.join(bad))
    return verified, bad


def import_photos(config, session_id, paths):
    """All-or-nothing selected batch; failures retain audio and prior attachments."""
    paths = list(paths)
    with ExitStack() as stack:
        directory, record = _context(stack, config, session_id, None)
        if record['state'] != 'imported':
            raise StorageError('Import audio successfully before attaching photos')
        if not paths and not record.get('photos'):
            return {'status': 'not_present', 'visual_count': 0}
        view = project_session(directory, record)
        if view['last_successful_state'] == 'created':
            raise StorageError('Managed audio must verify before photo intake')
        if not paths:
            _, bad = entries(directory, record)
            if not bad:
                return dict(status=record.get('visual_status', 'indexed'), visual_count=len(record['photos']), reused=True)
        entries(directory, record, strict=True, check_index=False)
        opened = []
        for supplied in paths:
            path = Path(supplied).expanduser().absolute()
            info = path.lstat()
            if path.suffix.lower() not in SUFFIXES or _is_redirect(info) or not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
                raise StorageError('Photo must be a nonempty regular supported file')
            stream = stack.enter_context(os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) |
                        getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)), 'rb'))
            if _fingerprint(os.fstat(stream.fileno())) != _fingerprint(info):
                raise StorageError('Photo changed while opening')
            opened.append((path, info, stream))
        # Original + staging/index allowance + possible future archive copy.
        payload = sum(info.st_size for _, info, _ in opened)
        archive = record['storage_preflight']['archive']['reserve_archive']
        bound = payload * (2 if archive else 1) + MIB + 4096 * (len(opened) + len(record.get('photos', [])))
        existing = sum(e['size_bytes'] for e in view['artifact_registry'].values() if e['status'] == 'verified')
        pending_audio = 0 if view['last_successful_state'] in ('segments_exported', 'manifested', 'packaged') else max(
            0, record['storage_preflight']['estimated_required_bytes'] - existing -
            record['storage_preflight']['headroom_policy']['reserved_bytes'])
        bound += pending_audio
        reserve = max(256 * MIB, (bound + 4) // 5)
        budget = dict(policy='selected_visual_batch_v1', selected_original_bytes=payload,
                      existing_verified_bytes=existing, pending_audio_budget_bytes=pending_audio,
                      archive_reserved=archive, estimated_output_bytes=bound, reserve_bytes=reserve,
                      required_free_bytes=bound + reserve, free_bytes=directory.free_bytes())
        if budget['free_bytes'] < budget['required_free_bytes']:
            raise StorageError('Visual storage denied; audio-only continuation available: ' + json.dumps(budget))
        attempt = uuid.uuid4().hex
        temp = stack.enter_context(directory.child('temp'))
        staging = stack.enter_context(temp.child('visuals-' + attempt, exclusive=True))
        photos = list(record.get('photos', []))
        now = datetime.now(timezone.utc).isoformat()
        for path, initial, source in opened:
            visual_id = f'V{len(photos) + 1:03}'
            leaf = visual_id + path.suffix.lower()
            with os.fdopen(staging.open(leaf, os.O_RDWR | os.O_CREAT | os.O_EXCL), 'w+b') as output:
                size, checksum = copy_stream(source, output)
                output.flush()
                os.fsync(output.fileno())
                output.seek(0)
                if hash_stream(output) != (size, checksum):
                    raise StorageError('Photo copy verification failed')
                output.seek(0)
                details = metadata(output.read(HEADER_LIMIT), path.suffix.lower())
            source.seek(0)
            if hash_stream(source) != (size, checksum) or size != initial.st_size or _fingerprint(os.fstat(source.fileno())) != _fingerprint(initial):
                raise StorageError('Photo source changed during import')
            photos.append(dict(visual_id=visual_id, original_filename=path.name,
                relative_path=f'originals/photos/{attempt}/{leaf}', size_bytes=size, sha256=checksum,
                created_at=now, verified_at=now, metadata=details))
        model = dict(schema_version=1, session_id=session_id, visual_count=len(photos),
                     timing_role='hint_only', photos=photos)
        blob = json_bytes(model)
        with os.fdopen(staging.open('visual_index.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'wb') as output:
            output.write(blob)
            output.flush()
            os.fsync(output.fileno())
        if opened:
            originals = stack.enter_context(directory.child('originals'))
            parent = stack.enter_context(originals.child('photos'))
            final = stack.enter_context(parent.child(attempt, exclusive=True))
            for photo in photos[len(record.get('photos', [])):]:
                leaf = photo['relative_path'].split('/')[-1]
                staging.publish(leaf, leaf, final)
                with ExitStack() as check:
                    _check_file(check, directory, photo)
        generated = stack.enter_context(directory.child('generated'))
        parent = stack.enter_context(generated.child('visuals'))
        final_index = stack.enter_context(parent.child(attempt, exclusive=True))
        staging.publish('visual_index.json', 'visual_index.json', final_index)
        record.setdefault('document_visuals', dict(visual_count=record['visual_count'],
            visual_status='none' if record['visual_count'] == 0 else record.get('visual_status', 'pending')))
        status = 'partial_warning' if any(p['metadata']['format'] is None for p in photos) else 'indexed'
        record.update(photos=photos, visual_count=len(photos), visual_status=status, visual_storage_preflight=budget,
                      visual_index=dict(relative_path=f'generated/visuals/{attempt}/visual_index.json',
                        size_bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(), created_at=now, verified_at=now))
        entries(directory, record, strict=True)
        directory.atomic_json(record)
        return dict(status=status, visual_count=len(photos), photos=photos, storage_preflight=budget)
