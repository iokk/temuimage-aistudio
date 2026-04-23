const path = require("path");

module.exports = {
  packagerConfig: {
    asar: true,
    executableName: "EcommerceWorkbenchDesktop",
    appBundleId: "com.ecommerce.workbench.desktop",
    extraResource: [
      path.resolve(__dirname, "../../.dist/renderer"),
      path.resolve(__dirname, "../../.dist/python-bundle"),
      path.resolve(__dirname, "../../.dist/python-runtime"),
    ]
  },
  rebuildConfig: {},
  makers: [
    {
      name: "@electron-forge/maker-dmg",
      platforms: ["darwin"],
      config: {
        format: "ULFO"
      }
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"]
    }
  ]
};
