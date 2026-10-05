/* Puck Dynasty web news wire */
async function loadNews() {
  try {
    const res = await fetch('/api/news');
    const data = await res.json();
    renderNews(data);
  } catch (e) { console.error(e); }
}

function renderNews(data) {
  const feed = document.getElementById('news-feed');
  const items = data.items || [];
  document.getElementById('news-count').textContent =
    `${items.length} stor${items.length === 1 ? 'y' : 'ies'}`;
  document.getElementById('news-empty').hidden = items.length > 0;
  feed.innerHTML = '';

  let lastGroup = null;
  for (const item of items) {
    // date header when the day changes (groups consecutive same-day stories)
    const groupKey = item.date_label || 'Unknown date';
    if (groupKey !== lastGroup) {
      const h = document.createElement('div');
      h.className = 'news-day';
      h.innerHTML = `<span>📆</span> ${esc(groupKey)}`;
      feed.appendChild(h);
      lastGroup = groupKey;
    }
    const el = document.createElement('article');
    el.className = 'news-item';
    el.innerHTML = `<p>${esc(item.story)}</p>`;
    feed.appendChild(el);
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
}

loadNews();

// Shared heartbeat: tells the game the tab is still open (every 30s).
// If the tab goes silent the game shuts itself down cleanly.
(function () {
  const beat = () => fetch('/api/heartbeat', {method: 'POST'}).catch(() => {});
  beat();
  setInterval(beat, 30000);
})();
