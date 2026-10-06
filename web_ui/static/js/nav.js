/* Puck Dynasty global nav behavior: dropdown toggles + current-page highlight. */
(function () {
  var nav = document.getElementById('pd-nav');
  if (!nav) return;

  // Dropdown open/close
  var drops = nav.querySelectorAll('.pd-nav-drop');
  function closeAll(except) {
    drops.forEach(function (d) {
      if (d !== except) {
        d.classList.remove('open');
        d.querySelector('.pd-nav-btn').setAttribute('aria-expanded', 'false');
      }
    });
  }
  drops.forEach(function (d) {
    var btn = d.querySelector('.pd-nav-btn');
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var wasOpen = d.classList.contains('open');
      closeAll(d);
      d.classList.toggle('open', !wasOpen);
      btn.setAttribute('aria-expanded', String(!wasOpen));
    });
  });
  document.addEventListener('click', function () { closeAll(null); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll(null);
  });

  // Highlight current page + its parent menu
  var path = window.location.pathname.replace(/\/$/, '') || '/';
  nav.querySelectorAll('[data-nav]').forEach(function (a) {
    var target = (a.getAttribute('data-nav') || '').replace(/\/$/, '') || '/';
    if (target === path) {
      a.classList.add('nav-current');
      var drop = a.closest('.pd-nav-drop');
      if (drop) drop.classList.add('active-parent');
    }
  });

  /* Suppress browser context menu globally — right-click should only
     ever show our coded menus, never the browser default. */
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
  });
})();
