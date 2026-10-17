/* Puck Dynasty — Multiplayer bar (Batch E, 2026-10-06).
 *
 * Global in-game MP layer, loaded on every page via nav.js when a
 * multiplayer game is active:
 *  - /api/mp/game polling (chat, day_advanced, state_sync, trade
 *    offers, NTC prompts, draft clocks, advance status, disconnect)
 *  - ready-gate pill (EHM: every manager readies before the day advances)
 *  - MP chat drawer
 *  - human-to-human trade offer cards (accept/reject)
 *  - NTC waiver prompt cards (ask/remove/cancel)
 *  - MP fantasy/entry draft clock modal (60s pick timer)
 *  - host-disconnect promote card (host migration)
 *  - state-sync reload (host advanced the day -> pull the new snapshot)
 */
(function () {
'use strict';

var state = { role: 'none', myTeam: null, connected: false, ready: false };
var pollTimer = null;
var chatOpen = false;
var chatLog = [];
var draftModal = null;   // {clock_id, action, team_id, deadline}
var seenOfferIds = {};

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>\"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

function api(path, opts) {
  return fetch(path, opts).then(function (r) { return r.json(); });
}

/* ---------------- boot ---------------- */
api('/api/mp/state').then(function (st) {
  if (!st || !st.ok || st.role === 'none') return;
  state.role = st.role;
  state.myTeam = st.my_team;
  state.connected = !!st.connected;
  buildBar();
  buildChat();
  pollTimer = setInterval(poll, 2500);
  poll();
  if (st.disconnected) onDisconnect(st.disconnected);
}).catch(function () {});

/* ---------------- bar ---------------- */
function buildBar() {
  var bar = document.createElement('div');
  bar.id = 'mp-bar';
  var roleLabel = { host: 'HOST', client: 'GM', spectator: 'SPECTATOR' }[state.role] || 'MP';
  bar.innerHTML =
    '<span class="mp-badge">' + esc(roleLabel) + '</span>' +
    '<span class="mp-team">' + esc(state.myTeam || '—') + '</span>' +
    '<span class="mp-ready" id="mp-ready" title="Ready vote — the day advances when every manager is ready">…</span>' +
    '<span class="mp-advance" id="mp-advance"></span>' +
    '<span class="mp-spacer"></span>' +
    (state.role === 'host' ? '<button class="mp-btn" id="mp-force" title="Advance the day even if some managers aren\'t ready">Force advance</button>' : '') +
    '<button class="mp-btn" id="mp-chat-btn">💬 Chat</button>';
  document.body.appendChild(bar);
  var ready = document.getElementById('mp-ready');
  if (state.role !== 'spectator') {
    ready.style.cursor = 'pointer';
    ready.addEventListener('click', toggleReady);
  }
  document.getElementById('mp-chat-btn').addEventListener('click', function () {
    chatOpen = !chatOpen;
    document.getElementById('mp-chat').classList.toggle('open', chatOpen);
  });
  var force = document.getElementById('mp-force');
  if (force) force.addEventListener('click', function () {
    if (!confirm('Force the day to advance even though some managers aren\'t ready?')) return;
    api('/api/mp/force', { method: 'POST' }).then(function (d) {
      toast(d.ok ? 'Forcing the advance…' : ('Failed: ' + (d.error || '')));
    });
  });
}

function buildChat() {
  var c = document.createElement('div');
  c.id = 'mp-chat';
  c.innerHTML =
    '<div class="mp-chat-head">League chat</div>' +
    '<div class="mp-chat-log" id="mp-chat-log"></div>' +
    '<div class="mp-chat-row">' +
    '<input id="mp-chat-in" maxlength="500" placeholder="Message the league…" autocomplete="off">' +
    '<button id="mp-chat-send">Send</button></div>';
  document.body.appendChild(c);
  var send = function () {
    var inp = document.getElementById('mp-chat-in');
    var text = inp.value.trim();
    if (!text) return;
    inp.value = '';
    api('/api/mp/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text }),
    }).then(function (d) {
      if (d.ok) addChat('You', text);
      else toast('Chat failed: ' + (d.error || ''));
    });
  };
  document.getElementById('mp-chat-send').addEventListener('click', send);
  document.getElementById('mp-chat-in').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') send();
  });
}

