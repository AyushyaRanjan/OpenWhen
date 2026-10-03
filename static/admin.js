'use strict';

// Open When… — contributor form + passcode-gated admin list.
// Plain vanilla JS, no frameworks, no network calls except to this same server.

const MAX_RECORD_MS = 3 * 60 * 1000;

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ config */

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) throw new Error('bad response');
    const cfg = await res.json();

    if (cfg.friend_name) $('friendName').textContent = cfg.friend_name;

    const select = $('mood');
    for (const mood of cfg.moods || []) {
      const option = document.createElement('option');
      option.value = mood;
      option.textContent = mood;
      select.appendChild(option);
    }
  } catch {
    // The heading already says "your friend"; nothing else is required here.
  }
}

/* --------------------------------------------------------------- recorder */

const rec = {
  mediaRecorder: null,
  stream: null,
  chunks: [],
  blob: null,
  url: null,
  startedAt: 0,
  timerId: null,
  mime: '',
};

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') return null; // browser can't record
  const candidates = [
    'audio/webm;codecs=opus', // Chrome, Edge, Android, Firefox
    'audio/webm',
    'audio/mp4', // Safari
    'audio/mpeg',
  ];
  for (const type of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(type)) return type;
    } catch {
      /* keep trying */
    }
  }
  return ''; // let the browser choose its own default
}

function extensionFor(mime) {
  const m = (mime || '').toLowerCase();
  if (m.includes('webm')) return 'webm';
  if (m.includes('mp4')) return 'mp4';
  if (m.includes('mpeg') || m.includes('mp3')) return 'mp3';
  if (m.includes('ogg')) return 'ogg';
  if (m.includes('wav')) return 'wav';
  return 'webm';
}

function formatTime(ms) {
  const total = Math.floor(ms / 1000);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function setRecMessage(text, isBad) {
  const p = $('recMsg');
  p.textContent = text;
  p.classList.toggle('bad', Boolean(isBad));
}

function micErrorMessage(err) {
  const name = err && err.name;
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return 'The microphone is blocked. Allow mic access for this page, then try again.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return "I couldn't find a microphone on this device.";
  }
  if (name === 'NotReadableError') {
    return 'Something else is using the microphone. Close it and try again.';
  }
  return "Couldn't start the microphone. You can still send a written message.";
}

function clearRecording() {
  if (rec.timerId) {
    clearInterval(rec.timerId);
    rec.timerId = null;
  }
  if (rec.stream) {
    rec.stream.getTracks().forEach((t) => t.stop());
    rec.stream = null;
  }
  if (rec.url) {
    URL.revokeObjectURL(rec.url);
    rec.url = null;
  }
  rec.mediaRecorder = null;
  rec.chunks = [];
  rec.blob = null;
  rec.mime = '';
}

function resetRecorderUI() {
  $('timer').textContent = '0:00';
  $('playback').hidden = true;
  $('playback').removeAttribute('src');
  $('rerecordBtn').hidden = true;
  $('recordBtn').hidden = false;
  $('recordBtn').disabled = false;
  $('stopBtn').disabled = true;
}

function tick() {
  const elapsed = Date.now() - rec.startedAt;
  $('timer').textContent = formatTime(elapsed);
  if (elapsed >= MAX_RECORD_MS) stopRecording();
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setRecMessage(
      "This page needs a secure context and a browser that can record audio. Try Chrome, Edge or Safari.",
      true,
    );
    return;
  }

  // Clear any previous take first, so we never leak a mic stream.
  clearRecording();

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    setRecMessage(micErrorMessage(err), true);
    return;
  }

  const mime = pickMimeType();
  if (mime === null) {
    stream.getTracks().forEach((t) => t.stop());
    setRecMessage("This browser can't record audio.", true);
    return;
  }

  try {
    rec.mediaRecorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream);
  } catch {
    try {
      rec.mediaRecorder = new MediaRecorder(stream);
    } catch {
      stream.getTracks().forEach((t) => t.stop());
      setRecMessage("Couldn't start recording on this browser.", true);
      return;
    }
  }

  rec.stream = stream;
  rec.chunks = [];
  rec.mime = rec.mediaRecorder.mimeType || mime;
  rec.mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size) rec.chunks.push(e.data);
  };
  rec.mediaRecorder.onstop = finishRecording;
  rec.mediaRecorder.start();

  rec.startedAt = Date.now();
  rec.timerId = setInterval(tick, 200);
  tick();

  $('recordBtn').hidden = true;
  $('stopBtn').disabled = false;
  $('rerecordBtn').hidden = true;
  setRecMessage("Recording… tap Stop when you're done.");
}

