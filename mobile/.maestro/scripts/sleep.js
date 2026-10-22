// Maestro has no plain sleep; busy-wait MS milliseconds.
// Usage: - runScript: { file: scripts/sleep.js, env: { MS: "4000" } }
var until = Date.now() + parseInt(MS, 10);
while (Date.now() < until) { /* wait */ }
