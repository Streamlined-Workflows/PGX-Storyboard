/* Reference Generation: putting chosen pictures together as one reference sheet (design document, section 7).
 *
 * Nothing here asks a model for anything. The pictures are placed on a canvas as they are: each keeps its own
 * proportions, scaled down to fit and never stretched or enlarged past its own size. Text (the title, row names, view
 * names and specification panels) is drawn by the browser, so it is always spelled as typed.
 *
 *   ReferenceAssembly.plan(spec)  -> { width, height, scale, items }   where everything goes; no drawing
 *   ReferenceAssembly.draw(plan)  -> a canvas with the sheet on it
 *   ReferenceAssembly.length(cm, units) -> "1 m 70 cm" or "5 ft 6.9 in"
 *   ReferenceAssembly.toCm(big, small, units) -> centimetres from metres + centimetres, or feet + inches
 *
 * spec: { width, height (0 = as tall as the content), background ('#rrggbb' or null for see-through), margin, spacing,
 *         labels, align ('left' | 'center' | 'right'), title, accent, font, panelStyle ('boxed' | 'plain'),
 *         sections: [{ name, blocks: [{ label, sub, fraction (0.2 to 1 of the sheet's width),
 *                     images: [{ img, caption, id }], panel: { label, sub, lines: [{ name, value }] } | null }] }] }
 * Blocks go left to right and wrap to a new line when the next one does not fit, sections top to bottom.
 */
