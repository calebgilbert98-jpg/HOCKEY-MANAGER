/* Puck Dynasty web inbox — Gmail-style rows (matches the 2026-10-04 redesign) */
let currentFilter = 'all';
let messages = [];
let openId = null;

async function loadInbox(filter = 'all') {
  currentFilter = filter;
  document.querySelectorAll('#filters button').forEach(b =>
    b.classList.toggle('active', b.dataset.f === filter));
  try {
    const res = await fetch('/api/inbox?filter=' + encodeURIComponent(filter));
    messages = await res.json();
    renderList();
  } catch (e) { console.error(e); }
}

function indicator(m) {
  if (m.is_overdue || m.requires_response) return 'red';
  if (m.is_urgent || m.priority >= 4) return 'gold';
  if (m.is_important || m.priority >= 3) return 'gold';
  if (!m.is_read) return 'blue';
  return 'none';
}

function renderList() {
  const list = document.getElementById('msg-list');
  document.getElementById('inbox-count').textContent =
    messages.length + ' message' + (messages.length === 1 ? '' : 's');
  list.innerHTML = '';
  if (!messages.length) {
    list.innerHTML = '<div class="empty">Nothing here. Enjoy the quiet.</div>';
    return;
  }
  for (const m of messages) {
    const ind = indicator(m);
    const needsAction = m.is_overdue || m.requires_response;
    const row = document.createElement('div');
    row.className = 'msg-row' + (m.is_read ? '' : ' unread');
    row.innerHTML = `
      <span class="bar ${ind}"></span>
      <div class="msg-text">
        <div class="msg-sender">${esc(m.sender)}</div>
        <div class="msg-subj">${esc(m.subject)}${m.snippet ? ' <span class="msg-snip">— ' + esc(m.snippet) + '</span>' : ''}</div>
      </div>
      <div class="msg-right">
        <div class="msg-date">${esc(m.date)}</div>
        ${needsAction ? '<span class="pill">Action needed</span>' : ''}
      </div>`;
    row.addEventListener('click', () => openReader(m));
    list.appendChild(row);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

// Action buttons per message action_type (mirrors Tkinter inbox_window.py)
function actionButtons(m) {
  const at = m.action_type;
  if (!at) return '';
  const btn = (op, label, primary) =>
    `<button class="btn-${primary ? 'primary' : 'ghost'}" data-op="${op}" data-mid="${esc(m.id)}">${label}</button>`;
  switch (at) {
    case 'trade_offer':
      return `<div class="msg-actions">
        ${btn('inbox_trade_accept', 'Accept Trade', true)}
        ${btn('inbox_trade_decline', 'Decline', false)}
        <a class="btn-ghost" href="/trades">Review & Adjust</a></div>`;
    case 'trade_counter':
      return `<div class="msg-actions">
        ${btn('inbox_trade_accept', 'Accept Counter', true)}
        ${btn('inbox_trade_decline', 'Walk Away', false)}
        <a class="btn-ghost" href="/trades">Review & Adjust</a></div>`;
    case 'contract_counter':
      return `<div class="msg-actions">
        ${btn('inbox_contract_accept', 'Accept', true)}
        <a class="btn-ghost" href="/contracts">Make New Offer</a>
        ${btn('inbox_contract_walkaway', 'Walk Away', false)}</div>`;
    default:
      return '';
  }
}

async function openReader(m) {
  openId = m.id;
  document.getElementById('r-from').textContent = m.sender;
  document.getElementById('r-date').textContent = m.date;
  document.getElementById('r-subject').textContent = m.subject;
  document.getElementById('r-category').textContent = m.category;
  document.getElementById('r-body').textContent = m.content || m.snippet || '(no content)';
  document.getElementById('r-read').textContent = m.is_read ? 'Mark as unread' : 'Mark as read';
  // action buttons
  let ab = document.getElementById('r-actions');
  if (!ab) {
    ab = document.createElement('div');
    ab.id = 'r-actions';
    document.getElementById('r-body').after(ab);
  }
  ab.innerHTML = actionButtons(m);
  ab.querySelectorAll('button[data-op]').forEach(b =>
    b.addEventListener('click', async () => {
      await sendCommand(b.dataset.op, {message_id: b.dataset.mid});
      closeReader();
      setTimeout(() => loadInbox(currentFilter), 600);
    }));
  document.getElementById('reader').hidden = false;
}

function closeReader() {
  document.getElementById('reader').hidden = true;
  openId = null;
}

async function sendCommand(op, extra) {
  try {
    await fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(Object.assign({op}, extra || {})),
    });
  } catch (e) { console.error(e); }
}

document.getElementById('reader-close').addEventListener('click', closeReader);
document.getElementById('reader').addEventListener('click', e => {
  if (e.target.id === 'reader') closeReader();
});
document.getElementById('r-read').addEventListener('click', async () => {
  if (openId) await sendCommand('mark_read', {message_id: openId});
  closeReader();
  setTimeout(() => loadInbox(currentFilter), 400);
});
document.getElementById('r-delete').addEventListener('click', async () => {
  if (openId) await sendCommand('delete_message', {message_id: openId});
  closeReader();
  setTimeout(() => loadInbox(currentFilter), 400);
});
document.querySelectorAll('#filters button').forEach(b =>
  b.addEventListener('click', () => loadInbox(b.dataset.f)));

loadInbox('all');

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
