/* Puck Dynasty web tactics — systems model + identity + analyst + coach */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'}[c]));
}

let TDATA = null;

document.getElementById('tactics-tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-tab]');
  if (!btn) return;
  document.querySelectorAll('#tactics-tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const tab = btn.dataset.tab;
  ['systems', 'identity', 'analyst', 'coach', 'practice'].forEach(t =>
    document.getElementById('view-' + t).classList.toggle('hidden', t !== tab));
  if (tab === 'practice') loadPractice();
});

function famColor(v) {
  if (v >= 70) return '#4CAF50';
  if (v >= 50) return '#FFC107';
  return '#F44336';
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  return res.json();
}

async function loadTactics() {
  try {
    const res = await fetch('/api/tactics');
    TDATA = await res.json();
    const d = TDATA;

    // Status bar: identity + familiarity + whiteboard control
    const ident = (d.identity && d.identity.active)
      ? (d.identity.presets.find(p => p.key === d.identity.active) || {}).name
      : 'Custom mix';
    const fam = d.familiarity == null ? 0 : Math.round(d.familiarity);
    document.getElementById('tactics-statusbar').innerHTML = `
      <div class="status-chip"><span class="dim">Identity</span><strong>${esc(ident || 'Custom mix')}</strong></div>
      <div class="status-chip"><span class="dim">Familiarity</span>
        <strong style="color:${famColor(fam)}">${fam}/100</strong>
        <div class="fam-bar"><div class="fam-fill" style="width:${fam}%;background:${famColor(fam)}"></div></div>
      </div>
      <div class="status-chip"><span class="dim">Whiteboard</span><strong>${d.control === 'gm' ? 'YOU (GM)' : 'Coach'}</strong></div>
      <div class="status-chip"><span class="dim">Roster fit</span><strong>${d.roster_fit != null ? Math.round(d.roster_fit * 100) + '%' : '—'}</strong></div>`;

    // Module pickers
    const grid = document.getElementById('module-grid');
    grid.innerHTML = (d.modules || []).map(m => `
      <div class="module-card" data-cat="${esc(m.key)}">
        <div class="module-head">
          <div>
            <h3>${esc(m.label)}</h3>
            <p class="dim">${esc(m.hint)}</p>
          </div>
          <div class="module-current">
            <div class="dim">Running</div>
            <strong>${esc(m.current_name)}</strong>
            <div class="tradeoff">${esc(m.tradeoffs)}</div>
          </div>
        </div>
        <div class="pill-row module-pills">
          ${m.systems.map(s => `<button data-sys="${esc(s.key)}" class="${s.key === m.current ? 'active' : ''}" title="${esc(s.blurb)}">${esc(s.name)}</button>`).join('')}
        </div>
        <div class="module-detail" id="md-${esc(m.key)}">
          <p>${esc(m.blurb)}</p>
          <p class="dim">${m.exemplars && m.exemplars.length ? 'Run by: ' + esc(m.exemplars.join(', ')) : ''}</p>
        </div>
      </div>`).join('');
    grid.querySelectorAll('.module-card').forEach(card => {
      card.querySelector('.module-pills').addEventListener('click', async e => {
        const btn = e.target.closest('button[data-sys]');
        if (!btn) return;
        const cat = card.dataset.cat, sys = btn.dataset.sys;
        card.querySelectorAll('.module-pills button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        btn.disabled = true;
        try {
          await postJSON('/api/tactics/system', {category: cat, system: sys});
          setTimeout(loadTactics, 900);
        } catch (err) { console.error(err); }
        btn.disabled = false;
      });
      // Double-click a system pill to inspect its detail (blurb, fit, exemplars).
      card.querySelector('.module-pills').addEventListener('dblclick', e => {
        const btn = e.target.closest('button[data-sys]');
        if (!btn) return;
        const m = (TDATA.modules || []).find(x => x.key === card.dataset.cat);
        const s = m && (m.systems || []).find(x => x.key === btn.dataset.sys);
        if (s) {
          document.getElementById('md-' + card.dataset.cat).innerHTML =
            `<p><strong>${esc(s.name)}</strong> — ${esc(s.blurb)}</p>
             <p class="tradeoff">${esc(s.tradeoffs)}</p>
             <p class="dim">Roster fit ${Math.round(s.fit * 100)}% (${s.fit_delta >= 0 ? '+' : ''}${Math.round(s.fit_delta * 100)} vs current)${s.exemplars && s.exemplars.length ? ' · Run by: ' + esc(s.exemplars.join(', ')) : ''}</p>`;
        }
      });
    });

    // Legacy game-management sliders
    const host = document.getElementById('tactic-groups');
    host.innerHTML = (d.groups || []).map(g => `
      <div class="legacy-group">
        <h4>${esc(g.title)}</h4>
        <p class="dim">${esc(g.hint)}</p>
        <div class="pill-row" data-attr="${esc(g.attr)}">
          ${g.values.map(v => `<button data-v="${esc(v)}" class="${v === g.current ? 'active' : ''}">${esc(v)}</button>`).join('')}
        </div>
      </div>`).join('');
    host.querySelectorAll('.pill-row').forEach(row =>
      row.addEventListener('click', async e => {
        const btn = e.target.closest('button[data-v]');
        if (!btn) return;
        const attr = row.dataset.attr, value = btn.dataset.v;
        row.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        await postJSON('/api/tactics/set', {attr, value});
        setTimeout(refreshReadout, 800);
      }));

    renderReadout(d);
    renderIdentity(d);
    renderIntel(d);
    renderCoach(d);
  } catch (e) { console.error(e); }
}

function renderReadout(d) {
  const eng = d.engine || {};
  const bits = [];
  const show = (k, label, invert) => {
    const v = eng[k];
    if (v == null) return;
    const pct = Math.round((v - 1.0) * 100);
    const good = invert ? pct < 0 : pct > 0;
    bits.push(`<span class="eng-bit ${good ? 'good' : pct === 0 ? '' : 'bad'}">${label} ${pct >= 0 ? '+' : ''}${pct}%</span>`);
  };
  show('attack', 'Attack'); show('defense', 'Chances allowed', true);
  show('pace', 'Pace'); show('shot_vol', 'Shot volume'); show('shot_qual', 'Shot quality');
  show('pp', 'PP'); show('pk', 'PK suppression', true); show('pressure', 'Pressure');
  document.getElementById('engine-lines').innerHTML =
    `<div class="dim" style="margin-bottom:8px">Engine multipliers from the seven modules:</div>
     <div class="eng-row">${bits.join('') || '<span class="dim">—</span>'}</div>
     <div class="dim" style="margin:10px 0 6px">Identity: ${(d.identity_lines || []).map(esc).join(' · ')}</div>`;
  document.getElementById('impact-lines').innerHTML =
    (d.impact || []).map(l => `<div class="impact-line">${esc(l)}</div>`).join('');
}

async function refreshReadout() {
  try {
    const res = await fetch('/api/tactics');
    renderReadout(await res.json());
  } catch (e) { /* ignore */ }
}

function renderIdentity(d) {
  const ident = d.identity || {};
  document.getElementById('identity-grid').innerHTML =
    (ident.presets || []).map(p => `
      <div class="identity-card ${ident.active === p.key ? 'active' : ''}">
        <div class="ident-head">
          <h3>${esc(p.name)}</h3>
          ${ident.active === p.key ? '<span class="ident-badge">INSTALLED</span>' : ''}
        </div>
        <div class="ident-tag">${esc(p.tagline)}</div>
        <p>${esc(p.blurb)}</p>
        <div class="ident-modules">${p.modules.map(m =>
          `<div class="ident-mod"><span class="dim">${esc(m.category)}</span><strong>${esc(m.system)}</strong></div>`).join('')}</div>
        <p class="dim small">Exemplars: ${esc((p.exemplars || []).join(', '))}</p>
        <button class="btn ${ident.active === p.key ? 'secondary' : 'primary'}" data-preset="${esc(p.key)}"
          ${ident.active === p.key ? 'disabled' : ''}>${ident.active === p.key ? 'Current Identity' : 'Install Identity'}</button>
      </div>`).join('');
  document.querySelectorAll('#identity-grid [data-preset]').forEach(btn =>
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await postJSON('/api/tactics/preset', {preset: btn.dataset.preset});
        setTimeout(loadTactics, 900);
      } catch (e) { console.error(e); }
      btn.disabled = false;
    }));
}

