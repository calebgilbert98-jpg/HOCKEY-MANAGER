/* Puck Dynasty web contracts */
let contractsTab = 'all';
async function loadContracts() {
  try {
    const res = await fetch('/api/contracts?tab=' + contractsTab);
    const data = await res.json();
    renderContracts(data.contracts || [], data.summary || {});
    const exp = (data.contracts || []).filter(c => c.expiring).length;
    const badge = document.getElementById('exp-badge');
    if (badge) badge.textContent = contractsTab === 'all' ? exp || '' : '';
  } catch (e) { console.error(e); }
}
document.getElementById('contracts-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#contracts-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  contractsTab = b.dataset.tab;
  loadContracts();
});
document.getElementById('btn-auto-neg').addEventListener('click', async () => {
  if (!confirm('Auto-negotiate extensions with all expiring contracts? Results will arrive in your inbox.')) return;
  await fetch('/api/contracts/auto_negotiate', { method: 'POST' });
  alert('Auto-negotiation queued — check your inbox for results.');
});

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
      <div class="c-name">${c.id ? `<span class="clickable-text" data-href="/player/${esc(c.id)}" title="Open player profile">${esc(c.name)}</span>` : esc(c.name)}${clauses.length ? ' <span class="c-clause">' + clauses.map(esc).join(' · ') + '</span>' : ''}</div>
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
          this.el('ext-note').textContent = 'Extension sent — waiting on the agent…';
          const st = await NegModal.track(this.playerId);
          if (st) {
            this.close();
            NegModal.open(this.playerId, st);
          } else {
            this.el('ext-note').textContent = 'The game thread did not respond — any talks are in your inbox.';
            btn.disabled = false;
            btn.textContent = 'Extend';
          }
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


/* v3 multi-day negotiation modal: shows the offer thread (your offers vs
   the agent's counter) with Accept / Counter / Walk away, all in-page
   via /api/contracts/negotiate. Never a desktop window. */
