// Parse the last copyTextFrom value ("m:ss") into seconds → output[KEY].
// Usage:
//   - copyTextFrom: { id: "seek-position" }
//   - runScript: { file: scripts/clock-to-seconds.js, env: { KEY: "pos" } }
var parts = maestro.copiedText.trim().split(':');
output[KEY] = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
