const { withGradleProperties } = require("@expo/config-plugins");

module.exports = function withGradleMemory(config) {
  return withGradleProperties(config, (cfg) => {
    const set = (key, value) => {
      const existing = cfg.modResults.find(
        (p) => p.type === "property" && p.key === key
      );
      if (existing) existing.value = value;
      else cfg.modResults.push({ type: "property", key, value });
    };
    set(
      "org.gradle.jvmargs",
      "-Xmx6g -XX:MaxMetaspaceSize=2g -XX:+HeapDumpOnOutOfMemoryError -Dfile.encoding=UTF-8"
    );
    return cfg;
  });
};
