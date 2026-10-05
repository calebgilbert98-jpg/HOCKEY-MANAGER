/* Puck Dynasty web tactics */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

document.getElementById('tactics-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#tactics-tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tab = btn.dataset.tab;
  document.getElementById('view-systems').classList.toggle('hidden', tab !== 'systems');
  document.getElementById('view-practice').classList.toggle('hidden', tab !== 'practice');
  if (tab === 'practice') loadPractice();
});

async function loadTactics() {
  try {
    const res = await fetch('/api/tactics');
    const data = await res.json();
    const host = document.getElementById('tactic-groups');
    host.innerHTML = (data.groups || []).map(g => `
      <div class="tactic-group">
        <h3>${esc(g.title)}</h3>
        <p class="dim">${esc(g.hint)}</p>
        <div class="pill-row" data-attr="${esc(g.attr)}">
          ${g.values.map(v => `
            <button data-v="${esc(v)}" class="${v === g.current ? 'active' : ''}">${esc(v)}</button>`
          ).join('')}
        </div>
      </div>`).join('');
    host.querySelectorAll('.pill-row').forEach(row =>
      row.addEventListener('click', async e => {
        const btn = e.target.closest('button[data-v]');
        if (!btn) return;
        const attr = row.dataset.attr;
        const value = btn.dataset.v;
        row.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        await fetch('/api/tactics/set', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({attr, value}),
        });
        // Refresh impact readout after a beat (command runs on Tk thread)
        setTimeout(refreshImpact, 800);
      }));
    renderImpact(data.impact || []);
  } catch (e) { console.error(e); }
}

function renderImpact(lines) {
  document.getElementById('impact-lines').innerHTML =
    lines.map(l => `<div class="impact-line">${esc(l)}</div>`).join('');
}

async function refreshImpact() {
  try {
    const res = await fetch('/api/tactics');
    const data = await res.json();
    renderImpact(data.impact || []);
  } catch (e) { /* ignore */ }
}

const practiceState = {focus: 'systems', intensity: 'moderate', bag: false};

async function loadPractice() {
  try {
    const res = await fetch('/api/tactics/practice');
    const d = await res.json();
    practiceState.focus = d.focus || 'systems';
    practiceState.intensity = d.intensity || 'moderate';
    practiceState.bag = !!d.bag_skate;
    const foci = d.foci || {};
    const ints = d.intensities || {};
    const fh = document.getElementById('practice-foci');
    fh.innerHTML = Object.entries(foci).map(([k, label]) =>
      `<button data-v="${esc(k)}" class="${k === practiceState.focus ? 'active' : ''}">${esc(label)}</button>`).join('');
    fh.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      fh.querySelectorAll('button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      practiceState.focus = b.dataset.v;
    }));
    const ih = document.getElementById('practice-intensity');
    ih.innerHTML = Object.entries(ints).map(([k, label]) =>
      `<button data-v="${esc(k)}" class="${k === practiceState.intensity ? 'active' : ''}">${esc(label)}</button>`).join('');
    ih.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      ih.querySelectorAll('button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      practiceState.intensity = b.dataset.v;
    }));
    document.getElementById('bag-skate').checked = practiceState.bag;
  } catch (e) { console.error(e); }
}

document.getElementById('practice-save').addEventListener('click', async () => {
  practiceState.bag = document.getElementById('bag-skate').checked;
  await fetch('/api/tactics/practice', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({focus: practiceState.focus, intensity: practiceState.intensity, bag_skate: practiceState.bag}),
  });
  alert('Practice plan saved.');
});

loadTactics();

(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
