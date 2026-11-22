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
  let root = null, info = null, openId = null, saveTimer = null;

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

  /* ---------- the list of identity projects ---------- */
  async function showList() {
    openId = null;
    root.innerHTML = '';
    const page = el(`<section class="ids-page">
      <div class="ids-head"><h2>Identity Studio</h2><span class="ids-grow"></span></div>
      <p class="ids-lede">A workspace for logos and app identities. Each identity project keeps its own brief, and later its references, concepts and exports, apart from your storyboard projects.</p>
      <form class="ids-new" autocomplete="off">
        <div><label for="idsNewName">New identity project</label><input id="idsNewName" maxlength="120" placeholder="Name, for example: Director app icon"></div>
        <button class="primary" type="submit">Create</button>
      </form>
      <div class="ids-list" aria-live="polite"><span class="hint">Loading…</span></div>
      <div class="ids-note"><b>What works today.</b> Create, open, describe, duplicate and delete identity projects, and save the brief for each one. Generating concepts, adding reference images and exporting icon sets are not built yet, so there are no buttons for them here.</div>
    </section>`);
    root.appendChild(page);
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
      <div class="ids-note">The brief is saved as you type. It is what later phases will read when they generate concepts; nothing is generated yet.</div>
    </section>`);
    root.innerHTML = ''; root.appendChild(page);
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
    page.addEventListener('input', changed); page.addEventListener('change', changed);
    page.querySelector('.ids-back').onclick = async () => { if (saveTimer) await save(); showList(); };
    swatches();
  }

  window.IdentityStudio = {
    mount(element) { root = element; root.classList.add('ids'); },
    show() { if (root) { if (openId) showProject(openId); else showList(); } },
  };
})();
