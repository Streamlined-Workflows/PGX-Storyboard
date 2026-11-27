/* The 3D Generation view: a three.js scene that shows a stored FBX exactly as it is, for looking at and checking.
 * Nothing here changes a file. Everything it holds (camera, what is hidden, shading) lasts only while the page is open.
 *
 *   const view = create({ grids: { x: false, y: true, z: false } });
 *   holder.append(view.element);                     // the same element can be put back after the page is redrawn
 *   await view.load(arrayBuffer)   -> { parts: [{ id, name }], size: [x, y, z], step }     parts are the file's model nodes
 *   view.clear()
 *   view.look('front' | 'back' | 'left' | 'right' | 'top' | 'bottom' | 'perspective')
 *   view.setProjection('perspective' | 'orthographic')   keeps the angle and the framing
 *   view.frame(id?)                                  fit everything, or one part, in the picture
 *   view.setShading('solid' | 'wire' | 'both');  view.setPalette(on)      one colour per part, to tell parts apart
 *   view.setHidden(ids);  view.isolate(id | null);  view.select(id | null)
 *   view.setDefects([{ model, polygons: [[x, y, z, …], …] }]);  view.showDefects(on)     faulty faces, drawn in the danger colour
 *   view.setGrid('x', true);  view.grids();  view.dispose()
 *
 * Grids: X is the upright plane facing along X, Y is the floor, Z is the upright plane facing along Z. Y is up and the
 * front of an asset faces +Z, so the Front view looks from +Z. Colours are the theme's tokens, read when the view is made.
 *
 * Files are untrusted. An FBX can name pictures anywhere on the internet; this view never fetches them. Only data held
 * inside the file itself is read.
 */
import * as THREE from '../vendor/three/three.module.min.js';
import { OrbitControls } from '../vendor/three/OrbitControls.js';
import { FBXLoader } from '../vendor/three/FBXLoader.js';

const LOOKS = { front: [0, 0, 1], back: [0, 0, -1], left: [-1, 0, 0], right: [1, 0, 0], top: [0, 1, 0.0001], bottom: [0, -1, 0.0001], perspective: [0.55, 0.42, 0.72] };

