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
  let root = null, host = null, data = null, mode = 'image', timer = null, saveTimer = null, showing = false, cfgOpen = true;
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
  function configBox() {
    const c = cfg(), o = data.options, used = k => o.used.includes(k);
    const tag = k => used(k) ? '<span class="ag-tag ag-used" title="This setting changes what the Asset Generator does today">In use</span>' : '<span class="ag-tag" title="Saved with the project. A later update will act on it">Stored</span>';
    const role = r => { const u = o.in_use[r.key] || {}, now = u.name ? 'Automatic: ' + u.name : 'None installed';
      return `<label><span>${esc(r.label)} ${u.name && (r.key === 'image' || r.key === 'image_lora') ? '<span class="ag-tag ag-used" title="This is the model that makes the pictures today">In use</span>' : tag('models.' + r.key)}</span>
        <select data-k="cfg-m-${r.key}" data-role="${r.key}"${u.name ? '' : ' disabled'}><option value="auto">${esc(now)}</option></select>${u.note ? `<span class="hint">${esc(u.note)}</span>` : ''}</label>`; };
    const box = el(`<details class="panel ag-config"${cfgOpen ? ' open' : ''}><summary><h2>Asset Configuration</h2><span class="hint">${esc(NAME[mode])}${c.name ? ' · ' + esc(c.name) : ''} · ${esc(c.rating)} · ${esc((o.types.find(t => t.key === c.type) || {}).label || '')}</span></summary>
      <div class="ag-cfggrid">
        <fieldset><legend>Project Identity</legend>
          <label><span>Asset name ${tag('name')}</span><input data-k="cfg-name" class="ag-cfg-name" type="text" maxlength="80" value="${esc(c.name)}" placeholder="For example: Misty's ship"></label>
          <label><span>Rating ${tag('rating')}</span><select data-k="cfg-rating" class="ag-cfg-rating">${o.ratings.map(r => `<option${r === c.rating ? ' selected' : ''}>${esc(r)}</option>`).join('')}</select></label>
          <label><span>Asset type ${tag('type')}</span><select data-k="cfg-type" class="ag-cfg-type">${o.types.map(t => `<option value="${t.key}"${t.key === c.type ? ' selected' : ''}>${esc(t.label)}</option>`).join('')}</select></label>
          <span class="hint">The name and type decide what <b>Save to Assets</b> creates. The rating is a label for filtering later; it does not change what is generated.</span>
        </fieldset>
        <fieldset><legend>AI Model Configuration</legend>${o.roles.map(role).join('')}
          <span class="hint">At most one model is installed for each role today, so there is nothing to choose between yet. Roles marked Stored are not used by the Asset Generator yet.</span></fieldset>
        <fieldset><legend>Workflow and Approval Controls</legend>
          ${o.workflow.map(w => `<label class="ag-check"><input data-k="cfg-w-${w.key}" data-flow="${w.key}" type="checkbox"${c.workflow[w.key] ? ' checked' : ''}> <span>${esc(w.label)} ${tag('workflow.' + w.key)}</span></label>`).join('')}
        </fieldset>
      </div></details>`);
    box.addEventListener('toggle', () => { cfgOpen = box.open; });
    const q = x => box.querySelector(x);
    q('.ag-cfg-name').oninput = ev => { c.name = ev.target.value.slice(0, 80); keep(); };
    q('.ag-cfg-name').onchange = () => draw();
    q('.ag-cfg-rating').onchange = ev => { c.rating = ev.target.value; keep(); draw(); };
    q('.ag-cfg-type').onchange = ev => { c.type = ev.target.value; keep(); draw(); };
    box.querySelectorAll('[data-role]').forEach(i => i.onchange = () => { c.models[i.dataset.role] = i.value; keep(); });
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
      <label class="ag-label">Prompt<textarea data-k="p-${name}" class="ag-prompt" rows="${composed ? 4 : 5}" placeholder="${esc(HINT[name] || '')}">${esc(st.prompt)}</textarea></label>
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
    q('.ag-prompt').oninput = ev => { st.prompt = ev.target.value; keep(); };
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
    paint(card, name);
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
      const add = el('<div class="ag-refcard"><div class="ag-ref ag-refempty"><label title="Add a reference picture"><input type="file" accept="image/*" hidden>+</label></div></div>'), pick = add.querySelector('input');
      pick.onchange = async () => { const f = pick.files[0]; if (!f) return; add.classList.add('ag-loading'); try { st.refs.push({ image: await host.upload(f), use: 'keep exactly' }); keep(); } catch (e) { host.toast(e.message); } draw(); };
      holder.append(add);
    }
    const adds = [...(st.refs.some(r => r.use === 'insert') ? [useOf('insert').adds] : []), ...st.refs.map((r, n) => nums[n] ? useOf(r.use).adds.replace('{n}', nums[n]) : null).filter(Boolean)];
    if (adds.length) holder.append(el(`<div class="hint ag-adds"><b>Added after your prompt:</b> ${esc(adds.join(' '))}</div>`));
    if (nums.includes(0)) holder.append(el('<div class="hint ag-adds">A kept picture takes one of the four places, so only three others are used with it.</div>'));
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
    hide() { showing = false; clearTimeout(timer); },
    _state: () => data,
  };
})();
