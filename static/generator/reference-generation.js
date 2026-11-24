/* Reference Generation: the Asset Generator mode that makes reference sheets and cuts pictures out of them.
 * Design document: docs/Reference_Generation_Design.md. Server side: reference.py and the /api/reference routes.
 *
 * Two workflows, each started by the person and never by the other:
 *   Sheet Generation   Simple mode: a classification, up to four source pictures, a prompt, and 1 to 10 complete sheets.
 *   Sheet Extraction   choose a sheet, mark regions on it (by hand, or with Detect regions), and cut them out as pictures.
 * Every picture made here is pending until approved or denied, and a pending one is deleted ten days after it was made.
 *
 * The Asset Generator page owns the surrounding page and hands this file what it needs:
 *   ReferenceGeneration.panel(host, tools) -> the element to show; the same element is put back after a redraw
 *     host   { pid, upload(file) -> name, view(name) -> url, toast(text), openViewer(url) }
 *     tools  { library(choose, already), layer() -> the element modals are added to }
 *   ReferenceGeneration.hide() stops the checking for finished pictures.
 * Cutting is done here in the browser at the sheet's own pixels, with no resizing, so the server needs no image library.
 */
window.ReferenceGeneration = (function () {
  'use strict';
  let lastLoad = 0, host = null, tools = null, data = null, loadedFor = null, workflow = 'generate', timer = null, saveTimer = null, showing = false, chosen = null;
  const root = document.createElement('div'); root.className = 'rg';
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
  function actions(a, name) {
    const bar = el(`<span class="rg-actions">${a.state === 'approved' ? '' : '<button class="small rg-approve" type="button" title="Keep this picture permanently">Approve</button>'}
      <button class="small rg-deny" type="button" title="${a.state === 'approved' ? 'Delete this picture' : 'Reject this picture and delete it now'}">${a.state === 'approved' ? 'Delete' : 'Deny'}</button>
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
      S().projects.push({ id, name: 'New reference', type: 'humanoid' }); S().open = id; flush();
      call('POST', '/save', { project: host.pid, state: S() }).then(out => take(out, true)).catch(e => host.toast(e.message));
    };
    if (!p) return box;
    box.querySelector('.rg-del').onclick = async () => {
      const mine = data.artifacts.filter(a => a.project === p.id).length;
      if (!await dialog('Delete this reference project?', `<p><b>${esc(p.name)}</b> and its settings are deleted${mine ? `, together with its ${mine} picture${mine > 1 ? 's' : ''}, approved ones included` : ''}. This cannot be undone.</p>`, [['Cancel', null], ['Delete', 'yes', true]])) return;
      try { flush(); if (mine) await call('POST', '/decide', { project: host.pid, ids: data.artifacts.filter(a => a.project === p.id).map(a => a.id), action: 'deny' });
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

  /* ---------- Sheet Generation (Simple mode) ---------- */
  function generation() {
    const p = P(), list = arts('sheet'), i = Math.max(0, list.findIndex(a => a.id === p.at)), cur = list.length ? (list.some(a => a.id === p.at) ? list[i] : list[list.length - 1]) : null, n = cur ? list.indexOf(cur) : -1;
    const dims = data.profiles.find(x => x.profile === p.profile).sizes[p.aspect], working = busy(p.id), failed = (data.jobs[p.id] || []).filter(j => j.status === 'error');
    const b = batch[p.id], doneNow = b ? Math.min(b.asked, list.length - b.had) : 0;
    const box = el(`<section class="panel rg-gen">
      <div class="rg-modes"><span class="ag-label">Mode</span><button class="small on" type="button" aria-pressed="true">Simple</button><button class="small" type="button" disabled title="Rows, individual views, locks and assembly. Not built yet.">Advanced <span class="pill">later</span></button>
        <span class="hint">Simple makes a complete sheet in one go from up to ${data.limits.sources} source pictures.</span></div>
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
    const p = P(), ex = p.extraction, sheets = arts('sheet'), views = arts('view');
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
    hide() { showing = false; clearTimeout(timer); },
    _state: () => data,
  };
})();