const NegModal = {
  playerId: null,
  state: null,
  liveTimer: null,
  sending: false,
  counterMode: false,

  el(id) { return document.getElementById(id); },

  /* After an offer is queued: wait for the game thread to stash the
     negotiation state, resolving with it (null on timeout). */
  async track(playerId) {
    for (let i = 0; i < 14; i++) {
      await new Promise(r => setTimeout(r, 500));
      try {
        const res = await fetch('/api/contracts/negotiation?player_id=' + encodeURIComponent(playerId));
        const data = await res.json();
        if (data && data.status && data.status !== 'none') return data;
      } catch (e) {}
    }
    return null;
  },

  open(playerId, state) {
    this.playerId = playerId;
    this.state = state || null;
    this.sending = false;
    this.counterMode = false;
    this.el('neg-counter-fields').hidden = true;
    this.el('neg-counter').textContent = 'Counter';
    this.el('neg-modal').hidden = false;
    this.el('neg-note').textContent = '';
    this.paint();
    this.startLive();
  },

  close() {
    this.el('neg-modal').hidden = true;
    this.stopLive();
  },

  /* While the modal is open, keep the thread in sync (the desktop side
     can also advance a negotiation). */
  startLive() {
    this.stopLive();
    this.liveTimer = setInterval(async () => {
      if (this.el('neg-modal').hidden || this.sending) return;
      try {
        const res = await fetch('/api/contracts/negotiation?player_id=' + encodeURIComponent(this.playerId));
        const data = await res.json();
        if (data && data.status && data.status !== 'none' &&
            JSON.stringify(data) !== JSON.stringify(this.state)) {
          this.state = data;
          this.paint();
        }
      } catch (e) {}
    }, 3000);
  },

  stopLive() {
    if (this.liveTimer) { clearInterval(this.liveTimer); this.liveTimer = null; }
  },

  async fetchState() {
    const res = await fetch('/api/contracts/negotiation?player_id=' + encodeURIComponent(this.playerId));
    return res.json();
  },

  /* Poll until the state moves off its pre-op snapshot (the main thread
     drains the command queue, so the verdict lands shortly after). */
  async waitForChange(pred, tries) {
    for (let i = 0; i < (tries || 14); i++) {
      await new Promise(r => setTimeout(r, 500));
      try {
        const data = await this.fetchState();
        if (data && data.status && data.status !== 'none' && pred(data)) {
          this.state = data;
          return data;
        }
      } catch (e) {}
    }
    return null;
  },

  offerStr(o) {
    return `${o.years} yr${o.years > 1 ? 's' : ''} × ${salaryStr(o.aav)}/yr`;
  },

  threadHtml(st) {
    let h = '';
    (st.your_offers || []).forEach((o, i) => {
      h += `<div class="neg-msg you"><div class="neg-who">You · offer ${i + 1}</div>${esc(this.offerStr(o))}</div>`;
    });
    if (st.status === 'countered' && st.counter_terms) {
      h += `<div class="neg-msg agent"><div class="neg-who">Agent · counter</div>Wants ${esc(this.offerStr(st.counter_terms))}</div>`;
    } else if (st.agent_ask && !((st.your_offers || []).length)) {
      h += `<div class="neg-msg agent"><div class="neg-who">Agent · ask</div>${salaryStr(st.agent_ask)}/yr</div>`;
    }
    if (st.status === 'accepted') h += `<div class="neg-msg sys">Deal agreed ✓</div>`;
    if (st.status === 'refused') h += `<div class="neg-msg sys">Talks broke down.</div>`;
    if (st.status === 'walked') h += `<div class="neg-msg sys">You walked away — talks closed.</div>`;
    if (st.status === 'awaiting_agent') h += `<div class="neg-msg sys">Waiting on the agent…</div>`;
    return h || '<div class="neg-msg sys">No offers yet.</div>';
  },

  paint() {
    const st = this.state;
    if (!st) return;
    this.el('neg-player').textContent = st.player_name || '—';
    const c = st.counter_terms;
    const active = st.status === 'countered';
    this.el('neg-ask').textContent =
      (active && c) ? `Agent's counter: ${this.offerStr(c)}`
                    : (st.note || 'Contract negotiation');
    this.el('neg-thread').innerHTML = this.threadHtml(st);
    ['neg-accept', 'neg-counter', 'neg-walk'].forEach(id => {
      this.el(id).style.display = active ? '' : 'none';
    });
    if (active && c) {
      this.el('neg-accept').textContent = `Accept ${salaryStr(c.aav)}/yr`;
      if (!this.counterMode) {
        this.el('neg-years').value = Math.min(7, Math.max(1, c.years));
        this.el('neg-aav').value = String(c.aav);
      }
    }
    this.paintCounterFields();
    if (!active && st.note) this.el('neg-note').textContent = st.note;
    this.setBusy(this.sending);
  },

  paintCounterFields() {
    const years = parseInt(this.el('neg-years').value, 10) || 1;
    this.el('neg-years-val').textContent = `${years} yr${years > 1 ? 's' : ''}`;
    const aav = parseInt(String(this.el('neg-aav').value).replace(/[^0-9]/g, ''), 10) || 0;
    this.el('neg-aav-val').textContent = salaryStr(aav) + '/yr';
  },

  setBusy(b) {
    ['neg-accept', 'neg-counter', 'neg-walk'].forEach(id => {
      this.el(id).disabled = b;
    });
  },

  async post(action, extra) {
    const body = Object.assign({player_id: this.playerId, action}, extra || {});
    const res = await fetch('/api/contracts/negotiate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    return res.json();
  },

  async accept() {
    if (this.sending) return;
    this.sending = true; this.setBusy(true);
    this.el('neg-note').textContent = 'Accepting the counter…';
    try {
      const r = await this.post('accept');
      if (!r.ok) {
        this.el('neg-note').textContent = 'Could not accept: ' + (r.error || 'unknown error');
      } else {
        const st = await this.waitForChange(d => d.status !== 'countered');
        if (st) this.paint();
        else this.el('neg-note').textContent = 'No response from the game thread — try again.';
      }
    } catch (e) {
      this.el('neg-note').textContent = 'Network error.';
    }
    this.sending = false; this.setBusy(false);
  },

  async onCounter() {
    if (this.sending) return;
    if (!this.counterMode) {
      this.counterMode = true;
      this.el('neg-counter-fields').hidden = false;
      this.el('neg-counter').textContent = 'Send counter';
      this.paintCounterFields();
      return;
    }
    const years = parseInt(this.el('neg-years').value, 10) || 1;
    const aav = parseInt(String(this.el('neg-aav').value).replace(/[^0-9]/g, ''), 10) || 0;
    if (aav <= 0) { this.el('neg-note').textContent = 'Enter an AAV for your counter-offer.'; return; }
    this.sending = true; this.setBusy(true);
    this.el('neg-note').textContent = 'Sending your counter…';
    try {
      const prevOffers = (this.state.your_offers || []).length;
      const r = await this.post('counter', {years, aav});
      if (!r.ok) {
        this.el('neg-note').textContent = 'Counter refused: ' + (r.error || 'unknown error');
      } else {
        const st = await this.waitForChange(d => (d.your_offers || []).length > prevOffers);
        if (st) {
          this.counterMode = false;
          this.el('neg-counter-fields').hidden = true;
          this.el('neg-counter').textContent = 'Counter';
          this.paint();
        } else {
          this.el('neg-note').textContent = 'No response from the game thread — try again.';
        }
      }
    } catch (e) {
      this.el('neg-note').textContent = 'Network error.';
    }
    this.sending = false; this.setBusy(false);
  },

  async walk() {
    if (this.sending) return;
    this.sending = true; this.setBusy(true);
    this.el('neg-note').textContent = 'Walking away…';
    try {
      const r = await this.post('walk');
      if (!r.ok) {
        this.el('neg-note').textContent = 'Could not walk away: ' + (r.error || 'unknown error');
      } else {
        const st = await this.waitForChange(d => d.status === 'walked');
        if (st) this.paint();
        else this.el('neg-note').textContent = 'No response from the game thread — try again.';
      }
    } catch (e) {
      this.el('neg-note').textContent = 'Network error.';
    }
    this.sending = false; this.setBusy(false);
  },

  bind() {
    const el = this.el.bind(this);
    el('neg-close').addEventListener('click', () => this.close());
    el('neg-modal').addEventListener('click', e => {
      if (e.target === el('neg-modal')) this.close();
    });
    el('neg-accept').addEventListener('click', () => this.accept());
    el('neg-counter').addEventListener('click', () => this.onCounter());
    el('neg-walk').addEventListener('click', () => this.walk());
    el('neg-years').addEventListener('input', () => this.paintCounterFields());
    el('neg-aav').addEventListener('input', () => this.paintCounterFields());
    el('neg-aav-down').addEventListener('click', () => {
      const v = parseInt(String(el('neg-aav').value).replace(/[^0-9]/g, ''), 10) || 0;
      el('neg-aav').value = String(Math.max(0, v - 100000));
      this.paintCounterFields();
    });
    el('neg-aav-up').addEventListener('click', () => {
      const v = parseInt(String(el('neg-aav').value).replace(/[^0-9]/g, ''), 10) || 0;
      el('neg-aav').value = String(v + 100000);
      this.paintCounterFields();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !el('neg-modal').hidden) this.close();
    });
  }
};
NegModal.bind();

loadContracts().then(preselectFromURL);

/* Pre-selection from context menu: /contracts?player=<id> opens the
 * extension dialog for that player. */
async function preselectFromURL() {
  try {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get('player');
    if (!pid) return;
    let name = 'Player';
    try {
      const pr = await fetch('/api/player/' + encodeURIComponent(pid));
      if (pr.ok) {
        const pd = await pr.json();
        name = (pd.header && pd.header.name) || name;
      }
    } catch (e) { /* ignore */ }
    extendContract(null, pid, name);
  } catch (e) { console.error(e); }
}

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
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
