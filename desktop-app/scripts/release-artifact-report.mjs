import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const makeDir = path.join(root, "client", "electron", "out", "make");

function collectFiles(directory) {
  const results = [];
  if (!fs.existsSync(directory)) {
    return results;
  }
  const entries = fs.readdirSync(directory, { withFileTypes: true });
  for (const entry of entries) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectFiles(target));
    } else if (entry.isFile()) {
      results.push(target);
    }
  }
  return results;
}

function sha256(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

const files = collectFiles(makeDir)
  .filter((file) => file.endsWith(".dmg") || file.endsWith(".zip"))
  .sort();

if (!files.length) {
  console.error("No release artifacts found under client/electron/out/make");
  process.exit(1);
}

const report = files.map((file) => {
  const stat = fs.statSync(file);
  return {
    file: path.relative(root, file),
    size_bytes: stat.size,
    sha256: sha256(file),
  };
});

console.log(
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      artifacts: report,
    },
    null,
    2
  )
);