function stopRecording() {
  if (rec.mediaRecorder && rec.mediaRecorder.state !== 'inactive') {
    rec.mediaRecorder.stop();
  }
}

function finishRecording() {
  if (rec.timerId) {
    clearInterval(rec.timerId);
    rec.timerId = null;
  }
  if (rec.stream) {
    rec.stream.getTracks().forEach((t) => t.stop());
    rec.stream = null;
  }
  if (rec.mediaRecorder) rec.mediaRecorder.onstop = null;

  const usedMime = rec.mime || 'audio/webm';
  rec.blob = new Blob(rec.chunks, { type: usedMime });
  rec.chunks = [];

  rec.url = URL.createObjectURL(rec.blob);
  const playback = $('playback');
  playback.src = rec.url;
  playback.hidden = false;

  $('stopBtn').disabled = true;
  $('recordBtn').hidden = true;
  $('rerecordBtn').hidden = false;
  setRecMessage('Have a listen. Happy with it?');
}

function reRecord() {
  clearRecording();
  resetRecorderUI();
  setRecMessage('');
  startRecording();
}

/* ------------------------------------------------------------ crisis card */

function showCrisis(data) {
  const card = $('crisisCard');
  card.replaceChildren();

  const heading = document.createElement('h2');
  heading.textContent = 'Before anything else';
  card.appendChild(heading);

  const message = document.createElement('p');
  message.textContent = data.message || 'Please reach out to someone who can help right now.';
  card.appendChild(message);

  const list = document.createElement('div');
  list.className = 'calllist';
  for (const resource of data.resources || []) {
    const link = document.createElement('a');
    link.href = resource.tel;
    link.textContent = resource.name;
    const note = document.createElement('span');
    note.textContent = `${resource.number} · ${resource.description}`;
    link.appendChild(note);
    list.appendChild(link);
  }
  card.appendChild(list);

  card.hidden = false;
  $('addView').hidden = true;
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ---------------------------------------------------------------- submit */

function showFormMessage(text, isBad) {
  const p = $('formMsg');
  p.textContent = text;
  p.classList.toggle('bad', Boolean(isBad));
}

async function submitItem(event) {
  event.preventDefault();

  const sender = $('sender').value.trim();
  const text = $('text').value.trim();
  const mood = $('mood').value;

  if (!sender) {
    showFormMessage('Please add your name so they know who it came from.', true);
    return;
  }
  if (!text && !rec.blob) {
    showFormMessage('A few words, a voice note, or both — anything is enough.', true);
    return;
  }

  const form = new FormData();
  form.append('kind', 'message');
  form.append('sender', sender);
  form.append('text', text);
  form.append('mood', mood);
  if (rec.blob) form.append('audio', rec.blob, `note.${extensionFor(rec.mime)}`);

  $('submitBtn').disabled = true;
  showFormMessage('Sending…');

  try {
    const res = await fetch('/api/item', { method: 'POST', body: form });
    const data = await res.json().catch(() => ({}));

    if (res.ok && data.crisis) {
      clearRecording();
      showCrisis(data);
      return;
    }
    if (!res.ok) {
      showFormMessage(data.detail || "That didn't save. Please try again.", true);
      return;
    }

    showFormMessage('Thank you, this will mean a lot.');
    $('addForm').reset();
    clearRecording();
    resetRecorderUI();
  } catch {
    showFormMessage("Couldn't reach the app. Is the server still running?", true);
  } finally {
    $('submitBtn').disabled = false;
  }
}

/* ----------------------------------------------------------------- admin */

let adminPasscode = sessionStorage.getItem('openwhen-admin') || '';

function adminHeaders(extra) {
  return Object.assign({ 'X-Admin-Passcode': adminPasscode }, extra || {});
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderGroup(title, items) {
  const group = el('div', 'group');
  group.appendChild(el('h3', null, title));

  if (!items.length) {
    group.appendChild(el('p', 'empty', 'Nothing here yet.'));
    return group;
  }

  for (const item of items) {
    const row = el('div', 'item');

    const meta = el('div', 'meta');
    meta.appendChild(el('span', 'who', item.sender || 'someone'));
    if (item.mood) meta.appendChild(el('span', 'tag', item.mood));
    if (item.created) {
      const when = new Date(item.created * 1000);
      meta.appendChild(el('span', 'when', when.toLocaleString()));
    }
    row.appendChild(meta);

    if (item.text) {
      // textContent, not innerHTML: a message is never treated as markup.
      row.appendChild(el('div', 'body', item.text));
    }

    if (item.audio) {
      const audio = document.createElement('audio');
      audio.controls = true;
      audio.src = `/media/${encodeURIComponent(item.audio)}`;
      row.appendChild(audio);
    }

    const remove = el('button', 'ghost danger', 'Delete');
    remove.type = 'button';
    remove.addEventListener('click', () => deleteItem(item.id, remove));
    row.appendChild(remove);

    group.appendChild(row);
  }
  return group;
}

async function loadAdmin() {
  const content = $('adminContent');
  content.replaceChildren(el('p', 'hint', 'Loading…'));

  try {
    const [messagesRes, winsRes] = await Promise.all([
      fetch('/api/items?kind=message', { headers: adminHeaders() }),
      fetch('/api/items?kind=win', { headers: adminHeaders() }),
    ]);

    if (messagesRes.status === 401 || winsRes.status === 401) {
      content.replaceChildren(
        el('p', 'hint bad', "That passcode didn't match. Tap the button again to retry."),
      );
      return false;
    }
    if (!messagesRes.ok || !winsRes.ok) {
      content.replaceChildren(el('p', 'hint bad', "Couldn't load the list. Try Refresh."));
      return true;
    }

    const messages = await messagesRes.json();
    const wins = await winsRes.json();

    content.replaceChildren(
      renderGroup(`Notes from loved ones (${messages.length})`, messages),
      renderGroup(`Their own wins (${wins.length})`, wins),
    );
    return true;
  } catch {
    content.replaceChildren(el('p', 'hint bad', "Couldn't reach the app."));
    return true;
  }
}

async function deleteItem(id, button) {
  if (!confirm('Delete this for good? This cannot be undone.')) return;
  button.disabled = true;
  try {
    const res = await fetch(`/api/item/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: adminHeaders(),
    });
    if (res.status === 401) {
      adminPasscode = '';
      sessionStorage.removeItem('openwhen-admin');
      $('adminView').hidden = true;
      return;
    }
    if (!res.ok) {
      button.disabled = false;
      return;
    }
    const row = button.closest('.item');
    if (row) row.remove();
  } catch {
    button.disabled = false;
  }
}

async function toggleAdmin() {
  const view = $('adminView');

  if (!view.hidden) {
    view.hidden = true;
    return;
  }

  if (!adminPasscode) {
    const entered = prompt('Admin passcode:');
    if (!entered) return;
    adminPasscode = entered;
  }

  view.hidden = false;
  const ok = await loadAdmin();
  if (ok && adminPasscode) {
    sessionStorage.setItem('openwhen-admin', adminPasscode);
  } else {
    sessionStorage.removeItem('openwhen-admin');
    if (ok === false) view.hidden = true;
  }
}

/* ------------------------------------------------------------------ wire */

$('recordBtn').addEventListener('click', startRecording);
$('stopBtn').addEventListener('click', stopRecording);
$('rerecordBtn').addEventListener('click', reRecord);
$('addForm').addEventListener('submit', submitItem);
$('adminToggle').addEventListener('click', toggleAdmin);
$('adminRefresh').addEventListener('click', loadAdmin);

loadConfig();
