/* VELXTRIA command palette: local navigation only; no network requests. */
(() => {
  'use strict';
  const links = [
    ['Business OS','/business-os-v59','Workspace and operations'],
    ['Revenue Priority','/revenue-priority','Highest-priority revenue actions'],
    ['Live Priorities','/revenue-priority/live','Live revenue priorities'],
    ['Business Workspace','/workspace','Invoices, customers and tasks'],
    ['Revenue Command','/revenue-command','Revenue operations'],
    ['Sales Pipeline','/sales-pipeline','Deals and opportunities'],
    ['Growth Center','/growth-intelligence','Growth intelligence'],
    ['Business Agents','/business-agents-v59','Business agent tools'],
    ['Decision Lab','/sovereign-lab-v57','Decision support'],
    ['Command Center','/sovereign-unified-v56','Unified command'],
    ['Workflow Studio','/sovereign-workflows-v56','Workflow orchestration'],
    ['Reports','/','Reporting overview'],
    ['Account','/account','Account settings']
  ];
  const openButton = document.getElementById('vx-command-open');
  const dialog = document.getElementById('vx-command-dialog');
  const input = document.getElementById('vx-command-search');
  const results = document.getElementById('vx-command-results');
  if (!openButton || !dialog || !input || !results || !dialog.showModal) return;
  const render = () => {
    const q = input.value.trim().toLocaleLowerCase();
    const matches = links.filter(([title,,desc]) =>
      (title + ' ' + desc).toLocaleLowerCase().includes(q)).slice(0, 12);
    results.replaceChildren();
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.className = 'vx-command-empty';
      empty.textContent = 'No matching tools. Try revenue, workspace, or agents.';
      results.append(empty);
      return;
    }
    matches.forEach(([title,url,desc],index) => {
      const link = document.createElement('a');
      link.href = url;
      link.className = 'vx-command-result';
      const label = document.createElement('strong');
      label.textContent = title;
      const detail = document.createElement('small');
      detail.textContent = desc;
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
    if (event.key === 'Enter') {
      const first = results.querySelector('a');
      if (first) {
        event.preventDefault();
        window.location.assign(first.href);
      }
    }
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