function addChat(from, text) {
  chatLog.push({ from: from, text: text });
  if (chatLog.length > 80) chatLog.shift();
  var log = document.getElementById('mp-chat-log');
  if (!log) return;
  var div = document.createElement('div');
  div.className = 'mp-chat-msg';
  div.innerHTML = '<b>' + esc(from) + ':</b> ' + esc(text);
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

/* ---------------- polling ---------------- */
function poll() {
  api('/api/mp/game').then(function (g) {
    if (!g || !g.ok) return;
    if (g.role !== 'none') state.role = g.role;
    state.connected = !!g.connected;
    renderAdvance(g.advance);
    (g.events || []).forEach(handleEvent);
    if (g.disconnected && !seenOfferIds.__dc) {
      seenOfferIds.__dc = true;
      onDisconnect(g.disconnected);
    }
  }).catch(function () {});
}

function renderAdvance(adv) {
  var r = document.getElementById('mp-ready');
  var a = document.getElementById('mp-advance');
  if (!r || !a) return;
  if (!adv) { r.textContent = '…'; a.textContent = ''; return; }
  var me = !!adv.me_ready;
  state.ready = me;
  r.textContent = me ? '✓ READY' : 'READY?';
  r.classList.toggle('on', me);
  var counts = adv.needed_count != null
    ? (adv.ready_count || 0) + '/' + adv.needed_count + ' ready' : '';
  var waiting = (adv.waiting || []).join(', ');
  a.textContent = counts + (waiting && !me ? ' · waiting: ' + waiting : '');
}

function toggleReady() {
  var r = document.getElementById('mp-ready');
  if (r) r.textContent = '…';
  api('/api/mp/ready', { method: 'POST' }).then(function (d) {
    if (!d.ok) return;
    var nonce = d.nonce, tries = 0;
    var t = setInterval(function () {
      tries++;
      api('/api/mp/result?nonce=' + encodeURIComponent(nonce)).then(function (d2) {
        if (d2.pending || tries > 20) { if (!d2.pending) clearInterval(t); return; }
        clearInterval(t);
        var res = d2.result || {};
        if (res.blocked) {
          toast('Blockers first: ' + (res.blockers || []).map(function (b) { return b.title; }).join('; '));
        } else if (!res.ok) {
          toast(res.message || 'Vote failed.');
        }
        poll();
      });
    }, 600);
  });
}

/* ---------------- events ---------------- */
/* Day advance: toast now, reload only after the follow-up state_sync
   is applied (or a fallback timer). Reloading immediately can abort
   the sync fetch in flight. */
var pendingDaySync = false;
var daySyncTimer = null;

function handleEvent(ev) {
  var k = ev.kind, p = ev.payload || {};
  switch (k) {
    case 'chat':
      addChat(p.from || '?', p.text || '');
      break;
    case 'day_advanced':
      toast('Day advanced: ' + (p.game_date || '') + ' — syncing…');
      pendingDaySync = true;
      if (daySyncTimer) clearTimeout(daySyncTimer);
      daySyncTimer = setTimeout(function () {
        if (pendingDaySync) {
          pendingDaySync = false;
          window.location.reload();
        }
      }, 15000);
      break;
    case 'state_sync':
      onStateSync(p);
      break;
    case 'trade_offer':
      showTradeOffer(p, false);
      break;
    case 'host_trade_offer':
      showTradeOffer(p, true);
      break;
    case 'ntc_waiver_request':
      showNtc(p);
      break;
    case 'draft_clock':
      showDraftClock(p, 'draft_pick', 'Entry Draft');
      break;
    case 'fantasy_draft_clock':
      showDraftClock(p, 'fantasy_draft_pick', 'Fantasy Draft');
      break;
    case 'draft_update':
      toast('Draft: ' + (p.team_id || '') + ' picked ' + (p.player_name || ''));
      break;
    case 'action_ack':
      toast('Accepted: ' + (p.action || '') + (p.result ? ' — ' + p.result : ''));
      break;
    case 'action_rejected':
      toast('Rejected: ' + (p.action || '') + ' — ' + (p.reason || ''), true);
      break;
    case 'checkpoint':
      toast('Host checkpoint: ' + (p.label || ''));
      break;
    case 'error':
      toast('Host: ' + (p.message || ''), true);
      break;
    case 'advance_status':
      break; // rendered by renderAdvance()
    case 'disconnected':
      onDisconnect(p.reason || '');
      break;
    default:
      break;
  }
}

function onStateSync(p) {
  toast('Host advanced — syncing…');
  api('/api/mp/sync').then(function (d) {
    if (!d.ok) { toast('Sync failed: ' + (d.error || ''), true); return; }
    return api('/api/mp/apply_snapshot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ save_b64: d.save_b64, label: d.label }),
    }).then(function (d2) {
      if (!d2.ok) { toast('Sync failed: ' + (d2.error || ''), true); return; }
      var nonce = d2.nonce, tries = 0;
      var t = setInterval(function () {
        tries++;
        api('/api/save/result?nonce=' + encodeURIComponent(nonce)).then(function (d3) {
          if (d3.pending || tries > 40) {
            if (!d3.pending) {
              clearInterval(t);
              pendingDaySync = false;
              window.location.reload();
            }
            return;
          }
          clearInterval(t);
          if (d3.result && d3.result.ok) {
            pendingDaySync = false;
            window.location.reload();
          }
          else toast('Sync failed: ' + ((d3.result || {}).message || ''), true);
        });
      }, 1000);
    });
  }).catch(function () { toast('Sync failed.', true); });
}

