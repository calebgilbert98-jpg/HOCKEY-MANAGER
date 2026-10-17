/* Puck Dynasty staff detail */
const SID = decodeURIComponent(window.location.pathname.split('/staff/')[1] || '');

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

async function load() {
  let d;
  try {
    const res = await fetch('/api/staff/' + encodeURIComponent(SID));
    if (!res.ok) { document.getElementById('sd-name').textContent = 'Staff not found'; return; }
    d = await res.json();
  } catch (e) { console.error(e); return; }
  document.title = d.name + ' — Puck Dynasty';
  document.getElementById('sd-name').textContent = d.name || '—';
  document.getElementById('sd-role').textContent =
    [d.role, d.department].filter(Boolean).join(' · ') || '—';
  const facts = [
    ['Rating', d.rating ? d.rating + ' / 100' : '—'],
    ['Age', d.age || '—'],
    ['Nationality', d.nationality || '—'],
    ['Experience', d.experience ? d.experience + ' yrs' : '—'],
    ['Years with team', d.years_with_team ?? '—'],
    ['Salary', d.salary ? '$' + Number(d.salary).toLocaleString() : '—'],
    ['Contract', d.contract_years ? d.contract_years + ' yr' + (d.contract_years === 1 ? '' : 's') : '—'],
    ['Morale', d.morale ?? '—'],
    ['Specialty', d.specialty || '—'],
    ['Reputation', d.reputation || '—'],
  ];
  document.getElementById('sd-facts').innerHTML = facts.map(([k, v]) =>
    `<div class="sd-fact"><label>${esc(k)}</label><strong>${esc(v)}</strong></div>`).join('');
  renderTabs(d);
}

function barColor(v) {
  if (v >= 80) return '#4CAF50';
  if (v >= 65) return '#8BC34A';
  if (v >= 50) return '#FFC107';
  if (v >= 35) return '#FF9800';
  return '#F44336';
}

/* ---- Detail tabs: Attributes / Standing / Personality / Record / Track Record / Analytics ---- */
const TAB_LABELS = {attributes: 'Attributes', standing: 'Standing', personality: 'Personality',
  record: 'Record', track_record: 'Track Record', analytics: 'Analytics'};

function renderTabs(d) {
  const tabs = d.tabs || {};
  const order = ['attributes', 'standing', 'personality', 'record', 'track_record', 'analytics']
    .filter(k => tabs[k] !== undefined);
  const nav = document.getElementById('sd-tabs');
  nav.innerHTML = order.map((k, i) =>
    `<button data-tab="${k}" class="${i === 0 ? 'active' : ''}">${TAB_LABELS[k]}</button>`).join('');
  const paint = (k) => {
    nav.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.tab === k));
    document.getElementById('sd-tab-body').innerHTML = renderTab(k, tabs[k]);
  };
  nav.querySelectorAll('button').forEach(b =>
    b.addEventListener('click', () => paint(b.dataset.tab)));
  if (order.length) paint(order[0]);
}

function renderTab(k, data) {
  if (k === 'attributes') {
    return (data || []).map(g => `
      <div class="sd-card"><h3>${esc(g.label)}</h3>
        ${(g.items || []).map(it => `
          <div class="attr-row"><span>${esc(it.name)}</span>
            <div class="mini-bar"><div class="mini-fill" style="width:${it.value}%;background:${barColor(it.value)}"></div></div>
            <strong>${it.value}</strong></div>`).join('')}
      </div>`).join('') || '<div class="dim">No attribute data.</div>';
  }
  if (k === 'standing') {
    const cls = {ok: 'resp resp-good', warn: 'resp resp-bad', info: 'resp resp-neutral'};
    return `<div class="sd-card">` + (data || []).map(l =>
      `<div class="${cls[l.kind] || cls.info}">• ${esc(l.text)}</div>`).join('') + `</div>`;
  }
  if (k === 'personality') {
    return `<div class="sd-card">
      ${data.style ? `<h3>${esc(data.style)}</h3>` : ''}
      ${data.style_description ? `<p class="dim">${esc(data.style_description)}</p>` : ''}
      ${(data.lines || []).map(l => `<div class="dim">• ${esc(l)}</div>`).join('')}
    </div>`;
  }
  if (k === 'record') {
    return `<div class="sd-card"><h3>Career Totals</h3><div>${esc(data.totals || 'No completed seasons on record yet — the first entry lands at season rollover.')}</div></div>
      <div class="sd-card"><h3>Honours</h3>${(data.honours || []).map(h => `<div>🏆 ${esc(h)}</div>`).join('') || '<div class="dim">No honours banked yet.</div>'}</div>
      ${(data.seasons || []).length ? `<div class="sd-card"><h3>Season by Season</h3>
        <div class="table-wrap"><table class="sd-table"><thead><tr>
          <th>Season</th><th>Team</th><th>Role</th><th>W-L-OTL</th><th>Playoffs</th><th></th>
        </tr></thead><tbody>
        ${data.seasons.map(s => `<tr${s.cup || s.adams ? ' class="gold-row"' : ''}>
          <td>${esc(s.season)}</td><td>${esc(s.team)}</td><td>${esc(s.role)}</td>
          <td>${esc(s.wl)}</td><td>${esc(s.playoffs)}</td>
          <td>${s.cup ? '🏆' : ''}${s.adams ? ' 🎖' : ''}</td></tr>`).join('')}
        </tbody></table></div></div>` : ''}`;
  }
  if (k === 'track_record') {
    return `<div class="sd-card"><h3>Scout Track Record</h3>
      <div><strong>${esc(data.record_line || 'No graded calls yet — a blank ledger.')}</strong></div>
      <p class="dim small">Every read this scout files is graded against what happens next. A validated breakout banks the club; a miss plants doubt — and clubs fire scouts under 40% on 10+ graded calls.</p></div>
      ${(data.history || []).length ? `<div class="sd-card"><h3>Recent Reads</h3>
        ${(data.history || []).map(h => `
          <div class="track-row"><span class="track-mark track-${h.mark}">${h.mark === 'hit' ? '✓' : h.mark === 'miss' ? '✗' : '·'}</span>
            <span>${esc(h.player)} — ${esc(h.kind)} read, ${esc(h.date)}</span></div>`).join('')}</div>` : ''}`;
  }
  if (k === 'analytics') {
    return `<div class="sd-card"><h3>Analytics Department</h3>
      <div class="big-stat">${data.quality}/100 — ${esc(data.tier)}</div>
      ${data.club_quality != null ? `<div>Club department quality: <strong>${data.club_quality}/100</strong> — models rebuild every ${data.refresh_days} days.</div>`
        : `<div class="dim">Would run your department at ${data.quality}/100 — models rebuild every ${data.refresh_days} days.</div>`}
      <p class="dim small">${esc(data.note || '')}</p></div>`;
  }
  return '';
}

