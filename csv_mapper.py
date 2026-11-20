"""Privacy-preserving browser-only sales CSV column mapper.

No uploaded bytes reach VELXTRIA until the visitor deliberately uses the
existing demo upload. This is an advisory preparation tool, not validation
or a server-side import.
"""
import html
import json

def page(required):
    if not isinstance(required, (list, tuple)) or len(required) != 8 or any(not isinstance(x, str) or not x for x in required) or len(set(required)) != len(required):
        raise ValueError("Invalid required CSV schema")
    schema = json.dumps(required).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return """<main style="max-width:850px;margin:3rem auto;padding:1.5rem">
<h1>Match your sales CSV columns</h1>
<p>Export a CSV with VELXTRIA's expected headers. All mapping and conversion happens in your browser; no file contents are uploaded by this tool. Review your result before using the demo.</p>
<p><strong>Limits:</strong> 5 MB input, 10,000 data rows. This tool preserves cell values, not their meaning. Never upload sensitive customer information to a public demo.</p>
<label for="source">Choose a CSV file</label> <input id="source" type="file" accept=".csv,text/csv">
<div id="mapping" aria-live="polite"></div><p id="feedback" role="status" aria-live="polite"></p>
<button id="export" type="button" disabled>Download mapped CSV</button>
<p><a href="/#try">Try your corrected CSV in the demo</a> · <a href="/register">Create a free account</a></p>
</main>
<script>
"use strict";
const REQUIRED = """ + schema + """;
const fileInput = document.getElementById("source");
const mapping = document.getElementById("mapping");
const feedback = document.getElementById("feedback");
const exportButton = document.getElementById("export");
let sourceRows = [], selectors = [];
function parseCSV(s) {
  const rows = []; let row = [], cell = "", quoted = false, ended = false;
  s = s.replace(/^\\uFEFF/, "");
  for (let i=0;i<s.length;i++) {
    const c=s[i];
    if (quoted) {
      if(c==='"' && s[i+1]==='"'){cell+='"';i++;}
      else if(c==='"'){quoted=false;ended=true;}
      else cell+=c;
    } else if (c==='"' && !cell && !ended) quoted=true;
    else if(c===',' ){row.push(cell);cell="";ended=false;}
    else if(c==='\\r'||c==='\\n'){
      if(c==='\\r'&&s[i+1]==='\\n')i++;
      row.push(cell);rows.push(row);row=[];cell="";ended=false;
    } else {
      if(ended || c==='"')throw Error("Invalid CSV quoting");
      cell+=c;
    }
  }
  if(quoted)throw Error("Unclosed quoted cell");
  if(cell!==""||row.length||ended){row.push(cell);rows.push(row);}
  return rows;
}
function csvCell(value) {
  let s=String(value);
  // Spreadsheet software may interpret formulas even in quoted CSV cells.
  // Prefix dangerous leading characters, including after whitespace.
  if (/^[\\s\\u0000-\\u001f]*[=+@-]/.test(s)) s="'"+s;
  return '"'+s.replace(/"/g,'""')+'"';
}
function update() {
  const indices=selectors.map(s=>Number(s.value));
  const valid=indices.every(i=>Number.isInteger(i)&&i>=0&&i<sourceRows[0].length)
    && new Set(indices).size===REQUIRED.length;
  exportButton.disabled=!valid;
  feedback.textContent=valid?"Ready to export. Check that each field contains the right data.":"Choose a different source column for every required field.";
}
fileInput.addEventListener("change",async()=>{
  sourceRows=[];selectors=[];mapping.replaceChildren();exportButton.disabled=true;
  const f=fileInput.files&&fileInput.files[0];
  if(!f)return;
  if(f.size>5*1024*1024){feedback.textContent="File exceeds 5 MB.";return;}
  try{
    const rows=parseCSV(await f.text());
    if(rows.length<2||rows.length>10001)throw Error("CSV needs 1–10,000 data rows");
    const width=rows[0].length;
    if(!width||width>200||rows.some(r=>r.length!==width))throw Error("Inconsistent CSV row widths");
    if(rows[0].some(h=>!h.trim()))throw Error("Empty source header");
    sourceRows=rows;
    for(const target of REQUIRED){
      const label=document.createElement("label");
      label.textContent=target+" → ";
      const select=document.createElement("select");
      const blank=document.createElement("option");blank.value="-1";blank.textContent="Select source column";select.append(blank);
      rows[0].forEach((header,i)=>{const option=document.createElement("option");option.value=String(i);option.textContent=header+" (column "+(i+1)+")";select.append(option);});
      const match=rows[0].findIndex(h=>h.trim().toLowerCase()===target.toLowerCase());
      if(match>=0)select.value=String(match);
      select.addEventListener("change",update);
      label.append(select);mapping.append(label,document.createElement("p"));selectors.push(select);
    }
    update();
  }catch(e){sourceRows=[];feedback.textContent="Cannot read CSV: "+e.message;}
});
exportButton.addEventListener("click",()=>{
  if(exportButton.disabled||!sourceRows.length)return;
  const indices=selectors.map(s=>Number(s.value));
  const rows=[REQUIRED,...sourceRows.slice(1).map(row=>indices.map(i=>row[i]))];
  const csv=rows.map(row=>row.map(csvCell).join(",")).join("\\r\\n")+"\\r\\n";
  const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  const a=document.createElement("a");a.href=url;a.download="velxtria-mapped.csv";
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
</script>""";
