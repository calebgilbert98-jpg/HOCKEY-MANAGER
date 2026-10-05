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
      <button class="btn-offer" data-id="${esc(p.id)}">Make offer</button>
      <button class="tb-mini" data-analysis="${esc(p.id)}" data-nm="${esc(p.name)}">Analysis</button>
      <label class="cmp-label"><input type="checkbox" class="cmp-check" data-pid="${esc(p.id)}"> Compare</label>`;
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
          this.el('offer-note').textContent = 'Offer sent — waiting on the agent…';
          const st = await NegModal.track(this.playerId);
          if (st) {
            this.close();
            NegModal.open(this.playerId, st);
          } else {
            this.el('offer-note').textContent = 'The game thread did not respond — any talks are in your inbox.';
            btn.disabled = false;
            btn.textContent = 'Sign';
          }
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

loadFA();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

/* ---------- 3-tab navigation ---------- */
(function initFaTabs() {
  const tabs = document.getElementById('fa-tabs');
  if (!tabs) return;
  tabs.addEventListener('click', e => {
    const b = e.target.closest('.tb-tab');
    if (!b) return;
    tabs.querySelectorAll('.tb-tab').forEach(t => t.classList.remove('active'));
    b.classList.add('active');
    document.querySelectorAll('#fa-tab-players,#fa-tab-staff,#fa-tab-market')
      .forEach(p => p.classList.add('hidden'));
    document.getElementById('fa-tab-' + b.dataset.tab).classList.remove('hidden');
    if (b.dataset.tab === 'staff') loadStaff();
    if (b.dataset.tab === 'market') loadMarket();
  });
})();

/* ---------- Staff tab ---------- */
async function loadStaff() {
  const q = document.getElementById('staff-q').value || '';
  const dept = document.getElementById('staff-dept').value || 'All';
  try {
    const res = await fetch('/api/free_agents/staff?' + new URLSearchParams({ q, department: dept }));
    const data = await res.json();
    renderStaff(data.staff || []);
  } catch (e) { console.error(e); }
}
function renderStaff(staff) {
  const host = document.getElementById('staff-list');
  host.innerHTML = staff.length ? '' : '<div class="block-empty">No free-agent staff found.</div>';
  for (const s of staff) {
    const el = document.createElement('div');
    el.className = 'fa-card';
    el.innerHTML = `
      <div class="fa-head">
        <div class="fa-ov" style="--c:${barColor(s.overall)}">${s.overall}</div>
        <div><div class="fa-name">${esc(s.name)}</div>
        <div class="fa-sub">${esc(s.role)} · ${esc(s.department)} · ${s.experience} yrs exp</div></div>
      </div>
      <div class="fa-actions">
        <button class="tb-mini" data-hire="${esc(s.id)}" data-nm="${esc(s.name)}">Hire</button>
      </div>`;
    host.appendChild(el);
  }
}
document.getElementById('staff-q').addEventListener('input', () => loadStaff());
document.getElementById('staff-dept').addEventListener('change', () => loadStaff());
document.getElementById('staff-list').addEventListener('click', async e => {
  const b = e.target.closest('[data-hire]');
  if (!b) return;
  const salary = prompt(`Offer annual salary for ${b.dataset.nm} (e.g. 150000):`, '150000');
  if (!salary) return;
  await fetch('/api/free_agents/staff/hire', { method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ staff_id: b.dataset.hire, salary: parseInt(salary) || 0, years: 3 }) });
  alert('Hire offer queued.');
  setTimeout(loadStaff, 800);
});

/* ---------- Market Overview tab ---------- */
async function loadMarket() {
  try {
    const res = await fetch('/api/free_agents/market');
    const d = await res.json();
    const host = document.getElementById('market-overview');
    const posRows = Object.entries(d.by_position || {})
      .sort((a, b) => b[1] - a[1])
      .map(([p, n]) => `<div class="mk-row"><span>${esc(p)}</span><b>${n}</b></div>`).join('');
    const topRows = (d.top_available || []).map(p =>
      `<div class="mk-row"><span>${esc(p.name)} <span class="dim">${esc(p.position)} · ${p.overall} OVR</span></span>
       <b>${salaryStr(p.ask)}</b></div>`).join('');
    host.innerHTML = `
      <div class="mk-grid">
        <div class="mk-card"><h3>Market Size</h3><div class="mk-big">${d.total}</div>
          <div class="dim">${d.by_type.UFA} UFA · ${d.by_type.RFA} RFA</div></div>
        <div class="mk-card"><h3>Avg Asking</h3><div class="mk-big">${salaryStr(d.avg_ask)}</div></div>
        <div class="mk-card"><h3>By Position</h3>${posRows}</div>
        <div class="mk-card"><h3>Top Available</h3>${topRows}</div>
      </div>`;
  } catch (e) { console.error(e); }
}

/* ---------- Market Analysis modal ---------- */
let analysisData = null, analysisTab = 'value';
async function openAnalysis(pid, name) {
  try {
    const res = await fetch('/api/free_agents/analysis?player_id=' + encodeURIComponent(pid));
    const d = await res.json();
    if (!d.ok) return alert(d.error || 'Analysis unavailable');
    analysisData = d;
    analysisTab = 'value';
    document.getElementById('analysis-title').textContent = 'Market Analysis — ' + name;
    document.querySelectorAll('#analysis-tabs .tb-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.atab === 'value'));
    renderAnalysis();
    document.getElementById('analysis-modal').hidden = false;
  } catch (e) { console.error(e); }
}
function renderAnalysis() {
  const d = analysisData, host = document.getElementById('analysis-body');
  if (analysisTab === 'value') {
    const v = d.value;
    host.innerHTML = `
      <p>Market value: <b>${'$' + v.market_value.toLocaleString()}</b><br>
      Asking: <b>${'$' + v.ask.toLocaleString()}</b></p>
      <p style="color:${v.color === 'green' ? '#4CAF50' : v.color === 'red' ? '#F44336' : '#3B82F6'}">
      <b>${esc(v.verdict)}</b></p>`;
  } else if (analysisTab === 'comps') {
    host.innerHTML = d.comparables.length
      ? '<ul>' + d.comparables.map(c =>
          `<li><b>${esc(c.name)}</b> — ${c.overall} OVR, age ${c.age}, ask ${salaryStr(c.ask)}</li>`).join('') + '</ul>'
      : '<p class="dim">No comparable players found.</p>';
  } else {
    const p = d.projection;
    host.innerHTML = `<p>Suggested term: <b>${p.years} years</b><br>
      Projected AAV range: <b>${salaryStr(p.aav_low)} – ${salaryStr(p.aav_high)}</b></p>`;
  }
}
document.getElementById('analysis-tabs').addEventListener('click', e => {
  const b = e.target.closest('.tb-tab');
  if (!b) return;
  document.querySelectorAll('#analysis-tabs .tb-tab').forEach(t => t.classList.remove('active'));
  b.classList.add('active');
  analysisTab = b.dataset.atab;
  renderAnalysis();
});
document.getElementById('analysis-close').addEventListener('click', () =>
  document.getElementById('analysis-modal').hidden = true);

/* ---------- Compare ---------- */
const cmpSel = new Set();
function bindCompare() {
  document.getElementById('fa-list').addEventListener('change', e => {
    const cb = e.target.closest('input.cmp-check');
    if (!cb) return;
    if (cb.checked) { if (cmpSel.size < 3) cmpSel.add(cb.dataset.pid); else cb.checked = false; }
    else cmpSel.delete(cb.dataset.pid);
    document.getElementById('cmp-n').textContent = cmpSel.size;
    document.getElementById('btn-compare').disabled = !cmpSel.size;
  });
  document.getElementById('btn-compare').addEventListener('click', async () => {
    if (!cmpSel.size) return;
    const res = await fetch('/api/free_agents/compare?player_ids=' + [...cmpSel].map(encodeURIComponent).join(','));
    const d = await res.json();
    const ps = d.players || [];
    const attrs = ['overall', 'age', 'ask'];
    const extra = ['shooting_accuracy', 'passing', 'skating', 'checking', 'defensive_awareness'];
    let html = '<table class="cmp-table"><tr><th></th>' +
      ps.map(p => `<th>${esc(p.name)}</th>`).join('') + '</tr>';
    for (const a of attrs.concat(extra)) {
      html += `<tr><td class="dim">${esc(a)}</td>` + ps.map(p => {
        let v = p[a];
        if (v == null && p.compare_attrs) v = p.compare_attrs[a];
        if (a === 'ask') v = salaryStr(v);
        return `<td>${esc(v == null ? '—' : v)}</td>`;
      }).join('') + '</tr>';
    }
    html += '</table>';
    document.getElementById('compare-body').innerHTML = html;
    document.getElementById('compare-modal').hidden = false;
  });
  document.getElementById('compare-close').addEventListener('click', () =>
    document.getElementById('compare-modal').hidden = true);
}
bindCompare();

/* Hook analysis buttons into player cards (delegated) */
document.getElementById('fa-list').addEventListener('click', e => {
  const b = e.target.closest('[data-analysis]');
  if (b) openAnalysis(b.dataset.analysis, b.dataset.nm);
});
