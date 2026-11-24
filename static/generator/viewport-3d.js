/* The 3D view of the Asset Generator: a three.js scene you can turn, move and zoom, with a grid that can be switched
 * on for each axis.
 *
 *   X grid: the upright plane that faces along X (it spans Y and Z)
 *   Y grid: the floor (it spans X and Z; Y is up, as three.js has it)
 *   Z grid: the upright plane that faces along Z (it spans X and Y)
 *
 * Colours come from the theme's tokens, read from the page when the view is made, so a theme restyles it.
 * Nothing is drawn on a timer: the picture is redrawn only when the view moves, a grid changes or the box changes size.
 *
 *   const view = create({ grids: { x: false, y: true, z: false } });
 *   holder.append(view.element);       // the same element can be put back after the page is redrawn
 *   view.setGrid('x', true); view.resetView(); view.setObject(object3D or null); view.dispose();
 */
import * as THREE from '../vendor/three/three.module.min.js';
import { OrbitControls } from '../vendor/three/OrbitControls.js';

const SIZE = 10, DIVISIONS = 10;          // each grid is 10 units across with a line every unit

export function create({ grids = {} } = {}) {
  const element = document.createElement('div'); element.className = 'ag-view3d';
  const token = (name, fallback) => new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.domElement.setAttribute('aria-label', '3D view. Drag to turn, right-drag to move, scroll to zoom.');
  element.append(renderer.domElement);

  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(45, 16 / 9, 0.05, 500);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x222222, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(4, 8, 6); scene.add(sun);

  /* One grid per axis. GridHelper is made lying flat (the Y grid); the other two are that grid stood up. */
  const line = token('--swift-text-muted', '#9ca3af'), axis = { x: token('--swift-axis-x', '#f87171'), y: token('--swift-axis-y', '#4ade80'), z: token('--swift-axis-z', '#fbbf24') };
  const plane = { x: new THREE.GridHelper(SIZE, DIVISIONS, line, line), y: new THREE.GridHelper(SIZE, DIVISIONS, line, line), z: new THREE.GridHelper(SIZE, DIVISIONS, line, line) };
  plane.x.rotation.z = Math.PI / 2; plane.z.rotation.x = Math.PI / 2;
  Object.entries(plane).forEach(([k, g]) => { g.material.transparent = true; g.material.opacity = 0.35; g.visible = !!grids[k]; scene.add(g); });
  /* The three axes, always shown, each in its own token colour, so the grids can be told apart. */
  const axes = new THREE.Group();
  [['x', [1, 0, 0]], ['y', [0, 1, 0]], ['z', [0, 0, 1]]].forEach(([k, d]) => {
    const points = [new THREE.Vector3(...d).multiplyScalar(-SIZE / 2), new THREE.Vector3(...d).multiplyScalar(SIZE / 2)];
    axes.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: axis[k] })));
  });
  scene.add(axes);

  /* Until 3D generation exists there is nothing of the project's to show, so a plain one-unit cube stands on the floor for scale. */
  const placeholder = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: token('--swift-text-muted', '#9ca3af'), roughness: 0.8 }));
  placeholder.position.y = 0.5;
  let shown = placeholder; scene.add(shown);

  const controls = new OrbitControls(camera, renderer.domElement);
  let queued = false;
  const render = () => { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; renderer.render(scene, camera); }); };
  controls.addEventListener('change', render);
  const resetView = () => { camera.position.set(5, 4, 7); controls.target.set(0, 0.5, 0); controls.update(); render(); };
  const fit = () => { const w = element.clientWidth, h = element.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render(); };
  const watch = new ResizeObserver(fit); watch.observe(element);
  resetView();

  return {
    element,
    grids: () => ({ x: plane.x.visible, y: plane.y.visible, z: plane.z.visible }),
    setGrid(k, on) { if (plane[k]) { plane[k].visible = !!on; render(); } },
    resetView,
    setObject(object) { scene.remove(shown); shown = object || placeholder; scene.add(shown); render(); },
    dispose() { watch.disconnect(); controls.dispose(); renderer.dispose(); element.remove(); },
    _debug: () => ({ camera: camera.position.toArray(), size: [renderer.domElement.width, renderer.domElement.height], calls: renderer.info.render.calls }),
  };
}
