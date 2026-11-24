/* SWIFT Director: Asset Generator.
 *
 * A tab for making pictures outside the storyboard. Two modes work today:
 *   Image Generation   one prompt, up to four reference pictures
 *   Depth Generation   background, middle ground and foreground made separately, then redrawn as one picture
 * Character Generation and 3D Generation are shown in the bar and arrive later.
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
    if (data) { ['image', ...LAYERS, 'composed'].forEach(n => { const mine = S()[n]; fresh.state[n].prompt = mine.prompt; fresh.state[n].count = mine.count; fresh.state[n].refs = mine.refs; fresh.state[n].at = mine.at; }); }
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
      <button data-m="image" role="tab">Image Generation</button><button data-m="character" role="tab" disabled title="Not built yet">Character Generation <span class="pill">later</span></button>
      <button data-m="depth" role="tab">Depth Generation</button><button data-m="3d" role="tab" disabled title="Not built yet">3D Generation <span class="pill">later</span></button></div><div class="ag-body"></div></div>`);
    page.querySelectorAll('.ag-modes button').forEach(b => { b.classList.toggle('on', b.dataset.m === mode); b.setAttribute('aria-selected', b.dataset.m === mode); b.onclick = () => { mode = b.dataset.m; draw(); }; });
    const body = page.querySelector('.ag-body');
    if (mode === 'image') {
      body.append(el('<p class="hint ag-lead">One picture from a prompt and up to four reference pictures. Made with FLUX.2, the same image model the storyboard uses.</p>'), box('image'));
    } else {
      body.append(el('<p class="hint ag-lead">Make the three layers separately, choose one of each with <b>Apply to Composed Output</b>, then run the composed output: the image model redraws the three as one picture. It is a redraw, not a cut-and-paste, so small details can change.</p>'));
      const row = el('<div class="ag-row"></div>'); LAYERS.forEach(l => row.append(box(l))); body.append(row, box('composed'));
    }
    root.append(page);
    if (focus) { const again = root.querySelector(`[data-k="${focus}"]`); if (again) again.focus(); }
  }

  function at(name) {                      // which finished picture a box is showing: the remembered one, else the newest
    const list = B(name).results; if (!list.length) return -1;
    const i = list.findIndex(r => r.id === S()[name].at); return i < 0 ? list.length - 1 : i;
  }

  function box(name) {
    const st = S()[name], composed = name === 'composed', list = B(name).results, i = at(name), cur = i >= 0 ? list[i] : null;
    const applied = !composed && name !== 'image' && cur && S().composed.applied[name] === cur.image;
    const card = el(`<section class="panel ag-box${composed ? ' ag-composed' : ''}" data-box="${name}">
      <h2>${TITLE[name]}</h2>
      <div class="ag-stage"><button class="ag-arrow ag-prev" type="button" aria-label="Previous picture" title="Previous picture">‹</button>
        <div class="ag-pic">${cur ? `<img alt="${TITLE[name]} picture ${i + 1}" src="${esc(host.view(cur.image))}">` : '<div class="ag-empty">No picture yet</div>'}${applied ? '<span class="pill ag-applied">Applied</span>' : ''}</div>
        <button class="ag-arrow ag-next" type="button" aria-label="Next picture" title="Next picture">›</button></div>
      <div class="ag-under"><span class="hint ag-count">${list.length ? (i + 1) + ' of ' + list.length : ''}</span><span class="ag-status hint"></span><span class="ag-grow"></span>
        ${cur ? `<a class="btn small" href="${esc(host.view(cur.image))}" download="${esc(TITLE[name].toLowerCase().replace(/ /g, '-') + '-' + (i + 1) + '.png')}">Download</a><select class="ag-asset" aria-label="Save this picture to the project's Assets" title="Add this picture to the project's Assets"><option value="">Save to Assets as…</option><option value="scene">Scene asset</option><option value="prop">Prop</option></select><button class="small ghost ag-del" type="button" title="Remove this picture from the list">Remove</button>` : ''}</div>
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
      q('.ag-asset').onchange = ev => { const kind = ev.target.value; ev.target.value = ''; if (kind) host.saveAsset(cur.image, kind); };
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
      const b = ev.currentTarget; b.disabled = true; clearTimeout(saveTimer);
      try { st.at = null; take(await call('POST', '/run', { project: host.pid, box: name, state: S() })); draw(); } catch (e) { host.toast(e.message); }
      b.disabled = false;
    };
    const ap = q('.ag-apply');
    if (ap) ap.onclick = async () => { clearTimeout(saveTimer); try { await call('POST', '/save', { project: host.pid, state: S() }); take(await call('POST', '/apply', { project: host.pid, layer: name, image: cur.image })); draw(); } catch (e) { host.toast(e.message); } };
    paint(card, name);
    return card;
  }

  /* The reference slots of a box: four, or for the composed output the one free slot that becomes image 4. */
  function refs(holder, name) {
    const st = S()[name], composed = name === 'composed', max = composed ? 1 : data.limits.refs;
    holder.append(el(`<span class="hint">${composed ? 'Image 4 (optional)' : 'Reference pictures (up to ' + max + ')'}</span>`));
    for (let n = 0; n < max; n++) {
      const img = st.refs[n], num = composed ? 4 : n + 1;
      const slot = el(`<div class="ag-ref${img ? '' : ' ag-refempty'}">${img ? `<img alt="Reference ${num}" src="${esc(host.view(img))}"><button class="ag-x" type="button" title="Take this reference out" aria-label="Remove reference ${num}">×</button><span class="ag-num">${num}</span>`
        : n === st.refs.length ? `<label title="Add a reference picture"><input type="file" accept="image/*" hidden>+</label>` : ''}</div>`);
      if (img) { slot.querySelector('.ag-x').onclick = () => { st.refs.splice(n, 1); keep(); draw(); }; slot.querySelector('img').onclick = () => host.openViewer(host.view(img), 'Reference ' + num); }
      const pick = slot.querySelector('input');
      if (pick) pick.onchange = async () => { const f = pick.files[0]; if (!f) return; slot.classList.add('ag-loading'); try { st.refs.push(await host.upload(f)); keep(); } catch (e) { host.toast(e.message); } draw(); };
      holder.append(slot);
    }
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
