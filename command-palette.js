/* VELXTRIA command palette: local navigation only; no network requests. */
(() => {
  'use strict';
  // Discover real destinations from the current page's navigation.
  // This prevents stale shortcuts and respects logged-out navigation.
  const links = Array.from(document.querySelectorAll('header nav a[href]'))
    .map(a => [a.textContent.trim().replace(/^✦\s*/, ''), a.getAttribute('href')])
    .filter(([title, url]) => title && url && url.startsWith('/') && !url.startsWith('//'));
  // Show the user's current position throughout the shared navigation.
  const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
  document.querySelectorAll('header nav a[href]').forEach(link => {
    const href = link.getAttribute('href');
    if (href && (href.replace(/\/$/, '') || '/') === currentPath) {
      link.setAttribute('aria-current', 'page');
    }
  });
  const unique = new Map();
  links.forEach(([title,url]) => { if (!unique.has(url)) unique.set(url,title); });
  const destinations = Array.from(unique, ([url,title]) => [title,url]);
  // Personal quick-launch stays in this browser; only known navigation paths are used.
  const STORE = 'vx-command-launch-v1';
  const allowed = new Set(destinations.map(([,url]) => url));
  const readState = () => {
    try {
      const value = JSON.parse(localStorage.getItem(STORE) || '{}');
      const valid = items => Array.isArray(items) ? [...new Set(items.filter(url =>
        typeof url === 'string' && allowed.has(url)))].slice(0, 8) : [];
      return {pinned:valid(value.pinned),recent:valid(value.recent)};
    } catch (_) { return {pinned:[],recent:[]}; }
  };
  let state = readState();
  const saveState = () => {
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (_) { /* private browsing */ }
  };
  if (allowed.has(currentPath)) {
    state.recent = [currentPath, ...state.recent.filter(url => url !== currentPath)].slice(0, 8);
    saveState();
  }
  const openButton = document.getElementById('vx-command-open');
  const dialog = document.getElementById('vx-command-dialog');
  const input = document.getElementById('vx-command-search');
  const results = document.getElementById('vx-command-results');
  if (!openButton || !dialog || !input || !results || !dialog.showModal) return;
  const render = () => {
    const q = input.value.trim().toLocaleLowerCase();
    const matches = destinations
      .map(([title,url]) => {
        const name = title.toLocaleLowerCase();
        const route = url.toLocaleLowerCase();
        const score = !q ? (state.pinned.includes(url) ? 3 : state.recent.includes(url) ? 2 : 0) :
          name === q ? 4 : name.startsWith(q) ? 3 :
          name.includes(q) ? 2 : route.includes(q) ? 1 : -1;
        return {title,url,score};
      })
      .filter(item => item.score >= 0)
      .sort((a,b) => b.score - a.score || a.title.localeCompare(b.title))
      .slice(0, 12);
    results.replaceChildren();
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.className = 'vx-command-empty';
      empty.textContent = 'No matching pages. Try a shorter search.';
      results.append(empty);
      return;
    }
    matches.forEach(({title,url},index) => {
      const link = document.createElement('a');
      link.href = url;
      link.className = 'vx-command-result';
      const label = document.createElement('strong');
      label.textContent = title;
      const detail = document.createElement('small');
      detail.textContent = url;
      link.append(label,detail);
      if (index === 0) link.dataset.first = 'true';
      const row = document.createElement('div');
      row.className = 'vx-command-item';
      const pin = document.createElement('button');
      pin.type = 'button';
      pin.className = 'vx-command-pin';
      const pinned = state.pinned.includes(url);
      pin.textContent = pinned ? '★' : '☆';
      pin.setAttribute('aria-label', (pinned ? 'Unpin ' : 'Pin ') + title);
      pin.setAttribute('aria-pressed', String(pinned));
      pin.title = pinned ? 'Remove from quick launch' : 'Add to quick launch';
      pin.addEventListener('click', () => {
        state.pinned = pinned ? state.pinned.filter(item => item !== url) :
          [url, ...state.pinned.filter(item => item !== url)].slice(0, 8);
        saveState();
        render();
        const next = Array.from(results.querySelectorAll('.vx-command-pin'))
          .find(button => button.getAttribute('aria-label').endsWith(title));
        if (next) next.focus();
      });
      row.append(link,pin);
      results.append(row);
    });
  };
  const open = () => {
    if (!dialog.open) dialog.showModal();
    input.value = '';
    render();
    input.focus();
  };
  openButton.addEventListener('click', open);
  input.addEventListener('input', render);
  input.addEventListener('keydown', event => {
    const items = Array.from(results.querySelectorAll('a'));
    if (event.key === 'ArrowDown' && items.length) {
      event.preventDefault();
      items[0].focus();
    } else if (event.key === 'Enter' && items.length) {
      event.preventDefault();
      window.location.assign(items[0].href);
    }
  });
  results.addEventListener('keydown', event => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    const items = Array.from(results.querySelectorAll('a'));
    const current = items.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    if (event.key === 'ArrowUp' && current === 0) input.focus();
    else items[(current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus();
  });
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (dialog.open) dialog.close();
      else open();
    }
  });
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });
})();