window.ReferenceAssembly = (function () {
  'use strict';
  const CM_FT = 30.48, CM_IN = 2.54;
  const trim = n => String(Math.round(n * 10) / 10);
  function length(cm, units) {
    if (!(cm > 0)) return '';
    if (units === 'imperial') { let ft = Math.floor(cm / CM_FT), inch = Math.round((cm - ft * CM_FT) / CM_IN * 10) / 10; if (inch >= 12) { ft += 1; inch = 0; } return (ft ? ft + ' ft ' : '') + trim(inch) + ' in'; }
    const m = Math.floor(cm / 100), rest = Math.round((cm - m * 100) * 10) / 10; return m ? m + ' m' + (rest ? ' ' + trim(rest) + ' cm' : '') : trim(rest) + ' cm';
  }
  const toCm = (big, small, units) => Math.round(((+big || 0) * (units === 'imperial' ? CM_FT : 100) + (+small || 0) * (units === 'imperial' ? CM_IN : 1)) * 100) / 100;
  const split = (cm, units) => units === 'imperial' ? [Math.floor(cm / CM_FT), Math.round((cm - Math.floor(cm / CM_FT) * CM_FT) / CM_IN * 10) / 10] : [Math.floor(cm / 100), Math.round((cm - Math.floor(cm / 100) * 100) * 10) / 10];

  function ink(background) {              // dark writing on a light or see-through sheet, light writing on a dark one
    if (!background) return [17, 17, 17];
    const [r, g, b] = [1, 3, 5].map(i => parseInt(background.slice(i, i + 2), 16));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? [17, 17, 17] : [242, 242, 242];
  }
  function plan(spec) {
    const ctx = document.createElement('canvas').getContext('2d'), W = spec.width, M = spec.margin, G = spec.spacing, inner = W - 2 * M, items = [];
    const [r, g, b] = ink(spec.background), strong = `rgb(${r},${g},${b})`, soft = `rgba(${r},${g},${b},0.66)`, faint = `rgba(${r},${g},${b},0.3)`;
    const font = (px, weight) => `${weight || 400} ${Math.round(px)}px ${spec.font || 'sans-serif'}`;
    const unit = W / 2048, T = { title: 44 * unit, section: 22 * unit, label: 28 * unit, sub: 20 * unit, caption: 20 * unit, body: 21 * unit };
    const wrap = (text, f, max) => { ctx.font = f; const out = []; String(text).split('\n').forEach(par => { let line = ''; par.split(/\s+/).forEach(word => { const next = line ? line + ' ' + word : word; if (line && ctx.measureText(next).width > max) { out.push(line); line = word; } else line = next; }); out.push(line); }); return out; };
    const text = (t, x, y, f, color, max) => { const lines = max ? wrap(t, f, max) : [t], px = parseInt(f.match(/(\d+)px/)[1], 10); lines.forEach((l, i) => items.push({ type: 'text', text: l, x, y: y + i * px * 1.35, font: f, color })); return lines.length * px * 1.35; };
    let y = M;
    if (spec.title) { y += text(spec.title, M, y, font(T.title, 700), strong, inner); items.push({ type: 'rect', x: M, y: y + 2 * unit, w: inner, h: Math.max(2, 4 * unit), fill: spec.accent || strong }); y += G + 6 * unit; }
    spec.sections.forEach(section => {
      const blocks = section.blocks.filter(bl => bl.images.length || bl.panel); if (!blocks.length) return;
      if (spec.labels) y += text(section.name.toUpperCase(), M, y, font(T.section, 600), soft) + G * 0.4;
      const lines = []; let line = [], used = 0;
      blocks.forEach(bl => { const f = Math.max(0.2, Math.min(1, bl.fraction || 1)); if (line.length && used + f > 1.001) { lines.push(line); line = []; used = 0; } line.push([bl, f]); used += f; });
      if (line.length) lines.push(line);
      lines.forEach(members => {
        let x = M, tall = 0;
        members.forEach(([bl, f]) => {
          const bw = inner * f - (f < 1 ? G / 2 : 0), top = y; let cy = top;
          if (spec.labels && (bl.label || bl.sub)) { if (bl.label) cy += text(bl.label, x, cy, font(T.label, 600), strong, bw); if (bl.sub) cy += text(bl.sub, x, cy, font(T.sub, 400), soft, bw); cy += G * 0.3; }
          const pw = bl.panel ? (bl.images.length ? Math.max(bw * 0.26, Math.min(bw, 300 * unit)) : bw) : 0, iw = bl.images.length ? bw - pw - (pw ? G : 0) : 0;
          let high = 0;
          if (bl.images.length) {
            const ratio = bl.images.map(im => im.img.naturalWidth / im.img.naturalHeight), n = ratio.length;
            /* One height for the whole row of pictures: what fills the width, but no taller than a sensible part of the sheet and never larger than the smallest picture really is. */
            const h = Math.max(8, Math.min((iw - G * (n - 1)) / ratio.reduce((a, c) => a + c, 0), W * 0.46, ...bl.images.map(im => im.img.naturalHeight)));
            const total = ratio.reduce((a, c) => a + c * h, 0) + G * (n - 1); let ix = x + (spec.align === 'left' ? 0 : spec.align === 'right' ? iw - total : (iw - total) / 2);
            bl.images.forEach((im, i) => { const w = ratio[i] * h; items.push({ type: 'image', img: im.img, id: im.id, x: Math.round(ix), y: Math.round(cy), w: Math.round(w), h: Math.round(h) });
              if (spec.labels && im.caption) { ctx.font = font(T.caption, 500); items.push({ type: 'text', text: im.caption, x: Math.round(ix + (w - ctx.measureText(im.caption).width) / 2), y: Math.round(cy + h + T.caption * 0.35), font: font(T.caption, 500), color: soft }); }
              ix += w + G; });
            high = h + (spec.labels && bl.images.some(im => im.caption) ? T.caption * 1.7 : 0);
          }
          if (bl.panel) {
            const px = x + (bl.images.length ? iw + G : 0), pad = spec.panelStyle === 'boxed' ? 16 * unit : 0, start = items.length; let py = cy + pad;
            if (bl.panel.label) py += text(bl.panel.label, px + pad, py, font(T.label, 700), strong, pw - 2 * pad);
            if (bl.panel.sub) py += text(bl.panel.sub, px + pad, py, font(T.sub, 500), soft, pw - 2 * pad);
            if (bl.panel.label || bl.panel.sub) py += 8 * unit;
            bl.panel.lines.forEach(l => { py += text(l.name.toUpperCase(), px + pad, py, font(T.body * 0.72, 600), soft, pw - 2 * pad); py += text(l.value, px + pad, py, font(T.body, 400), strong, pw - 2 * pad) + 6 * unit; });
            const ph = py - cy + pad; if (spec.panelStyle === 'boxed') items.splice(start, 0, { type: 'box', x: Math.round(px), y: Math.round(cy), w: Math.round(pw), h: Math.round(ph), stroke: faint, line: Math.max(1, 2 * unit) });
            high = Math.max(high, ph);
          }
          tall = Math.max(tall, cy + high - top); x += bw + G;
        });
        y += tall + G;
      });
    });
    const natural = Math.round(y - G + M), height = spec.height > 0 ? spec.height : natural, scale = Math.min(1, height / natural);
    return { width: W, height, natural, scale, background: spec.background, items };
  }
  function draw(pl) {
    const c = document.createElement('canvas'); c.width = pl.width; c.height = pl.height; const g = c.getContext('2d');
    if (pl.background) { g.fillStyle = pl.background; g.fillRect(0, 0, c.width, c.height); }
    g.save(); g.translate((pl.width - pl.width * pl.scale) / 2, 0); g.scale(pl.scale, pl.scale);       // a sheet set shorter than its content is shrunk as a whole, never squashed
    g.textBaseline = 'top'; g.imageSmoothingQuality = 'high';
    pl.items.forEach(it => {
      if (it.type === 'image') g.drawImage(it.img, it.x, it.y, it.w, it.h);
      else if (it.type === 'text') { g.font = it.font; g.fillStyle = it.color; g.fillText(it.text, it.x, it.y); }
      else if (it.type === 'rect') { g.fillStyle = it.fill; g.fillRect(it.x, it.y, it.w, it.h); }
      else if (it.type === 'box') { g.strokeStyle = it.stroke; g.lineWidth = it.line; g.strokeRect(it.x, it.y, it.w, it.h); }
    });
    g.restore(); return c;
  }
  return { plan, draw, length, toCm, split };
})();
