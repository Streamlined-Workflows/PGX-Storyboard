/* Reference Generation: the Asset Generator mode that makes reference sheets and cuts pictures out of them.
 * Design document: docs/Reference_Generation_Design.md. Server side: reference.py and the /api/reference routes.
 *
 * Two workflows, each started by the person and never by the other:
 *   Sheet Generation   Simple mode: a classification, up to four source pictures, a prompt, and 1 to 10 complete sheets.
 *                      Advanced mode: rows (a complete asset, base anatomy, one component...), each with up to six source
 *                      pictures and six view slots that are generated, uploaded, locked or switched off one by one.
 *                      Rows are then assembled into one sheet by reference-assembly.js, with optional specification panels.
 *   Sheet Extraction   choose a sheet, mark regions on it (by hand, or with Detect regions), and cut them out as pictures.
 * Every picture made here is pending until approved or denied, and a pending one is deleted ten days after it was made.
 *
 * The Asset Generator page owns the surrounding page and hands this file what it needs:
 *   ReferenceGeneration.panel(host, tools) -> the element to show; the same element is put back after a redraw
 *     host   { pid, upload(file) -> name, view(name) -> url, toast(text), openViewer(url) }
 *     tools  { library(choose, already), layer() -> the element modals are added to }
 *   ReferenceGeneration.handover(host, tools) -> the element 3D Generation shows: what has been sent to it from here
 *     tools also has go(mode), which switches the Asset Generator to another mode
 *   ReferenceGeneration.hide() stops the checking for finished pictures.
 * Cutting is done here in the browser at the sheet's own pixels, with no resizing, so the server needs no image library.
 */
