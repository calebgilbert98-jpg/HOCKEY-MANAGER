/* Puck Dynasty global nav behavior: dropdown toggles + current-page highlight. */
(function () {
  /* Disable Grammarly and browser spellcheck on all text inputs/textareas.
     This is a standalone game, not a web page — writing extensions should
     never inject into it. Grammarly respects data-gramm="false". */
  function _disableWritingExtensions(root) {
    try {
      (root || document).querySelectorAll('input[type="text"], input:not([type]), textarea, [contenteditable]').forEach(function (el) {
        el.setAttribute('data-gramm', 'false');
        el.setAttribute('data-gramm_editor', 'false');
        el.setAttribute('spellcheck', 'false');
        el.setAttribute('autocomplete', 'off');
      });
    } catch (e) { /* ignore */ }
  }
  _disableWritingExtensions(document);
  // Also catch dynamically-added inputs (modals, etc.)
  try {
    new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType === 1) _disableWritingExtensions(n);
        });
      });
    }).observe(document.body, {childList: true, subtree: true});
  } catch (e) { /* ignore */ }
})();

(function () {
  /* DISABLED 2026-10-06: the beforeunload shutdown beacon was killing the
     server on normal page navigations (not just window close), causing
     "connection refused" and slow loads. The 60s heartbeat timeout is
     sufficient fallback for actual window closes. */
  // window.addEventListener('beforeunload', function () {
  //   try { navigator.sendBeacon('/api/shutdown'); } catch (e) {}
  // });
})();
(function () {
  /* Multiplayer bar (Batch E): load the MP layer on every page. It
     self-activates only when a multiplayer game is live. */
  try {
    var _mpCss = document.createElement('link');
    _mpCss.rel = 'stylesheet';
    _mpCss.href = '/static/css/mp_bar.css';
    document.head.appendChild(_mpCss);
    var _mpJs = document.createElement('script');
    _mpJs.src = '/static/js/mp_bar.js';
    _mpJs.defer = true;
    document.head.appendChild(_mpJs);
  } catch (e) {}
})();

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

  /* Right-click handling lives in context_menu.js: it shows a custom menu
     for players/teams/staff and leaves the browser menu alone otherwise. */
})();
