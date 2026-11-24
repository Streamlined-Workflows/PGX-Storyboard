three.js 0.180.0 (MIT, see LICENSE), copied from the npm package `three` so the app works with no internet connection.

- `three.module.min.js`, `three.core.min.js`: `build/` unchanged.
- `OrbitControls.js`: `examples/jsm/controls/OrbitControls.js` with one change, its import reads
  `./three.module.min.js` instead of `three`.

To update: copy the same three files from a newer package and make the same one-line change.
