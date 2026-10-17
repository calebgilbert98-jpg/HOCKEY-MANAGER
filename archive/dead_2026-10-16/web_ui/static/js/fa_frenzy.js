/* Puck Dynasty — Free Agent Frenzy hub.
 * Desktop parity (event_day_hubs.py FreeAgencyFrenzy): signing wire,
 * top-UFA cards, done-deals feed, cap snapshot. Reuses /api/fa_frenzy.
 */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}
function salaryStr(s) {
  s = s || 0;
  return s >= 1e6 ? '$' + (s / 1e6).toFixed(2) + 'M'
                  : '$' + Math.round(s / 1e3) + 'K';
}

async function loadFrenzy() {
  try {
    const res = await fetch('/api/fa_frenzy');
    const d = await res.json();
    document.getElementById('frenzy-title').textContent = d.title || 'FREE AGENT FRENZY';
    document.getElementById('frenzy-tagline').textContent = d.tagline || '';

    // Wire
    const wire = document.getElementById('frenzy-wire');
    wire.innerHTML = (d.wire || []).map(l =>
      '<div class="wire-line">' + esc(l) + '</div>').join('') ||
      '<div class="empty-note">The wire is quiet.</div>';

    // Top UFA cards
    const ufas = document.getElementById('frenzy-ufas');
    const cards = d.top_ufas || [];
    if (!cards.length) {
      ufas.innerHTML = '<div class="empty-note">No free agents on the market.</div>';
    } else {
      ufas.innerHTML = '';
      for (const c of cards) {
        const card = document.createElement('div');
        card.className = 'ufa-card';
        card.innerHTML =
          '<div class="ufa-top"><span class="ufa-rank">#' + c.rank + '</span> ' +
          (c.id
            ? '<span class="clickable-text" data-href="/player/' + esc(c.id) + '" title="Open player profile"><span class="ufa-name">' + esc(c.name) + '</span></span>'
            : '<span class="ufa-name">' + esc(c.name) + '</span>') +
          '<span class="ufa-meta">' + esc(c.position) + ' · Age ' + esc(c.age) + ' · ' + esc(c.fa_type) + '</span></div>' +
          '<div class="ufa-mid"><span class="ufa-tier">' + esc(c.tier || '—') + '</span>' +
          '<span class="ufa-line">' + esc(c.season_line || '') + '</span></div>' +
          '<div class="ufa-bot"><span class="ufa-ask">Ask: ' + salaryStr(c.ask) + '/yr</span>' +
          '<button class="btn-offer-sm" data-id="' + esc(c.id) + '">Make offer</button></div>';
        ufas.appendChild(card);
      }
      ufas.querySelectorAll('.btn-offer-sm').forEach(b =>
        b.addEventListener('click', () => {
          window.location.href = '/free_agents?offer=' + encodeURIComponent(b.dataset.id);
        }));
    }

    // Done deals
    const deals = document.getElementById('frenzy-deals');
    deals.innerHTML = (d.deals || []).map(s =>
      '<div class="deal-line">• ' + esc(s) + '</div>').join('') ||
      '<div class="empty-note">No signings yet today.</div>';

    // Cap snapshot
    const cap = d.cap || {};
    document.getElementById('frenzy-cap').innerHTML =
      '<div class="cap-row"><span>Cap ceiling</span><b>' + salaryStr(cap.cap) + '</b></div>' +
      '<div class="cap-row"><span>Committed</span><b>' + salaryStr(cap.committed) + '</b></div>' +
      '<div class="cap-row"><span>Cap space</span><b class="' + (cap.space >= 0 ? 'good' : 'bad') + '">' + salaryStr(cap.space) + '</b></div>';
  } catch (e) { console.error(e); }
}

loadFrenzy();
setInterval(loadFrenzy, 60000); // the wire streams live during the frenzy

// Shared heartbeat
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Clickable player names navigate to profiles.
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select')) return;
  const t = e.target.closest('.clickable-text[data-href]');
  if (t) window.location.href = t.dataset.href;
});
