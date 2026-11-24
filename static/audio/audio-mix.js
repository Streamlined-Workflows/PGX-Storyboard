/* SWIFT Director: Audio Lab's mixing and export panels.
 *
 * Loaded before audio-lab.js, which hands this file a small set of functions (`core`) and calls back into it:
 *   draw()            redraws the clip settings, effects and mixer panels under the timeline
 *   meters(levels)    called on every frame of playback with the loudest recent point per track and for the mix
 *   exportDialog()    opens the export window
 *   close()           closes the export window
 * Nothing here plays or changes sound itself. Every change is an instruction stored on the timeline.
 */
window.AudioLabMix = function (core) {
  'use strict';
  const { el, esc, say, call, uid, secs, smp, clock } = core;
  /* The effects, in plain words. Ranges and defaults come from the server (info.effects). */
  const FX = {
    eq: { name: 'EQ', hint: 'Raise or lower the low, middle and high parts of the sound.', params: [['low_db', 'Low', 'dB', 0.5], ['low_hz', 'Low: below', 'Hz', 10], ['mid_db', 'Middle', 'dB', 0.5], ['mid_hz', 'Middle: around', 'Hz', 50], ['high_db', 'High', 'dB', 0.5], ['high_hz', 'High: above', 'Hz', 100]] },
    compressor: { name: 'Compressor', hint: 'Evens out loud and quiet moments by turning the loud ones down.', params: [['threshold_db', 'Works above', 'dB', 1], ['ratio', 'Strength', ': 1', 0.5], ['attack_ms', 'Reacts within', 'ms', 0.1], ['release_ms', 'Lets go after', 'ms', 10], ['makeup_db', 'Level added back', 'dB', 0.5]] },
    reverb: { name: 'Reverb', hint: 'Puts the sound in a room. The export runs on until the room has died away.', params: [['size', 'Room size', '', 0.05], ['decay_s', 'Dies away in', 's', 0.1], ['mix', 'Amount', '', 0.05]] },
  };
  const FLOOR = -60, TOP = 6;                                   // the range a meter shows, in dB
  const toDb = v => v > 0 ? 20 * Math.log10(v) : -Infinity;
  const fmtDb = v => (v > 0 ? '+' : '') + (Math.round(v * 10) / 10) + ' dB';
  let held = {}, over = false, modal = null, poll = null, lastExports = [];

  const T = () => core.T;
  const picked = () => [...core.sel].map(core.find).filter(Boolean);
  const editable = () => picked().filter(x => !x.t.locked && !x.c.locked);

  /* ---------- which chain of effects is open ---------- */
  function target() {
    const f = core.fxTarget; if (!f) return null;
    if (f.kind === 'master') return { owner: T().master, name: 'the whole mix', locked: false };
    if (f.kind === 'track') { const t = T().tracks.find(x => x.id === f.id); return t ? { owner: t, name: 'track “' + t.name + '”', locked: false } : null; }
    const x = core.find(f.id); return x ? { owner: x.c, name: 'clip “' + (x.c.label || (core.assets[x.c.asset_id] || {}).name || 'clip') + '”', locked: x.t.locked || x.c.locked } : null;
  }
  const fxCount = owner => { const n = (owner.effects || []).filter(f => f.on).length; return n ? 'Effects (' + n + ')' : 'Effects'; };
  const openFx = (kind, id) => { const f = core.fxTarget; core.fxTarget = f && f.kind === kind && f.id === id ? null : { kind, id }; core.draw(); };

  /* ---------- drawing ---------- */
  function draw() {
    const box = core.root && core.root.querySelector('.al-panels'); if (!box || !T()) return;
    const focus = document.activeElement && box.contains(document.activeElement) ? document.activeElement.dataset.k : null;
    box.innerHTML = '';
    if (core.fxTarget && !target()) core.fxTarget = null;
    if (picked().length) box.appendChild(clipCard());
    if (core.fxTarget) box.appendChild(fxCard());
    if (core.showMixer) box.appendChild(mixerCard());
    if (focus) { const again = box.querySelector(`[data-k="${focus}"]`); if (again) again.focus(); }
  }

  /* A number box or tick box that makes one change when it is committed. */
  function commit(input, fn) { input.onchange = () => core.edit(() => fn(input.type === 'checkbox' ? input.checked : input.type === 'text' ? input.value : +input.value)); }
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, isFinite(v) ? v : lo));

  function clipCard() {
    const all = picked(), list = editable(), one = all.length === 1 ? all[0].c : null, c = (list[0] || all[0]).c, off = !list.length;
    const same = k => list.every(x => x.c[k] === c[k]);
    const card = el(`<div class="al-card al-clipcard"><div class="al-cardhead"><b>${one ? 'Clip' : all.length + ' clips'}</b>${one ? `<span class="hint">starts ${clock(one.start)} · lasts ${clock(one.length)}</span>` : ''}${off ? '<span class="hint">Locked. Unlock the clip or its track to change it.</span>' : ''}</div>
      <div class="al-fields">
        ${one ? `<label>Name<input data-k="c-label" class="al-c-label" type="text" maxlength="120" value="${esc(one.label)}" placeholder="${esc((core.assets[one.asset_id] || {}).name || '')}"></label>` : ''}
        <label>Level <output class="al-c-gainout">${same('gain_db') ? fmtDb(c.gain_db) : 'mixed'}</output><input data-k="c-gain" class="al-c-gain" type="range" min="-60" max="24" step="0.5" value="${c.gain_db}"></label>
        <label>Fade in (seconds)<input data-k="c-fi" class="al-c-fi" type="number" min="0" step="0.05" value="${+secs(c.fade_in).toFixed(3)}"></label>
        <label>Fade out (seconds)<input data-k="c-fo" class="al-c-fo" type="number" min="0" step="0.05" value="${+secs(c.fade_out).toFixed(3)}"></label>
        <label title="1 is normal. 2 plays twice as fast, so the clip becomes half as long.">Speed<input data-k="c-speed" class="al-c-speed" type="number" min="0.25" max="4" step="0.05" value="${c.speed}"></label>
        <label title="In semitones. 12 is an octave up.">Pitch (semitones)<input data-k="c-pitch" class="al-c-pitch" type="number" min="-24" max="24" step="1" value="${c.pitch}"></label>
        <label class="al-tick2"><input data-k="c-rev" class="al-c-rev" type="checkbox"${c.reverse ? ' checked' : ''}> Reverse</label>
        <label class="al-tick2"><input data-k="c-mute" class="al-c-mute" type="checkbox"${c.muted ? ' checked' : ''}> Mute</label>
        <label class="al-tick2"><input data-k="c-lock" class="al-c-lock" type="checkbox"${all.every(x => x.c.locked) ? ' checked' : ''}> Lock</label>
        ${one ? `<button data-k="c-fx" class="small al-c-fx${core.fxTarget && core.fxTarget.kind === 'clip' && core.fxTarget.id === one.id ? ' on' : ''}" type="button">${fxCount(one)}</button>` : ''}
      </div>
      ${c.speed !== 1 || c.pitch !== 0 ? '<p class="hint al-note">Playback here is a preview: a speed change is heard like a tape, with the pitch moving too, and a pitch change is not heard. The export does both properly.</p>' : ''}</div>`);
    const q = s => card.querySelector(s), each = fn => list.forEach(x => fn(x.c));
    if (off) card.querySelectorAll('input:not(.al-c-lock), button').forEach(i => i.disabled = true);
    if (one) commit(q('.al-c-label'), v => { one.label = v.trim().slice(0, 120); });
    core.tweak(q('.al-c-gain'), v => { each(k => { k.gain_db = v; }); q('.al-c-gainout').textContent = fmtDb(v); });
    const fades = (k, fi, fo) => { k.fade_in = clamp(fi, 0, k.length); k.fade_out = clamp(fo, 0, k.length - k.fade_in); };
    commit(q('.al-c-fi'), v => each(k => fades(k, smp(clamp(v, 0, 3600)), k.fade_out)));
    commit(q('.al-c-fo'), v => each(k => { const fo = clamp(smp(clamp(v, 0, 3600)), 0, k.length); k.fade_out = fo; k.fade_in = Math.min(k.fade_in, k.length - fo); }));
    /* Changing the speed keeps the same stretch of sound and changes how long the clip lasts. */
    commit(q('.al-c-speed'), v => each(k => { const sp = clamp(v, 0.25, 4), through = core.used(k); k.speed = sp; k.length = Math.max(1, Math.round(through / sp)); fades(k, k.fade_in, k.fade_out); }));
    commit(q('.al-c-pitch'), v => each(k => { k.pitch = clamp(Math.round(v), -24, 24); }));
    commit(q('.al-c-rev'), v => each(k => { k.reverse = v; }));
    commit(q('.al-c-mute'), v => each(k => { k.muted = v; }));
    q('.al-c-lock').onchange = ev => core.edit(() => all.filter(x => !x.t.locked).forEach(x => { x.c.locked = ev.target.checked; }));
    if (one && !off) q('.al-c-fx').onclick = () => openFx('clip', one.id);
    return card;
  }

  function fxCard() {
    const t = target(), chain = t.owner.effects, spec = core.info.effects || {};
    const card = el(`<div class="al-card al-fxcard"><div class="al-cardhead"><b>Effects on ${esc(t.name)}</b><span class="hint">Applied from top to bottom.</span><span class="al-grow"></span>
      <select data-k="fx-add" class="al-fx-add" aria-label="Add an effect"><option value="">Add an effect…</option>${Object.keys(FX).filter(k => spec[k]).map(k => `<option value="${k}">${FX[k].name}</option>`).join('')}</select><button class="small ghost al-fx-close" type="button" title="Close">✕</button></div><div class="al-fxlist"></div></div>`);
    const list = card.querySelector('.al-fxlist');
    if (!chain.length) list.appendChild(el('<p class="hint">No effects yet. Add one above.</p>'));
    chain.forEach((fx, i) => {
      const def = FX[fx.type], row = el(`<div class="al-fx${fx.on ? '' : ' al-fxoff'}"><div class="al-fxhead"><label class="al-tick2"><input data-k="fx-on-${fx.id}" class="al-fx-on" type="checkbox"${fx.on ? ' checked' : ''}> <b>${def.name}</b></label><span class="hint">${def.hint}</span><span class="al-grow"></span>
        <button class="small ghost al-fx-up" type="button" title="Earlier"${i === 0 ? ' disabled' : ''}>↑</button><button class="small ghost al-fx-down" type="button" title="Later"${i === chain.length - 1 ? ' disabled' : ''}>↓</button><button class="small ghost al-fx-reset" type="button" title="Back to the starting settings">Reset</button><button class="small ghost al-fx-del" type="button" title="Remove this effect">Remove</button></div><div class="al-fxparams"></div></div>`);
      const params = row.querySelector('.al-fxparams');
      def.params.forEach(([key, label, unit, stepSize]) => {
        const [lo, hi] = spec[fx.type][key], show = v => (unit === '' ? Math.round(v * 100) + '%' : (Math.round(v * 100) / 100) + (unit === ': 1' ? ' : 1' : ' ' + unit));
        const p = el(`<label>${label} <output>${show(fx.params[key])}</output><input data-k="fx-${fx.id}-${key}" type="range" min="${lo}" max="${hi}" step="${stepSize}" value="${fx.params[key]}"></label>`);
        core.tweak(p.querySelector('input'), v => { fx.params[key] = v; p.querySelector('output').textContent = show(v); });
        params.appendChild(p);
      });
      const q = s => row.querySelector(s);
      commit(q('.al-fx-on'), v => { fx.on = v; });
      q('.al-fx-up').onclick = () => core.edit(() => chain.splice(i - 1, 0, chain.splice(i, 1)[0]));
      q('.al-fx-down').onclick = () => core.edit(() => chain.splice(i + 1, 0, chain.splice(i, 1)[0]));
      q('.al-fx-reset').onclick = () => core.edit(() => { Object.keys(fx.params).forEach(k => { fx.params[k] = spec[fx.type][k][2]; }); });
      q('.al-fx-del').onclick = () => core.edit(() => chain.splice(i, 1));
      list.appendChild(row);
    });
    const add = card.querySelector('.al-fx-add');
    add.onchange = () => { const type = add.value; if (!type) return; if (chain.length >= 8) { add.value = ''; return say('A chain holds up to 8 effects.'); }
      core.edit(() => chain.push({ id: uid(), type, on: true, params: Object.fromEntries(Object.entries(spec[type]).map(([k, v]) => [k, v[2]])) })); };
    card.querySelector('.al-fx-close').onclick = () => { core.fxTarget = null; core.draw(); };
    if (t.locked) card.querySelectorAll('input, select, button:not(.al-fx-close)').forEach(i => i.disabled = true);
    return card;
  }

  function mixerCard() {
    const tl = T(), solo = tl.tracks.some(t => t.solo), is = (kind, id) => core.fxTarget && core.fxTarget.kind === kind && core.fxTarget.id === id;
    const card = el(`<div class="al-card al-mixer"><div class="al-cardhead"><b>Mixer</b><span class="hint">Meters show the loudest recent moment while playing. Nothing is turned down for you: if the mix goes over full level it is marked, and the export says by how much.</span></div><div class="al-strips"></div></div>`);
    const strips = card.querySelector('.al-strips');
    tl.tracks.forEach(t => {
      const quiet = solo ? !t.solo : t.mute;
      const s = el(`<div class="al-strip${quiet ? ' al-stripquiet' : ''}" style="border-top-color:${core.color(t)}"><b class="al-stripname" title="${esc(t.name)}">${esc(t.name)}</b>
        <div class="al-faderrow"><div class="al-meter" data-meter="${t.id}" title="Level"><i></i></div><input data-k="m-vol-${t.id}" class="al-fader" type="range" min="-60" max="12" step="0.5" value="${t.volume_db}" aria-label="Volume of ${esc(t.name)}"></div>
        <output class="al-dbout">${fmtDb(t.volume_db)}</output>
        <input data-k="m-pan-${t.id}" class="al-mpan" type="range" min="-1" max="1" step="0.05" value="${t.pan}" aria-label="Balance of ${esc(t.name)}" title="Balance: left or right. Double-click to centre.">
        <div class="al-stripbtns"><button data-k="m-m-${t.id}" class="small al-mm${t.mute ? ' on' : ''}" type="button" title="Mute" aria-pressed="${t.mute}">M</button><button data-k="m-s-${t.id}" class="small al-ms${t.solo ? ' on' : ''}" type="button" title="Solo" aria-pressed="${t.solo}">S</button></div>
        <button data-k="m-fx-${t.id}" class="small al-mfx${is('track', t.id) ? ' on' : ''}" type="button">${fxCount(t)}</button></div>`);
      const q = x => s.querySelector(x);
      core.tweak(q('.al-fader'), v => { t.volume_db = v; q('.al-dbout').textContent = fmtDb(v); });
      core.tweak(q('.al-mpan'), v => { t.pan = v; });
      q('.al-mpan').ondblclick = () => core.edit(() => { t.pan = 0; });
      q('.al-fader').ondblclick = () => core.edit(() => { t.volume_db = 0; });
      q('.al-mm').onclick = () => core.edit(() => { t.mute = !t.mute; });
      q('.al-ms').onclick = () => core.edit(() => { t.solo = !t.solo; });
      q('.al-mfx').onclick = () => openFx('track', t.id);
      strips.appendChild(s);
    });
    const m = el(`<div class="al-strip al-master"><b class="al-stripname">Master</b>
      <div class="al-faderrow"><div class="al-meter" data-meter="master:0" title="Left"><i></i></div><div class="al-meter" data-meter="master:1" title="Right"><i></i></div><input data-k="m-vol-master" class="al-fader" type="range" min="-60" max="12" step="0.5" value="${tl.master.volume_db}" aria-label="Master volume"></div>
      <output class="al-dbout">${fmtDb(tl.master.volume_db)}</output>
      <button class="small al-over${over ? ' on' : ''}" type="button" title="Lights when the mix goes past full level, where an export would be clipped. Click to clear.">Over</button>
      <span class="hint al-peak">${held.master != null && held.master > -Infinity ? 'Loudest ' + fmtDb(held.master) : 'Loudest –'}</span>
      <button data-k="m-fx-master" class="small al-mfx${is('master') ? ' on' : ''}" type="button">${fxCount(tl.master)}</button></div>`);
    core.tweak(m.querySelector('.al-fader'), v => { tl.master.volume_db = v; m.querySelector('.al-dbout').textContent = fmtDb(v); });
    m.querySelector('.al-fader').ondblclick = () => core.edit(() => { tl.master.volume_db = 0; });
    m.querySelector('.al-over').onclick = () => { over = false; held = {}; core.draw(); };
    m.querySelector('.al-mfx').onclick = () => openFx('master');
    strips.appendChild(m);
    return card;
  }

  /* ---------- meters ---------- */
  function meters(levels) {
    const box = core.root && core.root.querySelector('.al-mixer');
    if (!levels) { if (box) box.querySelectorAll('.al-meter i').forEach(i => { i.style.height = '0'; }); return; }
    const top = Math.max(...levels.master), topDb = toDb(top);
    if (held.master == null || topDb > held.master) held.master = topDb;
    if (top > 1) over = true;
    if (!box) return;
    box.querySelectorAll('.al-meter').forEach(mt => {
      const [id, ch] = mt.dataset.meter.split(':'), v = (levels[id] || [])[+ch || 0] || 0, d = toDb(v), bar = mt.firstElementChild;
      bar.style.height = clamp((d - FLOOR) / (TOP - FLOOR) * 100, 0, 100) + '%';
      bar.className = d > 0 ? 'al-hot' : d > -6 ? 'al-warm' : '';
    });
    const light = box.querySelector('.al-over'), peak = box.querySelector('.al-peak');
    if (light) light.classList.toggle('on', over);
    if (peak && held.master > -Infinity) peak.textContent = 'Loudest ' + fmtDb(held.master);
  }

  /* ---------- export ---------- */
  const EXT = { wav: 'WAV', flac: 'FLAC', mp3: 'MP3' };
  const size = b => b == null ? '' : b > 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
  function close() { clearTimeout(poll); poll = null; if (modal) modal.remove(); modal = null; }
  document.addEventListener('keydown', ev => { if (modal && ev.key === 'Escape') close(); });

  function exportDialog() {
    close();
    const tl = T(), ex = core.info.export || { formats: ['wav'], sample_rates: [48000], mp3_rates: [320] }, end = core.endOf(), sel = picked();
    const from = sel.length ? Math.min(...sel.map(x => x.c.start)) : Math.min(core.head, end), to = sel.length ? Math.max(...sel.map(x => x.c.start + x.c.length)) : end;
    modal = el(`<div class="al-modal" role="dialog" aria-modal="true" aria-label="Export audio"><div class="al-modalbox">
      <div class="al-cardhead"><h2>Export audio</h2><span class="al-grow"></span><button class="small ghost al-x" type="button" title="Close">✕</button></div>
      <p class="hint">Makes a new file from the timeline as it is now, with every level, fade and effect applied. Your original sounds are not changed. The file stays on the server until you download or remove it.</p>
      <div class="al-fields al-exform">
        <label>What<select class="al-e-what"><option value="mix">The full mix</option><option value="stems">Each track as its own file (a zip)</option><option value="range">Part of the timeline</option></select></label>
        <label class="al-e-range" hidden>From (seconds)<input class="al-e-from" type="number" min="0" step="0.01" value="${+secs(from).toFixed(3)}"></label>
        <label class="al-e-range" hidden>To (seconds)<input class="al-e-to" type="number" min="0" step="0.01" value="${+secs(to).toFixed(3)}"></label>
        <label>File type<select class="al-e-format">${ex.formats.map(f => `<option value="${f}">${EXT[f]}${f === 'wav' ? ' (full quality, largest)' : f === 'flac' ? ' (full quality, smaller)' : ' (smallest, some quality lost)'}</option>`).join('')}</select></label>
        <label class="al-e-bitsbox">Detail<select class="al-e-bits"><option value="16">16-bit (standard)</option><option value="24">24-bit (for further editing)</option></select></label>
        <label class="al-e-kbpsbox" hidden>MP3 quality<select class="al-e-kbps">${ex.mp3_rates.map(k => `<option value="${k}"${k === 320 ? ' selected' : ''}>${k} kbps</option>`).join('')}</select></label>
        <label>Sample rate<select class="al-e-rate">${ex.sample_rates.map(r => `<option value="${r}"${r === tl.sample_rate ? ' selected' : ''}>${r / 1000} kHz${r === 48000 ? ' (video)' : ' (CD, music services)'}</option>`).join('')}</select></label>
        <label>Name<input class="al-e-name" type="text" maxlength="80" value="mix"></label>
      </div>
      <div class="al-exgo"><button class="primary al-e-go" type="button">Export</button><span class="hint al-e-says"></span></div>
      <h3>Exports of this project</h3><div class="al-exlist"><p class="hint">Loading…</p></div></div></div>`);
    const q = s => modal.querySelector(s);
    const shape = () => { const what = q('.al-e-what').value, f = q('.al-e-format').value; modal.querySelectorAll('.al-e-range').forEach(l => l.hidden = what !== 'range'); q('.al-e-bitsbox').hidden = f === 'mp3'; q('.al-e-kbpsbox').hidden = f !== 'mp3'; };
    q('.al-e-what').onchange = q('.al-e-format').onchange = shape; shape();
    q('.al-x').onclick = close; modal.onpointerdown = ev => { if (ev.target === modal) close(); };
    q('.al-e-go').onclick = async () => {
      const says = q('.al-e-says'), go = q('.al-e-go'), what = q('.al-e-what').value;
      const ask = { project: core.pid, what, format: q('.al-e-format').value, bits: +q('.al-e-bits').value, kbps: +q('.al-e-kbps').value, sample_rate: +q('.al-e-rate').value, name: q('.al-e-name').value };
      if (what === 'range') { ask.start = smp(+q('.al-e-from').value || 0); ask.end = smp(+q('.al-e-to').value || 0); if (ask.end <= ask.start) { says.textContent = 'The end must be after the start.'; return; } }
      if (core.conflict) { says.textContent = 'This timeline was changed in another window. Load the latest version first.'; return; }
      go.disabled = true; says.textContent = 'Saving the timeline…';
      try { await core.save(); await call('POST', 'export', ask); says.textContent = 'Started. It appears below.'; await refresh(); }
      catch (e) { says.textContent = e.message; }
      go.disabled = false;
    };
    core.root.querySelector('.al').appendChild(modal);
    q('.al-e-name').focus();
    refresh();
  }

  async function refresh() {
    if (!modal) return;
    clearTimeout(poll);
    try { lastExports = (await call('GET', 'exports?project=' + encodeURIComponent(core.pid))).exports; } catch (e) { if (modal) modal.querySelector('.al-exlist').innerHTML = '<p class="hint">' + esc(e.message) + '</p>'; return; }
    if (!modal) return;
    const list = modal.querySelector('.al-exlist'); list.innerHTML = '';
    if (!lastExports.length) list.appendChild(el('<p class="hint">Nothing exported yet.</p>'));
    lastExports.forEach(x => {
      const busy = x.state === 'waiting' || x.state === 'running', kind = x.what === 'stems' ? x.tracks.length + (x.tracks.length === 1 ? ' track' : ' tracks') + ', zip' : x.what === 'range' ? 'part of the timeline' : 'full mix';
      const facts = [kind, EXT[x.format] + (x.bits ? ' ' + x.bits + '-bit' : x.kbps ? ' ' + x.kbps + ' kbps' : ''), x.sample_rate / 1000 + ' kHz', x.seconds != null ? clock(smp(x.seconds)) : '', size(x.bytes)].filter(Boolean).join(' · ');
      const state = x.state === 'done' ? '' : x.state === 'running' ? 'Working… ' + Math.round(x.progress * 100) + '%' : x.state === 'waiting' ? 'Waiting its turn' : x.state === 'failed' ? 'Failed' : 'Stopped';
      const file = x.name + (x.what === 'stems' ? ' stems.zip' : '.' + x.format);
      const row = el(`<div class="al-ex al-ex-${x.state}"><div class="al-exmain"><b>${esc(x.name)}</b><span class="hint">${esc(facts)}</span>
          ${x.state === 'done' && x.peak_db != null ? `<span class="hint">Loudest point ${fmtDb(x.peak_db)}</span>` : ''}${state ? `<span class="pill">${state}</span>` : ''}
          ${busy ? `<progress max="1" value="${x.progress}"></progress>` : ''}${x.note ? `<span class="al-exnote">${esc(x.note)}</span>` : ''}</div>
        <div class="al-exbtns">${x.state === 'done' ? `<a class="btn small al-dl" href="${core.API}export/file?project=${encodeURIComponent(core.pid)}&id=${x.id}" download="${esc(file)}">Download</a>` : ''}
          ${busy ? '<button class="small al-ex-stop" type="button">Stop</button>' : '<button class="small ghost al-ex-del" type="button" title="Remove this export from the server">Remove</button>'}</div></div>`);
      const act = (sel, route) => { const b = row.querySelector(sel); if (b) b.onclick = async () => { b.disabled = true; try { await call('POST', route, { project: core.pid, id: x.id }); } catch (e) { say(e.message); } refresh(); }; };
      act('.al-ex-stop', 'export/stop'); act('.al-ex-del', 'export/remove');
      list.appendChild(row);
    });
    if (lastExports.some(x => x.state === 'waiting' || x.state === 'running')) poll = setTimeout(refresh, 800);
  }

  return { draw, meters, exportDialog, close, _state: () => ({ over, held: held.master, exports: lastExports, open: !!modal }) };
};
