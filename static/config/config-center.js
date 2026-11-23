/* SWIFT Director: the Project Configuration Center at the top of Assisted Storyboard.
 *
 * Six collapsible sections of per-project settings. The page hands in the open project and a
 * function to call when something changes; the settings live in project.config and are saved with
 * the project. Choices and their labels come from the server (/api/config/info), so this file
 * holds no lists of its own.
 *
 * Each setting carries a small tag: "In use" if it changes what the application does today,
 * "Stored" if it is kept for a later milestone. Nothing here pretends to do more than it does.
 */
(function () {
  'use strict';
  let info = null;
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const remembered = () => { try { return JSON.parse(localStorage.getItem('sd.config.open') || '[]'); } catch (e) { return []; } };
  const remember = (list) => { try { localStorage.setItem('sd.config.open', JSON.stringify(list)); } catch (e) { /* private mode */ } };
  const get = (o, path) => path.split('.').reduce((v, k) => (v == null ? v : v[k]), o);
  const set = (o, path, value) => { const keys = path.split('.'), last = keys.pop(); keys.reduce((v, k) => (v[k] = v[k] || {}), o)[last] = value; };
  const label = (list, key) => (list.find(x => String(x.key) === String(key)) || {}).label || key;

  const tag = (path) => info.used.includes(path) ? '<span class="cc-tag cc-used" title="This setting changes what SWIFT Director does today">In use</span>'
                                                 : '<span class="cc-tag" title="Saved with the project. A later update will act on it">Stored</span>';
  const select = (path, list, text, cfg) => `<label class="cc-field"><span>${esc(text)} ${tag(path)}</span><select data-path="${path}">${list.map(o => `<option value="${esc(o.key)}"${String(o.key) === String(get(cfg, path)) ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select></label>`;
  const input = (path, text, cfg, more) => `<label class="cc-field${more && more.wide ? ' cc-wide' : ''}"><span>${esc(text)} ${tag(path)}</span><${more && more.area ? 'textarea rows="3"' : 'input'} data-path="${path}" ${more && more.number ? 'type="number" min="1" max="3600" step="1"' : ''} placeholder="${esc((more && more.hint) || '')}"${more && more.area ? `>${esc(get(cfg, path) || '')}</textarea>` : ` value="${esc(get(cfg, path) == null ? '' : get(cfg, path))}">`}</label>`;
  const check = (path, text, cfg) => `<label class="cc-check"><input type="checkbox" data-path="${path}"${get(cfg, path) ? ' checked' : ''}> <span>${esc(text)}</span> ${tag(path)}</label>`;

  function sections(cfg, project) {
    const id = cfg.identity, type = id.video_type, use = info.in_use, p = cfg.production;
    const role = (r) => { const u = use[r.key] || {}; return `<div class="cc-role"><b>${esc(r.label)}</b><span>${u.name ? esc(u.name) + (u.runtime ? ` <span class="hint">· ${esc(u.runtime)}</span>` : '') : '<span class="hint">Not available</span>'}</span><span class="cc-tag${u.ready ? ' cc-used' : ''}">${u.ready ? 'Auto' : u.name ? 'Not confirmed' : 'Not installed'}</span>${u.note ? `<div class="hint">${esc(u.note)}</div>` : ''}</div>`; };
    const s = project.settings || {};
    return [
      { key: 'identity', title: 'Project Identity', summary: `${label(info.video_types, type)} · ${label(info.ratings, id.rating)}`, body:
        `<div class="cc-grid">${select('identity.rating', info.ratings, 'Project Rating', cfg)}${select('identity.video_type', info.video_types, 'Primary Video Type', cfg)}</div>
         <div class="hint">The rating is SWIFT Director's own classification, not an official film rating. It is saved with the project so filtering rules can be applied against it later; it does not change what is generated yet.</div>` +
        (type === 'story' ? `<div class="cc-grid">${select('identity.story.type', info.story_types, 'Story Type', cfg)}${select('identity.story.subtype', info.story_subtypes, 'Story Subtype', cfg)}${id.story.subtype === 'in_between' ? select('identity.story.in_between_purpose', info.in_between, 'In-between Purpose', cfg) : ''}</div>
           ${id.story.subtype === 'in_between' ? '<div class="hint">An In-between video is a bridge between larger story events. Linking it to the videos before and after it arrives with Production Collections.</div>' : ''}
           <div class="cc-notice">Story projects can be set up here, but Assisted Storyboard still starts from a song. Planning from a written story, script or outline arrives in a later update.</div>` : '') +
        (type === 'music_video' ? `<div class="cc-grid">${select('identity.music.type', info.music_types, 'Music Video Type', cfg)}${select('identity.music.subtype', info.music_subtypes, 'Music Video Subtype', cfg)}</div>
           <div class="hint">The subtype shapes the story concept the next time you press Write story concept. Re-enactment of Events is how stories have been written up to now.</div>` : '') +
        (type === 'commercial' ? `<div class="cc-grid">${select('identity.commercial.type', info.commercial_types, 'Commercial Type', cfg)}${input('identity.commercial.runtime', 'Runtime in seconds', cfg, { number: true, hint: 'e.g. 30' })}
           ${input('identity.commercial.audience', 'Target audience', cfg, { wide: true, hint: 'Who this is for' })}${input('identity.commercial.message', 'Key message', cfg, { wide: true, area: true, hint: 'The one thing the viewer should take away' })}${input('identity.commercial.call_to_action', 'Call to action', cfg, { wide: true, hint: 'e.g. Enlist at any Accord station' })}</div>
           <div class="cc-notice">Commercial projects can be set up here, but Assisted Storyboard still starts from a song. Planning from a product brief arrives in a later update.</div>` : '') },
      { key: 'models', title: 'AI Model Configuration', summary: 'Auto for every role', body:
        `<div class="hint">What performs each job today. Every role is on Auto, which means the one model SWIFT Director has a working setup for. Choosing between models arrives in the next milestone.</div>
         <div class="cc-roles">${info.roles.filter(r => !['stt', 'tts'].includes(r.key)).map(role).join('')}</div>` },
      { key: 'video', title: 'Video Generation', summary: `${p.aspect === 'custom' ? (p.custom_aspect || 'Custom') : p.aspect} · ${label(info.resolutions, p.export_resolution)} · ${p.target_fps} fps`, body:
        `<div class="cc-grid">${select('production.aspect', info.aspects, 'Aspect Ratio', cfg)}${p.aspect === 'custom' ? input('production.custom_aspect', 'Custom ratio', cfg, { hint: 'e.g. 4:5' }) : ''}${select('production.export_resolution', info.resolutions, 'Output Resolution', cfg)}${select('production.target_fps', info.fps, 'Target FPS', cfg)}${select('production.platform', info.platforms, 'Intended Platform', cfg)}${select('production.environment', info.environments, 'Generation Environment', cfg)}</div>
         <div class="cc-notice">These describe the finished video you want. Clips are generated today at ${esc(s.width || 832)} × ${esc(s.height || 480)}, 16 frames a second for story shots and 25 for singing shots, on this server. Reaching a larger size or a higher frame rate needs an upscaling step that is not installed yet, and only Local generation exists.</div>` },
      { key: 'audio', title: 'Audio and Speech', summary: use.tts && use.tts.ready ? 'Speech in and out' : 'Speech-to-text only', body:
        `<div class="hint">Speech-to-text listens to the song for lyrics and timing. Text-to-speech will make narration, dialogue and temporary voice tracks.</div>
         <div class="cc-roles">${info.roles.filter(r => ['stt', 'tts'].includes(r.key)).map(role).join('')}</div>` },
      { key: 'production', title: 'Production Settings', summary: `${label(info.directions, p.visual_direction)} · ${label(info.details, p.storyboard_detail)} detail`, body:
        `<div class="cc-grid">${select('production.visual_direction', info.directions, 'Visual Direction', cfg)}${select('production.storyboard_detail', info.details, 'Storyboard Detail', cfg)}${input('production.visual_notes', 'More about the look', cfg, { wide: true, area: true, hint: 'Anything that describes the visual direction' })}</div>
         <div class="hint">Storyboard Detail sets how much each key frame description says about framing, light and composition the next time you press Write the shots. Standard is how shots have been written up to now.</div>
         <div class="cc-sub">Continuity</div><div class="cc-checks">${info.continuity.map(c => check('production.continuity.' + c.key, c.label, cfg)).join('')}</div>` },
      { key: 'workflow', title: 'Workflow and Approval Controls', summary: `${info.workflow.filter(w => cfg.workflow[w.key]).length} of ${info.workflow.length} on`, body:
        `<div class="hint">These record how you want to work. The approvals that exist today (approving the story, locking story lines and key frames, picking a clip) keep working as they do; these switches start to act as each stage gains its own approval step.</div>
         <div class="cc-checks">${info.workflow.map(w => check('workflow.' + w.key, w.label, cfg)).join('')}</div>` },
    ];
  }

  async function render(box, project, hooks) {
    if (!box) return;
    if (!info) { try { info = await (await fetch('/api/config/info')).json(); } catch (e) { box.textContent = 'The project configuration could not be loaded.'; return; } }
    if (!hooks.force && box.dataset.pid === project.id && box.contains(document.activeElement) && /INPUT|TEXTAREA/.test(document.activeElement.tagName) && document.activeElement.type !== 'checkbox') return;   // never redraw under someone's typing
    box.dataset.pid = project.id;
    const cfg = project.config = project.config || JSON.parse(JSON.stringify(info.defaults));
    const open = remembered();
    box.className = 'cc';
    box.innerHTML = `<div class="cc-head"><h2>Project Configuration</h2><span class="hint">Saved with this project.</span><span class="cc-grow"></span><span class="hint cc-msg" aria-live="polite"></span><button class="small cc-defaults" type="button" title="New projects will start with these settings. Existing projects are not changed.">Use these settings for new projects</button></div>` +
      sections(cfg, project).map(s => `<details class="cc-section" data-key="${s.key}"${open.includes(s.key) ? ' open' : ''}><summary><b>${esc(s.title)}</b><span class="hint">${esc(s.summary)}</span></summary><div class="cc-body">${s.body}</div></details>`).join('');
    box.querySelectorAll('details').forEach(d => d.addEventListener('toggle', () => remember([...box.querySelectorAll('details[open]')].map(x => x.dataset.key))));
    box.querySelectorAll('[data-path]').forEach(f => f.addEventListener('change', () => {
      const path = f.dataset.path;
      let value = f.type === 'checkbox' ? f.checked : f.type === 'number' ? (f.value === '' ? null : Number(f.value)) : f.value;
      if (path === 'production.target_fps') value = Number(value);
      if (path === 'identity.video_type' && value !== cfg.identity.video_type && hooks.hasApprovedWork && hooks.hasApprovedWork()) {
        const from = label(info.video_types, cfg.identity.video_type), to = label(info.video_types, value);
        if (!confirm(`Change this project from ${from} to ${to}?\n\nThe approved story, the cast and the planned shots were made for a ${from}. They are all kept, and nothing is deleted, but they may no longer fit and you may want to write them again.`)) { render(box, project, hooks); return; }
      }
      set(cfg, path, value);
      hooks.changed();
      if (f.tagName === 'SELECT' || f.type === 'checkbox') render(box, project, hooks);      // some choices reveal other fields
    }));
    box.querySelector('.cc-defaults').onclick = async () => {
      const msg = box.querySelector('.cc-msg');
      try {
        const r = await fetch('/api/config/defaults', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ config: cfg }) });
        if (!r.ok) throw new Error('The server did not accept them.');
        info.defaults = JSON.parse(JSON.stringify(cfg)); msg.textContent = 'Saved. New projects will start with these settings.';
      } catch (e) { msg.textContent = e.message; }
      setTimeout(() => { if (msg.isConnected) msg.textContent = ''; }, 6000);
    };
  }

  window.ConfigCenter = { render };
})();
