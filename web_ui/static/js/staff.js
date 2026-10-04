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
            <div class="s-name">${esc(s.name)}</div>
            <div class="s-sub">${esc(sub || s.role)}</div>
          </div>
        </div>
        <div class="s-bar"><span style="width:${Math.min(100, s.rating)}%;background:${barColor(s.rating)}"></span></div>
        <div class="s-meta">
          <span>Morale <b>${s.morale}</b></span>
          <span>Exp <b>${s.experience}y</b></span>
          <span>Salary <b>${sal}</b></span>
        </div>`;
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

document.addEventListener('DOMContentLoaded', loadStaff);
