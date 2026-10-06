/* Puck Dynasty web inbox — Gmail-style rows (matches the 2026-10-04 redesign)
   Batch A (2026-10-05): all 11 v0.18.4 interactive action types ported. */
let currentFilter = 'all';
let messages = [];
let openId = null;
let openMsg = null;

async function loadInbox(filter = 'all') {
  currentFilter = filter;
  document.querySelectorAll('#filters button').forEach(b =>
    b.classList.toggle('active', b.dataset.f === filter));
  try {
    const res = await fetch('/api/inbox?filter=' + encodeURIComponent(filter));
    messages = await res.json();
    renderList();
  } catch (e) { console.error(e); }
}

function indicator(m) {
  if (m.is_overdue || m.requires_response) return 'red';
  if (m.is_urgent || m.priority >= 4) return 'gold';
  if (m.is_important || m.priority >= 3) return 'gold';
  if (!m.is_read) return 'blue';
  return 'none';
}

function renderList() {
  const list = document.getElementById('msg-list');
  document.getElementById('inbox-count').textContent =
    messages.length + ' message' + (messages.length === 1 ? '' : 's');
  list.innerHTML = '';
  if (!messages.length) {
    list.innerHTML = '<div class="empty">Nothing here. Enjoy the quiet.</div>';
    return;
  }
  for (const m of messages) {
    const ind = indicator(m);
    const needsAction = m.is_overdue || m.requires_response;
    const row = document.createElement('div');
    row.className = 'msg-row' + (m.is_read ? '' : ' unread');
    row.innerHTML = `
      <span class="bar ${ind}"></span>
      <div class="msg-text">
        <div class="msg-sender">${esc(m.sender)}</div>
        <div class="msg-subj">${esc(m.subject)}${m.snippet ? ' <span class="msg-snip">— ' + esc(m.snippet) + '</span>' : ''}</div>
      </div>
      <div class="msg-right">
        <div class="msg-date">${esc(m.date)}</div>
        ${needsAction ? '<span class="pill">Action needed</span>' : ''}
      </div>`;
    row.addEventListener('click', () => openReader(m));
    list.appendChild(row);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

function fmt$(n) {
  return '$' + Number(n || 0).toLocaleString('en-US');
}

/* ------------------------------------------------------------------
   Interactive action rendering (mirrors Tkinter inbox_window.py).
   Every button carries data-op + data-mid; the reader's delegated
   click handler routes them through /api/command.
   ------------------------------------------------------------------ */
function iaBtn(m, op, label, primary, extra) {
  let attrs = `data-op="${op}" data-mid="${esc(m.id)}"`;
  if (extra) {
    for (const k of Object.keys(extra)) {
      if (extra[k] !== undefined && extra[k] !== null)
        attrs += ` data-${k}="${esc(String(extra[k]))}"`;
    }
  }
  return `<button class="btn-${primary ? 'primary' : 'ghost'}" ${attrs}>${label}</button>`;
}

function iaSection(title, inner) {
  return `<div class="ia-section"><div class="ia-title">${title}</div>${inner}</div>`;
}

// Desktop special header buttons: START FANTASY DRAFT / WATCH THE REVEAL.
function specialButtons(m) {
  if (m.special_action === 'fantasy_draft')
    return `<div class="ia-special"><a class="btn-primary ia-big" href="/fantasy_draft">Start Fantasy Draft</a></div>`;
  if (m.special_action === 'lottery_reveal')
    return `<div class="ia-special"><a class="btn-primary ia-big" href="/lottery">Watch the Reveal</a></div>`;
  return '';
}

function actionButtons(m) {
  const at = m.action_type;
  const d = m.action_data || {};
  const done = !!m.action_done;
  let html = specialButtons(m);
  if (!at) return html;
  switch (at) {
    case 'trade_offer':
      if (done) {
        html += `<div class="ia-note">This negotiation is no longer on the table.</div>`;
        break;
      }
      html += `<div class="msg-actions">
        ${iaBtn(m, 'inbox_trade_accept', 'Accept Trade', true)}
        ${iaBtn(m, 'inbox_trade_decline', 'Decline', false)}
        <a class="btn-ghost" href="/trades">Review & Adjust</a></div>`;
      break;
    case 'trade_counter':
      if (done) {
        html += `<div class="ia-note">This negotiation is no longer on the table.</div>`;
        break;
      }
      html += `<div class="msg-actions">
        ${iaBtn(m, 'inbox_trade_accept', 'Accept Counter', true)}
        ${iaBtn(m, 'inbox_trade_decline', 'Walk Away', false)}
        <a class="btn-ghost" href="/trades">Review & Adjust</a></div>`;
      break;
    case 'contract_counter':
      if (done) {
        html += `<div class="ia-note">This negotiation is closed.</div>`;
        break;
      }
      html += `<div class="msg-actions">
        ${iaBtn(m, 'inbox_contract_accept', 'Accept', true)}
        <a class="btn-ghost" href="/contracts">Make New Offer</a>
        ${iaBtn(m, 'inbox_contract_walkaway', 'Walk Away', false)}</div>`;
      break;
    case 'game_day':
      html += gamedayHtml(m, d, done);
      break;
    case 'postmatch_presser':
      html += postmatchHtml(m, d, done);
      break;
    case 'rfa_qualifying':
      html += rfaHtml(m, d, done);
      break;
    case 'buyout_window':
      html += buyoutHtml(m, d, done);
      break;
    case 'staff_renewal':
      html += staffHtml(m, d, done);
      break;
    case 'media_fine_response':
      html += fineHtml(m, d, done);
      break;
    case 'offer_sheet_match':
      html += offerMatchHtml(m, d, done);
      break;
    case 'offer_sheet_trade_alt':
      html += offerTradeHtml(m, d, done);
      break;
    case 'arbitration_walkaway':
      html += arbitrationHtml(m, d, done);
      break;
    default:
      break;
  }
  return html;
}

/* ---- game_day: pre-match presser + team talk + instruction + Watch/Quick ---- */
function gamedayHtml(m, d, done) {
  let h = `<div class="ia-head">Game Day: ${esc(d.away || '')} @ ${esc(d.home || '')}</div>`;
  const stale = d.game_date && m.today && d.game_date !== m.today;
  if (stale || done) {
    h += `<div class="ia-note">This game has already been played — these options are no longer available.</div>`;
    return h;
  }
  // Pre-match presser
  const questions = d.presser || [];
  const answered = d.presser_answered || [];
  const reactions = d.presser_reactions || {};
  const allAnswered = questions.length > 0 && answered.length >= questions.length && answered.every(Boolean);
  let pq = '';
  if (!allAnswered && questions.length) {
    pq += iaBtn(m, 'inbox_presser_skip', '⏩ Skip presser', false);
  }
  if (d.presser_skipped) {
    pq += `<div class="ia-note">✓ Skipped — no comment for the press today.</div>`;
  } else {
    questions.forEach((q, qi) => {
      const isA = qi < answered.length && answered[qi];
      pq += `<div class="ia-q">Q${qi + 1}: ${esc(q.question || '')}</div>
             <div class="ia-dim">— ${esc(q.journalist || '')}</div>`;
      if (isA) {
        pq += `<div class="ia-note">✓ Answered</div>`;
        if (reactions[qi]) pq += `<div class="ia-dim">“${esc(reactions[qi])}”</div>`;
      } else {
        pq += `<div class="ia-btnrow">` + (q.answers || []).map((a, ai) =>
          iaBtn(m, 'inbox_presser_answer', esc(a.label || ''), false, {q: qi, a: ai})
        ).join('') + `</div>`;
      }
    });
  }
  h += iaSection('Pre-match presser', pq);

  // Team talk
  const talks = d.talk_options || [];
  let tt = '';
  if (d.talk_chosen !== undefined && d.talk_chosen !== null) {
    const opt = talks[d.talk_chosen] || {};
    tt += `<div class="ia-note">✓ “${esc(opt.label || '')}”</div>`;
    if (d.talk_reaction) tt += `<div class="ia-dim">“${esc(d.talk_reaction)}”</div>`;
  } else {
    tt += `<div class="ia-dim">Rally the room before puck drop:</div>`;
    talks.forEach((opt, oi) => {
      const fit = {'good': ' ✓ looks ideal', 'risky': ' ⚠ risky'}[opt.fit] || '';
      tt += `<div class="ia-opt">${iaBtn(m, 'inbox_team_talk', esc(opt.label || '') + fit, false, {option: oi})}
             <div class="ia-dim">“${esc(opt.text || '')}”</div></div>`;
    });
  }
  h += iaSection('Dressing room: team talk', tt);

  // Coach's instruction
  const instrs = d.instruction_options || [];
  let ci = '';
  if (d.instruction_chosen !== undefined && d.instruction_chosen !== null) {
    const chosen = instrs.find(o => o.id === d.instruction_chosen) || {};
    ci += `<div class="ia-note">✓ “${esc(chosen.label || d.instruction_chosen)}”</div>`;
  } else {
    ci += `<div class="ia-dim">The bench's marching orders for tonight:</div>`;
    instrs.forEach(o => {
      ci += `<div class="ia-opt">${iaBtn(m, 'inbox_instruction', esc(o.label || ''), false, {option_id: o.id})}
             <div class="ia-dim">“${esc(o.text || '')}”</div></div>`;
    });
  }
  h += iaSection("Coach's instruction", ci);

  // Watch / Quick
  let wq = `<div class="ia-btnrow big">`;
  if (m.is_preseason) {
    wq += `<button class="btn-ghost" disabled title="Preseason exhibitions aren't watchable">▶ Watch Live</button>`;
  } else {
    wq += iaBtn(m, 'inbox_gameday_watch', '▶ Watch Live', true);
  }
  wq += iaBtn(m, 'inbox_gameday_quick', '⚡ Quick Sim', false) + `</div>`;
  if (m.is_preseason) {
    wq += `<div class="ia-note">Preseason exhibitions aren't watchable — they're quick-simmed and no stats are recorded.</div>`;
  }
  h += iaSection('How to play tonight', wq);
  return h;
}

/* ---- postmatch_presser ---- */
function postmatchHtml(m, d, done) {
  let h = `<div class="ia-head">Post-match presser</div>`;
  const questions = d.questions || [];
  const answered = d.answered || [];
  const reactions = d.reactions || {};
  questions.forEach((q, qi) => {
    const isA = qi < answered.length && answered[qi];
    h += `<div class="ia-q">Q${qi + 1}: ${esc(q.question || '')}</div>
          <div class="ia-dim">— ${esc(q.journalist || '')}</div>`;
    if (isA) {
      h += `<div class="ia-note">✓ Answered</div>`;
      if (reactions[qi]) h += `<div class="ia-dim">“${esc(reactions[qi])}”</div>`;
    } else if (!done) {
      h += `<div class="ia-btnrow">` + (q.answers || []).map((a, ai) =>
        iaBtn(m, 'inbox_postmatch_answer', esc(a.label || ''), false, {q: qi, a: ai})
      ).join('') + `</div>`;
    }
  });
  if (done || (answered.length && answered.every(Boolean))) {
    h += `<div class="ia-note">Presser complete — the story is filed.</div>`;
  }
  return h;
}

/* ---- per-card helpers (rfa / buyout / staff share the decided-map shape) ---- */
function remainingCards(d, cards, idKey) {
  const decided = d.decided || {};
  return (cards || []).filter(c => !(String(c[idKey]) in decided));
}

/* ---- rfa_qualifying ---- */
function rfaHtml(m, d, done) {
  let h = `<div class="ia-head">Qualifying offers</div>`;
  const rem = remainingCards(d, d.cards, 'player_id');
  if (done || !rem.length) return h + `<div class="ia-note">All qualifying decisions are in.</div>`;
  rem.forEach(c => {
    h += iaSection(esc((c.name || 'Unknown').toUpperCase()),
      `<div class="ia-line">Qualifying offer: ${fmt$(c.qo_amount)} (was ${fmt$(c.prior_salary)})</div>
       <div class="ia-btnrow col">
         ${iaBtn(m, 'inbox_rfa_qualify', `Extend QO ${fmt$(c.qo_amount)}`, true, {player_id: c.player_id, qualify: true})}
         ${iaBtn(m, 'inbox_rfa_qualify', "Don't qualify (walks as UFA)", false, {player_id: c.player_id, qualify: false})}
       </div>`);
  });
  h += `<div class="ia-note">Qualifying keeps his rights; declining makes him a UFA.</div>`;
  return h;
}

/* ---- buyout_window ---- */
function buyoutHtml(m, d, done) {
  let h = `<div class="ia-head">Buyout window — June 15-30</div>`;
  const rem = remainingCards(d, d.cards, 'player_id');
  if (done || !rem.length) return h + `<div class="ia-note">The window has closed.</div>`;
  rem.forEach(c => {
    const flag = c.dead_weight ? '  ⚠️ Dead weight' : '';
    h += iaSection(esc((c.name || 'Unknown').toUpperCase()) + flag,
      `<div class="ia-line">Age ${c.age} · ${c.overall} ovr · ${fmt$(c.cap_hit)}/yr × ${c.years_left} left</div>
       <div class="ia-line">Buyout: ${fmt$(c.buyout_cost)} total → ${fmt$(c.annual_dead)}/yr dead cap × ${c.dead_years} yrs. Saves ${fmt$(c.savings_y1)} this season.</div>
       <div class="ia-btnrow col">
         ${iaBtn(m, 'inbox_buyout_decide', `Buy out (${esc(String(c.name || '').split(' ').slice(-1)[0])})`, true, {player_id: c.player_id, buyout: true})}
         ${iaBtn(m, 'inbox_buyout_decide', 'Keep him', false, {player_id: c.player_id, buyout: false})}
       </div>`);
  });
  h += `<div class="ia-note">Buyouts clear cap now but leave dead money for years. Undecided players stay put.</div>`;
  return h;
}

/* ---- staff_renewal ---- */
function staffHtml(m, d, done) {
  let h = `<div class="ia-head">Staff contract renewals</div>`;
  const rem = remainingCards(d, d.offers, 'staff_id');
  if (done || !rem.length) return h + `<div class="ia-note">All renewal decisions are in.</div>`;
  rem.forEach(o => {
    h += iaSection(esc(`${o.name || 'Unknown'} — ${(o.role || 'staffer').toUpperCase()}`),
      `<div class="ia-line">Age ${o.age} · career standing ${o.reputation}/100 · ${o.years_with_team || 0} yrs with the club · ${fmt$(o.salary)}/yr</div>
       <div class="ia-dim">His deal expired. Re-sign him now on a fresh deal (same role, same salary) or let him walk to the free-agent pool.</div>
       <div class="ia-btnrow col">
         ${iaBtn(m, 'inbox_staff_renew', 'Re-sign × 1 yr', false, {staff_id: o.staff_id, years: 1})}
         ${iaBtn(m, 'inbox_staff_renew', 'Re-sign × 2 yrs (recommended)', true, {staff_id: o.staff_id, years: 2})}
         ${iaBtn(m, 'inbox_staff_renew', 'Re-sign × 3 yrs', false, {staff_id: o.staff_id, years: 3})}
         ${iaBtn(m, 'inbox_staff_renew', 'Let him walk', false, {staff_id: o.staff_id, years: 'walk'})}
       </div>`);
  });
  h += `<div class="ia-note">Undecided staff walk to the pool when the new season starts.</div>`;
  return h;
}

/* ---- media_fine_response ---- */
function fineHtml(m, d, done) {
  let h = `<div class="ia-head">League fine</div>`;
  const amount = Number(d.fine_amount || 0);
  h += `<div class="ia-line big">${esc(d.fine_name || '')} (${esc(d.fine_team || '')})</div>
        <div class="ia-line">${fmt$(amount)} — ${esc(d.fine_reason || '')}</div>`;
  if (done || d.responded) {
    h += `<div class="ia-note">${esc(d.outcome || 'This fine has been answered.')}</div>`;
    return h;
  }
  if (d.fine_team !== m.user_team_name) {
    h += `<div class="ia-note">Not your club's fine — nothing for you to answer for.</div>`;
    return h;
  }
  h += iaSection('Your response',
    `<div class="ia-dim">The league office awaits your answer. An appeal works about one time in four — and the head office remembers who complains.</div>
     <div class="ia-btnrow">
       ${iaBtn(m, 'inbox_fine_respond', 'Appeal the fine', false, {choice: 'appeal'})}
       ${iaBtn(m, 'inbox_fine_respond', 'Accept and move on', true, {choice: 'accept'})}
     </div>`);
  return h;
}

/* ---- offer_sheet_match ---- */
function offerMatchHtml(m, d, done) {
  let h = `<div class="ia-head">Offer sheet</div>`;
  if (done) return h + `<div class="ia-note">Decision made.</div>`;
  h += `<div class="ia-line big">${fmt$(d.aav)}/yr × ${d.years || 1}y.</div>
        <div class="ia-line">Decline and take: ${esc(d.compensation || '')}</div>
        <div class="ia-dim">Matching keeps him at these terms — he can't be traded for a year without his consent.</div>
        <div class="ia-btnrow col">
          ${iaBtn(m, 'inbox_offer_sheet_match', 'Match the offer sheet', true, {match: true})}
          ${iaBtn(m, 'inbox_offer_sheet_match', 'Decline, take the picks', false, {match: false})}
        </div>`;
  return h;
}

/* ---- offer_sheet_trade_alt ---- */
function offerTradeHtml(m, d, done) {
  let h = `<div class="ia-head">Trade alternative</div>`;
  if (done) return h + `<div class="ia-note">Decision made.</div>`;
  const pkg = d.package_player_ids || [];
  h += `<div class="ia-line big">${fmt$(d.aav)}/yr × ${d.years || 1}y.</div>
        <div class="ia-line">Trade offer: ${pkg.length} player(s) (~${fmt$(d.package_value)} trade value) instead of: ${esc(d.compensation || '')}</div>
        <div class="ia-dim">Accepting trades his rights for the package — the picks stay with the offering club. Declining takes the pick compensation, exactly as the original decline.</div>
        <div class="ia-btnrow col">
          ${iaBtn(m, 'inbox_offer_sheet_trade', 'Accept the trade', true, {accept: true})}
          ${iaBtn(m, 'inbox_offer_sheet_trade', 'Decline, take the picks', false, {accept: false})}
        </div>`;
  return h;
}

/* ---- arbitration_walkaway ---- */
function arbitrationHtml(m, d, done) {
  let h = `<div class="ia-head">Arbitration walk-away window</div>`;
  if (done) return h + `<div class="ia-note">Decision made.</div>`;
  h += `<div class="ia-line big">Award: ${fmt$(d.award_aav)}/yr × ${d.term_years || 1}y.</div>
        <div class="ia-dim">Walk away within 48 hours and he becomes a UFA. Otherwise the award is binding.</div>
        <div class="ia-btnrow col">
          ${iaBtn(m, 'inbox_arbitration', 'Accept the award', true, {walk_away: false})}
          ${iaBtn(m, 'inbox_arbitration', 'Walk away (becomes UFA)', false, {walk_away: true})}
        </div>`;
  return h;
}

/* ------------------------------------------------------------------ */

async function openReader(m) {
  openId = m.id;
  // Always pull the detail endpoint: it carries action_data, the done
  // flag, today/preseason context, and the special-button detection.
  try {
    const res = await fetch('/api/inbox/message/' + encodeURIComponent(m.id));
    if (res.ok) m = await res.json();
  } catch (e) { console.error(e); }
  openMsg = m;
  document.getElementById('r-from').textContent = m.sender;
  document.getElementById('r-date').textContent = m.date;
  document.getElementById('r-subject').textContent = m.subject;
  document.getElementById('r-category').textContent = m.category;
  document.getElementById('r-read').textContent = m.is_read ? 'Mark as unread' : 'Mark as read';
  renderReaderBody();
  document.getElementById('reader').hidden = false;
}

function renderReaderBody() {
  const m = openMsg;
  if (!m) return;
  document.getElementById('r-body').textContent = m.content || m.snippet || '(no content)';
  let ab = document.getElementById('r-actions');
  if (!ab) {
    ab = document.createElement('div');
    ab.id = 'r-actions';
    document.getElementById('r-body').after(ab);
  }
  ab.innerHTML = actionButtons(m);
}

function closeReader() {
  document.getElementById('reader').hidden = true;
  openId = null;
  openMsg = null;
}

async function sendCommand(op, extra) {
  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(Object.assign({op}, extra || {})),
    });
    return await res.json().catch(() => ({}));
  } catch (e) { console.error(e); return {}; }
}

