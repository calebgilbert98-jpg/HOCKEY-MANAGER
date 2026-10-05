/* Player profile page renderer — fetches /api/player/<pid> and renders all 7 tabs. */
(function () {
  'use strict';
  const pid = document.body.dataset.pid;
  const $ = (id) => document.getElementById(id);

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function barColor(v) {
    if (v >= 75) return '#4CAF50';
    if (v >= 60) return '#8BC34A';
    if (v >= 45) return '#FFC107';
    if (v >= 30) return '#FF9800';
    return '#F44336';
  }

  function attrRow(label, value, fillStyle) {
    const v = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
    const bg = fillStyle || barColor(v);
    const style = ` style="width:${v}%;background:${bg};"`;
    return `<div class="attr-row"><span class="an" title="${esc(label)}">${esc(label)}</span>` +
      `<span class="ab"><span class="fill${cls}"${style}></span></span>` +
      `<span class="av">${v}</span></div>`;
  }

  function kvRow(k, v) {
    return `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`;
  }

  function unavailable(msg) {
    return `<div class="unavail">${esc(msg || 'Unavailable.')}</div>`;
  }

  /* ---- header ---- */
  function renderHeader(h) {
    document.title = h.name + ' — Puck Dynasty';
    const img = $('p-portrait-img');
    if (h.portrait) {
      img.src = h.portrait;
      img.hidden = false;
      img.onerror = () => { img.hidden = true; $('p-portrait-fallback').hidden = false; };
    } else {
      $('p-portrait-fallback').textContent = h.initials || '?';
    }
    if (h.portrait) $('p-portrait-fallback').hidden = true;
    $('p-name').textContent = h.name;
    $('p-pills').innerHTML = (h.pills || []).map((p) =>
      `<span class="pill kind-${esc(p.kind || '')}"${p.fg ? ` style="color:${esc(p.fg)}"` : ''}>${esc(p.text)}</span>`
    ).join('');
    $('p-strip').textContent = (h.strip || []).join('   •   ');
    $('p-rights-strip').textContent = (h.rights_strip || []).join('   •   ');
  }

  /* ---- overview ---- */
  function renderOverview(o) {
    $('ov-stats').innerHTML = (o.stats_cards || []).map((s) =>
      `<div class="stat-card"><div class="sv">${esc(s.value)}</div><div class="sl">${esc(s.label)}</div></div>`
    ).join('');
    const showSplits = o.show_splits && (o.splits || []).length > 1;
    $('ov-splits').hidden = !showSplits;
    if (showSplits) {
      $('ov-splits-list').innerHTML = o.splits.map((s) => {
        const gp = s.gp || 0;
        const line = o.goalie
          ? `${s.team}  ${gp} GP  ${s.w || 0}W-${s.l || 0}L`
          : `${s.team}  ${gp} GP  ${s.g || 0} G  ${s.a || 0} A  ${(s.g || 0) + (s.a || 0)} PTS`;
        return `<div class="split-line">${esc(line)}</div>`;
      }).join('');
    }
    $('ov-contract').innerHTML = (o.contract_rows || []).map((r) => kvRow(r.k, r.v)).join('');
    const compCard = $('ov-composites-card');
    if (o.composites && o.composites.length) {
      compCard.hidden = false;
      $('ov-composites').innerHTML = o.composites
        .map((c) => attrRow(c.label, c.value)).join('');
    } else {
      compCard.hidden = true;
    }
    $('ov-attrs').innerHTML = (o.attr_groups || []).map((g) =>
      `<div class="attr-col"><h3>${esc(g.name)}</h3>` +
      g.attrs.map((a) => attrRow(a.label, a.value)).join('') + `</div>`
    ).join('');
  }

  /* ---- health ---- */
  function renderHealth(h) {
    const parts = [];
    if (h.condition) {
      parts.push(attrRow('Condition', h.condition.value, h.condition.color));
      parts.push(`<div class="per-line">Condition: <b style="color:${esc(h.condition.color)}">${esc(h.condition.value)} (${esc(h.condition.label)})</b></div>`);
    }
    if (h.status) {
      parts.push(`<div class="per-line">Status: <b style="color:${esc(h.status.fg)}">${esc(h.status.text)}</b></div>`);
    }
    if (h.durability) {
      parts.push(`<div class="per-line">Durability: <b style="color:${esc(h.durability.color)}">${esc(h.durability.value)}/100 (${esc(h.durability.label)})</b></div>`);
    }
    $('h-status').innerHTML = parts.join('') || unavailable('Medical status unavailable.');

    const ac = $('h-active-card');
    if (h.active_injury) {
      ac.hidden = false;
      const ai = h.active_injury;
      const rows = [kvRow('Injury', ai.type)];
      if (ai.games_remaining > 0) {
        rows.push(kvRow('Est. return', `~${ai.games_remaining} game${ai.games_remaining !== 1 ? 's' : ''}`));
        rows.push(`<div class="caption" style="margin-top:6px">Recovery counts down per game played.</div>`);
      } else {
        rows.push(kvRow('Est. return', 'Day-to-day'));
      }
      if (ai.region) rows.push(kvRow('Area', ai.region));
      if (ai.concussion) rows.push(`<div class="per-line" style="color:#d29922">🧠 Concussion protocol</div>`);
      $('h-active').innerHTML = rows.join('');
    } else {
      ac.hidden = true;
    }

    $('h-history').innerHTML = (h.injury_history && h.injury_history.length)
      ? h.injury_history.map((e) => `<div class="bullet">• ${esc(e)}</div>`).join('')
      : `<div class="note">No recorded injuries.</div>`;
    const totals = [
      kvRow('Career games missed', h.career_games_missed || 0),
      kvRow('Days missed (season)', h.days_missed || 0),
    ];
    if (h.career_concussions) totals.push(kvRow('Career concussions', h.career_concussions));
    $('h-totals').innerHTML = totals.join('');
  }

  /* ---- analytics ---- */
  function renderAnalytics(a) {
    const host = $('a-sections');
    if (a.unavailable) {
      host.innerHTML = unavailable('Analytics unavailable (' + a.unavailable + ')');
    } else {
      const lens = a.lens;
      $('a-lens').textContent = lens
        ? `${lens.tier}  •  models as of ${lens.as_of} (rebuilt every ${lens.lag_days} day${lens.lag_days !== 1 ? 's' : ''})`
        : '';
      host.innerHTML = (a.sections || []).map((sec) =>
        `<div class="p-sect-title">${esc(sec.title)}</div>` +
        sec.rows.map((r) =>
          `<div class="metric-row"><span class="ml">${esc(r[0])}</span>` +
          `<span class="mv">${esc(r[1])}</span>` +
          (r[2] ? `<span class="mi" title="${esc(r[2])}">ⓘ</span>` : '') +
          `</div>`
        ).join('')
      ).join('');
    }
    // shot map
    const shots = (a.unavailable ? [] : (a.shots || []));
    if (shots.length) {
      $('a-shotmap').hidden = false;
      $('a-shot-legend').hidden = false;
      const totXg = shots.reduce((t, s) => t + (s.xg || 0), 0);
      const goals = shots.filter((s) => s.outcome === 'goal').length;
      $('a-shot-note').textContent =
        `${shots.length} shots · ${totXg.toFixed(2)} engine xG · ${goals} goals (last ${a.games_kept} tracked games)`;
      drawShotMap(shots);
    } else {
      $('a-shotmap').hidden = true;
      $('a-shot-legend').hidden = true;
      $('a-shot-note').textContent =
        a.unavailable ? 'Shot map unavailable.' :
        'No tracked shots yet — simulate games and his map builds itself from real shot locations (last 10 games kept per club).';
    }
  }

  function drawShotMap(shots) {
    const cv = $('a-shotmap');
    const ctx = cv.getContext('2d');
    const W = 620, H = 300, pad = 16;
    const ice = '#1d2b33';
    const f = (x, y) => [pad + (x - 100.0) / 100.0 * (W - 2 * pad), pad + y / 85.0 * (H - 2 * pad)];
    ctx.fillStyle = ice;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#3a3f44'; ctx.lineWidth = 2;
    ctx.strokeRect(4, 4, W - 4, H - 4);
    [[100.0, '#c0392b'], [125.0, '#2980b9'], [189.0, '#c0392b']].forEach(([x, color]) => {
      const [ax, ay] = f(x, 0), [, by] = f(x, 85);
      ctx.strokeStyle = color; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(ax, by); ctx.stroke();
    });
    [20.5, 64.5].forEach((cy0) => {
      const [ax, ay] = f(169, cy0);
      const r = 15 / 100.0 * (W - 2 * pad);
      ctx.strokeStyle = '#7f8c8d'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(ax, ay, r, 0, Math.PI * 2); ctx.stroke();
    });
    {
      const [ax, ay] = f(189, 42.5);
      const r = 6 / 100.0 * (W - 2 * pad);
      ctx.fillStyle = '#3d6b8c';
      ctx.beginPath(); ctx.arc(ax, ay, r, Math.PI * 1.5, Math.PI * 2.5); ctx.fill();
      const [nx] = f(190.5, 42.5);
      ctx.fillStyle = '#c0392b';
      ctx.fillRect(nx - 3, ay - 8, 6, 16);
    }
    const colors = { goal: '#2ecc71', save: '#3498db', blocked: '#7f8c8d', disallowed: '#f1c40f', pending: '#ecf0f1' };
    shots.forEach((s) => {
      const [cx, cy] = f(s.x || 160, s.y || 42.5);
      const r = 3 + (s.xg || 0) * 14;
      const col = colors[s.outcome] || '#ecf0f1';
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
      if (s.outcome === 'disallowed') {
        ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.stroke();
      } else {
        ctx.fillStyle = col; ctx.fill();
      }
      if (s.outcome === 'goal') {
        ctx.beginPath(); ctx.arc(cx, cy, r + 2, 0, Math.PI * 2);
        ctx.strokeStyle = '#d4af37'; ctx.lineWidth = 2; ctx.stroke();
      }
    });
  }

  /* ---- personality ---- */
  function renderPersonality(per) {
    const host = $('per-body');
    if (per.unavailable || !per.attitude) {
      host.innerHTML = unavailable('Personality unavailable.');
      return;
    }
    let html = `<div class="p-pills" style="margin-bottom:10px">` +
      `<span class="pill" style="color:${esc(per.attitude_color)}">${esc(per.attitude)}</span>` +
      (per.fans_tier ? `<span class="pill">Fans: ${esc(per.fans_tier)}</span>` : '') +
      `</div>`;
    html += attrRow('Morale', per.morale) + attrRow('Happiness', per.happiness) + attrRow('Loyalty', per.loyalty);
    html += `<div class="per-line" style="margin-top:6px">${esc(per.rep_line || '')}</div>`;
    if (per.why_fans_care && per.why_fans_care.length) {
      html += `<div class="per-line">Why fans care: ${esc(per.why_fans_care.join('; '))}</div>`;
    }
    host.innerHTML = html;
  }

  /* ---- scout ---- */
  function renderScout(s) {
    const rh = $('s-readiness');
    if (s.readiness && !s.readiness.unavailable) {
      const r = s.readiness;
      let html = `<div class="row-line bold">Right now  ${r.score}%   (talent grade ${r.base}%)</div>`;
      if (r.deltas && r.deltas.length) {
        html += r.deltas.map((d) =>
          `<div class="row-line">&nbsp;&nbsp;${esc(d.sign)}${esc(d.delta)}&nbsp;&nbsp;&nbsp;${esc(d.label)}</div>`
        ).join('');
      } else {
        html += `<div class="row-line">&nbsp;&nbsp;No situational adjustments — straight talent read.</div>`;
      }
      rh.innerHTML = html;
    } else {
      rh.innerHTML = unavailable('Readiness unavailable' + (s.readiness && s.readiness.unavailable ? ' (' + s.readiness.unavailable + ')' : '') + '.');
    }
    const rep = $('s-report');
    if (s.unavailable) {
      rep.innerHTML = unavailable('Scout report unavailable (' + s.unavailable + ')');
    } else if (!s.report) {
      rep.innerHTML = `<div class="per-line">No scout on staff — report unavailable.<br>Hire a scout to get a read on this player.</div>`;
    } else {
      const r = s.report;
      let html = `<div class="row-line bold">Filed by ${esc(r.scout)}  —  ${esc(r.record)}</div>` +
        `<div class="per-line">Report accuracy ${esc(r.accuracy)}  (${esc(r.viewings)} viewings)</div>`;
      if (r.composites && r.composites.length) {
        html += `<div class="per-line" style="color:#e5eaf3">Scout's ratings:  ${esc(r.composites.join('   '))}</div>`;
      }
      html += `<div class="row-line" style="margin-top:8px">Potential read:  ${esc(r.potential)}</div>`;
      if (r.strengths && r.strengths.length) html += `<div class="per-line">Best assets:  ${esc(r.strengths.join(', '))}</div>`;
      if (r.weaknesses && r.weaknesses.length) html += `<div class="per-line">Needs work:  ${esc(r.weaknesses.join(', '))}</div>`;
      else html += `<div class="per-line">No glaring holes in his game, per this scout.</div>`;
      if (r.notes) html += `<div class="per-line" style="margin-top:8px">${esc(r.notes)}</div>`;
      rep.innerHTML = html;
    }
  }

  /* ---- dynamics ---- */
  function renderDynamics(d) {
    const host = $('d-body');
    if (d.unavailable) {
      host.innerHTML = unavailable('Dynamics unavailable.');
      return;
    }
    let html = `<div class="p-pills" style="margin-bottom:10px">`;
    if (d.room_tier) html += `<span class="pill">Room: ${esc(d.room_tier)}</span>`;
    if (d.coach_fit) html += `<span class="pill">Coach: ${esc(d.coach_fit)}</span>`;
    if (d.trade_risk) html += `<span class="pill" style="color:${esc(d.trade_risk.fg)}">${esc(d.trade_risk.text)}</span>`;
    html += `</div>`;
    if (d.friends && d.friends.length) html += `<div class="per-line">Close with  ${esc(d.friends.join(', '))}</div>`;
    if (d.rivals && d.rivals.length) html += `<div class="per-line">Bad blood  ${esc(d.rivals.join(', '))}</div>`;
    (d.coach_bonds || []).forEach((b) => { html += `<div class="per-line">Forged bond  ${esc(b)}</div>`; });
    if (!(d.friends && d.friends.length) && !(d.rivals && d.rivals.length)) {
      html += `<div class="note">No notable relationships on this roster yet.</div>`;
    }
    host.innerHTML = html;
  }

  /* ---- history ---- */
  function renderHistory(h, goalie) {
    const host = $('hi-body');
    let html = '';
    (h.seasons || []).forEach((b) => {
      html += `<h3${b.live ? ' class="live"' : ''}>${esc(b.label)}${b.live ? '  (in progress)' : ''}</h3>`;
      b.stints.forEach((st) => {
        html += `<div class="row-line">${st.map((bit, i) => `<b class="${i === 0 ? 'bold' : ''}" style="margin-right:14px">${esc(bit)}</b>`).join('')}</div>`;
      });
      if (b.tot) html += `<div class="row-line"><span class="tot">${esc(b.tot)}</span></div>`;
    });
    if (!h.seasons || !h.seasons.length) html += unavailable('No NHL season history yet.');
    if (h.career) html += `<h3 style="margin-top:16px">Career Totals</h3><div class="row-line"><span class="tot">${esc(h.career)}</span></div>`;
    if (h.playoffs && h.playoffs.length) {
      html += `<h3 style="margin-top:16px">Playoffs</h3>`;
      html += h.playoffs.map((p) => `<div class="row-line">${esc(p)}</div>`).join('');
    }
    host.innerHTML = html;
  }

  /* ---- tabs ---- */
  document.querySelectorAll('#p-tabs button').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#p-tabs button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.ptab').forEach((t) => { t.hidden = true; });
      $('tab-' + btn.dataset.tab).hidden = false;
    });
  });

  /* ---- load ---- */
  fetch('/api/player/' + encodeURIComponent(pid))
    .then((r) => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then((d) => {
      if (d.error) { $('p-name').textContent = 'Player not found'; return; }
      renderHeader(d.header || {});
      renderOverview(d.overview || {});
      renderHealth(d.health || {});
      renderAnalytics(d.analytics || { unavailable: 'no data' });
      renderPersonality(d.personality || {});
      renderScout(d.scout || {});
      renderDynamics(d.dynamics || {});
      renderHistory(d.history || {}, d.goalie);
    })
    .catch((err) => {
      $('p-name').textContent = 'Profile unavailable';
      console.error('player profile load failed', err);
    });
})();
