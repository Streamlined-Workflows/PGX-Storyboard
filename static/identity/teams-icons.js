/* SWIFT Identity Studio: Microsoft Teams icon export.
 *
 * Turns one finished concept into the files a Teams app package needs:
 *   color.png       192 x 192, the symbol within the middle 96 x 96, on a solid or transparent square
 *   outline.png      32 x 32, white only, on a transparent background
 *   color32x32.png   32 x 32, full colour on transparent (optional; Outlook and Microsoft 365)
 *
 * Everything happens in the browser: the concept's plain background is removed, the mark is cropped
 * and scaled, and the files are downloaded to the person's computer. Nothing is written to the server.
 */
(function () {
  'use strict';
  const el = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const sheet = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };

  /* Remove the plain background. The background colour is read from the corners; a pixel's opacity grows with
     its distance from that colour, and edge pixels have the background's tint taken back out so no halo is left. */
  function cutOut(img, tolerance) {
    const c = sheet(img.naturalWidth, img.naturalHeight), x = c.getContext('2d', { willReadFrequently: true });
    x.drawImage(img, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height), p = d.data, W = c.width, H = c.height;
    const corners = [0, (W - 1) * 4, (H - 1) * W * 4, (H * W - 1) * 4], bg = [0, 1, 2].map(k => Math.round(corners.reduce((s, i) => s + p[i + k], 0) / 4));
    const lo = tolerance, hi = tolerance + 48;
    let x0 = W, y0 = H, x1 = -1, y1 = -1;
    for (let i = 0, n = 0; i < p.length; i += 4, n++) {
      if (p[i + 3] === 0) continue;
      const dist = Math.max(Math.abs(p[i] - bg[0]), Math.abs(p[i + 1] - bg[1]), Math.abs(p[i + 2] - bg[2]));
      const a = dist <= lo ? 0 : dist >= hi ? 1 : (dist - lo) / (hi - lo);
      if (a < 1 && a > 0) for (let k = 0; k < 3; k++) p[i + k] = Math.max(0, Math.min(255, Math.round((p[i + k] - bg[k] * (1 - a)) / a)));
      p[i + 3] = Math.round(p[i + 3] * a);
      if (p[i + 3] > 20) { const px = n % W, py = (n - px) / W; if (px < x0) x0 = px; if (px > x1) x1 = px; if (py < y0) y0 = py; if (py > y1) y1 = py; }
    }
    x.putImageData(d, 0, 0);
    if (x1 < 0) return null;                                   // nothing but background
    const w = x1 - x0 + 1, h = y1 - y0 + 1, out = sheet(w, h);
    out.getContext('2d').drawImage(c, x0, y0, w, h, 0, 0, w, h);
    return out;
  }

  /* Shrink in halving steps so small sizes stay crisp, then fit inside a box, centred. */
  function fit(mark, size, box) {
    let src = mark;
    const k = Math.min(box / mark.width, box / mark.height), w = Math.max(1, Math.round(mark.width * k)), h = Math.max(1, Math.round(mark.height * k));
    while (src.width / 2 >= w && src.height / 2 >= h) { const half = sheet(Math.ceil(src.width / 2), Math.ceil(src.height / 2)), hx = half.getContext('2d'); hx.imageSmoothingQuality = 'high'; hx.drawImage(src, 0, 0, half.width, half.height); src = half; }
    const out = sheet(size, size), ox = out.getContext('2d'); ox.imageSmoothingQuality = 'high';
    ox.drawImage(src, Math.round((size - w) / 2), Math.round((size - h) / 2), w, h);
    return out;
  }

  function whiteOnly(c) {                                      // keep the shape, make every pixel pure white
    const out = sheet(c.width, c.height), x = out.getContext('2d');
    x.drawImage(c, 0, 0); x.globalCompositeOperation = 'source-in'; x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height);
    return out;
  }

  function build(img, opts) {
    const mark = cutOut(img, opts.tolerance);
    if (!mark) return null;
    const color = sheet(192, 192), cx = color.getContext('2d');
    if (opts.background !== 'transparent') { cx.fillStyle = opts.colour; cx.fillRect(0, 0, 192, 192); }
    cx.drawImage(fit(mark, 192, 96), 0, 0);                    // the symbol sits in the middle 96 x 96, 48 px clear on every side
    return { 'color.png': color, 'outline.png': whiteOnly(fit(mark, 32, 32)), 'color32x32.png': fit(mark, 32, 32) };
  }

  /* A plain .zip (stored, not compressed: PNG files are already compressed). */
  const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = (b) => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function zip(files) {
    const parts = [], central = []; let offset = 0;
    const head = (sig, extra, name, crc, size) => { const b = new Uint8Array(extra + name.length), v = new DataView(b.buffer); v.setUint32(0, sig, true); return { b, v }; };
    for (const [name, data] of files) {
      const n = new TextEncoder().encode(name), crc = crc32(data);
      const l = head(0x04034b50, 30, n); l.v.setUint16(4, 20, true); l.v.setUint16(12, 0x21, true); l.v.setUint32(14, crc, true); l.v.setUint32(18, data.length, true); l.v.setUint32(22, data.length, true); l.v.setUint16(26, n.length, true); l.b.set(n, 30);
      const c = head(0x02014b50, 46, n); c.v.setUint16(4, 20, true); c.v.setUint16(6, 20, true); c.v.setUint16(14, 0x21, true); c.v.setUint32(16, crc, true); c.v.setUint32(20, data.length, true); c.v.setUint32(24, data.length, true); c.v.setUint16(28, n.length, true); c.v.setUint32(42, offset, true); c.b.set(n, 46);
      parts.push(l.b, data); central.push(c.b); offset += l.b.length + data.length;
    }
    const size = central.reduce((s, b) => s + b.length, 0), end = new Uint8Array(22), ev = new DataView(end.buffer);
    ev.setUint32(0, 0x06054b50, true); ev.setUint16(8, files.length, true); ev.setUint16(10, files.length, true); ev.setUint32(12, size, true); ev.setUint32(16, offset, true);
    return new Blob([...parts, ...central, end], { type: 'application/zip' });
  }

  const blobOf = (c) => new Promise(res => c.toBlob(res, 'image/png'));
  function save(blob, name) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }

  /* The panel: options on the left, the three files as they will look on the right. */
  async function open(box, concept) {
    box.innerHTML = '';
    const panel = el(`<section class="ids-teams">
      <div class="ids-head"><h2>Microsoft Teams icons</h2><span class="ids-grow"></span><button class="small ghost ids-t-close" type="button">Close</button></div>
      <p class="ids-lede">Made from the concept you chose. The files are saved to this computer, not the server.</p>
      <div class="ids-t-grid">
        <div class="ids-t-opts">
          <label>Colour icon background<select class="ids-t-bg"><option value="transparent">Transparent</option><option value="solid">Solid colour</option></select></label>
          <label class="ids-t-colour-row" hidden>Background colour<input type="color" class="ids-t-colour" value="${concept.colour || '#000000'}"></label>
          <label>Background removal <span class="ids-t-tol-val"></span><input type="range" class="ids-t-tol" min="4" max="120" value="24"></label>
          <div class="hint">Raise this if a pale haze is left around the mark. Lower it if light parts of the mark are disappearing.</div>
        </div>
        <div class="ids-t-out">
          <figure><div class="ids-t-tile ids-t-light"><canvas width="192" height="192" data-file="color.png"></canvas></div><figcaption><b>color.png</b> · 192 × 192 · symbol in the middle 96 × 96</figcaption></figure>
          <figure><div class="ids-t-tile ids-t-dark"><canvas width="192" height="192" data-file="color.png"></canvas></div><figcaption>The same file on a dark theme</figcaption></figure>
          <figure><div class="ids-t-tile ids-t-bar"><canvas width="32" height="32" data-file="outline.png" class="ids-t-big"></canvas><canvas width="32" height="32" data-file="outline.png"></canvas></div><figcaption><b>outline.png</b> · 32 × 32 · white on transparent (enlarged, and actual size)</figcaption></figure>
          <figure><div class="ids-t-tile ids-t-light"><canvas width="32" height="32" data-file="color32x32.png" class="ids-t-big"></canvas><canvas width="32" height="32" data-file="color32x32.png"></canvas></div><figcaption><b>color32x32.png</b> · 32 × 32 · optional, for Outlook and Microsoft 365</figcaption></figure>
        </div>
      </div>
      <div class="ids-acts"><button class="primary ids-t-zip" type="button">Download all three (.zip)</button><button class="small" data-one="color.png" type="button">color.png</button><button class="small" data-one="outline.png" type="button">outline.png</button><button class="small" data-one="color32x32.png" type="button">color32x32.png</button></div>
      <div class="hint ids-t-msg" aria-live="polite"></div>
      <div class="ids-note"><b>Check before you ship it.</b> The outline icon is the mark's whole silhouette in white. A detailed concept becomes a blob at this size; a simple one-shape mark works best, and a hand-drawn outline is better still. Teams adds its own border, so none is drawn here.</div>
    </section>`);
    box.appendChild(panel);
    const msg = panel.querySelector('.ids-t-msg'), img = new Image();
    img.src = concept.src;
    try { await img.decode(); } catch (e) { msg.textContent = 'The concept picture could not be loaded.'; return; }
    let files = null;
    const draw = () => {
      const bg = panel.querySelector('.ids-t-bg').value, tol = +panel.querySelector('.ids-t-tol').value;
      panel.querySelector('.ids-t-colour-row').hidden = bg !== 'solid'; panel.querySelector('.ids-t-tol-val').textContent = '(' + tol + ')';
      files = build(img, { background: bg, colour: panel.querySelector('.ids-t-colour').value, tolerance: tol });
      msg.textContent = files ? '' : 'Nothing is left after removing the background. Lower "Background removal".';
      panel.querySelectorAll('canvas[data-file]').forEach(c => { const x = c.getContext('2d'); x.clearRect(0, 0, c.width, c.height); if (files) x.drawImage(files[c.dataset.file], 0, 0); });
      panel.querySelectorAll('.ids-acts button').forEach(b => b.disabled = !files);
    };
    panel.querySelectorAll('.ids-t-opts select, .ids-t-opts input').forEach(i => i.addEventListener('input', draw));
    panel.querySelectorAll('[data-one]').forEach(b => b.onclick = async () => save(await blobOf(files[b.dataset.one]), b.dataset.one));
    panel.querySelector('.ids-t-zip').onclick = async () => {
      const list = [];
      for (const name of Object.keys(files)) list.push([name, new Uint8Array(await (await blobOf(files[name])).arrayBuffer())]);
      save(zip(list), (concept.name || 'teams') + '-teams-icons.zip');
    };
    panel.querySelector('.ids-t-close').onclick = () => { box.innerHTML = ''; };
    draw();
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  window.IdentityTeams = { open, build, zip };
})();
