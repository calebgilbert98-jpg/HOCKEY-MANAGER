/* Puck Dynasty web offer sheets — web port of OfferSheetWindow */
let OS_TARGETS = [];
let OS_SELECTED = null;
let OS_WINDOW = {ok: false, reason: ''};
let OS_PREVIEW_TIMER = null;
let OS_RESULT_TIMER = null;

function money(n) {
  n = Math.round(n || 0);
  return '$' + n.toLocaleString('en-US');
}

async function loadTargets() {
  try {
    const res = await fetch('/api/offer_sheets/targets');
    const data = await res.json();
    OS_TARGETS = data.targets || [];
    OS_WINDOW = data.window || {};
    const capSpace = data.cap_space || 0;
    document.getElementById('os-count').textContent =
      OS_TARGETS.length + (OS_TARGETS.length === 1 ? ' target' : ' targets');
    const st = document.getElementById('os-status');
    const winTxt = OS_WINDOW.ok ? 'window OPEN (Jul 1 – Dec 1)'
      : 'window CLOSED — ' + (OS_WINDOW.reason || 'unknown reason');
    st.innerHTML = `${esc(winTxt)} &nbsp;•&nbsp; ${OS_TARGETS.length} unsigned RFA${OS_TARGETS.length === 1 ? '' : 's'} on the market &nbsp;•&nbsp; Your cap space: <b>${money(capSpace)}</b>`;
    renderList();
  } catch (e) {
    console.error(e);
    document.getElementById('os-status').textContent = 'Could not load offer-sheet targets.';
  }
}

function renderList() {
  const list = document.getElementById('os-list');
  list.innerHTML = '';
  if (!OS_TARGETS.length) {
    list.innerHTML = '<div class="os-empty">No unsigned RFAs on rival clubs right now.</div>';
    return;
  }
  for (const t of OS_TARGETS) {
    const el = document.createElement('div');
    el.className = 'os-row' + (OS_SELECTED && OS_SELECTED.id === t.id ? ' sel' : '');
    el.innerHTML = `
      <div class="os-name">${esc(t.name)}</div>
      <div class="os-sub">${esc(t.position)} · Age ${t.age} · ${esc(t.team_name)} · ${esc(t.tier)}</div>
      <div class="os-market">Est. value ${money(t.market)}/yr</div>`;
    el.addEventListener('click', () => selectTarget(t));
    list.appendChild(el);
  }
}

function selectTarget(t) {
  OS_SELECTED = t;
  document.getElementById('os-result').textContent = '';
  document.getElementById('os-detail').textContent =
    `${t.name} — ${t.position}, age ${t.age}, ${t.tier}\nRights held by: ${t.team_name}\nEngine's market read: ${money(t.market)}/yr`;
  // Start the AAV at his market read (desktop behavior).
  const aav = Math.max(1.0, Math.min(12.0, (t.market || 4e6) / 1e6));
  document.getElementById('os-aav').value = aav;
  renderList();
  refreshPreview();
}

function currentTerms() {
  const aav = parseFloat(document.getElementById('os-aav').value) || 4;
  const years = parseInt(document.getElementById('os-years').value) || 4;
  document.getElementById('os-aav-val').textContent = '$' + aav.toFixed(1) + 'M';
  document.getElementById('os-years-val').textContent = years + (years === 1 ? ' yr' : ' yrs');
  return {aav: Math.round(aav * 1e6), years};
}

function schedulePreview() {
  clearTimeout(OS_PREVIEW_TIMER);
  OS_PREVIEW_TIMER = setTimeout(refreshPreview, 250);
}

async function refreshPreview() {
  if (!OS_SELECTED) return;
  const {aav, years} = currentTerms();
  const btn = document.getElementById('os-present');
  btn.disabled = true;
  try {
    const res = await fetch(
      `/api/offer_sheets/preview?player_id=${encodeURIComponent(OS_SELECTED.id)}&aav=${aav}&years=${years}`);
    const data = await res.json();
    if (!data.ok) {
      document.getElementById('os-comp').textContent = data.error || 'Preview unavailable.';
      return;
    }
    const comp = data.compensation || {};
    const compLines = (comp.lines || []).map(l =>
      `<div class="os-line ${l.ok ? 'ok' : 'bad'}">${l.ok ? '✅' : '❌'} ${esc(l.text)}</div>`).join('');
    document.getElementById('os-comp').innerHTML =
      `<div class="os-comp-label">${esc(comp.label || '')}</div>${compLines || '<div class="os-line">No picks change hands.</div>'}`;
    const checks = (data.checks || []).map(c =>
      `<div class="os-line ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✅' : '❌'} ${esc(c.text)}</div>`).join('');
    document.getElementById('os-checks').innerHTML = checks;
    document.getElementById('os-interest').textContent = data.interest ? '📣 ' + data.interest : '';
    btn.disabled = !data.valid;
  } catch (e) {
    console.error(e);
  }
}

async function presentOfferSheet() {
  if (!OS_SELECTED) return;
  const {aav, years} = currentTerms();
  const btn = document.getElementById('os-present');
  const resEl = document.getElementById('os-result');
  if (!confirm(`Present an offer sheet to ${OS_SELECTED.name} (${money(aav)}/yr × ${years}y)?`)) return;
  btn.disabled = true;
  resEl.textContent = 'Presenting…';
  try {
    const res = await fetch('/api/offer_sheets/present', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_id: OS_SELECTED.id, aav, years}),
    });
    const data = await res.json();
    if (!data.ok) {
      resEl.textContent = '❌ ' + (data.error || 'Could not present the sheet.');
      refreshPreview();
      return;
    }
    pollResult();
  } catch (e) {
    console.error(e);
    resEl.textContent = '❌ Failed to present the sheet.';
    refreshPreview();
  }
}

async function pollResult(attempts = 0) {
  const resEl = document.getElementById('os-result');
  try {
    const res = await fetch('/api/offer_sheets/result');
    const data = await res.json();
    const r = data.result;
    if (r && r.marker === 'present_offer_sheet') {
      if (r.ok) {
        resEl.textContent = '🎉 ' + r.summary;
        OS_SELECTED = null;
        document.getElementById('os-detail').textContent = 'Select a player on the left.';
        document.getElementById('os-present').disabled = true;
      } else {
        resEl.textContent = '❌ ' + r.summary;
        refreshPreview();
      }
      loadTargets();
      return;
    }
  } catch (e) { console.error(e); }
  if (attempts < 40) {
    clearTimeout(OS_RESULT_TIMER);
    OS_RESULT_TIMER = setTimeout(() => pollResult(attempts + 1), 1000);
  } else {
    resEl.textContent = 'Still processing — check the inbox/news for the outcome.';
    refreshPreview();
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'}[c]));
}

document.getElementById('os-aav').addEventListener('input', () => { currentTerms(); schedulePreview(); });
document.getElementById('os-years').addEventListener('input', () => { currentTerms(); schedulePreview(); });
document.getElementById('os-present').addEventListener('click', presentOfferSheet);

loadTargets();

// Shared heartbeat.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
