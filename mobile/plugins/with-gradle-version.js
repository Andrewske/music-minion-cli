const { withGradleProperties } = require("@expo/config-plugins");
const fs = require("fs");
const path = require("path");

module.exports = function withGradleVersion(config) {
  return withGradleProperties(config, (cfg) => {
    const wrapperPath = path.join(
      cfg.modRequest.platformProjectRoot,
      "gradle",
      "wrapper",
      "gradle-wrapper.properties"
    );
    if (fs.existsSync(wrapperPath)) {
      let content = fs.readFileSync(wrapperPath, "utf-8");
      content = content.replace(
        /gradle-\d+\.\d+(\.\d+)?-bin\.zip/,
        "gradle-8.13-bin.zip"
      );
      fs.writeFileSync(wrapperPath, content);
    }
    return cfg;
  });
};
