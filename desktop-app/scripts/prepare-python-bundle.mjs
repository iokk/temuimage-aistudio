import fs from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const sourcePythonDir = path.join(root, "python");
const sourceRendererDir = path.join(root, "client", "renderer", "dist");
const distDir = path.join(root, ".dist");
const bundleDir = path.join(distDir, "python-bundle");
const rendererBundleDir = path.join(distDir, "renderer");

async function rm(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function ensureDir(target) {
  await fs.mkdir(target, { recursive: true });
}

async function copyDir(source, destination) {
  await ensureDir(destination);
  const entries = await fs.readdir(source, { withFileTypes: true });
  for (const entry of entries) {
    if (
      entry.name === "__pycache__" ||
      entry.name === ".DS_Store" ||
      entry.name.endsWith(".pyc")
    ) {
      continue;
    }
    const sourcePath = path.join(source, entry.name);
    const destinationPath = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      await copyDir(sourcePath, destinationPath);
    } else if (entry.isFile()) {
      if (entry.name.endsWith(".pyc")) {
        continue;
      }
      await fs.copyFile(sourcePath, destinationPath);
    }
  }
}

async function writeManifest() {
  const manifest = {
    entrypoint: "main.py",
    requiredPython: "3.12",
    bundleCreatedAt: new Date().toISOString(),
    notes: [
      "python-bundle contains application source and requirements for packaged desktop builds.",
      "A future packaging step should place a bundled Python runtime in Resources/python-runtime.",
    ],
  };
  await fs.writeFile(
    path.join(bundleDir, "runtime-manifest.json"),
    JSON.stringify(manifest, null, 2),
    "utf8"
  );
}

async function main() {
  await ensureDir(distDir);
  await rm(bundleDir);
  await rm(rendererBundleDir);
  await copyDir(sourcePythonDir, bundleDir);
  await writeManifest();

  try {
    await copyDir(sourceRendererDir, rendererBundleDir);
  } catch (error) {
    throw new Error(
      "Renderer dist is missing. Run `npm run build:renderer` before preparing package assets."
    );
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
