/* SWIFT Identity Studio: the browser side of the module.
 *
 * Self-contained on purpose. It talks only to /api/identity/, draws only inside the element it is
 * given, and its classes all start with "ids-". The host page calls IdentityStudio.mount(element)
 * once and IdentityStudio.show() whenever the workspace is opened. Nothing here reads or changes
 * storyboard data.
 *
 * Phase 1 covers identity projects and their brief. Generation, references and exports come later,
 * and the page says so instead of showing controls that do nothing.
 */
(function () {
  'use strict';
  const API = '/api/identity/';
  let root = null, info = null, openId = null, saveTimer = null, pollTimer = null, conceptTick = null;

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const say = (msg) => { if (typeof window.toast === 'function') window.toast(msg); else console.warn(msg); };
  const when = (t) => t ? new Date(t * 1000).toLocaleString([], { dateStyle:'medium', timeStyle:'short' }) : '';

  async function call(method, route, body) {
    const opts = { method };
    if (body !== undefined) { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
    const r = await fetch(API + route, opts);
    let j = null;
    try { j = await r.json(); } catch (e) { throw new Error('Unexpected reply from the server (status ' + r.status + ').'); }
    if (!r.ok || j.error) throw new Error(j.error || 'Request failed: ' + r.status);
    return j;
  }

  /* ---------- the shared render queue, and this workspace's own jobs ---------- */
  const STATE_WORDS = { waiting:'waiting', submitted:'in the render queue', running:'running', done:'done', failed:'failed', stopped:'stopped', cancelled:'cancelled' };
  async function refreshQueue() {
    const line = root.querySelector('.ids-queue'); if (!line) return;
    let q, jobs = [];
    try { q = await call('GET', 'queue'); jobs = (await call('GET', 'jobs' + (openId ? '?project=' + encodeURIComponent(openId) : ''))).jobs; }
    catch (e) { line.textContent = 'The render queue could not be checked.'; return; }
    if (!line.isConnected) return;
    line.textContent = !q.comfy ? 'ComfyUI cannot be reached, so identity jobs will wait.'
      : q.other_jobs ? `The render queue is busy with ${q.other_jobs} other job${q.other_jobs === 1 ? '' : 's'}. Identity jobs wait until it is empty.`
      : 'The render queue is free.';
    if (q.identity_active) line.textContent += ` Identity jobs in play: ${q.identity_active}.` + (q.note ? ' ' + q.note : '');
    const box = root.querySelector('.ids-jobs'); if (!box) return;
    box.innerHTML = '';
    jobs.slice(-12).reverse().forEach(j => {
      const active = ['waiting', 'submitted', 'running'].includes(j.state), again = ['stopped', 'failed', 'cancelled'].includes(j.state);
      const row = el(`<div class="ids-job"><span class="pill">${esc(STATE_WORDS[j.state] || j.state)}</span><span class="ids-grow">${esc(j.label || j.kind)}${j.error ? `<div class="hint">${esc(j.error)}</div>` : ''}</span>${active ? '<button class="small ids-stop" type="button">Stop this job</button>' : ''}${again ? '<button class="small ids-retry" type="button">Retry</button>' : ''}</div>`);
      const act = (sel, route) => { const b = row.querySelector(sel); if (b) b.onclick = async () => { try { await call('POST', route, { id: j.id }); } catch (e) { say(e.message); } refreshQueue(); }; };
      act('.ids-stop', 'jobs/cancel'); act('.ids-retry', 'jobs/retry');
      box.appendChild(row);
    });
  }
  function poll() {                                           // only while the workspace is on screen
    clearInterval(pollTimer);
    pollTimer = setInterval(() => { if (root.classList.contains('on') && !document.hidden) { refreshQueue(); if (conceptTick) conceptTick(); } }, 3000);
    refreshQueue();
  }

  /* ---------- the list of identity projects ---------- */
  async function showList() {
    openId = null; conceptTick = null;
    root.innerHTML = '';
    const page = el(`<section class="ids-page">
      <div class="ids-head"><h2>Identity Studio</h2><span class="ids-grow"></span></div>
      <p class="ids-lede">A workspace for logos and app identities. Each identity project keeps its own brief, and later its references, concepts and exports, apart from your storyboard projects.</p>
      <form class="ids-new" autocomplete="off">
        <div><label for="idsNewName">New identity project</label><input id="idsNewName" maxlength="120" placeholder="Name, for example: Director app icon"></div>
        <button class="primary" type="submit">Create</button>
      </form>
      <div class="ids-list" aria-live="polite"><span class="hint">Loading…</span></div>
      <p class="hint ids-queue" aria-live="polite"></p>
      <div class="ids-note"><b>What works today.</b> Create, open, describe, duplicate and delete identity projects, and save the brief for each one. Inside a project you can add reference images, generate concepts, zoom into them and fix an area. Exporting icon sets and SVG files is not built yet, so there is no button for it here.</div>
    </section>`);
    root.appendChild(page); poll();
    page.querySelector('.ids-new').onsubmit = async (ev) => {
      ev.preventDefault();
      const input = page.querySelector('#idsNewName'), name = input.value.trim();
      if (!name) { input.focus(); return; }
      try { const p = await call('POST', 'projects', { name }); showProject(p.id); } catch (e) { say(e.message); }
    };
    let list = [];
    try { list = (await call('GET', 'projects')).projects; } catch (e) { say(e.message); }
    if (openId !== null || !page.isConnected) return;         // the person moved on while this loaded
    const wrap = page.querySelector('.ids-list');
    wrap.innerHTML = list.length ? '' : '<span class="hint">No identity projects yet. Name one above to start.</span>';
    list.forEach(p => wrap.appendChild(card(p)));
  }

  function card(p) {
    const d = el(`<article class="ids-card">
      <b>${esc(p.name)}</b>
      <div class="hint">${esc(p.app_name || 'No application name yet')}</div>
      <div class="hint">${esc(p.style || '')}</div>
      <div class="hint">${p.concepts} concepts · ${p.references} references</div>
      <div class="hint">Edited ${esc(when(p.updated))}</div>
      <div class="ids-acts"><button class="primary small ids-open" type="button">Open</button><button class="small ids-dup" type="button">Duplicate</button><button class="small ghost ids-del" type="button">Delete</button></div>
    </article>`);
    d.querySelector('.ids-open').onclick = () => showProject(p.id);
    d.querySelector('.ids-dup').onclick = async () => { try { await call('POST', 'projects/duplicate', { id: p.id }); showList(); } catch (e) { say(e.message); } };
    const del = d.querySelector('.ids-del');
    del.onclick = async () => {
      if (!del.dataset.sure) {                                // first press asks, second press does it
        del.dataset.sure = '1'; del.textContent = 'Really delete?'; del.classList.remove('ghost');
        setTimeout(() => { if (del.isConnected) { delete del.dataset.sure; del.textContent = 'Delete'; del.classList.add('ghost'); } }, 5000);
        return;
      }
      try { await call('POST', 'projects/delete', { id: p.id }); say('"' + p.name + '" was moved to the trash folder on the server.'); showList(); } catch (e) { say(e.message); }
    };
    return d;
  }

  /* ---------- one identity project: its name, description and brief ---------- */
  const options = (list, picked) => list.map(v => `<option value="${esc(v)}"${v === picked ? ' selected' : ''}>${esc(v)}</option>`).join('');

  async function showProject(id) {
    openId = id;
    root.innerHTML = '<section class="ids-page"><span class="hint">Loading…</span></section>';
    let p;
    try { if (!info) info = await call('GET', 'info'); p = await call('GET', 'project?id=' + encodeURIComponent(id)); }
    catch (e) { say(e.message); return showList(); }
    if (openId !== id) return;
    const s = p.settings;
    const page = el(`<section class="ids-page">
      <div class="ids-head"><button class="small ids-back" type="button">← All identity projects</button><span class="ids-grow"></span><span class="pill ids-state" aria-live="polite">saved</span></div>
      <div class="ids-grid">
        <div class="ids-wide"><label for="idsName">Project name</label><input id="idsName" data-top="name" maxlength="120" value="${esc(p.name)}"></div>
        <div class="ids-wide"><label for="idsDesc">Notes about this project</label><textarea id="idsDesc" data-top="description" maxlength="2000">${esc(p.description)}</textarea></div>
      </div>
      <h2>Brief</h2>
      <div class="ids-grid">
        <div><label for="idsApp">Application or company name</label><input id="idsApp" data-set="app_name" maxlength="120" value="${esc(s.app_name)}"></div>
        <div><label for="idsTag">Tagline</label><input id="idsTag" data-set="tagline" maxlength="200" value="${esc(s.tagline)}"></div>
        <div class="ids-wide"><label for="idsPurpose">What it does, or its industry</label><input id="idsPurpose" data-set="purpose" value="${esc(s.purpose)}"></div>
        <div class="ids-wide"><label for="idsLogo">What the logo should show</label><textarea id="idsLogo" data-set="description">${esc(s.description)}</textarea></div>
        <div><label for="idsStyle">Style</label><select id="idsStyle" data-set="style">${options(info.styles, s.style)}</select></div>
        <div><label for="idsLayout">Layout</label><select id="idsLayout" data-set="layout">${options(info.layouts, s.layout)}</select></div>
        <div><label for="idsBack">Background</label><select id="idsBack" data-set="background">${options(info.backgrounds, s.background)}</select></div>
        <div><label for="idsCount">Concepts per round</label><input id="idsCount" data-set="concept_count" type="number" min="1" max="8" value="${esc(s.concept_count)}"></div>
        <div class="ids-wide"><label for="idsNotes">Style notes</label><textarea id="idsNotes" data-set="style_notes">${esc(s.style_notes)}</textarea></div>
        <div class="ids-wide"><label for="idsPalette">Colours, as hex codes separated by spaces (up to 8)</label><input id="idsPalette" data-set="palette" placeholder="#22c55e #000000" value="${esc((s.palette || []).join(' '))}"><div class="ids-swatches"></div></div>
        <fieldset class="ids-wide ids-plats"><legend>Where it will be used</legend>${info.platforms.map(v => `<label><input type="checkbox" data-plat="${esc(v)}"${(s.platforms || []).includes(v) ? ' checked' : ''}> ${esc(v)}</label>`).join('')}</fieldset>
      </div>
      <h2>Reference images</h2>
      <p class="ids-lede">Add what you already have: a mark that must be kept exactly, such as an icon or a letterform, or pictures that show the style you want. PNG, JPEG, WebP or SVG.</p>
      <div class="ids-refs" aria-live="polite"></div>
      <div class="ids-drop"><label class="btn">Add reference images<input class="ids-file" type="file" accept=".png,.jpg,.jpeg,.webp,.svg,image/png,image/jpeg,image/webp,image/svg+xml" multiple hidden></label><span class="hint">or drop files here. Switch a reference to Enabled to have it used when generating; up to ${info.max_references} are used at once.</span></div>
      <h2>Concepts</h2>
      <div class="ids-gen">
        <div class="ids-grow"><label for="idsDirection">Direction for this round (optional)</label><input id="idsDirection" maxlength="500" placeholder="For example: rounder shapes, the mark inside a hexagon"></div>
        <button class="primary ids-go" type="button">Generate concepts</button>
      </div>
      <div class="hint ids-gen-notes" aria-live="polite"></div>
      <div class="ids-concepts" aria-live="polite"></div>
      <p class="hint">Concept art for internal use. It is drawn with FLUX.2 [dev], which is licensed for non-commercial use; final artwork for a product that is sold should come from an artist.</p>
      <p class="hint ids-queue" aria-live="polite"></p>
      <div class="ids-jobs"></div>
      <div class="ids-note">The brief is saved as you type. Generate concepts reads the brief and the enabled reference images. Concepts wait their turn behind any video renders.</div>
    </section>`);
    root.innerHTML = ''; root.appendChild(page); poll();
    const state = page.querySelector('.ids-state');
    const swatches = () => {
      const box = page.querySelector('.ids-swatches'); box.innerHTML = '';
      (page.querySelector('#idsPalette').value.match(/#[0-9a-fA-F]{6}\b/g) || []).slice(0, 8).forEach(c => { const i = document.createElement('i'); i.style.background = c; i.title = c; box.appendChild(i); });
    };
    const collect = () => {
      const body = { settings: {} };
      page.querySelectorAll('[data-top]').forEach(f => body[f.dataset.top] = f.value);
      page.querySelectorAll('[data-set]').forEach(f => body.settings[f.dataset.set] = f.value);
      body.settings.palette = (page.querySelector('#idsPalette').value.match(/#[0-9a-fA-F]{6}\b/g) || []).slice(0, 8);
      body.settings.concept_count = parseInt(page.querySelector('#idsCount').value, 10) || 4;
      body.settings.platforms = [...page.querySelectorAll('[data-plat]:checked')].map(c => c.dataset.plat);
      return body;
    };
    const save = async () => {
      clearTimeout(saveTimer); saveTimer = null;
      if (!collect().name.trim()) { state.textContent = 'a name is needed'; return; }
      try { await call('PUT', 'project?id=' + encodeURIComponent(id), collect()); if (state.isConnected) state.textContent = 'saved'; }
      catch (e) { if (state.isConnected) state.textContent = 'not saved'; say(e.message); }
    };
    const changed = () => { state.textContent = 'saving…'; swatches(); clearTimeout(saveTimer); saveTimer = setTimeout(save, 600); };
    const briefOnly = (ev) => { if (!ev.target.closest('.ids-refs, .ids-drop, .ids-gen')) changed(); };
    page.addEventListener('input', briefOnly); page.addEventListener('change', briefOnly);
    references(page, id, p.references);
    concepts(page, id, p, async () => { if (saveTimer) await save(); });
    page.querySelector('.ids-back').onclick = async () => { if (saveTimer) await save(); showList(); };
    swatches();
  }

  /* ---------- reference images: shown only inside <img>, where a browser runs no script ---------- */
  function references(page, pid, list) {
    const box = page.querySelector('.ids-refs'), drop = page.querySelector('.ids-drop'), input = page.querySelector('.ids-file');
    const q = 'project=' + encodeURIComponent(pid);
    const draw = () => {
      box.innerHTML = list.length ? '' : '<span class="hint">No reference images yet.</span>';
      list.forEach(r => {
        const card = el(`<article class="ids-ref">
          <div class="ids-thumb"><img alt="" src="${API}reference?${q}&id=${esc(r.id)}"></div>
          <b title="${esc(r.name)}">${esc(r.name)}</b>
          <div class="hint">${esc(r.kind.toUpperCase())} · ${Math.max(1, Math.round(r.bytes / 1024))} KB${r.kind === 'svg' ? ' · vector' : ''}</div>
          ${r.cleaned ? `<div class="hint">${r.cleaned} unsafe or unsupported part${r.cleaned === 1 ? ' was' : 's were'} removed. Check it still looks right.</div>` : ''}
          <button class="ids-switch${r.enabled === false ? '' : ' on'}" type="button" role="switch" aria-checked="${r.enabled !== false}" aria-label="Use ${esc(r.name)} when generating"><span>${r.enabled === false ? 'Disabled' : 'Enabled'}</span></button>
          <label>How to use it<select class="ids-use">${options(info.reference_uses, r.use)}</select></label>
          <label>Note<input class="ids-rnote" maxlength="500" placeholder="For example: the dot of the i is a water drop" value="${esc(r.note)}"></label>
          <div class="ids-acts"><button class="small ghost ids-rdel" type="button">Remove</button></div>
        </article>`);
        const put = async (body) => { try { Object.assign(r, await call('PUT', `reference?${q}&id=${r.id}`, body)); } catch (e) { say(e.message); } };
        const sw = card.querySelector('.ids-switch');
        sw.onclick = async () => { await put({ enabled: r.enabled === false }); const on = r.enabled !== false; sw.classList.toggle('on', on); sw.setAttribute('aria-checked', on); sw.firstElementChild.textContent = on ? 'Enabled' : 'Disabled'; };
        if (!r.flat) flatten(r, card.querySelector('.ids-thumb img'));
        card.querySelector('.ids-use').onchange = (ev) => put({ use: ev.target.value });
        card.querySelector('.ids-rnote').onchange = (ev) => put({ note: ev.target.value });
        card.querySelector('.ids-rdel').onclick = async () => {
          try { await call('POST', 'references/remove', { project: pid, id: r.id }); list.splice(list.indexOf(r), 1); draw(); } catch (e) { say(e.message); }
        };
        box.appendChild(card);
      });
    };
    /* The image model cannot read SVG or transparency, so the page draws each reference onto white and sends that PNG too. */
    const flatten = (r, img) => {
      const make = async () => {
        try {
          let w = img.naturalWidth || 1024, h = img.naturalHeight || 1024; const k = (r.kind === 'svg' ? 1024 : Math.min(1024, Math.max(w, h))) / Math.max(w, h);
          w = Math.max(1, Math.round(w * k)); h = Math.max(1, Math.round(h * k));
          const c = document.createElement('canvas'); c.width = w; c.height = h;
          const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, w, h); x.drawImage(img, 0, 0, w, h);
          const blob = await new Promise(res => c.toBlob(res, 'image/png'));
          const reply = await fetch(`${API}reference/flat?${q}&id=${r.id}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: blob });
          if (reply.ok) r.flat = true;
        } catch (e) { console.warn('Could not prepare ' + r.name + ' for generation', e); }
      };
      if (img.complete && img.naturalWidth) make(); else img.addEventListener('load', make, { once: true });
    };
    const add = async (files) => {
      for (const file of files) {
        try {
          const r = await fetch(`${API}references?${q}&name=${encodeURIComponent(file.name)}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file });
          let j = null; try { j = await r.json(); } catch (e) { throw new Error(r.status === 413 ? 'That file is too large for the server to accept.' : 'Unexpected reply from the server (status ' + r.status + ').'); }
          if (!r.ok || j.error) throw new Error(j.error || 'Request failed: ' + r.status);
          list.push(j); draw();
        } catch (e) { say(file.name + ': ' + e.message); }
      }
    };
    input.onchange = () => { add([...input.files]); input.value = ''; };
    drop.ondragover = (ev) => { ev.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = (ev) => { ev.preventDefault(); drop.classList.remove('over'); add([...ev.dataTransfer.files]); };
    draw();
  }

  /* ---------- concepts: generate, look closely, fix an area ---------- */
  const CONCEPT_WORDS = { waiting:'Waiting for the render queue', failed:'Failed', stopped:'Stopped', cancelled:'Cancelled' };
  function concepts(page, pid, project, flush) {
    const box = page.querySelector('.ids-concepts'), go = page.querySelector('.ids-go'), notes = page.querySelector('.ids-gen-notes');
    const q = 'project=' + encodeURIComponent(pid);
    let list = project.concepts || [];
    if (!info.ready.generation) { go.disabled = true; notes.textContent = 'Concept generation is not connected on this server.'; }
    const src = c => `${API}concept?${q}&id=${c.id}`;
    const fixer = c => !info.ready.fix ? null : async ({ mask, prompt }) => {
      const r = await fetch(`${API}concepts/fix?${q}&id=${c.id}&prompt=${encodeURIComponent(prompt)}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: mask });
      const j = await r.json().catch(() => ({ error: 'Unexpected reply from the server (status ' + r.status + ').' }));
      if (!r.ok || j.error) throw new Error(j.error || 'Request failed: ' + r.status);
      await reload();
    };
    const look = c => { const name = (project.settings.app_name || project.name) + (c.kind === 'fix' ? ' · fixed' : ' · concept'); if (typeof window.openViewer === 'function') window.openViewer(src(c), name, fixer(c)); else window.open(src(c), '_blank', 'noopener'); };
    const draw = () => {
      box.innerHTML = list.length ? '' : '<span class="hint">No concepts yet. Fill in the brief, enable the references you want followed, then press Generate concepts.</span>';
      [...list].reverse().forEach(c => {
        const done = c.state === 'done';
        const card = el(`<article class="ids-concept">
          <div class="ids-thumb ids-cthumb${done ? '' : ' ids-wait'}">${done ? `<img alt="Concept" loading="lazy" src="${src(c)}">` : `<span>${esc(CONCEPT_WORDS[c.state] || c.state)}</span>`}</div>
          <div class="hint">${c.kind === 'fix' ? 'Fix: ' + esc(c.direction) : c.direction ? esc(c.direction) : 'From the brief'}${c.references && c.references.length ? ` · ${c.references.length} reference${c.references.length === 1 ? '' : 's'}` : ''}</div>
          ${c.error ? `<div class="hint">${esc(c.error)}</div>` : ''}
          <div class="ids-acts">${done ? '<button class="small primary ids-look" type="button">Look closer</button>' : ''}${done && info.ready.fix ? '<button class="small ids-fix" type="button">Fix an area</button>' : ''}<button class="small ghost ids-cdel" type="button">Remove</button></div>
        </article>`);
        if (done) {
          card.querySelector('.ids-cthumb').onclick = () => look(c); card.querySelector('.ids-look').onclick = () => look(c);
          const f = card.querySelector('.ids-fix'); if (f) f.onclick = () => { look(c); const b = document.getElementById('vFix'); if (b) setTimeout(() => { if (!document.getElementById('viewer').classList.contains('fixing')) b.click(); }, 350); };
        }
        card.querySelector('.ids-cdel').onclick = async () => { try { await call('POST', 'concepts/remove', { project: pid, id: c.id }); await reload(); } catch (e) { say(e.message); } };
        box.appendChild(card);
      });
    };
    const key = l => l.map(c => c.id + c.state).join();
    const reload = async () => { try { const fresh = (await call('GET', 'project?id=' + encodeURIComponent(pid))).concepts; if (key(fresh) !== key(list)) { list = fresh; draw(); } } catch (e) { /* the next tick tries again */ } };
    conceptTick = () => { if (box.isConnected && list.some(c => c.state === 'waiting')) reload(); };
    go.onclick = async () => {
      go.disabled = true; notes.textContent = 'Queuing…';
      try {
        await flush();
        const out = await call('POST', 'concepts/generate', { project: pid, direction: page.querySelector('#idsDirection').value });
        notes.textContent = `Queued ${out.queued} concept${out.queued === 1 ? '' : 's'}. ` + out.notes.join(' ');
        await reload(); refreshQueue();
      } catch (e) { notes.textContent = e.message; }
      go.disabled = false;
    };
    draw();
  }

  /* ---------- System status: what this workspace runs that the storyboard does not ---------- */
  async function showModels(box) {
    if (!box) return;
    let data;
    try { data = await call('GET', 'models'); } catch (e) { box.innerHTML = '<h2>Identity Studio models</h2><div class="hint">' + esc(e.message) + '</div>'; return; }
    box.classList.add('ids');
    box.innerHTML = `<h2>Identity Studio models</h2><div class="hint">Only what Identity Studio adds. ${esc(data.shared)}</div>` +
      data.tools.map(t => `<div class="ids-tool">
        <div class="ids-mark ${t.installed ? 'ok' : ''}" title="${t.installed ? 'Installed' : 'Not installed yet'}">${t.installed ? '✓' : '–'}</div>
        <div><b>${esc(t.name)}</b> <span class="hint">${esc(t.kind)}</span>
          <div class="ids-use-text"><i>${esc(t.use)}</i></div>
          <div class="hint">${esc(t.note)}</div>
          <div class="${t.installed ? 'ids-good' : 'hint'}">${t.installed ? 'Installed' + (t.version ? ' · version ' + esc(t.version) : '') : 'Not installed yet. It is needed for ' + esc(t.needed_for) + ', and will be added to the server when that step is built.'}</div>
        </div></div>`).join('');
  }

  window.IdentityStudio = {
    showModels,
    mount(element) { root = element; root.classList.add('ids'); },
    show() { if (root) { if (openId) showProject(openId); else showList(); } },
  };
})();
