/* Puck Dynasty web free agents */
let FA_PLAYERS = [];
let FA_POS = 'ALL';
let FA_TYPE = 'ALL';
let FA_SORT = 'overall';

async function loadFA() {
  try {
    const res = await fetch('/api/free_agents');
    const data = await res.json();
    FA_PLAYERS = data.players || [];
    bindFilters();
    renderFA();
  } catch (e) { console.error(e); }
}

function bindFilters() {
  document.querySelectorAll('#pos-filter .fa-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#pos-filter .fa-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      FA_POS = btn.dataset.pos;
      renderFA();
    });
  });
  document.querySelectorAll('#type-filter .fa-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#type-filter .fa-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      FA_TYPE = btn.dataset.type;
      renderFA();
    });
  });
  document.getElementById('fa-sort').addEventListener('change', e => {
    FA_SORT = e.target.value;
    renderFA();
  });
}

function barColor(v) {
  if (v >= 75) return '#4CAF50';
  if (v >= 60) return '#8BC34A';
  if (v >= 45) return '#FFC107';
  if (v >= 30) return '#FF9800';
  return '#F44336';
}

function salaryStr(s) {
  s = s || 0;
  return s >= 1e6 ? '$' + (s / 1e6).toFixed(2) + 'M'
                  : '$' + Math.round(s / 1e3) + 'K';
}

function matchesPos(p) {
  if (FA_POS === 'ALL') return true;
  const pos = String(p.position || '');
  if (FA_POS === 'D') return /D\b|LD|RD|DEF/i.test(pos);
  return pos.split(/[\/, ]+/).includes(FA_POS);
}

function filtered() {
  let list = FA_PLAYERS.filter(p =>
    matchesPos(p) && (FA_TYPE === 'ALL' || p.fa_type === FA_TYPE));
  switch (FA_SORT) {
    case 'ask-asc': list.sort((a, b) => a.ask - b.ask); break;
    case 'ask-desc': list.sort((a, b) => b.ask - a.ask); break;
    case 'age': list.sort((a, b) => a.age - b.age); break;
    default: list.sort((a, b) => b.overall - a.overall);
  }
  return list;
}

function renderFA() {
  const list = document.getElementById('fa-list');
  const players = filtered();
  document.getElementById('fa-count').textContent =
    players.length + (players.length === 1 ? ' player' : ' players') + ' available';
  list.innerHTML = '';
  if (!players.length) {
    const el = document.createElement('div');
    el.className = 'fa-empty';
    el.textContent = 'No free agents match the current filters.';
    list.appendChild(el);
    return;
  }
  for (const p of players) {
    const el = document.createElement('div');
    el.className = 'fa-card';
    el.innerHTML = `
      <div class="fa-ov" style="--c:${barColor(p.overall)}">${p.overall}</div>
      <div class="fa-info">
        <div class="fa-name">${esc(p.name)} <span class="fa-tag">${esc(p.fa_type)}</span></div>
        <div class="fa-sub">${esc(p.position)} · Age ${p.age} · Asking ${salaryStr(p.ask)}</div>
      </div>
      <div class="fa-bar"><span style="width:${Math.min(100, p.overall)}%;background:${barColor(p.overall)}"></span></div>
      <button class="btn-offer" data-id="${esc(p.id)}">Make offer</button>`;
    const btn = el.querySelector('.btn-offer');
    btn.addEventListener('click', () => makeOffer(btn, p.id, p.ask, p.name));
    list.appendChild(el);
  }
}