/* ---------------- trade offers ---------------- */
function showTradeOffer(p, isHost) {
  var oid = p.offer_id || '';
  if (!oid || seenOfferIds[oid]) return;
  seenOfferIds[oid] = true;
  var card = document.createElement('div');
  card.className = 'mp-card';
  function plist(arr) {
    return (arr || []).map(function (x) {
      return typeof x === 'string' ? esc(x)
        : esc(x.name || '?') + ' (' + esc(x.pos || '?') + ', ' + (x.ovr || '?') + ' OVR)';
    }).join('<br>') || '<i>none</i>';
  }
  card.innerHTML =
    '<div class="mp-card-title">🤝 Trade offer' + (isHost ? ' (for your club)' : '') + '</div>' +
    '<div class="mp-card-sub">From <b>' + esc(p.from_manager || p.from_team || '?') +
    '</b> (' + esc(p.from_team || '') + ')</div>' +
    '<div class="mp-trade-cols"><div><b>You receive</b><br>' + plist(p.players_out) +
    (p.picks_out && p.picks_out.length ? '<br>' + p.picks_out.map(esc).join('<br>') : '') +
    '</div><div><b>You send</b><br>' + plist(p.players_in) +
    (p.picks_in && p.picks_in.length ? '<br>' + p.picks_in.map(esc).join('<br>') : '') +
    '</div></div>' +
    '<div class="mp-card-row"><button class="mp-accept">Accept</button>' +
    '<button class="mp-reject">Reject</button>' +
    '<button class="mp-dismiss">Later</button></div>';
  document.body.appendChild(card);
  card.querySelector('.mp-accept').addEventListener('click', function () {
    answerOffer(oid, 'accept', isHost);
    card.remove();
  });
  card.querySelector('.mp-reject').addEventListener('click', function () {
    answerOffer(oid, 'reject', isHost);
    card.remove();
  });
  card.querySelector('.mp-dismiss').addEventListener('click', function () { card.remove(); });
}

