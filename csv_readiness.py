"""Browser-only CSV readiness check for prospective VELXTRIA customers.

No files or parsed rows are sent to VELXTRIA. This is advisory only;
the real upload/report engine remains the source of truth.
"""
import html

MAX_BYTES = 5 * 1024 * 1024


def page(required, max_bytes=MAX_BYTES):
    """Render a public, no-login, local-only CSV preflight screen."""
    if not required or any(not isinstance(h, str) or not h.strip() for h in required):
        raise ValueError("A nonempty list of required CSV headers is necessary")
    import json
    encoded_headers = json.dumps(list(required)).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    # JSON inserted into script source, never into an HTML attribute.
    return """<section style="max-width:920px;margin:2rem auto;padding:1.5rem">
<h1>Check your sales CSV before uploading</h1>
<p>Check the file's size, column headers, and basic CSV structure <strong>on this device</strong>.
The file is not uploaded or stored by this checker. Only use sample or non-sensitive data in the actual demo.</p>
<p>This is a readiness check, not a guarantee that the report engine will accept every row.</p>
<label for="csv-ready-file">Choose a CSV file (5 MB maximum)</label>
<input id="csv-ready-file" type="file" accept=".csv,text/csv">
<div id="csv-ready-status" role="status" aria-live="polite">No file selected.</div>
<div id="csv-ready-results"></div>
<p><a href="/#try">Try the demo</a> · <a href="/register">Create a free account</a> · <a href="/">Back to home</a></p>
</section>
<script>
"use strict";
(function () {
const required = """ + encoded_headers + """;
const maxBytes = """ + str(int(max_bytes)) + """;
const input = document.getElementById('csv-ready-file');
const status = document.getElementById('csv-ready-status');
const results = document.getElementById('csv-ready-results');
function show(items) {
  results.replaceChildren();
  const ul = document.createElement('ul');
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    ul.appendChild(li);
  }
  results.appendChild(ul);
}
// Parse RFC-style quoted CSV, including escaped quotes and embedded newlines.
// Limit work to a 5 MB file, never transmit contents, and avoid innerHTML.
function parseCSV(source) {
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (quoted) {
      if (ch === '"') {
        if (source[i + 1] === '"') { field += '"'; i++; }
        else { quoted = false; closed = true; }
      } else { field += ch; }
    } else if (ch === ',' && !closed) {
      row.push(field); field = '';
    } else if (ch === ',' && closed) {
      row.push(field); field = ''; closed = false;
    } else if (ch === '\\n' || ch === '\\r') {
      if (ch === '\\r' && source[i + 1] === '\\n') i++;
      row.push(field); rows.push(row); row = []; field = ''; closed = false;
    } else if (ch === '"' && field === '' && !closed) {
      quoted = true;
    } else if (ch === '"' || closed) {
      throw new Error('Unexpected text after a quoted field');
    } else { field += ch; }
  }
  if (quoted) throw new Error('Unclosed quoted field');
  if (row.length || field !== '' || closed) { row.push(field); rows.push(row); }
  return rows;
}
input.addEventListener('change', async function () {
  const file = input.files && input.files[0];
  results.replaceChildren();
  if (!file) { status.textContent = 'No file selected.'; return; }
  if (file.size > maxBytes) { status.textContent = 'File exceeds 5 MB. Please export a smaller CSV.'; return; }
  if (!file.name.toLowerCase().endsWith('.csv')) { status.textContent = 'Choose a .csv file.'; return; }
  status.textContent = 'Checking locally…';
  try {
    let source = await file.text();
    if (source.charCodeAt(0) === 0xFEFF) source = source.slice(1);
    const rows = parseCSV(source);
    if (!rows.length) { status.textContent = 'Empty CSV.'; return; }
    const headers = rows[0].map(h => h.trim());
    const missing = required.filter(h => !headers.includes(h));
    const duplicates = headers.filter((h, i) => headers.indexOf(h) !== i);
    const inconsistent = rows.slice(1).filter(r => r.length !== headers.length).length;
    const notes = [
      'Required headers: ' + required.join(', '),
      'Data rows found: ' + Math.max(0, rows.length - 1),
      missing.length ? 'Missing headers: ' + missing.join(', ') : 'All required headers are present.',
      duplicates.length ? 'Duplicate column names: ' + [...new Set(duplicates)].join(', ') : 'No duplicate column names.',
      inconsistent ? inconsistent + ' rows have a different number of columns.' : 'Column counts are consistent.'
    ];
    if (headers.some(h => !h)) notes.push('One or more header names are blank.');
    show(notes);
    status.textContent = missing.length || duplicates.length || inconsistent || headers.some(h => !h)
      ? 'Fix the listed issues before trying the demo.'
      : 'Basic structure looks ready. Individual values still require report validation.';
  } catch (error) {
    status.textContent = 'Could not parse this CSV. Check quoting and file encoding.';
  }
});
})();
</script>"""
