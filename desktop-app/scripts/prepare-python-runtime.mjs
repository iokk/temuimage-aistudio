import { spawnSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const distDir = path.join(root, ".dist");
const runtimeDir = path.join(distDir, "python-runtime");
const pythonRequirements = path.join(root, "python", "requirements.txt");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    ...options,
  });
  if (result.status !== 0) {
    throw new Error(`Command failed: ${command} ${args.join(" ")}`);
  }
}

async function rm(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function ensureDir(target) {
  await fs.mkdir(target, { recursive: true });
}

async function writeManifest() {
  const manifest = {
    pythonExecutable: "bin/python3.12",
    createdAt: new Date().toISOString(),
    source: "python3.12 -m venv --copies",
    requirementsFile: "requirements.txt",
  };
  await fs.writeFile(
    path.join(runtimeDir, "runtime-manifest.json"),
    JSON.stringify(manifest, null, 2),
    "utf8"
  );
}

async function main() {
  await ensureDir(distDir);
  await rm(runtimeDir);
  run("python3.12", ["-m", "venv", "--copies", runtimeDir], { cwd: root });
  run(path.join(runtimeDir, "bin", "python"), ["-m", "pip", "install", "-r", pythonRequirements], {
    cwd: root,
  });
  await writeManifest();
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