function answerOffer(oid, decision, isHost) {
  var url = isHost ? '/api/mp/trade/respond_host' : '/api/mp/trade/respond';
  api(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ offer_id: oid, decision: decision }),
  }).then(function (d) {
    if (d.nonce) {
      // Host path runs on the main thread; poll for the outcome.
      var tries = 0;
      var t = setInterval(function () {
        tries++;
        api('/api/mp/result?nonce=' + encodeURIComponent(d.nonce)).then(function (d2) {
          if (d2.pending || tries > 20) { if (!d2.pending) clearInterval(t); return; }
          clearInterval(t);
          var r = d2.result || {};
          toast(r.ok ? ('Trade ' + decision + 'ed: ' + (r.message || '')) : ('Failed: ' + (r.message || '')));
          if (r.ok) setTimeout(function () { window.location.reload(); }, 800);
        });
      }, 700);
    } else {
      toast(d.ok ? ('Offer ' + decision + 'ed.') : ('Failed: ' + (d.error || '')));
    }
  });
}

/* ---------------- NTC prompts ---------------- */
function showNtc(p) {
  var card = document.createElement('div');
  card.className = 'mp-card';
  card.innerHTML =
    '<div class="mp-card-title">📋 No-trade clause</div>' +
    '<div class="mp-card-sub"><b>' + esc(p.player_name || '?') + '</b> has a ' +
    esc(p.clause || 'clause') + ' — destination: <b>' + esc(p.dest_team || '') + '</b></div>' +
    '<div class="mp-card-row"><button class="mp-accept" data-c="ask">Ask him to waive</button>' +
    '<button class="mp-reject" data-c="remove">Remove from deal</button>' +
    '<button class="mp-dismiss" data-c="cancel">Cancel deal</button></div>';
  document.body.appendChild(card);
  card.querySelectorAll('button').forEach(function (b) {
    b.addEventListener('click', function () {
      api('/api/mp/ntc_answer', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ waiver_id: p.waiver_id || '', player_id: p.player_id || '', choice: b.dataset.c }),
      });
      card.remove();
    });
  });
}

/* ---------------- draft clock ---------------- */
function showDraftClock(p, actionName, title) {
  closeDraftModal();
  var mine = (p.team_id || '') === (state.myTeam || '');
  draftModal = {
    clock_id: p.clock_id || '', action: actionName, team_id: p.team_id || '',
    deadline: Date.now() + 60000, mine: mine,
  };
  var m = document.createElement('div');
  m.className = 'mp-card mp-draft';
  m.id = 'mp-draft-modal';
  var pros = p.prospects || [];
  m.innerHTML =
    '<div class="mp-card-title">⏱️ ' + esc(title) + ' — on the clock: <b>' +
    esc(p.team_id || '') + '</b></div>' +
    '<div class="mp-card-sub">Pick #' + esc(p.overall || '') + ' (Round ' +
    esc(p.round_num || '') + ') · <span id="mp-clock">60</span>s left' +
    (mine ? '' : ' — not your pick; the board updates live.') + '</div>' +
    (mine ? '<input id="mp-draft-q" placeholder="Search prospects…" autocomplete="off">' +
      '<div class="mp-draft-list" id="mp-draft-list"></div>' : '') +
    '<div class="mp-card-row"><button class="mp-dismiss" id="mp-draft-close">Close</button></div>';
  document.body.appendChild(m);
  document.getElementById('mp-draft-close').addEventListener('click', closeDraftModal);
  if (mine) {
    var list = document.getElementById('mp-draft-list');
    var render = function (q) {
      q = (q || '').toLowerCase();
      list.innerHTML = '';
      pros.filter(function (x) {
        return !q || (x.name || '').toLowerCase().indexOf(q) >= 0;
      }).slice(0, 60).forEach(function (x) {
        var row = document.createElement('div');
        row.className = 'mp-draft-row';
        row.innerHTML = '<span><b>' + esc(x.name || '?') + '</b> <span class="dim">' +
          esc(x.pos || '') + ' · rank ' + esc(x.ranking || '?') + '</span></span>' +
          '<button>Draft</button>';
        row.querySelector('button').addEventListener('click', function () {
          api('/api/mp/action', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              action: actionName,
              params: { team_id: state.myTeam, clock_id: draftModal.clock_id, player_id: x.id },
            }),
          }).then(function (d) {
            toast(d.ok ? 'Pick submitted.' : ('Failed: ' + (d.error || '')));
          });
          closeDraftModal();
        });
        list.appendChild(row);
      });
    };
    // Fantasy payloads carry ids, not full prospects: resolve them.
    var ids = p.available_ids || [];
    if (!pros.length && ids.length) {
      list.innerHTML = '<div class="dim">Loading players…</div>';
      api('/api/mp/draft_players', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: ids.slice(0, 400) }),
      }).then(function (d) {
        pros = (d.ok && d.players) || [];
        render('');
      }).catch(function () { list.innerHTML = '<div class="dim">Could not load players.</div>'; });
    } else {
      render('');
    }
    document.getElementById('mp-draft-q').addEventListener('input', function (e) {
      render(e.target.value);
    });
  }
  draftModal.timer = setInterval(function () {
    var left = Math.max(0, Math.round((draftModal.deadline - Date.now()) / 1000));
    var el = document.getElementById('mp-clock');
    if (el) el.textContent = left;
    if (left <= 0) {
      clearInterval(draftModal.timer);
      toast('Draft clock expired — auto-pick.');
      closeDraftModal();
    }
  }, 500);
}

