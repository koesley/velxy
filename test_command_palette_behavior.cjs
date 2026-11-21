/* Browserless behavioral checks for command search. No npm dependencies. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync(require('node:path').join(__dirname, 'command-palette.js'), 'utf8');

function boot(scope, storage) {
  const elements = {};
  class Element {
    constructor(tag = 'div') {
      this.tagName = tag;
      this.children = [];
      this.dataset = {};
      this.listeners = {};
      this.attributes = {};
      this.textContent = '';
      this.value = '';
      this.open = false;
    }
    getAttribute(name) { return this.attributes[name] || null; }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    showModal() { this.open = true; }
    close() { this.open = false; }
    focus() { elements.active = this; }
    querySelectorAll(selector) {
      if (selector === 'a') return this.children.flatMap(child => child.children.filter(item => item.tagName === 'a'));
      if (selector === '.vx-command-pin') return this.children.flatMap(child => child.children.filter(item => item.className === 'vx-command-pin'));
      return [];
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  }
  const links = [
    ['Business OS','/business-os-v59'],
    ['Revenue Priority','/revenue-priority'],
    ['Reports','/']
  ].map(([title,url]) => {
    const a = new Element('a');
    a.textContent = title;
    a.setAttribute('href',url);
    return a;
  });
  const open = new Element('button');
  const dialog = new Element('dialog');
  const input = new Element('input');
  const results = new Element('div');
  const byId = {'vx-command-open':open,'vx-command-dialog':dialog,
    'vx-command-search':input,'vx-command-results':results};
  const document = {
    body: {dataset:{vxWorkspaceScope:scope}},
    querySelectorAll: selector => selector === 'header nav a[href]' ? links : [],
    getElementById: id => byId[id],
    createElement: tag => new Element(tag),
    addEventListener: () => {},
    get activeElement() { return elements.active; }
  };
  const localStorage = {
    getItem: key => storage[key] || null,
    setItem: (key,value) => { storage[key] = value; }
  };
  vm.runInNewContext(script, {document, localStorage,
    window:{location:{pathname:'/business-os-v59',assign:()=>{}}}}, {timeout:1000});
  assert.equal(links[0].getAttribute('aria-current'),'page');
  open.listeners.click();
  assert.equal(dialog.open,true);
  return {results,storage};
}

const storage = {
  'vx-command-launch-v2:101':JSON.stringify({pinned:['/revenue-priority','https://evil.invalid/','/revenue-priority'],recent:[]}),
  'vx-command-launch-v2:202':JSON.stringify({pinned:['/'],recent:[]})
};
const a = boot('101',storage);
const b = boot('202',storage);
assert.deepEqual(JSON.parse(storage['vx-command-launch-v2:101']).pinned,['/revenue-priority']);
assert.deepEqual(JSON.parse(storage['vx-command-launch-v2:202']).pinned,['/']);
const rowsA = a.results.children.filter(row => row.className === 'vx-command-item');
const rowsB = b.results.children.filter(row => row.className === 'vx-command-item');
assert.equal(rowsA[0].children[0].href,'/revenue-priority');
assert.equal(rowsB[0].children[0].href,'/');
console.log('Command center account isolation, safe shortcuts and quick-launch behavior: PASS');
