import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const outDir = path.join(root, "client", "electron", "out");

function findPackagedResourcesRoot() {
  const entries = fs.readdirSync(outDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const candidate = path.join(outDir, entry.name);
    const appEntries = fs.readdirSync(candidate, { withFileTypes: true });
    for (const appEntry of appEntries) {
      if (appEntry.isDirectory() && appEntry.name.endsWith(".app")) {
        return path.join(candidate, appEntry.name, "Contents", "Resources");
      }
    }
  }
  throw new Error("No packaged .app bundle found under client/electron/out");
}

const packagedAppRoot = findPackagedResourcesRoot();

const requiredFiles = [
  path.join(packagedAppRoot, "renderer", "index.html"),
  path.join(packagedAppRoot, "python-bundle", "main.py"),
  path.join(packagedAppRoot, "python-bundle", "runtime-manifest.json"),
  path.join(packagedAppRoot, "python-runtime", "bin", "python3.12"),
  path.join(packagedAppRoot, "python-runtime", "runtime-manifest.json"),
];

const missing = requiredFiles.filter((file) => !fs.existsSync(file));

if (missing.length) {
  console.error("Packaged app verification failed. Missing files:");
  for (const file of missing) {
    console.error(`- ${file}`);
  }
  process.exit(1);
}

console.log("Packaged app verification passed.");
for (const file of requiredFiles) {
  console.log(`- ${path.relative(root, file)}`);
}