function closeDraftModal() {
  if (draftModal && draftModal.timer) clearInterval(draftModal.timer);
  draftModal = null;
  var m = document.getElementById('mp-draft-modal');
  if (m) m.remove();
}

/* ---------------- disconnect / promote ---------------- */
function onDisconnect(reason) {
  if (state.role !== 'client' && state.role !== 'spectator') return;
  var card = document.createElement('div');
  card.className = 'mp-card';
  card.innerHTML =
    '<div class="mp-card-title">🔌 Lost connection to the host</div>' +
    '<div class="mp-card-sub">' + esc(reason || '') + '<br>Your last synced state was kept. ' +
    'Promote this client to host so the session can continue?</div>' +
    '<div class="mp-card-row"><button class="mp-accept" id="mp-promote">Promote to host</button>' +
    '<button class="mp-dismiss" id="mp-stay">Stay offline</button></div>';
  document.body.appendChild(card);
  document.getElementById('mp-stay').addEventListener('click', function () { card.remove(); });
  document.getElementById('mp-promote').addEventListener('click', function () {
    card.querySelector('#mp-promote').disabled = true;
    card.querySelector('#mp-promote').textContent = 'Promoting…';
    api('/api/mp/promote', { method: 'POST' }).then(function (d) {
      if (!d.ok) { toast('Promote failed: ' + (d.error || ''), true); return; }
      var tries = 0;
      var t = setInterval(function () {
        tries++;
        api('/api/mp/result?nonce=' + encodeURIComponent(d.nonce)).then(function (d2) {
          if (d2.pending || tries > 30) { if (!d2.pending) clearInterval(t); return; }
          clearInterval(t);
          var r = d2.result || {};
          toast(r.ok ? r.message : ('Promote failed: ' + (r.message || '')), !r.ok);
          if (r.ok) { seenOfferIds.__dc = false; setTimeout(function () { window.location.reload(); }, 1200); }
        });
      }, 800);
    });
  });
}

/* ---------------- toast ---------------- */
function toast(msg, isErr) {
  var t = document.createElement('div');
  t.className = 'mp-toast' + (isErr ? ' err' : '');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function () { t.classList.add('show'); }, 30);
  setTimeout(function () { t.classList.remove('show'); setTimeout(function () { t.remove(); }, 400); }, 3600);
}

})();
