/* A ZIP file made in the browser, for exports. Files are stored as they are, without compression (the pictures are
 * PNGs, which are already compressed), so this needs no library.
 *   ZipStore.build([{ path: 'Views/Front.png', data: Uint8Array }]) -> Blob
 */
window.ZipStore = (function () {
  'use strict';
  const TABLE = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc = bytes => { let c = 0xFFFFFFFF; for (let i = 0; i < bytes.length; i++) c = TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  function build(entries) {
    const now = new Date(), time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1), date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    const parts = [], central = []; let offset = 0;
    entries.forEach(e => {
      const name = new TextEncoder().encode(e.path), sum = crc(e.data), head = new DataView(new ArrayBuffer(30));
      head.setUint32(0, 0x04034b50, true); head.setUint16(4, 20, true); head.setUint16(6, 0x0800, true);      // 0x0800: the name is UTF-8
      head.setUint16(8, 0, true); head.setUint16(10, time, true); head.setUint16(12, date, true); head.setUint32(14, sum, true);
      head.setUint32(18, e.data.length, true); head.setUint32(22, e.data.length, true); head.setUint16(26, name.length, true); head.setUint16(28, 0, true);
      parts.push(new Uint8Array(head.buffer), name, e.data);
      const dir = new DataView(new ArrayBuffer(46));
      dir.setUint32(0, 0x02014b50, true); dir.setUint16(4, 20, true); dir.setUint16(6, 20, true); dir.setUint16(8, 0x0800, true); dir.setUint16(10, 0, true);
      dir.setUint16(12, time, true); dir.setUint16(14, date, true); dir.setUint32(16, sum, true); dir.setUint32(20, e.data.length, true); dir.setUint32(24, e.data.length, true);
      dir.setUint16(28, name.length, true); dir.setUint32(42, offset, true);
      central.push(new Uint8Array(dir.buffer), name); offset += 30 + name.length + e.data.length;
    });
    const size = central.reduce((n, c) => n + c.length, 0), end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true); end.setUint32(12, size, true); end.setUint32(16, offset, true);
    return new Blob([...parts, ...central, new Uint8Array(end.buffer)], { type: 'application/zip' });
  }
  return { build };
})();
