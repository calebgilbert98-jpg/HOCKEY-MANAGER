/* Puck Dynasty custom right-click context menus.
 * Detects players / teams / staff from existing data-href attributes
 * (e.g. data-href="/player/<id>") and shows an NHL 14-styled menu.
 * Right-clicks on anything else fall through to the browser menu.
 */
(function () {
  'use strict';

  var openMenu = null;

  function closeMenu() {
    if (openMenu) {
      openMenu.remove();
      openMenu = null;
    }
  }

  function onDocClick(e) {
    if (openMenu && !openMenu.contains(e.target)) closeMenu();
  }

  function onKey(e) {
    if (e.key === 'Escape') closeMenu();
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c];
    });
  }

  /* Small toast for action feedback. */
  function toast(msg) {
    var t = document.createElement('div');
    t.className = 'pd-ctx-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add('show'); }, 10);
    setTimeout(function () {
      t.classList.remove('show');
      setTimeout(function () { t.remove(); }, 300);
    }, 2600);
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* ignore */ }
    return { ok: res.ok && data.ok !== false, data: data };
  }

  function showMenu(x, y, items) {
    closeMenu();
    var menu = document.createElement('div');
    menu.className = 'pd-ctx-menu';
    menu.setAttribute('role', 'menu');
    items.forEach(function (item) {
      if (item.sep) {
        var s = document.createElement('div');
        s.className = 'pd-ctx-sep';
        menu.appendChild(s);
        return;
      }
      var b = document.createElement('button');
      b.className = 'pd-ctx-item' + (item.danger ? ' danger' : '');
      b.setAttribute('role', 'menuitem');
      b.innerHTML = '<span class="pd-ctx-label">' + esc(item.label) + '</span>' +
        (item.hint ? '<span class="pd-ctx-hint">' + esc(item.hint) + '</span>' : '');
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        closeMenu();
        try { item.action(); } catch (err) { console.error(err); }
      });
      menu.appendChild(b);
    });
    document.body.appendChild(menu);
    /* Keep inside viewport — flip near edges. */
    var r = menu.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = Math.max(8, x - r.width);
    if (y + r.height > window.innerHeight - 8) y = Math.max(8, y - r.height);
    menu.style.left = Math.max(8, x) + 'px';
    menu.style.top = Math.max(8, y) + 'px';
    openMenu = menu;
  }

  /* ---------- entity detection ---------- */
  function entityFromEvent(e) {
    var t = e.target.closest ? e.target.closest('[data-href]') : null;
    if (!t) return null;
    var href = t.getAttribute('data-href') || '';
    var m = href.match(/^\/player\/([^/?#]+)/);
    if (m) return { kind: 'player', id: decodeURIComponent(m[1]), el: t };
    m = href.match(/^\/team\/([^?#]+)/);
    if (m) return { kind: 'team', name: decodeURIComponent(m[1]), el: t };
    m = href.match(/^\/staff\/([^/?#]+)/);
    if (m) return { kind: 'staff', id: decodeURIComponent(m[1]), el: t };
    return null;
  }

  /* True when the right-clicked player is on the user's own team
   * (team-management actions only make sense there). */
  function isUserTeamContext(ent) {
    var path = window.location.pathname;
    if (path === '/roster' || path === '/lines' || path === '/captains') return true;
    /* Team page for the user's own club. */
    if (path.indexOf('/team/') === 0) {
      var head = document.querySelector('[data-is-user-team="1"]');
      if (head) return true;
    }
    /* Explicit marker on the clicked element or its row. */
    if (ent.el && ent.el.closest('[data-user-team="1"]')) return true;
    return false;
  }

  /* ---------- player menu ---------- */
  function playerMenu(ent, x, y) {
    var pid = ent.id;
    var items = [
      {
        label: 'View Profile', hint: 'Full player card',
        action: function () { window.location.href = '/player/' + encodeURIComponent(pid); },
      },
      {
        label: 'Compare', hint: 'Side-by-side with others',
        action: function () { window.location.href = '/compare?p1=' + encodeURIComponent(pid); },
      },
      {
        label: 'Propose Trade', hint: 'Open trade center',
        action: function () { window.location.href = '/trades?player=' + encodeURIComponent(pid); },
      },
    ];
    if (isUserTeamContext(ent)) {
      items.push({ sep: true });
      items.push({
        label: 'Edit Lines', hint: 'Line combinations',
        action: function () { window.location.href = '/lines'; },
      });
      items.push({
        label: 'Add to Trade Block',
        action: async function () {
          const r = await postJSON('/api/trade_block/add', { player_ids: [pid] });
          toast(r.ok ? 'Added to trade block' : 'Could not add to trade block');
        },
      });
      items.push({
        label: 'Sign Extension', hint: 'New contract',
        action: function () { window.location.href = '/contracts?player=' + encodeURIComponent(pid); },
      });
      items.push({ sep: true });
      items.push({
        label: 'Place on Waivers', danger: true,
        action: async function () {
          if (!confirm('Place this player on waivers? Other teams can claim him.')) return;
          const r = await postJSON('/api/waivers/place', { player_id: pid });
          toast(r.ok ? 'Placed on waivers' : 'Could not place on waivers');
          if (r.ok) setTimeout(function () { window.location.reload(); }, 900);
        },
      });
    }
    showMenu(x, y, items);
  }

  /* ---------- team menu ---------- */
  function teamMenu(ent, x, y) {
    var name = ent.name;
    showMenu(x, y, [
      {
        label: 'Team Overview', hint: 'Record, leaders, roster',
        action: function () { window.location.href = '/team/' + encodeURIComponent(name); },
      },
      {
        label: 'Propose Trade', hint: 'Open trade center',
        action: function () { window.location.href = '/trades?team=' + encodeURIComponent(name); },
      },
    ]);
  }

  /* ---------- staff menu ---------- */
  function staffMenu(ent, x, y) {
    var sid = ent.id;
    showMenu(x, y, [
      {
        label: 'View Details', hint: 'Staff profile',
        action: function () { window.location.href = '/staff/' + encodeURIComponent(sid); },
      },
      { sep: true },
      {
        label: 'Release', danger: true,
        action: async function () {
          if (!confirm('Release this staff member? Their contract ends immediately.')) return;
          const r = await postJSON('/api/staff/release', { staff_id: sid });
          toast(r.ok ? 'Staff released' : 'Could not release staff');
          if (r.ok) setTimeout(function () { window.location.reload(); }, 900);
        },
      },
    ]);
  }

  /* ---------- global right-click handler ----------
   * Only intercepts when we have a custom menu to show;
   * everything else keeps the native browser menu. */
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault(); /* never show the browser menu */
    var ent = entityFromEvent(e);
    if (!ent) return; /* no custom menu — show nothing */
    if (ent.kind === 'player') playerMenu(ent, e.clientX, e.clientY);
    else if (ent.kind === 'team') teamMenu(ent, e.clientX, e.clientY);
    else if (ent.kind === 'staff') staffMenu(ent, e.clientX, e.clientY);
  });

  document.addEventListener('click', onDocClick, true);
  document.addEventListener('keydown', onKey, true);
  window.addEventListener('scroll', closeMenu, true);
  window.addEventListener('resize', closeMenu);
})();
