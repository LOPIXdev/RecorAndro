'use strict';
const el = id => document.getElementById(id);
let csrf = '', upload = null, connected = false, polling = false;
async function request(path, body = undefined, headers = {}) {
  const r = await fetch(path, {method: body === undefined ? 'GET' : 'POST',
    headers: {...(body === undefined ? {} : {'X-CSRF-Token': csrf}), ...headers}, body});
  const value = await r.json();
  if (!r.ok) throw Error(value.error || 'Request failed');
  return value;
}
function render(s) {
  csrf = s.csrf || csrf;
  const busy = ['uploading', 'processing'].includes(s.state);
  el('message').textContent = `${s.state}: ${s.message || s.milestone || ''}`;
  el('session').textContent = s.session_id ? `Session ID: ${s.session_id}` : 'No verified import ID yet.';
  el('details').textContent = [s.recovery?.classification, s.recovery?.error_message,
    ...(s.errors || []).map(e => `${e.stage || ''}: ${e.message || e.code || ''}`),
    ...(s.warnings || [])].filter(Boolean).join('; ');
  if (s.session_id) el('sid').value = s.session_id;
  el('start').disabled = busy || !!upload || !connected;
  el('open').disabled = busy || !connected;
  el('stop').disabled = busy || !connected;
  el('resume').disabled = busy || !connected || !s.recovery ||
    !['resumable', 'failed_retryable'].includes(s.recovery.classification);
  el('parts').replaceChildren();
  for (const p of s.parts || []) {
    const li = document.createElement('li'), a = document.createElement('a');
    a.href = p.download; a.textContent = `Download ${p.name} (${p.size_bytes} bytes)`;
    li.append(a); el('parts').append(li);
  }
}
async function poll() {
  if (polling) return;
  polling = true;
  try { const s = await request('/state'); connected = true; render(s); }
  catch (e) { connected = false; el('message').textContent = `Connection unavailable: ${e.message}. Restart/reopen; no completion assumed.`;
    for (const id of ['start', 'open', 'resume', 'stop']) el(id).disabled = true; }
  finally { polling = false; }
}
el('start').onclick = async () => {
  el('notice').textContent = '';
  const file = el('audio').files[0], budget = Number(el('budget').value);
  if (!file) { el('notice').textContent = 'Select one recording. Cancelling selection starts nothing.'; return; }
  if (!Number.isInteger(budget) || budget < 1 || budget > 604800) { el('notice').textContent = 'Enter a budget of 1..604800 seconds.'; return; }
  if (!file.size || file.size > 128 * 1024 * 1024) { el('notice').textContent = 'Select a nonempty file up to 128 MiB.'; return; }
  upload = new AbortController(); el('start').disabled = true; el('cancel').disabled = false;
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  const id = Array.from(bytes, x => x.toString(16).padStart(2, '0')).join('');
  try {
    const r = await fetch('/start', {method: 'POST', signal: upload.signal, body: file,
      headers: {'X-CSRF-Token': csrf, 'Content-Type': 'application/octet-stream',
        'X-Filename': encodeURIComponent(file.name), 'X-Budget': String(budget), 'X-Job-ID': id}});
    const v = await r.json(); if (!r.ok) throw Error(v.error);
  } catch (e) { el('notice').textContent = `Upload ended: ${e.message}. Check status before starting again. Cancellation after full upload may not stop processing.`; }
  finally { upload = null; el('cancel').disabled = true; await poll(); }
};
el('cancel').onclick = () => { if (upload) upload.abort(); };
for (const action of ['open', 'resume']) el(action).onclick = async () => {
  el('notice').textContent = '';
  try { render(await request('/' + action, JSON.stringify({session_id: el('sid').value.trim()}), {'Content-Type': 'application/json'})); }
  catch (e) { el('notice').textContent = e.message; }
};
el('stop').onclick = async () => {
  try { await request('/stop', ''); connected = false; el('message').textContent = 'Adapter stopped. Restart the Termux command for a new private URL.'; }
  catch (e) { el('message').textContent = e.message; }
};
(async () => {
  const token = location.hash.slice(1); history.replaceState(null, '', '/');
  try { if (token) await request('/auth', '', {'X-Launch-Token': token}); await poll(); }
  catch (e) { el('message').textContent = e.message; }
  setInterval(poll, 2000);
})();
