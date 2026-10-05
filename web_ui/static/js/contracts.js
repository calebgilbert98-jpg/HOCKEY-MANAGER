/* Puck Dynasty web contracts */
async function loadContracts() {
  try {
    const res = await fetch('/api/contracts');
    const data = await res.json();
    renderContracts(data.contracts || [], data.summary || {});
  } catch (e) { console.error(e); }
}

function salaryStr(s) {
  s = s || 0;
  return s >= 1e6 ? '$' + (s / 1e6).toFixed(2) + 'M'
                  : '$' + Math.round(s / 1e3) + 'K';
}

function termStr(years) {
  if (years <= 0) return 'Expiring / signed out';
  return years + (years === 1 ? ' yr' : ' yrs') + ' left';
}

function renderContracts(contracts, summary) {
  const list = document.getElementById('contracts-list');
  const n = summary.player_count != null ? summary.player_count : contracts.length;
  document.getElementById('contracts-count').textContent =
    n + (n === 1 ? ' player' : ' players') + ' under contract';
  const capLine = document.getElementById('cap-line');
  if (summary.cap_ceiling) {
    const used = summary.total_cap_hit || 0;
    const pct = Math.round(used / summary.cap_ceiling * 100);
    capLine.textContent =
      `Cap hit: ${salaryStr(used)} / ${salaryStr(summary.cap_ceiling)} (${pct}% used)`;
  }
  list.innerHTML = '';
  if (!contracts.length) {
    const el = document.createElement('div');
    el.className = 'contracts-empty';
    el.textContent = 'No contracts on the roster.';
    list.appendChild(el);
    return;
  }
  for (const c of contracts) {
    const el = document.createElement('div');
    el.className = 'c-row' + (c.expiring ? ' expiring' : '');
    const clauses = [];
    if (c.no_movement) clauses.push('NMC');
    if (c.no_trade) clauses.push('NTC');
    if (c.two_way) clauses.push('2-way');
    el.innerHTML = `
      <div class="c-name">${esc(c.name)}${clauses.length ? ' <span class="c-clause">' + clauses.map(esc).join(' · ') + '</span>' : ''}</div>
      <div class="c-pos">${esc(c.position)} · Age ${c.age}</div>
      <div class="c-hit">${salaryStr(c.cap_hit)}</div>
      <div class="c-term${c.expiring ? ' hot' : ''}">${esc(termStr(c.years_remaining))}${c.expiring ? ' ⚠' : ''}</div>
      <button class="btn-extend" data-id="${esc(c.id)}">Extend</button>`;
    const btn = el.querySelector('.btn-extend');
    btn.addEventListener('click', () => extendContract(btn, c.id, c.name));
    list.appendChild(el);
  }
}

