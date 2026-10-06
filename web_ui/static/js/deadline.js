/* Puck Dynasty Trade Deadline Center — countdown, stance, market,
   rumors. Hub-style port of trade_deadline_center.py. */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

async function boot() {
  try {
    const d = await (await fetch('/api/deadline')).json();
    if (!d.available) {
      document.querySelector('main.dl-main').insertAdjacentHTML('beforeend',
        '<div class="empty">Deadline Center unavailable — no league loaded.</div>');
      return;
    }
    renderCountdown(d);
    renderStance(d);
    renderMarket(d.market || {});
    renderImpact((d.market || {}).impact || []);
    renderRumors(d.rumors || []);
    renderDeals((d.market || {}).recent_deals || []);
  } catch (e) {
    console.error(e);
  }
}

function renderCountdown(d) {
  const days = d.days_left;
  const num = document.getElementById('dl-days');
  const label = document.getElementById('dl-count-label');
  const dateEl = document.getElementById('dl-date');
  dateEl.textContent = (d.deadline_label || '') + ' · ' + (d.deadline_hour_et || '');
  if (d.passed) {
    num.textContent = '✕';
    label.textContent = 'the deadline has passed';
  } else if (d.is_deadline_day) {
    num.textContent = '0';
    label.textContent = 'DEADLINE DAY — deals lock at 3 PM ET';
    document.getElementById('dl-countdown').classList.add('is-today');
  } else if (days != null) {
    num.textContent = days;
    label.textContent = days === 1 ? 'day to the deadline' : 'days to the deadline';
  }
  document.getElementById('dl-sub').textContent =
    d.deadline_label ? 'Deadline: ' + d.deadline_label : 'Trade Deadline Center';
}

function renderStance(d) {
  const host = document.getElementById('dl-stance');
  const s = d.stance;
  if (!s) { host.innerHTML = '<div class="empty">No team data.</div>'; return; }
  const cls = s.verdict === 'BUYER' ? 'buy' : s.verdict === 'SELLER' ? 'sell' : 'tween';
  host.innerHTML = `
    <div class="stance-verdict ${cls}">${esc(s.verdict)}</div>
    <p class="panel-note">${esc(s.reason)}</p>
    ${s.record ? `<p class="stance-record">${esc(s.record)}${s.rank ? ` · ${s.rank} of ${s.of}` : ''}</p>` : ''}
    ${s.needs && s.needs.length ? `
      <div class="sd-h">Weakest areas</div>
      ${s.needs.map(n => `<div class="need-row"><span>${esc(n.group)}</span>
        <span class="num">avg ${n.avg_ovr} OVR · ${n.count} players</span></div>`).join('')}` : ''}
    ${s.cap_space != null ? `<p class="panel-note">Cap space: $${(s.cap_space / 1e6).toFixed(1)}M</p>` : ''}`;
  const declared = (d.declared_stance || '').toLowerCase();
  document.querySelectorAll('#stance-pills .tb-pill').forEach(b =>
    b.classList.toggle('active', b.dataset.v === declared));
}

document.getElementById('stance-pills').addEventListener('click', async e => {
  const b = e.target.closest('.tb-pill');
  if (!b) return;
  const v = b.dataset.v;
  try {
    const r = await fetch('/api/deadline/stance', { method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ stance: v }) });
    const d = await r.json();
    if (d.ok) {
      document.querySelectorAll('#stance-pills .tb-pill').forEach(p =>
        p.classList.toggle('active', p === b));
    }
  } catch (err) { console.error(err); }
});

function marketRows(list) {
  return (list || []).map(t => `
    <div class="market-row${t.is_user ? ' user' : ''}">
      <span class="market-team clickable-text" data-href="/team/${encodeURIComponent(t.team)}" title="Open team overview">${esc(t.team)}</span>
      <span class="market-rec">${esc(t.record)}</span>
      <span class="market-pts">${t.points} pts</span>
    </div>`).join('') || '<div class="panel-note">—</div>';
}

function renderMarket(m) {
  document.getElementById('dl-buyers').innerHTML = marketRows(m.buyers);
  document.getElementById('dl-sellers').innerHTML = marketRows(m.sellers);
}

function renderImpact(list) {
  const host = document.getElementById('dl-impact');
  host.innerHTML = list.length ? list.map(p => `
    <div class="impact-card">
      <div class="impact-name">${esc(p.name)} <span class="pos-tag">${esc(p.pos)}</span></div>
      <div class="panel-note">${esc(p.team)} · ${esc(p.status)}</div>
      <div class="impact-val ${esc(p.value).toLowerCase()}">${esc(p.value)} value</div>
    </div>`).join('')
    : '<div class="empty">No impact players on the market right now.</div>';
}

function renderRumors(rumors) {
  const host = document.getElementById('dl-rumors');
  host.innerHTML = rumors.length ? rumors.map(r => `
    <div class="rumor-row"><span class="rumor-dot">•</span><span>${esc(typeof r === 'string' ? r : (r.text || r.title || ''))}</span></div>`).join('')
    : '<div class="empty">The mill is quiet… for now.</div>';
}

function renderDeals(deals) {
  const host = document.getElementById('dl-deals');
  host.innerHTML = deals.length ? deals.map(x => `
    <div class="rumor-row"><span class="rumor-dot">🤝</span>
    <span>${esc(x.summary)}${x.date ? ` <span class="panel-note">(${esc(x.date)})</span>` : ''}</span></div>`).join('')
    : '<div class="empty">No deadline deals yet.</div>';
}

boot();

// Shared heartbeat
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, label')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
