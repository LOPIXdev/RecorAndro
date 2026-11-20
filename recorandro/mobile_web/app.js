'use strict';

const el = id => document.getElementById(id);
const MiB = 1024 * 1024;
const audioSuffix = /\.(m4a|mp3|wav|aac)$/i;
const photoSuffix = /\.(jpe?g|png|heic|heif)$/i;
const storedSession = 'recorandro-session';
let csrf = '', upload = null, connected = false, polling = false, acting = false;
let selectNew = false, stopped = false, current = {state: 'select'}, partList = '', pendingJob = null;

async function request(path, body, headers = {}, signal) {
  const post = body !== undefined;
  const response = await fetch(path, {
    method: post ? 'POST' : 'GET',
    headers: post ? {'X-CSRF-Token': csrf, ...headers} : headers,
    body, signal
  });
  const value = await response.json();
  if (!response.ok) {
    const error = Error(value.error || 'Request failed');
    error.status = response.status;
    throw error;
  }
  return value;
}

function byteSize(size) {
  if (size >= MiB) return `${(size / MiB).toFixed(1)} MiB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${size} bytes`;
}

function selection() {
  const file = el('audio').files[0];
  const photos = Array.from(el('photos').files);
  el('audio-name').textContent = file ? `${file.name} · ${byteSize(file.size)}` : '';
  el('photo-names').textContent = photos.map(photo => photo.name).join(', ');
}
el('audio').onchange = selection;
el('photos').onchange = selection;

function renderDownloads({parts = [], archive}) {
  const signature = JSON.stringify([parts, archive]);
  if (signature === partList) return;
  partList = signature;
  el('parts').replaceChildren();
  for (const item of [...parts, ...(archive ? [archive] : [])]) {
    const row = document.createElement('li');
    const label = document.createElement('div');
    const meta = document.createElement('span');
    label.textContent = item.number ? `Part ${item.number}` : 'Full Archive';
    meta.className = 'download-meta';
    const duration = Number.isFinite(item.duration_seconds) ? `${item.duration_seconds.toFixed(1)} s · ` : '';
    meta.textContent = `${duration}${byteSize(item.size_bytes)}`;
    label.append(meta);
    const link = document.createElement('a');
    link.className = 'download-link';
    link.href = item.download;
    link.textContent = 'Download';
    link.setAttribute('aria-label', `Download ${item.name}`);
    row.append(label, link);
    el('parts').append(row);
  }
}

function render(state = current) {
  current = state;
  csrf = state.csrf || csrf;
  const busy = !!upload || !!state.busy;
  if (pendingJob && state.job_id === pendingJob) {
    selectNew = false;
    pendingJob = null;
  }
  const selected = selectNew || state.state === 'select';
  const ready = connected && !busy && !selected && state.state === 'packaged';
  const showSetup = !busy && selected;
  el('setup').hidden = !showSetup;
  el('status').hidden = showSetup || ready;
  el('ready').hidden = !ready;
  el('session-card').hidden = showSetup || (!state.session_id && busy);
  el('reopen').hidden = busy;
  el('start').disabled = !connected || busy || acting;
  el('open').disabled = !connected || busy || acting;
  el('stop').disabled = !connected || busy || acting;
  el('cancel').hidden = !upload;
  el('cancel').disabled = !upload;
  el('new-session').hidden = busy;
  const canResume = !busy && !selected && ['resumable', 'failed_retryable'].includes(state.recovery?.classification);
  el('resume').hidden = !canResume;
  el('resume').disabled = !connected || acting || !canResume;

  const labels = {uploading: 'Receiving files', processing: 'Processing', busy: 'Session busy',
    interrupted: 'Work interrupted', failed: 'Processing failed', status: 'Session checked'};
  el('activity').textContent = !connected ? 'Connection interrupted' :
    upload && !['processing', 'uploading'].includes(state.state) ? 'Sending selected files' :
      [labels[state.state], state.message].filter(Boolean).join(' · ');
  const milestone = state.milestone?.replaceAll('_', ' ');
  const next = !busy && state.recovery?.next_stage?.replaceAll('_', ' ');
  el('milestone').textContent = [milestone && `Last verified: ${milestone}`, next && `Next: ${next}`]
    .filter(Boolean).join(' · ');
  el('session').textContent = state.session_id || 'No verified session ID yet';
  if (state.session_id) {
    sessionStorage.setItem(storedSession, state.session_id);
    if (!el('sid').value) el('sid').value = state.session_id;
  }
  const messages = new Set([
    state.recovery?.error_message,
    ...(state.errors || []).map(error => error.message || error.code),
    ...(state.optional_issues || []).map(issue => issue.stage === 'photos'
      ? `Photos skipped. ${issue.message}` : 'Full Archive could not be verified.'),
    ...(state.visual_status === 'partial_warning' ? ['Some selected photos have limited metadata.'] : []),
    state.cleanup_warning
  ].filter(Boolean));
  el('details').textContent = [...messages].join('\n');
  el('summary').textContent = ready
    ? `${state.parts.length} verified ${state.parts.length === 1 ? 'part' : 'parts'}${state.visual_count ? ` · ${state.visual_count} photos attached` : ''}`
    : '';
  el('archive-note').textContent = ready && !state.archive && !['explicit_off', 'unresolved'].includes(state.archive_status)
    ? 'Full Archive is unavailable. The verified part ZIPs are ready.' : '';
  renderDownloads(ready ? state : {});
}