/* v2 extension modal: in-page re-sign preview, never a desktop window */
const ExtModal = {
  playerId: null,
  data: null,
  debounce: null,
  _primed: false,

  el(id) { return document.getElementById(id); },

  open(playerId) {
    this.playerId = playerId;
    this.data = null;
    this._primed = false;
    const aavInput = this.el('ext-aav');
    aavInput.value = '';
    aavInput.dataset.touched = '';
    this.el('ext-modal').hidden = false;
    this.el('ext-submit').disabled = true;
    this.el('ext-note').textContent = '';
    this.el('ext-ask').textContent = 'Loading terms…';
    this.el('ext-cap').textContent = '';
    this.refresh();
  },

  close() {
    this.el('ext-modal').hidden = true;
    if (this.debounce) { clearTimeout(this.debounce); this.debounce = null; }
  },

  aavStep() {
    const d = this.data;
    if (!d) return 250000;
    const span = (d.max_salary - d.min_salary) / 40;
    return Math.max(100000, Math.round(span / 50000) * 50000);
  },

  terms() {
    const years = parseInt(this.el('ext-years').value, 10) || 1;
    let aav = parseInt(String(this.el('ext-aav').value).replace(/[^0-9]/g, ''), 10);
    if (!aav || aav < 0) aav = 0;
    return {years, aav};
  },

  async refresh() {
    const {years, aav} = this.terms();
    const pid = encodeURIComponent(this.playerId);
    const qs = aav > 0 ? `?player_id=${pid}&years=${years}&aav=${aav}`
                       : `?player_id=${pid}&years=${years}`;
    try {
      const res = await fetch('/api/contracts/extension_terms' + qs);
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
    this.el('ext-ask').textContent = msg;
    this.el('ext-cap').textContent = '';
    this.el('ext-submit').disabled = true;
    this.el('ext-note').textContent = msg;
  },

  paint() {
    const d = this.data, p = d.player;
    if (!this._primed) {
      const sug = Math.min(d.years_max, 5);
      if (parseInt(this.el('ext-years').value, 10) !== sug) {
        this.el('ext-years').value = sug;
        this.refreshDebounced();
      }
      this._primed = true;
    }
    this.el('ext-player').textContent =
      `${p.name} · ${p.position} · Age ${p.age} · ${p.overall} OVR`;
    this.el('ext-ask').textContent =
      `Current: ${salaryStr(p.cap_hit)}/yr × ${p.years_remaining} left · ` +
      `Likely accepts ${salaryStr(d.accept_band.low)}–${salaryStr(d.accept_band.high)}/yr`;
    const yr = this.el('ext-years');
    yr.min = d.years_min; yr.max = d.years_max;
    const t = this.terms();
    yr.value = Math.min(Math.max(t.years, d.years_min), d.years_max);
    this.el('ext-years-val').textContent = `${yr.value} yr${yr.value > 1 ? 's' : ''}`;
    if (t.aav === 0 || !this.el('ext-aav').dataset.touched) {
      this.el('ext-aav').value = String(d.aav_estimate);
      this.el('ext-aav').dataset.touched = '';
    }
    this.el('ext-aav-val').textContent = salaryStr(t.aav || d.aav_estimate) + '/yr';
    this.el('ext-aav-hint').textContent =
      `Allowed: ${salaryStr(d.min_salary)} – ${salaryStr(d.max_salary)}/yr · ` +
      `Term: ${d.years_min}–${d.years_max} yrs`;
    const c = d.preview;
    const fit = c.fits;
    this.el('ext-cap').innerHTML =
      `Cap space: <b>${salaryStr(c.current_space)}</b> → <b class="${fit ? 'good' : 'bad'}">${salaryStr(c.space_after)} after</b>` +
      ` <span class="cm-dim">(replaces ${salaryStr(p.cap_hit)}; charge ${salaryStr(c.projected_charge)} / ${salaryStr(c.live_cap)})</span>`;
    this.el('ext-cap').classList.toggle('over', !fit);
    let reason = d.valid_reason || '';
    if (!d.window.ok) reason = d.window.reason;
    const canExtend = d.valid && d.window.ok && fit;
    this.el('ext-submit').disabled = !canExtend;
    this.el('ext-note').textContent = canExtend
      ? (d.note || '')
      : (reason || 'These terms do not fit under the cap.');
  },

  async pollResult() {
    for (let i = 0; i < 12; i++) {
      await new Promise(r => setTimeout(r, 500));
      try {
        const res = await fetch('/api/contracts/result');
        const data = await res.json();
        if (data.result && data.result.marker === 'extend_contract_real') return data.result;
      } catch (e) {}
    }
    return null;
  },

  async submit() {
    const {years, aav} = this.terms();
    const btn = this.el('ext-submit');
    btn.disabled = true;
    btn.textContent = 'Sending…';
    try {
      const res = await fetch('/api/contracts/extend_real', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({player_id: this.playerId, years, aav})
      });
      const data = await res.json();
      if (data.ok) {
        this.el('ext-note').textContent = 'Extension sent — waiting for the game thread…';
        btn.textContent = 'Sent ✓';
        const outcome = await this.pollResult();
        if (outcome && outcome.ok === false) {
          this.el('ext-note').textContent = 'Extension refused: ' + (outcome.summary || 'failed validation');
          btn.disabled = false;
          btn.textContent = 'Extend';
        } else {
          this.el('ext-note').textContent = 'Extension queued ✓ — the player will accept or counter (extensions apply instantly on acceptance).';
          setTimeout(() => this.close(), 1200);
        }
      } else {
        this.el('ext-note').textContent = 'Could not send extension: ' + (data.error || 'unknown error');
        btn.disabled = false;
        btn.textContent = 'Extend';
      }
    } catch (e) {
      console.error(e);
      this.el('ext-note').textContent = 'Could not send extension (network error)';
      btn.disabled = false;
      btn.textContent = 'Extend';
    }
  },

  bind() {
    const el = this.el.bind(this);
    el('ext-close').addEventListener('click', () => this.close());
    el('ext-cancel').addEventListener('click', () => this.close());
    el('ext-modal').addEventListener('click', e => {
      if (e.target === el('ext-modal')) this.close();
    });
    el('ext-years').addEventListener('input', () => this.refreshDebounced());
    el('ext-aav').addEventListener('input', e => {
      e.target.dataset.touched = '1';
      this.refreshDebounced();
    });
    el('ext-aav-down').addEventListener('click', () => {
      const {aav} = this.terms();
      el('ext-aav').value = String(Math.max(0, aav - this.aavStep()));
      el('ext-aav').dataset.touched = '1';
      this.refresh();
    });
    el('ext-aav-up').addEventListener('click', () => {
      const {aav} = this.terms();
      el('ext-aav').value = String(aav + this.aavStep());
      el('ext-aav').dataset.touched = '1';
      this.refresh();
    });
    el('ext-submit').addEventListener('click', () => this.submit());
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !el('ext-modal').hidden) this.close();
    });
  }
};
ExtModal.bind();

async function extendContract(btn, playerId, name) {
  ExtModal.open(playerId);
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadContracts();
