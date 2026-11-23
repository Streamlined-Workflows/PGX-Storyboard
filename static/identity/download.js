/* SWIFT Identity Studio: download a concept in the file types the person ticks.
 *
 * PNG is the picture as generated. JPEG and WebP are the same picture re-encoded. SVG is a tracing of the
 * mark (curves that approximate it). ICO and ICNS are icon files holding the mark at the standard sizes,
 * with the plain background removed. The Teams-ready white icon is the 32 x 32 outline Teams asks for.
 * One type downloads as that file; several download together as one .zip. Everything is made in the
 * browser and saved to the person's computer.
 */
(function () {
  'use strict';
  const T = () => window.IdentityTeams;
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const bytes = async (blob) => new Uint8Array(await blob.arrayBuffer());
  const TOLERANCE = 24;                                     // how strongly the plain background is removed for icon files

  const TYPES = [
    { id: 'png',  label: 'PNG',  hint: 'The picture exactly as generated.', on: true },
    { id: 'jpg',  label: 'JPEG', hint: 'Smaller file, no transparency.' },
    { id: 'webp', label: 'WebP', hint: 'Small file for websites.' },
    { id: 'svg',  label: 'SVG',  hint: 'A tracing of the mark that scales to any size. An approximation, best for flat shapes.' },
    { id: 'ico',  label: 'ICO',  hint: 'Windows icon: 16, 32, 48, 64, 128 and 256 pixels, background removed.' },
    { id: 'icns', label: 'ICNS', hint: 'macOS icon: 16 to 1024 pixels, background removed.' },
    { id: 'teams', label: 'Teams-ready white icon', hint: '32 × 32, white on transparent. Teams requires PNG for this, so it is saved as a .png, not an .ico.' },
  ];

  const square = (mark, size) => T().fit(mark, size, Math.round(size * 0.9));        // a little breathing room inside the icon
  const flat = (img, type, quality) => {                     // the whole picture, re-encoded
    const c = T().sheet(img.naturalWidth, img.naturalHeight), x = c.getContext('2d');
    x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0);
    return new Promise(res => c.toBlob(res, type, quality));
  };

  async function ico(mark) {                                 // PNG-compressed entries, which Windows has read since Vista
    const sizes = [16, 32, 48, 64, 128, 256], pngs = [];
    for (const s of sizes) pngs.push(await bytes(await T().blobOf(square(mark, s))));
    const out = new Uint8Array(6 + 16 * sizes.length + pngs.reduce((n, p) => n + p.length, 0)), v = new DataView(out.buffer);
    v.setUint16(2, 1, true); v.setUint16(4, sizes.length, true);
    let at = 6 + 16 * sizes.length;
    sizes.forEach((s, i) => {
      const e = 6 + 16 * i;
      out[e] = s === 256 ? 0 : s; out[e + 1] = s === 256 ? 0 : s; v.setUint16(e + 4, 1, true); v.setUint16(e + 6, 32, true);
      v.setUint32(e + 8, pngs[i].length, true); v.setUint32(e + 12, at, true); out.set(pngs[i], at); at += pngs[i].length;
    });
    return new Blob([out], { type: 'image/x-icon' });
  }

  async function icns(mark) {
    const kinds = [['icp4', 16], ['icp5', 32], ['icp6', 64], ['ic07', 128], ['ic08', 256], ['ic09', 512], ['ic10', 1024]], parts = [];
    for (const [type, s] of kinds) parts.push([type, await bytes(await T().blobOf(square(mark, s)))]);
    const total = 8 + parts.reduce((n, [, p]) => n + 8 + p.length, 0), out = new Uint8Array(total), v = new DataView(out.buffer);
    const tag = (at, text) => { for (let i = 0; i < 4; i++) out[at + i] = text.charCodeAt(i); };
    tag(0, 'icns'); v.setUint32(4, total);
    let at = 8;
    for (const [type, p] of parts) { tag(at, type); v.setUint32(at + 4, 8 + p.length); out.set(p, at + 8); at += 8 + p.length; }
    return new Blob([out], { type: 'image/icns' });
  }

  function svg(mark) {
    if (!window.ImageTracer) throw new Error('The tracing tool did not load.');
    const k = 768 / Math.max(mark.width, mark.height),   // trace at one working size: smoother curves from small marks, less work from big ones
    w = Math.max(1, Math.round(mark.width * k)), h = Math.max(1, Math.round(mark.height * k));
    const c = T().sheet(w, h), x = c.getContext('2d', { willReadFrequently: true }); x.imageSmoothingQuality = 'high'; x.drawImage(mark, 0, 0, w, h);
    const data = x.getImageData(0, 0, w, h);
    for (let i = 3; i < data.data.length; i += 4) data.data[i] = data.data[i] >= 128 ? 255 : 0;      // hard edges: soft ones would be traced as rings of faint colour
    const text = window.ImageTracer.imagedataToSVG(data, { numberofcolors: 8, colorquantcycles: 5, pathomit: 16, ltres: 0.1, qtres: 1, roundcoords: 1, strokewidth: 0, linefilter: true, viewbox: true, desc: false })
      .replace(/<path[^>]*opacity="0"[^>]*\/>/g, '');          // drop the shapes that only describe the transparent background
    return new Blob([text], { type: 'image/svg+xml' });
  }

  /* -> [[file name, Blob], …] for the ticked types */
  async function make(src, name, picked, say) {
    const img = new Image(); img.src = src; await img.decode();
    const needsMark = picked.some(t => ['svg', 'ico', 'icns', 'teams'].includes(t));
    const mark = needsMark ? T().cutOut(img, TOLERANCE) : null;
    if (needsMark && !mark) throw new Error('The picture is all background, so there is no mark to make an icon from.');
    const out = [];
    for (const t of picked) {
      say('Making ' + TYPES.find(x => x.id === t).label + '…');
      await new Promise(r => setTimeout(r, 20));              // let the message show before the heavy work
      if (t === 'png') out.push([name + '.png', await (await fetch(src)).blob()]);
      if (t === 'jpg') out.push([name + '.jpg', await flat(img, 'image/jpeg', 0.92)]);
      if (t === 'webp') { const b = await flat(img, 'image/webp', 0.92); if (!b || b.type !== 'image/webp') throw new Error('This browser cannot save WebP. Untick it, or use Chrome or Edge.'); out.push([name + '.webp', b]); }
      if (t === 'svg') out.push([name + '.svg', svg(mark)]);
      if (t === 'ico') out.push([name + '.ico', await ico(mark)]);
      if (t === 'icns') out.push([name + '.icns', await icns(mark)]);
      if (t === 'teams') out.push([name + '-teams-outline.png', await T().blobOf(T().whiteOnly(T().fit(mark, 32, 32)))]);
    }
    return out;
  }

  function open(concept) {
    const dialog = el(`<div class="ids ids-modal" role="dialog" aria-modal="true" aria-label="Download concept"><div class="ids-modal-box">
      <h2>Download</h2>
      <p class="hint">Tick the file types you want. One type downloads as that file; more than one downloads as a single .zip. Files are saved to this computer.</p>
      <div class="ids-types">${TYPES.map(t => `<label><input type="checkbox" value="${t.id}"${t.on ? ' checked' : ''}> <span><b>${t.label}</b><span class="hint">${t.hint}</span></span></label>`).join('')}</div>
      <div class="hint ids-dl-msg" aria-live="polite"></div>
      <div class="ids-acts"><button class="primary ids-dl-go" type="button">Download</button><button class="ghost ids-dl-close" type="button">Cancel</button></div>
    </div></div>`);
    document.body.appendChild(dialog);
    const msg = dialog.querySelector('.ids-dl-msg'), go = dialog.querySelector('.ids-dl-go');
    const close = () => { dialog.remove(); document.removeEventListener('keydown', esc); };
    const esc = (ev) => { if (ev.key === 'Escape') close(); };
    document.addEventListener('keydown', esc);
    dialog.addEventListener('click', ev => { if (ev.target === dialog) close(); });
    dialog.querySelector('.ids-dl-close').onclick = close;
    go.onclick = async () => {
      const picked = [...dialog.querySelectorAll('input:checked')].map(i => i.value);
      if (!picked.length) { msg.textContent = 'Tick at least one file type.'; return; }
      go.disabled = true;
      try {
        const files = await make(concept.src, concept.name, picked, t => msg.textContent = t);
        if (files.length === 1) T().save(files[0][1], files[0][0]);
        else { const list = []; for (const [n, b] of files) list.push([n, await bytes(b)]); T().save(T().zip(list), concept.name + '.zip'); }
        close();
      } catch (e) { msg.textContent = e.message; go.disabled = false; }
    };
    go.focus();
  }

  window.IdentityDownload = { open, make, TYPES };
})();