window.ReferenceGeneration = (function () {
  'use strict';
  let lastLoad = 0, host = null, tools = null, data = null, loadedFor = null, workflow = 'generate', timer = null, saveTimer = null, showing = false, chosen = null;
  const root = document.createElement('div'); root.className = 'rg';
  const side = document.createElement('div'); side.className = 'rg rg-handover';      // shown by 3D Generation
  let preview = null;                      // the assembled sheet last previewed: { pid, canvas, used, stamp }
  const openPanels = new Set();            // which specification panels are open, so a redraw does not close them
  const batch = {};                        // per reference project, while a run is going: how many were asked for and how many sheets there were before
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const el = html => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  async function call(method, path, body) {
    const r = await fetch('/api/reference' + path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
    const out = await r.json().catch(() => ({})); if (!r.ok) throw new Error(out.error || 'The server could not do that.'); return out;
  }
  const S = () => data.state, P = () => S().projects.find(p => p.id === S().open) || null;
  const arts = role => data.artifacts.filter(a => a.project === S().open && a.role === role);
  const busy = id => (data.jobs[id] || []).filter(j => j.status === 'queued' || j.status === 'running').length;
  const anyBusy = () => Object.keys(data.jobs).some(busy);
  const typeOf = key => data.registry.flatMap(g => g.types).find(t => t.key === key);

  /* ---------- talking to the server ---------- */
  async function load() {
    if (!host.pid) { root.innerHTML = '<div class="panel hint">Open a project first.</div>'; return; }
    try { take(await call('GET', '?project=' + encodeURIComponent(host.pid)), loadedFor !== host.pid); loadedFor = host.pid; }
    catch (e) { root.innerHTML = '<div class="panel hint">' + esc(e.message) + '</div>'; }
  }
  /* What the server sends replaces the pictures and jobs shown. What the person has typed and chosen is kept, unless `all`:
   * after an action that changes it on the server (approve, deny, run), the server's copy is taken whole. */
  function take(fresh, all) {
    const before = data ? JSON.stringify([data.artifacts.map(a => [a.id, a.state, a.days_left]), data.jobs]) : '';
    if (data && !all) fresh.state = data.state;
    data = fresh;
    if (fresh.expired) host.toast(`${fresh.expired} unapproved picture${fresh.expired > 1 ? 's' : ''} reached ten days and ${fresh.expired > 1 ? 'were' : 'was'} deleted.`);
    if (all || before !== JSON.stringify([data.artifacts.map(a => [a.id, a.state, a.days_left]), data.jobs]) || !root.firstChild) draw();
    if (side.isConnected) drawSide();
    clearTimeout(timer); if (showing && anyBusy()) timer = setTimeout(load, 2500);
  }
  function keep() { clearTimeout(saveTimer); saveTimer = setTimeout(() => call('POST', '/save', { project: host.pid, state: S() }).catch(e => host.toast(e.message)), 700); }
  const flush = () => { clearTimeout(saveTimer); };

  /* A question in a box over the page. buttons: [[label, value, primary?]]; Escape or a click outside answers null. */
  function dialog(title, html, buttons) {
    return new Promise(done => {
      const box = el(`<div class="ag-modal" role="alertdialog" aria-modal="true" aria-label="${esc(title)}"><div class="ag-modalbox ag-ask rg-dialog"><h2>${esc(title)}</h2><div class="rg-dialogbody">${html}</div>
        <div class="ag-askbtns"><span class="ag-grow"></span>${buttons.map(([label, , primary], i) => `<button type="button" data-i="${i}" class="${primary ? 'primary' : ''}">${esc(label)}</button>`).join('')}</div></div></div>`);
      const end = v => { document.removeEventListener('keydown', key); box.remove(); done(v); };
      const key = ev => { if (ev.key === 'Escape') end(null); };
      box.querySelectorAll('[data-i]').forEach(b => { b.onclick = () => end(buttons[+b.dataset.i][1]); });
      box.onpointerdown = ev => { if (ev.target === box) end(null); };
      document.addEventListener('keydown', key); tools.layer().append(box); box.querySelector('[data-i]').focus();
    });
  }
  const left = a => a.state === 'approved' ? 'Approved' : a.hours_left >= 24 ? `Pending · deleted in ${a.days_left} day${a.days_left > 1 ? 's' : ''}` : `Pending · deleted in ${Math.max(1, a.hours_left)} hour${a.hours_left > 1 ? 's' : ''}`;
  const pill = a => `<span class="pill rg-state rg-${a.state}" title="${a.state === 'approved' ? 'Kept until you delete it.' : `Not approved yet. Unapproved pictures are deleted ${data.limits.retention_days} days after they are made.`}">${left(a)}</span>`;

  /* ---------- approve, deny, download ---------- */
  async function decide(ids, action, confirmed) {
    try {
      const out = await call('POST', '/decide', { project: host.pid, ids, action, confirmed: !!confirmed });
      if (out.needs) {                                                   // design 2.14: other pending pictures this one cannot do without
        const rows = out.needs.map(n => `<li><img alt="" src="${esc(host.view(n.image))}"><span>${esc(n.reason || 'Needed by the picture you are approving.')}</span></li>`).join('');
        const go = await dialog('Approve Required Dependencies', `<p>The picture you are approving depends on other pictures that have not been approved for permanent storage. They are needed to keep it complete. If they are not kept, it may become incomplete when they expire. Approve this picture and everything it needs?</p><ul class="rg-needs">${rows}</ul>`, [['Cancel', null], ['Approve All', 'yes', true]]);
        if (go) return decide(ids, action, true);
        return;
      }
      take(out, true);
      if (out.denied != null) host.toast(out.held && out.held.length ? 'An approved picture still needs that one, so it was kept.' : `Denied and deleted${out.files_deleted ? '' : data.files_deletable ? '' : ' from SWIFT Director (the image file itself stays in ComfyUI’s folder)'}.`);
    } catch (e) { host.toast(e.message); }
  }
  async function deny(a) {
    if (!await dialog(a.state === 'approved' ? 'Delete this approved picture?' : 'Deny this picture?', `<p>It is deleted along with its prompt and settings, and it leaves the Library. This cannot be undone.</p>`, [['Cancel', null], [a.state === 'approved' ? 'Delete' : 'Deny and delete', 'yes', true]])) return;
    decide([a.id], 'deny');
  }
  async function download(a, name) {
    if (a.state !== 'approved') {                                        // design 11 and 2.13: say so before a pending picture leaves
      const go = await dialog('Export Unapproved Asset', `<p>This picture has not been approved for permanent storage. It will be deleted from SWIFT Director when its time runs out (${esc(left(a).replace('Pending · ', ''))}) unless you approve it first. Downloading does not approve it or give it more time. Your downloaded copy is not affected when the local one is deleted. Continue?</p>`, [['Cancel', null], ['Continue Export', 'yes', true]]);
      if (!go) return;
    }
    const link = document.createElement('a'); link.href = host.view(a.image); link.download = name; document.body.append(link); link.click(); link.remove();
  }
  const stem = () => (P().name.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'reference');
  function actions(a, name, held) {                                        // held: the picture is in a locked view, so it cannot be denied
    const bar = el(`<span class="rg-actions">${a.state === 'approved' ? '' : '<button class="small rg-approve" type="button" title="Keep this picture permanently">Approve</button>'}
      <button class="small rg-deny" type="button"${held ? ' disabled' : ''} title="${held ? 'This view is locked. Unlock it to ' + (a.state === 'approved' ? 'delete' : 'deny') + ' its picture.' : a.state === 'approved' ? 'Delete this picture' : 'Reject this picture and delete it now'}">${a.state === 'approved' ? 'Delete' : 'Deny'}</button>
      <button class="small rg-download" type="button">Download</button></span>`);
    const ok = bar.querySelector('.rg-approve'); if (ok) ok.onclick = () => decide([a.id], 'approve');
    bar.querySelector('.rg-deny').onclick = () => deny(a); bar.querySelector('.rg-download').onclick = () => download(a, name);
    return bar;
  }

  /* ---------- drawing ---------- */
  function draw() {
    const focus = document.activeElement && root.contains(document.activeElement) ? document.activeElement.dataset.k : null;
    root.innerHTML = '';
    if (!data) { root.append(el('<div class="panel hint">Loading…</div>')); return; }
    root.append(head());
    if (P()) root.append(workflow === 'generate' ? generation() : extraction());
    if (P() && workflow === 'generate') root.append(exportBox());
    if (focus) { const again = root.querySelector(`[data-k="${focus}"]`); if (again) again.focus(); }
  }
  const fit = area => { if (area.offsetParent) { area.style.height = 'auto'; area.style.height = (area.scrollHeight + 2) + 'px'; } };

  /* The top box: which workflow, which reference project, and its classification. */
  function head() {
    const p = P(), t = p && typeOf(p.type), group = p && data.registry.find(g => g.key === p.parent);
    const box = el(`<section class="panel rg-head">
      <div class="rg-flows" role="tablist" aria-label="Reference Generation workflow"><button data-w="generate" role="tab">Sheet Generation</button><button data-w="extract" role="tab">Sheet Extraction</button>
        <span class="hint">Two separate workflows. Generating a sheet never starts an extraction.</span></div>
      <div class="rg-fields"><label class="ag-label">Reference project<select data-k="rg-open" class="rg-open">${S().projects.map(x => `<option value="${esc(x.id)}"${p && x.id === p.id ? ' selected' : ''}>${esc(x.name)}</option>`).join('') || '<option value="">None yet</option>'}</select></label>
        <button class="small rg-new" type="button">New reference project</button>${p ? '<button class="small ghost rg-del" type="button">Delete</button>' : ''}</div>
      ${p ? `<div class="rg-fields"><label class="ag-label">Name<input data-k="rg-name" class="rg-name" type="text" maxlength="80" value="${esc(p.name)}"></label>
        <label class="ag-label">Parent classification<select data-k="rg-parent" class="rg-parent">${data.registry.map(g => `<option value="${g.key}"${g.key === p.parent ? ' selected' : ''}>${esc(g.label)}</option>`).join('')}</select></label>
        <label class="ag-label">Asset type<select data-k="rg-type" class="rg-type">${group.types.map(x => `<option value="${x.key}"${x.key === p.type ? ' selected' : ''}>${esc(x.label)}</option>`).join('')}</select></label>
        <label class="ag-label">Subtype (optional)<select data-k="rg-sub" class="rg-sub"><option value="">None</option>${t.subtypes.map(x => `<option${x === p.subtype ? ' selected' : ''}>${esc(x)}</option>`).join('')}</select></label>
        ${p.subtype === 'Custom' ? `<label class="ag-label">Custom subtype<input data-k="rg-custom" class="rg-custom" type="text" maxlength="60" value="${esc(p.custom_subtype)}"></label>` : ''}</div>`
      : '<p class="hint">A reference project holds the sheets and cut-out views for one asset. Make one to begin.</p>'}</section>`);
    box.querySelectorAll('[data-w]').forEach(b => { b.classList.toggle('on', b.dataset.w === workflow); b.setAttribute('aria-selected', b.dataset.w === workflow); b.onclick = () => { workflow = b.dataset.w; draw(); }; });
    box.querySelector('.rg-open').onchange = ev => { S().open = ev.target.value; chosen = null; keep(); draw(); };
    box.querySelector('.rg-new').onclick = () => {
      const id = 'rp' + Math.random().toString(16).slice(2, 12).padEnd(10, '0');
      S().projects.push({ id, name: 'New reference', type: 'humanoid', rows: [] }); S().open = id; flush();
      call('POST', '/save', { project: host.pid, state: S() }).then(out => take(out, true)).catch(e => host.toast(e.message));
    };
    if (!p) return box;
    box.querySelector('.rg-del').onclick = async () => {
      const mine = data.artifacts.filter(a => a.project === p.id).length;
      if (!await dialog('Delete this reference project?', `<p><b>${esc(p.name)}</b> and its settings are deleted${mine ? `, together with its ${mine} picture${mine > 1 ? 's' : ''}, approved ones included` : ''}. This cannot be undone.</p>`, [['Cancel', null], ['Delete', 'yes', true]])) return;
      try { flush(); if (mine) await call('POST', '/decide', { project: host.pid, ids: data.artifacts.filter(a => a.project === p.id).map(a => a.id), action: 'deny', force: true });
        S().projects = S().projects.filter(x => x.id !== p.id); S().open = (S().projects[0] || {}).id || null; take(await call('POST', '/save', { project: host.pid, state: S() }), true); }
      catch (e) { host.toast(e.message); }
    };
    /* A change of name or classification rewrites the recommended prompt on the server, unless the person has written their own. */
    const resave = () => { flush(); call('POST', '/save', { project: host.pid, state: S() }).then(out => take(out, true)).catch(e => host.toast(e.message)); };
    const name = box.querySelector('.rg-name'); name.oninput = () => { p.name = name.value; keep(); }; name.onchange = resave;
    box.querySelector('.rg-parent').onchange = ev => { p.parent = ev.target.value; p.type = data.registry.find(g => g.key === p.parent).types[0].key; p.subtype = ''; resave(); };
    box.querySelector('.rg-type').onchange = ev => { p.type = ev.target.value; p.subtype = ''; resave(); };
    box.querySelector('.rg-sub').onchange = ev => { p.subtype = ev.target.value; resave(); };
    const custom = box.querySelector('.rg-custom'); if (custom) { custom.oninput = () => { p.custom_subtype = custom.value; keep(); }; custom.onchange = resave; }
    return box;
  }

  /* Pick a picture: Upload or Apply from Library, the same two choices as every other reference in the Asset Generator. */
  function source(label, choose, already) {
    const add = el(`<span class="rg-add"><button class="small rg-addbtn" type="button" aria-haspopup="true" aria-expanded="false">${esc(label)}</button><input type="file" accept="image/png,image/jpeg,image/webp" hidden>
      <span class="ag-source" hidden><button class="small ag-up" type="button">Upload</button><button class="small ag-lib" type="button">Apply from Library</button></span></span>`);
    const pick = add.querySelector('input'), menu = add.querySelector('.ag-source'), open = add.querySelector('.rg-addbtn');
    open.onclick = () => { menu.hidden = !menu.hidden; open.setAttribute('aria-expanded', !menu.hidden); };
    add.querySelector('.ag-up').onclick = () => pick.click();
    add.querySelector('.ag-lib').onclick = () => tools.library(choose, already || []);
    pick.onchange = async () => { if (!pick.files[0]) return; open.disabled = true; open.textContent = 'Uploading…'; try { choose(await host.upload(pick.files[0])); } catch (e) { host.toast(e.message); draw(); } };
    return add;
  }

  /* ---------- Sheet Generation ---------- */
  const newId = lead => lead + Math.random().toString(16).slice(2, 12).padEnd(10, '0');
  const saveNow = () => { flush(); return call('POST', '/save', { project: host.pid, state: S() }).then(out => take(out, true)).catch(e => host.toast(e.message)); };
  /* Simple or Advanced. Both keep what they hold, so switching back and forth loses nothing. The first switch to Advanced is the
   * conversion: a first row is made from what Simple mode has (its sources and its selected sheet), and nothing is extracted. */
  function modeBar() {
    const p = P(), bar = el(`<div class="rg-modes"><span class="ag-label">Mode</span><button class="small" data-mode="simple" type="button">Simple</button><button class="small" data-mode="advanced" type="button">Advanced</button>
      <span class="hint">${p.mode === 'advanced' ? 'Advanced builds the reference one row and one view at a time.' : `Simple makes a complete sheet in one go from up to ${data.limits.sources} source pictures.`}</span></div>`);
    bar.querySelectorAll('[data-mode]').forEach(b => { b.classList.toggle('on', b.dataset.mode === p.mode); b.setAttribute('aria-pressed', b.dataset.mode === p.mode);
      b.onclick = () => {
        if (p.mode === b.dataset.mode) return; p.mode = b.dataset.mode;
        if (p.mode === 'advanced' && !p.rows.length) { const sheet = data.artifacts.find(a => a.id === p.selected);
          p.rows.push({ id: newId('rw'), section: 'base', label: 'Complete ' + (typeOf(p.type).label.toLowerCase()), role: 'Complete asset', sources: [...p.sources, ...(sheet ? [sheet.image] : [])].slice(0, data.limits.row_sources).map(image => ({ image })) }); }
        saveNow();
      }; });
    return bar;
  }
  const generation = () => P().mode === 'advanced' ? advanced() : simple();

  /* ----- Advanced mode: rows and views ----- */
  const cands = (row, d) => data.artifacts.filter(a => a.row === row.id && a.role === (d ? 'view' : 'row') && (!d || a.direction === d));
  const chosenOf = (row, d) => { const made = cands(row, d), want = d ? row.slots[d].selected : row.selected; return made.find(a => a.id === want) || made[0] || null; };
  const slotBusy = (row, d) => (data.jobs[P().id] || []).filter(j => j.row === row.id && (!d || j.direction === d) && (j.status === 'queued' || j.status === 'running')).length;
  const listed = a => a.length > 1 ? a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1] : a[0] || '';
  /* Ask the server what a request would do, show it, and queue it only on yes (design 5.3: say which views are targeted first). */
  async function runViews(row, what, button) {
    const p = P(); if (button) button.disabled = true; flush();
    try {
      const pre = await call('POST', '/views', { project: host.pid, reference: p.id, row: row.id, what, state: S(), preview: true });
      const plan = pre.plan, sk = pre.skipped, total = plan.reduce((n, v) => n + v.count, 0), unused = plan.some(v => v.unused.length || v.unavailable.length);
      if (what === 'row' || what === 'missing' || unused) {
        const sent = v => v.used.length ? 'sent ' + listed(v.used.map(x => x.what)) : 'no reference pictures sent';
        const same = plan.every(v => JSON.stringify([v.used, v.unused, v.unavailable]) === JSON.stringify([plan[0].used, plan[0].unused, plan[0].unavailable]));
        const refs = (same ? [plan[0]] : plan).map(v => `<li>${same ? '' : '<b>' + cap(v.direction) + ':</b> '}${esc(cap(sent(v)))}.${v.unused.length ? ` <span class="rg-warn">Not sent, because the image model takes ${data.provider.inputs} pictures: ${esc(listed(v.unused.map(x => x.what)))}.</span>` : ''}${v.unavailable.length ? ` <span class="rg-warn">Not available: ${esc(listed(v.unavailable))}.</span>` : ''}</li>`).join('');
        const go = await dialog(what === 'missing' ? 'Generate Missing Views' : what === 'row' ? 'Generate Row' : 'Generate ' + cap(what) + ' View',
          `<p>This makes <b>${plan[0].count}</b> candidate${plan[0].count > 1 ? 's' : ''} for ${plan.length > 1 ? 'each of ' : ''}<b>${esc(listed(plan.map(v => cap(v.direction))))}</b>: ${total} picture${total > 1 ? 's' : ''} at ${plan[0].width} × ${plan[0].height}. Pictures already there are kept, and the ones in use stay in use.</p>
           ${sk.locked.length || sk.disabled.length ? `<p class="hint">Left alone: ${[sk.locked.length ? esc(listed(sk.locked.map(cap))) + ' (locked)' : '', sk.disabled.length ? esc(listed(sk.disabled.map(cap))) + ' (switched off)' : ''].filter(Boolean).join('; ')}.</p>` : ''}<ul class="rg-plan">${refs}</ul>`,
          [['Cancel', null], ['Generate', 'yes', true]]);
        if (!go) { take(pre, true); return; }
      }
      plan.forEach(v => { batch[row.id + v.direction] = { asked: v.count, had: cands(row, v.direction).length }; });
      take(await call('POST', '/views', { project: host.pid, reference: p.id, row: row.id, what }), true);
    } catch (e) { host.toast(e.message); draw(); }
  }
  async function placeIn(row, d, image) {
    try { flush(); take(await call('POST', '/place', { project: host.pid, reference: P().id, row: row.id, direction: d, image, state: S() }), true); } catch (e) { host.toast(e.message); draw(); }
  }
  function slotCard(row, d) {
    const sl = row.slots[d], list = cands(row, d), use = chosenOf(row, d), shown = list.find(a => a.id === sl.at) || use, n = shown ? list.indexOf(shown) : -1;
    const locked = row.locked || (sl.locked && !!use), working = slotBusy(row, d), b = batch[row.id + d], done = b ? Math.min(b.asked, list.length - b.had) : 0;
    if (!working) delete batch[row.id + d];
    const failed = (data.jobs[P().id] || []).find(j => j.row === row.id && j.direction === d && j.status === 'error');
    const card = el(`<div class="rg-slot${sl.enabled ? '' : ' rg-off'}${locked ? ' rg-locked' : ''}" data-dir="${d}">
      <div class="rg-slothead"><b>${cap(d)}</b><label title="Switched-off views are left out of generation and assembly"><input type="checkbox" data-k="en-${row.id}-${d}" class="rg-enable"${sl.enabled ? ' checked' : ''}${row.locked ? ' disabled' : ''}> Use</label>
        <span class="ag-grow"></span><button class="small rg-lock${sl.locked && use ? ' on' : ''}" type="button" aria-pressed="${!!(sl.locked && use)}"${use && !row.locked ? '' : ' disabled'} title="${use ? 'A locked view keeps its picture: generating and uploading leave it alone.' : 'Only a view with a picture can be locked.'}">${sl.locked && use ? 'Locked' : 'Lock'}</button></div>
      <div class="rg-slotpic">${shown ? `<img alt="${cap(d)} view" loading="lazy" src="${esc(host.view(shown.image))}">` : `<span class="hint">${working ? (b ? `Generating ${done}/${b.asked}` : 'Generating…') : sl.enabled ? 'Empty' : 'Switched off'}</span>`}</div>
      ${shown ? `<div class="rg-slotnav"><button class="small rg-sprev" type="button" aria-label="Previous candidate"${n > 0 ? '' : ' disabled'}>‹</button><span class="hint">${n + 1} of ${list.length}</span><button class="small rg-snext" type="button" aria-label="Next candidate"${n < list.length - 1 ? '' : ' disabled'}>›</button>
        ${shown === use ? '<span class="pill rg-selected">In use</span>' : `<button class="small rg-use" type="button"${locked ? ' disabled title="Unlock the view to change its picture"' : ''}>Use this one</button>`}</div><div>${pill(shown)}</div>` : ''}
      ${working && shown ? `<div class="hint">${b ? `Generating an additional ${b.asked - done}` : 'Generating…'}</div>` : ''}${failed ? `<div class="rg-warn">${esc(failed.error || 'A picture failed.')}</div>` : ''}
      <div class="rg-slotbtns"></div></div>`);
    card.querySelector('.rg-enable').onchange = ev => { sl.enabled = ev.target.checked; keep(); draw(); };
    card.querySelector('.rg-lock').onclick = () => { sl.locked = !(sl.locked && use); if (sl.locked) sl.selected = use.id; keep(); draw(); };
    const btns = card.querySelector('.rg-slotbtns');
    if (shown) {
      card.querySelector('img').onclick = () => host.openViewer(host.view(shown.image));
      card.querySelector('.rg-sprev').onclick = () => { sl.at = list[n - 1].id; keep(); draw(); }; card.querySelector('.rg-snext').onclick = () => { sl.at = list[n + 1].id; keep(); draw(); };
      const pick = card.querySelector('.rg-use'); if (pick) pick.onclick = () => { sl.selected = shown.id; keep(); draw(); };
    }
    if (sl.enabled && !locked) {
      const gen = el(`<button class="small rg-genview" type="button">${use ? 'Regenerate' : 'Generate'}</button>`); gen.onclick = () => runViews(row, d, gen);
      btns.append(gen, source('Upload', image => placeIn(row, d, image), []));
    }
    if (shown) btns.append(actions(shown, `${stem()}-${(row.label || row.role || 'row').toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${d}-${n + 1}.png`, locked && shown === use));
    return card;
  }
  function rowCard(row, index) {
    const p = P(), real = row.type || p.type, dims = data.profiles.find(x => x.profile === row.profile).sizes[row.aspect], whole = cands(row, null), wholeUse = chosenOf(row, null);
    const any = data.directions.some(d => chosenOf(row, d)), working = slotBusy(row, null);
    const reaches = (from, to, seen = []) => { const r = p.rows.find(x => x.id === from); return !!r && r.sources.some(s => s.row === to || (s.row && !seen.includes(s.row) && reaches(s.row, to, [...seen, from]))); };
    const others = p.rows.filter(o => o.id !== row.id && !reaches(o.id, row.id)).flatMap(o => data.directions.filter(d => chosenOf(o, d)).map(d => ({ row: o.id, direction: d, text: `${o.label || o.role || 'Row'} · ${cap(d)}` })));
    const card = el(`<section class="rg-rowcard${row.locked ? ' rg-rowlocked' : ''}" data-row="${row.id}">
      <div class="rg-fields rg-rowhead"><span class="rg-move"><button class="small ghost rg-up" type="button" aria-label="Move the row up"${index ? '' : ' disabled'}>▲</button><button class="small ghost rg-down" type="button" aria-label="Move the row down"${index < p.rows.length - 1 ? '' : ' disabled'}>▼</button></span>
        <label class="ag-label">Section<select data-k="rs-${row.id}" class="rg-rsection">${data.sections.map(x => `<option value="${x}"${x === row.section ? ' selected' : ''}>${cap(x)}</option>`).join('')}</select></label>
        <label class="ag-label">Row name<input data-k="rl-${row.id}" class="rg-rlabel" type="text" maxlength="60" value="${esc(row.label)}" placeholder="for example: Pirate hat"></label>
        <label class="ag-label">Component role<input data-k="rr-${row.id}" class="rg-rrole" type="text" maxlength="40" list="rg-roles" value="${esc(row.role)}" placeholder="for example: Headwear"></label>
        <label class="ag-label">Classification<select data-k="rt-${row.id}" class="rg-rtype"><option value="">Same as the project (${esc(typeOf(p.type).label)})</option>${data.registry.flatMap(g => g.types).map(t => `<option value="${t.key}"${t.key === row.type ? ' selected' : ''}>${esc(t.label)}</option>`).join('')}</select></label>
        ${row.type ? `<label class="ag-label">Subtype<select data-k="rb-${row.id}" class="rg-rsub"><option value="">None</option>${typeOf(row.type).subtypes.filter(x => x !== 'Custom').map(x => `<option${x === row.subtype ? ' selected' : ''}>${esc(x)}</option>`).join('')}</select></label>` : ''}
        <span class="ag-grow"></span><button class="small rg-rowlock${row.locked ? ' on' : ''}" type="button" aria-pressed="${row.locked}" title="A locked row and all its views are left alone by generation and uploads.">${row.locked ? 'Row locked' : 'Lock row'}</button><button class="small ghost rg-rowdel" type="button">Remove row</button></div>
      <div class="ag-label">Source pictures (up to ${data.limits.row_sources}) <span class="hint">The image model takes ${data.provider.inputs} pictures at a time; before each run you are told which are sent.</span></div><div class="rg-sources"></div>
      <label class="ag-label">Row prompt<span class="ag-promptwrap"><textarea data-k="rp-${row.id}" class="rg-prompt rg-rprompt" rows="3"${row.locked ? ' readonly' : ''}>${esc(row.prompt)}</textarea><span class="ag-chars"></span></span></label>
      <div class="hint">${row.prompt_edited ? 'This is your own prompt. <button class="small ghost rg-recommend" type="button">Use the recommended prompt</button>' : `Recommended for this ${esc(typeOf(real).label.toLowerCase())} row.`} Each view adds its own sentence, for example “${esc(data.direction_words.left)}”</div>
      <div class="ag-run"><label>Resolution<select data-k="rf-${row.id}" class="rg-rprofile">${data.profiles.map(x => `<option value="${x.profile}"${x.profile === row.profile ? ' selected' : ''}>${x.profile}</option>`).join('')}</select></label>
        <label>Shape<select data-k="ra-${row.id}" class="rg-raspect">${data.aspects.map(a => `<option${a === row.aspect ? ' selected' : ''}>${a}</option>`).join('')}</select></label>
        <label>Candidates<input data-k="rc-${row.id}" class="ag-n rg-rcount" type="number" min="1" max="${data.limits.count}" step="1" value="${row.count}"></label>
        <button class="primary rg-genrow" type="button"${dims.blocked || row.locked ? ' disabled' : ''}>${any ? 'Regenerate Row' : 'Generate Row'}</button>
        <button class="rg-genmissing" type="button"${dims.blocked || row.locked ? ' disabled' : ''}>Generate Missing Views</button><span class="rg-wholeadd"></span>
        <span class="hint">Each view is ${dims.size[0]} × ${dims.size[1]} pixels.${working ? ` ${working} picture${working > 1 ? 's' : ''} in progress.` : ''}</span></div>
      <div class="ag-run rg-rowlayout"><label>Width on the sheet<select data-k="rw-${row.id}" class="rg-rwidth"><option value="full"${row.width === 'full' ? ' selected' : ''}>Full</option><option value="half"${row.width === 'half' ? ' selected' : ''}>Half</option><option value="custom"${row.width === 'custom' ? ' selected' : ''}>Custom</option></select></label>
        ${row.width === 'custom' ? `<label>Percent<input data-k="rx-${row.id}" class="ag-n rg-rpct" type="number" min="20" max="100" step="5" value="${row.width_pct}"></label>` : ''}
        ${whole.length ? `<label>On the sheet show<select data-k="rm-${row.id}" class="rg-rassemble"><option value="views"${row.assemble === 'views' ? ' selected' : ''}>The views</option><option value="whole"${row.assemble === 'whole' ? ' selected' : ''}>The complete row picture</option></select></label>` : ''}
        <span class="hint">Rows narrower than full sit side by side when they fit.</span></div>
      ${row.section === 'detail' ? '<div class="cc rg-rowpanel"></div>' : ''}
      ${dims.blocked ? `<div class="rg-blocked">${esc(dims.blocked)}</div>` : ''}
      <div class="rg-slots"></div>
      <div class="rg-checks"></div>
      ${whole.length ? `<div class="ag-label">Complete row picture <span class="hint">Kept whole for assembly. It is not split into views; use Sheet Extraction for that.</span></div><div class="rg-wholes"></div>` : ''}</section>`);
    const set = (sel, key, after) => { const f = card.querySelector(sel); if (!f) return; f[f.tagName === 'SELECT' ? 'onchange' : 'oninput'] = () => { row[key] = f.type === 'number' ? +f.value : f.value; keep(); if (f.tagName === 'SELECT') (after || draw)(); }; if (f.tagName !== 'SELECT') f.onchange = after || draw; };
    set('.rg-rsection', 'section', saveNow); set('.rg-rlabel', 'label', saveNow); set('.rg-rrole', 'role', saveNow); set('.rg-rsub', 'subtype');
    card.querySelector('.rg-rtype').onchange = ev => { row.type = ev.target.value; row.subtype = ''; saveNow(); };
    card.querySelector('.rg-rprofile').onchange = ev => { row.profile = +ev.target.value; keep(); draw(); }; card.querySelector('.rg-raspect').onchange = ev => { row.aspect = ev.target.value; keep(); draw(); };
    card.querySelector('.rg-rcount').onchange = ev => { row.count = Math.max(1, Math.min(data.limits.count, Math.round(+ev.target.value) || 1)); keep(); draw(); };
    card.querySelector('.rg-up').onclick = () => { p.rows.splice(index - 1, 0, p.rows.splice(index, 1)[0]); keep(); draw(); };
    card.querySelector('.rg-down').onclick = () => { p.rows.splice(index + 1, 0, p.rows.splice(index, 1)[0]); keep(); draw(); };
    card.querySelector('.rg-rowlock').onclick = () => { row.locked = !row.locked; if (row.locked) data.directions.forEach(d => { const a = chosenOf(row, d); if (a) row.slots[d].selected = a.id; }); keep(); draw(); };
    card.querySelector('.rg-rowdel').onclick = async () => {
      const mine = data.artifacts.filter(a => a.row === row.id);
      if (!await dialog('Remove this row?', `<p><b>${esc(row.label || row.role || 'This row')}</b> is removed${mine.length ? `, together with its ${mine.length} picture${mine.length > 1 ? 's' : ''}, approved ones included` : ''}. Other rows are not touched. This cannot be undone.</p>`, [['Cancel', null], ['Remove', 'yes', true]])) return;
      try { flush(); if (mine.length) await call('POST', '/decide', { project: host.pid, ids: mine.map(a => a.id), action: 'deny', force: true }); p.rows = p.rows.filter(x => x.id !== row.id); await saveNow(); } catch (e) { host.toast(e.message); }
    };
    const src = card.querySelector('.rg-sources');
    row.sources.forEach((s0, k) => {
      const other = s0.row && p.rows.find(x => x.id === s0.row), got = s0.image ? { image: s0.image } : other && chosenOf(other, s0.direction);
      const c = el(`<div class="ag-ref${got ? '' : ' rg-missing'}" title="${s0.row ? esc(`The ${s0.direction} view in use in “${other ? other.label || other.role || 'another row' : 'a removed row'}”. It follows that row: nothing is copied.`) : ''}">${got ? `<img alt="Source ${k + 1}" src="${esc(host.view(got.image))}">` : '<span class="hint">Not available</span>'}${row.locked ? '' : `<button class="ag-x" type="button" aria-label="Remove source ${k + 1}">×</button>`}<span class="ag-num">${k + 1}${s0.row ? ' ↗' : ''}</span></div>`);
      if (got) c.querySelector('img').onclick = () => host.openViewer(host.view(got.image));
      const x = c.querySelector('.ag-x'); if (x) x.onclick = () => { row.sources.splice(k, 1); keep(); draw(); }; src.append(c);
    });
    if (row.sources.length < data.limits.row_sources && !row.locked) {
      src.append(source('+ Add a source picture', image => { if (!row.sources.some(x => x.image === image)) row.sources.push({ image }); keep(); draw(); }, row.sources.map(x => x.image).filter(Boolean)));
      if (others.length) { const from = el(`<select class="rg-inherit" aria-label="Use a view from another row"><option value="">From another row…</option>${others.map((o, k) => `<option value="${k}">${esc(o.text)}</option>`).join('')}</select>`);
        from.onchange = () => { const o = others[+from.value]; if (o && !row.sources.some(x => x.row === o.row && x.direction === o.direction)) row.sources.push({ row: o.row, direction: o.direction }); keep(); draw(); }; src.append(from); }
    }
    const area = card.querySelector('.rg-rprompt'), count = card.querySelector('.ag-chars');
    const show = () => { const len = area.value.length, lim = data.prompt_limit.characters; count.textContent = len.toLocaleString() + ' / ' + lim.toLocaleString(); count.className = 'ag-chars' + (len > lim ? ' ag-over' : len > lim * 0.9 ? ' ag-near' : ''); fit(area); };
    area.oninput = () => { row.prompt = area.value; row.prompt_edited = true; keep(); show(); }; area.onchange = () => draw(); show(); requestAnimationFrame(show);
    const rec = card.querySelector('.rg-recommend'); if (rec) rec.onclick = () => { row.prompt_edited = false; saveNow(); };
    card.querySelector('.rg-genrow').onclick = ev => runViews(row, 'row', ev.target); card.querySelector('.rg-genmissing').onclick = ev => runViews(row, 'missing', ev.target);
    if (!row.locked) card.querySelector('.rg-wholeadd').append(source('Upload complete row', image => placeIn(row, '', image), []));
    card.querySelector('.rg-rwidth').onchange = ev => { row.width = ev.target.value; keep(); draw(); };
    const pct = card.querySelector('.rg-rpct'); if (pct) pct.onchange = () => { row.width_pct = Math.max(20, Math.min(100, Math.round(+pct.value) || 50)); keep(); draw(); };
    const asm = card.querySelector('.rg-rassemble'); if (asm) asm.onchange = () => { row.assemble = asm.value; keep(); draw(); };
    const rp = card.querySelector('.rg-rowpanel'); if (rp) rp.append(panelEditor(row.panel, row.id, 'Specification panel for this row', 'Drawn beside this row.', [row.label, row.role]));
    const slots = card.querySelector('.rg-slots'); data.directions.forEach(d => slots.append(slotCard(row, d)));
    /* Consistency: plain facts worked out by the application, and what the language model found when asked to compare the views. Advice only. */
    const val = row.validation, inUse = data.directions.filter(d => row.slots[d].enabled && chosenOf(row, d)).length, checks = card.querySelector('.rg-checks');
    checks.innerHTML = `<div class="rg-fields"><button class="small rg-check" type="button"${inUse >= 2 ? '' : ' disabled'} title="The language model compares this row's views in use and lists where they disagree. It does not change or block anything.">${val ? 'Check consistency again' : 'Check consistency'}</button>
        <span class="hint">${inUse < 2 ? 'Needs at least two views with pictures.' : val ? `Checked by ${esc(val.model)}. ${val.findings.length ? '' : 'No disagreements were found. '}${val.stale ? 'The pictures in use have changed since, so this may no longer apply.' : ''}` : 'Not checked yet.'} Findings are advice: they never stop a generation.</span></div>
      ${(row.notes || []).length || (val && val.findings.length) ? `<ul class="rg-findings">${(row.notes || []).map(n => `<li><b>${esc(cap(n.aspect))}</b> ${esc(n.description)}</li>`).join('')}${val ? val.findings.map(f => `<li class="${val.stale ? 'rg-old' : ''}"><b>${esc(cap(f.aspect))}${f.views.length ? ' · ' + esc(f.views.map(cap).join(', ')) : ''}</b> ${esc(f.description)}${f.certain ? '' : ' <i>(not certain)</i>'}</li>`).join('') : ''}</ul>` : ''}`;
    checks.querySelector('.rg-check').onclick = async ev => { ev.target.disabled = true; ev.target.textContent = 'Comparing the views…'; flush();
      try { await call('POST', '/save', { project: host.pid, state: S() }); take(await call('POST', '/check', { project: host.pid, reference: p.id, row: row.id }), true); } catch (e) { host.toast(e.message); draw(); } };
    const wholes = card.querySelector('.rg-wholes');
    if (wholes) whole.forEach((a, k) => { const c = el(`<div class="rg-view"><img alt="Complete row picture ${k + 1}" loading="lazy" src="${esc(host.view(a.image))}">${pill(a)}${a === wholeUse ? '<span class="pill rg-selected">In use</span>' : '<button class="small rg-usewhole" type="button">Use this one</button>'}</div>`);
      c.querySelector('img').onclick = () => host.openViewer(host.view(a.image)); const u = c.querySelector('.rg-usewhole'); if (u) u.onclick = () => { row.selected = a.id; keep(); draw(); };
      c.append(actions(a, `${stem()}-row-${index + 1}-${k + 1}.png`)); wholes.append(c); });
    return card;
  }
  /* ----- Specification panels and assembly ----- */
  const RA = () => window.ReferenceAssembly;
  /* A specification panel's editor: whether it is drawn, its Label and Sub Label, three optional dimensions and any number of named lines. */
  function panelEditor(panel, key, title, note, names) {                  // names: [label, sub label] drawn when the fields are left empty
    const units = P().layout.units, [big, small] = units === 'imperial' ? ['ft', 'in'] : ['m', 'cm'];
    const filled = panel.fields.filter(f => f.value.trim()).length + Object.values(panel.dims).filter(Boolean).length;
    const box = el(`<details class="cc-section rg-panel" data-panel="${key}"${openPanels.has(key) ? ' open' : ''}><summary><b>${esc(title)}</b><span class="hint">${panel.include ? 'On the sheet' : 'Not on the sheet'} · ${esc(panel.label || names[0] || 'no label')} · ${filled} line${filled === 1 ? '' : 's'} filled in</span></summary><div class="cc-body rg-panelbody">
      <label class="cc-check"><input type="checkbox" data-k="pi-${key}" class="rg-pinclude"${panel.include ? ' checked' : ''}> <span>Include this panel on the assembled sheet</span></label><span class="hint">${esc(note)} Switching it off keeps everything typed here.</span>
      <div class="rg-fields"><label class="ag-label">Label<input data-k="pl-${key}" class="rg-plabel" type="text" maxlength="60" value="${esc(panel.label)}" placeholder="${esc(names[0] || 'for example: Pirate Hat')}"></label>
        <label class="ag-label">Sub Label<input data-k="ps-${key}" class="rg-psub" type="text" maxlength="60" value="${esc(panel.sub_label)}" placeholder="${esc(names[1] || 'for example: Headwear')}"></label>
        ${['height', 'width', 'depth'].map(d => { const [a, b2] = panel.dims[d] ? RA().split(panel.dims[d], units) : ['', '']; return `<span class="rg-dim" data-dim="${d}"><span class="ag-label">${cap(d)}</span><input data-k="pd-${key}-${d}-a" type="number" min="0" step="1" value="${a}" aria-label="${cap(d)} in ${big}"><i>${big}</i><input data-k="pd-${key}-${d}-b" type="number" min="0" step="0.1" value="${b2}" aria-label="${cap(d)} in ${small}"><i>${small}</i></span>`; }).join('')}</div>
      <div class="rg-plines"></div><div><button class="small rg-padd" type="button"${panel.fields.length >= 16 ? ' disabled' : ''}>Add a line</button> <span class="hint">Lines left empty are not drawn. Dimensions are stored in centimetres and shown in the units chosen under Assemble.</span></div></div></details>`);
    box.addEventListener('toggle', () => { if (box.open) openPanels.add(key); else openPanels.delete(key); });
    box.querySelector('.rg-pinclude').onchange = ev => { panel.include = ev.target.checked; keep(); draw(); };
    const bind = (sel, k) => { const f = box.querySelector(sel); f.oninput = () => { panel[k] = f.value; keep(); }; };
    bind('.rg-plabel', 'label'); bind('.rg-psub', 'sub_label');
    box.querySelectorAll('.rg-dim').forEach(d => { const [a, b2] = d.querySelectorAll('input'); a.onchange = b2.onchange = () => { panel.dims[d.dataset.dim] = RA().toCm(a.value, b2.value, units) || null; keep(); }; });      // no redraw: the person may be on their way to the second box
    const lines = box.querySelector('.rg-plines');
    panel.fields.forEach((f, k) => { const row = el(`<div class="rg-pline"><input data-k="pn-${key}-${k}" type="text" maxlength="40" value="${esc(f.name)}" placeholder="Name" aria-label="Line ${k + 1} name"><input data-k="pv-${key}-${k}" type="text" maxlength="300" value="${esc(f.value)}" placeholder="Value" aria-label="Line ${k + 1} value">
        <button class="small ghost" data-a="up" type="button" aria-label="Move line up"${k ? '' : ' disabled'}>▲</button><button class="small ghost" data-a="down" type="button" aria-label="Move line down"${k < panel.fields.length - 1 ? '' : ' disabled'}>▼</button><button class="small ghost" data-a="rm" type="button" aria-label="Remove line">×</button></div>`);
      const [nm, val] = row.querySelectorAll('input'); nm.oninput = () => { f.name = nm.value; keep(); }; val.oninput = () => { f.value = val.value; keep(); };
      row.querySelector('[data-a=up]').onclick = () => { panel.fields.splice(k - 1, 0, panel.fields.splice(k, 1)[0]); keep(); draw(); };
      row.querySelector('[data-a=down]').onclick = () => { panel.fields.splice(k + 1, 0, panel.fields.splice(k, 1)[0]); keep(); draw(); };
      row.querySelector('[data-a=rm]').onclick = () => { panel.fields.splice(k, 1); keep(); draw(); }; lines.append(row); });
    box.querySelector('.rg-padd').onclick = () => { panel.fields.push({ name: '', value: '' }); keep(); draw(); };
    return box;
  }
  /* Everything reference-assembly.js needs to lay the sheet out: the pictures in use, loaded, and the text to draw. */
  async function sheetSpec(only) {                                      // only: one row's id, for a component sheet
    const p = P(), L = p.layout, load = image => new Promise(done => { const i = new Image(); i.onload = () => done(i); i.onerror = () => done(null); i.src = host.view(image); });
    const panelOf = (pn, names) => pn.include ? { label: pn.label.trim() || names[0], sub: pn.sub_label.trim() || names[1], lines: [...['height', 'width', 'depth'].filter(d => pn.dims[d]).map(d => ({ name: d, value: RA().length(pn.dims[d], L.units) })), ...pn.fields.filter(f => f.value.trim()).map(f => ({ name: f.name, value: f.value }))] } : null;
    const sections = [];
    for (const section of data.sections) {
      const blocks = [];
      for (const row of p.rows.filter(r => r.section === section && (!only || r.id === only))) {
        const views = data.directions.filter(d => row.slots[d].enabled && chosenOf(row, d)).map(d => ({ a: chosenOf(row, d), caption: cap(d) })), whole = chosenOf(row, null);
        const pick = (row.assemble === 'whole' || !views.length) && whole ? [{ a: whole, caption: '' }] : views, images = [];
        for (const x of pick) { const img = await load(x.a.image); if (img && img.naturalWidth) images.push({ img, caption: x.caption, id: x.a.id }); }
        blocks.push({ label: row.label, sub: row.role, fraction: row.width === 'half' ? 0.5 : row.width === 'custom' ? row.width_pct / 100 : 1, images, panel: section === 'detail' ? panelOf(row.panel, [row.label, row.role]) : null });
      }
      if (section === 'base' && p.panel.include) { const first = blocks.find(b => b.images.length); const names = [p.name, typeOf(p.type).label + (p.subtype ? ' · ' + (p.subtype === 'Custom' ? p.custom_subtype : p.subtype) : '')]; if (first) first.panel = panelOf(p.panel, names); else blocks.unshift({ label: '', sub: '', fraction: 1, images: [], panel: panelOf(p.panel, names) }); }
      sections.push({ name: section, blocks });
    }
    const css = getComputedStyle(document.documentElement), width = L.orientation === 'portrait' ? Math.round(L.resolution / Math.SQRT2 / 16) * 16 : L.resolution;
    const one = only && p.rows.find(r => r.id === only);
    return { width, height: only ? 0 : L.height, background: L.background === 'solid' ? L.colour : null, margin: Math.round(L.margin * width / 2048), spacing: Math.round(L.spacing * width / 2048), labels: L.labels, align: L.align,
      title: one ? `${p.name} · ${one.label || one.role || 'Component'}` : L.title ? p.name : '', accent: css.getPropertyValue('--swift-green').trim(), font: getComputedStyle(document.body).fontFamily, panelStyle: L.panel_style, sections };
  }
  const stampOf = p => JSON.stringify([p.name, p.rows.map(r => [r.id, r.section, r.label, r.role, r.width, r.width_pct, r.assemble, r.selected, r.panel, data.directions.map(d => [r.slots[d].enabled, (chosenOf(r, d) || {}).id])]), p.panel, p.layout]);
  function assembleBox() {
    const p = P(), L = p.layout, o = data.layout_options, sel = (k, text, names) => `<label>${text}<select data-k="ly-${k}" data-ly="${k}">${o[k].map(v => `<option value="${v}"${v === L[k] ? ' selected' : ''}>${esc((names || {})[v] || cap(v))}</option>`).join('')}</select></label>`;
    const have = p.rows.some(r => data.directions.some(d => r.slots[d].enabled && chosenOf(r, d)) || chosenOf(r, null)), mine = preview && preview.pid === p.id ? preview : null, stale = mine && mine.stamp !== stampOf(p);
    const sheets = arts('sheet').filter(a => a.origin === 'assembled');
    const box = el(`<section class="rg-assemble"><h2>Assemble the sheet</h2>
      <p class="hint">Puts the pictures in use into one sheet: Base rows on top, Detail rows below, in the order above. The pictures are placed as they are, scaled to fit without stretching; nothing is regenerated, nothing is extracted, and the rows are not changed.</p>
      <div class="ag-run rg-layout">${sel('orientation', 'Orientation')}<label>Width<select data-k="ly-resolution" data-ly="resolution">${data.profiles.map(x => `<option value="${x.profile}"${x.profile === L.resolution ? ' selected' : ''}>${L.orientation === 'portrait' ? Math.round(x.profile / Math.SQRT2 / 16) * 16 : x.profile} px</option>`).join('')}</select></label>
        <label>Height (0 = automatic)<input data-k="ly-height" data-ly="height" class="ag-n" type="number" min="0" max="16384" step="16" value="${L.height}"></label>
        ${sel('background', 'Background', { solid: 'Solid colour', transparent: 'See-through' })}${L.background === 'solid' ? `<label>Colour<input data-k="ly-colour" data-ly="colour" type="color" value="${esc(L.colour)}"></label>` : ''}
        ${sel('align', 'Pictures', { left: 'To the left', center: 'Centred', right: 'To the right' })}<label>Spacing<input data-k="ly-spacing" data-ly="spacing" class="ag-n" type="number" min="0" max="200" step="4" value="${L.spacing}"></label>
        <label>Margin<input data-k="ly-margin" data-ly="margin" class="ag-n" type="number" min="0" max="400" step="4" value="${L.margin}"></label>${sel('panel_style', 'Panels', { boxed: 'In a box', plain: 'Plain text' })}${sel('units', 'Units', { metric: 'Metres and centimetres', imperial: 'Feet and inches' })}
        <label class="cc-check"><input type="checkbox" data-k="ly-labels" data-ly="labels"${L.labels ? ' checked' : ''}> <span>Row and view names</span></label><label class="cc-check"><input type="checkbox" data-k="ly-title" data-ly="title"${L.title ? ' checked' : ''}> <span>Title (the reference's name)</span></label></div>
      <div class="rg-fields"><button class="primary rg-preview" type="button"${have ? '' : ' disabled'}>Preview the assembled sheet</button><button class="rg-savesheet" type="button"${mine && !stale ? '' : ' disabled'}>Save as a sheet</button>
        <span class="hint">${!have ? 'No row has a picture in use yet.' : !mine ? 'Preview first; saving stores exactly what the preview shows, as a new pending sheet.' : stale ? 'Something changed since this preview. Preview again before saving.' : `${mine.canvas.width} × ${mine.canvas.height} pixels, ${mine.used.length} picture${mine.used.length === 1 ? '' : 's'}.${mine.scale < 1 ? ' The content was shrunk to fit the height you set.' : ''}`}</span></div>
      <div class="rg-previewhold${L.background === 'transparent' ? ' rg-checker' : ''}"></div>
      <h2>Assembled sheets <span class="hint">${sheets.length}</span></h2><div class="rg-sheets"></div></section>`);
    box.querySelectorAll('[data-ly]').forEach(f => { f.onchange = () => { const k = f.dataset.ly; L[k] = f.type === 'checkbox' ? f.checked : f.type === 'number' || k === 'resolution' ? +f.value : f.value; keep(); draw(); }; });
    if (mine) box.querySelector('.rg-previewhold').append(mine.canvas);
    box.querySelector('.rg-preview').onclick = async ev => {
      ev.target.disabled = true; ev.target.textContent = 'Laying out…';
      try { if (document.fonts && document.fonts.ready) await document.fonts.ready; const pl = RA().plan(await sheetSpec()), canvas = RA().draw(pl);
        preview = { pid: p.id, canvas, plan: pl, scale: pl.scale, used: [...new Set(pl.items.filter(i => i.type === 'image').map(i => i.id))], stamp: stampOf(p) }; canvas.onclick = () => host.openViewer(canvas.toDataURL('image/png')); }
      catch (e) { host.toast(e.message); }
      draw();
    };
    box.querySelector('.rg-savesheet').onclick = async ev => {
      ev.target.disabled = true; ev.target.textContent = 'Saving…'; flush();
      try { const out = await call('POST', '/assemble', { project: host.pid, reference: p.id, png: mine.canvas.toDataURL('image/png'), used: mine.used, state: S() }); preview = null; take(out, true); host.toast('Saved as a new sheet. It is pending until you approve it.'); }
      catch (e) { host.toast(e.message); draw(); }
    };
    const grid = box.querySelector('.rg-sheets');
    if (!sheets.length) grid.append(el('<p class="hint">None yet.</p>'));
    sheets.forEach((a, k) => { const c = el(`<div class="rg-view rg-sheetcard"><img alt="Assembled sheet ${k + 1}" loading="lazy" src="${esc(host.view(a.image))}"><b>Assembled sheet ${k + 1}</b><span class="hint">${a.width} × ${a.height} · made from ${a.requires.length} picture${a.requires.length === 1 ? '' : 's'}</span>${pill(a)}${p.selected === a.id ? '<span class="pill rg-selected">Selected sheet</span>' : ''}<span class="rg-actions rg-sheetbtns"></span></div>`);
      c.querySelector('img').onclick = () => host.openViewer(host.view(a.image));
      const pick = el(`<button class="small" type="button"${p.selected === a.id ? ' disabled' : ''} title="Make this the project's sheet. It does not approve it.">${p.selected === a.id ? 'Selected' : 'Select as the sheet'}</button>`); pick.onclick = () => { p.selected = a.id; keep(); draw(); };
      const cut = el('<button class="small" type="button" title="Open Sheet Extraction with this sheet. Nothing is cut until you say so.">Extract from this sheet…</button>'); cut.onclick = () => { p.extraction = { source: a.image, regions: [] }; workflow = 'extract'; keep(); draw(); };
      c.querySelector('.rg-sheetbtns').append(pick, cut); c.append(actions(a, `${stem()}-assembled-${k + 1}.png`)); grid.append(c); });
    return box;
  }

  /* ----- Export (design 11) and the hand-over to 3D Generation ----- */
  const EXPORT_HELP = { sheet: 'The selected sheet, as one picture.', views: 'A ZIP of the individual views that exist: each row\u2019s views in use and the extracted views.',
    package: 'A ZIP of the selected sheet, the individual views, and ReferenceManifest.json describing them.', components: 'A ZIP with one sheet for each row that has pictures, assembled from that row, with its panel if the panel is ticked.' };
  const hoursText = h => h >= 24 ? `${Math.ceil(h / 24)} day${Math.ceil(h / 24) > 1 ? 's' : ''}` : `${Math.max(1, h)} hour${h > 1 ? 's' : ''}`;
  const bytesOf = async url => { const r = await fetch(url); if (!r.ok) throw new Error('A picture could not be read from the server.'); return new Uint8Array(await r.arrayBuffer()); };
  const saveBlob = (blob, name) => { const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000); };
  async function runExport(profile, button) {
    const p = P(), label = button.textContent; button.disabled = true; flush();
    try {
      await call('POST', '/save', { project: host.pid, state: S() });
      const plan = await call('POST', '/export', { project: host.pid, reference: p.id, profile });
      if (plan.pending.length) {                                         // design 11 and 2.13: name what is pending and how long it has
        const rows = plan.pending.map(x => `<li><img alt="" src="${esc(host.view(x.image))}"><span><b>${esc(x.what)}</b> · not approved · deleted in ${hoursText(x.hours_left)}</span></li>`).join('');
        const go = await dialog('Export Unapproved Asset', `<p>This export contains pictures that have not been approved for permanent storage. They will be deleted from SWIFT Director when their time runs out unless you approve them first. Exporting does not approve them or give them more time. Your downloaded copy is not affected when the local ones are deleted. Continue?</p><p><b>${esc(p.name)}</b></p><ul class="rg-needs">${rows}</ul>`, [['Cancel', null], ['Continue Export', 'yes', true]]);
        if (!go) return;
      }
      button.textContent = 'Preparing…';
      if (!plan.zip) { saveBlob(new Blob([await bytesOf(host.view(plan.files[0].image))], { type: 'image/png' }), plan.name); return; }
      const entries = [];
      for (const f of plan.files) entries.push({ path: f.path, data: await bytesOf(host.view(f.image)) });
      if (plan.components.length && document.fonts && document.fonts.ready) await document.fonts.ready;
      for (const c of plan.components) {                                 // each component sheet is laid out from its own row, the same way a full sheet is
        const canvas = RA().draw(RA().plan(await sheetSpec(c.row))), blob = await new Promise(done => canvas.toBlob(done, 'image/png'));
        entries.push({ path: c.path, data: new Uint8Array(await blob.arrayBuffer()) });
        const entry = plan.manifest.files.find(x => x.path === c.path); if (entry) { entry.width = canvas.width; entry.height = canvas.height; }
      }
      entries.push({ path: 'ReferenceManifest.json', data: new TextEncoder().encode(JSON.stringify(plan.manifest, null, 2)) });
      saveBlob(window.ZipStore.build(entries), plan.name);
      host.toast(`Exported ${entries.length - 1} picture${entries.length === 2 ? '' : 's'} and the manifest.`);
    } catch (e) { host.toast(e.message); }
    finally { button.disabled = false; button.textContent = label; }
  }
  function exportBox() {
    const p = P(), sent = data.handover.find(h => h.reference === p.id);
    const box = el(`<section class="panel rg-export"><h2>Export</h2><p class="hint">Exports contain only pictures that already exist. Nothing is generated or extracted to fill a gap, and exporting does not approve anything.</p>
      <div class="rg-exports">${data.exports.map(x => `<div><button class="rg-exportbtn" data-profile="${x.key}" type="button">${esc(x.label)}</button><span class="hint">${EXPORT_HELP[x.key]}</span></div>`).join('')}</div>
      <h2>3D Generation</h2><div class="rg-fields"><button class="rg-send" type="button">${sent ? 'Send again to 3D Generation' : 'Send to 3D Generation'}</button>
        <span class="hint">${sent ? `${sent.items.length} picture${sent.items.length === 1 ? '' : 's'} sent. ` : ''}Hands over the selected sheet, each row's views in use and the extracted views, with the classification. Nothing is copied or approved. <button class="small ghost rg-to3d" type="button">Open 3D Generation</button></span></div></section>`);
    box.querySelectorAll('.rg-exportbtn').forEach(b => { b.onclick = () => runExport(b.dataset.profile, b); });
    box.querySelector('.rg-send').onclick = async ev => { ev.target.disabled = true; flush();
      try { await call('POST', '/save', { project: host.pid, state: S() }); take(await call('POST', '/send', { project: host.pid, reference: p.id }), true); host.toast('Sent to 3D Generation.'); } catch (e) { host.toast(e.message); draw(); } };
    box.querySelector('.rg-to3d').onclick = () => tools.go('3d');
    return box;
  }
  /* What 3D Generation shows: the references sent from here, looked up as they are now. */
  function drawSide() {
    side.innerHTML = '';
    if (!data) { side.append(el('<section class="panel"><span class="hint">Loading…</span></section>')); return; }
    const box = el(`<section class="panel"><div class="rg-fields"><h2>Reference pictures</h2><span class="ag-grow"></span><button class="small rg-getrefs" type="button">Make or choose references in Reference Generation</button></div>
      <p class="hint">3D Generation uses reference pictures made elsewhere; it has no picture-making controls of its own. ${data.handover.length ? 'These were sent from Reference Generation. They are the same pictures, not copies, so one that is denied or expires there disappears here.' : 'Nothing has been sent yet.'} Assigning them to 3D assets arrives with the asset definition phase.</p><div class="rg-handed"></div></section>`);
    box.querySelector('.rg-getrefs').onclick = () => tools.go('reference');
    const list = box.querySelector('.rg-handed');
    data.handover.forEach(h => { const gone = h.items.filter(i => i.state === 'gone').length, pend = h.items.filter(i => i.state === 'pending').length;
      const card = el(`<div class="rg-handcard"><div class="rg-fields"><b>${esc(h.name)}</b><span class="hint">${esc(h.parent_label)} / ${esc(h.type_label)}${h.subtype ? ' / ' + esc(h.subtype) : ''} · ${h.items.length} picture${h.items.length === 1 ? '' : 's'}${pend ? ` · ${pend} not approved yet` : ''}${gone ? ` · ${gone} no longer there` : ''}</span><span class="ag-grow"></span>
          <button class="small rg-openref" type="button">Open in Reference Generation</button><button class="small ghost rg-unsend" type="button">Remove</button></div><div class="rg-handitems"></div></div>`);
      h.items.forEach(i => { const what = i.role === 'sheet' ? 'Sheet' : cap(i.role), c = el(`<div class="rg-handitem${i.state === 'gone' ? ' rg-missing' : ''}" title="${esc([i.row_label, i.component].filter(Boolean).join(' · '))}">${i.image ? `<img alt="${esc(what)}" loading="lazy" src="${esc(host.view(i.image))}">` : '<span class="hint">Gone</span>'}<span>${esc(what)}${i.component && i.role !== 'sheet' ? ' · ' + esc(i.component) : ''}</span></div>`);
        const img = c.querySelector('img'); if (img) img.onclick = () => host.openViewer(host.view(i.image)); card.querySelector('.rg-handitems').append(c); });
      card.querySelector('.rg-openref').onclick = () => { if (S().projects.some(x => x.id === h.reference)) { S().open = h.reference; workflow = 'generate'; keep(); } tools.go('reference'); };
      card.querySelector('.rg-unsend').onclick = async () => { try { take(await call('POST', '/send', { project: host.pid, remove: h.id }), true); } catch (e) { host.toast(e.message); } };
      list.append(card); });
    side.append(box);
  }

  function advanced() {
    const p = P(), box = el(`<section class="panel rg-gen rg-adv"><datalist id="rg-roles">${data.roles.map(r => `<option value="${esc(r)}">`).join('')}</datalist>
      <p class="hint">A row is one thing to document: the complete asset, its base anatomy, or one component such as a hat or a coat. Each row has its own sources, prompt and up to six views. Generating or changing one row or view never touches another. When the rows have pictures, assemble them into one sheet at the bottom.</p>
      <div class="cc rg-basepanel"></div>
      <div class="rg-rows"></div><div class="rg-fields"><button class="rg-addbase" type="button">Add a Base row</button><button class="rg-adddetail" type="button">Add a Detail row</button><span class="hint">${p.rows.length} of ${data.limits.rows} rows</span></div></section>`);
    box.prepend(modeBar());
    box.querySelector('.rg-basepanel').append(panelEditor(p.panel, 'base', 'Base specification panel', 'Drawn beside the first Base row.', [p.name, typeOf(p.type).label]));
    box.append(assembleBox());
    const rows = box.querySelector('.rg-rows');
    ['base', 'detail'].forEach(section => { const mine = p.rows.filter(r => r.section === section); if (mine.length) rows.append(el(`<h2>${cap(section)} <span class="hint">${mine.length}</span></h2>`)); mine.forEach(r => rows.append(rowCard(r, p.rows.indexOf(r)))); });
    if (!p.rows.length) rows.append(el('<p class="hint">No rows yet.</p>'));
    const add = section => () => { if (p.rows.length >= data.limits.rows) return; p.rows.push({ id: newId('rw'), section, label: '', role: section === 'base' ? 'Complete asset' : 'Component' }); saveNow(); };
    box.querySelector('.rg-addbase').onclick = add('base'); box.querySelector('.rg-adddetail').onclick = add('detail');
    return box;
  }

  /* ----- Simple mode ----- */
  function simple() {
    const p = P(), list = arts('sheet').filter(a => a.origin !== 'assembled'), i = Math.max(0, list.findIndex(a => a.id === p.at)), cur = list.length ? (list.some(a => a.id === p.at) ? list[i] : list[list.length - 1]) : null, n = cur ? list.indexOf(cur) : -1;
    const dims = data.profiles.find(x => x.profile === p.profile).sizes[p.aspect], working = busy(p.id), failed = (data.jobs[p.id] || []).filter(j => j.status === 'error');
    const b = batch[p.id], doneNow = b ? Math.min(b.asked, list.length - b.had) : 0;
    const box = el(`<section class="panel rg-gen">
      <div class="ag-label">Source pictures (up to ${data.limits.sources}) <span class="hint">All of them are sent to the image model as the subject to keep.</span></div>
      <div class="rg-sources"></div>
      <label class="ag-label">Prompt<span class="ag-promptwrap"><textarea data-k="rg-prompt" class="rg-prompt" rows="5">${esc(p.prompt)}</textarea><span class="ag-chars"></span></span></label>
      <div class="hint">${p.prompt_edited ? 'This is your own prompt. <button class="small ghost rg-recommend" type="button">Use the recommended prompt</button>' : `Recommended for a ${esc(typeOf(p.type).label.toLowerCase())}. It follows the name and classification until you change it.`} Text on a sheet is not asked of the image model; specification panels will be added by the application.</div>
      <div class="ag-run"><label>Resolution<select data-k="rg-profile" class="rg-profile">${data.profiles.map(x => `<option value="${x.profile}"${x.profile === p.profile ? ' selected' : ''}>${x.profile}</option>`).join('')}</select></label>
        <label>Shape<select data-k="rg-aspect" class="rg-aspect">${data.aspects.map(a => `<option${a === p.aspect ? ' selected' : ''}>${a}</option>`).join('')}</select></label>
        <label>Sheets<input data-k="rg-count" class="ag-n rg-count" type="number" min="1" max="${data.limits.count}" step="1" value="${p.count}"></label>
        <button data-k="rg-run" class="primary rg-run" type="button"${dims.blocked ? ' disabled' : ''}>Run generations</button>
        <span class="hint rg-size">${dims.size[0]} × ${dims.size[1]} pixels, made by ${esc(data.provider.name)}.</span></div>
      ${dims.blocked ? `<div class="rg-blocked">${esc(dims.blocked)}</div>` : ''}
      <h2>Sheets</h2>
      <div class="ag-stage rg-stage"><button class="ag-arrow rg-prev" type="button" aria-label="Previous sheet"${n > 0 ? '' : ' disabled'}>‹</button>
        <div class="ag-pic rg-pic">${cur ? `<img alt="Reference sheet ${n + 1}" src="${esc(host.view(cur.image))}">` : `<div class="ag-empty${working ? ' ag-working' : ''}">${working && b ? `Generating ${doneNow}/${b.asked} sheets` : working ? 'Generating…' : 'No sheets yet'}</div>`}</div>
        <button class="ag-arrow rg-next" type="button" aria-label="Next sheet"${n >= 0 && n < list.length - 1 ? '' : ' disabled'}>›</button></div>
      <div class="ag-under rg-under"><span class="hint">${cur ? (n + 1) + ' of ' + list.length : ''}</span>${cur ? pill(cur) : ''}${cur && p.selected === cur.id ? '<span class="pill rg-selected">Selected sheet</span>' : ''}
        <span class="hint rg-status">${working ? (cur && b ? `Generating an additional ${b.asked - doneNow} sheet${b.asked - doneNow === 1 ? '' : 's'}` : cur ? 'Generating…' : '') : ''}${failed.length ? ' ' + esc(failed[0].error || 'A sheet failed.') : ''}</span><span class="ag-grow"></span></div>
      ${cur ? `<div class="hint rg-meta">${cur.width && cur.height ? `${cur.width} × ${cur.height} pixels, not upscaled. ` : ''}${cur.sources ? `Made from ${cur.sources.length} source picture${cur.sources.length === 1 ? '' : 's'}${cur.sources.length ? ', all of them used' : ''}. ` : ''}Selecting, downloading or extracting from a pending sheet does not approve it or give it more time.</div>` : ''}</section>`);
    box.prepend(modeBar());
    const src = box.querySelector('.rg-sources');
    p.sources.forEach((image, k) => { const c = el(`<div class="ag-ref"><img alt="Source ${k + 1}" src="${esc(host.view(image))}"><button class="ag-x" type="button" aria-label="Remove source ${k + 1}">×</button><span class="ag-num">${k + 1}</span></div>`);
      c.querySelector('img').onclick = () => host.openViewer(host.view(image)); c.querySelector('.ag-x').onclick = () => { p.sources.splice(k, 1); keep(); draw(); }; src.append(c); });
    if (p.sources.length < data.limits.sources) src.append(source('+ Add a source picture', image => { if (!p.sources.includes(image)) p.sources.push(image); keep(); draw(); }, p.sources));
    const area = box.querySelector('.rg-prompt'), count = box.querySelector('.ag-chars');
    const show = () => { const len = area.value.length, lim = data.prompt_limit.characters; count.textContent = len.toLocaleString() + ' / ' + lim.toLocaleString(); count.className = 'ag-chars' + (len > lim ? ' ag-over' : len > lim * 0.9 ? ' ag-near' : ''); fit(area); };
    area.oninput = () => { p.prompt = area.value; p.prompt_edited = true; keep(); show(); }; area.onchange = () => draw(); show(); requestAnimationFrame(show);
    const rec = box.querySelector('.rg-recommend'); if (rec) rec.onclick = () => { p.prompt_edited = false; flush(); call('POST', '/save', { project: host.pid, state: S() }).then(out => take(out, true)).catch(e => host.toast(e.message)); };
    box.querySelector('.rg-profile').onchange = ev => { p.profile = +ev.target.value; keep(); draw(); };
    box.querySelector('.rg-aspect').onchange = ev => { p.aspect = ev.target.value; keep(); draw(); };
    box.querySelector('.rg-count').onchange = ev => { p.count = Math.max(1, Math.min(data.limits.count, Math.round(+ev.target.value) || 1)); keep(); draw(); };
    box.querySelector('.rg-run').onclick = async ev => {
      ev.target.disabled = true; flush(); batch[p.id] = { asked: p.count, had: list.length };
      try { take(await call('POST', '/run', { project: host.pid, reference: p.id, state: S() }), true); } catch (e) { delete batch[p.id]; host.toast(e.message); draw(); }
    };
    if (!working) delete batch[p.id];
    box.querySelector('.rg-prev').onclick = () => { p.at = list[n - 1].id; keep(); draw(); };
    box.querySelector('.rg-next').onclick = () => { p.at = list[n + 1].id; keep(); draw(); };
    if (cur) {
      box.querySelector('.rg-pic img').onclick = () => host.openViewer(host.view(cur.image));
      const under = box.querySelector('.rg-under');
      const pick = el(`<button class="small rg-select" type="button"${p.selected === cur.id ? ' disabled' : ''} title="Make this the project's sheet. It does not approve it.">${p.selected === cur.id ? 'Selected' : 'Select as the sheet'}</button>`);
      pick.onclick = () => { p.selected = cur.id; keep(); draw(); };
      const cut = el('<button class="small rg-toextract" type="button" title="Open Sheet Extraction with this sheet. Nothing is cut until you say so.">Extract from this sheet…</button>');
      cut.onclick = () => { p.extraction = { source: cur.image, regions: [] }; workflow = 'extract'; keep(); draw(); };
      under.append(pick, cut, actions(cur, `${stem()}-sheet-${n + 1}.png`));
    }
    return box;
  }

  /* ---------- Sheet Extraction ---------- */
  /* Find separate shapes on a plain background: shrink the sheet, call every pixel that differs from the border colour
   * "something", join what touches, and box each group. It knows nothing about what a shape is or which way it faces. */
  function detect(img) {
    const k = Math.min(1, 320 / Math.max(img.naturalWidth, img.naturalHeight)), w = Math.max(1, Math.round(img.naturalWidth * k)), h = Math.max(1, Math.round(img.naturalHeight * k));
    const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(img, 0, 0, w, h);
    const px = g.getImageData(0, 0, w, h).data, edge = [];
    for (let x = 0; x < w; x++) edge.push(x, (h - 1) * w + x); for (let y = 0; y < h; y++) edge.push(y * w, y * w + w - 1);
    const mid = ch => { const v = edge.map(i => px[i * 4 + ch]).sort((a, b) => a - b); return v[v.length >> 1]; }, bg = [mid(0), mid(1), mid(2)];
    let on = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) on[i] = px[i * 4 + 3] > 24 && Math.abs(px[i * 4] - bg[0]) + Math.abs(px[i * 4 + 1] - bg[1]) + Math.abs(px[i * 4 + 2] - bg[2]) > 36 ? 1 : 0;
    for (let pass = 0; pass < 2; pass++) { const grown = new Uint8Array(on);      // close small gaps so one subject is one group
      for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) { const i = y * w + x; if (on[i - 1] || on[i + 1] || on[i - w] || on[i + w]) grown[i] = 1; } on = grown; }
    const seen = new Uint8Array(w * h), found = [];
    for (let start = 0; start < w * h; start++) {
      if (!on[start] || seen[start]) continue;
      let x0 = w, y0 = h, x1 = 0, y1 = 0; const todo = [start]; seen[start] = 1;
      while (todo.length) { const i = todo.pop(), x = i % w, y = (i - x) / w; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
        for (const j of [i - 1, i + 1, i - w, i + w]) if (j >= 0 && j < w * h && on[j] && !seen[j] && Math.abs((j % w) - x) <= 1) { seen[j] = 1; todo.push(j); } }
      const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
      if (bw * bh >= w * h * 0.012 && bh >= h * 0.06 && bw >= w * 0.03 && bw * bh < w * h * 0.97) found.push({ x: x0 / k, y: y0 / k, w: bw / k, h: bh / k });      // small or thin groups are most likely text
    }
    return found.sort((a, b) => Math.abs(a.y - b.y) > img.naturalHeight * 0.08 ? a.y - b.y : a.x - b.x).slice(0, 24);
  }
  function extraction() {
    const p = P(), ex = p.extraction, sheets = arts('sheet'), views = arts('view').filter(a => a.region);      // only the ones cut out of a sheet
    const box = el(`<section class="panel rg-ext">
      <div class="rg-fields"><span class="ag-label">Sheet to extract from</span>${sheets.length ? `<select data-k="rg-from" class="rg-from"><option value="">Choose one of this project's sheets…</option>${sheets.map((a, k) => `<option value="${esc(a.image)}"${a.image === ex.source ? ' selected' : ''}>Sheet ${k + 1}${p.selected === a.id ? ' (selected)' : ''}</option>`).join('')}</select>` : ''}<span class="rg-pick"></span>
        ${ex.source ? '<button class="small ghost rg-clear" type="button">Clear</button>' : ''}</div>
      ${ex.source ? `<p class="hint">Drag on the sheet to mark a region. Click a region to select it, then set what it shows on the right. Extracting cuts each region out at the sheet's own pixels: nothing is resized, redrawn or invented, and the sheet is not changed.</p>
        <div class="rg-work"><div class="rg-sheetwrap"><div class="rg-sheet"><img alt="The sheet to extract from" draggable="false" src="${esc(host.view(ex.source))}"></div></div>
          <div class="rg-side"><div class="rg-sidebtns"><button class="small rg-detect" type="button" title="Finds separate shapes on a plain background. It cannot tell which way a view faces, so set that yourself.">Detect regions</button>
            <button class="small ghost rg-none" type="button"${ex.regions.length ? '' : ' disabled'}>Remove all</button></div><div class="rg-regions"></div>
            <button class="primary rg-cut" type="button"${ex.regions.length ? '' : ' disabled'}>Extract ${ex.regions.length || ''} region${ex.regions.length === 1 ? '' : 's'}</button></div></div>`
      : '<p class="hint">Choose a sheet made here, upload one (PNG, JPEG or WebP), or take one from the Library. Extraction only ever starts from this page.</p>'}
      <h2>Extracted views <span class="hint">${views.length}</span></h2><div class="rg-views"></div></section>`);
    const setSource = image => { p.extraction = { source: image, regions: [] }; chosen = null; keep(); draw(); };
    box.querySelector('.rg-pick').append(source(ex.source ? 'Use another picture' : 'Upload or choose a picture', setSource, []));
    const from = box.querySelector('.rg-from'); if (from) from.onchange = () => { if (from.value) setSource(from.value); };
    const grid = box.querySelector('.rg-views');
    if (!views.length) grid.append(el('<p class="hint">Nothing has been extracted in this reference project yet.</p>'));
    views.forEach((a, k) => { const what = a.direction ? cap(a.direction) : a.component || 'Detail';
      const card = el(`<div class="rg-view"><img alt="${esc(what)}" loading="lazy" src="${esc(host.view(a.image))}"><b>${esc(what)}</b><span class="hint">${cap(a.section)}${a.component && a.direction ? ' · ' + esc(a.component) : ''} · ${a.width} × ${a.height}, original pixels</span>${pill(a)}</div>`);
      card.querySelector('img').onclick = () => host.openViewer(host.view(a.image)); card.append(actions(a, `${stem()}-${what.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${k + 1}.png`)); grid.append(card); });
    if (!ex.source) return box;
    box.querySelector('.rg-clear').onclick = () => setSource('');
    const sheet = box.querySelector('.rg-sheet'), img = sheet.querySelector('img'), side = box.querySelector('.rg-regions');
    const W = () => img.naturalWidth, H = () => img.naturalHeight;
    const clamp = r => { r.x = Math.max(0, Math.min(W() - 8, Math.round(r.x))); r.y = Math.max(0, Math.min(H() - 8, Math.round(r.y))); r.w = Math.max(8, Math.min(W() - r.x, Math.round(r.w))); r.h = Math.max(8, Math.min(H() - r.y, Math.round(r.h))); return r; };
    const marks = () => {
      sheet.querySelectorAll('.rg-mark').forEach(m => m.remove()); if (!W()) return;
      ex.regions.forEach((r, k) => { const m = el(`<button type="button" class="rg-mark${r.id === chosen ? ' on' : ''}" style="left:${r.x / W() * 100}%;top:${r.y / H() * 100}%;width:${r.w / W() * 100}%;height:${r.h / H() * 100}%" aria-label="Region ${k + 1}"><span>${k + 1}${r.direction ? ' ' + cap(r.direction) : ''}</span></button>`);
        m.onpointerdown = ev => ev.stopPropagation(); m.onclick = () => { chosen = r.id; marks(); rows(); }; sheet.append(m); });
    };
    const rows = () => {
      side.innerHTML = ''; if (!ex.regions.length) side.append(el('<p class="hint">No regions yet.</p>'));
      ex.regions.forEach((r, k) => {
        const row = el(`<div class="rg-region${r.id === chosen ? ' on' : ''}"><b>${k + 1}</b>
          <label>Shows<select data-f="direction"><option value="">Not a direction (detail)</option>${data.directions.map(d => `<option value="${d}"${d === r.direction ? ' selected' : ''}>${cap(d)}</option>`).join('')}</select></label>
          <label>Section<select data-f="section">${data.sections.map(s => `<option value="${s}"${s === r.section ? ' selected' : ''}>${cap(s)}</option>`).join('')}</select></label>
          <label>Component<input data-f="component" type="text" maxlength="60" placeholder="for example: head, coat" value="${esc(r.component)}"></label>
          <span class="rg-box">${['x', 'y', 'w', 'h'].map(f => `<label>${f === 'w' ? 'Width' : f === 'h' ? 'Height' : f.toUpperCase()}<input data-n="${f}" type="number" min="0" step="1" value="${r[f]}"></label>`).join('')}</span>
          <button class="small ghost rg-rm" type="button" aria-label="Remove region ${k + 1}">Remove</button>${r.detected && !r.direction ? '<span class="hint rg-unsure">Detected automatically: check the edges and say what it shows.</span>' : ''}</div>`);
        row.onclick = ev => { if (chosen !== r.id && !ev.target.closest('button')) { chosen = r.id; marks(); side.querySelectorAll('.rg-region').forEach((x, j) => x.classList.toggle('on', j === k)); } };
        row.querySelectorAll('[data-f]').forEach(f => { f.onchange = () => { r[f.dataset.f] = f.value; keep(); marks(); rows(); }; });
        row.querySelectorAll('[data-n]').forEach(f => { f.onchange = () => { r[f.dataset.n] = +f.value || 0; clamp(r); keep(); marks(); rows(); }; });
        row.querySelector('.rg-rm').onclick = () => { ex.regions.splice(k, 1); keep(); draw(); };
        side.append(row);
      });
    };
    const ready = () => { ex.regions.forEach(clamp); marks(); rows(); };
    if (img.complete && W()) ready(); else img.onload = ready;
    /* Drawing a new region: press on the sheet, drag, let go. */
    sheet.onpointerdown = ev => {
      if (ev.button || !W() || ex.regions.length >= data.limits.regions) return;
      const box0 = img.getBoundingClientRect(), at = e => ({ x: Math.max(0, Math.min(1, (e.clientX - box0.left) / box0.width)) * W(), y: Math.max(0, Math.min(1, (e.clientY - box0.top) / box0.height)) * H() });
      const a = at(ev), ghost = el('<div class="rg-mark rg-ghost"></div>'); sheet.append(ghost); sheet.setPointerCapture(ev.pointerId);
      const shape = e => { const b = at(e); return { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) }; };
      sheet.onpointermove = e => { const r = shape(e); ghost.style.cssText = `left:${r.x / W() * 100}%;top:${r.y / H() * 100}%;width:${r.w / W() * 100}%;height:${r.h / H() * 100}%`; };
      sheet.onpointerup = e => { sheet.onpointermove = sheet.onpointerup = null; ghost.remove(); const r = shape(e);
        if (r.w >= 8 && r.h >= 8) { const made = clamp({ id: 'r' + Date.now().toString(36) + ex.regions.length, ...r, direction: '', section: r.y + r.h / 2 < H() * 0.55 ? 'base' : 'detail', component: '', detected: false }); ex.regions.push(made); chosen = made.id; keep(); draw(); } };
    };
    box.querySelector('.rg-detect').onclick = () => {
      if (!W()) return; const found = detect(img);
      if (!found.length) { host.toast('No separate shapes were found. This works on sheets with a plain background; mark the regions by hand instead.'); return; }
      ex.regions = found.map((r, k) => clamp({ id: 'd' + Date.now().toString(36) + k, ...r, direction: '', section: r.y + r.h / 2 < H() * 0.55 ? 'base' : 'detail', component: '', detected: true })); chosen = null; keep(); draw();
      host.toast(`${found.length} region${found.length > 1 ? 's' : ''} found. Check each one and say what it shows.`);
    };
    box.querySelector('.rg-none').onclick = () => { ex.regions = []; chosen = null; keep(); draw(); };
    box.querySelector('.rg-cut').onclick = async ev => {
      ev.target.disabled = true; ev.target.textContent = 'Extracting…'; flush();
      try {
        const cuts = ex.regions.map(r => { const c = document.createElement('canvas'); c.width = r.w; c.height = r.h; c.getContext('2d').drawImage(img, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h); return { ...r, png: c.toDataURL('image/png') }; });
        await call('POST', '/save', { project: host.pid, state: S() });
        const out = await call('POST', '/extract', { project: host.pid, reference: p.id, source: ex.source, cuts });
        take(out, true); host.toast(`${out.extracted.length} view${out.extracted.length > 1 ? 's' : ''} extracted. They are pending until you approve them.`);
      } catch (e) { host.toast(e.message); draw(); }
    };
    return box;
  }

  return {
    panel(h, t) {
      host = h; tools = t; showing = true;
      if (loadedFor !== host.pid) { data = null; draw(); }
      if (!data || Date.now() - lastLoad > 5000) { lastLoad = Date.now(); load(); }      // the page above redraws often; asking again every time would be wasteful
      return root;
    },
    handover(h, t) { host = h; tools = t; if (loadedFor !== host.pid) data = null; drawSide(); if (!data || Date.now() - lastLoad > 5000) { lastLoad = Date.now(); load(); } return side; },
    hide() { showing = false; clearTimeout(timer); },
    _state: () => data, _preview: () => preview,
  };
})();
