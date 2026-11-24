/* SWIFT Director: Audio Lab, the multi-track audio timeline.
 *
 * Self-contained: it talks only to /api/audio/, draws only inside the element it is given, and its classes
 * start with "al-". The page calls AudioLab.show(element, project) when the tab is opened. From the project
 * it reads the id, and the song's tempo if Assisted Storyboard has analysed one; it changes nothing in it.
 *
 * Everything on the timeline is counted in whole samples at the timeline's rate. Every edit is an instruction
 * on a clip (where it sits, where in its sound it starts, how long it plays); no sound file is ever changed.
 * Waveforms are drawn from peak data the server made once per sound. A sound is decoded in the browser only
 * when it is first needed for playback.
 */
(function () {
  'use strict';
  const API = '/api/audio/', HEAD = 216, LANE = 98, MIN_PX = 2, MAX_PX = 800;
  /* Track colours are data, like the colours in a chart: they tell tracks apart and are stored with the track. */
  const KIND_COLOR = { music:'#22c55e', narration:'#38bdf8', dialogue:'#a78bfa', sfx:'#f59e0b', ambience:'#2dd4bf', foley:'#f472b6', custom:'#94a3b8' };
  let root, info, pid, T, assets = {}, peaks = {}, buffers = {}, sel = new Set(), activeTrack = null;
  let head = 0, px = 60, snapMode = 'grid', undo = [], redo = [], saveTimer = null, saving = false, conflict = false, songTempo = null;
  let ctx = null, playing = null, raf = 0;

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const say = (m) => { if (typeof window.toast === 'function') window.toast(m); else console.warn(m); };
  const uid = () => Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, '0')).join('');
  const R = () => T.sample_rate, secs = s => s / R(), smp = s => Math.round(s * R());
  const X = s => secs(s) * px, fromX = x => Math.max(0, smp(x / px));
  const clock = s => { const t = secs(s), m = Math.floor(t / 60); return m + ':' + (t - m * 60).toFixed(2).padStart(5, '0'); };
  const db = v => Math.pow(10, v / 20);
  const allClips = () => T.tracks.flatMap(t => t.clips.map(c => ({ c, t })));
  const find = id => allClips().find(x => x.c.id === id);
  const endOf = () => Math.max(0, ...allClips().map(x => x.c.start + x.c.length));
  const assetLen = c => { const a = assets[c.asset_id]; return a ? Math.round(a.file.length * R() / a.file.sample_rate) : c.offset + c.length; };   // a sound's length in timeline samples

  async function call(method, route, body) {
    const o = { method }; if (body !== undefined) { o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(body); }
    const r = await fetch(API + route, o), j = await r.json().catch(() => ({ error: 'Unexpected reply from the server (status ' + r.status + ').' }));
    if (!r.ok || j.error) { const e = new Error(j.error || 'Request failed: ' + r.status); e.status = r.status; throw e; }
    return j;
  }

  /* ---------- saving, undo, redo ---------- */
  function scheduleSave() { setState('saving…'); clearTimeout(saveTimer); saveTimer = setTimeout(save, 700); }
  async function save() {
    clearTimeout(saveTimer); saveTimer = null; if (saving || conflict) { if (saving) saveTimer = setTimeout(save, 300); return; }
    saving = true; const sent = JSON.stringify(T);
    try { const out = await call('PUT', 'timeline?project=' + encodeURIComponent(pid), { timeline: T, based_on: T.revision }); const editedMeanwhile = JSON.stringify(T) !== sent; T.revision = out.revision; setState(editedMeanwhile ? 'saving…' : 'saved'); if (editedMeanwhile) scheduleSave(); }
    catch (e) { if (e.status === 409) { conflict = true; setState('changed elsewhere'); banner('This timeline was changed in another window. <button class="small al-reload" type="button">Load the latest version</button>'); } else { setState('not saved'); say(e.message); } }
    saving = false;
  }
  const setState = t => { const s = root && root.querySelector('.al-state'); if (s) s.textContent = t; };
  function banner(html) { const b = root.querySelector('.al-banner'); b.innerHTML = html; b.hidden = !html; const r = b.querySelector('.al-reload'); if (r) r.onclick = () => { conflict = false; load(); }; }
  /* Every change goes through edit(): the state before it is kept for Undo, then the change is drawn and saved. */
  function edit(change) { const before = JSON.stringify(T), at = playing ? now() : null; change(); if (JSON.stringify(T) === before) { draw(); return; } undo.push(before); if (undo.length > 100) undo.shift(); redo = []; if (playing) { head = at; restart(); } draw(); scheduleSave(); }
  function step(from, to) { if (!from.length) return; to.push(JSON.stringify(T)); const rev = T.revision; T = JSON.parse(from.pop()); T.revision = rev; sel = new Set([...sel].filter(id => find(id))); if (playing) { head = now(); restart(); } draw(); scheduleSave(); }

  /* ---------- loading ---------- */
  async function load() {
    root.innerHTML = '<p class="hint">Loading Audio Lab…</p>';
    try {
      if (!info) info = await call('GET', 'info');
      let list = (await call('GET', 'assets?project=' + encodeURIComponent(pid))).assets;
      if (!list.length) { try { const got = await call('POST', 'assets/adopt', { project: pid }); if (got.brought.length) list = (await call('GET', 'assets?project=' + encodeURIComponent(pid))).assets; } catch (e) { /* nothing to bring in */ } }
      assets = Object.fromEntries(list.map(a => [a.id, a]));
      T = await call('GET', 'timeline?project=' + encodeURIComponent(pid));
    } catch (e) { root.innerHTML = '<p class="hint">Audio Lab could not be loaded: ' + esc(e.message) + '</p>'; return; }
    undo = []; redo = []; sel = new Set(); head = Math.min(head, endOf()); activeTrack = T.tracks[0] ? T.tracks[0].id : null;
    frame(); draw();
  }
  async function peaksFor(id) {
    if (peaks[id]) return peaks[id];
    const buf = await (await fetch(API + 'asset/peaks?id=' + id)).arrayBuffer(), v = new DataView(buf);
    return (peaks[id] = { rate: v.getUint32(5, true), data: new Int8Array(buf, 13) });
  }

  /* ---------- the fixed parts of the page ---------- */
  function frame() {
    root.innerHTML = '';
    root.appendChild(el(`<div class="al">
      <div class="al-bar">
        <button class="primary al-play" type="button" title="Play or pause (Space)">Play</button><button class="al-stop" type="button" title="Stop and go back to where playback started">Stop</button>
        <span class="al-clock" aria-live="off">0:00.00</span>
        <span class="al-sep"></span>
        <button class="small al-zout" type="button" title="Zoom out">−</button><button class="small al-zin" type="button" title="Zoom in (or hold Ctrl and scroll)">+</button>
        <label class="al-inline">Snap <select class="al-snap"><option value="off">Off</option><option value="grid">Grid</option><option value="beats">Beats</option><option value="markers">Markers and clips</option></select></label>
        <span class="al-sep"></span>
        <button class="small al-undo" type="button" title="Undo (Ctrl+Z)">Undo</button><button class="small al-redo" type="button" title="Redo (Ctrl+Y)">Redo</button>
        <button class="small al-split" type="button" title="Split at the playhead (S)">Split</button><button class="small al-dup" type="button" title="Duplicate the selected clips (Ctrl+D)">Duplicate</button><button class="small al-del" type="button" title="Delete the selected clips (Delete)">Delete</button>
        <button class="small al-mark" type="button" title="Add a marker at the playhead (M)">Marker</button>
        <span class="al-grow"></span><span class="pill al-state">saved</span>
      </div>
      <div class="al-banner" hidden></div>
      <div class="al-bin"><div class="al-binhead"><b>Sounds in this project</b><label class="btn small">Import audio<input class="al-file" type="file" accept="audio/*,video/mp4,.wav,.mp3,.flac,.ogg,.m4a,.opus" multiple hidden></label><button class="small al-tempo" type="button" hidden></button><span class="hint al-binhint"></span></div><div class="al-sounds"></div></div>
      <div class="al-scroll"><div class="al-grid"></div></div>
      <div class="al-foot"><button class="small al-addtrack" type="button">Add track</button><span class="hint">Click a lane or the ruler to move the playhead. Drag a clip to move it, its edges to trim it. Shift-click selects several. Playback here is a preview; the original files are never changed.</span></div>
    </div>`));
    const q = s => root.querySelector(s);
    q('.al-play').onclick = () => playing ? pause() : play();
    q('.al-stop').onclick = stop;
    q('.al-zin').onclick = () => zoom(1.5); q('.al-zout').onclick = () => zoom(1 / 1.5);
    q('.al-snap').value = snapMode; q('.al-snap').onchange = ev => { snapMode = ev.target.value; draw(); };
    q('.al-undo').onclick = () => step(undo, redo); q('.al-redo').onclick = () => step(redo, undo);
    q('.al-split').onclick = split; q('.al-dup').onclick = duplicate; q('.al-del').onclick = remove; q('.al-mark').onclick = addMarker;
    q('.al-addtrack').onclick = () => edit(() => { const t = { id: uid(), name: 'Track ' + (T.tracks.length + 1), kind: 'custom', color: null, volume_db: 0, pan: 0, mute: false, solo: false, locked: false, output: 'master', effects: [], clips: [] }; T.tracks.push(t); activeTrack = t.id; });
    q('.al-file').onchange = async ev => { await importFiles([...ev.target.files]); ev.target.value = ''; };
    q('.al-scroll').addEventListener('wheel', ev => { if (ev.ctrlKey) { ev.preventDefault(); zoom(ev.deltaY < 0 ? 1.2 : 1 / 1.2); } }, { passive: false });
    const tempo = q('.al-tempo');
    if (songTempo) { tempo.hidden = false; tempo.textContent = `Use the song's tempo (${Math.round(songTempo.bpm)} BPM)`; tempo.onclick = () => { edit(() => { T.tempo = { bpm: songTempo.bpm, first_beat: smp(songTempo.first), beats_per_bar: 4 }; }); snapMode = 'beats'; q('.al-snap').value = 'beats'; draw(); }; }
  }

  async function importFiles(files) {
    const hint = root.querySelector('.al-binhint');
    for (const f of files) {
      hint.textContent = 'Bringing in ' + f.name + '…';
      try {
        const r = await fetch(`${API}assets?project=${encodeURIComponent(pid)}&name=${encodeURIComponent(f.name)}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: f });
        const a = await r.json().catch(() => ({ error: 'Unexpected reply from the server (status ' + r.status + ').' }));
        if (!r.ok || a.error) throw new Error(a.error || 'Request failed: ' + r.status);
        assets[a.id] = a; if (a.already_there) say(f.name + ' was already in the library, so the existing copy is used.');
      } catch (e) { say(f.name + ': ' + e.message); }
    }
    hint.textContent = ''; draw();
  }

  /* ---------- drawing ---------- */
  function draw() {
    if (!root || !T) return;
    const q = s => root.querySelector(s);
    q('.al-undo').disabled = !undo.length; q('.al-redo').disabled = !redo.length;
    [q('.al-dup'), q('.al-del')].forEach(b => b.disabled = !sel.size);
    q('.al-play').textContent = playing ? 'Pause' : 'Play'; q('.al-clock').textContent = clock(head);
    drawBin(); drawGrid(); placeHead();
  }

  function drawBin() {
    const box = root.querySelector('.al-sounds'); box.innerHTML = '';
    const list = Object.values(assets);
    if (!list.length) { box.innerHTML = '<span class="hint">No sounds yet. Import audio to start: WAV, MP3, FLAC, OGG, M4A, or the sound from an MP4.</span>'; return; }
    list.forEach(a => {
      const chip = el(`<div class="al-sound" draggable="true" title="Drag onto a track, or press Add"><b>${esc(a.name)}</b><span class="hint">${clock(Math.round(a.file.length * R() / a.file.sample_rate))} · ${esc((a.file.format || '').toUpperCase())}${a.file.channels > 1 ? ' · stereo' : ''}</span><button class="small al-add" type="button">Add</button><button class="small ghost al-drop" type="button" title="Take this sound out of the project">✕</button></div>`);
      chip.ondragstart = ev => ev.dataTransfer.setData('text/al-asset', a.id);
      chip.querySelector('.al-add').onclick = () => place(a.id, activeTrack, head);
      chip.querySelector('.al-drop').onclick = async () => {
        const used = allClips().filter(x => x.c.asset_id === a.id).length;
        if (used && !confirm(`"${a.name}" is used by ${used} clip${used === 1 ? '' : 's'} on the timeline. Take it out of the project and remove ${used === 1 ? 'that clip' : 'those clips'}?`)) return;
        if (used) { edit(() => T.tracks.forEach(t => t.clips = t.clips.filter(c => c.asset_id !== a.id))); await save(); }
        try { await call('POST', 'assets/remove', { project: pid, id: a.id }); delete assets[a.id]; draw(); } catch (e) { say(e.message); }
      };
      box.appendChild(chip);
    });
  }

  function place(assetId, trackId, at) {
    edit(() => {
      let t = T.tracks.find(x => x.id === trackId && !x.locked);
      if (!t) { const a = assets[assetId]; t = { id: uid(), name: a && a.kind !== 'other' ? a.kind[0].toUpperCase() + a.kind.slice(1) : 'Track ' + (T.tracks.length + 1), kind: info.track_kinds.includes(a && a.kind) ? a.kind : 'custom', color: null, volume_db: 0, pan: 0, mute: false, solo: false, locked: false, output: 'master', effects: [], clips: [] }; T.tracks.push(t); }
      const c = { id: uid(), asset_id: assetId, start: snap(at), offset: 0, length: Math.max(1, assetLen({ asset_id: assetId, offset: 0, length: 0 })), gain_db: 0, fade_in: 0, fade_out: 0, speed: 1, pitch: 0, reverse: false, muted: false, locked: false, label: '', effects: [], link: null };
      t.clips.push(c); activeTrack = t.id; sel = new Set([c.id]);
    });
  }

  function gridStep() {                                         // the spacing of grid lines, in samples, for the current zoom
    if (snapMode === 'beats' && T.tempo.bpm) { let b = smp(60 / T.tempo.bpm); while (X(b) < 14) b *= T.tempo.beats_per_bar || 4; return b; }
    return smp([0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 300].find(s => s * px >= 14) || 600);
  }
  function snap(s, skip) {
    if (snapMode === 'off') return Math.max(0, Math.round(s));
    const near = [head, 0], reach = fromX(8);
    T.markers.forEach(m => near.push(m.at));
    allClips().forEach(({ c }) => { if (!skip || !skip.has(c.id)) near.push(c.start, c.start + c.length); });
    if (snapMode !== 'markers') { const g = gridStep(), base = snapMode === 'beats' && T.tempo.bpm ? T.tempo.first_beat : 0; near.push(base + Math.round((s - base) / g) * g); }
    let best = Math.round(s), gap = snapMode === 'markers' ? reach : Infinity;
    near.forEach(n => { const d = Math.abs(n - s); if (d < gap && (snapMode !== 'markers' || d <= reach)) { gap = d; best = n; } });
    return Math.max(0, best);
  }

  function drawGrid() {
    const grid = root.querySelector('.al-grid'), total = Math.max(endOf() + smp(30), smp(60)), width = Math.ceil(X(total));
    grid.innerHTML = ''; grid.style.width = (HEAD + width) + 'px';
    /* ruler */
    const ruler = el(`<div class="al-row al-rulerrow"><div class="al-corner"><span class="hint">${T.tracks.length} track${T.tracks.length === 1 ? '' : 's'} · ${clock(endOf())}</span></div><div class="al-ruler" style="width:${width}px"></div></div>`);
    const rl = ruler.querySelector('.al-ruler'), beats = snapMode === 'beats' && T.tempo.bpm;
    let stepS = gridStep(); while (X(stepS) < 70) stepS *= beats ? 2 : (stepS % smp(1) === 0 && stepS >= smp(1) ? 2 : 5);
    for (let s = beats ? T.tempo.first_beat : 0, i = 0; s <= total && i < 4000; s += stepS, i++) {
      const label = beats ? 'Bar ' + (Math.round((s - T.tempo.first_beat) / smp(60 / T.tempo.bpm) / (T.tempo.beats_per_bar || 4)) + 1) : clock(s).replace(/\.00$/, '');
      rl.appendChild(el(`<span class="al-tick" style="left:${X(s)}px">${esc(label)}</span>`));
    }
    T.markers.forEach(m => { const k = el(`<button class="al-marker" type="button" style="left:${X(m.at)}px" title="Click to go here. Double-click to rename. Right-click to remove.">${esc(m.name || 'Marker')}</button>`);
      k.onclick = ev => { ev.stopPropagation(); seek(m.at); };
      k.ondblclick = ev => { ev.stopPropagation(); const n = prompt('Marker name', m.name || ''); if (n != null) edit(() => { m.name = n.slice(0, 80); }); };
      k.oncontextmenu = ev => { ev.preventDefault(); edit(() => { T.markers = T.markers.filter(x => x !== m); }); };
      rl.appendChild(k); });
    rl.onpointerdown = ev => { if (ev.target === rl || ev.target.classList.contains('al-tick')) seek(snap(fromX(ev.clientX - rl.getBoundingClientRect().left))); };
    grid.appendChild(ruler);
    if (!T.tracks.length) { grid.appendChild(el('<div class="al-empty hint">No tracks yet. Press Add track, or press Add on a sound above.</div>')); return; }
    const g = gridStep(), lines = `repeating-linear-gradient(to right, var(--swift-border) 0 1px, transparent 1px ${X(g)}px)`;
    T.tracks.forEach((t, i) => grid.appendChild(trackRow(t, i, width, lines)));
    grid.appendChild(el('<div class="al-head-line"></div>'));
  }

  function trackRow(t, i, width, lines) {
    const color = t.color || KIND_COLOR[t.kind] || KIND_COLOR.custom, soloed = T.tracks.some(x => x.solo), quiet = soloed ? !t.solo : t.mute;
    const row = el(`<div class="al-row${t.id === activeTrack ? ' al-active' : ''}${quiet ? ' al-quiet' : ''}" data-track="${t.id}">
      <div class="al-th" style="border-left-color:${color}">
        <div class="al-thtop"><input class="al-name" value="${esc(t.name)}" maxlength="60" aria-label="Track name"><select class="al-kind" aria-label="Track type">${info.track_kinds.map(k => `<option value="${k}"${k === t.kind ? ' selected' : ''}>${k === 'sfx' ? 'Sound effects' : k[0].toUpperCase() + k.slice(1)}</option>`).join('')}</select></div>
        <div class="al-thmid"><button class="small al-m${t.mute ? ' on' : ''}" type="button" title="Mute" aria-pressed="${t.mute}">M</button><button class="small al-s${t.solo ? ' on' : ''}" type="button" title="Solo: hear only soloed tracks" aria-pressed="${t.solo}">S</button><button class="small al-l${t.locked ? ' on' : ''}" type="button" title="Lock: clips on this track cannot be changed" aria-pressed="${t.locked}">L</button>
          <input class="al-vol" type="range" min="-60" max="12" step="1" value="${t.volume_db}" title="Volume ${t.volume_db} dB" aria-label="Volume"><input class="al-pan" type="range" min="-1" max="1" step="0.1" value="${t.pan}" title="Pan" aria-label="Pan"></div>
        <div class="al-thbot"><button class="small ghost al-up" type="button" title="Move up"${i === 0 ? ' disabled' : ''}>↑</button><button class="small ghost al-down" type="button" title="Move down"${i === T.tracks.length - 1 ? ' disabled' : ''}>↓</button><button class="small ghost al-copy" type="button" title="Duplicate this track">Copy</button><button class="small ghost al-kill" type="button" title="Delete this track">Delete</button></div>
      </div>
      <div class="al-lane" style="width:${width}px;background-image:${lines}"></div></div>`);
    const q = s => row.querySelector(s), on = (s, fn) => q(s).onclick = () => edit(fn);
    q('.al-name').onchange = ev => edit(() => { t.name = ev.target.value.trim().slice(0, 60) || 'Track'; });
    q('.al-kind').onchange = ev => edit(() => { t.kind = ev.target.value; });
    on('.al-m', () => { t.mute = !t.mute; }); on('.al-s', () => { t.solo = !t.solo; }); on('.al-l', () => { t.locked = !t.locked; });
    /* a slider is one undo step however far it is dragged: the state from before the drag is kept when it starts */
    const slider = (s, apply) => { let before = null; q(s).oninput = ev => { if (before == null) before = JSON.stringify(T); apply(+ev.target.value, ev.target); liveMix(); }; q(s).onchange = () => { if (before != null && before !== JSON.stringify(T)) { undo.push(before); redo = []; scheduleSave(); root.querySelector('.al-undo').disabled = false; } before = null; }; };
    slider('.al-vol', (v, input) => { t.volume_db = v; input.title = 'Volume ' + v + ' dB'; }); slider('.al-pan', v => { t.pan = v; });
    on('.al-up', () => { T.tracks.splice(i - 1, 0, T.tracks.splice(i, 1)[0]); }); on('.al-down', () => { T.tracks.splice(i + 1, 0, T.tracks.splice(i, 1)[0]); });
    on('.al-copy', () => { const copy = JSON.parse(JSON.stringify(t)); copy.id = uid(); copy.name = (t.name + ' copy').slice(0, 60); copy.clips.forEach(c => c.id = uid()); T.tracks.splice(i + 1, 0, copy); });
    q('.al-kill').onclick = () => { if (t.clips.length && !confirm(`Delete the track "${t.name}" and its ${t.clips.length} clip${t.clips.length === 1 ? '' : 's'}? Undo brings it back.`)) return; edit(() => { T.tracks.splice(i, 1); if (activeTrack === t.id) activeTrack = T.tracks[0] ? T.tracks[0].id : null; }); };
    row.querySelector('.al-th').addEventListener('pointerdown', () => { if (activeTrack !== t.id) { activeTrack = t.id; root.querySelectorAll('.al-row').forEach(r => r.classList.toggle('al-active', r.dataset.track === t.id)); } });
    const lane = q('.al-lane');
    lane.onpointerdown = ev => { if (ev.target !== lane) return; activeTrack = t.id; sel.clear(); seek(snap(fromX(ev.clientX - lane.getBoundingClientRect().left))); };
    lane.ondragover = ev => { if ([...ev.dataTransfer.types].includes('text/al-asset')) ev.preventDefault(); };
    lane.ondrop = ev => { const id = ev.dataTransfer.getData('text/al-asset'); if (id && assets[id]) { ev.preventDefault(); if (t.locked) return say('That track is locked.'); place(id, t.id, fromX(ev.clientX - lane.getBoundingClientRect().left)); } };
    t.clips.forEach(c => lane.appendChild(clipBox(c, t, color)));
    return row;
  }

  function clipBox(c, t, color) {
    const a = assets[c.asset_id], w = Math.max(3, X(c.length));
    const box = el(`<div class="al-clip${sel.has(c.id) ? ' al-sel' : ''}${t.locked || c.locked ? ' al-locked' : ''}" data-clip="${c.id}" style="left:${X(c.start)}px;width:${w}px;border-color:${color}"><canvas></canvas><span class="al-label">${esc(c.label || (a ? a.name : 'Missing sound'))}</span><i class="al-trim al-tl"></i><i class="al-trim al-tr"></i></div>`);
    wave(box.querySelector('canvas'), c, w, color);
    box.onpointerdown = ev => grab(ev, c, t, box);
    return box;
  }
  async function wave(canvas, c, w, color) {
    const cw = Math.min(8192, Math.max(1, Math.round(w))), ch = LANE - 22; canvas.width = cw; canvas.height = ch;
    let p; try { p = await peaksFor(c.asset_id); } catch (e) { return; }
    if (!canvas.isConnected) return;
    const g = canvas.getContext('2d'), mid = ch / 2; g.fillStyle = color;
    const perPx = (c.length / R()) * p.rate / cw, first = (c.offset / R()) * p.rate, n = p.data.length / 2;
    for (let x = 0; x < cw; x++) {
      let lo = 127, hi = -128; const i0 = Math.floor(first + x * perPx), i1 = Math.max(i0 + 1, Math.floor(first + (x + 1) * perPx));
      for (let i = i0; i < i1 && i < n; i++) { if (i < 0) continue; if (p.data[i * 2] < lo) lo = p.data[i * 2]; if (p.data[i * 2 + 1] > hi) hi = p.data[i * 2 + 1]; }
      if (hi < lo) continue;
      const k = db(c.gain_db), y0 = mid - Math.min(1, hi / 127 * k) * mid, y1 = mid - Math.max(-1, lo / 127 * k) * mid;
      g.fillRect(x, y0, 1, Math.max(1, y1 - y0));
    }
  }

  /* ---------- pointer work on clips: select, move, trim ---------- */
  function grab(ev, c, t, box) {
    if (ev.button) return;
    ev.stopPropagation(); activeTrack = t.id;
    if (ev.shiftKey || ev.ctrlKey || ev.metaKey) { sel.has(c.id) ? sel.delete(c.id) : sel.add(c.id); draw(); return; }
    if (!sel.has(c.id)) { sel = new Set([c.id]); root.querySelectorAll('.al-clip').forEach(b => b.classList.toggle('al-sel', b.dataset.clip === c.id)); root.querySelectorAll('.al-dup,.al-del').forEach(b => b.disabled = false); }
    if (t.locked || c.locked) return;
    const mode = ev.target.classList.contains('al-tl') ? 'left' : ev.target.classList.contains('al-tr') ? 'right' : 'move';
    const before = JSON.stringify(T), x0 = ev.clientX, y0 = ev.clientY, group = [...sel].map(find).filter(x => x && !x.t.locked && !x.c.locked).map(x => ({ c: x.c, start: x.c.start, offset: x.c.offset, length: x.c.length }));
    const skip = new Set(group.map(g => g.c.id)), lead = group.find(g => g.c === c) || group[0];
    let moved = false, targetTrack = null;
    box.setPointerCapture(ev.pointerId);
    box.onpointermove = mv => {
      const d = fromX(Math.abs(mv.clientX - x0)) * Math.sign(mv.clientX - x0); if (Math.abs(mv.clientX - x0) > 2 || Math.abs(mv.clientY - y0) > 8) moved = true; if (!moved) return;
      if (mode === 'move') {
        const shift = snap(lead.start + d, skip) - lead.start, floor = -Math.min(...group.map(g => g.start));
        group.forEach(g => { g.c.start = g.start + Math.max(shift, floor); const b = root.querySelector(`[data-clip="${g.c.id}"]`); if (b) b.style.left = X(g.c.start) + 'px'; });
        if (group.length === 1) { const under = document.elementsFromPoint(mv.clientX, mv.clientY).find(e => e.classList && e.classList.contains('al-row') && e.dataset.track); targetTrack = under && under.dataset.track !== t.id ? under.dataset.track : null; root.querySelectorAll('.al-row').forEach(r => r.classList.toggle('al-target', !!targetTrack && r.dataset.track === targetTrack)); }
      } else if (mode === 'left') {
        const want = snap(lead.start + d, skip), lo = lead.start - lead.offset, hi = lead.start + lead.length - 1, s = Math.min(hi, Math.max(lo, want));
        c.start = s; c.offset = lead.offset + (s - lead.start); c.length = lead.length - (s - lead.start);
        box.style.left = X(c.start) + 'px'; box.style.width = Math.max(3, X(c.length)) + 'px';
      } else {
        const want = snap(lead.start + lead.length + d, skip), max = lead.start + (assetLen(c) - lead.offset), e = Math.min(max, Math.max(lead.start + 1, want));
        c.length = e - lead.start; box.style.width = Math.max(3, X(c.length)) + 'px';
      }
    };
    box.onpointerup = box.onpointercancel = () => {
      box.onpointermove = box.onpointerup = box.onpointercancel = null;
      if (!moved) return;
      if (targetTrack) { const to = T.tracks.find(x => x.id === targetTrack); if (to && !to.locked) { t.clips = t.clips.filter(x => x !== c); to.clips.push(c); activeTrack = to.id; } }
      if (JSON.stringify(T) !== before) { undo.push(before); redo = []; if (playing) { head = now(); restart(); } scheduleSave(); }
      draw();
    };
  }

  /* ---------- clip commands ---------- */
  function split() {
    const targets = (sel.size ? [...sel].map(find).filter(Boolean) : allClips()).filter(({ c, t }) => !t.locked && !c.locked && head > c.start && head < c.start + c.length);
    if (!targets.length) return say('Move the playhead inside a clip to split it.');
    edit(() => targets.forEach(({ c, t }) => { const cut = head - c.start, right = JSON.parse(JSON.stringify(c)); right.id = uid(); right.start = head; right.offset = c.offset + cut; right.length = c.length - cut; right.fade_in = 0; c.length = cut; c.fade_out = 0; t.clips.push(right); }));
  }
  function duplicate() { const picked = [...sel].map(find).filter(x => x && !x.t.locked); if (!picked.length) return; edit(() => { const made = new Set(); picked.forEach(({ c, t }) => { const copy = JSON.parse(JSON.stringify(c)); copy.id = uid(); copy.start = c.start + c.length; t.clips.push(copy); made.add(copy.id); }); sel = made; }); }
  function remove() { const gone = new Set([...sel].filter(id => { const x = find(id); return x && !x.t.locked && !x.c.locked; })); if (!gone.size) return; edit(() => { T.tracks.forEach(t => t.clips = t.clips.filter(c => !gone.has(c.id))); sel = new Set(); }); }
  function addMarker() { edit(() => { T.markers.push({ id: uid(), at: head, name: 'Marker ' + (T.markers.length + 1), kind: 'marker' }); T.markers.sort((a, b) => a.at - b.at); }); }

  /* ---------- playhead, zoom ---------- */
  function placeHead() { const line = root.querySelector('.al-head-line'); if (line) line.style.transform = `translateX(${HEAD + X(head)}px)`; const c = root.querySelector('.al-clock'); if (c) c.textContent = clock(head); }
  function seek(s) { head = Math.max(0, Math.round(s)); if (playing) restart(); else draw(); }
  function zoom(k) { const sc = root.querySelector('.al-scroll'), at = X(head) - sc.scrollLeft; px = Math.min(MAX_PX, Math.max(MIN_PX, px * k)); draw(); sc.scrollLeft = Math.max(0, X(head) - at); }

  /* ---------- playback: the browser's audio engine, built fresh each time Play is pressed ---------- */
  async function bufferFor(id) {
    if (buffers[id]) return buffers[id];
    const data = await (await fetch(API + 'asset/file?id=' + id)).arrayBuffer();
    return (buffers[id] = await ctx.decodeAudioData(data));
  }
  const audible = () => { const solo = T.tracks.filter(t => t.solo); return solo.length ? solo : T.tracks.filter(t => !t.mute); };
  async function play() {
    if (playing) return;
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === 'suspended') await ctx.resume();
    const from = head >= endOf() ? 0 : head, tracks = audible(), need = [...new Set(tracks.flatMap(t => t.clips.filter(c => !c.muted && c.start + c.length > from).map(c => c.asset_id)))].filter(id => assets[id]);
    const missing = need.filter(id => !buffers[id]);
    if (missing.length) { setState('loading sounds…'); try { await Promise.all(missing.map(bufferFor)); } catch (e) { setState('saved'); return say('A sound could not be loaded for playback: ' + e.message); } setState('saved'); }
    const master = ctx.createGain(); master.gain.value = db(T.master.volume_db); master.connect(ctx.destination);
    const t0 = ctx.currentTime + 0.06, startSec = secs(from), nodes = {}, sources = [];
    T.tracks.forEach(t => { const g = ctx.createGain(), p = ctx.createStereoPanner(); g.connect(p); p.connect(master); nodes[t.id] = { g, p }; });
    tracks.forEach(t => t.clips.forEach(c => {
      const buf = buffers[c.asset_id]; if (!buf || c.muted || c.start + c.length <= from) return;
      const src = ctx.createBufferSource(), g = ctx.createGain(); src.buffer = buf; src.connect(g); g.connect(nodes[t.id].g);
      const cs = secs(c.start), len = secs(c.length), into = Math.max(0, startSec - cs), when = t0 + Math.max(0, cs - startSec), level = db(c.gain_db), fi = secs(c.fade_in), fo = secs(c.fade_out);
      g.gain.setValueAtTime(fi > into ? level * (into / fi) : level, when);
      if (fi > into) g.gain.linearRampToValueAtTime(level, when + (fi - into));
      if (fo > 0) { const fadeAt = when + Math.max(0, len - fo - into); g.gain.setValueAtTime(level * Math.min(1, (len - into) / fo), Math.max(when, fadeAt)); g.gain.linearRampToValueAtTime(0, when + (len - into)); }
      src.start(when, secs(c.offset) + into, len - into); sources.push(src);
    }));
    playing = { t0, from, master, nodes, sources, began: from };
    liveMix(); draw(); tick();
  }
  function liveMix() { if (!playing) return; const solo = T.tracks.some(t => t.solo); T.tracks.forEach(t => { const n = playing.nodes[t.id]; if (!n) return; n.g.gain.value = (solo ? !t.solo : t.mute) ? 0 : db(t.volume_db); n.p.pan.value = t.pan; }); }
  function halt() { if (!playing) return null; cancelAnimationFrame(raf); playing.sources.forEach(s => { try { s.stop(); } catch (e) { /* already ended */ } }); try { playing.master.disconnect(); } catch (e) { /* gone */ } const was = playing; playing = null; return was; }
  function now() { return Math.max(0, smp(secs(playing.from) + (ctx.currentTime - playing.t0))); }
  function pause() { if (!playing) return; head = now(); halt(); draw(); }
  function stop() { const was = halt(); if (was) head = was.began; draw(); }
  async function restart() { const began = playing ? playing.began : head; halt(); await play(); if (playing) playing.began = began; }      // the caller sets `head` first
  function tick() {
    if (!playing) return;
    head = now();
    if (head >= endOf() + smp(0.2)) { const was = halt(); head = endOf(); if (was) draw(); return; }
    placeHead();
    const sc = root.querySelector('.al-scroll'), x = HEAD + X(head); if (sc && (x > sc.scrollLeft + sc.clientWidth - 40 || x < sc.scrollLeft + HEAD)) sc.scrollLeft = Math.max(0, x - HEAD - 60);
    raf = requestAnimationFrame(tick);
  }

  /* ---------- keys: only while Audio Lab is on screen and nobody is typing ---------- */
  document.addEventListener('keydown', ev => {
    if (!root || !T || !root.classList.contains('on') || /INPUT|TEXTAREA|SELECT/.test((ev.target.tagName || '')) || document.querySelector('#viewer.on, .ids-modal')) return;
    const k = ev.key.toLowerCase(), mod = ev.ctrlKey || ev.metaKey;
    if (k === ' ') { ev.preventDefault(); playing ? pause() : play(); }
    else if (mod && k === 'z' && !ev.shiftKey) { ev.preventDefault(); step(undo, redo); }
    else if (mod && (k === 'y' || (k === 'z' && ev.shiftKey))) { ev.preventDefault(); step(redo, undo); }
    else if (mod && k === 'd') { ev.preventDefault(); duplicate(); }
    else if (!mod && k === 's') split();
    else if (!mod && k === 'm') addMarker();
    else if (k === 'delete' || k === 'backspace') { ev.preventDefault(); remove(); }
    else if (k === 'home') seek(0);
    else if (k === 'end') seek(endOf());
  });
  window.addEventListener('beforeunload', () => { if (saveTimer && T && !conflict) save(); });

  window.AudioLab = {
    async show(element, project) {
      root = element;
      const a = project && project.assist && project.assist.analysis;
      songTempo = a && a.tempo ? { bpm: a.tempo, first: (a.beats && a.beats[0]) || 0 } : null;
      if (!project || !project.id) { root.innerHTML = '<p class="hint">Open a project to use Audio Lab.</p>'; return; }
      if (pid === project.id && T && root.querySelector('.al')) { draw(); return; }      // coming back to the tab: keep everything as it was
      if (playing) halt();
      if (saveTimer && T) await save();
      pid = project.id; head = 0; buffers = {}; conflict = false;
      await load();
    },
    hide() { if (playing) pause(); },
    _state: () => ({ T, head, px, sel: [...sel], undo: undo.length, redo: redo.length, playing: !!playing, assets: Object.keys(assets).length }),
  };
})();