const BOOL_KEYS = {qualify: 1, buyout: 1, match: 1, accept: 1, walk_away: 1};

async function runAction(b) {
  const op = b.dataset.op;
  const payload = {message_id: b.dataset.mid};
  for (const k of ['q', 'a', 'option', 'option_id', 'player_id', 'staff_id',
                   'years', 'qualify', 'buyout', 'match', 'accept',
                   'walk_away', 'choice']) {
    const v = b.dataset[k];
    if (v === undefined) continue;
    payload[k] = BOOL_KEYS[k] ? (v === 'true') : v;
  }
  b.disabled = true;
  await sendCommand(op, payload);
  if (op === 'inbox_gameday_watch') { window.location.href = '/watch'; return; }
  if (op === 'inbox_gameday_quick') {
    await sendCommand('advance_day', {});
    setTimeout(() => { window.location.href = '/'; }, 900);
    return;
  }
  // Wait for the main-thread drain, then re-render the reader in place.
  await new Promise(r => setTimeout(r, 700));
  await refreshReader();
}

async function refreshReader() {
  if (!openId) return;
  try {
    const res = await fetch('/api/inbox/message/' + encodeURIComponent(openId));
    if (!res.ok) return;
    openMsg = await res.json();
    const i = messages.findIndex(x => String(x.id) === String(openId));
    if (i >= 0) messages[i] = openMsg;
    document.getElementById('r-read').textContent =
      openMsg.is_read ? 'Mark as unread' : 'Mark as read';
    renderReaderBody();
  } catch (e) { console.error(e); }
}

document.getElementById('reader-close').addEventListener('click', closeReader);
document.getElementById('reader').addEventListener('click', e => {
  if (e.target.id === 'reader') { closeReader(); return; }
  const b = e.target.closest('button[data-op]');
  if (b && openMsg) runAction(b);
});
document.getElementById('r-read').addEventListener('click', async () => {
  if (openId) await sendCommand('mark_read', {message_id: openId});
  closeReader();
  setTimeout(() => loadInbox(currentFilter), 400);
});
document.getElementById('r-delete').addEventListener('click', async () => {
  if (openId) await sendCommand('delete_message', {message_id: openId});
  closeReader();
  setTimeout(() => loadInbox(currentFilter), 400);
});
document.querySelectorAll('#filters button').forEach(b =>
  b.addEventListener('click', () => loadInbox(b.dataset.f)));

loadInbox('all');

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
