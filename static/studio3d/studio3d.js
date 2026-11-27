/* 3D Generation: the Asset Generator mode for 3D assets (3d_Generation_Plan, Gate B of Phase 26).
 * Server side: the studio3d package and the /api/studio3d routes. The 3D view is viewport.js.
 *
 * What works today: bring in a binary FBX or a SWIFT ZIP, look at it, read its measurements and faults, name and
 * give roles to its parts, check a character's preparation, attach reference pictures sent from Reference
 * Generation, approve or deny, and export a SWIFT ZIP that can be brought back in. Every file is pending until
 * approved, and a pending one is deleted ten days after it arrived.
 * What does not: anything that needs a 3D model to be made or changed. No such tool is set up, so those tabs say so.
 *
 *   Studio3D.panel(host, tools) -> the element to show; the same element is put back after a redraw
 *     host   { pid, view(name) -> url, toast(text), openViewer(url) }
 *     tools  { layer() -> the element dialogs are added to, go(mode) -> switch the Asset Generator's mode }
 *   Studio3D.hide() stops the checking for running jobs.
 *
 * Kept only while the page is open: the camera, what is hidden or isolated, shading, the open tab and the selected
 * part. A fresh open starts on Geometry with nothing selected.
 */
window.Studio3D = (function () {
  'use strict';
  const root = document.createElement('div'); root.className = 's3 rg';
  let host = null, tools = null, info = null, list = null, asset = null, jobs = [], loadedFor = null, showing = false, timer = null;
  let tab = 'geometry', part = null, hidden = new Set(), isolated = null, viewer = null, viewerFailed = '', inView = null, viewNote = '';
  const look = { shading: 'solid', palette: false, faults: true, projection: 'perspective' };
  const exportChoice = { profile: 'standard', references: false };
  let lib = null; const libFilter = { q: '', type: '', favorite: false, archived: false, collection: '' };
  const TABS = [['geometry', 'Geometry'], ['optimization', 'Optimization'], ['components', 'Components'], ['uvs', 'UVs'], ['textures', 'Textures'], ['materials', 'Materials'], ['surface', 'Surface Editing'], ['character', 'Character Tools'], ['export', 'Export']];
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const el = html => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const num = n => n == null ? 'not counted' : Number(n).toLocaleString();
  const cap = s => s ? s[0].toUpperCase() + s.slice(1) : '';
  const bytes = n => n >= 1024 ** 3 ? (n / 1024 ** 3).toFixed(1) + ' GB' : n >= 1024 ** 2 ? (n / 1024 ** 2).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB';
  const lastKey = () => 'sd.studio3d.asset.' + host.pid;

  async function call(method, path, body, raw) {
    const r = await fetch('/api/studio3d' + path, { method, headers: raw ? { 'Content-Type': 'application/octet-stream' } : body ? { 'Content-Type': 'application/json' } : {}, body: raw || (body ? JSON.stringify(body) : undefined) });
    const out = await r.json().catch(() => ({})); if (!r.ok) throw new Error(out.error || 'The server could not do that.'); return out;
  }
  function dialog(title, html, buttons) {
    const back = document.activeElement;
    return new Promise(done => {
      const box = el(`<div class="ag-modal" role="alertdialog" aria-modal="true" aria-label="${esc(title)}"><div class="ag-modalbox ag-ask rg-dialog"><h2>${esc(title)}</h2><div class="rg-dialogbody">${html}</div>
        <div class="ag-askbtns"><span class="ag-grow"></span>${buttons.map(([label, , primary], i) => `<button type="button" data-i="${i}" class="${primary ? 'primary' : ''}">${esc(label)}</button>`).join('')}</div></div></div>`);
      const end = v => { document.removeEventListener('keydown', key); box.remove(); done(v); setTimeout(() => { if (back && back.isConnected) back.focus(); }, 0); };
      const key = ev => { if (ev.key === 'Escape') end(null); };
      box.querySelectorAll('[data-i]').forEach(b => { b.onclick = () => { const v = buttons[+b.dataset.i][1]; end(typeof v === 'function' ? v() : v); }; });
      box.onpointerdown = ev => { if (ev.target === box) end(null); };
      document.addEventListener('keydown', key); tools.layer().append(box); (box.querySelector('input') || box.querySelector('[data-i]')).focus();
    });
  }
  async function save(url, name) {
    const r = await fetch(url); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'That file could not be fetched.');
    const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob()); a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  }

  /* ---------- data ---------- */
  const geometry = () => asset ? asset.artifacts.filter(a => a.category === 'geometry') : [];
  const current = () => asset ? asset.artifacts.find(a => a.id === asset.selected.geometry) || null : null;
  const capability = key => (info.capabilities.find(c => c.capability === key) || { available: false, reason: 'Not built yet.' });
  const left = a => a.state === 'approved' ? 'Approved' : a.hours_left >= 24 ? `Pending · deleted in ${a.days_left} day${a.days_left > 1 ? 's' : ''}` : `Pending · deleted in ${Math.max(1, a.hours_left)} hour${a.hours_left > 1 ? 's' : ''}`;
  const pill = a => `<span class="pill rg-state rg-${a.state}" title="${a.state === 'approved' ? 'Kept until you delete it.' : `Not approved yet. Unapproved files are deleted ${info.retention_days} days after they arrive.`}">${left(a)}</span>`;

  async function boot() {
    if (!host.pid) { root.innerHTML = '<section class="panel hint">Open a project first.</section>'; return; }
    try {
      if (!info) info = await call('GET', '/info');
      list = await call('GET', '/assets?project=' + encodeURIComponent(host.pid));
      loadedFor = host.pid;
      let want = asset && list.assets.some(a => a.id === asset.id) ? asset.id : null;
      if (!want) { try { want = localStorage.getItem(lastKey()); } catch (e) { /* private browsing */ } }
      if (want && list.assets.some(a => a.id === want)) await open(want, true); else { asset = null; draw(); }
      refreshJobs(); loadLibrary();
    } catch (e) { root.innerHTML = `<section class="panel hint">${esc(e.message)}</section>`; }
  }
  async function open(id, quiet) {
    try { take(await call('GET', '/asset?id=' + encodeURIComponent(id))); }
    catch (e) { asset = null; if (!quiet) host.toast(e.message); draw(); }
  }
  function take(fresh) {
    if (!asset || asset.id !== fresh.id) { part = null; hidden = new Set(); isolated = null; }
    asset = fresh;
    try { localStorage.setItem(lastKey(), asset.id); } catch (e) { /* private browsing */ }
    const c = current(); if (part && !(c && c.components.some(x => x.id === part))) part = null;
    draw();
  }
  async function relist() { try { list = await call('GET', '/assets?project=' + encodeURIComponent(host.pid)); } catch (e) { /* the next action reports it */ } }
  async function act(fn, done) { try { const out = await fn(); if (out && out.id && out.artifacts) take(out); await relist(); draw(); if (done) host.toast(done); return out; } catch (e) { host.toast(e.message); draw(); return null; } }
  async function refreshJobs() {
    clearTimeout(timer); if (!showing || !host.pid) return;
    try { const before = JSON.stringify(jobs); jobs = (await call('GET', '/jobs?project=' + encodeURIComponent(host.pid))).jobs; if (before !== JSON.stringify(jobs)) drawJobs(); } catch (e) { /* shown on the next action */ }
    if (jobs.some(j => ['waiting', 'running', 'cancelling', 'awaiting force-stop confirmation'].includes(j.state))) timer = setTimeout(refreshJobs, 2500);
  }

  /* ---------- bringing files in ---------- */
  async function bring(file, into, approve) {
    if (!file) return;
    if (file.size > info.max_import) { host.toast('That file is larger than the studio reads.'); return; }
    host.toast(`Reading ${file.name}…`);
    const q = new URLSearchParams({ project: host.pid, name: file.name }); if (into) q.set('asset', into); if (approve) q.set('approve', '1');
    try {
      const out = await call('POST', '/import?' + q, null, file);
      take(out.asset); await relist(); draw();
      host.toast([`Imported ${file.name}.`, ...(out.notes || [])].join(' '));
    } catch (e) { host.toast(e.message); }
    refreshJobs();
  }

  /* ---------- approve, deny, export ---------- */
  async function approve(a, confirmed) {
    try {
      const out = await call('POST', '/approve', { asset: asset.id, ids: [a.id], confirmed: !!confirmed });
      if (out.needs) {
        const rows = out.needs.map(n => `<li><span><b>${esc(n.name)}</b> (${esc(n.category)}, ${bytes(n.size)}). ${esc(n.reason || 'Needed by the file you are approving.')}</span></li>`).join('');
        const go = await dialog('Approve Required Dependencies', `<p>The file you are approving depends on other files that have not been approved for permanent storage. They are needed to keep it complete. If they are not kept, it may become incomplete when they expire. Approve this file and everything it needs (${bytes(out.bytes)} more)?</p><ul class="rg-needs">${rows}</ul>`, [['Cancel', null], ['Approve All', 'yes', true]]);
        if (go) return approve(a, true);
        return;
      }
      take(out.asset); await relist(); draw(); host.toast('Approved. It is kept until you delete it.');
    } catch (e) { host.toast(e.message); }
  }
  async function deny(a) {
    const go = await dialog('Deny and delete', `<p><b>${esc(a.name)}</b> will be deleted from SWIFT Director now. This cannot be undone.</p>`, [['Cancel', null], ['Deny and delete', 'yes', true]]);
    if (go) act(() => call('POST', '/deny', { asset: asset.id, ids: [a.id] }), 'Denied and deleted.');
  }
  async function runExport(button, confirmed) {
    try {
      const out = await call('POST', '/export', { asset: asset.id, profile: exportChoice.profile, references: exportChoice.references, confirmed: !!confirmed });
      if (out.needs_confirmation) {
        const rows = out.plan.pending.map(p => `<li><span><b>${esc(p.name)}</b>${p.hours_left != null ? ` · deleted in ${p.hours_left >= 24 ? Math.ceil(p.hours_left / 24) + ' days' : Math.max(1, p.hours_left) + ' hours'}` : ''}</span></li>`).join('');
        const go = await dialog('Export Unapproved Asset', `<p>This export contains files that have not been approved for permanent storage. They will be deleted from SWIFT Director when their time runs out unless you approve them first. Exporting does not approve them or give them more time. Your downloaded copy is not affected when the local ones are deleted. Continue?</p><p><b>${esc(asset.name)}</b></p><ul class="rg-needs">${rows}</ul>`, [['Cancel', null], ['Continue Export', 'yes', true]]);
        if (go) return runExport(button, true);
        return;
      }
      await save('/api/studio3d/export/file?id=' + encodeURIComponent(out.id), out.name);
      host.toast(`Exported ${out.name} (${bytes(out.size)}).${out.pending ? ' Nothing in it was approved by exporting.' : ''}`);
    } catch (e) { host.toast(e.message); }
    finally { refreshJobs(); }
  }

  /* ---------- the 3D view ---------- */
  function syncView() {
    if (!viewer) return;
    const c = current(), byId = c ? Object.fromEntries(c.components.map(x => [x.id, x])) : {};
    viewer.setShading(look.shading); viewer.setPalette(look.palette); viewer.showDefects(look.faults); viewer.setProjection(look.projection);
    viewer.setHidden([...hidden].map(id => byId[id] && byId[id].source_model).filter(Boolean));
    viewer.isolate(isolated && byId[isolated] ? byId[isolated].source_model : null);
    viewer.select(part && byId[part] ? byId[part].source_model : null);
  }
  async function showInView() {
    const c = current(), key = c ? asset.id + '/' + c.id : null;
    if (!viewer || key === inView) { syncView(); return; }
    inView = key; viewNote = '';
    if (!c) { viewer.clear(); return; }
    try {
      const r = await fetch(`/api/studio3d/file?asset=${encodeURIComponent(asset.id)}&artifact=${encodeURIComponent(c.id)}`);
      if (!r.ok) throw new Error('The file could not be fetched.');
      const got = await viewer.load(await r.arrayBuffer());
      if (key !== inView) return;
      const unit = c.report.conventions.unit_scale, cm = got.step * unit;
      viewNote = `Each grid square is ${cm >= 100 ? (cm / 100) + ' m' : +cm.toFixed(3) + ' cm'}.`;
      if (c.report.defects.some(d => d.faces.length)) { try { viewer.setDefects((await call('GET', `/defects?asset=${encodeURIComponent(asset.id)}&artifact=${encodeURIComponent(c.id)}`)).defects); } catch (e) { /* the list still names them */ } }
      syncView();
    } catch (e) { viewNote = 'This file could not be drawn: ' + (e.message || 'it has something the view cannot read') + ' Its measurements are still shown.'; viewer.clear(); }
    const note = root.querySelector('.s3-viewnote'); if (note) note.textContent = viewNote;
  }
  function viewBox() {
    const g = viewer ? viewer.grids() : { x: false, y: true, z: false };
    const box = el(`<div class="s3-stage"><div class="s3-bar" role="toolbar" aria-label="3D view">
        <span class="s3-group">${['front', 'back', 'left', 'right', 'top', 'bottom', 'perspective'].map(v => `<button class="small" type="button" data-look="${v}" data-k="look-${v}">${v === 'perspective' ? '3/4' : cap(v)}</button>`).join('')}</span>
        <button class="small" type="button" data-k="frame" data-frame title="Fit ${part ? 'the selected part' : 'everything'} in the picture">Frame</button>
        <label class="s3-inline">Lens <select data-k="projection" data-opt="projection"><option value="perspective">Perspective</option><option value="orthographic">Orthographic</option></select></label>
        <label class="s3-inline">Surface <select data-k="shading" data-opt="shading"><option value="solid">Solid</option><option value="wire">Wireframe</option><option value="both">Solid with wireframe</option></select></label>
        <label class="s3-inline" title="Give each part its own colour so parts can be told apart. This is only for looking; it is not the asset's material."><input type="checkbox" data-k="palette" data-opt="palette"> Colour by part</label>
        <label class="s3-inline" title="Mark the faces the checks found faults in"><input type="checkbox" data-k="faults" data-opt="faults"> Mark faults</label>
        <span class="s3-group"><span class="ag-label">Grid</span>${['x', 'y', 'z'].map(k => `<label class="ag-grid ag-grid-${k}"><input type="checkbox" data-k="grid-${k}" data-g="${k}"${g[k] ? ' checked' : ''}> ${k.toUpperCase()}</label>`).join('')}</span></div>
      <div class="ag-3dhold s3-hold"><div class="hint ag-3dwait">${current() ? 'Starting the 3D view…' : 'Nothing to show yet. Import an FBX, a GLB or a SWIFT ZIP.'}</div></div>
      <div class="hint">Drag to turn, right-drag (or two fingers) to move, scroll to zoom. <span class="s3-viewnote">${esc(viewNote)}</span> What you set here is only for looking and is not saved.</div></div>`);
    const hold = box.querySelector('.s3-hold');
    box.querySelectorAll('[data-opt]').forEach(c => { const k = c.dataset.opt; if (c.type === 'checkbox') c.checked = look[k]; else c.value = look[k];
      c.onchange = () => { look[k] = c.type === 'checkbox' ? c.checked : c.value; syncView(); }; });
    box.querySelectorAll('[data-look]').forEach(b => { b.onclick = () => viewer && viewer.look(b.dataset.look); });
    box.querySelector('[data-frame]').onclick = () => { const c = current(), x = c && part ? c.components.find(y => y.id === part) : null; if (viewer) viewer.frame(x ? x.source_model : null); };
    box.querySelectorAll('[data-g]').forEach(c => { c.onchange = () => viewer && viewer.setGrid(c.dataset.g, c.checked); });
    const place = () => { if (!current()) { if (viewer) { viewer.clear(); inView = null; } return; } hold.innerHTML = ''; hold.append(viewer.element); showInView(); };
    if (viewer) place();
    else if (viewerFailed) hold.firstElementChild.textContent = 'The 3D view could not start: ' + viewerFailed + ' Measurements and checks still work.';
    else import('./viewport.js?v=1').then(m => { if (!viewer) viewer = m.create({}); if (hold.isConnected) place(); else if (showing) draw(); })
      .catch(e => { viewerFailed = (e.message || 'this browser has no WebGL') + '.'; if (hold.isConnected) hold.firstElementChild.textContent = 'The 3D view could not start: ' + viewerFailed + ' Measurements and checks still work.'; });
    return box;
  }

  /* ---------- the parts of the page ---------- */
  function head() {
    const s = list.storage, c = current();
    const box = el(`<section class="panel s3-head"><div class="rg-fields">
        <label class="ag-label">3D asset<select data-k="asset" class="s3-asset"><option value="">${list.assets.length ? 'Choose an asset…' : 'No 3D assets yet'}</option>${list.assets.map(a => `<option value="${esc(a.id)}"${asset && a.id === asset.id ? ' selected' : ''}>${esc(a.name)}${a.pending ? ` (${a.pending} pending)` : ''}</option>`).join('')}</select></label>
        <button type="button" class="s3-import primary" data-k="import">Import FBX, GLB or SWIFT ZIP</button><input type="file" class="s3-pick" accept=".fbx,.glb,.zip" hidden>
        <label class="s3-inline" title="Keep the imported file permanently straight away instead of reviewing it first"><input type="checkbox" class="s3-approve" data-k="approve-on-import"> Approve on import</label>
        ${asset ? `<label class="s3-inline" title="Add the next file to the open asset as another candidate instead of making a new asset"><input type="checkbox" class="s3-into" data-k="into"> Add to this asset</label>` : ''}
        <span class="ag-grow"></span>${asset ? `<button type="button" class="small" data-k="tolib" data-do="tolib"${c && c.state === 'approved' ? ' title="Keep the selected file in the asset library, for use in any project"' : ' disabled title="Only an approved file can go in the library. Approve the selected file first."'}>Add to Library</button>` : ''}${asset ? '<button type="button" class="small" data-k="copy" data-do="copy">Duplicate</button><button type="button" class="small ghost" data-k="delete" data-do="delete">Delete asset</button>' : ''}</div>
      ${asset ? `<div class="s3-context"><b>${esc(asset.name)}</b><span>${esc(asset.parent_label)} / ${esc(asset.type_label)}${asset.subtype ? ' / ' + esc(asset.subtype === 'Custom' ? asset.custom_subtype || 'Custom' : asset.subtype) : ''}</span>
          <span>${c ? 'Showing: ' + esc(c.name) + ' ' + pill(c) : 'No geometry yet'}</span>${asset.busy.length ? `<span class="pill rg-pending">${esc(asset.busy[0].label)}: ${esc(asset.busy[0].state)}</span>` : ''}</div>` : ''}
      <div class="hint s3-storage">Storage: ${bytes(s.approved)} approved, ${bytes(s.pending)} pending, ${bytes(s.free)} free on the disk. New work stops when less than ${bytes(s.floor_bytes)} is free. Files are binary FBX; ${esc(info.conventions)} is what the studio expects.
        <button type="button" class="small ghost" data-k="cleanup" data-do="cleanup" title="Delete every pending file whose ${info.retention_days} days have run out, now rather than at the next hourly check">Clean Up Now</button></div>
      <div class="hint s3-storage">${info.converter.tested ? `GLB files are converted to FBX by Blender ${esc(info.converter.blender)}, which passed its test on this computer.` : `<span class="pill rg-pending">GLB import is off</span> ${esc(info.converter.reason)}${info.converter.running ? '' : ' It is set up by the update script.'}`}
        ${info.converter.running ? `<button type="button" class="small${info.converter.tested ? ' ghost' : ''}" data-k="convtest" data-do="convtest" title="Convert a known one-metre cube with Blender and check that it comes out the right size, the right way up and in the right place">${info.converter.tested ? 'Test the converter again' : 'Test the converter'}</button>` : '<button type="button" class="small ghost" data-k="convcheck" data-do="convcheck">Check again</button>'}</div></section>`);
    const file = box.querySelector(".s3-pick");
    box.querySelector('.s3-asset').onchange = ev => { if (ev.target.value) open(ev.target.value); else { asset = null; draw(); } };
    box.querySelector('.s3-import').onclick = () => file.click();
    file.onchange = () => { const into = box.querySelector('.s3-into'); bring(file.files[0], into && into.checked ? asset.id : null, box.querySelector('.s3-approve').checked); file.value = ''; };
    box.querySelectorAll('[data-do]').forEach(b => { b.onclick = async () => {
      if (b.dataset.do === 'convcheck') { try { info = await call('GET', '/info'); draw(); } catch (e) { host.toast(e.message); } }
      if (b.dataset.do === 'convtest') { b.disabled = true; b.textContent = 'Testing…';
        try { const out = await call('POST', '/converter/test', {}); info.converter = out.converter; draw(); host.toast(out.passed ? `The converter passed with Blender ${out.blender}. GLB files can be imported.` : 'The converter did not pass: ' + out.problems.join('; ') + '. GLB import stays off.'); } catch (e) { host.toast(e.message); draw(); } }
      if (b.dataset.do === 'tolib') { try { await call('POST', '/library/add', { asset: asset.id }); host.toast('Added to the library. It is kept there even if this asset is deleted.'); loadLibrary(); } catch (e) { host.toast(e.message); } }
      if (b.dataset.do === 'copy') act(() => call('POST', '/asset/copy', { id: asset.id }), 'Duplicated. The copy shares the same stored files until one of them changes.');
      if (b.dataset.do === 'cleanup') { try { const out = await call('POST', '/cleanup'); list.storage = out.storage; host.toast(out.expired ? `Deleted ${out.expired} expired file${out.expired === 1 ? '' : 's'} and freed ${bytes(out.freed)}.` : 'Nothing had expired.'); if (asset) await open(asset.id, true); await relist(); draw(); } catch (e) { host.toast(e.message); } }
      if (b.dataset.do === 'delete') { const keep = asset.artifacts.filter(a => a.state === 'approved').length;
        const go = await dialog('Delete asset', `<p><b>${esc(asset.name)}</b> and its ${asset.artifacts.length} file${asset.artifacts.length === 1 ? '' : 's'}${keep ? `, including ${keep} approved` : ''}, will be deleted from SWIFT Director. This cannot be undone.</p>`, [['Cancel', null], ['Delete asset', 'yes', true]]);
        if (go) { try { await call('POST', '/asset/delete', { id: asset.id }); asset = null; inView = null; await relist(); draw(); host.toast('Deleted.'); } catch (e) { host.toast(e.message); } } }
    }; });
    return box;
  }

  function tree() {
    const c = current(), box = el('<aside class="panel s3-tree"><h2>Parts</h2></aside>');
    if (!c) { box.append(el('<p class="hint">The parts of the file appear here once there is geometry.</p>')); return box; }
    const kids = id => c.components.filter(x => (x.parent || null) === id);
    const ul = el('<ul class="s3-nodes" role="tree" aria-label="Parts of the selected file"></ul>');
    const add = (x, depth) => {
      const off = hidden.has(x.id), li = el(`<li role="treeitem" aria-selected="${x.id === part}" class="${x.id === part ? 'on' : ''}" style="--d:${depth}">
        <button type="button" class="s3-node" data-k="node-${esc(x.id)}" title="${x.node === 'mesh' ? num(x.vertices) + ' control points' : 'A group'}">${esc(x.name)}${x.role ? ` <span class="hint">${esc(x.role)}</span>` : ''}${x.locked ? ' <span class="pill s3-lock" title="Locked: its name, role and side cannot be changed until it is unlocked">🔒 Locked</span>' : ''}</button>
        <button type="button" class="small ghost" data-k="eye-${esc(x.id)}" data-eye aria-pressed="${off}" title="${off ? 'Show' : 'Hide'} in the 3D view. Not saved.">${off ? 'Hidden' : 'Shown'}</button>
        <button type="button" class="small ghost" data-k="iso-${esc(x.id)}" data-iso aria-pressed="${isolated === x.id}" title="Show only this in the 3D view. Not saved.">${isolated === x.id ? 'Only this' : 'Isolate'}</button></li>`);
      li.querySelector('.s3-node').onclick = () => { part = part === x.id ? null : x.id; if (part && tab !== 'character') tab = 'components'; draw(); };
      li.querySelector('[data-eye]').onclick = () => { off ? hidden.delete(x.id) : hidden.add(x.id); draw(); };
      li.querySelector('[data-iso]').onclick = () => { isolated = isolated === x.id ? null : x.id; draw(); };
      ul.append(li); kids(x.id).forEach(k => add(k, depth + 1));
    };
    kids(null).forEach(x => add(x, 0));
    c.components.filter(x => x.parent && !c.components.some(y => y.id === x.parent)).forEach(x => add(x, 0));
    box.append(ul);
    if (hidden.size || isolated) { const b = el('<button type="button" class="small" data-k="showall">Show everything</button>'); b.onclick = () => { hidden = new Set(); isolated = null; draw(); }; box.append(b); }
    return box;
  }

  const unavailable = (title, key, has) => { const c = key ? capability(key) : null;
    return el(`<div class="s3-pane"><h2>${esc(title)}</h2><div class="rg-blocked"><b>Not available yet.</b> ${esc(c ? c.reason : 'This part of the studio has not been built.')}</div>
      <p class="hint">Nothing on this tab can change the asset. ${has || ''}</p></div>`); };

  function geometryPane() {
    const pane = el('<div class="s3-pane"></div>'), c = current(), t = info.types.find(x => x.key === asset.type) || { subtypes: [] }, q = info.quality[asset.quality], gen = capability('geometry.generate');
    const groups = {}; info.types.forEach(x => { (groups[x.parent_label] = groups[x.parent_label] || []).push(x); });
    pane.append(el(`<div><h2>Asset</h2><div class="s3-form">
      <label class="ag-label">Name<input type="text" maxlength="80" data-k="f-name" data-f="name" value="${esc(asset.name)}"></label>
      <label class="ag-label">Type<select data-k="f-type" data-f="type">${Object.entries(groups).map(([g, ts]) => `<optgroup label="${esc(g)}">${ts.map(x => `<option value="${x.key}"${x.key === asset.type ? ' selected' : ''}>${esc(x.label)}</option>`).join('')}</optgroup>`).join('')}</select></label>
      <label class="ag-label">Subtype<select data-k="f-subtype" data-f="subtype"><option value="">Not set</option>${t.subtypes.map(s => `<option${s === asset.subtype ? ' selected' : ''}>${esc(s)}</option>`).join('')}</select></label>
      <label class="ag-label">Status<select data-k="f-production" data-f="production">${info.production.map(p => `<option value="${p}"${p === asset.production ? ' selected' : ''}>${cap(p)}</option>`).join('')}</select></label>
      <label class="ag-label">Quality<select data-k="f-quality" data-f="quality">${Object.entries(info.quality).map(([k, v]) => `<option value="${k}"${k === asset.quality ? ' selected' : ''}>${cap(k)} (${num(v.low)} to ${num(v.high)})</option>`).join('')}</select></label>
      <label class="ag-label">Target control points<input type="number" data-k="f-target" data-f="target_vertices" min="${q.low}" max="${q.high}" step="100" value="${asset.target_vertices}"></label></div>
      <p class="hint">The status is your own note of where the work stands. It does not approve anything, and approving does not change it.</p></div>`));
    pane.querySelectorAll('[data-f]').forEach(i => { i.onchange = () => act(() => call('PUT', '/asset?id=' + encodeURIComponent(asset.id), { fields: { [i.dataset.f]: i.type === 'number' ? +i.value : i.value } })); });

    const files = el(`<div><h2>Files</h2><p class="hint">Each import is a candidate. The selected one is what the view, the checks and an export use. Selecting does not approve.</p><div class="s3-files"></div>
      <div class="rg-blocked" title="${esc(gen.reason)}"><b>Generate from reference pictures: not available.</b> ${esc(gen.reason)}</div></div>`);
    geometry().forEach(a => { const sel = a.id === asset.selected.geometry;
      const row = el(`<div class="s3-file${sel ? ' on' : ''}"><div><b>${esc(a.name)}</b> ${pill(a)}${sel ? ' <span class="pill rg-selected">Selected</span>' : ''}<div class="hint">${cap(a.origin)} · ${bytes(a.size)} · ${num(a.report.totals.vertices)} control points</div></div>
        <span class="rg-actions">${sel ? '' : `<button type="button" class="small" data-a="select" data-k="sel-${esc(a.id)}">Select</button>`}${a.state === 'pending' ? `<button type="button" class="small" data-a="approve" data-k="ok-${esc(a.id)}">Approve</button>` : ''}
          <button type="button" class="small" data-a="deny" data-k="no-${esc(a.id)}">${a.state === 'pending' ? 'Deny' : 'Delete'}</button><button type="button" class="small ghost" data-a="save" data-k="dl-${esc(a.id)}">Download FBX</button></span></div>`);
      row.querySelectorAll('[data-a]').forEach(b => { b.onclick = async () => {
        if (b.dataset.a === 'select') act(() => call('POST', '/select', { asset: asset.id, artifact: a.id }));
        if (b.dataset.a === 'approve') approve(a);
        if (b.dataset.a === 'deny') deny(a);
        if (b.dataset.a === 'save') { if (a.state === 'pending' && !await dialog('Export Unapproved Asset', `<p>This file has not been approved for permanent storage. It will be deleted from SWIFT Director when its time runs out (${esc(left(a).replace('Pending · ', ''))}) unless you approve it first. Downloading does not approve it or give it more time. Your downloaded copy is not affected when the local one is deleted. Continue?</p>`, [['Cancel', null], ['Continue Export', 'yes', true]])) return;
          save(`/api/studio3d/file?asset=${encodeURIComponent(asset.id)}&artifact=${encodeURIComponent(a.id)}`, /\.fbx$/i.test(a.name) ? a.name : a.name + '.fbx').catch(e => host.toast(e.message)); }
      }; });
      files.querySelector('.s3-files').append(row); });
    asset.artifacts.filter(a => a.category === 'source').forEach(a => { const made = asset.artifacts.find(x => x.id === a.made);
      const row = el(`<div class="s3-file"><div><b>${esc(a.name)}</b> <span class="pill">Source file</span> ${pill(a)}<div class="hint">${made ? `What ${esc(made.name)} was converted from` : 'The file it was converted to is gone'} · ${bytes(a.size)} · kept as it arrived; not needed by the FBX</div></div>
        <span class="rg-actions">${a.state === 'pending' ? `<button type="button" class="small" data-a="approve" data-k="ok-${esc(a.id)}">Approve</button>` : ''}<button type="button" class="small" data-a="deny" data-k="no-${esc(a.id)}">${a.state === 'pending' ? 'Deny' : 'Delete'}</button><button type="button" class="small ghost" data-a="save" data-k="dl-${esc(a.id)}">Download</button></span></div>`);
      row.querySelector('[data-a="approve"]') && (row.querySelector('[data-a="approve"]').onclick = () => approve(a));
      row.querySelector('[data-a="deny"]').onclick = () => deny(a);
      row.querySelector('[data-a="save"]').onclick = () => save(`/api/studio3d/file?asset=${encodeURIComponent(asset.id)}&artifact=${encodeURIComponent(a.id)}`, a.name).catch(e => host.toast(e.message));
      files.querySelector('.s3-files').append(row); });
    if (!geometry().length) files.querySelector('.s3-files').append(el('<p class="hint">No files yet. Use Import with “Add to this asset” ticked, or import to make a new asset.</p>'));
    pane.append(files);
    if (c) pane.append(measures(c), faults(c));
    pane.append(references());
    return pane;
  }
  function measures(c) {
    const t = c.report.totals, b = asset.budget, v = c.report.conventions, size = t.size_cm;
    const diff = b.measured == null ? '' : b.difference === 0 ? 'exactly on target' : `${num(Math.abs(b.difference))} ${b.difference > 0 ? 'over' : 'under'} the target of ${num(b.target)}`;
    return el(`<div><h2>Measurements</h2><dl class="s3-facts">
      <dt>Control points</dt><dd>${num(t.vertices)} <span class="hint">${diff}${b.measured != null ? `; ${b.within_profile ? 'within' : 'outside'} the ${cap(b.profile)} range` + (b.within_profile ? '' : b.measured_profile === 'below' ? ', fewer than any quality range' : b.measured_profile === 'above' ? ', more than any quality range' : `, this is ${cap(b.measured_profile)} quality by count`) : ''}</span></dd>
      <dt>Faces</dt><dd>${num(t.faces)} <span class="hint">${num(t.tris)} triangles, ${num(t.quads)} quads, ${num(t.ngons)} with more sides</span></dd>
      <dt>Triangles when drawn</dt><dd>${num(t.triangles)}</dd><dt>Edges</dt><dd>${num(t.edges)}${t.boundary_edges ? ` <span class="hint">${num(t.boundary_edges)} open</span>` : ''}</dd>
      <dt>Size</dt><dd>${size ? size.map(n => +n.toFixed(1)).join(' × ') + ' cm <span class="hint">width × height × length' + (t.approximate_bounds ? ', approximate: the file uses pivots this reader does not apply' : '') + '</span>' : 'not measured'}</dd>
      <dt>Axes and units</dt><dd>${esc(v.up)} up, ${esc(v.front)} front, 1 unit = ${+v.unit_scale.toFixed(4)} cm <span class="pill ${v.canonical ? 'rg-approved' : 'rg-pending'}">${v.canonical ? 'Matches the studio' : 'Differs from the studio'}</span>${v.canonical ? '' : `<div class="hint">${esc(v.notes.join(' '))} The file is kept exactly as it is; the studio cannot convert it yet.</div>`}</dd>
      <dt>Carried in the file</dt><dd class="hint">${num(c.report.rigging.skeleton)} bones, ${num(c.report.rigging.skin)} skin bindings, ${num(c.report.rigging.blend_shapes)} blend shape sets, ${num(c.report.rigging.animation)} animations, ${num(c.report.rigging.materials)} materials, ${num(c.report.rigging.textures)} texture links. All kept as they are.</dd></dl>
      ${(c.report.limits || []).map(l => `<p class="hint">${esc(l)}</p>`).join('')}</div>`);
  }
  const SEVERITY = { 'technical failure': '✕ Failure', 'significant defect': '! Defect', 'warning': '! Warning', 'informational': 'i Note' };
  function faults(c) {
    const d = c.report.defects, names = Object.fromEntries(c.report.models.filter(m => m.geometry).map(m => [m.geometry, m.name]));
    return el(`<div><h2>Checks</h2>${d.length ? `<ul class="s3-issues" aria-label="Faults found">${d.map(x => `<li class="${x.severity === 'technical failure' || x.severity === 'significant defect' ? 's3-bad' : ''}"><b>${esc(SEVERITY[x.severity] || cap(x.severity))}</b> ${esc(cap(x.kind))} in ${esc(names[x.geometry] || 'a mesh')}: ${num(x.count)}. <span class="hint">${esc(x.description)}${x.faces.length ? ' Marked in the 3D view when Mark faults is on.' : ''}</span></li>`).join('')}</ul>` : '<p class="hint">✓ No faults found by the checks that were run: bad numbers, bad indices, collapsed, repeated and zero-area faces, edges shared by more than two faces, and unused points.</p>'}
      <p class="hint">Nothing is repaired automatically. These checks do not judge whether the shape looks right.</p></div>`);
  }
  function references() {
    const box = el(`<div><h2>Reference pictures</h2><p class="hint">Pictures made in Reference Generation can be attached to this asset. They are the same pictures, not copies: one denied or expired there shows as unavailable here. Attaching does not approve anything.</p><div class="s3-refs"></div><div class="s3-handed"></div></div>`);
    const refs = box.querySelector('.s3-refs');
    asset.references.forEach(r => { const what = r.direction ? cap(r.direction) : cap(r.roles[0]);
      const card = el(`<div class="rg-handitem${r.image ? '' : ' rg-missing'}">${r.image ? `<img alt="${esc(what)}" loading="lazy" src="${esc(host.view(r.image))}">` : '<span class="hint">Unavailable</span>'}<span>${esc(what)}${r.component ? ' · ' + esc(r.component) : ''} · ${r.state === 'approved' ? 'Approved' : r.state === 'pending' ? 'Pending' : 'Gone'}</span>
        <button type="button" class="small ghost" data-k="unref-${esc(r.id)}">Detach</button></div>`);
      const img = card.querySelector('img'); if (img) img.onclick = () => host.openViewer(host.view(r.image));
      card.querySelector('button').onclick = () => act(() => call('POST', '/reference', { asset: asset.id, ref: r.id, remove: true }));
      refs.append(card); });
    if (!asset.references.length) refs.append(el('<span class="hint">None attached.</span>'));
    const handed = box.querySelector('.s3-handed'), have = new Set(asset.references.map(r => r.artifact));
    list.handovers.forEach(h => { const fresh = h.items.filter(i => i.state !== 'gone' && !have.has(i.artifact));
      const row = el(`<div class="rg-fields"><span><b>${esc(h.name)}</b> <span class="hint">sent from Reference Generation · ${h.items.length} picture${h.items.length === 1 ? '' : 's'}${fresh.length ? '' : ' · all attached or gone'}</span></span><span class="ag-grow"></span>
        <button type="button" class="small" data-k="attach-${esc(h.id)}"${fresh.length ? '' : ' disabled'}>Attach ${fresh.length || ''} to this asset</button></div>`);
      row.querySelector('button').onclick = () => act(() => call('POST', '/references', { asset: asset.id, items: fresh.map(i => ({ artifact: i.artifact, direction: ['front', 'left', 'right', 'rear', 'top', 'bottom'].includes(i.role) ? i.role : '', role: i.role === 'sheet' ? 'primary' : '', component: i.component, reference_project: h.reference, row: i.row })) }), 'Attached.');
      handed.append(row); });
    const go = el(`<button type="button" class="small" data-k="to-reference">${list.handovers.length ? 'Open Reference Generation' : 'Nothing has been sent yet. Open Reference Generation'}</button>`); go.onclick = () => tools.go('reference'); handed.append(go);
    return box;
  }

  function componentsPane() {
    const c = current(); if (!c) return el('<div class="s3-pane"><h2>Components</h2><p class="hint">There is no geometry yet.</p></div>');
    const x = c.components.find(y => y.id === part), seg = capability('geometry.segment');
    const pane = el(`<div class="s3-pane"><h2>Components</h2><p class="hint">A component is one part the file already has: a mesh or a group. ${c.components.length} in this file. Names, roles, sides and locks are saved with the asset and go into an export; the file itself is not changed.</p>
      <div class="rg-blocked"><b>Splitting or joining meshes: not available.</b> ${esc(seg.reason)}</div></div>`);
    if (!x) { pane.append(el('<p class="hint">Choose a part in the list on the left to name it or give it a role.</p>')); return pane; }
    const roles = asset.character.roles, dis = x.locked ? ' disabled' : '';
    const form = el(`<div class="s3-form"><label class="ag-label">Name<input type="text" maxlength="80" data-k="c-name" data-c="name" value="${esc(x.name)}"${dis}></label>
      <label class="ag-label">Role<input type="text" maxlength="40" data-k="c-role" data-c="role" list="s3-roles" value="${esc(x.role)}" placeholder="${roles.length ? 'For example: ' + esc(roles[0]) : 'For example: Door'}"${dis}><datalist id="s3-roles">${roles.map(r => `<option value="${esc(r)}">`).join('')}</datalist></label>
      <label class="ag-label">Side<select data-k="c-side" data-c="side"${dis}>${info.sides.map(s => `<option value="${s}"${s === x.side ? ' selected' : ''}>${s ? cap(s) : 'Not set'}</option>`).join('')}</select></label>
      <label class="s3-inline"><input type="checkbox" data-k="c-locked" data-c="locked"${x.locked ? ' checked' : ''}> Locked</label></div>`);
    form.querySelectorAll('[data-c]').forEach(i => { i.onchange = () => act(() => call('POST', '/component', { asset: asset.id, artifact: c.id, component: x.id, fields: { [i.dataset.c]: i.type === 'checkbox' ? i.checked : i.value } })); });
    pane.append(form, el(`<dl class="s3-facts"><dt>Kind</dt><dd>${x.node === 'mesh' ? 'Mesh' : 'Group'}</dd>${x.node === 'mesh' ? `<dt>Control points</dt><dd>${num(x.vertices)}</dd><dt>Faces</dt><dd>${num(x.faces)}</dd><dt>UV channels</dt><dd>${x.uv_channels}</dd><dt>Material slots</dt><dd>${x.material_slots}</dd>` : ''}
      <dt>Position in the file</dt><dd>${x.transform.position.map(n => +n.toFixed(2)).join(', ')}</dd></dl>`));
    return pane;
  }

  const CHECK = { pass: '✓ Pass', warn: '! Warning', fail: '✕ Fail', manual: '? Needs your check', info: 'i Note' };
  function characterPane() {
    const ch = asset.character, c = current();
    if (!ch.applies) return el('<div class="s3-pane"><h2>Character Tools</h2><p class="hint">Character preparation is for assets classified as Humanoid; creatures can be inspected. Change the Type on the Geometry tab if this is a character.</p></div>');
    if (!c) return el('<div class="s3-pane"><h2>Character Tools</h2><p class="hint">There is no geometry yet.</p></div>');
    const pane = el(`<div class="s3-pane"><h2>Character Tools</h2><p class="hint">This checks that the character is ready to hand on to landmark mapping. It measures what can be measured and asks you about what only a person can judge. It changes no geometry. Give the body mesh the role <b>Base anatomy</b> on the Components tab first.</p>
      <div class="s3-form"><label class="ag-label">Profile<select data-k="ch-profile" data-ch="profile">${Object.entries(info.character.profiles).map(([k, v]) => `<option value="${k}"${k === ch.profile ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>
        <label class="ag-label">Pose of the file<select data-k="ch-pose" data-ch="pose">${Object.entries(info.character.poses).map(([k, v]) => `<option value="${k}"${k === ch.pose ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>
        <label class="ag-label">Intended height (cm)<input type="number" min="10" max="1000" step="0.1" data-k="ch-stature" data-ch="stature_cm" value="${ch.stature_cm || ''}"></label></div>
      <ul class="s3-issues" aria-label="Preparation checks">${ch.checks.map(k => `<li class="${k.status === 'fail' ? 's3-bad' : ''}"><b>${CHECK[k.status]}</b> ${esc(k.label)}. <span class="hint">${esc(k.detail)}</span>${k.status === 'manual' || ch.confirmed.includes(k.id) ? ` <label class="s3-inline"><input type="checkbox" data-k="ch-ok-${k.id}" data-confirm="${k.id}"${ch.confirmed.includes(k.id) ? ' checked' : ''}> I have checked this</label>` : ''}</li>`).join('')}</ul>
      <div class="rg-fields"><button type="button" class="primary s3-handoff" data-k="handoff"${ch.eligible ? '' : ' disabled'} title="${ch.eligible ? 'Record this exact file as the one handed to landmark mapping' : 'Every Fail and every Needs your check has to be cleared first'}">${ch.handoff ? 'Record the hand-off again' : 'Record hand-off to landmark mapping'}</button>
        <span class="hint">${ch.handoff ? `Recorded: ${esc(ch.handoff.base_name)}, ${esc(info.character.poses[ch.handoff.pose])}, ${ch.handoff.height_cm} cm${ch.handoff.pending ? '. The file is still pending, so this lapses if it expires.' : '.'}` : 'Recording changes nothing in the file and approves nothing.'} Landmark mapping itself is not built.</span></div>
      <div class="rg-blocked"><b>Not available yet:</b> ${info.character.unavailable.map(u => esc(u.label.toLowerCase())).join('; ')}. No tool for these is set up.</div></div>`);
    const send = fields => act(() => call('POST', '/character', { asset: asset.id, artifact: c.id, fields }));
    pane.querySelectorAll('[data-ch]').forEach(i => { i.onchange = () => send({ [i.dataset.ch]: i.type === 'number' ? (i.value ? +i.value : null) : i.value }); });
    pane.querySelectorAll('[data-confirm]').forEach(i => { i.onchange = () => send({ confirmed: [...pane.querySelectorAll('[data-confirm]')].filter(x => x.checked).map(x => x.dataset.confirm) }); });
    pane.querySelector('.s3-handoff').onclick = () => act(() => call('POST', '/character/handoff', { asset: asset.id }), 'Hand-off recorded.');
    return pane;
  }

  function exportPane() {
    const pane = el(`<div class="s3-pane"><h2>Export</h2><p class="hint">An export contains the selected file and what describes it. Nothing is generated, converted or repaired to make it, and exporting does not approve anything.</p>
      <div class="s3-form"><label class="ag-label">What to export<select data-k="x-profile" data-x="profile">${Object.entries(info.export_profiles).map(([k, v]) => `<option value="${k}"${k === exportChoice.profile ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>
        <label class="s3-inline"><input type="checkbox" data-k="x-refs" data-x="references"${exportChoice.references ? ' checked' : ''}${exportChoice.profile === 'standard' ? '' : ' disabled'}> Include attached reference pictures</label></div>
      <div class="s3-plan hint">Working out what would be exported…</div>
      <div class="rg-fields"><button type="button" class="primary s3-export" data-k="export" disabled>Export</button><span class="hint">To bring a SWIFT ZIP back in, use Import at the top. It comes back as a new asset to review; nothing here is overwritten.</span></div></div>`);
    pane.querySelectorAll('[data-x]').forEach(i => { i.onchange = () => { exportChoice[i.dataset.x] = i.type === 'checkbox' ? i.checked : i.value; draw(); }; });
    const button = pane.querySelector('.s3-export'), plan = pane.querySelector('.s3-plan'), id = asset.id;
    call('GET', `/export/plan?asset=${encodeURIComponent(id)}&profile=${exportChoice.profile}${exportChoice.references ? '&references=1' : ''}`).then(p => {
      if (!asset || asset.id !== id) return;
      plan.classList.remove('hint');
      plan.innerHTML = p.blocked ? `<div class="rg-blocked"><b>Cannot export.</b> ${esc(p.blocked)}</div>` : `<b>${esc(p.name)}</b><ul>${p.files.map(f => `<li>${esc(f.path)} <span class="hint">${bytes(f.size)}</span></li>`).join('')}${p.references.map(f => `<li>${esc(f.path)} <span class="hint">reference picture</span></li>`).join('')}${p.profile === 'standard' ? '<li>AssetManifest.json</li><li>Documentation/Compatibility_Report.md</li>' : ''}</ul>
        ${p.pending.length ? `<p><span class="pill rg-pending">Pending</span> ${p.pending.length} item${p.pending.length === 1 ? ' is' : 's are'} not approved. You will be asked to confirm.</p>` : ''}${p.warnings.map(w => `<p class="hint">! ${esc(w)}</p>`).join('')}`;
      button.disabled = !!p.blocked;
    }).catch(e => { plan.textContent = e.message; });
    button.onclick = () => runExport(button);
    return pane;
  }

  function inspector() {
    const c = current();
    if (tab === 'geometry') return geometryPane();
    if (tab === 'components') return componentsPane();
    if (tab === 'character') return characterPane();
    if (tab === 'export') return exportPane();
    if (tab === 'optimization') return unavailable('Optimization', 'geometry.optimize', c ? `The selected file has ${num(c.report.totals.vertices)} control points against a target of ${num(asset.target_vertices)}.` : '');
    if (tab === 'uvs') return unavailable('UVs', 'uv.unwrap', c ? 'UV channels in the file: ' + (c.components.filter(x => x.node === 'mesh').map(x => `${esc(x.name)} ${x.uv_channels}`).join(', ') || 'none') + '.' : '');
    if (tab === 'textures') return unavailable('Textures', 'texture.generate', c ? `The file links to ${num(c.report.rigging.textures)} texture file(s). They are not read or shown.` : '');
    if (tab === 'materials') return unavailable('Materials', null, c ? `The file carries ${num(c.report.rigging.materials)} material(s). They are kept in the file and not edited here. The colours in the 3D view are only for looking.` : '');
    return unavailable('Surface Editing', null, '');
  }

  /* ---------- the asset library: approved assets kept for any project ---------- */
  async function loadLibrary() {
    const q = new URLSearchParams(); if (libFilter.q) q.set('q', libFilter.q); if (libFilter.type) q.set('type', libFilter.type); if (libFilter.favorite) q.set('favorite', '1'); if (libFilter.archived) q.set('archived', '1'); if (libFilter.collection) q.set('collection', libFilter.collection);
    try { lib = await call('GET', '/library?' + q); if (libFilter.collection && !lib.collections.some(c => c.id === libFilter.collection)) { libFilter.collection = ''; return loadLibrary(); } drawLibrary(); } catch (e) { /* the next action reports it */ }
  }
  function drawLibrary() {
    const box = root.querySelector('.s3-library'); if (!box || !lib) return;
    const focus = document.activeElement && box.contains(document.activeElement) ? document.activeElement.dataset.k : null, caret = focus === 'lib-q' ? document.activeElement.selectionStart : null;
    box.innerHTML = '';
    box.append(el(`<div><h2>Asset library</h2><p class="hint">Approved 3D assets kept for reuse in any project. Adding is a separate step from approving. Using an item makes a new asset in this project from the same stored file; nothing is copied on disk and changing that asset never changes the library item. ${lib.total} item${lib.total === 1 ? '' : 's'} in all.</p>
      <div class="rg-fields"><label class="ag-label">Search<input type="search" data-k="lib-q" class="s3-libq" value="${esc(libFilter.q)}" placeholder="Name, tag or type"></label>
        <label class="ag-label">Type<select data-k="lib-type" data-lf="type"><option value="">Any type</option>${info.types.map(t => `<option value="${t.key}"${t.key === libFilter.type ? ' selected' : ''}>${esc(t.label)}</option>`).join('')}</select></label>
        <label class="ag-label">Collection<select data-k="lib-col" data-lf="collection"><option value="">All items</option>${lib.collections.map(c => `<option value="${esc(c.id)}"${c.id === libFilter.collection ? ' selected' : ''}>${esc(c.name)} (${c.count})</option>`).join('')}</select></label>
        <label class="s3-inline"><input type="checkbox" data-k="lib-fav" data-lf="favorite"${libFilter.favorite ? ' checked' : ''}> Favourites only</label>
        <label class="s3-inline"><input type="checkbox" data-k="lib-arch" data-lf="archived"${libFilter.archived ? ' checked' : ''}> Show archived instead</label>
        <span class="ag-grow"></span><button type="button" class="small" data-k="lib-newcol">New collection</button>${libFilter.collection ? '<button type="button" class="small ghost" data-k="lib-delcol">Delete this collection</button>' : ''}</div></div>`));
    let wait = null;
    box.querySelector('.s3-libq').oninput = ev => { libFilter.q = ev.target.value; clearTimeout(wait); wait = setTimeout(loadLibrary, 300); };
    box.querySelectorAll('[data-lf]').forEach(i => { i.onchange = () => { libFilter[i.dataset.lf] = i.type === 'checkbox' ? i.checked : i.value; loadLibrary(); }; });
    box.querySelector('[data-k="lib-newcol"]').onclick = async () => {
      const go = await dialog('New collection', '<p>A collection is a named group of library items. Deleting a collection never deletes the items in it.</p><label class="ag-label">Name<input type="text" maxlength="60" class="s3-colname"></label>', [['Cancel', null], ['Create', () => document.querySelector('.s3-colname').value, true]]);
      const name = (go || '').trim(); if (name) { try { await call('POST', '/library/collection', { name }); loadLibrary(); } catch (e) { host.toast(e.message); } } };
    const del = box.querySelector('[data-k="lib-delcol"]'); if (del) del.onclick = async () => { try { await call('POST', '/library/collection', { id: libFilter.collection, delete: true }); libFilter.collection = ''; loadLibrary(); } catch (e) { host.toast(e.message); } };
    const grid = el('<div class="s3-libgrid"></div>');
    lib.items.forEach(i => {
      const card = el(`<div class="s3-libitem${i.complete ? '' : ' s3-incomplete'}"><div><b>${esc(i.name)}</b>${i.favorite ? ' <span class="pill rg-approved">★ Favourite</span>' : ''}${i.archived ? ' <span class="pill">Archived</span>' : ''}${i.complete ? '' : ' <span class="pill rg-pending">File missing</span>'}
          <div class="hint">${esc(i.parent_label)} / ${esc(i.type_label)}${i.subtype ? ' / ' + esc(i.subtype) : ''} · ${num(i.vertices)} control points${i.size_cm ? ' · ' + i.size_cm.map(n => +n.toFixed(0)).join(' × ') + ' cm' : ''} · ${bytes(i.size)}${i.canonical === false ? ' · axes or units differ from the studio' : ''}</div>
          <div class="hint">${i.tags.length ? 'Tags: ' + i.tags.map(esc).join(', ') : 'No tags'} · used ${i.uses} time${i.uses === 1 ? '' : 's'}</div></div>
        <span class="rg-actions"><button type="button" class="small primary" data-l="use" data-k="lib-use-${esc(i.id)}"${i.complete && !i.archived ? '' : ' disabled'}>Use in this project</button>
          <button type="button" class="small" data-l="fav" data-k="lib-fav-${esc(i.id)}" aria-pressed="${i.favorite}">${i.favorite ? 'Unfavourite' : 'Favourite'}</button>
          <button type="button" class="small" data-l="tags" data-k="lib-tags-${esc(i.id)}">Name and tags</button><button type="button" class="small" data-l="where" data-k="lib-where-${esc(i.id)}">Where used</button>
          ${lib.collections.length ? `<select class="s3-libcol" data-k="lib-put-${esc(i.id)}" aria-label="Collections for ${esc(i.name)}"><option value="">Collections…</option>${lib.collections.map(c => `<option value="${esc(c.id)}">${i.collections.includes(c.id) ? 'Take out of' : 'Put in'} ${esc(c.name)}</option>`).join('')}</select>` : ''}
          <button type="button" class="small ghost" data-l="arch" data-k="lib-arch-${esc(i.id)}">${i.archived ? 'Restore' : 'Archive'}</button><button type="button" class="small ghost" data-l="remove" data-k="lib-rm-${esc(i.id)}">Remove from library</button></span></div>`);
      const put = fields => call('PUT', '/library/item?id=' + encodeURIComponent(i.id), { fields }).then(loadLibrary).catch(e => host.toast(e.message));
      const sel = card.querySelector('.s3-libcol'); if (sel) sel.onchange = () => { if (sel.value) call('POST', '/library/collection', { id: sel.value, item: i.id, on: !i.collections.includes(sel.value) }).then(loadLibrary).catch(e => host.toast(e.message)); };
      card.querySelectorAll('[data-l]').forEach(b => { b.onclick = async () => {
        const what = b.dataset.l;
        if (what === 'fav') put({ favorite: !i.favorite });
        if (what === 'arch') put({ archived: !i.archived });
        if (what === 'use') { try { take(await call('POST', '/library/use', { id: i.id, project: host.pid })); await relist(); draw(); loadLibrary(); host.toast(`“${i.name}” is now an asset in this project, already approved.`); } catch (e) { host.toast(e.message); } }
        if (what === 'tags') { const go = await dialog('Name and tags', `<label class="ag-label">Name<input type="text" maxlength="80" class="s3-libname" value="${esc(i.name)}"></label><label class="ag-label">Tags, separated by commas<input type="text" class="s3-libtags" value="${esc(i.tags.join(', '))}"></label>`, [['Cancel', null], ['Save', () => ({ name: document.querySelector('.s3-libname').value, tags: document.querySelector('.s3-libtags').value.split(',').map(t => t.trim()).filter(Boolean) }), true]]);
          if (go) put(go); }
        if (what === 'where') { try { const u = (await call('GET', '/library/usage?id=' + encodeURIComponent(i.id))).usage;
          await dialog('Where used', u.length ? `<ul class="rg-needs">${u.map(x => `<li><span><b>${esc(x.name)}</b> in ${esc(x.project_name)} <span class="hint">· ${esc(x.relation)}</span></span></li>`).join('')}</ul>` : '<p>No project is using this item, and the asset it came from has been deleted. The library still holds its file.</p>', [['Close', null, true]]); } catch (e) { host.toast(e.message); } }
        if (what === 'remove') { const go = await dialog('Remove from library', `<p><b>${esc(i.name)}</b> will be taken out of the library. ${i.uses ? `The ${i.uses} asset${i.uses === 1 ? '' : 's'} made from it stay${i.uses === 1 ? 's' : ''} as ${i.uses === 1 ? 'it is' : 'they are'} and keep${i.uses === 1 ? 's' : ''} the file.` : 'Its file is deleted too unless another asset still uses it.'} This cannot be undone.</p>`, [['Cancel', null], ['Remove', 'yes', true]]);
          if (go) { try { const out = await call('POST', '/library/remove', { id: i.id }); host.toast(out.freed ? `Removed. ${bytes(out.freed)} freed.` : 'Removed. The file is still in use elsewhere, so no space was freed.'); loadLibrary(); await relist(); } catch (e) { host.toast(e.message); } } }
      }; });
      grid.append(card); });
    if (!lib.items.length) grid.append(el(`<p class="hint">${lib.total ? 'Nothing matches.' : 'The library is empty. Open an asset, approve its file, then choose Add to Library.'}</p>`));
    box.append(grid);
    if (focus) { const again = box.querySelector(`[data-k="${CSS.escape(focus)}"]`); if (again) { again.focus(); if (caret != null) again.setSelectionRange(caret, caret); } }
  }

  function drawJobs() {
    const box = root.querySelector('.s3-jobs'); if (!box) return;
    const recent = jobs.slice().sort((a, b) => b.created - a.created).slice(0, 8);
    box.innerHTML = `<h2>Jobs</h2><p class="hint">One job runs at a time. Imports and exports are quick; nothing here uses the image, video or language models.</p>`;
    if (!recent.length) { box.append(el('<p class="hint">Nothing has run yet.</p>')); return; }
    const ul = el('<ul class="s3-joblist"></ul>');
    recent.forEach(j => { const active = ['waiting', 'running', 'cancelling', 'awaiting force-stop confirmation'].includes(j.state);
      const li = el(`<li><b>${esc(j.label)}</b> <span class="pill ${j.state === 'succeeded' ? 'rg-approved' : j.state === 'failed' || j.state === 'interrupted' ? 'rg-pending' : ''}">${esc(cap(j.state))}${j.position ? ' · place ' + j.position : ''}</span> <span class="hint">${esc(j.provider_name)}${j.stage ? ' · ' + esc(j.stage) : ''}${j.error ? ' · ' + esc(j.error.message) : ''}</span>
        ${j.state === 'waiting' || j.state === 'running' ? `<button type="button" class="small" data-j="cancel">Cancel</button>` : ''}${j.state === 'awaiting force-stop confirmation' ? `<button type="button" class="small" data-j="force">Force stop…</button>` : ''}${j.state === 'failed' && j.operation === 'package.export' || j.state === 'interrupted' && j.operation === 'package.export' ? `<button type="button" class="small" data-j="retry">Try again</button>` : ''}</li>`);
      li.querySelectorAll('[data-j]').forEach(b => { b.onclick = async () => { try {
        if (b.dataset.j === 'force') { const go = await dialog('Force stop', `<p><b>${esc(j.label)}</b> did not stop when asked. Forcing it ends the work at once and discards what it was making. Nothing already saved is touched.</p>`, [['Keep waiting', 'no'], ['Force stop', 'yes', true]]); await call('POST', '/jobs/force', { id: j.id, confirmed: go === 'yes' }); }
        else await call('POST', '/jobs/' + b.dataset.j, { id: j.id });
      } catch (e) { host.toast(e.message); } refreshJobs(); }; });
      void active; ul.append(li); });
    box.append(ul);
  }

  function draw() {
    if (!list || !info) return;
    const focus = document.activeElement && root.contains(document.activeElement) ? document.activeElement.dataset.k : null;
    root.innerHTML = '';
    root.append(head());
    if (!asset) {
      root.append(el(`<section class="panel"><h2>3D Generation</h2><p>Bring in a binary FBX file, a GLB file (converted to FBX by Blender), or a SWIFT ZIP exported from here, to look at it, measure it, check it and package it. Each file is pending until you approve it and is deleted after ${info.retention_days} days if you do not.</p>
        <p class="hint">Making or changing 3D models (generation, optimisation, UVs, textures, pose conversion, landmarks) is not available: no tool for it is set up on this computer yet. ${esc(info.access)}</p></section>`));
      if (viewer) { viewer.clear(); inView = null; }
    } else {
      const tabs = el(`<div class="panel ag-modes s3-tabs" role="tablist" aria-label="3D Generation tools">${TABS.map(([k, label]) => `<button type="button" role="tab" data-k="tab-${k}" data-tab="${k}" aria-selected="${k === tab}" class="${k === tab ? 'on' : ''}">${label}</button>`).join('')}</div>`);
      tabs.querySelectorAll('[data-tab]').forEach(b => { b.onclick = () => { tab = b.dataset.tab; draw(); }; });
      const work = el('<div class="s3-work"></div>'), side = el('<section class="panel s3-inspector"></section>');
      side.append(inspector()); work.append(tree(), viewBox(), side);
      root.append(tabs, work);
    }
    root.append(el('<section class="panel s3-library"></section>'), el('<section class="panel s3-jobs"></section>')); drawLibrary(); drawJobs();
    if (focus) { const again = root.querySelector(`[data-k="${CSS.escape(focus)}"]`); if (again) again.focus(); }
  }

  return {
    panel(h, t) { host = h; tools = t; showing = true; if (loadedFor !== host.pid) { list = null; asset = null; inView = null; tab = 'geometry'; root.innerHTML = '<section class="panel hint">Loading…</section>'; } boot(); return root; },
    hide() { showing = false; clearTimeout(timer); },
    _state: () => ({ asset, list, info, jobs, tab, part, hidden: [...hidden], isolated, look }), _viewer: () => viewer,
  };
})();
