/* SWIFT Director: Asset Generator.
 *
 * A tab for making pictures outside the storyboard. Two modes work today:
 *   Image Generation   one prompt, up to four reference pictures
 *   Depth Generation   background, middle ground and foreground made separately, then redrawn as one picture
 * Character Generation and 3D Generation have their Asset Configuration box; their generators arrive later.
 *
 * Every mode starts with an Asset Configuration box: what the asset is (name, rating, type), which models are used, and
 * workflow and approval controls. Each setting is tagged "In use" or "Stored", the same as the Project Configuration Center.
 *
 * The page hands this file what it needs: show(element, { pid, upload, view, toast, openViewer, saveAsset }).
 * Everything typed here is saved on the server with the project; the pictures are ordinary generated stills.
 */
window.AssetGenerator = (function () {
  'use strict';
  const LAYERS = ['background', 'middle', 'foreground'];
  const TITLE = { image: 'Image', background: 'Background', middle: 'Middle Ground', foreground: 'Foreground', composed: 'Composed Output' };
  const HINT = {
    image: 'Describe the picture. Reference pictures, if you add any, are numbered in the order shown: "the character in image 1", "the ship in image 2".',
    background: 'Describe the place with nobody and nothing in front of it: the room, the set, the landscape.',
    middle: 'Describe the main subject. Ask for a plain, empty background so only the subject carries over.',
    foreground: 'Describe what sits closest to the camera. Ask for a plain, empty background so only these things carry over.',
  };
  let root = null, host = null, data = null, mode = 'image', timer = null, saveTimer = null, showing = false;
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const el = html => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  async function call(method, path, body) {
    const r = await fetch('/api/generator' + path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
    const out = await r.json().catch(() => ({})); if (!r.ok) throw new Error(out.error || 'The server could not do that.'); return out;
  }
  const S = () => data.state, B = name => data.boxes[name];
  const busy = name => B(name).jobs.filter(j => j.status === 'queued' || j.status === 'running').length;
  const anyBusy = () => Object.keys(data.boxes).some(busy);

  /* ---------- talking to the server ---------- */
  async function load() {
    if (!host.pid) { root.innerHTML = '<div class="panel hint">Open a project first.</div>'; return; }
    try { take(await call('GET', '?project=' + encodeURIComponent(host.pid))); } catch (e) { root.innerHTML = '<div class="panel hint">' + esc(e.message) + '</div>'; }
  }
  /* New results from the server replace what is shown, but never what the person is typing. */
  function take(fresh) {
    const before = data ? JSON.stringify(data.boxes) : '', first = !data;
    if (data) { ['image', ...LAYERS, 'composed'].forEach(n => { const mine = S()[n]; fresh.state[n].prompt = mine.prompt; fresh.state[n].count = mine.count; fresh.state[n].refs = mine.refs; fresh.state[n].at = mine.at; });
      fresh.state.config = S().config; fresh.state.approved = S().approved.filter(id => fresh.state.approved.includes(id) || Object.values(fresh.boxes).some(b => b.results.some(r => r.id === id))); }
    data = fresh;
    if (first || before !== JSON.stringify(data.boxes) || !root.querySelector('.ag')) draw(); else status();
    clearTimeout(timer); if (showing && anyBusy()) timer = setTimeout(load, 2500);
  }
  function keep() { clearTimeout(saveTimer); saveTimer = setTimeout(() => call('POST', '/save', { project: host.pid, state: S() }).catch(e => host.toast(e.message)), 700); }

  /* ---------- drawing ---------- */
  function draw() {
    const focus = document.activeElement && root.contains(document.activeElement) ? document.activeElement.dataset.k : null;
    root.innerHTML = '';
    const page = el(`<div class="ag"><div class="panel ag-modes" role="tablist" aria-label="Asset Generator mode">
      <button data-m="image" role="tab">Image Generation</button><button data-m="character" role="tab">Character Generation <span class="pill">later</span></button>
      <button data-m="depth" role="tab">Depth Generation</button><button data-m="3d" role="tab">3D Generation <span class="pill">later</span></button></div><div class="ag-body"></div></div>`);
    page.querySelectorAll('.ag-modes button').forEach(b => { b.classList.toggle('on', b.dataset.m === mode); b.setAttribute('aria-selected', b.dataset.m === mode); b.onclick = () => { mode = b.dataset.m; draw(); }; });
    const body = page.querySelector('.ag-body');
    body.append(configBox());
    if (mode === 'character' || mode === '3d') {
      body.append(el(`<div class="panel hint">${mode === '3d' ? '3D Generation' : 'Character Generation'} is not built yet. The configuration above is saved with the project and will be used when it is.</div>`));
    } else if (mode === 'image') {
      body.append(el('<p class="hint ag-lead">One picture from a prompt and up to four reference pictures. Made with FLUX.2, the same image model the storyboard uses.</p>'), box('image'));
    } else {
      body.append(el('<p class="hint ag-lead">Make the three layers separately, choose one of each with <b>Apply to Composed Output</b>, then run the composed output: the image model redraws the three as one picture. It is a redraw, not a cut-and-paste, so small details can change.</p>'));
      const row = el('<div class="ag-row"></div>'); LAYERS.forEach(l => row.append(box(l))); body.append(row, box('composed'));
    }
    root.append(page);
    if (focus) { const again = root.querySelector(`[data-k="${focus}"]`); if (again) again.focus(); }
  }

  /* ---------- Asset Configuration: the box at the top of every mode ---------- */
  const cfg = () => S().config[mode];
  const NAME = { image: 'Image Generation', character: 'Character Generation', depth: 'Depth Generation', '3d': '3D Generation' };
  /* Built with the same markup and styles (.cc) as the Project Configuration box in Assisted Storyboard, so the two read alike:
   * a header, then sections that open and close, each with a one-line summary, and an "In use" or "Stored" tag on every setting. */
  const opened = () => { try { return JSON.parse(localStorage.getItem('sd.asset-config.open') || '[]'); } catch (e) { return []; } };
  const remember = list => { try { localStorage.setItem('sd.asset-config.open', JSON.stringify(list)); } catch (e) { /* private mode */ } };
  function configBox() {
    const c = cfg(), o = data.options, open = opened(), label = (list, key) => (list.find(x => x.key === key) || {}).label || key;
    const tag = k => o.used.includes(k) ? '<span class="cc-tag cc-used" title="This setting changes what the Asset Generator does today">In use</span>'
                                        : '<span class="cc-tag" title="Saved with the project. A later update will act on it">Stored</span>';
    const select = (key, list, text) => `<label class="cc-field"><span>${esc(text)} ${tag(key)}</span><select data-k="cfg-${key}" data-path="${key}">${list.map(x => `<option value="${esc(x.key)}"${x.key === c[key] ? ' selected' : ''}>${esc(x.label)}</option>`).join('')}</select></label>`;
    const role = r => { const u = o.in_use[r.key] || {}; return `<div class="cc-role"><b>${esc(r.label)}</b><span>${u.name ? esc(u.name) + (u.runtime ? ` <span class="hint">· ${esc(u.runtime)}</span>` : '') : '<span class="hint">Not available</span>'}</span><span class="cc-tag${u.ready ? ' cc-used' : ''}">${u.ready ? 'Auto' : u.name ? 'Not confirmed' : 'Not installed'}</span>${u.note ? `<div class="hint">${esc(u.note)}</div>` : ''}</div>`; };
    const check = w => `<label class="cc-check"><input type="checkbox" data-k="cfg-w-${w.key}" data-flow="${w.key}"${c.workflow[w.key] ? ' checked' : ''}> <span>${esc(w.label)}</span> ${tag('workflow.' + w.key)}</label>`;
    const sections = [
      { key: 'identity', title: 'Project Identity', summary: `${c.name || 'No name yet'} · ${c.rating} · ${label(o.types, c.type)}`, body:
        `<div class="cc-grid"><label class="cc-field"><span>Asset Name ${tag('name')}</span><input data-k="cfg-name" data-path="name" type="text" maxlength="80" value="${esc(c.name)}" placeholder="For example: Misty's ship"></label>
           ${select('rating', o.ratings.map(r => ({ key: r, label: r })), 'Asset Rating')}${select('type', o.types, 'Asset Type')}</div>
         <div class="hint">The name and type decide what Save to Assets creates. The rating is SWIFT Director's own classification, saved so filtering rules can be applied against it later; it does not change what is generated yet.</div>` },
      { key: 'models', title: 'AI Model Configuration', summary: 'Auto for every role', body:
        `<div class="hint">What performs each job today. Every role is on Auto, which means the one model SWIFT Director has a working setup for. The Asset Generator sends your prompt as typed, so the Prompting Model is not called here yet. Choosing between models arrives with the model registry.</div>
         <div class="cc-roles">${o.roles.map(role).join('')}</div>` },
      { key: 'workflow', title: 'Workflow and Approval Controls', summary: `${o.workflow.filter(w => c.workflow[w.key]).length} of ${o.workflow.length} on`, body:
        `<div class="hint">These record how you want to work in this generator. The two marked In use act now; the others start to act as their steps are built.</div>
         <div class="cc-checks">${o.workflow.map(check).join('')}</div>` },
    ];
    const box = el(`<div class="cc ag-config"><div class="cc-head"><h2>Asset Configuration</h2><span class="hint">${esc(NAME[mode])}. Saved with this project.</span></div>` +
      sections.map(x => `<details class="cc-section" data-key="${x.key}"${open.includes(x.key) ? ' open' : ''}><summary><b>${esc(x.title)}</b><span class="hint">${esc(x.summary)}</span></summary><div class="cc-body">${x.body}</div></details>`).join('') + '</div>');
    box.querySelectorAll('details').forEach(d => d.addEventListener('toggle', () => remember([...box.querySelectorAll('details[open]')].map(x => x.dataset.key))));
    box.querySelectorAll('[data-path]').forEach(f => {
      if (f.tagName === 'INPUT') { f.oninput = () => { c.name = f.value.slice(0, 80); keep(); }; f.onchange = () => draw(); }
      else f.onchange = () => { c[f.dataset.path] = f.value; keep(); draw(); };
    });
    box.querySelectorAll('[data-flow]').forEach(i => i.onchange = () => { c.workflow[i.dataset.flow] = i.checked; keep(); draw(); });
    return box;
  }
  const approved = id => S().approved.includes(id);
  const fileStem = name => ((cfg().name || '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'asset') + '-' + TITLE[name].toLowerCase().replace(/ /g, '-');

  function at(name) {                      // which finished picture a box is showing: the remembered one, else the newest
    const list = B(name).results; if (!list.length) return -1;
    const i = list.findIndex(r => r.id === S()[name].at); return i < 0 ? list.length - 1 : i;
  }

  function box(name) {
    const st = S()[name], composed = name === 'composed', list = B(name).results, i = at(name), cur = i >= 0 ? list[i] : null;
    const applied = !composed && name !== 'image' && cur && S().composed.applied[name] === cur.image;
    const needOk = cfg().workflow.approve_before_save, ok = !!cur && approved(cur.id), typeWord = ((data.options.types.find(t => t.key === cfg().type) || {}).label || 'asset').toLowerCase();
    const card = el(`<section class="panel ag-box${composed ? ' ag-composed' : ''}" data-box="${name}">
      <h2>${TITLE[name]}</h2>
      <div class="ag-stage"><button class="ag-arrow ag-prev" type="button" aria-label="Previous picture" title="Previous picture">‹</button>
        <div class="ag-pic">${cur ? `<img alt="${TITLE[name]} picture ${i + 1}" src="${esc(host.view(cur.image))}">` : '<div class="ag-empty">No picture yet</div>'}${applied ? '<span class="pill ag-applied">Applied</span>' : ''}</div>
        <button class="ag-arrow ag-next" type="button" aria-label="Next picture" title="Next picture">›</button></div>
      <div class="ag-under"><span class="hint ag-count">${list.length ? (i + 1) + ' of ' + list.length : ''}</span><span class="ag-status hint"></span><span class="ag-grow"></span>
        ${cur ? `<a class="btn small" href="${esc(host.view(cur.image))}" download="${esc(fileStem(name) + '-' + (i + 1) + '.png')}">Download</a>${needOk ? `<button class="small ag-ok${ok ? ' on' : ''}" type="button" aria-pressed="${ok}" title="${ok ? 'Approved. Click to take the approval back.' : 'Approve this picture so it can be saved to Assets.'}">${ok ? '✓ Approved' : 'Approve'}</button>` : ''}<button class="small ag-asset" type="button"${needOk && !ok ? ' disabled' : ''} title="${needOk && !ok ? 'Approve this picture first. This is set in Asset Configuration.' : 'Add this picture to Assets as ' + esc(typeWord) + (cfg().name ? ' named ' + esc(cfg().name) : '')}">Save to Assets</button><button class="small ghost ag-del" type="button" title="Remove this picture from the list">Remove</button>` : ''}</div>
      ${composed ? '<div class="ag-layers"></div>' : ''}
      <label class="ag-label">Prompt<span class="ag-promptwrap"><textarea data-k="p-${name}" class="ag-prompt" rows="${composed ? 4 : 5}" placeholder="${esc(HINT[name] || '')}">${esc(st.prompt)}</textarea><span class="ag-chars" aria-live="off"></span></span></label>
      ${composed ? '<p class="hint">Images 1, 2 and 3 are always the background, middle ground and foreground above, in that order. If you add a fourth reference, say what it is, for example: “Use image 4 as the colour and lighting style.” <button class="small ghost ag-reset" type="button">Reset prompt</button></p>' : ''}
      <div class="ag-refs"></div>
      <div class="ag-run"><label>Generations<input data-k="n-${name}" class="ag-n" type="number" min="1" max="${data.limits.count}" step="1" value="${st.count}"></label>
        <button data-k="r-${name}" class="primary ag-go" type="button">Run generations</button>
        ${!composed && name !== 'image' ? `<button data-k="a-${name}" class="ag-apply" type="button"${cur ? '' : ' disabled'}>${applied ? 'Applied to Composed Output' : 'Apply to Composed Output'}</button>` : ''}</div>
    </section>`);
    const q = s => card.querySelector(s);
    const step = d => { const n = list.length; if (!n) return; st.at = list[(i + d + n) % n].id; keep(); draw(); };
    q('.ag-prev').onclick = () => step(-1); q('.ag-next').onclick = () => step(1);
    q('.ag-prev').disabled = q('.ag-next').disabled = list.length < 2;
    if (cur) {
      q('.ag-pic img').onclick = () => host.openViewer(host.view(cur.image), TITLE[name]);
      q('.ag-asset').onclick = () => host.saveAsset(cur.image, { type: cfg().type, name: cfg().name, rating: cfg().rating });
      if (needOk) q('.ag-ok').onclick = () => { const a = S().approved, n = a.indexOf(cur.id); if (n < 0) a.push(cur.id); else a.splice(n, 1); keep(); draw(); };
      q('.ag-del').onclick = async () => { if (!confirm('Remove this picture from the list?')) return; try { st.at = null; take(await call('POST', '/remove', { project: host.pid, id: cur.id })); draw(); } catch (e) { host.toast(e.message); } };
    }
    q('.ag-prompt').oninput = ev => { st.prompt = ev.target.value; keep(); counter(card, name); };
    q('.ag-n').onchange = ev => { st.count = Math.max(1, Math.min(data.limits.count, Math.round(+ev.target.value || 1))); ev.target.value = st.count; keep(); };
    if (composed) {
      q('.ag-reset').onclick = () => { st.prompt = data.compose_prompt; keep(); draw(); };
      const layers = q('.ag-layers');
      LAYERS.forEach((l, n) => { const img = st.applied[l];
        layers.append(el(`<div class="ag-layer"><div class="ag-thumb">${img ? `<img alt="" src="${esc(host.view(img))}">` : '<span class="hint">not applied</span>'}</div><span class="hint">Image ${n + 1}: ${TITLE[l]}</span></div>`)); });
    }
    refs(q('.ag-refs'), name);
    q('.ag-go').onclick = async ev => {
      const b = ev.currentTarget;
      if (cfg().workflow.confirm_before_run && !confirm(`Run ${st.count} generation${st.count > 1 ? 's' : ''} for ${TITLE[name]}?`)) return;
      b.disabled = true; clearTimeout(saveTimer);
      try {
        const kept = st.refs.find(r => r.use === 'insert'), placed = kept ? await place(kept.image) : null;
        if (placed && placed.soft) host.toast('The inserted picture is small, so it was enlarged and will look soft. Use a larger one for a sharp result.');
        st.at = null; take(await call('POST', '/run', { project: host.pid, box: name, state: S(), placed })); draw();
      } catch (e) { host.toast(e.message); }
      b.disabled = false;
    };
    const ap = q('.ag-apply');
    if (ap) ap.onclick = async () => { clearTimeout(saveTimer); try { await call('POST', '/save', { project: host.pid, state: S() }); take(await call('POST', '/apply', { project: host.pid, layer: name, image: cur.image })); draw(); } catch (e) { host.toast(e.message); } };
    paint(card, name); counter(card, name);
    return card;
  }

  /* The reference slots of a box: four, or for the composed output the one free slot that becomes image 4.
   * Each picture has a "How to use it" choice, the same four as Identity Studio. A picture set to "Insert as it is"
   * is kept pixel for pixel; the others are numbered in the order the image model sees them. */
  const useOf = id => data.uses.find(u => u.id === id) || data.uses[1];
  function numbers(name) {                 // image number per reference, null for the inserted one
    const st = S()[name], base = name === 'composed' ? 3 : 0, kept = st.refs.some(r => r.use === 'insert'); let n = base;
    return st.refs.map(r => r.use === 'insert' ? null : (kept && n - base >= 3 ? 0 : ++n));      // 0: beyond what fits beside a kept picture
  }
  function added(name) {                   // the sentences the reference pictures add after the typed prompt
    const st = S()[name], nums = numbers(name);
    return [...(st.refs.some(r => r.use === 'insert') ? [useOf('insert').adds] : []), ...st.refs.map((r, n) => nums[n] ? useOf(r.use).adds.replace('{n}', nums[n]) : null).filter(Boolean)];
  }
  /* The count at the bottom right of a prompt box: characters that will be sent / about how many the image model reads.
   * It counts what is actually sent, so the sentences added for reference pictures are included. */
  function counter(card, name) {
    const out = card.querySelector('.ag-chars'), lim = data.prompt_limit, typed = S()[name].prompt.trim().length, extra = added(name).reduce((n, t) => n + t.length + 1, 0), x = typed + extra;
    out.textContent = x.toLocaleString() + ' / ' + lim.characters.toLocaleString();
    out.className = 'ag-chars' + (x > lim.characters ? ' ag-over' : x > lim.characters * 0.85 ? ' ag-near' : '');
    out.title = `${typed.toLocaleString()} typed${extra ? ' + ' + extra.toLocaleString() + ' added for the reference pictures' : ''}. ${lim.model} reads about ${lim.tokens} word pieces, which is roughly ${lim.characters.toLocaleString()} characters of English. `
      + (x > lim.characters ? 'This prompt is past that: the end of it may be ignored or weaken the rest. Put what matters most first, or shorten it.' : 'The limit is an estimate, since the model counts word pieces, not characters.');
  }
  function refs(holder, name) {
    const st = S()[name], composed = name === 'composed', max = composed ? 1 : data.limits.refs, nums = numbers(name);
    holder.append(el(`<span class="hint">${composed ? 'Image 4 (optional)' : 'Reference pictures (up to ' + max + ')'}</span>`));
    st.refs.forEach((r, n) => {
      const num = nums[n], uses = data.uses.filter(u => !composed || u.id !== 'insert');
      const slot = el(`<div class="ag-refcard"><div class="ag-ref"><img alt="Reference" src="${esc(host.view(r.image))}"><button class="ag-x" type="button" title="Take this reference out" aria-label="Remove reference">×</button><span class="ag-num">${num === null ? 'kept' : num === 0 ? 'not used' : num}</span></div>
        <label>How to use it<select data-k="u-${name}-${n}" class="ag-use">${uses.map(u => `<option value="${u.id}"${u.id === r.use ? ' selected' : ''}>${esc(u.name)}</option>`).join('')}</select></label>
        <div class="hint ag-usehelp">${esc(useOf(r.use).help)}</div></div>`);
      slot.querySelector('.ag-x').onclick = () => { st.refs.splice(n, 1); keep(); draw(); };
      slot.querySelector('img').onclick = () => host.openViewer(host.view(r.image), 'Reference');
      slot.querySelector('.ag-use').onchange = ev => {
        if (ev.target.value === 'insert') st.refs.forEach(o => { if (o !== r && o.use === 'insert') { o.use = 'keep exactly'; host.toast('Only one picture in a box can be inserted as it is. The other one is now followed closely.'); } });
        r.use = ev.target.value; keep(); draw(); };
      holder.append(slot);
    });
    if (st.refs.length < max) {
      /* The empty slot asks where the picture comes from: this computer, or one the project already has. */
      const add = el(`<div class="ag-refcard"><div class="ag-ref ag-refempty"><button class="ag-addref" type="button" title="Add a reference picture" aria-label="Add a reference picture" aria-haspopup="true" aria-expanded="false">+</button><input type="file" accept="image/*" hidden></div>
        <div class="ag-source" hidden><button class="small ag-up" type="button">Upload</button><button class="small ag-lib" type="button">Apply from Library</button></div></div>`), pick = add.querySelector('input'), menu = add.querySelector('.ag-source'), plus = add.querySelector('.ag-addref');
      plus.onclick = () => { menu.hidden = !menu.hidden; plus.setAttribute('aria-expanded', !menu.hidden); if (!menu.hidden) add.querySelector('.ag-up').focus(); };
      add.querySelector('.ag-up').onclick = () => pick.click();
      add.querySelector('.ag-lib').onclick = () => library(image => { st.refs.push({ image, use: 'keep exactly' }); keep(); draw(); }, st.refs.map(r => r.image));
      pick.onchange = async () => { const f = pick.files[0]; if (!f) return; add.classList.add('ag-loading'); try { st.refs.push({ image: await host.upload(f), use: 'keep exactly' }); keep(); } catch (e) { host.toast(e.message); } draw(); };
      holder.append(add);
    }
    const adds = added(name);
    if (adds.length) holder.append(el(`<div class="hint ag-adds"><b>Added after your prompt:</b> ${esc(adds.join(' '))}</div>`));
    if (nums.includes(0)) holder.append(el('<div class="hint ag-adds">A kept picture takes one of the four places, so only three others are used with it.</div>'));
  }

  /* Apply from Library: every picture the project already has, grouped, to pick one as a reference. */
  let picker = null;
  function closeLibrary() { if (picker) picker.remove(); picker = null; }
  document.addEventListener('keydown', ev => { if (picker && ev.key === 'Escape') closeLibrary(); });
  async function library(choose, already) {
    closeLibrary();
    picker = el(`<div class="ag-modal" role="dialog" aria-modal="true" aria-label="Apply from Library"><div class="ag-modalbox">
      <div class="ag-modalhead"><h2>Apply from Library</h2><input class="ag-find" type="search" placeholder="Filter by name" aria-label="Filter by name"><span class="ag-grow"></span><button class="small ghost ag-close" type="button" title="Close">✕</button></div>
      <p class="hint">Pictures this project already has. Click one to use it as the reference. Nothing is copied or changed.</p><div class="ag-libbody"><p class="hint">Loading…</p></div></div></div>`);
    picker.onpointerdown = ev => { if (ev.target === picker) closeLibrary(); };
    picker.querySelector('.ag-close').onclick = closeLibrary;
    root.querySelector('.ag').append(picker);
    const body = picker.querySelector('.ag-libbody'), find = picker.querySelector('.ag-find');
    let all = [];
    try { all = (await call('GET', '/library?project=' + encodeURIComponent(host.pid))).pictures; } catch (e) { body.innerHTML = '<p class="hint">' + esc(e.message) + '</p>'; return; }
    if (!picker) return;
    const show = () => {
      const want = find.value.trim().toLowerCase(), list = all.filter(p => !want || p.label.toLowerCase().includes(want) || p.group.toLowerCase().includes(want));
      body.innerHTML = '';
      if (!all.length) { body.append(el('<p class="hint">This project has no pictures yet. Generate one, or use Upload.</p>')); return; }
      if (!list.length) { body.append(el('<p class="hint">Nothing matches that.</p>')); return; }
      [...new Set(list.map(p => p.group))].forEach(group => {
        const grid = el('<div class="ag-libgrid"></div>');
        list.filter(p => p.group === group).forEach(p => {
          const used = already.includes(p.image), b = el(`<button class="ag-libitem${used ? ' ag-libused' : ''}" type="button" title="${esc(p.label)}"${used ? ' disabled' : ''}><img loading="lazy" alt="" src="${esc(host.view(p.image))}"><span>${esc(p.label)}</span>${used ? '<i>already a reference here</i>' : ''}</button>`);
          b.onclick = () => { closeLibrary(); choose(p.image); };
          grid.append(b);
        });
        body.append(el(`<h3>${esc(group)} <span class="hint">${list.filter(p => p.group === group).length}</span></h3>`), grid);
      });
    };
    find.oninput = show; show(); find.focus();
  }

  /* For a reference set to "Insert as it is": put it in the centre of a blank picture of the size pictures are made at, and
   * make the mask that tells the model to draw everywhere except on it. Same method as Identity Studio. */
  async function place(image) {
    const [W, H] = data.size, img = new Image(); img.src = host.view(image); await img.decode();
    const iw = img.naturalWidth || 512, ih = img.naturalHeight || 512, k = Math.min(W * 0.6 / iw, H * 0.6 / ih);
    const w = Math.round(iw * k), h = Math.round(ih * k), x = Math.round((W - w) / 2), y = Math.round((H - h) / 2);
    const sheet = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; return c; };
    const canvas = sheet(), cx = canvas.getContext('2d'); cx.imageSmoothingQuality = 'high'; cx.fillStyle = '#808080'; cx.fillRect(0, 0, W, H); cx.drawImage(img, x, y, w, h);
    const shape = sheet(), sx = shape.getContext('2d'); sx.imageSmoothingQuality = 'high';
    sx.drawImage(img, x, y, w, h); sx.globalCompositeOperation = 'source-in'; sx.fillStyle = '#000'; sx.fillRect(0, 0, W, H);      // its silhouette, in black
    const mask = sheet(), mx = mask.getContext('2d'); mx.fillStyle = '#fff'; mx.fillRect(0, 0, W, H);
    for (const [dx, dy] of [[0, 0], [2, 0], [-2, 0], [0, 2], [0, -2]]) mx.drawImage(shape, dx, dy);                                // a 2-pixel guard band so its edge is never repainted
    return { image, canvas: canvas.toDataURL('image/png'), mask: mask.toDataURL('image/png'), soft: k > 1.5 };
  }

  function paint(card, name) {
    const waiting = busy(name), failed = B(name).jobs.filter(j => j.status === 'error'), line = card.querySelector('.ag-status');
    line.className = 'ag-status ' + (failed.length && !waiting ? 'err' : waiting ? 'busy' : 'hint');
    line.textContent = waiting ? `Generating ${waiting} picture${waiting > 1 ? 's' : ''}…` : failed.length ? 'Failed: ' + (failed[failed.length - 1].error || 'unknown error') : '';
  }
  function status() { root.querySelectorAll('.ag-box').forEach(card => paint(card, card.dataset.box)); }

  return {
    show(element, given) {
      const changed = !host || host.pid !== given.pid;
      root = element; host = given; showing = true;
      if (changed) { data = null; root.innerHTML = '<div class="panel hint">Loading…</div>'; }
      load();
    },
    hide() { showing = false; clearTimeout(timer); closeLibrary(); },
    _state: () => data,
  };
})();