async function poll() {
  if (polling || acting || stopped) return;
  polling = true;
  try {
    const state = await request('/state');
    if (acting) return;
    connected = true;
    render(state);
  } catch {
    if (acting) return;
    connected = false;
    el('notice').textContent = 'Adapter unavailable. Reopen its private URL in Termux and check the saved session ID.';
    render();
  } finally {
    polling = false;
  }
}

el('start').onclick = async () => {
  if (!connected || acting || upload || current.busy) return;
  el('notice').textContent = '';
  const file = el('audio').files[0], budget = Number(el('budget').value);
  const photos = Array.from(el('photos').files);
  if (!file) {
    el('notice').textContent = 'Select one recording. Cancelling selection starts nothing.';
    return;
  }
  if (!Number.isInteger(budget) || budget < 1 || budget > 604800) {
    el('notice').textContent = 'Enter a budget of 1..604800 seconds.';
    return;
  }
  if (!audioSuffix.test(file.name) || !file.size || file.size > 128 * MiB) {
    el('notice').textContent = 'Choose a supported recording up to 128 MiB.';
    return;
  }
  if (photos.length > 8 || photos.some(photo => !photoSuffix.test(photo.name) || !photo.size || photo.size > 16 * MiB)
    || photos.reduce((sum, photo) => sum + photo.size, file.size) > 192 * MiB) {
    el('notice').textContent = 'Use up to eight supported photos, 16 MiB each, and 192 MiB total with audio.';
    return;
  }
  const setup = {
    photos: photos.map(({name, size}) => ({name, size})),
    archive: el('archive').checked ? 'on' : 'off',
    title: el('title').value.trim(), course: el('course').value.trim()
  };
  upload = new AbortController();
  render();
  const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
  pendingJob = id;
  try {
    await request('/start', photos.length ? new Blob([file, ...photos]) : file, {
      'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name),
      'X-Budget': String(budget), 'X-Job-ID': id, 'X-Setup': encodeURIComponent(JSON.stringify(setup))
    }, upload.signal);
    selectNew = false;
  } catch (error) {
    el('notice').textContent = `Upload ended: ${error.message}. Check status before starting again.`;
  } finally {
    upload = null;
    await poll();
    render();
  }
};

el('cancel').onclick = () => upload?.abort();
el('new-session').onclick = () => {
  selectNew = true;
  pendingJob = null;
  for (const id of ['audio', 'photos', 'title', 'course']) el(id).value = '';
  el('archive').checked = false;
  el('notice').textContent = '';
  selection();
  render();
};

async function sessionAction(action, sessionId) {
  if (acting) return;
  acting = true;
  el('notice').textContent = '';
  render();
  try {
    const state = await request('/' + action, JSON.stringify({session_id: sessionId}), {
      'Content-Type': 'application/json'
    });
    selectNew = false;
    pendingJob = null;
    render(state);
  } catch (error) {
    el('notice').textContent = error.message;
  } finally {
    acting = false;
    render();
  }
}

el('open').onclick = () => sessionAction('open', el('sid').value.trim());
el('resume').onclick = () => sessionAction('resume', current.session_id);
el('stop').onclick = async () => {
  acting = true;
  render();
  try {
    await request('/stop', '');
    stopped = true;
    connected = false;
    el('notice').textContent = 'Adapter stopped. Restart the Termux command to get a new private URL.';
  } catch (error) {
    el('notice').textContent = error.message;
  } finally {
    acting = false;
    render();
  }
};

(async () => {
  const token = location.hash.slice(1);
  history.replaceState(null, '', '/');
  try {
    if (token) await request('/auth', '', {'X-Launch-Token': token});
    el('sid').value = sessionStorage.getItem(storedSession) || '';
    await poll();
    if (connected && current.state === 'select' && el('sid').value) {
      el('reopen').open = true;
    }
  } catch (error) {
    el('notice').textContent = error.message;
  }
  setInterval(poll, 1000);
})();
