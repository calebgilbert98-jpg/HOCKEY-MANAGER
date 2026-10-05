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
}

load();

(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