export function create({ grids = {} } = {}) {
  const element = document.createElement('div'); element.className = 's3-view';
  const css = getComputedStyle(document.documentElement);
  const token = name => new THREE.Color(css.getPropertyValue(name).trim() || css.getPropertyValue('--swift-text-muted').trim() || 'gray');
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.domElement.tabIndex = 0;
  renderer.domElement.setAttribute('aria-label', '3D view. Drag to turn, right-drag to move, scroll to zoom. The buttons above set named views.');
  element.append(renderer.domElement);

  const scene = new THREE.Scene();
  const persp = new THREE.PerspectiveCamera(40, 16 / 9, 0.01, 100000), ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, -100000, 100000);
  let camera = persp;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x333333, 2.4));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5); scene.add(sun);

  const colour = { line: token('--swift-text-muted'), x: token('--swift-axis-x'), y: token('--swift-axis-y'), z: token('--swift-axis-z'), plain: token('--swift-gray-400'),
    select: token('--swift-green'), danger: token('--swift-danger'), wire: token('--swift-gray-300'),
    parts: ['--swift-green-400', '--swift-amber-400', '--swift-gray-300', '--swift-green-600', '--swift-amber', '--swift-gray-500', '--swift-green-300'].map(token) };

  /* ----- grids and axes, rebuilt to suit the size of what is shown ----- */
  const guides = new THREE.Group(); scene.add(guides);
  const on = { x: !!grids.x, y: grids.y !== false, z: !!grids.z };
  let plane = {}, step = 1, extent = 10;
  function buildGuides() {
    guides.clear();
    const make = () => { const g = new THREE.GridHelper(extent, Math.round(extent / step), colour.line, colour.line); g.material.transparent = true; g.material.opacity = 0.3; return g; };
    plane = { x: make(), y: make(), z: make() };
    plane.x.rotation.z = Math.PI / 2; plane.z.rotation.x = Math.PI / 2;
    Object.entries(plane).forEach(([k, g]) => { g.visible = on[k]; guides.add(g); });
    [['x', [1, 0, 0]], ['y', [0, 1, 0]], ['z', [0, 0, 1]]].forEach(([k, d]) => {
      const pts = [new THREE.Vector3(...d).multiplyScalar(-extent / 2), new THREE.Vector3(...d).multiplyScalar(extent / 2)];
      guides.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: colour[k] })));
    });
  }
  buildGuides();

  /* ----- what is shown ----- */
  let shown = null, parts = new Map(), meshes = [], box = new THREE.Box3(new THREE.Vector3(-1, 0, -1), new THREE.Vector3(1, 2, 1));
  let shading = 'solid', palette = false, hidden = new Set(), isolated = null, selected = null, defectsOn = true;
  const marks = new THREE.Group(), outline = new THREE.Box3Helper(new THREE.Box3(), colour.select); outline.visible = false; scene.add(outline);
  const solid = c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.85, metalness: 0, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  const wire = () => new THREE.MeshBasicMaterial({ color: colour.wire, wireframe: true });

  const idOf = o => { for (let p = o; p && p !== shown; p = p.parent) if (p.userData.part) return p.userData.part; return null; };
  const within = (o, id) => { for (let p = o; p && p !== shown; p = p.parent) if (p.userData.part === id) return true; return false; };
  function paint() {
    meshes.forEach((m, i) => {
      const part = idOf(m), base = palette ? colour.parts[m.userData.order % colour.parts.length] : colour.plain;
      let off = isolated != null && !within(m, isolated);
      for (let p = m; p && p !== shown && !off; p = p.parent) if (p.userData.part && hidden.has(p.userData.part)) off = true;
      m.visible = !off;
      m.material = shading === 'wire' ? m.userData.wire : m.userData.solid;
      m.userData.solid.color.copy(base);
      m.userData.over.visible = shading === 'both';
      void part; void i;
    });
    marks.visible = defectsOn;
    const target = selected != null ? [...parts.entries()].find(([id]) => id === selected) : null;
    if (target) { const b = new THREE.Box3().setFromObject(target[1]); outline.visible = !b.isEmpty(); if (outline.visible) outline.box.copy(b); } else outline.visible = false;
    render();
  }

  function clear() {
    if (shown) { scene.remove(shown); shown.traverse(o => { if (o.geometry) o.geometry.dispose(); }); }
    shown = null; parts = new Map(); meshes = []; hidden = new Set(); isolated = null; selected = null; marks.clear(); outline.visible = false;
    render();
  }

  async function load(buffer) {
    clear();
    const manager = new THREE.LoadingManager();
    manager.setURLModifier(url => /^(blob:|data:)/.test(url) ? url : 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==');
    manager.onError = () => {};
    const group = new FBXLoader(manager).parse(buffer, '');
    group.animations = [];
    let order = 0;
    group.traverse(o => {
      if (o.ID != null && o !== group) { o.userData.part = String(o.ID); parts.set(String(o.ID), o); }
      if (o.isMesh) {
        if (!o.geometry.getAttribute('normal')) o.geometry.computeVertexNormals();      // a file without normals would otherwise draw black
        o.userData.order = order++; o.userData.solid = solid(colour.plain); o.userData.wire = wire(); o.material = o.userData.solid; o.frustumCulled = false;
        const over = new THREE.LineSegments(new THREE.WireframeGeometry(o.geometry), new THREE.LineBasicMaterial({ color: colour.wire, transparent: true, opacity: 0.55 }));
        over.userData.overlay = true; over.visible = false; o.userData.over = over; o.add(over);
        meshes.push(o);
      } else if (o.isLight || o.isCamera) o.visible = false;
    });
    shown = group; scene.add(group); group.add(marks);
    group.updateMatrixWorld(true);
    box = new THREE.Box3().setFromObject(group);
    if (box.isEmpty()) box.set(new THREE.Vector3(-1, 0, -1), new THREE.Vector3(1, 2, 1));
    const size = box.getSize(new THREE.Vector3()), biggest = Math.max(size.x, size.y, size.z, 1e-6);
    step = Math.pow(10, Math.floor(Math.log10(biggest / 2)));
    extent = Math.max(10, Math.ceil(biggest * 2 / step / 2) * 2) * step;
    buildGuides();
    look('perspective');
    paint();
    return { parts: [...parts.entries()].map(([id, o]) => ({ id, name: o.name })), size: size.toArray(), step };
  }

  function setDefects(list) {
    marks.clear();
    (list || []).forEach(d => {
      const owner = parts.get(String(d.model)); if (!owner || !d.polygons || !d.polygons.length) return;
      const flat = [], edge = [];
      d.polygons.forEach(p => { const n = p.length / 3;
        for (let i = 1; i < n - 1; i++) flat.push(p[0], p[1], p[2], p[i * 3], p[i * 3 + 1], p[i * 3 + 2], p[i * 3 + 3], p[i * 3 + 4], p[i * 3 + 5]);
        for (let i = 0; i < n; i++) { const j = (i + 1) % n; edge.push(p[i * 3], p[i * 3 + 1], p[i * 3 + 2], p[j * 3], p[j * 3 + 1], p[j * 3 + 2]); } });
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
      const e = new THREE.BufferGeometry(); e.setAttribute('position', new THREE.Float32BufferAttribute(edge, 3));
      const face = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: colour.danger, side: THREE.DoubleSide, transparent: true, opacity: 0.8, depthTest: false }));
      const lines = new THREE.LineSegments(e, new THREE.LineBasicMaterial({ color: colour.danger, depthTest: false }));
      face.renderOrder = lines.renderOrder = 5;
      const hold = new THREE.Group(); hold.add(face, lines);
      owner.updateWorldMatrix(true, false);                      // marks live beside the model, so place them where its mesh is
      hold.applyMatrix4(new THREE.Matrix4().copy(shown.matrixWorld).invert().multiply(owner.matrixWorld));
      marks.add(hold);
    });
    render();
  }

  /* ----- cameras ----- */
  const controls = new OrbitControls(camera, renderer.domElement);
  let queued = false;
  const render = () => { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; sun.position.copy(camera.position); renderer.render(scene, camera); }); };
  controls.addEventListener('change', render);
  const aspect = () => (element.clientWidth || 16) / (element.clientHeight || 9);
  const distance = () => camera.position.distanceTo(controls.target);
  function sizeOrtho(d) { const h = d * Math.tan(THREE.MathUtils.degToRad(persp.fov / 2)); ortho.top = h; ortho.bottom = -h; ortho.left = -h * aspect(); ortho.right = h * aspect(); ortho.updateProjectionMatrix(); }
  function setProjection(kind) {
    const want = kind === 'orthographic' ? ortho : persp; if (want === camera) return;
    const dir = camera.position.clone().sub(controls.target).normalize(), d = camera === ortho ? ortho.userData.d / ortho.zoom : distance();
    want.position.copy(controls.target).addScaledVector(dir, d); want.quaternion.copy(camera.quaternion); want.up.copy(camera.up);
    if (want === ortho) { ortho.zoom = 1; ortho.userData.d = d; sizeOrtho(d); }
    camera = want; controls.object = camera; controls.update(); render();
  }
  function place(dir, b) {
    const sphere = b.getBoundingSphere(new THREE.Sphere()), r = Math.max(sphere.radius, 1e-4);
    const d = r / Math.sin(THREE.MathUtils.degToRad(persp.fov / 2)) * 1.15;
    controls.target.copy(sphere.center);
    camera.position.copy(sphere.center).addScaledVector(dir.clone().normalize(), d);
    camera.up.set(0, 1, 0);
    persp.near = d / 1000; persp.far = d * 1000; persp.updateProjectionMatrix();
    if (camera === ortho) { ortho.zoom = 1; ortho.userData.d = d; sizeOrtho(d); }
    controls.update(); render();
  }
  function look(name) { place(new THREE.Vector3(...(LOOKS[name] || LOOKS.perspective)), box); }
  function frame(id) {
    const o = id != null ? parts.get(String(id)) : null, b = o ? new THREE.Box3().setFromObject(o) : box.clone();
    place(camera.position.clone().sub(controls.target), b.isEmpty() ? box : b);
  }
  const fit = () => { const w = element.clientWidth, h = element.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); persp.aspect = w / h; persp.updateProjectionMatrix(); if (camera === ortho) sizeOrtho(ortho.userData.d || distance()); render(); };
  const watch = new ResizeObserver(fit); watch.observe(element);
  look('perspective');

  return {
    element, load, clear, look, frame, setProjection, setDefects,
    projection: () => camera === ortho ? 'orthographic' : 'perspective',
    setShading(kind) { shading = ['solid', 'wire', 'both'].includes(kind) ? kind : 'solid'; paint(); },
    setPalette(v) { palette = !!v; paint(); },
    setHidden(ids) { hidden = new Set((ids || []).map(String)); paint(); },
    isolate(id) { isolated = id == null ? null : String(id); paint(); },
    select(id) { selected = id == null ? null : String(id); paint(); },
    showDefects(v) { defectsOn = !!v; paint(); },
    grids: () => ({ ...on }),
    setGrid(k, v) { if (k in on) { on[k] = !!v; if (plane[k]) plane[k].visible = on[k]; render(); } },
    dispose() { watch.disconnect(); controls.dispose(); renderer.dispose(); element.remove(); },
    _debug: () => ({ camera: camera.position.toArray().map(n => +n.toFixed(3)), target: controls.target.toArray().map(n => +n.toFixed(3)), projection: camera === ortho ? 'orthographic' : 'perspective',
      size: [renderer.domElement.width, renderer.domElement.height], calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, meshes: meshes.length, visible: meshes.filter(m => m.visible).length,
      parts: parts.size, marks: marks.children.length, step, extent, outline: outline.visible, shading, palette }),
  };
}
