/* Puck Dynasty web staff */
async function loadStaff() {
  try {
    const res = await fetch('/api/staff');
    const data = await res.json();
    renderStaff(data.staff || [], data.count || 0);
  } catch (e) { console.error(e); }
}

function barColor(v) {
  if (v >= 80) return '#4CAF50';
  if (v >= 65) return '#8BC34A';
  if (v >= 50) return '#FFC107';
  if (v >= 35) return '#FF9800';
  return '#F44336';
}

function renderStaff(staff, count) {
  document.getElementById('staff-count').textContent =
    count + (count === 1 ? ' staff member' : ' staff members');
  const wrap = document.getElementById('staff-groups');
  wrap.innerHTML = '';
  if (!staff.length) {
    wrap.innerHTML = '<div class="staff-empty">No staff on the team.</div>';
    return;
  }
  // group by role, preserving first-seen order
  const groups = new Map();
  for (const s of staff) {
    const role = s.role || 'Staff';
    if (!groups.has(role)) groups.set(role, []);
    groups.get(role).push(s);
  }
  for (const [role, members] of groups) {
    members.sort((a, b) => b.rating - a.rating);
    const g = document.createElement('div');
    g.className = 'role-group';
    g.innerHTML = `<div class="role-title">${esc(role)} <span class="count">${members.length}</span></div>`;
    const grid = document.createElement('div');
    grid.className = 'staff-grid';
    for (const s of members) {
      const el = document.createElement('div');
      el.className = 'staff-card';
      const sal = s.salary >= 1e6 ? '$' + (s.salary / 1e6).toFixed(2) + 'M'
                                  : '$' + Math.round(s.salary / 1e3) + 'K';
      const sub = [s.age ? 'Age ' + s.age : null, s.nationality || null]
        .filter(Boolean).join(' · ');
      el.innerHTML = `
        <div class="s-head">
          <div class="s-rt" style="--c:${barColor(s.rating)}">${s.rating}</div>
          <div>
            <div class="s-name">${s.id ? `<span class="clickable-text" data-href="/staff/${esc(s.id)}" title="Open staff profile">${esc(s.name)}</span>` : esc(s.name)}</div>
            <div class="s-sub">${esc(sub || s.role)}</div>
          </div>
        </div>
        <div class="s-bar"><span style="width:${Math.min(100, s.rating)}%;background:${barColor(s.rating)}"></span></div>
        <div class="s-meta">
          <span>Morale <b>${s.morale}</b></span>
          <span>Exp <b>${s.experience}y</b></span>
          <span>Salary <b>${sal}</b></span>
        </div>
        <div class="s-actions">
          <button class="s-btn" data-act="reassign" data-id="${esc(s.id)}" data-name="${esc(s.name)}" data-role="${esc(s.role)}">Reassign Role</button>
          <button class="s-btn danger" data-act="release" data-id="${esc(s.id)}" data-name="${esc(s.name)}">Release</button>
        </div>`;
      el.querySelectorAll('.s-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          if (btn.dataset.act === 'release') releaseStaff(btn, btn.dataset.id, btn.dataset.name);
          else reassignStaff(btn, btn.dataset.id, btn.dataset.name, btn.dataset.role);
        });
      });
      grid.appendChild(el);
    }
    g.appendChild(grid);
    wrap.appendChild(g);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  return res.json();
}

async function releaseStaff(btn, id, name) {
  if (!confirm(`Are you sure you want to release ${name}?\nThis ends their contract immediately. Severance is owed on the remaining term.`)) return;
  btn.disabled = true;
  try {
    const r = await postJSON('/api/staff/release', {staff_id: id});
    if (r.ok) {
      await loadStaff();
    } else {
      alert('Could not release: ' + (r.error || 'unknown error'));
      btn.disabled = false;
    }
  } catch (e) {
    console.error(e);
    btn.disabled = false;
  }
}

let STAFF_ROLES = null;

async function staffRoles() {
  if (!STAFF_ROLES) {
    const res = await fetch('/api/staff/roles');
    const data = await res.json();
    STAFF_ROLES = data.roles || [];
  }
  return STAFF_ROLES;
}

async function reassignStaff(btn, id, name, currentRole) {
  const roles = await staffRoles();
  const overlay = document.createElement('div');
  overlay.className = 'cm-overlay';
  const opts = roles.map(r => `<option value="${esc(r.name)}" ${r.label === currentRole ? 'disabled' : ''}>${esc(r.label)}</option>`).join('');
  overlay.innerHTML =
    '<div class="cm-card" role="dialog" aria-modal="true">' +
    '<div class="cm-head"><div><div class="cm-title">Reassign ' + esc(name) + '</div>' +
    '<div class="cm-player">Current role: ' + esc(currentRole) + '</div></div>' +
    '<button class="cm-close" aria-label="Close">✕</button></div>' +
    '<div class="cm-field"><label>New role</label>' +
    '<select class="cm-select" id="reassign-role">' + opts + '</select></div>' +
    '<div class="cm-note" id="reassign-note"></div>' +
    '<div class="cm-actions"><button class="cm-cancel">Cancel</button>' +
    '<button class="cm-submit">Confirm Reassignment</button></div></div>';
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.querySelector('.cm-close').addEventListener('click', close);
  overlay.querySelector('.cm-cancel').addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  overlay.querySelector('.cm-submit').addEventListener('click', async () => {
    const role = overlay.querySelector('#reassign-role').value;
    const note = overlay.querySelector('#reassign-note');
    try {
      const r = await postJSON('/api/staff/reassign', {staff_id: id, role});
      if (r.ok) {
        close();
        await loadStaff();
      } else {
        note.textContent = r.error || 'Reassignment failed.';
      }
    } catch (e) {
      note.textContent = 'Request failed.';
    }
  });
}

document.addEventListener('DOMContentLoaded', loadStaff);

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();

// Shared: clickable entities navigate via data-href (not from action controls).
document.addEventListener('click', (e) => {
  if (e.target.closest('button, a, input, select')) return;
  const t = e.target.closest('.clickable[data-href], .clickable-text[data-href], .card-clickable[data-href]');
  if (t) window.location.href = t.dataset.href;
});