/* ---- Extension negotiation (desktop renegotiation mechanics) ---- */
let NEG_YEARS = 2;
document.getElementById('sd-negotiate').addEventListener('click', async () => {
  document.getElementById('neg-modal').classList.remove('hidden');
  document.getElementById('neg-result').textContent = '';
  try {
    const res = await fetch('/api/staff/' + encodeURIComponent(SID) + '/negotiate-preview');
    const d = await res.json();
    if (d.error) { document.getElementById('neg-ask').textContent = d.error; return; }
    const money = n => '$' + Number(n).toLocaleString();
    document.getElementById('neg-title').textContent = 'Negotiate — ' + d.name;
    document.getElementById('neg-ask').textContent =
      `Current: ${money(d.current_salary)}/yr x ${d.current_years}y. ` +
      `Asking window: ${money(d.ask_min)}–${money(d.ask_max)}/yr (market ask ${money(d.market_ask)}/yr). ` +
      `Demands + your offer + his temperament decide the roll.`;
    document.getElementById('neg-budget').textContent =
      d.budget_remaining != null ? `Club staff budget available: ${money(d.budget_remaining)}/yr.` : '';
    const sal = document.getElementById('neg-salary');
    if (!sal.value) sal.value = d.market_ask.toLocaleString();
    updateNegChance();
  } catch (e) { console.error(e); }
});
document.getElementById('neg-close').addEventListener('click', () =>
  document.getElementById('neg-modal').classList.add('hidden'));
document.getElementById('neg-years').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-v]');
  if (!btn) return;
  NEG_YEARS = parseInt(btn.dataset.v, 10);
  document.querySelectorAll('#neg-years button').forEach(b =>
    b.classList.toggle('active', b === btn));
});
document.getElementById('neg-salary').addEventListener('input', () => {
  clearTimeout(window._negT);
  window._negT = setTimeout(updateNegChance, 350);
});

function parseMoney() {
  const raw = document.getElementById('neg-salary').value || '';
  const v = parseInt(raw.replace(/[$,\s]/g, ''), 10);
  return isNaN(v) || v <= 0 ? 0 : v;
}

async function updateNegChance() {
  const offer = parseMoney();
  const host = document.getElementById('neg-chance');
  if (!offer) { host.textContent = 'Enter an offer amount.'; return; }
  try {
    const res = await fetch('/api/staff/' + encodeURIComponent(SID) +
      '/negotiate-preview?offer=' + offer);
    const d = await res.json();
    if (d.chance == null) { host.textContent = ''; return; }
    const c = d.chance;
    const color = c >= 0.75 ? '#4CAF50' : c >= 0.45 ? '#FFC107' : '#F44336';
    host.innerHTML = `Estimated acceptance chance: <strong style="color:${color}">${Math.round(c * 100)}%</strong>`;
  } catch (e) { host.textContent = ''; }
}

document.getElementById('neg-offer').addEventListener('click', async () => {
  const offer = parseMoney();
  const host = document.getElementById('neg-result');
  if (!offer) { host.textContent = 'Enter an offer amount.'; return; }
  const btn = document.getElementById('neg-offer');
  btn.disabled = true;
  host.textContent = 'Making offer…';
  try {
    const res = await fetch('/api/staff/' + encodeURIComponent(SID) + '/negotiate', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({salary: offer, years: NEG_YEARS}),
    });
    const d = await res.json();
    if (!d.ok) { host.textContent = 'Could not send: ' + (d.error || 'unknown'); btn.disabled = false; return; }
    setTimeout(async () => {
      try {
        const rr = await fetch('/api/staff/hire-result');
        const rd = await rr.json();
        const r = rd.result;
        if (r && r.kind === 'staff_negotiate') {
          host.innerHTML = r.ok
            ? `<div class="${r.accepted ? 'resp resp-good' : 'resp resp-bad'}">${esc(r.text || '')}</div>${r.accepted ? '<div class="dim small">Confirmed in your inbox.</div>' : ''}`
            : `<div class="resp resp-bad">${esc(r.error || 'failed')}</div>`;
          if (r.accepted) setTimeout(load, 1200);
        } else { host.textContent = 'Offer sent — result pending.'; }
      } catch (e) { host.textContent = 'Offer sent — result pending.'; }
      btn.disabled = false;
    }, 1200);
  } catch (e) { host.textContent = 'Request failed.'; btn.disabled = false; }
});

load();

(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