function renderIntel(d) {
  const list = d.intel || [];
  document.getElementById('intel-list').innerHTML = list.length ? list.map((c, i) => `
    <div class="intel-card intel-${esc(c.kind)}">
      <div class="intel-kind">${esc(c.kind.toUpperCase())}</div>
      <h3>${esc(c.title)}</h3>
      <p>${esc(c.text)}</p>
      ${c.action ? `<button class="btn secondary" data-intel="${i}">${esc(c.action.label)}</button>` : ''}
    </div>`).join('') :
    '<div class="dim">No analyst notes right now. The whiteboard looks sound.</div>';
  document.querySelectorAll('#intel-list [data-intel]').forEach(btn =>
    btn.addEventListener('click', async () => {
      const c = list[+btn.dataset.intel];
      if (!c || !c.action) return;
      btn.disabled = true;
      try {
        await postJSON(c.action.endpoint, c.action.payload);
        setTimeout(loadTactics, 900);
      } catch (e) { console.error(e); }
      btn.disabled = false;
    }));
}

function renderCoach(d) {
  const c = d.coach;
  const wb = document.getElementById('coach-whiteboard');
  if (!c) {
    wb.innerHTML = '<div class="dim">No head coach on staff.</div>';
    document.getElementById('coach-rows').innerHTML = '';
    return;
  }
  wb.innerHTML = `
    <div class="tactic-group">
      <h3>Whiteboard Control</h3>
      <p class="dim"><strong>${esc(c.name)}</strong> · ${esc(c.style)} · coach-system fit ${Math.round(c.fit * 100)}%.
      ${c.control === 'coach'
        ? 'He owns the whiteboard — he may adjust systems between periods.'
        : 'You own the whiteboard — he coaches the systems you install.'}</p>
      <div class="action-row">
        <button class="btn ${c.control === 'coach' ? 'primary' : 'secondary'}" id="wb-coach">Coach Controls</button>
        <button class="btn ${c.control === 'gm' ? 'primary' : 'secondary'}" id="wb-gm">I Control</button>
      </div>
    </div>`;
  document.getElementById('wb-coach').addEventListener('click', async e => {
    e.target.disabled = true;
    await postJSON('/api/tactics/control', {who: 'coach'});
    setTimeout(loadTactics, 900);
  });
  document.getElementById('wb-gm').addEventListener('click', async e => {
    e.target.disabled = true;
    await postJSON('/api/tactics/control', {who: 'gm'});
    setTimeout(loadTactics, 900);
  });
  document.getElementById('coach-rows').innerHTML = (c.rows || []).map(r => `
    <tr class="${r.match ? 'row-match' : 'row-mismatch'}">
      <td><strong>${esc(r.category)}</strong></td>
      <td>${esc(r.coach_wants)}</td>
      <td>${esc(r.current)}</td>
      <td>${r.match ? '<span class="resp resp-good">Aligned</span>' : '<span class="resp resp-warn">Differs</span>'}</td>
    </tr>`).join('');

  document.getElementById('coach-suggest').onclick = () => {
    const mism = (c.rows || []).filter(r => !r.match);
    const last = c.name.split(' ').slice(-1).join(' ');
    document.getElementById('coach-suggest-out').innerHTML = mism.length
      ? `<strong>${esc(last)}'s recommendation (${esc(c.style)}):</strong> switch `
        + mism.map(r => `${esc(r.category)} to <strong>${esc(r.coach_wants)}</strong>`).join('; ')
        + `. Or hand him the whiteboard and let him install it all.`
      : `He's happy — all seven modules already match his ${esc(c.style)} preferences.`;
  };
  document.getElementById('coach-enforce').onclick = async e => {
    e.target.disabled = true;
    await postJSON('/api/tactics/coach', {mode: 'enforce'});
    document.getElementById('coach-suggest-out').textContent =
      'Whiteboard is yours. He will coach your systems and stop adjusting mid-game.';
    setTimeout(loadTactics, 900);
  };
  document.getElementById('coach-takeover').onclick = async e => {
    e.target.disabled = true;
    await postJSON('/api/tactics/coach', {mode: 'takeover'});
    setTimeout(loadTactics, 900);
  };
}

/* ---- practice (unchanged) ---- */
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

document.getElementById('practice-save').addEventListener('click', async e => {
  const btn = e.target;
  btn.disabled = true;
  try {
    await postJSON('/api/tactics/practice', {
      focus: practiceState.focus,
      intensity: practiceState.intensity,
      bag_skate: document.getElementById('bag-skate').checked,
    });
  } catch (err) { console.error(err); }
  btn.disabled = false;
});

loadTactics();

(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select, label')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
