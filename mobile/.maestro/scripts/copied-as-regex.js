// Store the last copyTextFrom value as a regex-escaped literal → output[KEY].
// Maestro text selectors are regexes, and track titles carry ( ) [ ] . etc.
// Usage: - runScript: { file: scripts/copied-as-regex.js, env: { KEY: "title" } }
output[KEY] = maestro.copiedText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
