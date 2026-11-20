/* VELXTRIA command palette: local navigation only; no network requests. */
(() => {
  'use strict';
  // Discover real destinations from the current page's navigation.
  // This prevents stale shortcuts and respects logged-out navigation.
  const links = Array.from(document.querySelectorAll('header nav a[href]'))
    .map(a => [a.textContent.trim().replace(/^✦\s*/, ''), a.getAttribute('href')])
    .filter(([title, url]) => title && url && url.startsWith('/') && !url.startsWith('//'));
  const unique = new Map();
  links.forEach(([title,url]) => { if (!unique.has(url)) unique.set(url,title); });
  const destinations = Array.from(unique, ([url,title]) => [title,url]);
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
        const score = !q ? 0 : name === q ? 4 : name.startsWith(q) ? 3 :
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
      results.append(link);
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
