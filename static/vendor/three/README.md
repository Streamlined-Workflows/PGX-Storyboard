three.js 0.180.0 (MIT, see LICENSE), copied from the npm package `three` so the app works with no internet connection.

- `three.module.min.js`, `three.core.min.js`: `build/` unchanged.
- `OrbitControls.js`: `examples/jsm/controls/OrbitControls.js` with one change, its import reads
  `./three.module.min.js` instead of `three`.

To update: copy the same files from a newer package and make the same import changes.
- `FBXLoader.js`: `examples/jsm/loaders/FBXLoader.js`; its imports read `./three.module.min.js`, `./fflate.module.js`
  and `./NURBSCurve.js`.
- `NURBSCurve.js`, `NURBSUtils.js`: `examples/jsm/curves/`; imports changed the same way.
- `fflate.module.js`: `examples/jsm/libs/fflate.module.js` unchanged (fflate, MIT; its licence notice is at the top of the file).