/* v2 offer modal: in-page negotiation preview, never a desktop window */
const OfferModal = {
  playerId: null,
  data: null,
  debounce: null,

  el(id) { return document.getElementById(id); },

  open(playerId) {
    this.playerId = playerId;
    this.data = null;
    this._primed = false;
    const aavInput = this.el('offer-aav');
    aavInput.value = '';
    aavInput.dataset.touched = '';
    this.el('offer-modal').hidden = false;
    this.el('offer-submit').disabled = true;
    this.el('offer-note').textContent = '';
    this.el('offer-ask').textContent = 'Loading terms…';
    this.el('offer-cap').textContent = '';
    this.refresh();
  },

  close() {
    this.el('offer-modal').hidden = true;
    if (this.debounce) { clearTimeout(this.debounce); this.debounce = null; }
  },

  aavStep() {
    const d = this.data;
    if (!d) return 250000;
    const span = (d.max_salary - d.min_salary) / 40;
    return Math.max(100000, Math.round(span / 50000) * 50000);
  },

  terms() {
    const years = parseInt(this.el('offer-years').value, 10) || 1;
    let aav = parseInt(String(this.el('offer-aav').value).replace(/[^0-9]/g, ''), 10);
    if (!aav || aav < 0) aav = 0;
    return {years, aav};
  },

  async refresh() {
    const {years, aav} = this.terms();
    const pid = encodeURIComponent(this.playerId);
    const qs = aav > 0 ? `?player_id=${pid}&years=${years}&aav=${aav}`
                       : `?player_id=${pid}&years=${years}`;
    try {
      const res = await fetch('/api/free_agents/demands' + qs);
      const d = await res.json();
      if (!d.ok) { this.showError(d.error || 'Could not load terms'); return; }
      this.data = d;
      this.paint();
    } catch (e) {
      console.error(e);
      this.showError('Could not load terms (network error)');
    }
  },

  refreshDebounced() {
    if (this.debounce) clearTimeout(this.debounce);
    this.debounce = setTimeout(() => this.refresh(), 250);
  },

  showError(msg) {
    this.el('offer-ask').textContent = msg;
    this.el('offer-cap').textContent = '';
    this.el('offer-submit').disabled = true;
    this.el('offer-note').textContent = msg;
  },

  paint() {
    const d = this.data, p = d.player;
    if (!this._primed) {
      const sug = d.years_suggested || 4;
      if (parseInt(this.el('offer-years').value, 10) !== sug) {
        this.el('offer-years').value = sug;
        this.refreshDebounced(); // re-validate the preview at the suggested term
      }
      this._primed = true;
    }
    this.el('offer-player').textContent =
      `${p.name} · ${p.position} · Age ${p.age} · ${p.overall} OVR (${p.fa_type})`;
    this.el('offer-ask').textContent = `Agent's ask: ${salaryStr(d.ask)}/yr`;
    // bounds
    const yr = this.el('offer-years');
    yr.min = d.years_min; yr.max = d.years_max;
    if (parseInt(yr.value, 10) < d.years_min) yr.value = d.years_min;
    if (parseInt(yr.value, 10) > d.years_max) yr.value = d.years_max;
    const t = this.terms();
    yr.value = Math.min(Math.max(t.years, d.years_min), d.years_max);
    this.el('offer-years-val').textContent = `${yr.value} yr${yr.value > 1 ? 's' : ''}`;
    if (t.aav === 0 || !this.el('offer-aav').dataset.touched) {
      this.el('offer-aav').value = String(d.ask);
      this.el('offer-aav').dataset.touched = '';
    }
    this.el('offer-aav-val').textContent = salaryStr(t.aav || d.ask) + '/yr';
    this.el('offer-aav-hint').textContent =
      `Allowed: ${salaryStr(d.min_salary)} – ${salaryStr(d.max_salary)}/yr · ` +
      `Term: ${d.years_min}–${d.years_max} yrs`;
    // cap preview
    const c = d.preview;
    const space = c.space_after;
    const fit = c.fits;
    this.el('offer-cap').innerHTML =
      `Cap space: <b>${salaryStr(c.current_space)}</b> → <b class="${fit ? 'good' : 'bad'}">${salaryStr(space)} after</b>` +
      ` <span class="cm-dim">(charge ${salaryStr(c.projected_charge)} / ${salaryStr(c.live_cap)})</span>`;
    this.el('offer-cap').classList.toggle('over', !fit);
    // validity
    let reason = d.valid_reason || '';
    if (!d.window.ok) reason = d.window.reason;
    else if (!d.eligibility.ok) reason = d.eligibility.reason;
    const canSign = d.valid && d.window.ok && d.eligibility.ok && fit;
    this.el('offer-submit').disabled = !canSign;
    this.el('offer-note').textContent = canSign
      ? (d.note || '')
      : (reason || 'These terms do not fit under the cap.');
  },

  async pollResult() {
    for (let i = 0; i < 12; i++) {
      await new Promise(r => setTimeout(r, 500));
      try {
        const res = await fetch('/api/contracts/result');
        const data = await res.json();
        if (data.result && data.result.marker === 'sign_free_agent_real') return data.result;
      } catch (e) {}
    }
    return null;
  },

  async submit() {
    const {years, aav} = this.terms();
    const btn = this.el('offer-submit');
    btn.disabled = true;
    btn.textContent = 'Sending…';
    try {
      const res = await fetch('/api/free_agents/offer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({player_id: this.playerId, years, aav})
      });
      const data = await res.json();
      if (data.ok) {
        this.el('offer-note').textContent = 'Offer sent — waiting for the game thread…';
        btn.textContent = 'Sent ✓';
        const outcome = await this.pollResult();
        if (outcome && outcome.ok === false) {
          this.el('offer-note').textContent = 'Offer refused: ' + (outcome.summary || 'failed validation');
          btn.disabled = false;
          btn.textContent = 'Sign';
        } else {
          this.el('offer-note').textContent = 'Offer queued ✓ — the agent will respond (qualifying offers enter the consideration period).';
          setTimeout(() => this.close(), 1200);
        }
      } else {
        this.el('offer-note').textContent = 'Could not send offer: ' + (data.error || 'unknown error');
        btn.disabled = false;
        btn.textContent = 'Sign';
      }
    } catch (e) {
      console.error(e);
      this.el('offer-note').textContent = 'Could not send offer (network error)';
      btn.disabled = false;
      btn.textContent = 'Sign';
    }
  },

  bind() {
    const el = this.el.bind(this);
    el('offer-close').addEventListener('click', () => this.close());
    el('offer-cancel').addEventListener('click', () => this.close());
    el('offer-modal').addEventListener('click', e => {
      if (e.target === el('offer-modal')) this.close();
    });
    el('offer-years').addEventListener('input', () => this.refreshDebounced());
    el('offer-aav').addEventListener('input', e => {
      e.target.dataset.touched = '1';
      this.refreshDebounced();
    });
    el('offer-aav-down').addEventListener('click', () => {
      const {aav} = this.terms();
      el('offer-aav').value = String(Math.max(0, aav - this.aavStep()));
      el('offer-aav').dataset.touched = '1';
      this.refresh();
    });
    el('offer-aav-up').addEventListener('click', () => {
      const {aav} = this.terms();
      el('offer-aav').value = String(aav + this.aavStep());
      el('offer-aav').dataset.touched = '1';
      this.refresh();
    });
    el('offer-submit').addEventListener('click', () => this.submit());
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !el('offer-modal').hidden) this.close();
    });
  }
};
OfferModal.bind();

async function makeOffer(btn, playerId, ask, name) {
  OfferModal.open(playerId);
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadFA();
